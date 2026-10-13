"use strict";
/* ============================================================================
   Visão Conformidade — o que interessa para auditoria: mínimos legais (MDE 25%,
   FUNDEB 70%, com a apuração do TCE-ES ao lado), completude da prestação de
   contas no SICONFI e ao TCE-ES, obras paradas, conciliação entre fontes. E a
   faixa de KPIs do topo, visível em todas as visões.
   Abaixo do mínimo = vermelho COM símbolo e texto (nunca só a cor).
   ========================================================================== */

const MIN_MDE = () => META.minimo_mde_pct;
const MIN_70 = () => META.minimo_fundeb_profissionais_pct;
const kpisDoAno = ano => (META.kpis || {})[String(ano)] || {};
const siopeDe = (cod, ano) => SIOPE.get(chaveEA(cod, ano)) || {};
const itemUsado = (cod, ano, campo) => { try { return JSON.parse(siopeDe(cod, ano).itens_usados || "{}")[campo]; } catch (e) { return null; } };

function marcaMinimo(v, minimo) {
  if (nulo(v)) return h("span", { class: "badge nada" }, "sem dado");
  return v < minimo ? h("span", { class: "flag-abaixo" }, "✖ abaixo de " + nf(minimo, 0) + "%") : h("span", { class: "ok" }, "✔ cumpre");
}

function selo_pdf() {
  const e = (META.extraido_em_por_fonte || {}).SIOPE || {};
  return h("span", { class: "badge aviso", title: "Extraído do PDF que o SIOPE publica no FTP do FNDE: fonte sem SLA." },
    "⚠ extraído de PDF (SIOPE) · coletado em " + dataHoraBR(e.ultima));
}

/* ---------------------------------------------------------- faixa de KPIs */
function renderFaixaKPIs(destino) {
  const ano = estado.ano, k = kpisDoAno(ano), n = MUNICIPIOS.length;
  const box = h("div", { class: "kpis faixa-kpis", role: "region", "aria-label": "Indicadores de conformidade de " + ano });
  // ✖ = abaixo de mínimo legal; ⚑ = sinal a investigar (divergência entre fontes não é, por si, irregularidade).
  const tile = (rot, val, det, alerta, alvo, fonte, icone = "✖") => h("div", { class: "kpi" + (alerta ? " alerta" : "") },
    h("div", { class: "rot" }, rot), h("div", { class: "val" }, alerta ? icone + " " : "", val), h("div", { class: "det" }, det),
    h("div", { class: "acoes-kpi" },
      h("button", { type: "button", class: "leve", onclick: () => { irPara("conformidade"); setTimeout(() => { const el = document.getElementById(alvo); if (el) el.scrollIntoView({ block: "start" }); }, 0); } }, "ver lista →"),
      botaoFonte(rot + " — " + ano, fonte)));
  const cods = MUNICIPIOS.map(e => e.cod_ibge);
  box.append(tile("Municípios abaixo do mínimo de MDE (25%)",
    k.mde_com_dado ? k.mde_abaixo + " de " + k.mde_com_dado : "n/d",
    "art. 212 da CF · índice apurado pelo SIOPE" + (k.mde_com_dado < n ? " · " + (n - k.mde_com_dado) + " sem dado" : "") +
      (k.mde_tcees_com_dado ? " · pelo TCE-ES: " + k.mde_abaixo_tcees + " abaixo; em " + k.mde_cruza_minimo + " as duas apurações discordam sobre o mínimo" : ""),
    k.mde_abaixo > 0 || k.mde_abaixo_tcees > 0, "card-minimos", () => [{ indicador: "mde_pct", ano, detalhe: "os " + n + " municípios", q: qAnual("q_siope", cods, ano) },
      { indicador: "tcees_mde_pct", ano, detalhe: "os " + n + " municípios", q: qAnual("q_tcees_mde", cods, ano) }]));
  box.append(tile("Declaração RREO/RGF/DCA em atraso ou não entregue",
    k.entregas_com_dado ? k.entregas_irregulares + " de " + k.entregas_com_dado : "n/d",
    (k.entregas_atraso_30d ?? "–") + " com atraso > 30 dias · " + (k.entregas_com_nao_entregue ?? "–") + " com relatório não entregue · prazos da LRF",
    k.entregas_irregulares > 0, "card-entregas", () => [{ indicador: "entrega_atraso_dias", ano, detalhe: "extrato de entregas dos " + n + " municípios", q: qAnual("q_extrato", cods, ano) }]));
  const md = k.maior_divergencia;
  box.append(tile("Maior divergência: função 12 × despesa declarada ao SIOPE",
    md ? (md.pct >= 0 ? "+" : "") + nf(md.pct, 1) + "%" : "n/d",
    md ? md.ente + " · " + brlCompacto(md.rs) + " · " + k.divergencias_relevantes + " município(s) acima de " + nf(META.divergencia_relevante_pct, 0) + "%" : "sem dado comparável",
    md && Math.abs(md.pct) > META.divergencia_relevante_pct, "card-conciliacao",
    () => md ? [{ indicador: "divergencia_funcao12_siope", ano, detalhe: md.ente, q: [LINHA.get(md.cod_ibge + "|" + ano).q_dca_ie, LINHA.get(md.cod_ibge + "|" + ano).q_siope] }] : [],
    "⚑"));
  box.append(tile("FUNDEB abaixo de 70% na remuneração dos profissionais",
    k.fundeb70_com_dado ? k.fundeb70_abaixo + " de " + k.fundeb70_com_dado : "n/d",
    "art. 212-A, XI, da CF e Lei 14.113/2020 · índice apurado pelo SIOPE",
    k.fundeb70_abaixo > 0, "card-minimos", () => [{ indicador: "fundeb70_pct", ano, detalhe: "os " + n + " municípios", q: qAnual("q_siope", cods, ano) }]));
  destino.append(box);
}

