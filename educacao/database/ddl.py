"""Geração do DDL de `raw` a partir do catálogo de metadados.

As tabelas de `raw` são fiéis ao arquivo publicado: mesmas colunas, mesma
ordem, tipos vindos do catálogo (já conferidos contra os dados) e **nenhuma
restrição**. Chave primária, NOT NULL e checagem de domínio ficam para `stg` —
em `raw`, uma restrição só serviria para rejeitar dado real do INEP e travar a
carga.

Uso::

    python -m educacao.database.ddl --ano 2025          # imprime o DDL
    python -m educacao.database.ddl --ano 2025 --aplicar
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from psycopg import sql

from ..config.database import get_connection
from ..config.logging import configure_logger
from ..metadata.catalogo import DIRETORIO_CATALOGO
from ..metadata.fontes import ANOS

logger = configure_logger(__name__)

SCHEMA_RAW = "raw"


def carregar_catalogo(ano: int, diretorio: Path = DIRETORIO_CATALOGO) -> dict:
    arquivo = diretorio / f"{ano}.json"
    if not arquivo.exists():
        raise FileNotFoundError(
            f"Catálogo de {ano} não gerado. Rode `python -m educacao.metadata.catalogo`."
        )
    return json.loads(arquivo.read_text(encoding="utf-8"))


def create_table(tabela: dict, schema: str = SCHEMA_RAW) -> sql.Composed:
    colunas = [
        sql.SQL("{} {}").format(
            sql.Identifier(variavel["coluna"]),
            sql.SQL(variavel["tipo_postgres"]),
        )
        for variavel in tabela["variaveis"]
    ]
    return sql.SQL("CREATE TABLE IF NOT EXISTS {}.{} (\n    {}\n)").format(
        sql.Identifier(schema),
        sql.Identifier(tabela["tabela_raw"]),
        sql.SQL(",\n    ").join(colunas),
    )


def comentarios(tabela: dict, ano: int, schema: str = SCHEMA_RAW) -> list[sql.Composed]:
    """COMMENT ON para tabela e colunas, deixando o banco autoexplicativo."""

    alvo = sql.Identifier(schema, tabela["tabela_raw"])
    saida = [
        sql.SQL("COMMENT ON TABLE {} IS {}").format(
            alvo,
            sql.Literal(
                f"Censo Escolar {ano} - {tabela['nome']} "
                f"({tabela['total_variaveis']} variáveis, fonte: {tabela['arquivo']})"
            ),
        )
    ]
    for variavel in tabela["variaveis"]:
        if not variavel["descricao"]:
            continue
        texto = variavel["descricao"]
        if variavel["ajuste_tipo"]:
            texto = f"{texto} [tipo ajustado: {variavel['ajuste_tipo']}]"
        saida.append(
            sql.SQL("COMMENT ON COLUMN {}.{} IS {}").format(
                alvo, sql.Identifier(variavel["coluna"]), sql.Literal(texto)
            )
        )
    return saida


def ddl_do_ano(ano: int, com_comentarios: bool = True) -> list[sql.Composed]:
    catalogo = carregar_catalogo(ano)
    comandos: list[sql.Composed] = []
    for tabela in catalogo["tabelas"]:
        comandos.append(create_table(tabela))
        if com_comentarios:
            comandos.extend(comentarios(tabela, ano))
    return comandos


def aplicar(anos: list[int], com_comentarios: bool = True) -> None:
    with get_connection() as conexao:
        for ano in anos:
            catalogo = carregar_catalogo(ano)
            with conexao.cursor() as cursor:
                for tabela in catalogo["tabelas"]:
                    cursor.execute(create_table(tabela))
                    if com_comentarios:
                        for comando in comentarios(tabela, ano):
                            cursor.execute(comando)
                    logger.info(
                        "raw.%s criada (%s colunas)",
                        tabela["tabela_raw"],
                        tabela["total_variaveis"],
                    )
            conexao.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera (ou aplica) o DDL das tabelas de raw"
    )
    parser.add_argument("--ano", type=int, help="Apenas este ano")
    parser.add_argument(
        "--aplicar", action="store_true", help="Executa no banco em vez de imprimir"
    )
    parser.add_argument(
        "--sem-comentarios",
        action="store_true",
        help="Não gera COMMENT ON para tabela e colunas",
    )
    args = parser.parse_args()

    anos = [args.ano] if args.ano else list(ANOS)

    if args.aplicar:
        aplicar(anos, com_comentarios=not args.sem_comentarios)
        return

    with get_connection() as conexao:
        for ano in anos:
            for comando in ddl_do_ano(ano, com_comentarios=not args.sem_comentarios):
                print(comando.as_string(conexao) + ";")


if __name__ == "__main__":
    main()
