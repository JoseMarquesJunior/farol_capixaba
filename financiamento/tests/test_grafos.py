"""Redes do financiamento (etl/grafos.py) e a página que as desenha (build_grafos.py)."""

import json
import math
import re

import numpy as np
import pandas as pd
import pytest

from financiamento import build_grafos
from financiamento.etl import grafos as G
from financiamento.etl.tcees import Municipios


# ------------------------------------------------------------------ mercados
def _linha(el, sub, texto="manutencao das atividades", sf="361"):
    return {"CodigoElemento": el, "CodigoSubElemento": sub, "texto": texto, "CodigoSubFuncao": sf}


@pytest.mark.parametrize("linha, esperado", [
    (_linha("39", "32"), "transporte"),
    (_linha("33", "03"), "transporte"),
    (_linha("30", "01", "manutencao do transporte escolar"), "transporte"),   # combustível do transporte
    (_linha("39", "72", "manutencao do transporte escolar"), "beneficios"),   # vale-transporte não é transporte escolar
    (_linha("30", "07"), "alimentacao"),
    (_linha("39", "99", sf="306"), "alimentacao"),
    (_linha("37", "05"), "alimentacao"),
    (_linha("51", "91"), "obras"),
    (_linha("39", "16"), "obras"),
    (_linha("30", "23"), "kits"),
    (_linha("32", "99"), "kits"),
    (_linha("32", "04"), "didatico"),
    (_linha("30", "60"), "didatico"),
    (_linha("39", "99", "formacao continuada dos profissionais"), "didatico"),
    (_linha("37", "02"), "maoobra"),
    (_linha("40", "99"), "tic"),
    (_linha("52", "19"), "tic"),
    (_linha("52", "42"), "equipamentos"),
    (_linha("30", "16"), "consumo"),
    (_linha("46", "02"), "beneficios"),
    (_linha("39", "43"), "utilidades"),
    (_linha("43", "08"), "transferencias"),
    (_linha("39", "99"), "outros"),
])
def test_mercado_de_cada_natureza(linha, esperado):
    assert G.classificar_mercado(pd.DataFrame([linha])).iloc[0] == esperado


def test_todo_mercado_tem_rotulo_e_regra():
    assert len(set(G.ID_MERCADOS)) == len(G.MERCADOS)
    assert all(r and g for _, r, g in G.MERCADOS)


# ------------------------------------------------------------ tipos e origens
@pytest.mark.parametrize("nome, tipo", [
    ("CONSELHO DE ESCOLA DA EMEF MOACYR AVIDOS", "conselho"),
    ("CAIXA ESCOLAR ESCOLA PARQUE", "conselho"),
    ("ESPIRITO SANTO CENTRAIS ELETRICAS.S.A-ESCELSA", "concessionaria"),
    ("COMPANHIA ESPIRITO SANTENSE DE SANEAMENTO CESAN", "concessionaria"),
    ("PREFEITURA MUNICIPAL DE CARIACICA   ES", "publico"),
    ("MINISTRIO DA EDUCAO - FUNDO N. DES. DA EDUCAO", "publico"),   # como chega do TCE-ES, sem os acentos
    ("CONSORCIO PUBLICO REGIAO POLINORTE - CIM POLINORTE", "publico"),
    ("COOPE-SERRANA-COOP TRANSP SUL SERRANA CAPIXABA MAT", "terceiro"),
    ("INSTITUTO CONHECER.", "terceiro"),
    ("DISTRIBUIDORA DE HOTIFRUTIGRANJEIRO BERGER LTDA", "empresa"),
    ("EDITORA POSITIVO LTDA.", "empresa"),
])
def test_tipo_do_credor(nome, tipo):
    assert G.tipo_credor(nome) == tipo


@pytest.mark.parametrize("nome, grupo", [
    ("TRANSFERÊNCIAS DO FUNDEB - IMPOSTOS E TRANSFERÊNCIAS DE IMPOSTOS - 70%", "fundeb"),
    ("TRANSFERÊNCIAS DO FUNDEB ? IMPOSTOS 30%", "fundeb"),                       # código 113 de 2021–2022
    ("RECEITA DE IMPOSTOS E DE TRANSFERÊNCIA DE IMPOSTOS - EDUCAÇÃO", "impostos"),  # 111
    ("RECEITA DE IMPOSTOS E DE TRANSFERÊNCIA DE IMPOSTOS - MDE", "impostos"),       # 500
    ("RECURSOS ORDINÁRIOS", "impostos"),
    ("TRANSFERÊNCIA DO SALÁRIO EDUCAÇÃO", "fnde"),
    ("TRANSFERÊNCIAS DE RECURSOS DO FNDE REFERENTES AO PROGRAMA NACIONAL DE ALIMENTAÇÃO ESCOLAR (PNAE)", "fnde"),
    ("TRANSFERÊNCIAS DE RECURSOS DOS ESTADOS PARA PROGRAMAS DE EDUCAÇÃO", "estado"),
    ("TRANSFERÊNCIAS DO ESTADO REFERENTES A CONVÊNIOS E INSTRUMENTOS CONGÊNERES VINCULADOS À EDUCAÇÃO", "estado"),
    ("ROYALTIES E PARTICIPAÇÃO ESPECIAL DE PETRÓLEO E GÁS NATURAL VINCULADOS À EDUCAÇÃO", "outras"),
])
def test_origem_pelo_nome_da_fonte(nome, grupo):
    assert G.grupo_fonte(nome) == grupo


