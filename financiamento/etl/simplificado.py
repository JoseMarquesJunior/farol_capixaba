"""Pipeline do painel simplificado: só dados abertos do TCE-ES e duas tabelas fixas.

    python -m financiamento.etl.simplificado                      # 2021 até o exercício corrente
    python -m financiamento.etl.simplificado --anos 2021-2026 --atualizar offline

Gera ``dados/processado/dataset_simplificado.json``, que ``build_simplificado``
embute na página. Diferente do pipeline completo (``pipeline.py``), não consulta o
SICONFI, o SIOPE nem a CGU: despesa, receita e Nível 3 vêm dos dados abertos do
Tribunal em dados.es.gov.br, e só duas tabelas fixas, versionadas com o código,
completam o que o TCE-ES não publica:

* ``referencia/municipios_es.csv`` — os 78 municípios e o código IBGE (o Tribunal
  publica o nome do município; o código é o que a página usa no endereço);
* ``referencia/censo_escolar/`` — o nome da escola de cada conselho escolar (INEP).

Recursos do TCE-ES usados:

=========================================  ==================================================
"Despesas dos municípios" (anual)          despesa em Educação, subfunção, natureza, fonte ×
                                           subfunção; e, somada, a despesa de todas as funções
"Receitas dos municípios" (anual)          receita total, impostos, transferências, FUNDEB e
                                           repasses do FNDE, pela natureza da receita
"Educação" (despesas com saúde, educação…) matrículas da rede municipal ("Alunos")
Empenhos, contratações e itens             Nível 3 (os mesmos do pipeline completo)
=========================================  ==================================================

Conferido contra o SICONFI em 11/2026: a despesa da função 12 bate com o DCA I-E em
386 de 390 município-anos; a receita, com o RREO Anexo 01 em ~99%; o FUNDEB, com a
MSC em 390 de 390. Os repasses do FNDE são o que o município REGISTROU como receita
(a CGU mostra o que a União pagou): batem exatos em ~60% e a soma fica ~3% acima.

O exercício corrente entra parcial, até o último mês que cada município enviou. Os
arquivos dele, o catálogo do portal e os arquivos sem ano que o Tribunal regrava todo
mês são baixados de novo a cada execução; os exercícios fechados vêm do cache
(``--atualizar tudo`` refaz tudo).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests

from . import escolas as mod_escolas
from . import indicadores, manuais, msc as mod_msc, programas
from . import tcees as mod_tcees
from .config import PASTA, PROCESSADO
from .parsing import norm
from .pipeline import SCHEMA, _compacta, _consultas_partidas, _json_limpo, catalogo_subfuncoes, contratacoes_do_painel, \
    itens_do_painel, parse_anos
from .proveniencia import Registro, juntar_ids
from .tcees import ClienteTcees, ErroTcees, Municipios, num_br

log = logging.getLogger(__name__)

SAIDA = PROCESSADO / "dataset_simplificado.json"
ARQUIVO_MUNICIPIOS = PASTA / "referencia" / "municipios_es.csv"
DATASET_RECEITAS = "receitas-municipios"
PRIMEIRO_ANO = 2021
CHAVE = ["cod_ibge", "ano"]
ESTAGIOS = ["empenhada", "liquidada", "paga"]

#: Colunas das Receitas que o painel usa (o arquivo tem 38).
COLUNAS_RECEITA = ["Ano", "Mes", "EsferaAdministrativa", "ClassificacaoReceita", "CodigoCategoria", "CodigoOrigem",
                   "CodigoEspecie", "NomeEspecie", "NomeDetalhamentoNivel1", "NomeDetalhamentoNivel2",
                   "NomeDetalhamentoNivel3", "NomeTipoDetalhamento", "CodigoFonteReduzida", "Arrecadada"]
_NOMES_RECEITA = ["NomeEspecie", "NomeDetalhamentoNivel1", "NomeDetalhamentoNivel2", "NomeDetalhamentoNivel3",
                  "NomeTipoDetalhamento"]
#: Repasses do FNDE que formam as "transferências federais específicas", pelo NOME da
#: natureza — o código mudou com o ementário de 2022 (171805xx → 171450–53), o nome não.
PROGRAMAS_FNDE = {"salario_educacao": r"SAL[AÁ]RIO-EDUCA", "pnae": r"ALIMENTA[CÇ][AÃ]O ESCOLAR",
                  "pnate": r"TRANSPORTE DO ESCOLAR", "pdde": r"DINHEIRO DIRETO NA ESCOLA"}
#: Fonte de recursos no padrão nacional da STN (500–899). Antes dele, cada município do
#: ES usava os códigos do Tribunal (0xx–3xx): nos dados do TCE-ES, até 2022.
_FONTE_PADRONIZADA = r"[5-8]\d\d"
_MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "a", "o", "em", "na", "no", "para", "com", "à"}

_TCE = "Dados abertos do TCE-ES (dados.es.gov.br)"
_DESP = _TCE + " — \"Despesas dos municípios\", recorte da função 12, exceto modalidade 91 (intra-orçamentária)"
_REC = _TCE + " — \"Receitas dos municípios\", coluna \"Arrecadada\", categorias 1 e 2 (exceto intra-orçamentária)"
_SOMA = "soma da coluna \"Empenhada\" nos meses publicados"

#: Catálogo do "ver fonte" desta versão: os números de despesa e receita apontam para
#: os recursos do TCE-ES; os do Nível 3 são os mesmos do pipeline completo.
INDICADORES_SIMPLIFICADO: dict[str, dict[str, Any]] = {
    "desp_educacao_empenhada": {
        "rotulo": "Despesa em Educação (empenhada)", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _DESP, "calculo": _SOMA},
    "desp_total_empenhada": {
        "rotulo": "Despesa total do município (empenhada)", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _TCE + " — \"Despesas dos municípios\", todas as funções, exceto modalidade 91",
        "calculo": _SOMA},
    "desp_educacao_pct_total": {
        "rotulo": "Educação em % da despesa total", "fonte": "calculado", "unidade": "%",
        "localizacao": _TCE + " — \"Despesas dos municípios\"", "calculo": "função 12 empenhada ÷ despesa total empenhada × 100"},
    "desp_educacao_por_matricula": {
        "rotulo": "Despesa em Educação por matrícula", "fonte": "calculado", "unidade": "R$/matrícula",
        "localizacao": _DESP + " (despesa) e " + _TCE + " — recurso \"Educação\", coluna \"Alunos\" (matrículas)",
        "calculo": "despesa em Educação empenhada ÷ matrículas da rede municipal no exercício"},
    "matriculas_rede_municipal": indicadores.INDICADORES["matriculas_rede_municipal"],
    "subfuncao_empenhada": {
        "rotulo": "Despesa em Educação por subfunção (empenhada) — Nível 1", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _DESP + ": subfunção {detalhe}",
        "calculo": _SOMA + "; as subfunções somam exatamente a despesa em Educação"},
    "fluxo_fonte_subfuncao": {
        "rotulo": "Despesa em Educação por fonte de recursos e subfunção", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _DESP + ": colunas \"CodigoFonteReduzida\" × \"CodigoSubFuncao\"",
        "calculo": _SOMA + "; só nos exercícios com a fonte no padrão nacional da STN"},
    "natureza_economica": {
        "rotulo": "Despesa em Educação por natureza econômica — Nível 2", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _DESP + ": coluna \"CodigoCompleto\" (natureza da despesa, 8 dígitos)",
        "calculo": _SOMA + "; categoria pelo grupo da natureza e subcategoria pelo elemento (Portaria 163/2001)"},
    "receita_total": {
        "rotulo": "Receita total do município (arrecadada)", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _REC, "calculo": "soma dos meses publicados"},
    "origem_receita": {
        "rotulo": "Origem da receita", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _REC + ": {detalhe}", "calculo": "soma dos meses publicados, pela natureza da receita"},
    "receita_natureza": {
        "rotulo": "Receita por natureza", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _REC + ": {detalhe}", "calculo": "soma dos meses publicados"},
    **{k: indicadores.INDICADORES[k] for k in ("tcees_emp_empenhada", "empenho_credor", "empenho_credor_acao",
                                                "repasse_conselho_escolar", "item_contratado")},
}
INDICADORES_SIMPLIFICADO["tcees_emp_empenhada"] = {
    **INDICADORES_SIMPLIFICADO["tcees_emp_empenhada"],
    "calculo": "soma de \"Empenhada\" (movimento mensal, líquido de anulações); conferida contra as Despesas dos municípios"}

ORIGENS_SIMPLIFICADO = {
    "impostos_proprios": {"rotulo": "Impostos próprios (IPTU, ISS, ITBI, IRRF)", "fonte": "TCE-ES",
                          "localizacao": _REC + ", natureza 1.1.1 (impostos)"},
    "fundeb": {"rotulo": "FUNDEB (fundo + complementação da União)", "fonte": "TCE-ES",
               "localizacao": _REC + ", transferências correntes cuja natureza é do FUNDEB"},
    "federal_especifica": {"rotulo": "Transferências federais específicas da educação (FNDE: salário-educação, PNAE, PNATE, PDDE)",
                           "fonte": "TCE-ES",
                           "localizacao": _REC + ", transferências correntes do salário-educação, PNAE, PNATE e PDDE"},
    "outras": {"rotulo": "Outras receitas (demais transferências, taxas, contribuições, patrimoniais, capital…)",
               "fonte": "calculado", "localizacao": "receita total (" + _REC + ") − as três categorias acima"},
}


# ------------------------------------------------------------------ entrada

def carregar_municipios(arquivo: Path = ARQUIVO_MUNICIPIOS) -> dict[int, str]:
    """Os 78 municípios da tabela fixa: código IBGE → nome."""
    with open(arquivo, encoding="utf-8", newline="") as f:
        nomes = {int(l["cod_ibge"]): l["nome"] for l in csv.DictReader(f)}
    if len(nomes) != 78 or not all(str(c).startswith("32") for c in nomes):
        raise ValueError(f"{arquivo.name}: esperava os 78 municípios do ES; achei {len(nomes)}")
    return nomes


class ClienteRenovaAno(ClienteTcees):
    """Cache do TCE-ES com o exercício corrente sempre renovado.

    O Tribunal reescreve o arquivo do ano a cada remessa mensal. Os exercícios
    fechados vêm do cache; o catálogo do portal, os arquivos do ano corrente e os
    arquivos sem ano que mudam todo mês são baixados de novo, uma vez por execução.
    """

    SEMPRE = ("educacao", "obras", "bens", "pcm", "contratacoes_educacao")

    def __init__(self, ano_corrente: int | None, **kw: Any) -> None:
        super().__init__(**kw)
        self.ano_corrente = ano_corrente
        self._renovados: set[str] = set()
        self._catalogos_renovados: set[str] = set()

    def _renova(self, chave: str) -> bool:
        if self.atualizar == "offline" or self.ano_corrente is None or chave in self._renovados:
            return False
        partes = chave.split("/")
        return chave in self.SEMPRE or (len(partes) > 1 and partes[1] == str(self.ano_corrente))

    def _do_cache(self, chave: str) -> mod_tcees.Arquivo | None:
        return None if self._renova(chave) else super()._do_cache(chave)

    def _gravar(self, a: mod_tcees.Arquivo) -> mod_tcees.Arquivo:
        self._renovados.add(a.chave)
        return super()._gravar(a)

    def recursos(self, dataset: str) -> list[dict[str, Any]]:
        if self.atualizar == "offline" or self.ano_corrente is None or dataset in self._catalogos_renovados:
            return super().recursos(dataset)
        self._catalogos_renovados.add(dataset)
        self._catalogos.pop(dataset, None)
        antes, self.atualizar = self.atualizar, "tudo"
        try:
            return super().recursos(dataset)
        except ErroTcees as exc:  # portal fora do ar: segue com o catálogo do cache
            log.warning("catálogo %s não renovado (%s); usado o do cache", dataset, exc)
        finally:
            self.atualizar = antes
        return super().recursos(dataset)


def total_por_mes(bloco: pd.DataFrame) -> pd.DataFrame:
    """Filtro do recorte da despesa de TODAS as funções: soma por município e mês, exceto intra."""
    b = bloco.rename(columns={"AnoReferencia": "Ano", "MesReferencia": "Mes"})
    b = b[b["CodigoModalidade"].str.strip() != "91"]
    return (b.assign(Empenhada=num_br(b["Empenhada"]).fillna(0.0))
            .groupby(["Ano", "Mes", "EsferaAdministrativa"], as_index=False)["Empenhada"].sum())


def colunas_receita(bloco: pd.DataFrame) -> pd.DataFrame:
    return bloco.reindex(columns=COLUNAS_RECEITA)


def coletar_anuais(cliente: ClienteTcees, anos: Iterable[int], reg: Registro,
                   avisos: list[dict[str, Any]]) -> dict[str, dict[int, tuple[pd.DataFrame, str]]]:
    """Despesas (função 12 e total) e Receitas de cada ano: {tipo: {ano: (tabela, id da consulta)}}."""
    planos = {
        "despesas": (mod_tcees.DATASET_DESPESAS, "municipios-despesas-{ano}.zip", mod_tcees.so_educacao, "CodigoFuncao = 12",
                     "TCE-ES — Despesas dos municípios, {ano} (recorte: função 12)"),
        "despesas_total": (mod_tcees.DATASET_DESPESAS, "municipios-despesas-{ano}.zip", total_por_mes,
                           "todas as funções, exceto modalidade 91, somadas por município e mês",
                           "TCE-ES — Despesas dos municípios, {ano}"),
        "receitas": (DATASET_RECEITAS, "municipios-receitas-{ano}.zip", colunas_receita, "colunas usadas pelo painel",
                     "TCE-ES — Receitas dos municípios, {ano}"),
    }
    saida: dict[str, dict[int, tuple[pd.DataFrame, str]]] = {t: {} for t in planos}
    for tipo, (dataset, molde, filtro, descricao_filtro, descricao) in planos.items():
        for ano in anos:
            chave = f"{tipo}/{ano}"
            try:
                rec = next((x for x in cliente.recursos(dataset) if norm(x["nome"]) == molde.format(ano=ano)), None)
                if rec is None:
                    avisos.append({"recurso": chave, "aviso": "o portal não traz o arquivo deste ano"})
                    continue
                a = cliente.recorte_zip(chave, rec["url"], filtro, {"recurso": rec["nome"], "filtro": descricao_filtro})
                if not a.obtido_em:
                    avisos.append({"recurso": chave, "aviso": "não coletado (modo offline sem cache)"})
                    continue
                c = a.consulta(descricao.format(ano=ano))
                reg.adicionar(c)
                saida[tipo][ano] = (mod_tcees.ler_recorte(a), c.id)
            except (ErroTcees, ValueError, KeyError, zipfile.BadZipFile, requests.RequestException) as exc:
                avisos.append({"recurso": chave, "aviso": f"{type(exc).__name__}: {exc}"})
    return saida


# ------------------------------------------------------------------ despesa

def titulo(texto: Any) -> str:
    """"ALIMENTAÇÃO E NUTRIÇÃO" → "Alimentação e Nutrição"."""
    palavras = str(texto or "").strip().lower().split()
    return " ".join(p if i and p in _MINUSCULAS else p[:1].upper() + p[1:] for i, p in enumerate(palavras))


def despesa_funcao12(df: pd.DataFrame, mun: Municipios) -> pd.DataFrame:
    """Recorte da função 12 das Despesas → uma linha por lançamento mensal, sem intra-orçamentária."""
    d = df.rename(columns={"AnoReferencia": "Ano", "MesReferencia": "Mes"})
    cod = d["EsferaAdministrativa"].map(mun.cod)
    d = d[cod.notna() & (d["CodigoModalidade"].str.strip() != "91")]
    return pd.DataFrame({
        "cod_ibge": d["EsferaAdministrativa"].map(mun.cod).astype(int),
        "ano": pd.to_numeric(d["Ano"]).astype(int), "mes": pd.to_numeric(d["Mes"]).astype(int),
        "subfuncao": d["CodigoSubFuncao"].str.strip().str.zfill(3), "nome_subfuncao": d["DescricaoSubFuncao"].str.strip(),
        "fonte": d["CodigoFonteReduzida"].str.strip(), "nome_fonte": d["NomeFonteReduzida"].str.strip(),
        "natureza": d["CodigoCompleto"].str.strip(),
        "empenhada": num_br(d["Empenhada"]).fillna(0.0), "liquidada": num_br(d["Liquidada"]).fillna(0.0),
        "paga": num_br(d["Paga"]).fillna(0.0),
    })


def despesa_total(df: pd.DataFrame, mun: Municipios) -> pd.DataFrame:
    """Recorte já somado de todas as funções → município × ano × mês."""
    cod = df["EsferaAdministrativa"].map(mun.cod)
    d = df[cod.notna()]
    t = pd.DataFrame({"cod_ibge": d["EsferaAdministrativa"].map(mun.cod).astype(int),
                      "ano": pd.to_numeric(d["Ano"]).astype(int), "mes": pd.to_numeric(d["Mes"]).astype(int),
                      "empenhada": pd.to_numeric(d["Empenhada"], errors="coerce").fillna(0.0)})
    return t.groupby(CHAVE + ["mes"], as_index=False)["empenhada"].sum()


def situacao_fontes(d: pd.DataFrame) -> pd.DataFrame:
    """Município-ano → "padronizada" (≥ 99% do valor em fonte do padrão nacional) ou "local"."""
    x = d.assign(v=d["empenhada"].abs(), pad=d["fonte"].str.fullmatch(_FONTE_PADRONIZADA))
    g = x.assign(vp=x["v"].where(x["pad"], 0.0)).groupby(CHAVE, as_index=False)[["v", "vp"]].sum()
    g["fontes"] = (g["vp"] >= 0.99 * g["v"]).map({True: "padronizada", False: "local"})
    return g[CHAVE + ["fontes"]]


def tabelas_despesa(d: pd.DataFrame, q_por_ano: dict[int, str]) -> dict[str, pd.DataFrame]:
    """Total, subfunções, fluxo fonte × subfunção, natureza e o total mensal da função 12."""
    total = d.groupby(CHAVE, as_index=False).agg(
        desp_educacao_empenhada=("empenhada", "sum"), desp_educacao_liquidada=("liquidada", "sum"),
        desp_educacao_paga=("paga", "sum"), ultimo_mes=("mes", "max"))
    total = total.merge(situacao_fontes(d), on=CHAVE, how="left")

    nomes = d.groupby("subfuncao")["nome_subfuncao"].agg(lambda s: s.value_counts().index[0]).map(titulo)
    s = d.groupby(CHAVE + ["subfuncao"], as_index=False)[ESTAGIOS].sum()
    s = s[s[ESTAGIOS].abs().sum(axis=1) > 0.005].merge(total[CHAVE + ["desp_educacao_empenhada"]], on=CHAVE)
    s = s.assign(codigo="12." + s["subfuncao"], nome=s["subfuncao"].map(nomes), esfera="M", q=s["ano"].map(q_por_ano),
                 pct_educacao=(100 * s["empenhada"] / s["desp_educacao_empenhada"].where(lambda x: x > 0)).round(4))
    subfuncoes = s.sort_values(["cod_ibge", "ano", "empenhada"], ascending=[True, True, False])[
        ["cod_ibge", "esfera", "ano", "codigo", "nome", *ESTAGIOS, "pct_educacao", "q"]].reset_index(drop=True)

    pad = total.loc[total["fontes"] == "padronizada", CHAVE]
    dp = d.merge(pad, on=CHAVE)
    fluxo = (dp.assign(grupo=dp["fonte"].map(mod_msc.grupo_fonte))
             .groupby(CHAVE + ["grupo", "fonte", "subfuncao"], as_index=False)["empenhada"].sum())
    fluxo = fluxo[fluxo["empenhada"].abs() > 0.005].reset_index(drop=True)

    classes = {n: mod_msc.classificar_natureza(n) for n in d["natureza"].unique()}
    dn = d.assign(categoria=d["natureza"].map(lambda n: classes[n][0]), subcategoria=d["natureza"].map(lambda n: classes[n][1]),
                  elemento=d["natureza"].str[4:6])
    natureza = dn.groupby(CHAVE + ["categoria", "subcategoria", "elemento"], as_index=False)[ESTAGIOS].sum()
    natureza = natureza[natureza[ESTAGIOS].abs().sum(axis=1) > 0.005].reset_index(drop=True)

    mensal = d.groupby(CHAVE + ["mes"], as_index=False)["empenhada"].sum()
    return {"total": total, "subfuncoes": subfuncoes, "fluxo": fluxo, "natureza": natureza, "mensal": mensal}


#: Siglas que continuam em maiúsculas quando o nome da fonte vira caixa normal.
_SIGLAS = {"sus", "fnde", "fundeb", "icms", "cide", "cosip", "cfem", "rpps", "pdde", "pnae", "pnate", "fpm", "ipva", "itr",
           "iof", "lc", "ec", "stn", "fep", "mde", "ops", "suas", "fnas", "fns"}


def nomes_tcees_das_fontes(d: pd.DataFrame) -> dict[str, str]:
    """Nome de cada fonte padronizada como o TCE-ES a publica, em caixa normal (siglas preservadas).
    O painel só o usa quando a fonte não está nos nomes curtos que ele já conhece."""
    pad = d[d["fonte"].str.fullmatch(_FONTE_PADRONIZADA)]
    tce = pad.groupby("fonte")["nome_fonte"].agg(lambda s: s.value_counts().index[0])

    def caixa(nome: str) -> str:
        palavras = nome.lower().split()
        return " ".join(p.upper() if p.strip("().,-") in _SIGLAS else (p[:1].upper() + p[1:] if i == 0 else p)
                        for i, p in enumerate(palavras))
    return {f: caixa(n) for f, n in tce.items() if n}


# ------------------------------------------------------------------ receita

def receita_normalizada(df: pd.DataFrame, mun: Municipios) -> pd.DataFrame:
    """Receitas → lançamento mensal, só categorias 1 e 2 (as 7 e 8 são intra-orçamentárias)."""
    cod = df["EsferaAdministrativa"].map(mun.cod)
    d = df[cod.notna() & df["CodigoCategoria"].str.strip().isin(["1", "2"])]
    r = pd.DataFrame({
        "cod_ibge": d["EsferaAdministrativa"].map(mun.cod).astype(int),
        "ano": pd.to_numeric(d["Ano"]).astype(int), "mes": pd.to_numeric(d["Mes"]).astype(int),
        "categoria": d["CodigoCategoria"].str.strip(), "origem": d["CodigoOrigem"].str.strip(),
        "especie": d["CodigoEspecie"].str.strip(), "nome_especie": d["NomeEspecie"].fillna("").str.upper(),
        "nome": d[_NOMES_RECEITA].fillna("").agg(" | ".join, axis=1).str.upper(),
        "valor": num_br(d["Arrecadada"]).fillna(0.0),
    })
    corrente = (r["categoria"] == "1") & (r["origem"] == "7")
    parcela = pd.Series(None, index=r.index, dtype="object")
    for programa, rx in PROGRAMAS_FNDE.items():
        parcela = parcela.mask(corrente & parcela.isna() & r["nome"].str.contains(rx, regex=True), programa)
    parcela = parcela.mask(corrente & r["nome"].str.contains("FUNDEB") & ~r["nome"].str.contains("RESTITUI"), "fundeb")
    return r.assign(parcela=parcela)


def tabelas_receita(r: pd.DataFrame, q_por_ano: dict[int, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(receita do ano por grupo da natureza, origem da receita em quatro categorias)."""
    corrente = r["categoria"] == "1"
    transf = corrente & (r["origem"] == "7")
    grupos = {
        "receita_total": pd.Series(True, index=r.index),
        "impostos": corrente & (r["origem"] == "1") & (r["especie"] == "1"),
        "transferencias_correntes": transf,
        "transf_correntes_uniao": transf & r["nome_especie"].str.contains("UNI[AÃ]O", regex=True),
        "transf_correntes_estados": transf & r["nome_especie"].str.contains("ESTADO"),
        "transf_correntes_outras_publicas": transf & r["nome_especie"].str.contains("OUTRAS INSTITUI|MULTIGOVERNAMENTA", regex=True),
        "transferencias_capital": (r["categoria"] == "2") & (r["origem"] == "4"),
        "fundeb": r["parcela"].eq("fundeb"),
        "federal_especifica": r["parcela"].isin(list(PROGRAMAS_FNDE)),
    }
    ra = pd.DataFrame({k: r["valor"].where(m, 0.0) for k, m in grupos.items()}).assign(cod_ibge=r["cod_ibge"], ano=r["ano"])
    ra = ra.groupby(CHAVE, as_index=False).sum().round(2)
    ra = ra.merge(r.groupby(CHAVE, as_index=False)["mes"].max().rename(columns={"mes": "ultimo_mes"}), on=CHAVE)
    ra["q"] = ra["ano"].map(q_por_ano)
    ra["outras"] = (ra["receita_total"] - ra["impostos"] - ra["fundeb"] - ra["federal_especifica"]).round(2)
    fonte = "TCE-ES — Receitas dos municípios"
    origem = pd.concat([
        ra[CHAVE + ["q"]].assign(categoria=cat, valor=ra[col], fonte=f)
        for cat, col, f in (("impostos_proprios", "impostos", fonte), ("fundeb", "fundeb", fonte),
                            ("federal_especifica", "federal_especifica", fonte), ("outras", "outras", "calculado por diferença"),
                            ("total", "receita_total", fonte))], ignore_index=True)
    return ra, origem.sort_values(CHAVE).reset_index(drop=True)[["cod_ibge", "ano", "categoria", "valor", "fonte", "q"]]


