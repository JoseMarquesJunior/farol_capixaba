"""Carga do catálogo de metadados para o schema `meta`.

Materializa `educacao/metadata/catalog/*.json` em tabelas, para que o layout de
cada ano possa ser consultado em SQL ao lado dos próprios dados — por exemplo,
descobrir em que anos uma variável existe, ou listar o domínio de um `TP_`
sem sair do banco.

A carga é idempotente: as linhas do ano são apagadas antes de reinserir.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..config.database import get_connection
from ..config.logging import configure_logger
from ..metadata.catalogo import DIRETORIO_CATALOGO
from ..metadata.fontes import ANOS

logger = configure_logger(__name__)


def carregar_ano(conexao, ano: int, diretorio: Path = DIRETORIO_CATALOGO) -> int:
    arquivo = diretorio / f"{ano}.json"
    if not arquivo.exists():
        raise FileNotFoundError(f"Catálogo de {ano} não encontrado em {diretorio}")

    catalogo = json.loads(arquivo.read_text(encoding="utf-8"))
    tabelas, variaveis, dominios = [], [], []

    for tabela in catalogo["tabelas"]:
        tabelas.append(
            (
                ano,
                tabela["nome"],
                tabela["tabela_raw"],
                tabela["arquivo"],
                tabela["aba"],
                tabela["delimitador"],
                tabela["encoding"],
                tabela["total_variaveis"],
            )
        )
        for variavel in tabela["variaveis"]:
            variaveis.append(
                (
                    ano,
                    tabela["nome"],
                    variavel["nome"],
                    variavel["coluna"],
                    variavel["ordem"],
                    variavel["descricao"],
                    variavel["tipo_original"],
                    variavel["tamanho"],
                    variavel["tipo_postgres"],
                    variavel["ajuste_tipo"],
                    variavel["nota"],
                )
            )
            for ordem, valor in enumerate(variavel["dominio"]):
                dominios.append(
                    (
                        ano,
                        tabela["nome"],
                        variavel["nome"],
                        ordem,
                        valor["codigo"],
                        valor["rotulo"],
                    )
                )

    with conexao.cursor() as cursor:
        # ON DELETE CASCADE leva variavel e dominio junto.
        cursor.execute("DELETE FROM meta.tabela WHERE ano = %s", (ano,))
        cursor.executemany(
            "INSERT INTO meta.tabela (ano, tabela, tabela_raw, arquivo, aba,"
            " delimitador, encoding, total_variaveis)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            tabelas,
        )
        cursor.executemany(
            "INSERT INTO meta.variavel (ano, tabela, nome, coluna, ordem,"
            " descricao, tipo_original, tamanho, tipo_postgres, ajuste_tipo, nota)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            variaveis,
        )
        cursor.executemany(
            "INSERT INTO meta.dominio (ano, tabela, variavel, ordem, codigo, rotulo)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            dominios,
        )

    logger.info(
        "meta %s: %s tabelas, %s variáveis, %s valores de domínio",
        ano,
        len(tabelas),
        len(variaveis),
        len(dominios),
    )
    return len(variaveis)


def carregar_canonico(conexao, diretorio: Path = DIRETORIO_CATALOGO) -> int:
    arquivo = diretorio / "canonical.json"
    if not arquivo.exists():
        raise FileNotFoundError(
            "canonical.json não gerado. Rode `python -m educacao.metadata.canonico`."
        )

    modelo = json.loads(arquivo.read_text(encoding="utf-8"))
    canonicas, presencas = [], []

    for variavel in modelo["variaveis"]:
        canonicas.append(
            (
                variavel["nome"],
                variavel["coluna"],
                variavel["descricao"],
                variavel["tabela_referencia"],
                variavel["descontinuada"],
                variavel["primeiro_ano"],
                variavel["ultimo_ano"],
                variavel["tipo_postgres"],
                variavel["tipos_por_ano"] is not None,
            )
        )
        presencas.extend((variavel["nome"], ano) for ano in variavel["anos_presentes"])

    with conexao.cursor() as cursor:
        cursor.execute("DELETE FROM meta.variavel_canonica")
        cursor.executemany(
            "INSERT INTO meta.variavel_canonica (nome, coluna, descricao,"
            " tabela_referencia, descontinuada, primeiro_ano, ultimo_ano,"
            " tipo_postgres, tipo_varia)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            canonicas,
        )
        cursor.executemany(
            "INSERT INTO meta.presenca (nome, ano) VALUES (%s, %s)", presencas
        )

    logger.info(
        "meta canônico: %s variáveis (%s descontinuadas, %s com tipo variável)",
        len(canonicas),
        modelo["descontinuadas"],
        modelo["com_tipo_variavel"],
    )
    return len(canonicas)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Carrega o catálogo de metadados no schema meta"
    )
    parser.add_argument("--ano", type=int, help="Apenas este ano")
    args = parser.parse_args()

    anos = [args.ano] if args.ano else list(ANOS)
    with get_connection() as conexao:
        for ano in anos:
            carregar_ano(conexao, ano)
        if not args.ano:
            carregar_canonico(conexao)
        conexao.commit()


if __name__ == "__main__":
    main()
