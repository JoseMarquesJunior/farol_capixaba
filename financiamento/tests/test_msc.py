"""MSC orçamentária: Nível 2, fluxo por fonte e FUNDEB — com a resposta real de Afonso Cláudio 2024. Sem rede."""

import pytest

from financiamento.etl import msc

# Valores de controle: DCA I-E e I-C de Afonso Cláudio 2024 (o mesmo ente-ano da fixture).
DCA_EMPENHADA, DCA_LIQUIDADA, DCA_PAGA = 49_699_516.59, 48_939_943.63, 48_708_923.11
DCA_FUNDEB_FUNDO, DCA_FUNDEB_COMPLEMENTACAO = 28_116_758.90, 3_689_803.08
DCA_SUBFUNCOES = {"361": 29_089_152.95, "365": 14_078_309.39, "122": 4_190_427.26, "362": 1_440_090.34,
                  "367": 763_054.82, "364": 130_681.83, "363": 7_800.00}


@pytest.fixture(scope="module")
def despesa(msc_afonso_2024):
    return msc.despesa_educacao(msc_afonso_2024)


def test_estagios_do_empenho_batem_ao_centavo_com_o_dca(despesa):
    r = msc.resumo_despesa(despesa)
    assert r["empenhada"] == pytest.approx(DCA_EMPENHADA, abs=0.01)
    assert r["liquidada"] == pytest.approx(DCA_LIQUIDADA, abs=0.01)
    assert r["paga"] == pytest.approx(DCA_PAGA, abs=0.01)


def test_cada_subfuncao_bate_com_o_dca(despesa):
    por_sub = despesa.groupby("subfuncao")["empenhada"].sum().round(2).to_dict()
    assert por_sub == pytest.approx(DCA_SUBFUNCOES, abs=0.01)


def test_soma_das_subfuncoes_e_o_total_da_funcao(despesa):
    """Requisito do painel: soma da despesa por subfunção = total da função."""
    assert despesa.groupby("subfuncao")["empenhada"].sum().sum() == pytest.approx(DCA_EMPENHADA, abs=0.01)


def test_outras_funcoes_e_outras_contas_ficam_de_fora(msc_afonso_2024):
    outras = [l for l in msc_afonso_2024 if str(l.get("funcao")).zfill(2) != "12"]
    assert outras, "a fixture deveria trazer linhas de outras funções para exercitar o filtro"
    assert msc.despesa_educacao(outras).empty


def test_intra_orcamentaria_e_excluida():
    base = {"conta_contabil": "622130400", "funcao": "12", "subfuncao": "361", "fonte_recursos": "1500",
            "complemento_fonte": None, "valor": 100.0}
    linhas = [{**base, "natureza_despesa": "31901101"}, {**base, "natureza_despesa": "31911301", "valor": 999.0}]
    d = msc.despesa_educacao(linhas)
    assert msc.resumo_despesa(d) == {"empenhada": 100.0, "liquidada": 100.0, "paga": 100.0}


def test_fluxo_por_fonte_soma_o_total_e_usa_os_quatro_grupos(despesa):
    fluxo = msc.fluxo_fonte_subfuncao(despesa)
    assert fluxo["empenhada"].sum() == pytest.approx(DCA_EMPENHADA, abs=0.01)
    assert set(fluxo["grupo"]) <= set(msc.GRUPOS_FONTE)
    assert fluxo.loc[fluxo["grupo"] == "fundeb", "fonte"].isin(["540", "541", "542", "543"]).all()


def test_natureza_economica_soma_o_total(despesa):
    nat = msc.natureza_economica(despesa)
    assert nat["empenhada"].sum() == pytest.approx(DCA_EMPENHADA, abs=0.01)
    assert set(nat["categoria"]) <= set(msc.CATEGORIAS)
    assert set(nat["subcategoria"]) <= set(msc.SUBCATEGORIAS)


@pytest.mark.parametrize("natureza, esperado", [
    ("31901101", ("pessoal", "pessoal_ativo")),       # vencimentos
    ("31900401", ("pessoal", "pessoal_ativo")),       # contratação por tempo determinado
    ("31900101", ("pessoal", "pessoal_inativo")),     # aposentadorias
    ("33903001", ("custeio", "material_consumo")),
    ("33903901", ("custeio", "servicos_pj")),
    ("33504308", ("custeio", "entidades")),           # subvenção a entidade sem fins lucrativos (creche conveniada)
    ("33717001", ("custeio", "consorcios")),
    ("33904601", ("custeio", "auxilios")),
    ("44905199", ("investimento", "obras")),
    ("44905201", ("investimento", "equipamentos")),
    ("46907101", ("outras", "divida_inversoes")),
])
def test_mapeamento_da_natureza(natureza, esperado):
    assert msc.classificar_natureza(natureza) == esperado


def test_fonte_padronizada_e_local():
    assert msc.fonte_padronizada("1540") == (1, "540")
    assert msc.fonte_padronizada("2500") == (2, "500")  # 2 = exercícios anteriores, NÃO intra-orçamentária
    assert msc.fonte_padronizada("11110000") is None    # código local de 2021 (ES)
    assert msc.grupo_fonte("500") == "impostos" and msc.grupo_fonte("552") == "federal"


def test_exercicio_com_codigos_locais_nao_gera_fluxo():
    linhas = [{"conta_contabil": "622130400", "funcao": "12", "subfuncao": "361", "fonte_recursos": "11110000",
               "complemento_fonte": None, "natureza_despesa": "31901101", "valor": 10.0}]
    d = msc.despesa_educacao(linhas)
    assert msc.fontes_do_exercicio(d) == "local"
    assert msc.fluxo_fonte_subfuncao(d).empty
    assert not msc.natureza_economica(d).empty  # o Nível 2 não depende da fonte


def test_fundeb_identificado_pelos_codigos_do_dca(msc_afonso_2024):
    receita = msc.receita_realizada(msc_afonso_2024)
    f = msc.fundeb(receita, [msc.prefixo_natureza("RO1.7.5.1.00.0.0")], [msc.prefixo_natureza("RO1.7.1.5.00.0.0")])
    assert f.fundo == pytest.approx(DCA_FUNDEB_FUNDO, abs=0.01)
    assert f.complementacao == pytest.approx(DCA_FUNDEB_COMPLEMENTACAO, abs=0.01)
    assert set(f.por_fonte) == {"540", "542", "543"}  # fundo, VAAT e VAAR


def test_sem_linha_do_fundo_nao_ha_fundeb(msc_afonso_2024):
    receita = msc.receita_realizada(msc_afonso_2024)
    assert msc.fundeb(receita, ["9999"], ["1715"]) is None


@pytest.mark.parametrize("dca, prefixo", [
    ("RO1.7.5.1.00.0.0", "1751"), ("RO1.7.1.5.00.0.0", "1715"), ("RO1.7.5.8.01.0.0", "175801"),
])
def test_prefixo_da_conta_do_dca(dca, prefixo):
    assert msc.prefixo_natureza(dca) == prefixo
