"use strict";
/* ============================================================================
   Gráficos em SVG próprio (sem biblioteca: funcionam sem internet e usam as
   cores do tema): o diagrama de fluxo origem → destino (Sankey de duas colunas),
   a régua de distribuição com o mínimo legal e a barra empilhada 100%.
   Todos têm tabela gêmea no card; o tooltip só realça, nunca é o único acesso.
   ========================================================================== */

const SVG_NS = "http://www.w3.org/2000/svg";
function s(tag, attrs, ...filhos) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) el.setAttribute(k, v);
  for (const f of filhos.flat()) if (f !== null && f !== undefined) el.append(f instanceof Node ? f : document.createTextNode(String(f)));
  return el;
}

/* ------------------------------------------------------------------ tooltip */
let _tooltip = null;
function tooltip() {
  if (!_tooltip) { _tooltip = h("div", { class: "tooltip-svg", role: "status", "aria-live": "polite" }); document.body.append(_tooltip); }
  return _tooltip;
}
function mostrarDica(evt, linhas) {
  const t = limpar(tooltip());
  linhas.forEach((l, i) => t.append(h("div", { class: i === 0 ? "valor" : "rotulo" }, l)));
  t.style.display = "block";
  const r = evt.target.getBoundingClientRect();
  const x = evt.clientX !== undefined && evt.clientX !== 0 ? evt.clientX : r.left + r.width / 2;
  const y = evt.clientY !== undefined && evt.clientY !== 0 ? evt.clientY : r.top;
  const larg = t.offsetWidth, alt = t.offsetHeight;
  t.style.left = Math.max(8, Math.min(innerWidth - larg - 8, x + 14)) + "px";
  t.style.top = Math.max(8, Math.min(innerHeight - alt - 8, y + 14)) + "px";
}
function esconderDica() { if (_tooltip) _tooltip.style.display = "none"; }

/* ------------------------------------------------------------------- Sankey */
/**
 * Sankey de duas colunas.
 * origens:  [{id, rotulo, slot}]  (cor = slot da paleta categórica)
 * destinos: [{id, rotulo}]        (neutros: a cor pertence à origem)
 * arestas:  [{de, para, valor}]
 */
