"""Análise com IA do dossiê de uma empresa — o botão "Análise com IA" do dossiê.

Fluxo, com o que custa e o que não custa:

1. **Documentos** (`baixar_documentos`, sem IA): baixa os documentos do inventário do
   dossiê — contratos, publicações, editais, arquivos do PNCP — para
   ``dados/bruto/analises/<raiz>/docs/``, com URL, instante e SHA-256, e extrai o texto
   (pypdf; HTML vira texto). PDF sem texto é marcado como escaneado.
2. **Estimativa** (`preparar` + `estimar`, sem gerar texto): monta o pedido dentro de um
   orçamento (texto até 24 mil caracteres por documento e 300 mil no total; até 36 páginas
   escaneadas, que o modelo lê como imagem) e conta os tokens — pela API de contagem, que
   não cobra, quando há credencial; por estimativa, quando não há.
3. **Análise** (`analisar`): uma chamada ao Claude (``claude-opus-5-5``, saída estruturada,
   fallback de recusa do lado do servidor). O resultado é **gravado e reaproveitado**: a
   chave é o hash do pedido inteiro (modelo, instruções, dossiê, documentos). Pedir de novo
   com o mesmo pedido devolve o gravado, sem tokens. Só ``refazer=True`` chama a API de novo,
   e a análise anterior continua no histórico.
4. **Conferência** (`conferir`): cada trecho citado como evidência é procurado no texto do
   documento citado; cada número do texto, nos números do dossiê e dos documentos citados.
   Texto que afirma irregularidade é recusado. Documento escaneado fica "não conferível".

A chave da API fica só no servidor local (variável ANTHROPIC_API_KEY ou `ant auth login`);
a página nunca a vê. CPF digitado no texto dos documentos é mascarado antes do envio — o de
documento escaneado não dá para mascarar, e o resultado avisa.
"""

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import dossie as D
from . import normas as N
from .insights import PALAVRAS_PROIBIDAS, _bate, mascarar, numeros_do_texto

MODELO_PADRAO = "claude-opus-5-5"
ESFORCO_PADRAO = "high"
LIMITE_DOCS = 30
CHARS_POR_DOC = 24_000
CHARS_TOTAL = 300_000
PAGINAS_ESCANEADAS = 36
PAGINAS_POR_ESCANEADO = 12
#: Preço por milhão de tokens (entrada, saída), da tabela de modelos da API (out/2026).
PRECOS = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50), "claude-fable-5-1": (10.0, 50.0)}
Progresso = Callable[[str], None]


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def pasta_ia(raiz: str) -> Path:
    return D.PASTA_RESULTADOS / raiz / "ia"


# ------------------------------------------------------------------ documentos
def _texto_html(corpo: bytes) -> str:
    t = corpo.decode("utf-8", errors="replace")
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def _texto_pdf(corpo: bytes) -> tuple[str, int, int]:
    """(texto, páginas, páginas com texto)."""
    from pypdf import PdfReader
    r = PdfReader(io.BytesIO(corpo))
    partes, com_texto = [], 0
    for i, p in enumerate(r.pages, 1):
        t = (p.extract_text() or "").strip()
        if len(t) > 200:
            com_texto += 1
        partes.append(f"[página {i}]\n{t}")
    return "\n\n".join(partes), len(r.pages), com_texto


def baixar_documentos(dossie: dict[str, Any], limite: int = LIMITE_DOCS, progresso: Progresso | None = None,
                      atualizar: bool = False) -> list[dict[str, Any]]:
    """Baixa (ou lê do cache) os primeiros `limite` documentos do inventário e extrai o texto."""
    raiz = dossie["meta"]["raiz"]
    col = D.Coletor(raiz, atualizar=atualizar)
    pasta = D.PASTA_CRUS / raiz / "docs"
    saida = []
    inv = dossie.get("documentos") or []
    for n, doc in enumerate(inv[:limite], 1):
        if progresso:
            progresso(f"Documento {n} de {min(limite, len(inv))}: {doc['tipo']} — {doc['municipio'] or doc['referencia'][:40]}")
        st, corpo, meta = col.get(doc["id"] + ".bin", doc["url"], timeout=90, tentativas=2, pasta=pasta)
        d = {**doc, "status": st, "sha256": meta.get("sha256"), "bytes": len(corpo), "arquivo": meta.get("arquivo"), "obtido_em": meta.get("obtido_em"),
             "formato": None, "paginas": None, "paginas_com_texto": None, "escaneado": False, "texto_arquivo": None, "erro": meta.get("erro")}
        if st == 200 and corpo:
            try:
                if corpo[:5] == b"%PDF-":
                    texto, pags, com = _texto_pdf(corpo)
                    d.update(formato="pdf", paginas=pags, paginas_com_texto=com, escaneado=com == 0)
                elif b"<html" in corpo[:2000].lower() or b"<!doctype" in corpo[:200].lower():
                    texto = _texto_html(corpo)
                    d.update(formato="html")
                else:
                    texto = ""
                    d.update(formato="outro")
                if texto:
                    tp = pasta / (doc["id"] + ".txt")
                    tp.write_text(texto, encoding="utf-8")
                    d["texto_arquivo"] = str(tp)
                    d["caracteres"] = len(texto)
            except Exception as exc:
                d["erro"] = f"{type(exc).__name__}: {exc}"[:200]
        saida.append(d)
    return saida


