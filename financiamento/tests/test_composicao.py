"""Composição do painel de auditoria: origem da receita, conformidade, consolidado e validação. Sem rede."""

import pandas as pd
import pytest

from financiamento.etl import composicao
from financiamento.etl.proveniencia import Consulta, Registro

COD, ANO = 3200102, 2024


def _receita_b6(total=1000.0, impostos=100.0):
    return pd.DataFrame([{"cod_ibge": COD, "ano": ANO, "bimestre": 6, "tipo_rreo": "RREO", "q": "qa01",
                          "receita_total": total, "impostos": impostos}])


def _msc(fundeb=300.0):
    return pd.DataFrame([{"cod_ibge": COD, "ano": ANO, "fundeb_msc_total": fundeb, "q_msc": "qmsc"}])


def _repasses(valor=50.0, destino="municipio"):
    return pd.DataFrame([{"cod_ibge": COD, "ano": ANO, "programa": "pnae", "destino": destino, "valor": valor,
                          "meses": 10, "q": "qm1;qm2"}])


def _anual(**kw):
    base = {"cod_ibge": COD, "ente": "Afonso Cláudio", "esfera": "M", "ano": ANO, "fundeb_receita": 290.0,
            "q_dca_ic": "qic", "q_dca_ie": "qie", "desp_educacao_empenhada": 1000.0, "mde_aplicado_pct": None,
            "mde_fonte": None, "mde_verificado_em": None}
    return pd.DataFrame([{**base, **kw}])


def _origem(**kw):
    args = {"receita_bim": _receita_b6(), "tabela_msc": _msc(), "repasses": _repasses(), "anual": _anual()}
    args.update(kw)
    o = composicao.receita_origem(args["receita_bim"], args["tabela_msc"], args["repasses"], args["anual"], [COD], [ANO])
    return o.set_index("categoria")


def test_origem_particiona_a_receita_total():
    o = _origem()
    assert o.loc["impostos_proprios", "valor"] == 100.0
    assert o.loc["fundeb", "valor"] == 300.0 and o.loc["fundeb", "fonte"] == "SICONFI — MSC"
    assert o.loc["federal_especifica", "valor"] == 50.0
    assert o.loc["outras", "valor"] == 550.0  # 1000 − 100 − 300 − 50
    assert o.loc[["impostos_proprios", "fundeb", "federal_especifica", "outras"], "valor"].sum() == o.loc["total", "valor"]


def test_sem_msc_o_fundeb_vem_do_dca_e_a_fonte_fica_registrada():
    o = _origem(tabela_msc=pd.DataFrame(columns=["cod_ibge", "ano", "fundeb_msc_total", "q_msc"]))
    assert o.loc["fundeb", "valor"] == 290.0 and "DCA" in o.loc["fundeb", "fonte"]


def test_componente_ausente_nao_gera_resto():
    o = _origem(repasses=pd.DataFrame(columns=["cod_ibge", "ano", "programa", "destino", "valor", "meses", "q"]))
    assert pd.isna(o.loc["federal_especifica", "valor"]) and pd.isna(o.loc["outras", "valor"])


def test_pdde_pago_as_escolas_nao_entra_na_receita_do_municipio():
    o = _origem(repasses=_repasses(destino="escolas"))
    assert pd.isna(o.loc["federal_especifica", "valor"])


def _siope(**kw):
    base = {"cod_ibge": COD, "ano": ANO, "status_siope": "ok", "q": "qsiope", "mde_pct": 26.0, "mde_exigido": 1.0,
            "mde_aplicado": 1.04, "fundeb70_pct": 69.5, "despesa_total_educacao": 900.0,
            "pdf_publicado_em": "2025-02-19T11:06:53+00:00", "itens_usados": "{}"}
    return pd.DataFrame([{**base, **kw}])


