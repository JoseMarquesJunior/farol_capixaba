"""Parsing das respostas do SICONFI.

Os valores esperados vêm da resposta real da API para Vitória em 2024, conferidos
à mão contra o JSON na exploração (2026-09-21).
"""

import pytest

from financiamento.etl import parsing
from financiamento.etl.parsing import ErroParsing

from .conftest import linha


# ----------------------------------------------------------------- código IBGE

def test_codigo_ibge_municipal_tem_7_digitos():
    assert parsing.validar_ibge("3205309") == 3205309
    assert parsing.validar_ibge(3205309) == 3205309


@pytest.mark.parametrize("ruim", ["320530", "32053090", "abc", "", None, "3205309.0"])
def test_codigo_ibge_municipal_invalido(ruim):
    with pytest.raises(ErroParsing):
        parsing.validar_ibge(ruim)


def test_codigo_do_estado_tem_2_digitos():
    assert parsing.validar_ibge(32, municipio=False) == 32
    with pytest.raises(ErroParsing):
        parsing.validar_ibge(3205309, municipio=False)


# ------------------------------------------------------------------ DCA I-E

def test_educacao_dca_valores_reais(dca_ie):
    edu = parsing.educacao_dca(dca_ie)
    assert edu["empenhada"] == pytest.approx(805_765_334.24)
    assert edu["liquidada"] == pytest.approx(752_860_573.31)
    assert edu["paga"] == pytest.approx(740_591_170.17)
    assert edu["total_empenhada"] == pytest.approx(3_291_918_600.79)


def test_educacao_dca_ignora_subfuncoes(dca_ie):
    """'12.361 - Ensino Fundamental' etc. não podem ser confundidas com a função 12."""
    itens = [l for l in dca_ie if l["conta"].startswith("12.")]
    assert itens, "o fixture deveria ter subfunções da 12"
    assert parsing.educacao_dca(itens) is None


def test_soma_das_funcoes_bate_com_o_total_do_anexo(dca_ie):
    """Conferência pedida: a soma da despesa por função fecha com o total do anexo."""
    soma, total = parsing.soma_funcoes_dca(dca_ie)
    assert set(total) >= {"empenhada", "liquidada", "paga"}
    for estagio in ("empenhada", "liquidada", "paga"):
        assert soma[estagio] == pytest.approx(total[estagio], abs=1.0), estagio


def test_soma_das_funcoes_nao_conta_subfuncao_em_dobro(dca_ie):
    """Se as subfunções entrassem na soma, ela passaria muito do total."""
    soma, total = parsing.soma_funcoes_dca(dca_ie)
    assert soma["empenhada"] < 1.01 * total["empenhada"]


# -------------------------------------------------------------- subfunções

def test_subfuncoes_da_educacao_valores_reais(dca_ie):
    subs = parsing.subfuncoes_dca(dca_ie)
    por_codigo = {s["codigo"]: s for s in subs}
    assert por_codigo["12.361"]["nome"] == "Ensino Fundamental"
    assert por_codigo["12.365"]["nome"] == "Educação Infantil"
    assert por_codigo["12.361"]["empenhada"] == pytest.approx(417_363_662.41, abs=0.01)
    assert por_codigo["12.361"]["paga"] == pytest.approx(376_635_033.66, abs=0.01)
    assert por_codigo["12.122"]["nome"] == "Administração Geral"
    assert set(por_codigo) == {"12.361", "12.365", "12.366", "12.367", "12.122"}


def test_subfuncoes_somam_a_funcao(dca_ie):
    """Conferência de fechamento: o detalhe é completo, não uma amostra."""
    subs = parsing.subfuncoes_dca(dca_ie)
    assert sum(s["empenhada"] for s in subs) == pytest.approx(parsing.educacao_dca(dca_ie)["empenhada"], abs=1.0)
    assert sum(s["paga"] for s in subs) == pytest.approx(parsing.educacao_dca(dca_ie)["paga"], abs=1.0)


def test_subfuncoes_ignoram_as_outras_funcoes(dca_ie):
    """'10.301 - Atenção Básica' é subfunção da Saúde e não pode entrar na Educação."""
    codigos = {s["codigo"] for s in parsing.subfuncoes_dca(dca_ie)}
    assert all(c.startswith("12.") for c in codigos)
    saude = {s["codigo"] for s in parsing.subfuncoes_dca(dca_ie, funcao="10")}
    assert "10.301" in saude and "FU10" in saude  # o agregado da Saúde é FU10, não FU12
    assert all(c.startswith("10.") or c == "FU10" for c in saude)
    assert not (saude & codigos)


