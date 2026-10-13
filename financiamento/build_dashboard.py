"""Monta `dashboard.html` a partir dos fontes em `web/` e do dataset processado.

    python -m financiamento.build_dashboard

O HTML final é autocontido: CSS, JavaScript e dados vão dentro da página (um
`fetch` de arquivo local não funciona em `file://`). Vão junto os PDFs do RREO
Anexo 8 do SIOPE, cuja fonte só existe em FTP — ver `pdfs_embutidos`. A única
dependência externa é o Chart.js via CDN, fixado em versão e com hash de
integridade (SRI). O navegador nunca chama API.

Os fontes ficam separados em `web/` só para manutenção — o que é entregue é a
página única.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
WEB = PASTA / "web"
#: Cache bruto das coletas — de onde saem os PDFs embutidos (ver `pdfs_embutidos`).
BRUTO = PASTA / "dados" / "bruto"
DATASET = PASTA / "dados" / "processado" / "dataset.json"
#: Dataset da matriz de evidências do CNCA (`python -m financiamento.etl.evidencias`).
#: Separado do geral porque tem ciclo de atualização próprio; sem ele a página monta
#: com a aba do CNCA vazia e dizendo por quê, em vez de falhar.
DATASET_CNCA = PASTA / "dados" / "processado" / "dataset_cnca.json"
SAIDA = PASTA / "dashboard.html"

#: Marcador no template -> arquivo em `web/` cujo conteúdo entra no lugar.
#: `design-tokens.css` vem antes de `estilo.css`: define as variáveis que o
#: estilo consome. Ver docs/identidade_tcees/relatorio.md para a origem de cada
#: valor.
PARTES = {
    "__DESIGN_TOKENS_CSS__": "design-tokens.css",
    "__ESTILO_CSS__": "estilo.css",
    "__COMUM_JS__": "comum.js",
    "__FONTE_JS__": "fonte.js",
    "__SANKEY_JS__": "sankey.js",
    "__NIVEL3_JS__": "nivel3.js",
    "__VISAO_CONFORMIDADE_JS__": "visao_conformidade.js",
    "__VISAO_FLUXO_JS__": "visao_fluxo.js",
    "__VISAO_PANORAMA_JS__": "visao_panorama.js",
    "__VISAO_MUNICIPIO_JS__": "visao_municipio.js",
    "__VISAO_ESCOLAS_JS__": "visao_escolas.js",
    "__VISAO_PROGRAMAS_JS__": "visao_programas.js",
    "__VISAO_CNCA_JS__": "visao_cnca.js",
}

#: Ao trocar a versão, recalcule o hash:
#:   curl -sL <URL> | openssl dgst -sha384 -binary | openssl base64 -A
CHARTJS_VERSION = "4.4.7"
CHARTJS_URL = f"https://cdn.jsdelivr.net/npm/chart.js@{CHARTJS_VERSION}/dist/chart.umd.min.js"
CHARTJS_SRI = "sha384-vsrfeLOOY6KuIYKDlmVH5UiBmgIdB1oEf7p01YgWHuqmOHfZr374+odEv96n9tNC"

SCHEMA_ESPERADO = 2
SCHEMA_CNCA_ESPERADO = 1


def _json_para_html(dados: dict) -> str:
    """JSON seguro para ficar dentro de <script type="application/json">."""
    texto = json.dumps(dados, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    # "</script>" e "<!--" dentro de dado encerrariam/alterariam o bloco de script. Os escapes
    # têm de continuar sendo JSON válido: "\/" é legal; "\!" NÃO é, então "!" vai como !.
    return texto.replace("</", "<\\/").replace("<!--", "<\\u0021--")


def _codigo_para_html(codigo: str, arquivo: str) -> str:
    """CSS/JS seguro dentro de <style>/<script>: `</style>` ou `</script>` no meio
    de uma string encerraria o bloco. Nenhum dos fontes precisa dessa sequência."""
    for proibido in ("</style", "</script"):
        if proibido in codigo.lower():
            raise SystemExit(f"{arquivo}: contém {proibido!r}, que encerraria o bloco embutido")
    return codigo


def _expandir(tabela: dict) -> list[dict]:
    """Tabela colunar do dataset -> lista de dicts, igual ao `expandir` do painel."""
    colunas, dic = tabela["colunas"], tabela.get("dicionario", {})
    return [{c: (dic[c][v] if c in dic and v is not None else v) for c, v in zip(colunas, linha)}
            for linha in tabela["linhas"]]


def pdfs_embutidos(dados: dict, bruto: Path = BRUTO) -> tuple[dict[str, str], list[str]]:
    """Os PDFs de consulta em FTP, em base64, por caminho no cache bruto.

    O RREO Anexo 8 do SIOPE é a fonte legal do MDE, e o FNDE só o publica em
    `ftp://ftp.fnde.gov.br/web/siope/RREO/` — esquema que o Chrome removeu na
    versão 95 e o Firefox na 90, e que o FNDE não espelha em HTTP anônimo (porta
    443 fechada, `/siope/` responde 401). O link do "ver fonte" não abre em
    navegador nenhum; sem o documento dentro da página, o número do MDE fica sem
    a evidência que o sustenta. Por isso o PDF vai embutido.

    Cada arquivo é conferido contra o SHA-256 que a proveniência afirma: o que a
    página entrega é byte a byte o que foi coletado, não uma cópia qualquer que
    esteja no cache. PDF ausente ou divergente fica de fora e volta na lista de
    problemas — a página explica a falta, em vez de a montagem inteira cair por
    causa de um arquivo.
    """
    consultas = dados.get("consultas") or {}
    if not consultas.get("colunas"):
        return {}, []
    pdfs: dict[str, str] = {}
    problemas: list[str] = []
    for c in _expandir(consultas):
        if not str(c.get("url_base") or "").startswith("ftp://"):
            continue
        arquivo = c.get("arquivo")
        if not arquivo or arquivo in pdfs:
            continue
        caminho = bruto / arquivo
        if not caminho.is_file():
            problemas.append(f"{arquivo}: não está no cache bruto")
            continue
        conteudo = caminho.read_bytes()
        sha = hashlib.sha256(conteudo).hexdigest()
        if c.get("sha256") and sha != c["sha256"]:
            problemas.append(f"{arquivo}: SHA-256 {sha[:16]}… != {c['sha256'][:16]}… da proveniência")
            continue
        pdfs[arquivo] = base64.b64encode(conteudo).decode("ascii")
    return pdfs, problemas


def _dataset_cnca(caminho: Path) -> dict:
    """O dataset da matriz do CNCA, ou um vazio que a página sabe explicar.

    Faltar o arquivo é situação normal: quem só rodou o pipeline geral ainda não
    gerou a matriz. A aba monta e diz o que rodar — melhor que derrubar a montagem
    inteira do painel por causa de uma aba.
    """
    if not caminho.exists():
        return {"meta": {"esquema": SCHEMA_CNCA_ESPERADO, "ausente": True,
                         "motivo": "dataset_cnca.json não existe; rode "
                                   "`python -m financiamento.etl.evidencias`"}}
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    if dados["meta"]["esquema"] != SCHEMA_CNCA_ESPERADO:
        raise SystemExit(f"esquema {dados['meta']['esquema']} do dataset do CNCA != "
                         f"{SCHEMA_CNCA_ESPERADO} esperado pelo template")
    return dados


def montar(template: Path | None = None, dataset: Path = DATASET, saida: Path = SAIDA,
           web: Path | None = None, dataset_cnca: Path = DATASET_CNCA, bruto: Path = BRUTO) -> Path:
    web = web or WEB
    template = template or (web / "index.html")
    with open(dataset, encoding="utf-8") as f:
        dados = json.load(f)
    if dados["meta"]["esquema"] != SCHEMA_ESPERADO:
        raise SystemExit(f"esquema {dados['meta']['esquema']} do dataset != {SCHEMA_ESPERADO} esperado pelo template")
    cnca = _dataset_cnca(dataset_cnca)
    pdfs, problemas = pdfs_embutidos(dados, bruto)
    for p in problemas:
        print(f"aviso: PDF fora da página — {p}", file=sys.stderr)
    # Índice leve (caminho -> bytes do original): o painel lê no carregamento para saber
    # que há PDF e mostrar o tamanho, sem tocar no bloco pesado de base64.
    indice = {a: (len(b64) // 4) * 3 - b64.count("=") for a, b64 in pdfs.items()}

    html = template.read_text(encoding="utf-8")
    marcadores = list(PARTES) + ["__DATASET_JSON__", "__DATASET_CNCA_JSON__", "__PDFS_JSON__",
                                 "__PDFS_INDICE_JSON__", "__CHARTJS_URL__", "__CHARTJS_SRI__"]
    for marcador in marcadores:
        if html.count(marcador) != 1:
            raise SystemExit(f"o template deveria ter exatamente um {marcador}; tem {html.count(marcador)}")

    for marcador, arquivo in PARTES.items():
        html = html.replace(marcador, _codigo_para_html((web / arquivo).read_text(encoding="utf-8"), arquivo))
    html = (html.replace("__CHARTJS_URL__", CHARTJS_URL).replace("__CHARTJS_SRI__", CHARTJS_SRI)
            .replace("__DATASET_CNCA_JSON__", _json_para_html(cnca))
            .replace("__PDFS_INDICE_JSON__", _json_para_html(indice))
            .replace("__PDFS_JSON__", _json_para_html(pdfs))
            .replace("__DATASET_JSON__", _json_para_html(dados)))
    saida.write_text(html, encoding="utf-8", newline="\n")
    return saida


if __name__ == "__main__":
    destino = montar()
    print(f"{destino} ({destino.stat().st_size / 1024:.0f} KB)")
    sys.exit(0)
