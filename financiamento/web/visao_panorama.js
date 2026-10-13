"use strict";
/* ============================================================================
   Visão 1 — Panorama do ES: KPIs, no que se gasta, ranking, comparação,
   evolução, execução bimestral e cobertura.
   ========================================================================== */

function panoramaFiltros(destino) {
  const linha = h("div", { class: "linha" },
    campo("Exercício", seletorAno("f-ano", estado.ano, v => { estado.ano = v; render(); })),
    campo("Adicionar à comparação (até " + MAX_COMPARAR + ")",
      seletorEnte("f-ente", "", cod => { adicionar(cod); render(); },
        { vazio: "Escolha um município…", comEstado: true, limpaApos: true })),
    campo("Indicador nos gráficos", (() => {
      const s = h("select", { id: "f-metrica", onchange: e => { estado.metrica = e.target.value; render(); } });
      Object.entries(METRICAS).forEach(([k, v]) => s.append(h("option", { value: k }, v.rotulo)));
      s.value = estado.metrica;
      return s;
    })()),
    h("button", { type: "button", class: "leve", onclick: () => { estado.sel = []; estado.slot.clear(); render(); } }, "Limpar seleção"));

  const chips = h("div", { class: "chips", "aria-live": "polite" });
  if (!estado.sel.length) {
    chips.append(h("span", { class: "dica" }, "Nenhum ente selecionado — escolha até " + MAX_COMPARAR + " para comparar lado a lado."));
  } else {
    estado.sel.forEach(cod => {
      const s = estado.slot.get(cod), chave = chaveLinha(cores().serie[s], FORMAS[s]);
      chave.classList.add("chave");
      chips.append(h("span", { class: "chip" }, chave, ENTES.get(cod).nome,
        h("button", { type: "button", "aria-label": "Remover " + ENTES.get(cod).nome, onclick: () => { remover(cod); render(); } }, "×")));
    });
    if (estado.sel.length >= MAX_COMPARAR) chips.append(h("span", { class: "dica" }, "Máximo de " + MAX_COMPARAR + " atingido."));
  }
  destino.append(linha, chips);
}

function panoramaKPIs() {
  const box = h("div", { class: "kpis", "aria-label": "Indicadores-chave" }), ano = estado.ano;
  const ok = linhasMun(ano).filter(r => !nulo(r.desp_educacao_empenhada));
  const soma = ok.reduce((s, r) => s + r.desp_educacao_empenhada, 0);
  const est = COD_ESTADO && LINHA.get(COD_ESTADO + "|" + ano);
  box.append(kpi("Despesa em Educação — municípios, " + ano, ok.length ? brlCompacto(soma) : "sem dado",
    ok.length + " de " + MUNICIPIOS.length + " municípios com dado · empenhada" +
    (est && !nulo(est.desp_educacao_empenhada) ? " · Estado, à parte: " + brlCompacto(est.desp_educacao_empenhada) : "")));

  const ant = ano - 1;
  if (ANOS.includes(ant)) {
    const comuns = ok.filter(r => { const p = LINHA.get(r.cod_ibge + "|" + ant); return p && !nulo(p.desp_educacao_empenhada); });
    const a = comuns.reduce((s, r) => s + r.desp_educacao_empenhada, 0);
    const b = comuns.reduce((s, r) => s + LINHA.get(r.cod_ibge + "|" + ant).desp_educacao_empenhada, 0);
    box.append(comuns.length && b > 0
      ? kpi("Variação anual, " + ant + " → " + ano, (a >= b ? "▲ +" : "▼ ") + nf(100 * (a - b) / b, 1) + "%",
          "nominal, sem deflator · " + comuns.length + " municípios com dado nos dois anos")
      : kpi("Variação anual, " + ant + " → " + ano, "sem dado", "nenhum município com dado nos dois exercícios", { nd: true }));
  } else {
    box.append(kpi("Variação anual", "n/d", ano + " é o primeiro exercício da série carregada", { nd: true }));
  }

  const mde = linhasMun(ano).filter(r => !nulo(r.mde_aplicado_pct));
  if (mde.length) {
    const abaixo = mde.filter(r => r.mde_abaixo_minimo === true).length;
    const doSiope = mde.filter(r => r.mde_situacao === "siope").length;
    box.append(kpi("Municípios abaixo do mínimo de MDE (" + nf(META.minimo_mde_pct, 0) + "%)", abaixo + " de " + mde.length,
      doSiope + " com o índice do SIOPE" + (mde.length > doSiope ? ", " + (mde.length - doSiope) + " de registro manual" : "") +
      (MUNICIPIOS.length > mde.length ? "; " + (MUNICIPIOS.length - mde.length) + " sem dado" : "")));
  } else {
    box.append(kpi("Municípios abaixo do mínimo de MDE (" + nf(META.minimo_mde_pct, 0) + "%)", "n/d",
      "0 de " + MUNICIPIOS.length + " com % de MDE neste exercício", { nd: true }));
  }

  for (const p of D.programas) for (const c of p.campos) {
    if (!c.kpi) continue;
    const regs = ((D.dados_manuais.programas[p.id] || {})[c.id] || []).filter(r => r.verificado);
    const ult = new Map();
    regs.forEach(r => { const a = ult.get(r.cod_ibge); if (!a || (r.ano || 0) >= (a.ano || 0)) ult.set(r.cod_ibge, r); });
    const positivos = [...ult.values()].filter(r => r.valor === c.kpi.valor).length;
    box.append(regs.length
      ? kpi(c.kpi.rotulo, positivos + " de " + ult.size, "entre os " + ult.size + " verificados manualmente · " + (MUNICIPIOS.length - ult.size) + " sem registro", { prog: true })
      : kpi(c.kpi.rotulo, "n/d", "0 de " + MUNICIPIOS.length + " verificados · dado manual (Painel do MEC), ainda não registrado", { prog: true, nd: true }));
  }
  return box;
}

