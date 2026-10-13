"use strict";
/* ============================================================================
   Conformidade — a triagem dos 78 municípios. Mínimos legais (MDE 25%, FUNDEB
   70%) pelas duas apurações, prazos de prestação de contas ao Tesouro e ao
   TCE-ES, obras paradas e conciliação entre fontes.

   Decisões da auditoria que moldam esta visão:
   · a faixa de KPIs existe SÓ aqui (D4);
   · as duas apurações do MDE (SIOPE e TCE-ES) aparecem lado a lado, com o mesmo
     peso — nenhuma é "a verdadeira" (D6);
   · vermelho só para regra legal descumprida; atraso, divergência e obra parada
     são "sinal a verificar", em âmbar;
   · toda linha colorida diz o motivo em texto, na segunda coluna — antes o motivo
     ficava na 4ª coluna, fora da tela no celular.
   ========================================================================== */

const kpisDoAno = ano => (META.kpis || {})[String(ano)] || {};
const FILTROS_CONFORMIDADE = { todos: "Todos os municípios", alerta: "Com descumprimento ou sinal", descumpre: "Só com descumprimento" };
const passaFiltro = estadoLinha => estado.filtro === "todos" || (estado.filtro === "descumpre" ? estadoLinha === "descumpre" : estadoLinha === "descumpre" || estadoLinha === "sinal");

/** Janela de meses que o TCE-ES publica para as remessas mensais. */
function janelaRemessas() {
  const vencidas = PCM_LINHAS.filter(r => r.situacao !== "prazo_aberto" && r.situacao !== "ug_sem_remessa");
  if (!vencidas.length) return null;
  const per = vencidas.map(r => r.ano * 100 + r.mes), mesAno = v => String(v % 100).padStart(2, "0") + "/" + Math.floor(v / 100);
  return { vencidas, ini: mesAno(Math.min(...per)), fim: mesAno(Math.max(...per)), anoFim: Math.floor(Math.max(...per) / 100) };
}

