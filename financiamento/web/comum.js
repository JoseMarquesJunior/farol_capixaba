"use strict";
/* ============================================================================
   Núcleo compartilhado pelas três visões: dataset, estado, formatação, tabelas
   e o básico do Chart.js. Nenhuma chamada de rede além do Chart.js (CDN).
   Todo texto vindo dos dados entra por textContent — nunca innerHTML.
   ========================================================================== */
const D = JSON.parse(document.getElementById("dataset").textContent);
const META = D.meta;
const ANOS = META.anos;
const MAX_COMPARAR = 4;
const FORMAS = ["circle", "rect", "triangle", "rectRot"]; // canal secundário além da cor

const ENTES = new Map(D.entes.map(e => [e.cod_ibge, e]));
const MUNICIPIOS = D.entes.filter(e => e.esfera === "M");
const COD_ESTADO = (D.entes.find(e => e.esfera === "E") || {}).cod_ibge;
const LINHA = new Map(D.anual.map(r => [r.cod_ibge + "|" + r.ano, r]));
const BIM = new Map();
for (const b of D.bimestral) BIM.set(b.cod_ibge + "|" + b.ano + "|" + b.bimestre, b);
const SUB = new Map();  // cod_ibge|ano -> [subfunções, da maior para a menor]
for (const s of D.subfuncoes || []) {
  const k = s.cod_ibge + "|" + s.ano;
  if (!SUB.has(k)) SUB.set(k, []);
  SUB.get(k).push(s);
}
const CATALOGO_SUB = D.catalogo_subfuncoes || [];
const NOME_SUB = new Map(CATALOGO_SUB.map(s => [s.codigo, s.nome]));

/* ------------------------------------------- dados do painel de auditoria (esquema 2) */
/** Expande uma tabela colunar do dataset: nomes uma vez, linhas em listas e, para
 *  as colunas de texto repetitivo, índices num dicionário de valores distintos. */
function expandir(t) {
  if (!t || !t.colunas) return [];
  const dic = t.dicionario || {};
  return t.linhas.map(l => {
    const o = {};
    t.colunas.forEach((c, i) => { const v = l[i]; o[c] = dic[c] && v !== null && v !== undefined ? dic[c][v] : v; });
    return o;
  });
}
function agrupar(linhas, chave) {
  const m = new Map();
  for (const l of linhas) { const k = chave(l); if (!m.has(k)) m.set(k, []); m.get(k).push(l); }
  return m;
}
const chaveEA = (cod, ano) => cod + "|" + ano;
const CONSULTAS = new Map(expandir(D.consultas).map(c => [c.id, { ...c, url: (c.url_base || "") + (c.url_resto || "") }]));
const SIOPE = new Map(expandir(D.siope).map(s => [chaveEA(s.cod_ibge, s.ano), s]));
const ORIGEM = agrupar(expandir(D.origem), o => chaveEA(o.cod_ibge, o.ano));
const FLUXO = agrupar(expandir(D.fluxo), f => chaveEA(f.cod_ibge, f.ano));
const NATUREZA = agrupar(expandir(D.natureza), n => chaveEA(n.cod_ibge, n.ano));
const ENTREGAS = agrupar(expandir(D.entregas), e => chaveEA(e.cod_ibge, e.ano));
const REPASSES = agrupar(expandir(D.repasses), r => chaveEA(r.cod_ibge, r.ano));
const RECEITA_BIM = agrupar(expandir(D.receita_bimestral), r => chaveEA(r.cod_ibge, r.ano));

/** Cor fixa por ORIGEM do recurso, igual em todo o painel (a cor segue a entidade):
 *  impostos = slot 1, FUNDEB = slot 2, transferências federais (FNDE) = slot 3, outras = slot 4. */
const SLOT_ORIGEM = { impostos: 0, impostos_proprios: 0, fundeb: 1, federal: 2, federal_especifica: 2, outras: 3 };
const ORDEM_ORIGEM = ["impostos_proprios", "fundeb", "federal_especifica", "outras"];
const ORDEM_GRUPO = ["impostos", "fundeb", "federal", "outras"];

