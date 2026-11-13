"""Redes do financiamento da educação municipal no ES — o dado do painel de grafos.

Três redes, todas a partir do que o pipeline já guardou no cache:

* **Fornecedores** — grafo bipartido município × fornecedor (pessoa jurídica,
  agrupada pela raiz do CNPJ), com o valor empenhado na função 12 de 2021 a 2025,
  separado por **mercado** (transporte escolar, alimentação, obras…), exercício e
  **origem do recurso** (impostos, FUNDEB, FNDE, Estado, outras). Fonte: empenhos
  dos municípios do TCE-ES, recorte da função 12 em ``dados/bruto/tcees/empenhos/``.
* **Municípios conectados** — a projeção do grafo acima: dois municípios se ligam
  quando compram do mesmo fornecedor. Cada fornecedor distribui uma unidade de
  ligação entre os municípios que atende (peso de Newman, 1/(k−1)): quem atende
  60 municípios quase não liga ninguém; quem atende dois liga muito. As
  comunidades (Louvain, semente fixa) são os "mercados regionais", comparados às
  regiões do IBGE pelo índice de Rand ajustado e pela informação mútua normalizada.
* **Obras** — contratada × município nas obras da Educação do TCE-ES
  (``dados/processado/tcees_obras_educacao.csv``), com a situação de cada contrato.

Do IBGE vêm a malha dos 78 municípios e as regiões imediatas/intermediárias
(baixadas uma vez para ``dados/bruto/ibge/``, com SHA-256 e instante da coleta).

    python -m financiamento.etl.grafos      # grava dados/processado/grafos.json e os CSVs grafos_*.csv
    python -m financiamento.build_grafos    # monta financiamento/redes_financiamento.html

Ligação entre municípios, fornecedor em muitos municípios ou obra parada não são
irregularidade: são **padrões para orientar a verificação**. O dado é o que os
municípios declararam ao TCE-ES (CidadES).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import requests

from .config import BRUTO, PROCESSADO
from .parsing import norm
from .proveniencia import Consulta, Registro, caminho_relativo, juntar_ids
from .tcees import CONSELHO_ESCOLAR, ClienteTcees, Municipios, num_br, partes_empenhos, so_educacao

log = logging.getLogger(__name__)

ANOS_PADRAO = (2021, 2022, 2023, 2024, 2025)
SAIDA_JSON = PROCESSADO / "grafos.json"
PASTA_IBGE = BRUTO / "ibge"
ESQUEMA = 1

URL_LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/32/municipios"
URL_MALHA = ("https://servicodados.ibge.gov.br/api/v3/malhas/estados/32?formato=application/vnd.geo%2Bjson"
             "&intrarregiao=municipio&qualidade=intermediaria")

#: Projeção equiretangular centrada no ES: x = (lon − LON0)·cos(LAT0)·K, y = −(lat − LAT0)·K.
#: Em 3,4° de latitude o erro é desprezível, e o JS desenha a malha com a mesma fórmula.
PROJECAO = {"lon0": -40.67, "lat0": -19.6, "k": 290.0}

#: Semente do Louvain e da disposição: a mesma figura a cada execução.
SEMENTE = 42
RESOLUCAO = 1.0

# --------------------------------------------------------------------- mercados
#: Mercado de cada linha de empenho, decidido pela natureza da despesa (elemento e
#: subelemento) e, quando a natureza é genérica, pelo nome do programa/ação. A ordem
#: importa: vale a primeira regra que casar. Conferido nos subelementos de maior valor
#: de 2021–2025 (ver README, "Redes"). Pessoal (grupo 1) fica FORA da rede: o credor
#: da folha é o banco, o RPPS ou o próprio ente — não é fornecedor.
MERCADOS = [
    ("transporte", "Transporte escolar",
     "subelemento 39.32 (transporte escolar) ou 33.03 (locação de meios de transporte), ou ação/programa com "
     "\"transporte\" (menos vale-transporte e auxílio-transporte)"),
    ("alimentacao", "Alimentação escolar",
     "subfunção 306, subelemento 30.07 (gêneros de alimentação), 39.33 (fornecimento de alimentação) ou "
     "37.05 (copa e cozinha), ou ação com \"alimentação\", \"merenda\" ou \"PNAE\""),
    ("obras", "Obras e manutenção de prédios",
     "elemento 51 (obras e instalações) e subelementos 39.11/39.16 (manutenção de imóveis) e 30.24 (material "
     "para manutenção de imóveis)"),
    ("kits", "Uniformes e kits distribuídos aos alunos",
     "subelemento 30.23 (uniformes) e elemento 32 (material de distribuição gratuita), menos 32.04"),
    ("didatico", "Material didático e serviços pedagógicos",
     "subelementos 30.60 (material didático), 30.14 (material educativo e esportivo), 32.04 (material "
     "educacional e cultural), 39.65 (apoio ao ensino), elemento 35 (consultoria), ou elementos 32/35/39 em "
     "ação de material didático, livro, apostila, formação, capacitação, alfabetização ou aprendizagem"),
    ("maoobra", "Mão de obra terceirizada",
     "elementos 34 e 37 (locação de mão de obra: limpeza, vigilância, apoio) e subelementos 39.62, 39.77 e 39.78"),
    ("tic", "Tecnologia da informação",
     "elemento 40 (TIC), subelementos 52.19 (computadores), 30.17 (material de informática) e 39.57"),
    ("equipamentos", "Equipamentos e mobiliário", "elemento 52 (equipamentos e material permanente), exceto computadores"),
    ("consumo", "Material de consumo e expediente", "elemento 30 (material de consumo) não classificado acima"),
    ("beneficios", "Cartões de benefício e vale-transporte",
     "elementos 46 (auxílio-alimentação) e 49 (auxílio-transporte) e subelemento 39.72 (vale-transporte)"),
    ("utilidades", "Energia, água e telefonia", "subelementos 39.43 (energia), 39.44 (água e esgoto), 39.58 (telefonia) e 39.47 (comunicação)"),
    ("transferencias", "Subvenções, contribuições e auxílios",
     "elementos 41, 42, 43, 45, 48, 18 e transferências (70–76, 81): conselhos escolares, APAEs, consórcios"),
    ("outros", "Outros serviços e despesas", "o que sobra: elemento 39 genérico, 33, 47, 92, 93 etc."),
]
ID_MERCADOS = [m[0] for m in MERCADOS]
TODOS = "todos"

_TRANSP_ACAO = re.compile(r"transporte")
_ALIM_ACAO = re.compile(r"aliment|merenda|pnae")
_DIDAT_ACAO = re.compile(r"didat|apostil|livro|sistema de ensino|formacao|capacitac|alfabetiz|aprendizag")


def classificar_mercado(d: pd.DataFrame) -> pd.Series:
    """Mercado de cada linha. Colunas usadas: CodigoSubFuncao, CodigoElemento,
    CodigoSubElemento, texto (programa + ação, normalizado). Pessoal deve sair antes."""
    el = d["CodigoElemento"].astype(str).str.strip().str.zfill(2)
    sub = el + "." + d["CodigoSubElemento"].astype(str).str.strip().str.zfill(2)
    texto = d["texto"]
    sf = d["CodigoSubFuncao"].astype(str).str.strip().str.lstrip("0")
    beneficio = el.isin(["46", "49"]) | (sub == "39.72")
    utilidade = sub.isin(["39.43", "39.44", "39.58", "39.47"])
    transferencia = el.isin(["41", "42", "43", "45", "48", "18", "70", "71", "72", "73", "74", "75", "76", "81"])
    condicoes = [
        (beneficio, "beneficios"),
        (utilidade, "utilidades"),
        (transferencia, "transferencias"),
        (sub.isin(["39.32", "33.03"]) | texto.str.contains(_TRANSP_ACAO), "transporte"),
        ((sf == "306") | sub.isin(["30.07", "39.33", "37.05"]) | texto.str.contains(_ALIM_ACAO), "alimentacao"),
        ((el == "51") | sub.isin(["39.11", "39.16", "30.24"]), "obras"),
        ((sub == "30.23") | ((el == "32") & (sub != "32.04")), "kits"),
        (sub.isin(["30.60", "30.14", "32.04", "39.65"]) | (el == "35")
         | (el.isin(["32", "35", "39"]) & texto.str.contains(_DIDAT_ACAO)), "didatico"),
        (el.isin(["34", "37"]) | sub.isin(["39.62", "39.77", "39.78"]), "maoobra"),
        ((el == "40") | sub.isin(["52.19", "30.17", "39.57"]), "tic"),
        (el == "52", "equipamentos"),
        (el == "30", "consumo"),
    ]
    return pd.Series(np.select([c for c, _ in condicoes], [m for _, m in condicoes], default="outros"),
                     index=d.index, dtype="object")


# ---------------------------------------------------------------- tipo de credor
TIPOS = [
    ("empresa", "Empresas"),
    ("terceiro", "Cooperativas, associações e fundações"),
    ("publico", "Órgãos e entidades públicas"),
    ("concessionaria", "Concessionárias (energia, água, telefonia)"),
    ("conselho", "Conselhos e caixas escolares"),
]
#: Os nomes chegam do TCE-ES às vezes sem as letras acentuadas ("MINISTRIO",
#: "COMRCIO"): os padrões usam o pedaço sem acento.
_CONCESSIONARIA = re.compile(
    r"escelsa|centrais eletricas|\bedp\b|energisa|empresa luz e forca|\belfsm\b|telemar|telefonica|"
    r"\bvivo\b|\bclaro\b|\boi s\b|\boi s ?/ ?a|\boi movel|telecomunica|embratel|\btim s|tim celular|"
    r"companhia espirito santense de saneamento|\bcesan\b|saneamento")
_PUBLICO = re.compile(
    r"prefeitura|^municipio de|camara municipal|secretaria|minist|^fundo |\bfundo (municipal|estadual|nacional|"
    r"de |n\.)|\bfnde\b|instituto de previd|previdencia|\bipasma\b|\biprev|tribunal|^governo|estado do esp|"
    r"^espirito santo secretaria|\bsedu\b|\bsefaz\b|receita federal|\binss\b|instituto nacional do seguro|"
    r"\bdetran\b|corpo de bombeiros|funrebom|policia|conselho regional|\bcrea\b|universidade federal|"
    r"instituto federal|\bifes\b|\bufes\b|consorcio public|consorcio intermun|\bcim\b|caixa economica|"
    r"banco do brasil|banestes|banco do estado|correios|empresa brasileira de correios|undime|"
    r"uniao nacional dos dirigentes|\bamunes\b|associacao dos municipios|confederacao nacional de municipios|"
    r"servico autonomo|\bsaae\b|incaper|\biema\b|\bidaf\b|junta comercial|cartorio|ordem dos advogados")
_ESCOLA = re.compile(r"^(emef|emeief|emei|cmei|epg|eeef|eeefm|ceim|escola)\b|\bcaixa escolar\b")
_TERCEIRO = re.compile(r"cooperativ|\bcoop\b|\bcoop\.|^coop|associacao|instituto|fundacao|\bapae\b|sociedade|"
                       r"igreja|paroquia|movimento|federacao|organizacao|\bong\b|\bosc\b|entidade")


def tipo_credor(nome: Any) -> str:
    n = norm(nome)
    if CONSELHO_ESCOLAR.search(n) or _ESCOLA.search(n):
        return "conselho"
    if _CONCESSIONARIA.search(n):
        return "concessionaria"
    if _PUBLICO.search(n):
        return "publico"
    if _TERCEIRO.search(n):
        return "terceiro"
    return "empresa"


#: Tipos que entram na projeção município–município e no recorte padrão da página.
TIPOS_PADRAO = ("empresa", "terceiro")

# ------------------------------------------------------------- origem do recurso
FONTES = [
    ("impostos", "Impostos e recursos próprios (MDE)"),
    ("fundeb", "FUNDEB"),
    ("fnde", "FNDE (salário-educação, PNAE, PNATE e outros)"),
    ("estado", "Estado (convênios e programas estaduais)"),
    ("outras", "Outras (royalties, convênios da União, crédito…)"),
]
ID_FONTES = [f[0] for f in FONTES]


def grupo_fonte(nome: Any) -> str:
    """Origem pelo NOME da fonte reduzida — o código mudou em 2023 (111/112… → 500/540…), o nome não."""
    n = norm(nome)
    if "fundeb" in n:
        return "fundeb"
    if re.search(r"salario educa|\bfnde\b|\bpnae\b|\bpnate\b|alimentacao escolar|transporte escolar", n):
        return "fnde"
    if re.search(r"\bdos estados\b|\bdo estado\b|\bestados para\b|\bestaduais\b", n):
        return "estado"
    if re.search(r"impostos|ordinarios|nao vinculados", n):
        return "impostos"
    return "outras"


# ---------------------------------------------------------------- utilidades
def raiz_cnpj(doc: Any) -> str | None:
    """CNPJ com 14 dígitos → os 8 da raiz (a empresa, juntando matriz e filiais)."""
    d = re.sub(r"\D", "", str(doc or ""))
    return d[:8] if len(d) == 14 else None


def hhi(valores: Iterable[float]) -> float | None:
    """Índice de Herfindahl-Hirschman em 0–10.000 (soma dos quadrados das participações em %)."""
    v = np.array([x for x in valores if x > 0], dtype=float)
    if not v.size:
        return None
    s = v / v.sum() * 100
    return float((s ** 2).sum())


def pesos_newman(conjuntos: dict[str, Iterable[int]]) -> dict[tuple[int, int], tuple[float, int]]:
    """Fornecedor → municípios que atende ⇒ (a, b) → (peso, nº de fornecedores em comum).

    Cada fornecedor com k ≥ 2 municípios soma 1/(k−1) a cada par que atende — o
    peso de "colaboração" de Newman (2001). Um fornecedor estadual quase não liga
    ninguém; dois municípios que dividem fornecedores locais ficam fortemente ligados.
    """
    w: dict[tuple[int, int], list[float]] = defaultdict(lambda: [0.0, 0])
    for ms in conjuntos.values():
        ms = sorted(set(ms))
        k = len(ms)
        if k < 2:
            continue
        p = 1.0 / (k - 1)
        for i in range(k):
            for j in range(i + 1, k):
                par = w[(ms[i], ms[j])]
                par[0] += p
                par[1] += 1
    return {k: (v[0], int(v[1])) for k, v in w.items()}


def ari(a: dict[Any, Any], b: dict[Any, Any]) -> float | None:
    """Índice de Rand ajustado entre duas partições dos mesmos elementos (1 = idênticas, ~0 = acaso)."""
    nos = [x for x in a if x in b]
    n = len(nos)
    if n < 2:
        return None
    c2 = lambda x: x * (x - 1) / 2
    cont = Counter((a[x], b[x]) for x in nos)
    sa = sum(c2(v) for v in Counter(a[x] for x in nos).values())
    sb = sum(c2(v) for v in Counter(b[x] for x in nos).values())
    s = sum(c2(v) for v in cont.values())
    esperado = sa * sb / c2(n)
    maximo = 0.5 * (sa + sb)
    return None if maximo == esperado else float((s - esperado) / (maximo - esperado))


def nmi(a: dict[Any, Any], b: dict[Any, Any]) -> float | None:
    """Informação mútua normalizada (média aritmética das entropias): 1 = idênticas, 0 = independentes."""
    nos = [x for x in a if x in b]
    n = len(nos)
    if n < 2:
        return None
    cont = Counter((a[x], b[x]) for x in nos)
    ra, rb = Counter(a[x] for x in nos), Counter(b[x] for x in nos)
    mi = sum(v / n * math.log((v / n) / ((ra[i] / n) * (rb[j] / n))) for (i, j), v in cont.items())
    ha = -sum(v / n * math.log(v / n) for v in ra.values())
    hb = -sum(v / n * math.log(v / n) for v in rb.values())
    return None if ha + hb == 0 else float(2 * mi / (ha + hb))


def projetar(lon: float, lat: float) -> tuple[float, float]:
    p = PROJECAO
    return ((lon - p["lon0"]) * math.cos(math.radians(p["lat0"])) * p["k"], -(lat - p["lat0"]) * p["k"])


# ------------------------------------------------------------------- IBGE
@dataclass(frozen=True)
class Ibge:
    municipios: list[dict[str, Any]]
    malha: dict[str, Any]
    consultas: list[Consulta]


def _baixar_ibge(nome: str, url: str, atualizar: bool) -> tuple[bytes, Consulta]:
    dados_p, meta_p = PASTA_IBGE / nome, PASTA_IBGE / (nome + ".meta.json")
    if dados_p.exists() and meta_p.exists() and not atualizar:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        dados = dados_p.read_bytes()
    else:
        r = requests.get(url, timeout=(20, 120), headers={"User-Agent": "neduc-financiamento/1.0 (grafos)"})
        r.raise_for_status()
        dados = r.content
        meta = {"url": url, "obtido_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(dados).hexdigest(), "tamanho": len(dados)}
        PASTA_IBGE.mkdir(parents=True, exist_ok=True)
        dados_p.write_bytes(dados)
        meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    descr = {"municipios_es.json": "IBGE — localidades: municípios do ES com micro, região imediata e intermediária",
             "malha_municipios_es.geojson": "IBGE — malha municipal do ES (API de malhas v3, qualidade intermediária)"}[nome]
    c = Consulta(fonte="IBGE", recurso=f"ibge_{nome.split('.')[0]}", descricao=descr, url=meta["url"],
                 obtido_em=meta["obtido_em"], arquivo=caminho_relativo(dados_p), sha256=meta.get("sha256"))
    return dados, c


def ler_ibge(atualizar: bool = False) -> Ibge:
    d1, c1 = _baixar_ibge("municipios_es.json", URL_LOCALIDADES, atualizar)
    d2, c2 = _baixar_ibge("malha_municipios_es.geojson", URL_MALHA, atualizar)
    return Ibge(json.loads(d1.decode("utf-8")), json.loads(d2.decode("utf-8")), [c1, c2])


def _poligonos(geom: dict[str, Any]) -> list[list[list[float]]]:
    """Anéis externos de um Polygon/MultiPolygon."""
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [p[0] for p in geom["coordinates"]]


def _area(anel: np.ndarray) -> float:
    x, y = anel[:, 0], anel[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _dentro(px: np.ndarray, py: np.ndarray, anel: np.ndarray) -> np.ndarray:
    """Ponto em polígono (par-ímpar), vetorizado nos pontos."""
    dentro = np.zeros(px.shape, dtype=bool)
    x, y = anel[:, 0], anel[:, 1]
    x2, y2 = np.roll(x, -1), np.roll(y, -1)
    for a, b, c, d in zip(x, y, x2, y2):
        cruza = ((b > py) != (d > py)) & (px < (c - a) * (py - b) / ((d - b) if d != b else 1e-12) + a)
        dentro ^= cruza
    return dentro


def ponto_interior(geom: dict[str, Any], grade: int = 36) -> tuple[float, float]:
    """Ponto bem dentro do município (aproxima o "polo de inacessibilidade"): numa grade
    sobre o maior polígono, o ponto interno mais distante da borda. Diferente do centroide,
    nunca cai fora de um município côncavo nem no mar."""
    anel = max((np.array(p, dtype=float) for p in _poligonos(geom)), key=_area)
    xmin, ymin = anel.min(axis=0)
    xmax, ymax = anel.max(axis=0)
    gx, gy = np.meshgrid(np.linspace(xmin, xmax, grade), np.linspace(ymin, ymax, grade))
    px, py = gx.ravel(), gy.ravel()
    dentro = _dentro(px, py, anel)
    if not dentro.any():
        c = anel.mean(axis=0)
        return float(c[0]), float(c[1])
    px, py = px[dentro], py[dentro]
    a, b = anel[:-1], anel[1:]
    ab = b - a
    comp2 = (ab ** 2).sum(axis=1) + 1e-18
    p = np.stack([px, py], axis=1)[:, None, :]
    t = np.clip(((p - a[None]) * ab[None]).sum(axis=2) / comp2[None], 0, 1)
    proj = a[None] + t[..., None] * ab[None]
    dist = np.sqrt(((p - proj) ** 2).sum(axis=2)).min(axis=1)
    i = int(np.argmax(dist))
    return float(px[i]), float(py[i])


def municipios_ibge(ibge: Ibge, nomes_ibge: dict[int, str]) -> list[dict[str, Any]]:
    """Os 78, na ordem do código IBGE, com posição no mapa e regiões."""
    por_cod = {int(m["id"]): m for m in ibge.municipios}
    geom = {int(f["properties"]["codarea"]): f["geometry"] for f in ibge.malha["features"]}
    saida = []
    for cod in sorted(nomes_ibge):
        m = por_cod.get(cod)
        if m is None or cod not in geom:
            raise ValueError(f"município {cod} sem cadastro ou sem malha no IBGE")
        lon, lat = ponto_interior(geom[cod])
        x, y = projetar(lon, lat)
        imed = m["regiao-imediata"]
        saida.append({"cod": cod, "nome": nomes_ibge[cod], "lon": round(lon, 5), "lat": round(lat, 5),
                      "x": round(x, 2), "y": round(y, 2),
                      "imediata": imed["nome"], "intermediaria": imed["regiao-intermediaria"]["nome"],
                      "micro": m["microrregiao"]["nome"]})
    return saida


def fronteiras(malha: dict[str, Any], regiao: dict[int, str]) -> list[list[float]]:
    """Segmentos de borda entre municípios de regiões diferentes, mais a borda do estado.

    A malha do IBGE é topológica: dois vizinhos descrevem a divisa com os MESMOS
    vértices (conferido: 2.921 segmentos aparecem em exatamente dois municípios, 749 em
    um só — a divisa do estado e o litoral). Basta comparar a região dos dois lados.
    """
    lados: dict[tuple, set[int]] = defaultdict(set)
    for f in malha["features"]:
        cod = int(f["properties"]["codarea"])
        geom = f["geometry"]
        for p in ([geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]):
            for anel in p:
                for a, b in zip(anel, anel[1:]):
                    k = tuple(sorted([(round(a[0], 4), round(a[1], 4)), (round(b[0], 4), round(b[1], 4))]))
                    lados[k].add(cod)
    saida = []
    for (a, b), cods in sorted(lados.items()):
        if len(cods) == 1 or len({regiao.get(c) for c in cods}) > 1:
            saida.append([a[0], a[1], b[0], b[1]])
    return saida


def malha_compacta(malha: dict[str, Any]) -> dict[str, Any]:
    """GeoJSON com as coordenadas em 4 casas (≈ 11 m) — o que o desenho precisa."""
    def arredondar(c):
        return [arredondar(x) for x in c] if isinstance(c[0], list) else [round(c[0], 4), round(c[1], 4)]
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"cod": int(f["properties"]["codarea"])},
         "geometry": {"type": f["geometry"]["type"], "coordinates": arredondar(f["geometry"]["coordinates"])}}
        for f in malha["features"]]}


# --------------------------------------------------------------- empenhos
COLUNAS = ["Ano", "AnoReferencia", "Mes", "MesReferencia", "EsferaAdministrativa", "CodigoSubFuncao", "NomePrograma",
           "NomeAcao", "CodigoCompleto", "CodigoGrupoNatureza", "CodigoModalidade", "CodigoElemento",
           "CodigoSubElemento", "NomeFonteReduzida", "Empenhada", "Paga", "NomeCredorFornecedor",
           "CodigoCredorFornecedor", "NomeIdentificacao"]


def reduzir_parte(df: pd.DataFrame, mun: Municipios, ano: int) -> dict[str, pd.DataFrame]:
    """Uma parte do arquivo anual → somas por município × credor × mercado × origem × ação."""
    d = df.rename(columns={"AnoReferencia": "Ano", "MesReferencia": "Mes"})
    d = d.loc[:, ~d.columns.duplicated()].reindex(columns=[c for c in COLUNAS if c not in ("AnoReferencia", "MesReferencia")])
    d["cod_ibge"] = d["EsferaAdministrativa"].map(mun.cod)
    d = d[d["cod_ibge"].notna() & (d["CodigoModalidade"].astype(str).str.strip() != "91")].copy()
    d["cod_ibge"] = d["cod_ibge"].astype(int)
    d["ano"] = pd.to_numeric(d["Ano"], errors="coerce").fillna(ano).astype(int)
    d["mes"] = pd.to_numeric(d["Mes"], errors="coerce")
    for c in ("Empenhada", "Paga"):
        d[c] = num_br(d[c]).fillna(0.0).astype(float)
    grupo = d["CodigoGrupoNatureza"].astype(str).str.strip()
    grupo = grupo.where(grupo != "", d["CodigoCompleto"].astype(str).str[1:2])
    pessoal = grupo == "1"
    ident = d["NomeIdentificacao"].astype(str).str.upper().str.strip()
    d["raiz"] = d["CodigoCredorFornecedor"].map(raiz_cnpj)
    d["classe"] = np.where(ident.eq("CNPJ") & d["raiz"].notna(), "pj", np.where(ident.eq("CPF"), "pf", "outro"))
    d["fonte"] = d["NomeFonteReduzida"].map(grupo_fonte)
    meses = d[["cod_ibge", "ano", "mes"]].drop_duplicates()
    fora = d[pessoal].groupby(["cod_ibge", "ano"], as_index=False)["Empenhada"].sum()
    e = d[~pessoal].copy()
    e["texto"] = (e["NomePrograma"].astype(str) + " | " + e["NomeAcao"].astype(str)).map(norm)
    e["mercado"] = classificar_mercado(e)
    pj = e[e["classe"] == "pj"]
    arestas = pj.groupby(["cod_ibge", "ano", "raiz", "mercado", "fonte", "NomeAcao"], as_index=False)[["Empenhada", "Paga"]].sum()
    nomes = pj.groupby(["raiz", "CodigoCredorFornecedor", "NomeCredorFornecedor"], as_index=False)["Empenhada"].sum()
    resto = e[e["classe"] != "pj"].groupby(["cod_ibge", "ano", "mercado", "fonte", "classe"], as_index=False)["Empenhada"].sum()
    return {"arestas": arestas, "nomes": nomes, "resto": resto, "pessoal": fora, "meses": meses}


def ler_empenhos(anos: Iterable[int], nomes_ibge: dict[int, str]) -> tuple[dict[str, pd.DataFrame], dict[int, list[Consulta]], list[dict]]:
    """Lê do cache (sem rede) as partes de cada ano e junta as reduções."""
    cliente = ClienteTcees(atualizar="offline")
    mun = Municipios(nomes_ibge)
    partes: dict[str, list[pd.DataFrame]] = defaultdict(list)
    consultas: dict[int, list[Consulta]] = defaultdict(list)
    avisos: list[dict] = []
    for ano, r in partes_empenhos(cliente, anos):
        chave = f"empenhos/{ano}/{r['nome'].strip()}"
        a = cliente.recorte_zip(chave, r["url"], so_educacao, {"recurso": r["nome"], "filtro": "CodigoFuncao = 12"})
        if not a.obtido_em or a.caminho is None:
            avisos.append({"recurso": chave, "aviso": "fora do cache — rode antes `python -m financiamento.etl.tcees`"})
            continue
        consultas[ano].append(a.consulta(f"TCE-ES — Empenhos dos municípios, {r['nome'].strip()} (recorte: função 12)"))
        df = pd.read_csv(a.caminho, sep=";", encoding="utf-8", dtype=str, keep_default_na=False,
                         usecols=lambda c: c in COLUNAS)
        for k, v in reduzir_parte(df, mun, ano).items():
            partes[k].append(v)
        log.info("grafos: %s (%d linhas)", chave, len(df))
        del df
    if not partes:
        raise SystemExit("nenhum arquivo de empenhos no cache do TCE-ES — rode `python -m financiamento.etl.tcees --anos 2021-2025`")
    soma = lambda k, chave, cols: pd.concat(partes[k], ignore_index=True).groupby(chave, as_index=False)[cols].sum()
    junto = {
        "arestas": soma("arestas", ["cod_ibge", "ano", "raiz", "mercado", "fonte", "NomeAcao"], ["Empenhada", "Paga"]),
        "nomes": soma("nomes", ["raiz", "CodigoCredorFornecedor", "NomeCredorFornecedor"], ["Empenhada"]),
        "resto": soma("resto", ["cod_ibge", "ano", "mercado", "fonte", "classe"], ["Empenhada"]),
        "pessoal": soma("pessoal", ["cod_ibge", "ano"], ["Empenhada"]),
        "meses": pd.concat(partes["meses"], ignore_index=True).drop_duplicates(),
    }
    return junto, dict(consultas), avisos


def nome_preferido(variantes: pd.DataFrame) -> str:
    """Entre as grafias de um mesmo CNPJ, a de maior valor — evitando as que chegaram com '?' no lugar de letra."""
    v = variantes.assign(ruim=variantes["NomeCredorFornecedor"].str.contains(r"[?�]", regex=True))
    v = v.sort_values(["ruim", "Empenhada"], ascending=[True, False])
    return re.sub(r"\s+", " ", str(v["NomeCredorFornecedor"].iloc[0])).strip()


# ------------------------------------------------------------- disposição
def _espiral(n: int, raio: float = 0.6) -> np.ndarray:
    """Deslocamento determinístico (ângulo de ouro) para separar nós que nasceriam no mesmo ponto."""
    i = np.arange(n)
    ang = i * 2.399963
    r = raio * np.sqrt((i % 97) + 1)
    return np.stack([np.cos(ang) * r, np.sin(ang) * r], axis=1)


def relaxar_colisoes(pos: np.ndarray, raio: np.ndarray, fixos: np.ndarray, iteracoes: int = 60, folga: float = 0.8) -> np.ndarray:
    """Empurra nós sobrepostos até cada um ter o seu espaço; os fixos (municípios) não se movem."""
    pos = pos.copy()
    n = len(pos)
    livres = ~fixos
    for _ in range(iteracoes):
        mov = np.zeros_like(pos)
        maior = 0.0
        for s in range(0, n, 700):
            d = pos[s:s + 700, None, :] - pos[None, :, :]
            dist = np.sqrt((d ** 2).sum(axis=2)) + 1e-9
            sobra = raio[s:s + 700, None] + raio[None, :] + folga - dist
            idx = np.arange(s, min(s + 700, n))
            sobra[np.arange(len(idx)), idx] = 0
            sobra = np.where(sobra > 0, sobra, 0.0)
            # quem é livre leva o empurrão inteiro quando o outro é fixo; metade quando os dois são livres
            fator = np.where(fixos[None, :], 1.0, 0.5)
            mov[s:s + 700] += ((sobra * fator)[..., None] * d / dist[..., None]).sum(axis=1)
            maior = max(maior, float(sobra.max()))
        pos[livres] += mov[livres] * 0.9
        if maior < 0.05:
            break
    return pos


def conter(pos: np.ndarray, percentil: float = 95.0, folga: float = 1.12) -> np.ndarray:
    """Traz para um anel em volta da rede os nós que a repulsão jogou longe — em geral,
    município sem nenhum fornecedor compartilhado no mercado. Sem isso, um ponto
    solto achata a figura inteira quando a página enquadra tudo."""
    centro = np.median(pos, axis=0)
    p = pos - centro
    r = np.linalg.norm(p, axis=1)
    limite = float(np.percentile(r, percentil)) * folga if len(r) else 0.0
    if limite <= 0:
        return pos
    fora = r > limite
    novo = limite * (1 + 0.08 * np.tanh((r[fora] - limite) / limite))
    p[fora] = p[fora] / r[fora, None] * novo[:, None]
    return p + centro


def forca_atlas(pos0: np.ndarray, ai: np.ndarray, aj: np.ndarray, peso: np.ndarray, iteracoes: int = 260,
                kr: float = 1.0, kg: float = 1.0) -> np.ndarray:
    """ForceAtlas2 simplificado (Jacomy et al., 2014), denso em numpy: repulsão proporcional
    às massas (grau + 1), atração linear ponderada, gravidade fraca e passo resfriado.
    Determinístico: parte da disposição do mapa e não sorteia nada. `kr` = 1 foi escolhido
    comparando variantes desenhadas (2026-10-26): com repulsão maior a rede vira um disco
    uniforme e as comunidades somem; com 1, os três mercados regionais aparecem separados."""
    pos = pos0.astype(float).copy()
    pos -= pos.mean(axis=0)
    n = len(pos)
    grau = np.bincount(ai, minlength=n) + np.bincount(aj, minlength=n)
    massa = grau + 1.0
    t0 = 0.08 * float(np.abs(pos).max() or 1.0)
    for it in range(iteracoes):
        f = np.zeros_like(pos)
        for s in range(0, n, 512):
            d = pos[s:s + 512, None, :] - pos[None, :, :]
            d2 = (d ** 2).sum(axis=2) + 1.0
            f[s:s + 512] += ((kr * massa[s:s + 512, None] * massa[None, :] / d2)[..., None] * d).sum(axis=1)
        delta = pos[ai] - pos[aj]
        fa = peso[:, None] * delta
        np.subtract.at(f, ai, fa)
        np.add.at(f, aj, fa)
        norma = np.linalg.norm(pos, axis=1, keepdims=True) + 1e-9
        f -= kg * massa[:, None] * pos / norma
        desl = f / massa[:, None]
        tam = np.linalg.norm(desl, axis=1, keepdims=True) + 1e-9
        t = t0 * (1 - it / iteracoes) + 0.2
        pos += desl * np.minimum(1.0, t / tam)
    return pos


def _ajustar_extensao(pos: np.ndarray, referencia: np.ndarray) -> np.ndarray:
    """Leva a disposição livre para a mesma escala da do mapa (mesma altura e centro)."""
    p = pos - pos.mean(axis=0)
    ext = np.percentile(np.abs(p), 98, axis=0).max() or 1.0
    ref = referencia - referencia.mean(axis=0)
    ext_ref = np.percentile(np.abs(ref), 98, axis=0).max() or 1.0
    return p * (ext_ref / ext) + referencia.mean(axis=0)


def raio_no(valor: np.ndarray, maximo: float) -> np.ndarray:
    """Raio do nó em unidades do mapa — o mesmo que a página usa ao desenhar."""
    return 2.2 + 11.0 * np.sqrt(np.clip(valor, 0, None) / (maximo or 1.0))


def disposicoes(municipios: list[dict], fornecedores_k: pd.DataFrame, arestas: pd.DataFrame) -> dict[str, Any]:
    """Para um mercado: posição de cada fornecedor (k ≥ 2) no mapa e na disposição por forças.

    `fornecedores_k`: índice do fornecedor (f) e valor; `arestas`: m (índice do município), f, valor.
    """
    nm = len(municipios)
    mpos = np.array([[m["x"], m["y"]] for m in municipios], dtype=float)
    fs = fornecedores_k["f"].to_numpy()
    if not len(fs):
        return {"nos": [], "mapa": [], "forca": [], "forca_municipios": mpos.round(1).ravel().tolist()}
    local = {f: i for i, f in enumerate(fs)}
    a = arestas[arestas["f"].isin(local)]
    fi = a["f"].map(local).to_numpy()
    mi = a["m"].to_numpy()
    w = np.sqrt(np.clip(a["valor"].to_numpy(dtype=float), 0, None))
    # Mapa: centro de gravidade dos municípios atendidos, ponderado pela raiz do valor.
    soma = np.zeros((len(fs), 2))
    np.add.at(soma, fi, mpos[mi] * w[:, None])
    tot = np.bincount(fi, weights=w, minlength=len(fs))[:, None] + 1e-12
    base = soma / tot + _espiral(len(fs), 0.4)
    vmax = float(fornecedores_k["valor"].max())
    raio = np.concatenate([np.full(nm, 5.0), raio_no(fornecedores_k["valor"].to_numpy(dtype=float), vmax)])
    tudo = np.vstack([mpos, base])
    fixos = np.concatenate([np.ones(nm, bool), np.zeros(len(fs), bool)])
    mapa = relaxar_colisoes(tudo, raio, fixos)[nm:]
    # Forças: municípios e fornecedores livres, a partir do mapa.
    ai = mi
    aj = nm + fi
    peso = np.log1p(np.clip(a["valor"].to_numpy(dtype=float), 0, None) / 1e4)
    peso = 0.02 + peso / (peso.max() or 1.0)
    livre = conter(forca_atlas(np.vstack([mpos, mapa]), ai, aj, peso))
    livre = _ajustar_extensao(livre, np.vstack([mpos, mapa]))
    livre = relaxar_colisoes(livre, raio, np.zeros(len(livre), bool), iteracoes=40)
    return {"nos": fs.tolist(), "mapa": mapa.round(1).ravel().tolist(), "forca": livre[nm:].round(1).ravel().tolist(),
            "forca_municipios": livre[:nm].round(1).ravel().tolist()}


# -------------------------------------------------------------- comunidades
def comunidades(n: int, pares: dict[tuple[int, int], tuple[float, int]], resolucao: float = RESOLUCAO) -> tuple[list[int], float | None]:
    """Louvain (networkx, semente fixa) sobre os índices 0..n−1. Isolado = −1.
    Comunidades numeradas pela ordem de tamanho (0 = a maior); devolve também a modularidade."""
    import networkx as nx

    g = nx.Graph()
    g.add_nodes_from(range(n))
    for (a, b), (w, _) in pares.items():
        g.add_edge(a, b, weight=w)
    ligados = [v for v in g.nodes if g.degree(v) > 0]
    if len(ligados) < 2:
        return [-1] * n, None
    sub = g.subgraph(ligados)
    com = nx.community.louvain_communities(sub, weight="weight", resolution=resolucao, seed=SEMENTE)
    mod = nx.community.modularity(sub, com, weight="weight")
    com = sorted(com, key=lambda c: (-len(c), min(c)))
    rot = [-1] * n
    for i, c in enumerate(com):
        for v in c:
            rot[v] = i
    return rot, float(mod)


# ------------------------------------------------------------------ obras
SITUACOES_OBRA = [
    ("presumida", "Paralisação presumida (classificação do TCE-ES)"),
    ("paralisada", "Paralisada ou interrompida (declarada)"),
    ("nao_iniciada", "Não iniciada"),
    ("execucao", "Em execução"),
    ("concluida", "Concluída"),
    ("nao_identificada", "Situação não identificada"),
]


def situacao_obra(s: Any) -> str:
    n = norm(s)
    if "presumida" in n:
        return "presumida"
    if "paralisad" in n or "interrompid" in n:
        return "paralisada"
    if "nao iniciad" in n:
        return "nao_iniciada"
    if "execu" in n:
        return "execucao"
    if "conclu" in n:
        return "concluida"
    return "nao_identificada"


def _num(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


# ------------------------------------------------------------------ montagem
def _colunar(df: pd.DataFrame, colunas: list[str]) -> dict[str, Any]:
    return {"colunas": colunas, "linhas": df[colunas].astype(object).where(df[colunas].notna(), None).values.tolist()}


def montar(anos: Iterable[int] = ANOS_PADRAO, nomes_ibge: dict[int, str] | None = None,
           atualizar_ibge: bool = False) -> dict[str, Any]:
    anos = list(anos)
    if nomes_ibge is None:
        nomes_ibge = nomes_dos_municipios()
    ibge = ler_ibge(atualizar_ibge)
    municipios = municipios_ibge(ibge, nomes_ibge)
    idx_m = {m["cod"]: i for i, m in enumerate(municipios)}
    junto, consultas, avisos = ler_empenhos(anos, nomes_ibge)
    reg = Registro()
    for c in ibge.consultas:
        reg.adicionar(c)
    q_ano: dict[int, str] = {}
    for ano, cs in consultas.items():
        q_ano[ano] = juntar_ids([reg.adicionar(c) for c in cs])
    idx_ano = {a: i for i, a in enumerate(anos)}
    idx_k = {k: i for i, k in enumerate(ID_MERCADOS)}
    idx_fo = {f: i for i, f in enumerate(ID_FONTES)}

    # Fornecedores: raiz do CNPJ, nome preferido, tipo, CNPJs (matriz e filiais).
    nomes = junto["nomes"]
    forn = []
    for raiz, g in nomes.groupby("raiz", sort=True):
        nome = nome_preferido(g)
        forn.append({"raiz": raiz, "nome": nome, "tipo": tipo_credor(nome),
                     "cnpjs": ";".join(sorted(set(re.sub(r"\D", "", x) for x in g["CodigoCredorFornecedor"])))})
    fdf = pd.DataFrame(forn)
    idx_f = {r: i for i, r in enumerate(fdf["raiz"])}

    # Arestas: (município, fornecedor, mercado) com os valores por ano × origem; ação principal.
    ar = junto["arestas"].copy()
    ar["m"] = ar["cod_ibge"].map(idx_m)
    ar["f"] = ar["raiz"].map(idx_f)
    ar = ar[ar["m"].notna() & ar["f"].notna()]
    ar["m"], ar["f"] = ar["m"].astype(int), ar["f"].astype(int)
    ar["k"] = ar["mercado"].map(idx_k).astype(int)
    acao_top = (ar.groupby(["m", "f", "k", "NomeAcao"], as_index=False)["Empenhada"].sum()
                .sort_values("Empenhada", ascending=False).drop_duplicates(["m", "f", "k"]))
    n_acoes = ar.groupby(["m", "f", "k"])["NomeAcao"].nunique()
    cel = ar.groupby(["m", "f", "k", "ano", "fonte"], as_index=False)[["Empenhada", "Paga"]].sum()
    cel = cel[(cel["Empenhada"].abs() > 0.005) | (cel["Paga"].abs() > 0.005)]
    acoes_lista = sorted(set(acao_top["NomeAcao"].map(lambda s: re.sub(r"\s+", " ", str(s)).strip())))
    idx_acao = {a: i for i, a in enumerate(acoes_lista)}
    topo = {(r.m, r.f, r.k): idx_acao[re.sub(r"\s+", " ", str(r.NomeAcao)).strip()] for r in acao_top.itertuples(index=False)}
    arestas_m, arestas_f, arestas_k, arestas_acao, arestas_nacoes, arestas_v = [], [], [], [], [], []
    for (m, f, k), g in cel.groupby(["m", "f", "k"], sort=True):
        v = []
        for r in g.itertuples(index=False):
            v.extend([idx_ano[int(r.ano)], idx_fo[r.fonte], round(float(r.Empenhada), 2), round(float(r.Paga), 2)])
        arestas_m.append(int(m)); arestas_f.append(int(f)); arestas_k.append(int(k))
        arestas_acao.append(topo.get((m, f, k))); arestas_nacoes.append(int(n_acoes.get((m, f, k), 1)))
        arestas_v.append(v)

    # Totais por fornecedor (no período) e alcance por mercado — para escolher quem entra na disposição.
    tipo_f = fdf["tipo"].to_numpy()
    per = cel.groupby(["m", "f", "k"], as_index=False)["Empenhada"].sum()
    per = per[per["Empenhada"] > 0.005]
    layouts: dict[str, Any] = {}
    projecoes: dict[str, Any] = {}
    imed = {i: m["imediata"] for i, m in enumerate(municipios)}
    inter = {i: m["intermediaria"] for i, m in enumerate(municipios)}
    for merc in [TODOS] + ID_MERCADOS:
        p = per if merc == TODOS else per[per["k"] == idx_k[merc]]
        p = p.groupby(["m", "f"], as_index=False)["Empenhada"].sum().rename(columns={"Empenhada": "valor"})
        p = p[tipo_f[p["f"].to_numpy()] != "conselho"] if len(p) else p
        alcance = p.groupby("f").agg(k=("m", "nunique"), valor=("valor", "sum")).reset_index()
        rede = alcance[alcance["k"] >= 2].sort_values("f")
        layouts[merc] = disposicoes(municipios, rede, p)
        # Projeção (só empresas e terceiro setor — o recorte padrão).
        pp = p[np.isin(tipo_f[p["f"].to_numpy()], TIPOS_PADRAO)] if len(p) else p
        conj = pp.groupby("f")["m"].apply(list).to_dict() if len(pp) else {}
        pares = pesos_newman(conj)
        rot, mod = comunidades(len(municipios), pares)
        ligados = {i: r for i, r in enumerate(rot) if r >= 0}
        projecoes[merc] = {
            "pares": [[a, b, round(w, 4), n] for (a, b), (w, n) in sorted(pares.items())],
            "comunidade": rot, "modularidade": None if mod is None else round(mod, 4),
            "n_comunidades": len(set(ligados.values())),
            "ari_imediata": _r(ari(ligados, imed)), "nmi_imediata": _r(nmi(ligados, imed)),
            "ari_intermediaria": _r(ari(ligados, inter)), "nmi_intermediaria": _r(nmi(ligados, inter)),
            "fornecedores_compartilhados": int(sum(1 for v in conj.values() if len(set(v)) >= 2)),
        }
        log.info("grafos: mercado %s — %d fornecedores na rede, %d comunidades", merc, len(rede), projecoes[merc]["n_comunidades"])

    # O que fica fora da rede (pessoa física, outros identificadores, folha): soma por município × ano × mercado × origem.
    resto = junto["resto"].copy()
    resto["m"] = resto["cod_ibge"].map(idx_m)
    resto = resto[resto["m"].notna() & (resto["Empenhada"].abs() > 0.005)]
    residuais = [[int(r.m), idx_k[r.mercado], idx_ano[int(r.ano)], idx_fo[r.fonte], r.classe, round(float(r.Empenhada), 2)]
                 for r in resto.itertuples(index=False)]
    pes = junto["pessoal"]
    pessoal = [[idx_m[int(r.cod_ibge)], idx_ano[int(r.ano)], round(float(r.Empenhada), 2)]
               for r in pes.itertuples(index=False) if int(r.cod_ibge) in idx_m]

    # Completude: meses que o arquivo do TCE-ES traz (2023 não traz dezembro para parte dos municípios).
    meses = junto["meses"].dropna()
    incompletos = []
    for (cod, ano), g in meses.groupby(["cod_ibge", "ano"]):
        faltam = [x for x in range(1, 13) if x not in set(g["mes"].astype(int))]
        if faltam and int(ano) < datetime.now().year:
            incompletos.append({"m": idx_m[int(cod)], "ano": int(ano), "faltam": faltam})

    # Conferência: a soma da rede + resto + pessoal é o total de empenhos do TCE-ES (sem intra) do painel.
    conferencia = conferir_total(cel, resto, pes, municipios, anos)

    obras, q_obras = montar_obras(idx_m, idx_f, municipios)

    totais = {
        "pj": round(float(cel["Empenhada"].sum()), 2),
        "pf": round(float(resto.loc[resto["classe"] == "pf", "Empenhada"].sum()), 2),
        "outro": round(float(resto.loc[resto["classe"] == "outro", "Empenhada"].sum()), 2),
        "pessoal": round(float(pes["Empenhada"].sum()), 2),
    }
    consultas_json = {c.id: {"fonte": c.fonte, "descricao": c.descricao, "url": c.url, "obtido_em": c.obtido_em,
                             "arquivo": c.arquivo, "sha256": c.sha256, "metodo": c.metodo} for c in reg.todas()}
    for cid, c in carregar_consultas(q_obras).items():
        consultas_json.setdefault(cid, c)
    return {
        "meta": {
            "esquema": ESQUEMA, "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "anos": anos, "projecao": PROJECAO, "semente": SEMENTE, "resolucao": RESOLUCAO,
            "mercados": [{"id": i, "rotulo": r, "regra": g} for i, r, g in MERCADOS],
            "tipos": [{"id": i, "rotulo": r} for i, r in TIPOS], "tipos_padrao": list(TIPOS_PADRAO),
            "fontes": [{"id": i, "rotulo": r} for i, r in FONTES],
            "situacoes_obra": [{"id": i, "rotulo": r} for i, r in SITUACOES_OBRA],
            "q_empenhos": {str(a): q for a, q in q_ano.items()}, "q_ibge": juntar_ids([c.id for c in ibge.consultas]),
            "q_obras": q_obras, "consultas": consultas_json, "totais": totais, "incompletos": incompletos,
            "conferencia": conferencia, "avisos": avisos,
        },
        "municipios": municipios,
        "malha": malha_compacta(ibge.malha),
        "fronteiras": {
            "intermediaria": fronteiras(ibge.malha, {m["cod"]: m["intermediaria"] for m in municipios}),
            "imediata": fronteiras(ibge.malha, {m["cod"]: m["imediata"] for m in municipios}),
        },
        "fornecedores": _colunar(fdf, ["raiz", "nome", "tipo", "cnpjs"]),
        "acoes": acoes_lista,
        "arestas": {"m": arestas_m, "f": arestas_f, "k": arestas_k, "acao": arestas_acao, "n_acoes": arestas_nacoes,
                    "v": arestas_v},
        "residuais": residuais, "pessoal": pessoal,
        "layouts": layouts, "projecoes": projecoes, "obras": obras,
    }


def _r(x: float | None, d: int = 3) -> float | None:
    return None if x is None else round(x, d)


def conferir_total(cel: pd.DataFrame, resto: pd.DataFrame, pes: pd.DataFrame, municipios: list[dict], anos: list[int]) -> dict[str, Any]:
    """Compara a soma do que a rede leu com `tcees_empenhos_total.csv` (o total do painel principal)."""
    arq = PROCESSADO / "tcees_empenhos_total.csv"
    if not arq.exists():
        return {"ok": None, "motivo": "tcees_empenhos_total.csv ausente"}
    ref = pd.read_csv(arq)
    cod = {i: m["cod"] for i, m in enumerate(municipios)}
    a = cel.groupby(["m", "ano"])["Empenhada"].sum()
    b = resto.groupby(["m", "ano"])["Empenhada"].sum()
    soma = defaultdict(float)
    for (m, ano), v in a.items():
        soma[(cod[int(m)], int(ano))] += v
    for (m, ano), v in b.items():
        soma[(cod[int(m)], int(ano))] += v
    for r in pes.itertuples(index=False):
        soma[(int(r.cod_ibge), int(r.ano))] += r.Empenhada
    difs = []
    for r in ref.itertuples(index=False):
        if int(r.ano) in anos:
            difs.append(abs(soma.get((int(r.cod_ibge), int(r.ano)), 0.0) - float(r.tcees_emp_empenhada)))
    maior = max(difs) if difs else None
    return {"ok": maior is not None and maior < 1.0, "municipio_anos": len(difs),
            "maior_diferenca": None if maior is None else round(maior, 2)}


def carregar_consultas(ids: str) -> dict[str, dict]:
    """As consultas do pipeline (consultas.csv) citadas por `ids` — para o "ver fonte" das obras."""
    arq = PROCESSADO / "consultas.csv"
    if not ids or not arq.exists():
        return {}
    alvo = set(ids.split(";"))
    c = pd.read_csv(arq, dtype=str, keep_default_na=False)
    c = c[c["id"].isin(alvo)]
    return {r["id"]: {"fonte": r["fonte"], "descricao": r["descricao"], "url": r["url"], "obtido_em": r["obtido_em"],
                      "arquivo": r["arquivo"], "sha256": r.get("sha256") or None, "metodo": r.get("metodo") or "GET"}
            for r in c.to_dict("records")}


def montar_obras(idx_m: dict[int, int], idx_f: dict[str, int], municipios: list[dict]) -> tuple[dict[str, Any], str]:
    """Contratos de obra da Educação (TCE-ES) → arestas contratada × município e disposição no mapa."""
    arq = PROCESSADO / "tcees_obras_educacao.csv"
    if not arq.exists():
        return {"contratadas": {"colunas": [], "linhas": []}, "contratos": {"colunas": [], "linhas": []}, "layout": {}}, ""
    o = pd.read_csv(arq, dtype=str, keep_default_na=False)
    o = o[o["cod_ibge"].map(lambda c: c.isdigit() and int(c) in idx_m)].copy()
    o["m"] = o["cod_ibge"].astype(int).map(idx_m)
    o["doc"] = o["cnpj_contratado"].str.replace(r"\D", "", regex=True)
    o["id"] = o["doc"].map(lambda d: d[:8] if len(d) == 14 else (d or "sem-documento"))
    o["sit"] = o["situacao"].map(situacao_obra)
    o["valor_n"] = o["valor"].map(_num).fillna(o["valor_inicial"].map(_num))
    contratadas = []
    for cid, g in o.groupby("id", sort=True):
        nome = g["contratado"].mode().iloc[0] if len(g["contratado"].mode()) else g["contratado"].iloc[0]
        contratadas.append({"id": cid, "nome": re.sub(r"\s+", " ", nome).strip(), "docs": ";".join(sorted(set(g["doc"]))),
                            "f": idx_f.get(cid), "valor": round(float(g["valor_n"].fillna(0).sum()), 2)})
    cdf = pd.DataFrame(contratadas)
    idx_c = {c: i for i, c in enumerate(cdf["id"])}
    o["c"] = o["id"].map(idx_c)
    colunas = ["m", "c", "sit", "situacao", "tipo_intervencao", "objeto", "valor_n", "valor_medido", "pct_medido",
               "ultima_medicao", "assinatura", "fim_vigencia", "aditivos", "url_contrato", "ug", "chave", "q"]
    o["valor_medido"] = o["valor_medido"].map(_num)
    o["pct_medido"] = o["pct_medido"].map(_num)
    o["aditivos"] = o["aditivos"].map(_num)
    # Disposição: contratada no centro de gravidade dos municípios onde tem obra.
    ar = o.groupby(["m", "c"], as_index=False)["valor_n"].sum().rename(columns={"c": "f", "valor_n": "valor"})
    ar["valor"] = ar["valor"].fillna(0)
    alc = ar.groupby("f").agg(valor=("valor", "sum")).reset_index().sort_values("f")
    lay = disposicoes(municipios, alc, ar)
    q = juntar_ids(*o["q"].tolist())
    return {"contratadas": _colunar(cdf, ["id", "nome", "docs", "f", "valor"]),
            "contratos": _colunar(o, colunas), "layout": lay}, q


def nomes_dos_municipios() -> dict[int, str]:
    """Os 78 municípios como o painel os conhece (financiamento_anual.csv; sem rede)."""
    arq = PROCESSADO / "financiamento_anual.csv"
    if not arq.exists():
        raise SystemExit("dados/processado/financiamento_anual.csv ausente — rode antes o pipeline")
    a = pd.read_csv(arq, usecols=["cod_ibge", "ente", "esfera"]).drop_duplicates("cod_ibge")
    return {int(r.cod_ibge): str(r.ente) for r in a.itertuples(index=False) if r.esfera == "M"}


# ------------------------------------------------------------------- saídas
def gravar_csvs(dados: dict[str, Any], pasta: Path = PROCESSADO) -> list[Path]:
    """As tabelas por trás da página, para quem prefere planilha (`;`, vírgula decimal)."""
    mun = dados["municipios"]
    anos = dados["meta"]["anos"]
    fc, fl = dados["fornecedores"]["colunas"], dados["fornecedores"]["linhas"]
    forn = [dict(zip(fc, l)) for l in fl]
    a = dados["arestas"]
    linhas = []
    for i in range(len(a["m"])):
        v = a["v"][i]
        for j in range(0, len(v), 4):
            ano = anos[v[j]]
            linhas.append({"cod_ibge": mun[a["m"][i]]["cod"], "municipio": mun[a["m"][i]]["nome"],
                           "cnpj_raiz": forn[a["f"][i]]["raiz"], "fornecedor": forn[a["f"][i]]["nome"],
                           "tipo": forn[a["f"][i]]["tipo"], "mercado": ID_MERCADOS[a["k"][i]], "ano": ano,
                           "origem": ID_FONTES[v[j + 1]], "empenhada": v[j + 2], "paga": v[j + 3],
                           "acao_principal": dados["acoes"][a["acao"][i]] if a["acao"][i] is not None else "",
                           "q": dados["meta"]["q_empenhos"].get(str(ano), "")})
    saidas = []
    for nome, df in (("grafos_arestas", pd.DataFrame(linhas)), ("grafos_fornecedores", pd.DataFrame(forn))):
        p = pasta / f"{nome}.csv"
        df.to_csv(p, sep=";", decimal=",", index=False, encoding="utf-8-sig")
        saidas.append(p)
    proj = []
    for merc, pr in dados["projecoes"].items():
        for a_, b_, w, n in pr["pares"]:
            proj.append({"mercado": merc, "cod_a": mun[a_]["cod"], "municipio_a": mun[a_]["nome"], "cod_b": mun[b_]["cod"],
                         "municipio_b": mun[b_]["nome"], "peso_newman": w, "fornecedores_em_comum": n,
                         "comunidade_a": pr["comunidade"][a_], "comunidade_b": pr["comunidade"][b_]})
    p = pasta / "grafos_projecao.csv"
    pd.DataFrame(proj).to_csv(p, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    saidas.append(p)
    return saidas


def main(argv: Iterable[str] | None = None) -> int:
    from .pipeline import parse_anos

    ap = argparse.ArgumentParser(description="Redes do financiamento da educação (fornecedores, municípios, obras).")
    ap.add_argument("--anos", type=parse_anos, default=list(ANOS_PADRAO))
    ap.add_argument("--atualizar-ibge", action="store_true", help="baixa de novo a malha e as regiões do IBGE")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    dados = montar(args.anos, atualizar_ibge=args.atualizar_ibge)
    SAIDA_JSON.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print(f"{SAIDA_JSON} ({SAIDA_JSON.stat().st_size / 1024:.0f} KB)")
    for p in gravar_csvs(dados):
        print(p)
    m = dados["meta"]
    print(json.dumps({"totais": m["totais"], "conferencia": m["conferencia"], "avisos": m["avisos"],
                      "fornecedores": len(dados["fornecedores"]["linhas"]), "arestas": len(dados["arestas"]["m"]),
                      "projecoes": {k: {x: v[x] for x in ("n_comunidades", "modularidade", "ari_intermediaria", "ari_imediata")}
                                    for k, v in dados["projecoes"].items()}}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
