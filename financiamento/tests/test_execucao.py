"""Agregados de execução da matriz do CNCA: leiaute por exercício, fontes, RP, mês. Sem rede."""

import pandas as pd
import pytest

from financiamento.etl import execucao
from financiamento.etl.tcees import Municipios

MUN = Municipios({3200102: "Afonso Cláudio", 3205309: "Vitória"})

#: Colunas do leiaute de 2024-2025 (58 campos no arquivo real; aqui as que o módulo usa).
COLUNAS_2024 = ["AnoReferencia", "MesReferencia", "DataEmissao", "EsferaAdministrativa", "CodigoSubFuncao",
                "CodigoPrograma", "NomePrograma", "CodigoAcao", "NomeAcao", "CodigoModalidade",
                "CodigoElemento", "DescricaoElemento", "CodigoFonteReduzida", "NomeFonteReduzida", "AnoEmpenho",
                "NomeDetalhamento", "CodigoComplementoFontesDestinacoesRecursos",
                "Empenhada", "Liquidada", "Paga", "RPPExercicio", "RPPTransferido", "RPPPago",
                "RPPCancelado", "RPNPExercicio", "RPNPLiquidado", "RPNPPago", "RPNPCancelado"]

#: O leiaute de 2021-2023 NÃO tem data de emissão nem complemento de fonte.
COLUNAS_2021 = [c for c in COLUNAS_2024 if c not in ("DataEmissao", "CodigoComplementoFontesDestinacoesRecursos")]
COLUNAS_2021 = ["Ano" if c == "AnoReferencia" else "Mes" if c == "MesReferencia" else c for c in COLUNAS_2021]


def linha(**kw):
    base = {"AnoReferencia": "2024", "MesReferencia": "3", "DataEmissao": "2024-03-15 00:00:00",
            "EsferaAdministrativa": "Vitória", "CodigoSubFuncao": "361", "CodigoPrograma": "1",
            "NomePrograma": "ENSINO", "CodigoAcao": "2.001", "NomeAcao": "MANUTENCAO",
            "CodigoModalidade": "90", "CodigoElemento": "30", "DescricaoElemento": "Material de consumo",
            "CodigoFonteReduzida": "0569", "NomeFonteReduzida": "OUTRAS DO FNDE", "NomeDetalhamento": "",
            "CodigoComplementoFontesDestinacoesRecursos": "AAAA",
            "Empenhada": "1.000,00", "Liquidada": "800,00", "Paga": "500,00",
            "RPPExercicio": "0,00", "RPPTransferido": "0,00", "RPPPago": "0,00",
            "RPPCancelado": "0,00", "RPNPExercicio": "0,00", "RPNPLiquidado": "0,00",
            "RPNPPago": "0,00", "RPNPCancelado": "0,00", "AnoEmpenho": "2024"}
    base.update(kw)
    return base


def quadro(linhas, colunas=COLUNAS_2024):
    return pd.DataFrame(linhas).reindex(columns=colunas).fillna("")


# ------------------------------------------------------------------ preparo

def test_fonte_perde_o_zero_a_esquerda():
    d = execucao.preparar(quadro([linha(CodigoFonteReduzida="0551"), linha(CodigoFonteReduzida="551")]), MUN, 2024)
    assert set(d["fonte"]) == {"551"}


def test_municipio_fora_do_es_nao_entra():
    d = execucao.preparar(quadro([linha(EsferaAdministrativa="Belo Horizonte")]), MUN, 2024)
    assert d.empty


def test_intra_orcamentaria_fica_de_fora():
    d = execucao.preparar(quadro([linha(CodigoModalidade="91"), linha()]), MUN, 2024)
    assert len(d) == 1


def test_leiaute_de_2021_sem_data_de_emissao_vira_na_e_nao_zero():
    """DataEmissao só existe de 2024 em diante — 2021-2023 têm de sair NaT, nunca uma data inventada."""
    d = execucao.preparar(quadro([linha(**{"Ano": "2021", "Mes": "5"})], COLUNAS_2021), MUN, 2021)
    assert len(d) == 1
    assert d["data_emissao"].isna().all()
    assert d["complemento"].isna().all()
    assert d["ano"].iloc[0] == 2021 and d["mes"].iloc[0] == 5


def test_complemento_de_fonte_e_lido_quando_existe():
    d = execucao.preparar(quadro([linha(CodigoComplementoFontesDestinacoesRecursos="1001")]), MUN, 2024)
    assert d["complemento"].iloc[0] == "1001"


