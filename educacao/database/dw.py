"""Carga do modelo dimensional a partir da camada stg.

Grão real: escola x ano — o grão do próprio Censo. O modelo anterior tinha um
`fato_escola.qt_registros` que era `COUNT(*)` de linhas, o que não media nada;
aqui as medidas são as que o INEP publica.

Duas decisões que os dados impuseram:

* **`qt_mat_bas` não é a soma das etapas.** As categorias do INEP se sobrepõem:
  quem está no Ensino Médio Integrado conta em `QT_MAT_MED` e em `QT_MAT_PROF`.
  No ES de 2025 a soma ingênua excede o total em 46.640 matrículas. Por isso o
  total em `fato_escola_ano` é o do INEP, sem recalcular, e `dim_etapa.exclusiva`
  marca o que pode ser somado sem dupla contagem.
* **As subpartições finas fecham** — creche+pré=infantil, AI+AF=fundamental,
  EJA fund+EJA médio=EJA, esp_cc+esp_ce=especial, conferido em 73.966 linhas
  sem divergência. São essas que viram etapa. `prof_tec+prof_nao_tec=prof`
  diverge em 189 linhas e por isso a Educação Profissional entra inteira, como
  recorte, sem subdivisão.

Uso::

    python -m educacao.database.dw --carregar
"""

from __future__ import annotations

import argparse

from psycopg import sql

from ..config.database import get_connection
from ..config.logging import configure_logger

logger = configure_logger(__name__)

#: (sk, etapa, nível, coluna em stg.matricula, ordem, particiona sem sobreposição)
ETAPAS = (
    (1, "Creche", "Educação Infantil", "qt_mat_inf_cre", 1, True),
    (2, "Pré-Escola", "Educação Infantil", "qt_mat_inf_pre", 2, True),
    (3, "Anos Iniciais", "Ensino Fundamental", "qt_mat_fund_ai", 3, True),
    (4, "Anos Finais", "Ensino Fundamental", "qt_mat_fund_af", 4, True),
    (5, "Ensino Médio", "Ensino Médio", "qt_mat_med", 5, True),
    (6, "EJA Fundamental", "EJA", "qt_mat_eja_fund", 6, True),
    (7, "EJA Médio", "EJA", "qt_mat_eja_med", 7, True),
    (8, "Educação Profissional", "Profissional", "qt_mat_prof", 8, False),
    (9, "Educação Especial", "Especial", "qt_mat_esp", 9, False),
)

#: dimensão de categoria -> (variável no catálogo, coluna de código, coluna de rótulo)
DOMINIOS = {
    "dim_dependencia": ("TP_DEPENDENCIA", "tp_dependencia", "dependencia"),
    "dim_localizacao": ("TP_LOCALIZACAO", "tp_localizacao", "localizacao"),
    "dim_situacao": ("TP_SITUACAO_FUNCIONAMENTO", "tp_situacao_funcionamento", "situacao"),
    "dim_categoria_privada": (
        "TP_CATEGORIA_ESCOLA_PRIVADA",
        "tp_categoria_escola_privada",
        "categoria_privada",
    ),
}

#: Códigos que aparecem no dado e o dicionário não documenta. Investigados um
#: a um; o que não estiver aqui entra com rótulo genérico, ficando visível em
#: vez de quebrar a carga.
CODIGOS_NAO_DOCUMENTADOS = {
    "dim_categoria_privada": {
        # Usado de 2008 a 2021 em 51.972 escolas-ano; o INEP passou a gravar
        # nulo depois disso. Cobre dois sentidos: 49.627 são escolas públicas
        # (não aplicável) e 2.345 são privadas que não informaram.
        0: "Não aplicável ou não informado",
    },
}

#: Indicadores de infraestrutura levados para o fato, por serem os que a
#: análise de rede usa com mais frequência.
INFRAESTRUTURA = (
    "in_agua_potavel",
    "in_energia_rede_publica",
    "in_esgoto_rede_publica",
    "in_internet",
    "in_biblioteca",
    "in_laboratorio_informatica",
    "in_quadra_esportes",
    "in_acessibilidade_rampas",
)

_ORDEM_LIMPEZA = (
    "fato_matricula",
    "fato_escola_ano",
    "dim_escola",
    "dim_etapa",
    "dim_categoria_privada",
    "dim_situacao",
    "dim_localizacao",
    "dim_dependencia",
    "dim_municipio",
    "dim_tempo",
)


