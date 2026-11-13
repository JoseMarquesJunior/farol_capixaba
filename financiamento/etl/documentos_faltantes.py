"""Busca dos documentos que faltam no dossiê — contratos cujo link no TCE-ES é genérico.

O campo de link do contrato no TCE-ES é preenchido pelo município, e muitos põem o
endereço do portal, não o do documento (Presidente Kennedy: 18 de 1.186 contratos com link
específico; Vitória e Cachoeiro, acima de 93%). Sem o contrato, o extrato e os aditivos, a
análise fica no escuro. Este módulo tenta, para os maiores contratos sem documento:

* **PNCP por órgão e data** (automática): os contratos que a prefeitura publicou no PNCP
  numa janela em torno da assinatura, casados pelo CNPJ do fornecedor e pelo número; se
  casar, os arquivos do contrato entram no inventário;
* **DOM-ES, varredura das edições** (automática): o Diário Oficial dos Municípios não expõe
  busca textual, mas cada edição baixa inteira. Lê as edições da assinatura até três semanas
  depois, nas páginas que citam o município, procurando o CNPJ, o nome da empresa e o número
  do contrato. A página achada vira um PDF só dela (endereço público do próprio DOM-ES) e entra
  no inventário. Cada edição é baixada e lida UMA vez e serve a todas as empresas;
* **rotas manuais guiadas**: o portal de transparência do município (com o caminho no menu e
  os filtros), a busca do DOM-ES com os termos, o site com CAPTCHA (só manual — não se
  contorna) e um **modelo de pedido** pela LAI ou de requisição pela auditoria.

Tudo fica gravado no dossiê; refazer só quando se pede.
"""

from __future__ import annotations

import gzip
import io
import json
import logging
import re
import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Callable
from urllib.parse import urlparse

from . import dossie as D
from .config import BRUTO
from .parsing import norm

PASTA_DOM = BRUTO / "dioes" / "edicoes"
INDICE_DOM = BRUTO / "diarios" / "dom_es_edicoes.json"
MAX_CONTRATOS = 6          # os maiores sem documento; cada um custa alguns minutos de varredura
DIAS_ANTES, DIAS_DEPOIS = 3, 21
Progresso = Callable[[str], None]


# ------------------------------------------------------------------ apoio
@lru_cache(maxsize=1)
def cnpj_municipios() -> dict[str, str]:
    """Nome normalizado do município → CNPJ da prefeitura (cadastro de entes do SICONFI, no cache)."""
    p = BRUTO / "_sem_exercicio" / "entes" / "todos.json.gz"
    if not p.exists():
        return {}
    dados = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    itens = dados if isinstance(dados, list) else dados.get("itens") or dados.get("items") or []
    return {norm(e["ente"]): e["cnpj"] for e in itens if isinstance(e, dict) and e.get("esfera") == "M" and e.get("uf") == "ES" and e.get("cnpj")}


def _data(s: str) -> datetime | None:
    try:
        return datetime.strptime((s or "")[:10], "%Y-%m-%d")
    except ValueError:
        return None


def faltantes(d: dict[str, Any], limite: int = MAX_CONTRATOS) -> list[dict[str, Any]]:
    """Contratos sem link específico de contrato NEM de publicação, os de maior valor primeiro."""
    cs = (d.get("contratos") or {}).get("contratos") or []
    sem = [c for c in cs if not D.especifico(c.get("url_contrato")) and not D.especifico(c.get("url_publicacao"))]
    return sorted(sem, key=lambda c: -(c.get("valor_atual") or 0))[:limite]


def plataforma(url: str) -> str | None:
    host = urlparse(url or "").netloc
    if "portaltp.com.br" in host:
        return "portaltp"
    if host.endswith(".es.gov.br") and "/transparencia" in (url or ""):
        return "site_transparencia"
    if "dio.es.gov.br" in host:
        return "dom_es"
    return None