def test_agregado_demais_subfuncoes_entra_como_subfuncao():
    """'FU12 - Demais Subfunções' é valor real; descartá-lo abriria buraco na soma."""
    itens = [linha("FU12 - Demais Subfunções", "Despesas Empenhadas", 1234.0),
             linha("12.361 - Ensino Fundamental", "Despesas Empenhadas", 1000.0)]
    subs = {s["codigo"]: s for s in parsing.subfuncoes_dca(itens)}
    assert subs["FU12"]["empenhada"] == 1234.0 and subs["FU12"]["nome"] == "Demais Subfunções"
    assert sum(s["empenhada"] for s in subs.values()) == 2234.0


def test_linha_da_funcao_nao_e_confundida_com_subfuncao():
    """'12 - Educação' é o total; entrar como subfunção contaria em dobro."""
    assert parsing.subfuncoes_dca([linha("12 - Educação", "Despesas Empenhadas", 50.0)]) == []


def test_sem_subfuncao_devolve_lista_vazia():
    assert parsing.subfuncoes_dca([]) == []


def test_funcao_ausente_devolve_none_e_nunca_zero():
    assert parsing.educacao_dca([linha("01 - Legislativa", "Despesas Empenhadas", 10.0)]) is None
    assert parsing.educacao_dca([]) is None


def test_duplicata_identica_e_tolerada():
    itens = [linha("12 - Educação", "Despesas Empenhadas", 50.0)] * 2
    assert parsing.educacao_dca(itens)["empenhada"] == 50.0


def test_duplicata_com_valores_diferentes_para_o_processamento():
    itens = [linha("12 - Educação", "Despesas Empenhadas", 50.0), linha("12 - Educação", "Despesas Empenhadas", 60.0)]
    with pytest.raises(ErroParsing, match="valores diferentes"):
        parsing.educacao_dca(itens)


# ------------------------------------------------------------------ FUNDEB

def test_fundeb_valores_reais(dca_ic):
    f = parsing.fundeb_dca(dca_ic)
    assert f["receita"] == pytest.approx(303_786_072.41)
    assert f["contribuicao"] == pytest.approx(223_345_710.44)


def test_fundeb_soma_a_complementacao_da_uniao(dca_ic_com_complementacao):
    """Regressão do achado da auditoria: o I-C lança a complementação em conta separada.

    Conferido ao centavo contra o DCA I-HI ('Transferências do FUNDEB' = 38.202.456,35).
    Sem somar a complementação, o município aparecia 17% abaixo do que recebeu.
    """
    f = parsing.fundeb_dca(dca_ic_com_complementacao)
    assert f["receita_fundo"] == pytest.approx(31_570_760.18)
    assert f["complementacao_uniao"] == pytest.approx(6_631_696.17)
    assert f["receita"] == pytest.approx(38_202_456.35)
    assert f["contribuicao"] == pytest.approx(17_632_055.40)  # = 'Transferências ao FUNDEB' do I-HI


def test_fundeb_com_codigos_de_conta_de_2021(dca_ic_2021_codigos_antigos):
    """Em 2021 os códigos eram 1.7.5.8.01 e 1.7.1.8.09; o casamento é pelo nome da conta."""
    f = parsing.fundeb_dca(dca_ic_2021_codigos_antigos)
    assert f["receita_fundo"] == pytest.approx(82_097_002.79)
    assert f["complementacao_uniao"] == pytest.approx(32_613.60)
    assert f["receita"] == pytest.approx(82_129_616.39)


def test_fundeb_sem_complementacao_nao_inventa_a_chave(dca_ic):
    """Vitória não recebe complementação: a chave fica ausente (sem linha), não vale 0."""
    assert "complementacao_uniao" not in parsing.fundeb_dca(dca_ic)


def test_complementacao_sem_a_linha_do_fundo_nao_vira_total_parcial():
    compl = linha("1.7.1.5.00.0.0 - Transferências de Recursos de Complementação da União ao Fundo de Manutenção e "
                  "Desenvolvimento da Educação Básica e de Valorização dos Profissionais da Educação - FUNDEB",
                  "Receitas Brutas Realizadas", 10.0, cod_conta="RO1.7.1.5.00.0.0")
    assert parsing.fundeb_dca([compl]) is None


