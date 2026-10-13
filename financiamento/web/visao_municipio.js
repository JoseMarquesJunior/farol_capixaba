"use strict";
/* ============================================================================
   Visão 2 — Ficha do município: tudo de um ente num lugar só. O coração é o
   detalhe por subfunção (no que o dinheiro da Educação foi gasto).
   ========================================================================== */

function municipioFiltros(destino) {
  destino.append(h("div", { class: "linha" },
    campo("Município", seletorEnte("f-mun", estado.municipio, cod => { estado.municipio = cod; render(); }, { comEstado: true })),
    campo("Exercício", seletorAno("f-ano-mun", estado.ano, v => { estado.ano = v; render(); })),
    h("button", { type: "button", class: "leve", onclick: () => { irPara("fluxo"); } }, "Receita → aplicação deste município"),
    h("button", { type: "button", class: "leve", onclick: () => { irPara("panorama"); } }, "Ver no panorama do ES")));
}

/** Posição do ente no ranking de uma métrica, entre os municípios. */
function posicaoNoRanking(m, cod, ano) {
  const com = MUNICIPIOS.map(e => ({ cod: e.cod_ibge, v: valorMetrica(m, e.cod_ibge, ano) }))
    .filter(x => !nulo(x.v)).sort((a, b) => b.v - a.v);
  const i = com.findIndex(x => x.cod === cod);
  return i < 0 ? null : { pos: i + 1, de: com.length };
}

function fichaKPIs(cod, ano, r, ehMunicipio) {
  const box = h("div", { class: "kpis" });
  const posicao = ehMunicipio ? posicaoNoRanking(METRICAS.desp, cod, ano) : null;
  box.append(kpi("Despesa em Educação, " + ano,
    nulo(r.desp_educacao_empenhada) ? "sem dado" : brlCompacto(r.desp_educacao_empenhada),
    "empenhada, função 12" + (posicao ? " · " + posicao.pos + "º de " + posicao.de + " municípios" : " · Estado, fora do ranking"),
    { nd: nulo(r.desp_educacao_empenhada) }));

  const posPC = ehMunicipio ? posicaoNoRanking(METRICAS.pc, cod, ano) : null;
  box.append(kpi("Per capita", nulo(r.desp_educacao_per_capita) ? "sem dado" : brl(r.desp_educacao_per_capita),
    (nulo(r.populacao) ? "sem população" : nf(r.populacao) + " habitantes no exercício") + (posPC ? " · " + posPC.pos + "º de " + posPC.de : ""),
    { nd: nulo(r.desp_educacao_per_capita) }));

  const posPM = ehMunicipio ? posicaoNoRanking(METRICAS.pm, cod, ano) : null;
  box.append(kpi("Por matrícula", nulo(r.desp_educacao_por_matricula) ? "sem dado" : brl(r.desp_educacao_por_matricula),
    (nulo(r.tcees_alunos) ? (ehMunicipio ? "sem matrículas na fonte" : "o TCE-ES não publica matrículas do Estado")
      : nf(r.tcees_alunos) + " matrículas na rede municipal") + (posPM ? " · " + posPM.pos + "º de " + posPM.de : ""),
    { nd: nulo(r.desp_educacao_por_matricula) }));

  box.append(kpi("Educação na despesa do ente", pct(r.desp_educacao_pct_total),
    nulo(r.desp_total_empenhada) ? "sem o total do ente" : "de " + brlCompacto(r.desp_total_empenhada) + " empenhados no total",
    { nd: nulo(r.desp_educacao_pct_total) }));

  const ant = ano - 1, anterior = LINHA.get(cod + "|" + ant);
  if (anterior && !nulo(anterior.desp_educacao_empenhada) && !nulo(r.desp_educacao_empenhada) && anterior.desp_educacao_empenhada > 0) {
    const d = 100 * (r.desp_educacao_empenhada - anterior.desp_educacao_empenhada) / anterior.desp_educacao_empenhada;
    box.append(kpi("Variação, " + ant + " → " + ano, (d >= 0 ? "▲ +" : "▼ ") + nf(d, 1) + "%",
      "nominal, sem deflator · de " + brlCompacto(anterior.desp_educacao_empenhada)));
  } else {
    box.append(kpi("Variação anual", "n/d", ANOS.includes(ant) ? "sem dado em " + ant : ano + " é o primeiro exercício carregado", { nd: true }));
  }
  return box;
}

