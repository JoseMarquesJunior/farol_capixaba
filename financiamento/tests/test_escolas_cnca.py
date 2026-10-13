"""Vínculo recebedor → escola do Censo (por nome) e o módulo automático do CNCA. Sem banco, sem rede."""

import json

import pandas as pd
import pytest

from financiamento.etl import cnca, escolas

CADASTRO = pd.DataFrame({
    "co_entidade": [1, 2, 3, 4, 5, 6],
    "nome": ["EMEF CORREGO DUMER", "CMEI CORREGO DUMER", "EMEF PROF MARIA DA SILVA", "EEEFM IRACEMA CONCEICAO SILVA",
             "EMEF SAO JOSE", "EMEF SAO JOSE DO SUL"],
    "cod_ibge": [3200102, 3200102, 3200102, 3205309, 3205309, 3205309],
    "rede": ["municipal", "municipal", "municipal", "estadual", "municipal", "municipal"],
    "lat": [-20.0, -20.01, -20.02, -20.3, -20.31, -20.5], "lon": [-41.0, -41.01, -41.02, -40.3, -40.31, -40.5],
})


@pytest.fixture(scope="module")
def casador():
    return escolas.Casador(CADASTRO)


def test_termos_ignoram_o_que_nao_distingue_a_escola():
    assert escolas.termos("CONSELHO DE ESCOLA DA EMEF PROF. MARIA DA SILVA") == ["maria", "silva"]


def test_rede_e_tipo_pelo_nome():
    assert escolas.rede_pelo_nome("CONSELHO DE ESCOLA DA EEEFM X") == "estadual"
    assert escolas.rede_pelo_nome("CAIXA ESCOLAR DA EMEF X") == "municipal"
    assert escolas.tipo_pelo_nome("CONSELHO DO CMEI X") == "ei" and escolas.tipo_pelo_nome("EMEFTI X") == "ef"


def test_casa_pelo_nome_no_mesmo_municipio(casador):
    co, nota, metodo = casador.casar("CONSELHO DE ESCOLA DA EMEF PROFESSORA MARIA DA SILVA", 3200102)
    assert co == 3 and nota >= escolas.LIMIAR and metodo == "nome"


def test_homonimas_desempatam_pelo_tipo_da_escola(casador):
    assert casador.casar("CONSELHO DE ESCOLA EMEF CORREGO DUMER", 3200102)[0] == 1
    assert casador.casar("CONSELHO DE ESCOLA DO CMEI CORREGO DUMER", 3200102)[0] == 2


def test_ambiguo_fica_sem_vinculo_em_vez_de_chute(casador):
    co, _, metodo = casador.casar("CAIXA ESCOLAR SAO JOSE", 3205309)   # "São José" e "São José do Sul"
    assert co in (5, None)
    co, _, metodo = casador.casar("CONSELHO ESCOLAR JOSE", 3205309)    # serve às duas
    assert co is None and metodo.startswith("ambíguo")


def test_nao_casa_em_outro_municipio(casador):
    assert casador.casar("CONSELHO DE ESCOLA DA EMEF CORREGO DUMER", 3205309)[0] is None


def test_escola_estadual_sem_municipio_procura_na_rede_estadual_com_exigencia_maior(casador):
    co, nota, metodo = casador.casar("CONSELHO DE ESCOLA DA EEEFM IRACEMA CONCEICAO SILVA", None)
    assert co == 4 and "rede estadual" in metodo
    assert casador.casar("CONSELHO DA EMEF SAO JOSE", None)[2] == "sem município"   # municipal sem município: não tenta


def test_obra_ligada_ao_predio_por_coordenada_so_com_nome_parcial(casador):
    bem = {"nome": "ESCOLA IRACEMA DA PENHA", "categoria": "Educacional", "lat": -20.3001, "lon": -40.3001}
    co, _, metodo = escolas.casar_bem(bem, 3205309, casador, CADASTRO)
    assert co == 4 and "proximidade" in metodo
    longe = {**bem, "lat": -20.9, "lon": -40.9}                          # mesmo nome parcial, a quilômetros
    assert escolas.casar_bem(longe, 3205309, casador, CADASTRO)[0] is None
    sem_nome = {**bem, "nome": "PREDIO PUBLICO"}                        # perto, mas nada no nome
    assert escolas.casar_bem(sem_nome, 3205309, casador, CADASTRO)[0] is None