def _ler_texto(doc: dict) -> str:
    return Path(doc["texto_arquivo"]).read_text(encoding="utf-8") if doc.get("texto_arquivo") else ""


# ------------------------------------------------------------------ pedido
#: Regras da base normativa: as mesmas na análise e no complemento de uma análise antiga.
REGRAS_NORMAS = """- Base normativa: o documento "normas" é um catálogo de dispositivos legais com o texto oficial (e a redação de cada época, quando mudou). Em cada constatação do tipo "sinal", indique em "normas" pelo menos um dispositivo do catálogo que o auditor deve confrontar com o caso; nas de tipo "padrao" e "contexto", quando houver. Use só ids do catálogo e não cite outra norma no texto.
- "data_referencia" é a data do fato a que o dispositivo se aplica (assinatura do contrato ou do aditivo, publicação do edital), copiada do resumo ou do documento, no formato AAAA-MM-DD. O dispositivo será mostrado na redação em vigor nessa data.
- Escolha a lei do regime do contrato: a Lei 8.666 se o contrato foi licitado por ela (art. 191 da Lei 14.133), a Lei 14.133 nos demais. Se o regime não estiver claro nos dados, diga isso em "aplicacao" e indique os dispositivos dos dois regimes.
- "aplicacao": duas ou três frases — o que o dispositivo exige e o que, neste caso concreto, precisa ser verificado para saber se foi cumprido. Não conclua que houve descumprimento. Os valores de dispensa da Lei 14.133 são atualizados todo ano por decreto (art. 182): não trate o valor do texto da lei como o limite vigente.
"""

SISTEMA = """Você analisa o dossiê de uma empresa fornecedora de municípios do Espírito Santo, para auditores do Tribunal de Contas do Estado (TCE-ES). Você recebe: (1) um resumo estruturado com o que os dados abertos dizem da empresa — contratos no TCE-ES com modalidade e base legal, sinais estruturados (adesão a ata, emergência, dispensa, inexigibilidade), empenhos por município e ano, obras com medições e aditivos, preços unitários comparados com outros municípios, cadastro na Receita, sanções e publicações no PNCP; (2) o texto ou as páginas de documentos (contratos, editais, publicações), cada um com um id.

Seu trabalho é ler os documentos à luz do resumo e apontar o que um auditor deveria verificar primeiro — e por quê. Exemplos do que procurar: objeto do edital que restringe a competição; exigência de habilitação desproporcional; prazo de vigência e prorrogações; valor do contrato diferente do registrado; aditivo de valor alto; contratação emergencial repetida; adesão a ata de outro órgão; preço unitário muito acima do de outros municípios; capital social ou data de abertura incompatíveis com o porte dos contratos; atividade econômica (CNAE) que não corresponde ao objeto.

Regras que não podem ser quebradas, porque o texto vai para um instrumento de controle e será conferido:
- Toda constatação cita evidências: o id do documento, a página (0 quando não houver ou não souber), e um trecho COPIADO LITERALMENTE do documento (até 300 caracteres). Constatação que vem só do resumo estruturado cita o documento "resumo" e copia o trecho do resumo.
- Use só números que estão no resumo ou nos documentos. Não calcule somas, médias ou percentuais novos.
- Não afirme nem insinue irregularidade, fraude, superfaturamento, conluio, cartel, direcionamento ou crime. Descreva o padrão e diga o que verificar. Quem conclui é o auditor.
- Se os documentos forem poucos, ilegíveis ou não sustentarem uma conclusão, diga isso em "limites".
- O resumo traz "documentos_faltantes": contratos cujo documento não foi obtido, e o que a busca no PNCP e no Diário Oficial achou. Em "limites", nomeie os contratos de maior valor que ficaram sem documento (município e número) e diga o que pedir ao órgão (contrato, aditivos, processo de origem). Um extrato achado no Diário Oficial não substitui o contrato: diga o que ele confirma e o que não.
""" + REGRAS_NORMAS + """- Português do Brasil, frases curtas; termo técnico explicado em poucas palavras."""

NORMAS_SAIDA = {"type": "array", "items": {"type": "object", "properties": {
    "dispositivo": {"type": "string", "enum": N.IDS}, "data_referencia": {"type": "string"}, "aplicacao": {"type": "string"}},
    "required": ["dispositivo", "data_referencia", "aplicacao"], "additionalProperties": False}}

