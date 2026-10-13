"""Montagem do dashboard.html: dado embutido de forma segura e template íntegro."""

import base64
import hashlib
import json
import re

import pytest

from financiamento import build_dashboard

from .conftest import FIXTURES

DATASET_MINIMO = {"meta": {"esquema": 2}, "entes": [], "anual": [], "bimestral": [], "subfuncoes": []}


def _montar(tmp_path, dataset, bruto=None):
    ds = tmp_path / "dataset.json"
    ds.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
    saida = tmp_path / "out.html"
    build_dashboard.montar(dataset=ds, saida=saida, bruto=bruto or (tmp_path / "vazio"))
    return saida.read_text(encoding="utf-8")


def test_dataset_embutido_e_recuperavel(tmp_path):
    html = _montar(tmp_path, {**DATASET_MINIMO, "entes": [{"nome": "Vitória"}]})
    bloco = re.search(r'<script id="dataset" type="application/json">(.*?)</script>', html, re.S).group(1)
    assert json.loads(bloco)["entes"] == [{"nome": "Vitória"}]


def test_nenhum_marcador_fica_sem_resolver(tmp_path):
    html = _montar(tmp_path, DATASET_MINIMO)
    assert "__DATASET_JSON__" not in html and "__CHARTJS" not in html


def test_dado_com_fecha_script_nao_quebra_a_pagina(tmp_path):
    """Um nome com '</script>' encerraria o bloco e abriria brecha de injeção."""
    html = _montar(tmp_path, {**DATASET_MINIMO, "entes": [{"nome": "</script><b>x</b> <!-- y"}]})
    bloco = re.search(r'<script id="dataset" type="application/json">(.*?)</script>', html, re.S).group(1)
    assert "</" not in bloco and "<!--" not in bloco
    assert json.loads(bloco)["entes"][0]["nome"] == "</script><b>x</b> <!-- y"  # o JSON continua idêntico


def test_chartjs_fixado_com_integridade(tmp_path):
    html = _montar(tmp_path, DATASET_MINIMO)
    assert f"chart.js@{build_dashboard.CHARTJS_VERSION}" in html
    assert f'integrity="{build_dashboard.CHARTJS_SRI}"' in html


def test_esquema_incompativel_e_recusado(tmp_path):
    with pytest.raises(SystemExit, match="esquema"):
        _montar(tmp_path, {**DATASET_MINIMO, "meta": {"esquema": 99}})


# ------------------------------------------- PDFs do SIOPE embutidos na página

PDF_FIXTURE = "siope_RREO_Municipal_320240_6_2023.pdf"


def _dataset_com_pdf(tmp_path, sha=None):
    """Dataset com uma consulta em FTP, e o cache bruto com o PDF dela."""
    fixture = FIXTURES / PDF_FIXTURE
    bruto = tmp_path / "bruto"
    (bruto / "siope" / "2023").mkdir(parents=True)
    conteudo = fixture.read_bytes()
    (bruto / "siope" / "2023" / "RREO_Municipal_320240_6_2023.pdf").write_bytes(conteudo)
    dados = {**DATASET_MINIMO, "consultas": {
        "colunas": ["id", "fonte", "url_base", "url_resto", "arquivo", "sha256"],
        "dicionario": {"fonte": ["SIOPE"], "url_base": ["ftp://ftp.fnde.gov.br/web/siope/RREO/"]},
        "linhas": [["abc", 0, 0, "RREO_Municipal_320240_6_2023.pdf",
                    "siope/2023/RREO_Municipal_320240_6_2023.pdf",
                    sha if sha is not None else hashlib.sha256(conteudo).hexdigest()]]}}
    return dados, bruto, conteudo


def test_pdf_do_ftp_vai_embutido_e_intacto(tmp_path):
    """A URL ftp:// não abre em navegador nenhum: o PDF tem de estar na página."""
    dados, bruto, conteudo = _dataset_com_pdf(tmp_path)
    html = _montar(tmp_path, dados, bruto)
    pdfs = json.loads(re.search(r'<script id="pdfs" type="application/json">(.*?)</script>', html, re.S).group(1))
    indice = json.loads(re.search(r'<script id="pdfs-indice" type="application/json">(.*?)</script>', html, re.S).group(1))
    arquivo = "siope/2023/RREO_Municipal_320240_6_2023.pdf"
    assert base64.b64decode(pdfs[arquivo]) == conteudo  # byte a byte o que foi coletado
    assert indice[arquivo] == len(conteudo)  # o tamanho que o botão mostra


