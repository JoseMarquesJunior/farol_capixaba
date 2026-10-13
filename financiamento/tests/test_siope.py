"""SIOPE (Anexo 8 em PDF): extração por rótulo nos três layouts e conferência interna. Sem rede."""

import pytest

from financiamento.etl import siope


@pytest.fixture(scope="module")
def resultados(pdf_siope):
    return {chave: siope.indicadores(siope.texto_pdf(dados)) for chave, dados in pdf_siope.items()}


@pytest.mark.parametrize("chave, mde, fundeb70, receita_impostos", [
    (("320530", 2021), 26.42, 88.25, 1_668_810_476.03),   # layout 2021–2022 (itens 1–54)
    (("320530", 2024), 30.36, 100.00, 2_395_368_833.59),  # layout 2024–2025 (itens 1–40)
    (("320240", 2023), 25.58, None, None),                # layout 2023 (itens 1–45), Guarapari
])
def test_indicadores_legais_por_layout(resultados, chave, mde, fundeb70, receita_impostos):
    r = resultados[chave]
    assert r.valores["mde_pct"] == pytest.approx(mde)
    if fundeb70 is not None:
        assert r.valores["fundeb70_pct"] == pytest.approx(fundeb70)
    if receita_impostos is not None:
        assert r.valores["receita_resultante_impostos"] == pytest.approx(receita_impostos, abs=0.01)


def test_nenhum_aviso_nos_pdfs_reais(resultados):
    assert {k: r.avisos for k, r in resultados.items() if r.avisos} == {}


def test_vitoria_2024_valores_de_controle(resultados):
    v = resultados[("320530", 2024)].valores
    assert v["receita_impostos_proprios"] == pytest.approx(1_247_123_412.89, abs=0.01)
    assert v["fundeb_recebido"] == pytest.approx(304_624_799.98, abs=0.01)   # com rendimentos de aplicação
    assert v["fundeb_principal"] == pytest.approx(303_786_072.41, abs=0.01)  # = DCA I-C de Vitória 2024
    assert v["mde_exigido"] == pytest.approx(598_842_208.40, abs=0.01)
    assert v["mde_aplicado"] == pytest.approx(727_289_474.28, abs=0.01)
    assert v["despesa_total_educacao"] == pytest.approx(873_106_318.01, abs=0.01)
    assert v["pnae"] == pytest.approx(5_503_506.34, abs=0.01)
    assert v["mde_compensacao_ec119"] is None  # a seção da EC 119/2022 só existe no layout de 2023


def test_ec119_compensacao_explica_o_exigido(resultados):
    """Guarapari 2023: exigido inclui R$ 13,5 mi da EC 119; o % continua sobre a receita do ano."""
    v = resultados[("320240", 2023)].valores
    assert v["mde_compensacao_ec119"] == pytest.approx(13_481_439.43, abs=0.01)
    assert v["mde_aplicado"] < v["mde_exigido"]          # não alcançou o exigido COM a compensação…
    assert v["mde_pct"] >= siope.MINIMO_MDE_PCT           # …embora tenha cumprido os 25% do ano


def test_percentual_adulterado_vira_aviso(pdf_siope):
    texto = siope.texto_pdf(pdf_siope[("320530", 2024)]).replace("727.289.474,28 30,36", "727.289.474,28 35,00")
    r = siope.indicadores(texto)
    assert any("MDE" in a for a in r.avisos)


def test_rotulo_ausente_vira_aviso_e_nao_excecao():
    r = siope.indicadores("1- RECEITA DE IMPOSTOS 10,00 20,00\n")
    assert r.valores["receita_impostos_proprios"] == 20.0
    assert r.valores["mde_pct"] is None
    assert any("mde_exigido" in a for a in r.avisos)


def test_extrai_rotulo_quebrado_em_linhas_e_ignora_numero_de_nota():
    texto = ("15- MÍNIMO DE 70% DO FUNDEB NA REMUNERAÇÃO\nDOS PROFISSIONAIS DA EDUCAÇÃO BÁSICA "
             "213.237.359,99 304.624.799,98 304.624.799,98 100,00\n"
             "4- TOTAL DESTINADO AO FUNDEB - equivalente a 20% DE ((2.1.1) + (2.2))11 194.016.986,20 223.345.710,44\n")
    itens = siope.extrair_itens(texto)
    assert itens[0].numero == "15" and itens[0].valores == [213_237_359.99, 304_624_799.98, 304_624_799.98, 100.0]
    assert "profissionais da educacao basica" in itens[0].chave
    assert itens[1].valores == [194_016_986.20, 223_345_710.44]  # "(2.1.1)" e a nota "11" não são valores


@pytest.mark.parametrize("cod, esperado", [(3205309, "320530"), (3200102, "320010")])
def test_ibge6(cod, esperado):
    assert siope.ibge6(cod) == esperado


def test_ibge6_recusa_codigo_que_nao_e_de_municipio():
    with pytest.raises(ValueError):
        siope.ibge6(32)


def test_url_do_ftp():
    assert siope.url_ftp(3205309, 2024) == "ftp://ftp.fnde.gov.br/web/siope/RREO/RREO_Municipal_320530_6_2024.pdf"


def test_modo_offline_sem_cache_nao_usa_rede(tmp_path):
    c = siope.ClienteFtpSiope(tmp_path, atualizar="offline")
    a = c.baixar(3205309, 2024)
    assert not a.existe and a.obtido_em == ""  # "não coletado", distinto de "não publicado"


def test_arquivo_inexistente_e_cacheado_como_fato(tmp_path):
    c = siope.ClienteFtpSiope(tmp_path)
    c._gravar(c._meta(3205309, 2024), siope.Arquivo(False, siope.url_ftp(3205309, 2024), "2026-09-22T00:00:00+00:00", None))
    a = siope.ClienteFtpSiope(tmp_path, atualizar="nao").baixar(3205309, 2024)
    assert a.do_cache and not a.existe
    linha, consulta, _ = siope.processar(siope.ClienteFtpSiope(tmp_path), 3205309, 2024)
    assert linha["status_siope"] == "sem_pdf_publicado" and consulta is None
