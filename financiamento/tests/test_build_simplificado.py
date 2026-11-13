"""Montagem do painel simplificado (financiamento-simplificado.html)."""

import json
import re

import pytest

from financiamento import build_simplificado as simp

DATASET_MINIMO = {"meta": {"esquema": 2, "anos": [2024, 2025], "gerado_em": "2026-10-28T00:00:00+00:00"},
                  "entes": [{"cod_ibge": 3205002, "nome": "Serra", "esfera": "M"}], "anual": [], "subfuncoes": [],
                  "pcm": {"colunas": ["cod_ibge"], "linhas": [[3205002]]},
                  "siope": {"colunas": ["cod_ibge"], "linhas": [[3205002]]}}


def _montar(tmp_path, dataset=None):
    ds = tmp_path / "dataset.json"
    ds.write_text(json.dumps(dataset or DATASET_MINIMO, ensure_ascii=False), encoding="utf-8")
    saida = simp.montar(dataset=ds, saida=tmp_path / "painel.html")
    return saida.read_text(encoding="utf-8")


def _bloco(html, id_):
    return json.loads(re.search(rf'<script id="{id_}" type="application/json">(.*?)</script>', html, re.S).group(1))


def _fontes_proprias():
    return sorted(simp.WEB_SIMPLIFICADO.glob("*.js"))


def test_nenhum_marcador_fica_sem_resolver(tmp_path):
    assert not re.search(r"__[A-Z_]+__", _montar(tmp_path))


def test_embute_o_dataset_do_simplificado_tal_como_vem(tmp_path):
    """O dataset é o do pipeline do simplificado (só TCE-ES), não o do painel completo."""
    from financiamento.etl import simplificado
    assert simp.DATASET == simplificado.SAIDA and simp.DATASET.name == "dataset_simplificado.json"
    assert _bloco(_montar(tmp_path), "dataset") == DATASET_MINIMO


def test_sem_dataset_o_montador_diz_o_que_rodar(tmp_path):
    with pytest.raises(SystemExit, match="etl.simplificado"):
        simp.montar(dataset=tmp_path / "nao_existe.json", saida=tmp_path / "painel.html")


def test_pagina_nao_le_campos_do_tesouro():
    """Todos os números vêm do TCE-ES: nenhum campo do DCA, da MSC ou do RREO é lido."""
    js = "\n".join(p.read_text(encoding="utf-8") for p in _fontes_proprias())
    proibidos = ["q_dca_ie", "q_msc", "status_dca", "msc_empenhada", "receita_bimestral", "RECEITA_B6", "receita_a01",
                 "fontes_msc", "status_msc", "desp_educacao_per_capita", "populacao"]
    assert not [p for p in proibidos if p in js]


def test_sem_pdfs_embutidos(tmp_path):
    """Nenhum card desta versão cita o Anexo 8 do SIOPE: os PDFs ficam fora."""
    html = _montar(tmp_path)
    assert 'id="pdfs"' not in html and 'id="pdfs-indice"' not in html


def test_chartjs_fixado_com_integridade(tmp_path):
    html = _montar(tmp_path)
    assert simp.base.CHARTJS_URL in html and f'integrity="{simp.base.CHARTJS_SRI}"' in html


def test_dado_com_fecha_script_nao_quebra_a_pagina(tmp_path):
    dados = {**DATASET_MINIMO, "entes": [{"cod_ibge": 1, "nome": "</script><b>x</b> <!-- y", "esfera": "M"}]}
    html = _montar(tmp_path, dados)
    bruto = re.search(r'<script id="dataset" type="application/json">(.*?)</script>', html, re.S).group(1)
    assert "</" not in bruto and "<!--" not in bruto
    assert json.loads(bruto)["entes"][0]["nome"] == "</script><b>x</b> <!-- y"


def test_esquema_incompativel_e_recusado(tmp_path):
    with pytest.raises(SystemExit, match="esquema"):
        _montar(tmp_path, {**DATASET_MINIMO, "meta": {"esquema": 99}})


