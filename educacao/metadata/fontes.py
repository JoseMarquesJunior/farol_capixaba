"""Localização dos arquivos de cada ano do Censo dentro de `data/extracted`.

Os nomes de pasta e de arquivo mudam de ano para ano (`microdados_ed_basica_2015`,
`Microdados do Censo Escolar da Educação Básica 2022`,
`microdados_censo_escolar_2024_defeso`...), e parte deles foi extraída com o
acento corrompido. Por isso nada aqui é caminho fixo: tudo é descoberto por
padrão dentro da pasta do ano.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from ..config.settings import EXTRACTED_DIR

#: Faixa com dicionário `.xlsx` estruturado. De 1995 a 2006 só existe PDF.
ANOS = range(2007, 2026)

#: Prefixos deixados por execuções anteriores do pipeline, que não são fonte.
PREFIXOS_IGNORADOS = ("normalized_", "test_", "validation")

_ALIASES_TABELA = {
    "cadastro_escolas": "escola",
    "microdados_unidade_coleta": "escola",
    "suplemento_cursos_tecnicos": "curso_tecnico",
    "curso_tecnico": "curso_tecnico",
    "escola": "escola",
    "matricula": "matricula",
    "docente": "docente",
    "turma": "turma",
    "gestor": "gestor",
}


def sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def nome_tabela(aba: str) -> str:
    """Nome canônico da tabela a partir do título da aba do dicionário."""

    chave = sem_acento(aba).strip().lower().replace(" ", "_")
    for prefixo in ("tabela_de_", "tabela_"):
        if chave.startswith(prefixo):
            chave = chave[len(prefixo) :]
    chave = chave.strip("_")

    if chave not in _ALIASES_TABELA:
        raise KeyError(
            f"Aba '{aba}' não tem tabela correspondente. "
            f"Adicione o alias em {__name__}._ALIASES_TABELA."
        )
    return _ALIASES_TABELA[chave]


def pasta_do_ano(ano: int, raiz: Path | None = None) -> Path:
    pasta = (raiz or EXTRACTED_DIR) / str(ano)
    if not pasta.is_dir():
        raise FileNotFoundError(f"Ano {ano} não encontrado em {pasta.parent}")
    return pasta


def localizar_dicionario(ano: int, raiz: Path | None = None) -> Path:
    """Caminho do ANEXO I (dicionário de dados) do ano."""

    candidatos = [
        caminho
        for caminho in pasta_do_ano(ano, raiz).rglob("*.xlsx")
        if "icion" in caminho.name and not caminho.name.startswith("~$")
    ]
    if not candidatos:
        raise FileNotFoundError(f"Dicionário de dados não encontrado para {ano}")
    return sorted(candidatos)[0]


def localizar_arquivos(ano: int, raiz: Path | None = None) -> list[Path]:
    """CSVs de microdados do ano, sem os resíduos de execuções anteriores."""

    return sorted(
        caminho
        for caminho in pasta_do_ano(ano, raiz).rglob("*")
        if caminho.is_file()
        and caminho.suffix.lower() == ".csv"
        and not caminho.name.startswith(PREFIXOS_IGNORADOS)
    )
