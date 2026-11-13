"""Busca dos documentos faltantes (etl/documentos_faltantes.py): rotas, gravação e o que chega à IA."""

import json
import threading
from types import SimpleNamespace

import pytest
import requests

from financiamento import servidor_redes as S
from financiamento.etl import analise_ia as IA
from financiamento.etl import documentos_faltantes as F
from financiamento.etl import dossie as D

RAIZ = "22332830"
CNPJ = RAIZ + "000111"


def contrato(**k):
    base = {"municipio": "Presidente Kennedy", "ug": "Secretaria Municipal de Educação de Presidente Kennedy", "numero": "000240/2024",
            "objeto": "transporte escolar", "assinatura": "2024-12-27", "valor_inicial": 29666994.0, "valor_atual": 60430979.62, "arp": "000009/2024",
            "url_contrato": "https://presidentekennedy-es.portaltp.com.br/consultas/compras/contratos.aspx", "url_publicacao": "https://ioes.dio.es.gov.br/dom",
            "url_edital": "", "chave": "pk-240"}
    return base | k


def test_faltantes_escolhe_os_maiores_sem_link_algum():
    d = {"contratos": {"contratos": [
        contrato(),
        contrato(numero="1/2024", valor_atual=9e9, url_contrato="http://transparencia.serra.es.gov.br/Contrato.Detalhes.aspx?contratoId=33064"),  # tem link
        contrato(numero="2/2024", valor_atual=1.0, chave="b"),
        contrato(numero="3/2024", valor_atual=None, chave="c"),
    ]}}
    assert [c["numero"] for c in F.faltantes(d)] == ["000240/2024", "2/2024", "3/2024"]
    assert [c["numero"] for c in F.faltantes(d, limite=1)] == ["000240/2024"]


PAGINA_CERTA = ("PREFEITURA MUNICIPAL DE PRESIDENTE KENNEDY\nEXTRATO DO CONTRATO Nº 000240/2024\nContratada: DC TRANSPORTES E SERVIÇOS LTDA, "
                "CNPJ: 22.332.830/0001-11\nValor Total: R$ 29.666.994,00")
PAGINA_OUTRO_MUNICIPIO = "PREFEITURA DE CARIACICA\nContrato 000240/2024\nDC TRANSPORTES E SERVIÇOS LTDA 22.332.830/0001-11"
PAGINA_OUTRO_CONTRATO = "PRESIDENTE KENNEDY\nContrato 000193/2024 - 1º aditivo\nDC TRANSPORTES E SERVIÇOS LTDA, CNPJ 22.332.830/0001-11, valor R$ 1.000,00"


@pytest.fixture
def diario(monkeypatch):
    idx = [{"id": 9781, "data": "02/01/2025"}, {"id": 9770, "data": "27/12/2024"}, {"id": 9000, "data": "01/06/2024"}, {"id": 8418, "data": "25/09/2023"}]
    lidas = []
    paginas = {9770: [PAGINA_OUTRO_MUNICIPIO, "nada aqui", PAGINA_CERTA], 9781: [PAGINA_OUTRO_CONTRATO]}
    monkeypatch.setattr(F, "indice_dom", lambda: idx)
    monkeypatch.setattr(F, "paginas_edicao", lambda col, e: lidas.append(e) or paginas[e])
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    return lidas


def test_varredura_do_diario_acha_so_a_pagina_do_municipio_e_do_contrato(diario):
    r = F.rota_dom(None, contrato(), RAIZ, "DC TRANSPORTES E SERVICOS LTDA", CNPJ, lambda t: None)
    assert sorted(diario) == [9770, 9781]                        # só as edições da janela, não as de 2023/junho
    assert r["situacao"] == "encontrado" and [(p["edicao"], p["pagina"]) for p in r["paginas"]] == [(9770, 3)]
    assert r["paginas"][0]["casa_numero"] and "29.666.994,00" in r["paginas"][0]["trecho"]
    assert r["documentos"][0]["url"] == "https://ioes.dio.es.gov.br/apifront/portal/edicoes/pdf_diario/9770/3"
    assert D.especifico(r["documentos"][0]["url"])               # e entra no inventário


