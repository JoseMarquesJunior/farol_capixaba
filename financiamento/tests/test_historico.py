"""Versões da extração: gravar e comparar duas execuções. Sem rede."""

import pandas as pd

from financiamento.etl import historico


def _df(linhas):
    base = {"periodo": None, "detalhe": None, "rotulo": "r", "ente": "X"}
    return pd.DataFrame([{**base, **l} for l in linhas])


def test_comparacao_classifica_cada_registro():
    antes = _df([
        {"cod_ibge": 1, "ano": 2024, "indicador": "a", "valor": 10.0, "obtido_em": "t1"},
        {"cod_ibge": 1, "ano": 2024, "indicador": "b", "valor": 5.0, "obtido_em": "t1"},
        {"cod_ibge": 1, "ano": 2024, "indicador": "c", "valor": 7.0, "obtido_em": "t1"},
        {"cod_ibge": 1, "ano": 2024, "indicador": "d", "valor": 1.0, "obtido_em": "t1"},
    ])
    depois = _df([
        {"cod_ibge": 1, "ano": 2024, "indicador": "a", "valor": 10.001, "obtido_em": "t1"},  # arredondamento
        {"cod_ibge": 1, "ano": 2024, "indicador": "b", "valor": 6.0, "obtido_em": "t2"},     # alterado
        {"cod_ibge": 1, "ano": 2024, "indicador": "c", "valor": 7.0, "obtido_em": "t2"},     # reextraído
        {"cod_ibge": 1, "ano": 2024, "indicador": "e", "valor": 3.0, "obtido_em": "t2"},     # novo
    ])
    r = historico.comparar(antes, depois).set_index("indicador")["situacao"].to_dict()
    assert r == {"a": "igual", "b": "alterado", "c": "reextraido", "d": "removido", "e": "novo"}


def test_grava_e_lista_versoes(tmp_path):
    df = _df([{"cod_ibge": 1, "ano": 2024, "indicador": "a", "valor": 1.0, "obtido_em": "t"}])
    v = historico.gravar_versao(df, {"anos": [2024]}, pasta=tmp_path)
    assert historico.versoes(tmp_path) == [v]
    assert (tmp_path / v / "manifesto.json").read_text(encoding="utf-8").count("sha256_consolidado") == 1
    assert historico.ler(v, tmp_path)["valor"].tolist() == [1.0]
