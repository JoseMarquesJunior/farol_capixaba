"use strict";
/* ============================================================================
   Gráficos. Chart.js (via CDN, com hash de integridade) para linhas e barras; SVG
   próprio para o fluxo (Sankey), a régua do mínimo legal e a barra 100%.

   Regras que valem para todos:
   · todo gráfico tem tabela gêmea no card — o tooltip realça, nunca é o único
     acesso ao número;
   · o gráfico é UMA imagem para o leitor de tela (role="img" com um resumo que
     diz o que ele mostra) e nenhuma marca recebe foco de teclado — antes, as
     réguas somavam 156 paradas de Tab antes da primeira tabela;
   · a cor segue a entidade, nunca a posição.
   ========================================================================== */

/* ------------------------------------------------------------ Chart.js base */
const temChart = () => typeof window.Chart !== "undefined";
function avisoSemChart() {
  return h("div", { class: "aviso-grafico", role: "note" },
    "O gráfico não pôde ser desenhado: a biblioteca de gráficos vem da internet e não carregou. Os mesmos valores estão na tabela logo abaixo.");
}
const graficos = {};
function desenhar(id, canvas, config) {
  if (graficos[id]) graficos[id].destroy();
  graficos[id] = new Chart(canvas, config);
}
function chaveLinha(cor, forma) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg"); svg.setAttribute("viewBox", "0 0 22 12"); svg.setAttribute("aria-hidden", "true");
  const l = document.createElementNS(ns, "line");
  l.setAttribute("x1", 0); l.setAttribute("x2", 22); l.setAttribute("y1", 6); l.setAttribute("y2", 6);
  l.setAttribute("stroke", cor); l.setAttribute("stroke-width", 2); svg.append(l);
  const m = forma === "rect" ? document.createElementNS(ns, "rect")
    : forma === "triangle" || forma === "rectRot" ? document.createElementNS(ns, "polygon")
    : document.createElementNS(ns, "circle");
  if (forma === "rect") { m.setAttribute("x", 7); m.setAttribute("y", 2); m.setAttribute("width", 8); m.setAttribute("height", 8); }
  else if (forma === "triangle") m.setAttribute("points", "11,1.5 15.5,10 6.5,10");
  else if (forma === "rectRot") m.setAttribute("points", "11,1 15.5,6 11,11 6.5,6");
  else { m.setAttribute("cx", 11); m.setAttribute("cy", 6); m.setAttribute("r", 4); }
  m.setAttribute("fill", cor); svg.append(m);
  return svg;
}
/** Legenda de séries: cor + forma do marcador + nome (identidade nunca só pela cor). */
function legendaSeries(itens) {
  return h("div", { class: "legenda" }, itens.map(i => h("span", {}, chaveLinha(i.cor, i.forma), i.rotulo)));
}
/** Linha vertical que segue o ponteiro e "gruda" no X mais próximo. */
const plugCrosshair = {
  id: "crosshair",
  afterDatasetsDraw(chart) {
    const a = chart.tooltip && chart.tooltip.getActiveElements ? chart.tooltip.getActiveElements() : [];
    if (!a.length) return;
    const x = a[0].element.x, { top, bottom } = chart.chartArea, c = chart.ctx;
    c.save(); c.beginPath(); c.moveTo(x, top); c.lineTo(x, bottom);
    c.lineWidth = 1; c.strokeStyle = cores().axis; c.stroke(); c.restore();
  },
};
/** Rótulo de valor no fim de barras escolhidas (rótulo seletivo, nunca em todas). */
const plugRotulos = {
  id: "rotulosSelecionados",
  afterDatasetsDraw(chart, _a, opt) {
    if (!opt || !opt.destacar) return;
    const { ctx } = chart, meta = chart.getDatasetMeta(0), cs = cores();
    ctx.save(); ctx.font = `${cs.pesoMedio} 12px ${cs.fonte}`; ctx.textBaseline = "middle";
    meta.data.forEach((barra, i) => {
      if (!opt.destacar.has(i)) return;
      const txt = opt.formatar(chart.data.datasets[0].data[i]);
      const w = ctx.measureText(txt).width, x = barra.x + 6;
      if (x + w <= chart.width - 2) { ctx.textAlign = "left"; ctx.fillStyle = cs.ink; ctx.fillText(txt, x, barra.y); }
      else { ctx.textAlign = "right"; ctx.fillStyle = cs.sobreSerie; ctx.fillText(txt, barra.x - 6, barra.y); }
    });
    ctx.restore();
  },
};
/** Linha de referência horizontal (o mínimo legal), tracejada e rotulada. */
const plugReferencia = {
  id: "referencia",
  afterDatasetsDraw(chart, _a, opt) {
    if (!opt || nulo(opt.valor)) return;
    const y = chart.scales.y.getPixelForValue(opt.valor), { left, right } = chart.chartArea, c = chart.ctx, cs = cores();
    c.save(); c.setLineDash([6, 4]); c.lineWidth = 2; c.strokeStyle = cs.descumpre;
    c.beginPath(); c.moveTo(left, y); c.lineTo(right, y); c.stroke();
    c.setLineDash([]); c.font = `${cs.pesoMedio} 12px ${cs.fonte}`; c.fillStyle = cs.ink; c.textAlign = "right"; c.textBaseline = "bottom";
    c.fillText(opt.rotulo || "", right - 4, y - 3); c.restore();
  },
};
function opcoesBase(cs, formatarY) {
  return {
    responsive: true, maintainAspectRatio: false, animation: false,
    layout: { padding: { right: 8 } },
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: { backgroundColor: cs.surface, titleColor: cs.ink2, bodyColor: cs.ink, borderColor: cs.axis, borderWidth: 1,
        padding: 10, boxPadding: 4, usePointStyle: true, titleFont: { weight: "600" }, bodyFont: { weight: "600" } },
    },
    scales: {
      x: { grid: { color: cs.grid, lineWidth: 1 }, border: { color: cs.axis }, ticks: { color: cs.ink2, font: { size: 12 } } },
      y: { beginAtZero: true, grid: { color: cs.grid, lineWidth: 1 }, border: { color: cs.axis },
        ticks: { color: cs.ink2, font: { size: 12 }, callback: formatarY } },
    },
  };
}
function serieLinha(rotulo, dados, slot) {
  const cs = cores(), cor = cs.serie[slot];
  return { label: rotulo, data: dados.map(v => nulo(v) ? null : v), borderColor: cor, backgroundColor: cor, borderWidth: 2,
    tension: 0, spanGaps: false, pointStyle: FORMAS[slot], pointRadius: 5, pointHoverRadius: 7,
    pointBackgroundColor: cor, pointBorderColor: cs.surface, pointBorderWidth: 2 };
}
const eixoY = m => m.tipo === "pct" ? (v => nf(v, 0) + "%") : m.tipo === "moeda2" ? (v => "R$ " + nf(v, 0)) : tickMoeda;
/** Canvas pronto para Chart.js, ou o aviso quando a biblioteca não carregou. */
function areaGrafico(rotuloAcessivel, classe) {
  const cv = h("canvas", { role: "img", "aria-label": rotuloAcessivel + " Os valores estão na tabela logo abaixo." });
  return { cv, caixa: h("div", { class: "grafico" + (classe ? " " + classe : "") }, temChart() ? cv : avisoSemChart()) };
}

