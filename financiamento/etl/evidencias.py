"""A tabela de evidências da matriz do CNCA: um indício por linha, com a fonte na linha.

Junta três coisas que já existem separadas — a matriz (`config/matriz_cnca.yaml`),
os agregados de execução (`etl/execucao.py`) e o dataset do painel de
financiamento — e produz o papel de trabalho da seção 5 do prompt da
fiscalização: uma linha por município × achado × indicador, com valor, status,
tipo de evidência, confiança e a proveniência completa (fonte, endpoint, arquivo
do cache, instante da coleta e SHA-256 do arquivo bruto).

Três regras que o módulo inteiro obedece:

1. **Nenhuma regra produz "achado".** Produz `indicio_risco`, `sem_indicio`,
   `inconclusivo` ou `sem_dado_publico`. Quem transforma indício em achado é o
   auditor, com o documento na mão.
2. **Lacuna nunca vira zero.** Município sem dado no exercício sai com valor
   ``None`` e status ``sem_dado_publico``, com a nota dizendo por quê.
3. **O rótulo diz o que o número mede.** Como o CNCA não tem código próprio na
   contabilidade municipal (ver `docs/fase0_reconhecimento.md` §1), nenhum
   indicador daqui se chama "execução do CNCA": eles medem fonte, subfunção ou
   ação, e a nota de cada linha repete isso.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd

from . import censo_alfabetizacao as mod_censo
from . import execucao as mod_execucao
from . import matriz as mod_matriz
from .config import PROCESSADO
from .matriz import Achado, Matriz

log = logging.getLogger(__name__)

PASTA_EVIDENCIAS = PROCESSADO.parent / "evidencias"

#: As colunas do papel de trabalho, na ordem em que o auditor as lê.
#: `q` guarda os IDS de consulta da linha, além do endpoint e do hash já resolvidos.
#: Parece redundante e não é: o CSV precisa da proveniência legível, e o painel precisa
#: do id para reabrir a consulta inteira no "ver fonte" — sem ele, o diálogo abre vazio.
COLUNAS = [
    "municipio_ibge", "municipio", "questao_matriz", "achado_id", "pergunta_questionario",
    "indicador", "rotulo", "valor", "unidade", "ano", "status", "tipo_evidencia", "confianca",
    "fonte", "endpoint_ou_arquivo", "parametros", "data_extracao", "hash_bruto", "nota", "q",
]

#: Fontes que este módulo cita. O texto vai para a coluna `fonte` da evidência.
FONTE_EMPENHOS = "TCE-ES — Empenhos dos municípios (dados abertos, recorte da função 12)"
FONTE_DESPESAS = "TCE-ES — Despesas dos municípios (agregado com dotação, recorte da função 12)"
FONTE_CGU = "CGU — Portal da Transparência, transferências do FNDE (recorte UF=ES)"
FONTE_CENSO = "Censo Escolar (INEP), banco local do NEDUC"

#: Nota que acompanha todo indicador calculado sobre fonte de recursos.
NOTA_FONTE = ("Mede a FONTE de recursos, não o CNCA: não existe fonte, complemento, programa ou "
              "ação que identifique o CNCA na contabilidade municipal do ES.")


class ErroEvidencias(RuntimeError):
    """Falta uma tabela de entrada que o cálculo exige."""


# --------------------------------------------------------------- contexto

@dataclass
class Contexto:
    """O que os cálculos enxergam: a matriz, as tabelas e a proveniência."""

    matriz: Matriz
    tabelas: dict[str, pd.DataFrame]
    municipios: dict[int, str]
    anos: tuple[int, ...]
    consultas: pd.DataFrame = field(default_factory=pd.DataFrame)

    def tabela(self, nome: str, *, obrigatoria: bool = True) -> pd.DataFrame:
        d = self.tabelas.get(nome)
        if d is None or d.empty:
            if obrigatoria:
                raise ErroEvidencias(f"tabela ausente ou vazia: {nome}")
            return pd.DataFrame()
        return d

    def param(self, nome: str) -> Any:
        return self.matriz.param(nome)

    def proveniencia(self, q: Any) -> dict[str, str | None]:
        """Ids de consulta ("a;b;c") → endpoint, parâmetros, instante e hash.

        Com mais de uma consulta por número (o ano tem 3 a 5 partes de empenho),
        fica a primeira em ordem estável e o total aparece entre parênteses — o
        detalhe completo continua em `consultas.csv`, que o painel abre no
        "ver fonte".
        """
        vazio = {"endpoint_ou_arquivo": None, "parametros": None, "data_extracao": None, "hash_bruto": None}
        if not isinstance(q, str) or not q or self.consultas.empty:
            return vazio
        ids = [i for i in q.split(";") if i]
        achadas = self.consultas[self.consultas["id"].isin(ids)]
        if achadas.empty:
            return vazio
        primeira = achadas.sort_values("id").iloc[0]
        sufixo = f" (+{len(achadas) - 1} consultas)" if len(achadas) > 1 else ""
        return {
            "endpoint_ou_arquivo": f"{primeira.get('arquivo') or primeira.get('url')}{sufixo}",
            "parametros": str(primeira.get("descricao") or ""),
            "data_extracao": achadas["obtido_em"].min(),
            "hash_bruto": primeira.get("sha256") if isinstance(primeira.get("sha256"), str) else None,
        }


# ------------------------------------------------------------- utilidades

def _pct(a: float | None, b: float | None) -> float | None:
    """a ÷ b × 100, com None quando o denominador não sustenta a divisão."""
    if a is None or b is None or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    if pd.isna(a) or pd.isna(b) or abs(b) < 0.005:
        return None
    return round(a / b * 100, 2)


def _num(v: Any) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else round(f, 2)


def _linha(ctx: Contexto, achado: Achado, indicador_id: str, *, cod_ibge: int, ano: int | None,
           valor: Any, status: str, nota: str, fonte: str, q: Any = None,
           pergunta: str | None = None) -> dict[str, Any]:
    """Uma linha do papel de trabalho, com a proveniência já resolvida."""
    ind = next((i for i in achado.indicadores if i.id == indicador_id), None)
    if ind is None:
        raise ErroEvidencias(f"achado {achado.id} não declara o indicador {indicador_id!r} no YAML")
    if status not in mod_matriz.STATUS:
        raise ErroEvidencias(f"status inválido: {status!r}")
    return {
        "municipio_ibge": cod_ibge, "municipio": ctx.municipios.get(cod_ibge, ""),
        "questao_matriz": achado.questao, "achado_id": achado.id,
        "pergunta_questionario": pergunta or ";".join(achado.perguntas),
        "indicador": ind.id, "rotulo": ind.rotulo, "valor": valor, "unidade": ind.unidade, "ano": ano,
        "status": status, "tipo_evidencia": achado.tipo_evidencia, "confianca": achado.confianca,
        "fonte": fonte, **ctx.proveniencia(q), "nota": " ".join(nota.split()),
        "q": q if isinstance(q, str) else None,
    }


def _por_municipio_ano(ctx: Contexto) -> Iterable[tuple[int, int]]:
    for cod in sorted(ctx.municipios):
        for ano in ctx.anos:
            yield cod, ano


def _busca(d: pd.DataFrame, **filtros: Any) -> pd.DataFrame:
    for coluna, valor in filtros.items():
        if coluna not in d.columns:
            return d.iloc[0:0]
        d = d[d[coluna] == valor]
    return d


# ------------------------------------------------------------- cálculos

def a3_1(ctx: Contexto, a: Achado) -> list[dict[str, Any]]:
    """Previsão do CNCA no PPA/LOA/QDD — pelo que o orçamento NOMEIA e pela fonte 569."""
    dot = ctx.tabela("cnca_execucao_dotacao_fonte", obrigatoria=False)
    nom = ctx.tabela("cnca_execucao_dotacao_nomeada", obrigatoria=False)
    linhas = []
    for cod, ano in _por_municipio_ano(ctx):
        d569 = _busca(dot, cod_ibge=cod, ano=ano, fonte="569")
        v569 = _num(d569["previsao_atualizada"].sum()) if not d569.empty else None
        alfa = nom[(nom["cod_ibge"] == cod) & (nom["ano"] == ano) & nom["alfabetizacao"]] if not nom.empty \
            else pd.DataFrame()
        v_alfa = _num(alfa["previsao_atualizada"].sum()) if not alfa.empty else None
        # Dotação registrada como exatamente zero é ausência de dotação, não um valor:
        # gravá-la faria a linha sair como "sem dado público" com R$ 0,00 no valor.
        v569 = v569 or None
        v_alfa = v_alfa or None
        tem_alfa, tem_569 = v_alfa is not None, v569 is not None

        # A3.1 não marca município: a ausência de identificação do CNCA na classificação
        # orçamentária vale para os 78, e está dita uma vez na constatação C3.1. O que sai
        # por município é contexto para a resposta ao questionário.
        if tem_alfa:
            status, nota = "inconclusivo", ("Há ação orçamentária que nomeia alfabetização, com dotação. "
                                            "Conferir se a ação é mesmo do CNCA: as encontradas no ES em "
                                            "2021-2022 são de EJA/Brasil Alfabetizado. Ver constatação C3.1.")
        elif tem_569:
            status, nota = "inconclusivo", ("Há dotação na fonte 569, mas nenhuma ação nomeia alfabetização: "
                                            "o recurso existe, a rastreabilidade não. " + NOTA_FONTE
                                            + " Ver constatação C3.1.")
        else:
            status, nota = "sem_dado_publico", ("Nem dotação na fonte 569, nem ação que nomeie alfabetização "
                                                "neste exercício. Isso NÃO é indício contra o município: nenhum "
                                                "dos 78 identifica o CNCA na classificação orçamentária, e a "
                                                "maioria usa ação genérica. Ver constatação C3.1.")
        linhas.append(_linha(ctx, a, "acao_alfabetizacao_dotada", cod_ibge=cod, ano=ano, valor=v_alfa,
                             status=status, nota=nota, fonte=FONTE_DESPESAS,
                             q=alfa["q"].iloc[0] if not alfa.empty and "q" in alfa else None, pergunta="P17"))
        linhas.append(_linha(ctx, a, "dotacao_fonte_569", cod_ibge=cod, ano=ano, valor=v569,
                             status=status, nota=nota, fonte=FONTE_DESPESAS,
                             q=d569["q"].iloc[0] if not d569.empty and "q" in d569 else None, pergunta="P28"))
    return linhas


def a4_1(ctx: Contexto, a: Achado) -> list[dict[str, Any]]:
    """Baixa execução — na fonte 569 (proxy do PAR), com o PDDE-CNCA recebido ao lado."""
    dot = ctx.tabela("cnca_execucao_dotacao_fonte", obrigatoria=False)
    cnca = ctx.tabela("cnca_municipio", obrigatoria=False)
    limite = ctx.param("execucao_baixa_pct")
    linhas = []
    for cod, ano in _por_municipio_ano(ctx):
        d = _busca(dot, cod_ibge=cod, ano=ano, fonte="569")
        dotacao = _num(d["previsao_atualizada"].sum()) if not d.empty else None
        empenhado = _num(d["empenhada"].sum()) if not d.empty else None
        exec_pct = _pct(empenhado, dotacao)
        if exec_pct is None:
            status = "sem_dado_publico"
            nota = ("Sem dotação na fonte 569 neste exercício — a fonte só aparece nos empenhos a partir "
                    "de 2023. Não é zero de execução: é ausência de base para o cálculo.")
        elif exec_pct < limite:
            status = "indicio_risco"
            nota = (f"Executado {exec_pct:.1f}% da dotação da fonte 569, abaixo do limiar de {limite:.0f}% "
                    f"(parâmetro a calibrar). " + NOTA_FONTE)
        else:
            status = "sem_indicio"
            nota = f"Executado {exec_pct:.1f}% da dotação da fonte 569. " + NOTA_FONTE
        linhas.append(_linha(ctx, a, "execucao_fonte_569", cod_ibge=cod, ano=ano, valor=exec_pct,
                             status=status, nota=nota, fonte=FONTE_DESPESAS,
                             q=d["q"].iloc[0] if not d.empty and "q" in d else None))

        c = _busca(cnca, cod_ibge=cod, ano=ano)
        recebido = _num(c["pdde_cnca"].sum()) if not c.empty else None
        linhas.append(_linha(
            ctx, a, "pdde_cnca_recebido", cod_ibge=cod, ano=ano, valor=recebido,
            status="sem_dado_publico" if recebido is None else "sem_indicio",
            nota=("Valor RECEBIDO pelas escolas, não executado: o PDDE-CNCA é gasto pela unidade executora e "
                  "prestado ao FNDE, fora da contabilidade municipal. Ausência aqui significa nenhum pagamento "
                  "nos arquivos da CGU do exercício, não 'não recebeu'."),
            fonte=FONTE_CGU, q=c["q"].iloc[0] if not c.empty and "q" in c else None))
    return linhas


def a4_2(ctx: Contexto, a: Achado) -> list[dict[str, Any]]:
    """Defasagem entre o repasse federal e o primeiro empenho na fonte — só 2024-2025."""
    pe = ctx.tabela("cnca_execucao_primeiro_empenho", obrigatoria=False)
    rep = ctx.tabela("cnca_repasse_primeiro_mes", obrigatoria=False)
    limite = ctx.param("defasagem_dias")
    linhas = []
    for cod, ano in _por_municipio_ano(ctx):
        emp = pe[(pe["cod_ibge"] == cod) & (pe["ano"] == ano) & pe["fonte"].isin(["569", "551"])] \
            if not pe.empty else pd.DataFrame()
        r = _busca(rep, cod_ibge=cod, ano=ano)
        valor, status, nota = None, "sem_dado_publico", ""
        if emp.empty:
            nota = ("A data de emissão do empenho não existe no leiaute de 2021-2023 do TCE-ES, e não há "
                    "empenho datado nas fontes 551/569 neste exercício. O indicador não existe aqui — "
                    "não é defasagem zero.")
        elif r.empty:
            nota = "Sem repasse do FNDE identificado ao município no exercício: não há de que medir a defasagem."
        else:
            primeiro_emp = pd.to_datetime(emp["primeiro_empenho"], errors="coerce").min()
            primeiro_rep = pd.to_datetime(r["primeiro_repasse"], errors="coerce").min()
            if pd.isna(primeiro_emp) or pd.isna(primeiro_rep):
                nota = "Data ausente em uma das pontas."
            else:
                valor = int((primeiro_emp - primeiro_rep).days)
                status = "indicio_risco" if valor > limite else "sem_indicio"
                nota = (f"Primeiro repasse em {primeiro_rep:%Y-%m} (a CGU dá o MÊS, não o dia: erro de até 30 "
                        f"dias), primeiro empenho na fonte em {primeiro_emp:%Y-%m-%d}. Limiar de {limite} dias, "
                        f"a calibrar. O cronograma pedagógico não está em dado nenhum: isto compara repasse com "
                        f"empenho, não com o calendário da alfabetização.")
                if valor < 0:
                    status, nota = "inconclusivo", nota + " Defasagem negativa: empenho anterior ao primeiro repasse do ano (provável saldo do exercício anterior)."
        linhas.append(_linha(ctx, a, "defasagem_repasse_empenho", cod_ibge=cod, ano=ano, valor=valor,
                             status=status, nota=nota, fonte=f"{FONTE_CGU}; {FONTE_EMPENHOS}",
                             q=emp["q"].iloc[0] if not emp.empty and "q" in emp else None))
    return linhas


def a4_3(ctx: Contexto, a: Achado) -> list[dict[str, Any]]:
    """Elemento de despesa atípico dentro da fonte — indício, sempre para revisão humana."""
    fe = ctx.tabela("cnca_execucao_fonte_elemento", obrigatoria=False)
    linhas = []
    for cod, ano in _por_municipio_ano(ctx):
        d = fe[(fe["cod_ibge"] == cod) & (fe["ano"] == ano) & fe["fonte"].isin(["551", "569"])] \
            if not fe.empty else pd.DataFrame()
        if d.empty:
            valor, status = None, "sem_dado_publico"
            nota = "Sem empenho nas fontes 551 ou 569 neste exercício."
        else:
            atipicos = d[d["atipico"]] if "atipico" in d.columns else d.iloc[0:0]
            valor = _num(atipicos["empenhada"].sum()) if not atipicos.empty else 0.0
            if not atipicos.empty:
                quais = ", ".join(sorted({f"{r.elemento} ({r.DescricaoElemento})" for r in atipicos.itertuples()}))
                status = "indicio_risco"
                nota = (f"Empenho em elemento atípico para um programa de alfabetização: {quais}. "
                        f"ATÍPICO NÃO É IRREGULAR — o empenho do TCE-ES não tem histórico nem número de "
                        f"contrato, então só o documento no município decide. Linha para revisão humana.")
            else:
                status = "sem_indicio"
                nota = "Nenhum empenho em elemento atípico nas fontes 551/569 neste exercício."
        linhas.append(_linha(ctx, a, "empenho_elemento_atipico", cod_ibge=cod, ano=ano, valor=valor,
                             status=status, nota=nota, fonte=FONTE_EMPENHOS,
                             q=d["q"].iloc[0] if not d.empty and "q" in d else None))
    return linhas


def _mediana_concentracao(mensal: pd.DataFrame, base_min: float) -> dict[int, float]:
    """Mediana da concentração nov+dez de cada exercício, entre os municípios com base.

    É contra ela que A4.4 compara, e não contra um número fixo: a mediana do Estado vai
    de 13,3% (2023) a 24,4% (2021), e um limiar fixo de 25% marcaria 34 municípios em
    2021 contra 2 em 2023 — diferença que é do ano, não da gestão.
    """
    if mensal.empty:
        return {}
    total = mensal.groupby(["cod_ibge", "ano"])["empenhada"].sum().rename("total")
    fim = (mensal[mensal["mes"].isin([11, 12])].groupby(["cod_ibge", "ano"])["empenhada"]
           .sum().rename("fim"))
    d = pd.concat([total, fim], axis=1).reset_index()
    d["fim"] = d["fim"].fillna(0.0)
    d = d[d["total"].abs() >= base_min]
    if d.empty:
        return {}
    d["pct"] = d["fim"] / d["total"] * 100
    return {int(ano): float(v) for ano, v in d.groupby("ano")["pct"].median().items()}


def a4_4(ctx: Contexto, a: Achado) -> list[dict[str, Any]]:
    """Concentração da execução em nov+dez na subfunção 361 — o único indicador direto da Q4."""
    m = ctx.tabela("cnca_execucao_mensal", obrigatoria=False)
    if not m.empty:
        m = m[m["subfuncao"].astype(str) == mod_execucao.SUBFUNCAO_FUNDAMENTAL]
    margem = ctx.param("concentracao_acima_da_mediana_pp")
    piso = ctx.param("concentracao_piso_pct")
    base_min = ctx.param("concentracao_minimo_base")
    medianas = _mediana_concentracao(m, base_min)
    linhas = []
    for cod, ano in _por_municipio_ano(ctx):
        d = m[(m["cod_ibge"] == cod) & (m["ano"] == ano)] if not m.empty else m
        total = _num(d["empenhada"].sum()) if not d.empty else None
        fim = _num(d[d["mes"].isin([11, 12])]["empenhada"].sum()) if not d.empty else None
        pct = _pct(fim, total)
        if pct is None:
            status = "sem_dado_publico"
            nota = "Sem empenho na subfunção 361 neste exercício."
        elif total is not None and abs(total) < base_min:
            status = "inconclusivo"
            nota = (f"Base anual de R$ {total:,.0f} abaixo do mínimo de R$ {base_min:,.0f} para classificar: "
                    f"o percentual fica instável demais.")
        elif pct < 0:
            status = "inconclusivo"
            nota = (f"Percentual negativo ({pct:.1f}%): as anulações de empenho em nov+dez superaram os "
                    f"empenhos do período. Isso NÃO é boa execução — é um padrão a examinar por si.")
        else:
            mediana = medianas.get(ano)
            limite = None if mediana is None else max(mediana + margem, piso)
            if limite is None:
                status = "inconclusivo"
                nota = "Sem municípios suficientes no exercício para estabelecer a mediana de comparação."
            elif pct > limite:
                status = "indicio_risco"
                nota = (f"{pct:.1f}% do empenho anual da subfunção 361 feito em nov+dez, contra a mediana de "
                        f"{mediana:.1f}% do próprio exercício — {pct - mediana:.1f} p.p. acima dela, e acima do "
                        f"piso de {piso:.0f}%. A comparação é com o ano, não com um limiar fixo: a mediana do "
                        f"Estado vai de 13,3% (2023) a 24,4% (2021). Mede o ensino fundamental inteiro, não o CNCA.")
            else:
                status = "sem_indicio"
                nota = (f"{pct:.1f}% do empenho anual da subfunção 361 em nov+dez, contra a mediana de "
                        f"{mediana:.1f}% do exercício. Mede o ensino fundamental inteiro, não o CNCA.")
        linhas.append(_linha(ctx, a, "concentracao_nov_dez_361", cod_ibge=cod, ano=ano, valor=pct,
                             status=status, nota=nota, fonte=FONTE_EMPENHOS,
                             q=d["q"].iloc[0] if not d.empty and "q" in d else None))
        linhas.append(_linha(ctx, a, "perfil_mensal_361", cod_ibge=cod, ano=ano, valor=total,
                             status=status, nota=("Total empenhado no ano na subfunção 361; o perfil mês a mês "
                                                  "está em cnca_execucao_mensal.csv."),
                             fonte=FONTE_EMPENHOS, q=d["q"].iloc[0] if not d.empty and "q" in d else None))
    return linhas


def indisponivel(ctx: Contexto, a: Achado) -> list[dict[str, Any]]:
    """Achado que o dado público não alcança: uma linha por município, dizendo por quê.

    Isto não é preenchimento: `sem_dado_publico` é a RESPOSTA, e ela precisa estar
    na tabela para o painel de cobertura ser honesto.
    """
    nota = (a.ressalvas[0] if a.ressalvas else "Sem fonte pública que responda.")
    if a.caminho_alternativo:
        nota += f" Caminho: {a.caminho_alternativo}"
    linhas = []
    for cod in sorted(ctx.municipios):
        if a.indicadores:
            for ind in a.indicadores:
                linhas.append(_linha(ctx, a, ind.id, cod_ibge=cod, ano=None, valor=None,
                                     status="sem_dado_publico", nota=nota, fonte=ind.fonte or "—"))
        else:
            linhas.append({
                "municipio_ibge": cod, "municipio": ctx.municipios.get(cod, ""), "questao_matriz": a.questao,
                "achado_id": a.id, "pergunta_questionario": ";".join(a.perguntas), "indicador": "",
                "rotulo": a.enunciado, "valor": None, "unidade": "", "ano": None,
                "status": "sem_dado_publico", "tipo_evidencia": a.tipo_evidencia, "confianca": a.confianca,
                "fonte": "—", "endpoint_ou_arquivo": None, "parametros": None, "data_extracao": None,
                "hash_bruto": None, "nota": " ".join(nota.split()), "q": None,
            })
    return linhas


# --------------------------------------------------- Fase 2 (necessidades e resultados)

def a2_1(ctx: Contexto, a: Achado) -> list[dict[str, Any]]:
    """Valor de referência do Cantinho da Leitura — estimativa de UMA das ações do CNCA."""
    censo = ctx.tabela("cnca_censo_municipio", obrigatoria=False)
    linhas = []
    for cod, ano in _por_municipio_ano(ctx):
        d = _busca(censo, cod_ibge=cod, ano=ano)
        valor = _num(d["valor_referencia_cantinho"].iloc[0]) if not d.empty else None
        salas = _num(d["salas_anos_iniciais"].iloc[0]) if not d.empty else None
        if valor is None:
            status, nota = "sem_dado_publico", "Sem retrato do Censo para este município-ano."
        else:
            status = "inconclusivo"
            nota = (f"{salas:.0f} salas de aula utilizadas em escolas municipais com anos iniciais × "
                    f"R$ {mod_censo.VALOR_CANTINHO_POR_SALA:,.2f} (Resolução CD/FNDE 22/2023). "
                    f"É ESTIMATIVA de ordem de grandeza de UMA ação do CNCA — não é a necessidade "
                    f"total do município, e não diz se o município a conhece.")
        linhas.append(_linha(ctx, a, "valor_referencia_cantinho", cod_ibge=cod, ano=ano, valor=valor,
                             status=status, nota=nota, fonte=f"{FONTE_CENSO}; Resolução CD/FNDE 22/2023",
                             q=d["q"].iloc[0] if not d.empty and "q" in d else None))
    return linhas


def a2_2(ctx: Contexto, a: Achado) -> list[dict[str, Any]]:
    """O que a rede tem: turmas e matrículas de 1º-2º ano, e espaço de leitura."""
    censo = ctx.tabela("cnca_censo_municipio", obrigatoria=False)
    especificacao = {
        "turmas_1_2_ano": ("turmas_1_2_ano", "turmas", mod_censo.PRIMEIRO_ANO["turmas"]),
        "matriculas_1_2_ano": ("mat_1_2_ano", "matrículas", mod_censo.PRIMEIRO_ANO["matriculas"]),
        "escolas_com_sala_leitura": ("pct_escolas_com_leitura", "espaço de leitura", 2021),
    }
    linhas = []
    for cod, ano in _por_municipio_ano(ctx):
        d = _busca(censo, cod_ibge=cod, ano=ano)
        for ind, (coluna, rotulo, primeiro) in especificacao.items():
            valor = _num(d[coluna].iloc[0]) if not d.empty and coluna in d.columns else None
            if ano < primeiro:
                status = "sem_dado_publico"
                nota = (f"O Censo só desdobra {rotulo} de 1º e 2º ano a partir de {primeiro}. "
                        f"Em {ano} o indicador NÃO EXISTE — não é zero.")
                valor = None
            elif valor is None:
                status, nota = "sem_dado_publico", "Sem retrato do Censo para este município-ano."
            else:
                status = "inconclusivo"
                nota = ("O Censo mede o que a rede TEM, não o que o município SABE sobre ela. "
                        "Entra como contraste com a resposta ao questionário, não classifica o achado.")
            linhas.append(_linha(ctx, a, ind, cod_ibge=cod, ano=ano, valor=valor, status=status,
                                 nota=nota, fonte=FONTE_CENSO,
                                 q=d["q"].iloc[0] if not d.empty and "q" in d else None))
    return linhas


def _edicao_mais_recente(ica: pd.DataFrame, cod_ibge: int, ano: int) -> pd.DataFrame:
    """A linha do ICA daquele município-ano na edição mais nova que o publicou.

    Tolera a tabela ausente ou sem as colunas: uma fonte que não veio não derruba o
    resto da evidência, e o indicador sai como "sem dado público".
    """
    if ica.empty or not {"cod_ibge", "ano", "edicao", "taxa"} <= set(ica.columns):
        return pd.DataFrame()
    d = ica[(ica["cod_ibge"] == cod_ibge) & (ica["ano"] == ano) & ica["taxa"].notna()]
    return d.sort_values("edicao").tail(1) if not d.empty else d


def a5_4(ctx: Contexto, a: Achado) -> list[dict[str, Any]]:
    """Recurso do CNCA por aluno de 1º-2º ano × ICA — correlação descritiva, sem causa."""
    censo = ctx.tabela("cnca_censo_municipio", obrigatoria=False)
    cnca = ctx.tabela("cnca_municipio", obrigatoria=False)
    ica = ctx.tabela("ica_municipios", obrigatoria=False)
    queda_min = ctx.param("ica_queda_pp")
    linhas = []
    for cod, ano in _por_municipio_ano(ctx):
        c = _busca(censo, cod_ibge=cod, ano=ano)
        p = _busca(cnca, cod_ibge=cod, ano=ano)
        alunos = _num(c["mat_1_2_ano"].iloc[0]) if not c.empty else None
        recebido = _num(p["pdde_cnca"].sum()) if not p.empty else None
        por_aluno = (None if (alunos is None or recebido is None or alunos < 1)
                     else round(recebido / alunos, 2))
        if por_aluno is None:
            nota = ("Falta uma das pontas: matrícula de 1º-2º ano só existe no Censo a partir de 2023, "
                    "e o PDDE-CNCA só aparece onde houve pagamento na CGU no exercício.")
            status = "sem_dado_publico"
        else:
            status = "inconclusivo"
            nota = (f"R$ {por_aluno:,.2f} de PDDE-CNCA por aluno de 1º e 2º ano. LEITURA CAUSAL É "
                    f"PROIBIDA: o CNCA é fração pequena do gasto por aluno, e o MEC não publica os "
                    f"pesos dos critérios de repasse.")
        linhas.append(_linha(ctx, a, "recurso_por_aluno_alfabetizacao", cod_ibge=cod, ano=ano,
                             valor=por_aluno, status=status, nota=nota,
                             fonte=f"{FONTE_CGU}; {FONTE_CENSO}",
                             q=p["q"].iloc[0] if not p.empty and "q" in p else None))

        # ICA: a taxa da edição mais recente que tem valor para este ano de referência.
        # Uma edição nova republica os anos anteriores com a régua dela; fica a última.
        i = _edicao_mais_recente(ica, cod, ano)
        taxa = _num(i["taxa"].iloc[0]) if not i.empty else None
        if taxa is None:
            status_ica, nota_ica = "sem_dado_publico", "Sem ICA publicado para este município-ano."
        else:
            anterior = _edicao_mais_recente(ica, cod, ano - 1)
            v_ant = _num(anterior["taxa"].iloc[0]) if not anterior.empty else None
            variacao = None if v_ant is None else round(taxa - v_ant, 2)
            caiu = variacao is not None and variacao < -queda_min
            subiu_recurso = por_aluno is not None and por_aluno > 0
            status_ica = "inconclusivo"
            nota_ica = (f"ICA de {taxa:.0f}%"
                        + (f", variação de {variacao:+.0f} p.p. sobre o ano anterior" if variacao is not None else "")
                        + ". Comparação do município com ele mesmo, nunca entre estados: cada edição tem sua régua."
                        + (" Queda no ICA com recurso do CNCA identificado no exercício: prioridade de exame, "
                           "não achado." if caiu and subiu_recurso else ""))
        linhas.append(_linha(ctx, a, "ica_e_variacao", cod_ibge=cod, ano=ano, valor=taxa,
                             status=status_ica, nota=nota_ica, fonte="INEP — Avaliação da Alfabetização (ICA)",
                             q=i["q"].iloc[0] if not i.empty and "q" in i else None))
    return linhas


def a6_1(ctx: Contexto, a: Achado) -> list[dict[str, Any]]:
    """Recurso próprio na subfunção 361 e transferências do FNDE recebidas."""
    fontes = ctx.tabela("cnca_execucao_fontes", obrigatoria=False)
    rep = ctx.tabela("repasses_fnde", obrigatoria=False)
    proprias = set(mod_execucao.FONTES_PROPRIAS)
    linhas = []
    for cod, ano in _por_municipio_ano(ctx):
        f = fontes[(fontes["cod_ibge"] == cod) & (fontes["ano"] == ano)] if not fontes.empty else pd.DataFrame()
        total = _num(f["empenhada"].sum()) if not f.empty else None
        proprio = _num(f[f["fonte"].isin(proprias)]["empenhada"].sum()) if not f.empty else None
        pct = _pct(proprio, total)
        if pct is None:
            status, nota = "sem_dado_publico", "Sem empenho na função 12 neste exercício."
        else:
            status = "inconclusivo"
            codigos = "111/112/113 (codificação local do ES)" if ano < 2023 else "500 (impostos/MDE) e 540 (FUNDEB)"
            nota = (f"{pct:.1f}% do empenho da função 12 vem de fonte própria — fontes {codigos}. "
                    f"Quase toda a despesa da educação municipal é custeada por elas: o indicador NÃO "
                    f"distingue complementação ao CNCA de manutenção ordinária da rede.")
        linhas.append(_linha(ctx, a, "recurso_proprio_subfuncao_361", cod_ibge=cod, ano=ano, valor=pct,
                             status=status, nota=nota, fonte=FONTE_EMPENHOS,
                             q=f["q"].iloc[0] if not f.empty and "q" in f else None))

        r = rep[(rep["cod_ibge"] == cod) & (rep["ano"] == ano)] if not rep.empty else pd.DataFrame()
        valor = _num(r["valor"].sum()) if not r.empty else None
        linhas.append(_linha(
            ctx, a, "transferencias_fnde_recebidas", cod_ibge=cod, ano=ano, valor=valor,
            status="sem_dado_publico" if valor is None else "inconclusivo",
            nota=("Tudo o que o FNDE pagou ao município e às suas escolas no exercício, por ação. "
                  "Inclui salário-educação, PNAE, PNATE e PDDE — não é recurso do CNCA."),
            fonte=FONTE_CGU, q=r["q"].iloc[0] if not r.empty and "q" in r else None))
    return linhas


# ------------------------------------------------- Fase 3 (documental)

def documental(ctx: Contexto, a: Achado) -> list[dict[str, Any]]:
    """Achado que só existe em ato publicado, buscado no diário oficial.

    A regra central desta função é o que ela NÃO faz: nenhum município recebe
    `sem_indicio` por ter aparecido numa busca textual, e nenhum recebe
    `indicio_risco` por não ter aparecido. Busca em diário é TRIAGEM — o resultado
    é uma lista de edições para alguém ler, e a leitura é que decide.

    Fora dos 3 municípios que o Querido Diário cobre, o status é `sem_dado_publico`
    com o caminho alternativo na nota: é a resposta honesta para 96% do universo.
    """
    from .diarios import TERMOS_QD

    cobertura = ctx.tabela("cnca_diarios_cobertura", obrigatoria=False)
    ocorr = ctx.tabela("cnca_diarios_ocorrencias", obrigatoria=False)
    coberto = set(cobertura[cobertura["situacao"] == "coletado"]["cod_ibge"].astype(int)) \
        if not cobertura.empty else set()
    # "Não medido" é diferente de "não coberto": o primeiro é a API que não respondeu na
    # coleta, o segundo é o município que o projeto não indexa. Confundir os dois faria o
    # painel afirmar sobre o município uma coisa que se sabe sobre o serviço.
    nao_medido = set(cobertura[cobertura["situacao"] == "não medido"]["cod_ibge"].astype(int)) \
        if not cobertura.empty else set()
    # Achado sem termo de busca não foi procurado: dizer "nada encontrado" para ele seria
    # relatar o resultado de uma busca que nunca houve. É o caso de A1.2, que depende de
    # LER o ato que A1.1 localiza — busca textual não responde se o ato define atribuições.
    tem_busca = a.id in TERMOS_QD
    linhas = []
    for ind in a.indicadores:
        for cod in sorted(ctx.municipios):
            o = ocorr[(ocorr["cod_ibge"] == cod) & (ocorr["achado_id"] == a.id)] \
                if not ocorr.empty else pd.DataFrame()
            if not tem_busca:
                valor, status = None, "sem_dado_publico"
                nota = ("Não há busca textual que responda a este achado: ele exige LER o ato que "
                        + (a.caminho_alternativo or "a busca documental localiza") + ".")
            elif cod in nao_medido:
                valor, status = None, "sem_dado_publico"
                nota = ("A cobertura de diário deste município não foi medida: a API do Querido Diário "
                        "não respondeu na última coleta. Não se sabe se ele tem diário indexado — e "
                        "não se afirma que não tem. A busca manual no DOM-ES/AMUNES está na lista "
                        "(cnca_diarios_buscas_manuais.csv), com o termo, o período e o que registrar.")
            elif cod not in coberto:
                valor, status = None, "sem_dado_publico"
                nota = ("Município fora da cobertura do Querido Diário — dos 78 do ES, 3 têm diário "
                        "coletado. A busca no DOM-ES/AMUNES está na lista de buscas manuais "
                        "(cnca_diarios_buscas_manuais.csv), com o termo, o período e o que registrar.")
            elif o.empty:
                valor, status = 0, "sem_dado_publico"
                nota = ("Busca feita no diário deste município e nenhuma edição casou com os termos. "
                        "AUSÊNCIA DE RESULTADO NÃO É AUSÊNCIA DE ATO: o ato pode estar em portaria "
                        "interna não publicada, ou nomear a pessoa sem citar o programa.")
            else:
                valor, status = int(len(o)), "inconclusivo"
                nota = (f"{len(o)} edições casaram com os termos da busca, entre "
                        f"{o['data'].min()} e {o['data'].max()}. É TRIAGEM para leitura humana, não "
                        f"contagem de atos: os termos são amplos de propósito e trazem muito ruído. "
                        f"As edições estão em cnca_diarios_ocorrencias.csv, com excerto e link.")
            linhas.append(_linha(ctx, a, ind.id, cod_ibge=cod, ano=None, valor=valor, status=status,
                                 nota=nota, fonte="Diário Oficial (Querido Diário; DOM-ES/AMUNES)",
                                 q=o["q"].iloc[0] if not o.empty and "q" in o else None))
    return linhas


#: Achado → função que o calcula. O que não estiver aqui e não for `indisponivel`
#: fica pendente da fase correspondente, e aparece assim no painel de cobertura.
CALCULOS: dict[str, Callable[[Contexto, Achado], list[dict[str, Any]]]] = {
    "A3.1": a3_1, "A4.1": a4_1, "A4.2": a4_2, "A4.3": a4_3, "A4.4": a4_4,
    "A2.1": a2_1, "A2.2": a2_2, "A5.4": a5_4, "A6.1": a6_1,
    "A1.1": documental, "A1.2": documental, "A1.4": documental,
    "A1.7": documental, "A2.3": documental, "A5.3": documental,
}


# ------------------------------------------------ indicadores de pergunta

def indices_execucao(ctx: Contexto) -> pd.DataFrame:
    """Os quatro índices que P24 lista, por município × ano × fonte (e no total da função 12)."""
    dot = ctx.tabela("cnca_execucao_dotacao_fonte", obrigatoria=False)
    if dot.empty:
        return pd.DataFrame()
    total = dot.groupby(["cod_ibge", "ano"], as_index=False)[
        ["previsao_inicial", "previsao_atualizada", "empenhada", "liquidada", "paga"]].sum()
    total["fonte"] = "(todas — função 12)"
    d = pd.concat([dot.assign(fonte=dot["fonte"].astype(str)), total], ignore_index=True)
    d["indice_execucao_orcamentaria"] = d.apply(lambda r: _pct(r["empenhada"], r["previsao_atualizada"]), axis=1)
    d["indice_execucao_financeira"] = d.apply(lambda r: _pct(r["paga"], r["previsao_atualizada"]), axis=1)
    d["indice_liquidacao"] = d.apply(lambda r: _pct(r["liquidada"], r["empenhada"]), axis=1)
    d["indice_pagamento"] = d.apply(lambda r: _pct(r["paga"], r["liquidada"]), axis=1)
    d["municipio"] = d["cod_ibge"].map(ctx.municipios)
    return d


def restos_a_pagar(ctx: Contexto) -> pd.DataFrame:
    """Restos a pagar processados por fonte (P25, P26), com idade e teste de relevância.

    A idade NÃO sai de ``RPPTransferido``: essa coluna existe no dicionário do
    TCE-ES e vem **sempre vazia** nos arquivos dos municípios do ES (medido em
    2021-2025). Usá-la faria "nenhum município tem RP antigo" aparecer como
    achado, quando é ausência de dado. A idade sai do ``AnoEmpenho``: um empenho
    de ano anterior que ainda se move no exercício é, por construção, resto a
    pagar — e a diferença entre os dois anos é a idade dele.
    """
    f = ctx.tabela("cnca_execucao_fontes", obrigatoria=False)
    if f.empty:
        return pd.DataFrame()
    d = f.copy()
    d["rpp_inscrito_exercicio"] = d["rpp_inscrito"]
    d["rpp_pct_empenhado"] = d.apply(lambda r: _pct(r["rpp_inscrito"], r["empenhada"]), axis=1)
    d["rpp_relevante"] = d["rpp_pct_empenhado"].fillna(0) > ctx.param("rp_relevante_pct")

    idade = ctx.tabela("cnca_execucao_rp_idade", obrigatoria=False)
    minimo = ctx.param("rp_processados_idade_anos")
    if idade.empty:
        d["rp_idade_maxima"] = pd.NA
        d["rpp_movimentado_antigo"] = pd.NA
        d["rpp_prolongado"] = pd.NA      # não é False: é "não medido"
    else:
        # Pagar ou cancelar, neste exercício, resto a pagar PROCESSADO de um empenho
        # de dois ou mais anos atrás é exatamente o que P25 chama de "período
        # prolongado" — e é medível, ao contrário do estoque, que a fonte não publica.
        antigos = idade[(idade["idade_anos"] >= minimo)
                        & (idade["rp_processado_movimentado"].abs() > 0.005)]
        resumo = antigos.groupby(["cod_ibge", "ano", "fonte"], as_index=False).agg(
            rp_idade_maxima=("idade_anos", "max"),
            rpp_movimentado_antigo=("rp_processado_movimentado", "sum"))
        d = d.merge(resumo, on=["cod_ibge", "ano", "fonte"], how="left")
        d["rpp_prolongado"] = d["rp_idade_maxima"].notna()
    d["municipio"] = d["cod_ibge"].map(ctx.municipios)
    return d


def cobertura_pdde(ctx: Contexto) -> pd.DataFrame:
    """P21: escolas da rede municipal beneficiadas com PDDE do plano orçamentário do CNCA.

    O denominador é o CADASTRO de escolas municipais em atividade, não uma série
    anual: `escolas.csv` traz uma linha por escola, com `ano_censo` sendo o último
    exercício em que ela apareceu no Censo. Tomá-lo como série daria denominador
    zero em 2021-2024 e uma cobertura absurda. O mesmo denominador vale para todos
    os exercícios, e a coluna `denominador` diz isso na cara.
    """
    pdde = ctx.tabela("pdde_por_escola", obrigatoria=False)
    escolas = ctx.tabela("escolas", obrigatoria=False)
    if pdde.empty or escolas.empty:
        return pd.DataFrame()
    cnca = pdde[(pdde["po"].astype(str).str.zfill(4) == "000C") & pdde["cod_ibge"].notna()]
    benef = cnca.groupby(["cod_ibge", "ano"], as_index=False).agg(
        escolas_com_pdde_cnca=("cnpj_uex", "nunique"), valor=("valor", "sum"), q=("q", "first"))
    benef["cod_ibge"] = benef["cod_ibge"].astype(int)
    ativas = escolas[(escolas["rede"] == "municipal")
                     & escolas["em_atividade"].astype(str).str.lower().eq("true")]
    rede = ativas.groupby("cod_ibge", as_index=False).agg(escolas_rede=("co_entidade", "nunique"))
    censo = int(ativas["ano_censo"].max()) if not ativas.empty else None

    grade = pd.MultiIndex.from_product([sorted(ctx.municipios), ctx.anos],
                                       names=["cod_ibge", "ano"]).to_frame(index=False)
    d = grade.merge(benef, on=["cod_ibge", "ano"], how="left").merge(rede, on="cod_ibge", how="left")
    d["escolas_com_pdde_cnca"] = d["escolas_com_pdde_cnca"].fillna(0).astype(int)
    d["cobertura_pct"] = d.apply(lambda r: _pct(r["escolas_com_pdde_cnca"], r["escolas_rede"]), axis=1)
    d["denominador"] = f"escolas municipais em atividade no cadastro do Censo ({censo})"
    d["municipio"] = d["cod_ibge"].map(ctx.municipios)
    return d.sort_values(["cod_ibge", "ano"]).reset_index(drop=True)


# ------------------------------------------------------------- montagem

def montar(ctx: Contexto) -> pd.DataFrame:
    """A tabela longa de evidências, no formato da seção 5 do prompt."""
    linhas: list[dict[str, Any]] = []
    for a in ctx.matriz.achados:
        if a.id in CALCULOS:
            linhas += CALCULOS[a.id](ctx, a)
        elif a.tipo_evidencia == "indisponivel":
            linhas += indisponivel(ctx, a)
        # Achados das fases 2 e 3 ainda não entram: aparecem como pendência na cobertura.
    d = pd.DataFrame(linhas)
    if d.empty:
        return pd.DataFrame(columns=COLUNAS)
    d = d.reindex(columns=COLUNAS)
    # `ano` é vazio nos achados que não têm exercício (os documentais e os indisponíveis).
    # Inteiro anulável, para o CSV não gravar "2021.0" — ano com casa decimal num papel
    # de trabalho é o tipo de detalhe que faz o leitor duvidar do resto.
    d["ano"] = d["ano"].astype("Int64")
    d["pergunta_questionario"] = d["pergunta_questionario"].fillna("")
    return d.sort_values(["achado_id", "municipio_ibge", "ano", "indicador"],
                         na_position="last").reset_index(drop=True)


def cobertura(ctx: Contexto, evidencias: pd.DataFrame) -> pd.DataFrame:
    """Quanto da matriz o dado público alcança — a base da visão 5 do painel."""
    calculados = set(evidencias["achado_id"]) if not evidencias.empty else set()
    linhas = []
    for a in ctx.matriz.achados:
        if a.id in CALCULOS:
            situacao = "calculado"
        elif a.tipo_evidencia == "indisponivel":
            situacao = "sem dado público (resposta final)"
        else:
            situacao = f"pendente da fase {a.fase}"
        sub = evidencias[evidencias["achado_id"] == a.id] if a.id in calculados else pd.DataFrame()
        contagem = sub["status"].value_counts().to_dict() if not sub.empty else {}
        linhas.append({
            "questao_matriz": a.questao, "achado_id": a.id, "enunciado": a.enunciado,
            "fase": a.fase, "tipo_evidencia": a.tipo_evidencia, "confianca": a.confianca,
            "situacao": situacao, "constatacao": a.constatacao or "", "perguntas": ";".join(a.perguntas),
            "indicadores": ";".join(i.id for i in a.indicadores),
            **{f"n_{s}": contagem.get(s, 0) for s in mod_matriz.STATUS},
            "ressalvas": " | ".join(a.ressalvas),
            "caminho_alternativo": a.caminho_alternativo or "",
        })
    return pd.DataFrame(linhas)


def constatacoes(ctx: Contexto) -> pd.DataFrame:
    """As afirmações que valem para o universo — uma linha cada, não 78.

    Uma constatação sai do mapa de calor e vai para o texto do relatório: ela é sobre
    a classificação orçamentária, ou sobre o que a fonte publica, e não sobre a gestão
    de um município em particular.
    """
    return pd.DataFrame([{
        "constatacao_id": c.id, "questao_matriz": c.questao, "achados": ";".join(c.achados),
        "enunciado": c.enunciado, "medida": c.medida, "fonte": c.fonte,
        "abrangencia": c.abrangencia, "consequencia": c.consequencia,
    } for c in ctx.matriz.constatacoes])


def cobertura_perguntas(ctx: Contexto) -> pd.DataFrame:
    """Uma linha por pergunta do questionário: o que o dado responde e o que não responde."""
    return pd.DataFrame([{
        "pergunta": p.id, "bloco": p.bloco, "enunciado": p.enunciado, "tipo": p.tipo,
        "evidencia": p.evidencia, "achados": ";".join(p.achados), "responde_com": p.responde_com,
        "dados_pessoais": p.dados_pessoais, "opcoes": " | ".join(p.opcoes),
    } for p in ctx.matriz.perguntas])


#: Onde os módulos desta matriz gravam as consultas que fizeram. O pipeline geral já
#: grava as suas em `consultas.csv`; as daqui (Censo no recorte da alfabetização, e o
#: primeiro repasse do FNDE) não estão lá, e sem elas a proveniência da linha viria vazia.
ARQUIVO_CONSULTAS = PROCESSADO / "cnca_consultas.csv"


def gravar_consultas(consultas: Iterable[Any]) -> None:
    """Acrescenta consultas ao arquivo da matriz, sem repetir id."""
    novas = pd.DataFrame([{"id": c.id, "fonte": c.fonte, "recurso": c.recurso, "descricao": c.descricao,
                           "url": c.url, "obtido_em": c.obtido_em, "arquivo": c.arquivo,
                           "sha256": c.sha256} for c in consultas])
    if novas.empty:
        return
    if ARQUIVO_CONSULTAS.exists():
        novas = pd.concat([pd.read_csv(ARQUIVO_CONSULTAS, dtype=str), novas], ignore_index=True)
    ARQUIVO_CONSULTAS.parent.mkdir(parents=True, exist_ok=True)
    novas.drop_duplicates("id", keep="last").to_csv(ARQUIVO_CONSULTAS, index=False, encoding="utf-8")


def _consultas() -> pd.DataFrame:
    """As consultas do pipeline geral e as desta matriz, num índice só."""
    partes = [pd.read_csv(p, dtype=str) for p in (PROCESSADO / "consultas.csv", ARQUIVO_CONSULTAS)
              if p.exists()]
    if not partes:
        return pd.DataFrame()
    return pd.concat(partes, ignore_index=True).drop_duplicates("id", keep="last")


#: Colunas que SÃO texto mesmo parecendo número. Sem isto, `read_csv` lê a fonte
#: "569" como inteiro e todo filtro por código de fonte devolve vazio — em
#: silêncio, o que faria o painel exibir "sem dado" onde há dado.
COLUNAS_TEXTO = {"fonte": str, "complemento": str, "elemento": str, "subfuncao": str,
                 "po": str, "CodigoAcao": str}


def _carregar_tabelas(nomes: Iterable[str]) -> dict[str, pd.DataFrame]:
    saida = {}
    for nome in nomes:
        caminho = PROCESSADO / f"{nome}.csv"
        if not caminho.exists():
            log.warning("tabela ausente: %s", caminho.name)
            continue
        cabecalho = pd.read_csv(caminho, nrows=0).columns
        dtype = {c: t for c, t in COLUNAS_TEXTO.items() if c in cabecalho}
        saida[nome] = pd.read_csv(caminho, dtype=dtype)
    return saida


TABELAS = ("cnca_execucao_mensal", "cnca_execucao_fontes", "cnca_execucao_fonte_elemento",
           "cnca_execucao_primeiro_empenho", "cnca_execucao_acoes_nomeadas", "cnca_execucao_complemento",
           "cnca_execucao_rp_idade", "cnca_execucao_dotacao_fonte", "cnca_execucao_dotacao_nomeada",
           "cnca_repasse_primeiro_mes", "cnca_municipio", "pdde_por_escola", "escolas",
           "cnca_censo_municipio", "cnca_censo_escolas", "ica_municipios", "repasses_fnde",
           "cnca_diarios_cobertura", "cnca_diarios_ocorrencias", "cnca_diarios_buscas_manuais",
           "cnca_contratos_formacao", "cnca_contratos_municipio", "cnca_estado_municipio")


def contexto(anos: Iterable[int]) -> Contexto:
    """O contexto padrão: a matriz, os CSVs já gravados e o índice de consultas."""
    return Contexto(matriz=mod_matriz.carregar(), tabelas=_carregar_tabelas(TABELAS),
                    municipios=mod_execucao.nomes_municipios(), anos=tuple(sorted(anos)),
                    consultas=_consultas())


def executar(anos: Iterable[int], ctx: Contexto | None = None) -> dict[str, pd.DataFrame]:
    """Monta tudo a partir dos CSVs já gravados (sem rede)."""
    ctx = ctx or contexto(anos)
    ev = montar(ctx)
    return {
        "evidencias_cnca": ev,
        "constatacoes": constatacoes(ctx),
        "cobertura_achados": cobertura(ctx, ev),
        "cobertura_perguntas": cobertura_perguntas(ctx),
        "indices_execucao": indices_execucao(ctx),
        "restos_a_pagar": restos_a_pagar(ctx),
        "cobertura_pdde": cobertura_pdde(ctx),
        # Tabelas de pergunta: não classificam achado, respondem P18 e P47/P48 diretamente.
        "repasses_estaduais": ctx.tabela("cnca_estado_municipio", obrigatoria=False),
        "contratos_formacao": ctx.tabela("cnca_contratos_formacao", obrigatoria=False),
        "buscas_manuais_diarios": ctx.tabela("cnca_diarios_buscas_manuais", obrigatoria=False),
    }


#: Esquema do dataset do painel do CNCA. Sobe quando a forma muda, e o template recusa
#: um dataset de esquema diferente — é o que impede painel novo lendo dado velho.
SCHEMA_PAINEL = 1


def _linhas(df: pd.DataFrame, colunas: Iterable[str]) -> list[dict[str, Any]]:
    """DataFrame → lista de dicionários, só com as colunas pedidas e com NaN virando None.

    `NaN` não é JSON válido: o `build_dashboard` monta com `allow_nan=False` e falharia —
    o que é melhor que embutir `NaN` e o navegador engasgar em silêncio. `astype(object)`
    antes do `where` é o que preserva o inteiro como inteiro em vez de promovê-lo a float.
    """
    if df.empty:
        return []
    d = df.reindex(columns=[c for c in colunas if c in df.columns]).astype(object)
    return d.where(pd.notna(d), None).to_dict("records")


def dataset_painel(ctx: Contexto, saidas: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """O que o painel do CNCA embute: a matriz inteira e as evidências, sem redundância.

    Rótulo, tipo de evidência, confiança e ressalva de cada achado vêm da matriz e não
    se repetem linha a linha; a evidência guarda só o que varia por município.
    """
    m = ctx.matriz
    return {
        "meta": {
            "esquema": SCHEMA_PAINEL,
            "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fiscalizacao": m.fiscalizacao,
            "anos": list(ctx.anos),
            "parametros": {k: v for k, v in m.parametros.items()},
            "limitacoes": m.limitacoes,
            "status": mod_matriz.ROTULO_STATUS,
            "tipos_evidencia": mod_matriz.ROTULO_TIPO,
        },
        "questoes": [{"id": q.id, "enunciado": q.enunciado, "nota": q.nota,
                      "achados": [{
                          "id": a.id, "enunciado": a.enunciado, "fase": a.fase,
                          "tipo_evidencia": a.tipo_evidencia, "confianca": a.confianca,
                          "perguntas": list(a.perguntas), "constatacao": a.constatacao,
                          "regra": a.regra, "ressalvas": list(a.ressalvas),
                          "caminho_alternativo": a.caminho_alternativo,
                          "indicadores": [{"id": i.id, "rotulo": i.rotulo, "unidade": i.unidade,
                                           "formula": i.formula, "fonte": i.fonte, "nivel": i.nivel}
                                          for i in a.indicadores],
                      } for a in q.achados]} for q in m.questoes],
        "perguntas": [{"id": p.id, "bloco": p.bloco, "enunciado": p.enunciado, "tipo": p.tipo,
                       "opcoes": list(p.opcoes), "achados": list(p.achados), "evidencia": p.evidencia,
                       "responde_com": p.responde_com, "dados_pessoais": p.dados_pessoais}
                      for p in m.perguntas],
        "constatacoes": [{"id": c.id, "questao": c.questao, "achados": list(c.achados),
                          "enunciado": c.enunciado, "medida": c.medida, "fonte": c.fonte,
                          "abrangencia": c.abrangencia, "consequencia": c.consequencia}
                         for c in m.constatacoes],
        "municipios": [{"cod_ibge": c, "nome": n} for c, n in sorted(ctx.municipios.items())],
        # As consultas desta matriz vão junto: o dataset geral só conhece as do pipeline
        # geral, e sem estas o "ver fonte" de uma evidência do Censo, do diário ou do
        # SIGEFES abriria vazio. Só entram as que alguma evidência de fato cita.
        "consultas": _linhas(ctx.consultas[ctx.consultas["id"].isin(
            {i for q in saidas["evidencias_cnca"].get("q", pd.Series(dtype=str)).dropna()
             for i in str(q).split(";") if i})] if not ctx.consultas.empty else pd.DataFrame(),
            ["id", "fonte", "recurso", "descricao", "url", "obtido_em", "arquivo", "sha256"]),
        "evidencias": _linhas(saidas["evidencias_cnca"],
                              ["municipio_ibge", "achado_id", "indicador", "ano", "valor",
                               "status", "nota", "q"]),
        "indices": _linhas(saidas["indices_execucao"],
                           ["cod_ibge", "ano", "fonte", "indice_execucao_orcamentaria",
                            "indice_execucao_financeira", "indice_liquidacao", "indice_pagamento",
                            "previsao_atualizada", "empenhada", "liquidada", "paga"]),
        "restos": _linhas(saidas["restos_a_pagar"],
                          ["cod_ibge", "ano", "fonte", "empenhada", "rpp_inscrito",
                           "rpp_pct_empenhado", "rpp_relevante", "rpp_prolongado", "rp_idade_maxima"]),
        "pdde": _linhas(saidas["cobertura_pdde"],
                        ["cod_ibge", "ano", "escolas_com_pdde_cnca", "escolas_rede",
                         "cobertura_pct", "valor", "denominador"]),
        "estado": _linhas(saidas.get("repasses_estaduais", pd.DataFrame()),
                          ["cod_ibge", "ano", "empenhado", "pago", "empenhado_funpaes", "pago_funpaes"]),
        "contratos": _linhas(saidas.get("contratos_formacao", pd.DataFrame()),
                             ["cod_ibge", "ano", "contratacao", "objeto", "categoria_rotulo",
                              "termos", "responde_p47", "sem_efeito", "valor_total", "url_edital"]),
        "buscas_manuais": _linhas(saidas.get("buscas_manuais_diarios", pd.DataFrame()),
                                  ["cod_ibge", "achado_id", "o_que_procurar", "expressao", "onde",
                                   "periodo", "como_registrar"]),
        "cobertura_achados": _linhas(saidas["cobertura_achados"],
                                     ["achado_id", "questao_matriz", "situacao", "fase",
                                      "n_indicio_risco", "n_sem_indicio", "n_inconclusivo",
                                      "n_sem_dado_publico"]),
    }


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Tabela de evidências da matriz do CNCA (usa os CSVs; sem rede).")
    p.add_argument("--anos", default="2021-2025")
    args = p.parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    ini, _, fim = args.anos.partition("-")
    anos = range(int(ini), int(fim or ini) + 1)
    ctx = contexto(anos)
    saidas = executar(anos, ctx)
    PASTA_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    for nome, df in saidas.items():
        df.to_csv(PASTA_EVIDENCIAS / f"{nome}.csv", index=False, encoding="utf-8")
        print(f"{nome}: {len(df):,} linhas")

    # O dataset do painel sai junto: quem roda o ETL não precisa lembrar de um passo a mais.
    painel = dataset_painel(ctx, saidas)
    caminho = PROCESSADO / "dataset_cnca.json"
    caminho.write_text(json.dumps(painel, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
                       encoding="utf-8")
    print(f"dataset_cnca.json: {caminho.stat().st_size / 1024:.0f} KB")
    ev = saidas["evidencias_cnca"]
    if not ev.empty:
        try:
            ev.to_parquet(PASTA_EVIDENCIAS / "evidencias_cnca.parquet", index=False)
        except Exception as e:                      # noqa: BLE001 — parquet é conveniência, CSV é o contrato
            print(f"  (parquet não gravado: {e})", file=sys.stderr)
        print("\nstatus por achado:")
        print(ev.pivot_table(index="achado_id", columns="status", values="municipio_ibge",
                             aggfunc="count", fill_value=0).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