ESQUEMA_SAIDA = {
    "type": "object",
    "properties": {
        "resumo": {"type": "string"},
        "constatacoes": {"type": "array", "items": {"type": "object", "properties": {
            "titulo": {"type": "string"},
            "texto": {"type": "string"},
            "tipo": {"type": "string", "enum": ["sinal", "padrao", "contexto"]},
            "evidencias": {"type": "array", "items": {"type": "object", "properties": {
                "documento": {"type": "string"}, "pagina": {"type": "integer"}, "trecho": {"type": "string"}},
                "required": ["documento", "pagina", "trecho"], "additionalProperties": False}},
            "proxima_verificacao": {"type": "string"}, "normas": NORMAS_SAIDA},
            "required": ["titulo", "texto", "tipo", "evidencias", "proxima_verificacao", "normas"], "additionalProperties": False}},
        "limites": {"type": "array", "items": {"type": "string"}},
        "documentos_lidos": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["resumo", "constatacoes", "limites", "documentos_lidos"],
    "additionalProperties": False,
}


def resumo_dossie(d: dict[str, Any]) -> dict[str, Any]:
    """O que vai para o modelo do dossiê: enxuto, sem URL de fonte nem dado pessoal de sócio além do nome."""
    c = d.get("contratos") or {}
    contratos = [{k: x.get(k) for k in ("municipio", "numero", "objeto", "modalidade", "base_legal", "arp", "assinatura", "vigencia", "valor_inicial", "valor_atual", "sinal")}
                 for x in (c.get("contratos") or [])[:120]]
    cad = d.get("cadastro") or {}
    return {
        "empresa": d["meta"].get("nome"), "cnpj": D.fmt_cnpj(d["meta"].get("cnpj_consultado", "")),
        "cadastro": {k: cad.get(k) for k in ("razao_social", "data_inicio_atividade", "situacao", "cnae", "capital_social", "porte", "natureza_juridica", "municipio", "uf")}
                    | {"socios": [{"nome": s.get("nome"), "qualificacao": s.get("qualificacao"), "desde": s.get("desde")} for s in cad.get("socios", [])]} if cad.get("status") == "ok" else {"status": cad.get("status")},
        "sancoes": {k: (v.get("registros") if isinstance(v, dict) else v) for k, v in (d.get("sancoes") or {}).items()},
        "tcu": [(x.get("tipo"), x.get("situacao")) for x in (d.get("tcu") or {}).get("certidoes", [])],
        "empenhos_educacao": {k: (d.get("rede") or {}).get(k) for k in ("empenhado", "por_ano", "por_municipio", "por_mercado")},
        "contratos_tcees": {"resumo": c.get("resumo"), "contratos": contratos},
        "obras": [{k: o.get(k) for k in ("municipio", "objeto", "situacao", "valor", "valor_medido", "pct_medido", "aditivos", "ultima_medicao")} for o in d.get("obras") or []],
        "precos_comparados": {k: (d.get("precos") or {}).get(k) for k in ("itens_da_empresa", "comparaveis_total", "acima_2x", "regra")}
                             | {"maiores_diferencas": [{k: x.get(k) for k in ("descricao", "unidade", "municipio", "ano", "preco", "mediana_outros", "razao", "municipios_outros")}
                                                      for x in (d.get("precos") or {}).get("comparaveis", [])[:15]]},
        "pncp": [{k: x.get(k) for k in ("titulo", "objeto", "municipio", "ano", "valor", "modalidade", "amparo", "vigencia")} for x in (d.get("pncp") or {}).get("contratos", [])[:30]],
        "diarios": [{k: x.get(k) for k in ("municipio", "data", "trechos")} for x in (d.get("diarios") or {}).get("mencoes", [])[:10]],
        "documentos_faltantes": documentos_faltantes(d),
    }


def documentos_faltantes(d: dict[str, Any]) -> dict[str, Any]:
    """Que contratos ficaram sem documento para ler — e o que a busca achou ou não."""
    cs = (d.get("contratos") or {}).get("contratos") or []
    sem = [x for x in cs if not D.especifico(x.get("url_contrato")) and not D.especifico(x.get("url_publicacao"))]
    f = d.get("faltantes") or {}
    return {"contratos_sem_documento_no_tcees": [{k: x.get(k) for k in ("municipio", "numero", "valor_atual")} for x in sem[:30]],
            "busca_feita": bool(f),
            "busca": [{"municipio": r["contrato"]["municipio"], "numero": r["contrato"]["numero"], "situacao": r["situacao"],
                       "rotas": [{"rota": x["rota"], "situacao": x["situacao"], "detalhe": x.get("detalhe")} for x in r["rotas"]]}
                      for r in f.get("itens") or []]}


def preparar(dossie: dict[str, Any], docs: list[dict[str, Any]]) -> dict[str, Any]:
    """O pedido dentro do orçamento: quais documentos entram, como, e a chave do cache."""
    resumo = resumo_dossie(dossie)
    texto_resumo = mascarar(json.dumps(resumo, ensure_ascii=False, indent=1, default=str))
    catalogo = N.para_ia()
    conteudo: list[dict[str, Any]] = [{"type": "text", "text": "Documento \"resumo\" — resumo estruturado do dossiê (JSON):\n\n" + texto_resumo},
                                      {"type": "text", "text": "Documento \"normas\" — catálogo de dispositivos legais (texto oficial):\n\n" + catalogo}]
    usados, fora, chars, pags_img = [], [], len(texto_resumo) + len(catalogo), 0
    for doc in docs:
        motivo = None
        if doc.get("status") != 200:
            motivo = f"não baixou (HTTP {doc.get('status')}{', ' + doc['erro'] if doc.get('erro') else ''})"
        elif doc.get("escaneado"):
            if (doc.get("paginas") or 0) > PAGINAS_POR_ESCANEADO:
                motivo = f"escaneado com {doc['paginas']} páginas (limite {PAGINAS_POR_ESCANEADO})"
            elif pags_img + (doc.get("paginas") or 0) > PAGINAS_ESCANEADAS:
                motivo = "orçamento de páginas escaneadas esgotado"
        elif not doc.get("texto_arquivo"):
            motivo = "sem texto extraível"
        elif chars >= CHARS_TOTAL:
            motivo = "orçamento de texto esgotado"
        if motivo:
            fora.append({"id": doc["id"], "tipo": doc["tipo"], "referencia": doc["referencia"], "motivo": motivo})
            continue
        cab = f"Documento \"{doc['id']}\" — {doc['tipo']}; {doc['referencia']}; origem {doc['origem']}; {doc['url_original']}"
        if doc.get("escaneado"):
            pdf = (D.BRUTO / doc["arquivo"]).read_bytes()
            conteudo.append({"type": "text", "text": cab + " (PDF escaneado: leia as páginas abaixo)"})
            conteudo.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64.standard_b64encode(pdf).decode("ascii")}})
            pags_img += doc.get("paginas") or 0
            usados.append({**_enxuto(doc), "modo": "páginas como imagem"})
        else:
            texto = mascarar(_ler_texto(doc))
            corte = min(CHARS_POR_DOC, CHARS_TOTAL - chars)
            trecho = texto[:corte]
            conteudo.append({"type": "text", "text": cab + (f" (texto cortado em {corte} de {len(texto)} caracteres)" if len(texto) > corte else "") + "\n\n" + trecho})
            chars += len(trecho)
            usados.append({**_enxuto(doc), "modo": "texto", "caracteres_enviados": len(trecho), "caracteres_total": len(texto)})
    conteudo.append({"type": "text", "text": "Analise a empresa conforme as instruções. Cite as evidências pelos ids acima."})
    assinatura = json.dumps({"sistema": SISTEMA, "esquema": ESQUEMA_SAIDA, "resumo": texto_resumo, "normas": catalogo,
                             "docs": [(u["id"], u.get("sha256"), u.get("caracteres_enviados")) for u in usados]}, ensure_ascii=False, sort_keys=True)
    return {"conteudo": conteudo, "usados": usados, "fora": fora, "caracteres_texto": chars, "paginas_imagem": pags_img,
            "hash_pedido": hashlib.sha256(assinatura.encode("utf-8")).hexdigest(), "resumo": resumo}


