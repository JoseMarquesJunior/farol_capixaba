"""Base normativa da Análise com IA (etl/normas.py): leitura das fontes, versão na data, conferência, complemento."""

import json
import threading
from types import SimpleNamespace

import pytest
import requests

from financiamento import servidor_redes as S
from financiamento.etl import analise_ia as IA
from financiamento.etl import dossie as D
from financiamento.etl import normas as N


# ------------------------------------------------------------------ leitura das fontes
def test_json_ld_do_normas_leg_br_vira_arvore_com_versoes():
    dados = {"hasPart": {"legislationIdentifier": "urn:lex:br:federal:lei:2021-04-01;14133!", "hasPart": [
        {"legislationIdentifier": "urn:x!art86", "workExample": {"legislationDate": "2021-04-01", "legislationType": "Original_Version", "text": ""}, "hasPart": [
            {"legislationIdentifier": "urn:x!art86_par3", "workExample": [
                {"legislationDate": "2021-04-01", "legislationType": "Original_Version", "text": "limitada a ata <span xlink:href=\"urn:y\">federal</span> , estadual."},
                {"legislationDate": "2023-12-22", "legislationType": "Text_Change_Version", "text": "poderá ser exercida:"}]},
            {"legislationIdentifier": "urn:x!art86_par3_inc2,lei-14770-2023-12-22",
             "workExample": {"legislationDate": "2023-12-22", "legislationType": "Insertion_Version", "text": "por municípios;"}},
        ]}]}}
    nos = N._arvore_normas(dados)
    assert list(nos) == ["art86", "art86_par3", "art86_par3_inc2"]                 # o sufixo da lei que inseriu sai do caminho
    assert nos["art86_par3"]["versoes"][0][2] == "limitada a ata federal, estadual."    # sem marcação e sem espaço antes da vírgula
    assert N.montar_texto(nos, ["art86_par3"], "2023-06-01")["texto"] == "§ 3º limitada a ata federal, estadual."
    t = N.montar_texto(nos, ["art86_par3"], "2024-12-27")
    assert t["texto"] == "§ 3º poderá ser exercida:\n  II – por municípios;" and t["desde"] == "2023-12-22" and t["versoes"] == ["2021-04-01", "2023-12-22"]


def test_texto_atualizado_da_camara_vira_a_mesma_arvore():
    html = ("<p>Art. 65. Os contratos poderão ser alterados nos seguintes casos:</p><p>I - unilateralmente:</p><p>a) quando houver modificação do projeto;</p>"
            "<p><strike>§ 1º redação antiga riscada</strike></p><p>§ 1º O contratado fica obrigado a aceitar acréscimos até 25%.</p>"
            "<p>§ 8º A variação para reajuste pode ser registrada por apostila.</p><p>Art. 66. Outro artigo.</p><p>Parágrafo único. Prazo de cinco dias.</p>")
    nos = N._arvore_legin(html.encode("utf-8"))
    assert {"art65_cpt", "art65_cpt_inc1", "art65_cpt_inc1_ali1", "art65_par1", "art65_par8", "art66_par1u"} <= set(nos)
    assert nos["art65_par1"]["versoes"][0][2] == "O contratado fica obrigado a aceitar acréscimos até 25%."     # a redação riscada não entra
    assert N.montar_texto(nos, ["art65_cpt"], None)["texto"].splitlines() == [
        "Art. 65. Os contratos poderão ser alterados nos seguintes casos:", "  I – unilateralmente:", "    a) quando houver modificação do projeto;"]
    assert N.montar_texto(nos, ["art66_par1u"], None)["texto"] == "Parágrafo único. Prazo de cinco dias."


@pytest.mark.parametrize("lei, partes, esperado", [
    ("14133", ["art86_par3"], "Lei nº 14.133/2021, art. 86, § 3º"),
    ("14133", ["art75_cpt!", "art75_cpt_inc8"], "Lei nº 14.133/2021, art. 75, inciso VIII"),
    ("8666", ["art61_par1u"], "Lei nº 8.666/1993, art. 61, parágrafo único"),
    ("14133", ["art9_cpt!", "art9_cpt_inc1"], "Lei nº 14.133/2021, art. 9º, inciso I"),
])
def test_rotulo_da_citacao(lei, partes, esperado):
    assert N.rotulo_citacao(lei, partes) == esperado