/* ------------------------------------------------------------------- filtros */
function conformidadeFiltros(destino) {
  const mostrar = h("select", { id: "f-alertas", onchange: e => { estado.alertas = e.target.value === "1"; render(); } },
    h("option", { value: "0" }, "Todos os municípios"), h("option", { value: "1" }, "Só municípios com alerta"));
  mostrar.value = estado.alertas ? "1" : "0";
  destino.append(h("div", { class: "linha" },
    campo("Exercício", seletorAno("f-ano-conf", estado.ano, v => { estado.ano = v; render(); })),
    campo("Mostrar", mostrar)));
}

/* ------------------------------------------------------------ mínimos legais */
function contextoLegal(ano) {
  if (ano === 2020 || ano === 2021) {
    return h("div", { class: "callout warn", role: "note" }, h("strong", {}, "EC 119/2022 (art. 119 do ADCT). "),
      "O descumprimento do art. 212 em 2020 e 2021 não gera responsabilização se o ente complementou a diferença até 2023. " +
      "O percentual abaixo de 25% continua sendo o fato apurado; a compensação aparece no exercício de 2023.");
  }
  if (ano === 2023) {
    return h("div", { class: "callout", role: "note" }, h("strong", {}, "2023 — prazo da compensação da EC 119/2022. "),
      "Para quem tinha diferença pendente de 2020–2021, o valor EXIGIDO pelo SIOPE inclui a compensação; o % aplicado " +
      "continua sobre a receita do ano. Por isso a tabela mostra também se o aplicado alcançou o exigido.");
  }
  return null;
}