/* ------------------------------------------------------------------- SVG */
const SVG_NS = "http://www.w3.org/2000/svg";
function s(tag, attrs, ...filhos) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) el.setAttribute(k, v);
  for (const f of filhos.flat()) if (f !== null && f !== undefined) el.append(f instanceof Node ? f : document.createTextNode(String(f)));
  return el;
}
const larguraUtil = () => Math.max(300, Math.min(1220, (document.querySelector("main") || document.body).clientWidth - 64));
/** Quebra um rótulo em até duas linhas por palavras; a segunda leva "…" se ainda sobrar. */
function quebrarRotulo(texto, max) {
  const palavras = String(texto).split(/\s+/), linhas = [""];
  for (const p of palavras) {
    const atual = linhas[linhas.length - 1];
    if ((atual + " " + p).trim().length <= max || !atual) linhas[linhas.length - 1] = (atual + " " + p).trim();
    else if (linhas.length < 2) linhas.push(p);
    else { linhas[1] = (linhas[1] + " " + p).trim(); }
  }
  if (linhas[1] && linhas[1].length > max) linhas[1] = linhas[1].slice(0, max - 1) + "…";
  return linhas;
}

/**
 * Sankey de duas colunas: origem do recurso → destino.
 * origens: [{id, rotulo, slot}] (cor = slot da paleta); destinos: [{id, rotulo}] (neutros);
 * arestas: [{de, para, valor}]. Passar o ponteiro sobre um nó ou fluxo realça os fluxos dele.
 */
