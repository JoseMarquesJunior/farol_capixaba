"""Montagem do catálogo de metadados, ano a ano.

Princípio: **o cabeçalho do CSV é a verdade** sobre quais colunas existem e em
que ordem; o dicionário apenas enriquece cada uma com descrição, tipo, domínio
e histórico de coleta.

A alternativa — selecionar colunas pela matriz "Coleta por ano" do dicionário —
não funciona: ela registra o que foi *coletado na pesquisa*, não o que saiu no
arquivo publicado. Em 2015 ela marca 699 variáveis para um arquivo de 370
colunas, e em `Tabela_Curso_Técnico` de 2025 a matriz sequer tem coluna para
2025. Invertendo a direção, os 19 anos fecham sem nenhuma exceção.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from ..config.logging import configure_logger
from ..config.settings import (
    DEFAULT_ENCODING,
    DEFAULT_SEPARATOR,
    METADATA_DIR,
    ROOT,
)
from .dicionario import LinhaDicionario, ler_dicionario
from .dominios import parse_dominio
from .fontes import ANOS, localizar_arquivos, localizar_dicionario, nome_tabela
from .models import CatalogoAno, Tabela, Variavel
from .tipos import tipo_postgres
from .verificacao import LINHAS_AMOSTRA, ajustar_tipo, medir_arquivo

logger = configure_logger(__name__)

RAIZ_PROJETO = ROOT.parent
DIRETORIO_CATALOGO = METADATA_DIR / "catalog"


def ler_cabecalho(
    caminho: Path,
    delimitador: str = DEFAULT_SEPARATOR,
    encoding: str = DEFAULT_ENCODING,
) -> list[str]:
    """Nomes das colunas do CSV, na ordem em que aparecem."""

    with caminho.open("r", encoding=encoding, newline="") as arquivo:
        cabecalho = next(csv.reader(arquivo, delimiter=delimitador))
    return [coluna.strip().lstrip("﻿") for coluna in cabecalho]


def casar_aba(
    colunas: list[str],
    abas: dict[str, dict[str, LinhaDicionario]],
    caminho: Path,
) -> str:
    """Aba do dicionário que descreve este arquivo: a que cobre mais colunas."""

    melhor, cobertura = None, -1
    for titulo, variaveis in abas.items():
        cobertas = sum(1 for coluna in colunas if coluna in variaveis)
        if cobertas > cobertura:
            melhor, cobertura = titulo, cobertas

    orfas = [coluna for coluna in colunas if coluna not in abas[melhor]]
    if orfas:
        raise ValueError(
            f"{caminho.name}: {len(orfas)} coluna(s) sem entrada no dicionário "
            f"(aba '{melhor}'): {orfas[:5]}"
        )
    return melhor


def montar_tabela(
    ano: int,
    caminho: Path,
    abas: dict[str, dict[str, LinhaDicionario]],
    amostrar: bool = True,
    linhas: int = LINHAS_AMOSTRA,
) -> Tabela:
    colunas = ler_cabecalho(caminho)
    aba = casar_aba(colunas, abas, caminho)
    dicionario = abas[aba]

    medicoes = (
        medir_arquivo(caminho, DEFAULT_SEPARATOR, DEFAULT_ENCODING, linhas)
        if amostrar
        else {}
    )

    variaveis: list[Variavel] = []
    for ordem, coluna in enumerate(colunas):
        linha = dicionario[coluna]
        tipo = tipo_postgres(linha.tipo_original, linha.tamanho)
        ajuste = None

        medicao = medicoes.get(coluna)
        if medicao is not None:
            tipo, ajuste = ajustar_tipo(tipo, linha.tipo_original, medicao)
            if ajuste:
                logger.info(
                    "%s.%s: %s -> %s (%s)",
                    caminho.name,
                    coluna,
                    tipo_postgres(linha.tipo_original, linha.tamanho),
                    tipo,
                    ajuste,
                )

        variaveis.append(
            Variavel(
                nome=coluna,
                ordem=ordem,
                descricao=linha.descricao,
                tipo_original=linha.tipo_original,
                tamanho=linha.tamanho,
                tipo_postgres=tipo,
                dominio=parse_dominio(linha.categoria),
                nota=linha.nota,
                anos_coleta=linha.anos_coleta,
                ajuste_tipo=ajuste,
            )
        )

    return Tabela(
        ano=ano,
        nome=nome_tabela(aba),
        arquivo=caminho,
        aba=aba,
        delimitador=DEFAULT_SEPARATOR,
        encoding=DEFAULT_ENCODING,
        variaveis=variaveis,
    )


def montar_ano(
    ano: int, amostrar: bool = True, linhas: int = LINHAS_AMOSTRA
) -> CatalogoAno:
    caminho_dicionario = localizar_dicionario(ano)
    abas = ler_dicionario(caminho_dicionario)
    arquivos = localizar_arquivos(ano)

    if not arquivos:
        raise FileNotFoundError(f"Nenhum CSV de microdados encontrado para {ano}")

    tabelas = [
        montar_tabela(ano, caminho, abas, amostrar=amostrar, linhas=linhas)
        for caminho in arquivos
    ]
    return CatalogoAno(ano=ano, dicionario=caminho_dicionario, tabelas=tabelas)


def gravar(catalogo: CatalogoAno, destino: Path = DIRETORIO_CATALOGO) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"{catalogo.ano}.json"
    arquivo.write_text(
        json.dumps(catalogo.to_dict(RAIZ_PROJETO), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return arquivo


def gravar_indice(
    catalogos: list[CatalogoAno], destino: Path = DIRETORIO_CATALOGO
) -> Path:
    indice = {
        "anos": [
            {
                "ano": catalogo.ano,
                "tabelas": [
                    {
                        "nome": tabela.nome,
                        "tabela_raw": tabela.tabela_raw,
                        "variaveis": len(tabela.variaveis),
                        "ajustes_de_tipo": sum(
                            1 for v in tabela.variaveis if v.ajuste_tipo
                        ),
                    }
                    for tabela in catalogo.tabelas
                ],
            }
            for catalogo in sorted(catalogos, key=lambda c: c.ano)
        ]
    }
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / "indice.json"
    arquivo.write_text(
        json.dumps(indice, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return arquivo


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera o catálogo de metadados do Censo Escolar a partir "
        "do dicionário de dados de cada ano"
    )
    parser.add_argument("--ano", type=int, help="Gera apenas este ano")
    parser.add_argument(
        "--sem-amostra",
        action="store_true",
        help="Não confere os tipos declarados contra os dados (mais rápido)",
    )
    parser.add_argument(
        "--linhas",
        type=int,
        default=LINHAS_AMOSTRA,
        help="Linhas lidas por arquivo na conferência de tipos; 0 = arquivo inteiro",
    )
    args = parser.parse_args()

    anos = [args.ano] if args.ano else list(ANOS)
    catalogos: list[CatalogoAno] = []

    for ano in anos:
        catalogo = montar_ano(
            ano, amostrar=not args.sem_amostra, linhas=args.linhas
        )
        arquivo = gravar(catalogo)
        catalogos.append(catalogo)
        resumo = ", ".join(
            f"{t.nome}={len(t.variaveis)}" for t in catalogo.tabelas
        )
        logger.info("%s -> %s (%s)", ano, arquivo.name, resumo)

    if len(catalogos) > 1:
        logger.info("Índice: %s", gravar_indice(catalogos).name)


if __name__ == "__main__":
    main()
