"""Constantes do ETL: endereços, nomes de anexo esperados e caminhos.

Os nomes de anexo abaixo são o que se OBSERVOU em 2021–2025 (2026-09-21). Eles
não são tomados como verdade: `anexos.descobrir()` lê o nome real de cada
exercício nos próprios dados e o ETL avisa quando diverge destes valores.
"""

from __future__ import annotations

from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
BRUTO = PASTA / "dados" / "bruto"
PROCESSADO = PASTA / "dados" / "processado"
DADOS_MANUAIS = PASTA / "dados_manuais.yaml"
PROGRAMAS = PASTA / "programas.yaml"

BASE_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"

#: Código do Estado do ES em `entes`. Atenção: o campo `uf` dele vem "BR", não
#: "ES" — filtrar o Estado por `uf` o perde. Os municípios vêm com uf == "ES".
COD_ESTADO_ES = 32
UF_MUNICIPIOS = "ES"
N_MUNICIPIOS_ES = 78

#: Município usado para descobrir os nomes de anexo. Publica RREO comum, tem
#: FUNDEB e entrega a DCA completa em todos os exercícios testados.
ENTE_REFERENCIA = 3205309  # Vitória

#: Pequenos municípios podem publicar o RREO em `RREO Simplificado`, com o mesmo
#: nome de anexo. Sem tentar os dois tipos, 53 dos 78 apareceriam como "sem dado".
TIPOS_RREO = ("RREO", "RREO Simplificado")
BIMESTRES = (1, 2, 3, 4, 5, 6)

ANEXO_RREO_DESPESA_FUNCAO = "RREO-Anexo 02"
ANEXO_DCA_DESPESA_FUNCAO = "DCA-Anexo I-E"
ANEXO_DCA_RECEITA = "DCA-Anexo I-C"

#: Um exercício conta como "publicado" quando ao menos esta fração dos entes já
#: entregou a DCA de despesa por função.
LIMITE_COBERTURA_EXERCICIO = 0.5
N_EXERCICIOS = 5

URL_SICONFI = "https://siconfi.tesouro.gov.br/siconfi/pages/public/consulta_finbra/finbra_list.jsf"
URL_API_DOC = "https://apidatalake.tesouro.gov.br/docs/siconfi/"