function sankey({ origens, destinos, arestas, formatar, titulo }) {
  const cs = cores();
  const largura = larguraUtil(), estreito = largura < 640;
  const margem = estreito ? 118 : 240, maxCar = estreito ? 15 : 30;
  const lacuna = 10, topo = 8;
  const total = arestas.reduce((t, a) => t + a.valor, 0);
  const somaOrig = new Map(origens.map(o => [o.id, 0])), somaDest = new Map(destinos.map(d => [d.id, 0]));
  arestas.forEach(a => { somaOrig.set(a.de, somaOrig.get(a.de) + a.valor); somaDest.set(a.para, somaDest.get(a.para) + a.valor); });
  const orig = origens.filter(o => somaOrig.get(o.id) > 0), dest = destinos.filter(d => somaDest.get(d.id) > 0);
  const nMax = Math.max(orig.length, dest.length);
  const ALTURA_ROTULO = 50;  // até duas linhas de nome + o valor
  const altura = Math.max(280, nMax * 54 + topo * 2, nMax * ALTURA_ROTULO + 40);
  const escala = (altura - topo * 2 - lacuna * (nMax - 1)) / total;
  const x0 = margem, x1 = largura - margem, larguraNo = 14;
  const posicionar = (nos, soma) => {
    const usado = nos.reduce((t, n) => t + soma.get(n.id) * escala, 0) + lacuna * (nos.length - 1);
    let y = topo + (altura - topo * 2 - usado) / 2;
    const pos = new Map();
    for (const n of nos) { const h_ = Math.max(2, soma.get(n.id) * escala); pos.set(n.id, { y, h: h_, cursor: y }); y += h_ + lacuna; }
    return pos;
  };
  const pO = posicionar(orig, somaOrig), pD = posicionar(dest, somaDest);
  const maiorO = orig.slice().sort((a, b) => somaOrig.get(b.id) - somaOrig.get(a.id))[0];
  const maiorD = dest.slice().sort((a, b) => somaDest.get(b.id) - somaDest.get(a.id))[0];
  const resumo = (titulo || "Fluxo") + ": " + formatar(total) + " no total. Maior origem: " + (maiorO ? maiorO.rotulo + ", " + nf(100 * somaOrig.get(maiorO.id) / total, 0) + "%" : "—") +
    ". Maior destino: " + (maiorD ? maiorD.rotulo + ", " + nf(100 * somaDest.get(maiorD.id) / total, 0) + "%" : "—") + ". Os valores estão na tabela abaixo.";
  const svg = s("svg", { viewBox: `0 0 ${largura} ${altura}`, width: "100%", height: altura, role: "img", "aria-label": resumo, class: "sankey" });
  const gLinks = s("g", {}), gNos = s("g", {}), gRot = s("g", { "aria-hidden": "true" });
  const realcar = (filtro) => { svg.classList.add("foco"); gLinks.querySelectorAll(".aresta").forEach(p => p.classList.toggle("ativa", filtro(p))); };
  const soltar = () => { svg.classList.remove("foco"); esconderDica(); };

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
      const p = s("path", { d, fill: cs.serie[o.slot], "fill-opacity": 0.38, class: "aresta", "data-de": o.id, "data-para": a.para });
      p.addEventListener("pointermove", e => { realcar(x => x === p); mostrarDica(e, dica); });
      p.addEventListener("pointerleave", soltar);
      gLinks.append(p);
    }
  }
  const rotulo = (x, y, anchor, texto, valor) => {
    const linhas = quebrarRotulo(texto, maxCar), y0 = y - (linhas.length === 2 ? 15 : 7);
    return s("text", { x, y: y0, "text-anchor": anchor, "dominant-baseline": "middle", fill: cs.ink },
      s("title", {}, texto),
      linhas.map((l, i) => s("tspan", { x, dy: i ? "1.15em" : null, "font-weight": "600" }, l)),
      s("tspan", { x, dy: "1.2em", fill: cs.ink2, "font-size": "12" }, valor));
  };
  // Nó fino demais para o rótulo vizinho → o rótulo desce (ou sobe) até caber,
  // preso ao nó por uma linha-guia. Nunca dois rótulos sobrepostos.
  const espacar = (alvos) => {
    for (let i = 1; i < alvos.length; i++) alvos[i].y = Math.max(alvos[i].y, alvos[i - 1].y + ALTURA_ROTULO);
    const fundo = altura - 20, excesso = alvos.length ? alvos[alvos.length - 1].y - fundo : 0;
    if (excesso > 0) {
      alvos[alvos.length - 1].y -= excesso;
      for (let i = alvos.length - 2; i >= 0; i--) alvos[i].y = Math.min(alvos[i].y, alvos[i + 1].y - ALTURA_ROTULO);
    }
    return alvos;
  };
  const guia = (xNo, yNo, xRot, yRot) => Math.abs(yNo - yRot) < 3 ? null
    : s("path", { d: `M${xNo},${yNo} L${(xNo + xRot) / 2},${yNo} L${(xNo + xRot) / 2},${yRot} L${xRot},${yRot}`, fill: "none", stroke: cs.axis, "stroke-width": 1 });
  const no = (x, p, cor, dica, filtro) => {
    const r = s("rect", { x, y: p.y, width: larguraNo, height: p.h, rx: 2, fill: cor });
    r.addEventListener("pointermove", e => { realcar(filtro); mostrarDica(e, dica); });
    r.addEventListener("pointerleave", soltar);
    return r;
  };
  for (const { o, y } of espacar(orig.map(o => ({ o, y: pO.get(o.id).y + pO.get(o.id).h / 2 })))) {
    const p = pO.get(o.id), v = somaOrig.get(o.id), centro = p.y + p.h / 2;
    gNos.append(no(x0, p, cs.serie[o.slot], [formatar(v), o.rotulo, nf(100 * v / total, 1) + "% do total"], el => el.dataset.de === o.id));
    gRot.append(...[guia(x0 - 2, centro, x0 - 10, y), rotulo(x0 - 14, y, "end", o.rotulo, formatar(v) + " · " + nf(100 * v / total, 0) + "%")].filter(Boolean));
  }
  for (const { d, y } of espacar(dest.map(d => ({ d, y: pD.get(d.id).y + pD.get(d.id).h / 2 })))) {
    const p = pD.get(d.id), v = somaDest.get(d.id), centro = p.y + p.h / 2;
    gNos.append(no(x1, p, cs.neutro, [formatar(v), d.rotulo, nf(100 * v / total, 1) + "% do total"], el => el.dataset.para === d.id));
    gRot.append(...[guia(x1 + larguraNo + 2, centro, x1 + larguraNo + 10, y), rotulo(x1 + larguraNo + 14, y, "start", d.rotulo, formatar(v) + " · " + nf(100 * v / total, 0) + "%")].filter(Boolean));
  }
  svg.append(gLinks, gNos, gRot);
  return svg;
}

