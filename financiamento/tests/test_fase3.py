"""Fase 3 — contratos, diários e repasses estaduais. Sem rede.

Os três módulos têm em comum o que mais importa neles: classificar por
palavra-chave ou casar por nome, e deixar visível o que ficou de fora.
"""

import pandas as pd
import pytest

from financiamento.etl import contratos, diarios, estado


# ------------------------------------------------------------- contratos

def contratacao(objeto, **kw):
    base = {"cod_ibge": 3205309, "ano": 2024, "contratacao": "2024.001", "ug": "SEMED",
            "objeto": objeto, "setor": "Educação", "modalidade": "Pregão Eletrônico",
            "situacao": "Contrato assinado", "valor_total": 100000.0,
            "url_edital": "", "vinculo": "ug_educacao", "q": "q1"}
    base.update(kw)
    return base


def test_classifica_formacao_em_alfabetizacao_e_guarda_os_termos():
    d = contratos.classificar(pd.DataFrame([contratacao(
        "CONTRATAÇÃO DE EMPRESA PARA FORMAÇÃO CONTINUADA DE PROFESSORES EM ALFABETIZAÇÃO")]))
    assert len(d) == 1
    r = d.iloc[0]
    assert r["categoria"] == "formacao_alfabetizacao" and r["responde_p47"]
    assert r["termos"]                                   # o trecho que casou, para revisão


def test_material_de_alfabetizacao_e_cantinho_de_leitura():
    d = contratos.classificar(pd.DataFrame([
        contratacao("AQUISIÇÃO DE MATERIAL ESTRUTURADO DE ALFABETIZAÇÃO"),
        contratacao("IMPLANTAÇÃO DE CANTINHOS DE LEITURA NAS ESCOLAS", contratacao="2024.002"),
    ]))
    assert set(d["categoria"]) == {"material_alfabetizacao"}
    assert d["responde_p47"].all()


def test_formacao_generica_nao_responde_p47():
    d = contratos.classificar(pd.DataFrame([contratacao("FORMAÇÃO CONTINUADA DOS SERVIDORES")]))
    assert d.iloc[0]["categoria"] == "formacao_geral"
    assert not d.iloc[0]["responde_p47"]


def test_mencao_a_alfabetizacao_nao_some_mesmo_sem_ser_formacao():
    """As 6 contratações do ES que citam 'alfabetiz' não são formação — e nenhuma pode sumir."""
    d = contratos.classificar(pd.DataFrame([contratacao(
        "AQUISIÇÃO DE GÊNEROS ALIMENTÍCIOS PARA O PROGRAMA BRASIL ALFABETIZADO - EJA")]))
    assert len(d) == 1
    assert d.iloc[0]["categoria"] == "mencao_alfabetizacao"
    assert not d.iloc[0]["responde_p47"]


def test_objeto_sem_relacao_nao_entra():
    d = contratos.classificar(pd.DataFrame([contratacao("AQUISIÇÃO DE COMBUSTÍVEL")]))
    assert d.empty


def test_uma_contratacao_entra_numa_categoria_so():
    d = contratos.classificar(pd.DataFrame([contratacao(
        "FORMAÇÃO CONTINUADA EM ALFABETIZAÇÃO COM MATERIAL ESTRUTURADO E ASSESSORIA PEDAGÓGICA")]))
    assert len(d) == 1


def test_licitacao_revogada_fica_fora_do_valor_de_p48():
    d = contratos.classificar(pd.DataFrame([
        contratacao("ASSESSORIA PEDAGÓGICA PARA A REDE", valor_total=50000.0),
        contratacao("ASSESSORIA PEDAGÓGICA PARA A REDE", contratacao="2024.002",
                    situacao="Licitação Revogada ou Anulada", valor_total=900000.0),
    ]))
    assert int(d["sem_efeito"].sum()) == 1
    m = contratos.por_municipio(d).iloc[0]
    assert m["valor_p47"] == pytest.approx(50000.0)      # a revogada não entra
    assert m["contratacoes"] == 2                        # mas continua na tabela


# --------------------------------------------------------------- diários

def test_lista_de_buscas_manuais_cobre_quem_nao_tem_diario():
    cob = pd.DataFrame([
        {"cod_ibge": 3205309, "municipio": "Vitória", "fonte": "Querido Diário",
         "situacao": "coletado", "desde": "2025-01-13", "edicoes_desde_2023": 1677},
        {"cod_ibge": 3200102, "municipio": "Afonso Cláudio", "fonte": "Querido Diário",
         "situacao": "não coberto", "desde": None, "edicoes_desde_2023": 0},
    ])
    d = diarios.lista_buscas_manuais(cob)
    assert set(d["cod_ibge"]) == {3200102}               # só quem não tem diário coletado
    assert len(d) == len(diarios.BUSCAS)
    assert (d["como_registrar"].str.contains("não é ausência de ato")).all()


def test_toda_busca_tem_achado_correspondente_na_matriz():
    from financiamento.etl import matriz
    conhecidos = {a.id for a in matriz.carregar().achados}
    assert set(diarios.BUSCAS) <= conhecidos
    assert set(diarios.TERMOS_QD) <= conhecidos


