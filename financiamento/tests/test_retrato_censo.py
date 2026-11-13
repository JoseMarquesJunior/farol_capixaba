"""Tabela fixa do Censo Escolar (referencia/censo_escolar/): o pipeline lê só ela, sem banco."""

import inspect
import json

import pandas as pd
import pytest

from financiamento.etl import escolas


def _tabelas():
    return {
        "escolas": pd.DataFrame({"co_entidade": [32000001, 32000002], "no_entidade": ["EMEF A", "EEEFM B"],
                                 "co_municipio": [3205002, 3205309], "latitude": [None, -20.3], "longitude": [None, -40.3],
                                 "ultimo_ano": [2025, 2025], "ano_censo": [2025, 2025], "tp_dependencia": [3, 2],
                                 "tp_situacao_funcionamento": [1, 1], "qt_mat_bas": [300, 800], "qt_doc_bas": [20, 50],
                                 "in_internet": [1, 1], "in_biblioteca": [0, 1], "in_laboratorio_informatica": [0, 1],
                                 "in_quadra_esportes": [1, 1], "in_agua_potavel": [1, 1], "in_esgoto_rede_publica": [1, 0],
                                 "in_acessibilidade_rampas": [0, 1]}),
        "ideb": pd.DataFrame({"co_entidade": [32000001], "etapa": ["anos_iniciais"], "ano": [2023], "ideb_observado": [5.9]}),
        "paebes": pd.DataFrame({"co_entidade": [32000001], "ano": [2025], "etapa": ["5º ano"], "disciplina": ["Língua Portuguesa"],
                                "proficiencia_media": [210.5]}),
        "matriculas_etapa": pd.DataFrame({"ano": [2024, 2025], "co_municipio": [3205002, 3205002], "qt_mat_bas": [300, 310],
                                          "qt_mat_fund": [250, 260], "qt_mat_med": [0, 0]}),
    }


def test_le_o_retrato_gravado_sem_tocar_em_banco(tmp_path):
    meta = escolas.gravar_retrato(_tabelas(), tmp_path, gerado_em="2026-10-13T16:52:56+00:00")
    assert meta["ano_censo"] == 2025 and meta["linhas"]["escolas"] == 2
    tabelas, consulta, aviso = escolas.extrair_censo(pasta=tmp_path)
    assert aviso is None
    for k, df in _tabelas().items():
        pd.testing.assert_frame_equal(tabelas[k], df)
    assert consulta.fonte == "Censo" and consulta.obtido_em == "2026-10-13T16:52:56+00:00"
    assert consulta.url == escolas.URL_MICRODADOS and "até 2025" in consulta.descricao
    assert consulta.sha256 == escolas._sha256(tmp_path / "retrato.json")


def test_pipeline_nao_abre_o_banco():
    """Só o gerador anual conhece o banco do NEDUC; a leitura do pipeline, não."""
    assert "get_connection" not in inspect.getsource(escolas.extrair_censo)
    assert "get_connection" in inspect.getsource(escolas.gerar_retrato)


def test_csv_alterado_fora_do_gerador_e_recusado(tmp_path):
    escolas.gravar_retrato(_tabelas(), tmp_path)
    arq = tmp_path / "escolas.csv"
    arq.write_text(arq.read_text(encoding="utf-8").replace("EMEF A", "EMEF Z"), encoding="utf-8")
    tabelas, consulta, aviso = escolas.extrair_censo(pasta=tmp_path)
    assert consulta is None and all(t.empty for t in tabelas.values())
    assert "escolas.csv difere" in aviso


def test_retrato_ausente_vira_aviso_e_tabelas_vazias(tmp_path):
    tabelas, consulta, aviso = escolas.extrair_censo(pasta=tmp_path / "nao_existe")
    assert consulta is None and "ausente" in aviso
    assert all(t.empty for t in tabelas.values())


def test_tabela_vazia_nao_e_gravada(tmp_path):
    t = {**_tabelas(), "ideb": pd.DataFrame()}
    with pytest.raises(ValueError, match="ideb"):
        escolas.gravar_retrato(t, tmp_path)
    assert not (tmp_path / "retrato.json").exists()


def test_o_retrato_versionado_esta_integro():
    """O que viaja com o código para o servidor: completo, conferido e do Espírito Santo."""
    pasta = escolas.PASTA_RETRATO
    meta = json.loads((pasta / "retrato.json").read_text(encoding="utf-8"))
    assert meta["consultas"] == {k: " ".join(q.split()) for k, q in escolas.SQL.items()}, "SQL mudou: regere o retrato"
    tabelas, consulta, aviso = escolas.extrair_censo()
    assert aviso is None, aviso
    assert {k: len(v) for k, v in tabelas.items()} == meta["linhas"]
    assert tabelas["escolas"]["co_municipio"].astype(str).str.startswith("32").all()
    assert meta["ano_censo"] >= 2025
    assert (pasta / ".gitattributes").read_text(encoding="utf-8").strip().endswith("* -text")
