"""ICA (INEP): leitura da planilha oficial, recorte do ES com "sem dado" explícito, hash e proveniência. Sem rede."""

import json

import pandas as pd
import pytest
from openpyxl import Workbook

from financiamento.etl import cnca, composicao, ica, manuais, programas
from financiamento.etl.manuais import ErroManuais
from financiamento.etl.proveniencia import Registro

COLS = ["ANO", "CO_UF", "SG_UF", "CO_MUNICIPIO", "NO_MUNICIPIO", "NO_TP_REDE",
        "PC_ALUNO_ALFABETIZADO_2023", "PC_ALUNO_ALFABETIZADO_2024", "PC_ALUNO_ALFABETIZADO_2025",
        "META_FINAL_2024", "META_FINAL_2025", "META_FINAL_2026", "META_FINAL_2027", "META_FINAL_2028",
        "META_FINAL_2029", "META_FINAL_2030", "CO_NIVEL_ALFABETIZACAO", "PC_AVALIADOS_LP"]
VITORIA, AFONSO, ALEGRE, FICTICIO, PB = 3205309, 3200102, 3200201, 3299999, 2500106
MUNICIPIOS = {VITORIA, AFONSO, ALEGRE}

LINHAS = [
    # Vitória: série completa (valores reais da edição 2025).
    [2025, 32, "ES", "3205309", "Vitória", "MUNICIPAL", 66, 73, 79, 68, 70, 73, 75, 76, 78, 80, 4, 97],
    # Afonso Cláudio: sem taxa em 2025 — tem de virar "sem dado", nunca 0.
    [2025, 32, "ES", "3200102", "Afonso Cláudio", "MUNICIPAL", 60, 62, None, 62, 64, 66, 68, 70, 72, 80, None, None],
    # UF=ES mas fora da lista de entes: aviso.
    [2025, 32, "ES", "3299999", "Fictício", "MUNICIPAL", 50, 50, 50, 50, 50, 50, 50, 50, 50, 80, 1, 95],
    # Outro estado: ignorado sem aviso.
    [2025, 25, "PB", "2500106", "Alagoa Grande", "MUNICIPAL", 30, 35, 38, 40, 45, 50, 55, 60, 65, 80, 0, 91],
]