# ------------------------------------------------------------------ rota PNCP por órgão
def rota_pncp(col: D.Coletor, c: dict, raiz: str) -> dict[str, Any]:
    cnpj = cnpj_municipios().get(norm(c["municipio"]))
    dia = _data(c.get("assinatura"))
    if not cnpj or not dia:
        return {"rota": "PNCP por órgão", "situacao": "nao_aplicavel", "detalhe": "sem CNPJ do órgão ou sem data de assinatura"}
    ini, fim = (dia - timedelta(days=15)).strftime("%Y%m%d"), (dia + timedelta(days=60)).strftime("%Y%m%d")
    achados, total = [], 0
    for pagina in range(1, 4):
        st, corpo, meta = col.get(f"pncp_orgao_{cnpj}_{ini}_{fim}_p{pagina}.json", f"https://pncp.gov.br/api/consulta/v1/contratos?dataInicial={ini}&dataFinal={fim}"
                                  f"&cnpjOrgao={cnpj}&pagina={pagina}&tamanhoPagina=500", timeout=150, tentativas=3, pasta=D.PASTA_CRUS / "_pncp_orgao")
        if st == 204 or (st == 200 and not corpo):
            break
        dados = D._json(corpo) if st == 200 else None
        if not isinstance(dados, dict):
            return {"rota": "PNCP por órgão", "situacao": "erro", "detalhe": meta.get("erro") or f"HTTP {st}"}
        itens = dados.get("data") or []
        total = dados.get("totalRegistros") or len(itens)
        num = re.sub(r"\D", "", (c.get("numero") or "").split("/")[0]).lstrip("0")
        for x in itens:
            if re.sub(r"\D", "", x.get("niFornecedor") or "")[:8] != raiz:
                continue
            mesmo_num = num and re.sub(r"\D", "", str(x.get("numeroContratoEmpenho") or "").split("/")[0]).lstrip("0") == num
            achados.append({"numero": x.get("numeroContratoEmpenho"), "ano": x.get("anoContrato"), "seq": x.get("sequencialContrato"),
                            "objeto": (x.get("objetoContrato") or "")[:200], "valor": x.get("valorGlobal"), "controle": x.get("numeroControlePNCP"),
                            "casa_numero": bool(mesmo_num), "orgao": cnpj})
        if (dados.get("paginasRestantes") or 0) <= 0:
            break
    if not achados:
        return {"rota": "PNCP por órgão", "situacao": "nao_encontrado",
                "detalhe": f"a prefeitura (CNPJ {D.fmt_cnpj(cnpj)}) publicou {total} contrato(s) no PNCP entre {ini[6:]}/{ini[4:6]}/{ini[:4]} e {fim[6:]}/{fim[4:6]}/{fim[:4]}, nenhum com esta empresa "
                           "(o contrato pode ter sido publicado com o CNPJ de um fundo ou secretaria, ou não publicado)"}
    docs = []
    for a in sorted(achados, key=lambda a: not a["casa_numero"])[:3]:
        st, corpo, _ = col.get(f"pncp_arquivos_{cnpj}_{a['ano']}_{a['seq']}.json", f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/contratos/{a['ano']}/{a['seq']}/arquivos",
                               timeout=90, pasta=D.PASTA_CRUS / "_pncp_orgao")
        for arq in (D._json(corpo) if st == 200 else None) or []:
            docs.append({"tipo": "PNCP: " + (arq.get("tipoDocumentoNome") or "arquivo"), "url": arq.get("url") or
                         f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/contratos/{a['ano']}/{a['seq']}/arquivos/{arq.get('sequencialDocumento')}",
                         "titulo": arq.get("titulo")})
    return {"rota": "PNCP por órgão", "situacao": "encontrado", "detalhe": f"{len(achados)} contrato(s) da empresa no PNCP na janela; "
            + ("um casa com o número" if any(a["casa_numero"] for a in achados) else "nenhum com o mesmo número"), "contratos_pncp": achados, "documentos": docs}


# ------------------------------------------------------------------ rota DOM-ES
@lru_cache(maxsize=1)
def indice_dom() -> list[dict]:
    if not INDICE_DOM.exists():
        return []
    return json.loads(INDICE_DOM.read_text(encoding="utf-8"))["itens"]


