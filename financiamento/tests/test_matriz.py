"""A matriz de evidências do CNCA: carga, validação e cobertura. Sem rede."""

import textwrap

import pytest

from financiamento.etl import matriz
from financiamento.etl.matriz import ErroMatriz

BASE = """
esquema: 1
parametros:
  limite_x:
    valor: 70.0
    unidade: "%"
    descricao: "Um limiar qualquer."
questoes:
  - id: Q1
    enunciado: "Uma questão."
    achados:
      - id: A1.1
        enunciado: "Um achado."
        questao_matriz: Q1
        perguntas_questionario: [P1]
        fase: 1
        tipo_evidencia: direta
        confianca: alta
        indicadores:
          - id: ind_um
            rotulo: "Indicador um"
            formula: "a ÷ b"
            fonte: "TCE-ES"
            nivel: municipio_ano
            unidade: "%"
        regra_classificacao:
          indicio_risco: "valor < parametros.limite_x"
          sem_indicio: "valor >= parametros.limite_x"
        ressalvas: []
perguntas:
  - id: P1
    bloco: 1
    enunciado: "Uma pergunta."
    tipo: escolha_unica
    achados: [A1.1]
    evidencia: direta
    responde_com: "O indicador um."
"""


def escrever(tmp_path, texto):
    p = tmp_path / "m.yaml"
    p.write_text(textwrap.dedent(texto), encoding="utf-8")
    return p


# ------------------------------------------------------------ a matriz real