/**
 * Régua de distribuição de um percentual entre os municípios, com a linha do mínimo.
 * Abaixo do mínimo: marca em "×" na cor de descumprimento (forma + cor, nunca só cor).
 * valores: [{rotulo, v}]
 */
function reguaMinimo({ valores, minimo, formatar, titulo, teto }) {
  const cs = cores();
  const largura = larguraUtil();
  const com = valores.filter(x => !nulo(x.v)).sort((a, b) => a.v - b.v);
  const abaixo = com.filter(x => x.v < minimo);
  const mediana = com.length ? (com.length % 2 ? com[(com.length - 1) / 2].v : (com[com.length / 2 - 1].v + com[com.length / 2].v) / 2) : null;
  const resumo = titulo + ", " + com.length + " municípios com dado. " + (com.length
    ? "Menor: " + formatar(com[0].v) + " (" + com[0].rotulo + "); mediana: " + formatar(mediana) + "; maior: " + formatar(com[com.length - 1].v) + " (" + com[com.length - 1].rotulo + "). "
    : "") + (abaixo.length ? abaixo.length + " abaixo do mínimo de " + nf(minimo, 0) + "%: " + abaixo.map(x => x.rotulo).join(", ") + "." : "Nenhum abaixo do mínimo de " + nf(minimo, 0) + "%.") + " Os valores estão na tabela abaixo.";
  const vmin = Math.min(minimo - 2, ...com.map(x => x.v)), vmax = Math.max(teto || 0, minimo + 2, ...com.map(x => x.v));
  const e = 24, d = 24, altura = 100, base = 60;
  const X = v => e + (largura - e - d) * (v - vmin) / (vmax - vmin);
  const svg = s("svg", { viewBox: `0 0 ${largura} ${altura}`, width: "100%", height: altura, role: "img", "aria-label": resumo, class: "regua" });
  svg.append(s("line", { x1: e, x2: largura - d, y1: base, y2: base, stroke: cs.axis, "stroke-width": 1 }));
  const passo = (vmax - vmin) > 40 ? 10 : (vmax - vmin) > 12 ? 5 : 1;
  for (let t = Math.ceil(vmin / passo) * passo; t <= vmax; t += passo) {
    svg.append(s("line", { x1: X(t), x2: X(t), y1: base, y2: base + 5, stroke: cs.axis }),
      s("text", { x: X(t), y: base + 19, "text-anchor": "middle", fill: cs.ink2, "font-size": 12 }, nf(t, 0) + "%"));
  }
  svg.append(s("line", { x1: X(minimo), x2: X(minimo), y1: 6, y2: base + 5, stroke: cs.descumpre, "stroke-width": 2, "stroke-dasharray": "5 3" }),
    s("text", { x: X(minimo) + 6, y: 15, fill: cs.ink, "font-size": 12, "font-weight": 600 }, "mínimo " + nf(minimo, 0) + "%"));
  // Pontos próximos empilham em colunas de 6px; coluna cheia comprime o passo.
  const coluna = x => Math.round(X(x.v) / 6), totalCol = new Map(), ocupado = new Map();
  com.forEach(x => totalCol.set(coluna(x), (totalCol.get(coluna(x)) || 0) + 1));
  for (const x of com) {
    const col = coluna(x), n = ocupado.get(col) || 0; ocupado.set(col, n + 1);
    const passoY = Math.min(7, 40 / Math.max(1, totalCol.get(col) - 1));
    const cx = X(x.v), cy = base - 8 - n * passoY, embaixo = x.v < minimo;
    const dica = [formatar(x.v), x.rotulo, embaixo ? "abaixo do mínimo" : "cumpre o mínimo"];
    const g = embaixo
      ? s("path", { d: `M${cx - 4},${cy - 4} L${cx + 4},${cy + 4} M${cx - 4},${cy + 4} L${cx + 4},${cy - 4}`, stroke: cs.descumpre, "stroke-width": 2.4 })
      : s("circle", { cx, cy, r: 3.5, fill: cs.serie[0], stroke: cs.surface, "stroke-width": 1 });
    // Alvo de ponteiro maior que a marca; sem foco de teclado (a tabela ao lado é o acesso).
    const alvo = s("circle", { cx, cy, r: 7, fill: "transparent" });
    alvo.addEventListener("pointermove", ev => mostrarDica(ev, dica));
    alvo.addEventListener("pointerleave", esconderDica);
    svg.append(g, alvo);
  }
  return svg;
}

