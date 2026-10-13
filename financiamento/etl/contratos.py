"""Contratações de formação e material de alfabetização (P47, P48).

O município que terceiriza a formação continuada em alfabetização deixa rastro no
**objeto da contratação** — e é o único rastro que existe, porque o empenho do
TCE-ES não traz histórico nem número de contrato.

A classificação é por palavra-chave sobre `ObjetoContratacao`, e por isso é
**revisável por construção**: cada contratação classificada carrega os termos que
a fizeram entrar, para o auditor confirmar ou descartar uma a uma. Nenhuma
contratação vira achado por ter casado com uma palavra.

**A cobertura é desigual, e isso não é defeito deste módulo.** O recorte da Educação
em `tcees-contratacoes` usa três regras da própria fonte (unidade gestora de
educação, `SetorBeneficiado = Educação`, obra da Educação); `SetorBeneficiado` vem
vazio em 90% das contratações e só 22 municípios têm unidade gestora própria de
educação. Município que compra pela unidade gestora da prefeitura sem marcar o
setor **não aparece** — e ausência aqui não é ausência de contratação.

O PNCP cobriria parte dessa lacuna, mas a API de consulta não filtra por UF nem por
município: seria baixar ~144 mil contratos por mês do país inteiro para achar os do
ES. Fica registrado em `PNCP_CONSULTA` como caminho para quem for buscar um contrato
específico, e não é chamado em lote.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Iterable

import pandas as pd

from .config import PROCESSADO
from .parsing import norm

log = logging.getLogger(__name__)

#: Categorias de objeto que respondem P47 e P48. A ordem importa: uma contratação é
#: atribuída à primeira categoria que casar, para não ser contada duas vezes.
CATEGORIAS: dict[str, tuple[str, re.Pattern[str]]] = {
    "formacao_alfabetizacao": (
        "Formação continuada em alfabetização",
        re.compile(r"(formacao|capacitacao|aperfeicoamento|qualificacao)[^.]{0,80}"
                   r"(alfabetiz|literacia|leitura e escrita)"
                   r"|(alfabetiz|literacia)[^.]{0,80}(formacao|capacitacao|aperfeicoamento)", re.I)),
    "material_alfabetizacao": (
        "Material estruturado de alfabetização",
        re.compile(r"(material|livro|acervo|apostil|kit)[^.]{0,80}(alfabetiz|literacia|leitura e escrita)"
                   r"|cantinho[s]? de leitura", re.I)),
    "assessoria_pedagogica": (
        "Assessoria ou consultoria pedagógica",
        re.compile(r"assessoria[^.]{0,40}(pedagogic|educacion)|consultoria[^.]{0,40}(pedagogic|educacion)"
                   r"|tutoria pedagogica", re.I)),
    "formacao_geral": (
        "Formação continuada (sem menção à alfabetização)",
        re.compile(r"formacao continuada|capacitacao[^.]{0,40}(professor|docente|profissionais da educacao)", re.I)),
    "material_estruturado": (
        "Material didático estruturado ou apostilado",
        re.compile(r"material[^.]{0,30}(estruturado|apostilado|semiestruturado)|sistema[^.]{0,20}apostilado"
                   r"|material didatico[^.]{0,40}(estruturado|semiestruturado)", re.I)),
    # Última da lista, e de propósito: recolhe o que NOMEIA a alfabetização sem casar com
    # nenhuma categoria acima, para que nada que cite o programa saia da tela em silêncio.
    # Medido: das 6 contratações do ES que citam "alfabetiz", nenhuma é de formação —
    # são congresso, palestra, papelaria e alimentação do Brasil Alfabetizado (EJA).
    "mencao_alfabetizacao": (
        "Menciona alfabetização (revisão humana)",
        re.compile(r"alfabetiz|literacia|cantinho[s]? de leitura", re.I)),
}

#: As categorias que respondem P47 ("contratou terceiros para formação em alfabetização")
#: sem depender de leitura — as demais entram como contexto, para revisão.
CATEGORIAS_P47 = ("formacao_alfabetizacao", "material_alfabetizacao", "assessoria_pedagogica")

#: Situações em que a contratação não gerou contrato: entram na tabela marcadas, e
#: ficam fora do valor de P48 — somar licitação revogada infla o gasto.
SITUACOES_SEM_EFEITO = re.compile(r"revogad|anulad|fracassad|desert|cancelad", re.I)

#: Consulta ao PNCP para um contrato específico. NÃO é chamada em lote: a API não filtra
#: por UF nem por município, e devolve ~144 mil contratos por mês do país inteiro. Cada
#: contrato traz `unidadeOrgao.codigoIbge` e `ufSigla`, então o filtro por município é no
#: cliente. Medido em 23/09/2026: o servidor expira com timeout de 60 s e responde com 150 s.
PNCP_CONSULTA = ("https://pncp.gov.br/api/consulta/v1/contratos"
                 "?dataInicial={aaaammdd_ini}&dataFinal={aaaammdd_fim}&pagina=1&tamanhoPagina=500")

COLUNAS = ["cod_ibge", "ano", "contratacao", "ug", "objeto", "categoria", "categoria_rotulo",
           "termos", "responde_p47", "sem_efeito", "modalidade", "situacao", "valor_total",
           "url_edital", "vinculo", "q"]


@dataclass
class ResultadoContratos:
    contratos: pd.DataFrame = field(default_factory=pd.DataFrame)
    municipio: pd.DataFrame = field(default_factory=pd.DataFrame)
    avisos: list[dict[str, Any]] = field(default_factory=list)

    @property
    def tabelas(self) -> dict[str, pd.DataFrame]:
        return {"cnca_contratos_formacao": self.contratos,
                "cnca_contratos_municipio": self.municipio}


def _termos(texto: str, rx: re.Pattern[str]) -> str:
    """Os trechos que fizeram a contratação entrar — é o que o auditor lê para revisar."""
    achados = [m.group(0).strip() for m in rx.finditer(texto)]
    vistos: list[str] = []
    for a in achados:
        a = " ".join(a.split())[:90]
        if a not in vistos:
            vistos.append(a)
    return " | ".join(vistos[:3])


def classificar(contratacoes: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por contratação da Educação cujo objeto casa com alguma categoria."""
    if contratacoes.empty or "objeto" not in contratacoes.columns:
        return pd.DataFrame(columns=COLUNAS)
    d = contratacoes.copy()
    d["texto_norm"] = d["objeto"].fillna("").map(norm)
    linhas = []
    for r in d.itertuples(index=False):
        texto = r.texto_norm
        for chave, (rotulo, rx) in CATEGORIAS.items():
            if not rx.search(texto):
                continue
            situacao = str(getattr(r, "situacao", "") or "")
            linhas.append({
                "cod_ibge": r.cod_ibge, "ano": r.ano, "contratacao": getattr(r, "contratacao", None),
                "ug": getattr(r, "ug", None), "objeto": r.objeto, "categoria": chave,
                "categoria_rotulo": rotulo, "termos": _termos(texto, rx),
                "responde_p47": chave in CATEGORIAS_P47,
                "sem_efeito": bool(SITUACOES_SEM_EFEITO.search(situacao)),
                "modalidade": getattr(r, "modalidade", None), "situacao": situacao,
                "valor_total": getattr(r, "valor_total", None),
                "url_edital": getattr(r, "url_edital", None), "vinculo": getattr(r, "vinculo", None),
                "q": getattr(r, "q", None),
            })
            break                       # primeira categoria que casar; sem contagem dupla
    if not linhas:
        return pd.DataFrame(columns=COLUNAS)
    return pd.DataFrame(linhas).reindex(columns=COLUNAS)


