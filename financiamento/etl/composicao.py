"""Composição do painel de auditoria: origem da receita, conformidade, conciliação e
o dataset consolidado com proveniência por registro.

Tudo aqui é função pura sobre tabelas já extraídas — nenhuma chamada de rede.
Regras que valem em todo o módulo:

* ausência vira `None`/vazio, nunca zero; o que não fecha é RELATADO, não escondido;
* todo valor carrega os ids das consultas de onde saiu (`q…`), e o consolidado
  desdobra cada id em endpoint, parâmetros, instante e arquivo do cache;
* o índice legal de MDE vem do SIOPE (PDF); o registro manual só preenche lacuna,
  e divergência entre os dois é apontada.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlsplit

import pandas as pd

from . import fnde as mod_fnde
from . import msc as mod_msc
from .config import COD_ESTADO_ES
from .entregas import resumo_por_municipio
from .indicadores import INDICADORES, ORIGENS, negativo_permitido
from .parsing import norm
from .proveniencia import Registro, juntar_ids
from .siope import MINIMO_FUNDEB_PROFISSIONAIS_PCT, MINIMO_MDE_PCT

TOLERANCIA_CENTAVOS = 1.00          # R$ — duas fontes "batem" dentro disto
DIVERGENCIA_RELEVANTE_PCT = 5.0     # função 12 × SIOPE acima disto é destacada no painel

PROGRAMAS_FEDERAIS_ESPECIFICOS = ("salario_educacao", "pnae", "pnate", "pdde")
#: Situação de obra (normalizada) que conta como parada: declarada pelo município ou presumida pelo TCE-ES.
PARALISADA = "paralisa|interrompida"


def _num(v: Any) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------ receita por origem

def receita_origem(receita_bim: pd.DataFrame, tabela_msc: pd.DataFrame, repasses: pd.DataFrame,
                   anual: pd.DataFrame, municipios: Iterable[int], anos: Iterable[int]) -> pd.DataFrame:
    """A tabela "origem da receita" da Fase 1: município × exercício × categoria.

    Categorias mutuamente exclusivas (ver `indicadores.ORIGENS`): impostos
    próprios (Anexo 01), FUNDEB (MSC; na falta dela, DCA I-C — e a fonte usada
    fica registrada), transferências federais específicas (FNDE/CGU, só o que foi
    pago ao próprio município) e "outras", por diferença. Se um componente falta,
    "outras" fica vazia: não se calcula resto com parcela desconhecida.
    """
    b6 = receita_bim[receita_bim["bimestre"] == 6].set_index(["cod_ibge", "ano"])
    msc_i = tabela_msc.set_index(["cod_ibge", "ano"]) if not tabela_msc.empty else pd.DataFrame()
    anual_i = anual.set_index(["cod_ibge", "ano"])
    rep = repasses[(repasses["destino"] == "municipio") & repasses["programa"].isin(PROGRAMAS_FEDERAIS_ESPECIFICOS)] \
        if not repasses.empty else repasses
    rep_i = rep.groupby(["cod_ibge", "ano"]).agg(valor=("valor", "sum"), q=("q", lambda s: juntar_ids(*s))) \
        if not rep.empty else pd.DataFrame()

    linhas: list[dict[str, Any]] = []
    for ano in anos:
        for cod in municipios:
            k = (cod, ano)
            r6 = b6.loc[k] if k in b6.index else None
            total = _num(r6["receita_total"]) if r6 is not None else None
            q_a01 = r6["q"] if r6 is not None else None
            partes: dict[str, tuple[float | None, str | None, str]] = {
                "impostos_proprios": (_num(r6["impostos"]) if r6 is not None else None, q_a01, "SICONFI — RREO Anexo 01"),
            }
            fundeb, q_f, fonte_f = None, None, "SICONFI — MSC"
            if k in msc_i.index and _num(msc_i.loc[k, "fundeb_msc_total"]) is not None:
                fundeb, q_f = _num(msc_i.loc[k, "fundeb_msc_total"]), msc_i.loc[k, "q_msc"]
            elif k in anual_i.index and _num(anual_i.loc[k, "fundeb_receita"]) is not None:
                fundeb, q_f, fonte_f = _num(anual_i.loc[k, "fundeb_receita"]), anual_i.loc[k, "q_dca_ic"], "SICONFI — DCA I-C (sem MSC)"
            partes["fundeb"] = (fundeb, q_f, fonte_f)
            if k in rep_i.index:
                partes["federal_especifica"] = (round(float(rep_i.loc[k, "valor"]), 2), rep_i.loc[k, "q"], "FNDE — CGU")
            else:
                partes["federal_especifica"] = (None, None, "FNDE — CGU")
            conhecidas = [v for v, _, _ in partes.values()]
            outras = None if total is None or any(v is None for v in conhecidas) else round(total - sum(conhecidas), 2)
            q_todas = juntar_ids(q_a01, *(q for _, q, _ in partes.values()))
            for cat, (valor, q, fonte) in partes.items():
                linhas.append({"cod_ibge": cod, "ano": ano, "categoria": cat, "valor": valor, "fonte": fonte, "q": q})
            linhas.append({"cod_ibge": cod, "ano": ano, "categoria": "outras", "valor": outras,
                           "fonte": "calculado por diferença", "q": q_todas})
            linhas.append({"cod_ibge": cod, "ano": ano, "categoria": "total", "valor": total,
                           "fonte": "SICONFI — RREO Anexo 01", "q": q_a01})
    return pd.DataFrame(linhas, columns=["cod_ibge", "ano", "categoria", "valor", "fonte", "q"])


# ------------------------------------------------------------------ conformidade

def aplicar_siope(anual: pd.DataFrame, siope: pd.DataFrame) -> pd.DataFrame:
    """Leva os indicadores legais do SIOPE para a linha ente × exercício.

    MDE: SIOPE primeiro; registro manual só onde o SIOPE não tem. Os dois
    presentes e diferentes (> 0,01 p.p.) = `mde_divergente_manual`.
    """
    cols = ["cod_ibge", "ano", "status_siope", "q", "mde_pct", "mde_exigido", "mde_aplicado", "despesa_mde_limite",
            "fundeb70_pct", "fundeb70_exigido", "fundeb70_considerado", "receita_resultante_impostos",
            "receita_impostos_proprios", "destinado_fundeb", "fundeb_recebido", "fundeb_principal",
            "mde_compensacao_ec119", "despesa_total_educacao",
            "salario_educacao", "pdde", "pnae", "pnate", "pdf_gerado_em", "pdf_publicado_em", "itens_usados"]
    s = siope.reindex(columns=cols).rename(columns={
        "q": "q_siope", "mde_pct": "siope_mde_pct", "fundeb_recebido": "siope_fundeb_recebido",
        "salario_educacao": "siope_salario_educacao", "pdde": "siope_pdde", "pnae": "siope_pnae", "pnate": "siope_pnate",
        "itens_usados": "siope_itens"})
    a = anual.drop(columns=[c for c in s.columns if c in anual.columns and c not in ("cod_ibge", "ano")]).merge(
        s, on=["cod_ibge", "ano"], how="left")
    manual = a["mde_aplicado_pct"].copy()
    tem_siope = a["siope_mde_pct"].notna()
    a["mde_divergente_manual"] = tem_siope & manual.notna() & ((a["siope_mde_pct"] - manual).abs() > 0.01)
    a["mde_aplicado_pct"] = a["siope_mde_pct"].where(tem_siope, manual)
    a["mde_situacao"] = pd.Series("sem_dado", index=a.index).mask(manual.notna(), "informado_manual").mask(tem_siope, "siope")
    a["mde_fonte"] = a["mde_fonte"].where(~tem_siope, "SIOPE — RREO Anexo 8 (PDF no FTP do FNDE)")
    a["mde_verificado_em"] = a["mde_verificado_em"].where(~tem_siope, a["pdf_publicado_em"].astype("string").str[:10])
    a["mde_abaixo_minimo"] = a["mde_aplicado_pct"].map(lambda v: None if pd.isna(v) else bool(v < MINIMO_MDE_PCT)).astype(object)
    a["fundeb70_abaixo_minimo"] = a["fundeb70_pct"].map(
        lambda v: None if pd.isna(v) else bool(v < MINIMO_FUNDEB_PROFISSIONAIS_PCT)).astype(object)
    # Conciliação da Fase 2 × SIOPE: a mesma despesa, declarada duas vezes.
    base = a["desp_educacao_empenhada"].where(lambda x: x > 0)
    a["divergencia_funcao12_siope_pct"] = (100 * (a["desp_educacao_empenhada"] - a["despesa_total_educacao"]) / base).round(4)
    a["divergencia_funcao12_siope_rs"] = (a["desp_educacao_empenhada"] - a["despesa_total_educacao"]).round(2)
    return a


def aplicar_msc(anual: pd.DataFrame, tabela_msc: pd.DataFrame) -> pd.DataFrame:
    cols = ["cod_ibge", "ano", "status_msc", "fontes_msc", "q_msc", "msc_empenhada", "fundeb_msc_total",
            "fundeb_msc_fundo", "fundeb_msc_complementacao", "fundeb_msc_por_fonte", "receita_fnde_msc"]
    a = anual.merge(tabela_msc.reindex(columns=cols), on=["cod_ibge", "ano"], how="left")
    a["msc_confere_dca"] = [None if pd.isna(m) or pd.isna(d) else bool(abs(m - d) <= TOLERANCIA_CENTAVOS)
                            for m, d in zip(a["msc_empenhada"], a["desp_educacao_empenhada"])]
    return a


def aplicar_tcees(anual: pd.DataFrame, mde: pd.DataFrame, pcm_resumo: pd.DataFrame, obras: pd.DataFrame,
                  q: Mapping[str, Any], emp_total: pd.DataFrame | None = None) -> pd.DataFrame:
    """Leva ao ente × exercício o MDE apurado pelo TCE-ES, os prazos das remessas e o resumo das obras.

    `mde_cruza_minimo`: um índice abaixo de 25% e o outro não — o sinal mais forte
    da comparação entre as duas apurações.
    """
    a = anual.merge(mde.drop(columns=["q_tcees_mde"], errors="ignore"), on=["cod_ibge", "ano"], how="left")         if not mde.empty else anual.copy()
    for c in ("tcees_mde_pct", "tcees_mde_aplicado", "tcees_alunos", "tcees_mde_por_aluno", "tcees_receita_fundeb",
              "tcees_mes_ultimo_envio", "siope_mde_pct"):
        a[c] = pd.to_numeric(a[c], errors="coerce") if c in a else float("nan")
    a["q_tcees_mde"] = q.get("educacao") if not mde.empty else None
    a.loc[a["tcees_mde_pct"].isna(), "q_tcees_mde"] = None
    # Soma dos empenhos da função 12 (sem intra), para conferir contra o DCA I-E.
    if emp_total is not None and not emp_total.empty:
        emp = emp_total.reindex(columns=["cod_ibge", "ano", "tcees_emp_empenhada", "tcees_emp_paga", "tcees_emp_meses",
                                         "tcees_emp_meses_ausentes"]).copy()
        emp["q_tcees_emp"] = emp["ano"].map(lambda ano: juntar_ids(*(q.get("empenhos", {}).get(ano) or [])))
        a = a.merge(emp, on=["cod_ibge", "ano"], how="left")
    else:
        a = a.assign(tcees_emp_empenhada=pd.NA, tcees_emp_paga=pd.NA, tcees_emp_meses=pd.NA, tcees_emp_meses_ausentes=None,
                     q_tcees_emp=None)
    # Despesa por MATRÍCULA. O denominador é "Alunos" do próprio recurso "Educação" do
    # TCE-ES — o número de matrículas da rede MUNICIPAL que o Tribunal usa na aplicação
    # por aluno. Conferido contra o Censo (`conferencia_matriculas`): bateu nos 78
    # municípios em 2025. É um denominador melhor que a população para comparar
    # municípios, porque muda todo ano e mede quem a rede de fato atende.
    a["desp_educacao_por_matricula"] = (
        a["desp_educacao_empenhada"] / a["tcees_alunos"].where(lambda s: s > 0)
    ).round(2)
    a["div_mde_tcees_siope_pp"] = (a["tcees_mde_pct"] - a["siope_mde_pct"]).round(2)
    a["mde_cruza_minimo"] = [None if pd.isna(t) or pd.isna(s) else bool((t < MINIMO_MDE_PCT) != (s < MINIMO_MDE_PCT))
                             for t, s in zip(a["tcees_mde_pct"], a["siope_mde_pct"])]
    a["tcees_mde_abaixo_minimo"] = a["tcees_mde_pct"].map(lambda v: None if pd.isna(v) else bool(v < MINIMO_MDE_PCT)).astype(object)
    if not pcm_resumo.empty:
        a = a.merge(pcm_resumo, on=["cod_ibge", "ano"], how="left")
        a["q_pcm"] = a["pcm_remessas"].map(lambda n: None if pd.isna(n) else q.get("pcm"))
    else:
        for c in ("pcm_remessas", "pcm_com_atraso", "pcm_nao_homologadas", "pcm_maior_atraso_dias", "pcm_ugs",
                  "pcm_ugs_sem_remessa", "q_pcm"):
            a[c] = pd.NA
    if not obras.empty:
        o = obras.groupby("cod_ibge").agg(
            obras_educacao=("chave", "size"), obras_valor=("valor", "sum"),
            obras_paralisadas=("situacao", lambda s: int(s.map(norm).str.contains(PARALISADA).sum())),
            obras_nao_iniciadas=("situacao", lambda s: int(s.map(norm).str.contains("nao iniciada").sum())),
            obras_concluidas=("situacao", lambda s: int(s.map(norm).str.contains("concluida").sum())))
        a = a.merge(o, on="cod_ibge", how="left")  # retrato atual: igual em todos os exercícios
    else:
        for c in ("obras_educacao", "obras_valor", "obras_paralisadas", "obras_nao_iniciadas", "obras_concluidas"):
            a[c] = pd.NA
    return a


#: Subfunção → (coluna do `anual` com as matrículas da etapa, nome da etapa). Só o ensino
#: fundamental e o médio têm denominador próprio no "R$ por matrícula" de uma subfunção;
#: as demais continuam divididas pelo total da rede municipal (coluna "Alunos" do TCE-ES).
ETAPA_DA_SUBFUNCAO = {"12.361": ("censo_mat_fund", "ensino fundamental"), "12.362": ("censo_mat_med", "ensino médio")}
COLUNAS_MATRICULAS_ETAPA = ("censo_mat_total", "censo_mat_fund", "censo_mat_med", "q_censo_mat")


def aplicar_matriculas_etapa(anual: pd.DataFrame, matriculas: pd.DataFrame) -> pd.DataFrame:
    """Leva ao ente × exercício as matrículas da rede municipal por etapa (Censo do mesmo ano).

    Ano do censo = exercício, como no denominador do TCE-ES. Linha ausente fica NaN
    (censo não carregado), que o painel mostra como "sem dado"; zero é zero de verdade.
    """
    if matriculas is None or matriculas.empty:
        return anual.assign(censo_mat_total=float("nan"), censo_mat_fund=float("nan"), censo_mat_med=float("nan"),
                            q_censo_mat=None)
    m = matriculas.rename(columns={"mat_total": "censo_mat_total", "mat_fund": "censo_mat_fund", "mat_med": "censo_mat_med",
                                   "q": "q_censo_mat"})
    m = m.reindex(columns=["cod_ibge", "ano", *COLUNAS_MATRICULAS_ETAPA]).astype({"cod_ibge": "int64", "ano": "int64"})
    a = anual.merge(m, on=["cod_ibge", "ano"], how="left")
    for c in COLUNAS_MATRICULAS_ETAPA[:-1]:
        a[c] = pd.to_numeric(a[c], errors="coerce")
    a["q_censo_mat"] = pd.Series([None if pd.isna(t) or pd.isna(q) else q for t, q in zip(a["censo_mat_total"], a["q_censo_mat"])],
                                 index=a.index, dtype=object)
    return a


def _consolidar_matriculas_etapa(c: Consolidador, anual: pd.DataFrame, subfuncoes: pd.DataFrame) -> None:
    """As matrículas por etapa e o R$ por matrícula da etapa das subfunções 12.361 e 12.362."""
    if "censo_mat_total" not in anual or subfuncoes.empty:
        return
    sub = subfuncoes[subfuncoes["codigo"].isin(ETAPA_DA_SUBFUNCAO)].set_index(["cod_ibge", "ano", "codigo"])
    for r in anual[(anual["esfera"] == "M") & anual["censo_mat_total"].notna()].itertuples(index=False):
        for codigo, (coluna, etapa) in ETAPA_DA_SUBFUNCAO.items():
            mats = getattr(r, coluna)
            c.add("matriculas_etapa_censo", r.cod_ibge, r.ano, mats, r.q_censo_mat, detalhe=etapa)
            chave = (r.cod_ibge, r.ano, codigo)
            if pd.isna(mats) or mats <= 0 or chave not in sub.index:
                continue
            s = sub.loc[chave]
            c.add("subfuncao_por_matricula_etapa", r.cod_ibge, r.ano, round(float(s["empenhada"]) / float(mats), 2),
                  juntar_ids(s["q"], r.q_censo_mat), detalhe=f"{codigo} - {s['nome']} ÷ matrículas do {etapa}")


def aplicar_entregas(anual: pd.DataFrame, entregas: pd.DataFrame) -> pd.DataFrame:
    r = resumo_por_municipio(entregas).rename(columns={
        "com_atraso": "entregas_com_atraso", "nao_entregues": "entregas_nao_entregues",
        "retificados": "entregas_retificadas", "maior_atraso_dias": "entregas_maior_atraso_dias",
        "irregular": "entregas_irregular", "obrigacoes": "entregas_obrigacoes", "no_prazo": "entregas_no_prazo"})
    if "q" in entregas and not entregas.empty:  # uma consulta ao extrato por município-ano
        r = r.merge(entregas.groupby(["cod_ibge", "ano"], as_index=False)["q"].first()
                    .rename(columns={"q": "q_extrato"}), on=["cod_ibge", "ano"], how="left")
    return anual.merge(r, on=["cod_ibge", "ano"], how="left")


def kpis_conformidade(anual: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Os três KPIs do topo, por exercício — já prontos para o painel e para o README."""
    saida: dict[str, dict[str, Any]] = {}
    mun = anual[anual["esfera"] == "M"]
    for ano, g in mun.groupby("ano"):
        com_mde = g[g["mde_aplicado_pct"].notna()]
        com_ent = g[g["entregas_obrigacoes"].notna()]
        div = g[g["divergencia_funcao12_siope_pct"].notna()]
        maior = div.loc[div["divergencia_funcao12_siope_pct"].abs().idxmax()] if not div.empty else None
        com70 = g[g["fundeb70_pct"].notna()]
        saida[str(ano)] = {
            "mde_abaixo": int((com_mde["mde_aplicado_pct"] < MINIMO_MDE_PCT).sum()), "mde_com_dado": len(com_mde),
            "fundeb70_abaixo": int((com70["fundeb70_pct"] < MINIMO_FUNDEB_PROFISSIONAIS_PCT).sum()),
            "fundeb70_com_dado": len(com70),
            "entregas_irregulares": int(com_ent["entregas_irregular"].fillna(False).astype(bool).sum()),
            # Gravidade: quase todo município atrasa algum relatório por poucos dias; o que
            # distingue é atraso longo e o que não foi entregue.
            "entregas_atraso_30d": int((com_ent["entregas_maior_atraso_dias"].fillna(0) > 30).sum()),
            "entregas_com_nao_entregue": int((com_ent["entregas_nao_entregues"].fillna(0) > 0).sum()),
            "entregas_com_dado": len(com_ent),
            "maior_divergencia": None if maior is None else {
                "cod_ibge": int(maior["cod_ibge"]), "ente": maior["ente"],
                "pct": float(maior["divergencia_funcao12_siope_pct"]), "rs": float(maior["divergencia_funcao12_siope_rs"])},
            "divergencia_com_dado": len(div),
            "divergencias_relevantes": int((div["divergencia_funcao12_siope_pct"].abs() > DIVERGENCIA_RELEVANTE_PCT).sum()),
            # MDE pelo TCE-ES (a outra apuração) e onde as duas discordam sobre o mínimo.
            "mde_abaixo_tcees": int((g.get("tcees_mde_pct", pd.Series(dtype=float)) < MINIMO_MDE_PCT).sum()),
            "mde_tcees_com_dado": int(g.get("tcees_mde_pct", pd.Series(dtype=float)).notna().sum()),
            "mde_cruza_minimo": int(g.get("mde_cruza_minimo", pd.Series(dtype=object)).fillna(False).astype(bool).sum()),
            "pcm_municipios_com_atraso": int(((g.get("pcm_com_atraso", pd.Series(dtype=float)).fillna(0)
                                               + g.get("pcm_nao_homologadas", pd.Series(dtype=float)).fillna(0)) > 0).sum()),
        }
    return saida


