"""A tabela de evidências: classificação, lacuna que não vira zero e proveniência. Sem rede."""

import pandas as pd
import pytest

from financiamento.etl import evidencias, matriz

MUNICIPIOS = {3205309: "Vitória"}
ANOS = (2024,)


def contexto(**tabelas) -> evidencias.Contexto:
    consultas = pd.DataFrame([{"id": "q1", "fonte": "TCE-ES", "recurso": "tcees_empenhos",
                               "descricao": "Empenhos 2024", "url": "https://exemplo/x",
                               "obtido_em": "2026-09-22T17:00:00+00:00",
                               "arquivo": "tcees/empenhos/2024/parte-1.csv.gz", "sha256": "abc123"}])
    return evidencias.Contexto(matriz=matriz.carregar(), tabelas=tabelas, municipios=MUNICIPIOS,
                               anos=ANOS, consultas=consultas)


def mensal(*, nov_dez: float, resto: float, q="q1") -> pd.DataFrame:
    linhas = [{"cod_ibge": 3205309, "ano": 2024, "subfuncao": "361", "mes": 3,
               "empenhada": resto, "liquidada": resto, "paga": resto, "q": q},
              {"cod_ibge": 3205309, "ano": 2024, "subfuncao": "361", "mes": 12,
               "empenhada": nov_dez, "liquidada": nov_dez, "paga": nov_dez, "q": q}]
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------- A4.4

#: Valores em milhões: abaixo de `concentracao_minimo_base` o achado não classifica,
#: e um fixture pequeno demais testaria o limiar errado.
MI = 1_000_000.0


def test_a4_4_classifica_concentracao_acima_da_mediana_do_exercicio():
    ctx = contexto(cnca_execucao_mensal=mensal(nov_dez=4 * MI, resto=6 * MI))
    linhas = evidencias.a4_4(ctx, ctx.matriz.achado("A4.4"))
    conc = [l for l in linhas if l["indicador"] == "concentracao_nov_dez_361"][0]
    assert conc["valor"] == pytest.approx(40.0)
    # Único município no contexto: ele é a própria mediana, então não passa de
    # mediana + 10 p.p. — é isso que o critério relativo faz, e está certo.
    assert conc["status"] == "sem_indicio"
    assert "contra a mediana" in conc["nota"]


def test_a4_4_marca_quem_esta_acima_da_mediana_dos_pares():
    """O critério é relativo ao exercício: 40% num ano de mediana 10% é indício."""
    pares = pd.concat([mensal(nov_dez=1 * MI, resto=9 * MI).assign(cod_ibge=c)
                       for c in (3200102, 3200201, 3200300)] +
                      [mensal(nov_dez=4 * MI, resto=6 * MI)], ignore_index=True)
    ctx = contexto(cnca_execucao_mensal=pares)
    ctx.municipios = {3205309: "Vitória", 3200102: "A", 3200201: "B", 3200300: "C"}
    conc = [l for l in evidencias.a4_4(ctx, ctx.matriz.achado("A4.4"))
            if l["indicador"] == "concentracao_nov_dez_361" and l["municipio_ibge"] == 3205309][0]
    assert conc["valor"] == pytest.approx(40.0) and conc["status"] == "indicio_risco"


def test_a4_4_piso_impede_marcar_num_ano_em_que_todos_concentram_pouco():
    """Estar 10 p.p. acima de uma mediana de 2% ainda é pouco: o piso segura."""
    pares = pd.concat([mensal(nov_dez=0.2 * MI, resto=9.8 * MI).assign(cod_ibge=c)
                       for c in (3200102, 3200201, 3200300)] +
                      [mensal(nov_dez=1.5 * MI, resto=8.5 * MI)], ignore_index=True)
    ctx = contexto(cnca_execucao_mensal=pares)
    ctx.municipios = {3205309: "Vitória", 3200102: "A", 3200201: "B", 3200300: "C"}
    conc = [l for l in evidencias.a4_4(ctx, ctx.matriz.achado("A4.4"))
            if l["indicador"] == "concentracao_nov_dez_361" and l["municipio_ibge"] == 3205309][0]
    assert conc["valor"] == pytest.approx(15.0) and conc["status"] == "sem_indicio"


