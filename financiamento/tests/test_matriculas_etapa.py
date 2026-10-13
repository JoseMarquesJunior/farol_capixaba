"""Matrículas da rede municipal por etapa (Censo) como denominador do R$ por matrícula de uma subfunção.

Só o Ensino Fundamental (12.361) e o Ensino Médio (12.362) têm denominador próprio; as
demais subfunções seguem divididas pelo total. Sem banco: as tabelas do Censo são simuladas.
"""

import pandas as pd

from financiamento.etl import composicao, escolas
from financiamento.etl.indicadores import INDICADORES
from financiamento.etl.proveniencia import Registro


def _censo():
    return {"matriculas_etapa": pd.DataFrame({
        "ano": [2025, 2025, 2024], "co_municipio": [3205309, 3205002, 3205309],
        "qt_mat_bas": [40913, 68712, 41388], "qt_mat_fund": [25425, 46177, 25360], "qt_mat_med": [0, 0, 0]})}


def test_matriculas_por_etapa_soma_por_municipio_e_ano():
    m = escolas.matriculas_por_etapa(_censo())
    assert list(m.columns) == ["cod_ibge", "ano", "mat_total", "mat_fund", "mat_med"]
    vit = m[(m["cod_ibge"] == 3205309) & (m["ano"] == 2025)].iloc[0]
    assert (vit["mat_total"], vit["mat_fund"], vit["mat_med"]) == (40913, 25425, 0)   # zero é zero de verdade
    assert len(m) == 3


def test_sem_tabela_do_censo_devolve_vazio_com_as_colunas():
    m = escolas.matriculas_por_etapa({"escolas": pd.DataFrame()})
    assert m.empty and list(m.columns) == escolas.COLUNAS_MATRICULAS_ETAPA


def test_compor_leva_as_matriculas_por_etapa_com_a_consulta_do_censo(monkeypatch):
    monkeypatch.setattr(escolas, "extrair_censo", lambda **k: ({**_censo(), "escolas": pd.DataFrame()}, None, None))
    monkeypatch.setattr(escolas, "cadastro_escolas", lambda t: pd.DataFrame(columns=escolas.COLUNAS_CADASTRO))
    r = escolas.compor(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    assert list(r.matriculas_etapa.columns) == escolas.COLUNAS_MATRICULAS_ETAPA
    assert len(r.matriculas_etapa) == 3 and r.status["matriculas_etapa"] == 3


def _anual():
    return pd.DataFrame({"cod_ibge": [3205309, 3205309, 3200102], "ano": [2025, 2024, 2025], "esfera": ["M", "M", "M"],
                         "ente": ["Vitória", "Vitória", "Afonso Cláudio"], "tcees_alunos": [40913, 41388, 3682],
                         "q_dca_ie": ["a1", "a2", "a3"]})


def test_aplicar_matriculas_etapa_junta_por_ente_ano_e_deixa_sem_dado_quem_nao_tem_censo():
    m = escolas.matriculas_por_etapa(_censo()).assign(q="c1")
    a = composicao.aplicar_matriculas_etapa(_anual(), m)
    vit25 = a[(a["cod_ibge"] == 3205309) & (a["ano"] == 2025)].iloc[0]
    assert (vit25["censo_mat_total"], vit25["censo_mat_fund"], vit25["censo_mat_med"], vit25["q_censo_mat"]) == (40913, 25425, 0, "c1")
    afonso = a[a["cod_ibge"] == 3200102].iloc[0]
    assert pd.isna(afonso["censo_mat_fund"]) and afonso["q_censo_mat"] is None   # sem linha no Censo: sem dado, não zero


def test_aplicar_sem_censo_cria_as_colunas_vazias():
    a = composicao.aplicar_matriculas_etapa(_anual(), pd.DataFrame())
    assert set(composicao.COLUNAS_MATRICULAS_ETAPA) <= set(a.columns) and a["censo_mat_fund"].isna().all()


def test_consolidado_tem_a_matricula_da_etapa_e_o_valor_por_matricula_so_do_fundamental_e_do_medio():
    a = composicao.aplicar_matriculas_etapa(_anual(), escolas.matriculas_por_etapa(_censo()).assign(q="c1"))
    sub = pd.DataFrame({"cod_ibge": [3205309, 3205309, 3205309], "ano": [2025, 2025, 2025], "q": ["a1"] * 3,
                        "codigo": ["12.361", "12.362", "12.365"], "nome": ["Ensino Fundamental", "Ensino Médio", "Educação Infantil"],
                        "empenhada": [508500.0, 1000.0, 2000.0], "liquidada": [0.0] * 3, "paga": [0.0] * 3})
    c = composicao.Consolidador(Registro(), {3205309: "Vitória", 3200102: "Afonso Cláudio"}, {})
    composicao._consolidar_matriculas_etapa(c, a, sub)
    t = c.tabela()
    mats = t[t["indicador"] == "matriculas_etapa_censo"]
    assert sorted(mats["detalhe"].unique()) == ["ensino fundamental", "ensino médio"]
    assert len(mats) == 4                                   # Vitória 2025 e 2024 × duas etapas; Afonso Cláudio sem Censo
    pm = t[t["indicador"] == "subfuncao_por_matricula_etapa"]
    assert len(pm) == 1                                     # médio: zero matrículas → sem dado; infantil: não se desdobra
    assert pm.iloc[0]["valor"] == 20.0 and pm.iloc[0]["detalhe"].startswith("12.361")
    assert "a1" in pm.iloc[0]["consultas"] and "c1" in pm.iloc[0]["consultas"]   # DCA I-E e Censo, os dois lados


def test_indicadores_novos_estao_no_catalogo_com_localizacao_e_calculo():
    for ind in ("matriculas_etapa_censo", "subfuncao_por_matricula_etapa"):
        assert {"rotulo", "tema", "fonte", "unidade", "localizacao", "calculo"} <= set(INDICADORES[ind])
    assert "{detalhe}" in INDICADORES["matriculas_etapa_censo"]["localizacao"]