/* ------------------------------------------------ barra empilhada 100% (HTML) */
/** partes: [{rotulo, valor, slot}] → barra com lacunas de 2px e legenda nomeada. */
function barra100(partes, formatar) {
  const cs = cores(), total = partes.reduce((t, p) => t + Math.max(0, p.valor || 0), 0);
  if (total <= 0) return semDado();
  const barra = h("div", { class: "barra100", role: "img",
    "aria-label": partes.map(p => p.rotulo + ": " + (p.valor > 0 ? nf(100 * p.valor / total, 1) + "%" : "sem dado")).join("; ") });
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

/**
 * Barras horizontais em HTML, com UMA grade para o conjunto inteiro (todos os
 * trilhos com a mesma largura). Uma cor só: a magnitude é o comprimento.
 * itens: [{nome, codigo?, valor, atencao?}] ; `rotuloAtencao` explica a textura.
 */
function barrasHorizontais(itens, total, opcoes) {
  const o = opcoes || {};
  const maior = Math.max(...itens.filter(i => !i.grupo && !nulo(i.valor)).map(i => i.valor), 0);  // cabeçalho de grupo não tem valor
  const grade = h("div", { class: "barras", role: "list", "aria-label": o.rotulo || null });
  for (const i of itens) {
    if (i.grupo) { grade.append(h("div", { class: "cat-natureza", role: "listitem" }, h("h4", {}, i.grupo, i.detalhe ? h("span", { class: "muted" }, "  " + i.detalhe) : null))); continue; }
    grade.append(h("div", { class: "barra-sub" + (i.atencao ? " atencao" : ""), role: "listitem" },
      h("div", { class: "nome" }, h("span", {}, i.nome, i.atencao && o.rotuloAtencao ? h("span", { class: "sr-only" }, " (" + o.rotuloAtencao + ")") : null),
        i.codigo ? h("span", { class: "cod" }, i.codigo) : null),
      h("div", { class: "trilho-caixa", "aria-hidden": "true" }, h("div", { class: "trilho" },
        h("div", { class: "fill", style: "width:" + (maior > 0 ? 100 * Math.max(0, i.valor) / maior : 0) + "%" }))),
      h("div", { class: "valor" }, h("b", {}, brlCompacto(i.valor)), total > 0 ? h("span", { class: "pct" }, nf(100 * i.valor / total, 1) + "%") : null)));
  }
  return grade;
}
