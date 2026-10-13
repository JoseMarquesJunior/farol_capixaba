"""Agregados de execução que a matriz do CNCA pede e o pipeline geral não produzia.

O painel de financiamento já reduz os empenhos do TCE-ES a credores, ações e
fontes. A matriz do CNCA precisa de outros cortes — mês a mês, por fonte com
restos a pagar, por elemento dentro da fonte, e a data do primeiro empenho — e
eles saem do MESMO recorte já em cache (``dados/bruto/tcees/``), sem uma única
requisição de rede.

O que muda por exercício, e que este módulo trata explicitamente em vez de
preencher com zero (ver ``docs/fase0_reconhecimento.md`` §3):

============================  ==========  ==============================================
Coluna                        Exercícios  Consequência
============================  ==========  ==============================================
``DataEmissao``               2024+       A defasagem repasse → empenho (A4.2) não existe
                                          em 2021-2023: sai ``None``, nunca 0.
``CodigoComplemento…``        2024+       O complemento de fonte só pode ser medido em
                                          2024-2025 — e, medido, é genérico (AAAA).
fontes ``551``/``569``        2023+       Antes disso o ES usava codificação local.
13 colunas de restos a pagar  todos       P25 e P26 valem para a série inteira.
============================  ==========  ==============================================

Nada aqui fala em "execução do CNCA": o CNCA não tem código próprio na
contabilidade municipal. Os agregados são por FONTE, por SUBFUNÇÃO e por AÇÃO —
e é assim que a camada de evidências tem de rotulá-los.
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
from .proveniencia import Consulta, Registro
from .tcees import (ClienteTcees, Municipios, ler_recorte, num_br, partes_empenhos, so_educacao,
                    DATASET_DESPESAS)

log = logging.getLogger(__name__)

#: Fontes de recursos do TCE-ES que interessam à matriz, com o nome oficial da
#: Tabela de Fontes e Complementos 2025 (conferida em 2026-09-23).
FONTES_CNCA = {
    "551": "Transferências do FNDE — PDDE",
    "569": "Outras transferências do FNDE",
}
#: Fontes do próprio município (impostos vinculados à educação e FUNDEB). Os códigos
#: MUDAM em 2023: até 2022 o ES usava a codificação local (111 impostos-educação, 112
#: FUNDEB 70%, 113 FUNDEB 30%); de 2023 em diante, o padrão da STN (500 e 540). Medido:
#: 111+112+113 respondem por 87% do empenho da função 12 em 2021 e 0% em 2023, e 500+540
#: fazem o inverso. Usar só o par novo daria "0% de recurso próprio" em 2021-2022.
FONTES_PROPRIAS = {
    "500": "Impostos e transferências de impostos (MDE)",
    "540": "Transferências do FUNDEB",
    "111": "Impostos e transferências de impostos — educação (código local, até 2022)",
    "112": "FUNDEB 70% (código local, até 2022)",
    "113": "FUNDEB 30% (código local, até 2022)",
}
#: Subfunção do ensino fundamental — o menor grão em que a alfabetização aparece.
SUBFUNCAO_FUNDAMENTAL = "361"

#: Ação ou programa que NOMEIA a alfabetização. Medido em 2021-2025: casa com uma
#: única combinação, em um único município (e é EJA) — ver fase0 §1.2.
#: ATENÇÃO: `parsing.norm` devolve MINÚSCULAS sem acento. Estas regex são aplicadas
#: sobre o resultado dele, então precisam de `re.I` — sem isso não casam com nada,
#: e o painel exibiria "nenhum município nomeia alfabetização" por bug, não por achado.
RX_ALFABETIZACAO = re.compile(r"alfabetiz|crianca alfabetizada|\bcnca\b|renalfa|cantinho", re.I)
#: Ação de premiação de boas práticas (art. 12 do Decreto 11.556/2023) — P42.
RX_PREMIACAO = re.compile(r"premia|premio|boas praticas|reconhecimento de pratica", re.I)

#: Elementos de despesa atípicos para um programa de alfabetização. NÃO é lista de
#: irregularidade: é lista de linhas que merecem olhar humano (A4.3).
ELEMENTOS_ATIPICOS = {
    "11": "Vencimentos e vantagens fixas — pessoal civil",
    "13": "Obrigações patronais",
    "51": "Obras e instalações",
    "61": "Aquisição de imóveis",
    "92": "Despesas de exercícios anteriores",
}

#: Colunas de restos a pagar que a matriz usa (P25, P26).
#:
#: O arquivo do TCE-ES separa DOIS tipos de linha, e não diz isso em lugar nenhum
#: (medido em 2021-2025, 23/09/2026):
#:
#: * ``AnoEmpenho == AnoReferencia`` — execução do próprio exercício: Empenhada,
#:   Liquidada e Paga preenchidas; as colunas de RP zeradas, exceto a INSCRIÇÃO
#:   (``RPPExercicio``/``RPNPExercicio``), que só aparece na última parte do ano;
#: * ``AnoEmpenho < AnoReferencia`` — movimento de restos a pagar de anos
#:   anteriores: Empenhada, Liquidada e Paga ZERADAS, e o dinheiro em
#:   ``RPNPLiquidado``, ``RPNPPago``, ``RPPPago``, ``RPNPCancelado``.
#:
#: Somar Empenhada nessas linhas daria zero e faria parecer que não há restos a
#: pagar — quando há R$ 152 mi de RP não processado pago só numa parte de 2022.
COLUNAS_RP = {
    "RPPExercicio": "rpp_inscrito",        # processados inscritos no exercício (31/12)
    "RPNPExercicio": "rpnp_inscrito",
    "RPPPago": "rpp_pago",
    "RPPCancelado": "rpp_cancelado",
    "RPNPLiquidado": "rpnp_liquidado",
    "RPNPPago": "rpnp_pago",
    "RPNPCancelado": "rpnp_cancelado",
}

#: Colunas que o dicionário do TCE-ES declara e que vêm SEMPRE vazias nos arquivos
#: dos municípios do ES em 2021-2025. Declarar não é publicar: sem isto, "nenhum
#: município tem restos a pagar transferidos" sairia como achado, quando é ausência
#: de dado. A idade do RP é medida por `AnoEmpenho` (ver `rp_idade`).
COLUNAS_RP_VAZIAS = ("RPPTransferido", "RPNPTransferido", "RPNPBloqueado",
                     "RPNPRecebido", "RPNPRestabelecido", "RPPRecebido")

CHAVE = ["cod_ibge", "ano"]


@dataclass
class ResultadoExecucao:
    """Os agregados, mais as consultas que os produziram e o que faltou."""

    mensal: pd.DataFrame = field(default_factory=pd.DataFrame)
    fontes: pd.DataFrame = field(default_factory=pd.DataFrame)
    fonte_elemento: pd.DataFrame = field(default_factory=pd.DataFrame)
    primeiro_empenho: pd.DataFrame = field(default_factory=pd.DataFrame)
    acoes_nomeadas: pd.DataFrame = field(default_factory=pd.DataFrame)
    complemento: pd.DataFrame = field(default_factory=pd.DataFrame)
    rp_idade: pd.DataFrame = field(default_factory=pd.DataFrame)
    dotacao_fonte: pd.DataFrame = field(default_factory=pd.DataFrame)
    dotacao_nomeada: pd.DataFrame = field(default_factory=pd.DataFrame)
    repasse_primeiro_mes: pd.DataFrame = field(default_factory=pd.DataFrame)
    consultas: list[Consulta] = field(default_factory=list)
    q_empenhos: dict[int, str] = field(default_factory=dict)
    q_despesas: dict[int, str] = field(default_factory=dict)
    avisos: list[dict[str, Any]] = field(default_factory=list)

    @property
    def tabelas(self) -> dict[str, pd.DataFrame]:
        return {"cnca_execucao_mensal": self.mensal, "cnca_execucao_fontes": self.fontes,
                "cnca_execucao_fonte_elemento": self.fonte_elemento,
                "cnca_execucao_primeiro_empenho": self.primeiro_empenho,
                "cnca_execucao_acoes_nomeadas": self.acoes_nomeadas,
                "cnca_execucao_complemento": self.complemento,
                "cnca_execucao_rp_idade": self.rp_idade,
                "cnca_execucao_dotacao_fonte": self.dotacao_fonte,
                "cnca_execucao_dotacao_nomeada": self.dotacao_nomeada,
                "cnca_repasse_primeiro_mes": self.repasse_primeiro_mes}


# ------------------------------------------------------------------ preparo

def _fonte(serie: pd.Series) -> pd.Series:
    """Código de fonte sem zero à esquerda ('0551' e '551' são a mesma fonte)."""
    return serie.fillna("").astype(str).str.strip().str.lstrip("0").replace("", pd.NA)


def preparar(df: pd.DataFrame, mun: Municipios, ano: int) -> pd.DataFrame:
    """Recorte bruto (58 colunas) → tabela normalizada, guardando o que a matriz usa.

    Diferente de `tcees.empenhos`, que reduz às colunas do painel geral: aqui ficam
    a data de emissão, o complemento de fonte, o subelemento e os restos a pagar.
    Colunas ausentes no leiaute do exercício viram NA — nunca zero.
    """
    d = df.rename(columns={"AnoReferencia": "Ano", "MesReferencia": "Mes"}).copy()
    d["cod_ibge"] = d["EsferaAdministrativa"].map(mun.cod)
    d = d[d["cod_ibge"].notna()].copy()
    if d.empty:
        return d
    d["cod_ibge"] = d["cod_ibge"].astype(int)
    d["ano"] = pd.to_numeric(d.get("Ano"), errors="coerce").fillna(ano).astype(int)
    d["mes"] = pd.to_numeric(d.get("Mes"), errors="coerce")
    for bruto, novo in (("Empenhada", "empenhada"), ("Liquidada", "liquidada"), ("Paga", "paga")):
        d[novo] = num_br(d[bruto]).fillna(0.0)
    for bruto, novo in COLUNAS_RP.items():
        d[novo] = num_br(d[bruto]).fillna(0.0) if bruto in d.columns else 0.0
    # O ano do empenho, ao lado do ano de referência, é o que dá a IDADE do resto a
    # pagar — e é a única forma de medi-la, já que RPPTransferido vem vazio.
    d["ano_empenho"] = pd.to_numeric(d.get("AnoEmpenho"), errors="coerce")
    d["intra"] = d["CodigoModalidade"].astype(str).str.strip() == "91"
    d["fonte"] = _fonte(d["CodigoFonteReduzida"])
    d["subfuncao"] = d["CodigoSubFuncao"].astype(str).str.strip().str.lstrip("0")
    d["elemento"] = d["CodigoElemento"].astype(str).str.strip().str.lstrip("0").str.zfill(2)
    # 2021-2023 não trazem estas duas colunas: NA, para o indicador dizer "não existe".
    # A data vem ISO ("2024-03-15 00:00:00") nos arquivos de 2024-2025; `format="mixed"`
    # aceita variação de leiaute sem adivinhar dia/mês ao contrário.
    d["data_emissao"] = pd.to_datetime(d["DataEmissao"], errors="coerce", format="mixed") \
        if "DataEmissao" in d.columns else pd.NaT
    d["complemento"] = (d["CodigoComplementoFontesDestinacoesRecursos"].astype(str).str.strip()
                        if "CodigoComplementoFontesDestinacoesRecursos" in d.columns else pd.NA)
    d["texto"] = (d["NomePrograma"].fillna("") + " " + d["NomeAcao"].fillna("") + " "
                  + d["NomeDetalhamento"].fillna("")).map(norm)
    return d[~d["intra"]]


# --------------------------------------------------------------- reduções

def reduzir(d: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Uma parte do ano → somas e contagens combináveis entre partes.

    Tudo aqui é soma, contagem ou mínimo: pode ser recombinado com o de outra
    parte sem reler o arquivo (é o que mantém a memória sob controle, como na
    redução do painel geral).
    """
    if d.empty:
        return {k: pd.DataFrame() for k in ("mensal", "fontes", "fonte_elemento", "primeiro_empenho",
                                            "acoes_nomeadas", "complemento", "rp_idade")}
    somas = dict(empenhada=("empenhada", "sum"), liquidada=("liquidada", "sum"), paga=("paga", "sum"),
                 lancamentos=("empenhada", "size"))
    rp = {novo: (novo, "sum") for novo in COLUNAS_RP.values()}
    nomeadas = d[d["texto"].str.contains(RX_ALFABETIZACAO, na=False)
                 | d["texto"].str.contains(RX_PREMIACAO, na=False)]
    com_data = d[d["data_emissao"].notna()]
    antigos = d[d["ano_empenho"].notna() & (d["ano_empenho"] < d["ano"])]
    return {
        # A4.4: perfil mensal por subfunção (a 361 é a que interessa; as outras dão o contraste).
        "mensal": d.groupby(CHAVE + ["subfuncao", "mes"], as_index=False).agg(
            empenhada=("empenhada", "sum"), liquidada=("liquidada", "sum"), paga=("paga", "sum")),
        # A4.1, A6.1, P24, P25, P26: a fonte com execução e restos a pagar.
        "fontes": d.groupby(CHAVE + ["fonte", "NomeFonteReduzida"], as_index=False).agg(**somas, **rp),
        # A4.3: elemento dentro da fonte, para revisão humana.
        "fonte_elemento": d.groupby(CHAVE + ["fonte", "elemento", "DescricaoElemento"], as_index=False).agg(
            empenhada=("empenhada", "sum"), lancamentos=("empenhada", "size")),
        # A4.2: data do primeiro empenho de cada fonte (só existe de 2024 em diante).
        "primeiro_empenho": (com_data.groupby(CHAVE + ["fonte"], as_index=False)
                             .agg(primeiro_empenho=("data_emissao", "min"),
                                  ultimo_empenho=("data_emissao", "max"),
                                  lancamentos_com_data=("data_emissao", "size"))
                             if not com_data.empty else pd.DataFrame()),
        # A3.1, P42: a ação que NOMEIA alfabetização ou premiação de boas práticas.
        "acoes_nomeadas": nomeadas.groupby(
            CHAVE + ["CodigoAcao", "NomeAcao", "NomePrograma", "fonte"], as_index=False).agg(**somas),
        # A prova da limitação estrutural: com que complemento de fonte se empenha.
        "complemento": (d[d["complemento"].notna()].groupby(CHAVE + ["fonte", "complemento"], as_index=False)
                        .agg(empenhada=("empenhada", "sum"), lancamentos=("empenhada", "size"))
                        if d["complemento"].notna().any() else pd.DataFrame()),
        # P25, P26: movimento do exercício sobre empenhos de ANOS ANTERIORES — é isto
        # que dá a idade do resto a pagar, já que RPPTransferido vem vazio na fonte.
        # O dinheiro está nas colunas de RP, não em Empenhada/Liquidada/Paga.
        "rp_idade": (antigos.groupby(CHAVE + ["fonte", "ano_empenho"], as_index=False)
                     .agg(**{novo: (novo, "sum") for novo in COLUNAS_RP.values()},
                          lancamentos=("empenhada", "size"))
                     if not antigos.empty else pd.DataFrame()),
    }