# ------------------------------------------------------------------ composição

def mesmo_periodo_anterior(mensal: pd.DataFrame, total: pd.DataFrame, ano: int) -> pd.Series:
    """Para o exercício parcial: a despesa do ano anterior até o mesmo mês, por município."""
    ult = total.loc[total["ano"] == ano].set_index("cod_ibge")["ultimo_mes"]
    ant = mensal[mensal["ano"] == ano - 1]
    ant = ant[ant["mes"] <= ant["cod_ibge"].map(ult)]
    return ant.groupby("cod_ibge")["empenhada"].sum().round(2)


def compor_anual(nomes: dict[int, str], anos: list[int], desp: dict[str, pd.DataFrame], total_mun: pd.DataFrame,
                 mde: pd.DataFrame, emp_total: pd.DataFrame | None, q: dict[str, Any], ano_parcial: int | None) -> pd.DataFrame:
    """Uma linha por município × exercício, com o que os cards e os rankings usam."""
    a = pd.DataFrame([{"cod_ibge": c, "ano": ano, "ente": nomes[c], "esfera": "M"} for c in sorted(nomes) for ano in anos])
    a = a.merge(desp["total"], on=CHAVE, how="left")
    if not total_mun.empty:
        a = a.merge(total_mun.groupby(CHAVE, as_index=False)["empenhada"].sum().rename(columns={"empenhada": "desp_total_empenhada"}),
                    on=CHAVE, how="left")
    else:
        a["desp_total_empenhada"] = None
    if not mde.empty:
        a = a.merge(mde[CHAVE + ["tcees_alunos", "tcees_mes_ultimo_envio"]], on=CHAVE, how="left")
    else:
        a["tcees_alunos"], a["tcees_mes_ultimo_envio"] = None, None
    if emp_total is not None and not emp_total.empty:
        a = a.merge(emp_total[CHAVE + ["tcees_emp_empenhada", "tcees_emp_meses", "tcees_emp_meses_ausentes"]], on=CHAVE, how="left")
    else:
        a["tcees_emp_empenhada"], a["tcees_emp_meses"], a["tcees_emp_meses_ausentes"] = None, None, None
    for c in ("desp_educacao_empenhada", "desp_total_empenhada", "tcees_alunos"):
        a[c] = pd.to_numeric(a[c], errors="coerce").astype(float)
    a["desp_educacao_pct_total"] = (100 * a["desp_educacao_empenhada"] / a["desp_total_empenhada"].where(lambda x: x > 0)).round(4)
    a["desp_educacao_por_matricula"] = (a["desp_educacao_empenhada"] / a["tcees_alunos"].where(lambda x: x > 0)).round(2)
    a["status_despesa"] = a["desp_educacao_empenhada"].notna().map({True: "ok", False: "sem_dado"})
    a["fontes"] = a["fontes"].fillna("sem_dado")
    a["parcial"] = a["ano"].eq(ano_parcial)
    a["desp_educacao_empenhada_ant_periodo"] = None
    if ano_parcial is not None:
        ant = mesmo_periodo_anterior(desp["mensal"], desp["total"], ano_parcial)
        e = a["ano"] == ano_parcial
        a.loc[e, "desp_educacao_empenhada_ant_periodo"] = a.loc[e, "cod_ibge"].map(ant)

        # No ano corrente, mês que ainda não chegou não é mês ausente.
        def so_ate(r: pd.Series) -> Any:
            if not r["parcial"] or pd.isna(r["tcees_emp_meses_ausentes"]) or pd.isna(r["ultimo_mes"]):
                return r["tcees_emp_meses_ausentes"]
            return ",".join(m for m in str(r["tcees_emp_meses_ausentes"]).split(",") if m and int(m) <= r["ultimo_mes"]) or None
        a["tcees_emp_meses_ausentes"] = a.apply(so_ate, axis=1)
    a["q_despesa"] = a["ano"].map(q.get("despesas", {}))
    a["q_despesa_total"] = a["ano"].map(q.get("despesas_total", {}))
    a["q_receita"] = a["ano"].map(q.get("receitas", {}))
    a["q_tcees_mde"] = q.get("educacao")
    a["q_tcees_emp"] = a["ano"].map({k: ";".join(v) for k, v in (q.get("empenhos") or {}).items()})
    a["q_tcees_mde_desp"] = [juntar_ids(x, y) for x, y in zip(a["q_despesa"], a["q_tcees_mde"])]
    return a.sort_values(CHAVE).reset_index(drop=True)