def paginas_edicao(col: D.Coletor, edicao: int) -> list[str]:
    """Texto de cada página de uma edição — baixada e lida uma vez, para todas as empresas."""
    txt = PASTA_DOM / f"{edicao}.paginas.json.gz"
    if txt.exists():
        return json.loads(gzip.decompress(txt.read_bytes()).decode("utf-8"))
    st, corpo, meta = col.get(f"{edicao}.pdf", f"https://ioes.dio.es.gov.br/portal/edicoes/download/{edicao}", timeout=180, tentativas=2, pasta=PASTA_DOM)
    if st != 200 or corpo[:5] != b"%PDF-":
        raise RuntimeError(f"edição {edicao}: {meta.get('erro') or 'HTTP ' + str(st)}")
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)   # avisos de fonte, um por página: não interessam
    paginas =[(p.extract_text() or "") for p in PdfReader(io.BytesIO(corpo)).pages]
    txt.write_bytes(gzip.compress(json.dumps(paginas, ensure_ascii=False).encode("utf-8")))
    (PASTA_DOM / f"{edicao}.pdf").unlink(missing_ok=True)   # fica o texto (e o .meta.json com o SHA-256 do original)
    return paginas


def rota_dom(col: D.Coletor, c: dict, raiz: str, nome_empresa: str, cnpj: str, progresso: Progresso) -> dict[str, Any]:
    dia = _data(c.get("assinatura"))
    idx = indice_dom()
    if not dia:
        return {"rota": "DOM-ES (varredura)", "situacao": "nao_aplicavel", "detalhe": "sem data de assinatura"}
    if not idx or dia < datetime.strptime(idx[-1]["data"], "%d/%m/%Y"):
        return {"rota": "DOM-ES (varredura)", "situacao": "nao_aplicavel", "detalhe": "data anterior ao índice de edições em cache (de 09/2023 em diante)"}
    janela = [e for e in idx if dia - timedelta(days=DIAS_ANTES) <= datetime.strptime(e["data"], "%d/%m/%Y") <= dia + timedelta(days=DIAS_DEPOIS)]
    mun = norm(c["municipio"])
    num, ano = (c.get("numero") or "/").split("/")[:2]
    num = num.lstrip("0") or num
    p_num = re.compile(rf"\b0*{re.escape(num)}\s*/\s*{re.escape(ano)}\b") if num and ano else None
    p_cnpj = re.compile(re.escape(D.fmt_cnpj(cnpj)[:10]).replace(r"\.", r"\.?"))
    # As duas primeiras palavras do nome ("dc transportes"): uma só seria fraca demais.
    palavras = [w for w in re.sub(r"[^a-z0-9 ]", " ", norm(nome_empresa)).split() if w not in ("ltda", "eireli", "epp", "me", "sa", "servicos", "comercio", "e", "de", "da", "do")][:2]
    p_nome = re.compile(r"\s+".join(map(re.escape, palavras))) if palavras else None
    achados, falhas = [], 0
    for n, e in enumerate(sorted(janela, key=lambda x: x["id"]), 1):
        progresso(f"Diário Oficial: edição de {e['data']} ({n} de {len(janela)}) — contrato {c['numero']}")
        try:
            paginas = paginas_edicao(col, e["id"])
        except Exception:
            falhas += 1
            continue
        for i, t in enumerate(paginas, 1):
            tn = norm(t)
            if mun not in tn:
                continue
            m_num = p_num.search(t) if p_num else None
            m_valor = re.search(re.escape(_valor_br(c["valor_inicial"])), t) if c.get("valor_inicial") else None
            m_cnpj = p_cnpj.search(t)
            tem_emp = bool(m_cnpj or (p_nome and p_nome.search(tn)))
            tem_num = bool(m_num)
            if tem_emp and (m_num or m_valor):
                # O trecho começa perto do que identifica o contrato: o número, senão o valor, senão o CNPJ.
                pos = _inicio_trecho(t, next(m.start() for m in (m_num, m_valor, m_cnpj) if m))
                achados.append({"edicao": e["id"], "data": e["data"], "pagina": i, "casa_numero": tem_num,
                                "trecho": re.sub(r"\s+", " ", t[pos:pos + 600]).strip(),
                                "url": f"https://ioes.dio.es.gov.br/apifront/portal/edicoes/pdf_diario/{e['id']}/{i}",
                                "visualizar": f"https://ioes.dio.es.gov.br/portal/visualizacoes/pdf/{e['id']}/#/p:{i}/e:{e['id']}"})
        time.sleep(0.5)
    base = {"rota": "DOM-ES (varredura)", "edicoes_lidas": len(janela) - falhas, "edicoes_com_falha": falhas,
            "janela": [(dia - timedelta(days=DIAS_ANTES)).strftime("%d/%m/%Y"), (dia + timedelta(days=DIAS_DEPOIS)).strftime("%d/%m/%Y")]}
    if not achados:
        return {**base, "situacao": "nao_encontrado", "detalhe": f"nenhuma página de {c['municipio']} com a empresa e o número/valor do contrato em {len(janela) - falhas} edição(ões)"}
    return {**base, "situacao": "encontrado", "detalhe": f"{len(achados)} página(s) com a empresa e o número ou o valor do contrato", "paginas": achados,
            "documentos": [{"tipo": "extrato no DOM-ES", "url": a["url"], "titulo": f"DOM-ES {a['data']}, p. {a['pagina']}"} for a in achados[:4]]}