def combinar(partes: Iterable[dict[str, pd.DataFrame]], q_por_ano: dict[int, str]) -> dict[str, pd.DataFrame]:
    """Junta as reduções das partes de todos os anos numa tabela por chave."""
    partes = [p for p in partes if p]
    if not partes:
        return {}
    q = lambda df: df.assign(q=df["ano"].map(q_por_ano)) if not df.empty else df

    def junta(chave: str) -> pd.DataFrame:
        pedacos = [p[chave] for p in partes if chave in p and not p[chave].empty]
        return pd.concat(pedacos, ignore_index=True) if pedacos else pd.DataFrame()

    saida: dict[str, pd.DataFrame] = {}

    m = junta("mensal")
    saida["mensal"] = q(m.groupby(CHAVE + ["subfuncao", "mes"], as_index=False).sum()) if not m.empty else m

    f = junta("fontes")
    if not f.empty:
        agg = {c: "sum" for c in ["empenhada", "liquidada", "paga", "lancamentos", *COLUNAS_RP.values()]}
        f = f.groupby(CHAVE + ["fonte", "NomeFonteReduzida"], as_index=False).agg(agg)
        f = f[f[["empenhada", "liquidada", "paga"]].abs().sum(axis=1) > 0.005]
    saida["fontes"] = q(f)

    fe = junta("fonte_elemento")
    if not fe.empty:
        fe = fe.groupby(CHAVE + ["fonte", "elemento", "DescricaoElemento"], as_index=False).sum()
        fe = fe[fe["empenhada"].abs() > 0.005]
        fe["atipico"] = fe["elemento"].isin(ELEMENTOS_ATIPICOS)
    saida["fonte_elemento"] = q(fe)

    pe = junta("primeiro_empenho")
    if not pe.empty:
        pe = pe.groupby(CHAVE + ["fonte"], as_index=False).agg(
            primeiro_empenho=("primeiro_empenho", "min"), ultimo_empenho=("ultimo_empenho", "max"),
            lancamentos_com_data=("lancamentos_com_data", "sum"))
    saida["primeiro_empenho"] = q(pe)

    an = junta("acoes_nomeadas")
    if not an.empty:
        an = an.groupby(CHAVE + ["CodigoAcao", "NomeAcao", "NomePrograma", "fonte"], as_index=False).sum()
        texto = (an["NomePrograma"].fillna("") + " " + an["NomeAcao"].fillna("")).map(norm)
        an["alfabetizacao"] = texto.str.contains(RX_ALFABETIZACAO, na=False)
        an["premiacao"] = texto.str.contains(RX_PREMIACAO, na=False)
    saida["acoes_nomeadas"] = q(an)

    c = junta("complemento")
    saida["complemento"] = q(c.groupby(CHAVE + ["fonte", "complemento"], as_index=False).sum()) if not c.empty else c

    ri = junta("rp_idade")
    if not ri.empty:
        ri = ri.groupby(CHAVE + ["fonte", "ano_empenho"], as_index=False).sum()
        ri["idade_anos"] = (ri["ano"] - ri["ano_empenho"]).astype(int)
        # "Processado" = já liquidado quando virou resto a pagar. O que o exercício
        # movimentou de RP PROCESSADO de anos anteriores é o que responde P25.
        ri["rp_processado_movimentado"] = ri["rpp_pago"] + ri["rpp_cancelado"]
        ri["rp_nao_processado_movimentado"] = ri["rpnp_pago"] + ri["rpnp_cancelado"]
        colunas = [c for c in COLUNAS_RP.values()]
        ri = ri[ri[colunas].abs().sum(axis=1) > 0.005]
    saida["rp_idade"] = q(ri)
    return saida