/* -------------------------------------------------------------------- KPIs */
function kpiDuplo(rot, partes, det, acoes) {
  return h("div", { class: "kpi" }, h("div", { class: "rot" }, rot),
    h("div", { class: "linha-val" }, partes.map(p => h("span", {}, chipEstado(p.estado, p.texto)))),
    det ? h("div", { class: "det" }, det) : null, h("div", { class: "acoes-kpi" }, acoes));
}
function acoesKpi(alvo, tituloFonte, itens) {
  return [h("button", { type: "button", class: "leve", onclick: () => { const el = document.getElementById(alvo); if (el) { el.scrollIntoView({ block: "start" }); el.focus({ preventScroll: true }); } } }, "ver lista ↓"),
    botaoFonte(tituloFonte, itens)];
}
function faixaKPIs() {
  const ano = estado.ano, k = kpisDoAno(ano), n = MUNICIPIOS.length, cods = MUNICIPIOS.map(e => e.cod_ibge), ko = META.kpis_obras || {};
  const box = h("div", { class: "kpis seis", role: "region", "aria-label": "Resumo da conformidade em " + ano });
  const est = v => nulo(v) ? "semdado" : v > 0 ? "descumpre" : "cumpre";
  box.append(kpiDuplo("MDE — mínimo de 25% da receita de impostos (" + ano + ")", [
      { estado: k.mde_com_dado ? est(k.mde_abaixo) : "semdado", texto: "SIOPE: " + (k.mde_com_dado ? k.mde_abaixo + " abaixo" : "sem dado") },
      { estado: k.mde_tcees_com_dado ? est(k.mde_abaixo_tcees) : "semdado", texto: "TCE-ES: " + (k.mde_tcees_com_dado ? k.mde_abaixo_tcees + " abaixo" : "sem dado") }],
    "de " + n + " municípios · as duas apurações discordam sobre o mínimo em " + (k.mde_cruza_minimo ?? 0),
    acoesKpi("card-minimos", "MDE — " + ano, () => [{ indicador: "mde_pct", ano, detalhe: "os " + n + " municípios", q: qAnual("q_siope", cods, ano) },
      { indicador: "tcees_mde_pct", ano, detalhe: "os " + n + " municípios", q: qAnual("q_tcees_mde", cods, ano) }])));
  box.append(kpiDuplo("FUNDEB — 70% na remuneração dos profissionais (" + ano + ")", [
      { estado: k.fundeb70_com_dado ? est(k.fundeb70_abaixo) : "semdado", texto: k.fundeb70_com_dado ? k.fundeb70_abaixo + " abaixo" : "sem dado" }],
    "de " + (k.fundeb70_com_dado || 0) + " municípios com dado · apuração do SIOPE",
    acoesKpi("card-minimos", "FUNDEB 70% — " + ano, () => [{ indicador: "fundeb70_pct", ano, detalhe: "os " + n + " municípios", q: qAnual("q_siope", cods, ano) }])));
  const partesEntregas = [{ estado: k.entregas_atraso_30d > 0 ? "sinal" : "cumpre", texto: (k.entregas_atraso_30d ?? "–") + " com atraso > 30 dias" }];
  if (k.entregas_com_nao_entregue > 0) partesEntregas.unshift({ estado: "descumpre", texto: k.entregas_com_nao_entregue + " com relatório não entregue" });
  box.append(kpiDuplo("Relatórios fiscais ao Tesouro — RREO, RGF e DCA (" + ano + ")", partesEntregas,
    (k.entregas_irregulares ?? "–") + " de " + (k.entregas_com_dado ?? n) + " com algum atraso · " + (k.entregas_com_nao_entregue ?? 0) + " com relatório não entregue",
    acoesKpi("card-entregas", "Entregas — " + ano, () => [{ indicador: "entrega_atraso_dias", ano, detalhe: "extrato de entregas dos " + n + " municípios", q: qAnual("q_extrato", cods, ano) }])));
  // Mesma regra da tabela: prazo vencido e remessa ainda pendente é descumprimento;
  // remessa enviada depois do prazo é atraso (sinal).
  const jan = janelaRemessas();
  let munPend = 0, munAtr = 0;
  if (jan) for (const rs of agrupar(jan.vencidas, r => r.cod_ibge).values()) {
    if (rs.some(r => r.situacao === "nao_homologada")) munPend++; else if (rs.some(r => r.situacao === "com_atraso")) munAtr++;
  }
  box.append(kpiDuplo("Prestação de contas mensal ao TCE-ES", jan ? [
      { estado: munPend ? "descumpre" : "cumpre", texto: munPend + " com remessa pendente" },
      { estado: munAtr ? "sinal" : "cumpre", texto: munAtr + " só com atraso" }] : [{ estado: "semdado", texto: "sem dado" }],
    jan ? "municípios · janela publicada pelo Tribunal: " + jan.ini + " a " + jan.fim + " (não é o exercício)" : "recurso do TCE-ES não coletado",
    acoesKpi("card-remessas-tcees", "Remessas ao TCE-ES", () => [{ indicador: "remessa_tcees_atraso_dias", ano: jan ? jan.anoFim : ano, detalhe: "todas as UGs dos municípios",
      q: [...new Set(PCM_LINHAS.map(r => r.q).filter(Boolean))].join(";") }])));
  box.append(kpiDuplo("Obras da Educação paradas (situação atual)", [
      { estado: ko.paralisadas ? "sinal" : "cumpre", texto: nf(ko.paralisadas || 0) + " contratos · " + brlCompacto(ko.paralisadas_valor || 0) }],
    nf(ko.presumidas || 0) + " com paralisação presumida pelo TCE-ES e " + nf(ko.declaradas || 0) + " declaradas paralisadas · em " + (ko.paralisadas_municipios || 0) + " municípios",
    acoesKpi("card-obras-paradas", "Obras da Educação", () => [{ indicador: "obra_educacao", ano: META.ano_mais_recente, detalhe: "todos os contratos da Educação",
      q: (([...OBRAS_EDU.values()].flat())[0] || {}).q }])));
  const md = k.maior_divergencia;
  box.append(kpiDuplo("Despesa em Educação declarada em duas fontes (" + ano + ")", [
      { estado: k.divergencias_relevantes > 0 ? "sinal" : "cumpre", texto: (k.divergencias_relevantes ?? 0) + " com divergência > " + nf(META.divergencia_relevante_pct, 0) + "%" }],
    md ? "maior: " + md.ente + ", " + (md.pct >= 0 ? "+" : "−") + nf(Math.abs(md.pct), 1) + "% (" + brlCompacto(md.rs) + ") · SICONFI × SIOPE" : "sem dado comparável",
    acoesKpi("card-conciliacao", "Conciliação — " + ano, () => md ? [{ indicador: "divergencia_funcao12_siope", ano, detalhe: md.ente,
      q: [(LINHA.get(md.cod_ibge + "|" + ano) || {}).q_dca_ie, (LINHA.get(md.cod_ibge + "|" + ano) || {}).q_siope] }] : [])));
  return box;
}

/* ------------------------------------------------------------------- filtros */
function conformidadeFiltros(destino) {
  const mostrar = h("select", { id: "f-filtro", onchange: e => ajustar({ filtro: e.target.value }) },
    Object.entries(FILTROS_CONFORMIDADE).map(([v, t]) => h("option", { value: v }, t)));
  mostrar.value = estado.filtro;
  destino.append(campo("Exercício", seletorAno("f-ano", estado.ano, v => ajustar({ ano: v }))), campo("Mostrar", mostrar));
}
const conformidadeRecorte = () => ["exercício ", h("strong", {}, String(estado.ano)), " · ", h("strong", {}, FILTROS_CONFORMIDADE[estado.filtro].toLowerCase())];

