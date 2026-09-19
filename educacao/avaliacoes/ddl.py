"""DDL das tabelas de avaliação em `raw`, a partir do catálogo.

Mesma regra do Censo: `raw` é fiel ao arquivo publicado — mesmas colunas, mesma
ordem, e **nenhuma restrição**. Chave, NOT NULL e domínio ficam para `stg`.

As tabelas do IDEB são a exceção ao "mesmas colunas": a planilha é larga por
edição, com 135 colunas, e carregá-la assim em `raw` reproduziria em banco um
formato que só existe porque é cômodo numa planilha. Em vez disso, o IDEB entra
em `raw` **já em formato longo**, uma linha por (escola, edição, medida), o que
é fiel ao conteúdo sem ser refém da apresentação. A tradução acontece na carga,
não aqui.

Uso::

    python -m educacao.avaliacoes.ddl              # imprime
    python -m educacao.avaliacoes.ddl --aplicar
"""

from __future__ import annotations

import argparse
import sys

from psycopg import sql

from ..config.database import get_connection
from ..config.logging import configure_logger
from .catalogo import CATALOGADORES, carregar

logger = configure_logger(__name__)

SCHEMA = "raw"

#: O IDEB não vira uma tabela por planilha: as seis planilhas alimentam duas
#: tabelas longas, uma por alvo (escola ou município).
IDEB_LONGO = {
    "escolas": "ideb_escola",
    "municipios": "ideb_municipio",
}

_COLUNAS_IDEB_ESCOLA = (
    ("sg_uf", "CHAR(2)", "Sigla da UF"),
    ("co_municipio", "INTEGER", "Código IBGE do município"),
    ("no_municipio", "VARCHAR(120)", "Nome do município"),
    ("co_entidade", "INTEGER", "Código INEP da escola (ID_ESCOLA na planilha)"),
    ("no_entidade", "VARCHAR(150)", "Nome da escola"),
    ("rede", "VARCHAR(20)", "Rede: Estadual, Municipal, Federal ou Privada"),
    ("etapa", "VARCHAR(16)", "anos_iniciais, anos_finais ou ensino_medio"),
    ("edicao", "SMALLINT", "Ano da edição do IDEB"),
    ("medida", "VARCHAR(24)",
     "aprovacao, indicador_rendimento, nota, ideb_observado ou ideb_projecao"),
    ("serie", "SMALLINT",
     "Série da taxa de aprovação; nula quando a coluna é o total da etapa. "
     "Vem do rótulo humano da planilha, nunca do sufixo do nome de máquina"),
    ("disciplina", "VARCHAR(24)",
     "matematica, portugues ou media_padronizada, nas colunas de nota"),
    ("valor", "NUMERIC", "Valor publicado; '-' da planilha vira NULL"),
    ("coluna_origem", "VARCHAR(40)", "Nome de máquina da coluna de origem"),
)


def colunas_ideb(alvo: str) -> tuple[tuple[str, str, str], ...]:
    if alvo == "escolas":
        return _COLUNAS_IDEB_ESCOLA
    return tuple(
        c for c in _COLUNAS_IDEB_ESCOLA if c[0] not in ("co_entidade", "no_entidade")
    )


def create_table_ideb(alvo: str) -> sql.Composed:
    definicoes = [
        sql.SQL("{} {}").format(sql.Identifier(nome), sql.SQL(tipo))
        for nome, tipo, _ in colunas_ideb(alvo)
    ]
    return sql.SQL("CREATE TABLE IF NOT EXISTS {}.{} (\n    {}\n)").format(
        sql.Identifier(SCHEMA),
        sql.Identifier(IDEB_LONGO[alvo]),
        sql.SQL(",\n    ").join(definicoes),
    )


def comentarios_ideb(alvo: str) -> list[sql.Composed]:
    tabela = sql.Identifier(SCHEMA, IDEB_LONGO[alvo])
    saida = [
        sql.SQL("COMMENT ON TABLE {} IS {}").format(
            tabela,
            sql.Literal(
                "IDEB em formato longo, uma linha por medida publicada. "
                "A planilha de origem é larga por edição; ver educacao/avaliacoes/ideb.py"
            ),
        )
    ]
    saida.extend(
        sql.SQL("COMMENT ON COLUMN {}.{} IS {}").format(
            tabela, sql.Identifier(nome), sql.Literal(descricao)
        )
        for nome, _, descricao in colunas_ideb(alvo)
        if descricao
    )
    return saida


def create_table(tabela: dict) -> sql.Composed:
    colunas = [
        sql.SQL("{} {}").format(
            sql.Identifier(v["coluna"]), sql.SQL(v["tipo_postgres"])
        )
        for v in tabela["variaveis"]
    ]
    return sql.SQL("CREATE TABLE IF NOT EXISTS {}.{} (\n    {}\n)").format(
        sql.Identifier(SCHEMA),
        sql.Identifier(tabela["tabela_raw"]),
        sql.SQL(",\n    ").join(colunas),
    )


def comentarios(tabela: dict) -> list[sql.Composed]:
    alvo = sql.Identifier(SCHEMA, tabela["tabela_raw"])
    edicoes = tabela["edicoes"]
    faixa = (
        f"{min(edicoes)}-{max(edicoes)}" if len(edicoes) > 1 else str(edicoes[0])
    )
    saida = [
        sql.SQL("COMMENT ON TABLE {} IS {}").format(
            alvo,
            sql.Literal(
                f"{tabela['fonte'].upper()} {faixa} — {tabela['total_variaveis']} "
                f"variáveis (fonte: {tabela['arquivo']})"
            ),
        )
    ]
    saida.extend(
        sql.SQL("COMMENT ON COLUMN {}.{} IS {}").format(
            alvo, sql.Identifier(v["coluna"]), sql.Literal(v["descricao"])
        )
        for v in tabela["variaveis"]
        if v["descricao"]
    )
    return saida


def comandos(fontes: list[str] | None = None) -> list[sql.Composed]:
    saida: list[sql.Composed] = []
    for fonte in CATALOGADORES:
        if fontes and fonte not in fontes:
            continue
        if fonte == "ideb":
            for alvo in IDEB_LONGO:
                saida.append(create_table_ideb(alvo))
                saida.extend(comentarios_ideb(alvo))
            continue
        for tabela in carregar(fonte)["tabelas"]:
            saida.append(create_table(tabela))
            saida.extend(comentarios(tabela))
    return saida


def aplicar(fontes: list[str] | None = None) -> None:
    with get_connection() as conexao:
        with conexao.cursor() as cursor:
            for comando in comandos(fontes):
                cursor.execute(comando)
        conexao.commit()

    with get_connection() as conexao, conexao.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = %s"
            " AND (tablename LIKE 'ideb%%' OR tablename LIKE 'saeb%%'"
            "      OR tablename LIKE 'enem%%' OR tablename LIKE 'paebes%%')"
            " ORDER BY tablename",
            (SCHEMA,),
        )
        for (nome,) in cursor.fetchall():
            logger.info("raw.%s", nome)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="DDL das avaliações em raw")
    parser.add_argument("--fonte", action="append", help="Restringe a uma fonte")
    parser.add_argument("--aplicar", action="store_true", help="Executa no banco")
    args = parser.parse_args()

    if args.aplicar:
        aplicar(args.fonte)
        return

    with get_connection() as conexao:
        for comando in comandos(args.fonte):
            print(comando.as_string(conexao) + ";")


if __name__ == "__main__":
    main()