# ------------------------------------------------------- dotação (despesas)

def dotacao_por_fonte(df: pd.DataFrame, mun: Municipios, ano: int) -> pd.DataFrame:
    """Recorte de "Despesas dos municípios" → dotação e execução POR FONTE.

    O painel geral já agrega a dotação por AÇÃO; a matriz precisa dela por fonte,
    que é o único corte em que a fonte 569 (proxy do PAR) aparece. Este arquivo
    NÃO traz o complemento de fonte — só os empenhos trazem, e só de 2024.
    """
    d = df.copy()
    d["cod_ibge"] = d["EsferaAdministrativa"].map(mun.cod)
    d = d[d["cod_ibge"].notna()]
    if d.empty:
        return pd.DataFrame()
    d = d.assign(
        cod_ibge=d["cod_ibge"].astype(int),
        ano=pd.to_numeric(d.get("Ano"), errors="coerce").fillna(ano).astype(int),
        fonte=_fonte(d["CodigoFonteReduzida"]),
        subfuncao=d["CodigoSubFuncao"].astype(str).str.strip().str.lstrip("0"),
        previsao_inicial=num_br(d["PrevisaoInicial"]).fillna(0.0),
        previsao_atualizada=num_br(d["PrevisaoAtualizada"]).fillna(0.0),
        empenhada=num_br(d["Empenhada"]).fillna(0.0),
        liquidada=num_br(d["Liquidada"]).fillna(0.0),
        paga=num_br(d["Paga"]).fillna(0.0),
    )
    d = d[d["CodigoModalidade"].astype(str).str.strip() != "91"]
    return d.groupby(CHAVE + ["fonte", "NomeFonteReduzida"], as_index=False)[
        ["previsao_inicial", "previsao_atualizada", "empenhada", "liquidada", "paga"]].sum()