/* ------------------------------------------------------------ mínimos legais */
function contextoLegal(ano) {
  if (ano === 2020 || ano === 2021) return h("div", { class: "callout info", role: "note" }, h("strong", {}, "EC 119/2022. "),
    comTermos("O descumprimento do mínimo de MDE em 2020 e 2021 não gera responsabilização se o ente complementou a diferença até 2023. O percentual abaixo de 25% continua sendo o fato apurado; a compensação aparece no exercício de 2023."));
  if (ano === 2023) return h("div", { class: "callout info", role: "note" }, h("strong", {}, "2023 — prazo da compensação da EC 119/2022. "),
    "Para quem tinha diferença pendente de 2020–2021, o valor exigido pelo SIOPE inclui a compensação. Por isso a tabela mostra também se o aplicado alcançou o exigido.");
  return null;
}
/** Estado e motivo de um município nos mínimos legais (as duas apurações com o mesmo peso). */
function situacaoMinimos(r, ano) {
  const motivos = [], estados = [];
  const siope = r.mde_aplicado_pct, tce = r.tcees_mde_pct, f70 = r.fundeb70_pct;
  const baixoS = !nulo(siope) && siope < MIN_MDE(), baixoT = !nulo(tce) && tce < MIN_MDE();
  // Quando só uma apuração fica abaixo, o motivo já mostra o valor da outra: a
  // discordância entre as duas fica visível sem uma frase a mais.
  if (baixoS && baixoT) { estados.push("descumpre"); motivos.push("MDE abaixo de 25% pelo SIOPE (" + nf(siope, 2) + "%) e pelo TCE-ES (" + nf(tce, 2) + "%)"); }
  else if (baixoT) { estados.push("descumpre"); motivos.push("MDE abaixo de 25% pelo TCE-ES (" + nf(tce, 2) + "%)" + (nulo(siope) ? "" : "; pelo SIOPE, " + nf(siope, 2) + "%")); }
  else if (baixoS) { estados.push("descumpre"); motivos.push("MDE abaixo de 25% pelo SIOPE (" + nf(siope, 2) + "%)" + (nulo(tce) ? "" : "; pelo TCE-ES, " + nf(tce, 2) + "%")); }
  else if (r.mde_cruza_minimo) { estados.push("sinal"); motivos.push("as duas apurações discordam sobre o mínimo"); }
  if (!nulo(f70) && f70 < MIN_70()) { estados.push("descumpre"); motivos.push("FUNDEB abaixo de 70% na remuneração (" + nf(f70, 2) + "%)"); }
  if (ano === 2023 && r.mde_compensacao_ec119 > 0 && r.mde_aplicado + 0.005 < r.mde_exigido) {
    estados.push("descumpre"); motivos.push("aplicado abaixo do exigido com a compensação da EC 119 (faltam " + brlCompacto(r.mde_exigido - r.mde_aplicado) + ")");
  }
  const semNada = nulo(siope) && nulo(tce) && nulo(f70);
  return { estado: semNada ? "semdado" : estados.length ? piorEstado(estados) : "cumpre", motivo: motivos.join("; ") };
}
const celulaPct = (v, minimo) => nulo(v) ? semDado() : h("span", {}, nf(v, 2) + "%", v < minimo ? h("span", { class: "sr-only" }, " (abaixo do mínimo)") : null);