def test_mediana_de_concentracao_ignora_base_pequena():
    d = pd.concat([mensal(nov_dez=9 * MI, resto=1 * MI),
                   mensal(nov_dez=900.0, resto=100.0).assign(cod_ibge=3200102)], ignore_index=True)
    medianas = evidencias._mediana_concentracao(d, 1_000_000.0)
    assert medianas == {2024: pytest.approx(90.0)}   # o município de base pequena não entra


def test_a4_4_percentual_negativo_e_inconclusivo_e_nunca_boa_execucao():
    """Anulação maior que empenho no período não é boa execução — é padrão a examinar."""
    ctx = contexto(cnca_execucao_mensal=mensal(nov_dez=-2 * MI, resto=12 * MI))
    conc = [l for l in evidencias.a4_4(ctx, ctx.matriz.achado("A4.4"))
            if l["indicador"] == "concentracao_nov_dez_361"][0]
    assert conc["valor"] < 0 and conc["status"] == "inconclusivo"


def test_a4_4_base_pequena_demais_nao_classifica():
    ctx = contexto(cnca_execucao_mensal=mensal(nov_dez=900.0, resto=100.0))
    conc = [l for l in evidencias.a4_4(ctx, ctx.matriz.achado("A4.4"))
            if l["indicador"] == "concentracao_nov_dez_361"][0]
    assert conc["status"] == "inconclusivo" and "abaixo do mínimo" in conc["nota"]


def test_a4_4_sem_empenho_na_subfuncao_nao_vira_zero():
    ctx = contexto(cnca_execucao_mensal=pd.DataFrame(
        columns=["cod_ibge", "ano", "subfuncao", "mes", "empenhada", "liquidada", "paga", "q"]))
    conc = [l for l in evidencias.a4_4(ctx, ctx.matriz.achado("A4.4"))
            if l["indicador"] == "concentracao_nov_dez_361"][0]
    assert conc["valor"] is None and conc["status"] == "sem_dado_publico"


# ---------------------------------------------------------------- A3.1

def dotacao(fonte="569", previsao=1000.0, empenhada=800.0):
    return pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "fonte": fonte, "NomeFonteReduzida": "X",
                          "previsao_inicial": previsao, "previsao_atualizada": previsao,
                          "empenhada": empenhada, "liquidada": empenhada, "paga": empenhada, "q": "q1"}])


def nomeada(alfabetizacao=True, previsao=500.0):
    return pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "CodigoAcao": "2.1", "NomeAcao": "ALFABETIZA",
                          "NomePrograma": "P", "fonte": "500", "alfabetizacao": alfabetizacao,
                          "premiacao": not alfabetizacao, "previsao_inicial": previsao,
                          "previsao_atualizada": previsao, "empenhada": 0.0, "q": "q1"}])


def test_a3_1_nunca_gera_indicio_individual():
    """A ausência de identificação do CNCA vale para os 78: é constatação, não achado de um."""
    for tabelas in (
        dict(cnca_execucao_dotacao_fonte=dotacao(fonte="500"), cnca_execucao_dotacao_nomeada=pd.DataFrame()),
        dict(cnca_execucao_dotacao_fonte=dotacao(), cnca_execucao_dotacao_nomeada=pd.DataFrame()),
        dict(cnca_execucao_dotacao_fonte=dotacao(), cnca_execucao_dotacao_nomeada=nomeada()),
    ):
        ctx = contexto(**tabelas)
        for l in evidencias.a3_1(ctx, ctx.matriz.achado("A3.1")):
            assert l["status"] != "indicio_risco"
            assert "C3.1" in l["nota"]


