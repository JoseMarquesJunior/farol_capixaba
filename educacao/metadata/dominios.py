"""Leitura da coluna 'Categoria' do dicionário de dados.

A célula traz o domínio de valores da variável, uma linha por código::

    1 - Federal
    2 - Estadual
    3 - Municipal
    4 - Privada

Há duas variações: linhas de ressalva sem código (``- Não aplicável para
escolas públicas``) e rótulos longos que o INEP quebrou em mais de uma
linha, que precisam ser recolados ao rótulo anterior.
"""

from __future__ import annotations

import re

from .models import ValorDominio

_COM_CODIGO = re.compile(r"^(-?\d+)\s*[-–]\s*(.+)$")
_SEM_CODIGO = re.compile(r"^[-–]\s*(.+)$")


def parse_dominio(categoria: str | None) -> list[ValorDominio]:
    """Converte a célula 'Categoria' numa lista de pares código/rótulo."""

    if not categoria:
        return []

    valores: list[ValorDominio] = []

    for linha in str(categoria).splitlines():
        linha = linha.strip()
        if not linha:
            continue

        com_codigo = _COM_CODIGO.match(linha)
        if com_codigo:
            valores.append(
                ValorDominio(
                    codigo=com_codigo.group(1),
                    rotulo=com_codigo.group(2).strip(),
                )
            )
            continue

        sem_codigo = _SEM_CODIGO.match(linha)
        if sem_codigo:
            valores.append(
                ValorDominio(codigo=None, rotulo=sem_codigo.group(1).strip())
            )
            continue

        # Continuação do rótulo anterior, quebrado em várias linhas na planilha.
        if valores:
            anterior = valores[-1]
            valores[-1] = ValorDominio(
                codigo=anterior.codigo,
                rotulo=f"{anterior.rotulo} {linha}".strip(),
            )

    return valores