/** Barras horizontais em HTML: uma cor só (a magnitude é o comprimento, não o tom). */
function barrasSubfuncao(itens, total, opcoes) {
  const o = opcoes || {};
  const maior = Math.max(...itens.map(i => i.empenhada), 0);
  return h("div", {}, itens.map(i => {
    const atencao = o.marcarForaPrioridade && SUB_FORA_DA_PRIORIDADE.has(i.codigo);
    return h("div", { class: "barra-sub" + (atencao ? " atencao" : "") },
      h("div", { class: "nome" }, i.nome, " ", h("span", { class: "cod" }, i.codigo)),
      h("div", { class: "trilho" }, h("div", { class: "fill", style: "width:" + (maior > 0 ? 100 * i.empenhada / maior : 0) + "%" })),
      h("div", { class: "valor" }, h("b", {}, brlCompacto(i.empenhada)), " ",
        h("span", { class: "pct" }, total > 0 ? nf(100 * i.empenhada / total, 1) + "%" : "")));
  }));
}

const COLUNAS_SUB = [
  { rotulo: "Código", valor: i => i.codigo },
  { rotulo: "Subfunção", valor: i => i.nome },
  { rotulo: "Empenhada (R$)", num: true, valor: i => i.empenhada, fmt: brl },
  { rotulo: "Liquidada (R$)", num: true, valor: i => i.liquidada, fmt: brl },
  { rotulo: "Paga (R$)", num: true, valor: i => i.paga, fmt: brl },
  { rotulo: "% da Educação", num: true, valor: i => i.pct_educacao, fmt: v => nf(v, 2) + "%" },
];

