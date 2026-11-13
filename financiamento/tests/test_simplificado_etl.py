"""Pipeline do painel simplificado (etl/simplificado.py): só dados abertos do TCE-ES."""

import pandas as pd
import pytest

from financiamento.etl import simplificado as s
from financiamento.etl.tcees import Municipios

MUN = Municipios({3205002: "Serra", 3205309: "Vitória"})


def _receita(linhas):
    colunas = ["Ano", "Mes", "EsferaAdministrativa", "ClassificacaoReceita", "CodigoCategoria", "CodigoOrigem", "CodigoEspecie",
               "NomeEspecie", "NomeTipoDetalhamento", "Arrecadada"]
    df = pd.DataFrame(linhas, columns=colunas)
    return s.colunas_receita(df).fillna("")


RECEITAS = _receita([
    # 2021: ementário antigo
    ("2021", "1", "Serra", "11180111", "1", "1", "1", "IMPOSTOS", "IPTU - PRINCIPAL", "100,00"),
    ("2021", "1", "Serra", "17580111", "1", "7", "5", "TRANSFERÊNCIAS MULTIGOVERNAMENTAIS", "TRANSFERÊNCIAS DE RECURSOS DO FUNDEB - PRINCIPAL", "300,00"),
    ("2021", "2", "Serra", "17180911", "1", "7", "1", "TRANSFERÊNCIAS DA UNIÃO E DE SUAS ENTIDADES", "COMPLEMENTAÇÃO DA UNIÃO AO FUNDEB - PRINCIPAL", "20,00"),
    ("2021", "2", "Serra", "17180511", "1", "7", "1", "TRANSFERÊNCIAS DA UNIÃO E DE SUAS ENTIDADES", "TRANSFERÊNCIAS DO SALÁRIO-EDUCAÇÃO - PRINCIPAL", "30,00"),
    ("2021", "2", "Serra", "17180121", "1", "7", "1", "TRANSFERÊNCIAS DA UNIÃO E DE SUAS ENTIDADES", "COTA-PARTE DO FPM - PRINCIPAL", "200,00"),
    ("2021", "3", "Serra", "24180111", "2", "4", "1", "TRANSFERÊNCIAS DA UNIÃO E DE SUAS ENTIDADES",
     "TRANSPORTE ESCOLAR PARA EDUCAÇÃO BÁSICA - CAMINHO DA ESCOLA - PRINCIPAL", "50,00"),
    ("2021", "3", "Serra", "72100000", "7", "2", "1", "CONTRIBUIÇÕES", "INTRA-ORÇAMENTÁRIA", "999,00"),
    # 2022: ementário novo — códigos diferentes, mesmos nomes
    ("2022", "1", "Serra", "17515001", "1", "7", "5", "TRANSFERÊNCIAS DE OUTRAS INSTITUIÇÕES PÚBLICAS", "TRANSFERÊNCIAS DE RECURSOS DO FUNDEB - PRINCIPAL", "310,00"),
    ("2022", "1", "Serra", "17145201", "1", "7", "1", "TRANSFERÊNCIAS DA UNIÃO E DE SUAS ENTIDADES",
     "TRANSFERÊNCIAS REFERENTES AO PROGRAMA NACIONAL DE ALIMENTAÇÃO ESCOLAR - PNAE - PRINCIPAL", "40,00"),
    ("2022", "1", "Serra", "19225101", "1", "9", "2", "INDENIZAÇÕES, RESTITUIÇÕES E RESSARCIMENTOS", "RESTITUIÇÕES DE RECURSOS DO FUNDEB - PRINCIPAL", "5,00"),
    ("2022", "1", "Município Inexistente", "11180111", "1", "1", "1", "IMPOSTOS", "IPTU - PRINCIPAL", "7,00"),
])