const SITUACAO_ENTREGA = {
  no_prazo: "no prazo", entregue_com_atraso: "entregue com atraso", nao_entregue: "não entregue",
  prazo_aberto: "prazo em aberto", retificado: "retificado", sem_data: "sem data",
};
const NOME_SUBFUNCAO_CURTO = { "361": "Ensino fundamental", "365": "Educação infantil", "122": "Administração geral",
  "367": "Educação especial", "366": "Educação de jovens e adultos", "362": "Ensino médio", "363": "Ensino profissional",
  "364": "Ensino superior", "306": "Alimentação e nutrição", "368": "Educação básica", "782": "Transporte rodoviário" };
const nomeSubfuncao = cod => NOME_SUBFUNCAO_CURTO[cod] || NOME_SUB.get("12." + cod) || ("subfunção " + cod);

/** Subfunções que não são competência típica de um município (art. 211 CF):
 *  o município atua prioritariamente no fundamental e no infantil. Aparecer aqui
 *  não é irregularidade — é um ponto que merece olhar na auditoria. */
const SUB_FORA_DA_PRIORIDADE = new Set(["12.362", "12.363", "12.364"]);
const SUB_ADMINISTRACAO = "12.122";

/* ------------------------------------------------------------------ formato */
const $ = (s, r = document) => r.querySelector(s);
const nf = (v, d = 0) => new Intl.NumberFormat("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d }).format(v);
const brl = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
const dataBR = iso => iso ? iso.slice(0, 10).split("-").reverse().join("/") : "—";
const dataHoraBR = iso => iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";
const nulo = v => v === null || v === undefined || (typeof v === "number" && Number.isNaN(v));

function brlCompacto(v) {
  const a = Math.abs(v);
  if (a >= 1e9) return "R$ " + nf(v / 1e9, 2) + " bi";
  if (a >= 1e6) return "R$ " + nf(v / 1e6, 1) + " mi";
  if (a >= 1e3) return "R$ " + nf(v / 1e3, 0) + " mil";
  return brl(v);
}
/** Rótulo curto para eixo: "R$ 200 mi", "R$ 1 bi" (sem casas quando redondo). */
function tickMoeda(v) {
  const a = Math.abs(v), sem = x => nf(x, Number.isInteger(x) ? 0 : 1);
  if (a >= 1e9) return "R$ " + sem(v / 1e9) + " bi";
  if (a >= 1e6) return "R$ " + sem(v / 1e6) + " mi";
  if (a >= 1e3) return "R$ " + sem(v / 1e3) + " mil";
  return "R$ " + nf(v, 0);
}
const pct = (v, d = 1) => nulo(v) ? "sem dado" : nf(v, d) + "%";

/** Cria elemento: h("div", {class:"x"}, "texto", outroNo). Texto sempre como nó de texto. */
function h(tag, attrs, ...filhos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos.flat()) {
    if (f === null || f === undefined || f === false) continue;
    el.append(f instanceof Node ? f : document.createTextNode(String(f)));
  }
  return el;
}
const limpar = el => { while (el.firstChild) el.removeChild(el.firstChild); return el; };

function cores() {
  const cs = getComputedStyle(document.documentElement);
  const v = n => cs.getPropertyValue(n).trim();
  return { surface: v("--surface"), ink: v("--ink"), ink2: v("--ink-2"), grid: v("--grid"), axis: v("--axis"),
    neutro: v("--neutral-mark"), serie: [v("--s1"), v("--s2"), v("--s3"), v("--s4")],
    // Canvas não entende var(): a fonte e o branco do rótulo dentro da barra
    // têm de ser lidos dos tokens aqui, senão o gráfico sai fora da identidade.
    fonte: v("--tc-fonte"), sobreSerie: v("--tc-primaria-txt"),
    pesoMedio: v("--tc-peso-medio") };
}

