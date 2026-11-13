"""Instrumentos contratuais do TCE-ES (todos os contratos, de todos os setores), recortados
para os fornecedores que aparecem nas redes — a base do dossiê de cada empresa.

O recurso "Instrumentos contratuais <anos>" do dataset de contratações traz, contrato a
contrato: o CNPJ do contratado, objeto, modalidade, base legal (dispensa, inexigibilidade,
emergência…), valores inicial e atual, vigência e TRÊS links — do contrato, da publicação
e do edital. Medido em 26/10/2026: 365 mil contratos, 57% com link específico do contrato.
O pipeline do painel não usava este recurso; as redes passam a usar.

    python -m financiamento.etl.instrumentos      # ~230 MB lidos em fluxo; fica o recorte (alguns MB)

O recorte guarda só as linhas cujo contratado (raiz do CNPJ) está entre os fornecedores
das redes ou entre as contratadas de obras — e, como todo recorte do cache, o SHA-256 e o
tamanho do arquivo original no `.json` ao lado.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import PROCESSADO
from .parsing import norm
from .tcees import DATASET_CONTRATACOES, ClienteTcees

log = logging.getLogger(__name__)

COLUNAS = ["NomeEsferaAdministrativa", "NomeUnidadeGestoraCadastro", "IdentificacaoContratacao", "NumeroInstrumentoContratacao",
           "AnoInstrumentoContratacao", "ObjetoInstrumento", "ObjetoContratacao", "ModalidadeLicitacao", "BaseLegalContratacao",
           "CriterioJulgamento", "RegistroPrecos", "NumeroArp", "AnoArp", "TipoInstrumento", "SituacaoInstrumento", "SetorBeneficiado",
           "DataAssinaturaInstrumentoContratacao", "InicioVigenciaContrato", "FimVigenciaContrato", "ValorTotalContratacaoInstrumento",
           "ValorAtualContratacaoInstrumento", "NumeroIdentificacaoContratado", "NomeContratado", "UrlInstrumentoContratacao",
           "UrlPublicacaoInstrumentoContratacao", "UrlEdital", "ChaveInstrumento"]


def raizes_das_redes() -> set[str]:
    g = json.loads((PROCESSADO / "grafos.json").read_text(encoding="utf-8"))
    raizes = {l[0] for l in g["fornecedores"]["linhas"]}
    raizes |= {str(l[0]) for l in g["obras"]["contratadas"]["linhas"] if len(str(l[0])) == 8}
    return raizes


def recursos(cliente: ClienteTcees) -> list[dict]:
    return [r for r in cliente.recursos(DATASET_CONTRATACOES) if re.match(r"instrumentos contratuais \d{4}", norm(r["nome"]))]


def coletar(atualizar: str = "nao") -> list:
    cliente = ClienteTcees(atualizar=atualizar)
    raizes = raizes_das_redes()

    def manter(l: dict[str, str]) -> bool:
        return re.sub(r"\D", "", l.get("NumeroIdentificacaoContratado") or "")[:8] in raizes

    arquivos = []
    for r in recursos(cliente):
        chave = "instrumentos/" + norm(r["nome"]).replace(" ", "_").replace("-", "")
        log.info("instrumentos: %s", r["nome"])
        arquivos.append(cliente.recorte_csv_fluxo(chave, r["url"], manter, {"recurso": r["nome"],
                        "filtro": "contratado (raiz do CNPJ) entre os fornecedores das redes ou contratadas de obras"}))
    return arquivos


@lru_cache(maxsize=1)
def carregar() -> pd.DataFrame:
    """Todos os recortes já no cache, numa tabela só (vazia se ainda não foi coletado)."""
    cliente = ClienteTcees(atualizar="offline")
    partes = []
    for r in recursos(cliente):
        chave = "instrumentos/" + norm(r["nome"]).replace(" ", "_").replace("-", "")
        a = cliente._do_cache(chave)
        if a is None or a.caminho is None:
            continue
        with gzip.open(a.caminho, "rt", encoding="utf-8") as f:
            df = pd.read_csv(f, sep=";", dtype=str, keep_default_na=False)
        partes.append(df.reindex(columns=COLUNAS).assign(_recurso=r["nome"], _url=a.url, _obtido_em=a.obtido_em, _sha256=a.sha256 or "",
                                                         _arquivo=str(a.caminho)))
    if not partes:
        return pd.DataFrame(columns=COLUNAS + ["raiz"])
    d = pd.concat(partes, ignore_index=True).drop_duplicates(subset=["ChaveInstrumento", "NumeroIdentificacaoContratado"])
    d["raiz"] = d["NumeroIdentificacaoContratado"].str.replace(r"\D", "", regex=True).str[:8]
    return d


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Recorta os instrumentos contratuais do TCE-ES para os fornecedores das redes.")
    ap.add_argument("--atualizar", choices=("nao", "tudo"), default="nao")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    for a in coletar(args.atualizar):
        print(a.caminho, a.extra.get("linhas_mantidas"), "de", a.extra.get("linhas_total"), "linhas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
