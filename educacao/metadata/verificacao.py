"""Conferência do tipo declarado contra uma amostra dos dados reais.

O dicionário do INEP declara só `Num`, `Char` e `Data`, e a coluna `Tam.` nem
sempre bate com o arquivo. Dois casos reais que quebram a carga se o tipo
declarado for aceito no escuro:

* `LATITUDE`/`LONGITUDE` são declaradas `Num` com Tam=20, mas contêm decimais
  (`-11.9309573`) — viram NUMERIC, não BIGINT.
* `NU_TELEFONE` é declarada `Num` com Tam=8 e traz valores de 9 dígitos.

Esta passagem lê as primeiras linhas de cada arquivo, mede o que existe de
fato e promove o tipo quando o declarado não comporta o dado. Todo ajuste fica
registrado no catálogo, em `ajuste_tipo`.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from .tipos import cabe_no_tipo, tipo_inteiro

LINHAS_AMOSTRA = 20_000

_INTEIRO = re.compile(r"^-?\d+$")
_DECIMAL = re.compile(r"^-?\d*[.,]\d+$")


@dataclass(slots=True)
class Medicao:
    preenchidos: int = 0
    inteiros: int = 0
    decimais: int = 0
    outros: int = 0
    max_digitos: int = 0
    max_texto: int = 0
    exemplo_outro: str | None = None

    @property
    def numerica(self) -> bool:
        return self.outros == 0 and self.preenchidos > 0

    @property
    def tem_decimal(self) -> bool:
        return self.decimais > 0


def medir_arquivo(
    caminho: Path,
    delimitador: str,
    encoding: str,
    linhas: int = LINHAS_AMOSTRA,
) -> dict[str, Medicao]:
    """Mede cada coluna do arquivo. `linhas=0` percorre o arquivo inteiro."""

    with caminho.open("r", encoding=encoding, newline="") as arquivo:
        leitor = csv.reader(arquivo, delimiter=delimitador)
        cabecalho = [c.strip().lstrip("﻿") for c in next(leitor)]
        medicoes = {coluna: Medicao() for coluna in cabecalho}

        for contador, linha in enumerate(leitor):
            if linhas and contador >= linhas:
                break
            for coluna, bruto in zip(cabecalho, linha):
                valor = bruto.strip()
                if not valor:
                    continue
                medicao = medicoes[coluna]
                medicao.preenchidos += 1
                medicao.max_texto = max(medicao.max_texto, len(valor))

                if _INTEIRO.match(valor):
                    medicao.inteiros += 1
                    medicao.max_digitos = max(
                        medicao.max_digitos, len(valor.lstrip("-"))
                    )
                elif _DECIMAL.match(valor):
                    medicao.decimais += 1
                    inteira = valor.lstrip("-").split(".")[0].split(",")[0]
                    medicao.max_digitos = max(medicao.max_digitos, len(inteira))
                else:
                    medicao.outros += 1
                    if medicao.exemplo_outro is None:
                        medicao.exemplo_outro = valor[:40]

    return medicoes


def ajustar_tipo(
    tipo_declarado: str,
    tipo_original: str | None,
    medicao: Medicao,
) -> tuple[str, str | None]:
    """Devolve (tipo final, motivo do ajuste) para uma coluna já medida."""

    if medicao.preenchidos == 0:
        return tipo_declarado, None

    original = (tipo_original or "").strip().lower()

    if original == "num":
        if medicao.outros:
            return (
                "TEXT",
                f"declarada Num, mas a amostra tem valor não numérico "
                f"(ex.: {medicao.exemplo_outro!r})",
            )
        if medicao.tem_decimal:
            return (
                "NUMERIC",
                "declarada Num inteira, mas a amostra tem casas decimais",
            )
        if not cabe_no_tipo(tipo_declarado, medicao.max_digitos):
            promovido = tipo_inteiro(medicao.max_digitos)
            return (
                promovido,
                f"a amostra chega a {medicao.max_digitos} dígitos, "
                f"acima do que {tipo_declarado} comporta",
            )
        return tipo_declarado, None

    if original == "char" and tipo_declarado.startswith("VARCHAR"):
        declarado = int(tipo_declarado[len("VARCHAR(") : -1])
        if medicao.max_texto > declarado:
            return (
                "TEXT",
                f"a amostra chega a {medicao.max_texto} caracteres, "
                f"acima do Tam.={declarado} declarado",
            )

    return tipo_declarado, None