def test_data_de_emissao_iso_nao_e_lida_ao_contrario():
    """2024-03-15 é 15 de março, não 3 de quinze — dayfirst estragaria a defasagem de A4.2."""
    d = execucao.preparar(quadro([linha(DataEmissao="2024-03-15 00:00:00")]), MUN, 2024)
    assert d["data_emissao"].iloc[0] == pd.Timestamp("2024-03-15")


# ----------------------------------------------------------------- reduções

def test_mensal_soma_por_subfuncao_e_mes():
    d = execucao.preparar(quadro([linha(MesReferencia="11", Empenhada="100,00"),
                                  linha(MesReferencia="11", Empenhada="50,00"),
                                  linha(MesReferencia="1", Empenhada="10,00"),
                                  linha(MesReferencia="11", CodigoSubFuncao="365", Empenhada="7,00")]), MUN, 2024)
    m = execucao.reduzir(d)["mensal"]
    nov361 = m[(m["mes"] == 11) & (m["subfuncao"] == "361")]
    assert nov361["empenhada"].iloc[0] == pytest.approx(150.0)
    assert m[(m["mes"] == 11) & (m["subfuncao"] == "365")]["empenhada"].iloc[0] == pytest.approx(7.0)


def test_restos_a_pagar_sao_somados_por_fonte():
    d = execucao.preparar(quadro([linha(RPPExercicio="300,00", RPPPago="100,00")]), MUN, 2024)
    f = execucao.reduzir(d)["fontes"]
    assert f["rpp_inscrito"].iloc[0] == pytest.approx(300.0)
    assert f["rpp_pago"].iloc[0] == pytest.approx(100.0)


def test_rp_idade_le_o_movimento_nas_linhas_de_anos_anteriores():
    """O arquivo tem dois tipos de linha, e o dinheiro do RP está só no segundo.

    Linha do próprio exercício traz Empenhada/Liquidada/Paga e RP zerado; linha de
    empenho de ano anterior traz Empenhada/Liquidada/Paga ZERADAS e o dinheiro nas
    colunas de RP. Somar Empenhada nelas daria zero e diria que não há restos a pagar.
    """
    d = execucao.preparar(quadro([
        linha(AnoEmpenho="2024", Empenhada="1.000,00", Liquidada="900,00", Paga="800,00"),
        linha(AnoEmpenho="2021", Empenhada="0,00", Liquidada="0,00", Paga="0,00",
              RPPPago="500,00", RPNPPago="300,00"),
    ]), MUN, 2024)
    ri = execucao.combinar([execucao.reduzir(d)], {2024: "q1"})["rp_idade"]
    assert len(ri) == 1
    r = ri.iloc[0]
    assert r["ano_empenho"] == 2021 and r["idade_anos"] == 3
    assert r["rpp_pago"] == pytest.approx(500.0)
    assert r["rp_processado_movimentado"] == pytest.approx(500.0)
    assert r["rp_nao_processado_movimentado"] == pytest.approx(300.0)


def test_rp_idade_ignora_o_exercicio_corrente():
    d = execucao.preparar(quadro([linha(AnoEmpenho="2024", RPPPago="500,00")]), MUN, 2024)
    assert execucao.reduzir(d)["rp_idade"].empty


def test_elemento_atipico_e_marcado_mas_nao_julgado():
    d = execucao.preparar(quadro([linha(CodigoElemento="11", DescricaoElemento="Vencimentos"),
                                  linha(CodigoElemento="30", DescricaoElemento="Material")]), MUN, 2024)
    fe = execucao.combinar([execucao.reduzir(d)], {2024: "q1"})["fonte_elemento"]
    assert set(fe[fe["atipico"]]["elemento"]) == {"11"}
    assert set(fe[~fe["atipico"]]["elemento"]) == {"30"}


def test_acao_que_nomeia_alfabetizacao_e_capturada_apesar_do_norm_minusculo():
    """`parsing.norm` devolve minúsculas: a regex precisa casar assim, ou o painel diria 'nenhuma'."""
    d = execucao.preparar(quadro([linha(NomeAcao="MANUTENÇÃO DO PROGRAMA DE ALFABETIZAÇÃO"),
                                  linha(NomeAcao="MANUTENCAO DO ENSINO")]), MUN, 2024)
    an = execucao.combinar([execucao.reduzir(d)], {2024: "q1"})["acoes_nomeadas"]
    assert len(an) == 1 and an["alfabetizacao"].all()


