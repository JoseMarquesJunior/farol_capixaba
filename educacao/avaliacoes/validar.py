"""Confere o catálogo das avaliações contra os arquivos publicados.

Mesma garantia do validador do Censo: o catálogo não pode se descolar da fonte.
Para cada tabela, a lista de variáveis do JSON tem que ser idêntica, **e na
mesma ordem**, ao cabeçalho do arquivo. Se o INEP ou a SEDU republicarem algo,
ou se alguém editar o catálogo à mão, a divergência aparece aqui.

O IDEB é conferido de outro jeito, porque não tem cabeçalho de CSV: valem a
linha de nomes de máquina da planilha e a checagem de que as séries lidas são
exatamente as que a etapa deve ter (`ideb.verificar_series`).

Uso::

    python -m educacao.avaliacoes.validar
    python -m educacao.avaliacoes.validar --fonte saeb
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from ..config.settings import AVALIACOES_DIR
from . import ideb as mod_ideb
from .catalogo import CATALOGADORES, cabecalho_csv, carregar

TIPOS_VALIDOS = ("SMALLINT", "INTEGER", "BIGINT", "NUMERIC", "VARCHAR", "TEXT")
RAIZ = AVALIACOES_DIR.parent.parent


@dataclass(slots=True)
class Resultado:
    fonte: str
    tabela: str
    ok: bool
    detalhe: str
    colunas: int = 0


def _validar_ideb(tabela: dict) -> Resultado:
    caminho = RAIZ / tabela["arquivo"]
    if not caminho.exists():
        return Resultado("ideb", tabela["nome"], False, f"arquivo ausente: {caminho}")

    problemas = mod_ideb.verificar_series(caminho)
    if problemas:
        return Resultado("ideb", tabela["nome"], False, "; ".join(problemas))

    workbook, worksheet = mod_ideb.abrir_planilha(caminho)
    try:
        cabecalho = mod_ideb.localizar_cabecalho(worksheet)
    finally:
        workbook.close()

    esperado = len(tabela["variaveis"])
    encontrado = len(cabecalho.identificacao) + len(cabecalho.medidas)
    if esperado != encontrado:
        return Resultado(
            "ideb",
            tabela["nome"],
            False,
            f"catálogo tem {esperado} colunas, planilha tem {encontrado}",
        )

    edicoes = tabela["edicoes"]
    return Resultado(
        "ideb",
        tabela["nome"],
        True,
        f"{encontrado} colunas, {len(edicoes)} edições {min(edicoes)}-{max(edicoes)}",
        encontrado,
    )


def _validar_csv(fonte: str, tabela: dict) -> Resultado:
    caminho = RAIZ / tabela["arquivo"]
    if not caminho.exists():
        return Resultado(fonte, tabela["nome"], False, f"arquivo ausente: {caminho}")

    esperado = [v["nome"] for v in tabela["variaveis"]]
    encontrado = cabecalho_csv(caminho, tabela["delimitador"], tabela["encoding"])

    if esperado != encontrado:
        if set(esperado) == set(encontrado):
            return Resultado(fonte, tabela["nome"], False, "mesmas colunas, ordem diferente")
        so_catalogo = [c for c in esperado if c not in set(encontrado)]
        so_arquivo = [c for c in encontrado if c not in set(esperado)]
        return Resultado(
            fonte,
            tabela["nome"],
            False,
            f"só no catálogo={so_catalogo[:3]} só no arquivo={so_arquivo[:3]}",
        )

    sem_tipo = [
        v["nome"]
        for v in tabela["variaveis"]
        if not v["tipo_postgres"].upper().startswith(TIPOS_VALIDOS)
    ]
    if sem_tipo:
        return Resultado(fonte, tabela["nome"], False, f"tipo inesperado em {sem_tipo[:3]}")

    com_dominio = sum(1 for v in tabela["variaveis"] if v["dominio"])
    detalhe = f"{len(encontrado)} colunas"
    if com_dominio:
        detalhe += f", {com_dominio} com domínio"
    return Resultado(fonte, tabela["nome"], True, detalhe, len(encontrado))


def validar_fonte(fonte: str) -> list[Resultado]:
    try:
        catalogo = carregar(fonte)
    except FileNotFoundError as erro:
        return [Resultado(fonte, "-", False, str(erro))]

    validador = _validar_ideb if fonte == "ideb" else None
    return [
        validador(t) if validador else _validar_csv(fonte, t)
        for t in catalogo["tabelas"]
    ]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Valida o catálogo das avaliações")
    parser.add_argument("--fonte", action="append", help="Valida apenas esta fonte")
    args = parser.parse_args()

    fontes = args.fonte or list(CATALOGADORES)
    resultados: list[Resultado] = []
    for fonte in fontes:
        resultados.extend(validar_fonte(fonte))

    for r in resultados:
        marca = "ok   " if r.ok else "FALHA"
        print(f"  {marca} {r.fonte:<7} {r.tabela:<36} {r.detalhe}")

    falhas = [r for r in resultados if not r.ok]
    colunas = sum(r.colunas for r in resultados)
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