function cardMinimos(ano) {
  const cods = MUNICIPIOS.map(e => e.cod_ibge);
  const card = h("article", { class: "card largo", id: "card-minimos" }, cabecalho(
    "Mínimos legais: MDE (25%) e FUNDEB na remuneração (70%) — " + ano,
    "Percentuais apurados pelo próprio SIOPE no RREO Anexo 8 (6º bimestre), conferidos contra os valores da mesma linha do demonstrativo. " +
    "Ao lado, o % de MDE apurado pelo TCE-ES: as duas apurações podem divergir por critério; ⚑ marca quando uma fica abaixo de 25% e a outra não.",
    { itens: () => [{ indicador: "mde_pct", ano, detalhe: "os " + cods.length + " municípios", q: qAnual("q_siope", cods, ano) },
                    { indicador: "tcees_mde_pct", ano, detalhe: "os " + cods.length + " municípios", q: qAnual("q_tcees_mde", cods, ano) },
                    { indicador: "fundeb70_pct", ano, detalhe: "os " + cods.length + " municípios", q: qAnual("q_siope", cods, ano) }] }));
  card.append(h("p", {}, selo_pdf()));
  const ctx = contextoLegal(ano);
  if (ctx) card.append(ctx);

  const linhas = linhasMun(ano).map(r => ({ r, s: siopeDe(r.cod_ibge, ano) }));
  const reguas = h("div", { class: "reguas" });
  reguas.append(h("h4", {}, "% da receita de impostos aplicado em MDE"),
    reguaMinimo({ valores: linhas.map(l => ({ rotulo: l.r.ente, v: l.r.mde_aplicado_pct })), minimo: MIN_MDE(), formatar: v => nf(v, 2) + "%", titulo: "Distribuição do % aplicado em MDE" }),
    h("h4", {}, "% do FUNDEB na remuneração dos profissionais da educação básica"),
    reguaMinimo({ valores: linhas.map(l => ({ rotulo: l.r.ente, v: l.r.fundeb70_pct })), minimo: MIN_70(), formatar: v => nf(v, 2) + "%", titulo: "Distribuição do % do FUNDEB na remuneração", teto: 100 }));
  card.append(reguas);

  const alerta = l => (l.r.mde_aplicado_pct < MIN_MDE()) || (l.r.fundeb70_pct < MIN_70()) || (l.r.tcees_mde_pct < MIN_MDE()) ||
    (ano === 2023 && l.r.mde_compensacao_ec119 > 0 && l.r.mde_aplicado < l.r.mde_exigido);
  const visiveis = linhas.filter(l => !estado.alertas || alerta(l))
    .sort((a, b) => (a.r.mde_aplicado_pct ?? 999) - (b.r.mde_aplicado_pct ?? 999));
  const colunas = [
    { rotulo: "Município", valor: l => l.r.ente, render: l => h("button", { type: "button", class: "link", onclick: () => { estado.municipio = l.r.cod_ibge; irPara("fluxo"); } }, l.r.ente) },
    { rotulo: "% MDE", num: true, valor: l => l.r.mde_aplicado_pct, render: l => nulo(l.r.mde_aplicado_pct) ? "sem dado" : nf(l.r.mde_aplicado_pct, 2) + "%" },
    { rotulo: "MDE × 25%", valor: l => l.r.mde_abaixo_minimo, render: l => marcaMinimo(l.r.mde_aplicado_pct, MIN_MDE()) },
    { rotulo: "% MDE — TCE-ES", num: true, valor: l => l.r.tcees_mde_pct,
      render: l => nulo(l.r.tcees_mde_pct) ? "sem dado" : h("span", {}, nf(l.r.tcees_mde_pct, 2) + "%", l.r.tcees_mde_pct < MIN_MDE() ? h("span", { class: "flag-abaixo" }, " ✖") : null) },
    { rotulo: "TCE-ES − SIOPE (p.p.)", num: true, valor: l => l.r.div_mde_tcees_siope_pp,
      render: l => { const v = l.r.div_mde_tcees_siope_pp; if (nulo(v)) return "—"; const t = (v > 0 ? "+" : "") + nf(v, 2);
        return l.r.mde_cruza_minimo ? h("strong", { title: "Uma apuração abaixo de 25% e a outra não" }, "⚑ " + t) : t; } },
    { rotulo: "Aplicado em MDE (R$)", num: true, valor: l => l.r.mde_aplicado, fmt: brl },
    { rotulo: "Exigido (R$)", num: true, valor: l => l.r.mde_exigido, fmt: brl },
  ];
  if (ano === 2023) colunas.push(
    { rotulo: "…do qual compensação EC 119 (R$)", num: true, valor: l => l.r.mde_compensacao_ec119, render: l => nulo(l.r.mde_compensacao_ec119) ? "—" : brl(l.r.mde_compensacao_ec119) },
    { rotulo: "Aplicado ≥ exigido?", valor: l => l.r.mde_aplicado >= l.r.mde_exigido,
      render: l => nulo(l.r.mde_aplicado) ? "sem dado" : l.r.mde_aplicado + 0.005 >= l.r.mde_exigido ? h("span", { class: "ok" }, "✔ sim") : h("span", { class: "flag-abaixo" }, "✖ não (falta " + brlCompacto(l.r.mde_exigido - l.r.mde_aplicado) + ")") });
  colunas.push(
    { rotulo: "% FUNDEB remuneração", num: true, valor: l => l.r.fundeb70_pct, render: l => nulo(l.r.fundeb70_pct) ? "sem dado" : nf(l.r.fundeb70_pct, 2) + "%" },
    { rotulo: "FUNDEB × 70%", valor: l => l.r.fundeb70_abaixo_minimo, render: l => marcaMinimo(l.r.fundeb70_pct, MIN_70()) },
    { rotulo: "Fonte", valor: () => "", render: l => botaoFonte(l.r.ente + " — Anexo 8 de " + ano, () => [
      { indicador: "mde_pct", ano, q: l.r.q_siope, observacao: itemUsado(l.r.cod_ibge, ano, "mde_pct"), valor: pct(l.r.mde_aplicado_pct, 2) },
      { indicador: "fundeb70_pct", ano, q: l.r.q_siope, observacao: itemUsado(l.r.cod_ibge, ano, "fundeb70_pct"), valor: pct(l.r.fundeb70_pct, 2) },
      { indicador: "siope", ano, detalhe: "valor exigido e aplicado (limite do art. 212)", q: l.r.q_siope, observacao: itemUsado(l.r.cod_ibge, ano, "mde_exigido") },
      { indicador: "tcees_mde_pct", ano, q: l.r.q_tcees_mde, valor: pct(l.r.tcees_mde_pct, 2) },
      { indicador: "div_mde_tcees_siope_pp", ano, q: [l.r.q_tcees_mde, l.r.q_siope], valor: nulo(l.r.div_mde_tcees_siope_pp) ? null : nf(l.r.div_mde_tcees_siope_pp, 2) + " p.p." }]) },
  );
  card.append(h("p", { class: "nota" }, (estado.alertas ? visiveis.length + " município(s) com alerta" : linhas.length + " municípios") +
    ", do menor para o maior % de MDE. Clique no nome para ver de onde vem e onde é aplicado o recurso."));
  card.append(tabela(colunas, visiveis, "Mínimos legais por município, " + ano, { classeLinha: l => alerta(l) ? "alerta" : null }),
    botaoCSV("minimos_legais_" + ano + ".csv", colunas.filter(c => c.rotulo !== "Fonte"), visiveis));
  return card;
}