function cardMinimos(ano) {
  const cods = MUNICIPIOS.map(e => e.cod_ibge);
  const card = h("article", { class: "card largo", id: "card-minimos", tabindex: "-1" }, cabecalho("Mínimos legais — MDE (25%) e FUNDEB (70%), " + ano, {
    simples: "A Constituição obriga cada município a aplicar pelo menos 25% da receita de impostos na educação (MDE) e 70% do FUNDEB no pagamento dos profissionais. O MDE tem duas apurações — a declarada pelo município ao SIOPE e a feita pelo TCE-ES — que podem divergir por critério; o painel mostra as duas com o mesmo peso.",
    nota: "Percentuais do SIOPE lidos do Anexo 8 do RREO (6º bimestre), conferidos contra os valores da mesma linha do demonstrativo; percentual do TCE-ES da apuração do Tribunal sobre as remessas do CidadES. A tabela começa pela menor das duas apurações.",
    limitacao: "MDE em três apurações",
    fonte: { itens: () => [{ indicador: "mde_pct", ano, detalhe: "os " + cods.length + " municípios", q: qAnual("q_siope", cods, ano) },
      { indicador: "tcees_mde_pct", ano, detalhe: "os " + cods.length + " municípios", q: qAnual("q_tcees_mde", cods, ano) },
      { indicador: "fundeb70_pct", ano, detalhe: "os " + cods.length + " municípios", q: qAnual("q_siope", cods, ano) }] } }));
  card.append(h("span", { class: "ressalva" }, "Ressalva: o índice do SIOPE é extraído de PDF · coletado em " + dataHoraBR(((META.extraido_em_por_fonte || {}).SIOPE || {}).ultima)));
  const ctx = contextoLegal(ano);
  if (ctx) card.append(ctx);
  const linhas = linhasMun(ano).map(r => ({ r, ...situacaoMinimos(r, ano) }));
  card.append(h("div", { class: "reguas" },
    h("h4", {}, "% da receita de impostos aplicado em MDE — apuração do SIOPE"),
    redesenhavel(() => reguaMinimo({ valores: linhas.map(l => ({ rotulo: l.r.ente, v: l.r.mde_aplicado_pct })), minimo: MIN_MDE(), formatar: v => nf(v, 2) + "%", titulo: "Distribuição do % aplicado em MDE pela apuração do SIOPE" })),
    h("h4", {}, "% da receita de impostos aplicado em MDE — apuração do TCE-ES"),
    redesenhavel(() => reguaMinimo({ valores: linhas.map(l => ({ rotulo: l.r.ente, v: l.r.tcees_mde_pct })), minimo: MIN_MDE(), formatar: v => nf(v, 2) + "%", titulo: "Distribuição do % aplicado em MDE pela apuração do TCE-ES" })),
    h("h4", {}, "% do FUNDEB na remuneração dos profissionais da educação básica"),
    redesenhavel(() => reguaMinimo({ valores: linhas.map(l => ({ rotulo: l.r.ente, v: l.r.fundeb70_pct })), minimo: MIN_70(), formatar: v => nf(v, 2) + "%", titulo: "Distribuição do % do FUNDEB na remuneração", teto: 100 }))));
  const visiveis = linhas.filter(l => passaFiltro(l.estado));
  const menor = l => Math.min(...[l.r.mde_aplicado_pct, l.r.tcees_mde_pct].filter(v => !nulo(v)), 999);
  const colunas = [
    { rotulo: "Município", valor: l => l.r.ente, classe: "col-nome", render: l => linkMunicipio(l.r.cod_ibge, "conformidade", l.r.ente) },
    { rotulo: "Situação", valor: l => ESTADOS[l.estado].rotulo, ordem: l => ORDEM_ESTADO[l.estado], render: l => chipEstado(l.estado) },
    { rotulo: "Motivo", valor: l => l.motivo, classe: "motivo", render: l => l.motivo || h("span", { class: "muted" }, "—") },
    { rotulo: "% MDE — SIOPE", num: true, valor: l => l.r.mde_aplicado_pct, render: l => celulaPct(l.r.mde_aplicado_pct, MIN_MDE()) },
    { rotulo: "% MDE — TCE-ES", num: true, valor: l => l.r.tcees_mde_pct, render: l => celulaPct(l.r.tcees_mde_pct, MIN_MDE()) },
    { rotulo: "TCE-ES − SIOPE (p.p.)", num: true, valor: l => l.r.div_mde_tcees_siope_pp, fmt: v => (v > 0 ? "+" : v < 0 ? "−" : "") + nf(Math.abs(v), 2) },
    { rotulo: "% FUNDEB na remuneração", num: true, valor: l => l.r.fundeb70_pct, render: l => celulaPct(l.r.fundeb70_pct, MIN_70()) },
    { rotulo: "Aplicado em MDE (R$)", num: true, valor: l => l.r.mde_aplicado, fmt: brl },
    { rotulo: "Exigido (R$)", num: true, valor: l => l.r.mde_exigido, fmt: brl },
  ];
  if (ano === 2023) colunas.push({ rotulo: "…do qual compensação EC 119 (R$)", num: true, valor: l => l.r.mde_compensacao_ec119, fmt: brl });
  colunas.push(colunaFonte(l => l.r.ente + " — mínimos legais de " + ano, l => [
    { indicador: "mde_pct", ano, q: l.r.q_siope, observacao: itemUsado(l.r.cod_ibge, ano, "mde_pct"), valor: pct(l.r.mde_aplicado_pct, 2) },
    { indicador: "tcees_mde_pct", ano, q: l.r.q_tcees_mde, valor: pct(l.r.tcees_mde_pct, 2) },
    { indicador: "fundeb70_pct", ano, q: l.r.q_siope, observacao: itemUsado(l.r.cod_ibge, ano, "fundeb70_pct"), valor: pct(l.r.fundeb70_pct, 2) },
    { indicador: "siope", ano, detalhe: "valor exigido e aplicado (limite do art. 212)", q: l.r.q_siope, observacao: itemUsado(l.r.cod_ibge, ano, "mde_exigido") },
    { indicador: "div_mde_tcees_siope_pp", ano, q: [l.r.q_tcees_mde, l.r.q_siope], valor: nulo(l.r.div_mde_tcees_siope_pp) ? null : nf(l.r.div_mde_tcees_siope_pp, 2) + " p.p." }]));
  card.append(tabela(colunas, visiveis.sort((a, b) => menor(a) - menor(b)), "Mínimos legais por município, " + ano,
    { classeLinha: l => l.estado === "descumpre" ? "l-descumpre" : l.estado === "sinal" ? "l-sinal" : null,
      busca: "Buscar município…", csv: "minimos_legais_" + ano + ".csv", vazio: "Nenhum município com descumprimento ou sinal neste exercício." }));
  return card;
}

