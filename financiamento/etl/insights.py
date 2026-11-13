"""Insights das redes do financiamento: fatos calculados e, opcionalmente, a redação
por um modelo Claude a partir SÓ desses fatos — com cada número conferido.

O desenho segue o princípio do painel (todo número tem fonte):

1. **Fatos** (`calcular_fatos`): determinísticos, calculados aqui do `grafos.json` —
   comunidades, concentração, alcance, crescimento, origem FNDE, pessoa física no
   transporte, obras paradas. Cada fato traz os números (valor bruto e como é escrito),
   o link para o recorte da página que o mostra e os ids das consultas de origem.
2. **Redação** (`redigir`, só com ``--com-ia``): o Claude recebe a lista de fatos e
   devolve observações curtas em JSON (saída estruturada), citando os fatos que usou.
   Nada da página chama a API: a chave fica na máquina de quem roda o ETL, e o texto
   é gravado uma vez, com modelo, id da requisição e hash do prompt.
3. **Verificação** (`verificar`): todo número do texto tem de bater com um número dos
   fatos citados (com a tolerância do arredondamento escrito); fato citado tem de
   existir; palavras que afirmam irregularidade ("fraude", "superfaturamento"…) são
   recusadas. O que não passa NÃO vai para a página — e o motivo fica registrado.

    python -m financiamento.etl.insights             # só os fatos (sem rede)
    python -m financiamento.etl.insights --com-ia    # + redação pelo Claude (ANTHROPIC_API_KEY ou `ant auth login`)

Ligação, alcance, concentração e obra parada não são irregularidade: são padrões para
escolher onde olhar. O texto gerado diz isso, e a verificação recusa o que disser o contrário.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import PROCESSADO

ENTRADA = PROCESSADO / "grafos.json"
SAIDA = PROCESSADO / "insights.json"
ESQUEMA = 1
MODELO_PADRAO = "claude-opus-5-5"
TIPOS_PADRAO = ("empresa", "terceiro")
#: Mercados em que concentração e alcance são lidos (os demais são pequenos ou de monopólio natural).
MERCADOS_LIDOS = ("transporte", "alimentacao", "obras", "didatico", "kits", "maoobra", "tic", "equipamentos", "consumo")
PALAVRAS_PROIBIDAS = re.compile(r"\b(fraud\w*|irregularidad\w*|irregular\b|superfatur\w*|conluio|cartel\w*|desvio\w*|corrup\w*|"
                                r"ilega\w*|crime\w*|criminos\w*|propina\w*|direcionament\w*)", re.I)
_CPF = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")


# --------------------------------------------------------------- formatação
def _br(v: float, casas: int) -> str:
    s = f"{v:,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_brl(v: float) -> str:
    """Como a página escreve: R$ 1,40 bi / R$ 6,4 mi / R$ 950 mil."""
    a = abs(v)
    if a >= 1e9:
        return "R$ " + _br(v / 1e9, 2) + " bi"
    if a >= 1e6:
        return "R$ " + _br(v / 1e6, 1) + " mi"
    if a >= 1e3:
        return "R$ " + _br(v / 1e3, 0) + " mil"
    return "R$ " + _br(v, 2)


def fmt_pct(v: float) -> str:
    return _br(v, 1 if abs(v) < 10 else 0) + "%"


def fmt_int(v: float) -> str:
    return _br(v, 0)


def fmt_dec(v: float, casas: int = 2) -> str:
    return _br(v, casas)


def mascarar(texto: str) -> str:
    """CPF digitado no nome de credor (MEI/EI) não sai daqui — nem para a página, nem para a API."""
    return _CPF.sub("[CPF omitido]", texto)


def _n(rotulo: str, valor: float, unidade: str) -> dict[str, Any]:
    texto = {"brl": fmt_brl, "pct": fmt_pct, "int": fmt_int, "dec": fmt_dec}[unidade](valor)
    return {"rotulo": rotulo, "valor": round(float(valor), 6), "unidade": unidade, "texto": texto}


# --------------------------------------------------------------- leitura do grafo
class Rede:
    """O grafos.json lido uma vez, com as somas que os fatos usam (no período, por mercado)."""

    def __init__(self, dados: dict[str, Any]):
        self.d = dados
        self.meta = dados["meta"]
        self.anos = self.meta["anos"]
        self.mun = dados["municipios"]
        fc = dados["fornecedores"]["colunas"]
        self.forn = [dict(zip(fc, l)) for l in dados["fornecedores"]["linhas"]]
        self.mercados = [m["id"] for m in self.meta["mercados"]]
        self.rot_mercado = {m["id"]: m["rotulo"] for m in self.meta["mercados"]} | {"todos": "Todos os mercados"}
        self.fontes = [f["id"] for f in self.meta["fontes"]]
        self._cache: dict[tuple, dict] = {}

    def nome_f(self, f: int) -> str:
        return mascarar(self.forn[f]["nome"])

    def somas(self, mercado: str = "todos", fonte: str | None = None, ano: int | None = None,
              tipos: Iterable[str] = TIPOS_PADRAO) -> dict[tuple[int, int], float]:
        """(município, fornecedor) → empenhado no recorte."""
        chave = (mercado, fonte, ano, tuple(sorted(tipos)))
        if chave in self._cache:
            return self._cache[chave]
        a = self.d["arestas"]
        ki = None if mercado == "todos" else self.mercados.index(mercado)
        fi = None if fonte is None else self.fontes.index(fonte)
        ai = None if ano is None else self.anos.index(ano)
        tipos = set(tipos)
        s: dict[tuple[int, int], float] = defaultdict(float)
        for i in range(len(a["m"])):
            if ki is not None and a["k"][i] != ki:
                continue
            f = a["f"][i]
            if self.forn[f]["tipo"] not in tipos:
                continue
            v = a["v"][i]
            for j in range(0, len(v), 4):
                if (ai is None or v[j] == ai) and (fi is None or v[j + 1] == fi):
                    s[(a["m"][i], f)] += v[j + 2]
        s = {k: x for k, x in s.items() if x > 0.005}
        self._cache[chave] = s
        return s

    @staticmethod
    def por_fornecedor(s: dict[tuple[int, int], float]) -> dict[int, dict[str, Any]]:
        out: dict[int, dict[str, Any]] = defaultdict(lambda: {"emp": 0.0, "muns": set()})
        for (m, f), v in s.items():
            out[f]["emp"] += v
            out[f]["muns"].add(m)
        return out

    @staticmethod
    def por_municipio(s: dict[tuple[int, int], float]) -> dict[int, dict[int, float]]:
        out: dict[int, dict[int, float]] = defaultdict(dict)
        for (m, f), v in s.items():
            out[m][f] = v
        return out


def hhi(valores: Iterable[float]) -> float | None:
    v = [x for x in valores if x > 0]
    t = sum(v)
    return None if not v or t <= 0 else sum((x / t * 100) ** 2 for x in v)


# --------------------------------------------------------------- os fatos
def calcular_fatos(dados: dict[str, Any]) -> list[dict[str, Any]]:
    """Fatos determinísticos sobre as três redes. Mesma entrada → mesmos fatos, na mesma ordem."""
    r = Rede(dados)
    q_emp = ";".join(x for x in r.meta["q_empenhos"].values() if x)
    q_obras = r.meta.get("q_obras", "")
    q_ibge = r.meta.get("q_ibge", "")
    fatos: list[dict[str, Any]] = []

    def fato(id_: str, tema: str, tipo: str, texto: str, numeros: list[dict], link: dict, q: str) -> None:
        fatos.append({"id": id_, "tema": tema, "tipo": tipo, "texto": mascarar(texto), "numeros": numeros, "link": link, "q": q})

    # 1. Contexto: o que a rede cobre.
    T = r.meta["totais"]
    fato("contexto-total", "contexto", "contexto",
         f"De {r.anos[0]} a {r.anos[-1]}, os municípios do ES empenharam {fmt_brl(T['pj'])} a pessoas jurídicas na Educação (fora pessoal); "
         f"a folha e os encargos ({fmt_brl(T['pessoal'])}) e as pessoas físicas ({fmt_brl(T['pf'])}) ficam fora da rede.",
         [_n("empenhado a pessoas jurídicas", T["pj"], "brl"), _n("pessoal e encargos", T["pessoal"], "brl"), _n("pessoas físicas", T["pf"], "brl")],
         {"visao": "metodologia"}, q_emp)
    inc = r.meta.get("incompletos", [])
    if inc:
        anos_inc = Counter(x["ano"] for x in inc)
        a_inc, n_inc = anos_inc.most_common(1)[0]
        fato("contexto-incompleto", "contexto", "contexto",
             f"O arquivo do TCE-ES de {a_inc} não traz dezembro para {n_inc} municípios: a soma desse ano fica curta para eles.",
             [_n("municípios sem dezembro", n_inc, "int"), _n("ano", a_inc, "int")], {"visao": "metodologia"}, q_emp)

    # 2. Comunidades: o mercado segue a geografia?
    P = dados["projecoes"]["todos"]
    tam = Counter(c for c in P["comunidade"] if c >= 0)
    if P["n_comunidades"]:
        partes, dominantes = [], []
        for c, n in sorted(tam.items()):
            regs = Counter(r.mun[i]["intermediaria"] for i, x in enumerate(P["comunidade"]) if x == c).most_common(1)[0]
            partes.append(f"{'ABCDEFGHIJ'[c]} ({n} municípios, {regs[1]} da região intermediária de {regs[0]})")
            dominantes.append(_n(f"municípios da comunidade {'ABCDEFGHIJ'[c]} na região {regs[0]}", regs[1], "int"))
        fato("comunidades-todos", "comunidades", "padrao",
             f"Pelos fornecedores em comum, os 78 municípios se dividem em {P['n_comunidades']} comunidades: " + "; ".join(partes)
             + f". A coincidência com as regiões intermediárias do IBGE é {fmt_dec(P['ari_intermediaria'])} (índice de Rand ajustado; 1 seria igual).",
             [_n("comunidades", P["n_comunidades"], "int"), _n("índice de Rand ajustado (intermediárias)", P["ari_intermediaria"], "dec"),
              *[_n(f"municípios na comunidade {'ABCDEFGHIJ'[c]}", n, "int") for c, n in sorted(tam.items())], *dominantes],
             {"visao": "municipios", "mercado": "todos"}, ";".join(x for x in (q_emp, q_ibge) if x))
    lidos = [(m, dados["projecoes"][m]) for m in MERCADOS_LIDOS if dados["projecoes"][m]["ari_intermediaria"] is not None
             and dados["projecoes"][m]["fornecedores_compartilhados"] >= 20]
    lidos.sort(key=lambda x: -x[1]["ari_intermediaria"])
    if len(lidos) >= 4:
        alto, baixo = lidos[:2], lidos[-3:]
        fato("comunidades-regional-vs-estadual", "comunidades", "padrao",
             "Os mercados que mais seguem as regiões intermediárias do IBGE são " + " e ".join(f"{r.rot_mercado[m].lower()} ({fmt_dec(p['ari_intermediaria'])})" for m, p in alto)
             + "; os que menos seguem são " + ", ".join(f"{r.rot_mercado[m].lower()} ({fmt_dec(p['ari_intermediaria'])})" for m, p in baixo)
             + " — nesses, os mesmos fornecedores vendem ao estado inteiro, sem respeitar região.",
             [_n(f"índice de Rand ajustado — {r.rot_mercado[m]}", p["ari_intermediaria"], "dec") for m, p in alto + baixo],
             {"visao": "municipios", "mercado": baixo[0][0]}, q_emp)

    # 3. Concentração por mercado e os municípios mais concentrados.
    for m in ("transporte", "alimentacao", "didatico", "obras", "kits", "tic"):
        pm = r.por_municipio(r.somas(m))
        com = [(i, hhi(v.values()), sum(v.values()), max(v.items(), key=lambda x: x[1])) for i, v in pm.items() if v]
        if len(com) < 10:
            continue
        altos = [x for x in com if x[1] is not None and x[1] > 2500]
        fato(f"concentracao-{m}", "concentracao", "padrao",
             f"Em {r.rot_mercado[m].lower()}, {len(altos)} dos {len(com)} municípios com gasto têm o mercado concentrado (HHI acima de 2.500, faixa alta do CADE).",
             [_n("municípios com concentração alta", len(altos), "int"), _n("municípios com gasto no mercado", len(com), "int"), _n("limiar do HHI", 2500, "int")],
             {"visao": "fornecedores", "mercado": m, "ir": "concentracao"}, q_emp)
        if m in ("transporte", "alimentacao"):
            dominados = sorted([x for x in com if x[3][1] / x[2] >= 0.8 and x[2] >= 1e6], key=lambda x: -x[2])[:3]
            for i, h, tot, (f, v) in dominados:
                cod = r.mun[i]["cod"]
                fato(f"dominado-{m}-{cod}", "concentracao", "sinal",
                     f"Em {r.mun[i]['nome']}, {r.nome_f(f)} fica com {fmt_pct(v / tot * 100)} de {r.rot_mercado[m].lower()} ({fmt_brl(v)} de {fmt_brl(tot)} em {r.anos[0]}–{r.anos[-1]}).",
                     [_n("parcela do maior fornecedor", v / tot * 100, "pct"), _n("valor do maior fornecedor", v, "brl"), _n("mercado do município", tot, "brl")],
                     {"visao": "fornecedores", "mercado": m, "sel": f"m:{cod}"}, q_emp)

    # 4. Alcance: quem vende a mais municípios em cada mercado.
    for m in ("transporte", "alimentacao", "didatico", "kits", "tic", "obras"):
        pf = r.por_fornecedor(r.somas(m))
        if not pf:
            continue
        f, x = max(pf.items(), key=lambda kv: (len(kv[1]["muns"]), kv[1]["emp"]))
        if len(x["muns"]) < 5:
            continue
        total = sum(y["emp"] for y in pf.values())
        fato(f"alcance-{m}", "alcance", "padrao",
             f"Em {r.rot_mercado[m].lower()}, o fornecedor de maior alcance é {r.nome_f(f)}: atende {len(x['muns'])} municípios e recebeu {fmt_brl(x['emp'])} "
             f"({fmt_pct(x['emp'] / total * 100)} do mercado no ES).",
             [_n("municípios atendidos", len(x["muns"]), "int"), _n("valor recebido", x["emp"], "brl"), _n("parcela do mercado no ES", x["emp"] / total * 100, "pct")],
             {"visao": "fornecedores", "mercado": m, "sel": f"f:{r.forn[f]['raiz']}"}, q_emp)

        # O de maior VALOR entre os que atendem 5+ municípios: o alcance sozinho às vezes aponta um fornecedor pequeno.
        grandes = [(kv[1]["emp"], kv[0]) for kv in pf.items() if len(kv[1]["muns"]) >= 5]
        if grandes:
            emp_g, fg = max(grandes)
            if fg != f:
                xg = pf[fg]
                fato(f"valor-{m}", "alcance", "padrao",
                     f"Entre os fornecedores de {r.rot_mercado[m].lower()} que atendem 5 municípios ou mais, o de maior valor é {r.nome_f(fg)}: "
                     f"{fmt_brl(emp_g)} ({fmt_pct(emp_g / total * 100)} do mercado no ES) em {len(xg['muns'])} municípios.",
                     [_n("valor recebido", emp_g, "brl"), _n("parcela do mercado no ES", emp_g / total * 100, "pct"),
                      _n("municípios atendidos", len(xg["muns"]), "int"), _n("mínimo de municípios", 5, "int")],
                     {"visao": "fornecedores", "mercado": m, "sel": f"f:{r.forn[fg]['raiz']}"}, q_emp)

    # 5. Pontes: quem atravessa mais comunidades.
    pf = r.por_fornecedor(r.somas("todos"))
    pontes = []
    for f, x in pf.items():
        coms = {P["comunidade"][i] for i in x["muns"] if P["comunidade"][i] >= 0}
        if len(coms) == P["n_comunidades"] and len(x["muns"]) >= 2:
            pontes.append((len(x["muns"]), x["emp"], f))
    if pontes:
        pontes.sort(reverse=True)
        n_m, emp, f = pontes[0]
        fato("pontes", "comunidades", "padrao",
             f"{len(pontes)} fornecedores têm clientes nas {P['n_comunidades']} comunidades; o de maior alcance, {r.nome_f(f)}, atende {n_m} municípios ({fmt_brl(emp)}).",
             [_n("fornecedores em todas as comunidades", len(pontes), "int"), _n("municípios atendidos", n_m, "int"), _n("valor recebido", emp, "brl"),
              _n("comunidades", P["n_comunidades"], "int")],
             {"visao": "fornecedores", "mercado": "todos", "sel": f"f:{r.forn[f]['raiz']}"}, q_emp)

    # 6. Crescimento: quem mais aumentou de 2021 para 2025, e quem entrou depois e já é grande.
    a0, a1 = r.anos[0], r.anos[-1]
    s0 = r.por_fornecedor(r.somas("todos", ano=a0))
    s1 = r.por_fornecedor(r.somas("todos", ano=a1))
    cres = sorted(((s1[f]["emp"] - (s0[f]["emp"] if f in s0 else 0.0), f) for f in s1 if len(s1[f]["muns"]) >= 2), reverse=True)[:3]
    for pos, (dif, f) in enumerate(cres):
        antes = s0[f]["emp"] if f in s0 else 0.0
        fato(f"crescimento-{pos + 1}", "crescimento", "sinal",
             f"{r.nome_f(f)} passou de {fmt_brl(antes)} em {a0} para {fmt_brl(s1[f]['emp'])} em {a1}, em {len(s1[f]['muns'])} municípios.",
             [_n(f"valor em {a0}", antes, "brl"), _n(f"valor em {a1}", s1[f]["emp"], "brl"), _n(f"municípios em {a1}", len(s1[f]["muns"]), "int"),
              _n("aumento", dif, "brl")],
             {"visao": "fornecedores", "mercado": "todos", "ano": a1, "sel": f"f:{r.forn[f]['raiz']}"}, q_emp)
    primeiros = {}
    for ano in r.anos:
        for f in r.por_fornecedor(r.somas("todos", ano=ano)):
            primeiros.setdefault(f, ano)
    novos = sorted(((len(s1[f]["muns"]), s1[f]["emp"], f) for f in s1 if primeiros.get(f, a0) >= a0 + 2 and len(s1[f]["muns"]) >= 5), reverse=True)
    if novos:
        n_m, emp, f = novos[0]
        fato("entrantes", "crescimento", "sinal",
             f"{len(novos)} fornecedores sem empenho até {a0 + 1} já atendiam 5 municípios ou mais em {a1}; o maior, {r.nome_f(f)}, primeira aparição em "
             f"{primeiros[f]}, atende {n_m} municípios ({fmt_brl(emp)} em {a1}).",
             [_n("novos fornecedores com 5+ municípios", len(novos), "int"), _n("municípios atendidos", n_m, "int"), _n(f"valor em {a1}", emp, "brl"),
              _n("ano da primeira aparição", primeiros[f], "int"), _n("mínimo de municípios", 5, "int")],
             {"visao": "fornecedores", "mercado": "todos", "ano": a1, "sel": f"f:{r.forn[f]['raiz']}"}, q_emp)

    # 7. Origem FNDE: quanto do dinheiro federal específico fica com poucos fornecedores.
    fnde = r.por_fornecedor(r.somas("todos", fonte="fnde"))
    if fnde:
        tot = sum(x["emp"] for x in fnde.values())
        top = sorted(fnde.items(), key=lambda kv: -kv[1]["emp"])
        dez = sum(x["emp"] for _, x in top[:10])
        f, x = top[0]
        fato("fnde-concentracao", "origem", "padrao",
             f"Do que os municípios empenharam com recursos do FNDE (salário-educação, PNAE, PNATE e outros) a pessoas jurídicas, {fmt_brl(tot)}, "
             f"os 10 maiores fornecedores ficam com {fmt_pct(dez / tot * 100)}; o maior é {r.nome_f(f)} ({fmt_brl(x['emp'])}, {len(x['muns'])} municípios).",
             [_n("empenhado com recursos do FNDE", tot, "brl"), _n("parcela dos 10 maiores", dez / tot * 100, "pct"), _n("valor do maior", x["emp"], "brl"),
              _n("municípios do maior", len(x["muns"]), "int"), _n("tamanho do grupo dos maiores", 10, "int")],
             {"visao": "fornecedores", "mercado": "todos", "fonte": "fnde", "sel": f"f:{r.forn[f]['raiz']}"}, q_emp)

    # 8. Pessoa física no transporte (motoristas autônomos): o mercado é mais concentrado do que parece?
    kt = r.mercados.index("transporte")
    pfm: dict[int, float] = defaultdict(float)
    for m_, k_, _a, _f, classe, v in dados["residuais"]:
        if k_ == kt and classe == "pf":
            pfm[m_] += v
    pj_t = r.por_municipio(r.somas("transporte", tipos=[t["id"] for t in r.meta["tipos"]]))
    altos_pf = []
    for i, v in pfm.items():
        tot = v + sum(pj_t.get(i, {}).values())
        if tot > 0 and v / tot >= 0.3:
            altos_pf.append((v / tot * 100, v, i))
    if altos_pf:
        altos_pf.sort(reverse=True)
        pct, v, i = altos_pf[0]
        fato("transporte-pessoa-fisica", "concentracao", "contexto",
             f"Em {len(altos_pf)} municípios, pessoas físicas (motoristas autônomos) recebem 30% ou mais do transporte escolar — fora da rede, que só tem CNPJ. "
             f"O maior caso é {r.mun[i]['nome']}, com {fmt_pct(pct)} ({fmt_brl(v)}).",
             [_n("municípios com 30%+ a pessoas físicas", len(altos_pf), "int"), _n("parcela de pessoas físicas", pct, "pct"), _n("valor a pessoas físicas", v, "brl"),
              _n("limiar", 30, "pct")],
             {"visao": "fornecedores", "mercado": "transporte", "sel": f"m:{r.mun[i]['cod']}"}, q_emp)

    # 9. Obras paradas.
    ob = dados.get("obras") or {}
    if ob.get("contratos", {}).get("linhas"):
        cc = ob["contratos"]["colunas"]
        contratos = [dict(zip(cc, l)) for l in ob["contratos"]["linhas"]]
        kc = ob["contratadas"]["colunas"]
        contratadas = [dict(zip(kc, l)) for l in ob["contratadas"]["linhas"]]
        parados = [x for x in contratos if x["sit"] in ("presumida", "paralisada")]
        valor_parado = sum(x["valor_n"] or 0 for x in parados)
        por_c: dict[int, set] = defaultdict(set)
        val_c: dict[int, float] = defaultdict(float)
        for x in parados:
            por_c[x["c"]].add(x["m"])
            val_c[x["c"]] += x["valor_n"] or 0
        multi = sorted(((len(ms), val_c[c], c) for c, ms in por_c.items() if len(ms) >= 2), reverse=True)
        presumida = sum(1 for x in parados if x["sit"] == "presumida")
        fato("obras-paradas", "obras", "sinal",
             f"Dos {len(contratos)} contratos de obra da Educação declarados ao TCE-ES, {len(parados)} estão parados ({fmt_brl(valor_parado)}); "
             f"{presumida} deles em paralisação presumida pelo Tribunal, por falta de medição. {len(multi)} contratadas têm obra parada em dois ou mais municípios.",
             [_n("contratos", len(contratos), "int"), _n("contratos parados", len(parados), "int"), _n("valor parado", valor_parado, "brl"),
              _n("em paralisação presumida", presumida, "int"), _n("contratadas com obra parada em 2+ municípios", len(multi), "int")],
             {"visao": "obras", "sit": "paradas", "minObras": 2}, q_obras)
        for pos, (n_m, v, c) in enumerate(multi[:3]):
            C = contratadas[c]
            fato(f"obras-contratada-{pos + 1}", "obras", "sinal",
                 f"{mascarar(C['nome'])} tem obra da Educação parada em {n_m} municípios, somando {fmt_brl(v)} em contratos parados.",
                 [_n("municípios com obra parada", n_m, "int"), _n("valor dos contratos parados", v, "brl")],
                 {"visao": "obras", "sel": f"c:{C['id']}"}, q_obras)
    return fatos


# --------------------------------------------------------------- verificação
_NUM = re.compile(r"(R\$\s*)?(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?\s*(%|bi\b|bilh\w*|mi\b|milh\w*|mil\b)?", re.I)


def numeros_do_texto(texto: str) -> list[tuple[float, str, float]]:
    """Números escritos em pt-BR → (valor, unidade, tolerância do arredondamento escrito)."""
    saida = []
    for m in _NUM.finditer(texto):
        rs, inteiro, dec, suf = m.group(1), m.group(2), m.group(3), (m.group(4) or "").lower()
        ini = m.start(2)
        if ini > 0 and (texto[ini - 1].isalpha() or texto[ini - 1] in "/-"):   # parte de nome ou código ("PNATE-2", "22/09")
            continue
        fim = m.end(3) if m.group(3) else m.end(2)   # logo depois do último dígito, não depois do espaço
        if fim < len(texto) and (texto[fim].isalpha() or texto[fim] in "ºª°"):   # "3R", "1ª"
            continue
        valor = float(inteiro.replace(".", "") + ("." + dec if dec else ""))
        casas = len(dec) if dec else 0
        escala = 1.0
        if suf.startswith("bi"):
            escala = 1e9
        elif suf.startswith("mi") and suf != "mil":
            escala = 1e6
        elif suf == "mil":
            escala = 1e3
        unidade = "pct" if suf == "%" else ("brl" if rs or escala > 1 else "num")
        tol = 0.5 * 10 ** (-casas) * escala
        saida.append((valor * escala, unidade, tol))
    return saida


def _bate(valor: float, unidade: str, tol: float, permitidos: list[dict]) -> bool:
    for p in permitidos:
        u = p["unidade"]
        if unidade == "pct" and u != "pct":
            continue
        if unidade == "brl" and u != "brl":
            continue
        if unidade == "num" and u not in ("int", "dec", "pct"):
            continue
        v = p["valor"]
        if abs(valor - v) <= max(tol, abs(v) * 0.01) + 1e-9:
            return True
    return False


def verificar(insight: dict[str, Any], fatos: dict[str, dict], anos: Iterable[int]) -> list[str]:
    """Problemas que impedem o insight de ir para a página (lista vazia = aprovado)."""
    problemas = []
    citados = insight.get("fatos") or []
    if not citados:
        problemas.append("não cita nenhum fato")
    faltando = [c for c in citados if c not in fatos]
    if faltando:
        problemas.append("cita fato inexistente: " + ", ".join(faltando))
    permitidos = [n for c in citados if c in fatos for n in fatos[c]["numeros"]]
    # Sempre permitidos: os anos do período, os 78 municípios e o 1 e o 2 dos limiares ("2 ou mais", "1 seria igual").
    permitidos += [{"valor": float(a), "unidade": "int"} for a in anos] + [{"valor": float(x), "unidade": "int"} for x in (1, 2, 78)]
    texto = " ".join(str(insight.get(k, "")) for k in ("titulo", "texto", "proxima_verificacao"))
    for valor, unidade, tol in numeros_do_texto(texto):
        if not _bate(valor, unidade, tol, permitidos):
            problemas.append(f"número sem lastro nos fatos citados: {valor:g} ({unidade})")
    proib = sorted({m.group(0).lower() for m in PALAVRAS_PROIBIDAS.finditer(texto)})
    if proib:
        problemas.append("afirma o que os dados não sustentam: " + ", ".join(proib))
    if insight.get("tipo") not in ("padrao", "sinal", "contexto"):
        problemas.append(f"tipo inválido: {insight.get('tipo')!r}")
    return problemas


# --------------------------------------------------------------- redação (Claude)
ESQUEMA_SAIDA = {
    "type": "object",
    "properties": {
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "texto": {"type": "string"},
                    "proxima_verificacao": {"type": "string"},
                    "tipo": {"type": "string", "enum": ["padrao", "sinal", "contexto"]},
                    "fatos": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["titulo", "texto", "proxima_verificacao", "tipo", "fatos"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["insights"],
    "additionalProperties": False,
}

SISTEMA = """Você escreve observações curtas sobre as redes de fornecedores da Educação nos 78 municípios do Espírito Santo, para dois públicos ao mesmo tempo: auditores do Tribunal de Contas do Estado (TCE-ES) e cidadãos sem formação técnica.

