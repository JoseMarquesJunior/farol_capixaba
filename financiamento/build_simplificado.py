"""Monta o painel simplificado do financiamento a partir de `web_simplificado/`.

    python -m financiamento.build_simplificado

Gera `financiamento-simplificado.html`: o dossiê do município numa página
contínua, com o menu fixo à esquerda — Resumo (fluxo fonte → subfunção em
primeiro), Receita, Despesa e Quem recebeu. Fica de fora o que o
pedido do leiaute excluiu: conformidade (mínimos constitucionais, entregas,
remessas), obras, escolas e programas federais.

Os dados vêm de `dados/processado/dataset_simplificado.json`, gerado por
`python -m financiamento.etl.simplificado` só com dados abertos do TCE-ES (e as
tabelas fixas de municípios e do Censo) — não do dataset do painel completo.

Só o leiaute e as seções são novos (`web_simplificado/`): os módulos de dados,
gráficos e fonte vêm de `web_novo/` SEM cópia — mudar o painel novo muda este
também, de propósito. `web_novo/` e os montadores existentes não são tocados.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from financiamento import build_dashboard as base
from financiamento.etl.simplificado import SAIDA as DATASET

PASTA = Path(__file__).resolve().parent
WEB_SIMPLIFICADO = PASTA / "web_simplificado"
WEB_NOVO = PASTA / "web_novo"
SAIDA = PASTA / "financiamento-simplificado.html"

#: Marcador do template -> (pasta, arquivo), na ordem em que entram na página.
#: A ordem importa: cada parte só usa, no carregamento, o que as anteriores
#: definiram. Os compartilhados apontam para `web_novo/` sem cópia.
PARTES = {
    "__DESIGN_TOKENS_CSS__": (WEB_NOVO, "design-tokens.css"),
    "__ESTILO_CSS__": (WEB_NOVO, "estilo.css"),
    "__ESTILO_SIMPLIFICADO_CSS__": (WEB_SIMPLIFICADO, "estilo-simplificado.css"),
    "__NUCLEO_JS__": (WEB_NOVO, "nucleo.js"),
    "__GLOSSARIO_JS__": (WEB_NOVO, "glossario.js"),
    "__DADOS_JS__": (WEB_NOVO, "dados.js"),
    "__FONTE_JS__": (WEB_NOVO, "fonte.js"),
    "__GRAFICOS_JS__": (WEB_NOVO, "graficos.js"),
    "__NIVEL3_JS__": (WEB_NOVO, "nivel3.js"),
    # Sem seção de metodologia: no lugar do metodologia.js do painel novo, só o
    # glossário restrito a esta versão e as ressalvas que vão dentro de cada card.
    "__GLOSSARIO_SIMPLIFICADO_JS__": (WEB_SIMPLIFICADO, "glossario-simplificado.js"),
    "__MUNICIPIO_SIMPLIFICADO_JS__": (WEB_SIMPLIFICADO, "municipio-simplificado.js"),
    "__PAINEL_SIMPLIFICADO_JS__": (WEB_SIMPLIFICADO, "painel-simplificado.js"),
}

def montar(dataset: Path = DATASET, saida: Path = SAIDA) -> Path:
    if not dataset.exists():
        raise SystemExit(f"{dataset} não existe: rode antes `python -m financiamento.etl.simplificado`")
    with open(dataset, encoding="utf-8") as f:
        dados = json.load(f)
    if dados["meta"]["esquema"] != base.SCHEMA_ESPERADO:
        raise SystemExit(f"esquema {dados['meta']['esquema']} do dataset != {base.SCHEMA_ESPERADO} esperado pelo template")
    template = WEB_SIMPLIFICADO / "painel.html"
    html = template.read_text(encoding="utf-8")
    blocos = {
        "__CHARTJS_URL__": base.CHARTJS_URL, "__CHARTJS_SRI__": base.CHARTJS_SRI,
        "__DATASET_JSON__": base._json_para_html(dados),
    }
    for marcador in list(PARTES) + list(blocos):
        if html.count(marcador) != 1:
            raise SystemExit(f"{template.name}: deveria ter exatamente um {marcador}; tem {html.count(marcador)}")
    for marcador, (pasta, arquivo) in PARTES.items():
        html = html.replace(marcador, base._codigo_para_html((pasta / arquivo).read_text(encoding="utf-8"), arquivo))
    for marcador, conteudo in blocos.items():
        html = html.replace(marcador, conteudo)
    saida.write_text(html, encoding="utf-8", newline="\n")
    return saida


if __name__ == "__main__":
    destino = montar()
    print(f"{destino} ({destino.stat().st_size / 1024:.0f} KB)")
    sys.exit(0)