def _enxuto(doc: dict) -> dict:
    return {k: doc.get(k) for k in ("id", "tipo", "referencia", "municipio", "origem", "url", "url_original", "sha256", "paginas", "escaneado", "arquivo", "obtido_em")}


def _params(pedido: dict, modelo: str, esforco: str) -> dict[str, Any]:
    return {"model": modelo, "system": SISTEMA, "messages": [{"role": "user", "content": pedido["conteudo"]}],
            "output_config": {"effort": esforco, "format": {"type": "json_schema", "schema": ESQUEMA_SAIDA}}}


def credencial_disponivel() -> bool:
    import os
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or Path.home().joinpath(".config", "anthropic").exists())


def estimar(pedido: dict, modelo: str = MODELO_PADRAO, esforco: str = ESFORCO_PADRAO, cliente: Any = None) -> dict[str, Any]:
    """Tokens de entrada (contados pela API, sem custo, quando há credencial) e o custo provável."""
    entrada, metodo = None, "estimativa (3,6 caracteres por token; 1.800 tokens por página escaneada)"
    if cliente is not None or credencial_disponivel():
        try:
            import anthropic
            cliente = cliente or anthropic.Anthropic()
            r = cliente.beta.messages.count_tokens(**_params(pedido, modelo, esforco))
            entrada, metodo = r.input_tokens, "contado pela API (count_tokens)"
        except Exception as exc:
            metodo += f"; a contagem pela API falhou ({type(exc).__name__})"
    if entrada is None:
        entrada = int(pedido["caracteres_texto"] / 3.6 + pedido["paginas_imagem"] * 1800 + len(SISTEMA) / 3.6)
    saida = 12_000  # resposta + raciocínio, típico desta tarefa
    pe, ps = PRECOS.get(modelo, PRECOS[MODELO_PADRAO])
    return {"modelo": modelo, "tokens_entrada": entrada, "tokens_saida_previstos": saida, "metodo": metodo,
            "custo_usd": round(entrada * pe / 1e6 + saida * ps / 1e6, 2), "documentos_usados": len(pedido["usados"]),
            "documentos_fora": len(pedido["fora"]), "paginas_imagem": pedido["paginas_imagem"], "caracteres_texto": pedido["caracteres_texto"]}


