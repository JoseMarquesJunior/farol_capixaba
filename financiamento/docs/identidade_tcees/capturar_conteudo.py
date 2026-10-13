"""Segunda passagem: captura telas do painel que de fato renderizam KPIs,
tabelas e gráficos — a visão geral de Educação em 2026 traz só o painel de
descrição, sem dados.

    python docs/identidade_tcees/capturar_conteudo.py

Aceita o aviso de cookies (ele cobre o rodapé e entra nos screenshots), rola a
página até o fim para disparar o carregamento preguiçoso e só então mede.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PASTA = Path(__file__).resolve().parent
BASE = "https://paineldecontrole.tcees.tc.br"

# Rotas escolhidas por cobrirem componentes diferentes: a mesma visão em ano
# fechado (2024), a visão de indicadores do Estado e a home do painel.
ROTAS = {
    "educacao_2024": "/areasTematicas/educacao/visaoGeral/2024/todos/todos/null/null/1",
    "educacao_2026": "/areasTematicas/educacao/visaoGeral/2026/todos/todos/null/null/1",
    "estado": "/estado/visaoGeral/2024/null/null/null/null/1",
    "home": "/",
}

MEDE_JS = r"""
() => {
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const s = getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
  };
  const PROPS = ['color', 'background-color', 'font-family', 'font-size', 'font-weight',
    'border-radius', 'box-shadow', 'border', 'border-bottom', 'padding', 'height', 'text-align'];
  const descreve = (el) => {
    const s = getComputedStyle(el);
    const o = {tag: el.tagName.toLowerCase(), classe: (el.getAttribute('class') || '').slice(0, 120),
               texto: (el.innerText || '').trim().slice(0, 80)};
    for (const p of PROPS) {
      const v = s.getPropertyValue(p);
      if (v && v !== 'none' && v !== 'normal' && v !== '0px') o[p] = v;
    }
    return o;
  };
  const pega = (sel, max = 6) => {
    let els; try { els = document.querySelectorAll(sel); } catch (e) { return []; }
    return Array.from(els).filter(vis).slice(0, max).map(descreve);
  };
  return {
    etiqueta: pega('.etiqueta, .etiqueta .conteudo, .valor-etiqueta, .descricao-etiqueta'),
    painel: pega('.p-panel, .p-panel-header, .p-panel-content'),
    datatable: pega('#datagrid .p-datatable, .p-datatable-thead th, .p-datatable-tbody td'),
    botao: pega('.p-button, button.btn, .btn-primary'),
    aba: pega('.p-tabview-nav li, [role="tab"], .nav-tabs li'),
    nota: pega('[class*="nota-"], [class*="label-"], .circuloNotasIEG, .circuloNotasISP'),
    grafico: pega('canvas, svg.highcharts-root, .highcharts-container, [class*="grafico"]', 8),
    indicador: pega('[class*="indicador"]', 8),
    alerta: pega('#alerta, .alert, [class*="alerta"]'),
    legenda: pega('[class*="legenda"]', 8),
    textoPagina: document.body.innerText.slice(0, 2500),
  };
}
"""


def main() -> int:
    resultado = {}
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        ctx = navegador.new_context(viewport={"width": 1440, "height": 900},
                                    device_scale_factor=2, locale="pt-BR")
        pagina = ctx.new_page()
        for nome, rota in ROTAS.items():
            url = BASE + rota
            print(f"-> {nome}: {url}")
            try:
                pagina.goto(url, wait_until="networkidle", timeout=120_000)
            except Exception:
                pagina.goto(url, wait_until="load", timeout=120_000)
            pagina.wait_for_timeout(6_000)
            # O aviso de cookies fica fixo no rodapé e entraria em todo screenshot.
            try:
                pagina.get_by_role("button", name="Aceitar e fechar").click(timeout=4_000)
                pagina.wait_for_timeout(800)
            except Exception:
                pass
            # Rola até o fim: o painel carrega blocos sob demanda.
            pagina.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            pagina.wait_for_timeout(5_000)
            pagina.evaluate("() => window.scrollTo(0, 0)")
            pagina.wait_for_timeout(1_500)
            pagina.screenshot(path=str(PASTA / f"{nome}.png"), full_page=True)
            resultado[nome] = pagina.evaluate(MEDE_JS)
            print(f"   {len(resultado[nome]['textoPagina'])} chars de texto; "
                  f"etiquetas={len(resultado[nome]['etiqueta'])} "
                  f"tabela={len(resultado[nome]['datatable'])} "
                  f"grafico={len(resultado[nome]['grafico'])}")
        navegador.close()
    (PASTA / "extracao_conteudo.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print("extracao_conteudo.json salvo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