def test_trecho_comeca_no_titulo_do_ato_ou_numa_palavra():
    t = "outro ato. Vigência: 90 dias. EXTRATO DO CONTRATO Nº 240/2024 - ADESÃO A ATA"
    assert t[F._inicio_trecho(t, t.index("240/2024")):].startswith("EXTRATO DO CONTRATO")
    t = "x" * 300 + " palavra inteira 240/2024"
    assert t[F._inicio_trecho(t, t.index("240/2024")):].startswith("palavra")


def test_varredura_fora_do_indice_nao_se_aplica(diario):
    assert F.rota_dom(None, contrato(assinatura="2022-08-09"), RAIZ, "DC", CNPJ, lambda t: None)["situacao"] == "nao_aplicavel"
    assert diario == []


def test_pncp_por_orgao_casa_pelo_cnpj_da_empresa(monkeypatch):
    monkeypatch.setattr(F, "cnpj_municipios", lambda: {"presidente kennedy": "27165703000126"})
    pedidos = []

    def get(nome, url, **k):
        pedidos.append(url)
        if "/arquivos" in url:
            return 200, json.dumps([{"tipoDocumentoNome": "Contrato", "url": "https://pncp.gov.br/api/pncp/v1/orgaos/27165703000126/contratos/2024/7/arquivos/1", "titulo": "contrato"}]).encode(), {}
        return 200, json.dumps({"data": [
            {"niFornecedor": "99999999000100", "numeroContratoEmpenho": "240", "anoContrato": 2024, "sequencialContrato": 6},
            {"niFornecedor": CNPJ, "numeroContratoEmpenho": "000240/2024", "anoContrato": 2024, "sequencialContrato": 7, "valorGlobal": 29666994.0},
        ], "totalRegistros": 2, "paginasRestantes": 0}).encode(), {}

    r = F.rota_pncp(SimpleNamespace(get=get), contrato(), RAIZ)
    assert "cnpjOrgao=27165703000126" in pedidos[0] and "dataInicial=20241212" in pedidos[0]
    assert r["situacao"] == "encontrado" and len(r["contratos_pncp"]) == 1 and r["contratos_pncp"][0]["casa_numero"]
    assert r["documentos"][0]["tipo"] == "PNCP: Contrato"


def test_pncp_sem_contrato_da_empresa_explica_o_motivo(monkeypatch):
    monkeypatch.setattr(F, "cnpj_municipios", lambda: {"presidente kennedy": "27165703000126"})
    r = F.rota_pncp(SimpleNamespace(get=lambda *a, **k: (200, b'{"data": [], "totalRegistros": 10, "paginasRestantes": 0}', {})), contrato(), RAIZ)
    assert r["situacao"] == "nao_encontrado" and "10 contrato(s)" in r["detalhe"] and "fundo ou secretaria" in r["detalhe"]


def test_orientacao_manual_e_pedido_pela_lai():
    passos = F.orientacao_manual(contrato(), {}, "DC TRANSPORTES E SERVICOS LTDA", CNPJ)
    portal = passos[0]
    assert portal["url"] == "https://presidentekennedy-es.portaltp.com.br/consultas/compras/contratos.aspx"
    assert "2024" in portal["como"] and "Atas de Adesão" in portal["como"]
    assert any("22.332.830/0001-11" in p["como"] and "27/12/2024" in p["como"] for p in passos)
    t = F.modelo_pedido(contrato(), "DC TRANSPORTES E SERVICOS LTDA", CNPJ)
    assert "000240/2024" in t and "27/12/2024" in t and "12.527/2011" in t and "000009/2024" in t and "aditivos" in t


