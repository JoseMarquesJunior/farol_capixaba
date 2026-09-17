"""Confere o catálogo gravado contra os arquivos de microdados.

Esta é a garantia de que o catálogo não se descola da fonte: para cada ano e
cada tabela, a lista de variáveis do JSON tem que ser *idêntica*, na ordem, ao
cabeçalho do CSV correspondente. Se o INEP republicar um arquivo ou alguém
editar o catálogo à mão, a divergência aparece aqui.

Uso::

    python -m educacao.metadata.validar
    python -m educacao.metadata.validar --ano 2025
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from .catalogo import DIRETORIO_CATALOGO, RAIZ_PROJETO, ler_cabecalho
from .fontes import ANOS

TIPOS_VALIDOS = ("SMALLINT", "INTEGER", "BIGINT", "NUMERIC", "VARCHAR", "TEXT")


@dataclass(slots=True)
class Resultado:
    ano: int
    tabela: str
    ok: bool
    detalhe: str


def validar_tabela(ano: int, tabela: dict) -> Resultado:
    caminho = RAIZ_PROJETO / tabela["arquivo"]
    if not caminho.exists():
        return Resultado(ano, tabela["nome"], False, f"arquivo ausente: {caminho}")

    esperado = [variavel["nome"] for variavel in tabela["variaveis"]]
    encontrado = ler_cabecalho(
        caminho, tabela["delimitador"], tabela["encoding"]
    )

    if esperado != encontrado:
        if set(esperado) == set(encontrado):
            return Resultado(
                ano, tabela["nome"], False, "mesmas colunas, ordem diferente"
            )
        so_catalogo = [c for c in esperado if c not in set(encontrado)]
        so_arquivo = [c for c in encontrado if c not in set(esperado)]
        return Resultado(
            ano,
            tabela["nome"],
            False,
            f"só no catálogo={so_catalogo[:3]} só no arquivo={so_arquivo[:3]}",
        )

    sem_tipo = [
        variavel["nome"]
        for variavel in tabela["variaveis"]
        if not variavel["tipo_postgres"].upper().startswith(TIPOS_VALIDOS)
    ]
    if sem_tipo:
        return Resultado(
            ano, tabela["nome"], False, f"tipo inesperado em {sem_tipo[:3]}"
        )

    ajustes = sum(1 for v in tabela["variaveis"] if v["ajuste_tipo"])
    detalhe = f"{len(encontrado)} colunas"
    if ajustes:
        detalhe += f", {ajustes} com tipo ajustado"
    return Resultado(ano, tabela["nome"], True, detalhe)


def validar_ano(ano: int, diretorio: Path = DIRETORIO_CATALOGO) -> list[Resultado]:
    arquivo = diretorio / f"{ano}.json"
    if not arquivo.exists():
        return [Resultado(ano, "-", False, f"catálogo não gerado ({arquivo.name})")]

    catalogo = json.loads(arquivo.read_text(encoding="utf-8"))
    return [validar_tabela(ano, tabela) for tabela in catalogo["tabelas"]]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida o catálogo de metadados contra os microdados"
    )
    parser.add_argument("--ano", type=int, help="Valida apenas este ano")
    args = parser.parse_args()

    anos = [args.ano] if args.ano else list(ANOS)
    resultados: list[Resultado] = []
    for ano in anos:
        resultados.extend(validar_ano(ano))

    for resultado in resultados:
        marca = "ok  " if resultado.ok else "FALHA"
        print(f"  {marca} {resultado.ano} {resultado.tabela:14} {resultado.detalhe}")

    falhas = [r for r in resultados if not r.ok]
    colunas = sum(
        int(r.detalhe.split()[0]) for r in resultados if r.ok and r.detalhe[0].isdigit()
    )
    print()
    print(
        f"{len(resultados) - len(falhas)}/{len(resultados)} tabelas conferem "
        f"({colunas:,} colunas verificadas)"
    )
    if falhas:
        print(f"{len(falhas)} FALHA(S)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
