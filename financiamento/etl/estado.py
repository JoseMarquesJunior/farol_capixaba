"""Recursos estaduais em regime de colaboração (P18): o que a SEDU e o FUNPAES repassam.

No ES o CNCA é implementado dentro do **PAES**, e o braço financeiro do PAES para os
municípios é o **FUNPAES** (Lei estadual 10.787/2017). O prompt da fiscalização
tratava isto como hipótese a testar — "filtrar despesas estaduais pela UG
SEDU/FUNPAES e modalidade de transferência a municípios". A hipótese se confirmou,
e melhor do que se esperava (ver `docs/fase0_reconhecimento.md` §4):

* o FUNPAES tem **unidade gestora própria** no SIGEFES, com nome;
* a modalidade de aplicação separa **40** (transferências a municípios), **41**
  (fundo a fundo) e **42** (execução delegada);
* e o campo ``Favorecido`` traz o **fundo municipal nominalmente** — é por ele que
  se chega ao município.

Com isso P18 sobe de *proxy* para evidência quase direta. A ressalva é o casamento
por NOME do favorecido, que precisa de taxa de acerto medida — como o projeto já faz
com os conselhos escolares. O que não casa aparece como "favorecido não identificado",
com o nome original, e nunca é descartado em silêncio.

O arquivo do SIGEFES tem ~1,4 GB por exercício e 71 colunas. É lido **em fluxo**, e
só o recorte fica no cache, com o SHA-256 do arquivo original ao lado — o que prova
de onde o recorte saiu sem guardar 4 GB.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Iterable

import pandas as pd

from .config import BRUTO, PROCESSADO
from .parsing import norm
from .proveniencia import Consulta, Registro
from .tcees import ClienteTcees, num_br

log = logging.getLogger(__name__)

PASTA_CACHE = BRUTO / "estado"
DATASET = "despesas"

#: Modalidade de aplicação que significa "saiu do Estado para o município".
MODALIDADES_MUNICIPIO = {
    "40": "Transferências a municípios",
    "41": "Transferências a municípios — fundo a fundo",
    "42": "Execução orçamentária delegada a municípios",
}

#: Função 12 = Educação. O recorte guarda a função inteira, e não só o FUNPAES:
#: o que é do PAES hoje pode mudar de programa amanhã, e o filtro fino fica na leitura.
FUNCAO_EDUCACAO = "12"

#: A unidade gestora do FUNPAES, reconhecida pelo nome: "FUNDO EST. DE APOIO À AMP. E
#: MELH. DAS COND. DE OFERTA DA EDUC. INF. E DO ENS. FUND. NO ES". O recorte guarda a
#: função 12 inteira, e esta marca separa o que é do braço financeiro do PAES.
RX_FUNPAES = re.compile(r"funpaes|fundo est.*apoio.*(?:amp|melh)", re.I)

COLUNAS = ["ano", "mes", "cod_ibge", "municipio", "metodo_casamento", "favorecido", "cnpj", "ug", "funpaes",
           "programa", "acao", "fonte", "modalidade", "modalidade_rotulo",
           "empenhado", "liquidado", "pago", "q"]


@dataclass
class ResultadoEstado:
    repasses: pd.DataFrame = field(default_factory=pd.DataFrame)
    municipio: pd.DataFrame = field(default_factory=pd.DataFrame)
    nao_identificados: pd.DataFrame = field(default_factory=pd.DataFrame)
    consultas: list[Consulta] = field(default_factory=list)
    avisos: list[dict[str, Any]] = field(default_factory=list)

    @property
    def tabelas(self) -> dict[str, pd.DataFrame]:
        return {"cnca_estado_repasses": self.repasses, "cnca_estado_municipio": self.municipio,
                "cnca_estado_nao_identificados": self.nao_identificados}


def manter(linha: dict[str, str]) -> bool:
    """Filtro do recorte: despesa de educação que sai do Estado para um município."""
    if (linha.get("CodigoFuncao") or "").strip().lstrip("0") != FUNCAO_EDUCACAO:
        return False
    return (linha.get("CodigoModalidade") or "").strip().lstrip("0") in {"40", "41", "42"}


#: Prefixos que o SIGEFES põe antes do nome do município no favorecido. Tirá-los é o
#: que sobra do nome para a comparação aproximada.
RX_PREFIXO_FAVORECIDO = re.compile(
    r"^(prefeitura|fundo|secretaria|camara)\b[\w\s\-\.]*?\bde\s+|^(prefeitura|fundo)\s+municipal\s+", re.I)

#: Similaridade mínima para aceitar um casamento aproximado. Alta de propósito: em
#: 0,90, "divino sao lourenco" casa com "divino de sao lourenco" (0,95) e
#: "governador lindemberg" com "governador lindenberg" (0,98), mas nenhum par de
#: municípios distintos do ES chega perto disso.
SIMILARIDADE_MINIMA = 0.90


def _municipio_do_favorecido(nome: str, mapa: dict[str, int]) -> tuple[int | None, str]:
    """Casa o favorecido com um dos 78 municípios. Devolve (código, método usado).

    "FUNDO MUNICIPAL DE EDUCAÇÃO INFANTIL E ENSINO FUNDAMENTAL - FMEIEF - FUNDÃO"
    → Fundão. O casamento procura CADA nome de município dentro do favorecido, e
    fica com o mais longo que casar — sem isso, "Serra" casaria dentro de
    "Serra Negra" e "Linhares" perderia para nada.

    Quando nenhum nome casa inteiro, tenta por SIMILARIDADE, porque o SIGEFES grafa
    alguns municípios de outro jeito que o IBGE: medido nos dados de 2023, "PREFEITURA
    MUNICIPAL DE DIVINO SÃO LOURENÇO" (o IBGE escreve "Divino de São Lourenço") e
    "GOVERNADOR LINDEMBERG" (o IBGE escreve "Lindenberg") somavam R$ 9,3 milhões que
    ficavam de fora. O método fica na linha, para quem revisa saber quais vieram daí.
    """
    n = norm(nome)
    melhor, tamanho = None, 0
    for nome_mun, cod in mapa.items():
        if len(nome_mun) > tamanho and re.search(rf"(^|[^a-z]){re.escape(nome_mun)}([^a-z]|$)", n):
            melhor, tamanho = cod, len(nome_mun)
    if melhor is not None:
        return melhor, "nome exato"

    resto = norm(RX_PREFIXO_FAVORECIDO.sub("", nome))
    if not resto:
        return None, "sem casamento"
    pontuacoes = sorted(((SequenceMatcher(None, resto, nome_mun).ratio(), cod, nome_mun)
                         for nome_mun, cod in mapa.items()), reverse=True)
    if pontuacoes and pontuacoes[0][0] >= SIMILARIDADE_MINIMA:
        return pontuacoes[0][1], f"aproximado ({pontuacoes[0][0]:.2f})"
    return None, "sem casamento"


def preparar(df: pd.DataFrame, nomes_ibge: dict[int, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Recorte do SIGEFES → repasses com município identificado, e os que não casaram."""
    if df.empty:
        return pd.DataFrame(columns=COLUNAS), pd.DataFrame()
    mapa = {norm(nome): cod for cod, nome in nomes_ibge.items()}
    d = pd.DataFrame({
        "ano": pd.to_numeric(df.get("Ano"), errors="coerce").astype("Int64"),
        "mes": pd.to_datetime(df.get("Data"), errors="coerce", format="mixed").dt.month,
        "favorecido": df.get("Favorecido", pd.Series(dtype=str)).fillna("").str.strip(),
        "cnpj": df.get("CpfCnpjNis", pd.Series(dtype=str)).fillna("").str.strip(),
        "ug": df.get("UnidadeGestora", pd.Series(dtype=str)).fillna("").str.strip(),
        "programa": df.get("Programa", pd.Series(dtype=str)).fillna("").str.strip(),
        "acao": df.get("Acao", pd.Series(dtype=str)).fillna("").str.strip(),
        "fonte": df.get("Fonte", pd.Series(dtype=str)).fillna("").str.strip(),
        "modalidade": df.get("CodigoModalidade", pd.Series(dtype=str)).fillna("").str.strip().str.lstrip("0"),
        "empenhado": num_br(df.get("ValorEmpenho", pd.Series(dtype=str))).fillna(0.0),
        "liquidado": num_br(df.get("ValorLiquidado", pd.Series(dtype=str))).fillna(0.0),
        "pago": num_br(df.get("ValorPago", pd.Series(dtype=str))).fillna(0.0),
    })
    d["modalidade_rotulo"] = d["modalidade"].map(MODALIDADES_MUNICIPIO)
    d["funpaes"] = d["ug"].str.contains(RX_FUNPAES, na=False)
    casados = d["favorecido"].map(lambda n: _municipio_do_favorecido(n, mapa))
    d["cod_ibge"] = casados.map(lambda t: t[0])
    d["metodo_casamento"] = casados.map(lambda t: t[1])
    d["municipio"] = d["cod_ibge"].map(nomes_ibge)

    identificados = d[d["cod_ibge"].notna()].copy()
    identificados["cod_ibge"] = identificados["cod_ibge"].astype(int)
    # O que não casou NÃO é descartado: vira tabela própria, com o nome original, para
    # o auditor ver o que ficou de fora e decidir se é município ou outra coisa.
    sobra = d[d["cod_ibge"].isna()]
    sobra = (sobra.groupby(["ano", "favorecido", "ug"], as_index=False)
             .agg(empenhado=("empenhado", "sum"), lancamentos=("empenhado", "size"))
             .sort_values("empenhado", ascending=False)) if not sobra.empty else pd.DataFrame()
    return identificados.reindex(columns=COLUNAS), sobra