function cardSubfuncoes(cod, ano, r, ehMunicipio) {
  const itens = subDe(cod, ano);
  const card = h("article", { class: "card largo" }, cabecalho("No que foi gasto — Educação por subfunção, " + ano,
    "Detalhe da função 12 no DCA Anexo I-E (Nível 1). As subfunções somam exatamente a despesa em Educação, então esta é a decomposição completa do gasto — não uma amostra.",
    { itens: () => itens.map(i => ({ indicador: "subfuncao_empenhada", ano, detalhe: i.codigo + " - " + i.nome, q: i.q, valor: brl(i.empenhada) }))
        .concat([{ indicador: "desp_educacao_empenhada", ano, q: r.q_dca_ie, valor: nulo(r.desp_educacao_empenhada) ? null : brl(r.desp_educacao_empenhada) }]) }));
  if (!itens.length) {
    card.append(h("p", {}, h("span", { class: "badge nada" }, "Sem dado"),
      " Este ente não tem detalhe por subfunção em " + ano + (r.status_dca === "ok" ? "." : " (situação da DCA: " + (r.status_dca || "sem linha") + ").")));
    return card;
  }
  const total = r.desp_educacao_empenhada || itens.reduce((s, i) => s + (i.empenhada || 0), 0);
  card.append(barrasSubfuncao(itens, total, { marcarForaPrioridade: ehMunicipio }));

  const admin = itens.find(i => i.codigo === SUB_ADMINISTRACAO);
  const fora = ehMunicipio ? itens.filter(i => SUB_FORA_DA_PRIORIDADE.has(i.codigo)) : [];
  const notas = [];
  if (admin) notas.push("Administração Geral concentra " + nf(admin.pct_educacao, 1) + "% da despesa em Educação (" + brlCompacto(admin.empenhada) + ").");
  if (fora.length) {
    notas.push("Fora da prioridade municipal do art. 211 da CF: " +
      fora.map(i => i.nome.toLowerCase() + " (" + brlCompacto(i.empenhada) + ", " + nf(i.pct_educacao, 1) + "%)").join(" e ") +
      ". Não é irregularidade por si — é ponto a verificar.");
  }
  if (notas.length) card.append(h("div", { class: "callout" + (fora.length ? " warn" : "") }, notas.join(" ")));

  card.append(tabela(COLUNAS_SUB, itens, "Educação por subfunção — " + ENTES.get(cod).nome + ", " + ano,
    { inteira: true, rodape: ["", "Total da função 12", brl(total), nulo(r.desp_educacao_liquidada) ? "" : brl(r.desp_educacao_liquidada), nulo(r.desp_educacao_paga) ? "" : brl(r.desp_educacao_paga), "100%"] }));
  card.append(botaoCSV("subfuncoes_" + cod + "_" + ano + ".csv", COLUNAS_SUB, itens));
  return card;
}

function cardMatrizSubfuncoes(cod) {
  const card = h("article", { class: "card largo" }, cabecalho("Subfunção por exercício — despesa empenhada",
    "A série completa do ente. Célula vazia = a subfunção não aparece na DCA daquele exercício (não é zero).",
    { itens: () => ANOS.map(a => ({ indicador: "subfuncao_empenhada", ano: a, detalhe: "todas as subfunções, " + a, q: (LINHA.get(cod + "|" + a) || {}).q_dca_ie })) }));
  const codigos = new Map();
  for (const ano of ANOS) for (const s of subDe(cod, ano)) if (!codigos.has(s.codigo)) codigos.set(s.codigo, s.nome);
  if (!codigos.size) { card.append(h("p", { class: "muted" }, "Sem detalhe por subfunção em nenhum exercício carregado.")); return card; }

  const valor = (codigo, ano) => { const s = subDe(cod, ano).find(x => x.codigo === codigo); return s ? s.empenhada : null; };
  const linhas = [...codigos].map(([codigo, nome]) => ({ codigo, nome }))
    .sort((a, b) => (valor(b.codigo, estado.ano) || 0) - (valor(a.codigo, estado.ano) || 0));
  const colunas = [{ rotulo: "Subfunção", valor: l => l.codigo + " — " + l.nome }].concat(ANOS.map(ano => ({
    rotulo: String(ano), num: true, valor: l => valor(l.codigo, ano),
    render: l => { const v = valor(l.codigo, ano); return nulo(v) ? "—" : brlCompacto(v); },
  })));
  const rodape = ["Total da Educação"].concat(ANOS.map(ano => {
    const r = LINHA.get(cod + "|" + ano);
    return r && !nulo(r.desp_educacao_empenhada) ? brlCompacto(r.desp_educacao_empenhada) : "—";
  }));
  card.append(tabela(colunas, linhas, "Subfunção por exercício", { inteira: true, rodape }),
    botaoCSV("subfuncoes_serie_" + cod + ".csv", colunas, linhas));
  return card;
}

