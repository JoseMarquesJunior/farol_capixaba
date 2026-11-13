"""Insights das redes (etl/insights.py): fatos, verificação dos números e a chamada ao Claude (simulada)."""

import json
from types import SimpleNamespace

import pytest

from financiamento.etl import insights as I


# ------------------------------------------------------------------ formato
def test_formatos_como_a_pagina():
    assert I.fmt_brl(13_003_571_512.1) == "R$ 13,00 bi"
    assert I.fmt_brl(6_431_403.43) == "R$ 6,4 mi"
    assert I.fmt_brl(222_000) == "R$ 222 mil"
    assert I.fmt_pct(71.9) == "72%"
    assert I.fmt_pct(7.4) == "7,4%"
    assert I.fmt_int(2121) == "2.121"
    assert I.fmt_dec(0.494) == "0,49"


def test_mascara_cpf_no_nome():
    assert I.mascarar("ROMILDO SILVA FILHO 10382056701") == "ROMILDO SILVA FILHO [CPF omitido]"
    assert I.mascarar("EMPRESA 123.456.789-09 LTDA") == "EMPRESA [CPF omitido] LTDA"
    assert I.mascarar("CNPJ 05427772000128") == "CNPJ 05427772000128"   # 14 dígitos não é CPF


def test_numeros_do_texto():
    achados = I.numeros_do_texto("Recebeu R$ 6,4 mi (72%) em 2.121 escolas; índice 0,49; R$ 1,4 bilhão; 3R COMERCIO; 1ª vez; PNATE-2")
    unidades = [(round(v, 2), u) for v, u, _ in achados]
    assert (6_400_000.0, "brl") in unidades and (72.0, "pct") in unidades and (2121.0, "num") in unidades
    assert (0.49, "num") in unidades and (1_400_000_000.0, "brl") in unidades
    assert all(v not in (3.0, 1.0, 2.0) for v, _ in unidades)   # "3R", "1ª" e "PNATE-2" não são números do texto


# ------------------------------------------------------------------ verificação
FATOS = {"f1": {"id": "f1", "numeros": [I._n("valor", 6_431_403.43, "brl"), I._n("parcela", 71.9, "pct"), I._n("municípios", 68, "int")]},
         "f2": {"id": "f2", "numeros": [I._n("índice", 0.494, "dec")]}}


def _ins(texto, fatos=("f1",), tipo="sinal", titulo="Um padrão", prox="Comparar os preços."):
    return {"titulo": titulo, "texto": texto, "proxima_verificacao": prox, "tipo": tipo, "fatos": list(fatos)}


def test_verificacao_aceita_numero_dos_fatos_e_arredondamento():
    assert I.verificar(_ins("Atende 68 municípios e recebeu R$ 6,4 mi, 72% do mercado, de 2021 a 2025."), FATOS, [2021, 2025]) == []
    assert I.verificar(_ins("Cerca de R$ 6 mi.", ), FATOS, [2021]) == []          # arredondado, mas do fato
    assert I.verificar(_ins("Índice de 0,49.", fatos=("f2",)), FATOS, [2021]) == []


@pytest.mark.parametrize("texto, problema", [
    ("Recebeu R$ 9,1 mi.", "sem lastro"),                       # número inventado
    ("Atende 70 municípios.", "sem lastro"),
    ("O padrão indica superfaturamento.", "não sustentam"),     # afirma irregularidade
    ("Há indício de fraude.", "não sustentam"),
])
def test_verificacao_recusa(texto, problema):
    assert any(problema in p for p in I.verificar(_ins(texto), FATOS, [2021]))


def test_verificacao_recusa_fato_inexistente_tipo_e_sem_citacao():
    assert any("inexistente" in p for p in I.verificar(_ins("Texto.", fatos=("zz",)), FATOS, []))
    assert any("não cita" in p for p in I.verificar(_ins("Texto.", fatos=()), FATOS, []))
    assert any("tipo inválido" in p for p in I.verificar(_ins("Texto.", tipo="achado"), FATOS, []))


def test_numero_de_outro_fato_nao_vale():
    """O lastro é o dos fatos CITADOS: o 0,49 do f2 não sustenta um texto que só cita o f1."""
    assert any("sem lastro" in p for p in I.verificar(_ins("Índice de 0,49."), FATOS, []))


# ------------------------------------------------------------------ fatos reais
@pytest.fixture(scope="module")
def dados():
    if not I.ENTRADA.exists():
        pytest.skip("grafos.json ainda não gerado")
    return json.loads(I.ENTRADA.read_text(encoding="utf-8"))