def kpis_obras(obras: pd.DataFrame) -> dict[str, Any]:
    """Retrato das obras da educação (não depende do exercício)."""
    if obras.empty:
        return {}
    s = obras["situacao"].map(norm)
    par = s.str.contains(PARALISADA)
    return {"contratos": len(obras), "municipios": int(obras["cod_ibge"].nunique()), "valor": float(obras["valor"].sum()),
            "paralisadas": int(par.sum()), "paralisadas_municipios": int(obras.loc[par, "cod_ibge"].nunique()),
            "paralisadas_valor": float(obras.loc[par, "valor"].sum()),
            # "Paralisação presumida": classificação do TCE-ES para obra sem medição recente, não declaração do município.
            "presumidas": int(s.str.contains("presumida").sum()),
            "declaradas": int(s.str.contains("paralisada|interrompida").sum()),
            "nao_iniciadas": int(s.str.contains("nao iniciada").sum()),
            "situacoes": obras["situacao"].value_counts().to_dict()}


# ---------------------------------------------------------------- consolidado

def _formatar(indicador: str, detalhe: str | None, anexos: Mapping[str, str]) -> tuple[str, str]:
    meta = INDICADORES[indicador]
    campos = {"anexo_ie": anexos.get("dca_despesa_funcao", "DCA-Anexo I-E"),
              "anexo_ic": anexos.get("dca_receita", "DCA-Anexo I-C"),
              "anexo_a02": anexos.get("rreo_despesa_funcao", "RREO-Anexo 02"), "detalhe": detalhe or ""}
    return meta["localizacao"].format(**campos), meta["calculo"]


