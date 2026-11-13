"""Monta a página das redes do financiamento da educação a partir de `web_grafos/`.

    python -m financiamento.etl.grafos      # antes: gera dados/processado/grafos.json
    python -m financiamento.build_grafos    # grava financiamento/redes_financiamento.html

Um arquivo só, autocontido e sem nenhuma chamada à internet (nem biblioteca de
CDN: o motor do grafo é próprio, em `web_grafos/motor.js`). A identidade visual,
as tabelas e a exportação CSV/Excel vêm do painel novo (`web_novo/`), reusadas
— não copiadas —, para que o mesmo componente tenha a mesma cara nas duas páginas.
As duas ficam na mesma pasta e se linkam por caminho relativo.

O `dashboard.html`, o `novo_dashboard.html` e os fontes deles não são tocados.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from financiamento import build_dashboard as base

PASTA = Path(__file__).resolve().parent
WEB = PASTA / "web_grafos"
WEB_NOVO = PASTA / "web_novo"
DATASET = PASTA / "dados" / "processado" / "grafos.json"
INSIGHTS = PASTA / "dados" / "processado" / "insights.json"
SAIDA = PASTA / "redes_financiamento.html"
ESQUEMA_ESPERADO = 1

#: Marcador → arquivo, na ordem em que entram na página. A ordem importa: cada
#: parte só usa, no carregamento, o que as anteriores definiram.
PARTES = {
    "__DESIGN_TOKENS_CSS__": WEB_NOVO / "design-tokens.css",
    "__ESTILO_CSS__": WEB_NOVO / "estilo.css",
    "__REDES_CSS__": WEB / "redes.css",
    "__NUCLEO_JS__": WEB_NOVO / "nucleo.js",
    "__DADOS_REDES_JS__": WEB / "dados_redes.js",
    "__MOTOR_JS__": WEB / "motor.js",
    "__COMPONENTES_JS__": WEB / "componentes.js",
    "__FORNECEDORES_JS__": WEB / "fornecedores.js",
    "__MUNICIPIOS_JS__": WEB / "municipios.js",
    "__OBRAS_JS__": WEB / "obras.js",
    "__INSIGHTS_JS__": WEB / "insights.js",
    "__EMPRESA_JS__": WEB / "empresa.js",
    "__METODOLOGIA_JS__": WEB / "metodologia.js",
    "__APP_JS__": WEB / "app.js",
}
#: O painel de financiamento, para os links "dossiê do município" (mesma pasta).
CONFIG = {"painel": "novo_dashboard.html"}


def ler_dataset(caminho: Path = DATASET) -> dict:
    if not caminho.exists():
        raise SystemExit(f"{caminho} não existe — rode antes `python -m financiamento.etl.grafos`")
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    if dados.get("meta", {}).get("esquema") != ESQUEMA_ESPERADO:
        raise SystemExit(f"esquema {dados.get('meta', {}).get('esquema')} de {caminho.name} != {ESQUEMA_ESPERADO} esperado pela página")
    return dados


def ler_insights(dados: dict, caminho: Path = INSIGHTS) -> dict:
    """A aba Insights: o insights.json do ETL, se existe; senão, só os fatos, calculados aqui
    mesmo (são determinísticos e rápidos) — a aba nunca fica vazia por falta de uma etapa."""
    from financiamento.etl import insights as ins

    try:
        ins.calcular_fatos(dados)
    except (KeyError, ValueError, IndexError, TypeError) as exc:   # dado incompleto (ex.: o mínimo dos testes)
        return {"meta": {"esquema": ins.ESQUEMA, "redacao": None, "aviso": f"fatos não calculados ({type(exc).__name__})"},
                "fatos": [], "insights": [], "recusados": []}
    if caminho.exists():
        with open(caminho, encoding="utf-8") as f:
            salvo = json.load(f)
        fatos = ins.calcular_fatos(dados)
        if salvo.get("meta", {}).get("fatos_sha256") == ins.hashlib.sha256(
                json.dumps(fatos, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest():
            return salvo
        # Os dados mudaram depois da redação: vale o fato novo, e a página avisa.
        return {**ins.montar(dados, anterior=salvo), "insights": [], "recusados": []}
    return ins.montar(dados)


def montar(dados: dict | None = None, saida: Path = SAIDA, template: Path = WEB / "redes.html",
           config: dict | None = None) -> Path:
    dados = dados if dados is not None else ler_dataset()
    if "insights" not in dados:
        dados = {**dados, "insights": ler_insights(dados)}
    html = template.read_text(encoding="utf-8")
    blocos = {"__CONFIG_JSON__": base._json_para_html(CONFIG if config is None else config),
              "__DATASET_JSON__": base._json_para_html(dados)}
    for marcador in list(PARTES) + list(blocos):
        if html.count(marcador) != 1:
            raise SystemExit(f"{template.name}: deveria ter exatamente um {marcador}; tem {html.count(marcador)}")
    for marcador, arquivo in PARTES.items():
        html = html.replace(marcador, base._codigo_para_html(arquivo.read_text(encoding="utf-8"), arquivo.name))
    for marcador, conteudo in blocos.items():
        html = html.replace(marcador, conteudo)
    saida.write_text(html, encoding="utf-8", newline="\n")
    return saida


if __name__ == "__main__":
    argparse.ArgumentParser(description="Monta financiamento/redes_financiamento.html.").parse_args()
    destino = montar()
    print(f"{destino} ({destino.stat().st_size / 1024:.0f} KB)")
    sys.exit(0)
