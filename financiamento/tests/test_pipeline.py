"""Composição dos indicadores e detecção do exercício. Sem rede."""

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from financiamento.etl import pipeline
from financiamento.etl.entes import Ente
from financiamento.etl.pipeline import MINIMO_MDE_PCT

BIMESTRAL_VAZIO = pd.DataFrame(columns=["cod_ibge", "ano", "bimestre", "tipo_rreo",
                                        "dotacao_atualizada", "empenhada_acum", "liquidada_acum"])


def _linha(cod, ano, **kw):
    base = {"cod_ibge": cod, "ente": f"M{cod}", "esfera": "M", "ano": ano, "status_dca": "ok", "status_fundeb": "ok",
            "populacao": 1000, "desp_educacao_empenhada": 5_000_000.0, "desp_educacao_liquidada": 4_000_000.0,
            "desp_educacao_paga": 3_000_000.0, "desp_total_empenhada": 20_000_000.0,
            "fundeb_receita": 2_000_000.0, "fundeb_contribuicao": 1_500_000.0, "fechamento_dca_ok": True}
    return {**base, **kw}


def _mde(cod, ano, valor):
    return {"cod_ibge": cod, "ano": ano, "valor": valor, "situacao": "informado", "fonte": "SIOPE",
            "verificado_em": "2026-09-21", "verificado": True}


def test_indicadores_derivados():
    a = pipeline.montar_anual([_linha(3200102, 2024)], BIMESTRAL_VAZIO, []).iloc[0]
    assert a["desp_educacao_per_capita"] == 5000.0
    assert a["desp_educacao_pct_total"] == 25.0
    assert a["fundeb_pct_desp_educacao"] == 40.0
    assert a["fundeb_liquido"] == 500_000.0


def test_sem_dado_fica_vazio_e_nunca_vira_zero():
    """Município sem DCA: nenhum indicador pode virar 0."""
    ausente = {"cod_ibge": 3200136, "ente": "Sem dado", "esfera": "M", "ano": 2025,
               "status_dca": "sem_dado_publicado", "status_fundeb": "sem_dado_publicado"}
    a = pipeline.montar_anual([ausente], BIMESTRAL_VAZIO, []).iloc[0]
    for coluna in ("desp_educacao_empenhada", "desp_educacao_per_capita", "desp_educacao_pct_total",
                   "fundeb_pct_desp_educacao", "fundeb_liquido", "populacao"):
        assert pd.isna(a[coluna]), coluna
    assert a["status_dca"] == "sem_dado_publicado"


def test_populacao_zero_ou_ausente_nao_gera_per_capita():
    a = pipeline.montar_anual([_linha(1, 2024, populacao=0), _linha(2, 2024, populacao=None)], BIMESTRAL_VAZIO, [])
    assert a["desp_educacao_per_capita"].isna().all()


def test_mde_sem_registro_manual_e_sem_dado_e_sem_flag():
    a = pipeline.montar_anual([_linha(3200102, 2024)], BIMESTRAL_VAZIO, []).iloc[0]
    assert a["mde_situacao"] == "sem_dado"
    assert pd.isna(a["mde_aplicado_pct"])
    assert a["mde_abaixo_minimo"] is None  # não é False: não sabemos


@pytest.mark.parametrize("valor, abaixo", [(24.99, True), (25.0, False), (31.2, False)])
def test_flag_do_minimo_constitucional(valor, abaixo):
    a = pipeline.montar_anual([_linha(3200102, 2024)], BIMESTRAL_VAZIO, [_mde(3200102, 2024, valor)]).iloc[0]
    assert MINIMO_MDE_PCT == 25.0
    assert a["mde_situacao"] == "informado_manual" and a["mde_abaixo_minimo"] is abaixo


def test_mde_de_outro_ano_nao_vaza():
    a = pipeline.montar_anual([_linha(3200102, 2024)], BIMESTRAL_VAZIO, [_mde(3200102, 2023, 10.0)]).iloc[0]
    assert a["mde_situacao"] == "sem_dado"


def test_mde_duplicado_e_erro():
    with pytest.raises(Exception, match="mais de um registro"):
        pipeline.montar_anual([_linha(3200102, 2024)], BIMESTRAL_VAZIO,
                              [_mde(3200102, 2024, 20.0), _mde(3200102, 2024, 30.0)])


def test_marcador_manual_nao_verificado_e_ignorado():
    marcador = {"cod_ibge": 3200102, "ano": 2024, "valor": None, "situacao": "nao_verificado",
                "fonte": None, "verificado_em": None, "verificado": False}
    a = pipeline.montar_anual([_linha(3200102, 2024)], BIMESTRAL_VAZIO, [marcador]).iloc[0]
    assert a["mde_situacao"] == "sem_dado"


def test_conferencia_rreo_contra_dca():
    bim = pd.DataFrame([{"cod_ibge": 3200102, "ano": 2024, "bimestre": 6, "tipo_rreo": "RREO Simplificado",
                         "dotacao_atualizada": 6e6, "empenhada_acum": 5_050_000.0, "liquidada_acum": 4e6}])
    a = pipeline.montar_anual([_linha(3200102, 2024)], bim, []).iloc[0]
    assert a["dif_rreo_dca_pct"] == 1.0 and a["tipo_rreo_b6"] == "RREO Simplificado"
    v = pipeline.verificacoes(pd.DataFrame([a]), [])
    assert v["rreo_vs_dca"]["divergentes"] == 1  # 1% > tolerância de 0,5%