def _origem():
    r = s.receita_normalizada(RECEITAS, MUN)
    ra, origem = s.tabelas_receita(r, {2021: "q21", 2022: "q22"})
    return ra.set_index(["ano"]), origem.set_index(["ano", "categoria"])["valor"]


def test_origem_da_receita_nos_dois_ementarios():
    ra, o = _origem()
    # 2021: FUNDEB = fundo (1.7.5.8) + complementação (1.7.1.8.09); FNDE = salário-educação; intra fora.
    assert o[(2021, "total")] == 700.0
    assert o[(2021, "impostos_proprios")] == 100.0
    assert o[(2021, "fundeb")] == 320.0
    assert o[(2021, "federal_especifica")] == 30.0
    assert o[(2021, "outras")] == 250.0          # FPM 200 + Caminho da Escola 50 (capital, não é FNDE corrente)
    # 2022: código novo do FUNDEB; a restituição do FUNDEB (origem 9) não é transferência.
    assert o[(2022, "fundeb")] == 310.0 and o[(2022, "federal_especifica")] == 40.0
    assert o[(2022, "outras")] == 5.0
    assert ra.loc[2021, "transferencias_capital"] == 50.0
    assert ra.loc[2021, "transf_correntes_uniao"] == 250.0 and ra.loc[2021, "transf_correntes_outras_publicas"] == 300.0


def test_municipio_fora_da_lista_nao_entra():
    r = s.receita_normalizada(RECEITAS, MUN)
    assert set(r["cod_ibge"]) == {3205002}


def _despesa(linhas):
    colunas = ["Ano", "Mes", "EsferaAdministrativa", "CodigoModalidade", "CodigoSubFuncao", "DescricaoSubFuncao",
               "CodigoFonteReduzida", "NomeFonteReduzida", "CodigoCompleto", "Empenhada", "Liquidada", "Paga"]
    return s.despesa_funcao12(pd.DataFrame(linhas, columns=colunas), MUN)


DESPESA = _despesa([
    ("2022", "1", "Serra", "90", "361", "ENSINO FUNDAMENTAL", "111", "IMPOSTOS - EDUCAÇÃO", "31901100", "100,00", "100,00", "90,00"),
    ("2022", "12", "Serra", "90", "365", "EDUCAÇÃO INFANTIL", "113", "FUNDEB", "33903900", "50,00", "40,00", "40,00"),
    ("2023", "1", "Serra", "90", "361", "ENSINO FUNDAMENTAL", "540", "FUNDEB", "31901100", "200,00", "200,00", "200,00"),
    ("2023", "2", "Serra", "90", "306", "ALIMENTAÇÃO E NUTRIÇÃO", "552", "PNAE", "33903000", "30,00", "30,00", "30,00"),
    ("2023", "2", "Serra", "91", "361", "ENSINO FUNDAMENTAL", "500", "IMPOSTOS", "31919100", "999,00", "0,00", "0,00"),
    ("2024", "1", "Serra", "90", "361", "ENSINO FUNDAMENTAL", "540", "FUNDEB", "31901100", "210,00", "0,00", "0,00"),
])


def test_despesa_por_subfuncao_fonte_e_natureza():
    t = s.tabelas_despesa(DESPESA, {2022: "d22", 2023: "d23", 2024: "d24"})
    total = t["total"].set_index("ano")
    assert total.loc[2023, "desp_educacao_empenhada"] == 230.0          # a intra-orçamentária (modalidade 91) fica fora
    assert total.loc[2022, "fontes"] == "local" and total.loc[2023, "fontes"] == "padronizada"
    assert set(t["fluxo"]["ano"]) == {2023, 2024}                        # 2022 com códigos antigos: sem fluxo
    f23 = t["fluxo"][t["fluxo"]["ano"] == 2023].set_index("fonte")
    assert f23.loc["540", "grupo"] == "fundeb" and f23.loc["552", "grupo"] == "federal"
    sub = t["subfuncoes"][t["subfuncoes"]["ano"] == 2023].set_index("codigo")
    assert sub.loc["12.306", "nome"] == "Alimentação e Nutrição" and sub.loc["12.361", "pct_educacao"] == pytest.approx(86.9565, 1e-3)
    assert sub["q"].eq("d23").all()
    nat = t["natureza"][t["natureza"]["ano"] == 2023].set_index("elemento")
    assert nat.loc["11", "categoria"] == "pessoal" and nat.loc["30", "categoria"] == "custeio"