function cardNoQueSeGasta() {
  const ano = estado.ano, cods = MUNICIPIOS.map(e => e.cod_ibge);
  const card = h("article", { class: "card largo" },
    cabecalho("No que os municípios gastam — Educação por subfunção, " + ano,
      "Soma dos 78 municípios. As subfunções são o detalhe da função 12 no DCA Anexo I-E e somam exatamente o total da Educação. O Estado fica de fora (é mostrado à parte).",
      { itens: () => [{ indicador: "subfuncao_empenhada", ano, detalhe: "todas as subfunções da função 12, soma dos " + cods.length + " municípios", q: qAnual("q_dca_ie", cods, ano) }] }));

  const agregado = new Map();
  for (const e of MUNICIPIOS) {
    for (const s of subDe(e.cod_ibge, ano)) {
      const a = agregado.get(s.codigo) || { codigo: s.codigo, nome: s.nome, empenhada: 0, liquidada: 0, paga: 0, municipios: 0 };
      a.empenhada += s.empenhada || 0; a.liquidada += s.liquidada || 0; a.paga += s.paga || 0; a.municipios++;
      agregado.set(s.codigo, a);
    }
  }
  const itens = [...agregado.values()].sort((a, b) => b.empenhada - a.empenhada);
  if (!itens.length) { card.append(h("p", { class: "muted" }, "Sem detalhe por subfunção neste exercício.")); return card; }
  const total = itens.reduce((s, i) => s + i.empenhada, 0);
  itens.forEach(i => { i.pct_educacao = total > 0 ? 100 * i.empenhada / total : null; });

  card.append(barrasSubfuncao(itens, total, { marcarForaPrioridade: true }));
  const fora = itens.filter(i => SUB_FORA_DA_PRIORIDADE.has(i.codigo));
  if (fora.length) {
    card.append(h("div", { class: "callout" },
      h("strong", {}, "Fora da prioridade municipal (art. 211 CF). "),
      "O município atua prioritariamente no ensino fundamental e na educação infantil. Em " + ano + ", " +
      fora.map(i => i.nome.toLowerCase() + " aparece em " + i.municipios + " município(s), " + brlCompacto(i.empenhada)).join("; ") +
      ". Não é irregularidade por si — é ponto a verificar caso a caso."));
  }
  const colunas = [{ rotulo: "Municípios com a subfunção", num: true, valor: i => i.municipios }].concat(COLUNAS_SUB.slice(0, 5));
  card.append(h("details", { class: "tab" }, h("summary", {}, "Valores por trás do gráfico — subfunções (" + itens.length + " linhas)"),
    tabela(COLUNAS_SUB.slice(0, 5).concat(colunas[0]), itens, "Educação por subfunção, municípios do ES, " + ano,
      { inteira: true, rodape: ["", "Total", brl(total), "", ""] }),
    botaoCSV("subfuncoes_es_" + ano + ".csv", COLUNAS_SUB, itens)));
  return card;
}

