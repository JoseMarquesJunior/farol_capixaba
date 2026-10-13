import gzip
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _carregar(nome: str) -> list[dict]:
    comprimido = FIXTURES / f"{nome}.json.gz"
    if comprimido.exists():
        with gzip.open(comprimido, "rt", encoding="utf-8") as f:
            return json.load(f)
    with open(FIXTURES / f"{nome}.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def dca_ie() -> list[dict]:
    """DCA-Anexo I-E, Vitória 2024, resposta real da API."""
    return _carregar("dca_i_e_vitoria_2024")


@pytest.fixture(scope="session")
def dca_ic() -> list[dict]:
    """DCA-Anexo I-C, Vitória 2024 (recorte: FUNDEB e totais)."""
    return _carregar("dca_i_c_vitoria_2024")


@pytest.fixture(scope="session")
def dca_ic_com_complementacao() -> list[dict]:
    """I-C de Afonso Cláudio 2025: recebe complementação da União (conta 1.7.1.5)."""
    return _carregar("dca_i_c_afonso_claudio_2025")


@pytest.fixture(scope="session")
def dca_ic_2021_codigos_antigos() -> list[dict]:
    """I-C de Colatina 2021: os códigos de conta do FUNDEB eram outros (1.7.5.8.01 e 1.7.1.8.09)."""
    return _carregar("dca_i_c_colatina_2021")


@pytest.fixture(scope="session")
def rreo_a02() -> list[dict]:
    """RREO-Anexo 02, 6º bimestre, Vitória 2024 (recorte: Educação e total)."""
    return _carregar("rreo_a02_b6_vitoria_2024")


@pytest.fixture(scope="session")
def msc_afonso_2024() -> list[dict]:
    """MSC orçamentária real (MSCC, classe 6, dez/2024, ending_balance) de Afonso Cláudio.

    Recorte: todas as linhas dos estágios do empenho da função 12, as de receita do
    FUNDEB e 300 linhas de outras contas/funções (que o parser tem de ignorar).
    Valores de controle, do DCA do mesmo ente-ano: função 12 empenhada 49.699.516,59,
    liquidada 48.939.943,63, paga 48.708.923,11; FUNDEB fundo 28.116.758,90 +
    complementação 3.689.803,08.
    """
    return _carregar("msc_afonso_claudio_2024")


@pytest.fixture(scope="session")
def rreo_a01_vitoria() -> list[dict]:
    """RREO-Anexo 01 (tipo "RREO"), 6º bimestre, Vitória 2024 — linhas de receita, resposta real."""
    return _carregar("rreo_a01_b6_vitoria_2024")


@pytest.fixture(scope="session")
def rreo_a01_simplificado() -> list[dict]:
    """RREO-Anexo 01 (tipo "RREO Simplificado"), 6º bimestre, Afonso Cláudio 2024."""
    return _carregar("rreo_a01_b6_afonso_claudio_2024")


@pytest.fixture(scope="session")
def extrato_afonso_2024() -> list[dict]:
    """/extrato_entregas real de Afonso Cláudio, 2024 (37 linhas, Prefeitura e Câmara)."""
    return _carregar("extrato_entregas_afonso_claudio_2024")


@pytest.fixture(scope="session")
def pdf_siope():
    """PDFs reais do Anexo 8 do SIOPE, um por layout: {(IBGE6, ano): bytes}."""
    return {(p.name.split("_")[3], int(p.stem.split("_")[-1])): p.read_bytes()
            for p in FIXTURES.glob("siope_RREO_Municipal_*.pdf")}


def linha(conta: str, coluna: str, valor: float, *, cod_conta: str = "X", anexo: str = "A",
          rotulo: str = "R", populacao: int | None = 1000) -> dict:
    """Linha sintética no formato de `/dca` e `/rreo`."""
    return {"anexo": anexo, "rotulo": rotulo, "cod_conta": cod_conta, "conta": conta,
            "coluna": coluna, "valor": valor, "populacao": populacao}
