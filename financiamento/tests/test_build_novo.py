"""Montagem do painel novo (novo_dashboard.html) e do papel de trabalho do CNCA."""

import json
import re

import pytest

from financiamento import build_novo_dashboard as novo

DATASET_MINIMO = {"meta": {"esquema": 2, "anos": [2024, 2025], "gerado_em": "2026-09-23T00:00:00+00:00"},
                  "entes": [{"cod_ibge": 3205002, "nome": "Serra", "esfera": "M"}], "anual": [], "bimestral": [], "subfuncoes": []}
CNCA_MINIMO = {"meta": {"esquema": 1, "anos": [2025]}, "questoes": [], "evidencias": []}


def _montar(tmp_path, dataset=None, cnca=None):
    ds, dc = tmp_path / "dataset.json", tmp_path / "dataset_cnca.json"
    ds.write_text(json.dumps(dataset or DATASET_MINIMO, ensure_ascii=False), encoding="utf-8")
    dc.write_text(json.dumps(cnca or CNCA_MINIMO, ensure_ascii=False), encoding="utf-8")
    painel, cnca_html = novo.montar(dataset=ds, dataset_cnca=dc, saida_painel=tmp_path / "painel.html",
                                    saida_cnca=tmp_path / "cnca.html", bruto=tmp_path / "vazio")
    return painel.read_text(encoding="utf-8"), cnca_html.read_text(encoding="utf-8")


def _bloco(html, id_):
    return json.loads(re.search(rf'<script id="{id_}" type="application/json">(.*?)</script>', html, re.S).group(1))


def test_nenhum_marcador_fica_sem_resolver(tmp_path):
    painel, cnca = _montar(tmp_path)
    for html in (painel, cnca):
        assert not re.search(r"__[A-Z_]+__", html)


def test_painel_embute_o_dataset_inteiro(tmp_path):
    painel, _ = _montar(tmp_path)
    assert _bloco(painel, "dataset")["entes"] == DATASET_MINIMO["entes"]


def test_cnca_vai_para_arquivo_proprio(tmp_path):
    """Decisão D3: o papel de trabalho do CNCA sai do painel. A página dele leva a
    matriz e só o pedaço do dataset geral que usa — não as tabelas de 18 MB."""
    painel, cnca = _montar(tmp_path)
    assert 'id="dataset-cnca"' not in painel
    assert _bloco(cnca, "dataset-cnca")["meta"]["esquema"] == 1
    reduzido = _bloco(cnca, "dataset")
    assert set(reduzido) == {"meta", "entes"}
    assert reduzido["meta"]["indicadores"] == {}


def test_os_dois_arquivos_se_linkam(tmp_path):
    painel, cnca = _montar(tmp_path)
    assert novo.SAIDA_CNCA.name in painel      # ARQUIVO_CNCA em painel.js
    assert "novo_dashboard.html" in cnca       # ARQUIVO_PAINEL em cnca.js


def test_dado_com_fecha_script_nao_quebra_a_pagina(tmp_path):
    dados = {**DATASET_MINIMO, "entes": [{"cod_ibge": 1, "nome": "</script><b>x</b> <!-- y", "esfera": "M"}]}
    painel, cnca = _montar(tmp_path, dados)
    for html in (painel, cnca):
        bruto = re.search(r'<script id="dataset" type="application/json">(.*?)</script>', html, re.S).group(1)
        assert "</" not in bruto and "<!--" not in bruto
        assert json.loads(bruto)["entes"][0]["nome"] == "</script><b>x</b> <!-- y"


def test_chartjs_fixado_com_integridade(tmp_path):
    painel, _ = _montar(tmp_path)
    assert novo.base.CHARTJS_URL in painel and f'integrity="{novo.base.CHARTJS_SRI}"' in painel


def test_esquema_incompativel_e_recusado(tmp_path):
    with pytest.raises(SystemExit, match="esquema"):
        _montar(tmp_path, {**DATASET_MINIMO, "meta": {"esquema": 99}})


@pytest.mark.parametrize("partes", [novo.PARTES_PAINEL, novo.PARTES_CNCA], ids=["painel", "cnca"])
def test_todas_as_partes_entram_na_pagina(tmp_path, partes):
    painel, cnca = _montar(tmp_path)
    html = painel if partes is novo.PARTES_PAINEL else cnca
    for arquivo in partes.values():
        fonte = (novo.WEB_NOVO / arquivo).read_text(encoding="utf-8")
        marca = next(l for l in fonte.splitlines() if len(l) > 40)
        assert marca in html, arquivo


@pytest.mark.parametrize("partes", [novo.PARTES_PAINEL, novo.PARTES_CNCA], ids=["painel", "cnca"])
def test_nenhum_nome_global_repetido_entre_as_partes(partes):
    """Os .js de uma página dividem o escopo global: um nome repetido sobrescreve o outro em silêncio."""
    nomes, repetidos = {}, []
    for arquivo in [a for a in partes.values() if a.endswith(".js")]:
        fonte = (novo.WEB_NOVO / arquivo).read_text(encoding="utf-8")
        for nome in re.findall(r"(?m)^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)|^(?:const|let|var)\s+([A-Za-z_$][\w$]*)", fonte):
            nome = nome[0] or nome[1]
            if nome in nomes:
                repetidos.append(f"{nome}: {nomes[nome]} e {arquivo}")
            nomes[nome] = arquivo
    assert not repetidos, repetidos