function cardComparacao() {
  const ano = estado.ano;
  const card = h("article", { class: "card largo" }, cabecalho("Comparação lado a lado — " + ano,
    "Os entes escolhidos no filtro, no exercício selecionado. “sem dado” é ausência na fonte, nunca zero.",
    { itens: () => estado.sel.flatMap(cod => { const r = LINHA.get(cod + "|" + ano) || {}; const nome = ENTES.get(cod).nome; return [
      { indicador: "desp_educacao_empenhada", ano, detalhe: nome, q: r.q_dca_ie, valor: nulo(r.desp_educacao_empenhada) ? null : brl(r.desp_educacao_empenhada) },
      { indicador: "fundeb_receita", ano, detalhe: nome, q: r.q_dca_ic, valor: nulo(r.fundeb_receita) ? null : brl(r.fundeb_receita) },
      nulo(r.desp_educacao_por_matricula) ? null : { indicador: "desp_educacao_por_matricula", ano, detalhe: nome,
        q: [r.q_dca_ie, r.q_tcees_mde].filter(Boolean).join(";"), valor: brl(r.desp_educacao_por_matricula) },
      r.mde_situacao === "siope" ? { indicador: "mde_pct", ano, detalhe: nome, q: r.q_siope, valor: pct(r.mde_aplicado_pct, 2) } : null].filter(Boolean); }) }));
  if (!estado.sel.length) { card.append(h("p", { class: "muted" }, "Selecione ao menos um município ou o Estado.")); return card; }
  const linhasDef = [
    ["População do exercício", r => r.populacao, v => nf(v)],
    ["Matrículas na rede municipal", r => r.tcees_alunos, v => nf(v)],
    ["Despesa em Educação (empenhada)", r => r.desp_educacao_empenhada, brl],
    ["Despesa em Educação (liquidada)", r => r.desp_educacao_liquidada, brl],
    ["Despesa em Educação (paga)", r => r.desp_educacao_paga, brl],
    ["Per capita (R$/hab.)", r => r.desp_educacao_per_capita, brl],
    ["Por matrícula (R$/matrícula)", r => r.desp_educacao_por_matricula, brl],
    ["Matrículas ÷ população", r => nulo(r.tcees_alunos) || !r.populacao ? null : 100 * r.tcees_alunos / r.populacao, v => nf(v, 1) + "%"],
    ["Educação em % da despesa total", r => r.desp_educacao_pct_total, v => nf(v, 2) + "%"],
    ["Receita do FUNDEB recebida", r => r.fundeb_receita, brl],
    ["Contribuição ao FUNDEB", r => r.fundeb_contribuicao, brl],
    ["FUNDEB líquido (recebida − contribuição)", r => r.fundeb_liquido, brl],
    ["Receita do FUNDEB ÷ despesa em Educação", r => r.fundeb_pct_desp_educacao, v => nf(v, 1) + "%"],
    ["% aplicado em MDE (SIOPE; mín. 25%)", r => r.mde_aplicado_pct, v => nf(v, 2) + "%"],
    ["% do FUNDEB na remuneração (SIOPE; mín. 70%)", r => r.fundeb70_pct, v => nf(v, 2) + "%"],
  ];
  const cols = [{ rotulo: "Indicador", valor: l => l[0] }].concat(estado.sel.map(cod => ({
    rotulo: ENTES.get(cod).nome, num: true,
    valor: l => { const r = LINHA.get(cod + "|" + ano); return r ? l[1](r) : null; },
    render: l => { const r = LINHA.get(cod + "|" + ano), v = r ? l[1](r) : null; return nulo(v) ? "sem dado" : l[2](v); },
  })));
  const tab = tabela(cols, linhasDef, "Comparação lado a lado, " + ano, { inteira: true });
  card.append(h("p", { class: "nota" }, "Dois denominadores, porque medem coisas diferentes: o ", h("strong", {}, "per capita"),
    " divide pela população do município (que só muda a cada dois exercícios) e o ", h("strong", {}, "por matrícula"),
    " divide pelas matrículas da rede municipal no ano (coluna \"Alunos\" do TCE-ES, conferida contra o Censo). " +
    "Para comparar municípios com redes de tamanhos diferentes, o por matrícula é o denominador mais próximo do serviço prestado." +
    (estado.sel.includes(COD_ESTADO) ? " O Estado fica sem matrículas: o recurso do TCE-ES cobre só os municípios." : "")));
  card.append(tab, botaoCSV("comparacao_" + ano + ".csv",
    cols.map(c => ({ rotulo: c.rotulo, valor: c.render ? (x => { const t = c.render(x); return t === "sem dado" ? "" : t; }) : c.valor })), linhasDef));
  return card;
}

function cardEvolucao() {
  const m = METRICAS[estado.metrica];
  const card = h("article", { class: "card" }, cabecalho("Evolução, " + ANOS[0] + "–" + ANOS[ANOS.length - 1], m.rotulo + ". " + m.nota,
    { itens: () => estado.sel.flatMap(cod => ANOS.map(a => ({ indicador: indicadorDaMetrica(m), ano: a, detalhe: ENTES.get(cod).nome + ", " + a,
      q: qDaMetrica(m, cod, a) }))) }));
  if (!estado.sel.length) { card.append(h("p", { class: "muted" }, "Selecione entes para ver a evolução.")); return card; }
  const cs = cores();
  const cv = h("canvas", { role: "img", "aria-label": "Evolução de " + m.rotulo + " para " + estado.sel.map(c => ENTES.get(c).nome).join(", ") + ". Valores na tabela abaixo." });
  card.append(legendaEntes(estado.sel), h("div", { class: "grafico" }, temChart() ? cv : avisoSemChart()));
  if (temChart()) {
    const op = opcoesBase(cs, eixoY(m));
    op.plugins.tooltip.callbacks.label = c => " " + c.dataset.label + ": " + fmtMetricaCheio(m, c.parsed.y);
    setTimeout(() => desenhar("evol", cv, { type: "line",
      data: { labels: ANOS, datasets: conjuntoLinhas(ANOS, (cod, ano) => valorMetrica(m, cod, ano), estado.sel) },
      options: op, plugins: [plugCrosshair] }), 0);
  }
  const linhas = [];
  estado.sel.forEach(cod => ANOS.forEach(a => linhas.push({ cod, ano: a, r: LINHA.get(cod + "|" + a) || {} })));
  card.append(blocoTabela("evolução", [
    { rotulo: "Ente", valor: l => ENTES.get(l.cod).nome },
    { rotulo: "Ano", valor: l => l.ano },
    { rotulo: m.rotulo, num: true, valor: l => valorMetrica(m, l.cod, l.ano),
      render: l => { const v = valorMetrica(m, l.cod, l.ano); return nulo(v) ? "sem dado" : fmtMetricaCheio(m, v); } },
    { rotulo: "Despesa empenhada (R$)", num: true, valor: l => l.r.desp_educacao_empenhada, render: l => nulo(l.r.desp_educacao_empenhada) ? "sem dado" : brl(l.r.desp_educacao_empenhada) },
    { rotulo: "População", num: true, valor: l => l.r.populacao, fmt: nf },
    { rotulo: "Situação da DCA", valor: l => l.r.status_dca || "sem linha" },
  ], linhas, "evolucao_" + estado.metrica + ".csv"));
  return card;
}