Você recebe uma lista de FATOS já calculados a partir dos dados abertos do TCE-ES (empenhos e obras de 2021 a 2025). Cada fato tem um id, um texto e os números que ele contém. Seu trabalho é juntar fatos relacionados em observações que ajudem a decidir onde olhar — não é descobrir fatos novos.

Como escrever cada observação:
- Título de até 90 caracteres que diga o padrão, não o tema.
- Texto de 2 a 4 frases, em português do Brasil, frases curtas, sem jargão; quando um termo técnico for inevitável (HHI, comunidade), diga em poucas palavras o que significa.
- Uma "próxima verificação": uma checagem concreta que um auditor poderia fazer a seguir com documentos ou dados (por exemplo, comparar preços unitários entre municípios, ler as medições de um contrato).
- O tipo: "sinal" para algo que merece verificação, "padrao" para uma estrutura do mercado, "contexto" para o que ajuda a ler os outros.
- Cite em "fatos" os ids de TODOS os fatos de onde saíram as informações.

Regras que não podem ser quebradas, porque o texto será publicado num instrumento de controle e conferido número a número:
- Use só números que aparecem nos fatos citados, escritos como no fato (formato brasileiro: R$ 6,4 mi, 72%, 2.121). Não calcule somas, diferenças, médias ou razões novas. Arredondar um número do fato é aceitável; inventar não é.
- Não afirme nem insinue irregularidade, fraude, superfaturamento, conluio, cartel, direcionamento ou crime. Ligação entre municípios, alcance grande, concentração e obra parada são padrões que pedem verificação — diga isso quando for o caso.
- Não especule sobre causas que os fatos não mostram. Se um fato traz uma limitação (um ano incompleto, pessoas físicas fora da rede), leve a limitação junto.
- Nomes de empresas e municípios exatamente como nos fatos.

