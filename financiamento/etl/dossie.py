"""Dossiê de uma empresa fornecedora — a "Análise profunda" da página de redes.

Junta, para a raiz de um CNPJ, o que já está no cache e o que as fontes públicas dão
pelo CNPJ, sem chave e sem IA:

* **TCE-ES — instrumentos contratuais** (recorte de `etl/instrumentos.py`): os contratos
  da empresa em todos os setores, com modalidade, base legal, valores e os links do
  contrato, da publicação e do edital. Daí saem os sinais estruturados: adesão a ata
  ("carona"), emergência, dispensa, inexigibilidade, contrato sem modalidade;
* **TCE-ES — itens contratados** (`tcees_itens.csv`): o preço unitário de cada item
  comparado com o MESMO item (descrição e unidade) em outros municípios;
* **TCE-ES — obras** (`tcees_obras_educacao.csv`): situação, medições, aditivos;
* **Redes** (`grafos.json`): o empenhado na Educação por município, ano e mercado;
* **Receita Federal** via BrasilAPI (ou minhareceita): sócios, abertura, capital, CNAE;
* **Sanções**: CEIS e CNEP (arquivos do dia, da CGU) e a certidão consolidada do TCU;
* **PNCP**: contratos publicados com a empresa como fornecedora e os arquivos de cada um;
* **Querido Diário**: menções ao CNPJ (só Vitória, Serra e Vila Velha têm diário coletado).

Cada resposta crua fica em ``dados/bruto/analises/<raiz>/`` com URL, instante e SHA-256;
o dossiê montado, em ``dados/analises/<raiz>/dossie.json``. Pedir de novo devolve o que
está gravado — só ``atualizar=True`` vai às fontes outra vez. Uma fonte que falha vira
aviso; as outras seguem.

Nada aqui afirma irregularidade: são sinais para orientar a verificação.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import statistics
import time
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import pandas as pd
import requests

from .config import BRUTO, PASTA, PROCESSADO
from .parsing import norm

PASTA_RESULTADOS = PASTA / "dados" / "analises"
PASTA_CRUS = BRUTO / "analises"
UA = {"User-Agent": "neduc-financiamento/1.0 (prototipo de analise; contato: NEDUC)"}
ESQUEMA = 1
#: Municípios com diário coletado pelo Querido Diário (medido em 26/10/2026).
QD_COBERTOS = {3205309: "Vitória", 3205002: "Serra", 3205200: "Vila Velha"}
Progresso = Callable[[str], None]


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fmt_cnpj(d: str) -> str:
    d = re.sub(r"\D", "", d or "")
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else d


# ------------------------------------------------------------------ rede (com cache cru)
class Coletor:
    """GET com cache em disco: o corpo e um .meta.json (URL, instante, status, SHA-256)."""

    def __init__(self, raiz: str, atualizar: bool = False):
        self.pasta = PASTA_CRUS / raiz
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.atualizar = atualizar
        self.sessao = requests.Session()
        self.sessao.headers.update(UA)
        self.fontes: list[dict[str, Any]] = []

    def get(self, nome: str, url: str, *, accept: str | None = None, timeout: float = 150, tentativas: int = 2,
            pasta: Path | None = None) -> tuple[int | None, bytes, dict]:
        pasta = pasta or self.pasta
        corpo_p, meta_p = pasta / nome, pasta / (nome + ".meta.json")
        if corpo_p.exists() and meta_p.exists() and not self.atualizar:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            # Falha de rede ou HTTP de erro é tentada de novo; resposta recebida (inclusive uma
            # recusa do órgão) é reaproveitada — não se insiste em quem recusou.
            if meta.get("status") is not None and meta["status"] < 500 and not meta.get("erro"):
                self.fontes.append({**meta, "cache": True})
                return meta.get("status"), corpo_p.read_bytes(), meta
        erro, r = None, None
        for i in range(tentativas):
            try:
                r = self.sessao.get(url, timeout=timeout, headers={"Accept": accept} if accept else None, allow_redirects=True)
                erro = None
                break
            except requests.RequestException as exc:
                erro = f"{type(exc).__name__}: {exc}"[:300]
                time.sleep(5 * (i + 1))
        corpo = r.content if r is not None else b""
        meta = {"nome": nome, "url": url, "url_final": r.url if r is not None else None, "status": r.status_code if r is not None else None,
                "obtido_em": _agora(), "sha256": hashlib.sha256(corpo).hexdigest() if corpo else None, "bytes": len(corpo),
                "content_type": r.headers.get("content-type") if r is not None else None, "erro": erro,
                "arquivo": str(corpo_p.relative_to(BRUTO).as_posix())}
        pasta.mkdir(parents=True, exist_ok=True)
        corpo_p.write_bytes(corpo)
        meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        self.fontes.append(meta)
        return meta["status"], corpo, meta


def _json(corpo: bytes) -> Any:
    try:
        return json.loads(corpo.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


# ------------------------------------------------------------------ fontes externas
def cadastro(col: Coletor, cnpj: str) -> dict[str, Any]:
    for nome, url in (("cadastro_brasilapi.json", f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"),
                      ("cadastro_minhareceita.json", f"https://minhareceita.org/{cnpj}")):
        st, corpo, meta = col.get(nome, url, timeout=60)
        d = _json(corpo) if st == 200 else None
        if isinstance(d, dict) and d.get("razao_social"):
            return {"status": "ok", "fonte": urlparse(url).netloc, "q": meta["sha256"],
                    "razao_social": d.get("razao_social"), "nome_fantasia": d.get("nome_fantasia"),
                    "data_inicio_atividade": d.get("data_inicio_atividade"), "situacao": d.get("descricao_situacao_cadastral"),
                    "data_situacao": d.get("data_situacao_cadastral"), "cnae": f"{d.get('cnae_fiscal')} — {d.get('cnae_fiscal_descricao')}",
                    "cnaes_secundarios": [f"{c.get('codigo')} — {c.get('descricao')}" for c in (d.get("cnaes_secundarios") or [])][:12],
                    "capital_social": d.get("capital_social"), "porte": d.get("porte"), "natureza_juridica": d.get("natureza_juridica"),
                    "municipio": d.get("municipio"), "uf": d.get("uf"), "simples": d.get("opcao_pelo_simples"), "mei": d.get("opcao_pelo_mei"),
                    "socios": [{"nome": s.get("nome_socio"), "qualificacao": s.get("qualificacao_socio"), "desde": s.get("data_entrada_sociedade"),
                                "faixa_etaria": s.get("faixa_etaria")} for s in (d.get("qsa") or [])]}
    return {"status": "indisponivel", "motivo": "BrasilAPI e minhareceita não responderam com o cadastro"}


def _zip_sancoes(col: Coletor, tipo: str) -> tuple[bytes | None, dict | None]:
    """O arquivo do dia mais recente (a CGU publica um por dia; tenta até 7 dias para trás)."""
    pasta = PASTA_CRUS / "_sancoes"
    for d in range(0, 8):
        dia = (date.today() - timedelta(days=d)).strftime("%Y%m%d")
        st, corpo, meta = col.get(f"{tipo}_{dia}.zip", f"https://portaldatransparencia.gov.br/download-de-dados/{tipo}/{dia}", timeout=120, tentativas=1, pasta=pasta)
        if st == 200 and corpo[:2] == b"PK":
            return corpo, meta
    return None, None


def sancoes(col: Coletor, cnpjs: list[str], raiz: str) -> dict[str, Any]:
    saida: dict[str, Any] = {}
    for tipo in ("ceis", "cnep"):
        corpo, meta = _zip_sancoes(col, tipo)
        if corpo is None:
            saida[tipo] = {"status": "indisponivel"}
            continue
        achados = []
        with zipfile.ZipFile(io.BytesIO(corpo)) as z:
            nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(nome) as f:
                for l in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";"):
                    doc = re.sub(r"\D", "", l.get("CPF OU CNPJ DO SANCIONADO") or "")
                    if len(doc) == 14 and (doc in cnpjs or doc[:8] == raiz):
                        achados.append({k: l.get(k) for k in ("NOME DO SANCIONADO", "CATEGORIA DA SANÇÃO", "DATA INÍCIO SANÇÃO", "DATA FINAL SANÇÃO",
                                                              "ÓRGÃO SANCIONADOR", "UF ÓRGÃO SANCIONADOR", "FUNDAMENTAÇÃO LEGAL", "VALOR DA MULTA") if k in l})
        saida[tipo] = {"status": "ok", "arquivo_do_dia": meta["url"].rsplit("/", 1)[-1], "q": meta["sha256"], "registros": achados}
    return saida


def tcu(col: Coletor, cnpj: str) -> dict[str, Any]:
    st, corpo, meta = col.get("tcu_certidao.json", f"https://certidoes-apf.apps.tcu.gov.br/api/rest/publico/certidoes/{cnpj}", accept="application/json", timeout=60)
    if b"firewall" in corpo[:2000].lower():
        # O firewall do TCU recusou a consulta. Não se contorna: fica registrado, e a certidão
        # é emitida à mão no site do Tribunal.
        return {"status": "bloqueado", "motivo": "recusado pelo firewall de aplicações do TCU",
                "consulta_manual": "https://certidoes-apf.apps.tcu.gov.br/"}
    d = _json(corpo) if st == 200 else None
    if not isinstance(d, dict):
        return {"status": "indisponivel", "motivo": f"HTTP {st}"}
    return {"status": "ok", "q": meta["sha256"], "certidoes": [{"tipo": c.get("tipo"), "descricao": c.get("descricao"), "situacao": c.get("situacao"),
                                                               "emitida_em": c.get("dataHoraEmissao")} for c in d.get("certidoes", [])]}


def pncp(col: Coletor, cnpj: str, limite_arquivos: int = 25) -> dict[str, Any]:
    url = f"https://pncp.gov.br/api/search/?q={cnpj}&tipos_documento=contrato&pagina=1&tam_pagina=100"
    st, corpo, meta = col.get("pncp_contratos.json", url, timeout=150, tentativas=5)   # a busca do PNCP derruba ~2/3 das conexões
    d = _json(corpo) if st == 200 else None
    if not isinstance(d, dict):
        return {"status": "indisponivel", "motivo": meta.get("erro") or f"HTTP {st}"}
    contratos = []
    # A busca não é filtro exato: fica só o que tem a empresa como fornecedora.
    for x in d.get("items", []):
        if re.sub(r"\D", "", x.get("fornecedor_ni") or "") != cnpj:
            continue
        m = re.match(r"/contratos/(\d{14})/(\d{4})/(\d+)", x.get("item_url") or "")
        contratos.append({"titulo": x.get("title"), "objeto": x.get("description"), "orgao": x.get("orgao_nome"), "municipio": x.get("municipio_nome"),
                          "uf": x.get("uf"), "ano": x.get("ano"), "valor": _float(x.get("valor_global")), "assinatura": x.get("data_assinatura"),
                          "vigencia": [x.get("data_inicio_vigencia"), x.get("data_fim_vigencia")], "modalidade": x.get("modalidade_licitacao_nome"),
                          "amparo": x.get("amparo_legal_nome"), "controle": x.get("numero_controle_pncp"),
                          "pagina": f"https://pncp.gov.br/app/contratos/{m.group(1)}/{m.group(2)}/{m.group(3)}" if m else None,
                          "_chave": m.groups() if m else None, "arquivos": []})
    for c in contratos[:limite_arquivos]:
        if not c["_chave"]:
            continue
        o, a, s = c["_chave"]
        st2, corpo2, _ = col.get(f"pncp_arquivos_{o}_{a}_{s}.json", f"https://pncp.gov.br/api/pncp/v1/orgaos/{o}/contratos/{a}/{s}/arquivos", timeout=90)
        lista = _json(corpo2) if st2 == 200 else []
        for arq in lista or []:
            c["arquivos"].append({"titulo": arq.get("titulo"), "tipo": arq.get("tipoDocumentoNome"), "url": arq.get("url") or
                                  f"https://pncp.gov.br/api/pncp/v1/orgaos/{o}/contratos/{a}/{s}/arquivos/{arq.get('sequencialDocumento')}",
                                  "publicado": arq.get("dataPublicacaoPncp")})
        time.sleep(0.5)
    for c in contratos:
        c.pop("_chave", None)
    return {"status": "ok", "q": meta["sha256"], "total_busca": d.get("total"), "contratos": contratos}


def diarios(col: Coletor, cnpj: str) -> dict[str, Any]:
    frase = f'"{fmt_cnpj(cnpj)}"'
    achados, falhas = [], 0
    for cod, nome in QD_COBERTOS.items():
        st, corpo, _ = col.get(f"qd_{cod}.json", f"https://queridodiario.ok.org.br/api/gazettes?querystring={requests.utils.quote(frase)}&territory_ids={cod}&size=20&excerpt_size=300", timeout=60)
        d = _json(corpo) if st == 200 else None
        if not isinstance(d, dict):
            falhas += 1
            continue
        for g in d.get("gazettes", []):
            achados.append({"municipio": nome, "data": g.get("date"), "url": g.get("url"), "trechos": [re.sub(r"\s+", " ", t)[:300] for t in (g.get("excerpts") or [])[:2]]})
    return {"status": "ok" if falhas < len(QD_COBERTOS) else "indisponivel", "cobertura": list(QD_COBERTOS.values()),
            "mencoes": sorted(achados, key=lambda x: x["data"] or "", reverse=True)}


def _float(v: Any) -> float | None:
    try:
        x = float(str(v).replace(",", ".")) if not isinstance(v, (int, float)) else float(v)
        return x
    except (TypeError, ValueError):
        return None


def _num_br(v: str) -> float | None:
    s = str(v or "").strip()
    if not s:
        return None
    try:
        return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)
    except ValueError:
        return None


# ------------------------------------------------------------------ dados locais
def especifico(u: str) -> bool:
    """Link que aponta um documento, e não a página inicial de um portal."""
    if not isinstance(u, str) or not u.startswith("http"):
        return False
    p = urlparse(u)
    if p.query and re.search(r"\d{3,}", p.query):
        return True
    return bool(re.search(r"\.pdf$|/pdf/|visualizacoes|/arquivos?/|/download|\d{4,}", (p.path or "").rstrip("/") + (p.fragment or ""), re.I))


def url_dioes(u: str) -> str:
    """Visualizador do DOM-ES com página (``…/visualizacoes/pdf/7474/#/p:9``) → PDF só daquela página."""
    m = re.search(r"ioes\.dio\.es\.gov\.br/portal/visualizacoes/pdf/(\d+).*?p:(\d+)", u or "")
    return f"https://ioes.dio.es.gov.br/apifront/portal/edicoes/pdf_diario/{m.group(1)}/{m.group(2)}" if m else u


def classificar_base_legal(modalidade: str, base: str, objeto: str, arp: str) -> str | None:
    """Sinal estruturado do contrato (não é irregularidade: é o que vale ler primeiro)."""
    b, o = norm(base), norm(objeto)
    if "adesao" in o or "carona" in o or (arp and not modalidade):
        return "adesao_ata"
    if re.search(r"art\.? ?75,? (inciso )?viii|art\.? ?24,? (inciso )?iv\b|emergenc", b + " " + o):
        return "emergencia"
    if re.search(r"art\.? ?74|art\.? ?25\b|inexigib", b):
        return "inexigibilidade"
    if re.search(r"art\.? ?75|art\.? ?24\b|dispensa", b):
        return "dispensa"
    if not modalidade:
        return "sem_modalidade"
    return None


ROTULO_SINAL = {"adesao_ata": "adesão a ata de registro de preços (carona)", "emergencia": "contratação emergencial",
                "inexigibilidade": "inexigibilidade de licitação", "dispensa": "dispensa de licitação",
                "sem_modalidade": "sem modalidade nem base legal informadas"}


def contratos_tcees(raiz: str) -> dict[str, Any]:
    from .instrumentos import carregar
    d = carregar()
    if d.empty:
        return {"status": "indisponivel", "motivo": "recorte dos instrumentos contratuais ainda não coletado (python -m financiamento.etl.instrumentos)"}
    e = d[d["raiz"] == raiz]
    linhas = []
    for r in e.to_dict("records"):
        sinal = classificar_base_legal(r["ModalidadeLicitacao"], r["BaseLegalContratacao"], r["ObjetoInstrumento"] + " " + r["ObjetoContratacao"], r["NumeroArp"])
        linhas.append({"municipio": r["NomeEsferaAdministrativa"], "ug": r["NomeUnidadeGestoraCadastro"], "contratacao": r["IdentificacaoContratacao"],
                       "numero": f"{r['NumeroInstrumentoContratacao']}/{r['AnoInstrumentoContratacao']}", "objeto": (r["ObjetoInstrumento"] or r["ObjetoContratacao"])[:400],
                       "modalidade": r["ModalidadeLicitacao"], "base_legal": r["BaseLegalContratacao"], "arp": f"{r['NumeroArp']}/{r['AnoArp']}" if r["NumeroArp"] else "",
                       "tipo": r["TipoInstrumento"], "situacao": r["SituacaoInstrumento"], "setor": r["SetorBeneficiado"], "assinatura": r["DataAssinaturaInstrumentoContratacao"],
                       "vigencia": [r["InicioVigenciaContrato"], r["FimVigenciaContrato"]], "valor_inicial": _num_br(r["ValorTotalContratacaoInstrumento"]),
                       "valor_atual": _num_br(r["ValorAtualContratacaoInstrumento"]), "url_contrato": r["UrlInstrumentoContratacao"],
                       "url_publicacao": r["UrlPublicacaoInstrumentoContratacao"], "url_edital": r["UrlEdital"], "chave": r["ChaveInstrumento"], "sinal": sinal})
    linhas.sort(key=lambda x: (x["assinatura"] or ""), reverse=True)
    sinais = Counter(x["sinal"] for x in linhas if x["sinal"])
    fonte = e.iloc[0] if len(e) else d.iloc[0]
    return {"status": "ok", "q": ";".join(sorted(set(d["_sha256"]))), "fonte": sorted(set(d["_recurso"])), "contratos": linhas,
            "resumo": {"contratos": len(linhas), "municipios": len({x["municipio"] for x in linhas}),
                       "valor_atual": round(sum(x["valor_atual"] or 0 for x in linhas), 2),
                       "sinais": {k: {"rotulo": ROTULO_SINAL[k], "contratos": n} for k, n in sinais.most_common()},
                       "com_link_contrato": sum(especifico(x["url_contrato"]) for x in linhas)},
            "_obtido_em": fonte.get("_obtido_em")}


@lru_cache(maxsize=1)
def _itens() -> pd.DataFrame:
    it = pd.read_csv(PROCESSADO / "tcees_itens.csv", dtype=str, keep_default_na=False,
                     usecols=["cod_ibge", "ano", "contratacao", "descricao", "unidade", "quantidade", "valor_unitario", "valor_total", "cnpj_contratada", "contratada"])
    it["raiz"] = it["cnpj_contratada"].str.replace(r"\D", "", regex=True).str[:8]
    it["vu"] = pd.to_numeric(it["valor_unitario"], errors="coerce")
    it["chave_item"] = it["descricao"].map(lambda s: re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", norm(s))).strip()[:70]) + " | " + it["unidade"].map(norm)
    return it


def precos(raiz: str, nomes_mun: dict[int, str], limite: int = 40) -> dict[str, Any]:
    """Preço unitário da empresa × o mesmo item (descrição + unidade) contratado em outros municípios."""
    it = _itens()
    meus = it[(it["raiz"] == raiz) & (it["vu"] > 0)]
    if meus.empty:
        return {"status": "ok", "itens_da_empresa": 0, "comparaveis": []}
    outros = it[(it["raiz"] != raiz) & (it["vu"] > 0) & it["chave_item"].isin(set(meus["chave_item"]))]
    ref = outros.groupby("chave_item").agg(mediana=("vu", "median"), municipios=("cod_ibge", "nunique"), n=("vu", "size"), minimo=("vu", "min"), maximo=("vu", "max"))
    comp = []
    for r in meus.itertuples(index=False):
        if r.chave_item not in ref.index:
            continue
        x = ref.loc[r.chave_item]
        if x["municipios"] < 3:
            continue
        comp.append({"descricao": r.descricao[:160], "unidade": r.unidade, "municipio": nomes_mun.get(int(r.cod_ibge), r.cod_ibge), "ano": r.ano,
                     "contratacao": r.contratacao, "quantidade": _float(r.quantidade), "preco": round(float(r.vu), 4), "mediana_outros": round(float(x["mediana"]), 4),
                     "razao": round(float(r.vu) / float(x["mediana"]), 2) if x["mediana"] else None, "municipios_outros": int(x["municipios"]),
                     "faixa_outros": [round(float(x["minimo"]), 4), round(float(x["maximo"]), 4)],
                     "diferenca_total": round((float(r.vu) - float(x["mediana"])) * (_float(r.quantidade) or 0), 2)})
    comp.sort(key=lambda c: -(c["diferenca_total"] or 0))
    return {"status": "ok", "itens_da_empresa": int(len(meus)), "comparaveis_total": len(comp),
            "acima_2x": sum(1 for c in comp if (c["razao"] or 0) >= 2), "comparaveis": comp[:limite],
            "regra": "mesmo item = mesma descrição normalizada (70 primeiros caracteres) e mesma unidade; referência = mediana dos outros fornecedores, só com 3+ municípios"}


def obras(raiz: str, nomes_mun: dict[int, str]) -> list[dict[str, Any]]:
    o = pd.read_csv(PROCESSADO / "tcees_obras_educacao.csv", dtype=str, keep_default_na=False)
    o = o[o["cnpj_contratado"].str.replace(r"\D", "", regex=True).str[:8] == raiz]
    return [{"municipio": nomes_mun.get(int(r["cod_ibge"]), r["cod_ibge"]) if r["cod_ibge"].isdigit() else r["cod_ibge"], "objeto": r["objeto"][:300],
             "situacao": r["situacao"], "valor": _float(r["valor"]), "valor_medido": _float(r["valor_medido"]), "pct_medido": _float(r["pct_medido"]),
             "aditivos": _float(r["aditivos"]), "ultima_medicao": r["ultima_medicao"], "url_contrato": r["url_contrato"], "url_edital": r["url_edital"],
             "chave": r["chave"]} for r in o.to_dict("records")]


@lru_cache(maxsize=1)
def _grafos() -> dict:
    return json.loads((PROCESSADO / "grafos.json").read_text(encoding="utf-8"))


def rede(raiz: str) -> dict[str, Any]:
    g = _grafos()
    fc = g["fornecedores"]["colunas"]
    idx = next((i for i, l in enumerate(g["fornecedores"]["linhas"]) if l[0] == raiz), None)
    if idx is None:
        return {"status": "fora_da_rede"}
    f = dict(zip(fc, g["fornecedores"]["linhas"][idx]))
    anos, mercados, mun = g["meta"]["anos"], [m["id"] for m in g["meta"]["mercados"]], g["municipios"]
    rot = {m["id"]: m["rotulo"] for m in g["meta"]["mercados"]}
    por_mun, por_ano, por_merc = defaultdict(float), defaultdict(float), defaultdict(float)
    a = g["arestas"]
    for i in range(len(a["f"])):
        if a["f"][i] != idx:
            continue
        v = a["v"][i]
        for j in range(0, len(v), 4):
            por_mun[mun[a["m"][i]]["nome"]] += v[j + 2]
            por_ano[anos[v[j]]] += v[j + 2]
            por_merc[rot[mercados[a["k"][i]]]] += v[j + 2]
    return {"status": "ok", "nome": f["nome"], "tipo": f["tipo"], "cnpjs": f["cnpjs"].split(";") if f["cnpjs"] else [],
            "empenhado": round(sum(por_ano.values()), 2), "por_ano": {str(k): round(v, 2) for k, v in sorted(por_ano.items())},
            "por_municipio": dict(sorted(((k, round(v, 2)) for k, v in por_mun.items()), key=lambda x: -x[1])),
            "por_mercado": dict(sorted(((k, round(v, 2)) for k, v in por_merc.items()), key=lambda x: -x[1])),
            "q": ";".join(x for x in g["meta"]["q_empenhos"].values() if x)}


# ------------------------------------------------------------------ inventário de documentos
def inventario(dossie: dict[str, Any]) -> list[dict[str, Any]]:
    """Os documentos que dá para tentar baixar, com prioridade (contratos de maior valor primeiro)."""
    docs: dict[str, dict] = {}

    def add(url: str, tipo: str, ref: str, valor: float | None, origem: str, municipio: str = "") -> None:
        if not especifico(url):
            return
        u = url_dioes(url.strip())
        if u in docs:
            return
        docs[u] = {"id": "d" + hashlib.sha1(u.encode()).hexdigest()[:8], "url": u, "url_original": url.strip(), "tipo": tipo,
                   "referencia": ref, "municipio": municipio, "valor": valor, "origem": origem}

    for c in (dossie.get("contratos", {}).get("contratos") or []):
        ref = f"contrato {c['numero']} — {c['municipio']}"
        add(c["url_contrato"], "contrato", ref, c["valor_atual"], "TCE-ES (instrumentos contratuais)", c["municipio"])
        add(c["url_publicacao"], "publicação do contrato", ref, c["valor_atual"], "TCE-ES (instrumentos contratuais)", c["municipio"])
        add(c["url_edital"], "edital", ref, c["valor_atual"], "TCE-ES (instrumentos contratuais)", c["municipio"])
    for o in dossie.get("obras") or []:
        ref = f"obra — {o['municipio']}: {o['objeto'][:60]}"
        add(o["url_contrato"], "contrato de obra", ref, o["valor"], "TCE-ES (obras)", o["municipio"])
        add(o["url_edital"], "edital de obra", ref, o["valor"], "TCE-ES (obras)", o["municipio"])
    for c in (dossie.get("pncp", {}).get("contratos") or []):
        for a in c["arquivos"]:
            add(a["url"], f"PNCP: {a.get('tipo') or 'arquivo'}", f"{c['titulo']} — {c['municipio']}", c["valor"], "PNCP", c.get("municipio") or "")
    for r in (dossie.get("faltantes") or {}).get("itens") or []:   # achados pela busca dos documentos faltantes
        c = r["contrato"]
        for rota in r["rotas"]:
            for doc in rota.get("documentos") or []:
                add(doc["url"], doc["tipo"], f"contrato {c['numero']} — {c['municipio']}" + (f" ({doc['titulo']})" if doc.get("titulo") else ""),
                    c["valor_atual"], rota["rota"], c["municipio"])
    ordem = {"contrato": 0, "contrato de obra": 0, "publicação do contrato": 2, "edital": 1, "edital de obra": 1, "extrato no DOM-ES": 1}
    return sorted(docs.values(), key=lambda d: (ordem.get(d["tipo"], 0 if d["tipo"].startswith("PNCP") else 3), -(d["valor"] or 0)))


# ------------------------------------------------------------------ montagem
def caminho(raiz: str) -> Path:
    return PASTA_RESULTADOS / raiz / "dossie.json"


def ler(raiz: str) -> dict[str, Any] | None:
    p = caminho(raiz)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def montar(raiz: str, atualizar: bool = False, progresso: Progresso | None = None, repetir_falhas: bool = False) -> dict[str, Any]:
    """O dossiê da empresa. Se já existe e não se pediu atualizar, devolve o gravado — sem ir à rede.

    `repetir_falhas`: remonta reaproveitando as respostas do cache e indo à rede só onde a
    conexão falhou. `atualizar`: vai de novo a todas."""
    raiz = re.sub(r"\D", "", raiz)[:8]
    if not atualizar and not repetir_falhas and (salvo := ler(raiz)) is not None:
        return {**salvo, "_reaproveitado": True}
    passo = progresso or (lambda _t: None)
    g = _grafos()
    nomes_mun = {m["cod"]: m["nome"] for m in g["municipios"]}
    col = Coletor(raiz, atualizar=atualizar)
    d: dict[str, Any] = {"meta": {"esquema": ESQUEMA, "raiz": raiz, "gerado_em": _agora(), "avisos": []}}

    def etapa(nome: str, rotulo: str, funcao: Callable[[], Any]) -> None:
        passo(rotulo)
        try:
            d[nome] = funcao()
        except Exception as exc:  # fonte isolada: falha vira aviso
            d[nome] = {"status": "erro", "motivo": f"{type(exc).__name__}: {exc}"[:300]}
            d["meta"]["avisos"].append(f"{rotulo}: {type(exc).__name__}")

    etapa("rede", "Empenhos nas redes (cache local)", lambda: rede(raiz))
    cnpjs = d["rede"].get("cnpjs") if isinstance(d["rede"], dict) else None
    if not cnpjs:
        cnpjs = sorted({re.sub(r"\D", "", x) for x in _itens().loc[_itens()["raiz"] == raiz, "cnpj_contratada"]}) or [raiz + "000100"]
    matriz = next((c for c in cnpjs if c[8:12] == "0001"), cnpjs[0])
    d["meta"].update({"cnpjs": cnpjs, "cnpj_consultado": matriz})
    etapa("contratos", "Contratos no TCE-ES (instrumentos contratuais)", lambda: contratos_tcees(raiz))
    etapa("obras", "Obras da Educação (TCE-ES)", lambda: obras(raiz, nomes_mun))
    etapa("precos", "Preços unitários × outros municípios", lambda: precos(raiz, nomes_mun))
    etapa("cadastro", "Cadastro na Receita (BrasilAPI)", lambda: cadastro(col, matriz))
    etapa("sancoes", "Sanções: CEIS e CNEP (CGU)", lambda: sancoes(col, cnpjs, raiz))
    etapa("tcu", "Certidão consolidada do TCU", lambda: tcu(col, matriz))
    etapa("pncp", "Contratos no PNCP", lambda: pncp(col, matriz))
    etapa("diarios", "Menções em diários oficiais (Querido Diário)", lambda: diarios(col, matriz))
    nome = (d["rede"].get("nome") if isinstance(d["rede"], dict) else None) or (d["cadastro"].get("razao_social") if isinstance(d["cadastro"], dict) else None) or raiz
    d["meta"]["nome"] = nome
    if (anterior := ler(raiz)) and anterior.get("faltantes"):   # remontar não descarta a busca dos faltantes
        d["faltantes"] = anterior["faltantes"]
    passo("Inventário de documentos")
    d["documentos"] = inventario(d)
    d["fontes"] = [{k: f.get(k) for k in ("nome", "url", "status", "obtido_em", "sha256", "bytes", "arquivo", "erro", "cache")} for f in col.fontes]
    caminho(raiz).parent.mkdir(parents=True, exist_ok=True)
    caminho(raiz).write_text(json.dumps(d, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return d