/* -------------------------------------------------------------- entregas */
function cardEntregas(ano) {
  const cods = MUNICIPIOS.map(e => e.cod_ibge);
  const card = h("article", { class: "card largo", id: "card-entregas" }, cabecalho(
    "Completude da prestação de contas no SICONFI — RREO, RGF e DCA de " + ano,
    "Data de homologação do extrato de entregas × prazo legal. A API não traz prazo: ele é calculado pela LRF, e a data (UTC) é convertida para o horário de Brasília.",
    { itens: () => [{ indicador: "entrega_atraso_dias", ano, detalhe: "extrato de entregas dos " + cods.length + " municípios", q: qAnual("q_extrato", cods, ano) }] }));
  const k = kpisDoAno(ano);
  card.append(h("p", {}, h("strong", {}, (k.entregas_irregulares ?? "–") + " de " + (k.entregas_com_dado ?? "–")),
    " municípios com ao menos uma entrega fora do prazo; ", h("strong", {}, String(k.entregas_atraso_30d ?? "–")), " com atraso acima de 30 dias; ",
    h("strong", {}, String(k.entregas_com_nao_entregue ?? "–")), " com relatório não entregue."));
  card.append(h("ul", { class: "lista nota" }, Object.entries(META.fundamento_entregas || {}).map(([r, f]) => h("li", {}, h("strong", {}, r + ": "), f)),
    h("li", {}, "Relatório retificado mostra a data da retificação (não a da entrega original): por isso não é contado como atraso.")));

  const linhas = MUNICIPIOS.map(e => {
    const ob = ENTREGAS.get(chaveEA(e.cod_ibge, ano)) || [];
    const irr = ob.filter(o => o.situacao === "entregue_com_atraso" || o.situacao === "nao_entregue");
    return { e, r: LINHA.get(e.cod_ibge + "|" + ano) || {}, ob, irr,
      atraso: irr.filter(o => o.situacao === "entregue_com_atraso").length, nao: irr.filter(o => o.situacao === "nao_entregue").length,
      ret: ob.filter(o => o.situacao === "retificado").length,
      maior: Math.max(0, ...irr.map(o => o.dias_atraso || 0)) };
  }).filter(l => !estado.alertas || l.irr.length)
    .sort((a, b) => b.nao - a.nao || b.maior - a.maior || b.atraso - a.atraso);
  const nomePer = o => o.relatorio === "RREO" ? o.periodo + "º bim." : o.relatorio === "DCA" ? "anual" : o.periodo + "º " + (o.periodicidade === "S" ? "sem." : "quadr.");
  const colunas = [
    { rotulo: "Município", valor: l => l.e.nome },
    { rotulo: "Obrigações", num: true, valor: l => l.ob.length },
    { rotulo: "Com atraso", num: true, valor: l => l.atraso },
    { rotulo: "Não entregues", num: true, valor: l => l.nao },
    { rotulo: "Retificados", num: true, valor: l => l.ret },
    { rotulo: "Maior atraso (dias)", num: true, valor: l => l.maior || null, render: l => l.maior ? nf(l.maior) : "—" },
    { rotulo: "O que atrasou", valor: l => l.irr.map(o => o.poder + " " + o.relatorio + " " + nomePer(o)).join("; "),
      render: l => l.irr.length ? h("details", {}, h("summary", {}, l.irr.length + " relatório(s)"),
        h("ul", { class: "lista" }, l.irr.map(o => h("li", {}, h("strong", {}, o.poder + " · " + o.relatorio + " " + nomePer(o)), ": prazo " + dataBR(o.prazo) + ", " +
          (o.situacao === "nao_entregue" ? "não entregue (" + nf(o.dias_atraso) + " dias desde o prazo)" : "entregue " + dataBR(o.data_local) + " (" + nf(o.dias_atraso) + " dias)"))))) : "—" },
    { rotulo: "Fonte", valor: () => "", render: l => botaoFonte(l.e.nome + " — extrato de entregas de " + ano,
      () => [{ indicador: "entrega_atraso_dias", ano, detalhe: l.e.nome, q: l.r.q_extrato }]) },
  ];
  card.append(tabela(colunas, linhas, "Entregas por município, " + ano, { classeLinha: l => l.irr.length ? (l.nao || l.maior > 30 ? "alerta" : "atencao") : null }),
    botaoCSV("entregas_" + ano + ".csv", colunas.filter(c => c.rotulo !== "Fonte"), linhas));
  return card;
}