class Consolidador:
    """Monta o dataset longo: um registro por número, com a proveniência desdobrada."""

    def __init__(self, registro: Registro, entes: Mapping[int, str], anexos_por_ano: Mapping[int, Mapping[str, str]]):
        self.registro, self.entes, self.anexos = registro, entes, anexos_por_ano
        self.linhas: list[dict[str, Any]] = []

    def add(self, indicador: str, cod: int, ano: int, valor: Any, q: Any, *, detalhe: str | None = None,
            periodo: str | None = None, fonte: str | None = None, unidade: str | None = None,
            localizacao_extra: str | None = None, observacao: str | None = None) -> None:
        """Um registro. (cod_ibge, ano, periodo, indicador, detalhe) é a CHAVE estável entre
        extrações; o que pode mudar sem mudar o número (situação, item do PDF) vai em `observacao`."""
        v = _num(valor)
        if v is None:
            return
        loc, calc = _formatar(indicador, detalhe, self.anexos.get(ano, {}))
        meta = INDICADORES[indicador]
        self.linhas.append({
            "cod_ibge": cod, "ente": self.entes.get(cod), "ano": ano, "periodo": periodo, "indicador": indicador,
            "rotulo": meta["rotulo"], "detalhe": detalhe, "valor": round(v, 4), "unidade": unidade or meta["unidade"],
            "fonte": fonte or meta["fonte"], "consultas": juntar_ids(q if isinstance(q, str) else None),
            "localizacao": loc + (f" — {localizacao_extra}" if localizacao_extra else ""), "calculo": calc,
            "observacao": observacao,
        })

    def tabela(self) -> pd.DataFrame:
        df = pd.DataFrame(self.linhas)
        if df.empty:
            return df
        cache: dict[str, dict[str, str]] = {}

        def desdobrar(ids: str) -> dict[str, str]:
            if ids in cache:
                return cache[ids]
            consultas = [self.registro[i] for i in ids.split(";") if i in self.registro]
            partes = [urlsplit(c.url) for c in consultas]
            d = {
                "fonte_consulta": " | ".join(dict.fromkeys(c.fonte for c in consultas)),
                "endpoint": " | ".join(dict.fromkeys(f"{p.scheme}://{p.netloc}{p.path}" for p in partes)),
                "parametros": " | ".join("&".join(f"{k}={v}" for k, v in parse_qsl(p.query)) or p.path.rsplit("/", 1)[-1]
                                         for p in partes),
                "obtido_em": " | ".join(c.obtido_em for c in consultas),
                "arquivo_cache": " | ".join(c.arquivo for c in consultas),
            }
            cache[ids] = d
            return d

        prov = pd.DataFrame([desdobrar(i) for i in df["consultas"].fillna("")])
        return pd.concat([df.reset_index(drop=True), prov], axis=1)