def _planilha(tmp_path, linhas=LINHAS, colunas=COLS, nome="ica.xlsx"):
    """Planilha no layout do INEP: 1ª linha rótulo humano, 2ª o código da variável, rodapé sem código."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Divulgação Alfabet Municipio"
    ws.append([c.replace("_", " ").title() for c in colunas])
    ws.append(list(colunas))
    for l in linhas:
        ws.append(l)
    ws.append([None] * len(colunas))
    ws.append(["(1) Percentual de alunos acima de 743 pontos na escala Saeb"] + [None] * (len(colunas) - 1))
    p = tmp_path / nome
    wb.save(p)
    return p


def test_carregar_descarta_rodape_e_le_numeros(tmp_path):
    df = ica.carregar(_planilha(tmp_path))
    assert len(df) == 4 and df["CO_MUNICIPIO"].tolist()[0] == "3205309"
    assert df.loc[0, "PC_ALUNO_ALFABETIZADO_2025"] == 79 and pd.isna(df.loc[1, "PC_ALUNO_ALFABETIZADO_2025"])


def test_planilha_sem_coluna_esperada_e_recusada(tmp_path):
    cols = [c for c in COLS if c != "META_FINAL_2025"]
    linhas = [[v for c, v in zip(COLS, l) if c != "META_FINAL_2025"] for l in LINHAS]
    with pytest.raises(ica.ErroIca, match="META_FINAL_2025"):
        ica.carregar(_planilha(tmp_path, linhas, cols))


def test_codigo_duplicado_e_recusado(tmp_path):
    with pytest.raises(ica.ErroIca, match="duplicado"):
        ica.carregar(_planilha(tmp_path, LINHAS + [LINHAS[0]]))


def test_recorte_es_em_formato_longo_com_sem_dado_explicito(tmp_path):
    tabela, metas, avisos = ica.recortar_es(ica.carregar(_planilha(tmp_path)), MUNICIPIOS, q="abc")
    assert len(tabela) == 3 * 3 and set(tabela["cod_ibge"]) == MUNICIPIOS      # 3 municípios × 2023–2025
    vit = tabela[(tabela["cod_ibge"] == VITORIA) & (tabela["ano"] == 2025)].iloc[0]
    assert (vit["taxa"], vit["meta"], vit["nivel"], vit["participacao"], vit["situacao"]) == (79.0, 70.0, 4, 97.0, "informado")
    assert pd.isna(tabela[(tabela["cod_ibge"] == VITORIA) & (tabela["ano"] == 2023)].iloc[0]["meta"])  # não há meta 2023
    afonso25 = tabela[(tabela["cod_ibge"] == AFONSO) & (tabela["ano"] == 2025)].iloc[0]
    assert pd.isna(afonso25["taxa"]) and afonso25["situacao"] == "sem_dado"    # nunca 0
    alegre = tabela[tabela["cod_ibge"] == ALEGRE]
    assert (alegre["situacao"] == "sem_dado").all() and alegre["taxa"].isna().all()
    assert (tabela["q"] == "abc").all()
    # Metas: 7 anos para cada município presente; nenhuma para o ausente nem para a PB.
    assert len(metas[metas["cod_ibge"] == VITORIA]) == 7 and ALEGRE not in set(metas["cod_ibge"]) and PB not in set(metas["cod_ibge"])
    textos = " ".join(a["aviso"] for a in avisos)
    assert "ausente" in textos and str(ALEGRE) in textos and "fora da lista" in textos and str(FICTICIO) in textos
    assert str(PB) not in textos


def test_hash_divergente_para_alto_e_nao_segue(tmp_path):
    p = _planilha(tmp_path)
    with pytest.raises(ica.ErroIca, match="SHA-256"):
        ica.garantir_fonte(p, url="https://exemplo/ica.xlsx", sha_esperado="0" * 64, atualizar="nao")


def test_arquivo_ja_presente_ganha_metadados_sem_baixar(tmp_path):
    """Planilha colocada à mão (ou já em cache) não dispara download; o .json registra a leitura."""
    p = _planilha(tmp_path)
    sha = ica.sha256_de(p)
    caminho, meta = ica.garantir_fonte(p, url="https://exemplo/ica.xlsx", sha_esperado=sha, atualizar="nao")
    assert caminho == p and meta["sha256"] == sha and meta["obtido_em"]
    lado = json.loads(p.with_suffix(".xlsx.json").read_text(encoding="utf-8"))
    assert lado["sha256"] == sha and lado["url"] == "https://exemplo/ica.xlsx"


def test_offline_sem_cache_e_nao_coletado(tmp_path):
    r = ica.executar(MUNICIPIOS, atualizar="offline", caminho=tmp_path / "nao_existe.xlsx")
    assert r.tabela.empty and r.status["coletado"] is False and r.status["ok"] is True
    assert "não coletado" in r.avisos[0]["aviso"]


def test_executar_registra_consulta_com_hash_e_alimenta_programas_api(tmp_path):
    p = _planilha(tmp_path)
    r = ica.executar(MUNICIPIOS, atualizar="nao", caminho=p, url="https://exemplo/ica.xlsx", sha_esperado=ica.sha256_de(p))
    assert r.status["coletado"] and r.status["sem_dado"] == 4          # Afonso 2025 + Alegre nos 3 anos
    consultas = r.consultas.todas()
    assert len(consultas) == 1 and consultas[0].fonte == "INEP" and consultas[0].sha256 == ica.sha256_de(p)
    assert (r.tabela["q"] == consultas[0].id).all()

    municipio = pd.DataFrame([{"cod_ibge": VITORIA, "ano": 2025, "pdde_cnca": 10.0, "escolas_cnca": 2,
                               "pdde_alfabetizacao": None, "q": "x"}])
    api = cnca.programas_api(municipio, r.tabela)["cnca"]
    assert set(api) == {"repasse", "ica"} and api["repasse"][0]["indicador"] == "cnca_pdde"
    por = {(x["cod_ibge"], x["ano"]): x for x in api["ica"]}
    assert por[(VITORIA, 2025)]["valor"] == 79.0 and por[(VITORIA, 2025)]["meta"] == 70.0 and por[(VITORIA, 2025)]["nivel"] == 4
    afonso = por[(AFONSO, 2025)]
    assert afonso["valor"] is None and afonso["situacao"] == "sem_dado" and afonso["verificado"] and afonso["automatico"]
    assert all(x["indicador"] == "ica_taxa" for x in api["ica"])


def test_consolidado_do_ica_tem_proveniencia_e_pula_sem_dado(tmp_path):
    p = _planilha(tmp_path)
    r = ica.executar(MUNICIPIOS, atualizar="nao", caminho=p, url="https://exemplo/ica.xlsx", sha_esperado=ica.sha256_de(p))
    reg = Registro()
    reg.juntar(r.consultas.todas())
    c = composicao.Consolidador(reg, {VITORIA: "Vitória", AFONSO: "Afonso Cláudio", ALEGRE: "Alegre"}, {})
    composicao._consolidar_ica(c, {"resultados": r.tabela, "metas": r.metas})
    t = c.tabela()
    assert {"ica_taxa", "ica_meta", "ica_participacao"} <= set(t["indicador"])
    assert composicao.validar(t)["sem_proveniencia"] == 0
    taxas = t[t["indicador"] == "ica_taxa"]
    assert not ((taxas["cod_ibge"] == AFONSO) & (taxas["ano"] == 2025)).any()   # sem dado não vira linha (nem zero)
    assert not (taxas["cod_ibge"] == ALEGRE).any()
    assert len(t[(t["indicador"] == "ica_meta") & (t["cod_ibge"] == VITORIA)]) == 7
    assert (t["fonte"] == "INEP").all()


def test_niveis_cobrem_a_escala_publicada():
    assert set(ica.NIVEIS) == {0, 1, 2, 3, 4, 5} and "40%" in ica.NIVEIS[0] and "80%" in ica.NIVEIS[5]
    assert ica.LIMIAR_SAEB == 743


def test_ica_e_campo_automatico_e_nao_aceita_dado_manual(tmp_path):
    catalogo = programas.carregar()
    p = tmp_path / "m.yaml"
    p.write_text("programas:\n  cnca:\n    ica:\n      - {cod_ibge: 3205309, ano: 2025, valor: 50, fonte: X, verificado_em: 2026-09-23}\n",
                 encoding="utf-8")
    with pytest.raises(ErroManuais, match="vem de API"):
        manuais.carregar(catalogo, MUNICIPIOS, p)
