"""Conversão do tipo declarado no dicionário do INEP para um tipo PostgreSQL.

O dicionário usa apenas três tipos — `Num`, `Char` e `Data` — e uma coluna
`Tam.` com o número de caracteres. Nenhum dos três distingue inteiro de
decimal, e `Tam.` nem sempre corresponde ao que está no arquivo, por isso
`educacao.metadata.verificacao` confere cada tipo contra uma amostra dos
dados antes do catálogo ser gravado.
"""

from __future__ import annotations

LIMITE_VARCHAR = 255

#: `Data` não vira DATE: o INEP grava datas no formato SAS
#: (``10FEB2025:00:00:00``), que o PostgreSQL não converte direto. A coluna
#: entra em `raw` como texto e é convertida na camada `stg`.
TIPO_DATA = "TEXT"


def tipo_postgres(tipo_original: str | None, tamanho: int | None) -> str:
    """Tipo PostgreSQL correspondente ao par (Tipo, Tam.) do dicionário."""

    if tipo_original is None:
        return "TEXT"

    tipo = tipo_original.strip().lower()

    if tipo == "char":
        if tamanho and tamanho <= LIMITE_VARCHAR:
            return f"VARCHAR({tamanho})"
        return "TEXT"

    if tipo == "data":
        return TIPO_DATA

    if tipo == "num":
        return tipo_inteiro(tamanho)

    return "TEXT"


def tipo_inteiro(digitos: int | None) -> str:
    """Menor tipo inteiro que comporta um número com `digitos` casas."""

    if digitos is None:
        return "BIGINT"
    if digitos <= 4:
        return "SMALLINT"
    if digitos <= 9:
        return "INTEGER"
    return "BIGINT"


def cabe_no_tipo(tipo: str, digitos: int) -> bool:
    """Se um inteiro com `digitos` casas cabe em `tipo` sem estourar."""

    limites = {"SMALLINT": 4, "INTEGER": 9, "BIGINT": 18}
    return digitos <= limites.get(tipo.upper(), 18)