def test_todas_as_partes_entram_na_pagina(tmp_path):
    html = _montar(tmp_path)
    for pasta, arquivo in simp.PARTES.values():
        fonte = (pasta / arquivo).read_text(encoding="utf-8")
        marca = next(l for l in fonte.splitlines() if len(l) > 40)
        assert marca in html, arquivo


def test_compartilhados_vem_de_web_novo_sem_copia():
    """Os módulos de dados, gráficos e fonte são os do painel novo, lidos de lá:
    não pode haver cópia deles em web_simplificado/ para divergir em silêncio."""
    proprios = {a for p, a in simp.PARTES.values() if p == simp.WEB_SIMPLIFICADO}
    compartilhados = {a for p, a in simp.PARTES.values() if p == simp.WEB_NOVO}
    assert compartilhados, "o painel simplificado deve reutilizar módulos do novo"
    for arquivo in compartilhados:
        assert not (simp.WEB_SIMPLIFICADO / arquivo).exists(), f"cópia indevida: {arquivo}"
    for arquivo in proprios:
        assert (simp.WEB_SIMPLIFICADO / arquivo).exists(), arquivo


def test_nenhum_nome_global_repetido_entre_as_partes():
    """Os .js de uma página dividem o escopo global: um nome repetido sobrescreve o outro em silêncio."""
    nomes, repetidos = {}, []
    for pasta, arquivo in simp.PARTES.values():
        if not arquivo.endswith(".js"):
            continue
        fonte = (pasta / arquivo).read_text(encoding="utf-8")
        for nome in re.findall(r"(?m)^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)|^(?:const|let|var)\s+([A-Za-z_$][\w$]*)", fonte):
            nome = nome[0] or nome[1]
            if nome in nomes:
                repetidos.append(f"{nome}: {nomes[nome]} e {arquivo}")
            nomes[nome] = arquivo
    assert not repetidos, repetidos


def test_pagina_nao_chama_a_internet():
    """A página é autocontida: os dados vêm embutidos, e os Insights por IA (que
    chamavam uma API externa) saíram desta versão."""
    for p in _fontes_proprias():
        js = p.read_text(encoding="utf-8")
        assert "XMLHttpRequest" not in js and "innerHTML" not in js, p.name
        assert "fetch(" not in js and "https://" not in js, p.name
    assert "__INSIGHTS" not in (simp.WEB_SIMPLIFICADO / "painel.html").read_text(encoding="utf-8")
    assert not (simp.WEB_SIMPLIFICADO / "insights-simplificado.js").exists()


def test_carimbo_com_a_data_da_ultima_atualizacao():
    js = (simp.WEB_SIMPLIFICADO / "painel-simplificado.js").read_text(encoding="utf-8")
    assert '"Última atualização dos dados: " + dataBR(META.gerado_em)' in js
    assert 'id="carimbo"' in (simp.WEB_SIMPLIFICADO / "painel.html").read_text(encoding="utf-8")


def test_texto_de_desenvolvedor_nao_aparece_na_tela():
    js = "\n".join(p.read_text(encoding="utf-8") for p in _fontes_proprias())
    textos = re.findall(r'"([^"\n]*)"', js)
    assert not [t for t in textos if "python -m" in t or ".yaml" in t or "etl/" in t]


def test_o_que_o_pedido_excluiu_nao_e_chamado():
    """O pedido do leiaute tirou conformidade (mínimos, entregas, remessas,
    SICONFI × SIOPE), execução bimestral, FUNDEB em três fontes, três olhares do
    FNDE, fonte e detalhamento, obras, escolas e programas federais."""
    js = "\n".join(p.read_text(encoding="utf-8") for p in _fontes_proprias())
    proibidos = ["situacaoMinimos", "cardSituacao", "cardSerieMinimos", "cruzamentoFnde", "cardFundeb",
                 "cardBimestral", "cardNivel3Fontes", "cardNivel3Conselhos", "cardNivel3Obras",
                 "renderSecaoEscolas", "cardProgramasDoMunicipio", "cardsCncaMunicipio",
                 "MIN_MDE", "MIN_70", "mde_aplicado", "tcees_mde", "fundeb70", "divergencia_funcao12",
                 "ENTREGAS", "PCM_LINHAS", "cardNivel3Limites", "cardNivel3Acoes", "ACOES_EA", "DOTACAO_EA"]
    achados = [p for p in proibidos if p in js]
    assert not achados, achados


