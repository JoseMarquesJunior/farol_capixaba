"""Transformações de `raw` para `stg` nas quatro fontes de avaliação.

Três coisas acontecem aqui:

* **repivotagem** — o IDEB entra em `raw` longo (uma linha por medida) e sai
  largo por medida, que é o formato em que se consulta;
* **tradução da máscara** — o `ID_MUNICIPIO` do SAEB vira código IBGE
  (`saeb.py`), e as escolas mascaradas são agregadas por município, ponderadas
  pelo número de presentes;
* **conversão de tipo** — o PAEBES usa vírgula decimal, que não entra em
  NUMERIC pelo COPY; as colunas chegam em `raw` como texto e viram número aqui,
  do mesmo jeito que as datas SAS do Censo.

Idempotente: cada tabela é reescrita por inteiro a cada execução.

Uso::

    python -m educacao.avaliacoes.stg --aplicar    # cria as tabelas
    python -m educacao.avaliacoes.stg --carregar
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from psycopg import sql

from ..config.database import get_connection
from ..config.logging import configure_logger
from .saeb import construir_mascara, mapear_etapas

logger = configure_logger(__name__)

SCHEMA = "stg"
DIRETORIO_SQL = Path(__file__).resolve().parent / "sql"

EDICOES_SAEB = (2015, 2017, 2019, 2021, 2023)

#: Colunas do PAEBES que chegam como texto por causa da vírgula decimal.
_NUMERO_PAEBES = (
    "nu_acerto",
    "nu_total",
    "tx_acerto",
    "vl_proficiencia",
    "vl_proficiencia_erro",
    "vl_ise",
)


def _numero(coluna: str) -> sql.Composed:
    """Texto com vírgula decimal -> NUMERIC, tolerando vazio."""

    return sql.SQL(
        "nullif(replace(btrim({}), ',', '.'), '')::numeric"
    ).format(sql.Identifier(coluna))


# -------------------------------------------------------------------- IDEB

_MEDIDAS_IDEB = (
    ("aprovacao", "medida = 'aprovacao' AND serie IS NULL"),
    ("indicador_rendimento", "medida = 'indicador_rendimento'"),
    ("nota_matematica", "medida = 'nota' AND disciplina = 'matematica'"),
    ("nota_portugues", "medida = 'nota' AND disciplina = 'portugues'"),
    ("nota_media", "medida = 'nota' AND disciplina = 'media_padronizada'"),
    ("ideb_observado", "medida = 'ideb_observado'"),
    ("ideb_projecao", "medida = 'ideb_projecao'"),
)


def _pivot_ideb(
    destino: str,
    origem: str,
    chave: list[str],
    chave_destino: list[str],
    extras: list[str],
) -> sql.Composed:
    """Repivota o IDEB longo para largo por medida.

    `chave` são as colunas em `raw` e `chave_destino` os nomes em `stg`: a
    coluna que em `raw` se chama `edicao` vira `ano` na `stg`, para ficar igual
    ao resto do modelo.
    """

    colunas = chave_destino + extras + [nome for nome, _ in _MEDIDAS_IDEB]
    selecoes = [sql.Identifier(c) for c in chave]
    selecoes += [sql.SQL("max({})").format(sql.Identifier(c)) for c in extras]
    selecoes += [
        sql.SQL("max(valor) FILTER (WHERE {})").format(sql.SQL(condicao))
        for _, condicao in _MEDIDAS_IDEB
    ]
    return sql.SQL(
        "INSERT INTO {destino} ({colunas})\nSELECT {selecoes}\n"
        "FROM {origem}\nGROUP BY {chave}"
    ).format(
        destino=sql.Identifier(SCHEMA, destino),
        colunas=sql.SQL(", ").join(sql.Identifier(c) for c in colunas),
        selecoes=sql.SQL(",\n       ").join(selecoes),
        origem=sql.Identifier("raw", origem),
        chave=sql.SQL(", ").join(sql.Identifier(c) for c in chave),
    )


def carregar_ideb(conexao) -> None:
    passos = [
        (
            "ideb_escola",
            _pivot_ideb(
                "ideb_escola",
                "ideb_escola",
                ["co_entidade", "edicao", "etapa"],
                ["co_entidade", "ano", "etapa"],
                ["co_municipio", "no_entidade", "rede"],
            ),
        ),
        (
            "ideb_municipio",
            _pivot_ideb(
                "ideb_municipio",
                "ideb_municipio",
                ["co_municipio", "edicao", "etapa", "rede"],
                ["co_municipio", "ano", "etapa", "rede"],
                ["no_municipio"],
            ),
        ),
        (
            "ideb_aprovacao_serie",
            sql.SQL(
                "INSERT INTO {destino} (co_entidade, ano, etapa, serie, aprovacao)\n"
                "SELECT co_entidade, edicao, etapa, serie, max(valor)\n"
                "FROM {origem} WHERE medida = 'aprovacao' AND serie IS NOT NULL\n"
                "GROUP BY co_entidade, edicao, etapa, serie"
            ).format(
                destino=sql.Identifier(SCHEMA, "ideb_aprovacao_serie"),
                origem=sql.Identifier("raw", "ideb_escola"),
            ),
        ),
    ]
    # O pivot nomeia a coluna de ano como `edicao` na origem; o destino usa `ano`.
    for tabela, comando in passos:
        with conexao.cursor() as cursor:
            cursor.execute(
                sql.SQL("TRUNCATE TABLE {}").format(sql.Identifier(SCHEMA, tabela))
            )
            cursor.execute(comando)
            gravadas = cursor.rowcount
        conexao.commit()
        logger.info("stg.%-24s %8s linhas", tabela, f"{gravadas:,}")


# -------------------------------------------------------------------- ENEM


#: (coluna em stg, coluna em raw, tipo). O dicionário do ENEM por Escola não
#: declara tipo nenhum, então tudo entra em `raw` como texto e é convertido
#: aqui, com o tipo decidido pelo que a coluna significa.
_CAMPOS_ENEM = (
    ("co_entidade", "co_escola_educacenso", "integer"),
    ("ano", "nu_ano", "smallint"),
    ("co_municipio", "co_municipio_escola", "integer"),
    ("no_entidade", "no_escola_educacenso", None),
    ("tp_dependencia", "tp_dependencia_adm_escola", "smallint"),
    ("tp_localizacao", "tp_localizacao_escola", "smallint"),
    ("matriculas", "nu_matriculas", "integer"),
    ("participantes", "nu_participantes", "integer"),
    ("taxa_participacao", "nu_taxa_participacao", "numeric"),
    ("media_cn", "nu_media_cn", "numeric"),
    ("media_ch", "nu_media_ch", "numeric"),
    ("media_lp", "nu_media_lp", "numeric"),
    ("media_mt", "nu_media_mt", "numeric"),
    ("media_red", "nu_media_red", "numeric"),
    ("media_obj", "nu_media_obj", "numeric"),
    ("media_total", "nu_media_tot", "numeric"),
    # INSE aqui é faixa ("Grupo 1".."Grupo 6"), não índice numérico.
    ("inse", "inse", None),
    ("pc_formacao_docente", "pc_formacao_docente", "numeric"),
    ("taxa_permanencia", "nu_taxa_permanencia", "numeric"),
    ("taxa_aprovacao", "nu_taxa_aprovacao", "numeric"),
    ("taxa_reprovacao", "nu_taxa_reprovacao", "numeric"),
    ("taxa_abandono", "nu_taxa_abandono", "numeric"),
    ("porte_escola", "porte_escola", None),
)


def carregar_enem(conexao) -> None:
    selecoes = [
        sql.Identifier(origem)
        if tipo is None
        else sql.SQL("nullif(btrim({}), '')::{}").format(
            sql.Identifier(origem), sql.SQL(tipo)
        )
        for _, origem, tipo in _CAMPOS_ENEM
    ]
    comando = sql.SQL(
        "INSERT INTO {destino} ({colunas})\nSELECT {selecoes}\nFROM {origem}"
    ).format(
        destino=sql.Identifier(SCHEMA, "enem_escola"),
        colunas=sql.SQL(", ").join(sql.Identifier(d) for d, _, _ in _CAMPOS_ENEM),
        selecoes=sql.SQL(",\n       ").join(selecoes),
        origem=sql.Identifier("raw", "enem_por_escola"),
    )
    with conexao.cursor() as cursor:
        cursor.execute(
            sql.SQL("TRUNCATE TABLE {}").format(sql.Identifier(SCHEMA, "enem_escola"))
        )
        cursor.execute(comando)
        gravadas = cursor.rowcount
    conexao.commit()
    logger.info("stg.%-24s %8s linhas", "enem_escola", f"{gravadas:,}")


# -------------------------------------------------------------------- SAEB


def _colunas_de(conexao, tabela: str) -> list[str]:
    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = 'raw' AND table_name = %s"
            " ORDER BY ordinal_position",
            (tabela,),
        )
        return [linha[0] for linha in cursor.fetchall()]


def _media_ponderada(coluna: str, peso: str) -> sql.Composed:
    """Média ponderada que ignora a escola sem aquela medida."""

    return sql.SQL(
        "sum({col} * {peso}) FILTER (WHERE {col} IS NOT NULL)"
        " / nullif(sum({peso}) FILTER (WHERE {col} IS NOT NULL), 0)"
    ).format(col=sql.Identifier(coluna), peso=sql.Identifier(peso))


def carregar_saeb(conexao) -> None:
    for tabela in ("saeb_municipio", "saeb_municipio_nivel"):
        with conexao.cursor() as cursor:
            cursor.execute(
                sql.SQL("TRUNCATE TABLE {}").format(sql.Identifier(SCHEMA, tabela))
            )
        conexao.commit()

    for ano in EDICOES_SAEB:
        construir_mascara(conexao, ano)

        origem = f"saeb_escola_{ano}"
        etapas = mapear_etapas(_colunas_de(conexao, origem))

        for nome, etapa in sorted(etapas.items()):
            selecoes = [
                sql.SQL("m.co_municipio"),
                sql.Literal(ano),
                sql.Literal(nome),
                sql.SQL("count(*)::int"),
                sql.SQL("sum({})::int").format(sql.Identifier(etapa.matriculados))
                if etapa.matriculados
                else sql.SQL("NULL::int"),
                sql.SQL("sum({})::int").format(sql.Identifier(etapa.presentes)),
                _media_ponderada(etapa.taxa, etapa.presentes)
                if etapa.taxa
                else sql.SQL("NULL::numeric"),
                _media_ponderada(etapa.media_lp, etapa.presentes)
                if etapa.media_lp
                else sql.SQL("NULL::numeric"),
                _media_ponderada(etapa.media_mt, etapa.presentes)
                if etapa.media_mt
                else sql.SQL("NULL::numeric"),
            ]
            comando = sql.SQL(
                "INSERT INTO {destino} (co_municipio, ano, etapa, escolas,"
                " matriculados_censo, presentes, taxa_participacao, media_lp, media_mt)\n"
                "SELECT {selecoes}\n"
                "FROM {origem} e"
                " JOIN {mascara} m ON m.ano = {ano} AND m.id_municipio_saeb = e.id_municipio\n"
                "WHERE e.{presentes} > 0\n"
                "GROUP BY m.co_municipio"
            ).format(
                destino=sql.Identifier(SCHEMA, "saeb_municipio"),
                selecoes=sql.SQL(",\n       ").join(selecoes),
                origem=sql.Identifier("raw", origem),
                mascara=sql.Identifier(SCHEMA, "saeb_mascara_municipio"),
                ano=sql.Literal(ano),
                presentes=sql.Identifier(etapa.presentes),
            )
            with conexao.cursor() as cursor:
                cursor.execute(comando)
                gravadas = cursor.rowcount
            conexao.commit()

            if etapa.niveis:
                partes = [
                    sql.SQL(
                        "SELECT m.co_municipio, {ano}, {etapa}, {disc}, {nivel},"
                        " {media}"
                        " FROM {origem} e JOIN {mascara} m"
                        " ON m.ano = {ano} AND m.id_municipio_saeb = e.id_municipio"
                        " WHERE e.{presentes} > 0"
                        " GROUP BY m.co_municipio"
                    ).format(
                        ano=sql.Literal(ano),
                        etapa=sql.Literal(nome),
                        disc=sql.Literal(disciplina),
                        nivel=sql.Literal(nivel),
                        media=_media_ponderada(coluna, etapa.presentes),
                        origem=sql.Identifier("raw", origem),
                        mascara=sql.Identifier(SCHEMA, "saeb_mascara_municipio"),
                        presentes=sql.Identifier(etapa.presentes),
                    )
                    for (disciplina, nivel), coluna in sorted(etapa.niveis.items())
                ]
                comando_nivel = sql.SQL(
                    "INSERT INTO {destino}"
                    " (co_municipio, ano, etapa, disciplina, nivel, percentual)\n"
                    "SELECT * FROM ({uniao})"
                    " AS t(co_municipio, ano, etapa, disciplina, nivel, percentual)\n"
                    "WHERE t.percentual IS NOT NULL"
                ).format(
                    destino=sql.Identifier(SCHEMA, "saeb_municipio_nivel"),
                    uniao=sql.SQL(" UNION ALL ").join(partes),
                )
                with conexao.cursor() as cursor:
                    cursor.execute(comando_nivel)
                    niveis = cursor.rowcount
                conexao.commit()
            else:
                niveis = 0

            logger.info(
                "stg.saeb_municipio %s %-4s %3s municípios, %4s linhas de nível",
                ano,
                nome,
                f"{gravadas:,}",
                f"{niveis:,}",
            )


# ------------------------------------------------------------------ PAEBES


def _inteiro(coluna: str, tipo: str = "integer") -> sql.Composed:
    """Converte para inteiro sem supor se a origem é texto ou número.

    As colunas do PAEBES chegam em `raw` com tipos mistos — `FL_AVALIADO` veio
    inteiro e `FL_PRESENTE` veio texto, porque o dicionário declara uma como
    inteiro e a outra como texto. Passar por `::text` primeiro nivela os dois.
    """

    return sql.SQL("nullif(btrim({}::text), '')::{}").format(
        sql.Identifier(coluna), sql.SQL(tipo)
    )


def carregar_paebes(conexao) -> None:
    comando = sql.SQL(
        """
        INSERT INTO {destino} (
            cd_aluno, ano, disciplina, co_entidade, co_municipio, etapa, rede,
            turno, regional, presente, avaliado, proficiencia, erro_padrao,
            padrao_desempenho, acertos, total_itens, ise, nse)
        SELECT {aluno}, 2025, nm_disciplina, {escola}, {municipio},
               dc_etapa_avaliada, dc_rede, dc_turno_agregado, nm_regional,
               {presente} = 1, {avaliado} = 1,
               {proficiencia}, {erro}, dc_padrao_desempenho,
               {acertos}, {total}, {ise}, dc_nse
        FROM {origem}
        WHERE nullif(btrim(cd_aluno::text), '') IS NOT NULL
          AND nullif(btrim(cd_escola::text), '') IS NOT NULL
        """
    ).format(
        destino=sql.Identifier(SCHEMA, "paebes_aluno"),
        origem=sql.Identifier("raw", "paebes_aluno_2025"),
        aluno=_inteiro("cd_aluno", "bigint"),
        escola=_inteiro("cd_escola"),
        municipio=_inteiro("cd_municipio"),
        presente=_inteiro("fl_presente", "smallint"),
        avaliado=_inteiro("fl_avaliado", "smallint"),
        proficiencia=_numero("vl_proficiencia"),
        erro=_numero("vl_proficiencia_erro"),
        acertos=_numero("nu_acerto"),
        total=_numero("nu_total"),
        ise=_numero("vl_ise"),
    )
    with conexao.cursor() as cursor:
        cursor.execute(
            sql.SQL("TRUNCATE TABLE {}").format(sql.Identifier(SCHEMA, "paebes_aluno"))
        )
        cursor.execute(comando)
        gravadas = cursor.rowcount
    conexao.commit()
    logger.info("stg.%-24s %8s linhas", "paebes_aluno", f"{gravadas:,}")


# --------------------------------------------------------------------- CLI

CARREGADORES = {
    "ideb": carregar_ideb,
    "enem": carregar_enem,
    "saeb": carregar_saeb,
    "paebes": carregar_paebes,
}


def aplicar_ddl() -> None:
    with get_connection() as conexao:
        for caminho in sorted(DIRETORIO_SQL.glob("*.sql")):
            with conexao.cursor() as cursor:
                cursor.execute(caminho.read_text(encoding="utf-8"))
            conexao.commit()
            logger.info("aplicado: %s", caminho.name)


def carregar(fontes: list[str] | None = None) -> None:
    with get_connection() as conexao:
        for fonte, funcao in CARREGADORES.items():
            if fontes and fonte not in fontes:
                continue
            funcao(conexao)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="stg das avaliações")
    parser.add_argument("--aplicar", action="store_true", help="Cria as tabelas")
    parser.add_argument("--carregar", action="store_true", help="Executa as transformações")
    parser.add_argument("--fonte", action="append", help="Restringe a uma fonte")
    args = parser.parse_args()

    if args.aplicar:
        aplicar_ddl()
    if args.carregar:
        carregar(args.fonte)
    if not args.aplicar and not args.carregar:
        parser.print_help()


if __name__ == "__main__":
    main()