def test_fechamento_dca_falho_e_reportado():
    anual = pipeline.montar_anual([_linha(1, 2024), _linha(2, 2024, fechamento_dca_ok=False)], BIMESTRAL_VAZIO, [])
    v = pipeline.verificacoes(anual, [])
    assert [f["cod_ibge"] for f in v["fechamento_dca"]["falhas"]] == [2]
    assert v["codigos_ibge_7_digitos"] is False  # códigos de teste têm 1 dígito


def _sub(cod, ano, codigo, nome, empenhada):
    return {"cod_ibge": cod, "ano": ano, "codigo": codigo, "nome": nome,
            "empenhada": empenhada, "liquidada": empenhada, "paga": empenhada}


def test_subfuncoes_ganham_participacao_e_ordem():
    anual = pipeline.montar_anual([_linha(3200102, 2024)], BIMESTRAL_VAZIO, [])
    sub = pd.DataFrame([_sub(3200102, 2024, "12.122", "Administração Geral", 1_000_000.0),
                        _sub(3200102, 2024, "12.361", "Ensino Fundamental", 4_000_000.0)])
    s = pipeline._ordenar_subfuncoes(sub, anual)
    assert list(s["codigo"]) == ["12.361", "12.122"]  # da maior para a menor
    assert list(s["pct_educacao"]) == [80.0, 20.0]    # sobre os 5.000.000 da função 12
    assert list(s["ente"]) == ["M3200102", "M3200102"]


def test_catalogo_de_subfuncoes_ordena_por_volume_e_ignora_o_estado():
    anual = pipeline.montar_anual(
        [_linha(3200102, 2024), _linha(32, 2024, esfera="E", ente="ES")], BIMESTRAL_VAZIO, [])
    sub = pd.DataFrame([_sub(3200102, 2024, "12.361", "Ensino Fundamental", 4_000_000.0),
                        _sub(3200102, 2024, "12.122", "Administração Geral", 1_000_000.0),
                        _sub(32, 2024, "12.362", "Ensino Médio", 9_000_000.0)])
    cat = pipeline.catalogo_subfuncoes(pipeline._ordenar_subfuncoes(sub, anual))
    assert [c["codigo"] for c in cat] == ["12.361", "12.122"]  # o Ensino Médio é só do Estado


def test_subfuncao_que_nao_fecha_e_reportada():
    """Se o detalhe não somar a função 12, a conferência precisa acusar."""
    anual = pipeline.montar_anual(
        [_linha(1, 2024, subfuncoes_fecham=True), _linha(2, 2024, subfuncoes_fecham=False)], BIMESTRAL_VAZIO, [])
    v = pipeline.verificacoes(anual, [])
    assert [f["cod_ibge"] for f in v["subfuncoes_fecham"]["falhas"]] == [2]


def test_parse_anos():
    assert pipeline.parse_anos("2021-2025") == [2021, 2022, 2023, 2024, 2025]
    assert pipeline.parse_anos("2024,2022") == [2022, 2024]


# ------------------------------------------------------ detecção do exercício

class _Cliente:
    """DCA 'publicada' só para os anos em `publicados`."""

    def __init__(self, publicados):
        self.publicados = publicados

    def consultar(self, endpoint, **p):
        return SimpleNamespace(itens=[{"x": 1}] if p["an_exercicio"] in self.publicados else [])


def _entes(n=40):
    return [Ente(3200000 + i, f"M{i}", "M", 1000 - i) for i in range(n)]


def test_detecta_o_exercicio_mais_recente_publicado(monkeypatch):
    def descobrir(cliente, ano, refs):
        if ano not in cliente.publicados:
            raise pipeline.parsing.ErroParsing("sem anexos")
        return SimpleNamespace(dca_despesa_funcao="DCA-Anexo I-E")

    monkeypatch.setattr(pipeline.mod_anexos, "descobrir", descobrir)
    lista = _entes()
    # Em set/2026 o exercício 2025 já saiu; 2026 ainda não.
    assert pipeline.detectar_ultimo_exercicio(_Cliente({2024, 2025}), lista, lista[:5], date(2026, 9, 21)) == 2025
    # Se a DCA de 2025 ainda não saiu, cai para 2024.
    assert pipeline.detectar_ultimo_exercicio(_Cliente({2024}), lista, lista[:5], date(2026, 3, 1)) == 2024


def test_exercicio_com_cobertura_baixa_e_ignorado(monkeypatch):
    monkeypatch.setattr(pipeline.mod_anexos, "descobrir",
                        lambda c, ano, refs: SimpleNamespace(dca_despesa_funcao="DCA-Anexo I-E"))

    class Parcial:
        def consultar(self, endpoint, **p):
            # 2025: só um município da amostra publicou; 2024: todos.
            publicou = p["an_exercicio"] == 2024 or p["id_ente"] == 3200000
            return SimpleNamespace(itens=[{"x": 1}] if publicou else [])

    lista = _entes()
    assert pipeline.detectar_ultimo_exercicio(Parcial(), lista, lista[:5], date(2026, 9, 21)) == 2024
