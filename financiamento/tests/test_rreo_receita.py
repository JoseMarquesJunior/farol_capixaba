"""RREO Anexo 01 (receita por categoria), com respostas reais dos dois tipos de RREO. Sem rede."""

import pytest

from financiamento.etl import rreo_receita


def test_receita_de_vitoria_2024(rreo_a01_vitoria):
    r = rreo_receita.receita_a01(rreo_a01_vitoria)
    # Impostos próprios = item 1 ("receita de impostos") do Anexo 8 do SIOPE, ao centavo.
    assert r["impostos"] == pytest.approx(1_247_123_412.89, abs=0.01)
    assert r["receita_total"] > r["receitas_correntes"] > r["transferencias_correntes"] > 0
    partes = ("transf_correntes_uniao", "transf_correntes_estados", "transf_correntes_outras_publicas",
              "transf_correntes_privadas", "transf_correntes_demais")
    assert sum(r.get(p, 0.0) for p in partes) == pytest.approx(r["transferencias_correntes"], abs=1.0)


def test_simplificado_nao_inventa_linha_ausente(rreo_a01_simplificado):
    r = rreo_receita.receita_a01(rreo_a01_simplificado)
    assert r["receita_total"] > 0 and r["impostos"] > 0
    assert "transf_correntes_privadas" not in r  # o Simplificado não traz a linha: fica sem dado, não zero


def test_anexo_sem_receita_devolve_none():
    assert rreo_receita.receita_a01([]) is None
    assert rreo_receita.receita_a01([{"cod_conta": "Impostos", "coluna": "PREVISÃO INICIAL", "valor": 1.0}]) is None


def test_coluna_errada_nao_e_lida_como_realizada(rreo_a01_vitoria):
    so_previsao = [l for l in rreo_a01_vitoria if not l["coluna"].startswith("Até o Bimestre")]
    assert rreo_receita.receita_a01(so_previsao) is None
