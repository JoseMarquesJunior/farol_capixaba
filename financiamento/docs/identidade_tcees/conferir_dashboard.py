"""Renderiza o `dashboard.html` gerado e tira um screenshot de cada visão.

    python docs/identidade_tcees/conferir_dashboard.py

Serve para conferir a identidade visual aplicada contra `viewport.png` (o
painel real). Também reporta erro de console: como o HTML é autocontido, um
erro de JavaScript aqui passaria despercebido de outro jeito.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PASTA = Path(__file__).resolve().parent
DASHBOARD = PASTA.parent.parent / "dashboard.html"
SAIDA = PASTA / "conferencia"

VISOES = ["conformidade", "fluxo", "panorama", "municipio", "escolas", "programas"]


def main() -> int:
    if not DASHBOARD.exists():
        raise SystemExit(f"{DASHBOARD} não existe — rode `python -m financiamento.build_dashboard`")
    SAIDA.mkdir(exist_ok=True)
    erros: list[str] = []
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1440, "height": 900},
                                    device_scale_factor=2, locale="pt-BR")
        pagina.on("pageerror", lambda e: erros.append(f"pageerror: {str(e)[:300]}"))
        pagina.on("console", lambda m: erros.append(f"console.error: {m.text[:300]}")
                  if m.type == "error" else None)

        pagina.goto(DASHBOARD.as_uri(), wait_until="load", timeout=180_000)
        pagina.wait_for_timeout(6_000)
        pagina.screenshot(path=str(SAIDA / "00-topo.png"))
        print("00-topo.png")

        for visao in VISOES:
            try:
                pagina.evaluate(f"() => irPara({visao!r})")
            except Exception as e:
                erros.append(f"irPara({visao}): {type(e).__name__}: {e}")
                continue
            pagina.wait_for_timeout(3_000)
            pagina.evaluate("() => window.scrollTo(0, 0)")
            pagina.screenshot(path=str(SAIDA / f"{visao}.png"))
            print(f"{visao}.png")

        # Conferência de tokens: os valores aplicados têm de ser os do painel.
        medido = pagina.evaluate("""() => {
          const cs = getComputedStyle(document.documentElement);
          const el = (s) => document.querySelector(s);
          const st = (s, p) => { const e = el(s); return e ? getComputedStyle(e)[p] : null; };
          return {
            base: cs.fontSize,
            fonte: getComputedStyle(document.body).fontFamily,
            fundo: getComputedStyle(document.body).backgroundColor,
            marinho: cs.getPropertyValue('--tc-marinho').trim(),
            raio: cs.getPropertyValue('--tc-raio').trim(),
            crumbFundo: st('.migalhas', 'backgroundColor'),
            crumbBorda: st('.migalhas', 'borderBottomColor'),
            crumbItem: st('.migalhas li', 'lineHeight'),
            cardRaio: st('.card', 'borderRadius'),
            cardSombra: st('.card', 'boxShadow'),
            thPeso: st('th', 'fontWeight'),
            thPad: st('th', 'padding'),
          };
        }""")
        navegador.close()

    print("\n--- valores aplicados ---")
    for k, v in medido.items():
        print(f"  {k}: {v}")
    print(f"\n--- erros de página: {len(erros)} ---")
    for e in erros[:15]:
        print(f"  {e}")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