/* ------------------------------------------------------------------- estado */
const METRICAS = {
  desp: { rotulo: "Despesa em Educação (R$, empenhada)", campo: "desp_educacao_empenhada", tipo: "moeda",
    nota: "Despesa empenhada na função 12 (Educação), exceto intra-orçamentárias — DCA Anexo I-E." },
  pc: { rotulo: "Despesa em Educação per capita (R$/hab.)", campo: "desp_educacao_per_capita", tipo: "moeda2",
    nota: "Despesa empenhada em Educação ÷ população do exercício, como o SICONFI a reporta. Essa população só muda a cada dois exercícios: parte da variação anual é mudança do denominador (ver limitações no rodapé)." },
  pm: { rotulo: "Despesa em Educação por matrícula (R$/matrícula)", campo: "desp_educacao_por_matricula", tipo: "moeda2",
    nota: "Despesa empenhada em Educação ÷ matrículas da rede MUNICIPAL no exercício (coluna \"Alunos\" do recurso \"Educação\" do TCE-ES, conferida contra o Censo Escolar). Diferente do per capita, o denominador muda todo ano e mede quem a rede atende. Só municípios: o recurso do TCE-ES não cobre o Estado." },
  pct: { rotulo: "Educação em % da despesa total do ente", campo: "desp_educacao_pct_total", tipo: "pct",
    nota: "Função 12 ÷ despesa total empenhada do ente (exceto intra-orçamentárias). Não é o índice de MDE." },
  fundeb: { rotulo: "Receita do FUNDEB ÷ despesa em Educação (%)", campo: "fundeb_pct_desp_educacao", tipo: "pct",
    nota: "Receita bruta do FUNDEB recebida (DCA Anexo I-C) ÷ despesa em Educação. É a participação pelo lado da RECEITA — não a despesa custeada pelo FUNDEB, e não desconta a contribuição." },
  admin: { rotulo: "Administração Geral em % da Educação", campo: "__sub:12.122", tipo: "pct",
    nota: "Subfunção 12.122 (Administração Geral) ÷ despesa em Educação. Mede quanto da função 12 fica na estrutura administrativa. Município sem essa subfunção declarada aparece como “sem dado”, não como 0%." },
};
const fmtMetrica = (m, v) => nulo(v) ? "sem dado" :
  m.tipo === "moeda" ? brlCompacto(v) : m.tipo === "moeda2" ? brl(v) : nf(v, 1) + "%";
const fmtMetricaCheio = (m, v) => nulo(v) ? "" :
  m.tipo === "moeda" ? brl(v) : m.tipo === "moeda2" ? brl(v) : nf(v, 2) + "%";

/** Indicador do catálogo (meta.indicadores) por trás de cada métrica do panorama. */
function indicadorDaMetrica(m) {
  return ({ desp_educacao_empenhada: "desp_educacao_empenhada", desp_educacao_per_capita: "desp_educacao_per_capita",
    desp_educacao_pct_total: "desp_educacao_pct_total", fundeb_pct_desp_educacao: "fundeb_pct_desp_educacao",
    desp_educacao_por_matricula: "desp_educacao_por_matricula" })[m.campo] || "subfuncao_empenhada";
}
/** Consultas de origem de uma métrica num ente-ano (as derivadas citam os dois lados). */
function qDaMetrica(m, cod, ano) {
  const r = LINHA.get(cod + "|" + ano) || {};
  if (m.campo === "fundeb_pct_desp_educacao") return [r.q_dca_ie, r.q_dca_ic].filter(Boolean).join(";");
  if (m.campo === "desp_educacao_por_matricula") return [r.q_dca_ie, r.q_tcees_mde].filter(Boolean).join(";");
  return r.q_dca_ie || "";
}

/** Valor de uma métrica, inclusive as derivadas de subfunção ("__sub:12.122"). */
function valorMetrica(m, cod, ano) {
  if (m.campo.startsWith("__sub:")) {
    const codigo = m.campo.slice(6);
    const achado = (SUB.get(cod + "|" + ano) || []).find(s => s.codigo === codigo);
    return achado ? achado.pct_educacao : null;
  }
  const r = LINHA.get(cod + "|" + ano);
  return r ? r[m.campo] : null;
}