def executar(anos: list[int] | None = None, *, atualizar: str = "nao", hoje: datetime | None = None,
             saida: Path = SAIDA) -> dict[str, Any]:
    """Coleta (ou lê do cache), compõe e grava o dataset do simplificado. Devolve o dataset."""
    hoje = hoje or datetime.now(timezone.utc)
    anos = sorted(anos or range(PRIMEIRO_ANO, hoje.year + 1))
    ano_parcial = hoje.year if hoje.year in anos else None
    nomes = carregar_municipios()
    mun = Municipios(nomes)
    cliente = ClienteRenovaAno(ano_parcial, atualizar=atualizar)
    log.info("exercícios %s (parcial: %s) · atualizar=%s", anos, ano_parcial, atualizar)

    # Nível 3, matrículas e itens: o mesmo extrator do pipeline completo, sem as medições de obra.
    res = mod_tcees.executar(nomes, anos, atualizar=atualizar, com_medicoes=False, hoje=hoje, cliente=cliente)
    reg, avisos, q = res.consultas, list(res.avisos), dict(res.q)
    anuais = coletar_anuais(cliente, anos, reg, avisos)
    for tipo, por_ano in anuais.items():
        q[tipo] = {a: cid for a, (_, cid) in por_ano.items()}

    if not anuais["despesas"] or not anuais["receitas"]:
        raise SystemExit("sem as Despesas ou as Receitas do TCE-ES em nenhum exercício: nada a montar (ver avisos)\n"
                         + "\n".join(f"  - {a['recurso']}: {a['aviso']}" for a in avisos[-10:]))
    d = pd.concat([despesa_funcao12(t, mun) for t, _ in anuais["despesas"].values()], ignore_index=True)
    desp = tabelas_despesa(d, q["despesas"])
    total_mun = pd.concat([despesa_total(t, mun) for t, _ in anuais["despesas_total"].values()], ignore_index=True) \
        if anuais["despesas_total"] else pd.DataFrame(columns=CHAVE + ["mes", "empenhada"])
    r = pd.concat([receita_normalizada(t, mun) for t, _ in anuais["receitas"].values()], ignore_index=True)
    receita_anual, origem = tabelas_receita(r, q["receitas"])

    # Exercício corrente sem nenhum mês publicado ainda (janeiro): fica fora.
    if ano_parcial is not None and desp["total"].query("ano == @ano_parcial").empty:
        anos, ano_parcial = [a for a in anos if a != ano_parcial], None
    anual = compor_anual(nomes, anos, desp, total_mun, res.mde, res.empenhos.get("total"), q, ano_parcial)

    emp = res.empenhos
    vazio = pd.DataFrame()
    res_esc = mod_escolas.compor(pd.DataFrame(), emp.get("conselhos", vazio), pd.DataFrame())
    reg.juntar(res_esc.consultas.todas())
    usadas = set(res_esc.vinculos["co_entidade"].dropna().astype(int))
    escolas_usadas = res_esc.escolas[res_esc.escolas["co_entidade"].isin(usadas)]

    ultimos = anual.loc[anual["parcial"], "ultimo_mes"].dropna()
    status = {"TCE-ES": {**res.status, "avisos": len(avisos), "anos_receita": sorted(q["receitas"]),
                         "anos_despesa": sorted(q["despesas"])},
              "Censo": res_esc.status}
    dataset = {
        "meta": {
            "esquema": SCHEMA,
            "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "versao": "simplificado-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "extraido_em_por_fonte": {f: reg.extraido_em(f) for f in ("TCE-ES", "Censo")},
            "fontes_status": json.loads(json.dumps(status, default=str)),
            "anos": anos,
            "ano_mais_recente": max(a for a in anos if a != ano_parcial),
            "ano_parcial": ano_parcial,
            "ultimo_mes_parcial": int(ultimos.mode().iloc[0]) if len(ultimos) else None,
            "n_municipios": len(nomes),
            "indicadores": INDICADORES_SIMPLIFICADO,
            "origens": ORIGENS_SIMPLIFICADO,
            "grupos_fonte": mod_msc.GRUPOS_FONTE,
            "nome_fonte": mod_msc.NOME_FONTE,
            "nome_fonte_tcees": nomes_tcees_das_fontes(d),
            "categorias_natureza": mod_msc.CATEGORIAS,
            "subcategorias_natureza": mod_msc.SUBCATEGORIAS,
            "elementos": mod_msc.NOME_ELEMENTO,
            "avisos": avisos,
        },
        "entes": [{"cod_ibge": c, "nome": n, "esfera": "M"} for c, n in sorted(nomes.items())],
        "anual": _json_limpo(anual),
        "subfuncoes": _json_limpo(desp["subfuncoes"]),
        "catalogo_subfuncoes": catalogo_subfuncoes(desp["subfuncoes"]),
        "receita_anual": _compacta(receita_anual, ["cod_ibge", "ano", "ultimo_mes", "receita_total", "impostos",
                                                   "transferencias_correntes", "transf_correntes_uniao",
                                                   "transf_correntes_estados", "transf_correntes_outras_publicas",
                                                   "transferencias_capital", "q"], dicionario=["q"]),
        "origem": _compacta(origem, ["cod_ibge", "ano", "categoria", "valor", "fonte", "q"], dicionario=["categoria", "fonte", "q"]),
        "fluxo": _compacta(desp["fluxo"], ["cod_ibge", "ano", "grupo", "fonte", "subfuncao", "empenhada"], dicionario=["grupo"]),
        "natureza": _compacta(desp["natureza"], ["cod_ibge", "ano", "categoria", "subcategoria", "elemento", *ESTAGIOS],
                              dicionario=["categoria", "subcategoria"]),
        "consultas": _compacta(_consultas_partidas(reg), ["id", "fonte", "recurso", "descricao", "url_base", "url_resto",
                                                          "obtido_em", "arquivo", "metodo", "sha256"],
                               dicionario=["fonte", "recurso", "descricao", "url_base", "metodo"]),
        "credores": _compacta(emp.get("credores", vazio), ["cod_ibge", "ano", "credor", "credor_nome", "pessoa_fisica",
                                                           "empenhada", "liquidada", "paga", "empenhos", "elemento", "fonte", "q"],
                              dicionario=["credor", "credor_nome", "elemento", "q"]),
        "conselhos": _compacta(emp.get("conselhos", vazio), ["cod_ibge", "ano", "credor", "credor_nome", "empenhada", "paga",
                                                             "acao", "fonte", "q"], dicionario=["credor", "credor_nome", "acao", "q"]),
        "credor_acao": _compacta(emp.get("credor_acao", vazio), ["cod_ibge", "ano", "CodigoAcao", "NomeAcao", "credor",
                                                                 "credor_nome", "elemento", "fonte", "empenhada", "paga",
                                                                 "demais", "q"],
                                 dicionario=["CodigoAcao", "NomeAcao", "credor", "credor_nome", "elemento", "fonte", "q"]),
        "itens": _compacta(itens_do_painel(res.itens.get("itens", vazio)),
                           ["cod_ibge", "ano", "contratacao", "chave", "ug", "descricao", "unidade", "quantidade",
                            "valor_unitario", "valor_total", "contratada", "cnpj_contratada", "medicoes", "valor_medido",
                            "vinculo", "q"], dicionario=["ug", "unidade", "contratada", "cnpj_contratada", "vinculo", "q"]),
        "itens_resumo": _compacta(res.itens.get("itens_resumo", vazio), mod_tcees.COLUNAS_ITENS_RESUMO, dicionario=["vinculos", "q"]),
        "itens_contratada": _compacta(res.itens.get("itens_contratada", vazio), mod_tcees.COLUNAS_ITENS_CONTRATADA,
                                      dicionario=["contratada", "q"]),
        "contratacoes": _compacta(contratacoes_do_painel(res.contratacoes),
                                  ["cod_ibge", "ano", "contratacao", "ug", "objeto", "modalidade", "url_edital", "q"],
                                  dicionario=["ug", "modalidade", "q"]),
        "escolas": _compacta(escolas_usadas, mod_escolas.COLUNAS_CADASTRO, dicionario=["rede", "q"]),
        "escolas_vinculos": _compacta(res_esc.vinculos, ["fonte", "origem", "nome_origem", "cod_ibge", "co_entidade", "nota",
                                                         "metodo"], dicionario=["fonte", "metodo"]),
        "dados_manuais": {"portais": manuais.carregar(programas.carregar(), set(nomes)).get("portais", [])},
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, separators=(",", ":"), default=str)
    log.info("gravado %s (%d avisos)", saida, len(avisos))
    return dataset


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Dataset do painel simplificado — só dados abertos do TCE-ES.")
    p.add_argument("--anos", type=parse_anos, help=f"ex.: 2021-2026 (padrão: {PRIMEIRO_ANO} até o exercício corrente)")
    p.add_argument("--atualizar", choices=("nao", "vazios", "tudo", "offline"), default="nao",
                   help="nao: exercícios fechados do cache, o corrente renovado; tudo: baixa tudo de novo; "
                        "offline: só o cache")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    d = executar(args.anos, atualizar=args.atualizar)
    m = d["meta"]
    print(f"{SAIDA} · exercícios {m['anos']} (parcial: {m['ano_parcial']}, até o mês {m['ultimo_mes_parcial']}) · "
          f"{len(m['avisos'])} aviso(s)")
    for a in m["avisos"][:20]:
        print(f"  - {a['recurso']}: {a['aviso']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