/* ------------------------------------------------------------- conciliação */
function cardConciliacao(ano) {
  const lim = META.divergencia_relevante_pct;
  const card = h("article", { class: "card largo", id: "card-conciliacao" }, cabecalho(
    "Conciliação: despesa da função 12 (SICONFI) × despesa com educação declarada ao SIOPE — " + ano,
    "A mesma despesa, declarada duas vezes pelo município: ao Tesouro (DCA Anexo I-E, função 12, empenhada) e ao FNDE (Anexo 8, \"total geral das despesas com educação\", empenhada). " +
    "Divergência grande é sinal a investigar — não erro do pipeline. A despesa \"para fins de limite\" do MDE vai ao lado só como contexto: ela soma a contribuição ao FUNDEB e desconta deduções, então não se compara direto.",
    { itens: () => { const c = MUNICIPIOS.map(e => e.cod_ibge); return [{ indicador: "divergencia_funcao12_siope", ano, detalhe: "os " + c.length + " municípios", q: qAnual("q_dca_ie", c, ano) + ";" + qAnual("q_siope", c, ano) }]; } }));
  const linhas = linhasMun(ano).filter(r => !nulo(r.divergencia_funcao12_siope_pct))
    .filter(r => !estado.alertas || Math.abs(r.divergencia_funcao12_siope_pct) > lim)
    .sort((a, b) => Math.abs(b.divergencia_funcao12_siope_pct) - Math.abs(a.divergencia_funcao12_siope_pct));
  const semDado = linhasMun(ano).filter(r => nulo(r.divergencia_funcao12_siope_pct));
  const colunas = [
    { rotulo: "Município", valor: r => r.ente },
    { rotulo: "Função 12 — SICONFI (R$)", num: true, valor: r => r.desp_educacao_empenhada, fmt: brl },
    { rotulo: "Educação — SIOPE (R$)", num: true, valor: r => r.despesa_total_educacao, fmt: brl },
    { rotulo: "Diferença (R$)", num: true, valor: r => r.divergencia_funcao12_siope_rs, fmt: brl },
    { rotulo: "Diferença (%)", num: true, valor: r => r.divergencia_funcao12_siope_pct,
      render: r => { const v = r.divergencia_funcao12_siope_pct; const t = (v > 0 ? "+" : "") + nf(v, 2) + "%"; return Math.abs(v) > lim ? h("strong", {}, "⚑ " + t) : t; } },
    { rotulo: "MDE para fins de limite — SIOPE (R$)", num: true, valor: r => r.despesa_mde_limite, fmt: brl },
    { rotulo: "Fonte", valor: () => "", render: r => botaoFonte(r.ente + " — conciliação de " + ano, () => [
      { indicador: "desp_educacao_empenhada", ano, q: r.q_dca_ie, valor: brl(r.desp_educacao_empenhada) },
      { indicador: "siope", ano, detalhe: "despesa_total_educacao", q: r.q_siope, observacao: itemUsado(r.cod_ibge, ano, "despesa_total_educacao"), valor: brl(r.despesa_total_educacao) },
      { indicador: "divergencia_funcao12_siope", ano, q: [r.q_dca_ie, r.q_siope], valor: pct(r.divergencia_funcao12_siope_pct, 2) }]) },
  ];
  const acima = linhasMun(ano).filter(r => Math.abs(r.divergencia_funcao12_siope_pct) > lim).length;
  card.append(h("p", {}, h("strong", {}, String(acima)), " município(s) com divergência acima de " + nf(lim, 0) + "% (⚑). " +
    "Positiva: a função 12 do SICONFI é maior que o declarado ao SIOPE; negativa: menor." +
    (semDado.length ? " Sem dado comparável: " + semDado.map(r => r.ente).join(", ") + "." : "")));
  card.append(tabela(colunas, linhas, "Conciliação função 12 × SIOPE, " + ano, { classeLinha: r => Math.abs(r.divergencia_funcao12_siope_pct) > lim ? "atencao" : null }),
    botaoCSV("conciliacao_" + ano + ".csv", colunas.filter(c => c.rotulo !== "Fonte"), linhas));
  return card;
}