TITULOS_ATO = re.compile(r"EXTRATO|RESULTADO|HOMOLOGA|ADJUDICA|TERMO ADITIVO|AVISO|RATIFICA")


def _inicio_trecho(t: str, ancora: int) -> int:
    """Começo do trecho: o título do ato logo antes da âncora (extrato, homologação…), senão o início de uma palavra."""
    antes = t[max(0, ancora - 400):ancora]
    titulos = list(TITULOS_ATO.finditer(antes))
    if titulos:
        return max(0, ancora - 400) + titulos[-1].start()
    pos = max(0, ancora - 200)
    while 0 < pos < ancora and not t[pos - 1].isspace():
        pos += 1
    return pos


def _valor_br(v: float) -> str:
    return f"{v:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")


def _data_br(s: str | None) -> str:
    dia = _data(s or "")
    return dia.strftime("%d/%m/%Y") if dia else "a assinatura"


# ------------------------------------------------------------------ rotas manuais
def orientacao_manual(c: dict, d: dict, nome_empresa: str, cnpj: str) -> list[dict[str, str]]:
    plats = {plataforma(c.get("url_contrato")), plataforma(c.get("url_publicacao"))}
    num = c.get("numero") or ""
    ano = (c.get("assinatura") or "")[:4]
    passos = []
    if "portaltp" in plats:
        base = "https://" + urlparse(c["url_contrato"]).netloc
        passos.append({"onde": "Portal da Transparência do município (portaltp)", "url": base + "/consultas/compras/contratos.aspx",
                       "como": f"Menu Compras › \"Contratos e Aditivos\" (e \"Contratos e Aditivos (Documentos)\" para o PDF); em Entidade escolha "
                               f"\"{c.get('ug') or 'a unidade que assinou'}\", em Ano escolha {ano}, clique em Aplicar e pesquise \"{nome_empresa.split()[0]}\" ou o número {num}."
                               + (f" O contrato veio da ata {c['arp']}: veja também Compras › \"Atas de Adesão\" e \"Termos de Compromisso/Atas\"." if c.get("arp") else "")})
    if "site_transparencia" in plats:
        passos.append({"onde": "Site de transparência da prefeitura", "url": c["url_contrato"],
                       "como": "Tem CAPTCHA: consulta só manual (o robô não contorna). Filtre por ano e fornecedor."})
    passos.append({"onde": "Diário Oficial dos Municípios (DOM-ES)", "url": "https://ioes.dio.es.gov.br/buscanova",
                   "como": f"Busque \"{D.fmt_cnpj(cnpj)}\" ou \"{nome_empresa}\" com o filtro de data a partir de uma semana antes da assinatura ({_data_br(c.get('assinatura'))}) — a homologação sai antes; "
                           f"procure o extrato do contrato {num}, da ata {c.get('arp') or '—'} e os termos aditivos."})
    passos.append({"onde": "PNCP", "url": "https://pncp.gov.br/app/contratos?q=" + cnpj,
                   "como": "Busque o CNPJ da empresa e confira o órgão (a publicação pode estar no CNPJ do fundo ou da secretaria)."})
    return passos