def _pdde():
    return pd.DataFrame({
        "cod_ibge": [3200102, 3200102, 3200102, None], "ano": [2024, 2024, 2025, 2024],
        "po": ["000C", "0000", "000C", "000C"], "po_nome": ["PDDE - CNCA", "PDDE BÁSICO", "PDDE - CNCA", "PDDE - CNCA"],
        "cnpj_uex": ["11", "11", "22", "33"], "uex": ["CONSELHO EMEF CORREGO DUMER", "CONSELHO EMEF CORREGO DUMER",
                                                     "CONSELHO EMEF PROF MARIA DA SILVA", "CONSELHO EEEFM IRACEMA CONCEICAO SILVA"],
        "destino": ["escolas"] * 4, "valor": [1000.0, 500.0, 700.0, 900.0], "meses": [1, 1, 1, 1], "q": ["a", "b", "c", "d"]})


def test_compor_liga_pdde_a_escola_e_soma_por_plano(monkeypatch):
    monkeypatch.setattr(escolas, "extrair_censo", lambda **k: ({"escolas": pd.DataFrame(), "ideb": pd.DataFrame(),
                                                                "paebes": pd.DataFrame()}, None, None))
    monkeypatch.setattr(escolas, "cadastro_escolas", lambda t: CADASTRO.reindex(columns=escolas.COLUNAS_CADASTRO))
    r = escolas.compor(_pdde(), pd.DataFrame(), pd.DataFrame())
    assert r.status["vinculos"]["pdde"] == {"total": 3, "casados": 3}
    d = r.dinheiro.set_index(["co_entidade", "ano", "po"])["valor"]
    assert d[(1, 2024, "000C")] == 1000.0 and d[(1, 2024, "0000")] == 500.0 and d[(4, 2024, "000C")] == 900.0
    assert list(r.dinheiro.columns) == escolas.COLUNAS_DINHEIRO


def test_cnca_por_municipio_escolas_e_estado():
    t = cnca.compor(_pdde(), pd.DataFrame({"ano": [2024], "mes": [3], "favorecido": ["SEDU"], "cnpj": ["1"], "valor": [10.0],
                                           "q": ["e"]}), None)
    m = t["municipio"].set_index("ano")
    assert m.loc[2024, "pdde_cnca"] == 1000.0 and m.loc[2024, "escolas_cnca"] == 1   # o sem município não entra na soma municipal
    assert m.loc[2025, "pdde_cnca"] == 700.0
    assert len(t["escolas"]) == 3 and set(t["escolas"]["programa"]) == {"pdde_cnca"}  # a escola estadual sem município fica
    regs = cnca.programas_api(t["municipio"])["cnca"]["repasse"]
    assert {r["ano"] for r in regs} == {2024, 2025} and all(r["automatico"] and r["verificado"] for r in regs)
    json.dumps(regs)                                                                  # vai para o dataset


def test_grafia_vizinha_e_apostrofo_casam_mas_nomes_proximos_nao():
    cad = pd.DataFrame({"co_entidade": [7, 8, 9], "cod_ibge": [3205309] * 3, "rede": ["municipal"] * 3,
                        "nome": ["EMEF JUSCELINO KUBITSCHEK DE OLIVEIRA", "EMEF ORLANDINA DALMEIDA LUCAS", "EMEF JOAQUINA ROSA"],
                        "lat": [None] * 3, "lon": [None] * 3})
    c = escolas.Casador(cad)
    assert c.casar("CONSELHO DE ESCOLA DA EMEF JUSCELINO KUBITSCHECK DE OLIVEIRA", 3205309)[0] == 7
    assert c.casar("CONSELHO DE ESCOLA DA EMEF ORLANDINA D'ALMEIDA LUCAS", 3205309)[0] == 8
    assert c.casar("CAIXA ESCOLAR EMEF JOAQUIM ROSA", 3205309)[0] is None      # JOAQUIM ≠ JOAQUINA