@pytest.fixture
def dossie(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "PASTA_RESULTADOS", tmp_path / "analises")
    monkeypatch.setattr(D, "PASTA_CRUS", tmp_path / "crus")
    (tmp_path / "analises" / RAIZ).mkdir(parents=True)
    d = {"meta": {"raiz": RAIZ, "nome": "DC TRANSPORTES E SERVICOS LTDA", "gerado_em": "2026-10-27T00:00:00+00:00", "cnpj_consultado": CNPJ},
         "contratos": {"status": "ok", "contratos": [contrato()]}, "documentos": [], "fontes": []}
    D.caminho(RAIZ).write_text(json.dumps(d), encoding="utf-8")
    chamadas = []
    monkeypatch.setattr(F, "rota_pncp", lambda col, c, raiz: chamadas.append("pncp") or {"rota": "PNCP por órgão", "situacao": "nao_encontrado", "detalhe": "nada"})
    monkeypatch.setattr(F, "rota_dom", lambda col, c, raiz, nome, cnpj, p: chamadas.append("dom") or {
        "rota": "DOM-ES (varredura)", "situacao": "encontrado", "detalhe": "1 página",
        "paginas": [{"edicao": 9770, "data": "27/12/2024", "pagina": 524, "casa_numero": True, "trecho": "Valor Total: R$ 29.666.994,00", "url": "u", "visualizar": "v"}],
        "documentos": [{"tipo": "extrato no DOM-ES", "url": "https://ioes.dio.es.gov.br/apifront/portal/edicoes/pdf_diario/9770/524", "titulo": "DOM-ES 27/12/2024, p. 524"}]})
    return chamadas


def test_busca_grava_no_dossie_e_nao_refaz(dossie):
    d = F.buscar(RAIZ)
    f = d["faltantes"]
    assert f["procurados"] == f["encontrados"] == f["contratos_sem_documento"] == 1 and dossie == ["pncp", "dom"]
    doc = d["documentos"][0]
    assert doc["origem"] == "DOM-ES (varredura)" and doc["tipo"] == "extrato no DOM-ES" and "000240/2024" in doc["referencia"]
    assert D.ler(RAIZ)["faltantes"]["encontrados"] == 1           # gravado em disco
    F.buscar(RAIZ)
    assert dossie == ["pncp", "dom"]                                # pedir de novo não vai às fontes
    F.buscar(RAIZ, refazer=True)
    assert dossie == ["pncp", "dom"] * 2


def test_inventario_refeito_mantem_os_achados(dossie):
    d = F.buscar(RAIZ)
    assert any(x["origem"] == "DOM-ES (varredura)" for x in D.inventario(d))


def test_ia_recebe_o_que_falta_e_o_que_a_busca_achou(dossie):
    antes = IA.documentos_faltantes(D.ler(RAIZ))
    assert not antes["busca_feita"] and antes["contratos_sem_documento_no_tcees"][0]["numero"] == "000240/2024"
    depois = IA.documentos_faltantes(F.buscar(RAIZ))
    assert depois["busca_feita"] and depois["busca"][0]["situacao"] == "encontrado"
    assert [r["rota"] for r in depois["busca"][0]["rotas"]] == ["PNCP por órgão", "DOM-ES (varredura)"]
    assert "documentos_faltantes" in IA.SISTEMA


def test_servidor_devolve_a_busca_gravada(dossie):
    F.buscar(RAIZ)
    srv = S.ThreadingHTTPServer(("127.0.0.1", 0), S.Manipulador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        assert requests.post(url + f"/api/faltantes/{RAIZ}", json={}, timeout=5).status_code == 403
        r = requests.post(url + f"/api/faltantes/{RAIZ}", json={}, headers={"X-Redes": "1"}, timeout=5)
        assert r.status_code == 200 and r.json()["resultado"]["faltantes"]["encontrados"] == 1 and dossie == ["pncp", "dom"]
    finally:
        srv.shutdown()