def test_sem_secao_de_metodologia_e_ressalvas_sem_temas_excluidos():
    """Esta versão não tem a seção "Como ler e metodologia": o metodologia.js do
    painel novo não entra, e as ressalvas que vão dentro dos cards não citam MDE,
    mínimos, remessas nem SIOPE."""
    assert ("web_novo", "metodologia.js") not in {(p.name, a) for p, a in simp.PARTES.values()}
    js = "\n".join(p.read_text(encoding="utf-8") for p in _fontes_proprias())
    assert "renderMetodologia" not in js and "sec-metodologia" not in js
    textos = " ".join(re.findall(r'"([^"\n]*)"', (simp.WEB_SIMPLIFICADO / "glossario-simplificado.js").read_text(encoding="utf-8")))
    for proibido in ["MDE", "SIOPE", "25%", "70%", "remessa", "Remessa", "Tesouro", "CNCA"]:
        assert proibido not in textos, proibido


def test_textos_removidos_a_pedido_nao_voltam():
    js = "\n".join(p.read_text(encoding="utf-8") for p in _fontes_proprias())
    removidos = [
        "O dossiê do município numa página contínua",
        "Uma fonte que pese ao menos 5% da despesa do ano aparece com o próprio nome",
        "Toda a receita do município no ano, dividida em quatro origens",
        "A despesa em Educação dividida por etapa de ensino",
        "O gasto total e o gasto por matrícula, ano a ano",
        "A série completa de cada etapa de ensino",
        "O gasto em Educação pelo tipo de despesa",
        "Nível 3 é o detalhe mais fino do gasto",
        "Como ler e metodologia",
        "Per capita\", nulo(",
        "Educação na despesa do ente",
        "Versão simplificada do painel do financiamento da educação nos municípios",
        "Uma página só: o menu leva a cada parte",
        "Dados coletados até",
        "Abertura pelas categorias do RREO Anexo 01",
        "renderRodape",
        "secaoInsights",
        "Insights (IA)",
    ]
    assert not [t for t in removidos if t in js]
    template = (simp.WEB_SIMPLIFICADO / "painel.html").read_text(encoding="utf-8")
    assert not [i for i in ('id="rodape"', 'id="menu-nota"') if i in template]


def test_nota_de_como_os_itens_entraram_e_retirada_do_card_compartilhado():
    """A nota mora no nivel3.js do painel novo (intocado): sai por pós-processamento."""
    js = (simp.WEB_SIMPLIFICADO / "municipio-simplificado.js").read_text(encoding="utf-8")
    assert 'notas: ["Como estas linhas entraram"]' in js


def test_saida_fica_ao_lado_dos_outros_paineis_nao_em_docs():
    """docs/ é o Farol Capixaba no ar: este montador não escreve lá."""
    assert simp.SAIDA.parent == simp.PASTA
    assert simp.SAIDA.name == "financiamento-simplificado.html"


def test_paineis_existentes_continuam_com_os_fontes_deles():
    """O simplificado lê web_novo/, mas só os montadores antigos escrevem a partir
    dele; nenhum arquivo novo entra em web_novo/ nem em web/."""
    assert simp.WEB_SIMPLIFICADO != simp.WEB_NOVO != simp.base.WEB
    proprios = {a for p, a in simp.PARTES.values() if p == simp.WEB_SIMPLIFICADO}
    assert {"estilo-simplificado.css", "glossario-simplificado.js", "municipio-simplificado.js",
            "painel-simplificado.js"} == proprios
