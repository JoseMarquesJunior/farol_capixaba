"""Dossiê da empresa (etl/dossie.py), Análise com IA (etl/analise_ia.py) e o servidor local."""

import json
import threading
from types import SimpleNamespace

import pytest
import requests

from financiamento import servidor_redes as S
from financiamento.etl import analise_ia as IA
from financiamento.etl import dossie as D


# ------------------------------------------------------------------ regras do dossiê
@pytest.mark.parametrize("modalidade, base, objeto, arp, esperado", [
    ("", "", "Aquisição de uniforme através de adesão da ATA DE REGISTRO DE PREÇOS Nº 004/2023", "", "adesao_ata"),
    ("", "", "transporte escolar", "12", "adesao_ata"),
    ("", "Art. 75, inciso VIII, Lei 14.133/2021", "serviço", "", "emergencia"),
    ("", "Art. 24, inciso IV, Lei 8.666/1993", "serviço", "", "emergencia"),
    ("", "Art. 74, inciso II, Lei 14.133/2021", "show", "", "inexigibilidade"),
    ("", "Art. 75, inciso II, Lei 14.133/2021", "compra", "", "dispensa"),
    ("", "", "transporte escolar", "", "sem_modalidade"),
    ("Pregão Eletrônico", "Lei 14.133/2021", "transporte escolar", "", None),
])
def test_sinal_da_base_legal(modalidade, base, objeto, arp, esperado):
    assert D.classificar_base_legal(modalidade, base, objeto, arp) == esperado


def test_links_especificos_e_pagina_do_diario():
    assert D.especifico("https://www.vilapavao.es.gov.br/uploads/contrato/contrato-anexo-ed6d16.pdf")
    assert D.especifico("http://transparencia.serra.es.gov.br/Contrato.Detalhes.aspx?contratoId=33064")
    assert not D.especifico("https://ioes.dio.es.gov.br/dom") and not D.especifico(".")
    assert D.url_dioes("https://ioes.dio.es.gov.br/portal/visualizacoes/pdf/7474/#/p:9/e:7474") == \
        "https://ioes.dio.es.gov.br/apifront/portal/edicoes/pdf_diario/7474/9"


def test_inventario_prioriza_contratos_de_maior_valor_e_nao_repete():
    d = {"contratos": {"contratos": [
        {"numero": "1/2024", "municipio": "A", "valor_atual": 10.0, "url_contrato": "https://x.gov.br/c/1001.pdf", "url_publicacao": "", "url_edital": "https://x.gov.br/e/9999.pdf"},
        {"numero": "2/2024", "municipio": "B", "valor_atual": 50.0, "url_contrato": "https://x.gov.br/c/2002.pdf", "url_publicacao": "https://x.gov.br/c/2002.pdf", "url_edital": ""}]},
        "obras": [], "pncp": {"contratos": []}}
    inv = D.inventario(d)
    assert [x["url"] for x in inv] == ["https://x.gov.br/c/2002.pdf", "https://x.gov.br/c/1001.pdf", "https://x.gov.br/e/9999.pdf"]


# ------------------------------------------------------------------ conferência da IA
def test_conferencia_de_trechos_numeros_e_palavras(tmp_path):
    texto = tmp_path / "d1.txt"
    texto.write_text("[página 1]\nCLÁUSULA SEGUNDA — O valor global do contrato é de R$ 1.250.000,00, com vigência de 12 meses. Assinado em 27/12/2024.", encoding="utf-8")
    docs = {"d1": {"id": "d1", "texto_arquivo": str(texto), "escaneado": False}, "d2": {"id": "d2", "escaneado": True}}
    pedido = {"resumo": {"empresa": "X", "contratos": 3}, "usados": [{"id": "d1"}, {"id": "d2"}]}
    ev_ok = {"documento": "d1", "pagina": 1, "trecho": "o valor global do contrato é de R$ 1.250.000,00"}
    saida = {"constatacoes": [
        {"titulo": "Valor alto", "texto": "O contrato vale R$ 1,25 mi por 12 meses.", "tipo": "sinal", "evidencias": [ev_ok], "proxima_verificacao": "Ler os aditivos.",
         "normas": [{"dispositivo": "14133.art125", "data_referencia": "2024-12-27", "aplicacao": "Acréscimos até 25% do valor inicial. Separar aditivo de prorrogação."}]},
        {"titulo": "Sinal sem norma", "texto": "O contrato vale R$ 1,25 mi.", "tipo": "sinal", "evidencias": [ev_ok], "proxima_verificacao": "-"},
        {"titulo": "Trecho inventado", "texto": "Vigência de 12 meses.", "tipo": "padrao", "evidencias": [{"documento": "d1", "pagina": 1, "trecho": "prorrogação automática por 60 meses"}], "proxima_verificacao": "-"},
        {"titulo": "Número inventado", "texto": "O contrato vale R$ 9,9 mi.", "tipo": "sinal", "evidencias": [ev_ok], "proxima_verificacao": "-"},
        {"titulo": "Escaneado", "texto": "Assinatura em página escaneada.", "tipo": "contexto", "evidencias": [{"documento": "d2", "pagina": 2, "trecho": "assinatura"}], "proxima_verificacao": "-"},
        {"titulo": "Afirma demais", "texto": "Há fraude no contrato.", "tipo": "sinal", "evidencias": [ev_ok], "proxima_verificacao": "-"},
    ]}
    r = IA.conferir(saida, pedido, docs)
    situacao = {c["titulo"]: c["conferencia"] for c in r["constatacoes"]}
    assert situacao == {"Valor alto": "conferida", "Sinal sem norma": "com ressalvas", "Trecho inventado": "com ressalvas", "Número inventado": "com ressalvas",
                        "Escaneado": "não conferível"}
    assert [x["titulo"] for x in r["recusadas"]] == ["Afirma demais"]
    c = {c["titulo"]: c for c in r["constatacoes"]}
    n = c["Valor alto"]["normas"][0]
    assert n["rotulo"] == "Lei nº 14.133/2021, art. 125" and n["texto"].startswith("Art. 125. Texto de 14133.art125") and n["aplicacao"].startswith("Acréscimos")
    assert "sinal sem base normativa indicada" in c["Sinal sem norma"]["problemas"]