const estado = {
  visao: "conformidade",
  alertas: false,              // Conformidade: só municípios com alerta
  ano: META.ano_mais_recente,
  metrica: "desp",
  sel: [],                     // entes comparados no panorama
  slot: new Map(),             // ente -> slot de cor (a cor segue a entidade)
  municipio: null,             // ente da ficha
  topo: "15",
  programa: null,
  escola: null,                // escola (código INEP) aberta na visão Escolas
  rede: "todas",               // filtro de rede na visão Escolas
};
const graficos = {};

function slotLivre() { for (let i = 0; i < MAX_COMPARAR; i++) if (![...estado.slot.values()].includes(i)) return i; return -1; }
function adicionar(cod) {
  if (!ENTES.has(cod) || estado.sel.includes(cod) || estado.sel.length >= MAX_COMPARAR) return;
  estado.slot.set(cod, slotLivre()); // quem sai não repinta quem fica
  estado.sel.push(cod);
}
function remover(cod) { estado.sel = estado.sel.filter(c => c !== cod); estado.slot.delete(cod); }

/* ------------------------------------------------------------------- tabelas */
function tabela(colunas, linhas, legenda, opcoes) {
  const o = opcoes || {};
  const t = h("table", {}, h("caption", { class: "sr-only" }, legenda || ""));
  t.append(h("thead", {}, h("tr", {}, colunas.map(c => h("th", { class: c.num ? "num" : "", scope: "col" }, c.rotulo)))));
  const tb = h("tbody");
  for (const l of linhas) {
    const classe = (o.classeLinha && o.classeLinha(l)) || (o.destacar && o.destacar(l) ? "destaque" : null);
    const tr = h("tr", { class: classe }, colunas.map(c => {
      const bruto = c.valor(l);
      const conteudo = c.render ? c.render(l) : (nulo(bruto) ? "sem dado" : (c.fmt ? c.fmt(bruto) : bruto));
      return h("td", { class: c.num ? "num" : "" }, conteudo);
    }));
    tb.append(tr);
  }
  t.append(tb);
  if (o.rodape) t.append(h("tfoot", {}, h("tr", {}, colunas.map((c, i) => h("td", { class: c.num ? "num" : "" }, o.rodape[i] ?? "")))));
  return h("div", { class: "tabela-wrap" + (o.inteira ? " inteira" : ""), tabindex: "0", role: "region", "aria-label": legenda || "Tabela" }, t);
}
function baixarCSV(nome, colunas, linhas) {
  const esc = v => { const s = nulo(v) ? "" : String(v); return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
  const corpo = [colunas.map(c => esc(c.rotulo)).join(",")]
    .concat(linhas.map(l => colunas.map(c => esc(c.valor(l))).join(",")));
  const blob = new Blob(["﻿" + corpo.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const a = h("a", { href: URL.createObjectURL(blob), download: nome });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function botaoCSV(nome, colunas, linhas) {
  return h("div", { class: "acoes-tabela" },
    h("button", { type: "button", class: "leve", onclick: () => baixarCSV(nome, colunas, linhas) }, "Baixar CSV"));
}
function blocoTabela(titulo, colunas, linhas, arquivo, opcoes) {
  return h("details", { class: "tab" },
    h("summary", {}, "Valores por trás do gráfico — " + titulo + " (" + linhas.length + " linhas)"),
    tabela(colunas, linhas, titulo, opcoes), botaoCSV(arquivo, colunas, linhas));
}

/** Quantas linhas uma lista longa mostra antes de pedir "mostrar mais". */
const LINHAS_INICIAIS = 10;

/**
 * Tabela que começa curta e abre inteira no botão. Municípios com 120 escolas
 * faziam o card rolar sem fim; a lista completa continua a um clique (e no CSV).
 * `opcoes.inicio` muda o corte; o resto vai igual para `tabela`.
 */
function tabelaExpansivel(colunas, linhas, legenda, opcoes) {
  const o = opcoes || {}, inicio = o.inicio || LINHAS_INICIAIS;
  const caixa = h("div", { class: "expansivel" });
  if (linhas.length <= inicio) {
    caixa.append(tabela(colunas, linhas, legenda, o));
    return caixa;
  }
  let aberta = false;
  const alvo = h("div", {});
  const rotulo = () => aberta ? "Mostrar menos" : "Mostrar todas as " + nf(linhas.length) + " linhas";
  const botao = h("button", { type: "button", class: "leve mostrar-mais", "aria-expanded": "false",
    onclick: () => {
      aberta = !aberta;
      botao.setAttribute("aria-expanded", String(aberta));
      botao.textContent = rotulo();
      desenha();
      if (!aberta) caixa.scrollIntoView({ block: "nearest", behavior: "auto" });
    } }, rotulo());
  const desenha = () => {
    limpar(alvo).append(tabela(colunas, aberta ? linhas : linhas.slice(0, inicio), legenda, o));
    nota.textContent = aberta ? "Mostrando as " + nf(linhas.length) + " linhas."
      : "Mostrando " + inicio + " de " + nf(linhas.length) + ".";
  };
  const nota = h("span", { class: "nota", "aria-live": "polite" });
  desenha();
  caixa.append(alvo, h("div", { class: "acoes-tabela" }, botao, " ", nota));
  return caixa;
}

/* -------------------------------------------------------------- Chart.js base */
const temChart = () => typeof window.Chart !== "undefined";
function avisoSemChart() {
  return h("div", { class: "aviso-grafico", role: "note" },
    "O gráfico não pôde ser desenhado (a biblioteca Chart.js vem de um CDN e não carregou — sem internet?). " +
    "Os mesmos valores estão na tabela logo abaixo.");
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
function legendaEntes(entes) {
  return h("div", { class: "legenda" }, entes.map(cod => {
    const s = estado.slot.get(cod);
    return h("span", {}, chaveLinha(cores().serie[s], FORMAS[s]), ENTES.get(cod).nome);
  }));
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
    const { ctx } = chart, meta = chart.getDatasetMeta(0), cs = cores();
    ctx.save(); ctx.font = `${cs.pesoMedio} 12px ${cs.fonte}`; ctx.textBaseline = "middle";
    meta.data.forEach((barra, i) => {
      if (!opt.destacar.has(i)) return;
      const txt = opt.formatar(chart.data.datasets[0].data[i]);
      const w = ctx.measureText(txt).width, x = barra.x + 6;
      // Cabe fora da barra? Fica em tinta de texto sobre a superfície; senão entra
      // na barra, em branco, que contrasta com qualquer slot da paleta.
      if (x + w <= chart.width - 2) { ctx.textAlign = "left"; ctx.fillStyle = cs.ink; ctx.fillText(txt, x, barra.y); }
      else { ctx.textAlign = "right"; ctx.fillStyle = cs.sobreSerie; ctx.fillText(txt, barra.x - 6, barra.y); }
    });
    ctx.restore();
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
        padding: 10, boxPadding: 4, usePointStyle: true, titleFont: { weight: "600" }, bodyFont: { weight: "600" },
        callbacks: { labelPointStyle: () => ({ pointStyle: "line", rotation: 0 }) } },
    },
    scales: {
      x: { grid: { color: cs.grid, lineWidth: 1 }, border: { color: cs.axis }, ticks: { color: cs.ink2, font: { size: 12 } } },
      y: { beginAtZero: true, grid: { color: cs.grid, lineWidth: 1 }, border: { color: cs.axis },
        ticks: { color: cs.ink2, font: { size: 12 }, callback: formatarY } },
    },
  };
}
function desenhar(id, canvas, config) {
  if (graficos[id]) graficos[id].destroy();
  graficos[id] = new Chart(canvas, config);
}
function conjuntoLinhas(rotulos, valorDe, entes) {
  const cs = cores();
  return entes.map(cod => {
    const s = estado.slot.get(cod), cor = cs.serie[s];
    return { label: ENTES.get(cod).nome, data: rotulos.map(r => { const v = valorDe(cod, r); return nulo(v) ? null : v; }),
      borderColor: cor, backgroundColor: cor, borderWidth: 2, tension: 0, spanGaps: false,
      pointStyle: FORMAS[s], pointRadius: 5, pointHoverRadius: 7, pointBackgroundColor: cor,
      pointBorderColor: cs.surface, pointBorderWidth: 2 };
  });
}
const eixoY = m => m.tipo === "pct" ? (v => nf(v, 0) + "%") : tickMoeda;

/* ------------------------------------------------------------- utilitários */
const linhasMun = ano => MUNICIPIOS.map(e => LINHA.get(e.cod_ibge + "|" + ano)).filter(Boolean);
const subDe = (cod, ano) => SUB.get(cod + "|" + ano) || [];
const municipiosPorNome = () => MUNICIPIOS.slice().sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));