def test_a3_1_sem_fonte_569_e_sem_acao_e_sem_dado_publico():
    ctx = contexto(cnca_execucao_dotacao_fonte=dotacao(fonte="500"),
                   cnca_execucao_dotacao_nomeada=pd.DataFrame())
    l = evidencias.a3_1(ctx, ctx.matriz.achado("A3.1"))[0]
    assert l["status"] == "sem_dado_publico" and "NÃO é indício contra o município" in l["nota"]


def test_a3_1_com_fonte_569_mas_sem_acao_nomeada_e_inconclusivo():
    ctx = contexto(cnca_execucao_dotacao_fonte=dotacao(), cnca_execucao_dotacao_nomeada=pd.DataFrame())
    l = evidencias.a3_1(ctx, ctx.matriz.achado("A3.1"))[0]
    assert l["status"] == "inconclusivo"


def test_a3_1_com_acao_nomeada_pede_conferencia_de_eja():
    ctx = contexto(cnca_execucao_dotacao_fonte=dotacao(), cnca_execucao_dotacao_nomeada=nomeada())
    l = evidencias.a3_1(ctx, ctx.matriz.achado("A3.1"))[0]
    assert l["status"] == "inconclusivo" and "EJA" in l["nota"]


# ----------------------------------------------------------- Fase 2

def censo_mun(**kw):
    base = {"cod_ibge": 3205309, "ano": 2024, "escolas": 30, "mat_anos_iniciais": 4000,
            "salas_utilizadas": 300, "salas_leitura": 10, "mat_1_ano": 400, "mat_2_ano": 420,
            "turmas_1_ano": 20, "turmas_2_ano": 21, "turmas_anos_iniciais": 100,
            "escolas_anos_iniciais": 25, "escolas_com_leitura": 15, "salas_anos_iniciais": 250,
            "mat_1_2_ano": 820, "turmas_1_2_ano": 41, "pct_escolas_com_leitura": 60.0,
            "valor_referencia_cantinho": 250 * 1235.0, "q": "q1"}
    base.update(kw)
    return pd.DataFrame([base])


def test_a2_1_valor_de_referencia_e_rotulado_como_estimativa():
    ctx = contexto(cnca_censo_municipio=censo_mun())
    l = evidencias.a2_1(ctx, ctx.matriz.achado("A2.1"))[0]
    assert l["valor"] == pytest.approx(250 * 1235.0)
    assert l["status"] == "inconclusivo" and "ESTIMATIVA" in l["nota"]


def test_a2_2_diz_que_o_indicador_nao_existe_antes_do_leiaute():
    """Turma por ano escolar só existe em 2025: em 2024 é 'não existe', não zero."""
    ctx = contexto(cnca_censo_municipio=censo_mun())
    turmas = [l for l in evidencias.a2_2(ctx, ctx.matriz.achado("A2.2"))
              if l["indicador"] == "turmas_1_2_ano"][0]
    assert turmas["valor"] is None and turmas["status"] == "sem_dado_publico"
    assert "NÃO EXISTE" in turmas["nota"]


def test_a2_2_matricula_existe_em_2024():
    ctx = contexto(cnca_censo_municipio=censo_mun())
    mat = [l for l in evidencias.a2_2(ctx, ctx.matriz.achado("A2.2"))
           if l["indicador"] == "matriculas_1_2_ano"][0]
    assert mat["valor"] == pytest.approx(820) and mat["status"] == "inconclusivo"


def test_a5_4_recurso_por_aluno_proibe_leitura_causal():
    cnca = pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "pdde_cnca": 8200.0, "q": "q1"}])
    ctx = contexto(cnca_censo_municipio=censo_mun(), cnca_municipio=cnca)
    l = [x for x in evidencias.a5_4(ctx, ctx.matriz.achado("A5.4"))
         if x["indicador"] == "recurso_por_aluno_alfabetizacao"][0]
    assert l["valor"] == pytest.approx(10.0)          # 8200 ÷ 820 alunos
    assert "LEITURA CAUSAL É PROIBIDA" in l["nota"]