def test_siope_tem_precedencia_sobre_o_manual_e_divergencia_e_apontada():
    a = composicao.aplicar_siope(_anual(mde_aplicado_pct=24.0, mde_fonte="manual", mde_verificado_em="2026-01-01"),
                                 _siope()).iloc[0]
    assert a["mde_aplicado_pct"] == 26.0 and a["mde_situacao"] == "siope"
    assert bool(a["mde_divergente_manual"]) and a["mde_abaixo_minimo"] is False
    assert a["fundeb70_abaixo_minimo"] is True  # 69,5% < 70%


def test_sem_siope_vale_o_manual():
    a = composicao.aplicar_siope(_anual(mde_aplicado_pct=24.0, mde_fonte="manual", mde_verificado_em="2026-01-01"),
                                 _siope().iloc[0:0]).iloc[0]
    assert a["mde_situacao"] == "informado_manual" and a["mde_abaixo_minimo"] is True


def test_divergencia_funcao12_siope():
    a = composicao.aplicar_siope(_anual(), _siope()).iloc[0]
    assert a["divergencia_funcao12_siope_pct"] == 10.0 and a["divergencia_funcao12_siope_rs"] == 100.0


def test_kpis_do_topo():
    a = composicao.aplicar_siope(_anual(), _siope(mde_pct=24.0))
    a = composicao.aplicar_entregas(a, pd.DataFrame([{"cod_ibge": COD, "ano": ANO, "situacao": "entregue_com_atraso",
                                                      "dias_atraso": 5}]))
    k = composicao.kpis_conformidade(a)[str(ANO)]
    assert k["mde_abaixo"] == 1 and k["fundeb70_abaixo"] == 1 and k["entregas_irregulares"] == 1
    assert k["maior_divergencia"]["cod_ibge"] == COD and k["maior_divergencia"]["pct"] == 10.0


# ------------------------------------------------------------------ consolidado e validação

def _registro():
    r = Registro()
    for cid_url in ("dca?an_exercicio=2024&id_ente=3200102&no_anexo=I-E", "dca?an_exercicio=2024&id_ente=3200102&no_anexo=I-C"):
        r.adicionar(Consulta(fonte="SICONFI", recurso="dca", descricao="d", url=f"https://api/{cid_url}",
                             obtido_em="2026-09-22T10:00:00+00:00", arquivo="2024/dca/x.json.gz"))
    return r


def test_cada_registro_carrega_valor_fonte_endpoint_parametros_e_instante():
    reg = _registro()
    ie = reg.todas()[1].id if "I-E" in reg.todas()[1].url else reg.todas()[0].id
    c = composicao.Consolidador(reg, {COD: "Afonso Cláudio"}, {ANO: {"dca_despesa_funcao": "DCA-Anexo I-E"}})
    c.add("desp_educacao_empenhada", COD, ANO, 1000.0, ie)
    t = c.tabela().iloc[0]
    assert t["valor"] == 1000.0 and t["fonte"] == "SICONFI"
    assert t["endpoint"] == "https://api/dca"
    assert "id_ente=3200102" in t["parametros"] and t["obtido_em"] == "2026-09-22T10:00:00+00:00"
    assert '"12 - Educação"' in t["localizacao"] and "DCA-Anexo I-E" in t["localizacao"]


def test_valor_ausente_nao_vira_registro():
    c = composicao.Consolidador(_registro(), {}, {})
    c.add("desp_educacao_empenhada", COD, ANO, None, "x")
    c.add("desp_educacao_empenhada", COD, ANO, float("nan"), "x")
    assert c.tabela().empty


def _consolidado(linhas):
    base = {"ente": "X", "periodo": None, "detalhe": None, "consultas": "q1"}
    return pd.DataFrame([{**base, **l} for l in linhas])