def dotacao_nomeada(df: pd.DataFrame, mun: Municipios, ano: int) -> pd.DataFrame:
    """Ações com dotação cujo nome cita alfabetização ou premiação de boas práticas (A3.1, P42)."""
    d = df.copy()
    d["cod_ibge"] = d["EsferaAdministrativa"].map(mun.cod)
    d = d[d["cod_ibge"].notna()]
    if d.empty:
        return pd.DataFrame()
    texto = (d["NomePrograma"].fillna("") + " " + d["NomeAcao"].fillna("")).map(norm)
    d = d[texto.str.contains(RX_ALFABETIZACAO, na=False) | texto.str.contains(RX_PREMIACAO, na=False)]
    if d.empty:
        return pd.DataFrame()
    d = d.assign(
        cod_ibge=d["cod_ibge"].astype(int),
        ano=pd.to_numeric(d.get("Ano"), errors="coerce").fillna(ano).astype(int),
        fonte=_fonte(d["CodigoFonteReduzida"]),
        previsao_inicial=num_br(d["PrevisaoInicial"]).fillna(0.0),
        previsao_atualizada=num_br(d["PrevisaoAtualizada"]).fillna(0.0),
        empenhada=num_br(d["Empenhada"]).fillna(0.0),
    )
    t = (d["NomePrograma"].fillna("") + " " + d["NomeAcao"].fillna("")).map(norm)
    d["alfabetizacao"] = t.str.contains(RX_ALFABETIZACAO, na=False)
    d["premiacao"] = t.str.contains(RX_PREMIACAO, na=False)
    return d.groupby(CHAVE + ["CodigoAcao", "NomeAcao", "NomePrograma", "fonte",
                              "alfabetizacao", "premiacao"], as_index=False)[
        ["previsao_inicial", "previsao_atualizada", "empenhada"]].sum()