# ------------------------------------------------------------------ cache das análises
def historico(raiz: str) -> list[dict[str, Any]]:
    p = pasta_ia(raiz)
    if not p.exists():
        return []
    itens = []
    for f in sorted(p.glob("*.json"), reverse=True):
        try:
            x = json.loads(f.read_text(encoding="utf-8"))
            itens.append({"arquivo": f.name, "gerado_em": x["meta"]["gerado_em"], "modelo": x["meta"]["modelo"], "hash_pedido": x["meta"]["hash_pedido"],
                          "custo_usd": x["meta"].get("custo_usd"), "constatacoes": len(x.get("constatacoes", []))})
        except (ValueError, KeyError):
            continue
    return itens


def ultima(raiz: str) -> dict[str, Any] | None:
    h = historico(raiz)
    return json.loads((pasta_ia(raiz) / h[0]["arquivo"]).read_text(encoding="utf-8")) if h else None


def gravada(raiz: str, hash_pedido: str) -> dict[str, Any] | None:
    for h in historico(raiz):
        if h["hash_pedido"] == hash_pedido:
            return json.loads((pasta_ia(raiz) / h["arquivo"]).read_text(encoding="utf-8"))
    return None


# ------------------------------------------------------------------ conferência
def _norm_trecho(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (s or "").lower())).strip()