/* -------------------------------------------------------------- entregas */
function cardEntregas(ano) {
  const cods = MUNICIPIOS.map(e => e.cod_ibge), k = kpisDoAno(ano);
  const card = h("article", { class: "card largo", id: "card-entregas", tabindex: "-1" }, cabecalho("Relatórios fiscais ao Tesouro — RREO, RGF e DCA de " + ano, {
    simples: "A Lei de Responsabilidade Fiscal fixa prazos para o município publicar seus relatórios fiscais. Aqui, quem entregou fora do prazo e quem ainda não entregou.",
    nota: "Data de homologação do extrato de entregas do SICONFI × prazo legal. A API não traz o prazo: ele é calculado pela LRF, e a data (UTC) é convertida para o horário de Brasília. Relatório retificado mostra a data da retificação, e por isso não é contado como atraso.",
    limitacao: "Entregas", fonte: { itens: () => [{ indicador: "entrega_atraso_dias", ano, detalhe: "extrato de entregas dos " + cods.length + " municípios", q: qAnual("q_extrato", cods, ano) }] } }));
  card.append(h("p", {}, h("strong", {}, (k.entregas_irregulares ?? "–") + " de " + (k.entregas_com_dado ?? "–")), " municípios com ao menos uma entrega fora do prazo; ",
    h("strong", {}, String(k.entregas_atraso_30d ?? "–")), " com atraso acima de 30 dias; ", h("strong", {}, String(k.entregas_com_nao_entregue ?? "–")), " com relatório não entregue."));
  card.append(h("ul", { class: "lista nota" }, Object.entries(META.fundamento_entregas || {}).map(([r, f]) => h("li", {}, h("strong", {}, r + ": "), f))));
  const nomePer = o => o.relatorio === "RREO" ? o.periodo + "º bim." : o.relatorio === "DCA" ? "anual" : o.periodo + "º " + (o.periodicidade === "S" ? "sem." : "quadr.");
  const linhas = MUNICIPIOS.map(e => {
    const ob = ENTREGAS.get(chaveEA(e.cod_ibge, ano)) || [];
    const irr = ob.filter(o => o.situacao === "entregue_com_atraso" || o.situacao === "nao_entregue");
    const atraso = irr.filter(o => o.situacao === "entregue_com_atraso").length, nao = irr.filter(o => o.situacao === "nao_entregue").length;
    const maior = Math.max(0, ...irr.map(o => o.dias_atraso || 0));
    const est = !ob.length ? "semdado" : nao ? "descumpre" : atraso ? "sinal" : "cumpre";
    const motivo = [nao ? nao + " relatório(s) não entregue(s)" : null, atraso ? atraso + " entregue(s) com atraso, o maior de " + nf(maior) + " dias" : null].filter(Boolean).join("; ");
    return { e, r: LINHA.get(e.cod_ibge + "|" + ano) || {}, ob, irr, atraso, nao, maior, estado: est, motivo,
      ret: ob.filter(o => o.situacao === "retificado").length };
  }).filter(l => passaFiltro(l.estado)).sort((a, b) => b.nao - a.nao || b.maior - a.maior || b.atraso - a.atraso);
  const colunas = [
    { rotulo: "Município", valor: l => l.e.nome, classe: "col-nome", render: l => linkMunicipio(l.e.cod_ibge, "conformidade", l.e.nome) },
    { rotulo: "Situação", valor: l => ESTADOS[l.estado].rotulo, ordem: l => ORDEM_ESTADO[l.estado], render: l => chipEstado(l.estado, l.estado === "sinal" ? "atraso" : null) },
    { rotulo: "Motivo", valor: l => l.motivo, classe: "motivo", render: l => l.motivo || h("span", { class: "muted" }, "—") },
    { rotulo: "Obrigações", num: true, valor: l => l.ob.length },
    { rotulo: "Com atraso", num: true, valor: l => l.atraso },
    { rotulo: "Não entregues", num: true, valor: l => l.nao },
    { rotulo: "Retificados", num: true, valor: l => l.ret },
    { rotulo: "Maior atraso (dias)", num: true, valor: l => l.maior || null, render: l => l.maior ? nf(l.maior) : "—" },
    { rotulo: "Quais", valor: l => l.irr.map(o => o.poder + " " + o.relatorio + " " + nomePer(o)).join("; "), ordenavel: false,
      render: l => l.irr.length ? h("details", {}, h("summary", {}, l.irr.length + " relatório(s)"),
        h("ul", { class: "lista" }, l.irr.map(o => h("li", {}, h("strong", {}, o.poder + " · " + o.relatorio + " " + nomePer(o)), ": prazo " + dataBR(o.prazo) + ", " +
          (o.situacao === "nao_entregue" ? "não entregue (" + nf(o.dias_atraso) + " dias desde o prazo)" : "entregue em " + dataBR(o.data_local) + " (" + nf(o.dias_atraso) + " dias de atraso)"))))) : "—" },
    colunaFonte(l => l.e.nome + " — extrato de entregas de " + ano, l => [{ indicador: "entrega_atraso_dias", ano, detalhe: l.e.nome, q: l.r.q_extrato }]),
  ];
  card.append(tabela(colunas, linhas, "Entregas por município, " + ano,
    { classeLinha: l => l.estado === "descumpre" ? "l-descumpre" : l.estado === "sinal" ? "l-sinal" : null, busca: "Buscar município…", csv: "entregas_" + ano + ".csv",
      vazio: "Nenhum município com atraso ou relatório pendente neste exercício." }));
  return card;
}