def test_a5_4_sem_uma_das_pontas_nao_inventa_numero():
    ctx = contexto(cnca_censo_municipio=censo_mun(), cnca_municipio=pd.DataFrame())
    l = [x for x in evidencias.a5_4(ctx, ctx.matriz.achado("A5.4"))
         if x["indicador"] == "recurso_por_aluno_alfabetizacao"][0]
    assert l["valor"] is None and l["status"] == "sem_dado_publico"


def test_a5_4_ica_compara_o_municipio_com_ele_mesmo():
    ica = pd.DataFrame([{"cod_ibge": 3205309, "edicao": 2025, "ano": 2024, "taxa": 70.0,
                         "situacao": "informado", "q": "q1"},
                        {"cod_ibge": 3205309, "edicao": 2025, "ano": 2023, "taxa": 80.0,
                         "situacao": "informado", "q": "q1"}])
    ctx = contexto(cnca_censo_municipio=censo_mun(), cnca_municipio=pd.DataFrame(), ica_municipios=ica)
    l = [x for x in evidencias.a5_4(ctx, ctx.matriz.achado("A5.4")) if x["indicador"] == "ica_e_variacao"][0]
    assert l["valor"] == pytest.approx(70.0)
    assert "-10 p.p." in l["nota"] and "nunca entre estados" in l["nota"]


def test_a6_1_usa_o_codigo_de_fonte_do_exercicio():
    """Até 2022 o ES usa 111/112/113; de 2023, 500/540. Só o par novo daria 0% em 2021."""
    f = pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "fonte": "111", "NomeFonteReduzida": "X",
                       "empenhada": 800.0, "liquidada": 0, "paga": 0, "lancamentos": 1,
                       "rpp_inscrito": 0, "rpnp_inscrito": 0, "rpp_pago": 0, "rpp_cancelado": 0,
                       "rpnp_liquidado": 0, "rpnp_pago": 0, "rpnp_cancelado": 0, "q": "q1"},
                      {"cod_ibge": 3205309, "ano": 2024, "fonte": "569", "NomeFonteReduzida": "Y",
                       "empenhada": 200.0, "liquidada": 0, "paga": 0, "lancamentos": 1,
                       "rpp_inscrito": 0, "rpnp_inscrito": 0, "rpp_pago": 0, "rpp_cancelado": 0,
                       "rpnp_liquidado": 0, "rpnp_pago": 0, "rpnp_cancelado": 0, "q": "q1"}])
    ctx = contexto(cnca_execucao_fontes=f)
    l = [x for x in evidencias.a6_1(ctx, ctx.matriz.achado("A6.1"))
         if x["indicador"] == "recurso_proprio_subfuncao_361"][0]
    assert l["valor"] == pytest.approx(80.0)
    assert "NÃO" in l["nota"] and "manutenção ordinária" in l["nota"]


# ------------------------------------------------------- constatações

def test_constatacoes_sao_ditas_uma_vez_e_nao_por_municipio():
    d = evidencias.constatacoes(contexto())
    assert len(d) == 3
    assert set(d["constatacao_id"]) == {"C3.1", "C4.5", "C4.3"}
    assert (d["medida"].str.len() > 0).all()
    assert (d["consequencia"].str.len() > 0).all()


def test_cobertura_liga_o_achado_a_constatacao():
    ctx = contexto(cnca_execucao_mensal=mensal(nov_dez=4 * MI, resto=6 * MI))
    c = evidencias.cobertura(ctx, evidencias.montar(ctx))
    assert c[c["achado_id"] == "A3.1"]["constatacao"].iloc[0] == "C3.1"
    assert c[c["achado_id"] == "A4.4"]["constatacao"].iloc[0] == ""