function cardRanking() {
  const m = METRICAS[estado.metrica], ano = estado.ano;
  const card = h("article", { class: "card" }, cabecalho("Ranking dos municípios, " + ano,
    m.rotulo + ". Só municípios (o Estado fica de fora). Os selecionados aparecem na cor da comparação.",
    { itens: () => [{ indicador: indicadorDaMetrica(m), ano, detalhe: "os " + MUNICIPIOS.length + " municípios",
      q: MUNICIPIOS.map(e => qDaMetrica(m, e.cod_ibge, ano)).join(";") }] }));
  const todos = MUNICIPIOS.map(e => ({ cod: e.cod_ibge, nome: e.nome, v: valorMetrica(m, e.cod_ibge, ano) }));
  const com = todos.filter(x => !nulo(x.v)).sort((a, b) => b.v - a.v);
  const sem = todos.filter(x => nulo(x.v));
  com.forEach((x, i) => { x.pos = i + 1; });

  const sel = h("select", { id: "f-topo", onchange: e => { estado.topo = e.target.value; render(); } },
    h("option", { value: "15" }, "15 maiores"), h("option", { value: "-15" }, "15 menores"), h("option", { value: "todos" }, "Todos (" + com.length + ")"));
  sel.value = estado.topo;
  card.append(h("div", { style: "max-width:240px;margin-top:6px" }, campo("Mostrar", sel)));

  const fatia = estado.topo === "todos" ? com : estado.topo === "-15" ? com.slice(-15) : com.slice(0, 15);
  const cs = cores(), altura = Math.max(200, fatia.length * 22 + 50);
  const cv = h("canvas", { role: "img", "aria-label": "Ranking de " + m.rotulo + " em " + ano + ". Valores na tabela abaixo." });
  card.append(h("div", { class: "grafico", style: "height:" + altura + "px" }, temChart() ? cv : avisoSemChart()));
  if (temChart() && fatia.length) {
    const destacar = new Set(), cor = [];
    fatia.forEach((x, i) => { if (estado.sel.includes(x.cod)) { destacar.add(i); cor.push(cs.serie[estado.slot.get(x.cod)]); } else cor.push(cs.neutro); });
    const op = opcoesBase(cs, eixoY(m));
    op.indexAxis = "y"; op.interaction = { mode: "nearest", axis: "y", intersect: false };
    op.layout.padding.right = 78;
    op.scales.x = op.scales.y;
    op.scales.x.ticks = { ...op.scales.x.ticks, maxRotation: 0, autoSkip: true, maxTicksLimit: 6 };
    op.scales.y = { grid: { display: false }, border: { color: cs.axis }, ticks: { color: cs.ink2, font: { size: 12 }, autoSkip: false } };
    op.plugins.tooltip.callbacks = { title: i => (fatia[i[0].dataIndex].pos + "º · " + fatia[i[0].dataIndex].nome), label: c => " " + fmtMetricaCheio(m, c.parsed.x) };
    op.plugins.rotulosSelecionados = { destacar, formatar: v => fmtMetrica(m, v) };
    // Em tela estreita o eixo não comporta nomes longos: abrevia o RÓTULO (o nome
    // inteiro continua no tooltip e na tabela).
    const abrev = n => innerWidth < 600 && n.length > 15 ? n.slice(0, 14) + "…" : n;
    setTimeout(() => desenhar("rank", cv, { type: "bar",
      data: { labels: fatia.map(x => abrev(x.nome)), datasets: [{ data: fatia.map(x => x.v), backgroundColor: cor,
        barThickness: 14, borderRadius: { topRight: 4, bottomRight: 4, topLeft: 0, bottomLeft: 0 }, borderSkipped: false }] },
      options: op, plugins: [plugRotulos] }), 0);
  }
  const posicoes = estado.sel.filter(c => ENTES.get(c).esfera === "M")
    .map(c => { const x = com.find(y => y.cod === c); return ENTES.get(c).nome + ": " + (x ? x.pos + "º de " + com.length : "sem dado"); });
  if (posicoes.length) card.append(h("p", { class: "nota" }, "Posição — " + posicoes.join(" · ")));
  if (sem.length) card.append(h("p", { class: "nota" }, "Sem dado neste indicador e exercício (" + sem.length + "): " + sem.map(x => x.nome).join(", ") + "."));
  card.append(blocoTabela("ranking completo", [
    { rotulo: "Posição", num: true, valor: l => l.pos, render: l => l.pos ? l.pos + "º" : "—" },
    { rotulo: "Município", valor: l => l.nome },
    { rotulo: m.rotulo, num: true, valor: l => l.v, render: l => nulo(l.v) ? "sem dado" : fmtMetricaCheio(m, l.v) },
  ], com.concat(sem), "ranking_" + estado.metrica + "_" + ano + ".csv", { destacar: l => estado.sel.includes(l.cod) }));
  return card;
}