/** Seletor de ente. `comEstado` inclui o Estado num grupo à parte. */
function seletorEnte(id, valor, aoEscolher, opcoes) {
  const o = opcoes || {};
  const s = h("select", { id, onchange: e => { const v = e.target.value; if (v || o.permiteVazio) aoEscolher(v ? +v : null); if (o.limpaApos) e.target.value = ""; } });
  if (o.vazio) s.append(h("option", { value: "" }, o.vazio));
  const g = h("optgroup", { label: "Municípios (" + MUNICIPIOS.length + ")" });
  municipiosPorNome().forEach(x => g.append(h("option", { value: x.cod_ibge }, x.nome)));
  s.append(g);
  if (o.comEstado && COD_ESTADO) {
    s.append(h("optgroup", { label: "Estado (fora de somas e rankings)" },
      h("option", { value: COD_ESTADO }, ENTES.get(COD_ESTADO).nome + " — Estado")));
  }
  if (valor) s.value = valor;
  return s;
}
function seletorAno(id, valor, aoEscolher) {
  const s = h("select", { id, onchange: e => aoEscolher(+e.target.value) });
  ANOS.slice().reverse().forEach(a => s.append(h("option", { value: a }, a + (a === META.ano_mais_recente ? " (mais recente)" : ""))));
  s.value = valor;
  return s;
}
function campo(rotulo, controle) {
  const id = controle.id || ("c" + Math.random().toString(36).slice(2, 8));
  controle.id = id;
  return h("div", { class: "campo" }, h("label", { for: id }, rotulo), controle);
}
function kpi(rot, val, det, extra) {
  return h("div", { class: "kpi" + (extra && extra.prog ? " prog" : "") },
    h("div", { class: "rot" }, rot),
    h("div", { class: "val" + (extra && extra.nd ? " nd" : "") }, val),
    h("div", { class: "det" }, det));
}