# --------------------------------------------------------------- execução

def executar(nomes_ibge: dict[int, str], anos: Iterable[int], *, atualizar: str = "nao",
             registro: Registro | None = None) -> ResultadoExecucao:
    """Lê o recorte já em cache e devolve os agregados da matriz.

    Com `atualizar="nao"` (o padrão) não há rede: o que não estiver em cache é
    registrado como aviso e o resto sai normalmente — uma fonte que falta não
    derruba as outras.
    """
    anos = sorted(anos)
    mun = Municipios(nomes_ibge)
    cliente = ClienteTcees(atualizar=atualizar)
    reg = registro or Registro()
    res = ResultadoExecucao()
    partes: list[dict[str, pd.DataFrame]] = []

    # --- empenhos, parte a parte (a parte inteira é descartada depois da redução)
    for ano, r in partes_empenhos(cliente, anos):
        nome = r["nome"].strip()
        chave = f"empenhos/{ano}/{nome}"
        try:
            a = cliente.recorte_zip(chave, r["url"], so_educacao,
                                    {"recurso": nome, "filtro": "CodigoFuncao = 12"})
        except Exception as e:                      # noqa: BLE001 — uma parte que falha não derruba o resto
            res.avisos.append({"fonte": "TCE-ES", "ano": ano, "aviso": f"{nome}: {e}"})
            continue
        if not a.obtido_em or a.caminho is None:
            res.avisos.append({"fonte": "TCE-ES", "ano": ano, "aviso": f"{nome}: fora do cache (sem rede)"})
            continue
        c = a.consulta(f"TCE-ES — Empenhos dos municípios, {nome} (recorte: função 12)")
        reg.adicionar(c)
        res.consultas.append(c)
        res.q_empenhos[ano] = c.id
        try:
            bruto = ler_recorte(a)
            partes.append(reduzir(preparar(bruto, mun, ano)))
            del bruto
        except Exception as e:                      # noqa: BLE001
            res.avisos.append({"fonte": "TCE-ES", "ano": ano, "aviso": f"{nome}: leitura falhou: {e}"})
        log.info("execução: %s lido", nome)

    for chave, tabela in combinar(partes, res.q_empenhos).items():
        setattr(res, chave, tabela)

    # --- dotação (arquivo agregado, um por ano)
    dot, dot_nom = [], []
    for ano in anos:
        rec = next((x for x in cliente.recursos(DATASET_DESPESAS)
                    if norm(x["nome"]) == f"municipios-despesas-{ano}.zip"), None)
        if rec is None:
            res.avisos.append({"fonte": "TCE-ES", "ano": ano, "aviso": "despesas: recurso não encontrado no catálogo"})
            continue
        chave = f"despesas/{ano}"
        try:
            a = cliente.recorte_zip(chave, rec["url"], so_educacao,
                                    {"recurso": rec["nome"], "filtro": "CodigoFuncao = 12"})
        except Exception as e:                      # noqa: BLE001
            res.avisos.append({"fonte": "TCE-ES", "ano": ano, "aviso": f"despesas {ano}: {e}"})
            continue
        if not a.obtido_em or a.caminho is None:
            res.avisos.append({"fonte": "TCE-ES", "ano": ano, "aviso": f"despesas {ano}: fora do cache (sem rede)"})
            continue
        c = a.consulta(f"TCE-ES — Despesas dos municípios (agregado com dotação), {ano} (recorte: função 12)")
        reg.adicionar(c)
        res.consultas.append(c)
        res.q_despesas[ano] = c.id
        try:
            bruto = ler_recorte(a)
            if not (t := dotacao_por_fonte(bruto, mun, ano)).empty:
                dot.append(t.assign(q=c.id))
            if not (t := dotacao_nomeada(bruto, mun, ano)).empty:
                dot_nom.append(t.assign(q=c.id))
            del bruto
        except Exception as e:                      # noqa: BLE001
            res.avisos.append({"fonte": "TCE-ES", "ano": ano, "aviso": f"despesas {ano}: leitura falhou: {e}"})
    res.dotacao_fonte = pd.concat(dot, ignore_index=True) if dot else pd.DataFrame()
    res.dotacao_nomeada = pd.concat(dot_nom, ignore_index=True) if dot_nom else pd.DataFrame()

    # --- primeiro repasse do FNDE (cache da CGU já recortado pelo pipeline geral)
    try:
        res.repasse_primeiro_mes = primeiro_repasse_fnde(nomes_ibge, anos)
    except Exception as e:                          # noqa: BLE001
        res.avisos.append({"fonte": "FNDE", "ano": None, "aviso": f"primeiro repasse: {e}"})
    return res