def test_raiz_do_cnpj():
    assert G.raiz_cnpj("05.427.772/0001-28") == "05427772"
    assert G.raiz_cnpj("05427772000128") == "05427772"
    assert G.raiz_cnpj("12345678901") is None       # CPF não é CNPJ
    assert G.raiz_cnpj("") is None


# ----------------------------------------------------------------- medidas
def test_hhi():
    assert G.hhi([100]) == pytest.approx(10000)
    assert G.hhi([50, 50]) == pytest.approx(5000)
    assert G.hhi([25, 25, 25, 25]) == pytest.approx(2500)
    assert G.hhi([0, -5]) is None


def test_pesos_de_newman():
    pares = G.pesos_newman({"a": [1, 2], "b": [1, 2, 3], "c": [4]})
    assert pares[(1, 2)] == (pytest.approx(1.0 + 0.5), 2)   # "a" liga com peso 1, "b" com 1/(3−1)
    assert pares[(1, 3)] == (pytest.approx(0.5), 1)
    assert (4, 4) not in pares and all(4 not in k for k in pares)   # quem atende um só não liga ninguém


def test_concordancia_entre_particoes():
    a = {1: "x", 2: "x", 3: "y", 4: "y"}
    b = {1: 0, 2: 0, 3: 1, 4: 1}            # mesma divisão, outros rótulos
    assert G.ari(a, b) == pytest.approx(1.0)
    assert G.nmi(a, b) == pytest.approx(1.0)
    c = {1: 0, 2: 1, 3: 0, 4: 1}            # cruzada
    assert G.ari(a, c) < 0.01
    assert G.nmi(a, c) == pytest.approx(0.0, abs=1e-9)


def test_comunidades_separam_dois_grupos_e_marcam_isolado():
    pares = {}
    for grupo in ((0, 1, 2), (3, 4, 5)):
        for i in grupo:
            for j in grupo:
                if i < j:
                    pares[(i, j)] = (1.0, 1)
    pares[(2, 3)] = (0.05, 1)               # uma ponte fraca
    rot, mod = G.comunidades(7, pares)
    assert rot[0] == rot[1] == rot[2] != rot[3] == rot[4] == rot[5]
    assert rot[6] == -1 and mod > 0.3
    assert G.comunidades(7, pares) == (rot, mod)   # semente fixa: a mesma divisão


# ------------------------------------------------------------------ geometria
def test_ponto_interior_de_poligono_concavo():
    u = {"type": "Polygon", "coordinates": [[[0, 0], [3, 0], [3, 3], [2, 3], [2, 1], [1, 1], [1, 3], [0, 3], [0, 0]]]}
    x, y = G.ponto_interior(u)
    anel = np.array(u["coordinates"][0], dtype=float)
    assert G._dentro(np.array([x]), np.array([y]), anel)[0]
    assert not (1 < x < 2 and y > 1)        # nunca no vão do "U", onde fica o centroide


def test_fronteiras_so_entre_regioes_diferentes_e_na_borda():
    q = lambda x0: [[[x0, 0], [x0 + 1, 0], [x0 + 1, 1], [x0, 1], [x0, 0]]]
    malha = {"features": [{"properties": {"codarea": str(c)}, "geometry": {"type": "Polygon", "coordinates": q(i)}}
                          for i, c in enumerate((1, 2, 3))]}
    segs = G.fronteiras(malha, {1: "A", 2: "A", 3: "B"})
    verticais_internas = {s[0] for s in segs if s[0] == s[2] and s[0] in (1, 2)}
    assert verticais_internas == {2}        # 1|2 é a mesma região; 2|3 é divisa
    assert any(s[0] == s[2] == 0 for s in segs) and any(s[0] == s[2] == 3 for s in segs)   # borda externa


def test_conter_traz_ponto_solto_para_perto():
    pos = np.vstack([np.random.default_rng(0).normal(size=(200, 2)), [[500.0, 0.0]]])
    contido = G.conter(pos)
    assert np.linalg.norm(contido[-1]) < 10
    assert np.allclose(contido[:200], pos[:200]) or np.linalg.norm(contido[:200] - pos[:200], axis=1).max() < 5


def test_projecao_igual_a_da_pagina():
    """O JS (motor.js, projetarLonLat) usa a mesma fórmula: o mapa e os nós coincidem."""
    p = G.PROJECAO
    x, y = G.projetar(p["lon0"] + 1, p["lat0"] - 1)
    assert x == pytest.approx(math.cos(math.radians(p["lat0"])) * p["k"])
    assert y == pytest.approx(p["k"])