function cardEvolucaoMunicipio(cod) {
  const card = h("article", { class: "card" }, cabecalho("Evolução da despesa em Educação",
    "Empenhada na função 12, " + ANOS[0] + "–" + ANOS[ANOS.length - 1] + ", em valores nominais.",
    { itens: () => ANOS.map(a => { const x = LINHA.get(cod + "|" + a) || {}; return { indicador: "desp_educacao_empenhada", ano: a, detalhe: String(a), q: x.q_dca_ie,
      valor: nulo(x.desp_educacao_empenhada) ? null : brl(x.desp_educacao_empenhada) }; }) }));
  const cs = cores();
  const cv = h("canvas", { role: "img", "aria-label": "Evolução da despesa em Educação de " + ENTES.get(cod).nome + ". Valores na tabela abaixo." });
  card.append(h("div", { class: "grafico" }, temChart() ? cv : avisoSemChart()));
  const linhas = ANOS.map(ano => ({ ano, r: LINHA.get(cod + "|" + ano) || {} }));
  if (temChart()) {
    const op = opcoesBase(cs, tickMoeda);
    op.plugins.tooltip.callbacks.label = c => " " + brl(c.parsed.y);
    op.plugins.tooltip.callbacks.title = i => "Exercício " + i[0].label;
    setTimeout(() => desenhar("mun-evol", cv, { type: "line", data: { labels: ANOS, datasets: [{
      label: "Despesa em Educação", data: linhas.map(l => nulo(l.r.desp_educacao_empenhada) ? null : l.r.desp_educacao_empenhada),
      borderColor: cs.serie[0], backgroundColor: cs.serie[0], borderWidth: 2, tension: 0, spanGaps: false,
      pointStyle: "circle", pointRadius: 5, pointHoverRadius: 7, pointBorderColor: cs.surface, pointBorderWidth: 2 }] },
      options: op, plugins: [plugCrosshair] }), 0);
  }
  card.append(blocoTabela("evolução", [
    { rotulo: "Ano", valor: l => l.ano },
    { rotulo: "Empenhada (R$)", num: true, valor: l => l.r.desp_educacao_empenhada, render: l => nulo(l.r.desp_educacao_empenhada) ? "sem dado" : brl(l.r.desp_educacao_empenhada) },
    { rotulo: "Liquidada (R$)", num: true, valor: l => l.r.desp_educacao_liquidada, render: l => nulo(l.r.desp_educacao_liquidada) ? "sem dado" : brl(l.r.desp_educacao_liquidada) },
    { rotulo: "Paga (R$)", num: true, valor: l => l.r.desp_educacao_paga, render: l => nulo(l.r.desp_educacao_paga) ? "sem dado" : brl(l.r.desp_educacao_paga) },
    { rotulo: "Per capita (R$)", num: true, valor: l => l.r.desp_educacao_per_capita, render: l => nulo(l.r.desp_educacao_per_capita) ? "sem dado" : brl(l.r.desp_educacao_per_capita) },
    { rotulo: "Matrículas (rede municipal)", num: true, valor: l => l.r.tcees_alunos, render: l => nulo(l.r.tcees_alunos) ? "sem dado" : nf(l.r.tcees_alunos) },
    { rotulo: "Por matrícula (R$)", num: true, valor: l => l.r.desp_educacao_por_matricula, render: l => nulo(l.r.desp_educacao_por_matricula) ? "sem dado" : brl(l.r.desp_educacao_por_matricula) },
    { rotulo: "% da despesa do ente", num: true, valor: l => l.r.desp_educacao_pct_total, render: l => pct(l.r.desp_educacao_pct_total, 2) },
  ], linhas, "evolucao_" + cod + ".csv", { destacar: l => l.ano === estado.ano }));
  return card;
}

