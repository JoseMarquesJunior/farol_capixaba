"""ICA — Indicador Criança Alfabetizada (INEP), por município do ES.

O ICA é o indicador oficial de META do Compromisso Nacional Criança
Alfabetizada: o percentual de alunos da rede municipal, ao fim do 2º ano, acima
de 743 pontos na escala Saeb de Língua Portuguesa (definição da aba "Variáveis"
da própria planilha do INEP). Não é o Saeb amostral tradicional: a Avaliação da
Alfabetização é aplicada às redes municipais com participação de 90% a 100% dos
alunos no ES (coluna PC_AVALIADOS_LP), e o INEP publica o resultado município a
município, junto com a meta pactuada para cada ano até 2030.

Fonte: uma planilha oficial, publicada uma vez por edição, com as três últimas
taxas (2023, 2024, 2025) e as metas 2024–2030 de todos os municípios do país.
Baixá-la é trivial; o que importa é PROVAR que o arquivo lido é o publicado. Por
isso o download é verificado por SHA-256 e a coleta para — alto, sem seguir em
silêncio — se o hash divergir do esperado: o INEP pode ter republicado a
planilha, e um dado diferente sob o mesmo nome mudaria a página sem que nada
quebrasse.

Reaproveitado de https://github.com/luizmaibashi/painel-alfabetizacao-cgu
(MIT License, © 2026 Luiz Fernando Maibashi): a URL do arquivo, o SHA-256 da
edição 2025, a leitura com `header=1` (a primeira linha é o rótulo humano, a
segunda o código da variável), o descarte das linhas de rodapé sem código de
município, a rejeição de código duplicado e a política de falhar alto no hash
(`src/evaluation/05_backtest_prospectivo_2025.py` e
`reports/proveniencia_ica_2025.md` daquele repositório). O recorte para o ES, o
formato longo por ano, o "sem dado" explícito e a proveniência são deste projeto.

"Sem dado" nunca vira zero: taxa ausente na planilha vira `situacao = sem_dado`
(o INEP não publicou o valor — aplicação não realizada ou participação
insuficiente); município do ES ausente da planilha vira aviso e linhas
`sem_dado`. Na edição 2025 os 78 municípios do ES têm valor em todos os anos.

Uso avulso::

    python -m financiamento.etl.ica                  # usa o cache; baixa se não houver
    python -m financiamento.etl.ica --atualizar tudo # baixa de novo e confere o hash
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .config import BRUTO
from .proveniencia import Consulta, Registro, caminho_relativo

log = logging.getLogger(__name__)

#: Edição publicada em 2026-04-01 (data registrada no repositório de referência).
EDICAO = 2025
URL = ("https://download.inep.gov.br/avaliacao_da_alfabetizacao/resultados/"
       "resultados_e_metas_municipios_2025_3.xlsx")
#: SHA-256 do arquivo publicado, conferido em 2026-08-29 (referência) e em 2026-09-23 (aqui).
SHA256 = "709c7eeba34d9c91e7f193e6c2b25e453ec7b535a6d8ac7e39c095bd0c24eb60"
PAGINA = ("https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/"
          "avaliacao-da-alfabetizacao/resultados/2025")
PASTA_CACHE = BRUTO / "inep" / "ica"
ARQUIVO = PASTA_CACHE / URL.rsplit("/", 1)[-1]

ANOS_TAXA = (2023, 2024, 2025)
ANOS_META = (2024, 2025, 2026, 2027, 2028, 2029, 2030)
#: Colunas que a planilha PRECISA ter (nomes da segunda linha do cabeçalho).
COLUNAS_OBRIGATORIAS = ("CO_MUNICIPIO", "SG_UF", "NO_MUNICIPIO", "PC_ALUNO_ALFABETIZADO_2023",
                        "PC_ALUNO_ALFABETIZADO_2024", "PC_ALUNO_ALFABETIZADO_2025", "META_FINAL_2024",
                        "META_FINAL_2025", "META_FINAL_2026", "PC_AVALIADOS_LP")
#: Escala publicada na aba "Variáveis" da planilha: código → faixa.
NIVEIS = {0: "abaixo do nível 1 (até 40%)", 1: "nível 1 (40% a 50%)", 2: "nível 2 (50% a 60%)",
          3: "nível 3 (60% a 70%)", 4: "nível 4 (70% a 80%)", 5: "nível 5 (acima de 80%)"}
LIMIAR_SAEB = 743  # pontos na escala Saeb de LP acima dos quais o aluno conta como alfabetizado

COLUNAS_RESULTADO = ["cod_ibge", "edicao", "ano", "taxa", "meta", "nivel", "participacao", "situacao", "q"]
COLUNAS_META = ["cod_ibge", "edicao", "ano", "meta", "q"]
FONTE = "INEP — Avaliação da Alfabetização, resultados e metas por município (planilha oficial da edição 2025)"


class ErroIca(RuntimeError):
    """A fonte não pôde ser obtida ou não é a esperada (hash divergente, colunas ausentes)."""


@dataclass
class ResultadoIca:
    tabela: pd.DataFrame                      # COLUNAS_RESULTADO — uma linha por município × ano com taxa
    metas: pd.DataFrame                       # COLUNAS_META — metas pactuadas até 2030
    consultas: Registro
    avisos: list[dict[str, Any]]
    status: dict[str, Any]
    edicao: int = EDICAO
    bruto: pd.DataFrame = field(default_factory=pd.DataFrame)  # a planilha inteira (para conferência)


def sha256_de(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _baixar(url: str, destino: Path, tentativas: int = 3, pausa: float = 4.0) -> str:
    """Baixa o arquivo e devolve o instante da coleta (UTC).

    O servidor do INEP derruba a conexão de forma intermitente (WinError 10054,
    observado em 2026-08-31 pela referência e em 2026-09-23 aqui); poucas
    tentativas com espera resolvem — sem elas a coleta falharia por rede, não por
    problema da fonte.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                                               "Accept": "*/*"})
    ultimo: Exception | None = None
    for tentativa in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                dados = r.read()
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(dados)
            return _agora()
        except (urllib.error.URLError, OSError) as exc:
            ultimo = exc
            log.warning("ICA: tentativa %d/%d falhou (%s)", tentativa, tentativas, exc)
            time.sleep(pausa)
    raise ErroIca(f"não foi possível baixar a planilha do ICA após {tentativas} tentativas: {ultimo}. "
                  f"Baixe manualmente de {url} e salve em {destino}.")


