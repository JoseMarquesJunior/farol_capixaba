"""Proveniência: id estável, registro sem repetição, junção de ids. Sem rede."""

import math

from financiamento.etl.proveniencia import Consulta, Registro, caminho_relativo, juntar_ids


def _c(obtido="2026-09-22T10:00:00+00:00", url="https://x/dca?an_exercicio=2024&id_ente=1"):
    return Consulta(fonte="SICONFI", recurso="dca", descricao="d", url=url, obtido_em=obtido, arquivo="2024/dca/a.json.gz")


def test_id_depende_so_da_requisicao():
    assert _c().id == _c(obtido="2030-01-01T00:00:00+00:00").id
    assert _c().id != _c(url="https://x/dca?an_exercicio=2023&id_ente=1").id


def test_fonte_invalida_e_recusada():
    try:
        Consulta(fonte="OUTRA", recurso="x", descricao="d", url="u", obtido_em="t", arquivo="a")
    except ValueError:
        return
    raise AssertionError("fonte inválida deveria levantar ValueError")


def test_registro_guarda_a_coleta_mais_antiga():
    r = Registro()
    r.adicionar(_c(obtido="2026-09-22T12:00:00+00:00"))
    r.adicionar(_c(obtido="2026-09-21T08:00:00+00:00"))
    assert len(r) == 1 and r.todas()[0].obtido_em.startswith("2026-09-21")
    assert r.extraido_em("SICONFI")["consultas"] == 1


def test_juntar_ids_ignora_vazio_e_nan():
    assert juntar_ids("a", None, math.nan, "b;a", ["c", "b"], float("nan")) == "a;b;c"
    assert juntar_ids() == ""


def test_caminho_relativo_usa_barras(tmp_path):
    arq = tmp_path / "2024" / "dca" / "x.json.gz"
    assert caminho_relativo(arq, tmp_path) == "2024/dca/x.json.gz"
