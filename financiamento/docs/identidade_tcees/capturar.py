"""Captura a identidade visual real do Painel de Controle do TCE-ES.

    python docs/identidade_tcees/capturar.py

O painel é uma SPA Angular: buscar o HTML sem executar JavaScript traz só a
casca. Este script abre a página num Chromium de verdade, espera a renderização
e extrai os estilos *computados* — nada aqui é estimado a partir do screenshot.

Saídas (nesta mesma pasta):
  pagina_completa.png   screenshot da página inteira
  viewport.png          screenshot do viewport inicial (1440x900)
  extracao.json         tudo que foi lido do DOM
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PASTA = Path(__file__).resolve().parent
URL = ("https://paineldecontrole.tcees.tc.br/areasTematicas/educacao/visaoGeral/"
       "2026/todos/todos/null/null/1")

# Executado no navegador. Devolve um dicionário JSON-serializável.
EXTRACAO_JS = r"""
() => {
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const s = getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
  };

  // ---- variáveis CSS customizadas -----------------------------------------
  // getComputedStyle nem sempre enumera custom properties, então também varremos
  // as folhas de estilo atrás de regras que definam --*.
  const varsComputadas = {};
  const cs = getComputedStyle(document.documentElement);
  for (let i = 0; i < cs.length; i++) {
    const p = cs[i];
    if (p.startsWith('--')) varsComputadas[p] = cs.getPropertyValue(p).trim();
  }
  const varsFolhas = {};
  const seletoresVar = new Set();
  for (const sheet of Array.from(document.styleSheets)) {
    let regras;
    try { regras = sheet.cssRules; } catch (e) { continue; }  // CORS
    const anda = (lista) => {
      for (const r of Array.from(lista || [])) {
        if (r.cssRules) { anda(r.cssRules); continue; }
        if (!r.style) continue;
        for (let i = 0; i < r.style.length; i++) {
          const p = r.style[i];
          if (!p.startsWith('--')) continue;
          seletoresVar.add(r.selectorText);
          varsFolhas[p] = varsFolhas[p] || [];
          varsFolhas[p].push({seletor: r.selectorText, valor: r.style.getPropertyValue(p).trim()});
        }
      }
    };
    anda(regras);
  }

  // ---- estilos computados de componentes ----------------------------------
  const PROPS = ['color', 'background-color', 'background-image', 'font-family',
    'font-size', 'font-weight', 'line-height', 'letter-spacing', 'border-radius',
    'box-shadow', 'border', 'border-top', 'border-bottom', 'padding', 'margin',
    'text-transform', 'height', 'min-height', 'width', 'gap', 'text-decoration-line'];

  const descreve = (el) => {
    const s = getComputedStyle(el);
    const out = {
      tag: el.tagName.toLowerCase(),
      classe: (el.getAttribute('class') || '').slice(0, 200),
      id: el.id || null,
      texto: (el.innerText || '').trim().slice(0, 120),
      rect: (() => { const r = el.getBoundingClientRect();
        return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}; })(),
    };
    for (const p of PROPS) {
      const v = s.getPropertyValue(p);
      if (v && v !== 'none' && v !== 'normal' && v !== 'auto' && v !== '0px') out[p] = v;
    }
    return out;
  };

  const ALVOS = {
    header: 'header, .header, [class*="header"], mat-toolbar, .navbar, .topbar',
    nav: 'nav, .nav, [class*="menu"], [class*="sidebar"], [class*="sidenav"], mat-sidenav',
    breadcrumb: '[class*="breadcrumb"], [class*="migalha"], [class*="caminho"]',
    botao: 'button, .btn, [class*="button"], [role="button"]',
    card: '[class*="card"], mat-card, [class*="indicador"], [class*="painel"], [class*="box"], [class*="widget"]',
    tabela: 'table, mat-table, [class*="table"], [class*="tabela"], [class*="grid"]',
    th: 'th, mat-header-cell, thead td',
    td: 'td, mat-cell',
    link: 'a[href]',
    titulo: 'h1, h2, h3, h4',
    aba: '[role="tab"], mat-tab, [class*="tab"]',
    campo: 'select, input, mat-select, [class*="select"], [class*="filtro"]',
  };

  const componentes = {};
  for (const [nome, sel] of Object.entries(ALVOS)) {
    const achados = [];
    let els;
    try { els = document.querySelectorAll(sel); } catch (e) { els = []; }
    for (const el of Array.from(els)) {
      if (!vis(el)) continue;
      achados.push(descreve(el));
      if (achados.length >= 12) break;
    }
    componentes[nome] = achados;
  }

  // ---- paleta real: frequência das cores computadas em elementos visíveis ---
  const conta = (mapa, chave, el) => {
    if (!chave || chave === 'rgba(0, 0, 0, 0)' || chave === 'transparent') return;
    const e = mapa[chave] = mapa[chave] || {n: 0, exemplos: []};
    e.n++;
    if (e.exemplos.length < 6) {
      e.exemplos.push(el.tagName.toLowerCase() + (el.className && typeof el.className === 'string'
        ? '.' + el.className.trim().split(/\s+/).slice(0, 3).join('.') : ''));
    }
  };
  const corTexto = {}, corFundo = {}, corBorda = {}, fontes = {}, tamanhos = {},
        pesos = {}, raios = {}, sombras = {};
  let n = 0;
  for (const el of Array.from(document.querySelectorAll('*'))) {
    if (n++ > 12000) break;
    if (!vis(el)) continue;
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    // cor de texto só conta se o elemento tem texto próprio
    const temTexto = Array.from(el.childNodes).some(
      (c) => c.nodeType === 3 && c.textContent.trim().length > 0);
    if (temTexto) {
      conta(corTexto, s.color, el);
      fontes[s.fontFamily] = (fontes[s.fontFamily] || 0) + 1;
      tamanhos[s.fontSize] = (tamanhos[s.fontSize] || 0) + 1;
      pesos[s.fontWeight] = (pesos[s.fontWeight] || 0) + 1;
    }
    if (r.width * r.height > 200) conta(corFundo, s.backgroundColor, el);
    if (s.borderTopWidth !== '0px' || s.borderLeftWidth !== '0px') conta(corBorda, s.borderTopColor, el);
    if (s.borderRadius && s.borderRadius !== '0px') raios[s.borderRadius] = (raios[s.borderRadius] || 0) + 1;
    if (s.boxShadow && s.boxShadow !== 'none') sombras[s.boxShadow] = (sombras[s.boxShadow] || 0) + 1;
  }
  const ordena = (o) => Object.fromEntries(
    Object.entries(o).sort((a, b) => (b[1].n || b[1]) - (a[1].n || a[1])).slice(0, 40));

  // ---- logos e favicon -----------------------------------------------------
  const imagens = Array.from(document.querySelectorAll('img, svg image, use'))
    .filter(vis)
    .map((el) => ({tag: el.tagName.toLowerCase(),
      src: el.getAttribute('src') || el.getAttribute('href') || el.getAttribute('xlink:href'),
      alt: el.getAttribute('alt'), classe: el.getAttribute('class'),
      rect: (() => { const r = el.getBoundingClientRect();
        return {w: Math.round(r.width), h: Math.round(r.height)}; })()}))
    .slice(0, 40);
  const icones = Array.from(document.querySelectorAll('link[rel*="icon"], link[rel="manifest"]'))
    .map((l) => ({rel: l.getAttribute('rel'), href: l.href, sizes: l.getAttribute('sizes')}));

  // ---- fontes carregadas ---------------------------------------------------
  const faces = [];
  for (const sheet of Array.from(document.styleSheets)) {
    let regras; try { regras = sheet.cssRules; } catch (e) { continue; }
    for (const r of Array.from(regras || [])) {
      if (r.constructor.name === 'CSSFontFaceRule' || r.type === 5) {
        faces.push({familia: r.style.getPropertyValue('font-family'),
                    peso: r.style.getPropertyValue('font-weight'),
                    src: r.style.getPropertyValue('src').slice(0, 300)});
      }
    }
  }

  // ---- texto da navegação: serve para montar o breadcrumb do dashboard ------
  const textoNav = Array.from(document.querySelectorAll('nav a, nav button, [class*="menu"] a, [class*="breadcrumb"] *, [role="tab"]'))
    .filter(vis).map((el) => (el.innerText || '').trim()).filter((t) => t && t.length < 60).slice(0, 60);

  return {
    url: location.href, titulo: document.title,
    varsComputadas, varsFolhas, seletoresVar: Array.from(seletoresVar).slice(0, 40),
    componentes,
    paleta: {texto: ordena(corTexto), fundo: ordena(corFundo), borda: ordena(corBorda)},
    tipografia: {familias: ordena(fontes), tamanhos: ordena(tamanhos), pesos: ordena(pesos), faces: faces.slice(0, 30)},
    forma: {raios: ordena(raios), sombras: ordena(sombras)},
    imagens, icones, textoNav,
    folhas: Array.from(document.styleSheets).map((s) => s.href).filter(Boolean),
  };
}
"""


def main() -> int:
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1440, "height": 900},
                                    device_scale_factor=2, locale="pt-BR")
        erros: list[str] = []
        pagina.on("console", lambda m: erros.append(f"console.{m.type}: {m.text[:200]}")
                  if m.type in ("error", "warning") else None)
        pagina.on("pageerror", lambda e: erros.append(f"pageerror: {str(e)[:200]}"))

        print(f"abrindo {URL}")
        try:
            pagina.goto(URL, wait_until="networkidle", timeout=120_000)
        except Exception as e:           # networkidle pode não chegar numa SPA com polling
            print(f"  networkidle nao atingido ({type(e).__name__}); seguindo com load")
            pagina.goto(URL, wait_until="load", timeout=120_000)
        pagina.wait_for_timeout(8_000)   # a SPA ainda monta componentes depois do networkidle

        pagina.screenshot(path=str(PASTA / "viewport.png"))
        pagina.screenshot(path=str(PASTA / "pagina_completa.png"), full_page=True)
        print("screenshots salvos")

        dados = pagina.evaluate(EXTRACAO_JS)
        dados["_erros_pagina"] = erros[:40]
        dados["_texto_visivel_chars"] = pagina.evaluate("() => document.body.innerText.length")
        (PASTA / "extracao.json").write_text(
            json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"extracao.json salvo; texto visivel: {dados['_texto_visivel_chars']} chars")
        navegador.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