def garantir_fonte(caminho: Path = ARQUIVO, url: str = URL, sha_esperado: str = SHA256, *,
                   atualizar: str = "nao") -> tuple[Path, dict[str, Any]] | None:
    """Garante a planilha no cache e devolve (caminho, metadados) — ou None em modo offline sem cache.

    Metadados ficam num `.json` ao lado do arquivo: URL, instante da coleta, tamanho
    e SHA-256 — o que permite provar de onde veio o que a página mostra.
    """
    meta_path = caminho.with_suffix(caminho.suffix + ".json")
    if atualizar == "offline":
        if not caminho.exists():
            return None
    elif atualizar == "tudo" or not caminho.exists():
        obtido_em = _baixar(url, caminho)
        meta_path.write_text(json.dumps({"url": url, "obtido_em": obtido_em, "tamanho": caminho.stat().st_size,
                                         "sha256": sha256_de(caminho)}, ensure_ascii=False, indent=1), encoding="utf-8")
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        # Arquivo já no cache sem o .json (colocado à mão, como a mensagem de erro do download
        # sugere): não se baixa de novo; o instante registrado é o da primeira leitura, e o hash
        # abaixo é o que prova que é o arquivo publicado.
        meta = {"url": url, "obtido_em": _agora(), "tamanho": caminho.stat().st_size, "sha256": sha256_de(caminho),
                "origem": "arquivo já presente no cache; instante registrado na primeira leitura"}
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    sha = sha256_de(caminho)
    if sha != sha_esperado:
        raise ErroIca(
            "SHA-256 da planilha do ICA não confere.\n"
            f"  esperado: {sha_esperado}\n  obtido:   {sha}\n  arquivo:  {caminho}\n"
            "O INEP pode ter republicado a planilha. Não seguimos em silêncio: confira a página de "
            f"resultados ({PAGINA}), atualize SHA256 em etl/ica.py de forma explícita e registre a mudança.")
    meta["sha256"] = sha
    return caminho, meta