function cardBimestralMunicipio(cod, ano) {
  const bims = [1, 2, 3, 4, 5, 6];
  const card = h("article", { class: "card" }, cabecalho("Execução ao longo de " + ano,
    "Despesa empenhada em Educação acumulada até cada bimestre (RREO Anexo 02). Compara-se com a dotação atualizada do próprio bimestre.",
    { itens: () => bims.map(b => BIM.get(cod + "|" + ano + "|" + b)).filter(Boolean)
      .map(x => ({ indicador: "empenhada_acum", ano, detalhe: String(x.bimestre), observacao: "tipo de RREO: " + x.tipo_rreo, q: x.q, valor: brl(x.empenhada_acum) })) }));
  const linhas = bims.map(b => ({ b, x: BIM.get(cod + "|" + ano + "|" + b) }));
  if (!linhas.some(l => l.x)) { card.append(h("p", {}, h("span", { class: "badge nada" }, "Sem dado"), " Nenhum bimestre publicado em " + ano + ".")); return card; }
  const cs = cores();
  const cv = h("canvas", { role: "img", "aria-label": "Execução bimestral em " + ano + ". Valores na tabela abaixo." });
  card.append(h("div", { class: "grafico" }, temChart() ? cv : avisoSemChart()));
  if (temChart()) {
    const op = opcoesBase(cs, tickMoeda);
    op.plugins.tooltip.callbacks.label = c => " " + c.dataset.label + ": " + brl(c.parsed.y);
    setTimeout(() => desenhar("mun-bim", cv, { type: "line", data: { labels: bims.map(b => b + "º bim"), datasets: [
      { label: "Empenhada acumulada", data: linhas.map(l => l.x && !nulo(l.x.empenhada_acum) ? l.x.empenhada_acum : null),
        borderColor: cs.serie[0], backgroundColor: cs.serie[0], borderWidth: 2, tension: 0, spanGaps: false,
        pointStyle: "circle", pointRadius: 5, pointHoverRadius: 7, pointBorderColor: cs.surface, pointBorderWidth: 2 },
      { label: "Liquidada acumulada", data: linhas.map(l => l.x && !nulo(l.x.liquidada_acum) ? l.x.liquidada_acum : null),
        borderColor: cs.serie[1], backgroundColor: cs.serie[1], borderWidth: 2, tension: 0, spanGaps: false,
        pointStyle: "rect", pointRadius: 5, pointHoverRadius: 7, pointBorderColor: cs.surface, pointBorderWidth: 2 }] },
      options: op, plugins: [plugCrosshair] }), 0);
  }
  card.append(h("div", { class: "legenda" },
    h("span", {}, chaveLinha(cs.serie[0], "circle"), "Empenhada acumulada"),
    h("span", {}, chaveLinha(cs.serie[1], "rect"), "Liquidada acumulada")));
  card.append(blocoTabela("execução bimestral", [
    { rotulo: "Bimestre", valor: l => l.b + "º" },
    { rotulo: "Tipo de RREO", valor: l => l.x ? l.x.tipo_rreo : null },
    { rotulo: "Dotação atualizada (R$)", num: true, valor: l => l.x && l.x.dotacao_atualizada, render: l => l.x && !nulo(l.x.dotacao_atualizada) ? brl(l.x.dotacao_atualizada) : "sem dado" },
    { rotulo: "Empenhada acum. (R$)", num: true, valor: l => l.x && l.x.empenhada_acum, render: l => l.x && !nulo(l.x.empenhada_acum) ? brl(l.x.empenhada_acum) : "sem dado" },
    { rotulo: "Liquidada acum. (R$)", num: true, valor: l => l.x && l.x.liquidada_acum, render: l => l.x && !nulo(l.x.liquidada_acum) ? brl(l.x.liquidada_acum) : "sem dado" },
    { rotulo: "Empenhada ÷ dotação", num: true, valor: l => l.x && l.x.dotacao_atualizada > 0 ? 100 * l.x.empenhada_acum / l.x.dotacao_atualizada : null,
      render: l => l.x && l.x.dotacao_atualizada > 0 ? nf(100 * l.x.empenhada_acum / l.x.dotacao_atualizada, 1) + "%" : "sem dado" },
  ], linhas, "bimestral_" + cod + "_" + ano + ".csv"));
  return card;
}