def test_supressao_de_aplicabilidade_e_revogacao():
    v = [("2021-04-01", "Original_Version", "limite de 25%"), ("2024-05-17", "Applicability_Suppression_Version", "limite de 25%")]
    assert N._texto_na_data(v, "2025-01-01") == ("limite de 25%", "2021-04-01")        # MP 1.221 (calamidade): não muda o texto
    assert N._texto_na_data([("2021-04-01", "Original_Version", "x"), ("2023-08-03", "Suppression_Version", "(Suprimido)")], "2024-01-01")[0] is None
    assert N._texto_na_data([("2023-12-22", "Insertion_Version", "novo")], "2023-06-01") == (None, None)   # ainda não existia


def test_catalogo_sem_ids_repetidos_e_esquema_so_aceita_o_catalogo():
    assert len(N.IDS) == len(set(N.IDS))
    item = IA.ESQUEMA_SAIDA["properties"]["constatacoes"]["items"]
    assert "normas" in item["required"] and item["properties"]["normas"]["items"]["properties"]["dispositivo"]["enum"] == N.IDS
    assert IA.REGRAS_NORMAS in IA.SISTEMA and IA.REGRAS_NORMAS in IA.SISTEMA_NORMAS


# ------------------------------------------------------------------ versão na data e conferência
def test_redacao_em_vigor_na_data_do_contrato():
    antes, depois = N.resolver("14133.art86.§3", "2023-06-01"), N.resolver("14133.art86.§3", "27/12/2024")
    assert "estadual ou distrital." in antes["texto"] and "municipal" not in antes["texto"]
    assert "II – por municípios" in depois["texto"] and depois["redacao_desde"] == "2023-12-22" and depois["data_referencia"] == "2024-12-27"
    assert depois["url"] == "https://normas.leg.br/?urn=urn:lex:br:federal:lei:2021-04-01;14133!art86_par3"
    assert N.resolver("8666.art65.§1", "2024-12-27")["versionado"] is False                 # a Câmara só dá a redação atual


def test_conferencia_das_normas():
    textos = ["contrato assinado em 2024-12-27"]
    ok, p = IA.conferir_normas([{"dispositivo": "14133.art125", "data_referencia": "2024-12-27", "aplicacao": "Verificar aditivos."}], "sinal", textos)
    assert p == [] and ok[0]["avisos"] == [] and ok[0]["aplicacao"] == "Verificar aditivos."
    _, p = IA.conferir_normas([{"dispositivo": "14133.art125", "data_referencia": "2019-01-01", "aplicacao": ""}], "sinal", textos)
    assert any("2019-01-01 não aparece" in x for x in p) and any("não estava em vigor em 01/01/2019" in x for x in p)
    _, p = IA.conferir_normas([{"dispositivo": "14133.art125", "data_referencia": "ontem", "aplicacao": ""}], "padrao", textos)
    assert any("data de referência inválida" in x for x in p)
    vazio, p = IA.conferir_normas([{"dispositivo": "lei.inventada", "data_referencia": "2024-12-27", "aplicacao": ""}], "sinal", textos)
    assert vazio == [] and "dispositivo fora do catálogo: lei.inventada" in p and "sinal sem base normativa indicada" in p
    assert IA.conferir_normas([], "contexto", textos) == ([], [])                            # contexto não exige norma


# ------------------------------------------------------------------ complemento de uma análise antiga
class ClienteNormas:
    def __init__(self, itens):
        self.chamadas, self.itens = 0, itens
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream, count_tokens=lambda **kw: SimpleNamespace(input_tokens=9000)))

    def _stream(self, **kw):
        self.chamadas += 1
        assert kw["system"] == IA.SISTEMA_NORMAS and kw["output_config"]["format"]["schema"] == IA.ESQUEMA_NORMAS
        msg = SimpleNamespace(stop_reason="end_turn", model="claude-opus-5-5", _request_id="req_n", usage=SimpleNamespace(input_tokens=9000, output_tokens=1500),
                              content=[SimpleNamespace(type="text", text=json.dumps({"itens": self.itens}))])
        return type("CM", (), {"__enter__": lambda self: SimpleNamespace(get_final_message=lambda: msg), "__exit__": lambda self, *a: False})()