def carregar(caminho: Path) -> pd.DataFrame:
    """Lê a planilha oficial e rejeita o que não é município (rodapé) e código duplicado."""
    bruto = pd.read_excel(caminho, sheet_name=0, header=1, dtype={"CO_MUNICIPIO": "string"})
    faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in bruto.columns]
    if faltantes:
        raise ErroIca(f"planilha do ICA sem colunas esperadas: {faltantes}")
    df = bruto.dropna(subset=["CO_MUNICIPIO"]).copy()
    df["CO_MUNICIPIO"] = df["CO_MUNICIPIO"].astype(str).str.strip().str.zfill(7)
    if df["CO_MUNICIPIO"].duplicated().any():
        raise ErroIca("planilha do ICA com código de município duplicado")
    numericas = [c for c in df.columns if c.startswith(("PC_", "META_FINAL_", "CO_NIVEL"))]
    for c in numericas:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.reset_index(drop=True)


def recortar_es(bruto: pd.DataFrame, municipios: Iterable[int], q: str, edicao: int = EDICAO
                ) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    """Formato longo (município × ano) só para os municípios do ES, com "sem dado" explícito.

    Município da lista ausente da planilha entra com `sem_dado` em todos os anos, e
    vira aviso; município da planilha (UF=ES) fora da lista também vira aviso — nunca
    é silenciado nem inventado.
    """
    esperados = {int(m) for m in municipios}
    es = bruto[bruto["SG_UF"].astype(str).str.upper() == "ES"].copy()
    es["cod_ibge"] = es["CO_MUNICIPIO"].astype(int)
    avisos: list[dict[str, Any]] = []
    fora = sorted(set(es["cod_ibge"]) - esperados)
    if fora:
        avisos.append({"aviso": f"município com UF=ES na planilha mas fora da lista de entes: {fora}"})
    ausentes = sorted(esperados - set(es["cod_ibge"]))
    if ausentes:
        avisos.append({"aviso": f"município do ES ausente da planilha do ICA (entra como sem dado): {ausentes}"})
    por_cod = {int(r.cod_ibge): r for r in es.itertuples(index=False)}

    def _num(v: Any) -> float | None:
        return None if v is None or pd.isna(v) else float(v)

    linhas: list[dict[str, Any]] = []
    metas: list[dict[str, Any]] = []
    for cod in sorted(esperados):
        r = por_cod.get(cod)
        for ano in ANOS_TAXA:
            taxa = _num(getattr(r, f"PC_ALUNO_ALFABETIZADO_{ano}", None)) if r is not None else None
            meta = _num(getattr(r, f"META_FINAL_{ano}", None)) if r is not None and ano in ANOS_META else None
            no_ano_da_edicao = r is not None and ano == edicao
            nivel = _num(getattr(r, "CO_NIVEL_ALFABETIZACAO", None)) if no_ano_da_edicao else None
            linhas.append({"cod_ibge": cod, "edicao": edicao, "ano": ano, "taxa": taxa, "meta": meta,
                           "nivel": None if nivel is None else int(nivel),
                           "participacao": _num(getattr(r, "PC_AVALIADOS_LP", None)) if no_ano_da_edicao else None,
                           "situacao": "informado" if taxa is not None else "sem_dado", "q": q})
        if r is not None:
            for ano in ANOS_META:
                m = _num(getattr(r, f"META_FINAL_{ano}", None))
                if m is not None:
                    metas.append({"cod_ibge": cod, "edicao": edicao, "ano": ano, "meta": m, "q": q})
    tabela = pd.DataFrame(linhas, columns=COLUNAS_RESULTADO)
    return tabela, pd.DataFrame(metas, columns=COLUNAS_META), avisos