function cardFundebMDE(cod, ano, r) {
  const nome = ENTES.get(cod).nome, s = SIOPE.get(chaveEA(cod, ano)) || {};
  const item = campo_ => { try { return JSON.parse(s.itens_usados || "{}")[campo_]; } catch (e) { return null; } };
  const card = h("article", { class: "card largo" }, cabecalho("FUNDEB e mínimos legais — " + ano, null,
    { itens: () => [
      { indicador: "fundeb_receita", ano, q: r.q_dca_ic, valor: nulo(r.fundeb_receita) ? null : brl(r.fundeb_receita) },
      { indicador: "fundeb_msc", ano, detalhe: "fundo + complementação", q: r.q_msc, valor: nulo(r.fundeb_msc_total) ? null : brl(r.fundeb_msc_total) },
      { indicador: "siope", ano, detalhe: "fundeb_principal", q: r.q_siope, observacao: item("fundeb_principal"), valor: nulo(r.fundeb_principal) ? null : brl(r.fundeb_principal) },
      { indicador: "fundeb_contribuicao", ano, q: r.q_dca_ic },
      { indicador: "mde_pct", ano, q: r.q_siope, observacao: item("mde_pct"), valor: pct(r.mde_aplicado_pct, 2) },
      { indicador: "fundeb70_pct", ano, q: r.q_siope, observacao: item("fundeb70_pct"), valor: pct(r.fundeb70_pct, 2) }] }));
  const linhas = [
    ["Receita do FUNDEB recebida (DCA)", r.fundeb_receita, brl, "DCA Anexo I-C: transferência do fundo + complementação da União."],
    ["…a mesma receita na MSC", r.fundeb_msc_total, brl, "Natureza de receita do FUNDEB na MSC (códigos achados no I-C)." + (nulo(r.fundeb_msc_total) || nulo(r.fundeb_receita) ? "" : Math.abs(r.fundeb_msc_total - r.fundeb_receita) <= 1 ? " Bate com o DCA." : " Difere do DCA em " + brl(r.fundeb_msc_total - r.fundeb_receita) + ".")],
    ["…e no SIOPE (principal)", r.fundeb_principal, brl, "Anexo 8, itens \"Principal\" (sem rendimentos de aplicação)." + (nulo(r.fundeb_principal) || nulo(r.fundeb_receita) ? "" : Math.abs(r.fundeb_principal - r.fundeb_receita) <= 1 ? " Bate com o DCA." : " Difere do DCA em " + brl(r.fundeb_principal - r.fundeb_receita) + ".")],
    ["…da qual complementação da União", r.fundeb_complementacao_uniao, brl, "VAAF/VAAT/VAAR. Conta separada no I-C; ausente = o ente não recebeu."],
    ["Contribuição ao FUNDEB", r.fundeb_contribuicao, brl, "Dedução de receita (o quanto o ente verteu ao fundo)."],
    ["FUNDEB líquido", r.fundeb_liquido, brl, "Recebida − contribuição. Negativo = o ente verte mais do que recebe."],
    ["Receita do FUNDEB ÷ despesa em Educação", r.fundeb_pct_desp_educacao, v => nf(v, 1) + "%", "Participação pela RECEITA, não a despesa custeada pelo FUNDEB."],
  ];
  card.append(tabela([
    { rotulo: "Indicador", valor: l => l[0] },
    { rotulo: "Valor", num: true, valor: l => l[1], render: l => nulo(l[1]) ? "sem dado" : l[2](l[1]) },
    { rotulo: "O que é", valor: l => l[3] },
  ], linhas, "FUNDEB de " + nome + " em " + ano, { inteira: true }));

  const min = META.minimo_mde_pct, min70 = META.minimo_fundeb_profissionais_pct;
  card.append(h("h3", { style: "margin-top:16px" }, "Mínimos legais apurados pelo SIOPE"));
  const linhaMin = (rotulo, v, minimo, extra) => h("p", {}, rotulo + ": ", nulo(v) ? h("span", { class: "badge nada" }, "sem dado") : h("strong", {}, nf(v, 2) + "% "),
    nulo(v) ? null : (v < minimo ? h("span", { class: "flag-abaixo" }, "✖ abaixo do mínimo de " + nf(minimo, 0) + "%") : h("span", { class: "ok" }, "✔ cumpre o mínimo de " + nf(minimo, 0) + "%")), extra || null);
  card.append(linhaMin("MDE sobre a receita de impostos (art. 212 CF)", r.mde_aplicado_pct, min,
      r.mde_situacao === "informado_manual" ? h("span", { class: "badge manual" }, " Manual · verificado em " + dataBR(r.mde_verificado_em)) : null),
    linhaMin("FUNDEB na remuneração dos profissionais da educação básica", r.fundeb70_pct, min70));
  if (ano === 2023 && r.mde_compensacao_ec119 > 0) {
    card.append(h("div", { class: r.mde_aplicado + 0.005 >= r.mde_exigido ? "callout" : "callout warn" }, h("strong", {}, "EC 119/2022: "),
      "o valor exigido de " + brl(r.mde_exigido) + " inclui " + brl(r.mde_compensacao_ec119) + " de compensação pendente de 2020–2021; o aplicado foi " + brl(r.mde_aplicado) +
      (r.mde_aplicado + 0.005 >= r.mde_exigido ? " — alcançou o exigido." : " — ficou " + brl(r.mde_exigido - r.mde_aplicado) + " abaixo do exigido com a compensação.")));
  }
  if (r.mde_situacao === "siope") card.append(h("p", { class: "nota" }, selo_pdf(), " PDF gerado pelo SIOPE em " + dataBR(s.pdf_gerado_em) + ", publicado no FTP em " + dataBR(s.pdf_publicado_em) + "."));
  if (r.mde_divergente_manual) card.append(h("div", { class: "callout warn" }, "O registro manual de MDE deste ente-ano difere do índice do SIOPE; vale o do SIOPE. Revise dados_manuais.yaml."));
  return card;
}

