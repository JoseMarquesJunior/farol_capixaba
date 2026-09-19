"""Carga das avaliações para `raw`, filtrada no Espírito Santo.

Cada fonte identifica a UF de um jeito, e o filtro é aplicado em streaming, na
leitura: nada do resto do Brasil chega a entrar no banco.

==========  ============================  ==================================
fonte       coluna do filtro              formato de origem
==========  ============================  ==================================
IDEB        ``SG_UF = 'ES'``              planilha larga -> longo na carga
ENEM        ``SG_UF_ESCOLA = 'ES'``       CSV dentro do ZIP
SAEB        ``ID_UF = 32``                CSV solto (extraído por Range)
PAEBES      ``CD_ESTADO = 32``            CSV dentro do ZIP
==========  ============================  ==================================

O PAEBES já vem só do ES, mas o filtro fica aplicado mesmo assim: é barato e
transforma uma suposição em garantia.

Os CSV entram por ``COPY`` com filtro linha a linha, como no Censo. O IDEB não
pode: a origem é `.xlsx`, então as linhas são despivotadas em Python e
enviadas por ``copy.write_row()``.

Cada carga é registrada em `etl.carga` com o sha256 do arquivo — repetir o
comando não recarrega o que já entrou.

Uso::

    python -m educacao.avaliacoes.carga
    python -m educacao.avaliacoes.carga --fonte ideb
    python -m educacao.avaliacoes.carga --fonte saeb --forcar
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
import zipfile
from pathlib import Path

from psycopg import sql

from ..config.database import get_connection
from ..config.logging import configure_logger
from ..config.settings import AVALIACOES_DIR
from . import ideb as mod_ideb
from .catalogo import CATALOGADORES
from .catalogo import carregar as carregar_catalogo
from .ddl import IDEB_LONGO, SCHEMA, colunas_ideb

logger = configure_logger(__name__)

RAIZ = AVALIACOES_DIR.parent.parent
SIGLA_ES = "ES"
CO_UF_ES = "32"
AUSENTE = "-"

#: Coluna que carrega a UF em cada fonte, e o valor que representa o ES.
FILTRO_UF = {
    "enem": ("SG_UF_ESCOLA", SIGLA_ES),
    "saeb": ("ID_UF", CO_UF_ES),
    "paebes": ("CD_ESTADO", CO_UF_ES),
}


def sha256(caminho: Path, bloco: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for pedaco in iter(lambda: arquivo.read(bloco), b""):
            digest.update(pedaco)
    return digest.hexdigest()


def ja_carregado(conexao, tabela_raw: str, digest: str, filtro: str) -> bool:
    """Se o arquivo já entrou **e** a tabela ainda tem o que ele gravou.

    Conferir as duas coisas importa: o registro em `etl.carga` sobrevive a um
    DROP TABLE, e confiar só nele faz a carga pular uma tabela vazia.
    """

    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT linhas_gravadas FROM etl.carga"
            " WHERE tabela_raw = %s AND sha256 = %s AND filtro = %s"
            "   AND status = 'concluida'"
            " ORDER BY fim DESC LIMIT 1",
            (tabela_raw, digest, filtro),
        )
        registro = cursor.fetchone()
        if registro is None:
            return False

        cursor.execute("SELECT to_regclass(%s)", (f"{SCHEMA}.{tabela_raw}",))
        if cursor.fetchone()[0] is None:
            return False

        cursor.execute(
            sql.SQL("SELECT count(*) FROM {}").format(
                sql.Identifier(SCHEMA, tabela_raw)
            )
        )
        return cursor.fetchone()[0] == registro[0]


def _abrir_csv(caminho: Path, encoding: str):
    """Devolve (arquivo de texto, fechar) para CSV solto ou dentro de ZIP."""

    if caminho.suffix.lower() == ".zip":
        pacote = zipfile.ZipFile(caminho)
        nome = next(n for n in pacote.namelist() if n.lower().endswith(".csv"))
        binario = pacote.open(nome)
        texto = io.TextIOWrapper(binario, encoding=encoding, newline="")

        def fechar() -> None:
            texto.close()
            binario.close()
            pacote.close()

        return texto, fechar

    arquivo = caminho.open(encoding=encoding, newline="")
    return arquivo, arquivo.close


def registrar_inicio(conexao, fonte: str, tabela: dict | str, arquivo: str,
                     digest: str, filtro: str, edicao: int | None) -> int:
    nome = tabela if isinstance(tabela, str) else tabela["nome"]
    tabela_raw = tabela if isinstance(tabela, str) else tabela["tabela_raw"]
    with conexao.cursor() as cursor:
        cursor.execute(
            "INSERT INTO etl.carga (ano, tabela, tabela_raw, arquivo, sha256, filtro)"
            " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (edicao, f"{fonte}:{nome}", tabela_raw, arquivo, digest, filtro),
        )
        carga_id = cursor.fetchone()[0]
    conexao.commit()
    return carga_id


def registrar_fim(conexao, carga_id: int, lidas: int, gravadas: int) -> None:
    with conexao.cursor() as cursor:
        cursor.execute(
            "UPDATE etl.carga SET fim = now(), status = 'concluida',"
            " linhas_lidas = %s, linhas_gravadas = %s WHERE id = %s",
            (lidas, gravadas, carga_id),
        )
    conexao.commit()


def registrar_falha(conexao, carga_id: int, erro: Exception) -> None:
    conexao.rollback()
    with conexao.cursor() as cursor:
        cursor.execute(
            "UPDATE etl.carga SET fim = now(), status = 'falhou', erro = %s"
            " WHERE id = %s",
            (str(erro)[:2000], carga_id),
        )
    conexao.commit()


# ------------------------------------------------------------------- CSV


def carregar_csv(conexao, fonte: str, tabela: dict, forcar: bool = False) -> None:
    caminho = RAIZ / tabela["arquivo"]
    if not caminho.exists():
        raise FileNotFoundError(caminho)

    coluna_uf, valor_uf = FILTRO_UF[fonte]
    filtro = f"{coluna_uf} = {valor_uf}"
    digest = sha256(caminho)

    if not forcar and ja_carregado(conexao, tabela["tabela_raw"], digest, filtro):
        logger.info("raw.%s já carregada (mesmo sha256)", tabela["tabela_raw"])
        return

    cabecalho = [v["nome"] for v in tabela["variaveis"]]
    try:
        indice_uf = next(
            i for i, c in enumerate(cabecalho) if c.casefold() == coluna_uf.casefold()
        )
    except StopIteration:
        raise ValueError(
            f"{tabela['tabela_raw']}: sem a coluna {coluna_uf} para filtrar o ES"
        ) from None

    edicao = tabela["edicoes"][0] if len(tabela["edicoes"]) == 1 else None
    carga_id = registrar_inicio(
        conexao, fonte, tabela, tabela["arquivo"], digest, filtro, edicao
    )

    comando = sql.SQL(
        "COPY {} FROM STDIN WITH (FORMAT csv, DELIMITER {}, NULL '')"
    ).format(
        sql.Identifier(SCHEMA, tabela["tabela_raw"]),
        sql.Literal(tabela["delimitador"]),
    )

    try:
        lidas = gravadas = 0
        arquivo, fechar = _abrir_csv(caminho, tabela["encoding"])
        try:
            next(arquivo)  # cabeçalho não vai para o COPY
            with conexao.cursor() as cursor:
                cursor.execute(
                    sql.SQL("TRUNCATE TABLE {}").format(
                        sql.Identifier(SCHEMA, tabela["tabela_raw"])
                    )
                )
                with cursor.copy(comando) as copy:
                    for linha in arquivo:
                        lidas += 1
                        campos = linha.split(tabela["delimitador"], indice_uf + 1)
                        if len(campos) <= indice_uf:
                            continue
                        if campos[indice_uf].strip() != valor_uf:
                            continue
                        copy.write(linha)
                        gravadas += 1
        finally:
            fechar()

        registrar_fim(conexao, carga_id, lidas, gravadas)
        logger.info(
            "raw.%-22s %8s de %9s linhas (%.1f%%)  filtro: %s",
            tabela["tabela_raw"],
            f"{gravadas:,}",
            f"{lidas:,}",
            gravadas / lidas * 100 if lidas else 0,
            filtro,
        )
    except Exception as erro:
        registrar_falha(conexao, carga_id, erro)
        logger.error("falha em raw.%s: %s", tabela["tabela_raw"], erro)
        raise


# ------------------------------------------------------------------ IDEB


def _numero(valor) -> float | None:
    """Converte a célula da planilha; '-' e vazio viram NULL."""

    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip()
    if not texto or texto == AUSENTE:
        return None
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def linhas_ideb(caminho: Path, alvo: str):
    """Despivota uma planilha do IDEB em registros longos do ES."""

    etapa = mod_ideb.etapa_do_arquivo(caminho)
    workbook, worksheet = mod_ideb.abrir_planilha(caminho)
    try:
        cabecalho = mod_ideb.localizar_cabecalho(worksheet)
        ident = cabecalho.identificacao
        col_uf = ident["SG_UF"]
        com_escola = alvo == "escolas"

        for numero, linha in enumerate(worksheet.iter_rows(values_only=True), 1):
            if numero < cabecalho.primeira_linha_dados:
                continue
            if not linha or len(linha) <= col_uf or linha[col_uf] != SIGLA_ES:
                continue

            base = [
                linha[col_uf],
                linha[ident["CO_MUNICIPIO"]],
                linha[ident["NO_MUNICIPIO"]],
            ]
            if com_escola:
                base += [linha[ident["ID_ESCOLA"]], linha[ident["NO_ESCOLA"]]]
            base.append(linha[ident["REDE"]])

            for coluna in cabecalho.medidas:
                if coluna.indice >= len(linha):
                    continue
                valor = _numero(linha[coluna.indice])
                if valor is None:
                    continue
                yield base + [
                    etapa,
                    coluna.edicao,
                    coluna.medida,
                    coluna.serie,
                    coluna.disciplina,
                    valor,
                    coluna.nome,
                ]
    finally:
        workbook.close()


def carregar_ideb(conexao, alvo: str, forcar: bool = False) -> None:
    tabela_raw = IDEB_LONGO[alvo]
    colunas = [nome for nome, _, _ in colunas_ideb(alvo)]
    filtro = f"SG_UF = {SIGLA_ES}"

    arquivos = mod_ideb.arquivos(alvo)
    digest = hashlib.sha256(
        "".join(sha256(caminho) for caminho in arquivos).encode()
    ).hexdigest()

    if not forcar and ja_carregado(conexao, tabela_raw, digest, filtro):
        logger.info("raw.%s já carregada (mesmo sha256)", tabela_raw)
        return

    carga_id = registrar_inicio(
        conexao,
        "ideb",
        tabela_raw,
        ", ".join(c.name for c in arquivos),
        digest,
        filtro,
        None,
    )

    comando = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(SCHEMA, tabela_raw),
        sql.SQL(", ").join(sql.Identifier(c) for c in colunas),
    )

    try:
        gravadas = 0
        with conexao.cursor() as cursor:
            cursor.execute(
                sql.SQL("TRUNCATE TABLE {}").format(sql.Identifier(SCHEMA, tabela_raw))
            )
            with cursor.copy(comando) as copy:
                for caminho in arquivos:
                    antes = gravadas
                    for registro in linhas_ideb(caminho, alvo):
                        copy.write_row(registro)
                        gravadas += 1
                    logger.info(
                        "   %-38s %8s medidas", caminho.stem, f"{gravadas - antes:,}"
                    )

        registrar_fim(conexao, carga_id, gravadas, gravadas)
        logger.info("raw.%-22s %8s linhas  filtro: %s", tabela_raw, f"{gravadas:,}", filtro)
    except Exception as erro:
        registrar_falha(conexao, carga_id, erro)
        logger.error("falha em raw.%s: %s", tabela_raw, erro)
        raise


# ------------------------------------------------------------------- CLI


def carregar(fontes: list[str] | None = None, forcar: bool = False) -> None:
    with get_connection() as conexao:
        for fonte in CATALOGADORES:
            if fontes and fonte not in fontes:
                continue
            if fonte == "ideb":
                for alvo in IDEB_LONGO:
                    carregar_ideb(conexao, alvo, forcar=forcar)
                continue
            for tabela in carregar_catalogo(fonte)["tabelas"]:
                carregar_csv(conexao, fonte, tabela, forcar=forcar)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Carrega as avaliações em raw, filtradas para o ES"
    )
    parser.add_argument("--fonte", action="append", help="Restringe a uma fonte")
    parser.add_argument("--forcar", action="store_true", help="Recarrega mesmo assim")
    args = parser.parse_args()

    carregar(args.fonte, forcar=args.forcar)


if __name__ == "__main__":
    main()