def modelo_pedido(c: dict, nome_empresa: str, cnpj: str) -> str:
    return (f"Solicito cópia integral do contrato nº {c.get('numero')}, firmado em {_data_br(c.get('assinatura'))} entre a {c.get('ug') or 'unidade gestora'} "
            f"do Município de {c.get('municipio')} e {nome_empresa} (CNPJ {D.fmt_cnpj(cnpj)}), objeto: \"{(c.get('objeto') or '')[:200]}\""
            + (f", decorrente da ata de registro de preços nº {c['arp']}" if c.get("arp") else "")
            + ", acompanhado do edital e do processo de origem, de todos os termos aditivos e apostilamentos, das publicações no Diário Oficial "
              "e das medições ou notas fiscais que sustentam os pagamentos. Fundamento: Lei nº 12.527/2011 (acesso à informação) e Lei nº 14.133/2021, art. 174.")


# ------------------------------------------------------------------ busca completa
def buscar(raiz: str, progresso: Progresso | None = None, refazer: bool = False, limite: int = MAX_CONTRATOS) -> dict[str, Any]:
    """Procura os documentos dos maiores contratos sem link e grava no dossiê (inventário inclusive)."""
    passo = progresso or (lambda _t: None)
    d = D.ler(raiz) or D.montar(raiz, progresso=passo)
    if d.get("faltantes") and not refazer:
        return d
    col = D.Coletor(raiz)
    nome = d["meta"].get("nome") or raiz
    cnpj = d["meta"].get("cnpj_consultado") or raiz
    resultado, alvo = [], faltantes(d, limite)
    for n, c in enumerate(alvo, 1):
        passo(f"Contrato {n} de {len(alvo)}: {c['numero']} — {c['municipio']} — PNCP por órgão")
        rotas = [rota_pncp(col, c, raiz)]
        rotas.append(rota_dom(col, c, raiz, nome, cnpj, passo))
        achou = [r for r in rotas if r["situacao"] == "encontrado"]
        resultado.append({"contrato": {k: c.get(k) for k in ("municipio", "ug", "numero", "objeto", "assinatura", "valor_inicial", "valor_atual", "arp", "url_contrato", "url_publicacao", "chave")},
                          "situacao": "encontrado" if achou else "nao_encontrado", "rotas": rotas,
                          "orientacao": orientacao_manual(c, d, nome, cnpj), "modelo_pedido": modelo_pedido(c, nome, cnpj)})
    total_sem = len([c for c in (d.get("contratos") or {}).get("contratos", []) if not D.especifico(c.get("url_contrato")) and not D.especifico(c.get("url_publicacao"))])
    d["faltantes"] = {"gerado_em": D._agora(), "contratos_sem_documento": total_sem, "procurados": len(resultado),
                      "encontrados": sum(r["situacao"] == "encontrado" for r in resultado), "itens": resultado,
                      "regra": f"os {limite} maiores contratos sem link específico de contrato nem de publicação; DOM-ES de {DIAS_ANTES} dias antes a {DIAS_DEPOIS} dias depois da assinatura"}
    d["documentos"] = D.inventario(d)   # o que foi achado entra no inventário — e a Análise com IA passa a ler
    d.setdefault("fontes", []).extend({k: f.get(k) for k in ("nome", "url", "status", "obtido_em", "sha256", "bytes", "arquivo", "erro", "cache")} for f in col.fontes)
    D.caminho(raiz).write_text(json.dumps(d, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return d


if __name__ == "__main__":
    import sys
    r = buscar(sys.argv[1], progresso=print, refazer="--refazer" in sys.argv)["faltantes"]
    print(f"{r['encontrados']} de {r['procurados']} contrato(s) com documento achado ({r['contratos_sem_documento']} sem documento no TCE-ES)")
