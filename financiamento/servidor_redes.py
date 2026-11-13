"""Servidor local do protótipo das redes: serve a página e as duas ações do dossiê.

    python -m financiamento.servidor_redes            # da raiz do repositório: http://127.0.0.1:8765
    python servidor_redes.py --abrir                  # ou de dentro de financiamento/
    python -m financiamento.servidor_redes --abrir    # e abre o navegador

* **Análise profunda** — monta o dossiê da empresa (`etl/dossie.py`): o que o cache já tem
  e as fontes públicas pelo CNPJ. Não usa IA. Fica gravado em ``dados/analises/<raiz>/``.
* **Procurar documentos faltantes** — para os maiores contratos cujo link no TCE-ES é
  genérico, procura no PNCP (por órgão) e varre o Diário Oficial dos Municípios
  (`etl/documentos_faltantes.py`); o que acha entra no inventário que a IA lê.
* **Análise com IA** — lê os documentos do dossiê com o Claude (`etl/analise_ia.py`). Antes
  de gastar, a página mostra a estimativa de tokens e de custo e pede confirmação.

**Nada é descartado e nada é refeito sem pedido.** Pedir o dossiê ou a análise de novo
devolve o que está gravado, sem ir às fontes e sem tokens. Só "Atualizar dossiê" e
"Refazer análise" vão de novo — e a análise anterior fica no histórico.

A chave da API fica só aqui: ANTHROPIC_API_KEY no ambiente (ou `ant auth login`). O servidor
escuta só em 127.0.0.1 e recusa chamada sem o cabeçalho ``X-Redes`` ou com outro Host — uma
página de fora aberta no navegador não consegue disparar uma análise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import traceback
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

# Rodado como arquivo (`python servidor_redes.py`, de dentro de financiamento/), a raiz do
# repositório não está no caminho de busca — e o pacote `financiamento` não seria achado.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from financiamento.etl import analise_ia as IA
from financiamento.etl import documentos_faltantes as F
from financiamento.etl import dossie as D

PASTA = Path(__file__).resolve().parent
PAGINA = PASTA / "redes_financiamento.html"
PORTA = 8765

TAREFAS: dict[str, dict[str, Any]] = {}
EM_CURSO: dict[str, str] = {}          # (tipo, raiz) → id da tarefa em andamento
TRAVA = threading.Lock()


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def iniciar_tarefa(chave: str, funcao: Callable[[Callable[[str], None]], Any]) -> str:
    """Roda `funcao(progresso)` numa thread. Mesma chave em andamento → devolve a mesma tarefa."""
    with TRAVA:
        if chave in EM_CURSO and TAREFAS[EM_CURSO[chave]]["estado"] == "rodando":
            return EM_CURSO[chave]
        tid = uuid.uuid4().hex[:12]
        TAREFAS[tid] = {"id": tid, "chave": chave, "estado": "rodando", "etapas": [], "inicio": _agora(), "resultado": None, "erro": None}
        EM_CURSO[chave] = tid

    def progresso(texto: str) -> None:
        TAREFAS[tid]["etapas"].append({"em": _agora(), "texto": texto})

    def rodar() -> None:
        try:
            TAREFAS[tid]["resultado"] = funcao(progresso)
            TAREFAS[tid]["estado"] = "pronto"
        except Exception as exc:
            TAREFAS[tid].update(estado="erro", erro=f"{type(exc).__name__}: {exc}")
            traceback.print_exc()
        TAREFAS[tid]["fim"] = _agora()

    threading.Thread(target=rodar, daemon=True).start()
    return tid


def _raiz(s: str) -> str | None:
    d = re.sub(r"\D", "", s)
    return d[:8] if len(d) >= 8 else None


# ------------------------------------------------------------------ ações
def estado_ia(raiz: str) -> dict[str, Any]:
    return {"ultima": IA.com_normas(raiz, IA.ultima(raiz)), "historico": IA.historico(raiz)}


def tarefa_estimar(raiz: str, modelo: str) -> Callable:
    def f(progresso):
        d = D.montar(raiz, progresso=progresso)          # reaproveita o dossiê gravado
        docs = IA.baixar_documentos(d, progresso=progresso)
        pedido = IA.preparar(d, docs)
        progresso("Contando os tokens")
        est = IA.estimar(pedido, modelo)
        return {"estimativa": est, "documentos_usados": pedido["usados"], "documentos_fora": pedido["fora"],
                "ja_analisado": IA.gravada(raiz, pedido["hash_pedido"]) is not None, "credencial": IA.credencial_disponivel()}
    return f


def tarefa_analisar(raiz: str, refazer: bool, modelo: str) -> Callable:
    def f(progresso):
        return IA.com_normas(raiz, IA.analisar(raiz, refazer=refazer, modelo=modelo, progresso=progresso))
    return f


# ------------------------------------------------------------------ HTTP
class Manipulador(BaseHTTPRequestHandler):
    server_version = "redes-neduc/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # menos ruído no console
        if not self.path.startswith("/api/tarefa/"):
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def _json(self, codigo: int, corpo: Any) -> None:
        dados = json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _seguro(self) -> bool:
        """Só chamada da própria página: Host local e o cabeçalho X-Redes (que outra origem não manda sem CORS)."""
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost") or self.headers.get("X-Redes") != "1":
            self._json(403, {"erro": "chamada recusada: use a página servida por este servidor"})
            return False
        return True

    def _corpo(self) -> dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(min(n, 100_000)).decode("utf-8"))
        except ValueError:
            return {}

    def do_GET(self) -> None:
        caminho = self.path.split("?")[0]
        if caminho in ("/", "/redes_financiamento.html"):
            if not PAGINA.exists():
                return self._json(404, {"erro": "redes_financiamento.html não existe — rode python -m financiamento.build_grafos"})
            dados = PAGINA.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)
            return
        if caminho == "/novo_dashboard.html" and (PASTA / "novo_dashboard.html").exists():
            dados = (PASTA / "novo_dashboard.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)
            return
        if not caminho.startswith("/api/"):
            return self._json(404, {"erro": "não encontrado"})
        if not self._seguro():
            return
        if caminho == "/api/status":
            return self._json(200, {"servidor": True, "ia_disponivel": IA.credencial_disponivel(), "modelo": IA.MODELO_PADRAO})
        if m := re.fullmatch(r"/api/tarefa/(\w+)", caminho):
            t = TAREFAS.get(m.group(1))
            return self._json(200 if t else 404, t or {"erro": "tarefa não encontrada"})
        if m := re.fullmatch(r"/api/dossie/(\d{8,14})", caminho):
            d = D.ler(_raiz(m.group(1)))
            return self._json(200 if d else 404, d or {"existe": False})
        if m := re.fullmatch(r"/api/ia/(\d{8,14})", caminho):
            return self._json(200, estado_ia(_raiz(m.group(1))))
        return self._json(404, {"erro": "rota não encontrada"})

    def do_POST(self) -> None:
        caminho = self.path.split("?")[0]
        if not caminho.startswith("/api/") or not self._seguro():
            return None if caminho.startswith("/api/") else self._json(404, {"erro": "não encontrado"})
        corpo = self._corpo()
        if m := re.fullmatch(r"/api/dossie/(\d{8,14})", caminho):
            raiz, atualizar, falhas = _raiz(m.group(1)), bool(corpo.get("atualizar")), bool(corpo.get("repetir_falhas"))
            if not atualizar and not falhas and (d := D.ler(raiz)) is not None:
                return self._json(200, {"pronto": True, "resultado": {**d, "_reaproveitado": True}})
            tid = iniciar_tarefa(f"dossie:{raiz}", lambda p: D.montar(raiz, atualizar=atualizar, repetir_falhas=falhas, progresso=p))
            return self._json(202, {"tarefa": tid})
        if m := re.fullmatch(r"/api/faltantes/(\d{8,14})", caminho):
            raiz, refazer = _raiz(m.group(1)), bool(corpo.get("refazer"))
            if not refazer and (d := D.ler(raiz)) is not None and d.get("faltantes"):
                return self._json(200, {"pronto": True, "resultado": {**d, "_reaproveitado": True}})
            tid = iniciar_tarefa(f"faltantes:{raiz}", lambda p: F.buscar(raiz, progresso=p, refazer=refazer))
            return self._json(202, {"tarefa": tid})
        if m := re.fullmatch(r"/api/ia/(\d{8,14})/estimar", caminho):
            raiz = _raiz(m.group(1))
            return self._json(202, {"tarefa": iniciar_tarefa(f"estimar:{raiz}", tarefa_estimar(raiz, corpo.get("modelo") or IA.MODELO_PADRAO))})
        if m := re.fullmatch(r"/api/ia/(\d{8,14})/normas/estimar", caminho):
            raiz = _raiz(m.group(1))
            if IA.ultima(raiz) is None:
                return self._json(404, {"erro": "não há análise gravada"})
            return self._json(200, {"estimativa": IA.estimar_normas(raiz, corpo.get("modelo") or IA.MODELO_PADRAO), "credencial": IA.credencial_disponivel()})
        if m := re.fullmatch(r"/api/ia/(\d{8,14})/normas", caminho):
            # Base normativa de uma análise antiga: já feita → devolve; senão, só com confirmação e credencial.
            raiz = _raiz(m.group(1))
            u = IA.com_normas(raiz, IA.ultima(raiz))
            if u is None:
                return self._json(404, {"erro": "não há análise gravada"})
            if u.get("_complemento_normas"):
                return self._json(200, {"pronto": True, "resultado": {**u, "_reaproveitada": True}})
            if not corpo.get("confirmado"):
                return self._json(409, {"erro": "confirme a estimativa de custo antes de chamar a IA"})
            if not IA.credencial_disponivel():
                return self._json(412, {"erro": "sem credencial da Anthropic: defina ANTHROPIC_API_KEY e reinicie o servidor"})
            modelo = corpo.get("modelo") or IA.MODELO_PADRAO
            return self._json(202, {"tarefa": iniciar_tarefa(f"normas:{raiz}", lambda p: IA.complementar_normas(raiz, modelo=modelo, progresso=p))})
        if m := re.fullmatch(r"/api/ia/(\d{8,14})", caminho):
            raiz, refazer = _raiz(m.group(1)), bool(corpo.get("refazer"))
            # Já existe análise e não se pediu para refazer: devolve a gravada — nenhum token.
            if not refazer and (u := IA.com_normas(raiz, IA.ultima(raiz))) is not None:
                return self._json(200, {"pronto": True, "resultado": {**u, "_reaproveitada": True}})
            if not corpo.get("confirmado"):
                return self._json(409, {"erro": "confirme a estimativa de custo antes de chamar a IA"})
            if not IA.credencial_disponivel():
                return self._json(412, {"erro": "sem credencial da Anthropic: defina ANTHROPIC_API_KEY e reinicie o servidor"})
            tid = iniciar_tarefa(f"ia:{raiz}", tarefa_analisar(raiz, refazer, corpo.get("modelo") or IA.MODELO_PADRAO))
            return self._json(202, {"tarefa": tid})
        return self._json(404, {"erro": "rota não encontrada"})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Servidor local das redes (protótipo): página + Análise profunda + Análise com IA.")
    ap.add_argument("--porta", type=int, default=PORTA)
    ap.add_argument("--abrir", action="store_true", help="abre a página no navegador")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    srv = ThreadingHTTPServer(("127.0.0.1", args.porta), Manipulador)
    url = f"http://127.0.0.1:{args.porta}/"
    print(f"Servidor das redes em {url}  (Ctrl+C para parar)")
    print("IA: " + ("credencial encontrada" if IA.credencial_disponivel() else "SEM credencial — defina ANTHROPIC_API_KEY para a Análise com IA"))
    if args.abrir:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