function cardBimestral() {
  const ano = estado.ano, m = METRICAS[estado.metrica], porHab = estado.metrica === "pc";
  const card = h("article", { class: "card largo" }, cabecalho("Execução bimestral em " + ano + " — despesa empenhada acumulada em Educação",
    "RREO Anexo 02, valores acumulados até o bimestre (municípios pequenos publicam em “RREO Simplificado”). " +
      (porHab ? "Em R$ por habitante, para acompanhar o indicador escolhido. " : "Em R$. ") + "Bimestre sem publicação fica em branco.",
    { itens: () => estado.sel.flatMap(cod => [1, 2, 3, 4, 5, 6].map(b => BIM.get(cod + "|" + ano + "|" + b)).filter(Boolean)
      .map(x => ({ indicador: "empenhada_acum", ano, detalhe: String(x.bimestre), observacao: ENTES.get(cod).nome + " · " + x.tipo_rreo, q: x.q }))) }));
  if (!estado.sel.length) { card.append(h("p", { class: "muted" }, "Selecione entes para ver a execução no ano.")); return card; }
  const cs = cores(), bims = [1, 2, 3, 4, 5, 6];
  const valorDe = (cod, b) => {
    const x = BIM.get(cod + "|" + ano + "|" + b); if (!x || nulo(x.empenhada_acum)) return null;
    if (!porHab) return x.empenhada_acum;
    const p = (LINHA.get(cod + "|" + ano) || {}).populacao; return p ? x.empenhada_acum / p : null;
  };
  const cv = h("canvas", { role: "img", "aria-label": "Despesa empenhada acumulada por bimestre em " + ano + ". Valores na tabela abaixo." });
  card.append(legendaEntes(estado.sel), h("div", { class: "grafico" }, temChart() ? cv : avisoSemChart()));
  if (temChart()) {
    const op = opcoesBase(cs, porHab ? (v => "R$ " + nf(v, 0)) : tickMoeda);
    op.plugins.tooltip.callbacks.label = c => " " + c.dataset.label + ": " + brl(c.parsed.y);
    op.plugins.tooltip.callbacks.title = i => i[0].label;
    setTimeout(() => desenhar("bim", cv, { type: "line",
      data: { labels: bims.map(b => b + "º bim"), datasets: conjuntoLinhas(bims, valorDe, estado.sel) },
      options: op, plugins: [plugCrosshair] }), 0);
  }
  const linhas = [];
  estado.sel.forEach(cod => bims.forEach(b => linhas.push({ cod, b, x: BIM.get(cod + "|" + ano + "|" + b) })));
  card.append(blocoTabela("execução bimestral", [
    { rotulo: "Ente", valor: l => ENTES.get(l.cod).nome }, { rotulo: "Bimestre", valor: l => l.b },
    { rotulo: "Tipo de RREO", valor: l => l.x ? l.x.tipo_rreo : null },
    { rotulo: "Dotação atualizada (R$)", num: true, valor: l => l.x && l.x.dotacao_atualizada, render: l => l.x && !nulo(l.x.dotacao_atualizada) ? brl(l.x.dotacao_atualizada) : "sem dado" },
    { rotulo: "Empenhada acumulada (R$)", num: true, valor: l => l.x && l.x.empenhada_acum, render: l => l.x && !nulo(l.x.empenhada_acum) ? brl(l.x.empenhada_acum) : "sem dado" },
    { rotulo: "Liquidada acumulada (R$)", num: true, valor: l => l.x && l.x.liquidada_acum, render: l => l.x && !nulo(l.x.liquidada_acum) ? brl(l.x.liquidada_acum) : "sem dado" },
  ], linhas, "bimestral_" + ano + ".csv"));
  return card;
}