def test_validacao_aponta_negativo_inesperado_e_aceita_o_esperado():
    df = _consolidado([
        {"cod_ibge": COD, "ano": ANO, "indicador": "desp_educacao_empenhada", "valor": -5.0},  # inesperado
        {"cod_ibge": COD, "ano": ANO, "indicador": "fundeb_liquido", "valor": -5.0},           # saldo pode ser negativo
        {"cod_ibge": COD, "ano": ANO, "indicador": "dif_rreo_dca_pct", "valor": -1.2},
    ])
    v = composicao.validar(df)
    assert v["n_negativos_inesperados"] == 1
    assert v["negativos_inesperados"][0]["indicador"] == "desp_educacao_empenhada"


def test_validacao_de_codigo_ibge():
    assert composicao.validar(_consolidado([{"cod_ibge": 3205309, "ano": ANO, "indicador": "populacao", "valor": 1},
                                            {"cod_ibge": 32, "ano": ANO, "indicador": "populacao", "valor": 1}]))["ibge_7_digitos"]
    assert not composicao.validar(_consolidado([{"cod_ibge": 320530, "ano": ANO, "indicador": "populacao",
                                                 "valor": 1}]))["ibge_7_digitos"]


def test_registro_sem_consulta_e_contado():
    df = _consolidado([{"cod_ibge": COD, "ano": ANO, "indicador": "populacao", "valor": 1, "consultas": ""}])
    assert composicao.validar(df)["sem_proveniencia"] == 1


def test_conferencias_cruzadas_contam_o_que_bate():
    a = _anual(msc_empenhada=1000.0, fundeb_msc_total=290.4, fundeb_principal=None, despesa_total_educacao=1000.0)
    c = composicao.conferencias_cruzadas(a)
    assert c["msc_x_dca_funcao12"]["batem"] == 1
    assert c["fundeb_msc_x_dca"]["batem"] == 1          # 0,40 < R$ 1,00
    assert c["fundeb_siope_x_dca"]["comparaveis"] == 0  # sem SIOPE: não é comparável, não é "bate"


@pytest.mark.parametrize("valor", [0.0, 1.0])
def test_zero_e_valor_legitimo_nao_ausencia(valor):
    c = composicao.Consolidador(_registro(), {}, {})
    c.add("fundeb_complementacao_uniao", COD, ANO, valor, "q")
    assert len(c.tabela()) == 1


# ------------------------------------------------------------------ TCE-ES

def _obras_tce():
    return pd.DataFrame({"cod_ibge": [COD, COD, COD], "chave": ["k1", "k2", "k3"], "valor": [100.0, 200.0, 300.0],
                         "situacao": ["Paralisação presumida", "Paralisada", "Concluída e recebida provisoriamente"]})


def test_mde_do_tcees_ao_lado_do_siope_e_quando_cruzam_o_minimo():
    a = _anual(siope_mde_pct=25.4, q_siope="qs")
    mde = pd.DataFrame([{"cod_ibge": COD, "ano": ANO, "tcees_mde_pct": 24.8, "tcees_mde_aplicado": 10.0}])
    emp = pd.DataFrame([{"cod_ibge": COD, "ano": ANO, "tcees_emp_empenhada": 999.5, "tcees_emp_paga": 900.0,
                         "tcees_emp_meses": 12, "tcees_emp_meses_ausentes": ""}])
    r = composicao.aplicar_tcees(a, mde, pd.DataFrame(), _obras_tce(), {"educacao": "qt", "empenhos": {ANO: ["p1", "p2"]}},
                                 emp).iloc[0]
    assert r.div_mde_tcees_siope_pp == pytest.approx(-0.6) and r.mde_cruza_minimo and r.tcees_mde_abaixo_minimo
    assert r.q_tcees_mde == "qt" and r.q_tcees_emp == "p1;p2"
    assert (r.obras_educacao, r.obras_paralisadas) == (3, 2)
    c = composicao.conferencias_cruzadas(pd.DataFrame([r]))
    assert c["empenhos_tcees_x_dca"]["batem"] == 1 and c["mde_tcees_x_siope"]["batem"] == 0
    # ano sem dezembro no arquivo do TCE-ES: não entra na conferência, é contado à parte
    c = composicao.conferencias_cruzadas(pd.DataFrame([r]).assign(tcees_emp_meses=11, tcees_emp_empenhada=900.0))
    assert c["empenhos_tcees_x_dca"]["comparaveis"] == 0 and c["empenhos_tcees_x_dca"]["incompletos"] == 1