def test_a_matriz_do_projeto_carrega_e_cobre_as_49_perguntas():
    m = matriz.carregar()
    assert len(m.perguntas) == 49
    assert {q.id for q in m.questoes} == {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6"}
    # A matriz de planejamento lista 7+4+1+5+5+1 achados.
    assert len(m.achados) == 23
    assert [len(q.achados) for q in m.questoes] == [7, 4, 1, 5, 5, 1]


def test_todo_achado_de_proxy_ou_indicio_traz_ressalva():
    """Proxy sem ressalva vira achado na leitura — é a regra central do papel de trabalho."""
    m = matriz.carregar()
    for a in m.achados:
        if a.tipo_evidencia in ("proxy", "indicio", "inferencia"):
            assert a.ressalvas, f"{a.id} é {a.tipo_evidencia} e não traz ressalva"


def test_nenhum_status_da_matriz_se_chama_achado():
    m = matriz.carregar()
    for a in m.achados:
        assert set(a.regra) <= set(matriz.STATUS)
    assert "achado" not in matriz.STATUS


def test_cobertura_conta_o_que_o_dado_publico_nao_alcanca():
    c = matriz.carregar().cobertura()
    assert c["achados"] == 23 and c["perguntas"] == 49
    # O painel de cobertura só é honesto se as indisponíveis estiverem contadas.
    assert c["achados_por_tipo"]["indisponivel"] > 0
    assert c["perguntas_por_evidencia"]["indisponivel"] > 0
    assert c["perguntas_com_dados_pessoais"] >= 5   # bloco 1 inteiro + P9-P11


def test_perguntas_com_dado_pessoal_estao_marcadas():
    m = matriz.carregar()
    for pid in ("P2", "P4", "P9", "P11"):
        assert m.pergunta(pid).dados_pessoais, f"{pid} coleta dado pessoal e não está marcada"


# --------------------------------------------------------------- validação

def test_carrega_matriz_minima(tmp_path):
    m = matriz.carregar(escrever(tmp_path, BASE))
    assert m.param("limite_x") == 70.0
    assert m.achado("A1.1").automatizavel
    assert m.pergunta("P1").enunciado == "Uma pergunta."


def test_recusa_achado_que_aponta_para_pergunta_inexistente(tmp_path):
    p = escrever(tmp_path, BASE.replace("perguntas_questionario: [P1]", "perguntas_questionario: [P99]"))
    with pytest.raises(ErroMatriz, match="P99"):
        matriz.carregar(p)


def test_recusa_pergunta_que_aponta_para_achado_inexistente(tmp_path):
    p = escrever(tmp_path, BASE.replace("achados: [A1.1]", "achados: [A9.9]"))
    with pytest.raises(ErroMatriz, match="A9.9"):
        matriz.carregar(p)


def test_recusa_limiar_citado_e_inexistente(tmp_path):
    """Limiar mudo classifica errado em silêncio — tem de falhar na carga."""
    p = escrever(tmp_path, BASE.replace("parametros.limite_x", "parametros.limite_inexistente"))
    with pytest.raises(ErroMatriz, match="limite_inexistente"):
        matriz.carregar(p)


def test_recusa_parametro_sem_descricao(tmp_path):
    p = escrever(tmp_path, BASE.replace('    descricao: "Um limiar qualquer."\n', ""))
    with pytest.raises(ErroMatriz, match="descricao"):
        matriz.carregar(p)


def test_recusa_tipo_de_evidencia_desconhecido(tmp_path):
    p = escrever(tmp_path, BASE.replace("tipo_evidencia: direta", "tipo_evidencia: certeza"))
    with pytest.raises(ErroMatriz, match="tipo_evidencia"):
        matriz.carregar(p)


def test_recusa_status_desconhecido_na_regra(tmp_path):
    p = escrever(tmp_path, BASE.replace("indicio_risco:", "achado_confirmado:"))
    with pytest.raises(ErroMatriz, match="status inválido"):
        matriz.carregar(p)


def test_recusa_proxy_sem_ressalva(tmp_path):
    p = escrever(tmp_path, BASE.replace("tipo_evidencia: direta", "tipo_evidencia: proxy"))
    with pytest.raises(ErroMatriz, match="ressalva"):
        matriz.carregar(p)


def test_recusa_achado_nao_indisponivel_sem_indicador(tmp_path):
    texto = BASE.replace("""        indicadores:
          - id: ind_um
            rotulo: "Indicador um"
            formula: "a ÷ b"
            fonte: "TCE-ES"
            nivel: municipio_ano
            unidade: "%"
""", "        indicadores: []\n")
    with pytest.raises(ErroMatriz, match="indicador"):
        matriz.carregar(escrever(tmp_path, texto))


def test_recusa_achado_repetido(tmp_path):
    texto = BASE.replace("""      - id: A1.1
        enunciado: "Um achado.\"""", """      - id: A1.1
        enunciado: "Repetido."
        questao_matriz: Q1
        perguntas_questionario: []
        fase: 1
        tipo_evidencia: indisponivel
        confianca: baixa
        indicadores: []
        regra_classificacao:
          sem_dado_publico: "sempre"
        ressalvas: []
      - id: A1.1
        enunciado: "Um achado.\"""")
    with pytest.raises(ErroMatriz, match="repetidos"):
        matriz.carregar(escrever(tmp_path, texto))


def test_recusa_esquema_desconhecido(tmp_path):
    with pytest.raises(ErroMatriz, match="esquema"):
        matriz.carregar(escrever(tmp_path, BASE.replace("esquema: 1", "esquema: 2")))


def test_recusa_nivel_de_indicador_invalido(tmp_path):
    with pytest.raises(ErroMatriz, match="nivel"):
        matriz.carregar(escrever(tmp_path, BASE.replace("nivel: municipio_ano", "nivel: bairro")))


def test_param_inexistente_falha_alto():
    with pytest.raises(ErroMatriz, match="parâmetro inexistente"):
        matriz.carregar().param("nao_existe")


# ------------------------------------------------------------ constatações

def test_a_matriz_real_tem_constatacoes_ligadas_a_achados():
    m = matriz.carregar()
    assert len(m.constatacoes) >= 1
    conhecidos = {a.id for a in m.achados}
    for c in m.constatacoes:
        assert set(c.achados) <= conhecidos
        assert c.medida and c.consequencia


def test_achado_com_constatacao_nao_marca_municipio():
    """Dizer a mesma coisa duas vezes — uma delas injustamente — é o que isto impede."""
    m = matriz.carregar()
    a = m.achado("A3.1")
    assert a.constatacao == "C3.1"
    assert "indicio_risco" not in a.regra


def test_recusa_constatacao_inexistente(tmp_path):
    texto = BASE.replace("        fase: 1\n", "        fase: 1\n        constatacao: C9.9\n")
    with pytest.raises(ErroMatriz, match="constatação inexistente"):
        matriz.carregar(escrever(tmp_path, texto))


def test_recusa_achado_que_tem_constatacao_e_ainda_marca_indicio(tmp_path):
    texto = BASE.replace("        fase: 1\n", "        fase: 1\n        constatacao: C1\n") + """
constatacoes:
  - id: C1
    questao_matriz: Q1
    achados: [A1.1]
    enunciado: "Vale para todos."
    medida: "Medido em todos."
    fonte: "X"
    abrangencia: "todos"
    consequencia: "Não marcar município."
"""
    with pytest.raises(ErroMatriz, match="não pode gerar indício individual"):
        matriz.carregar(escrever(tmp_path, texto))