/* ------------------------------------------- registros manuais e automáticos */
/** Registros de um campo de programa: os manuais (dados_manuais.yaml) e, para campo de
 *  origem "api", os automáticos gerados pelo ETL (programas_api), no mesmo formato. */
function todosRegistros(pid, campoId) {
  return [].concat(((D.dados_manuais.programas[pid] || {})[campoId]) || [],
    (((D.programas_api || {})[pid] || {})[campoId]) || []);
}
function registrosDe(pid, campoId, cod) {
  return todosRegistros(pid, campoId)
    .filter(r => r.cod_ibge === cod && r.verificado)
    .sort((a, b) => (b.ano || 0) - (a.ano || 0));
}
function rotuloValor(campo, v) {
  if (campo.tipo === "categorico") return (campo.rotulos_valores || {})[v] || String(v);
  if (campo.tipo === "moeda") return brl(v);
  if (campo.tipo === "percentual") return nf(v, 1) + "%";
  if (campo.tipo === "quantidade") return nf(v);
  return String(v);
}
function badgeRegistro(r) {
  if (r.automatico) return h("span", { class: r.situacao === "sem_dado" ? "badge nada" : "badge api" },
    r.situacao === "sem_dado" ? "Automático · a fonte não publicou o valor" : "Automático" + (r.escolas ? " · " + r.escolas + " escola(s)" : ""));
  return h("span", { class: r.situacao === "sem_amostra" ? "badge aviso" : "badge manual" },
    (r.situacao === "sem_amostra" ? "⚠ " : "") + "Manual · verificado em " + dataBR(r.verificado_em));
}
function celulaCampo(p, campo, cod) {
  const regs = registrosDe(p.id, campo.id, cod);
  if (!regs.length) return h("span", { class: "badge nada" }, "Sem dado carregado");
  // Registro automático traz o indicador do catálogo (cnca_pdde, ica_taxa...) para o "ver fonte";
  // "sem_dado" é a fonte lida sem o valor — diferente de "sem dado carregado" (ninguém registrou).
  return h("div", {}, regs.map(r => h("div", { class: "celula-reg" },
    r.situacao === "sem_amostra"
      ? h("span", {}, h("strong", {}, "Sem amostra suficiente"), r.ano ? " (" + r.ano + ")" : "")
      : r.situacao === "sem_dado"
        ? h("span", {}, h("strong", {}, "Sem dado publicado"), r.ano ? " (" + r.ano + ")" : "")
        : h("span", {}, h("strong", {}, rotuloValor(campo, r.valor)), campo.serie && r.ano ? " (" + r.ano + ")" : ""),
    " ", badgeRegistro(r), r.automatico && r.q && r.situacao !== "sem_dado" ? [" ", botaoFonte(campo.rotulo + " — " + ENTES.get(cod).nome + ", " + r.ano,
      () => [{ indicador: r.indicador || "cnca_pdde", ano: r.ano, detalhe: r.detalhe || "000C", q: r.q, valor: rotuloValor(campo, r.valor) }])] : null,
    h("span", { class: "fonte" }, r.fonte + (r.observacao ? " — " + r.observacao : "")))));
}
/** Municípios com ao menos um campo verificado, no programa. */
function municipiosComRegistro(p) {
  const com = new Set();
  for (const campo of p.campos) {
    for (const r of todosRegistros(p.id, campo.id)) if (r.verificado) com.add(r.cod_ibge);
  }
  return com;
}