function cardProgramasDoMunicipio(cod, ehMunicipio) {
  const card = h("article", { class: "card largo" }, h("header", {},
    h("h3", {}, "Programas federais neste município"),
    h("p", { class: "nota" }, "Campos de registro manual, com fonte e data. “Sem dado carregado” significa que ninguém registrou o valor — não que seja zero.")));
  if (!ehMunicipio) { card.append(h("p", { class: "muted" }, "Os programas carregados têm granularidade municipal; o Estado não entra.")); return card; }
  if (!D.programas.length) { card.append(h("p", { class: "muted" }, "Nenhum programa configurado.")); return card; }
  for (const p of D.programas) {
    const linhas = p.campos.map(c => ({ p, c }));
    card.append(h("h3", { style: "margin-top:12px;font-size:.95rem" }, p.nome));
    card.append(tabela([
      { rotulo: "Campo", valor: l => l.c.rotulo, render: l => h("span", {}, h("strong", {}, l.c.rotulo), h("br"),
          h("span", { class: "nota" }, l.c.origem === "api" ? "origem: API" : "origem: registro manual")) },
      { rotulo: "Situação", valor: l => "", render: l => celulaCampo(l.p, l.c, cod) },
    ], linhas, "Programas em " + ENTES.get(cod).nome, { inteira: true }));
  }
  card.append(h("div", { class: "rodape-card" },
    h("button", { type: "button", class: "leve", onclick: () => irPara("programas") }, "Ver o módulo de programas completo →")));
  return card;
}

function renderMunicipio(destino) {
  if (!estado.municipio) estado.municipio = MUNICIPIOS[0].cod_ibge;
  const cod = estado.municipio, ano = estado.ano;
  const ente = ENTES.get(cod), ehMunicipio = ente.esfera === "M";
  const r = LINHA.get(cod + "|" + ano) || {};

  destino.append(h("div", { class: "ficha-topo" },
    h("h2", {}, ente.nome), h("span", { class: "codigo" }, (ehMunicipio ? "Código IBGE " : "UF ") + cod + " · exercício " + ano)));

  if (r.status_dca && r.status_dca !== "ok") {
    destino.append(h("div", { class: "callout warn" }, h("strong", {}, "Sem dado de despesa por função em " + ano + ". "),
      "Situação da DCA: " + r.status_dca + ". Os campos abaixo ficam vazios — nada é estimado."));
  }
  destino.append(fichaKPIs(cod, ano, r, ehMunicipio));
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" },
    cardSubfuncoes(cod, ano, r, ehMunicipio),
    cardMatrizSubfuncoes(cod),
    cardEvolucaoMunicipio(cod),
    cardBimestralMunicipio(cod, ano),
    cardFundebMDE(cod, ano, r),
    cardProgramasDoMunicipio(cod, ehMunicipio))));
}