def por_municipio(contratos: pd.DataFrame) -> pd.DataFrame:
    """Resumo por município-ano: quantas contratações e quanto, dentro e fora de P47.

    O valor de P48 exclui contratação sem efeito (revogada, anulada, fracassada,
    deserta, cancelada): somá-las inflaria o gasto com algo que não aconteceu.
    """
    if contratos.empty:
        return pd.DataFrame()
    valem = contratos[~contratos["sem_efeito"].fillna(False)]
    p47 = valem[valem["responde_p47"].fillna(False)]
    base = contratos.groupby(["cod_ibge", "ano"], as_index=False).agg(
        contratacoes=("contratacao", "nunique"), q=("q", "first"))
    a = p47.groupby(["cod_ibge", "ano"], as_index=False).agg(
        contratacoes_p47=("contratacao", "nunique"), valor_p47=("valor_total", "sum"))
    b = valem.groupby(["cod_ibge", "ano"], as_index=False).agg(
        contratacoes_validas=("contratacao", "nunique"), valor_total=("valor_total", "sum"))
    d = base.merge(a, on=["cod_ibge", "ano"], how="left").merge(b, on=["cod_ibge", "ano"], how="left")
    for c in ("contratacoes_p47", "contratacoes_validas"):
        d[c] = d[c].fillna(0).astype(int)
    return d.sort_values(["cod_ibge", "ano"]).reset_index(drop=True)


def executar() -> ResultadoContratos:
    """Lê as contratações da Educação já recortadas pelo pipeline geral (sem rede)."""
    caminho = PROCESSADO / "tcees_contratacoes_educacao.csv"
    res = ResultadoContratos()
    if not caminho.exists():
        res.avisos.append({"fonte": "TCE-ES", "aviso": f"{caminho.name} não existe — rode o pipeline geral antes"})
        return res
    contratacoes = pd.read_csv(caminho)
    res.contratos = classificar(contratacoes)
    res.municipio = por_municipio(res.contratos)
    fora = sorted(set(contratacoes["cod_ibge"].dropna().astype(int)) - set(res.contratos["cod_ibge"].dropna().astype(int)))
    if fora:
        res.avisos.append({"fonte": "TCE-ES", "aviso":
                           f"{len(fora)} municípios têm contratação da Educação e nenhuma casou com as "
                           f"categorias de formação/material — ausência de categoria, não de contratação"})
    return res


def main(argv: Iterable[str] | None = None) -> int:
    argparse.ArgumentParser(description="Contratações de formação e material de alfabetização.").parse_args(
        list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    res = executar()
    PROCESSADO.mkdir(parents=True, exist_ok=True)
    for nome, df in res.tabelas.items():
        df.to_csv(PROCESSADO / f"{nome}.csv", index=False, encoding="utf-8")
        print(f"{nome}: {len(df):,} linhas")
    if not res.contratos.empty:
        print("\npor categoria:")
        print(res.contratos.groupby(["categoria", "responde_p47"]).agg(
            n=("contratacao", "nunique"), municipios=("cod_ibge", "nunique"),
            valor=("valor_total", "sum")).to_string())
    for a in res.avisos:
        print(f"  aviso: {a['aviso']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