/* ------------------------------------------------- remessas mensais ao TCE-ES */
function cardRemessasTcees() {
  const jan = janelaRemessas();
  const card = h("article", { class: "card largo", id: "card-remessas-tcees", tabindex: "-1" }, cabecalho("Prestação de contas mensal ao TCE-ES — prazos", {
    simples: "Todo mês, cada unidade do município (prefeitura, câmara, fundos) envia ao Tribunal a prestação de contas. Aqui, as remessas enviadas depois do prazo e as ainda pendentes.",
    nota: "A data-limite vem na própria fonte; atraso = homologação depois do limite. \"Pendente\" = prazo vencido sem homologação na data da coleta, numa UG que homologa outros meses. UG sem nenhuma remessa homologada na janela inteira é contada à parte: o padrão é o de conta consolidada em outra UG, não de atraso (a confirmar com o Tribunal).",
    fonte: { itens: () => [{ indicador: "remessa_tcees_atraso_dias", ano: jan ? jan.anoFim : META.ano_mais_recente, detalhe: "todas as UGs dos municípios",
      q: [...new Set(PCM_LINHAS.map(r => r.q).filter(Boolean))].join(";") }] } }));
  if (!jan) { card.append(h("p", {}, chipEstado("semdado", "não coletado"), " O recurso do TCE-ES não foi coletado nesta versão do painel.")); return card; }
  const semRemessa = agrupar(PCM_LINHAS.filter(r => r.situacao === "ug_sem_remessa"), r => r.cod_ibge);
  const porMun = agrupar(jan.vencidas, r => r.cod_ibge);
  const linhas = MUNICIPIOS.map(e => {
    const rs = porMun.get(e.cod_ibge) || [];
    const atr = rs.filter(r => r.situacao === "com_atraso"), nh = rs.filter(r => r.situacao === "nao_homologada");
    const sr = [...new Set((semRemessa.get(e.cod_ibge) || []).map(r => r.ug))];
    const maior = Math.max(0, ...atr.concat(nh).map(r => r.dias_atraso || 0));
    const est = !rs.length ? "semdado" : nh.length ? "descumpre" : atr.length ? "sinal" : "cumpre";
    const motivo = [nh.length ? nh.length + " remessa(s) com prazo vencido e ainda pendente(s)" : null,
      atr.length ? atr.length + " enviada(s) com atraso, o maior de " + nf(maior) + " dias" : null].filter(Boolean).join("; ");
    return { e, rs, atr, nh, sr, maior, estado: est, motivo, ugs: new Set(rs.map(r => r.ug)).size };
  }).filter(l => passaFiltro(l.estado)).sort((a, b) => b.nh.length - a.nh.length || b.maior - a.maior || b.atr.length - a.atr.length);
  const comProblema = linhas.filter(l => l.atr.length || l.nh.length).length;
  card.append(h("p", {}, "Janela publicada pelo TCE-ES: remessas de ", h("strong", {}, jan.ini), " a ", h("strong", {}, jan.fim),
    " (o Tribunal publica só os meses recentes). ", h("strong", {}, String(comProblema)), " município(s) com remessa atrasada ou pendente."));
  const itemRem = r => h("li", {}, h("strong", {}, r.ug), " · " + String(r.mes).padStart(2, "0") + "/" + r.ano + ": limite " + dataBR(r.limite) + ", " +
    (r.situacao === "nao_homologada" ? "pendente (" + nf(r.dias_atraso || 0) + " dias desde o limite)" : "homologada em " + dataBR(r.homologacao) + " (" + nf(r.dias_atraso || 0) + " dias de atraso)"));
  const colunas = [
    { rotulo: "Município", valor: l => l.e.nome, classe: "col-nome", render: l => linkMunicipio(l.e.cod_ibge, "conformidade", l.e.nome) },
    { rotulo: "Situação", valor: l => ESTADOS[l.estado].rotulo, ordem: l => ORDEM_ESTADO[l.estado],
      render: l => chipEstado(l.estado, l.estado === "descumpre" ? "pendente" : l.estado === "sinal" ? "atraso" : null) },
    { rotulo: "Motivo", valor: l => l.motivo, classe: "motivo", render: l => l.motivo || h("span", { class: "muted" }, "—") },
    { rotulo: "UGs", num: true, valor: l => l.ugs },
    { rotulo: "Remessas vencidas", num: true, valor: l => l.rs.length },
    { rotulo: "Com atraso", num: true, valor: l => l.atr.length },
    { rotulo: "Pendentes", num: true, valor: l => l.nh.length },
    { rotulo: "Maior atraso (dias)", num: true, valor: l => l.maior || null, render: l => l.maior ? nf(l.maior) : "—" },
    { rotulo: "UGs sem remessa na janela", num: true, valor: l => l.sr.length,
      render: l => l.sr.length ? h("details", {}, h("summary", {}, String(l.sr.length)), h("ul", { class: "lista" }, l.sr.map(u => h("li", {}, u)))) : "0" },
    { rotulo: "Quais", valor: l => l.atr.concat(l.nh).map(r => r.ug + " " + r.mes + "/" + r.ano).join("; "), ordenavel: false,
      render: l => (l.atr.length + l.nh.length) ? h("details", {}, h("summary", {}, (l.atr.length + l.nh.length) + " remessa(s)"),
        h("ul", { class: "lista" }, l.nh.concat(l.atr).slice(0, 40).map(itemRem))) : "—" },
    colunaFonte(l => l.e.nome + " — prestação de contas mensal ao TCE-ES",
      l => [{ indicador: "remessa_tcees_atraso_dias", ano: jan.anoFim, detalhe: l.e.nome + " (todas as UGs)", q: (l.rs[0] || {}).q }]),
  ];
  card.append(tabela(colunas, linhas, "Prestação de contas mensal ao TCE-ES",
    { classeLinha: l => l.estado === "descumpre" ? "l-descumpre" : l.estado === "sinal" ? "l-sinal" : null, busca: "Buscar município…", csv: "remessas_tcees.csv",
      vazio: "Nenhum município com remessa atrasada ou pendente." }));
  return card;
}