/* ------------------------------------------------------------ endereço (hash) */
function lerHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  if (["conformidade", "fluxo", "panorama", "municipio", "escolas", "programas", "cnca"].includes(p.get("v"))) estado.visao = p.get("v");
  if (p.get("alertas") === "1") estado.alertas = true;
  const ano = parseInt(p.get("ano"), 10);
  if (ANOS.includes(ano)) estado.ano = ano;
  if (METRICAS[p.get("ind")]) estado.metrica = p.get("ind");
  const m = parseInt(p.get("m"), 10);
  if (ENTES.has(m)) estado.municipio = m;
  (p.get("e") || "").split(",").map(Number).forEach(adicionar);
  if (p.get("p")) estado.programa = p.get("p");
  if (p.get("esc")) estado.escola = parseInt(p.get("esc"), 10) || null;
  if (["todas", "municipal", "estadual"].includes(p.get("rede"))) estado.rede = p.get("rede");
}
function gravarHash() {
  const p = new URLSearchParams({ v: estado.visao, ano: estado.ano });
  if (estado.visao === "panorama") { p.set("ind", estado.metrica); if (estado.sel.length) p.set("e", estado.sel.join(",")); }
  if (["municipio", "fluxo", "escolas", "cnca"].includes(estado.visao) && estado.municipio) p.set("m", estado.municipio);
  if (estado.visao === "escolas") { if (estado.escola) p.set("esc", estado.escola); if (estado.rede !== "todas") p.set("rede", estado.rede); }
  if (estado.visao === "fluxo" && estado.sel.length) p.set("e", estado.sel.join(","));
  if (estado.visao === "conformidade" && estado.alertas) p.set("alertas", "1");
  if (estado.visao === "programas" && estado.programa) p.set("p", estado.programa);
  history.replaceState(null, "", "#" + p.toString());
}