def consolidar(c: Consolidador, *, anual: pd.DataFrame, subfuncoes: pd.DataFrame, bimestral: pd.DataFrame,
               receita_bim: pd.DataFrame, origem: pd.DataFrame, fluxo: pd.DataFrame, natureza: pd.DataFrame,
               entregas: pd.DataFrame, siope: pd.DataFrame, repasses: pd.DataFrame,
               tcees: Mapping[str, Any] | None = None, cnca: Mapping[str, pd.DataFrame] | None = None,
               escolas: pd.DataFrame | None = None, dinheiro_escolas: pd.DataFrame | None = None,
               ica: Mapping[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Todos os números do painel, um por linha, com proveniência."""
    for r in anual.itertuples(index=False):
        cod, ano = r.cod_ibge, r.ano
        for ind in ("desp_educacao_empenhada", "desp_educacao_liquidada", "desp_educacao_paga", "desp_total_empenhada",
                    "populacao", "desp_educacao_per_capita", "desp_educacao_pct_total"):
            c.add(ind, cod, ano, getattr(r, ind), r.q_dca_ie)
        for ind in ("fundeb_receita", "fundeb_complementacao_uniao", "fundeb_contribuicao", "fundeb_liquido"):
            c.add(ind, cod, ano, getattr(r, ind), r.q_dca_ic)
        c.add("fundeb_pct_desp_educacao", cod, ano, r.fundeb_pct_desp_educacao, juntar_ids(r.q_dca_ie, r.q_dca_ic))
        c.add("rreo_b6_empenhada", cod, ano, r.rreo_b6_empenhada, r.q_rreo_b6)
        c.add("dif_rreo_dca_pct", cod, ano, r.dif_rreo_dca_pct, juntar_ids(r.q_rreo_b6, r.q_dca_ie))
        if getattr(r, "status_msc", None) == "ok":
            c.add("msc_educacao_empenhada", cod, ano, r.msc_empenhada, r.q_msc)
            c.add("fundeb_msc", cod, ano, r.fundeb_msc_total, r.q_msc, detalhe="fundo + complementação")
        c.add("divergencia_funcao12_siope", cod, ano, r.divergencia_funcao12_siope_pct, juntar_ids(r.q_dca_ie, r.q_siope))
        if getattr(r, "mde_situacao", None) == "siope":
            c.add("mde_pct", cod, ano, r.mde_aplicado_pct, r.q_siope, detalhe="aplicação em MDE sobre a receita de impostos",
                  observacao=_item(r.siope_itens, "mde_pct"))
        if not pd.isna(getattr(r, "fundeb70_pct", None)):
            c.add("fundeb70_pct", cod, ano, r.fundeb70_pct, r.q_siope, detalhe="mínimo de 70% do FUNDEB na remuneração",
                  observacao=_item(r.siope_itens, "fundeb70_pct"))
    for r in subfuncoes.itertuples(index=False):
        c.add("subfuncao_empenhada", r.cod_ibge, r.ano, r.empenhada, r.q, detalhe=f"{r.codigo} - {r.nome}")
    for r in bimestral.itertuples(index=False):
        c.add("empenhada_acum", r.cod_ibge, r.ano, r.empenhada_acum, r.q, detalhe=str(r.bimestre), periodo=f"{r.bimestre}º bim")
    for r in receita_bim.itertuples(index=False):
        # Exercício fechado (6º bimestre): todas as linhas; demais bimestres: só as usadas no painel.
        chaves = [k for k in ("receita_total", "impostos", "transferencias_correntes", "transferencias_capital")] \
            if r.bimestre != 6 else [k for k in receita_bim.columns if k not in ("cod_ibge", "ano", "bimestre", "tipo_rreo", "q")]
        for k in chaves:
            c.add("receita_a01", r.cod_ibge, r.ano, getattr(r, k), r.q, detalhe=_conta_a01(k), periodo=f"{r.bimestre}º bim")
    for r in origem.itertuples(index=False):
        if r.categoria == "total":
            continue
        meta = ORIGENS[r.categoria]
        c.add("origem_receita", r.cod_ibge, r.ano, r.valor, r.q, detalhe=meta["localizacao"], fonte=r.fonte,
              localizacao_extra=f"categoria: {meta['rotulo']}")
    for r in fluxo.itertuples(index=False):
        c.add("fluxo_fonte_subfuncao", r.cod_ibge, r.ano, r.empenhada, r.q,
              detalhe=f"subfuncao {r.subfuncao}, fonte {r.fonte} ({mod_msc.nome_fonte(r.fonte)})")
    for r in natureza.itertuples(index=False):
        c.add("natureza_economica", r.cod_ibge, r.ano, r.empenhada, r.q,
              detalhe=f"elemento {r.elemento} ({mod_msc.NOME_ELEMENTO.get(r.elemento, 'ver Portaria 163/2001')}) — "
                      f"{mod_msc.CATEGORIAS[r.categoria]} / {mod_msc.SUBCATEGORIAS[r.subcategoria]}")
    for r in entregas.itertuples(index=False):
        c.add("entrega_atraso_dias", r.cod_ibge, r.ano, 0 if r.situacao == "no_prazo" else r.dias_atraso, r.q,
              detalhe=f"{r.poder} · {r.relatorio} · período {r.periodo}", periodo=str(r.periodo),
              observacao=f"prazo {r.prazo} · entregue {r.data_local or '—'} · situação {r.situacao}")
    for r in siope.itertuples(index=False):
        itens = json.loads(r.itens_usados) if isinstance(r.itens_usados, str) else {}
        for campo, item in itens.items():
            if campo in ("mde_pct", "fundeb70_pct"):
                continue
            unidade = "%" if campo.endswith("_pct") else "R$"
            c.add("siope", r.cod_ibge, r.ano, getattr(r, campo, None), r.q, detalhe=campo, unidade=unidade,
                  observacao=item)
    for r in repasses.itertuples(index=False):
        c.add("repasse_fnde", r.cod_ibge, r.ano, r.valor, r.q,
              detalhe=f"{mod_fnde.PROGRAMAS.get(r.programa, r.programa)} → {mod_fnde.DESTINOS.get(r.destino, r.destino)}",
              observacao=f"{r.meses} meses com repasse")
    if tcees:
        _consolidar_tcees(c, anual, tcees)
    _consolidar_matriculas_etapa(c, anual, subfuncoes)
    if cnca:
        _consolidar_cnca(c, cnca)
    if ica:
        _consolidar_ica(c, ica)
    if dinheiro_escolas is not None and escolas is not None and not dinheiro_escolas.empty:
        _consolidar_escolas(c, escolas, dinheiro_escolas)
    return c.tabela()


def _data(v: Any) -> str:
    return "—" if pd.isna(v) else pd.Timestamp(v).strftime("%Y-%m-%d")


def _consolidar_tcees(c: Consolidador, anual: pd.DataFrame, t: Mapping[str, Any]) -> None:
    """MDE do Tribunal, prazos, obras, empenhos (Nível 3) e dotação."""
    for r in anual[anual["esfera"] == "M"].itertuples(index=False):
        if not pd.isna(getattr(r, "tcees_mde_pct", None)):
            c.add("tcees_mde_pct", r.cod_ibge, r.ano, r.tcees_mde_pct, r.q_tcees_mde)
            c.add("tcees_mde_aplicado", r.cod_ibge, r.ano, r.tcees_mde_aplicado, r.q_tcees_mde)
            c.add("div_mde_tcees_siope_pp", r.cod_ibge, r.ano, r.div_mde_tcees_siope_pp,
                  juntar_ids(r.q_tcees_mde, getattr(r, "q_siope", None)))
        if not pd.isna(getattr(r, "tcees_alunos", None)):
            c.add("matriculas_rede_municipal", r.cod_ibge, r.ano, r.tcees_alunos, r.q_tcees_mde)
            c.add("desp_educacao_por_matricula", r.cod_ibge, r.ano, getattr(r, "desp_educacao_por_matricula", None),
                  juntar_ids(getattr(r, "q_dca_ie", None), r.q_tcees_mde))
        if not pd.isna(getattr(r, "tcees_emp_empenhada", None)):
            c.add("tcees_emp_empenhada", r.cod_ibge, r.ano, r.tcees_emp_empenhada, r.q_tcees_emp)
    pcm = t.get("pcm", pd.DataFrame())
    for r in pcm.itertuples(index=False):
        if r.situacao in ("prazo_aberto", "ug_sem_remessa") or pd.isna(r.ano) or pd.isna(r.mes):
            continue
        c.add("remessa_tcees_atraso_dias", r.cod_ibge, int(r.ano), 0 if r.situacao == "no_prazo" else r.dias_atraso, r.q,
              detalhe=f"{r.ug} · mês {int(r.mes):02d}", periodo=f"{int(r.mes):02d}",
              observacao=f"limite {_data(r.limite)} · homologada {_data(r.homologacao)} · situação {r.situacao}")
    obras = t.get("obras", pd.DataFrame())
    for r in obras.itertuples(index=False):
        ano = pd.to_numeric(str(r.assinatura)[:4], errors="coerce")
        if pd.isna(ano):
            continue
        c.add("obra_educacao", r.cod_ibge, int(ano), r.valor, r.q,
              detalhe=f"contratação {r.contratacao} · instrumento {r.chave}",
              observacao=f"{str(r.objeto)[:120]} · situação {r.situacao or '—'} · contratada {r.contratado or '—'}")
        if not pd.isna(getattr(r, "valor_medido", None)):
            c.add("obra_medido", r.cod_ibge, int(ano), r.valor_medido, r.q,
                  detalhe=f"contratação {r.contratacao} · instrumento {r.chave}",
                  observacao=f"{int(r.medicoes)} medição(ões), última em {r.ultima_medicao}")
    e = t.get("empenhos") or {}
    for r in e.get("credores", pd.DataFrame()).itertuples(index=False):
        c.add("empenho_credor", r.cod_ibge, r.ano, r.empenhada, r.q, detalhe=f"{r.credor} — {r.credor_nome}",
              observacao=f"elemento mais frequente: {r.elemento}; fonte {r.fonte}")
    for r in e.get("acoes", pd.DataFrame()).itertuples(index=False):
        c.add("empenho_acao", r.cod_ibge, r.ano, r.empenhada, r.q,
              detalhe=f"ação {r.CodigoAcao} - {r.NomeAcao} (subfunção {r.CodigoSubFuncao})")
    for r in e.get("fontes", pd.DataFrame()).itertuples(index=False):
        c.add("empenho_fonte", r.cod_ibge, r.ano, r.empenhada, r.q,
              detalhe=f"fonte {r.CodigoFonteReduzida}, detalhamento {r.CodigoDetalhamento} ({r.NomeDetalhamento})")
    for r in e.get("conselhos", pd.DataFrame()).itertuples(index=False):
        c.add("repasse_conselho_escolar", r.cod_ibge, r.ano, r.empenhada, r.q, detalhe=f"{r.credor} — {r.credor_nome}")
    for r in e.get("funpaes", pd.DataFrame()).itertuples(index=False):
        c.add("funpaes_empenho", r.cod_ibge, r.ano, r.empenhada, r.q,
              detalhe=f"{r.NomeAcao} · {r.DescricaoElemento} · fonte {r.CodigoFonteReduzida} · {r.credor} — {r.credor_nome}")
    for r in e.get("credor_acao", pd.DataFrame()).itertuples(index=False):
        c.add("empenho_credor_acao", r.cod_ibge, r.ano, r.empenhada, r.q,
              detalhe=f"ação {r.CodigoAcao} - {r.NomeAcao} · {r.credor} — {r.credor_nome}",
              observacao=f"elemento mais frequente: {r.elemento or '—'}; fonte {r.fonte or '—'}"
                         + (f"; soma de {int(r.demais)} credores" if r.demais else ""))
    for r in (t.get("itens") or {}).get("itens", pd.DataFrame()).itertuples(index=False):
        c.add("item_contratado", r.cod_ibge, r.ano, r.valor_total, r.q,
              detalhe=f"contratação {r.contratacao} · lote {r.lote} item {r.item}",
              observacao=f"{str(r.descricao)[:160]} · {_num(r.quantidade) or 0:g} {r.unidade or ''} × "
                         f"{_num(r.valor_unitario) or 0:.2f} · contratada {r.contratada or '—'} · "
                         f"vínculo com a Educação: {r.vinculo}")
        if not pd.isna(getattr(r, "valor_medido", None)):
            c.add("item_medido", r.cod_ibge, r.ano, r.valor_medido, r.q,
                  detalhe=f"contratação {r.contratacao} · lote {r.lote} item {r.item}",
                  observacao=f"{int(r.medicoes)} medição(ões) do item")
    dot = t.get("dotacao", pd.DataFrame())
    if not dot.empty:   # a mesma ação vem partida entre obra e não-obra: no consolidado ela é uma só
        por_acao = dot.groupby(["cod_ibge", "ano", "CodigoAcao", "NomeAcao"], as_index=False).agg(
            PrevisaoAtualizada=("PrevisaoAtualizada", "sum"), q=("q", "first"))
        for r in por_acao.itertuples(index=False):
            c.add("dotacao_atualizada", r.cod_ibge, r.ano, r.PrevisaoAtualizada, r.q,
                  detalhe=f"ação {r.CodigoAcao} - {r.NomeAcao}")


def _consolidar_cnca(c: Consolidador, cnca: Mapping[str, pd.DataFrame]) -> None:
    for r in cnca["municipio"].itertuples(index=False):
        c.add("cnca_pdde", r.cod_ibge, r.ano, r.pdde_cnca, r.q, detalhe="PO 000C (CNCA)")
        c.add("cnca_pdde", r.cod_ibge, r.ano, r.pdde_alfabetizacao, r.q, detalhe="PO 0007 (PDDE - Alfabetização)")
    for r in cnca["estado"].itertuples(index=False):
        c.add("cnca_estado", COD_ESTADO_ES, int(r.ano), r.valor, r.q, detalhe=str(r.favorecido), periodo=f"{int(r.mes):02d}")


def _consolidar_ica(c: Consolidador, ica: Mapping[str, pd.DataFrame]) -> None:
    """ICA do INEP: taxa por ano, participação da edição e as metas pactuadas até 2030.

    Linha `sem_dado` não entra (não há número a consolidar) — `add` já descarta valor
    nulo; a ausência fica registrada no dataset (`ica.resultados`) e na página.
    """
    for r in ica.get("resultados", pd.DataFrame()).itertuples(index=False):
        detalhe = f"edição {int(r.edicao)}"
        c.add("ica_taxa", int(r.cod_ibge), int(r.ano), r.taxa, r.q, detalhe=detalhe)
        c.add("ica_participacao", int(r.cod_ibge), int(r.ano), r.participacao, r.q, detalhe=detalhe)
    for r in ica.get("metas", pd.DataFrame()).itertuples(index=False):
        c.add("ica_meta", int(r.cod_ibge), int(r.ano), r.meta, r.q, detalhe=f"edição {int(r.edicao)}")


_CANAL = {"pdde": "PDDE", "repasse_municipal": "repasse do município ao conselho escolar",
          "obra": "contrato de obra no prédio (valor atual)"}


def _consolidar_escolas(c: Consolidador, escolas: pd.DataFrame, dinheiro: pd.DataFrame) -> None:
    """Recurso por escola, no município do Censo (a escola estadual conta no município onde fica)."""
    d = dinheiro.join(escolas.set_index("co_entidade")[["cod_ibge", "nome"]], on="co_entidade")
    for r in d[d["cod_ibge"].notna() & d["ano"].notna()].itertuples(index=False):
        canal = f"PDDE {r.po} ({r.po_nome})" if r.canal == "pdde" else _CANAL[r.canal]
        c.add("escola_recurso", int(r.cod_ibge), int(r.ano), r.valor, r.q, detalhe=f"INEP {int(r.co_entidade)} · {canal}",
              observacao=r.nome)


def _item(itens_json: Any, campo: str) -> str | None:
    try:
        return json.loads(itens_json).get(campo)
    except (TypeError, ValueError):
        return None


def _conta_a01(chave: str) -> str:
    from .rreo_receita import LINHAS
    return next((k for k, v in LINHAS.items() if v == chave), chave)


# ----------------------------------------------------------------- validação

def validar(consolidado: pd.DataFrame) -> dict[str, Any]:
    """Conferências do dataset final (também cobertas por testes).

    * código IBGE com 7 dígitos em todo registro de município;
    * nenhum valor negativo onde o indicador não admite (`indicadores.negativo`);
    * todo registro com pelo menos uma consulta de origem, exceto os calculados
      a partir de outros registros (que citam as consultas dos insumos).
    """
    if consolidado.empty:
        return {"registros": 0, "ibge_7_digitos": True, "negativos_inesperados": [], "sem_proveniencia": 0}
    # Município: 7 dígitos. A única exceção admitida é o Estado do ES (código 32, 2 dígitos).
    codigos = consolidado["cod_ibge"].astype(str)
    ibge_ok = bool(codigos.str.fullmatch(r"\d{7}").where(codigos != str(COD_ESTADO_ES), True).all())
    neg = consolidado[(consolidado["valor"] < 0) & ~consolidado["indicador"].map(negativo_permitido)]
    sem = consolidado[consolidado["consultas"].fillna("") == ""]
    return {
        "registros": int(len(consolidado)),
        "ibge_7_digitos": ibge_ok,
        "negativos_inesperados": neg[["cod_ibge", "ente", "ano", "indicador", "detalhe", "valor"]].head(50).to_dict("records"),
        "n_negativos_inesperados": int(len(neg)),
        "sem_proveniencia": int(len(sem)),
        "por_fonte": consolidado["fonte"].value_counts().to_dict() if "fonte" in consolidado else {},
    }


def conferencia_matriculas(anual: pd.DataFrame, escolas: pd.DataFrame) -> dict[str, Any]:
    """"Alunos" do TCE-ES × matrículas da rede municipal no Censo, no ano do retrato.

    O denominador de "R$ por matrícula" é o do Tribunal; esta é a prova de que ele é o
    do Censo. Compara só o ano do retrato do Censo em cache (o cadastro traz uma linha
    por escola, no último censo dela), então é uma conferência pontual, não da série.
    """
    vazio = {"comparaveis": 0, "batem": 0, "ano": None, "maiores": []}
    if escolas.empty or "matriculas" not in escolas or "tcees_alunos" not in anual:
        return vazio
    e = escolas[(escolas["rede"] == "municipal") & escolas["matriculas"].notna()]
    if e.empty:
        return vazio
    ano = int(e["ano_censo"].mode().iloc[0])
    censo = e[e["ano_censo"] == ano].groupby("cod_ibge")["matriculas"].sum()
    m = anual[(anual["esfera"] == "M") & (anual["ano"] == ano) & anual["tcees_alunos"].notna()].copy()
    m["censo"] = m["cod_ibge"].map(censo)
    x = m[m["censo"].notna()]
    dif = (x["tcees_alunos"] - x["censo"]).abs()
    return {"comparaveis": int(len(x)), "batem": int((dif < 0.5).sum()), "ano": ano, "unidade": "matrículas",
            "maiores": x.loc[dif >= 0.5].assign(dif=(x["tcees_alunos"] - x["censo"]).astype("Int64"))
            .reindex(dif[dif >= 0.5].sort_values(ascending=False).index)
            .head(10)[["cod_ibge", "ente", "ano", "dif"]].to_dict("records")}


def conferencias_cruzadas(anual: pd.DataFrame, escolas: pd.DataFrame | None = None) -> dict[str, Any]:
    """Uma fonte contra a outra — o que o README e o painel reportam."""
    m = anual[anual["esfera"] == "M"]

    def bate(a: str, b: str, tol: float = TOLERANCIA_CENTAVOS) -> dict[str, Any]:
        if a not in m or b not in m:
            return {"comparaveis": 0, "batem": 0, "maiores": []}
        x = m[m[a].notna() & m[b].notna()]
        ok = (x[a] - x[b]).abs() <= tol
        return {"comparaveis": int(len(x)), "batem": int(ok.sum()),
                "maiores": x.loc[~ok].assign(dif=(x[a] - x[b]).round(2)).reindex(
                    (x.loc[~ok, a] - x.loc[~ok, b]).abs().sort_values(ascending=False).index)
                .head(10)[["cod_ibge", "ente", "ano", "dif"]].to_dict("records")}

    def bate_completo() -> dict[str, Any]:
        """Empenhos × DCA onde o arquivo do TCE-ES tem o ano inteiro; os incompletos são contados à parte."""
        if "tcees_emp_meses" not in m:
            return {"comparaveis": 0, "batem": 0, "maiores": [], "incompletos": 0}
        completos = m["tcees_emp_meses"].fillna(0).astype(float) >= 12
        x = m[completos & m["tcees_emp_empenhada"].notna() & m["desp_educacao_empenhada"].notna()]
        ok = (x["tcees_emp_empenhada"] - x["desp_educacao_empenhada"]).abs() <= TOLERANCIA_CENTAVOS
        fora = x.loc[~ok].assign(dif=(x["tcees_emp_empenhada"] - x["desp_educacao_empenhada"]).round(2))
        return {"comparaveis": int(len(x)), "batem": int(ok.sum()),
                "maiores": fora.reindex(fora["dif"].abs().sort_values(ascending=False).index)
                .head(10)[["cod_ibge", "ente", "ano", "dif"]].to_dict("records"),
                "incompletos": int((m["tcees_emp_empenhada"].notna() & ~completos).sum())}

    matriculas = conferencia_matriculas(anual, escolas if escolas is not None else pd.DataFrame())
    return {
        "msc_x_dca_funcao12": {"descricao": "Despesa da função 12 empenhada: MSC (contas 6.2.2.1.3.01–07, sem intra) × DCA I-E",
                               **bate("msc_empenhada", "desp_educacao_empenhada")},
        "fundeb_msc_x_dca": {"descricao": "Receita do FUNDEB: MSC × DCA I-C", **bate("fundeb_msc_total", "fundeb_receita")},
        "fundeb_siope_x_dca": {"descricao": "Receita do FUNDEB, só o principal: SIOPE (Anexo 8, itens \"Principal\") × DCA I-C",
                               **bate("fundeb_principal", "fundeb_receita")},
        "funcao12_x_siope": {"descricao": "Despesa com educação: função 12 (DCA I-E) × total geral do Anexo 8 (SIOPE)",
                             **bate("desp_educacao_empenhada", "despesa_total_educacao")},
        "mde_tcees_x_siope": {"descricao": "% aplicado em MDE: apuração do TCE-ES × SIOPE (tolerância de 0,5 p.p.)",
                              **bate("tcees_mde_pct", "siope_mde_pct", 0.5)},
        "empenhos_tcees_x_dca": {"descricao": "Função 12 empenhada: soma dos empenhos do TCE-ES (sem intra) × DCA I-E, "
                                              "só município-anos com os 12 meses no arquivo do TCE-ES (tolerância de R$ 1,00)",
                                 **bate_completo()},
        "matriculas_tcees_x_censo": {"descricao": "Matrículas no denominador de \"R$ por matrícula\": \"Alunos\" do recurso "
                                                  "\"Educação\" do TCE-ES × soma das matrículas da rede municipal no Censo "
                                                  f"Escolar de {matriculas['ano']}" if matriculas["ano"] else
                                                  "Matrículas: TCE-ES × Censo (sem retrato do Censo nesta execução)",
                                     **matriculas},
    }