def por_municipio(repasses: pd.DataFrame) -> pd.DataFrame:
    """Quanto o Estado repassou a cada município por exercício, e quanto disso é FUNPAES."""
    if repasses.empty:
        return pd.DataFrame()
    total = repasses.groupby(["cod_ibge", "municipio", "ano"], as_index=False).agg(
        empenhado=("empenhado", "sum"), liquidado=("liquidado", "sum"), pago=("pago", "sum"),
        lancamentos=("empenhado", "size"), q=("q", "first"))
    fp = repasses[repasses["funpaes"].fillna(False)].groupby(["cod_ibge", "ano"], as_index=False).agg(
        empenhado_funpaes=("empenhado", "sum"), pago_funpaes=("pago", "sum"))
    d = total.merge(fp, on=["cod_ibge", "ano"], how="left")
    for c in ("empenhado_funpaes", "pago_funpaes"):
        d[c] = d[c].fillna(0.0)
    return d.sort_values(["cod_ibge", "ano"]).reset_index(drop=True)


def executar(nomes_ibge: dict[int, str], anos: Iterable[int], *, atualizar: str = "nao",
             registro: Registro | None = None) -> ResultadoEstado:
    """Baixa (ou lê do cache) o recorte do SIGEFES e monta os repasses por município."""
    cliente = ClienteTcees(pasta=PASTA_CACHE, atualizar=atualizar)
    res = ResultadoEstado()
    partes, sobras = [], []
    for ano in sorted(anos):
        rec = next((x for x in cliente.recursos(DATASET) if str(ano) in (x.get("nome") or "")), None)
        if rec is None:
            res.avisos.append({"fonte": "Governo do ES", "ano": ano, "aviso": "recurso não encontrado no catálogo"})
            continue
        chave = f"sigefes/{ano}"
        try:
            a = cliente.recorte_csv_fluxo(chave, rec["url"], manter,
                                          {"recurso": rec["nome"],
                                           "filtro": "CodigoFuncao = 12 e CodigoModalidade em (40, 41, 42)"},
                                          encoding="utf-8-sig")
        except Exception as e:                      # noqa: BLE001 — um ano que falha não derruba os outros
            res.avisos.append({"fonte": "Governo do ES", "ano": ano, "aviso": f"{e}"})
            continue
        if not a.obtido_em or a.caminho is None:
            res.avisos.append({"fonte": "Governo do ES", "ano": ano, "aviso": "fora do cache (sem rede)"})
            continue
        c = a.consulta(f"Governo do ES (SIGEFES) — despesas {ano} "
                       f"(recorte: função 12, transferências a municípios)")
        if registro is not None:
            registro.adicionar(c)
        res.consultas.append(c)
        bruto = pd.read_csv(a.caminho, sep=";", encoding="utf-8", dtype=str, keep_default_na=False)
        rep, sobra = preparar(bruto, nomes_ibge)
        if not rep.empty:
            partes.append(rep.assign(q=c.id))
        if not sobra.empty:
            sobras.append(sobra)
        log.info("estado: %s lido (%s linhas no recorte)", rec["nome"], len(bruto))

    res.repasses = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=COLUNAS)
    res.nao_identificados = pd.concat(sobras, ignore_index=True) if sobras else pd.DataFrame()
    res.municipio = por_municipio(res.repasses)
    if not res.repasses.empty:
        casados = res.repasses["empenhado"].sum()
        perdidos = res.nao_identificados["empenhado"].sum() if not res.nao_identificados.empty else 0.0
        taxa = casados / (casados + perdidos) * 100 if (casados + perdidos) else 0.0
        res.avisos.append({"fonte": "Governo do ES", "ano": None, "aviso":
                           f"casamento por nome do favorecido: {taxa:.1f}% do valor foi atribuído a um "
                           f"município; o resto está em cnca_estado_nao_identificados.csv"})
    return res


def main(argv: Iterable[str] | None = None) -> int:
    from .evidencias import gravar_consultas
    from .execucao import nomes_municipios

    p = argparse.ArgumentParser(description="Repasses do Estado (SIGEFES) aos municípios na Educação.")
    p.add_argument("--anos", default="2023-2025")
    p.add_argument("--atualizar", default="nao", choices=["nao", "vazios", "tudo", "offline"])
    args = p.parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    ini, _, fim = args.anos.partition("-")
    res = executar(nomes_municipios(), range(int(ini), int(fim or ini) + 1), atualizar=args.atualizar)
    PROCESSADO.mkdir(parents=True, exist_ok=True)
    for nome, df in res.tabelas.items():
        df.to_csv(PROCESSADO / f"{nome}.csv", index=False, encoding="utf-8")
        print(f"{nome}: {len(df):,} linhas")
    gravar_consultas(res.consultas)
    for a in res.avisos:
        print(f"  aviso: {a['aviso']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
