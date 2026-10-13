"""Extração dos valores de interesse das respostas do SICONFI (funções puras).

Nomes reais das colunas, conferidos em 2026-09-21 contra a API (não são
documentados publicamente e podem mudar — por isso as comparações de texto
ignoram acento e caixa, e o que não casa vira `None`, nunca zero):

`/rreo` e `/dca` devolvem uma linha por (conta × coluna), com os campos::

    exercicio, demonstrativo, periodo, periodicidade, instituicao, cod_ibge,
    uf, populacao, anexo, esfera, rotulo, coluna, cod_conta, conta, valor

* `populacao` vem em TODA linha e é a população do exercício (Vitória 2024 =
  331.785, contra 343.378 no retrato atual de `/entes`, que ignora
  `an_exercicio`). É a fonte do per capita.
* **RREO-Anexo 02** (despesa por função). Educação é `conta == "Educação"`;
  as subfunções vêm como "Educação Infantil" etc. Há dois blocos, distintos por
  `cod_conta`: `RREO2TotalDespesas` (exceto intra-orçamentárias) e
  `RREO2TotalDespesasIntra`. Colunas usadas: "DOTAÇÃO ATUALIZADA (a)",
  "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)" e "DESPESAS LIQUIDADAS ATÉ O
  BIMESTRE (d)" (acumuladas, não do bimestre).
* **DCA-Anexo I-E** (despesa por função, fechamento anual). Educação é
  `conta == "12 - Educação"`; o total é `conta == "Despesas Exceto
  Intraorçamentárias"`. Colunas: "Despesas Empenhadas", "Despesas Liquidadas",
  "Despesas Pagas". Só cobre despesa EXCETO intra-orçamentária — o mesmo escopo
  do bloco `RREO2TotalDespesas`, o que permite conferir um contra o outro.
  O mesmo anexo detalha as SUBFUNÇÕES ("12.361 - Ensino Fundamental"), mais o
  agregado "FU12 - Demais Subfunções" — dez subfunções distintas aparecem no ES
  entre 2021 e 2025, de 2 a 9 por município.
* **DCA-Anexo I-C** (receita). FUNDEB recebido = duas contas, coluna "Receitas
  Brutas Realizadas": "Transferências de Recursos do Fundo de Manutenção e
  Desenvolvimento da Educação Básica…" e "Transferências de Recursos de
  Complementação da União ao Fundo…" (códigos diferentes em 2021 e 2022+). A
  contribuição ao FUNDEB é a coluna "Deduções - FUNDEB", lida no total de
  receitas (`ReceitasExcetoIntraOrcamentarias`).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, Sequence

Linha = dict[str, Any]


class ErroParsing(ValueError):
    """A resposta tem uma forma que o parser não sabe interpretar com segurança."""


def norm(texto: Any) -> str:
    """Minúsculas, sem acento e com espaços colapsados — para comparar nomes."""
    if texto is None:
        return ""
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def validar_ibge(cod: Any, *, municipio: bool = True) -> int:
    """Código IBGE como inteiro; município tem 7 dígitos, o Estado tem 2."""
    texto = str(cod).strip()
    esperado = 7 if municipio else 2
    if not re.fullmatch(rf"\d{{{esperado}}}", texto):
        raise ErroParsing(f"código IBGE inválido (esperava {esperado} dígitos): {cod!r}")
    return int(texto)


def _unico(linhas: Sequence[Linha], descricao: str) -> float | None:
    """Valor de uma célula (conta × coluna). Duplicata idêntica é tolerada;
    duplicata com valores diferentes é ambígua e para o processamento."""
    if not linhas:
        return None
    valores = {round(float(l["valor"]), 2) for l in linhas if l.get("valor") is not None}
    if not valores:
        return None
    if len(valores) > 1:
        raise ErroParsing(f"{descricao}: {len(linhas)} linhas com valores diferentes {sorted(valores)}")
    return valores.pop()


def populacao(itens: Iterable[Linha]) -> int | None:
    """População do exercício, como o SICONFI a reporta nas próprias linhas."""
    valores = {int(l["populacao"]) for l in itens if l.get("populacao") is not None}
    if len(valores) == 1:
        return valores.pop()
    if len(valores) > 1:
        raise ErroParsing(f"população ambígua nas linhas: {sorted(valores)}")
    return None


# ------------------------------------------------------------------ DCA I-E

_ESTAGIOS_DCA = {
    "despesas empenhadas": "empenhada",
    "despesas liquidadas": "liquidada",
    "despesas pagas": "paga",
}
_FUNCAO = re.compile(r"^\d{2} - ")
_TOTAL_EXCETO_INTRA = "despesas exceto intraorcamentarias"


def _por_estagio(linhas: Iterable[Linha], descricao: str) -> dict[str, float]:
    grupos: dict[str, list[Linha]] = {}
    for l in linhas:
        if (estagio := _ESTAGIOS_DCA.get(norm(l["coluna"]))) is not None:
            grupos.setdefault(estagio, []).append(l)
    return {e: v for e, ls in grupos.items() if (v := _unico(ls, f"{descricao}/{e}")) is not None}


def educacao_dca(itens: Iterable[Linha]) -> dict[str, float] | None:
    """Despesa da função 12 (Educação) no DCA-Anexo I-E, por estágio.

    Devolve `{"empenhada", "liquidada", "paga", "total_empenhada", ...}` ou
    `None` se a função não está no anexo. Os `total_*` são a despesa total do
    ente (exceto intra-orçamentária), para calcular a participação da educação.
    """
    itens = list(itens)
    educacao = _por_estagio((l for l in itens if str(l["conta"]).startswith("12 - ")), "DCA I-E função 12")
    if not educacao:
        return None
    total = _por_estagio((l for l in itens if norm(l["conta"]) == _TOTAL_EXCETO_INTRA), "DCA I-E total")
    return {**educacao, **{f"total_{e}": v for e, v in total.items()}}


#: Subfunção dentro de uma função: "12.361 - Ensino Fundamental". O SICONFI ainda
#: agrega o resto em "FU12 - Demais Subfunções", que é um valor real e entra como
#: subfunção própria (código "12.xxx") — ignorá-lo abriria um buraco na soma.
_SUBFUNCAO = re.compile(r"^(?P<funcao>\d{2})\.(?P<sub>\d{3}) - (?P<nome>.+)$")
_DEMAIS = re.compile(r"^FU(?P<funcao>\d{2}) - (?P<nome>.+)$")


def subfuncoes_dca(itens: Iterable[Linha], funcao: str = "12") -> list[dict[str, Any]]:
    """Despesa por subfunção de uma função, no DCA-Anexo I-E.

    Uma entrada por subfunção, com os estágios que o anexo trouxer. As
    subfunções somam exatamente o total da função (conferido em 395 de 395
    ente-anos de 2021–2025), o que torna a soma uma verificação de fechamento.
    """
    por_sub: dict[str, dict[str, Any]] = {}
    for l in itens:
        conta = str(l["conta"])
        achado = _SUBFUNCAO.match(conta) or _DEMAIS.match(conta)
        if not achado or achado["funcao"] != funcao:
            continue
        estagio = _ESTAGIOS_DCA.get(norm(l["coluna"]))
        if estagio is None:
            continue
        grupos = achado.groupdict()
        codigo = f"{funcao}.{grupos['sub']}" if "sub" in grupos else f"FU{funcao}"
        item = por_sub.setdefault(codigo, {"codigo": codigo, "nome": grupos["nome"].strip(), "_linhas": {}})
        item["_linhas"].setdefault(estagio, []).append(l)

    saida = []
    for codigo, item in sorted(por_sub.items()):
        valores = {e: v for e, ls in item.pop("_linhas").items()
                   if (v := _unico(ls, f"subfunção {codigo}/{e}")) is not None}
        saida.append({**item, **valores})
    return saida


def soma_funcoes_dca(itens: Iterable[Linha]) -> tuple[dict[str, float], dict[str, float]]:
    """(soma das funções, total do anexo) por estágio — para a conferência de fechamento.

    Só entram as linhas de função (`NN - Nome`); subfunções (`NN.NNN - …`) e
    agregados `FUxx - Demais Subfunções` ficam de fora para não somar em dobro.
    """
    itens = list(itens)
    soma: dict[str, float] = {}
    for l in itens:
        if _FUNCAO.match(str(l["conta"])) and (e := _ESTAGIOS_DCA.get(norm(l["coluna"]))):
            soma[e] = soma.get(e, 0.0) + float(l["valor"])
    total = _por_estagio((l for l in itens if norm(l["conta"]) == _TOTAL_EXCETO_INTRA), "DCA I-E total")
    return soma, total


# ------------------------------------------------------------------ DCA I-C

#: O FUNDEB entra no I-C em DUAS contas de nível diferente, e casar só a primeira
#: subestima os municípios que recebem complementação:
#:   * transferências do fundo (Estado)  1.7.5.1.00.0.0  (em 2021: 1.7.5.8.01.0.0)
#:   * complementação da União (VAAT…)   1.7.1.5.00.0.0  (em 2021: 1.7.1.8.09.0.0)
#: O código mudou entre 2021 e 2022, então o casamento é pelo NOME da conta.
#: Conferido ao centavo contra o DCA I-HI: `Transferências do FUNDEB` (4.5.2.2.0)
#: = fundo + complementação (Afonso Cláudio 2025: 31.570.760,18 + 6.631.696,17).
_FUNDEB_FUNDO = re.compile(r"transferencias de recursos do fundo de manutencao e desenvolvimento da educacao basica")
_FUNDEB_COMPLEMENTACAO = re.compile(
    r"transferencias de recursos de complementacao da uniao ao fundo de manutencao e desenvolvimento da educacao basica")


def _prefixo(cod_conta: str) -> tuple[str, ...]:
    """`RO1.7.5.1.00.0.0` -> ('1','7','5','1'): a parte significativa do código."""
    partes = cod_conta.removeprefix("RO").split(".")
    while partes and set(partes[-1]) == {"0"}:
        partes.pop()
    return tuple(partes)


def _contas_de_topo(itens: Sequence[Linha], padrao: re.Pattern[str]) -> dict[str, list[Linha]]:
    """Contas de receita que casam com `padrao`, sem conta filha de outra já casada."""
    por_conta: dict[str, list[Linha]] = {}
    for l in itens:
        if (norm(l["coluna"]) == "receitas brutas realizadas" and str(l["cod_conta"]).startswith("RO1.7")
                and padrao.search(norm(l["conta"]))):
            por_conta.setdefault(l["cod_conta"], []).append(l)
    prefixos = {c: _prefixo(c) for c in por_conta}
    return {
        c: ls for c, ls in por_conta.items()
        if not any(o != c and len(q) < len(prefixos[c]) and prefixos[c][: len(q)] == q for o, q in prefixos.items())
    }


def _receita_de_topo(itens: Sequence[Linha], padrao: re.Pattern[str], descricao: str) -> float | None:
    """Soma das contas que casam com `padrao`, sem contar conta filha de outra já casada."""
    topo = _contas_de_topo(itens, padrao)
    if not topo:
        return None
    return sum(_unico(ls, f"{descricao} {c}") or 0.0 for c, ls in topo.items())


def contas_fundeb_dca(itens: Iterable[Linha]) -> dict[str, list[str]]:
    """Códigos das contas do FUNDEB no I-C, achadas pelo NOME: `{"fundo": [...], "complementacao": [...]}`.

    É a ponte para a MSC, que só traz códigos: o prefixo destas contas é o que
    identifica o FUNDEB na natureza de receita de 8 dígitos (ver `msc.prefixo_natureza`).
    """
    itens = list(itens)
    return {"fundo": sorted(_contas_de_topo(itens, _FUNDEB_FUNDO)),
            "complementacao": sorted(_contas_de_topo(itens, _FUNDEB_COMPLEMENTACAO))}


def fundeb_dca(itens: Iterable[Linha]) -> dict[str, float] | None:
    """Receita do FUNDEB e contribuição ao FUNDEB no DCA-Anexo I-C.

    `receita` = transferências do fundo + complementação da União. Sem a linha do
    fundo devolve `None` (total parcial seria enganoso); a complementação ausente
    fica FORA do dicionário — "sem linha", não zero. A contribuição é a dedução
    "Deduções - FUNDEB" no total de receitas.
    """
    itens = list(itens)
    fundo = _receita_de_topo(itens, _FUNDEB_FUNDO, "FUNDEB fundo")
    if fundo is None:
        return None
    complementacao = _receita_de_topo(itens, _FUNDEB_COMPLEMENTACAO, "FUNDEB complementação")

    saida = {"receita": fundo + (complementacao or 0.0), "receita_fundo": fundo}
    if complementacao is not None:
        saida["complementacao_uniao"] = complementacao
    deducao = [
        l for l in itens
        if l["cod_conta"] == "ReceitasExcetoIntraOrcamentarias" and norm(l["coluna"]) == "deducoes - fundeb"
    ]
    if (valor := _unico(deducao, "dedução FUNDEB")) is not None:
        saida["contribuicao"] = valor
    return saida


# ----------------------------------------------------------------- RREO A02

_COLUNAS_RREO = (
    ("dotacao_atualizada", "dotacao atualizada"),
    ("empenhada_acum", "despesas empenhadas ate o bimestre"),
    ("liquidada_acum", "despesas liquidadas ate o bimestre"),
)


def educacao_rreo(itens: Iterable[Linha]) -> dict[str, float] | None:
    """Educação (função 12) no RREO-Anexo 02, despesa exceto intra-orçamentária.

    Valores acumulados até o bimestre. `None` se a linha não existir.
    """
    bloco = [l for l in itens if l["cod_conta"] == "RREO2TotalDespesas"]
    educacao = [l for l in bloco if norm(l["conta"]) == "educacao"]
    saida: dict[str, float] = {}
    for chave, prefixo in _COLUNAS_RREO:
        linhas = [l for l in educacao if norm(l["coluna"]).startswith(prefixo)]
        if (v := _unico(linhas, f"RREO A02 educação/{chave}")) is not None:
            saida[chave] = v
    return saida or None
