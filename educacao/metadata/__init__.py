"""Catálogo de metadados do Censo Escolar, derivado do ANEXO I de cada ano."""

from .catalogo import montar_ano, gravar, gravar_indice
from .models import CatalogoAno, Tabela, ValorDominio, Variavel

__all__ = [
    "CatalogoAno",
    "Tabela",
    "ValorDominio",
    "Variavel",
    "gravar",
    "gravar_indice",
    "montar_ano",
]
