"""MSC orçamentária do SICONFI: FUNDEB recebido, despesa da Educação por natureza
econômica (Nível 2) e por fonte de recursos (o fluxo fonte → subfunção).

Consulta usada (uma por município e exercício)::

    /msc_orcamentaria?id_ente=<IBGE7>&an_referencia=<ano>&me_referencia=12
                     &co_tipo_matriz=MSCC&classe_conta=6&id_tv=ending_balance&limit=5000

Os seis parâmetros são obrigatórios: sem `classe_conta` a API devolve zero linhas.
`limit` aceita 5000 (o padrão é 1000 — e com 1000 a coleta de Vitória levou HTTP
429 depois de 20 páginas). Dezembro com `ending_balance` = o acumulado do ano.

Estrutura REAL da resposta — conferida em 2026-09-22 (Vitória 2021/2024 e
Afonso Cláudio 2022/2024). Uma linha por combinação de informações
complementares, com os 21 campos::

    tipo_matriz, cod_ibge, classe_conta, conta_contabil, poder_orgao,
    ano_fonte_recursos, fonte_recursos, funcao, subfuncao, exercicio,
    mes_referencia, educacao_saude, data_referencia, entrada_msc,
    natureza_despesa, ano_inscricao, natureza_receita, valor, natureza_conta,
    tipo_valor, complemento_fonte

* **Só códigos, nenhuma descrição.** Os nomes vêm do DCA (que tem descrição) e
  das tabelas oficiais citadas abaixo.
* `conta_contabil` — 9 dígitos do PCASP, sem pontos. Na classe 6:
    - `621200000` receita realizada (6.2.1.2); `6213…` deduções (6.2.1.3);
    - `6221301x0`…`6221307x0` crédito empenhado: 01 a liquidar, 02 em
      liquidação, 03 liquidado a pagar, 04 liquidado pago, 05/06 inscritos em
      restos a pagar não processados, 07 inscritos em restos a pagar processados.
  Em dezembro o empenho do ano já está redistribuído entre 01…07 (a inscrição
  em restos a pagar move 01→05 e 03→07). Logo: **empenhada = 01…07; liquidada =
  03 + 04 + 07; paga = 04**. Conferido AO CENTAVO contra o DCA Anexo I-E em
  Afonso Cláudio 2024 (49.699.516,59 / 48.939.943,63 / 48.708.923,11), e
  subfunção a subfunção. As contas `6229…` e `63…` são controles paralelos e
  execução de restos a pagar de anos anteriores: ficam de fora.
* `natureza_despesa` — 8 dígitos `CGMMEEDD`: categoria (3 corrente, 4 capital),
  grupo, modalidade de aplicação, elemento e desdobramento. **Intra-orçamentária
  = modalidade 91**, excluída — o mesmo escopo do DCA I-E.
* `natureza_receita` — 8 dígitos do ementário (`17515001` = 1.7.5.1.50.0.1).
* `fonte_recursos` — em 2022 e depois, 4 dígitos: o 1º é o exercício (1 =
  corrente, 2 = anteriores; é o mesmo valor de `ano_fonte_recursos`) e os 3
  seguintes são a fonte padronizada da STN (500 impostos, 540–543 FUNDEB…).
  **Em 2021 os municípios do ES usavam códigos locais de 8 dígitos** (ex.:
  `11110000`), que não se traduzem sem a tabela da época — o fluxo por fonte
  fica indisponível nesse exercício.
* `complemento_fonte` — `1001` MDE, `1002` saúde, `1070` FUNDEB aplicado nos
  profissionais da educação básica (70%). `educacao_saude` veio sempre nulo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from .cliente import ClienteSiconfi, Resposta
from .proveniencia import Consulta, caminho_relativo

Linha = dict[str, Any]

ENDPOINT = "msc_orcamentaria"
LIMITE_PAGINA = 5000

CONTA_RECEITA_REALIZADA = "621200000"
#: Estágios do empenho na classe 6 (ver docstring). Os três conjuntos somam
#: exatamente os três estágios do DCA I-E.
CONTAS_EMPENHADA = tuple(f"62213{n:02d}00" for n in range(1, 8))
CONTAS_LIQUIDADA = ("622130300", "622130400", "622130700")
CONTAS_PAGA = ("622130400",)
MODALIDADE_INTRA = "91"


def parametros(cod_ibge: int, ano: int) -> dict[str, Any]:
    return {"id_ente": cod_ibge, "an_referencia": ano, "me_referencia": 12, "co_tipo_matriz": "MSCC",
            "classe_conta": 6, "id_tv": "ending_balance", "limit": LIMITE_PAGINA}


def coletar(cliente: ClienteSiconfi, cod_ibge: int, ano: int) -> tuple[Resposta, Consulta]:
    """A matriz de dezembro (classe 6) de um município, com a consulta que a trouxe."""
    p = parametros(cod_ibge, ano)
    r = cliente.consultar(ENDPOINT, **p)
    consulta = Consulta(
        fonte="SICONFI", recurso=ENDPOINT,
        descricao=f"MSC orçamentária (MSCC, classe 6, dezembro, saldo final), exercício {ano}",
        url=cliente.url_completa(ENDPOINT, p), obtido_em=r.obtido_em, arquivo=caminho_relativo(r.arquivo))
    return r, consulta


# ----------------------------------------------------------- fonte de recursos

_FONTE_PADRAO = re.compile(r"^(?P<exercicio>[12])(?P<codigo>\d{3})$")

#: Nomes das fontes padronizadas (Portaria STN nº 710/2021 e atualizações) que
#: aparecem na Educação dos municípios do ES. Código sem nome aqui aparece como
#: "fonte NNN" — melhor do que inventar a descrição.
NOME_FONTE = {
    "500": "Recursos não vinculados de impostos",
    "501": "Outros recursos não vinculados",
    "540": "FUNDEB — impostos e transferências de impostos",
    "541": "FUNDEB — complementação da União (VAAF)",
    "542": "FUNDEB — complementação da União (VAAT)",
    "543": "FUNDEB — complementação da União (VAAR)",
    "550": "Salário-educação",
    "551": "FNDE — PDDE",
    "552": "FNDE — PNAE (alimentação escolar)",
    "553": "FNDE — PNATE (transporte escolar)",
    "569": "Outras transferências do FNDE",
    "570": "Convênios com a União vinculados à educação",
    "571": "Convênios com o Estado vinculados à educação",
    "573": "Royalties do petróleo e gás vinculados à educação",
    "574": "Operações de crédito vinculadas à educação",
    "599": "Outros recursos vinculados à educação",
}

#: Origem no diagrama de fluxo. São quatro grupos mutuamente exclusivos; a fonte
#: 500 junta impostos PRÓPRIOS e TRANSFERIDOS (FPM, ICMS…) — a contabilidade não
#: os separa pela fonte, e dividir seria estimar.
GRUPOS_FONTE = {
    "impostos": "Impostos e transferências de impostos (fonte 500)",
    "fundeb": "FUNDEB (fontes 540–543)",
    "federal": "Transferências federais específicas — FNDE (fontes 550–553, 569)",
    "outras": "Outras fontes (convênios, royalties, operações de crédito, demais recursos)",
}


def fonte_padronizada(fonte: Any) -> tuple[int, str] | None:
    """`"1540"` → `(1, "540")`; código fora do padrão da STN → `None`."""
    achado = _FONTE_PADRAO.match(str(fonte or "").strip())
    return (int(achado["exercicio"]), achado["codigo"]) if achado else None


def grupo_fonte(codigo: str) -> str:
    if codigo == "500":
        return "impostos"
    if codigo in {"540", "541", "542", "543"}:
        return "fundeb"
    if codigo in {"550", "551", "552", "553", "569"}:
        return "federal"
    return "outras"


def nome_fonte(codigo: str) -> str:
    return NOME_FONTE.get(codigo, f"fonte {codigo}")


# ---------------------------------------------------- natureza econômica (Nível 2)

#: Mapeamento da natureza da despesa em categorias econômicas — o Nível 2.
#: Conferido nas naturezas reais da função 12 de Vitória e Afonso Cláudio (2024)
#: antes de generalizar. Base: Portaria Interministerial STN/SOF nº 163/2001
#: (anexo II): o 2º dígito é o GRUPO e os dígitos 5–6 o ELEMENTO.
#:
#: Atenção a um equívoco comum: "classe 3/4" aqui é a CATEGORIA econômica da
#: natureza da despesa (3 corrente, 4 capital). No PCASP, as classes 3 e 4 são
#: variações patrimoniais (VPD/VPA) da matriz patrimonial — outra coisa, que não
#: é usada neste painel.
CATEGORIAS = {
    "pessoal": "Pessoal e encargos sociais",
    "custeio": "Custeio (outras despesas correntes)",
    "investimento": "Investimentos",
    "outras": "Outras (juros, amortização, inversões)",
}

SUBCATEGORIAS = {
    "pessoal_ativo": "Pessoal ativo e encargos",
    "pessoal_inativo": "Inativos e pensionistas",
    "material_consumo": "Material de consumo",
    "distribuicao_gratuita": "Material e bens para distribuição gratuita",
    "servicos_pj": "Serviços de terceiros — pessoa jurídica",
    "servicos_pf": "Serviços de terceiros — pessoa física",
    "mao_de_obra": "Locação de mão de obra",
    "tic": "Serviços de tecnologia da informação",
    "entidades": "Transferências a entidades sem fins lucrativos",
    "consorcios": "Rateio de consórcios públicos",
    "auxilios": "Auxílio-alimentação e auxílio-transporte",
    "outras_correntes": "Demais despesas correntes",
    "obras": "Obras e instalações",
    "equipamentos": "Equipamentos e material permanente",
    "outros_investimentos": "Demais investimentos",
    "divida_inversoes": "Juros, amortização e inversões financeiras",
}

#: Elementos de despesa mais comuns na Educação (Portaria 163/2001, anexo II).
NOME_ELEMENTO = {
    "01": "Aposentadorias", "03": "Pensões", "04": "Contratação por tempo determinado",
    "05": "Outros benefícios previdenciários", "07": "Contribuição a entidades fechadas de previdência",
    "08": "Outros benefícios assistenciais", "11": "Vencimentos e vantagens fixas — pessoal civil",
    "13": "Obrigações patronais", "14": "Diárias — civil", "16": "Outras despesas variáveis — pessoal civil",
    "18": "Auxílio financeiro a estudantes", "30": "Material de consumo",
    "31": "Premiações", "32": "Material, bem ou serviço para distribuição gratuita",
    "33": "Passagens e despesas com locomoção", "35": "Serviços de consultoria",
    "36": "Outros serviços de terceiros — pessoa física", "37": "Locação de mão de obra",
    "39": "Outros serviços de terceiros — pessoa jurídica",
    "40": "Serviços de tecnologia da informação e comunicação — PJ", "41": "Contribuições",
    "43": "Subvenções sociais", "46": "Auxílio-alimentação", "47": "Obrigações tributárias e contributivas",
    "48": "Outros auxílios financeiros a pessoas físicas", "49": "Auxílio-transporte",
    "51": "Obras e instalações", "52": "Equipamentos e material permanente", "61": "Aquisição de imóveis",
    "70": "Rateio pela participação em consórcio público", "91": "Sentenças judiciais",
    "92": "Despesas de exercícios anteriores", "93": "Indenizações e restituições",
    "94": "Indenizações e restituições trabalhistas", "96": "Ressarcimento de despesas de pessoal requisitado",
}

_MODALIDADES_CONSORCIO = {"71", "72", "73", "74", "75", "76"}


def classificar_natureza(natureza: str) -> tuple[str, str]:
    """Natureza de 8 dígitos → (categoria, subcategoria) do Nível 2."""
    n = str(natureza or "")
    if not re.fullmatch(r"\d{8}", n):
        return "outras", "divida_inversoes" if n[:1] == "4" else "outras_correntes"
    grupo, modalidade, elemento = n[1], n[2:4], n[4:6]
    if grupo == "1":
        return "pessoal", "pessoal_inativo" if elemento in {"01", "03", "05"} else "pessoal_ativo"
    if grupo == "3":
        if modalidade == "50":
            return "custeio", "entidades"
        if modalidade in _MODALIDADES_CONSORCIO:
            return "custeio", "consorcios"
        return "custeio", {
            "30": "material_consumo", "32": "distribuicao_gratuita", "39": "servicos_pj", "36": "servicos_pf",
            "37": "mao_de_obra", "40": "tic", "46": "auxilios", "49": "auxilios",
        }.get(elemento, "outras_correntes")
    if grupo == "4":
        return "investimento", {"51": "obras", "52": "equipamentos"}.get(elemento, "outros_investimentos")
    return "outras", "divida_inversoes"


# ------------------------------------------------------------------ parsing

def _texto(v: Any) -> str:
    return "" if v is None else str(v).strip()


def despesa_educacao(itens: Iterable[Linha], funcao: str = "12") -> pd.DataFrame:
    """Despesa da função 12, exceto intra-orçamentária, no maior detalhe útil.

    Uma linha por (subfunção, fonte, complemento, natureza) com empenhada,
    liquidada e paga. Fonte fora do padrão da STN fica com `fonte_padrao=False`
    e o código original em `fonte_original`.
    """
    registros: dict[tuple, dict[str, Any]] = {}
    for l in itens:
        conta = _texto(l.get("conta_contabil"))
        if conta not in CONTAS_EMPENHADA or _texto(l.get("funcao")).zfill(2) != funcao:
            continue
        natureza = _texto(l.get("natureza_despesa"))
        if natureza[2:4] == MODALIDADE_INTRA:
            continue
        original = _texto(l.get("fonte_recursos"))
        padrao = fonte_padronizada(original)
        chave = (_texto(l.get("subfuncao")).zfill(3), original, _texto(l.get("complemento_fonte")), natureza)
        r = registros.setdefault(chave, {
            "subfuncao": chave[0], "fonte_original": original, "fonte_padrao": padrao is not None,
            "exercicio_fonte": padrao[0] if padrao else None, "fonte": padrao[1] if padrao else None,
            "complemento": chave[2] or None, "natureza": natureza, "empenhada": 0.0, "liquidada": 0.0, "paga": 0.0,
        })
        valor = float(l.get("valor") or 0.0)
        r["empenhada"] += valor
        if conta in CONTAS_LIQUIDADA:
            r["liquidada"] += valor
        if conta in CONTAS_PAGA:
            r["paga"] += valor
    colunas = ["subfuncao", "fonte_original", "fonte_padrao", "exercicio_fonte", "fonte", "complemento",
               "natureza", "empenhada", "liquidada", "paga"]
    df = pd.DataFrame(list(registros.values()), columns=colunas)
    return df[df[["empenhada", "liquidada", "paga"]].abs().sum(axis=1) > 0].reset_index(drop=True)


def receita_realizada(itens: Iterable[Linha]) -> pd.DataFrame:
    """Receita realizada no ano (conta 6.2.1.2) por natureza, fonte e complemento."""
    soma: dict[tuple, float] = {}
    for l in itens:
        if _texto(l.get("conta_contabil")) != CONTA_RECEITA_REALIZADA:
            continue
        chave = (_texto(l.get("natureza_receita")), _texto(l.get("fonte_recursos")), _texto(l.get("complemento_fonte")))
        soma[chave] = soma.get(chave, 0.0) + float(l.get("valor") or 0.0)
    return pd.DataFrame([{"natureza_receita": k[0], "fonte_original": k[1], "complemento": k[2] or None, "valor": v}
                         for k, v in soma.items()], columns=["natureza_receita", "fonte_original", "complemento", "valor"])


def prefixo_natureza(cod_conta_dca: str) -> str:
    """`RO1.7.5.1.00.0.0` → `"1751"`; `RO1.7.5.8.01.0.0` → `"175801"`.

    Liga a conta do DCA (que tem descrição) à natureza de 8 dígitos da MSC (que
    não tem): é assim que o código do FUNDEB é IDENTIFICADO nos dados, em vez de
    adivinhado.
    """
    partes = cod_conta_dca.removeprefix("RO").split(".")
    while partes and set(partes[-1]) == {"0"}:
        partes.pop()
    return "".join(partes)


@dataclass(frozen=True, slots=True)
class FundebMSC:
    fundo: float
    complementacao: float | None
    por_fonte: dict[str, float]  # "540": …, "542": … (só em 2022+)

    @property
    def total(self) -> float:
        return self.fundo + (self.complementacao or 0.0)


def fundeb(receita: pd.DataFrame, prefixos_fundo: Sequence[str], prefixos_complementacao: Sequence[str]) -> FundebMSC | None:
    """Receita do FUNDEB na MSC, pelos prefixos de natureza achados no DCA I-C.

    `None` quando não há linha do fundo (total parcial seria enganoso); a
    complementação ausente fica `None` — "sem linha", não zero.
    """
    if receita.empty or not prefixos_fundo:
        return None
    nat = receita["natureza_receita"].astype(str)
    eh_fundo = nat.str.startswith(tuple(prefixos_fundo))
    eh_compl = nat.str.startswith(tuple(prefixos_complementacao)) if prefixos_complementacao else pd.Series(False, index=receita.index)
    if not eh_fundo.any():
        return None
    selecionado = receita[eh_fundo | eh_compl]
    por_fonte: dict[str, float] = {}
    for fonte, valor in zip(selecionado["fonte_original"], selecionado["valor"]):
        if (p := fonte_padronizada(fonte)) is not None:
            por_fonte[p[1]] = round(por_fonte.get(p[1], 0.0) + float(valor), 2)
    return FundebMSC(
        fundo=round(float(receita.loc[eh_fundo, "valor"].sum()), 2),
        complementacao=round(float(receita.loc[eh_compl, "valor"].sum()), 2) if eh_compl.any() else None,
        por_fonte=por_fonte,
    )


def receita_por_fonte(receita: pd.DataFrame) -> dict[str, float]:
    """Receita realizada por fonte padronizada (3 dígitos) — só 2022+."""
    saida: dict[str, float] = {}
    for fonte, valor in zip(receita["fonte_original"], receita["valor"]):
        if (p := fonte_padronizada(fonte)) is not None:
            saida[p[1]] = round(saida.get(p[1], 0.0) + float(valor), 2)
    return saida


def fluxo_fonte_subfuncao(despesa: pd.DataFrame) -> pd.DataFrame:
    """Empenhado por (grupo de fonte, fonte, subfunção) — as arestas do diagrama.

    Só faz sentido com fontes padronizadas; um exercício com códigos locais
    devolve vazio (e o painel diz por quê).
    """
    d = despesa[despesa["fonte_padrao"]]
    if d.empty:
        return pd.DataFrame(columns=["grupo", "fonte", "subfuncao", "empenhada"])
    d = d.assign(grupo=d["fonte"].map(grupo_fonte))
    return (d.groupby(["grupo", "fonte", "subfuncao"], as_index=False)["empenhada"].sum()
            .query("empenhada != 0").reset_index(drop=True))


def natureza_economica(despesa: pd.DataFrame) -> pd.DataFrame:
    """Nível 2: empenhada, liquidada e paga por categoria, subcategoria e elemento."""
    if despesa.empty:
        return pd.DataFrame(columns=["categoria", "subcategoria", "elemento", "empenhada", "liquidada", "paga"])
    classes = despesa["natureza"].map(classificar_natureza)
    d = despesa.assign(categoria=classes.str[0], subcategoria=classes.str[1], elemento=despesa["natureza"].str[4:6])
    return (d.groupby(["categoria", "subcategoria", "elemento"], as_index=False)[["empenhada", "liquidada", "paga"]]
            .sum().reset_index(drop=True))


def fontes_do_exercicio(despesa: pd.DataFrame) -> str:
    """"padronizada", "local" ou "sem_dado" — decide se o fluxo por fonte existe."""
    if despesa.empty:
        return "sem_dado"
    return "padronizada" if despesa["fonte_padrao"].mean() >= 0.99 else "local"


def resumo_despesa(despesa: pd.DataFrame) -> Mapping[str, float]:
    return {k: round(float(despesa[k].sum()), 2) for k in ("empenhada", "liquidada", "paga")}
