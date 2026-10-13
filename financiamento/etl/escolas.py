"""Visão por escola: o dinheiro que chega à escola, ligado ao Censo Escolar (INEP).

Três canais identificam a escola que recebeu (os únicos em dado aberto):

* **PDDE federal** (CGU): a unidade executora (conselho da escola), por plano
  orçamentário — inclui o PDDE-CNCA;
* **repasse do município ao conselho escolar** (TCE-ES, empenhos): programas
  municipais de autonomia financeira das escolas;
* **obra com bem vinculador** (TCE-ES, contratações): o prédio da obra, com coordenadas.

O pessoal (a maior parte da despesa) NÃO chega à escola em dado aberto: o vínculo
do servidor no TCE-ES não traz lotação.

A ligação ao Censo (``dw.dim_escola`` e ``dw.fato_escola_ano`` do PostgreSQL do
NEDUC) é por NOME, dentro do mesmo município e da rede compatível — o CNPJ da
unidade executora não existe no Censo. Por isso cada vínculo guarda o método e a
pontuação, e só entra no painel o que passa no limiar (``LIMIAR``) com folga sobre
o segundo candidato (``FOLGA``). Nas obras há também a distância entre o centroide
do bem e a coordenada da escola no Censo. Nada é ligado "no escuro": o que não
casa aparece como "não identificada no Censo", com o nome original.

Fonte Censo = banco local; o retrato usado fica em ``dados/bruto/censo/`` (CSV +
``.json`` com o instante e as consultas SQL), para a execução ser reproduzível
sem o banco.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .config import BRUTO
from .parsing import norm
from .proveniencia import Consulta, Registro, caminho_relativo, juntar_ids

log = logging.getLogger(__name__)

PASTA_CACHE = BRUTO / "censo"
URL_BANCO = "postgresql://localhost:5432/educacao_dw"
LIMIAR = 0.75     # fração dos termos distintivos do nome de origem achados no nome do Censo
FOLGA = 0.25      # vantagem mínima sobre o segundo melhor candidato
RAIO_OBRA_M = 400.0

SQL = {
    "escolas": """
        select e.co_entidade, e.no_entidade, e.co_municipio, e.latitude, e.longitude, e.ultimo_ano,
               f.ano as ano_censo, f.tp_dependencia, f.tp_situacao_funcionamento, f.qt_mat_bas, f.qt_doc_bas,
               f.in_internet, f.in_biblioteca, f.in_laboratorio_informatica, f.in_quadra_esportes,
               f.in_agua_potavel, f.in_esgoto_rede_publica, f.in_acessibilidade_rampas
        from dw.dim_escola e
        left join dw.fato_escola_ano f on f.co_entidade = e.co_entidade and f.ano = e.ultimo_ano
        where f.tp_dependencia in (2, 3) and e.ultimo_ano >= 2021""",
    "ideb": """
        select co_entidade, etapa, ano, ideb_observado
        from stg.v_ideb_censo where ideb_observado is not null and etapa in ('anos_iniciais', 'anos_finais')""",
    "paebes": """
        select co_entidade, ano, etapa, disciplina, proficiencia_media
        from stg.v_paebes_escola where proficiencia_media is not null""",
    # Matrículas da rede MUNICIPAL por etapa, município × ano do censo: o denominador do
    # "R$ por matrícula" de uma subfunção (12.361 ÷ fundamental, 12.362 ÷ médio). O total
    # (qt_mat_bas) vai junto para provar que é a mesma base da coluna "Alunos" do TCE-ES.
    "matriculas_etapa": """
        select e.nu_ano_censo as ano, e.co_municipio,
               sum(m.qt_mat_bas) as qt_mat_bas, sum(m.qt_mat_fund) as qt_mat_fund, sum(m.qt_mat_med) as qt_mat_med
        from stg.escola e
        join stg.matricula m on m.co_entidade = e.co_entidade and m.nu_ano_censo = e.nu_ano_censo
        where e.tp_dependencia = 3 and e.co_uf = 32 and e.nu_ano_censo >= 2021
        group by 1, 2""",
}
REDE = {2: "estadual", 3: "municipal"}
COLUNAS_CADASTRO = ["co_entidade", "nome", "cod_ibge", "rede", "ano_censo", "em_atividade", "matriculas", "docentes", "lat",
                    "lon", "internet", "biblioteca", "lab_informatica", "quadra", "agua_potavel", "esgoto", "rampas",
                    "ideb_ai", "ideb_ai_ano", "ideb_af", "ideb_af_ano", "paebes_5_lp", "paebes_5_mt", "paebes_ano", "q"]
COLUNAS_DINHEIRO = ["co_entidade", "ano", "canal", "po", "po_nome", "detalhe", "valor", "q"]
CANAIS = {"pdde": "PDDE — FNDE direto à unidade executora da escola (CGU)",
          "repasse_municipal": "Repasse do município ao conselho escolar (empenhos, TCE-ES)",
          "obra": "Contrato de obra no prédio da escola (contratações, TCE-ES)"}

# ------------------------------------------------------------ Censo (fonte)


def extrair_censo(*, atualizar: str = "nao") -> tuple[dict[str, pd.DataFrame], Consulta | None, str | None]:
    """Retrato do Censo (escolas, IDEB, PAEBES) — do banco, ou do cache se o banco não estiver acessível.

    Devolve (tabelas, consulta, aviso). Sem banco e sem cache: tabelas vazias e aviso.
    """
    meta = PASTA_CACHE / "censo_escolas.json"
    arquivos = {k: PASTA_CACHE / f"{k}.csv.gz" for k in SQL}
    usar_cache = atualizar in {"nao", "offline", "vazios"} and meta.exists() and all(a.exists() for a in arquivos.values())
    aviso = None
    if not usar_cache:
        if atualizar == "offline":
            return {k: pd.DataFrame() for k in SQL}, None, "Censo não coletado (modo offline, sem retrato em cache)"
        try:
            from educacao.config.database import get_connection  # o banco do NEDUC; opcional para o painel
            with get_connection() as conn:
                tabelas = {k: pd.read_sql_query(q, conn) for k, q in SQL.items()}
        except Exception as exc:  # noqa: BLE001 — banco indisponível não derruba o painel
            if meta.exists():
                aviso = f"banco do Censo indisponível ({type(exc).__name__}); usado o retrato em cache"
                usar_cache = True
            else:
                return {k: pd.DataFrame() for k in SQL}, None, f"banco do Censo indisponível e sem retrato em cache: {exc}"
        else:
            PASTA_CACHE.mkdir(parents=True, exist_ok=True)
            for k, df in tabelas.items():
                df.to_csv(arquivos[k], index=False, encoding="utf-8", compression={"method": "gzip", "mtime": 0})
            meta.write_text(json.dumps({"obtido_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                        "banco": URL_BANCO, "consultas": {k: " ".join(q.split()) for k, q in SQL.items()},
                                        "linhas": {k: len(v) for k, v in tabelas.items()}}, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    if usar_cache:
        tabelas = {k: pd.read_csv(a, dtype={"co_entidade": "int64"} if k != "matriculas_etapa" else None)
                   for k, a in arquivos.items()}
    d = json.loads(meta.read_text(encoding="utf-8"))
    consulta = Consulta(fonte="Censo", recurso="educacao_dw", metodo="SQL (PostgreSQL local do NEDUC)",
                        descricao="Censo Escolar (INEP) carregado no NEDUC: dw.dim_escola, dw.fato_escola_ano, "
                                  "stg.v_ideb_censo, stg.v_paebes_escola e stg.escola × stg.matricula (matrículas por etapa)",
                        url=URL_BANCO + "#dw.dim_escola", obtido_em=d["obtido_em"], arquivo=caminho_relativo(meta))
    return tabelas, consulta, aviso


def cadastro_escolas(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Uma linha por escola pública (municipal ou estadual) ativa desde 2021, com IDEB e PAEBES mais recentes."""
    e = t["escolas"]
    if e.empty:
        return pd.DataFrame(columns=COLUNAS_CADASTRO)
    d = pd.DataFrame({
        "co_entidade": e["co_entidade"].astype("int64"), "nome": e["no_entidade"].str.strip(),
        "cod_ibge": pd.to_numeric(e["co_municipio"], errors="coerce").astype("Int64"),
        "rede": e["tp_dependencia"].map(REDE), "ano_censo": e["ano_censo"],
        "em_atividade": e["tp_situacao_funcionamento"] == 1, "matriculas": e["qt_mat_bas"], "docentes": e["qt_doc_bas"],
        "lat": pd.to_numeric(e["latitude"], errors="coerce"), "lon": pd.to_numeric(e["longitude"], errors="coerce"),
        "internet": e["in_internet"], "biblioteca": e["in_biblioteca"], "lab_informatica": e["in_laboratorio_informatica"],
        "quadra": e["in_quadra_esportes"], "agua_potavel": e["in_agua_potavel"], "esgoto": e["in_esgoto_rede_publica"],
        "rampas": e["in_acessibilidade_rampas"],
    })
    i = t["ideb"]
    if not i.empty:
        ult = i.sort_values("ano").groupby(["co_entidade", "etapa"]).tail(1)
        for etapa, sufixo in (("anos_iniciais", "ai"), ("anos_finais", "af")):
            x = ult[ult["etapa"] == etapa].set_index("co_entidade")
            d[f"ideb_{sufixo}"] = d["co_entidade"].map(x["ideb_observado"])
            d[f"ideb_{sufixo}_ano"] = d["co_entidade"].map(x["ano"]).astype("Int64")
    p = t["paebes"]
    if not p.empty:
        p5 = p[p["etapa"].map(norm).str.contains("5. ano|5o ano|5 ano", regex=True)]
        for disc, col in (("portuguesa", "paebes_5_lp"), ("matematica", "paebes_5_mt")):
            x = p5[p5["disciplina"].map(norm).str.contains(disc)].sort_values("ano").groupby("co_entidade").tail(1)
            d[col] = d["co_entidade"].map(x.set_index("co_entidade")["proficiencia_media"])
        d["paebes_ano"] = d["co_entidade"].map(p5.groupby("co_entidade")["ano"].max()).astype("Int64")
    return d.reindex(columns=COLUNAS_CADASTRO)