def test_a3_1_acao_de_premiacao_nao_conta_como_alfabetizacao():
    ctx = contexto(cnca_execucao_dotacao_fonte=dotacao(), cnca_execucao_dotacao_nomeada=nomeada(alfabetizacao=False))
    l = evidencias.a3_1(ctx, ctx.matriz.achado("A3.1"))[0]
    assert l["status"] == "inconclusivo"


# ---------------------------------------------------------------- A4.1

def test_a4_1_execucao_abaixo_do_limiar_e_indicio():
    ctx = contexto(cnca_execucao_dotacao_fonte=dotacao(previsao=1000.0, empenhada=500.0),
                   cnca_municipio=pd.DataFrame())
    l = [x for x in evidencias.a4_1(ctx, ctx.matriz.achado("A4.1")) if x["indicador"] == "execucao_fonte_569"][0]
    assert l["valor"] == pytest.approx(50.0) and l["status"] == "indicio_risco"


def test_a4_1_sem_dotacao_na_fonte_nao_vira_execucao_zero():
    ctx = contexto(cnca_execucao_dotacao_fonte=dotacao(fonte="500"), cnca_municipio=pd.DataFrame())
    l = [x for x in evidencias.a4_1(ctx, ctx.matriz.achado("A4.1")) if x["indicador"] == "execucao_fonte_569"][0]
    assert l["valor"] is None and l["status"] == "sem_dado_publico"


def test_a4_1_pdde_recebido_e_rotulado_como_recebido_nao_executado():
    cnca = pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "pdde_cnca": 12345.0, "q": "q1"}])
    ctx = contexto(cnca_execucao_dotacao_fonte=dotacao(), cnca_municipio=cnca)
    l = [x for x in evidencias.a4_1(ctx, ctx.matriz.achado("A4.1")) if x["indicador"] == "pdde_cnca_recebido"][0]
    assert l["valor"] == pytest.approx(12345.0)
    assert "RECEBIDO" in l["nota"] and "não executado" in l["nota"]


# ---------------------------------------------------------------- A4.2

def test_a4_2_sem_data_de_emissao_no_exercicio_diz_que_o_indicador_nao_existe():
    ctx = contexto(cnca_execucao_primeiro_empenho=pd.DataFrame(),
                   cnca_repasse_primeiro_mes=pd.DataFrame())
    l = evidencias.a4_2(ctx, ctx.matriz.achado("A4.2"))[0]
    assert l["valor"] is None and l["status"] == "sem_dado_publico"
    assert "não é defasagem zero" in l["nota"]


def test_a4_2_calcula_a_defasagem_e_avisa_do_erro_de_ate_30_dias():
    pe = pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "fonte": "569",
                        "primeiro_empenho": "2024-06-10", "ultimo_empenho": "2024-12-01",
                        "lancamentos_com_data": 3, "q": "q1"}])
    rep = pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "primeiro_mes": 2,
                         "primeiro_repasse": "2024-02-01", "valor": 1.0}])
    ctx = contexto(cnca_execucao_primeiro_empenho=pe, cnca_repasse_primeiro_mes=rep)
    l = evidencias.a4_2(ctx, ctx.matriz.achado("A4.2"))[0]
    assert l["valor"] == 130 and l["status"] == "indicio_risco"
    assert "erro de até 30" in l["nota"]


def test_a4_2_defasagem_negativa_e_inconclusiva():
    pe = pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "fonte": "569",
                        "primeiro_empenho": "2024-01-05", "ultimo_empenho": "2024-12-01",
                        "lancamentos_com_data": 1, "q": "q1"}])
    rep = pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "primeiro_mes": 3,
                         "primeiro_repasse": "2024-03-01", "valor": 1.0}])
    ctx = contexto(cnca_execucao_primeiro_empenho=pe, cnca_repasse_primeiro_mes=rep)
    l = evidencias.a4_2(ctx, ctx.matriz.achado("A4.2"))[0]
    assert l["valor"] < 0 and l["status"] == "inconclusivo"