function cardMDE() {
  const ano = estado.ano, min = META.minimo_mde_pct, cods = MUNICIPIOS.map(e => e.cod_ibge);
  const card = h("article", { class: "card" }, cabecalho("MDE — mínimo constitucional de " + nf(min, 0) + "% (art. 212 CF)",
    "Despesa em manutenção e desenvolvimento do ensino como % da receita de impostos e transferências — o índice apurado pelo SIOPE.",
    { itens: () => [{ indicador: "mde_pct", ano, detalhe: "os " + cods.length + " municípios", q: qAnual("q_siope", cods, ano) }] }));
  const com = linhasMun(ano).filter(r => !nulo(r.mde_aplicado_pct));
  card.append(h("div", { class: "callout", role: "note" }, h("strong", {}, "De onde vem. "),
    "O SICONFI não publica o RREO Anexo 08 por API. O índice é o do SIOPE, lido do PDF do Anexo 8 que o FNDE publica no FTP " +
    "(os relatórios HTML do SIOPE exigem reCAPTCHA). Registro manual só entra onde o SIOPE não tem o dado."));
  if (!com.length) {
    card.append(h("p", {}, h("span", { class: "badge nada" }, "Sem dado"), " Nenhum município com % de MDE em " + ano + "."));
    return card;
  }
  const abaixo = com.filter(r => r.mde_abaixo_minimo === true).sort((a, b) => a.mde_aplicado_pct - b.mde_aplicado_pct);
  card.append(h("p", {}, h("strong", {}, abaixo.length + " de " + com.length), " municípios abaixo de " + nf(min, 0) + "% em " + ano + "."));
  if (abaixo.length) card.append(tabela([
    { rotulo: "Município", valor: r => r.ente },
    { rotulo: "% aplicado", num: true, valor: r => r.mde_aplicado_pct, fmt: v => nf(v, 2) + "%" },
    { rotulo: "Frente ao mínimo", valor: r => r.mde_abaixo_minimo, render: () => h("span", { class: "flag-abaixo" }, "✖ Abaixo de " + nf(min, 0) + "%") },
    { rotulo: "Origem", valor: r => r.mde_situacao, render: r => r.mde_situacao === "siope" ? h("span", { class: "badge aviso" }, "SIOPE (PDF)")
        : h("span", { class: "badge manual" }, "Manual · " + dataBR(r.mde_verificado_em)) },
  ], abaixo, "Municípios abaixo do mínimo de MDE, " + ano, { classeLinha: () => "alerta" }));
  card.append(h("div", { class: "rodape-card" }, h("button", { type: "button", class: "leve", onclick: () => irPara("conformidade") }, "Todos os municípios, FUNDEB 70% e entregas →")));
  return card;
}

