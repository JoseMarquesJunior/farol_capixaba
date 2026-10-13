"""Cliente do SICONFI: paginação, cache bruto e distinção entre 'vazio' e 'falhou'. Sem rede."""

import gzip
import json

import pytest

from financiamento.etl.cliente import ClienteSiconfi, ErroSiconfi


class ClienteFalso(ClienteSiconfi):
    """Troca a rede por páginas pré-fabricadas e conta as chamadas."""

    def __init__(self, paginas, *args, **kw):
        super().__init__(*args, **kw)
        self.paginas = list(paginas)
        self.chamadas: list[dict] = []

    def _pagina(self, endpoint, params):
        self.chamadas.append(dict(params))
        return self.paginas.pop(0)


def _pagina(itens, mais=False, limit=2):
    return {"items": itens, "hasMore": mais, "limit": limit}


def test_junta_as_paginas_e_avanca_o_offset(tmp_path):
    c = ClienteFalso([_pagina([{"a": 1}, {"a": 2}], mais=True), _pagina([{"a": 3}])], tmp_path)
    r = c.consultar("dca", an_exercicio=2024, id_ente=1)
    assert [i["a"] for i in r.itens] == [1, 2, 3]
    assert [ch["offset"] for ch in c.chamadas] == [0, 2]
    assert not r.do_cache


def test_segunda_consulta_sai_do_cache_sem_rede(tmp_path):
    c = ClienteFalso([_pagina([{"a": 1}])], tmp_path)
    primeira = c.consultar("dca", an_exercicio=2024, id_ente=1)
    segunda = c.consultar("dca", an_exercicio=2024, id_ente=1)
    assert len(c.chamadas) == 1
    assert segunda.do_cache and segunda.itens == primeira.itens
    assert segunda.obtido_em == primeira.obtido_em  # a trilha de auditoria preserva o instante original


def test_cache_guarda_a_requisicao_e_o_instante(tmp_path):
    c = ClienteFalso([_pagina([{"a": 1}])], tmp_path)
    r = c.consultar("rreo", an_exercicio=2023, nr_periodo=6, id_ente=7)
    with gzip.open(r.arquivo, "rt", encoding="utf-8") as f:
        corpo = json.load(f)
    assert corpo["params"] == {"an_exercicio": 2023, "nr_periodo": 6, "id_ente": 7}
    assert corpo["total_itens"] == 1 and corpo["obtido_em"]
    assert r.arquivo.parent.parts[-2:] == ("2023", "rreo")  # separado por exercício


def test_resposta_vazia_tambem_e_cacheada(tmp_path):
    c = ClienteFalso([_pagina([])], tmp_path)
    assert c.consultar("dca", an_exercicio=2025, id_ente=1).itens == []
    assert c.consultar("dca", an_exercicio=2025, id_ente=1).do_cache
    assert len(c.chamadas) == 1


def test_atualizar_vazios_refaz_so_o_que_veio_vazio(tmp_path):
    vazio = ClienteFalso([_pagina([])], tmp_path)
    vazio.consultar("dca", an_exercicio=2025, id_ente=1)
    cheio = ClienteFalso([_pagina([{"a": 1}])], tmp_path)
    cheio.consultar("dca", an_exercicio=2024, id_ente=1)

    refaz = ClienteFalso([_pagina([{"a": 9}])], tmp_path, atualizar="vazios")
    assert refaz.consultar("dca", an_exercicio=2025, id_ente=1).itens == [{"a": 9}]
    assert refaz.consultar("dca", an_exercicio=2024, id_ente=1).do_cache  # o cheio não foi refeito
    assert len(refaz.chamadas) == 1


def test_atualizar_tudo_ignora_o_cache(tmp_path):
    ClienteFalso([_pagina([{"a": 1}])], tmp_path).consultar("dca", an_exercicio=2024, id_ente=1)
    novo = ClienteFalso([_pagina([{"a": 2}])], tmp_path, atualizar="tudo")
    assert novo.consultar("dca", an_exercicio=2024, id_ente=1).itens == [{"a": 2}]


def test_cache_corrompido_e_refeito(tmp_path):
    c = ClienteFalso([_pagina([{"a": 1}]), _pagina([{"a": 2}])], tmp_path)
    r = c.consultar("dca", an_exercicio=2024, id_ente=1)
    r.arquivo.write_bytes(b"isto nao e gzip")
    assert c.consultar("dca", an_exercicio=2024, id_ente=1).itens == [{"a": 2}]


def test_paginacao_malformada_nao_gira_para_sempre(tmp_path):
    c = ClienteFalso([{"items": [], "hasMore": True, "limit": 0}], tmp_path)
    with pytest.raises(ErroSiconfi, match="hasMore sem limit"):
        c.consultar("dca", an_exercicio=2024, id_ente=1)


def test_parametros_diferentes_nao_colidem_no_cache(tmp_path):
    c = ClienteFalso([], tmp_path)
    a = c.caminho("rreo", {"an_exercicio": 2024, "nr_periodo": 1, "co_tipo_demonstrativo": "RREO", "no_anexo": "RREO-Anexo 02"})
    b = c.caminho("rreo", {"an_exercicio": 2024, "nr_periodo": 1, "co_tipo_demonstrativo": "RREO Simplificado", "no_anexo": "RREO-Anexo 02"})
    assert a != b
    assert " " not in a.name


def test_falha_de_rede_levanta_e_nao_cacheia(tmp_path, monkeypatch):
    import requests

    class Sessao:
        def get(self, *a, **k):
            raise requests.ConnectionError("sem rede")

    monkeypatch.setattr("financiamento.etl.cliente.time.sleep", lambda s: None)
    c = ClienteSiconfi(tmp_path, tentativas=3)
    monkeypatch.setattr(c, "_sessao", lambda: Sessao())
    with pytest.raises(ErroSiconfi, match="falhou após 3 tentativas"):
        c.consultar("dca", an_exercicio=2024, id_ente=1)
    assert not list(tmp_path.rglob("*.json.gz"))  # 'falhou' NÃO vira 'vazio' no cache


def test_atualizar_invalido_e_rejeitado(tmp_path):
    with pytest.raises(ValueError):
        ClienteSiconfi(tmp_path, atualizar="talvez")