# ---------------------------------------------------------------- A4.3

def test_a4_3_elemento_atipico_vira_indicio_com_aviso_de_revisao_humana():
    fe = pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "fonte": "569", "elemento": "11",
                        "DescricaoElemento": "Vencimentos", "empenhada": 900.0, "lancamentos": 2,
                        "atipico": True, "q": "q1"}])
    ctx = contexto(cnca_execucao_fonte_elemento=fe)
    l = evidencias.a4_3(ctx, ctx.matriz.achado("A4.3"))[0]
    assert l["status"] == "indicio_risco"
    assert "ATÍPICO NÃO É IRREGULAR" in l["nota"] and "revisão humana" in l["nota"]


def test_a4_3_sem_elemento_atipico_e_sem_indicio():
    fe = pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "fonte": "569", "elemento": "30",
                        "DescricaoElemento": "Material", "empenhada": 900.0, "lancamentos": 2,
                        "atipico": False, "q": "q1"}])
    ctx = contexto(cnca_execucao_fonte_elemento=fe)
    l = evidencias.a4_3(ctx, ctx.matriz.achado("A4.3"))[0]
    assert l["valor"] == pytest.approx(0.0) and l["status"] == "sem_indicio"


# ------------------------------------------------------- indisponíveis

def test_achado_indisponivel_gera_linha_por_municipio_com_o_motivo():
    ctx = contexto()
    linhas = evidencias.indisponivel(ctx, ctx.matriz.achado("A1.3"))
    assert len(linhas) == len(MUNICIPIOS)
    assert all(l["status"] == "sem_dado_publico" for l in linhas)
    assert all("Caminho:" in l["nota"] for l in linhas)


# --------------------------------------------------------- proveniência

def test_proveniencia_leva_ao_arquivo_bruto_com_hash():
    """O critério de aceite: de qualquer célula se chega ao registro bruto."""
    ctx = contexto(cnca_execucao_mensal=mensal(nov_dez=4 * MI, resto=6 * MI))
    l = evidencias.a4_4(ctx, ctx.matriz.achado("A4.4"))[0]
    assert l["endpoint_ou_arquivo"] == "tcees/empenhos/2024/parte-1.csv.gz"
    assert l["hash_bruto"] == "abc123"
    assert l["data_extracao"] == "2026-09-22T17:00:00+00:00"


def test_proveniencia_vazia_quando_nao_ha_consulta():
    ctx = contexto()
    assert ctx.proveniencia(None)["hash_bruto"] is None
    assert ctx.proveniencia("")["endpoint_ou_arquivo"] is None


def test_indicador_fora_do_yaml_falha_alto():
    ctx = contexto()
    with pytest.raises(evidencias.ErroEvidencias, match="não declara o indicador"):
        evidencias._linha(ctx, ctx.matriz.achado("A4.4"), "inventado", cod_ibge=3205309, ano=2024,
                          valor=1, status="sem_indicio", nota="", fonte="x")


def test_status_fora_do_vocabulario_falha_alto():
    ctx = contexto()
    with pytest.raises(evidencias.ErroEvidencias, match="status inválido"):
        evidencias._linha(ctx, ctx.matriz.achado("A4.4"), "concentracao_nov_dez_361", cod_ibge=3205309,
                          ano=2024, valor=1, status="achado", nota="", fonte="x")


# ------------------------------------------------------------ montagem

def test_montar_respeita_as_colunas_do_papel_de_trabalho():
    ctx = contexto(cnca_execucao_mensal=mensal(nov_dez=4 * MI, resto=6 * MI))
    d = evidencias.montar(ctx)
    assert list(d.columns) == evidencias.COLUNAS
    assert not d.empty
    assert set(d["status"]) <= set(matriz.STATUS)


def test_ano_sai_inteiro_e_nao_com_casa_decimal():
    ctx = contexto(cnca_execucao_mensal=mensal(nov_dez=4 * MI, resto=6 * MI))
    d = evidencias.montar(ctx)
    assert str(d["ano"].dtype) == "Int64"