/* ------------------------------------------------------ conferências gerais */
function cardConferencias() {
  const card = h("article", { class: "card largo", id: "card-conferencias" }, cabecalho(
    "Conferências entre fontes e do próprio pipeline (todos os exercícios)",
    "Uma fonte contra a outra, ao centavo (tolerância de R$ 1,00). O que não bate é listado — é informação para a auditoria, não defeito escondido."));
  const cc = META.conferencias_cruzadas || {};
  card.append(h("ul", { class: "lista" }, Object.values(cc).map(c => h("li", {}, h("strong", {}, c.descricao + ": "),
    c.comparaveis ? c.batem + " de " + c.comparaveis + " ente-anos batem" : "sem par comparável",
    c.incompletos ? " · " + c.incompletos + " ente-ano(s) fora da conferência: o arquivo do TCE-ES não traz todos os meses" : "",
    c.maiores && c.maiores.length ? h("details", {}, h("summary", {}, "maiores diferenças"),
      h("ul", { class: "lista" }, c.maiores.map(m => h("li", {}, m.ente + " (" + m.ano + "): " +
        (c.unidade ? nf(m.dif) + " " + c.unidade : brl(m.dif)))))) : null))));
  const v = META.validacao || {};
  card.append(h("h4", {}, "Validação do dataset consolidado"),
    h("ul", { class: "lista" },
      h("li", {}, nf(v.registros || 0) + " registros, cada um com endpoint, parâmetros e instante da coleta; sem proveniência: " + (v.sem_proveniencia ?? "–") + "."),
      h("li", {}, "Código IBGE com 7 dígitos em todos os municípios: " + (v.ibge_7_digitos ? "sim" : "NÃO") + "."),
      h("li", {}, "Valores negativos onde o indicador não admite: " + (v.n_negativos_inesperados || 0) +
        ((v.negativos_inesperados || []).length ? " — " + v.negativos_inesperados.map(n => n.ente + " " + n.ano + ", " + (n.detalhe || n.indicador) + ": " + brl(n.valor)).join("; ") + " (dado da fonte, a revisar)" : "") + ".")));
  const st = (META.fontes_status || {}).Censo || {};
  const ROT_VINC = { pdde: "Unidades executoras do PDDE", conselho: "Conselhos escolares (credores do município)", obra: "Prédios de obras (bens vinculadores)" };
  if (st.vinculos) card.append(h("h4", {}, "Vínculo recebedor → escola do Censo (por nome)"),
    h("ul", { class: "lista" }, Object.entries(st.vinculos).filter(([, v]) => v.total).map(([f, v]) =>
      h("li", {}, ROT_VINC[f] + ": " + v.casados + " de " + v.total + " identificados (" + nf(100 * v.casados / v.total, 0) +
        "%); o restante fica sem vínculo, com o nome original."))));
  const avisosTce = (D.avisos || []).filter(a => a.fonte === "TCE-ES");
  if (avisosTce.length) card.append(h("h4", {}, "Avisos do TCE-ES (" + avisosTce.length + ")"),
    h("details", {}, h("summary", {}, "ver avisos — arquivo incompleto, recurso que não baixou"),
      h("ul", { class: "lista" }, avisosTce.map(a => h("li", {}, a.aviso)))));
  const avisos = (D.avisos || []).filter(a => a.fonte === "SIOPE");
  if (avisos.length) card.append(h("h4", {}, "Conferência interna do PDF do SIOPE que não fechou"),
    h("ul", { class: "lista" }, avisos.map(a => h("li", {}, (ENTES.get(a.cod_ibge) || {}).nome + " (" + a.ano + "): " + a.aviso))));
  return card;
}

function renderConformidade(destino) {
  const ano = estado.ano;
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" },
    cardMinimos(ano), cardEntregas(ano), cardRemessasTcees(), cardObrasParadas(), cardConciliacao(ano), cardConferencias())));
}
