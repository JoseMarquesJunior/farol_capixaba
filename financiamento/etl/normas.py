"""Base normativa da Análise com IA: catálogo fechado de dispositivos, texto oficial, versão na data.

A IA não escreve texto de lei. Ela escolhe dispositivos DESTE catálogo (o esquema da saída só
aceita estes ids), diz a data dos fatos e explica como o dispositivo se aplica ao caso. O texto
mostrado vem da fonte oficial, na redação em vigor naquela data:

* **normas.leg.br** (Congresso Nacional, CC BY 4.0): JSON-LD estruturado, com as versões de cada
  dispositivo e a data de cada uma — Lei 14.133/2021, Lei 14.113/2020 (Fundeb), Lei 12.527/2011
  (LAI). Ex.: o art. 86, § 3º, da Lei 14.133 mudou em 22/12/2023 (Lei 14.770): antes disso um
  município não podia aderir à ata de outro município.
* **Câmara dos Deputados, legin, "texto atualizado"**: só a redação atual — Lei 8.666/1993,
  LDB, Código de Trânsito. O normas.leg.br não traz o texto estruturado destas, e o planalto.gov.br
  não responde deste ambiente.

Versões de "supressão de aplicabilidade" (MP 1.221/2024: regras suspensas em calamidade pública)
são ignoradas: não mudam o texto e não valem para o ES.

    python -m financiamento.etl.normas          # baixa as fontes e grava dados/processado/normas.json
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from functools import lru_cache
from typing import Any

from . import dossie as D
from .config import BRUTO, PROCESSADO

PASTA = BRUTO / "normas"
ARQUIVO = PROCESSADO / "normas.json"
API = "https://normas.leg.br/api/public/normas?urn={urn}&&tipo_documento=maior-detalhe"
LEGIN = "https://www2.camara.leg.br/legin/fed/lei/{caminho}-normaatualizada-pl.html"

LEIS: dict[str, dict[str, Any]] = {
    "14133": {"nome": "Lei nº 14.133/2021", "assunto": "Licitações e Contratos", "fonte": "normas", "urn": "urn:lex:br:federal:lei:2021-04-01;14133"},
    "14113": {"nome": "Lei nº 14.113/2020", "assunto": "Fundeb", "fonte": "normas", "urn": "urn:lex:br:federal:lei:2020-12-25;14113"},
    "12527": {"nome": "Lei nº 12.527/2011", "assunto": "Acesso à Informação", "fonte": "normas", "urn": "urn:lex:br:federal:lei:2011-11-18;12527"},
    "8666": {"nome": "Lei nº 8.666/1993", "assunto": "Licitações e Contratos (regime anterior)", "fonte": "legin", "legin": "1993/lei-8666-21-junho-1993-322221",
             "nota": "Revogada pelo art. 193, II, da Lei 14.133/2021; continua regendo os contratos licitados por ela (art. 191, parágrafo único)."},
    "9394": {"nome": "Lei nº 9.394/1996", "assunto": "LDB", "fonte": "legin", "legin": "1996/lei-9394-20-dezembro-1996-362578"},
    "9503": {"nome": "Lei nº 9.503/1997", "assunto": "Código de Trânsito Brasileiro", "fonte": "legin", "legin": "1997/lei-9503-23-setembro-1997-372348"},
}

#: (id, lei, partes, quando usar). Cada parte é um caminho de dispositivo; "!" no fim = só o nó, sem os filhos.
CATALOGO: list[tuple[str, str, list[str], str]] = [
    ("14133.art9.I", "14133", ["art9_cpt!", "art9_cpt_inc1"], "cláusula do edital que restringe a competição ou é impertinente ao objeto"),
    ("14133.art23", "14133", ["art23_cpt"], "valor estimado e pesquisa de preços compatível com o mercado"),
    ("14133.art72", "14133", ["art72"], "instrução do processo de contratação direta (dispensa ou inexigibilidade)"),
    ("14133.art74", "14133", ["art74_cpt"], "inexigibilidade de licitação"),
    ("14133.art75.II", "14133", ["art75_cpt!", "art75_cpt_inc2"], "dispensa por valor em compras e serviços"),
    ("14133.art75.VIII", "14133", ["art75_cpt!", "art75_cpt_inc8"], "contratação emergencial"),
    ("14133.art75.§1", "14133", ["art75_par1"], "fracionamento: somatório das despesas do mesmo objeto no exercício"),
    ("14133.art84", "14133", ["art84"], "vigência da ata de registro de preços"),
    ("14133.art86.§2", "14133", ["art86_par2"], "requisitos da adesão à ata por órgão não participante (carona)"),
    ("14133.art86.§3", "14133", ["art86_par3"], "quem pode aderir à ata de quem (municipal × estadual/federal)"),
    ("14133.art86.§4", "14133", ["art86_par4"], "limite de 50% por órgão aderente"),
    ("14133.art86.§5", "14133", ["art86_par5"], "limite do dobro do quantitativo para o conjunto das adesões"),
    ("14133.art91", "14133", ["art91_cpt"], "forma escrita, juntada ao processo e divulgação do contrato e dos aditivos"),
    ("14133.art94", "14133", ["art94_cpt"], "divulgação no PNCP como condição de eficácia do contrato, e prazos"),
    ("14133.art95", "14133", ["art95_cpt"], "quando o instrumento de contrato é obrigatório e quando a nota de empenho o substitui"),
    ("14133.art106", "14133", ["art106"], "duração de serviços contínuos (até 5 anos)"),
    ("14133.art107", "14133", ["art107"], "prorrogação de serviços contínuos (até 10 anos)"),
    ("14133.art117", "14133", ["art117_cpt"], "fiscal do contrato designado"),
    ("14133.art124", "14133", ["art124_cpt"], "hipóteses de alteração do contrato"),
    ("14133.art125", "14133", ["art125_cpt"], "limite de acréscimos e supressões (25%; 50% em reforma)"),
    ("14133.art136", "14133", ["art136"], "apostila: reajuste e o que não é alteração do contrato"),
    ("14133.art191", "14133", ["art191"], "opção pelo regime da Lei 8.666 durante a transição e regência do contrato"),
    ("8666.art15.II", "8666", ["art15_cpt!", "art15_cpt_inc2"], "registro de preços no regime anterior"),
    ("8666.art24.II", "8666", ["art24_cpt!", "art24_cpt_inc2"], "dispensa por valor no regime anterior"),
    ("8666.art24.IV", "8666", ["art24_cpt!", "art24_cpt_inc4"], "emergência no regime anterior"),
    ("8666.art25", "8666", ["art25_cpt!"], "inexigibilidade no regime anterior"),
    ("8666.art26", "8666", ["art26_cpt"], "justificativa e publicação da dispensa e da inexigibilidade no regime anterior"),
    ("8666.art57.II", "8666", ["art57_cpt!", "art57_cpt_inc2"], "prorrogação de serviços contínuos no regime anterior (até 60 meses)"),
    ("8666.art61.pu", "8666", ["art61_par1u"], "publicação resumida do contrato na imprensa oficial no regime anterior"),
    ("8666.art65.§1", "8666", ["art65_par1"], "limite de acréscimos e supressões no regime anterior"),
    ("8666.art65.§8", "8666", ["art65_par8"], "reajuste por apostila no regime anterior"),
    ("8666.art67", "8666", ["art67_cpt"], "fiscal do contrato no regime anterior"),
    ("9394.art70.VIII", "9394", ["art70_cpt!", "art70_cpt_inc8"], "transporte escolar como manutenção e desenvolvimento do ensino (MDE)"),
    ("14113.art25", "14113", ["art25_cpt"], "uso dos recursos do Fundeb em MDE"),
    ("12527.art8.§1.IV", "12527", ["art8_cpt!", "art8_par1!", "art8_par1_inc4"], "transparência ativa de licitações e contratos (documento faltante)"),
    ("9503.art136", "9503", ["art136"], "requisitos dos veículos de transporte escolar"),
    ("9503.art138", "9503", ["art138"], "requisitos do condutor de transporte escolar"),
]
IDS = [c[0] for c in CATALOGO]

NAO_VIGENTE = re.compile(r"^\(?\s*(suprimid|vetad|revogad)", re.I)


# ------------------------------------------------------------------ rótulos
def _romano(n: int) -> str:
    r, s = "", n
    for v, l in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while s >= v:
            r, s = r + l, s - v
    return r


def _ordinal(n: str) -> str:
    return n + "º" if n.isdigit() and int(n) < 10 else n


def rotulo_no(caminho: str) -> tuple[str, str]:
    """('par', '§ 3º'), ('inc', 'II –'), ('ali', 'a)'), ('cpt', 'Art. 86.')."""
    ult = caminho.split("_")[-1]
    m = re.fullmatch(r"([a-z]+)(\d*)(u?)", ult)
    tipo, n, u = (m.group(1), m.group(2), m.group(3)) if m else (ult, "", "")
    if tipo == "cpt":
        a = re.match(r"art(\d+)", caminho).group(1)
        return "cpt", f"Art. {_ordinal(a)}" + ("" if int(a) < 10 else ".")
    if tipo == "par":
        return "par", "Parágrafo único." if u else f"§ {_ordinal(n)}"
    if tipo == "inc":
        return "inc", _romano(int(n)) + " –"
    if tipo == "ali":
        return "ali", chr(96 + int(n)) + ")"
    if tipo == "ite":
        return "ite", n + "."
    return tipo, ""


def rotulo_citacao(lei: str, partes: list[str]) -> str:
    """'Lei nº 14.133/2021, art. 86, § 3º' — do caminho mais específico."""
    alvo = max((p.rstrip("!") for p in partes), key=lambda p: p.count("_"))
    pedacos = []
    for tok in alvo.split("_"):
        m = re.fullmatch(r"([a-z]+)(\d*)(u?)", tok)
        t, n, u = m.groups()
        if t == "art":
            pedacos.append(f"art. {_ordinal(n)}")
        elif t == "par":
            pedacos.append("parágrafo único" if u else f"§ {_ordinal(n)}")
        elif t == "inc":
            pedacos.append(f"inciso {_romano(int(n))}")
        elif t == "ali":
            pedacos.append(f"alínea \"{chr(96 + int(n))}\"")
    return LEIS[lei]["nome"] + ", " + ", ".join(pedacos)


# ------------------------------------------------------------------ fontes
def _limpo(s: str) -> str:
    """Sem marcação (o normas.leg.br põe <span xlink:href> nas remissões; a Câmara, <font>)."""
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", s))).strip()
    return re.sub(r"\s+([,.;:)])", r"\1", t)


def _arvore_normas(dados: dict) -> dict[str, dict]:
    """JSON-LD do normas.leg.br → {caminho: {versoes: [(data, tipo, texto)], id_oficial}} na ordem do texto."""
    nos: dict[str, dict] = {}

    def andar(no: Any) -> None:
        if isinstance(no, list):
            for x in no:
                andar(x)
            return
        if not isinstance(no, dict):
            return
        ident = no.get("legislationIdentifier") or ""
        if "!" in ident:
            bruto = ident.split("!", 1)[1]
            cam = re.sub(r",[^_]*", "", bruto)        # 'art86_par3_inc1,lei-14770-2023-12-22' → 'art86_par3_inc1'
            w = no.get("workExample")
            w = w if isinstance(w, list) else [w] if w else []
            if cam.startswith("art"):
                nos[cam] = {"id_oficial": ident, "versoes": [(x.get("legislationDate"), x.get("legislationType") or "", _limpo(x.get("text") or "")) for x in w]}
        andar(no.get("hasPart"))

    andar(dados.get("hasPart"))
    return nos


_ROTULO_LEGIN = re.compile(r"^(?:Art\.\s*(\d+)[º°o]?\s*[-–.]?|§\s*(\d+)[º°o]?\s*[-–.]?|Parágrafo\s+único\.?\s*[-–]?|([IVXLC]+)\s*[-–]|([a-z])\))\s*")


def _arvore_legin(corpo: bytes) -> dict[str, dict]:
    """HTML do "texto atualizado" da Câmara (um <p> por dispositivo) → a mesma árvore, com uma versão só."""
    t = corpo.decode("utf-8", errors="replace")
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?is)<(strike|s|del)\b[^>]*>.*?</\1>", " ", t)          # redação revogada riscada
    paragrafos = [_limpo(p) for p in re.split(r"(?i)<p\b[^>]*>", t)]
    nos: dict[str, dict] = {}
    art = par = inc = None
    for p in paragrafos:
        if not p:
            continue
        m = _ROTULO_LEGIN.match(p)
        if not m:
            continue
        texto = p[m.end():].strip()
        if m.group(1):
            art, par, inc = f"art{int(m.group(1))}", None, None
            cam = art + "_cpt"
            nos.setdefault(art, {"versoes": [(None, "", "")]})
        elif art is None:
            continue
        elif m.group(2) or p.startswith("Parágrafo"):
            par, inc = (f"{art}_par{int(m.group(2))}" if m.group(2) else f"{art}_par1u"), None
            cam = par
        elif m.group(3):
            inc = f"{par or art + '_cpt'}_inc{_numero_romano(m.group(3))}"
            cam = inc
        elif m.group(4) and inc:
            cam = f"{inc}_ali{ord(m.group(4)) - 96}"
        else:
            continue
        if cam in nos:      # o mesmo rótulo de novo (texto de lei alterada citado em nota): fica o primeiro
            continue
        nos[cam] = {"versoes": [(None, "", texto)]}
    return nos


def _numero_romano(s: str) -> int:
    v = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    for i, ch in enumerate(s):
        total += -v[ch] if i + 1 < len(s) and v[ch] < v[s[i + 1]] else v[ch]
    return total


def _url_publica(lei: str, caminho: str = "") -> str:
    L = LEIS[lei]
    if L["fonte"] == "normas":
        return "https://normas.leg.br/?urn=" + L["urn"] + ("!" + caminho if caminho else "")
    return LEGIN.format(caminho=L["legin"])


# ------------------------------------------------------------------ versão na data
def _texto_na_data(versoes: list, data: str | None) -> tuple[str | None, str | None]:
    """(texto, desde) do dispositivo na data; (None, None) se não estava em vigor."""
    validas = [v for v in versoes if "Applicability_Suppression" not in v[1]]
    if data:
        validas = [v for v in validas if v[0] is None or v[0] <= data]
    if not validas:
        return None, None
    d, tipo, texto = validas[-1]
    if NAO_VIGENTE.match(texto or "") or tipo.startswith(("Suppression", "Revocation", "Vetoed")):
        return None, d
    return texto, d


def _subarvore(nos: dict[str, dict], parte: str) -> list[str]:
    so = parte.endswith("!")
    raiz = parte.rstrip("!")
    if so:
        return [raiz] if raiz in nos else []
    return [c for c in nos if c == raiz or c.startswith(raiz + "_")]


def montar_texto(nos: dict[str, dict], partes: list[str], data: str | None) -> dict[str, Any]:
    linhas, desde, datas, ausentes = [], None, set(), []
    for parte in partes:
        cams = _subarvore(nos, parte)
        if not cams:
            ausentes.append(parte)
        if cams and re.fullmatch(r"art\d+", cams[0]):
            cams = cams[1:]          # o nó do artigo é só um contêiner, sem texto
        for cam in cams:
            versoes = nos[cam]["versoes"]
            datas |= {v[0] for v in versoes if v[0] and "Applicability_Suppression" not in v[1]}
            texto, d = _texto_na_data(versoes, data)
            if not texto:
                if cam == parte.rstrip("!"):
                    ausentes.append(parte)
                continue
            tipo, rot = rotulo_no(cam)
            recuo = {"inc": "  ", "ali": "    ", "ite": "      "}.get(tipo, "")
            linhas.append(f"{recuo}{rot} {texto}".rstrip())
            if d and (desde is None or d > desde):
                desde = d
    return {"texto": "\n".join(linhas), "desde": desde, "versoes": sorted(datas), "ausentes": ausentes}


# ------------------------------------------------------------------ coleta
def item(ident: str, lei: str, partes: list[str], quando: str, nos: dict[str, dict]) -> dict[str, Any]:
    L = LEIS[lei]
    return {"id": ident, "lei": lei, "lei_nome": L["nome"], "assunto": L["assunto"], "partes": partes, "quando": quando,
            "rotulo": rotulo_citacao(lei, partes), "url": _url_publica(lei, partes[-1].rstrip("!")), "nota": L.get("nota"),
            "fonte": "normas.leg.br (versões datadas)" if L["fonte"] == "normas" else "Câmara dos Deputados, texto atualizado (só a redação atual)",
            "versionado": L["fonte"] == "normas", "nos": nos}


def coletar(atualizar: bool = False) -> dict[str, Any]:
    """Baixa as leis (cache cru com SHA-256), monta cada dispositivo do catálogo e grava normas.json."""
    col = D.Coletor("_normas", atualizar=atualizar)
    arvores, fontes = {}, {}
    for lei, L in LEIS.items():
        if L["fonte"] == "normas":
            st, corpo, meta = col.get(f"{lei}.json", API.format(urn=L["urn"]), timeout=180, tentativas=3, pasta=PASTA)
            dados = D._json(corpo) if st == 200 else None
            arvores[lei] = _arvore_normas(dados) if isinstance(dados, dict) else {}
        else:
            st, corpo, meta = col.get(f"{lei}.html", LEGIN.format(caminho=L["legin"]), timeout=180, tentativas=3, pasta=PASTA)
            arvores[lei] = _arvore_legin(corpo) if st == 200 else {}
        fontes[lei] = {"url": meta.get("url"), "status": st, "sha256": meta.get("sha256"), "obtido_em": meta.get("obtido_em"), "arquivo": meta.get("arquivo"),
                       "dispositivos": len(arvores[lei])}
    itens = {ident: item(ident, lei, partes, quando, {c: arvores[lei][c] for p in partes for c in _subarvore(arvores[lei], p)})
             for ident, lei, partes, quando in CATALOGO}
    saida = {"gerado_em": D._agora(), "fontes": fontes, "itens": itens}
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    carregar.cache_clear()
    return saida


@lru_cache(maxsize=1)
def carregar() -> dict[str, Any]:
    if not ARQUIVO.exists():
        return coletar()
    return json.loads(ARQUIVO.read_text(encoding="utf-8"))


def _data_iso(s: str | None) -> str | None:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def resolver(ident: str, data: str | None) -> dict[str, Any] | None:
    """O dispositivo na redação em vigor na data (ISO ou dd/mm/aaaa); None se o id não existe."""
    it = carregar()["itens"].get(ident)
    if it is None:
        return None
    iso = _data_iso(data)
    t = montar_texto(it["nos"], it["partes"], iso if it["versionado"] else None)
    return {k: it[k] for k in ("id", "rotulo", "url", "fonte", "versionado", "nota", "lei_nome")} | {
        "data_referencia": iso, "texto": t["texto"], "redacao_desde": t["desde"], "versoes": t["versoes"],
        "em_vigor": bool(t["texto"]) and not t["ausentes"], "ausentes": t["ausentes"]}


def para_ia() -> str:
    """O catálogo como a IA o recebe: id, rótulo, quando usar e o texto (com as versões, quando mudou)."""
    blocos = []
    for ident, lei, partes, quando in CATALOGO:
        it = carregar()["itens"].get(ident)
        if it is None:
            continue
        atual = montar_texto(it["nos"], partes, None)
        bloco = f"[{ident}] {it['rotulo']} — usar para: {quando}."
        if it.get("nota"):
            bloco += " " + it["nota"]
        datas = atual["versoes"]
        if it["versionado"] and len(datas) > 1:
            for d in datas:
                v = montar_texto(it["nos"], partes, d)
                bloco += f"\n  Redação em vigor a partir de {d}:\n" + _recuar(v["texto"] or "(não estava em vigor)")
        else:
            bloco += "\n" + _recuar(atual["texto"] or "(texto indisponível na fonte)")
        blocos.append(bloco)
    return "\n\n".join(blocos)


def _recuar(t: str) -> str:
    return "\n".join("    " + l for l in t.splitlines())


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(errors="replace")
    s = coletar(atualizar="--atualizar" in sys.argv)
    for lei, f in s["fontes"].items():
        print(f"{LEIS[lei]['nome']}: HTTP {f['status']}, {f['dispositivos']} dispositivos")
    for ident in IDS:
        r = resolver(ident, None)
        print(("OK  " if r["em_vigor"] else "FALTA ") + ident, "|", r["rotulo"], "|", r["texto"][:110].replace("\n", " / "), r["ausentes"] or "")
