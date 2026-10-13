"""Repasses do FNDE (CGU): leitura do recorte, classificação e recusa do servidor. Sem rede."""

import gzip

import pytest
import requests

from financiamento.etl import fnde

CABECALHO = ("ANO / MÊS;TIPO TRANSFERÊNCIA;TIPO FAVORECIDO;UF;CÓDIGO MUNICÍPIO SIAFI;NOME MUNICÍPIO;CÓDIGO ÓRGÃO SIAFI;"
             "NOME ÓRGÃO;AÇÃO;NOME AÇÃO;CÓDIGO PLANO ORÇAMENTÁRIO;NOME PLANO ORÇAMENTÁRIO;CÓDIGO FAVORECIDO;"
             "NOME FAVORECIDO;VALOR TRANSFERIDO")


def _recorte(tmp_path, linhas):
    p = tmp_path / "transferencias_202404_ES.csv.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write(CABECALHO + "\n" + "\n".join(linhas) + "\n")
    return p


LINHAS = [
    "202404;Legais;Administração Pública Municipal;ES;5601;AFONSO CLAUDIO;26298;FNDE;00PI;PNAE;0000;PNAE;1;PREFEITURA;146003,84",
    "202404;Legais;Entidades Sem Fins Lucrativos;ES;5601;AFONSO CLAUDIO;26298;FNDE;0515;PDDE;0000;PDDE BASICO;2;CAIXA ESCOLAR;1000,50",
    "202404;Legais;Administração Pública Estadual ou do Distrito Federal;ES;5705;VITORIA;26298;FNDE;0369;SE;0000;SE;3;ESTADO;9,99",
    "202404;Legais;Administração Pública Municipal;ES;5705;VITORIA;36000;SAUDE;8585;MAC;0000;MAC;4;FMS;777,00",
    "202404;Legais;Administração Pública Municipal;ES;5705;VITORIA;26298;FNDE;20RP;OBRAS;0000;OBRAS;5;PMV;50,00",
    # CNCA: PDDE às escolas (PO 000C) — com e sem município — e apoio ao Estado (ação 0509, PO 0014).
    "202404;Legais;Entidades Sem Fins Lucrativos;ES;5705;VITORIA;26298;FNDE;0515;PDDE;000C;PDDE - CNCA;6;CONSELHO EMEF A;3000,00",
    "202404;Legais;Entidades Sem Fins Lucrativos;ES;;;26298;FNDE;0515;PDDE;000C;PDDE - CNCA;7;CONSELHO EEEFM B;2000,00",
    "202404;Legais;Administração Pública Estadual ou do Distrito Federal;ES;;;26298;FNDE;0509;APOIO EB;0014;CNCA;8;SEDU;624559,31",
]


def test_le_o_recorte_com_valor_brasileiro(tmp_path):
    df = fnde.ler_recorte(_recorte(tmp_path, LINHAS))
    assert df.loc[0, "valor"] == pytest.approx(146003.84)
    assert {"acao", "tipo_favorecido", "municipio", "valor"} <= set(df.columns)


def test_classifica_programa_e_destino(tmp_path):
    df = fnde.classificar(fnde.ler_recorte(_recorte(tmp_path, LINHAS)))
    por_acao = dict(zip(df["acao"], zip(df["programa"], df["destino"])))
    assert por_acao["00PI"] == ("pnae", "municipio")
    assert por_acao["0515"] == ("pdde", "escolas")        # PDDE vai às unidades executoras
    assert por_acao["20RP"] == ("outras_fnde", "municipio")
    assert "8585" not in por_acao                          # saúde: não é FNDE
    assert "0369" not in por_acao                          # favorecido estadual fica de fora


def test_pdde_por_escola_guarda_o_plano_orcamentario_e_a_escola_sem_municipio(tmp_path):
    df = fnde.ler_recorte(_recorte(tmp_path, LINHAS))
    p = fnde.pdde_por_escola(df)
    assert set(p["acao"]) == {"0515"}
    cnca = p[p["po"] == fnde.PO_PDDE_CNCA]
    assert len(cnca) == 2 and cnca["valor"].sum() == pytest.approx(5000.0)
    assert set(cnca["destino"]) == {"escolas"}            # unidade executora, inclusive a estadual sem município


def test_cnca_ao_estado_pela_acao_0509_po_0014(tmp_path):
    e = fnde.cnca_estado(fnde.ler_recorte(_recorte(tmp_path, LINHAS)))
    assert len(e) == 1 and e["valor"].iloc[0] == pytest.approx(624559.31)


def test_recorte_sem_coluna_obrigatoria_e_erro_claro(tmp_path):
    p = tmp_path / "ruim.csv.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write("UF;VALOR TRANSFERIDO\nES;1,00\n")
    with pytest.raises(ValueError, match="colunas ausentes"):
        fnde.ler_recorte(p)


def test_mapa_de_municipios_pelo_nome():
    mapa = fnde.mapa_municipios({3200102: "Afonso Cláudio", 3204708: "São Gabriel da Palha"})
    assert mapa["afonso claudio"] == 3200102 and mapa["sao gabriel da palha"] == 3204708


class _Resposta:
    def __init__(self, status):
        self.status_code, self.url = status, "https://dadosabertos-download.cgu.gov.br/x.zip"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        raise requests.HTTPError(f"HTTP {self.status_code}")


def test_recusa_do_servidor_interrompe_a_coleta_sem_insistir(tmp_path, monkeypatch):
    c = fnde.ClienteTransparencia(tmp_path, pausa=0)
    chamadas = []
    monkeypatch.setattr(c.sessao, "get", lambda *a, **k: chamadas.append(1) or _Resposta(405))
    with pytest.raises(fnde.ServidorRecusou):
        c.obter("202405")
    with pytest.raises(fnde.ServidorRecusou):
        c.obter("202406")  # não tenta de novo nesta execução
    assert len(chamadas) == 1 and c.recusou


def test_mes_inexistente_e_cacheado(tmp_path, monkeypatch):
    c = fnde.ClienteTransparencia(tmp_path, pausa=0)
    monkeypatch.setattr(c.sessao, "get", lambda *a, **k: _Resposta(404))
    m = c.obter("209901")
    assert not m.existe
    assert not fnde.ClienteTransparencia(tmp_path, atualizar="offline").obter("209901").existe