def conferir_normas(citadas: list[dict], tipo: str | None, textos: list[str]) -> tuple[list[dict], list[str]]:
    """Cada dispositivo citado → o texto oficial em vigor na data de referência, e o que não confere.

    A data tem de aparecer no dossiê ou num documento (em AAAA-MM-DD ou dd/mm/aaaa): data inventada
    mostraria a redação errada. Dispositivo que não estava em vigor naquela data é apontado."""
    saida, problemas = [], []
    for n in citadas:
        r = N.resolver(n.get("dispositivo", ""), n.get("data_referencia"))
        if r is None:
            problemas.append(f"dispositivo fora do catálogo: {n.get('dispositivo')}")
            continue
        avisos = []
        iso = r["data_referencia"]
        if not iso:
            avisos.append(f"data de referência inválida ({n.get('data_referencia')!r}): mostrada a redação atual")
        elif not any(iso in t or datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y") in t for t in textos):
            avisos.append(f"a data {iso} não aparece no dossiê nem nos documentos")
        if iso and not r["em_vigor"]:
            avisos.append(f"{r['rotulo']} não estava em vigor em {datetime.strptime(iso, '%Y-%m-%d').strftime('%d/%m/%Y')}")
        problemas += avisos
        saida.append({**r, "aplicacao": mascarar(n.get("aplicacao") or ""), "avisos": avisos})
    if tipo == "sinal" and not saida:
        problemas.append("sinal sem base normativa indicada")
    return saida, problemas


def conferir(saida: dict[str, Any], pedido: dict[str, Any], docs: dict[str, dict]) -> dict[str, Any]:
    textos = {"resumo": json.dumps(pedido["resumo"], ensure_ascii=False, default=str)}
    for u in pedido["usados"]:
        d = docs.get(u["id"]) or {}
        textos[u["id"]] = mascarar(_ler_texto(d)) if not d.get("escaneado") else None
    permitidos_globais = [{"valor": v, "unidade": u if u != "num" else "dec"} for v, u, _ in numeros_do_texto(textos["resumo"])]
    aceitas, recusadas = [], []
    for c in saida.get("constatacoes", []):
        c = {**c, "titulo": mascarar(c["titulo"]), "texto": mascarar(c["texto"]), "proxima_verificacao": mascarar(c["proxima_verificacao"])}
        problemas, situacoes, permitidos = [], [], list(permitidos_globais)
        c["normas"], prob_normas = conferir_normas(c.get("normas") or [], c.get("tipo"), [t for t in textos.values() if t])
        problemas += prob_normas
        permitidos += [{"valor": v, "unidade": u if u != "num" else "dec"} for n in c["normas"] for v, u, _ in numeros_do_texto(n["texto"])]
        for ev in c.get("evidencias", []):
            t = textos.get(ev["documento"], "__inexistente__")
            if t == "__inexistente__":
                ev["conferencia"] = "documento não enviado"
                problemas.append(f"cita documento que não foi enviado: {ev['documento']}")
            elif t is None:
                ev["conferencia"] = "não conferível (escaneado)"
                situacoes.append("nao_conferivel")
            else:
                achou = _norm_trecho(ev["trecho"])[:200] in _norm_trecho(t)
                ev["conferencia"] = "trecho encontrado" if achou else "trecho NÃO encontrado no documento"
                situacoes.append("ok" if achou else "falhou")
                permitidos += [{"valor": v, "unidade": u if u != "num" else "dec"} for v, u, _ in numeros_do_texto(t[:400_000])]
        aplicacoes = " ".join(n["aplicacao"] for n in c["normas"])
        for v, u, tol in numeros_do_texto(c["texto"] + " " + c["titulo"] + " " + aplicacoes):
            if not _bate(v, u, tol, permitidos + [{"valor": float(a), "unidade": "int"} for a in range(2000, 2031)]):
                problemas.append(f"número sem lastro no resumo nem nos documentos citados: {v:g}")
        proib = sorted({m.group(0).lower() for m in PALAVRAS_PROIBIDAS.finditer(c["texto"] + " " + c["titulo"] + " " + aplicacoes)})
        if proib:
            recusadas.append({**c, "problemas": [f"afirma o que os dados não sustentam: {', '.join(proib)}"] + problemas})
            continue
        if not c.get("evidencias"):
            problemas.append("sem evidência citada")
        c["conferencia"] = ("com ressalvas" if problemas or "falhou" in situacoes else
                            "não conferível" if situacoes and all(s == "nao_conferivel" for s in situacoes) else "conferida")
        c["problemas"] = problemas
        aceitas.append(c)
    return {"constatacoes": aceitas, "recusadas": recusadas}


# ------------------------------------------------------------------ análise
def analisar(raiz: str, refazer: bool = False, modelo: str = MODELO_PADRAO, esforco: str = ESFORCO_PADRAO,
             cliente: Any = None, progresso: Progresso | None = None) -> dict[str, Any]:
    passo = progresso or (lambda _t: None)
    d = D.ler(raiz)
    if d is None:
        passo("Montando o dossiê primeiro")
        d = D.montar(raiz, progresso=passo)
    docs = baixar_documentos(d, progresso=passo)
    pedido = preparar(d, docs)
    if not refazer and (salva := gravada(raiz, pedido["hash_pedido"])) is not None:
        return {**salva, "_reaproveitada": True}
    passo("Chamando o Claude (pode levar alguns minutos)")
    import anthropic
    cliente = cliente or anthropic.Anthropic()
    est = estimar(pedido, modelo, esforco, cliente)
    params = _params(pedido, modelo, esforco)
    with cliente.beta.messages.stream(max_tokens=32_000, betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params) as fluxo:
        resposta = fluxo.get_final_message()
    if resposta.stop_reason == "refusal":
        raise RuntimeError(f"o modelo recusou a análise (categoria: {getattr(getattr(resposta, 'stop_details', None), 'category', None)})")
    if resposta.stop_reason == "max_tokens":
        raise RuntimeError("a resposta passou do limite de tokens")
    texto = next((b.text for b in resposta.content if getattr(b, "type", None) == "text"), None)
    if texto is None:
        raise RuntimeError("a resposta não trouxe texto")
    bruta = json.loads(texto)
    passo("Conferindo trechos e números")
    conf = conferir(bruta, pedido, {x["id"]: x for x in docs})
    uso = getattr(resposta, "usage", None)
    tin, tout = getattr(uso, "input_tokens", None), getattr(uso, "output_tokens", None)
    pe, ps = PRECOS.get(modelo, PRECOS[MODELO_PADRAO])
    resultado = {
        "meta": {"raiz": raiz, "empresa": d["meta"].get("nome"), "gerado_em": _agora(), "modelo": getattr(resposta, "model", modelo),
                 "modelo_pedido": modelo, "esforco": esforco, "id_requisicao": getattr(resposta, "_request_id", None), "hash_pedido": pedido["hash_pedido"],
                 "dossie_gerado_em": d["meta"].get("gerado_em"), "tokens": {"entrada": tin, "saida": tout},
                 "custo_usd": round((tin or 0) * pe / 1e6 + (tout or 0) * ps / 1e6, 4) if tin is not None else est["custo_usd"],
                 "fallback": any(getattr(it, "type", None) == "fallback_message" for it in (getattr(uso, "iterations", None) or [])),
                 "estimativa": est},
        "resumo": mascarar(bruta.get("resumo", "")), "limites": [mascarar(x) for x in bruta.get("limites", [])],
        "documentos_usados": pedido["usados"], "documentos_fora": pedido["fora"], **conf,
    }
    p = pasta_ia(raiz)
    p.mkdir(parents=True, exist_ok=True)
    # Nome que nunca se repete: uma análise nunca sobrescreve outra (o histórico é o registro do que foi pago).
    base = datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "_" + pedido["hash_pedido"][:12]
    nome, n = base + ".json", 1
    while (p / nome).exists():
        nome, n = f"{base}_{n}.json", n + 1
    (p / nome).write_text(json.dumps(resultado, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return resultado


# ------------------------------------------------------------------ base normativa de uma análise antiga
SISTEMA_NORMAS = """Você recebe as constatações já redigidas da análise de uma empresa fornecedora de municípios do Espírito Santo (para auditores do TCE-ES), os contratos da empresa no TCE-ES e um catálogo de dispositivos legais com o texto oficial. Para cada constatação, pelo número dela, indique os dispositivos do catálogo que o auditor deve confrontar com o caso. Não reescreva as constatações.

Regras:
- Use só números que estão nas constatações, nos contratos ou no catálogo.
- Não afirme nem insinue irregularidade, fraude, superfaturamento, conluio, cartel, direcionamento ou crime.
""" + REGRAS_NORMAS + """- Português do Brasil, frases curtas."""

ESQUEMA_NORMAS = {"type": "object", "properties": {"itens": {"type": "array", "items": {"type": "object", "properties": {
    "indice": {"type": "integer"}, "normas": NORMAS_SAIDA}, "required": ["indice", "normas"], "additionalProperties": False}}},
    "required": ["itens"], "additionalProperties": False}


def pasta_normas(raiz: str) -> Path:
    return pasta_ia(raiz) / "normas"          # fora do glob do histórico: um complemento não é uma análise


def complemento_normas(raiz: str, arquivo: str) -> dict[str, Any] | None:
    p = pasta_normas(raiz) / arquivo
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def com_normas(raiz: str, analise: dict[str, Any] | None, arquivo: str | None = None) -> dict[str, Any] | None:
    """A análise com a base normativa do complemento, se houver. O arquivo da análise não muda."""
    if not analise:
        return analise
    if arquivo is None:
        h = historico(raiz)
        arquivo = h[0]["arquivo"] if h else None
    comp = complemento_normas(raiz, arquivo) if arquivo else None
    saida = {**analise, "_arquivo": arquivo, "_sem_normas": sum(1 for c in analise.get("constatacoes", []) if "normas" not in c)}
    if comp:
        por = {x["indice"]: x for x in comp["itens"]}
        saida["constatacoes"] = [c if "normas" in c else {**c, "normas": por.get(i, {}).get("normas", []), "normas_avisos": por.get(i, {}).get("avisos", []),
                                                         "normas_complemento": True}
                                 for i, c in enumerate(analise.get("constatacoes", []))]
        saida["_complemento_normas"] = comp["meta"]
        saida["_sem_normas"] = 0
    return saida


def _pedido_normas(raiz: str, analise: dict[str, Any]) -> dict[str, Any]:
    d = D.ler(raiz) or {}
    contratos = [{k: x.get(k) for k in ("municipio", "numero", "objeto", "modalidade", "base_legal", "arp", "assinatura", "vigencia", "valor_inicial", "valor_atual", "sinal")}
                 for x in ((d.get("contratos") or {}).get("contratos") or [])[:120]]
    constatacoes = [{"indice": i, "tipo": c.get("tipo"), "titulo": c.get("titulo"), "texto": c.get("texto"), "proxima_verificacao": c.get("proxima_verificacao"),
                     "evidencias": [e.get("trecho") for e in c.get("evidencias", [])]} for i, c in enumerate(analise.get("constatacoes", []))]
    corpo = mascarar(json.dumps({"constatacoes": constatacoes, "contratos_tcees": contratos}, ensure_ascii=False, indent=1, default=str))
    catalogo = N.para_ia()
    conteudo = [{"type": "text", "text": "Constatações e contratos (JSON):\n\n" + corpo},
                {"type": "text", "text": "Documento \"normas\" — catálogo de dispositivos legais (texto oficial):\n\n" + catalogo},
                {"type": "text", "text": "Indique a base normativa de cada constatação, pelo índice."}]
    return {"conteudo": conteudo, "corpo": corpo, "caracteres": len(corpo) + len(catalogo) + len(SISTEMA_NORMAS)}


def _params_normas(pedido: dict, modelo: str) -> dict[str, Any]:
    return {"model": modelo, "system": SISTEMA_NORMAS, "messages": [{"role": "user", "content": pedido["conteudo"]}],
            "output_config": {"effort": "medium", "format": {"type": "json_schema", "schema": ESQUEMA_NORMAS}}}


def estimar_normas(raiz: str, modelo: str = MODELO_PADRAO, cliente: Any = None) -> dict[str, Any]:
    analise = ultima(raiz)
    if analise is None:
        raise ValueError("não há análise gravada")
    pedido = _pedido_normas(raiz, analise)
    entrada, metodo = None, "estimativa (3,6 caracteres por token)"
    if cliente is not None or credencial_disponivel():
        try:
            import anthropic
            cliente = cliente or anthropic.Anthropic()
            entrada, metodo = cliente.beta.messages.count_tokens(**_params_normas(pedido, modelo)).input_tokens, "contado pela API (count_tokens)"
        except Exception as exc:
            metodo += f"; a contagem pela API falhou ({type(exc).__name__})"
    entrada = entrada or int(pedido["caracteres"] / 3.6)
    saida = 400 * len(analise.get("constatacoes", [])) + 2000
    pe, ps = PRECOS.get(modelo, PRECOS[MODELO_PADRAO])
    return {"modelo": modelo, "tokens_entrada": entrada, "tokens_saida_previstos": saida, "metodo": metodo,
            "custo_usd": round(entrada * pe / 1e6 + saida * ps / 1e6, 2), "constatacoes": len(analise.get("constatacoes", []))}


def complementar_normas(raiz: str, modelo: str = MODELO_PADRAO, cliente: Any = None, progresso: Progresso | None = None) -> dict[str, Any]:
    """Base normativa de uma análise feita antes do catálogo, sem reler os documentos. Gravada à parte."""
    passo = progresso or (lambda _t: None)
    h = historico(raiz)
    if not h:
        raise ValueError("não há análise gravada")
    arquivo = h[0]["arquivo"]
    analise = ultima(raiz)
    if complemento_normas(raiz, arquivo) is not None:          # já feito: devolve, sem tokens
        return {**com_normas(raiz, analise, arquivo), "_reaproveitado": True}
    pedido = _pedido_normas(raiz, analise)
    passo("Chamando o Claude para indicar a base normativa")
    import anthropic
    cliente = cliente or anthropic.Anthropic()
    with cliente.beta.messages.stream(max_tokens=16_000, betas=["server-side-fallback-2026-07-01"], fallbacks="default", **_params_normas(pedido, modelo)) as fluxo:
        resposta = fluxo.get_final_message()
    if resposta.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"a resposta não terminou ({resposta.stop_reason})")
    texto = next((b.text for b in resposta.content if getattr(b, "type", None) == "text"), None)
    if texto is None:
        raise RuntimeError("a resposta não trouxe texto")
    bruta = json.loads(texto)
    passo("Conferindo datas, vigência e números")
    d = D.ler(raiz) or {}
    textos = [pedido["corpo"], json.dumps(resumo_dossie(d), ensure_ascii=False, default=str) if d.get("meta") else ""]
    for x in analise.get("documentos_usados", []):
        tp = D.PASTA_CRUS / raiz / "docs" / (x["id"] + ".txt")
        if tp.exists():
            textos.append(mascarar(tp.read_text(encoding="utf-8")))
    permitidos = [{"valor": v, "unidade": u if u != "num" else "dec"} for t in textos for v, u, _ in numeros_do_texto(t[:400_000])]
    tipos = {i: c.get("tipo") for i, c in enumerate(analise.get("constatacoes", []))}
    itens = []
    for x in bruta.get("itens", []):
        if x.get("indice") not in tipos:
            continue
        normas, avisos = conferir_normas(x.get("normas") or [], tipos[x["indice"]], textos)
        aplic = " ".join(n["aplicacao"] for n in normas)
        lastro = permitidos + [{"valor": v, "unidade": u if u != "num" else "dec"} for n in normas for v, u, _ in numeros_do_texto(n["texto"])]
        avisos += [f"número sem lastro: {v:g}" for v, u, tol in numeros_do_texto(aplic)
                   if not _bate(v, u, tol, lastro + [{"valor": float(a), "unidade": "int"} for a in range(2000, 2031)])]
        if PALAVRAS_PROIBIDAS.search(aplic):
            avisos.append("aplicação recusada: afirma o que os dados não sustentam")
            normas = [{**n, "aplicacao": ""} for n in normas]
        itens.append({"indice": x["indice"], "normas": normas, "avisos": avisos})
    uso = getattr(resposta, "usage", None)
    tin, tout = getattr(uso, "input_tokens", None), getattr(uso, "output_tokens", None)
    pe, ps = PRECOS.get(modelo, PRECOS[MODELO_PADRAO])
    comp = {"meta": {"raiz": raiz, "arquivo_analise": arquivo, "gerado_em": _agora(), "modelo": getattr(resposta, "model", modelo),
                     "id_requisicao": getattr(resposta, "_request_id", None), "tokens": {"entrada": tin, "saida": tout},
                     "custo_usd": round((tin or 0) * pe / 1e6 + (tout or 0) * ps / 1e6, 4), "catalogo_gerado_em": N.carregar()["gerado_em"]},
            "itens": itens}
    p = pasta_normas(raiz)
    p.mkdir(parents=True, exist_ok=True)
    (p / arquivo).write_text(json.dumps(comp, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return com_normas(raiz, analise, arquivo)