def test_sem_dado_do_tcees_nada_vira_zero():
    r = composicao.aplicar_tcees(_anual(siope_mde_pct=30.0), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}).iloc[0]
    assert pd.isna(r.tcees_mde_pct) and r.mde_cruza_minimo is None and pd.isna(r.obras_educacao)
    assert pd.isna(r.desp_educacao_por_matricula)          # sem matrículas não há denominador: fica vazio


def test_despesa_por_matricula_usa_os_alunos_do_tribunal():
    """O segundo denominador da comparação: matrícula em vez de habitante."""
    mde = pd.DataFrame([{"cod_ibge": COD, "ano": ANO, "tcees_mde_pct": 26.0, "tcees_alunos": 500}])
    r = composicao.aplicar_tcees(_anual(), mde, pd.DataFrame(), pd.DataFrame(), {"educacao": "qt"}).iloc[0]
    assert r.desp_educacao_por_matricula == pytest.approx(2.0)      # 1.000,00 ÷ 500 matrículas
    zero = pd.DataFrame([{"cod_ibge": COD, "ano": ANO, "tcees_mde_pct": 26.0, "tcees_alunos": 0}])
    r = composicao.aplicar_tcees(_anual(), zero, pd.DataFrame(), pd.DataFrame(), {"educacao": "qt"}).iloc[0]
    assert pd.isna(r.desp_educacao_por_matricula)                   # rede sem matrícula não vira divisão por zero


def test_matriculas_do_tribunal_sao_conferidas_contra_o_censo():
    """O denominador só se sustenta se for o do Censo — a conferência diz quando não é."""
    anual = pd.concat([_anual(tcees_alunos=500), _anual(cod_ibge=3205309, ente="Vitória", tcees_alunos=900)],
                      ignore_index=True)
    escolas = pd.DataFrame({"co_entidade": [1, 2, 3], "cod_ibge": [COD, COD, 3205309], "rede": ["municipal"] * 3,
                            "ano_censo": [ANO] * 3, "matriculas": [200.0, 300.0, 800.0]})
    c = composicao.conferencia_matriculas(anual, escolas)
    assert c["ano"] == ANO and c["comparaveis"] == 2 and c["batem"] == 1
    assert c["maiores"][0]["cod_ibge"] == 3205309 and c["maiores"][0]["dif"] == 100
    assert composicao.conferencia_matriculas(anual, pd.DataFrame())["comparaveis"] == 0


def test_kpis_de_obras_separam_paralisacao_presumida_da_declarada():
    k = composicao.kpis_obras(_obras_tce())
    assert (k["paralisadas"], k["presumidas"], k["declaradas"]) == (2, 1, 1)
    assert k["paralisadas_valor"] == 300.0