def test_pagina_nao_chama_api_nem_usa_innerhtml():
    js = "\n".join(p.read_text(encoding="utf-8") for p in novo.WEB_NOVO.glob("*.js"))
    assert "fetch(" not in js and "XMLHttpRequest" not in js
    assert "innerHTML" not in js.replace("nunca innerHTML", "")


def test_texto_de_desenvolvedor_nao_aparece_na_tela():
    """Auditoria P1-12: comando de terminal e caminho de YAML não são texto de interface."""
    js = "\n".join(p.read_text(encoding="utf-8") for p in novo.WEB_NOVO.glob("*.js"))
    textos = re.findall(r'"([^"\n]*)"', js)  # só literais de texto: comentário de código pode citar o YAML
    assert not [t for t in textos if "python -m" in t or ".yaml" in t or "etl/" in t]


# ------------------------------------------- versão pública (Farol Capixaba)

def _tabela(colunas, linhas, dicionario=None):
    return {"colunas": colunas, "linhas": linhas, **({"dicionario": dicionario} if dicionario else {})}


def test_mascara_cpf_e_telefone_so_nos_campos_de_nome_e_documento():
    dados = {**DATASET_MINIMO,
             "credor_acao": _tabela(["credor", "credor_nome", "q"], [[0, 0, "c36937236276"], [1, 1, "a1"]],
                                    {"credor": ["(pessoa física)", "27165547000101"],
                                     "credor_nome": ["MARIA DA SILVA 08318768752", "LOJA ME (28) 3547-1327"]}),
             "itens": _tabela(["cnpj_contratada", "descricao", "contratada"],
                              [["08123287798", "20172359006 CÓRREGO ZÉ CHICO", "JOÃO 086.196.967-77"],
                               ["27165547000101", "item", "EMPRESA LTDA"]]),
             "consultas": _tabela(["id", "sha256"], [["d48865025235", "1eeeeeb4092176c52640515383b4117170e6b6282ae488aae30d31b119140297"]])}
    conta = novo.mascarar_pessoais(dados)
    nomes = dados["credor_acao"]["dicionario"]["credor_nome"]
    assert nomes == ["MARIA DA SILVA [CPF omitido]", "LOJA ME [telefone omitido]"]
    assert dados["itens"]["linhas"][0] == ["[CPF omitido]", "20172359006 CÓRREGO ZÉ CHICO", "JOÃO [CPF omitido]"]
    assert dados["itens"]["linhas"][1][0] == "27165547000101"          # CNPJ (14 dígitos) fica
    assert dados["credor_acao"]["dicionario"]["credor"][1] == "27165547000101"
    assert dados["credor_acao"]["linhas"][0][2] == "c36937236276"      # id de consulta é proveniência: intocado
    assert dados["consultas"]["linhas"][0] == ["d48865025235", "1eeeeeb4092176c52640515383b4117170e6b6282ae488aae30d31b119140297"]
    assert conta == {"cpf_em_documento": 1, "cpf_em_texto": 2, "telefone": 1}


def test_versao_do_site_sem_cnca_e_com_volta_ao_farol(tmp_path):
    ds = tmp_path / "dataset.json"
    dados = {**DATASET_MINIMO, "credores": _tabela(["credor_nome"], [["ANA 08318768752"]])}
    ds.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    saida, conta = novo.montar_site(dataset=ds, saida=tmp_path / "site.html", bruto=tmp_path / "vazio")
    html = saida.read_text(encoding="utf-8")
    assert _bloco(html, "config") == {"cnca": None, "voltar": {"href": "index.html", "rotulo": "Farol Capixaba da Educação"}}
    assert f'"{novo.SAIDA_CNCA.name}"' not in html                     # nenhum link: só um comentário de CSS cita o nome
    assert "08318768752" not in html and conta["cpf_em_texto"] == 1


def test_versao_local_continua_com_o_cnca(tmp_path):
    painel, _ = _montar(tmp_path)
    assert _bloco(painel, "config")["cnca"] == novo.SAIDA_CNCA.name


def test_site_so_acrescenta_arquivo_em_docs():
    """docs/ é o Farol Capixaba no ar: os três arquivos dele não podem ser sobrescritos."""
    assert novo.SAIDA_SITE.parent.name == "docs"
    assert novo.SAIDA_SITE.name not in {"index.html", "mapa_EM.html", "concorrência_EF_Anos_Iniciais.html"}


def test_painel_antigo_continua_com_os_fontes_dele():
    """O painel novo não reaproveita web/: mudar um não pode mexer no outro."""
    assert novo.WEB_NOVO != novo.base.WEB
    assert set(novo.PARTES_PAINEL.values()).isdisjoint({"visao_conformidade.js", "comum.js"})