@pytest.fixture
def analise_antiga(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "PASTA_RESULTADOS", tmp_path / "analises")
    monkeypatch.setattr(D, "PASTA_CRUS", tmp_path / "crus")
    raiz = "22332830"
    (tmp_path / "analises" / raiz / "ia").mkdir(parents=True)
    d = {"meta": {"raiz": raiz, "nome": "DC", "gerado_em": "2026-10-27T00:00:00+00:00", "cnpj_consultado": raiz + "000111"},
         "contratos": {"status": "ok", "contratos": [{"municipio": "Presidente Kennedy", "numero": "000240/2024", "assinatura": "2024-12-27", "arp": "000009/2024",
                                                       "valor_inicial": 29666994.0, "valor_atual": 60430979.62, "url_contrato": "", "url_publicacao": ""}]}, "documentos": []}
    D.caminho(raiz).write_text(json.dumps(d), encoding="utf-8")
    a = {"meta": {"gerado_em": "2026-10-27T17:19:36+00:00", "modelo": "claude-opus-5-5", "hash_pedido": "abc", "custo_usd": 0.5},
         "constatacoes": [{"titulo": "Carona", "texto": "Adesão à ata 9/2024.", "tipo": "sinal", "evidencias": [], "proxima_verificacao": "-"},
                          {"titulo": "Contexto", "texto": "Empresa de 2015.", "tipo": "contexto", "evidencias": [], "proxima_verificacao": "-"}],
         "limites": [], "documentos_usados": []}
    arq = IA.pasta_ia(raiz) / "20261027-141936-128237_abc.json"
    arq.write_text(json.dumps(a), encoding="utf-8")
    return raiz, arq


def test_complemento_grava_a_parte_e_nao_refaz(analise_antiga):
    raiz, arq = analise_antiga
    original = arq.read_bytes()
    assert IA.com_normas(raiz, IA.ultima(raiz))["_sem_normas"] == 2
    cli = ClienteNormas([{"indice": 0, "normas": [{"dispositivo": "14133.art86.§3", "data_referencia": "2024-12-27",
                                                    "aplicacao": "Município aderiu à ata de outro município: verificar se a ata veio de licitação."}]},
                         {"indice": 7, "normas": []}])                                          # índice inexistente: ignorado
    r = IA.complementar_normas(raiz, cliente=cli)
    c0, c1 = r["constatacoes"]
    assert cli.chamadas == 1 and r["_sem_normas"] == 0 and r["_complemento_normas"]["custo_usd"] == pytest.approx(9000 * 4 / 1e6 + 1500 * 20 / 1e6)
    assert c0["normas"][0]["rotulo"] == "Lei nº 14.133/2021, art. 86, § 3º" and "por municípios" in c0["normas"][0]["texto"] and c0["normas_complemento"]
    assert c1["normas"] == [] and c1["normas_complemento"]                                     # contexto sem norma: sem aviso
    assert arq.read_bytes() == original and len(IA.historico(raiz)) == 1                          # a análise paga não muda; o complemento não é análise
    again = IA.complementar_normas(raiz, cliente=cli)
    assert cli.chamadas == 1 and again["_reaproveitado"]                                          # pedir de novo não chama a API


def test_complemento_recusa_aplicacao_que_afirma_irregularidade(analise_antiga):
    raiz, _ = analise_antiga
    cli = ClienteNormas([{"indice": 0, "normas": [{"dispositivo": "14133.art125", "data_referencia": "2024-12-27", "aplicacao": "Houve superfaturamento."}]}])
    r = IA.complementar_normas(raiz, cliente=cli)
    assert r["constatacoes"][0]["normas"][0]["aplicacao"] == "" and any("recusada" in x for x in r["constatacoes"][0]["normas_avisos"])


def test_servidor_estima_exige_confirmacao_e_devolve_o_complemento(analise_antiga):
    raiz, _ = analise_antiga
    srv = S.ThreadingHTTPServer(("127.0.0.1", 0), S.Manipulador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    H = {"X-Redes": "1"}
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/api/ia/{raiz}"
        e = requests.post(url + "/normas/estimar", json={}, headers=H, timeout=5).json()
        assert e["estimativa"]["constatacoes"] == 2 and e["estimativa"]["custo_usd"] > 0
        assert requests.post(url + "/normas", json={}, headers=H, timeout=5).status_code == 409
        assert requests.get(url, headers=H, timeout=5).json()["ultima"]["_sem_normas"] == 2
        IA.complementar_normas(raiz, cliente=ClienteNormas([{"indice": 0, "normas": [{"dispositivo": "14133.art125", "data_referencia": "2024-12-27", "aplicacao": "x"}]}]))
        r = requests.post(url + "/normas", json={}, headers=H, timeout=5)
        assert r.status_code == 200 and r.json()["resultado"]["_reaproveitada"]
        assert requests.get(url, headers=H, timeout=5).json()["ultima"]["constatacoes"][0]["normas"][0]["rotulo"] == "Lei nº 14.133/2021, art. 125"
    finally:
        srv.shutdown()