def test_consolidado_do_tcees_cnca_e_escolas_tem_proveniencia():
    reg = _registro()
    q = reg.todas()[0].id
    c = composicao.Consolidador(reg, {COD: "Afonso Cláudio", 32: "Espírito Santo"}, {})
    anual = _anual(tcees_mde_pct=26.0, tcees_mde_aplicado=10.0, div_mde_tcees_siope_pp=1.0, q_tcees_mde=q, q_siope=q,
                   tcees_emp_empenhada=5.0, q_tcees_emp=q, tcees_alunos=500, desp_educacao_por_matricula=2.0)
    vazio = pd.DataFrame()
    obras = _obras_tce().assign(assinatura="2024-02-01", contratacao="C", objeto="Reforma", contratado="X", q=q,
                                valor_medido=[50.0, None, None], medicoes=[1, None, None], ultima_medicao="2024-05-01")
    cred = pd.DataFrame([{"cod_ibge": COD, "ano": ANO, "credor": "1", "credor_nome": "A", "empenhada": -3.0,
                          "elemento": "39", "fonte": "1500", "q": q}])
    cnca_t = {"municipio": pd.DataFrame([{"cod_ibge": COD, "ano": ANO, "pdde_cnca": 10.0, "pdde_alfabetizacao": None, "q": q}]),
              "estado": pd.DataFrame([{"ano": ANO, "mes": 3, "favorecido": "SEDU", "valor": 7.0, "q": q}])}
    escolas_t = pd.DataFrame({"co_entidade": [9], "cod_ibge": [COD], "nome": ["EMEF A"]})
    dinheiro = pd.DataFrame([{"co_entidade": 9, "ano": ANO, "canal": "pdde", "po": "000C", "po_nome": "CNCA", "detalhe": None,
                              "valor": 10.0, "q": q}])
    ca = pd.DataFrame([{"cod_ibge": COD, "ano": ANO, "CodigoAcao": "2001", "NomeAcao": "Manutenção", "credor": "1",
                        "credor_nome": "A", "elemento": "39", "fonte": "1500", "empenhada": -3.0, "paga": 0.0,
                        "demais": 0, "q": q}])
    itens = pd.DataFrame([{"cod_ibge": COD, "ano": ANO, "contratacao": "2024.X.01.0001", "chave": "k", "ug": "SEME",
                           "lote": "1", "item": "1", "descricao": "Merenda", "unidade": "Kg", "quantidade": 10.0,
                           "valor_unitario": 2.0, "valor_total": 20.0, "contratada": "X", "cnpj_contratada": "1",
                           "medicoes": 1.0, "quantidade_medida": 5.0, "valor_medido": 10.0, "aditivos": None,
                           "valor_alterado": None, "vinculo": "ug_educacao", "q": q}])
    composicao._consolidar_tcees(c, anual, {"pcm": vazio, "obras": obras, "dotacao": vazio,
                                            "empenhos": {"credores": cred, "credor_acao": ca},
                                            "itens": {"itens": itens}})
    composicao._consolidar_cnca(c, cnca_t)
    composicao._consolidar_escolas(c, escolas_t, dinheiro)
    ica_t = {"resultados": pd.DataFrame([{"cod_ibge": COD, "edicao": 2025, "ano": 2025, "taxa": 79.0, "meta": 70.0, "nivel": 4,
                                          "participacao": 97.0, "situacao": "informado", "q": q},
                                         {"cod_ibge": COD, "edicao": 2025, "ano": 2024, "taxa": None, "meta": 68.0, "nivel": None,
                                          "participacao": None, "situacao": "sem_dado", "q": q}]),
             "metas": pd.DataFrame([{"cod_ibge": COD, "edicao": 2025, "ano": 2026, "meta": 73.0, "q": q}])}
    composicao._consolidar_ica(c, ica_t)
    t = c.tabela()
    assert {"tcees_mde_pct", "obra_educacao", "obra_medido", "empenho_credor", "cnca_pdde", "cnca_estado",
            "escola_recurso", "matriculas_rede_municipal", "desp_educacao_por_matricula",
            "item_contratado", "empenho_credor_acao", "ica_taxa", "ica_meta", "ica_participacao"} <= set(t["indicador"])
    assert len(t[(t["indicador"] == "ica_taxa")]) == 1                # "sem dado" de 2024 não vira linha
    v = composicao.validar(t)
    assert v["sem_proveniencia"] == 0 and v["ibge_7_digitos"]
    assert v["n_negativos_inesperados"] == 0                  # saldo negativo de credor (anulação) é admitido
    assert set(t.loc[t["indicador"] == "cnca_estado", "cod_ibge"]) == {32}