def test_exercicio_parcial_compara_com_o_mesmo_periodo():
    d = _despesa([
        ("2025", str(m), "Serra", "90", "361", "ENSINO FUNDAMENTAL", "540", "FUNDEB", "31901100", "10,00", "0", "0")
        for m in range(1, 13)] + [
        ("2026", str(m), "Serra", "90", "361", "ENSINO FUNDAMENTAL", "540", "FUNDEB", "31901100", "12,00", "0", "0")
        for m in range(1, 10)])
    desp = s.tabelas_despesa(d, {2025: "d25", 2026: "d26"})
    emp = pd.DataFrame({"cod_ibge": [3205002, 3205002], "ano": [2025, 2026], "tcees_emp_empenhada": [120.0, 96.0],
                        "tcees_emp_meses": [12, 8], "tcees_emp_meses_ausentes": [None, "9,10,11,12"]})
    mde = pd.DataFrame({"cod_ibge": [3205002], "ano": [2026], "tcees_alunos": [10], "tcees_mes_ultimo_envio": [9]})
    a = s.compor_anual({3205002: "Serra", 3205309: "Vitória"}, [2025, 2026], desp, pd.DataFrame(), mde, emp,
                       {"despesas": {2025: "d25", 2026: "d26"}}, 2026).set_index(["cod_ibge", "ano"])
    r = a.loc[(3205002, 2026)]
    assert r["parcial"] and r["ultimo_mes"] == 9 and r["desp_educacao_empenhada"] == 108.0
    assert r["desp_educacao_empenhada_ant_periodo"] == 90.0               # jan–set de 2025, não o ano inteiro
    assert r["tcees_emp_meses_ausentes"] == "9"                           # out–dez ainda não chegaram: não são ausência
    assert r["desp_educacao_por_matricula"] == 10.8
    assert not a.loc[(3205002, 2025), "parcial"]
    assert a.loc[(3205309, 2026), "status_despesa"] == "sem_dado"


def test_total_por_mes_soma_e_tira_a_intra():
    bloco = pd.DataFrame({"Ano": ["2024"] * 3, "Mes": ["1", "1", "2"], "EsferaAdministrativa": ["Serra"] * 3,
                          "CodigoModalidade": ["90", "91", "90"], "Empenhada": ["1.000,50", "5,00", "2,00"]})
    t = s.total_por_mes(bloco).set_index("Mes")["Empenhada"]
    assert t["1"] == 1000.5 and t["2"] == 2.0


def test_cliente_renova_so_o_ano_corrente_e_uma_vez(tmp_path):
    c = s.ClienteRenovaAno(2026, pasta=tmp_path, atualizar="nao")
    assert c._renova("despesas/2026") and c._renova("empenhos/2026/x") and c._renova("contratacoes_educacao")
    assert not c._renova("despesas/2025") and not c._renova("itens/2024")
    c._renovados.add("despesas/2026")
    assert not c._renova("despesas/2026")
    assert not s.ClienteRenovaAno(2026, pasta=tmp_path, atualizar="offline")._renova("despesas/2026")


def test_tabela_fixa_dos_78_municipios():
    nomes = s.carregar_municipios()
    assert len(nomes) == 78 and nomes[3205002] == "Serra"


def test_titulo_das_subfuncoes():
    assert s.titulo("EDUCAÇÃO DE JOVENS E ADULTOS") == "Educação de Jovens e Adultos"