def test_fatos_sao_deterministicos_e_bem_formados(dados):
    a, b = I.calcular_fatos(dados), I.calcular_fatos(dados)
    assert a == b and len(a) >= 15
    ids = [f["id"] for f in a]
    assert len(ids) == len(set(ids))
    for f in a:
        assert f["tipo"] in ("padrao", "sinal", "contexto") and f["link"]["visao"] in ("fornecedores", "municipios", "obras", "metodologia")
        assert f["numeros"] and all(isinstance(n["valor"], float) for n in f["numeros"])
        assert "[CPF omitido]" in f["texto"] or not I._CPF.search(f["texto"])


def test_o_texto_de_cada_fato_passa_na_propria_verificacao(dados):
    """Se o texto determinístico de um fato não passasse, o verificador recusaria redações corretas."""
    for f in I.calcular_fatos(dados):
        problemas = I.verificar(_ins(f["texto"], fatos=(f["id"],), tipo=f["tipo"], titulo="", prox=""), {f["id"]: f}, dados["meta"]["anos"])
        assert problemas == [], (f["id"], problemas)


# ------------------------------------------------------------------ chamada ao Claude (simulada)
class ClienteFalso:
    def __init__(self, saida, parada="end_turn"):
        self.pedidos, self._saida, self._parada = [], saida, parada
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.pedidos.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=json.dumps(self._saida))],
                               stop_reason=self._parada, stop_details=SimpleNamespace(category="cyber") if self._parada == "refusal" else None,
                               model="claude-opus-5-5", _request_id="req_teste",
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=500, iterations=None))


def test_redigir_pede_saida_estruturada_com_fallback(dados):
    fatos = I.calcular_fatos(dados)
    cli = ClienteFalso({"insights": []})
    r = I.redigir(fatos, cliente=cli)
    kw = cli.pedidos[0]
    assert kw["model"] == "claude-opus-5-5" and kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert kw["output_config"]["format"]["type"] == "json_schema" and kw["output_config"]["effort"] == "high"
    assert "thinking" not in kw and "temperature" not in kw
    assert all(f["id"] in kw["messages"][0]["content"] for f in fatos)          # todos os fatos vão no pedido
    assert r["proveniencia"]["id_requisicao"] == "req_teste" and len(r["proveniencia"]["prompt_sha256"]) == 64


def test_recusa_do_modelo_vira_erro_e_os_fatos_ficam(dados):
    with pytest.raises(RuntimeError, match="recusou"):
        I.redigir(I.calcular_fatos(dados), cliente=ClienteFalso({"insights": []}, parada="refusal"))


def test_montar_com_ia_aceita_o_que_tem_lastro_e_recusa_o_resto(dados):
    fatos = {f["id"]: f for f in I.calcular_fatos(dados)}
    f = fatos["obras-paradas"]
    bom = {"titulo": "Obras paradas pesam", "texto": f["texto"], "proxima_verificacao": "Ler as medições dos contratos parados.",
           "tipo": "sinal", "fatos": ["obras-paradas"]}
    ruim = {**bom, "titulo": "Inventado", "texto": "São 999 contratos parados, indício de fraude."}
    saida = I.montar(dados, com_ia=True, cliente=ClienteFalso({"insights": [bom, ruim]}))
    assert [x["titulo"] for x in saida["insights"]] == ["Obras paradas pesam"]
    assert saida["recusados"][0]["titulo"] == "Inventado" and len(saida["recusados"][0]["problemas"]) == 2
    assert saida["meta"]["redacao"]["aceitos"] == 1 and saida["meta"]["redacao"]["fatos_sha256"] == saida["meta"]["fatos_sha256"]


def test_sem_ia_a_redacao_anterior_so_vale_com_os_mesmos_fatos(dados):
    feito = I.montar(dados, com_ia=True, cliente=ClienteFalso({"insights": []}))
    feito["insights"] = [{"titulo": "x", "texto": "y", "proxima_verificacao": "z", "tipo": "padrao", "fatos": ["contexto-total"]}]
    assert I.montar(dados, anterior=feito)["insights"] == feito["insights"]
    velho = {**feito, "meta": {**feito["meta"], "fatos_sha256": "outro"}}
    novo = I.montar(dados, anterior=velho)
    assert novo["insights"] == [] and "mudaram" in novo["meta"]["aviso"]
