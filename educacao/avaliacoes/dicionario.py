"""Leitura dos dicionários das fontes de avaliação.

Cada fonte publica o dicionário com um layout próprio, e nenhum coincide com o
ANEXO I do Censo::

    SAEB    linha 3   Variável | Tipo | Tamanho | Descrição | Código de Preench.
    ENEM    linha 3   (ordem) | Variável | Descrição da Variável | Categoria | Edição
    PAEBES  linha 1   Tipo de Resultado | Variável | Descrição | Tipagem | Código | Regras
    IDEB    —         não existe dicionário; a especificação está em `ideb.py`

O que se repete é o princípio já usado no Censo: **nada é posição fixa**. O
cabeçalho é localizado pelo texto dos rótulos, e o que cada fonte tem de
particular fica declarado em `LAYOUTS`, não espalhado em condicionais.

Duas particularidades que o layout precisa declarar:

* o SAEB quebra o domínio em **várias linhas da planilha** — a linha da variável
  traz o primeiro código e as seguintes, com a coluna do nome vazia, trazem os
  demais. ENEM e PAEBES põem o domínio inteiro numa célula só;
* o PAEBES separa código e rótulo por ``»`` em vez de ``-``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

from ..metadata.dominios import parse_dominio
from ..metadata.models import ValorDominio

LINHAS_BUSCA_CABECALHO = 12

#: Nome de variável é identificador: sem espaço e curto. O filtro existe porque
#: o SAEB de 2015 e 2017 deixa uma nota de rodapé solta na coluna da variável
#: ("OBS.: AS QUESTÕES 1 A 6 SÃO DE RESPONSABILIDADE DO APLICADOR...").
_MAX_NOME = 64


def _parece_variavel(nome: str) -> bool:
    return len(nome) <= _MAX_NOME and " " not in nome


@dataclass(frozen=True, slots=True)
class Layout:
    """Como ler o dicionário de uma fonte."""

    fonte: str
    rotulo_nome: str
    rotulo_descricao: str
    rotulo_tipo: str | None = None
    rotulo_tamanho: str | None = None
    rotulo_categoria: str | None = None
    #: SAEB: a linha seguinte, com o nome vazio, continua o domínio da anterior.
    dominio_em_linhas: bool = False
    #: Separador entre código e rótulo dentro da célula de domínio.
    separador_dominio: str = "-"


LAYOUTS: dict[str, Layout] = {
    "saeb": Layout(
        fonte="saeb",
        rotulo_nome="Variável",
        rotulo_descricao="Descrição",
        rotulo_tipo="Tipo",
        rotulo_tamanho="Tamanho",
        rotulo_categoria="Código de Preenchimento",
        dominio_em_linhas=True,
    ),
    "enem": Layout(
        fonte="enem",
        rotulo_nome="Variável",
        rotulo_descricao="Descrição da Variável",
        rotulo_categoria="Categoria",
    ),
    "paebes": Layout(
        fonte="paebes",
        rotulo_nome="Variável",
        rotulo_descricao="Descrição",
        rotulo_tipo="Tipagem",
        rotulo_categoria="Código de Preenchimento",
        separador_dominio="»",
    ),
}


@dataclass(slots=True)
class LinhaDicionario:
    """Uma variável descrita no dicionário, ainda sem tipo PostgreSQL."""

    nome: str
    descricao: str | None = None
    tipo_original: str | None = None
    tamanho: int | None = None
    categoria: str | None = None

    @property
    def dominio(self) -> list[ValorDominio]:
        return parse_dominio(self.categoria)


@dataclass(slots=True)
class Cabecalho:
    linha: int
    col_nome: int
    col_descricao: int | None = None
    col_tipo: int | None = None
    col_tamanho: int | None = None
    col_categoria: int | None = None


def _texto(valor) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _inteiro(valor) -> int | None:
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def _normalizar_dominio(texto: str | None, separador: str) -> str | None:
    """Traz o separador da fonte para o ``-`` que `parse_dominio` entende."""

    if not texto or separador == "-":
        return texto
    linhas = []
    for linha in str(texto).splitlines():
        cabeca, marcador, cauda = linha.partition(separador)
        linhas.append(f"{cabeca.strip()} - {cauda.strip()}" if marcador else linha)
    return "\n".join(linhas)


def localizar_cabecalho(worksheet, layout: Layout) -> Cabecalho:
    """Acha a linha do cabeçalho e a coluna de cada campo, pelo texto do rótulo.

    O rótulo do nome é obrigatório; os demais são opcionais porque nem toda
    fonte publica tipo, tamanho ou domínio.
    """

    alvos = {
        "col_nome": layout.rotulo_nome,
        "col_descricao": layout.rotulo_descricao,
        "col_tipo": layout.rotulo_tipo,
        "col_tamanho": layout.rotulo_tamanho,
        "col_categoria": layout.rotulo_categoria,
    }

    for numero, linha in enumerate(
        worksheet.iter_rows(max_row=LINHAS_BUSCA_CABECALHO, values_only=True), start=1
    ):
        achados: dict[str, int] = {}
        for indice, celula in enumerate(linha):
            if not isinstance(celula, str):
                continue
            rotulo = celula.strip().casefold()
            for campo, esperado in alvos.items():
                if esperado and campo not in achados and rotulo.startswith(
                    esperado.casefold()
                ):
                    achados[campo] = indice

        if "col_nome" in achados:
            return Cabecalho(linha=numero, **achados)

    raise ValueError(
        f"cabeçalho não encontrado em '{worksheet.title}': "
        f"nenhuma das {LINHAS_BUSCA_CABECALHO} primeiras linhas tem "
        f"'{layout.rotulo_nome}'"
    )


def ler_aba(worksheet, layout: Layout) -> list[LinhaDicionario]:
    """Converte uma aba do dicionário na lista de variáveis que ela descreve."""

    cabecalho = localizar_cabecalho(worksheet, layout)

    def campo(linha: tuple, coluna: int | None) -> str | None:
        if coluna is None or coluna >= len(linha):
            return None
        return _texto(linha[coluna])

    variaveis: list[LinhaDicionario] = []
    for linha in worksheet.iter_rows(
        min_row=cabecalho.linha + 1, values_only=True
    ):
        nome = campo(linha, cabecalho.col_nome)
        categoria = campo(linha, cabecalho.col_categoria)

        if nome is not None and not _parece_variavel(nome):
            continue

        if nome is None:
            # SAEB: linha sem nome continua o domínio da variável anterior.
            if layout.dominio_em_linhas and categoria and variaveis:
                anterior = variaveis[-1]
                anterior.categoria = (
                    f"{anterior.categoria}\n{categoria}"
                    if anterior.categoria
                    else categoria
                )
            continue

        variaveis.append(
            LinhaDicionario(
                nome=nome,
                descricao=campo(linha, cabecalho.col_descricao),
                tipo_original=campo(linha, cabecalho.col_tipo),
                tamanho=_inteiro(
                    linha[cabecalho.col_tamanho]
                    if cabecalho.col_tamanho is not None
                    and cabecalho.col_tamanho < len(linha)
                    else None
                ),
                categoria=_normalizar_dominio(categoria, layout.separador_dominio),
            )
        )

    return variaveis


def ler(caminho: Path, layout: Layout, aba: str | None = None) -> list[LinhaDicionario]:
    """Lê uma aba do dicionário (a primeira que não seja índice, por padrão)."""

    workbook = load_workbook(caminho, read_only=True, data_only=True)
    try:
        if aba is not None:
            if aba not in workbook.sheetnames:
                raise KeyError(f"aba '{aba}' não existe em {caminho.name}")
            alvo = aba
        else:
            alvo = next(
                (n for n in workbook.sheetnames if not n.strip().lower().startswith("índice")),
                workbook.sheetnames[0],
            )
        return ler_aba(workbook[alvo], layout)
    finally:
        workbook.close()