/* --------------------------------------------------------- obras paradas */
function cardObrasParadas() {
  const k = META.kpis_obras || {}, todas = [...OBRAS_EDU.values()].flat();
  const card = h("article", { class: "card largo", id: "card-obras-paradas", tabindex: "-1" }, cabecalho("Obras da Educação paradas ou não iniciadas — situação atual", {
    simples: "Contratos de obra em escolas e prédios da Educação que estão parados ou nem começaram, pela situação na data da coleta.",
    nota: "Contratos com setor beneficiado \"Educação\" declarados ao TCE-ES. \"Paralisação presumida\" é a classificação do Tribunal para obra sem medição recente — indício, não confirmação.",
    limitacao: "Obras", fonte: { itens: () => [{ indicador: "obra_educacao", ano: META.ano_mais_recente, detalhe: "todos os contratos da Educação", q: (todas[0] || {}).q }] } }));
  if (!todas.length) { card.append(h("p", {}, chipEstado("semdado", "não coletado"), " As contratações do TCE-ES não foram coletadas nesta versão do painel.")); return card; }
  card.append(h("div", { class: "kpis" },
    kpi("Contratos de obra da Educação", nf(k.contratos || todas.length), (k.municipios || "–") + " municípios · " + brlCompacto(k.valor || 0)),
    kpi("Paralisadas (declarado)", nf(k.declaradas || 0), "situação \"Paralisada\" ou \"Interrompida\"", { estado: k.declaradas ? "sinal" : null }),
    kpi("Paralisação presumida", nf(k.presumidas || 0), "sem medição recente, segundo o TCE-ES", { estado: k.presumidas ? "sinal" : null }),
    kpi("Não iniciadas", nf(k.nao_iniciadas || 0), "contrato assinado, obra não começou")));
  const filtro = h("select", { id: "f-obras", onchange: () => refazer() },
    h("option", { value: "parada" }, "Paralisadas e presumidas"), h("option", { value: "nao_iniciada" }, "Não iniciadas"), h("option", { value: "todas" }, "Todas as situações"));
  const corpo = h("div");
  const colunas = [
    { rotulo: "Município", valor: o => nomeEnte(o.cod_ibge), classe: "col-nome", render: o => linkMunicipio(o.cod_ibge, "obras", nomeEnte(o.cod_ibge)) },
    { rotulo: "Situação", valor: o => o.situacao, render: o => seloObra(o.situacao) },
    { rotulo: "Objeto", valor: o => o.objeto, render: o => h("span", { title: o.objeto }, String(o.objeto || "").slice(0, 110) + (String(o.objeto || "").length > 110 ? "…" : "")) },
    { rotulo: "Contratada", valor: o => o.contratado },
    { rotulo: "Valor atual (R$)", num: true, valor: o => o.valor, fmt: brl },
    { rotulo: "Assinatura", num: true, valor: o => o.assinatura, fmt: dataBR },
    { rotulo: "Medido", num: true, valor: o => o.pct_medido, render: o => nulo(o.valor_medido) ? semDado("sem medição") : nf(o.pct_medido || 0, 0) + "% · última " + dataBR(o.ultima_medicao) },
    colunaFonte(o => "Obra " + o.contratacao, o => itensFonteObra(o)),
  ];
  function refazer() {
    const f = filtro.value;
    const sel = todas.filter(o => f === "todas" || (f === "parada" ? obraParada(o) : classeObra(o.situacao) === "nao_iniciada")).sort((a, b) => (b.valor || 0) - (a.valor || 0));
    limpar(corpo).append(h("p", { class: "nota" }, sel.length + " contrato(s), " + brl(sel.reduce((t, o) => t + (o.valor || 0), 0)) + ", do maior para o menor valor."),
      tabela(colunas, sel, "Obras da Educação", { classeLinha: o => obraParada(o) ? "l-sinal" : null, busca: "Buscar município, objeto ou contratada…", csv: "obras_educacao_" + f + ".csv" }));
  }
  card.append(h("div", { style: "max-width:300px;margin:6px 0" }, campo("Situação", filtro)), corpo);
  refazer();
  return card;
}

