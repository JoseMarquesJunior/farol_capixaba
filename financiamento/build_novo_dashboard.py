"""Monta o painel novo e o papel de trabalho do CNCA a partir de `web_novo/`.

    python -m financiamento.build_novo_dashboard

Gera dois arquivos autocontidos, lado a lado:

* `novo_dashboard.html` — o painel de financiamento da educação, refeito a partir
  da auditoria de UX (triagem, panorama, dossiê do município, programas e
  metodologia);
* `novo_cnca_evidencias.html` — o papel de trabalho da fiscalização do CNCA, que
  saiu do painel para um arquivo próprio (decisão D3 da auditoria).

Os dois se linkam por caminho relativo: ficam na mesma pasta.

    python -m financiamento.build_novo_dashboard --site

monta também a versão PÚBLICA do painel, publicada no site Farol Capixaba da
Educação (`docs/financiamento_educacao.html`, na raiz do repositório). Ela difere
da local em duas coisas, e só nelas:

* não leva o papel de trabalho do CNCA nem links para ele — é instrumento de uma
  fiscalização, com indício de risco por município nomeado, e não vai a público;
* mascara CPF e telefone de pessoa física nos campos de nome e de documento
  (`mascarar_pessoais`). O dado aberto do TCE-ES traz CPF digitado no nome do credor
  ou no lugar do CNPJ da contratada; republicá-lo num site novo é exposição sem
  necessidade (LGPD). A versão local dos auditores continua íntegra.

O `dashboard.html` antigo e os fontes dele (`web/`, `build_dashboard.py`) não são
tocados. Daquele montador vêm só as funções que garantem o dado embutido de forma
segura e os PDFs do SIOPE conferidos por SHA-256 — reusadas, não copiadas.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from financiamento import build_dashboard as base

PASTA = Path(__file__).resolve().parent
WEB_NOVO = PASTA / "web_novo"
SAIDA_PAINEL = PASTA / "novo_dashboard.html"
SAIDA_CNCA = PASTA / "novo_cnca_evidencias.html"
#: O site Farol Capixaba da Educação (GitHub Pages, servido de main /docs). Só se
#: ACRESCENTA arquivo ali: os três que já existem se linkam por caminho relativo e
#: não podem mudar de nome nem de lugar.
SAIDA_SITE = PASTA.parent / "docs" / "financiamento_educacao.html"

#: Configuração embutida na página (bloco `config`, lida por painel.js).
CONFIG_LOCAL = {"cnca": SAIDA_CNCA.name, "voltar": None}
CONFIG_SITE = {"cnca": None, "voltar": {"href": "index.html", "rotulo": "Farol Capixaba da Educação"}}

#: Campos em que o município às vezes digita CPF ou telefone de pessoa física: nomes
#: (credor, contratada, unidade executora, recebedor) e o objeto do contrato.
#: Descrição de item fica de fora: os números de 11 dígitos dela são códigos de rota.
CAMPOS_TEXTO_PESSOAL = {"credor_nome", "contratada", "contratado", "uex", "nome_origem", "objeto", "favorecido"}
#: Campos de documento: com 11 dígitos é CPF (CNPJ tem 14) — o valor inteiro sai.
CAMPOS_DOCUMENTO = {"credor", "cnpj_contratada", "cnpj_contratado", "cnpj_uex"}
_CPF_NO_TEXTO = re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)|(?<=[^\W\d_]|\s)\d{11}(?!\d)")
_TELEFONE = re.compile(r"\(\d{2}\)\s?\d{4,5}-?\d{4}(?!\d)")
CPF_OMITIDO = "[CPF omitido]"
TELEFONE_OMITIDO = "[telefone omitido]"

_CSS = {"__DESIGN_TOKENS_CSS__": "design-tokens.css", "__ESTILO_CSS__": "estilo.css"}
#: Marcador -> arquivo em `web_novo/`, na ordem em que entram na página. A ordem
#: importa: cada parte só usa, no carregamento, o que as anteriores definiram.
PARTES_PAINEL = {**_CSS,
    "__NUCLEO_JS__": "nucleo.js", "__GLOSSARIO_JS__": "glossario.js", "__DADOS_JS__": "dados.js",
    "__FONTE_JS__": "fonte.js", "__GRAFICOS_JS__": "graficos.js", "__NIVEL3_JS__": "nivel3.js",
    "__CONFORMIDADE_JS__": "conformidade.js", "__PANORAMA_JS__": "panorama.js", "__ESCOLAS_JS__": "escolas.js",
    "__MUNICIPIO_JS__": "municipio.js", "__PROGRAMAS_JS__": "programas.js", "__METODOLOGIA_JS__": "metodologia.js",
    "__PAINEL_JS__": "painel.js",
}
PARTES_CNCA = {**_CSS,
    "__NUCLEO_JS__": "nucleo.js", "__GLOSSARIO_JS__": "glossario.js", "__DADOS_JS__": "dados.js",
    "__FONTE_JS__": "fonte.js", "__CNCA_JS__": "cnca.js",
}

#: O que o papel de trabalho do CNCA precisa do dataset geral: os metadados de
#: coleta (para o carimbo e o "ver fonte") e a lista de entes. O resto — 18 MB —
#: fica fora; as consultas do CNCA vêm no dataset dele.
META_CNCA = ("esquema", "anos", "ano_mais_recente", "n_municipios", "gerado_em", "versao",
             "extraido_em_por_fonte", "anexos", "minimo_mde_pct", "minimo_fundeb_profissionais_pct")


def dataset_reduzido(dados: dict) -> dict:
    """O pedaço do dataset geral que a página do CNCA usa."""
    meta = {k: dados["meta"][k] for k in META_CNCA if k in dados["meta"]}
    meta["indicadores"] = {}  # os do CNCA entram pela própria página, a partir da matriz
    return {"meta": meta, "entes": dados.get("entes", [])}


def _embutir(template: Path, partes: dict[str, str], web: Path, blocos: dict[str, str]) -> str:
    """Substitui cada marcador do template por uma parte de `web` ou por um bloco pronto."""
    html = template.read_text(encoding="utf-8")
    for marcador in list(partes) + list(blocos):
        if html.count(marcador) != 1:
            raise SystemExit(f"{template.name}: deveria ter exatamente um {marcador}; tem {html.count(marcador)}")
    for marcador, arquivo in partes.items():
        html = html.replace(marcador, base._codigo_para_html((web / arquivo).read_text(encoding="utf-8"), arquivo))
    for marcador, conteudo in blocos.items():
        html = html.replace(marcador, conteudo)
    return html


def _ler_dataset(caminho: Path) -> dict:
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    if dados["meta"]["esquema"] != base.SCHEMA_ESPERADO:
        raise SystemExit(f"esquema {dados['meta']['esquema']} do dataset != {base.SCHEMA_ESPERADO} esperado pelo template")
    return dados


def _mascarar_valor(campo: str, v, conta: Counter):
    if not isinstance(v, str):
        return v
    if campo in CAMPOS_DOCUMENTO:
        if len(re.sub(r"\D", "", v)) == 11 and not re.search(r"[^\d.\-/\s]", v):
            conta["cpf_em_documento"] += 1
            return CPF_OMITIDO
        return v
    if campo in CAMPOS_TEXTO_PESSOAL:
        v, n = _CPF_NO_TEXTO.subn(CPF_OMITIDO, v)
        conta["cpf_em_texto"] += n
        v, n = _TELEFONE.subn(TELEFONE_OMITIDO, v)
        conta["telefone"] += n
    return v


def _andar_mascarando(obj, conta: Counter) -> None:
    if isinstance(obj, dict):
        if "colunas" in obj and "linhas" in obj:  # tabela colunar: dicionário de valores + linhas
            colunas, dic = obj["colunas"], obj.get("dicionario") or {}
            for c, valores in dic.items():
                dic[c] = [_mascarar_valor(c, v, conta) for v in valores]
            for linha in obj["linhas"]:
                for i, c in enumerate(colunas):
                    if c not in dic:
                        linha[i] = _mascarar_valor(c, linha[i], conta)
            return
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                _andar_mascarando(v, conta)
            else:
                obj[k] = _mascarar_valor(k, v, conta)
    elif isinstance(obj, list):
        for x in obj:
            if isinstance(x, (dict, list)):
                _andar_mascarando(x, conta)


def mascarar_pessoais(dados: dict) -> Counter:
    """Troca CPF e telefone de pessoa física por "[CPF omitido]"/"[telefone omitido]".

    Altera `dados` no lugar e devolve quantas trocas fez de cada tipo. Só olha os
    campos de nome e de documento (CAMPOS_TEXTO_PESSOAL, CAMPOS_DOCUMENTO): ids de
    consulta, SHA-256 e endereços têm sequências de 11 dígitos que não são CPF, e não
    podem mudar — são a proveniência.
    """
    conta: Counter = Counter()
    _andar_mascarando(dados, conta)
    return conta


def montar_painel(dados: dict, saida: Path = SAIDA_PAINEL, web: Path = WEB_NOVO, bruto: Path = base.BRUTO,
                  config: dict | None = None) -> Path:
    pdfs, problemas = base.pdfs_embutidos(dados, bruto)
    for p in problemas:
        print(f"aviso: PDF fora da página — {p}", file=sys.stderr)
    indice = {a: (len(b64) // 4) * 3 - b64.count("=") for a, b64 in pdfs.items()}
    html = _embutir(web / "painel.html", PARTES_PAINEL, web, {
        "__CHARTJS_URL__": base.CHARTJS_URL, "__CHARTJS_SRI__": base.CHARTJS_SRI,
        "__CONFIG_JSON__": base._json_para_html(config if config is not None else CONFIG_LOCAL),
        "__PDFS_INDICE_JSON__": base._json_para_html(indice), "__PDFS_JSON__": base._json_para_html(pdfs),
        "__DATASET_JSON__": base._json_para_html(dados)})
    saida.write_text(html, encoding="utf-8", newline="\n")
    return saida


def montar_site(dataset: Path = base.DATASET, saida: Path = SAIDA_SITE, web: Path = WEB_NOVO,
                bruto: Path = base.BRUTO) -> tuple[Path, Counter]:
    """A versão pública, para o Farol Capixaba: sem o CNCA e com o dado pessoal mascarado."""
    dados = _ler_dataset(dataset)  # leitura própria: a máscara altera o dict no lugar
    conta = mascarar_pessoais(dados)
    return montar_painel(dados, saida, web, bruto, CONFIG_SITE), conta


def montar_cnca(dados: dict, cnca: dict, saida: Path = SAIDA_CNCA, web: Path = WEB_NOVO) -> Path:
    html = _embutir(web / "cnca.html", PARTES_CNCA, web, {
        "__DATASET_JSON__": base._json_para_html(dataset_reduzido(dados)),
        "__DATASET_CNCA_JSON__": base._json_para_html(cnca)})
    saida.write_text(html, encoding="utf-8", newline="\n")
    return saida


def montar(dataset: Path = base.DATASET, dataset_cnca: Path = base.DATASET_CNCA, saida_painel: Path = SAIDA_PAINEL,
           saida_cnca: Path = SAIDA_CNCA, web: Path = WEB_NOVO, bruto: Path = base.BRUTO) -> tuple[Path, Path]:
    dados = _ler_dataset(dataset)
    cnca = base._dataset_cnca(dataset_cnca)
    return (montar_painel(dados, saida_painel, web, bruto), montar_cnca(dados, cnca, saida_cnca, web))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Monta o painel novo e o papel de trabalho do CNCA.")
    ap.add_argument("--site", action="store_true",
                    help="monta também a versão pública do site Farol Capixaba (docs/financiamento_educacao.html)")
    args = ap.parse_args()
    for destino in montar():
        print(f"{destino} ({destino.stat().st_size / 1024:.0f} KB)")
    if args.site:
        destino, conta = montar_site()
        print(f"{destino} ({destino.stat().st_size / 1024:.0f} KB) — versão pública, sem o CNCA; "
              f"mascarados: {conta['cpf_em_documento']} CPF em campo de documento, {conta['cpf_em_texto']} em nome ou objeto, "
              f"{conta['telefone']} telefone(s)")
    sys.exit(0)