_NOME_FUNDEB = "Transferências de Recursos do Fundo de Manutenção e Desenvolvimento da Educação Básica - FUNDEB"


def test_fundeb_conta_filha_nao_conta_em_dobro():
    itens = [
        linha(f"1.7.5.1.00.0.0 - {_NOME_FUNDEB}", "Receitas Brutas Realizadas", 100.0, cod_conta="RO1.7.5.1.00.0.0"),
        linha(f"1.7.5.1.01.0.0 - {_NOME_FUNDEB} (VAAF)", "Receitas Brutas Realizadas", 60.0, cod_conta="RO1.7.5.1.01.0.0"),
        linha(f"1.7.5.1.02.0.0 - {_NOME_FUNDEB} (VAAT)", "Receitas Brutas Realizadas", 40.0, cod_conta="RO1.7.5.1.02.0.0"),
    ]
    assert parsing.fundeb_dca(itens)["receita"] == 100.0


def test_fundeb_soma_filhas_quando_o_pai_nao_vem():
    itens = [
        linha(f"1.7.5.1.01.0.0 - {_NOME_FUNDEB} (VAAF)", "Receitas Brutas Realizadas", 60.0, cod_conta="RO1.7.5.1.01.0.0"),
        linha(f"1.7.5.1.02.0.0 - {_NOME_FUNDEB} (VAAT)", "Receitas Brutas Realizadas", 40.0, cod_conta="RO1.7.5.1.02.0.0"),
    ]
    assert parsing.fundeb_dca(itens)["receita"] == 100.0


def test_fundeb_ausente_devolve_none():
    outra = linha("1.1.1.2.50.0.0 - IPTU", "Receitas Brutas Realizadas", 5.0, cod_conta="RO1.1.1.2.50.0.0")
    assert parsing.fundeb_dca([outra]) is None


def test_fundeb_sem_deducao_nao_inventa_contribuicao_zero():
    itens = [linha(f"1.7.5.1.00.0.0 - {_NOME_FUNDEB}", "Receitas Brutas Realizadas", 100.0, cod_conta="RO1.7.5.1.00.0.0")]
    assert "contribuicao" not in parsing.fundeb_dca(itens)


# ----------------------------------------------------------------- RREO A02

def test_educacao_rreo_valores_reais(rreo_a02):
    edu = parsing.educacao_rreo(rreo_a02)
    assert edu["empenhada_acum"] == pytest.approx(805_765_334.24, rel=1e-9)
    assert set(edu) == {"dotacao_atualizada", "empenhada_acum", "liquidada_acum"}


def test_rreo_6_bimestre_bate_com_o_fechamento_da_dca(rreo_a02, dca_ie):
    """Mesmo escopo (exceto intra-orçamentárias): o 6º bimestre do RREO fecha com a DCA."""
    assert parsing.educacao_rreo(rreo_a02)["empenhada_acum"] == pytest.approx(
        parsing.educacao_dca(dca_ie)["empenhada"], abs=1.0)


def test_rreo_subfuncao_nao_e_confundida_com_educacao(rreo_a02):
    so_infantil = [l for l in rreo_a02 if l["conta"] == "Educação Infantil"]
    assert so_infantil
    assert parsing.educacao_rreo(so_infantil) is None


def test_rreo_bloco_intra_nao_entra():
    itens = [linha("Educação", "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)", 9.0, cod_conta="RREO2TotalDespesasIntra")]
    assert parsing.educacao_rreo(itens) is None


# ---------------------------------------------------------------- utilitários

def test_norm_ignora_acento_caixa_e_espacos():
    assert parsing.norm("  Despesas   EMPENHADAS ATÉ o Bimestre ") == "despesas empenhadas ate o bimestre"
    assert parsing.norm(None) == ""


def test_populacao_unica_ou_none_ou_erro():
    assert parsing.populacao([linha("a", "b", 1, populacao=331785), linha("c", "d", 2, populacao=331785)]) == 331785
    assert parsing.populacao([linha("a", "b", 1, populacao=None)]) is None
    with pytest.raises(ErroParsing):
        parsing.populacao([linha("a", "b", 1, populacao=1), linha("c", "d", 2, populacao=2)])
