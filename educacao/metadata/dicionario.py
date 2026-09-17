"""Leitura das abas do ANEXO I (dicionário de dados) do Censo Escolar.

O layout das colunas é idêntico em todos os anos de 2007 a 2025::

    0=N | 1=Nome da Variável | 2=Descrição | 3=Tipo | 4=Tam.(1) | 5=Categoria
    6..N=Coleta por ano ("s"=sim) | última="Notas Importantes"

O que muda é a *posição* do cabeçalho e a da coluna de notas: o cabeçalho está
na linha 7 em toda parte, menos em `Tabela_Curso_Técnico` de 2025 (linha 8); as
notas aparecem na coluna 21, 22, 23, 24, 25 ou 13 conforme o ano e a aba. Nada
disso é fixado aqui — tudo é localizado pelo texto do cabeçalho.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

_ROTULO_NOME = "Nome da Vari"
_ROTULO_NOTAS = "Nota"
_LINHAS_BUSCA_CABECALHO = 20


@dataclass(slots=True)
class LinhaDicionario:
    """Uma linha de variável do dicionário, ainda sem tipo PostgreSQL."""

    nome: str
    descricao: str | None
    tipo_original: str | None
    tamanho: int | None
    categoria: str | None
    nota: str | None
    anos_coleta: list[int] = field(default_factory=list)


@dataclass(slots=True)
class Cabecalho:
    linha: int
    col_nome: int
    col_notas: int | None
    anos: dict[int, int]
    """Mapa coluna -> ano da matriz 'Coleta por ano'."""


def _texto(valor) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _inteiro(valor) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def localizar_cabecalho(worksheet) -> Cabecalho:
    """Encontra a linha do cabeçalho e as colunas de nome, notas e anos."""

    for numero, linha in enumerate(
        worksheet.iter_rows(max_row=_LINHAS_BUSCA_CABECALHO, values_only=True),
        start=1,
    ):
        col_nome = None
        col_notas = None
        for indice, celula in enumerate(linha):
            if not isinstance(celula, str):
                continue
            rotulo = celula.strip()
            if rotulo.startswith(_ROTULO_NOME):
                col_nome = indice
            elif rotulo.startswith(_ROTULO_NOTAS):
                col_notas = indice

        if col_nome is None:
            continue

        return Cabecalho(
            linha=numero,
            col_nome=col_nome,
            col_notas=col_notas,
            anos=_anos_da_matriz(worksheet, numero),
        )

    raise ValueError(
        f"Cabeçalho '{_ROTULO_NOME}...' não encontrado na aba '{worksheet.title}'"
    )


def _anos_da_matriz(worksheet, linha_cabecalho: int) -> dict[int, int]:
    """Lê a linha logo abaixo do cabeçalho, onde ficam os anos em dois dígitos."""

    linhas = list(
        worksheet.iter_rows(
            min_row=linha_cabecalho + 1,
            max_row=linha_cabecalho + 1,
            values_only=True,
        )
    )
    if not linhas:
        return {}

    anos: dict[int, int] = {}
    for indice, celula in enumerate(linhas[0]):
        texto = _texto(celula)
        if texto and texto.isdigit() and len(texto) == 2:
            anos[indice] = 2000 + int(texto)
    return anos


def ler_aba(worksheet) -> dict[str, LinhaDicionario]:
    """Todas as variáveis de uma aba, indexadas pelo nome."""

    cabecalho = localizar_cabecalho(worksheet)
    variaveis: dict[str, LinhaDicionario] = {}

    for linha in worksheet.iter_rows(
        min_row=cabecalho.linha + 1, values_only=True
    ):
        nome = _texto(
            linha[cabecalho.col_nome]
            if cabecalho.col_nome < len(linha)
            else None
        )
        # Rodapés ("Notas:", "1) Tamanho do campo...") caem aqui: têm texto com
        # espaço na coluna do nome, que nenhuma variável do Censo tem.
        if not nome or " " in nome or nome.startswith(_ROTULO_NOME):
            continue

        anos = [
            ano
            for coluna, ano in sorted(cabecalho.anos.items())
            if coluna < len(linha)
            and str(linha[coluna]).strip().lower() == "s"
        ]

        nota = None
        if cabecalho.col_notas is not None and cabecalho.col_notas < len(linha):
            nota = _texto(linha[cabecalho.col_notas])

        variaveis.setdefault(
            nome,
            LinhaDicionario(
                nome=nome,
                descricao=_texto(linha[2]) if len(linha) > 2 else None,
                tipo_original=_texto(linha[3]) if len(linha) > 3 else None,
                tamanho=_inteiro(linha[4]) if len(linha) > 4 else None,
                categoria=_texto(linha[5]) if len(linha) > 5 else None,
                nota=nota,
                anos_coleta=anos,
            ),
        )

    return variaveis


def ler_dicionario(caminho: Path) -> dict[str, dict[str, LinhaDicionario]]:
    """Lê o dicionário inteiro: {título da aba: {nome da variável: linha}}."""

    workbook = load_workbook(caminho, data_only=True, read_only=True)
    try:
        return {
            worksheet.title.strip(): ler_aba(worksheet)
            for worksheet in workbook.worksheets
        }
    finally:
        workbook.close()