def primeiro_repasse_fnde(nomes_ibge: dict[int, str], anos: Iterable[int]) -> pd.DataFrame:
    """Mês do PRIMEIRO repasse do FNDE a cada município no exercício (A4.2).

    A CGU publica o mês de pagamento, não o dia: a data devolvida é o **primeiro
    dia do mês**, e a defasagem calculada em cima dela tem erro de até 30 dias —
    quem consumir precisa dizer isso, e o indicador de A4.2 diz.

    Só entram repasses ao PRÓPRIO município (prefeitura, secretaria ou fundo):
    o PDDE vai às unidades executoras e não transita pelo orçamento municipal,
    então não faz sentido cobrar empenho dele.
    """
    from . import fnde as mod_fnde

    mapa = mod_fnde.mapa_municipios(nomes_ibge)
    linhas = []
    for ano in sorted(anos):
        pasta = mod_fnde.PASTA_CACHE / str(ano)
        if not pasta.exists():
            continue
        for caminho in sorted(pasta.glob("transferencias_*_ES.csv.gz")):
            try:
                d = mod_fnde.classificar(mod_fnde.ler_recorte(caminho))
            except Exception as e:                  # noqa: BLE001 — um mês ilegível não derruba o resto
                log.warning("repasse %s: %s", caminho.name, e)
                continue
            d = d[d["destino"] == "municipio"]
            if d.empty:
                continue
            d = d.assign(cod_ibge=d["municipio"].map(norm).map(mapa))
            d = d[d["cod_ibge"].notna()]
            if d.empty:
                continue
            d["ano"] = pd.to_numeric(d["ano_mes"].str[:4], errors="coerce")
            d["mes"] = pd.to_numeric(d["ano_mes"].str[4:6], errors="coerce")
            linhas.append(d.groupby(["cod_ibge", "ano"], as_index=False).agg(
                primeiro_mes=("mes", "min"), valor=("valor", "sum")))
    if not linhas:
        return pd.DataFrame()
    d = pd.concat(linhas, ignore_index=True).groupby(["cod_ibge", "ano"], as_index=False).agg(
        primeiro_mes=("primeiro_mes", "min"), valor=("valor", "sum"))
    d["cod_ibge"] = d["cod_ibge"].astype(int)
    d["ano"] = d["ano"].astype(int)
    d["primeiro_repasse"] = pd.to_datetime(
        d["ano"].astype(str) + "-" + d["primeiro_mes"].astype(int).astype(str).str.zfill(2) + "-01")
    return d