def limpar(conexao) -> None:
    with conexao.cursor() as cursor:
        for tabela in _ORDEM_LIMPEZA:
            cursor.execute(
                sql.SQL("TRUNCATE TABLE {} CASCADE").format(
                    sql.Identifier("dw", tabela)
                )
            )
    conexao.commit()


def carregar_dimensoes(conexao) -> None:
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO dw.dim_tempo (ano, decada)
            SELECT DISTINCT nu_ano_censo, (nu_ano_censo / 10) * 10
            FROM stg.escola
            """
        )
        logger.info("dw.dim_tempo: %s anos", cursor.rowcount)

        # Município: atributos do ano mais recente em que aparece.
        cursor.execute(
            """
            INSERT INTO dw.dim_municipio (
                co_municipio, no_municipio, co_mesorregiao, no_mesorregiao,
                co_microrregiao, no_microrregiao, co_regiao_geog_imed,
                no_regiao_geog_imed)
            SELECT DISTINCT ON (co_municipio)
                   co_municipio, no_municipio, co_mesorregiao, no_mesorregiao,
                   co_microrregiao, no_microrregiao, co_regiao_geog_imed,
                   no_regiao_geog_imed
            FROM stg.escola
            WHERE co_municipio IS NOT NULL
            ORDER BY co_municipio, nu_ano_censo DESC
            """
        )
        logger.info("dw.dim_municipio: %s municípios", cursor.rowcount)

        for tabela, (variavel, col_codigo, col_rotulo) in DOMINIOS.items():
            cursor.execute(
                sql.SQL(
                    """
                    INSERT INTO {} ({}, {})
                    SELECT DISTINCT ON (codigo::smallint) codigo::smallint, rotulo
                    FROM meta.dominio
                    WHERE variavel = {} AND codigo ~ '^[0-9]+$'
                    ORDER BY codigo::smallint, ano DESC
                    """
                ).format(
                    sql.Identifier("dw", tabela),
                    sql.Identifier(col_codigo),
                    sql.Identifier(col_rotulo),
                    sql.Literal(variavel),
                )
            )
            documentados = cursor.rowcount

            # Códigos presentes no dado que o dicionário não descreve.
            cursor.execute(
                sql.SQL(
                    "SELECT DISTINCT e.{coluna} FROM stg.escola e"
                    " LEFT JOIN {dim} d ON d.{coluna} = e.{coluna}"
                    " WHERE e.{coluna} IS NOT NULL AND d.{coluna} IS NULL"
                    " ORDER BY 1"
                ).format(
                    coluna=sql.Identifier(col_codigo),
                    dim=sql.Identifier("dw", tabela),
                )
            )
            faltantes = [linha[0] for linha in cursor.fetchall()]
            rotulos = CODIGOS_NAO_DOCUMENTADOS.get(tabela, {})

            for codigo in faltantes:
                cursor.execute(
                    sql.SQL("INSERT INTO {} ({}, {}) VALUES (%s, %s)").format(
                        sql.Identifier("dw", tabela),
                        sql.Identifier(col_codigo),
                        sql.Identifier(col_rotulo),
                    ),
                    (
                        codigo,
                        rotulos.get(
                            codigo, f"Código {codigo} sem descrição no dicionário"
                        ),
                    ),
                )
                logger.warning(
                    "dw.%s: código %s presente no dado e ausente do dicionário",
                    tabela,
                    codigo,
                )

            logger.info(
                "dw.%s: %s categorias (%s do dicionário, %s só no dado)",
                tabela,
                documentados + len(faltantes),
                documentados,
                len(faltantes),
            )

        cursor.executemany(
            "INSERT INTO dw.dim_etapa"
            " (sk_etapa, etapa, nivel, coluna_origem, ordem, exclusiva)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            ETAPAS,
        )
        logger.info("dw.dim_etapa: %s etapas", len(ETAPAS))

        # Escola: identidade, com nome/município/geo do ano mais recente.
        cursor.execute(
            """
            INSERT INTO dw.dim_escola (
                co_entidade, no_entidade, co_municipio,
                primeiro_ano, ultimo_ano, anos_no_censo, latitude, longitude)
            WITH recente AS (
                SELECT DISTINCT ON (co_entidade)
                       co_entidade, no_entidade, co_municipio
                FROM stg.escola
                ORDER BY co_entidade, nu_ano_censo DESC
            ),
            periodo AS (
                SELECT co_entidade,
                       min(nu_ano_censo) AS primeiro_ano,
                       max(nu_ano_censo) AS ultimo_ano,
                       count(*)          AS anos_no_censo
                FROM stg.escola GROUP BY co_entidade
            ),
            geo AS (
                SELECT DISTINCT ON (co_entidade) co_entidade, latitude, longitude
                FROM stg.escola
                WHERE latitude IS NOT NULL
                ORDER BY co_entidade, nu_ano_censo DESC
            )
            SELECT r.co_entidade, r.no_entidade, r.co_municipio,
                   p.primeiro_ano, p.ultimo_ano, p.anos_no_censo,
                   g.latitude, g.longitude
            FROM recente r
            JOIN periodo p USING (co_entidade)
            LEFT JOIN geo g USING (co_entidade)
            """
        )
        logger.info("dw.dim_escola: %s escolas", cursor.rowcount)

    conexao.commit()


def carregar_fatos(conexao) -> None:
    colunas_infra = sql.SQL(", ").join(
        sql.Identifier(coluna) for coluna in INFRAESTRUTURA
    )
    origem_infra = sql.SQL(", ").join(
        sql.SQL("e.{}").format(sql.Identifier(coluna)) for coluna in INFRAESTRUTURA
    )

    with conexao.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                """
                INSERT INTO dw.fato_escola_ano (
                    co_entidade, ano, co_municipio, tp_dependencia, tp_localizacao,
                    tp_situacao_funcionamento, tp_categoria_escola_privada,
                    no_entidade, no_bairro,
                    qt_mat_bas, qt_mat_esp, qt_doc_bas, qt_tur_bas, {infra})
                SELECT e.co_entidade, e.nu_ano_censo, e.co_municipio,
                       e.tp_dependencia, e.tp_localizacao,
                       e.tp_situacao_funcionamento, e.tp_categoria_escola_privada,
                       e.no_entidade, e.no_bairro,
                       m.qt_mat_bas, m.qt_mat_esp, d.qt_doc_bas, t.qt_tur_bas,
                       {origem}
                FROM stg.escola e
                LEFT JOIN stg.matricula m
                       ON m.co_entidade = e.co_entidade
                      AND m.nu_ano_censo = e.nu_ano_censo
                LEFT JOIN stg.docente d
                       ON d.co_entidade = e.co_entidade
                      AND d.nu_ano_censo = e.nu_ano_censo
                LEFT JOIN stg.turma t
                       ON t.co_entidade = e.co_entidade
                      AND t.nu_ano_censo = e.nu_ano_censo
                """
            ).format(infra=colunas_infra, origem=origem_infra)
        )
        logger.info("dw.fato_escola_ano: %s linhas", cursor.rowcount)

        # Matrícula em formato longo. Só entram etapas com matrícula: ausência
        # de linha significa nenhuma matrícula naquela etapa.
        partes = [
            sql.SQL(
                "SELECT co_entidade, nu_ano_censo, {sk}, {coluna}"
                " FROM stg.matricula WHERE coalesce({coluna}, 0) > 0"
            ).format(sk=sql.Literal(sk), coluna=sql.Identifier(coluna))
            for sk, _, _, coluna, _, _ in ETAPAS
        ]
        cursor.execute(
            sql.SQL(
                "INSERT INTO dw.fato_matricula"
                " (co_entidade, ano, sk_etapa, qt_matricula) {corpo}"
            ).format(corpo=sql.SQL(" UNION ALL ").join(partes))
        )
        logger.info("dw.fato_matricula: %s linhas", cursor.rowcount)

    conexao.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Carrega o modelo dimensional a partir de stg"
    )
    parser.add_argument(
        "--carregar", action="store_true", help="Executa a carga (limpa antes)"
    )
    args = parser.parse_args()

    if not args.carregar:
        parser.print_help()
        return

    with get_connection() as conexao:
        limpar(conexao)
        carregar_dimensoes(conexao)
        carregar_fatos(conexao)
    logger.info("dw carregado")


if __name__ == "__main__":
    main()