function sankey({ origens, destinos, arestas, formatar, titulo }) {
  const cs = cores();
  const largura = Math.max(320, Math.min(1180, (document.querySelector("main") || document.body).clientWidth - 64));
  const estreito = largura < 640;
  const margemE = estreito ? 110 : 250, margemD = estreito ? 110 : 250;
  const lacuna = 10, topo = 8;
  const total = arestas.reduce((t, a) => t + a.valor, 0);
  const somaOrig = new Map(origens.map(o => [o.id, 0])), somaDest = new Map(destinos.map(d => [d.id, 0]));
  arestas.forEach(a => { somaOrig.set(a.de, somaOrig.get(a.de) + a.valor); somaDest.set(a.para, somaDest.get(a.para) + a.valor); });
  const orig = origens.filter(o => somaOrig.get(o.id) > 0), dest = destinos.filter(d => somaDest.get(d.id) > 0);
  const nMax = Math.max(orig.length, dest.length);
  const ALTURA_ROTULO = 34;  // nome + valor: duas linhas
  const altura = Math.max(280, nMax * 50 + topo * 2, nMax * ALTURA_ROTULO + 40);
  const escala = (altura - topo * 2 - lacuna * (nMax - 1)) / total;
  const x0 = margemE, x1 = largura - margemD, larguraNo = 14;

  const posicionar = (nos, soma) => {
    const usado = nos.reduce((t, n) => t + soma.get(n.id) * escala, 0) + lacuna * (nos.length - 1);
    let y = topo + (altura - topo * 2 - usado) / 2;
    const pos = new Map();
    for (const n of nos) { const h_ = Math.max(2, soma.get(n.id) * escala); pos.set(n.id, { y, h: h_, cursor: y }); y += h_ + lacuna; }
    return pos;
  };
  const pO = posicionar(orig, somaOrig), pD = posicionar(dest, somaDest);
  const svg = s("svg", { viewBox: `0 0 ${largura} ${altura}`, width: "100%", height: altura, role: "img",
    "aria-label": (titulo || "Fluxo") + ". Valores na tabela abaixo.", class: "sankey" });
  const gLinks = s("g", {}), gNos = s("g", {}), gRot = s("g", { class: "rotulos" });

  const ordemDest = new Map(dest.map((d, i) => [d.id, i]));
  for (const o of orig) {
    const suas = arestas.filter(a => a.de === o.id && a.valor > 0).sort((a, b) => ordemDest.get(a.para) - ordemDest.get(b.para));
    for (const a of suas) {
      const po = pO.get(o.id), pd = pD.get(a.para), esp = a.valor * escala;
      const ya = po.cursor, yb = pd.cursor; po.cursor += esp; pd.cursor += esp;
      const xm = (x0 + larguraNo + x1) / 2;
      const d = `M${x0 + larguraNo},${ya} C${xm},${ya} ${xm},${yb} ${x1},${yb} L${x1},${yb + esp} C${xm},${yb + esp} ${xm},${ya + esp} ${x0 + larguraNo},${ya + esp} Z`;
      const nomeD = dest.find(x => x.id === a.para).rotulo;
      const dica = [formatar(a.valor), o.rotulo + " → " + nomeD,
        nf(100 * a.valor / somaOrig.get(o.id), 1) + "% da origem · " + nf(100 * a.valor / somaDest.get(a.para), 1) + "% do destino"];
      const p = s("path", { d, fill: cs.serie[o.slot], "fill-opacity": 0.38, class: "aresta", tabindex: 0,
        "aria-label": dica.join(". ") });
      p.addEventListener("pointermove", e => mostrarDica(e, dica));
      p.addEventListener("focus", e => mostrarDica(e, dica));
      p.addEventListener("pointerleave", esconderDica);
      p.addEventListener("blur", esconderDica);
      gLinks.append(p);
    }
  }
  const rotulo = (x, y, anchor, texto, valor) => {
    const corte = estreito ? 15 : 34;
    const curto = texto.length > corte ? texto.slice(0, corte - 1) + "…" : texto;
    return s("text", { x, y: y - 7, "text-anchor": anchor, "dominant-baseline": "middle", fill: cs.ink },
      s("tspan", { "font-weight": "600" }, curto), s("tspan", { x, dy: "1.2em", fill: cs.ink2, "font-size": "12" }, valor));
  };
  // Rótulo no centro do nó; nó fino demais para o rótulo vizinho → o rótulo desce (ou sobe)
  // até caber, preso ao nó por uma linha-guia. Nunca dois rótulos sobrepostos.
  const espacar = (alvos) => {
    for (let i = 1; i < alvos.length; i++) alvos[i].y = Math.max(alvos[i].y, alvos[i - 1].y + ALTURA_ROTULO);
    const fundo = altura - 16, excesso = alvos.length ? alvos[alvos.length - 1].y - fundo : 0;
    if (excesso > 0) {
      alvos[alvos.length - 1].y -= excesso;
      for (let i = alvos.length - 2; i >= 0; i--) alvos[i].y = Math.min(alvos[i].y, alvos[i + 1].y - ALTURA_ROTULO);
    }
    return alvos;
  };
  // Sem a linha-guia quando o rótulo já está na altura do nó; `append` do DOM
  // escreveria "null" no SVG, então o nulo é filtrado antes (ver `comNos`).
  const comNos = (...ns) => ns.filter(Boolean);
  const guia = (xNo, yNo, xRot, yRot) => Math.abs(yNo - yRot) < 3 ? null
    : s("path", { d: `M${xNo},${yNo} L${(xNo + xRot) / 2},${yNo} L${(xNo + xRot) / 2},${yRot} L${xRot},${yRot}`, fill: "none", stroke: cs.axis, "stroke-width": 1 });
  const alvosO = espacar(orig.map(o => ({ o, y: pO.get(o.id).y + pO.get(o.id).h / 2 })));
  for (const { o, y } of alvosO) {
    const p = pO.get(o.id), v = somaOrig.get(o.id), centro = p.y + p.h / 2;
    const dica = [formatar(v), o.rotulo, nf(100 * v / total, 1) + "% do total"];
    const r = s("rect", { x: x0, y: p.y, width: larguraNo, height: p.h, rx: 2, fill: cs.serie[o.slot], tabindex: 0, "aria-label": dica.join(". ") });
    r.addEventListener("pointermove", e => mostrarDica(e, dica)); r.addEventListener("focus", e => mostrarDica(e, dica));
    r.addEventListener("pointerleave", esconderDica); r.addEventListener("blur", esconderDica);
    gNos.append(r);
    gRot.append(...comNos(guia(x0 - 2, centro, x0 - 10, y), rotulo(x0 - 14, y, "end", o.rotulo, formatar(v) + " · " + nf(100 * v / total, 0) + "%")));
  }
  const alvosD = espacar(dest.map(d => ({ d, y: pD.get(d.id).y + pD.get(d.id).h / 2 })));
  for (const { d, y } of alvosD) {
    const p = pD.get(d.id), v = somaDest.get(d.id), centro = p.y + p.h / 2;
    const dica = [formatar(v), d.rotulo, nf(100 * v / total, 1) + "% do total"];
    const r = s("rect", { x: x1, y: p.y, width: larguraNo, height: p.h, rx: 2, fill: cs.neutro, tabindex: 0, "aria-label": dica.join(". ") });
    r.addEventListener("pointermove", e => mostrarDica(e, dica)); r.addEventListener("focus", e => mostrarDica(e, dica));
    r.addEventListener("pointerleave", esconderDica); r.addEventListener("blur", esconderDica);
    gNos.append(r);
    gRot.append(...comNos(guia(x1 + larguraNo + 2, centro, x1 + larguraNo + 10, y), rotulo(x1 + larguraNo + 14, y, "start", d.rotulo, formatar(v) + " · " + nf(100 * v / total, 0) + "%")));
  }
  svg.append(gLinks, gNos, gRot);
  return svg;
}