# ------------------------------------------------------------------ nunca refazer sem pedido
class ClienteFalso:
    def __init__(self):
        self.chamadas = 0
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream, count_tokens=lambda **kw: SimpleNamespace(input_tokens=1234)))

    def _stream(self, **kw):
        self.chamadas += 1
        assert kw["model"] == "claude-opus-5-5" and kw["fallbacks"] == "default" and kw["output_config"]["format"]["type"] == "json_schema"
        msg = SimpleNamespace(stop_reason="end_turn", model="claude-opus-5-5", _request_id="req_x",
                              usage=SimpleNamespace(input_tokens=1000, output_tokens=200, iterations=None),
                              content=[SimpleNamespace(type="text", text=json.dumps({"resumo": "ok", "constatacoes": [], "limites": [], "documentos_lidos": []}))])
        cm = SimpleNamespace(__enter__=lambda s=None: SimpleNamespace(get_final_message=lambda: msg), __exit__=lambda *a: False)
        return type("CM", (), {"__enter__": lambda self: SimpleNamespace(get_final_message=lambda: msg), "__exit__": lambda self, *a: False})()


@pytest.fixture
def pastas(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "PASTA_RESULTADOS", tmp_path / "analises")
    monkeypatch.setattr(D, "PASTA_CRUS", tmp_path / "crus")
    raiz = "12345678"
    (tmp_path / "analises" / raiz).mkdir(parents=True)
    d = {"meta": {"raiz": raiz, "nome": "EMPRESA TESTE", "gerado_em": "2026-10-27T00:00:00+00:00", "cnpj_consultado": raiz + "000199"}, "documentos": []}
    (tmp_path / "analises" / raiz / "dossie.json").write_text(json.dumps(d), encoding="utf-8")
    return raiz


def test_analise_e_gravada_e_reaproveitada(pastas):
    cli = ClienteFalso()
    a = IA.analisar(pastas, cliente=cli)
    assert cli.chamadas == 1 and a["meta"]["custo_usd"] == pytest.approx(1000 * 4 / 1e6 + 200 * 20 / 1e6)
    b = IA.analisar(pastas, cliente=cli)                   # mesmo pedido: lê do disco
    assert cli.chamadas == 1 and b["_reaproveitada"] and b["meta"]["hash_pedido"] == a["meta"]["hash_pedido"]
    IA.analisar(pastas, cliente=cli, refazer=True)          # só refaz quando se pede
    assert cli.chamadas == 2 and len(IA.historico(pastas)) == 2   # e a anterior fica no histórico


def test_dossie_gravado_nao_vai_a_rede(pastas, monkeypatch):
    monkeypatch.setattr(D, "Coletor", lambda *a, **k: (_ for _ in ()).throw(AssertionError("não devia ir à rede")))
    assert D.montar(pastas)["_reaproveitado"] is True


# ------------------------------------------------------------------ servidor
@pytest.fixture
def servidor(pastas):
    srv = S.ThreadingHTTPServer(("127.0.0.1", 0), S.Manipulador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", pastas
    srv.shutdown()


def test_servidor_recusa_chamada_sem_cabecalho_proprio(servidor):
    url, raiz = servidor
    assert requests.get(url + "/api/status", timeout=5).status_code == 403
    assert requests.post(url + f"/api/ia/{raiz}", json={"confirmado": True}, timeout=5).status_code == 403
    assert requests.get(url + "/api/status", headers={"X-Redes": "1"}, timeout=5).json()["servidor"] is True


def test_servidor_devolve_o_gravado_e_exige_confirmacao(servidor):
    url, raiz = servidor
    H = {"X-Redes": "1"}
    r = requests.post(url + f"/api/dossie/{raiz}", json={}, headers=H, timeout=5)
    assert r.status_code == 200 and r.json()["resultado"]["_reaproveitado"]
    assert requests.post(url + f"/api/ia/{raiz}", json={}, headers=H, timeout=5).status_code == 409   # sem análise e sem confirmar
    IA.analisar(raiz, cliente=ClienteFalso())
    r = requests.post(url + f"/api/ia/{raiz}", json={}, headers=H, timeout=5)                         # já existe: devolve, sem confirmar nada
    assert r.status_code == 200 and r.json()["resultado"]["_reaproveitada"]
