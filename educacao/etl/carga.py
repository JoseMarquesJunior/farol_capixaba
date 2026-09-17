"""Carga dos microdados para `raw`, com filtro do Espírito Santo em streaming.

O `COPY` lê direto do CSV publicado pelo INEP: nenhum arquivo intermediário é
escrito em disco, e o filtro é aplicado linha a linha no caminho para o banco —
nada do resto do Brasil chega a entrar.

Filtro, por ordem de preferência:

* `CO_UF = 32` quando a tabela tem a coluna (todo o período 2007-2024, e a
  tabela de escola de 2025);
* `CO_ENTIDADE` começando em `32` nas cinco tabelas de 2025 que só trazem o
  código da escola. A equivalência foi conferida contra os dados: das 214.192
  escolas do Brasil em 2025, as 3.847 do ES têm código iniciado em 32, e
  nenhuma escola de outra UF tem.

Os arquivos não têm nenhum campo entre aspas — conferido em 600 mil linhas de
2015, 2024 e 2025 —, então a linha é dividida por `;` só até a coluna do filtro
e, passando, segue inteira e intacta para o `COPY`.

Cada carga é registrada em `etl.carga` com o sha256 do arquivo: repetir o
comando não recarrega o que já entrou, e uma republicação do INEP é detectada
pela mudança do hash.

Uso::

    python -m educacao.etl.carga                 # todos os anos
    python -m educacao.etl.carga --ano 2025
    python -m educacao.etl.carga --ano 2025 --forcar
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

from psycopg import sql

from ..config.database import get_connection
from ..config.logging import configure_logger
from ..config.settings import DEFAULT_ENCODING, DEFAULT_SEPARATOR
from ..metadata.catalogo import RAIZ_PROJETO
from ..metadata.fontes import ANOS

logger = configure_logger(__name__)

CO_UF_ES = "32"
PREFIXO_ENTIDADE_ES = "32"


@dataclass(slots=True)
class Filtro:
    coluna: str
    indice: int
    modo: str
    valor: str

    def __str__(self) -> str:
        operador = "=" if self.modo == "igual" else "começa com"
        return f"{self.coluna} {operador} {self.valor}"

    def aceita(self, campos: list[str]) -> bool:
        valor = campos[self.indice].strip()
        if self.modo == "igual":
            return valor == self.valor
        return valor.startswith(self.valor)


def definir_filtro(colunas: list[str]) -> Filtro:
    if "CO_UF" in colunas:
        return Filtro("CO_UF", colunas.index("CO_UF"), "igual", CO_UF_ES)
    if "CO_ENTIDADE" in colunas:
        return Filtro(
            "CO_ENTIDADE",
            colunas.index("CO_ENTIDADE"),
            "prefixo",
            PREFIXO_ENTIDADE_ES,
        )
    raise ValueError(
        "Arquivo sem CO_UF nem CO_ENTIDADE: não há como recortar o ES"
    )


def sha256(caminho: Path, bloco: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for pedaco in iter(lambda: arquivo.read(bloco), b""):
            digest.update(pedaco)
    return digest.hexdigest()


def ja_carregado(conexao, tabela_raw: str, digest: str, filtro: str) -> bool:
    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM etl.carga"
            " WHERE tabela_raw = %s AND sha256 = %s AND filtro = %s"
            "   AND status = 'concluida' LIMIT 1",
            (tabela_raw, digest, filtro),
        )
        return cursor.fetchone() is not None


def tabelas_do_ano(conexao, ano: int) -> list[dict]:
    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT tabela, tabela_raw, arquivo FROM meta.tabela"
            " WHERE ano = %s ORDER BY tabela",
            (ano,),
        )
        return [
            {"tabela": linha[0], "tabela_raw": linha[1], "arquivo": linha[2]}
            for linha in cursor.fetchall()
        ]


def copiar(conexao, tabela_raw: str, caminho: Path, filtro: Filtro) -> tuple[int, int]:
    """Faz o COPY filtrado. Devolve (linhas lidas, linhas gravadas)."""

    comando = sql.SQL(
        "COPY {} FROM STDIN WITH (FORMAT csv, DELIMITER {}, NULL '')"
    ).format(sql.Identifier("raw", tabela_raw), sql.Literal(DEFAULT_SEPARATOR))

    lidas = gravadas = 0
    corte = filtro.indice + 1

    with conexao.cursor() as cursor:
        cursor.execute(
            sql.SQL("TRUNCATE TABLE {}").format(sql.Identifier("raw", tabela_raw))
        )
        with caminho.open("r", encoding=DEFAULT_ENCODING, newline="") as arquivo:
            next(arquivo)  # o cabeçalho não vai para o COPY
            with cursor.copy(comando) as copy:
                for linha in arquivo:
                    lidas += 1
                    if not filtro.aceita(linha.split(DEFAULT_SEPARATOR, corte)):
                        continue
                    copy.write(linha)
                    gravadas += 1

    return lidas, gravadas


def carregar_tabela(conexao, ano: int, alvo: dict, forcar: bool = False) -> None:
    caminho = RAIZ_PROJETO / alvo["arquivo"]
    if not caminho.exists():
        raise FileNotFoundError(caminho)

    with caminho.open("r", encoding=DEFAULT_ENCODING, newline="") as arquivo:
        colunas = [
            coluna.strip().lstrip("﻿")
            for coluna in next(csv.reader(arquivo, delimiter=DEFAULT_SEPARATOR))
        ]

    filtro = definir_filtro(colunas)
    digest = sha256(caminho)

    if not forcar and ja_carregado(conexao, alvo["tabela_raw"], digest, str(filtro)):
        logger.info("raw.%s já carregada (mesmo sha256); pulando", alvo["tabela_raw"])
        return

    with conexao.cursor() as cursor:
        cursor.execute(
            "INSERT INTO etl.carga (ano, tabela, tabela_raw, arquivo, sha256, filtro)"
            " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (
                ano,
                alvo["tabela"],
                alvo["tabela_raw"],
                alvo["arquivo"],
                digest,
                str(filtro),
            ),
        )
        carga_id = cursor.fetchone()[0]
    conexao.commit()

    try:
        lidas, gravadas = copiar(conexao, alvo["tabela_raw"], caminho, filtro)

        with conexao.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT count(*) FROM {}").format(
                    sql.Identifier("raw", alvo["tabela_raw"])
                )
            )
            na_tabela = cursor.fetchone()[0]

        if na_tabela != gravadas:
            raise RuntimeError(
                f"contagem divergente em raw.{alvo['tabela_raw']}: "
                f"{gravadas} enviadas, {na_tabela} na tabela"
            )

        with conexao.cursor() as cursor:
            cursor.execute(
                "UPDATE etl.carga SET fim = now(), status = 'concluida',"
                " linhas_lidas = %s, linhas_gravadas = %s WHERE id = %s",
                (lidas, gravadas, carga_id),
            )
        conexao.commit()

        proporcao = (gravadas / lidas * 100) if lidas else 0
        logger.info(
            "raw.%-22s %7s de %9s linhas (%.1f%%)  filtro: %s",
            alvo["tabela_raw"],
            f"{gravadas:,}",
            f"{lidas:,}",
            proporcao,
            filtro,
        )

    except Exception as erro:
        conexao.rollback()
        with conexao.cursor() as cursor:
            cursor.execute(
                "UPDATE etl.carga SET fim = now(), status = 'falhou', erro = %s"
                " WHERE id = %s",
                (str(erro)[:2000], carga_id),
            )
        conexao.commit()
        logger.error("falha em raw.%s: %s", alvo["tabela_raw"], erro)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Carrega os microdados do Censo em raw, filtrados para o ES"
    )
    parser.add_argument("--ano", type=int, help="Apenas este ano")
    parser.add_argument(
        "--forcar",
        action="store_true",
        help="Recarrega mesmo que o arquivo já tenha entrado",
    )
    args = parser.parse_args()

    anos = [args.ano] if args.ano else list(ANOS)

    with get_connection() as conexao:
        for ano in anos:
            for alvo in tabelas_do_ano(conexao, ano):
                carregar_tabela(conexao, ano, alvo, forcar=args.forcar)


if __name__ == "__main__":
    main()