# ------------------------------------------------------------ casamento de nomes

#: Termos estruturais que não distinguem uma escola de outra (tipo, rede, entidade).
_ESTRUTURAIS = set("""
conselho escola escolar escolas caixa associacao comunidade pais mestres apoio unidade executora executor da de do das dos e
a o em municipal estadual ensino fundamental medio infantil educacao educacional centro pre primeiro grau 1o 1 2 i ii
pluridocente unidocente multisseriada integral tempo emef emei emeief emeef emieef eeef eeefm eeem eefm eefmti ceefmti cmei
cei ceim umei epg eppg epm aec cce ce apm cm cmeb emeb eeeef escolinha creche colegio polo nucleo rural unificada
reforma ampliacao construcao obra obras localizada localizado rua avenida av bairro sn s n no na
munic educ infan esc fund ens basica basico educao assoc
prof profa professor professora dr dra pe padre sr sra
jovens adultos eja parcial
""".split())
#: Tipo da escola no nome: desempata homônimas ("EMEF Córrego Dumer" × "CMEI Córrego Dumer").
_TIPOS = {"emef": "ef", "eeef": "ef", "emeief": "ief", "emeef": "ief", "emieef": "ief", "cmei": "ei", "ceim": "ei",
          "cei": "ei", "umei": "ei", "cemei": "ei", "emei": "ei", "creche": "ei", "eeefm": "efm", "eeem": "em", "eefm": "efm"}


