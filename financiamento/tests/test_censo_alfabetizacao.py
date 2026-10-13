"""Censo no recorte da alfabetização: etapa, salas e espaço de leitura. Sem rede e sem banco."""

import pandas as pd
import pytest

from financiamento.etl import censo_alfabetizacao as censo

COLUNAS = ["ano", "co_entidade", "co_municipio", "tp_dependencia", "tp_situacao_funcionamento",
           "qt_salas_utilizadas", "qt_salas_leitura", "in_biblioteca", "in_sala_leitura",
           "in_biblioteca_sala_leitura", "qt_mat_fund_ai", "qt_mat_fund_ai_1", "qt_mat_fund_ai_2",
           "qt_tur_fund_ai", "qt_tur_fund_ai_1", "qt_tur_fund_ai_2"]


def escola(**kw):
    base = {"ano": 2025, "co_entidade": 32000001, "co_municipio": 3205309, "tp_dependencia": 3,
            "tp_situacao_funcionamento": 1, "qt_salas_utilizadas": 10, "qt_salas_leitura": 1,
            "in_biblioteca": 0, "in_sala_leitura": 1, "in_biblioteca_sala_leitura": 0,
            "qt_mat_fund_ai": 200, "qt_mat_fund_ai_1": 40, "qt_mat_fund_ai_2": 45,
            "qt_tur_fund_ai": 8, "qt_tur_fund_ai_1": 2, "qt_tur_fund_ai_2": 2}
    base.update(kw)
    return base


def quadro(linhas):
    return pd.DataFrame(linhas).reindex(columns=COLUNAS)


def test_rede_e_situacao_sao_traduzidas():
    d = censo.preparar(quadro([escola(), escola(co_entidade=2, tp_dependencia=2),
                               escola(co_entidade=3, tp_situacao_funcionamento=3)]))
    assert list(d["rede"]) == ["municipal", "estadual", "municipal"]
    assert list(d["em_atividade"]) == [True, True, False]


def test_espaco_de_leitura_reune_os_tres_marcadores_do_censo():
    """Exigir só `in_biblioteca` deixaria de fora a escola que tem sala de leitura."""
    d = censo.preparar(quadro([
        escola(co_entidade=1, in_biblioteca=1, in_sala_leitura=0, in_biblioteca_sala_leitura=0),
        escola(co_entidade=2, in_biblioteca=0, in_sala_leitura=1, in_biblioteca_sala_leitura=0),
        escola(co_entidade=3, in_biblioteca=0, in_sala_leitura=0, in_biblioteca_sala_leitura=1),
        escola(co_entidade=4, in_biblioteca=0, in_sala_leitura=0, in_biblioteca_sala_leitura=0),
    ]))
    assert list(d["tem_sala_leitura"]) == [True, True, True, False]
    assert list(d["tem_biblioteca"]) == [True, False, False, False]


def test_coluna_ausente_no_leiaute_antigo_vira_na_e_nao_zero():
    """Em 2021-2022 o Censo não desdobra o ano escolar: somar zeros diria 'nenhuma matrícula'."""
    d = censo.preparar(quadro([escola(ano=2021, qt_mat_fund_ai_1=None, qt_mat_fund_ai_2=None,
                                      qt_tur_fund_ai_1=None, qt_tur_fund_ai_2=None)]))
    m = censo.por_municipio(d)
    assert pd.isna(m["mat_1_2_ano"].iloc[0])
    assert pd.isna(m["turmas_1_2_ano"].iloc[0])
    assert m["mat_anos_iniciais"].iloc[0] == 200         # o total dos anos iniciais existe


def test_agrega_a_rede_municipal_e_soma_1_e_2_ano():
    d = censo.preparar(quadro([escola(co_entidade=1), escola(co_entidade=2, qt_mat_fund_ai_1=10,
                                                             qt_mat_fund_ai_2=12, qt_tur_fund_ai_1=1,
                                                             qt_tur_fund_ai_2=1)]))
    m = censo.por_municipio(d).iloc[0]
    assert m["escolas"] == 2
    assert m["mat_1_2_ano"] == 40 + 45 + 10 + 12
    assert m["turmas_1_2_ano"] == 2 + 2 + 1 + 1


def test_escola_estadual_nao_entra_na_rede_municipal():
    d = censo.preparar(quadro([escola(co_entidade=1), escola(co_entidade=2, tp_dependencia=2)]))
    assert censo.por_municipio(d)["escolas"].iloc[0] == 1


def test_escola_fechada_nao_entra():
    d = censo.preparar(quadro([escola(co_entidade=1), escola(co_entidade=2, tp_situacao_funcionamento=3)]))
    assert censo.por_municipio(d)["escolas"].iloc[0] == 1


def test_denominador_do_espaco_de_leitura_e_a_rede_que_alfabetiza():
    """Escola sem anos iniciais (só creche, por exemplo) não entra no denominador."""
    d = censo.preparar(quadro([
        escola(co_entidade=1, in_sala_leitura=1),
        escola(co_entidade=2, in_sala_leitura=0),
        escola(co_entidade=3, qt_mat_fund_ai=0, in_sala_leitura=0),
    ]))
    m = censo.por_municipio(d).iloc[0]
    assert m["escolas_anos_iniciais"] == 2
    assert m["pct_escolas_com_leitura"] == pytest.approx(50.0)


def test_valor_de_referencia_do_cantinho_usa_a_resolucao_do_fnde():
    d = censo.preparar(quadro([escola(qt_salas_utilizadas=10)]))
    m = censo.por_municipio(d).iloc[0]
    assert m["salas_anos_iniciais"] == 10
    assert m["valor_referencia_cantinho"] == pytest.approx(10 * censo.VALOR_CANTINHO_POR_SALA)
    assert censo.VALOR_CANTINHO_POR_SALA == 1235.00


def test_primeiro_ano_por_corte_e_medido_e_nao_presumido():
    """Matrícula desdobra 1º/2º ano desde 2023; turma, só em 2025 (medido no banco)."""
    assert censo.PRIMEIRO_ANO == {"matriculas": 2023, "turmas": 2025}


def test_tabela_vazia_nao_quebra():
    assert censo.preparar(pd.DataFrame()).empty
    assert censo.por_municipio(pd.DataFrame()).empty