/* ----------------------------------------------- régua com o mínimo legal */
/**
 * Distribuição de um percentual entre os municípios, com a linha do mínimo.
 * Abaixo do mínimo: marca em "×" e na cor de status crítico (forma + cor, nunca só cor).
 * valores: [{rotulo, v}]
 */
function reguaMinimo({ valores, minimo, formatar, titulo, teto }) {
  const cs = cores();
  const largura = Math.max(300, Math.min(1180, (document.querySelector("main") || document.body).clientWidth - 64));
  const com = valores.filter(x => !nulo(x.v));
  const vmin = Math.min(minimo - 2, ...com.map(x => x.v)), vmax = Math.max(teto || 0, minimo + 2, ...com.map(x => x.v));
  const e = 24, d = 24, altura = 96, base = 58;
  const X = v => e + (largura - e - d) * (v - vmin) / (vmax - vmin);
  const svg = s("svg", { viewBox: `0 0 ${largura} ${altura}`, width: "100%", height: altura, role: "img",
    "aria-label": titulo + ". Valores na tabela abaixo.", class: "regua" });
  svg.append(s("line", { x1: e, x2: largura - d, y1: base, y2: base, stroke: cs.axis, "stroke-width": 1 }));
  const passo = (vmax - vmin) > 40 ? 10 : 5;
  for (let t = Math.ceil(vmin / passo) * passo; t <= vmax; t += passo) {
    svg.append(s("line", { x1: X(t), x2: X(t), y1: base, y2: base + 5, stroke: cs.axis }),
      s("text", { x: X(t), y: base + 18, "text-anchor": "middle", fill: cs.ink2, "font-size": 11 }, nf(t, 0) + "%"));
  }
  const crit = getComputedStyle(document.documentElement).getPropertyValue("--crit").trim();
  svg.append(s("line", { x1: X(minimo), x2: X(minimo), y1: 6, y2: base + 5, stroke: crit, "stroke-width": 2 }),
    s("text", { x: X(minimo) + 6, y: 14, fill: cs.ink, "font-size": 12, "font-weight": 600 }, "mínimo " + nf(minimo, 0) + "%"));
  // Empilha pontos próximos para não sobrepor (colunas de 6px). Coluna cheia (ex.: dezenas
  // de municípios em 100%) comprime o passo para caber na altura, em vez de vazar o gráfico.
  const coluna = x => Math.round(X(x.v) / 6), total = new Map(), ocupado = new Map();
  com.forEach(x => total.set(coluna(x), (total.get(coluna(x)) || 0) + 1));
  for (const x of com.slice().sort((a, b) => a.v - b.v)) {
    const col = coluna(x), n = ocupado.get(col) || 0; ocupado.set(col, n + 1);
    const passo = Math.min(7, 40 / Math.max(1, total.get(col) - 1));
    const cx = X(x.v), cy = base - 8 - n * passo, abaixo = x.v < minimo;
    const dica = [formatar(x.v), x.rotulo, abaixo ? "abaixo do mínimo" : "cumpre o mínimo"];
    const g = abaixo
      ? s("path", { d: `M${cx - 4},${cy - 4} L${cx + 4},${cy + 4} M${cx - 4},${cy + 4} L${cx + 4},${cy - 4}`, stroke: crit, "stroke-width": 2.2 })
      : s("circle", { cx, cy, r: 3.5, fill: cs.serie[0], stroke: cs.surface, "stroke-width": 1 });
    const alvo = s("circle", { cx, cy, r: 7, fill: "transparent", tabindex: 0, "aria-label": dica.join(". ") });
    alvo.addEventListener("pointermove", ev => mostrarDica(ev, dica)); alvo.addEventListener("focus", ev => mostrarDica(ev, dica));
    alvo.addEventListener("pointerleave", esconderDica); alvo.addEventListener("blur", esconderDica);
    svg.append(g, alvo);
  }
  return svg;
}

/* ------------------------------------------------ barra empilhada 100% (HTML) */
/** partes: [{rotulo, valor, slot}] → barra com lacunas de 2px e legenda nomeada. */
function barra100(partes, formatar) {
  const cs = cores(), total = partes.reduce((t, p) => t + Math.max(0, p.valor || 0), 0);
  const barra = h("div", { class: "barra100", role: "img", "aria-label": partes.map(p => p.rotulo + ": " + (total > 0 ? nf(100 * p.valor / total, 1) + "%" : "sem dado")).join("; ") });
  if (total <= 0) return h("span", { class: "badge nada" }, "Sem dado");
  for (const p of partes) {
    if (!(p.valor > 0)) continue;
    const pc = 100 * p.valor / total;
    barra.append(h("span", { class: "seg", style: `width:${pc}%;background:${cs.serie[p.slot]}`,
      title: p.rotulo + ": " + formatar(p.valor) + " (" + nf(pc, 1) + "%)" }));
  }
  return barra;
}

function legendaSlots(itens) {
  const cs = cores();
  return h("div", { class: "legenda" }, itens.map(i => h("span", {}, h("span", { class: "chave-ret", style: "background:" + cs.serie[i.slot] }), i.rotulo)));
}