COLUNAS_MATRICULAS_ETAPA = ["cod_ibge", "ano", "mat_total", "mat_fund", "mat_med", "q"]


def matriculas_por_etapa(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Município × ano do censo: matrículas da rede municipal no total, no ensino fundamental e no médio.

    Só estas duas etapas têm subfunção própria no ranking (12.361 e 12.362); as demais
    subfunções continuam divididas pelo total. Zero é zero de verdade (a rede municipal
    quase não tem ensino médio); ausência de linha é censo não carregado.
    """
    m = t.get("matriculas_etapa", pd.DataFrame())
    if m is None or m.empty:
        return pd.DataFrame(columns=COLUNAS_MATRICULAS_ETAPA)
    d = pd.DataFrame({
        "cod_ibge": pd.to_numeric(m["co_municipio"], errors="coerce").astype("Int64"),
        "ano": pd.to_numeric(m["ano"], errors="coerce").astype("Int64"),
        "mat_total": pd.to_numeric(m["qt_mat_bas"], errors="coerce"),
        "mat_fund": pd.to_numeric(m["qt_mat_fund"], errors="coerce"),
        "mat_med": pd.to_numeric(m["qt_mat_med"], errors="coerce"),
    }).dropna(subset=["cod_ibge", "ano"])
    return d.groupby(["cod_ibge", "ano"], as_index=False)[["mat_total", "mat_fund", "mat_med"]].sum(min_count=1) \
        .sort_values(["cod_ibge", "ano"]).reset_index(drop=True)


def tipo_pelo_nome(nome: Any) -> str | None:
    for t in re.split(r"[^a-z0-9]+", norm(nome)):
        if t in _TIPOS:
            return _TIPOS[t]
        if t.startswith(("emeief", "emef", "cmei", "eeefm")):  # EMEIEFTI, EMEFTI, …
            return _TIPOS[next(k for k in ("emeief", "emef", "cmei", "eeefm") if t.startswith(k))]
    n = norm(nome)
    if "educacao infantil" in n and "fundamental" in n:
        return "ief"
    if "educacao infantil" in n or "educ infan" in n:
        return "ei"
    return None
_TIPO_MUNICIPAL = re.compile(r"\b(emef|emei|emeief|emeef|emieef|cmei|umei|epg|eppg|epm|cmeb|emeb|municipal)\b")
_TIPO_ESTADUAL = re.compile(r"\b(eeef|eeefm|eeem|eefm|eefmti|ceefmti|eeeef|estadual)\b")


def termos(nome: Any) -> list[str]:
    """Termos distintivos de um nome de escola (sem os estruturais), na ordem."""
    sem_apostrofo = re.sub(r"['´`’]", "", norm(nome))          # D'ALMEIDA = DALMEIDA (como o Censo escreve)
    return [t for t in re.split(r"[^a-z0-9]+", sem_apostrofo) if t and t not in _ESTRUTURAIS and len(t) > 1]


def _parecido(t: str, alvo: set[str]) -> bool:
    """Grafia vizinha de um termo longo (KUBITSCHECK × KUBITSCHEK). Só termos de 8+ letras e
    semelhança ≥ 0,9, para não confundir nomes próximos (JOAQUIM × JOAQUINA ficam de fora)."""
    return len(t) >= 8 and any(len(a) >= 8 and SequenceMatcher(None, t, a).ratio() >= 0.9 for a in alvo)


def rede_pelo_nome(nome: Any) -> str | None:
    n = norm(nome)
    if _TIPO_ESTADUAL.search(n):
        return "estadual"
    if _TIPO_MUNICIPAL.search(n):
        return "municipal"
    return None


def _pontuar(origem: list[str], alvo: set[str]) -> float:
    """Fração dos termos da origem achados no alvo. O último termo pode estar
    truncado (nomes cortados em 60 caracteres na CGU): vale prefixo."""
    if not origem:
        return 0.0
    achados = 0.0
    for i, t in enumerate(origem):
        if t in alvo:
            achados += 1
        elif i == len(origem) - 1 and len(t) >= 3 and any(a.startswith(t) for a in alvo):
            achados += 1
        elif _parecido(t, alvo):
            achados += 1
    return achados / len(origem)


@dataclass
class Casador:
    """Casa um nome de origem com a escola do Censo, no mesmo município."""

    escolas: pd.DataFrame
    _por_mun: dict[int, list[tuple[int, str, set[str], str]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for r in self.escolas.itertuples(index=False):
            if pd.isna(r.cod_ibge):
                continue
            item = (int(r.co_entidade), r.nome, set(termos(r.nome)), r.rede, tipo_pelo_nome(r.nome))
            self._por_mun.setdefault(int(r.cod_ibge), []).append(item)
            if r.rede == "estadual":
                self._por_mun.setdefault(0, []).append(item)  # rede estadual inteira, para UEx sem município

    def casar(self, nome: str, cod_ibge: Any) -> tuple[int | None, float, str]:
        """(co_entidade ou None, pontuação, método).

        Pontuação principal: fração dos termos da origem achados no nome do Censo.
        Desempate entre homônimas: fração inversa (termos do Censo achados na
        origem) e o tipo da escola (EMEF, CMEI…) quando os dois nomes o trazem.
        Sem município (escola estadual no arquivo da CGU): procura na rede
        estadual do ES inteira, com exigência maior.
        """
        origem = termos(nome)
        if not origem or max(len(t) for t in origem) < 4:
            return None, 0.0, "nome sem termo distintivo"
        rede = rede_pelo_nome(nome)
        estadual_sem_municipio = pd.isna(cod_ibge)
        if estadual_sem_municipio and rede == "municipal":
            return None, 0.0, "sem município"
        grupo = 0 if estadual_sem_municipio else int(cod_ibge)
        candidatos = [c for c in self._por_mun.get(grupo, []) if rede is None or c[3] == rede]
        tipo = tipo_pelo_nome(nome)
        conjunto = set(origem)
        notas = []
        for co, nome_c, termos_c, _, tipo_c in candidatos:
            direta = _pontuar(origem, termos_c)
            inversa = len(termos_c & conjunto) / len(termos_c) if termos_c else 0.0
            bonus = 0.2 if tipo and tipo_c and tipo == tipo_c else (-0.2 if tipo and tipo_c else 0.0)
            notas.append((direta + 0.3 * inversa + bonus, direta, co))
        if not notas:
            return None, 0.0, "sem escola do Censo no município"
        notas.sort(reverse=True)
        melhor, segundo = notas[0], (notas[1][0] if len(notas) > 1 else -1.0)
        limiar, folga = (0.99, 0.3) if estadual_sem_municipio else (LIMIAR, 0.15)
        if melhor[1] >= limiar and melhor[0] - segundo >= folga:
            return melhor[2], round(melhor[1], 3), "nome" + (" (rede estadual do ES)" if estadual_sem_municipio else "")
        return None, round(melhor[1], 3), "ambíguo ou abaixo do limiar"


def _distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def casar_bem(bem: dict[str, Any], cod_ibge: int, casador: Casador, escolas: pd.DataFrame) -> tuple[int | None, float, str]:
    """Bem vinculador de obra → escola: pelo nome e, havendo coordenadas, pela distância."""
    co, nota, metodo = casador.casar(bem.get("nome", ""), cod_ibge)
    lat, lon = bem.get("lat"), bem.get("lon")
    if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
        return co, nota, metodo
    mun = escolas[(escolas["cod_ibge"] == cod_ibge) & escolas["lat"].notna()]
    if mun.empty:
        return co, nota, metodo
    dist = mun.apply(lambda r: _distancia_m(lat, lon, r["lat"], r["lon"]), axis=1)
    perto = mun.assign(d=dist).sort_values("d").iloc[0]
    if co is not None:
        d_co = dist[mun["co_entidade"] == co]
        return co, nota, "nome" + (f" (a {d_co.iloc[0]:.0f} m)" if len(d_co) else "")
    origem = termos(bem.get("nome", ""))
    if perto["d"] <= RAIO_OBRA_M and _pontuar(origem, set(termos(perto["nome"]))) >= 0.5:
        return int(perto["co_entidade"]), 0.5, f"proximidade ({perto['d']:.0f} m) e nome parcial"
    return None, nota, metodo


# ------------------------------------------------------------------ composição

@dataclass
class ResultadoEscolas:
    escolas: pd.DataFrame                 # cadastro do Censo (só as públicas ativas desde 2021)
    vinculos: pd.DataFrame                # fonte × identificador de origem → co_entidade (com método e nota)
    dinheiro: pd.DataFrame                # escola × ano × canal (pdde por PO, repasse municipal, obra)
    consultas: Registro
    avisos: list[str]
    status: dict[str, Any]
    q_censo: str | None = None
    matriculas_etapa: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=COLUNAS_MATRICULAS_ETAPA))  # município × ano


def compor(pdde: pd.DataFrame, conselhos: pd.DataFrame, obras: pd.DataFrame, *, atualizar: str = "nao") -> ResultadoEscolas:
    reg = Registro()
    avisos: list[str] = []
    tabelas, consulta, aviso = extrair_censo(atualizar=atualizar)
    if aviso:
        avisos.append(aviso)
    q = reg.adicionar(consulta) if consulta else None
    escolas = cadastro_escolas(tabelas).assign(q=q)
    matriculas_etapa = matriculas_por_etapa(tabelas).assign(q=q)[COLUNAS_MATRICULAS_ETAPA]
    vinc: list[dict[str, Any]] = []
    dinheiro: list[pd.DataFrame] = []
    if not escolas.empty:
        casador = Casador(escolas)
        # 1) PDDE: uma unidade executora pode receber em vários anos e POs — casa uma vez.
        if not pdde.empty:
            p = pdde[pdde["destino"] == "escolas"]
            uex = p.drop_duplicates("cnpj_uex")[["cnpj_uex", "uex", "cod_ibge"]]
            for r in uex.itertuples(index=False):
                co, nota, met = casador.casar(r.uex, r.cod_ibge)
                vinc.append({"fonte": "pdde", "origem": r.cnpj_uex, "nome_origem": r.uex,
                             "cod_ibge": None if pd.isna(r.cod_ibge) else int(r.cod_ibge),
                             "co_entidade": co, "nota": nota, "metodo": met})
        # 2) Repasse municipal a conselho escolar (credor dos empenhos).
        if not conselhos.empty:
            for r in conselhos.drop_duplicates(["cod_ibge", "credor"]).itertuples(index=False):
                co, nota, met = casador.casar(r.credor_nome, r.cod_ibge)
                vinc.append({"fonte": "conselho", "origem": f"{r.cod_ibge}|{r.credor}", "nome_origem": r.credor_nome,
                             "cod_ibge": int(r.cod_ibge), "co_entidade": co, "nota": nota, "metodo": met})
        # 3) Obras com bem vinculador.
        if not obras.empty and "bens" in obras:
            for r in obras[obras["bens"].notna()].itertuples(index=False):
                for i, bem in enumerate(json.loads(r.bens)):
                    if "educacion" not in norm(bem.get("categoria")) and not termos(bem.get("nome")):
                        continue
                    co, nota, met = casar_bem(bem, int(r.cod_ibge), casador, escolas)
                    vinc.append({"fonte": "obra", "origem": f"{r.chave}#{i}", "nome_origem": bem.get("nome"),
                                 "cod_ibge": int(r.cod_ibge), "co_entidade": co, "nota": nota, "metodo": met})
    vinculos = pd.DataFrame(vinc, columns=["fonte", "origem", "nome_origem", "cod_ibge", "co_entidade", "nota", "metodo"])
    vinculos["co_entidade"] = vinculos["co_entidade"].astype("Int64")

    if not vinculos.empty:
        v = vinculos.dropna(subset=["co_entidade"])
        vp = v[v["fonte"] == "pdde"].set_index("origem")["co_entidade"]
        if not pdde.empty:
            x = pdde[pdde["destino"] == "escolas"].assign(co_entidade=lambda d: d["cnpj_uex"].map(vp)).dropna(subset=["co_entidade"])
            dinheiro.append(x.groupby(["co_entidade", "ano", "po", "po_nome"], as_index=False)
                            .agg(valor=("valor", "sum"), q=("q", lambda s: juntar_ids(*s)))
                            .assign(canal="pdde", detalhe=None))
        vc = v[v["fonte"] == "conselho"].set_index("origem")["co_entidade"]
        if not conselhos.empty:
            x = conselhos.assign(co_entidade=(conselhos["cod_ibge"].astype(str) + "|" + conselhos["credor"]).map(vc)) \
                .dropna(subset=["co_entidade"])
            dinheiro.append(x.groupby(["co_entidade", "ano"], as_index=False)
                            .agg(valor=("empenhada", "sum"), q=("q", lambda s: juntar_ids(*s)), detalhe=("credor_nome", "first"))
                            .assign(canal="repasse_municipal", po=None, po_nome=None))
        vo = v[v["fonte"] == "obra"].assign(chave=lambda d: d["origem"].str.split("#").str[0])
        if not obras.empty and not vo.empty:
            x = obras.merge(vo[["chave", "co_entidade"]].drop_duplicates(), on="chave")
            x["ano"] = pd.to_numeric(x["assinatura"].str[:4], errors="coerce").astype("Int64")
            dinheiro.append(x.groupby(["co_entidade", "ano"], as_index=False, dropna=False)
                            .agg(valor=("valor", "sum"), q=("q", lambda s: juntar_ids(*s)), detalhe=("chave", lambda s: ";".join(s)))
                            .assign(canal="obra", po=None, po_nome=None))
    dinheiro_df = pd.concat(dinheiro, ignore_index=True)[COLUNAS_DINHEIRO] if dinheiro else pd.DataFrame(columns=COLUNAS_DINHEIRO)
    taxa = {f: {"total": int((vinculos["fonte"] == f).sum()),
                "casados": int(((vinculos["fonte"] == f) & vinculos["co_entidade"].notna()).sum())}
            for f in ("pdde", "conselho", "obra")}
    status = {"fonte": "Censo", "ok": not escolas.empty, "escolas": len(escolas), "vinculos": taxa, "avisos": len(avisos),
              "matriculas_etapa": len(matriculas_etapa), "extraido_em": reg.extraido_em("Censo")}
    return ResultadoEscolas(escolas, vinculos, dinheiro_df, reg, avisos, status, q, matriculas_etapa)
