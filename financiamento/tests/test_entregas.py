"""Completude das entregas: prazos da LRF, fuso e situação — com o extrato real de Afonso Cláudio 2024. Sem rede."""

from datetime import date

import pandas as pd
import pytest

from financiamento.etl import entregas


@pytest.mark.parametrize("tipo, ano, periodo, periodicidade, esperado", [
    ("RREO", 2024, 1, "B", date(2024, 3, 30)),   # fev/2024 tem 29 dias: 29/02 + 30 = 30/03
    ("RREO", 2023, 1, "B", date(2023, 3, 30)),
    ("RREO", 2024, 6, "B", date(2025, 1, 30)),
    ("RGF", 2024, 1, "Q", date(2024, 5, 30)),
    ("RGF", 2024, 3, "Q", date(2025, 1, 30)),
    ("RGF", 2024, 1, "S", date(2024, 7, 30)),    # semestral (art. 63)
    ("DCA", 2024, 1, "A", date(2025, 4, 30)),
])
def test_prazos_da_lrf(tipo, ano, periodo, periodicidade, esperado):
    assert entregas.prazo(tipo, ano, periodo, periodicidade) == esperado


def test_entrega_na_madrugada_utc_conta_no_dia_anterior_em_brasilia():
    assert entregas.data_local("2024-05-31T02:30:00Z") == date(2024, 5, 30)


def test_situacoes_do_extrato_real(extrato_afonso_2024):
    df = pd.DataFrame(entregas.situacoes(extrato_afonso_2024, 3200102, 2024, date(2026, 9, 22)))
    # 1 DCA + 6 RREO + 2 RGF semestrais da Prefeitura + 2 da Câmara
    assert len(df) == 11
    assert set(df["relatorio"]) == {"DCA", "RREO", "RGF"}
    atrasado = df[df["situacao"] == "entregue_com_atraso"]
    assert len(atrasado) == 1
    a = atrasado.iloc[0]
    assert (a["poder"], a["relatorio"], a["periodo"]) == ("Câmara", "RGF", 1)
    assert a["prazo"] == "2024-07-30" and a["data_local"] == "2024-11-27" and a["dias_atraso"] == 120
    assert (df["situacao"] == "no_prazo").sum() == 10


def test_obrigacao_sem_registro_e_nao_entregue_ou_prazo_aberto():
    so_dca = [{"entregavel": "Balanço Anual (DCA)", "instituicao": "Prefeitura Municipal de X - ES", "periodo": 1,
               "periodicidade": "A", "status_relatorio": "HO", "data_status": "2025-04-10T12:00:00Z"}]
    df = pd.DataFrame(entregas.situacoes(so_dca, 1, 2024, date(2026, 1, 1)))
    rreo = df[df["relatorio"] == "RREO"]
    assert (rreo["situacao"] == "nao_entregue").all() and rreo["dias_atraso"].gt(0).all()
    cedo = pd.DataFrame(entregas.situacoes(so_dca, 1, 2024, date(2024, 2, 1)))
    assert (cedo.loc[cedo["relatorio"] == "RREO", "situacao"] == "prazo_aberto").all()
    # Sem RGF no extrato, a periodicidade quadrimestral é assumida — e isso fica anotado.
    rgf = df[df["relatorio"] == "RGF"]
    assert len(rgf) == 6 and rgf["observacao"].notna().all()


def test_retificado_nao_e_afirmado_como_atraso():
    reg = [{"entregavel": "Relatório Resumido de Execução Orçamentária", "instituicao": "Prefeitura Municipal de X",
            "periodo": 1, "periodicidade": "B", "status_relatorio": "RE", "data_status": "2024-12-01T12:00:00Z"}]
    df = pd.DataFrame(entregas.situacoes(reg, 1, 2024, date(2026, 1, 1)))
    b1 = df[(df["relatorio"] == "RREO") & (df["periodo"] == 1)].iloc[0]
    assert b1["situacao"] == "retificado" and pd.isna(b1["dias_atraso"])


def test_resumo_marca_municipio_irregular(extrato_afonso_2024):
    df = pd.DataFrame(entregas.situacoes(extrato_afonso_2024, 3200102, 2024, date(2026, 9, 22)))
    r = entregas.resumo_por_municipio(df).iloc[0]
    assert r["com_atraso"] == 1 and r["nao_entregues"] == 0 and bool(r["irregular"])
    assert r["maior_atraso_dias"] == 120


@pytest.mark.parametrize("texto, tipo", [
    ("Balanço Anual (DCA)", "DCA"), ("Relatório Resumido de Execução Orçamentária", "RREO"),
    ("Relatório de Gestão Fiscal Simplificado", "RGF"), ("MSC Agregada", "MSC"), ("Outro", None),
])
def test_tipo_do_entregavel(texto, tipo):
    assert entregas.tipo_entregavel(texto) == tipo