# ------------------------------------------------------------------ redução
def _empenho(**kw):
    base = {"Ano": "2024", "Mes": "3", "EsferaAdministrativa": "Serra", "CodigoSubFuncao": "361", "NomePrograma": "ENSINO",
            "NomeAcao": "MANUTENCAO", "CodigoCompleto": "33903999", "CodigoGrupoNatureza": "3", "CodigoModalidade": "90",
            "CodigoElemento": "39", "CodigoSubElemento": "99", "NomeFonteReduzida": "TRANSFERÊNCIAS DO FUNDEB - 70%",
            "Empenhada": "1.000,50", "Paga": "1.000,50", "NomeCredorFornecedor": "EMPRESA X LTDA",
            "CodigoCredorFornecedor": "12345678000199", "NomeIdentificacao": "CNPJ"}
    return {**base, **kw}


def test_reduzir_parte_separa_rede_pessoa_fisica_pessoal_e_intra():
    df = pd.DataFrame([
        _empenho(),
        _empenho(CodigoCredorFornecedor="12345678000270", Empenhada="10,00", Paga="0,00"),   # filial: mesma raiz
        _empenho(CodigoModalidade="91", Empenhada="999,00"),                                  # intraorçamentária: fora
        _empenho(NomeIdentificacao="CPF", CodigoCredorFornecedor="12345678901", Empenhada="50,00"),
        _empenho(CodigoGrupoNatureza="1", CodigoCompleto="31901101", Empenhada="7.000,00"),  # pessoal
        _empenho(EsferaAdministrativa="Outro Lugar"),                                          # fora do ES: fora
    ])
    r = G.reduzir_parte(df, Municipios({3205002: "Serra"}), 2024)
    a = r["arestas"]
    assert len(a) == 1 and a.iloc[0]["raiz"] == "12345678" and a.iloc[0]["Empenhada"] == pytest.approx(1010.50)
    assert a.iloc[0]["fonte"] == "fundeb" and a.iloc[0]["mercado"] == "outros"
    assert r["resto"].set_index("classe")["Empenhada"].to_dict() == {"pf": 50.0}
    assert r["pessoal"]["Empenhada"].sum() == pytest.approx(7000.0)


# ------------------------------------------------------------------ página
def _dataset_minimo():
    return {"meta": {"esquema": build_grafos.ESQUEMA_ESPERADO, "anos": [2024], "mercados": [], "fontes": [], "tipos": [],
                     "tipos_padrao": [], "consultas": {}, "q_empenhos": {}, "situacoes_obra": [], "projecao": G.PROJECAO},
            "municipios": [], "malha": {"type": "FeatureCollection", "features": []}, "fronteiras": {},
            "fornecedores": {"colunas": [], "linhas": []}, "acoes": [], "arestas": {"m": [], "f": [], "k": [], "acao": [], "n_acoes": [], "v": []},
            "residuais": [], "pessoal": [], "layouts": {}, "projecoes": {}, "obras": {}}


def test_pagina_sem_marcador_pendente_e_com_o_dado(tmp_path):
    dados = _dataset_minimo()
    dados["acoes"] = ["</script><b>ação com tag</b>"]          # dado hostil não fecha o bloco
    html = build_grafos.montar(dados, saida=tmp_path / "redes.html").read_text(encoding="utf-8")
    assert not re.search(r"__[A-Z_]+__", html)
    bloco = re.search(r'<script type="application/json" id="dados-redes">(.*?)</script>', html, re.S).group(1)
    assert json.loads(bloco)["acoes"] == dados["acoes"]
    assert "cdn." not in html and "unpkg" not in html            # nenhuma biblioteca de fora: funciona offline


def test_pagina_recusa_esquema_diferente(tmp_path):
    arq = tmp_path / "grafos.json"
    arq.write_text(json.dumps({**_dataset_minimo(), "meta": {"esquema": 999}}), encoding="utf-8")
    with pytest.raises(SystemExit):
        build_grafos.ler_dataset(arq)


@pytest.mark.skipif(not G.SAIDA_JSON.exists(), reason="grafos.json ainda não gerado")
def test_dataset_gerado_e_coerente():
    d = json.loads(G.SAIDA_JSON.read_text(encoding="utf-8"))
    n_m, n_f = len(d["municipios"]), len(d["fornecedores"]["linhas"])
    a = d["arestas"]
    assert n_m == 78
    assert max(a["m"]) < n_m and max(a["f"]) < n_f and max(a["k"]) < len(G.MERCADOS)
    assert all(len(v) % 4 == 0 and v for v in a["v"])
    for merc, lay in d["layouts"].items():
        assert len(lay["mapa"]) == len(lay["forca"]) == 2 * len(lay["nos"]), merc
    assert d["meta"]["conferencia"]["ok"] is True     # a rede soma o mesmo que o total de empenhos do painel