def executar(municipios: Iterable[int], *, atualizar: str = "nao", caminho: Path = ARQUIVO,
             url: str = URL, sha_esperado: str = SHA256) -> ResultadoIca:
    """Coleta (ou lê do cache), verifica o hash e recorta o ES. Falha de hash levanta ErroIca."""
    municipios = sorted({int(m) for m in municipios})
    registro = Registro()
    vazio_res, vazio_meta = pd.DataFrame(columns=COLUNAS_RESULTADO), pd.DataFrame(columns=COLUNAS_META)
    fonte = garantir_fonte(caminho, url, sha_esperado, atualizar=atualizar)
    if fonte is None:
        aviso = {"aviso": "não coletado (modo offline, sem cache da planilha do ICA)"}
        return ResultadoIca(vazio_res, vazio_meta, registro, [aviso],
                            {"fonte": "INEP", "ok": True, "coletado": False, "edicao": EDICAO, "avisos": 1})
    arquivo, meta = fonte
    c = Consulta(fonte="INEP", recurso="ica_resultados_municipios", metodo="GET (download de arquivo)",
                 descricao=f"INEP — resultados e metas do Indicador Criança Alfabetizada por município, edição {EDICAO}",
                 url=meta["url"], obtido_em=meta["obtido_em"], arquivo=caminho_relativo(arquivo), sha256=meta["sha256"])
    registro.adicionar(c)
    bruto = carregar(arquivo)
    tabela, metas, avisos = recortar_es(bruto, municipios, c.id)
    sem_dado = int((tabela["situacao"] == "sem_dado").sum())
    status = {"fonte": "INEP", "ok": True, "coletado": True, "edicao": EDICAO, "municipios_es": len(municipios),
              "linhas_planilha": int(len(bruto)), "sem_dado": sem_dado, "sha256": meta["sha256"],
              "obtido_em": meta["obtido_em"], "avisos": len(avisos), "extraido_em": registro.extraido_em("INEP")}
    return ResultadoIca(tabela, metas, registro, avisos, status, EDICAO, bruto)


def programas_api(tabela: pd.DataFrame) -> list[dict[str, Any]]:
    """Registros do campo `ica` (origem `api`) do programas.yaml, no formato dos registros manuais.

    Um por município × ano. Linha `sem_dado` continua verificada (a fonte foi lida e
    não traz o valor) — no painel aparece como "sem dado publicado", nunca como 0%.
    """
    regs: list[dict[str, Any]] = []
    for r in tabela.itertuples(index=False):
        sem = r.situacao == "sem_dado"
        regs.append({"cod_ibge": int(r.cod_ibge), "ano": int(r.ano), "valor": None if sem else round(float(r.taxa), 1),
                     "situacao": r.situacao, "fonte": FONTE, "verificado_em": None, "q": r.q, "verificado": True,
                     "automatico": True, "indicador": "ica_taxa", "detalhe": f"edição {int(r.edicao)}",
                     "meta": None if r.meta is None or pd.isna(r.meta) else float(r.meta),
                     "nivel": None if r.nivel is None or pd.isna(r.nivel) else int(r.nivel)})
    return regs


def main(argv: Iterable[str] | None = None) -> int:
    from .cliente import ClienteSiconfi
    from .entes import listar_entes_es

    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--atualizar", choices=("nao", "tudo", "offline"), default="nao")
    p.add_argument("-v", "--verboso", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verboso else logging.INFO, format="%(levelname)-7s %(message)s")
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(errors="replace")
    entes = listar_entes_es(ClienteSiconfi(atualizar="nao"))
    r = executar([e.cod_ibge for e in entes if e.esfera == "M"], atualizar=args.atualizar)
    print(json.dumps(r.status, ensure_ascii=False, indent=1, default=str))
    for a in r.avisos:
        print("aviso:", a["aviso"])
    if not r.tabela.empty:
        ult = r.tabela[r.tabela["ano"] == r.edicao]
        print(f"edição {r.edicao}: {ult['taxa'].notna().sum()} municípios com taxa, "
              f"média {ult['taxa'].mean():.1f}%, {int((ult['taxa'] < ult['meta']).sum())} abaixo da meta")
    return 0


if __name__ == "__main__":
    sys.exit(main())
