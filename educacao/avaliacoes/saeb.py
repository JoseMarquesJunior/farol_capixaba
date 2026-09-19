"""Tradução da máscara municipal do SAEB e agregação por município.

O SAEB publica `ID_ESCOLA` e `ID_MUNICIPIO` mascarados: chaves sequenciais
regeradas a cada edição, sem relação com os códigos INEP e IBGE. Medido nas
cinco edições carregadas, `ID_ESCOLA` **não** preserva a ordem — a máscara de
escola é irreversível, e é por isso que o SAEB só entra no modelo no grão
município.

`ID_MUNICIPIO`, ao contrário, **preserva a ordem**: `ID_UF` é monotônico quando
se ordena por `ID_MUNICIPIO`, o que revela uma renumeração sequencial da lista
de municípios ordenada por código IBGE. Quando a quantidade de municípios
mascarados de uma UF é igual à quantidade que a UF tem, o alinhamento posicional
é a única correspondência possível, e a tradução é exata.

No Espírito Santo a contagem bate nas cinco edições (78 = 78), e a tradução foi
conferida nas pontas: o primeiro código mascarado cai em Afonso Cláudio
(3200102) e o último em Vitória (3205309), que são de fato o primeiro e o último
município do ES por código IBGE.

`construir_mascara()` **exige** a igualdade e levanta exceção se ela não
ocorrer: é preferível não carregar a carregar município trocado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from psycopg import sql

from ..config.logging import configure_logger

logger = configure_logger(__name__)

SCHEMA = "stg"
CO_UF_ES = 32

#: Forma curta usada nos nomes de coluna -> etapa canônica.
_ETAPA_CURTA = {
    "2": "2EF",
    "3": "3EM",
    "5": "5EF",
    "9": "9EF",
    "EM": "EM",
    "EMI": "EMI",
    "EMT": "EMT",
}

_MEDIA = re.compile(r"^MEDIA_(?P<etapa>[A-Z0-9]+)_(?P<disc>LP|MT)$", re.I)
_NIVEL = re.compile(r"^NIVEL_(?P<nivel>\d+)_(?P<disc>LP|MT)(?P<etapa>[A-Z0-9]*)$", re.I)
_PRESENTES = re.compile(r"^NU_PRESENTES_(?P<etapa>[A-Z0-9]+)$", re.I)
_MATRICULADOS = re.compile(r"^NU_MATRICULADOS_CENSO_(?P<etapa>[A-Z0-9]+)$", re.I)


def _canonica(bruta: str) -> str | None:
    chave = bruta.strip().upper()
    return _ETAPA_CURTA.get(chave, chave if chave in _ETAPA_CURTA.values() else None)


@dataclass(frozen=True, slots=True)
class Etapa:
    """As colunas que uma etapa avaliada tem numa edição."""

    nome: str
    presentes: str | None = None
    matriculados: str | None = None
    taxa: str | None = None
    media_lp: str | None = None
    media_mt: str | None = None
    #: (disciplina, nível) -> coluna
    niveis: dict = None

    def completa(self) -> bool:
        return self.presentes is not None


def mapear_etapas(colunas: list[str]) -> dict[str, Etapa]:
    """Descobre, pelos nomes de coluna, quais etapas a edição traz.

    O vocabulário muda entre edições — 2015 só tem 5EF e 9EF, 2017 acrescenta
    3EM, e de 2019 em diante o médio vira EM/EMI/EMT —, então nada é fixo: as
    etapas são deduzidas dos próprios nomes.
    """

    campos: dict[str, dict] = {}

    def slot(etapa: str) -> dict:
        return campos.setdefault(etapa, {"niveis": {}})

    for coluna in colunas:
        nome = coluna.upper()

        if achado := _PRESENTES.match(nome):
            if etapa := _canonica(achado["etapa"]):
                slot(etapa)["presentes"] = coluna.lower()
            continue
        if achado := _MATRICULADOS.match(nome):
            if etapa := _canonica(achado["etapa"]):
                slot(etapa)["matriculados"] = coluna.lower()
            continue
        if nome.startswith("TAXA_PARTICIPACAO_"):
            if etapa := _canonica(nome[len("TAXA_PARTICIPACAO_") :]):
                slot(etapa)["taxa"] = coluna.lower()
            continue
        if achado := _MEDIA.match(nome):
            if etapa := _canonica(achado["etapa"]):
                chave = "media_lp" if achado["disc"].upper() == "LP" else "media_mt"
                slot(etapa)[chave] = coluna.lower()
            continue
        if achado := _NIVEL.match(nome):
            if etapa := _canonica(achado["etapa"]):
                disciplina = "portugues" if achado["disc"].upper() == "LP" else "matematica"
                slot(etapa)["niveis"][(disciplina, int(achado["nivel"]))] = coluna.lower()

    return {
        nome: Etapa(nome=nome, **dados)
        for nome, dados in campos.items()
        if dados.get("presentes")
    }


def construir_mascara(conexao, ano: int) -> int:
    """Traduz a máscara municipal daquela edição e grava em stg.

    Levanta se a contagem do ES não bater com a do Censo: sem igualdade, o
    alinhamento posicional deixa de ser demonstrável.
    """

    tabela = f"saeb_escola_{ano}"
    with conexao.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                "SELECT DISTINCT id_municipio FROM {} WHERE id_uf = %s"
                " ORDER BY id_municipio"
            ).format(sql.Identifier("raw", tabela)),
            (CO_UF_ES,),
        )
        mascarados = [linha[0] for linha in cursor.fetchall()]

        cursor.execute(
            "SELECT co_municipio FROM dw.dim_municipio ORDER BY co_municipio"
        )
        reais = [linha[0] for linha in cursor.fetchall()]

    if len(mascarados) != len(reais):
        raise ValueError(
            f"SAEB {ano}: {len(mascarados)} municípios mascarados no ES contra "
            f"{len(reais)} em dw.dim_municipio. Sem igualdade o alinhamento "
            f"ordenado não é demonstrável; a tradução foi abortada."
        )

    with conexao.cursor() as cursor:
        cursor.execute(
            sql.SQL("DELETE FROM {} WHERE ano = %s").format(
                sql.Identifier(SCHEMA, "saeb_mascara_municipio")
            ),
            (ano,),
        )
        with cursor.copy(
            sql.SQL("COPY {} (ano, id_municipio_saeb, co_municipio) FROM STDIN").format(
                sql.Identifier(SCHEMA, "saeb_mascara_municipio")
            )
        ) as copy:
            for mascarado, real in zip(mascarados, reais):
                copy.write_row((ano, mascarado, real))
    conexao.commit()

    logger.info(
        "stg.saeb_mascara_municipio %s — %d municípios traduzidos (%s -> %s ... %s -> %s)",
        ano,
        len(reais),
        mascarados[0],
        reais[0],
        mascarados[-1],
        reais[-1],
    )
    return len(reais)