def test_pdf_com_sha_divergente_fica_de_fora(tmp_path, capsys):
    """Evidência que não bate com a proveniência não entra — e a montagem segue."""
    dados, bruto, _ = _dataset_com_pdf(tmp_path, sha="0" * 64)
    html = _montar(tmp_path, dados, bruto)
    pdfs = json.loads(re.search(r'<script id="pdfs" type="application/json">(.*?)</script>', html, re.S).group(1))
    assert pdfs == {}
    assert "SHA-256" in capsys.readouterr().err


def test_pdf_ausente_no_cache_nao_derruba_a_montagem(tmp_path, capsys):
    dados, bruto, _ = _dataset_com_pdf(tmp_path)
    (bruto / "siope" / "2023" / "RREO_Municipal_320240_6_2023.pdf").unlink()
    html = _montar(tmp_path, dados, bruto)
    assert '<script id="pdfs" type="application/json">{}</script>' in html
    assert "não está no cache" in capsys.readouterr().err


def _fontes_js() -> str:
    """Todo o JavaScript da página: o esqueleto e as partes de `web/`."""
    esqueleto = (build_dashboard.WEB / "index.html").read_text(encoding="utf-8")
    partes = [(build_dashboard.WEB / a).read_text(encoding="utf-8")
              for a in build_dashboard.PARTES.values() if a.endswith(".js")]
    return esqueleto.split('<script id="dataset"')[1] + "\n".join(partes)


def test_pagina_nao_chama_api_nem_usa_innerhtml():
    """O navegador nunca chama a API, e todo texto vindo dos dados entra por textContent."""
    js = _fontes_js()
    assert "apidatalake" not in js  # nenhuma URL de API no código da página
    assert "fetch(" not in js and "XMLHttpRequest" not in js
    assert "innerHTML" not in js.replace("nunca innerHTML", "")


def test_nenhum_nome_global_repetido_entre_as_partes():
    """Os .js dividem o escopo global: uma função com o mesmo nome em dois arquivos
    sobrescreve a outra em silêncio (já aconteceu: `cardOrigem` de Programas apagou
    a de Receita → aplicação)."""
    nomes: dict[str, str] = {}
    repetidos = []
    for arquivo in [a for a in build_dashboard.PARTES.values() if a.endswith(".js")]:
        fonte = (build_dashboard.WEB / arquivo).read_text(encoding="utf-8")
        for nome in re.findall(r"(?m)^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)|^(?:const|let|var)\s+([A-Za-z_$][\w$]*)", fonte):
            nome = nome[0] or nome[1]
            if nome in nomes:
                repetidos.append(f"{nome}: {nomes[nome]} e {arquivo}")
            nomes[nome] = arquivo
    assert not repetidos, repetidos


def test_todas_as_partes_entram_na_pagina(tmp_path):
    """Cada arquivo de `web/` precisa acabar dentro do HTML final."""
    html = _montar(tmp_path, DATASET_MINIMO)
    for arquivo in build_dashboard.PARTES.values():
        fonte = (build_dashboard.WEB / arquivo).read_text(encoding="utf-8")
        marca = next(l for l in fonte.splitlines() if len(l) > 40)  # uma linha distintiva
        assert marca in html, arquivo


def test_parte_que_encerraria_o_bloco_e_recusada(tmp_path, monkeypatch):
    """Um `</script>` dentro de um .js embutido encerraria o bloco na página."""
    ruim = tmp_path / "web"
    ruim.mkdir()
    for arquivo in build_dashboard.PARTES.values():
        (ruim / arquivo).write_text("// ok\n", encoding="utf-8")
    (ruim / "comum.js").write_text('var x = "</script>";\n', encoding="utf-8")
    (ruim / "index.html").write_text((build_dashboard.WEB / "index.html").read_text(encoding="utf-8"), encoding="utf-8")
    ds = tmp_path / "dataset.json"
    ds.write_text(json.dumps(DATASET_MINIMO), encoding="utf-8")
    with pytest.raises(SystemExit, match="encerraria o bloco"):
        build_dashboard.montar(dataset=ds, saida=tmp_path / "out.html", web=ruim)
