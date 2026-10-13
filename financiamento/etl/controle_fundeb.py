"""Controle independente da receita do FUNDEB: DCA I-C (usado no dataset) contra DCA I-HI.

O I-C traz a receita orçamentária realizada; o I-HI, a variação patrimonial
"Transferências do FUNDEB" (4.5.2.2.0). Em princípio devem coincidir, e foi esse
controle que revelou que a complementação da União fica numa conta à parte do I-C.
Não faz parte do ETL principal (exige uma consulta a mais por ente e ano); rode
quando quiser reconferir.

    python -m financiamento.etl.controle_fundeb

Grava `dados/processado/controle_fundeb.csv`. Divergências que sobram são,
até onde se verificou, inconsistência entre anexos do próprio município (base de
caixa contra base de competência), quase sempre na perna da complementação.
"""

from __future__ import annotations

import logging
import sys
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from .cliente import ClienteSiconfi
from .config import PROCESSADO

log = logging.getLogger(__name__)

ANEXO_HI = "DCA-Anexo I-HI"
CONTA_RECEBIDO = "P4.5.2.2.0.00.00"  # Transferências do FUNDEB (VPA)
CONTA_CONTRIBUICAO = "P3.5.2.2.0.00.00"  # Transferências ao FUNDEB (VPD)
TOLERANCIA = 1.00  # R$


def _valores_hi(cliente: ClienteSiconfi, cod: int, ano: int) -> dict[str, float | None]:
    itens = cliente.consultar("dca", an_exercicio=ano, id_ente=cod, no_anexo=ANEXO_HI).itens
    # No I-HI a coluna é a data de fechamento ("31/12/2024").
    fechamento = [l for l in itens if str(ano) in str(l["coluna"])]
    pegar = lambda conta: next((float(l["valor"]) for l in fechamento if l["cod_conta"] == conta), None)
    return {"hi_recebido": pegar(CONTA_RECEBIDO), "hi_contribuicao": pegar(CONTA_CONTRIBUICAO)}


def comparar(cliente: ClienteSiconfi, anual: pd.DataFrame, trabalhadores: int = 6) -> pd.DataFrame:
    """Uma linha por ente × ano com a diferença entre I-C e I-HI."""
    base = anual[anual["esfera"] == "M"][["cod_ibge", "ente", "ano", "fundeb_receita", "fundeb_contribuicao"]].copy()
    pares = [(int(c), int(a)) for c, a in zip(base["cod_ibge"], base["ano"])]
    with ThreadPoolExecutor(trabalhadores) as pool:
        hi = list(pool.map(lambda p: _valores_hi(cliente, *p), pares))
    base = pd.concat([base.reset_index(drop=True), pd.DataFrame(hi)], axis=1)
    base["dif_receita"] = base["fundeb_receita"] - base["hi_recebido"]
    base["dif_contribuicao"] = base["fundeb_contribuicao"] - base["hi_contribuicao"]
    return base


def resumo(comp: pd.DataFrame) -> list[str]:
    linhas = []
    for nome, dif, ref in (("receita", "dif_receita", "hi_recebido"), ("contribuição", "dif_contribuicao", "hi_contribuicao")):
        com = comp[comp[ref].notna()]
        ok = int((com[dif].abs() <= TOLERANCIA).sum())
        linhas.append(f"{nome}: {ok} de {len(com)} ente-anos conferem (|dif| <= R$ {TOLERANCIA:.2f}); "
                      f"{len(comp) - len(com)} sem linha no I-HI")
    return linhas


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    anual = pd.read_csv(PROCESSADO / "financiamento_anual.csv")
    comp = comparar(ClienteSiconfi(), anual)
    comp.to_csv(PROCESSADO / "controle_fundeb.csv", index=False, encoding="utf-8")
    print("\n".join(resumo(comp)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