Escreva de 6 a 10 observações, da mais útil para a menos útil, cobrindo temas diferentes."""


def prompt_usuario(fatos: list[dict[str, Any]]) -> str:
    enxuto = [{"id": f["id"], "tema": f["tema"], "tipo": f["tipo"], "texto": f["texto"],
               "numeros": [{"rotulo": n["rotulo"], "como_escrever": n["texto"]} for n in f["numeros"]]} for f in fatos]
    return "Fatos calculados (JSON):\n\n" + json.dumps(enxuto, ensure_ascii=False, indent=1)


def redigir(fatos: list[dict[str, Any]], modelo: str = MODELO_PADRAO, esforco: str = "high", cliente: Any = None) -> dict[str, Any]:
    """Uma chamada ao Claude com saída estruturada. Devolve as observações e a proveniência da redação."""
    import anthropic

    cliente = cliente or anthropic.Anthropic()
    usuario = prompt_usuario(fatos)
    hash_prompt = hashlib.sha256((SISTEMA + "\n\n" + usuario).encode("utf-8")).hexdigest()
    # Fallback do lado do servidor ("default"): se um classificador recusar, a API refaz a
    # chamada no modelo que a Anthropic recomenda para aquela categoria, na mesma requisição.
    resposta = cliente.beta.messages.create(
        model=modelo,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": esforco, "format": {"type": "json_schema", "schema": ESQUEMA_SAIDA}},
        system=SISTEMA,
        messages=[{"role": "user", "content": usuario}],
    )
    proveniencia = {"modelo_pedido": modelo, "modelo": getattr(resposta, "model", modelo), "esforco": esforco,
                    "id_requisicao": getattr(resposta, "_request_id", None), "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "prompt_sha256": hash_prompt, "parada": resposta.stop_reason}
    uso = getattr(resposta, "usage", None)
    if uso is not None:
        proveniencia["tokens"] = {"entrada": getattr(uso, "input_tokens", None), "saida": getattr(uso, "output_tokens", None)}
        # Houve fallback? Uma entrada "fallback_message" em usage.iterations diz que outro modelo respondeu.
        proveniencia["fallback"] = any(getattr(it, "type", None) == "fallback_message" for it in (getattr(uso, "iterations", None) or []))
    if resposta.stop_reason == "refusal":
        det = getattr(resposta, "stop_details", None)
        raise RuntimeError(f"o modelo recusou a redação (categoria: {getattr(det, 'category', None)})")
    if resposta.stop_reason == "max_tokens":
        raise RuntimeError("a redação passou do limite de tokens — reduza os fatos ou aumente max_tokens")
    texto = next((b.text for b in resposta.content if getattr(b, "type", None) == "text"), None)
    if texto is None:
        raise RuntimeError("a resposta não trouxe texto")
    return {"insights": json.loads(texto)["insights"], "proveniencia": proveniencia}


# --------------------------------------------------------------- montagem
def montar(dados: dict[str, Any], com_ia: bool = False, modelo: str = MODELO_PADRAO, esforco: str = "high",
           cliente: Any = None, anterior: dict[str, Any] | None = None) -> dict[str, Any]:
    fatos = calcular_fatos(dados)
    por_id = {f["id"]: f for f in fatos}
    hash_fatos = hashlib.sha256(json.dumps(fatos, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    saida: dict[str, Any] = {"meta": {"esquema": ESQUEMA, "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                      "fatos_sha256": hash_fatos, "redacao": None, "aviso": None},
                             "fatos": fatos, "insights": [], "recusados": []}
    if not com_ia:
        # Sem IA, a redação anterior continua valendo SE os fatos não mudaram (mesmo hash).
        if anterior and anterior.get("meta", {}).get("fatos_sha256") == hash_fatos and anterior.get("insights"):
            saida["insights"], saida["recusados"] = anterior["insights"], anterior.get("recusados", [])
            saida["meta"]["redacao"] = anterior["meta"].get("redacao")
        elif anterior and anterior.get("insights"):
            saida["meta"]["aviso"] = "os fatos mudaram desde a última redação: rode de novo com --com-ia"
        return saida
    r = redigir(fatos, modelo, esforco, cliente)
    anos = dados["meta"]["anos"]
    for ins in r["insights"]:
        ins = {**ins, "titulo": mascarar(ins["titulo"]), "texto": mascarar(ins["texto"]), "proxima_verificacao": mascarar(ins["proxima_verificacao"])}
        problemas = verificar(ins, por_id, anos)
        (saida["recusados"] if problemas else saida["insights"]).append({**ins, **({"problemas": problemas} if problemas else {})})
    saida["meta"]["redacao"] = {**r["proveniencia"], "aceitos": len(saida["insights"]), "recusados": len(saida["recusados"]),
                                "fatos_sha256": hash_fatos}
    return saida


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Insights das redes: fatos calculados e, com --com-ia, a redação pelo Claude.")
    ap.add_argument("--com-ia", action="store_true", help="redige os insights com o Claude (precisa de ANTHROPIC_API_KEY ou `ant auth login`)")
    ap.add_argument("--modelo", default=MODELO_PADRAO)
    ap.add_argument("--esforco", default="high", choices=("low", "medium", "high", "xhigh", "max"))
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if not ENTRADA.exists():
        raise SystemExit(f"{ENTRADA} não existe — rode antes `python -m financiamento.etl.grafos`")
    dados = json.loads(ENTRADA.read_text(encoding="utf-8"))
    anterior = json.loads(SAIDA.read_text(encoding="utf-8")) if SAIDA.exists() else None
    try:
        saida = montar(dados, args.com_ia, args.modelo, args.esforco, anterior=anterior)
    except Exception as exc:  # credencial ausente, rede, recusa: os fatos são gravados mesmo assim
        if not args.com_ia:
            raise
        print(f"redação não feita: {type(exc).__name__}: {exc}", file=sys.stderr)
        saida = montar(dados, False, anterior=anterior)
        saida["meta"]["aviso"] = f"a última tentativa de redação falhou ({type(exc).__name__}); a página mostra os fatos"
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    m = saida["meta"]
    print(f"{SAIDA}: {len(saida['fatos'])} fatos, {len(saida['insights'])} insights aceitos, {len(saida['recusados'])} recusados"
          + (f" — {m['aviso']}" if m.get("aviso") else ""))
    for r in saida["recusados"]:
        print(f"  recusado: {r['titulo']} — {'; '.join(r['problemas'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