# ---------------------------------------------------------------- estado

def test_filtro_do_sigefes_pega_so_educacao_transferida_a_municipio():
    assert estado.manter({"CodigoFuncao": "12", "CodigoModalidade": "40"})
    assert estado.manter({"CodigoFuncao": "012", "CodigoModalidade": "41"})
    assert not estado.manter({"CodigoFuncao": "12", "CodigoModalidade": "90"})   # aplicação direta
    assert not estado.manter({"CodigoFuncao": "10", "CodigoModalidade": "40"})   # saúde


NOMES = {3205002: "Serra", 3205200: "Vila Velha", 3202405: "Guarapari",
         3201803: "Divino de São Lourenço", 3202256: "Governador Lindenberg"}
MAPA = {estado.norm(v): k for k, v in NOMES.items()}
casar = lambda n: estado._municipio_do_favorecido(n, MAPA)


def test_favorecido_casa_com_o_municipio_pelo_nome_mais_longo():
    """'Serra' casaria dentro de outros nomes; fica o mais longo que casar."""
    assert casar("FUNDO MUNICIPAL DE EDUCAÇÃO - SERRA") == (3205002, "nome exato")
    assert casar("PREFEITURA MUNICIPAL DE VILA VELHA") == (3205200, "nome exato")


def test_grafia_diferente_do_ibge_casa_por_similaridade():
    """O SIGEFES escreve 'Divino São Lourenço' e 'Lindemberg'; o IBGE, de outro jeito.

    Eram R$ 9,3 milhões de 2023 caindo fora do casamento por causa de uma preposição
    e de uma letra. O método usado fica registrado na linha.
    """
    cod, metodo = casar("PREFEITURA MUNICIPAL DE DIVINO SÃO LOURENÇO")
    assert cod == 3201803 and metodo.startswith("aproximado")
    cod, metodo = casar("PREFEITURA MUNICIPAL DE GOVERNADOR LINDEMBERG")
    assert cod == 3202256 and metodo.startswith("aproximado")


def test_similaridade_nao_inventa_municipio():
    """Favorecido que não é município nenhum tem de sair sem casamento, não no mais parecido."""
    assert casar("FUNDO ESTADUAL DE SAÚDE") == (None, "sem casamento")
    assert casar("COOPERATIVA DE TRANSPORTES DA REGIAO SUL") == (None, "sem casamento")
    assert casar("") == (None, "sem casamento")


def sigefes(**kw):
    base = {"Ano": "2024", "Data": "2024-05-10", "Favorecido": "FUNDO MUNICIPAL DE EDUCAÇÃO - SERRA",
            "CpfCnpjNis": "123", "UnidadeGestora": "FUNDO EST. DE APOIO À AMP. E MELH. DAS COND.",
            "Programa": "MELHORIA DA QUALIDADE", "Acao": "COOPERAÇÃO ESTADO/MUNICÍPIOS",
            "Fonte": "Recursos não vinculados", "CodigoModalidade": "40",
            "ValorEmpenho": "1.000,00", "ValorLiquidado": "900,00", "ValorPago": "800,00"}
    base.update(kw)
    return base


def test_repasse_identifica_municipio_e_marca_funpaes():
    rep, sobra = estado.preparar(pd.DataFrame([sigefes()]), {3205002: "Serra"})
    assert len(rep) == 1 and sobra.empty
    r = rep.iloc[0]
    assert r["cod_ibge"] == 3205002 and r["funpaes"]
    assert r["empenhado"] == pytest.approx(1000.0)
    assert r["modalidade_rotulo"] == "Transferências a municípios"


def test_favorecido_que_nao_casa_vai_para_tabela_propria_e_nao_some():
    rep, sobra = estado.preparar(pd.DataFrame([
        sigefes(), sigefes(Favorecido="CONSÓRCIO INTERMUNICIPAL DO NORTE", ValorEmpenho="5.000,00")]),
        {3205002: "Serra"})
    assert len(rep) == 1
    assert len(sobra) == 1
    assert sobra.iloc[0]["empenhado"] == pytest.approx(5000.0)


def test_resumo_por_municipio_separa_o_funpaes():
    rep, _ = estado.preparar(pd.DataFrame([
        sigefes(),
        sigefes(UnidadeGestora="SECRETARIA DE ESTADO DA EDUCAÇÃO", ValorEmpenho="300,00")]),
        {3205002: "Serra"})
    m = estado.por_municipio(rep.assign(q="q1")).iloc[0]
    assert m["empenhado"] == pytest.approx(1300.0)
    assert m["empenhado_funpaes"] == pytest.approx(1000.0)


def test_fontes_proprias_cobrem_os_dois_periodos_de_codificacao():
    """Até 2022 o ES usa 111/112/113; de 2023, 500/540. Só o par novo daria 0% em 2021."""
    from financiamento.etl.execucao import FONTES_PROPRIAS
    assert {"500", "540", "111", "112", "113"} <= set(FONTES_PROPRIAS)
