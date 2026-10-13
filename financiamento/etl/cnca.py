"""CNCA — Compromisso Nacional Criança Alfabetizada: quanto, de onde e para quem.

Tudo automático, a partir de duas fontes já coletadas pelo painel:

* **FNDE (CGU)** — o CNCA tem plano orçamentário próprio nas transferências
  federais: ação 0515 (PDDE) PO **000C**, pago a cada escola (unidade executora);
  PO 0007 "PDDE - Alfabetização" (o antecessor, 2021–2022); e ação 0509 PO
  **0014**, pago ao Estado (SEDU), que coordena o CNCA no regime de colaboração.
* **TCE-ES (empenhos)** — no ES o CNCA é implementado dentro do PAES; o braço
  financeiro do PAES para os municípios é o **FUNPAES** (Lei estadual
  10.787/2017), que os municípios identificam no nome do programa, da ação ou do
  detalhamento da fonte. Pelos empenhos se vê EM QUE ele foi gasto.

O que NÃO está em dado aberto: em que cada escola gastou o PDDE-CNCA (a escola
presta contas ao FNDE, fora da contabilidade municipal).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .fnde import PO_PDDE_ALFABETIZACAO, PO_PDDE_CNCA
from .proveniencia import juntar_ids

FONTE_REPASSE = "CGU — transferências do FNDE, ação 0515 (PDDE), plano orçamentário 000C"


def compor(escolas_pdde: pd.DataFrame, estado_cnca: pd.DataFrame, funpaes: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
    """Tabelas do módulo: por município-ano, por escola, ao Estado e o FUNPAES."""
    e = escolas_pdde[escolas_pdde["po"].isin([PO_PDDE_CNCA, PO_PDDE_ALFABETIZACAO])].copy()
    e["programa"] = e["po"].map({PO_PDDE_CNCA: "pdde_cnca", PO_PDDE_ALFABETIZACAO: "pdde_alfabetizacao"})
    com_mun = e[e["cod_ibge"].notna()]
    if com_mun.empty:
        municipio = pd.DataFrame(columns=["cod_ibge", "ano", "pdde_cnca", "escolas_cnca", "pdde_alfabetizacao",
                                          "escolas_alfabetizacao", "q"])
    else:
        municipio = (com_mun.pivot_table(index=["cod_ibge", "ano"], columns="programa", values="valor", aggfunc="sum")
                     .reindex(columns=["pdde_cnca", "pdde_alfabetizacao"]))
        n = com_mun.pivot_table(index=["cod_ibge", "ano"], columns="programa", values="cnpj_uex", aggfunc="nunique") \
            .reindex(columns=["pdde_cnca", "pdde_alfabetizacao"]).add_prefix("escolas_")
        n.columns = ["escolas_cnca", "escolas_alfabetizacao"]
        q = com_mun.groupby(["cod_ibge", "ano"])["q"].agg(lambda s: juntar_ids(*s))
        municipio = municipio.join(n).join(q).reset_index()
        municipio["cod_ibge"] = municipio["cod_ibge"].astype(int)
    escolas = e[["cod_ibge", "ano", "programa", "po", "cnpj_uex", "uex", "valor", "meses", "q"]].reset_index(drop=True)
    fp = funpaes if funpaes is not None else pd.DataFrame()
    return {"municipio": municipio, "escolas": escolas, "estado": estado_cnca.reset_index(drop=True), "funpaes": fp}


def programas_api(municipio: pd.DataFrame, ica: pd.DataFrame | None = None) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Os campos de origem "api" do programas.yaml, no formato dos registros manuais.

    `repasse` vem do PDDE-CNCA (CGU); `ica`, quando a planilha do INEP foi coletada,
    do módulo `ica` (uma linha por município × ano, com "sem dado" explícito).
    """
    regs = [{"cod_ibge": int(r.cod_ibge), "ano": int(r.ano), "valor": round(float(r.pdde_cnca), 2), "situacao": "informado",
             "fonte": FONTE_REPASSE, "verificado_em": None, "q": r.q, "verificado": True, "automatico": True,
             "indicador": "cnca_pdde", "detalhe": "000C",
             "escolas": None if pd.isna(r.escolas_cnca) else int(r.escolas_cnca)}
            for r in municipio.itertuples(index=False) if not pd.isna(r.pdde_cnca)]
    campos: dict[str, list[dict[str, Any]]] = {"repasse": regs}
    if ica is not None and not ica.empty:
        from .ica import programas_api as _ica_api
        campos["ica"] = _ica_api(ica)
    return {"cnca": campos}