/* ------------------------------------------------------------- conciliação */
function cardConciliacao(ano) {
  const lim = META.divergencia_relevante_pct;
  const card = h("article", { class: "card largo", id: "card-conciliacao", tabindex: "-1" }, cabecalho("Conciliação: despesa em Educação no SICONFI × no SIOPE — " + ano, {
    simples: "O município declara a mesma despesa com educação duas vezes: ao Tesouro (SICONFI) e ao FNDE (SIOPE). Diferença grande entre as duas é sinal a verificar — não prova de erro.",
    nota: "Função 12 empenhada (DCA Anexo I-E) × \"total geral das despesas com educação\" empenhado (Anexo 8 do SIOPE). A despesa \"para fins de limite\" do MDE vai ao lado só como contexto: ela soma a contribuição ao FUNDEB e desconta deduções, então não se compara direto.",
    fonte: { itens: () => { const c = MUNICIPIOS.map(e => e.cod_ibge); return [{ indicador: "divergencia_funcao12_siope", ano, detalhe: "os " + c.length + " municípios", q: qAnual("q_dca_ie", c, ano) + ";" + qAnual("q_siope", c, ano) }]; } } }));
  const todas = linhasMun(ano).map(r => {
    const v = r.divergencia_funcao12_siope_pct;
    return { r, estado: nulo(v) ? "semdado" : Math.abs(v) > lim ? "sinal" : "cumpre",
      motivo: nulo(v) ? "sem dado comparável" : Math.abs(v) > lim ? "diferença de " + nf(Math.abs(v), 1) + "% entre as fontes (limiar: " + nf(lim, 0) + "%)" : "" };
  });
  const linhas = todas.filter(l => passaFiltro(l.estado)).sort((a, b) => Math.abs(b.r.divergencia_funcao12_siope_pct ?? 0) - Math.abs(a.r.divergencia_funcao12_siope_pct ?? 0));
  const acima = todas.filter(l => l.estado === "sinal").length;
  card.append(h("p", {}, h("strong", {}, String(acima)), " município(s) com divergência acima de " + nf(lim, 0) + "%. " +
    "Positiva: a despesa no SICONFI é maior que a declarada ao SIOPE; negativa: menor."));
  const colunas = [
    { rotulo: "Município", valor: l => l.r.ente, classe: "col-nome", render: l => linkMunicipio(l.r.cod_ibge, "conformidade", l.r.ente) },
    { rotulo: "Situação", valor: l => ESTADOS[l.estado].rotulo, ordem: l => ORDEM_ESTADO[l.estado], render: l => chipEstado(l.estado, l.estado === "sinal" ? "divergência" : l.estado === "cumpre" ? "fontes batem" : null) },
    { rotulo: "Função 12 — SICONFI (R$)", num: true, valor: l => l.r.desp_educacao_empenhada, fmt: brl },
    { rotulo: "Educação — SIOPE (R$)", num: true, valor: l => l.r.despesa_total_educacao, fmt: brl },
    { rotulo: "Diferença (R$)", num: true, valor: l => l.r.divergencia_funcao12_siope_rs, fmt: brl },
    { rotulo: "Diferença (%)", num: true, valor: l => l.r.divergencia_funcao12_siope_pct, fmt: v => (v > 0 ? "+" : v < 0 ? "−" : "") + nf(Math.abs(v), 2) + "%" },
    { rotulo: "MDE para fins de limite — SIOPE (R$)", num: true, valor: l => l.r.despesa_mde_limite, fmt: brl },
    colunaFonte(l => l.r.ente + " — conciliação de " + ano, l => [
      { indicador: "desp_educacao_empenhada", ano, q: l.r.q_dca_ie, valor: nulo(l.r.desp_educacao_empenhada) ? null : brl(l.r.desp_educacao_empenhada) },
      { indicador: "siope", ano, detalhe: "despesa_total_educacao", q: l.r.q_siope, observacao: itemUsado(l.r.cod_ibge, ano, "despesa_total_educacao"), valor: nulo(l.r.despesa_total_educacao) ? null : brl(l.r.despesa_total_educacao) },
      { indicador: "divergencia_funcao12_siope", ano, q: [l.r.q_dca_ie, l.r.q_siope], valor: pct(l.r.divergencia_funcao12_siope_pct, 2) }]),
  ];
  card.append(tabela(colunas, linhas, "Conciliação SICONFI × SIOPE, " + ano,
    { classeLinha: l => l.estado === "sinal" ? "l-sinal" : null, busca: "Buscar município…", csv: "conciliacao_" + ano + ".csv", vazio: "Nenhum município com divergência relevante." }));
  return card;
}

function renderConformidade(destino) {
  const ano = estado.ano;
  destino.append(h("div", { class: "cab-visao" }, h("h2", {}, "Conformidade — triagem dos 78 municípios, " + ano),
    h("p", {}, "O que merece atenção primeiro: mínimos constitucionais, prazos de prestação de contas, obras paradas e diferenças entre fontes. Clique no nome de um município para abrir o dossiê dele.")));
  destino.append(faixaKPIs(), legendaEstados());
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" },
    cardMinimos(ano), cardEntregas(ano), cardRemessasTcees(), cardObrasParadas(), cardConciliacao(ano))));
}