def test_acao_de_premiacao_e_capturada_para_p42():
    d = execucao.preparar(quadro([linha(NomeAcao="PREMIO BOAS PRATICAS NA EDUCAÇÃO")]), MUN, 2024)
    an = execucao.combinar([execucao.reduzir(d)], {2024: "q1"})["acoes_nomeadas"]
    assert len(an) == 1 and an["premiacao"].all() and not an["alfabetizacao"].any()


def test_primeiro_empenho_so_aparece_onde_ha_data():
    d21 = execucao.preparar(quadro([linha(**{"Ano": "2021", "Mes": "5"})], COLUNAS_2021), MUN, 2021)
    assert execucao.reduzir(d21)["primeiro_empenho"].empty
    d24 = execucao.preparar(quadro([linha(DataEmissao="2024-07-02 00:00:00"),
                                    linha(DataEmissao="2024-03-15 00:00:00")]), MUN, 2024)
    pe = execucao.reduzir(d24)["primeiro_empenho"]
    assert pe["primeiro_empenho"].iloc[0] == pd.Timestamp("2024-03-15")


def test_combinar_soma_as_partes_do_mesmo_ano_sem_duplicar_chave():
    p1 = execucao.reduzir(execucao.preparar(quadro([linha(Empenhada="100,00")]), MUN, 2024))
    p2 = execucao.reduzir(execucao.preparar(quadro([linha(Empenhada="40,00")]), MUN, 2024))
    f = execucao.combinar([p1, p2], {2024: "q1"})["fontes"]
    assert len(f) == 1 and f["empenhada"].iloc[0] == pytest.approx(140.0)
    assert f["q"].iloc[0] == "q1"


# ------------------------------------------------------------------ dotação

COLUNAS_DESPESA = ["Ano", "EsferaAdministrativa", "CodigoSubFuncao", "CodigoPrograma", "NomePrograma",
                   "CodigoAcao", "NomeAcao", "CodigoModalidade", "CodigoFonteReduzida", "NomeFonteReduzida",
                   "PrevisaoInicial", "PrevisaoAtualizada", "Empenhada", "Liquidada", "Paga"]


def despesa(**kw):
    base = {"Ano": "2024", "EsferaAdministrativa": "Vitória", "CodigoSubFuncao": "361", "CodigoPrograma": "1",
            "NomePrograma": "ENSINO", "CodigoAcao": "2.001", "NomeAcao": "MANUTENCAO", "CodigoModalidade": "90",
            "CodigoFonteReduzida": "0569", "NomeFonteReduzida": "OUTRAS DO FNDE",
            "PrevisaoInicial": "1.000,00", "PrevisaoAtualizada": "2.000,00",
            "Empenhada": "500,00", "Liquidada": "400,00", "Paga": "300,00"}
    base.update(kw)
    return base


def test_dotacao_por_fonte_ignora_intra_e_soma():
    d = execucao.dotacao_por_fonte(pd.DataFrame([despesa(), despesa(), despesa(CodigoModalidade="91")]), MUN, 2024)
    assert len(d) == 1
    assert d["previsao_atualizada"].iloc[0] == pytest.approx(4000.0)
    assert d["fonte"].iloc[0] == "569"


def test_dotacao_nomeada_separa_alfabetizacao_de_premiacao():
    d = execucao.dotacao_nomeada(pd.DataFrame([
        despesa(NomeAcao="PROGRAMA BRASIL ALFABETIZADO"),
        despesa(NomeAcao="REALIZAÇÃO DE PROJETOS E PREMIAÇÕES"),
        despesa(NomeAcao="MANUTENCAO DO ENSINO"),
    ]), MUN, 2024)
    assert len(d) == 2
    assert d[d["alfabetizacao"]]["NomeAcao"].iloc[0] == "PROGRAMA BRASIL ALFABETIZADO"
    assert d[d["premiacao"]]["NomeAcao"].iloc[0] == "REALIZAÇÃO DE PROJETOS E PREMIAÇÕES"


def test_nomes_municipios_descarta_o_estado():
    """O universo da fiscalização são os 78 municípios; o Estado sairia como 79º."""
    nomes = execucao.nomes_municipios()
    assert len(nomes) == 78
    assert 32 not in nomes
    assert all(len(str(c)) == 7 for c in nomes)