def test_cobertura_classifica_todos_os_achados():
    """Todo achado tem situação: calculado, sem dado público, ou pendente de fase.

    Depois da Fase 3 não há mais pendentes — todos os 23 são calculados ou têm o
    'sem dado público' como resposta final. O que o teste garante é que nenhum
    achado fica de fora da cobertura em silêncio, e não qual é a distribuição.
    """
    ctx = contexto(cnca_execucao_mensal=mensal(nov_dez=4 * MI, resto=6 * MI))
    c = evidencias.cobertura(ctx, evidencias.montar(ctx))
    assert len(c) == 23
    assert (c["situacao"].str.len() > 0).all()
    situacoes = set(c["situacao"])
    assert "calculado" in situacoes
    assert "sem dado público (resposta final)" in situacoes
    validas = {"calculado", "sem dado público (resposta final)"}
    assert all(s in validas or s.startswith("pendente da fase") for s in situacoes)


def test_cobertura_de_perguntas_traz_as_49():
    c = evidencias.cobertura_perguntas(contexto())
    assert len(c) == 49
    assert c["dados_pessoais"].sum() >= 5


# --------------------------------------------------------- índices e RP

def test_indices_de_execucao_do_p24():
    ctx = contexto(cnca_execucao_dotacao_fonte=dotacao(previsao=1000.0, empenhada=800.0))
    d = evidencias.indices_execucao(ctx)
    fonte = d[d["fonte"] == "569"].iloc[0]
    assert fonte["indice_execucao_orcamentaria"] == pytest.approx(80.0)
    assert fonte["indice_liquidacao"] == pytest.approx(100.0)
    assert "(todas — função 12)" in set(d["fonte"])


def fontes_rp(**kw):
    base = {"cod_ibge": 3205309, "ano": 2024, "fonte": "569", "NomeFonteReduzida": "X",
            "empenhada": 1000.0, "liquidada": 900.0, "paga": 800.0, "lancamentos": 3,
            "rpp_inscrito": 100.0, "rpnp_inscrito": 0.0, "rpp_pago": 50.0, "rpp_cancelado": 0.0,
            "rpnp_liquidado": 0.0, "rpnp_pago": 0.0, "rpnp_cancelado": 0.0, "q": "q1"}
    base.update(kw)
    return pd.DataFrame([base])


def test_restos_a_pagar_marca_relevante_pelo_inscrito_no_exercicio():
    ctx = contexto(cnca_execucao_fontes=fontes_rp(rpp_inscrito=100.0, empenhada=1000.0))
    d = evidencias.restos_a_pagar(ctx).iloc[0]
    assert d["rpp_pct_empenhado"] == pytest.approx(10.0)
    assert d["rpp_relevante"]


def test_restos_a_pagar_prolongado_vem_da_idade_do_empenho():
    idade = pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "fonte": "569", "ano_empenho": 2021,
                           "idade_anos": 3, "rp_processado_movimentado": 400.0,
                           "rp_nao_processado_movimentado": 0.0, "q": "q1"}])
    ctx = contexto(cnca_execucao_fontes=fontes_rp(), cnca_execucao_rp_idade=idade)
    d = evidencias.restos_a_pagar(ctx).iloc[0]
    assert d["rp_idade_maxima"] == 3 and d["rpp_prolongado"]
    assert d["rpp_movimentado_antigo"] == pytest.approx(400.0)


def test_restos_a_pagar_sem_tabela_de_idade_diz_nao_medido_e_nao_falso():
    """Sem a tabela de idade, 'não há RP antigo' seria um achado inventado."""
    ctx = contexto(cnca_execucao_fontes=fontes_rp())
    d = evidencias.restos_a_pagar(ctx).iloc[0]
    assert pd.isna(d["rpp_prolongado"])