def nomes_municipios() -> dict[int, str]:
    """Código IBGE → nome, do dataset já processado (sem rede).

    A lista canônica vem de `/entes` do SICONFI, mas ela já está gravada em
    `financiamento_anual.csv`; reler dali evita uma requisição só para nomear
    município, e o casamento com o nome do TCE-ES é o mesmo (`Municipios` normaliza).

    O Estado (código 32) também está nesse CSV e é descartado aqui: o universo da
    fiscalização são os 78 municípios, e deixá-lo passar faria toda contagem de
    cobertura sair sobre 79.
    """
    caminho = PROCESSADO / "financiamento_anual.csv"
    if not caminho.exists():
        raise FileNotFoundError(f"{caminho} não existe — rode o pipeline geral antes")
    d = pd.read_csv(caminho, usecols=["cod_ibge", "ente"]).drop_duplicates("cod_ibge")
    return {int(r.cod_ibge): str(r.ente) for r in d.itertuples(index=False)
            if len(str(int(r.cod_ibge))) == 7}


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Agregados de execução para a matriz do CNCA (usa o cache; sem rede).")
    p.add_argument("--anos", default="2021-2025")
    p.add_argument("--atualizar", default="nao", choices=["nao", "vazios", "tudo", "offline"])
    args = p.parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    ini, _, fim = args.anos.partition("-")
    anos = range(int(ini), int(fim or ini) + 1)
    res = executar(nomes_municipios(), anos, atualizar=args.atualizar)
    PROCESSADO.mkdir(parents=True, exist_ok=True)
    for nome, df in res.tabelas.items():
        df.to_csv(PROCESSADO / f"{nome}.csv", index=False, encoding="utf-8")
        print(f"{nome}: {len(df):,} linhas")
    from .evidencias import gravar_consultas
    gravar_consultas(res.consultas)
    for a in res.avisos:
        print(f"  aviso: {a}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
