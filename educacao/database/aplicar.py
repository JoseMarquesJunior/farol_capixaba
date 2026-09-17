"""Aplica a fundação do banco: schemas, catálogo `meta` e controle `etl`.

Uso::

    python -m educacao.database.aplicar                  # schemas + meta
    python -m educacao.database.aplicar --limpar-legado  # remove o que sobrou
                                                         # da tentativa anterior
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..config.database import get_connection
from ..config.logging import configure_logger
from ..metadata.fontes import ANOS
from .meta import carregar_ano, carregar_canonico

logger = configure_logger(__name__)

DIRETORIO_SQL = Path(__file__).resolve().parent / "sql"

#: Objetos da tentativa anterior, que não seguem a convenção atual.
#: São removidos apenas se estiverem vazios — ver `limpar_legado`.
SCHEMAS_LEGADOS = ("staging", "feature")
TABELAS_LEGADAS = (
    ("raw", "escolas_1995"),
    ("raw", "escolas_2025"),
    ("raw", "docentes_2025"),
    ("dw", "dim_escola"),
    ("dw", "dim_docente"),
    ("dw", "fato_escola"),
    ("dw", "fato_docente"),
    ("dw", "fato_matricula"),
)


def executar_scripts(conexao) -> None:
    for caminho in sorted(DIRETORIO_SQL.glob("*.sql")):
        with conexao.cursor() as cursor:
            cursor.execute(caminho.read_text(encoding="utf-8"))
        conexao.commit()
        logger.info("aplicado: %s", caminho.name)


def _contar(cursor, schema: str, tabela: str) -> int | None:
    cursor.execute("SELECT to_regclass(%s)", (f"{schema}.{tabela}",))
    if cursor.fetchone()[0] is None:
        return None
    cursor.execute(f'SELECT count(*) FROM "{schema}"."{tabela}"')
    return cursor.fetchone()[0]


def limpar_legado(conexao) -> None:
    """Remove objetos da tentativa anterior, recusando-se a apagar dado."""

    with conexao.cursor() as cursor:
        ocupadas: list[str] = []
        alvos: list[tuple[str, str]] = list(TABELAS_LEGADAS)

        for schema in SCHEMAS_LEGADOS:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_schema = %s AND table_type = 'BASE TABLE'",
                (schema,),
            )
            alvos.extend((schema, linha[0]) for linha in cursor.fetchall())

        for schema, tabela in alvos:
            linhas = _contar(cursor, schema, tabela)
            if linhas:
                ocupadas.append(f"{schema}.{tabela} ({linhas} linhas)")

        if ocupadas:
            raise RuntimeError(
                "Há dado nos objetos legados; nada foi removido: "
                + ", ".join(ocupadas)
            )

        removidos = 0
        for schema, tabela in TABELAS_LEGADAS:
            if _contar(cursor, schema, tabela) is not None:
                cursor.execute(f'DROP TABLE "{schema}"."{tabela}" CASCADE')
                logger.info("removida tabela legada %s.%s (vazia)", schema, tabela)
                removidos += 1

        for schema in SCHEMAS_LEGADOS:
            cursor.execute("SELECT to_regnamespace(%s)", (schema,))
            if cursor.fetchone()[0] is not None:
                cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
                logger.info("removido schema legado %s (vazio)", schema)
                removidos += 1

    conexao.commit()
    if not removidos:
        logger.info("nenhum objeto legado encontrado")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cria schemas, catálogo meta e controle etl"
    )
    parser.add_argument(
        "--limpar-legado",
        action="store_true",
        help="Remove objetos vazios da tentativa anterior antes de aplicar",
    )
    parser.add_argument(
        "--sem-meta",
        action="store_true",
        help="Só cria as estruturas, sem carregar o catálogo",
    )
    args = parser.parse_args()

    with get_connection() as conexao:
        if args.limpar_legado:
            limpar_legado(conexao)

        executar_scripts(conexao)

        if not args.sem_meta:
            for ano in ANOS:
                carregar_ano(conexao, ano)
            carregar_canonico(conexao)
            conexao.commit()

    logger.info("fundação aplicada")


if __name__ == "__main__":
    main()