function cardCobertura() {
  const ano = estado.ano, mun = linhasMun(ano);
  const card = h("article", { class: "card" }, h("header", {},
    h("h3", {}, "Cobertura e conferências — " + ano),
    h("p", { class: "nota" }, "Municípios sem dado são reportados aqui, nunca omitidos nem preenchidos com zero.")));
  const rot = { sem_dado_publicado: "não publicou", falha_consulta: "falha na consulta (refazer o ETL)", funcao_ausente: "sem a função Educação",
    sem_linha_fundeb: "sem linha de FUNDEB", nao_coletado: "não coletado (fora do cache)", sem_pdf_publicado: "sem PDF no FTP do FNDE",
    pdf_ilegivel: "PDF ilegível", parcial: "PDF lido em parte" };
  const item = (titulo, ok, faltam) => h("li", {}, h("strong", {}, titulo + ": "), ok + " de " + mun.length +
    (faltam.length ? ". Sem dado: " + faltam.map(r => r.ente + " (" + (rot[r.status] || r.status) + ")").join("; ") + "." : " — nenhum município ausente."));
  const semDCA = mun.filter(r => r.status_dca !== "ok").map(r => ({ ...r, status: r.status_dca }));
  const semFun = mun.filter(r => r.status_fundeb !== "ok").map(r => ({ ...r, status: r.status_fundeb }));
  const semB6 = mun.filter(r => nulo(r.rreo_b6_empenhada));
  const incompleto = mun.filter(r => r.n_bimestres_rreo < 6);
  const semMSC = mun.filter(r => r.status_msc !== "ok").map(r => ({ ...r, status: r.status_msc || "sem linha" }));
  const semSIOPE = mun.filter(r => r.status_siope !== "ok").map(r => ({ ...r, status: r.status_siope || "sem linha" }));
  card.append(h("ul", { class: "lista" },
    item("DCA (despesa por função)", mun.length - semDCA.length, semDCA),
    item("FUNDEB (DCA Anexo I-C)", mun.length - semFun.length, semFun),
    item("MSC orçamentária (natureza e fonte)", mun.length - semMSC.length, semMSC),
    item("SIOPE (Anexo 8 em PDF)", mun.length - semSIOPE.length, semSIOPE),
    h("li", {}, h("strong", {}, "RREO, 6º bimestre: "), (mun.length - semB6.length) + " de " + mun.length +
      (semB6.length ? ". Sem dado: " + semB6.map(r => r.ente).join("; ") + "." : " — nenhum município ausente.") +
      (incompleto.length ? " Com algum bimestre faltando: " + incompleto.length + "." : ""))));
  const v = D.verificacoes, div = v.rreo_vs_dca.divergentes;
  const sub = v.subfuncoes_fecham;
  card.append(h("p", { class: "nota" }, h("strong", {}, "Conferências do ETL (todos os exercícios). "),
    "Soma das funções da DCA fecha com o total do anexo: " + (v.fechamento_dca.conferidos - v.fechamento_dca.falhas.length) + " de " + v.fechamento_dca.conferidos + " ente-anos. " +
    (sub ? "Soma das subfunções fecha com a função 12: " + (sub.conferidos - sub.falhas.length) + " de " + sub.conferidos + ". " : "") +
    "6º bimestre do RREO vs DCA: " + (v.rreo_vs_dca.comparaveis - div) + " de " + v.rreo_vs_dca.comparaveis + " dentro de 0,5%" +
    (div ? "; " + div + " divergem (retificações entre RREO e DCA)." : ".")));
  if (v.rreo_vs_dca.maiores.length) card.append(h("details", { class: "tab" }, h("summary", {}, "Maiores divergências RREO × DCA"),
    tabela([{ rotulo: "Ente", valor: r => r.ente }, { rotulo: "Ano", valor: r => r.ano },
      { rotulo: "RREO 6º bim. vs DCA (%)", num: true, valor: r => r.dif_rreo_dca_pct, fmt: x => nf(x, 2) + "%" }],
      v.rreo_vs_dca.maiores, "Maiores divergências RREO × DCA")));
  if (v.falhas_consulta_rreo.length) card.append(h("div", { class: "callout warn" }, "Consultas do RREO que falharam: " + v.falhas_consulta_rreo.length + " ente-ano(s). Refaça o ETL."));
  return card;
}

function renderPanorama(destino) {
  destino.append(panoramaKPIs());
  destino.append(h("section", { class: "bloco" },
    h("header", {}, h("h2", {}, "Financiamento geral"),
      h("p", { class: "muted small" }, "Fonte: SICONFI (Tesouro Nacional) — DCA (fechamento anual) e RREO Anexo 02 (bimestral). Valores nominais, despesa empenhada, exceto intra-orçamentárias.")),
    h("div", { class: "grade" },
      cardNoQueSeGasta(), cardComparacao(), cardEvolucao(), cardRanking(), cardBimestral(), cardMDE(), cardCobertura())));
}
