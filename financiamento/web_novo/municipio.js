"use strict";
/* ============================================================================
   Dossiê do município — tudo de um ente num lugar só (decisão D9: a antiga
   "Ficha do município" e a "Receita → aplicação" viraram uma página, e as
   Escolas uma seção dela). Cada seção é uma subpágina com endereço próprio
   (#v=municipio&m=…&s=…), para a página não passar de 11 mil pixels e o botão
   Voltar do navegador levar de volta à seção anterior.

   A seção Conformidade traz o que faltava para a jornada de auditoria: a série
   2021–2025 dos mínimos legais do município, com a linha do mínimo, e as
   entregas, remessas e conciliação dele — antes espalhadas em outras visões.
   ========================================================================== */

const SECOES = [
  { id: "resumo", rotulo: "Resumo", estado: true },
  { id: "conformidade", rotulo: "Conformidade" },
  { id: "receita", rotulo: "Receita" },
  { id: "despesa", rotulo: "Despesa", estado: true },
  { id: "nivel3", rotulo: "Quem recebeu e o que foi comprado" },
  { id: "obras", rotulo: "Obras" },
  { id: "escolas", rotulo: "Escolas" },
  { id: "programas", rotulo: "Programas federais" },
];
const ehMunicipio = cod => (ENTES.get(cod) || {}).esfera === "M";
const secoesDo = cod => SECOES.filter(s => ehMunicipio(cod) || s.estado);

function municipioFiltros(destino) {
  destino.append(
    campo("Município", seletorEnte("f-mun", estado.municipio, cod => irPara({ m: cod, esc: null }), { comEstado: true })),
    campo("Exercício", seletorAno("f-ano", estado.ano, v => ajustar({ ano: v }))));
  if (estado.secao === "escolas") {
    const rede = h("select", { id: "f-rede", onchange: e => ajustar({ rede: e.target.value, escola: null }) },
      Object.entries(REDES).map(([v, t]) => h("option", { value: v }, t)));
    rede.value = estado.rede;
    destino.append(campo("Rede das escolas", rede));
  }
}
const municipioRecorte = () => [h("strong", {}, nomeEnte(estado.municipio)), " · exercício ", h("strong", {}, String(estado.ano)),
  " · seção ", h("strong", {}, (SECOES.find(s => s.id === estado.secao) || SECOES[0]).rotulo),
  estado.secao === "escolas" ? [" · ", h("strong", {}, REDES[estado.rede].toLowerCase())] : null];

/* ================================================================ resumo */
function emResumo(cod, ano, r) {
  const nome = nomeEnte(cod), partes = [];
  if (nulo(r.desp_educacao_empenhada)) return h("p", { class: "em-resumo" }, "Não há dado de despesa em Educação de " + nome + " em " + ano + " (situação da DCA: " + (r.status_dca || "sem linha") + "). Nada é estimado.");
  partes.push(nome + " empenhou " + brlCompacto(r.desp_educacao_empenhada) + " em Educação em " + ano);
  if (!nulo(r.desp_educacao_pct_total)) partes[0] += " — " + nf(r.desp_educacao_pct_total, 1) + "% de toda a sua despesa";
  if (!nulo(r.desp_educacao_por_matricula)) partes[0] += ", ou " + brl(r.desp_educacao_por_matricula) + " por matrícula da rede municipal";
  partes[0] += ".";
  if (ehMunicipio(cod)) {
    const s = situacaoMinimos(r, ano);
    partes.push(s.estado === "cumpre" ? "Cumpriu os mínimos constitucionais da educação pelas duas apurações."
      : s.estado === "semdado" ? "Não há dado sobre os mínimos constitucionais neste exercício."
      : "Nos mínimos constitucionais: " + s.motivo + ".");
  }
  return h("p", { class: "em-resumo" }, partes.join(" "));
}
function fichaKPIs(cod, ano, r) {
  const mun = ehMunicipio(cod), box = h("div", { class: "kpis" });
  const pos = m => mun ? posicaoNoRanking(m, cod, ano) : null;
  box.append(kpi("Despesa em Educação, " + ano, nulo(r.desp_educacao_empenhada) ? "sem dado" : brlCompacto(r.desp_educacao_empenhada),
    "empenhada, função 12" + (mun ? " · " + fraseRanking(pos(METRICAS.desp), "gasto total") : " · o Estado fica fora do ranking"), { nd: nulo(r.desp_educacao_empenhada) }));
  box.append(kpi("Por matrícula", nulo(r.desp_educacao_por_matricula) ? "sem dado" : brl(r.desp_educacao_por_matricula),
    (nulo(r.tcees_alunos) ? (mun ? "sem matrículas na fonte" : "o TCE-ES não publica matrículas do Estado") : nf(r.tcees_alunos) + " matrículas na rede municipal") +
      (mun && !nulo(r.desp_educacao_por_matricula) ? " · " + fraseRanking(pos(METRICAS.pm), "gasto por matrícula") : ""), { nd: nulo(r.desp_educacao_por_matricula) }));
  box.append(kpi("Per capita", nulo(r.desp_educacao_per_capita) ? "sem dado" : brl(r.desp_educacao_per_capita),
    (nulo(r.populacao) ? "sem população" : nf(r.populacao) + " habitantes") + (mun && !nulo(r.desp_educacao_per_capita) ? " · " + fraseRanking(pos(METRICAS.pc), "gasto per capita") : ""),
    { nd: nulo(r.desp_educacao_per_capita) }));
  box.append(kpi("Educação na despesa do ente", pct(r.desp_educacao_pct_total),
    nulo(r.desp_total_empenhada) ? "sem o total do ente" : "de " + brlCompacto(r.desp_total_empenhada) + " empenhados no total", { nd: nulo(r.desp_educacao_pct_total) }));
  const ant = LINHA.get(cod + "|" + (ano - 1));
  if (ant && !nulo(ant.desp_educacao_empenhada) && !nulo(r.desp_educacao_empenhada) && ant.desp_educacao_empenhada > 0)
    box.append(kpi("Variação, " + (ano - 1) + " → " + ano, variacao(100 * (r.desp_educacao_empenhada - ant.desp_educacao_empenhada) / ant.desp_educacao_empenhada),
      "nominal, sem descontar a inflação · de " + brlCompacto(ant.desp_educacao_empenhada)));
  else box.append(kpi("Variação anual", "—", ANOS.includes(ano - 1) ? "sem dado em " + (ano - 1) : ano + " é o primeiro exercício da série", { nd: true }));
  return box;
}
/** O quadro "situação no exercício": cada regra numa linha, com o estado e o caminho para o detalhe. */
function cardSituacao(cod, ano, r) {
  const card = h("article", { class: "card largo", id: "card-situacao" }, cabecalho("Situação em " + ano + " — o que o painel encontrou", {
    simples: "As regras e sinais acompanhados pelo painel para este município no exercício. Cada linha leva ao detalhe." }));
  const lista = h("ul", { class: "situacao-lista" });
  const linha = (rot, est, texto, det, secao) => lista.append(h("li", {}, h("span", { class: "rot" }, rot), chipEstado(est, texto),
    h("span", { class: "det" }, det || "", secao ? [det ? " · " : "", linkPara({ s: secao }, "ver detalhe")] : null)));
  const est = (v, min) => nulo(v) ? "semdado" : v < min ? "descumpre" : "cumpre";
  linha("MDE — apuração do SIOPE", est(r.mde_aplicado_pct, MIN_MDE()), nulo(r.mde_aplicado_pct) ? "sem dado" : nf(r.mde_aplicado_pct, 2) + "%", "mínimo de 25%", "conformidade");
  linha("MDE — apuração do TCE-ES", est(r.tcees_mde_pct, MIN_MDE()), nulo(r.tcees_mde_pct) ? "sem dado" : nf(r.tcees_mde_pct, 2) + "%",
    r.mde_cruza_minimo ? "as duas apurações discordam sobre o mínimo" : "mínimo de 25%", "conformidade");
  linha("FUNDEB na remuneração", est(r.fundeb70_pct, MIN_70()), nulo(r.fundeb70_pct) ? "sem dado" : nf(r.fundeb70_pct, 2) + "%", "mínimo de 70%", "conformidade");
  const ob = ENTREGAS.get(chaveEA(cod, ano)) || [];
  const nao = ob.filter(o => o.situacao === "nao_entregue").length, atr = ob.filter(o => o.situacao === "entregue_com_atraso").length;
  linha("Relatórios ao Tesouro", !ob.length ? "semdado" : nao ? "descumpre" : atr ? "sinal" : "cumpre",
    !ob.length ? "sem dado" : nao ? nao + " não entregue(s)" : atr ? atr + " com atraso" : "no prazo", ob.length + " obrigações no ano", "conformidade");
  const rem = PCM_LINHAS.filter(x => x.cod_ibge === cod && x.situacao !== "prazo_aberto" && x.situacao !== "ug_sem_remessa");
  const pend = rem.filter(x => x.situacao === "nao_homologada").length, atrR = rem.filter(x => x.situacao === "com_atraso").length;
  linha("Remessas mensais ao TCE-ES", !rem.length ? "semdado" : pend ? "descumpre" : atrR ? "sinal" : "cumpre",
    !rem.length ? "sem dado" : pend ? pend + " pendente(s)" : atrR ? atrR + " com atraso" : "no prazo", "janela recente publicada pelo Tribunal", "conformidade");
  const obras = OBRAS_EDU.get(cod) || [], paradas = obras.filter(obraParada);
  linha("Obras da Educação", !obras.length ? "semdado" : paradas.length ? "sinal" : "cumpre",
    !obras.length ? "nenhuma declarada" : paradas.length ? paradas.length + " parada(s)" : "nenhuma parada", obras.length + " contrato(s) · situação atual", obras.length ? "obras" : null);
  const dv = r.divergencia_funcao12_siope_pct;
  linha("Despesa no SICONFI × SIOPE", nulo(dv) ? "semdado" : Math.abs(dv) > META.divergencia_relevante_pct ? "sinal" : "cumpre",
    nulo(dv) ? "sem dado" : Math.abs(dv) > META.divergencia_relevante_pct ? "diferença de " + nf(Math.abs(dv), 1) + "%" : "fontes batem",
    "limiar de " + nf(META.divergencia_relevante_pct, 0) + "%", "conformidade");
  card.append(lista);
  return card;
}
function secaoResumo(destino, cod, ano, r) {
  destino.append(emResumo(cod, ano, r), fichaKPIs(cod, ano, r));
  const grade = h("div", { class: "grade" });
  if (ehMunicipio(cod)) grade.append(cardSituacao(cod, ano, r));
  const itens = subDe(cod, ano);
  const gasto = h("article", { class: "card largo", id: "card-gasto-resumo" }, cabecalho("No que foi gasto — por etapa de ensino, " + ano, {
    simples: "Como a despesa em Educação se divide entre as etapas de ensino e a administração. O detalhe (liquidado, pago, série histórica) está na seção Despesa.",
    fonte: { itens: () => itens.map(i => ({ indicador: "subfuncao_empenhada", ano, detalhe: i.codigo + " - " + i.nome, q: i.q, valor: brl(i.empenhada) })) } }));
  if (itens.length) gasto.append(barrasSubfuncao(itens, r.desp_educacao_empenhada || itens.reduce((t, i) => t + (i.empenhada || 0), 0), ehMunicipio(cod)),
    h("p", { class: "nota" }, linkPara({ s: "despesa" }, "Ver a despesa em detalhe")));
  else gasto.append(h("p", {}, chipEstado("semdado"), " Sem detalhe por subfunção em " + ano + "."));
  grade.append(gasto);
  destino.append(grade);
}

/* ========================================================== conformidade */
function cardSerieMinimos(cod) {
  const linhas = ANOS.map(a => ({ ano: a, r: LINHA.get(cod + "|" + a) || {} }));
  const card = h("article", { class: "card largo", id: "card-serie-minimos" }, cabecalho("Mínimos legais, " + ANOS[0] + "–" + ANOS[ANOS.length - 1] + " — " + nomeEnte(cod), {
    simples: "A trajetória do município nos dois mínimos constitucionais da educação. A linha tracejada é o mínimo: abaixo dela, o município descumpriu a regra por aquela apuração.",
    nota: "MDE pelas duas apurações (SIOPE e TCE-ES), que podem divergir por critério (restos a pagar, cancelamentos, glosas); FUNDEB na remuneração pela apuração do SIOPE.",
    limitacao: "MDE em três apurações",
    fonte: { itens: () => linhas.flatMap(l => [
      { indicador: "mde_pct", ano: l.ano, detalhe: String(l.ano), q: l.r.q_siope, valor: pct(l.r.mde_aplicado_pct, 2) },
      { indicador: "tcees_mde_pct", ano: l.ano, detalhe: String(l.ano), q: l.r.q_tcees_mde, valor: pct(l.r.tcees_mde_pct, 2) },
      { indicador: "fundeb70_pct", ano: l.ano, detalhe: String(l.ano), q: l.r.q_siope, valor: pct(l.r.fundeb70_pct, 2) }]) } }));
  const cs = cores(), grade = h("div", { class: "par-graficos" });
  const serieMde = [linhas.map(l => l.r.mde_aplicado_pct), linhas.map(l => l.r.tcees_mde_pct)];
  const g1 = areaGrafico("% aplicado em MDE por ano, pelas apurações do SIOPE e do TCE-ES, com o mínimo de 25%.", "baixo");
  const g2 = areaGrafico("% do FUNDEB na remuneração por ano, com o mínimo de 70%.", "baixo");
  grade.append(h("div", {}, h("h4", {}, "% da receita de impostos aplicado em MDE"),
      legendaSeries([{ cor: cs.serie[0], forma: FORMAS[0], rotulo: "apuração do SIOPE" }, { cor: cs.serie[1], forma: FORMAS[1], rotulo: "apuração do TCE-ES" }]), g1.caixa),
    h("div", {}, h("h4", {}, "% do FUNDEB na remuneração dos profissionais"), legendaSeries([{ cor: cs.serie[0], forma: FORMAS[0], rotulo: "apuração do SIOPE" }]), g2.caixa));
  card.append(grade);
  const faixa = (vals, min) => { const v = vals.flat().filter(x => !nulo(x)); return { min: Math.floor(Math.min(min, ...v) - 2), max: Math.ceil(Math.max(min, ...v) + 2) }; };
  if (temChart()) {
    const desenhaSerie = (id, cv, datasets, min, rotulo) => {
      const f = faixa(datasets.map(d => d.data), min), op = opcoesBase(cs, v => nf(v, 0) + "%");
      op.scales.y.beginAtZero = false; op.scales.y.min = f.min; op.scales.y.max = f.max;
      op.plugins.tooltip.callbacks = { label: c => " " + c.dataset.label + ": " + (nulo(c.parsed.y) ? "sem dado" : nf(c.parsed.y, 2) + "%") };
      op.plugins.referencia = { valor: min, rotulo: rotulo };
      setTimeout(() => desenhar(id, cv, { type: "line", data: { labels: ANOS, datasets }, options: op, plugins: [plugCrosshair, plugReferencia] }), 0);
    };
    desenhaSerie("serie-mde", g1.cv, [serieLinha("SIOPE", serieMde[0], 0), serieLinha("TCE-ES", serieMde[1], 1)], MIN_MDE(), "mínimo 25%");
    desenhaSerie("serie-f70", g2.cv, [serieLinha("SIOPE", linhas.map(l => l.r.fundeb70_pct), 0)], MIN_70(), "mínimo 70%");
  }
  card.append(tabela([
    { rotulo: "Exercício", valor: l => l.ano },
    { rotulo: "Situação", valor: l => ESTADOS[situacaoMinimos(l.r, l.ano).estado].rotulo, ordem: l => ORDEM_ESTADO[situacaoMinimos(l.r, l.ano).estado], render: l => chipEstado(situacaoMinimos(l.r, l.ano).estado) },
    { rotulo: "Motivo", valor: l => situacaoMinimos(l.r, l.ano).motivo, classe: "motivo", render: l => situacaoMinimos(l.r, l.ano).motivo || h("span", { class: "muted" }, "—") },
    { rotulo: "% MDE — SIOPE", num: true, valor: l => l.r.mde_aplicado_pct, fmt: v => nf(v, 2) + "%" },
    { rotulo: "% MDE — TCE-ES", num: true, valor: l => l.r.tcees_mde_pct, fmt: v => nf(v, 2) + "%" },
    { rotulo: "TCE-ES − SIOPE (p.p.)", num: true, valor: l => l.r.div_mde_tcees_siope_pp, fmt: v => (v > 0 ? "+" : v < 0 ? "−" : "") + nf(Math.abs(v), 2) },
    { rotulo: "% FUNDEB na remuneração", num: true, valor: l => l.r.fundeb70_pct, fmt: v => nf(v, 2) + "%" },
    { rotulo: "Aplicado em MDE (R$)", num: true, valor: l => l.r.mde_aplicado, fmt: brl },
    { rotulo: "Exigido (R$)", num: true, valor: l => l.r.mde_exigido, fmt: brl },
    { rotulo: "…compensação EC 119 (R$)", num: true, valor: l => l.r.mde_compensacao_ec119, fmt: brl },
  ], linhas, "Mínimos legais por exercício — " + nomeEnte(cod), { inicio: 0, busca: false, csv: "minimos_" + cod + ".csv",
    classeLinha: l => { const e = situacaoMinimos(l.r, l.ano).estado; return e === "descumpre" ? "l-descumpre" : e === "sinal" ? "l-sinal" : l.ano === estado.ano ? "destaque" : null; } }));
  const ec = linhas.find(l => l.ano === 2023 && l.r.mde_compensacao_ec119 > 0);
  if (ec) card.append(h("div", { class: "callout info" }, h("strong", {}, "EC 119/2022: "), "o valor exigido de " + brl(ec.r.mde_exigido) + " em 2023 inclui " +
    brl(ec.r.mde_compensacao_ec119) + " de compensação pendente de 2020–2021; o aplicado foi " + brl(ec.r.mde_aplicado) +
    (ec.r.mde_aplicado + 0.005 >= ec.r.mde_exigido ? " — alcançou o exigido." : " — ficou " + brl(ec.r.mde_exigido - ec.r.mde_aplicado) + " abaixo.")));
  return card;
}
function cardEntregasMunicipio(cod, ano) {
  const ob = (ENTREGAS.get(chaveEA(cod, ano)) || []).slice(), r = LINHA.get(cod + "|" + ano) || {};
  const card = h("article", { class: "card", id: "card-entregas-mun" }, cabecalho("Relatórios fiscais ao Tesouro — " + ano, {
    simples: "Cada relatório que a Lei de Responsabilidade Fiscal manda publicar no ano, com o prazo e a data da entrega.",
    nota: "Relatório retificado mostra a data da retificação, e por isso não é contado como atraso.", limitacao: "Entregas",
    fonte: { itens: () => [{ indicador: "entrega_atraso_dias", ano, detalhe: nomeEnte(cod), q: r.q_extrato }] } }));
  const nomePer = o => o.relatorio === "RREO" ? o.periodo + "º bimestre" : o.relatorio === "DCA" ? "anual" : o.periodo + "º " + (o.periodicidade === "S" ? "semestre" : "quadrimestre");
  const est = o => o.situacao === "nao_entregue" ? "descumpre" : o.situacao === "entregue_com_atraso" ? "sinal" : o.situacao === "no_prazo" ? "cumpre" : "semdado";
  const rot = { no_prazo: "no prazo", entregue_com_atraso: "com atraso", nao_entregue: "não entregue", prazo_aberto: "prazo em aberto", retificado: "retificado", sem_data: "sem data" };
  card.append(tabela([
    { rotulo: "Relatório", valor: o => o.poder + " · " + o.relatorio + " " + nomePer(o) },
    { rotulo: "Situação", valor: o => rot[o.situacao] || o.situacao, ordem: o => ORDEM_ESTADO[est(o)], render: o => chipEstado(est(o), rot[o.situacao] || o.situacao) },
    { rotulo: "Prazo", num: true, valor: o => o.prazo, fmt: dataBR },
    { rotulo: "Entregue em", num: true, valor: o => o.data_local, fmt: dataBR },
    { rotulo: "Dias de atraso", num: true, valor: o => o.dias_atraso || null, fmt: nf },
  ], ob.sort((a, b) => ORDEM_ESTADO[est(a)] - ORDEM_ESTADO[est(b)] || (b.dias_atraso || 0) - (a.dias_atraso || 0)), "Entregas de " + nomeEnte(cod) + " em " + ano,
  { inicio: 8, busca: false, fixarPrimeira: false, classeLinha: o => est(o) === "descumpre" ? "l-descumpre" : est(o) === "sinal" ? "l-sinal" : null,
    csv: "entregas_" + cod + "_" + ano + ".csv", vazio: "Sem obrigações registradas no extrato deste exercício." }));
  return card;
}
function cardRemessasMunicipio(cod) {
  const rem = PCM_LINHAS.filter(x => x.cod_ibge === cod && x.situacao !== "prazo_aberto");
  const card = h("article", { class: "card", id: "card-remessas-mun" }, cabecalho("Prestação de contas mensal ao TCE-ES", {
    simples: "As remessas mensais de cada unidade do município ao Tribunal, na janela recente que o TCE-ES publica. Aparecem as atrasadas e as pendentes.",
    nota: "UG sem nenhuma remessa homologada na janela inteira é listada à parte: o padrão é o de conta consolidada em outra UG, não de atraso.",
    fonte: { itens: () => [{ indicador: "remessa_tcees_atraso_dias", ano: META.ano_mais_recente, detalhe: nomeEnte(cod) + " (todas as UGs)", q: (rem[0] || {}).q }] } }));
  const irr = rem.filter(x => x.situacao === "nao_homologada" || x.situacao === "com_atraso");
  const sem = [...new Set(rem.filter(x => x.situacao === "ug_sem_remessa").map(x => x.ug))];
  const vencidas = rem.filter(x => x.situacao !== "ug_sem_remessa");
  card.append(h("p", {}, nf(vencidas.length) + " remessa(s) vencida(s) na janela, de " + new Set(vencidas.map(x => x.ug)).size + " UG(s); " + irr.length + " fora do prazo ou pendente(s)." +
    (sem.length ? " UG(s) sem nenhuma remessa na janela: " + sem.join(", ") + "." : "")));
  card.append(tabela([
    { rotulo: "UG", valor: x => x.ug },
    { rotulo: "Mês", valor: x => String(x.mes).padStart(2, "0") + "/" + x.ano, ordem: x => x.ano * 100 + x.mes },
    { rotulo: "Situação", valor: x => x.situacao === "nao_homologada" ? "pendente" : "atraso", render: x => chipEstado(x.situacao === "nao_homologada" ? "descumpre" : "sinal", x.situacao === "nao_homologada" ? "pendente" : "com atraso") },
    { rotulo: "Data-limite", num: true, valor: x => x.limite, fmt: dataBR },
    { rotulo: "Homologada em", num: true, valor: x => x.homologacao, fmt: dataBR },
    { rotulo: "Dias", num: true, valor: x => x.dias_atraso, fmt: nf },
  ], irr.sort((a, b) => (b.dias_atraso || 0) - (a.dias_atraso || 0)), "Remessas atrasadas ou pendentes — " + nomeEnte(cod),
  { inicio: 8, busca: false, fixarPrimeira: false, classeLinha: x => x.situacao === "nao_homologada" ? "l-descumpre" : "l-sinal",
    csv: "remessas_" + cod + ".csv", vazio: "Nenhuma remessa atrasada ou pendente na janela publicada." }));
  return card;
}
function cardConciliacaoMunicipio(cod, ano, r) {
  const card = h("article", { class: "card largo", id: "card-conciliacao-mun" }, cabecalho("Despesa em Educação declarada em duas fontes — " + ano, {
    simples: "A mesma despesa declarada ao Tesouro (SICONFI) e ao FNDE (SIOPE). Diferença grande entre as duas é sinal a verificar, não prova de erro.",
    fonte: { itens: () => [{ indicador: "desp_educacao_empenhada", ano, q: r.q_dca_ie, valor: nulo(r.desp_educacao_empenhada) ? null : brl(r.desp_educacao_empenhada) },
      { indicador: "siope", ano, detalhe: "despesa_total_educacao", q: r.q_siope, valor: nulo(r.despesa_total_educacao) ? null : brl(r.despesa_total_educacao) },
      { indicador: "divergencia_funcao12_siope", ano, q: [r.q_dca_ie, r.q_siope], valor: pct(r.divergencia_funcao12_siope_pct, 2) }] } }));
  const dv = r.divergencia_funcao12_siope_pct;
  card.append(h("dl", { class: "obra-dl" },
    h("dt", {}, "Função 12 — SICONFI"), h("dd", {}, nulo(r.desp_educacao_empenhada) ? semDado() : brl(r.desp_educacao_empenhada)),
    h("dt", {}, "Educação — SIOPE"), h("dd", {}, nulo(r.despesa_total_educacao) ? semDado() : brl(r.despesa_total_educacao)),
    h("dt", {}, "Diferença"), h("dd", {}, nulo(dv) ? semDado("sem dado comparável") : [brl(r.divergencia_funcao12_siope_rs) + " (" + (dv > 0 ? "+" : dv < 0 ? "−" : "") + nf(Math.abs(dv), 2) + "%) ",
      chipEstado(Math.abs(dv) > META.divergencia_relevante_pct ? "sinal" : "cumpre", Math.abs(dv) > META.divergencia_relevante_pct ? "acima do limiar de " + nf(META.divergencia_relevante_pct, 0) + "%" : "dentro do limiar")])));
  return card;
}
function secaoConformidade(destino, cod, ano, r) {
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" },
    cardSerieMinimos(cod), cardEntregasMunicipio(cod, ano), cardRemessasMunicipio(cod), cardConciliacaoMunicipio(cod, ano, r))));
}

/* ================================================================ receita */
function origemDe(cod, ano) {
  return Object.fromEntries((ORIGEM.get(chaveEA(cod, ano)) || []).map(o => [o.categoria, o]));
}
function cardOrigemReceita(cod, ano) {
  const o = origemDe(cod, ano), total = o.total && o.total.valor, nome = nomeEnte(cod);
  const card = h("article", { class: "card largo", id: "card-origem" }, cabecalho("De onde vem a receita — " + nome + ", " + ano, {
    simples: "Toda a receita do município no ano, dividida em quatro origens: impostos próprios, FUNDEB, transferências federais da educação e o restante.",
    nota: "Receita realizada no ano (exceto intra-orçamentária), em quatro origens que não se sobrepõem. \"Outras\" é calculada por diferença e fica vazia se faltar qualquer parcela.",
    fonte: { itens: () => ORDEM_ORIGEM.concat(["total"]).filter(c => o[c]).map(c => ({ indicador: c === "total" ? "receita_a01" : "origem_receita", ano,
      detalhe: c === "total" ? "ReceitasExcetoIntraOrcamentarias" : (META.origens[c] || {}).rotulo, q: o[c].q, valor: nulo(o[c].valor) ? null : brl(o[c].valor),
      observacao: c === "total" ? null : "fonte: " + o[c].fonte + " — " + (META.origens[c] || {}).localizacao })) } }));
  if (nulo(total)) { card.append(h("p", {}, chipEstado("semdado"), " O RREO Anexo 01 (6º bimestre) de " + ano + " não foi publicado.")); return card; }
  const partes = ORDEM_ORIGEM.map(c => ({ rotulo: (META.origens[c] || {}).rotulo || c, valor: o[c] ? o[c].valor : null, slot: SLOT_ORIGEM[c], c }));
  card.append(barra100(partes, brl), legendaSlots(partes.map(p => ({ rotulo: p.rotulo.split(" (")[0], slot: p.slot }))));
  card.append(tabela([
    { rotulo: "Origem", valor: p => p.rotulo },
    { rotulo: "Valor (R$)", num: true, valor: p => p.valor, fmt: brl },
    { rotulo: "% da receita", num: true, valor: p => nulo(p.valor) ? null : 100 * p.valor / total, fmt: v => nf(v, 1) + "%" },
    { rotulo: "Fonte do número", valor: p => o[p.c] ? o[p.c].fonte : "" },
  ], partes, "Origem da receita de " + nome + ", " + ano, { inicio: 0, busca: false, fixarPrimeira: false, rodape: ["Receita total (Anexo 01)", brl(total), "100%", "SICONFI — RREO Anexo 01"] }));
  if (o.outras && o.outras.valor < 0) card.append(h("div", { class: "callout sinal" }, "As parcelas somam mais que a receita total: as fontes não fecham entre si para este município. É sinal a verificar."));
  card.append(cruzamentoFnde(cod, ano));
  return card;
}
/** Os repasses do FNDE vistos por três fontes: quem pagou (CGU), o que o município registrou (MSC) e o que declarou (SIOPE). */
function cruzamentoFnde(cod, ano) {
  const rep = REPASSES.get(chaveEA(cod, ano)) || [], r = LINHA.get(cod + "|" + ano) || {}, sp = siopeDe(cod, ano);
  let msc = {};
  try { msc = JSON.parse(r.receita_fnde_msc || "{}"); } catch (e) { msc = {}; }
  const cgu = (prog, destino) => { const x = rep.filter(p => p.programa === prog && (!destino || p.destino === destino)); return x.length ? x.reduce((t, p) => t + p.valor, 0) : null; };
  const linhas = [
    { rotulo: "Salário-educação", cgu: cgu("salario_educacao", "municipio"), msc: msc["550"], siope: sp.salario_educacao, prog: "salario_educacao" },
    { rotulo: "PNAE — alimentação escolar", cgu: cgu("pnae", "municipio"), msc: msc["552"], siope: sp.pnae, prog: "pnae" },
    { rotulo: "PNATE — transporte escolar", cgu: cgu("pnate", "municipio"), msc: msc["553"], siope: sp.pnate, prog: "pnate" },
    { rotulo: "PDDE — pago ao município", cgu: cgu("pdde", "municipio"), msc: msc["551"], siope: sp.pdde, prog: "pdde" },
  ];
  const escolas = cgu("pdde", "escolas");
  const bloco = h("div", { class: "subbloco" }, h("h4", {}, "Repasses do FNDE: três olhares sobre o mesmo dinheiro"),
    h("p", { class: "nota" }, comTermos("Pago pela União (CGU, por mês de pagamento) × registrado pelo município na contabilidade (MSC, fontes 550–553) × declarado ao FNDE (SIOPE). A MSC e o SIOPE incluem os rendimentos de aplicação da conta do programa; a CGU mostra só o repasse — por isso as duas primeiras costumam ser um pouco maiores. Diferença grande, ou na direção oposta, é sinal a verificar.")),
    tabela([
      { rotulo: "Programa", valor: l => l.rotulo },
      { rotulo: "Pago (CGU)", num: true, valor: l => l.cgu, fmt: brl },
      { rotulo: "Registrado (MSC)", num: true, valor: l => l.msc, fmt: brl },
      { rotulo: "Declarado (SIOPE)", num: true, valor: l => l.siope, fmt: brl },
      colunaFonte(l => l.rotulo + " — " + nomeEnte(cod) + ", " + ano, l => [
        { indicador: "repasse_fnde", ano, detalhe: (META.programas_fnde || {})[l.prog], q: rep.filter(p => p.programa === l.prog).map(p => p.q).join(";"), valor: nulo(l.cgu) ? null : brl(l.cgu) },
        { indicador: "receita_fonte_msc", ano, detalhe: { salario_educacao: "550", pnae: "552", pnate: "553", pdde: "551" }[l.prog], q: r.q_msc, valor: nulo(l.msc) ? null : brl(l.msc) },
        { indicador: "siope", ano, detalhe: l.prog, q: r.q_siope, valor: nulo(l.siope) ? null : brl(l.siope) }]),
    ], linhas, "Repasses do FNDE em três fontes", { inicio: 0, busca: false, fixarPrimeira: false }));
  if (!nulo(escolas)) bloco.append(h("p", { class: "nota" }, h("strong", {}, "PDDE pago direto às escolas: " + brl(escolas) + ". "),
    "Vai às unidades executoras (caixas escolares) e não passa pelo orçamento municipal — por isso não entra na receita do município."));
  const fs = (META.fontes_status || {}).FNDE || {};
  if (fs.meses !== undefined && fs.meses_esperados !== undefined && fs.meses < fs.meses_esperados)
    bloco.append(h("div", { class: "callout sinal" }, "Repasses da CGU carregados para " + fs.meses + " de " + fs.meses_esperados + " meses. Exercícios com meses faltando ficam subestimados na coluna \"Pago\"."));
  return bloco;
}
function cardFundeb(cod, ano, r) {
  const card = h("article", { class: "card largo", id: "card-fundeb" }, cabecalho("FUNDEB — " + nomeEnte(cod) + ", " + ano, {
    simples: "Quanto o município recebeu do FUNDEB, quanto contribuiu para o fundo e o saldo entre os dois. O mesmo valor aparece em três fontes, que devem bater.",
    limitacao: "FUNDEB",
    fonte: { itens: () => [
      { indicador: "fundeb_receita", ano, q: r.q_dca_ic, valor: nulo(r.fundeb_receita) ? null : brl(r.fundeb_receita) },
      { indicador: "fundeb_msc", ano, detalhe: "fundo + complementação", q: r.q_msc, valor: nulo(r.fundeb_msc_total) ? null : brl(r.fundeb_msc_total) },
      { indicador: "siope", ano, detalhe: "fundeb_principal", q: r.q_siope, observacao: itemUsado(cod, ano, "fundeb_principal"), valor: nulo(r.fundeb_principal) ? null : brl(r.fundeb_principal) },
      { indicador: "fundeb_contribuicao", ano, q: r.q_dca_ic }] } }));
  const bate = (a, b) => nulo(a) || nulo(b) ? "" : Math.abs(a - b) <= 1 ? " Bate com o DCA." : " Difere do DCA em " + brl(a - b) + ".";
  card.append(tabela([
    { rotulo: "Indicador", valor: l => l[0] },
    { rotulo: "Valor", num: true, valor: l => l[1], render: l => nulo(l[1]) ? semDado() : l[2](l[1]) },
    { rotulo: "O que é", valor: l => l[3] },
  ], [
    ["Receita do FUNDEB recebida (DCA)", r.fundeb_receita, brl, "Transferência do fundo + complementação da União (DCA Anexo I-C)."],
    ["…a mesma receita na MSC", r.fundeb_msc_total, brl, "Receita do FUNDEB na contabilidade mensal." + bate(r.fundeb_msc_total, r.fundeb_receita)],
    ["…e no SIOPE (principal)", r.fundeb_principal, brl, "Anexo 8, sem rendimentos de aplicação." + bate(r.fundeb_principal, r.fundeb_receita)],
    ["…da qual complementação da União", r.fundeb_complementacao_uniao, brl, "VAAF, VAAT e VAAR. Ausente = o ente não recebeu."],
    ["Contribuição ao FUNDEB", r.fundeb_contribuicao, brl, "O quanto o ente verteu ao fundo, dos seus impostos."],
    ["FUNDEB líquido", r.fundeb_liquido, brl, "Recebido − contribuição. Negativo = o ente verte mais do que recebe."],
    ["Receita do FUNDEB ÷ despesa em Educação", r.fundeb_pct_desp_educacao, v => nf(v, 1) + "%", "Participação pela receita, não a despesa custeada pelo FUNDEB."],
  ], "FUNDEB de " + nomeEnte(cod) + " em " + ano, { inicio: 0, busca: false, fixarPrimeira: false }));
  return card;
}
function secaoReceita(destino, cod, ano, r) {
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" }, cardOrigemReceita(cod, ano), cardFundeb(cod, ano, r))));
}

/* ================================================================ despesa */
function cardSubfuncoes(cod, ano, r) {
  const itens = subDe(cod, ano);
  const card = h("article", { class: "card largo", id: "card-subfuncoes" }, cabecalho("No que foi gasto — Educação por subfunção, " + ano, {
    simples: "A despesa em Educação dividida por etapa de ensino, com o empenhado, o liquidado e o pago. É a decomposição completa do gasto, não uma amostra.",
    nota: "Detalhe da função 12 no DCA Anexo I-E (Nível 1). As subfunções somam exatamente a despesa em Educação.",
    fonte: { itens: () => itens.map(i => ({ indicador: "subfuncao_empenhada", ano, detalhe: i.codigo + " - " + i.nome, q: i.q, valor: brl(i.empenhada) }))
      .concat([{ indicador: "desp_educacao_empenhada", ano, q: r.q_dca_ie, valor: nulo(r.desp_educacao_empenhada) ? null : brl(r.desp_educacao_empenhada) }]) } }));
  if (!itens.length) { card.append(h("p", {}, chipEstado("semdado"), " Sem detalhe por subfunção em " + ano + (r.status_dca && r.status_dca !== "ok" ? " (situação da DCA: " + r.status_dca + ")." : "."))); return card; }
  const total = r.desp_educacao_empenhada || itens.reduce((t, i) => t + (i.empenhada || 0), 0);
  card.append(barrasSubfuncao(itens, total, ehMunicipio(cod)));
  const fora = ehMunicipio(cod) ? itens.filter(i => SUB_FORA_DA_PRIORIDADE.has(i.codigo)) : [];
  const admin = itens.find(i => i.codigo === SUB_ADMINISTRACAO);
  if (fora.length) card.append(notaForaPrioridade());
  if (admin) card.append(h("p", { class: "nota" }, "Administração geral concentra " + nf(admin.pct_educacao, 1) + "% da despesa em Educação (" + brlCompacto(admin.empenhada) + ")."));
  card.append(tabela(COLUNAS_SUB, itens, "Educação por subfunção — " + nomeEnte(cod) + ", " + ano, { inicio: 0, busca: false, csv: "subfuncoes_" + cod + "_" + ano + ".csv",
    rodape: ["", "Total da função 12", brl(total), nulo(r.desp_educacao_liquidada) ? "" : brl(r.desp_educacao_liquidada), nulo(r.desp_educacao_paga) ? "" : brl(r.desp_educacao_paga), "100%"] }));
  return card;
}
function cardMatrizSubfuncoes(cod) {
  const card = h("article", { class: "card largo", id: "card-matriz-sub" }, cabecalho("Subfunção por exercício — despesa empenhada", {
    simples: "A série completa de cada etapa de ensino. Célula vazia quer dizer que a subfunção não aparece na declaração daquele ano — não que o gasto foi zero.",
    fonte: { itens: () => ANOS.map(a => ({ indicador: "subfuncao_empenhada", ano: a, detalhe: "todas as subfunções, " + a, q: (LINHA.get(cod + "|" + a) || {}).q_dca_ie })) } }));
  const codigos = new Map();
  for (const a of ANOS) for (const sf of subDe(cod, a)) if (!codigos.has(sf.codigo)) codigos.set(sf.codigo, sf.nome);
  if (!codigos.size) { card.append(h("p", {}, chipEstado("semdado"), " Sem detalhe por subfunção em nenhum exercício carregado.")); return card; }
  const valor = (codigo, a) => { const sf = subDe(cod, a).find(x => x.codigo === codigo); return sf ? sf.empenhada : null; };
  const linhas = [...codigos].map(([codigo, nome]) => ({ codigo, nome })).sort((a, b) => (valor(b.codigo, estado.ano) || 0) - (valor(a.codigo, estado.ano) || 0));
  const colunas = [{ rotulo: "Subfunção", valor: l => l.codigo + " — " + l.nome }].concat(ANOS.map(a => ({
    rotulo: String(a), num: true, valor: l => valor(l.codigo, a), render: l => { const v = valor(l.codigo, a); return nulo(v) ? h("span", { class: "muted" }, "—") : brlCompacto(v); }, csv: l => valor(l.codigo, a) })));
  card.append(tabela(colunas, linhas, "Subfunção por exercício", { inicio: 0, busca: false, csv: "subfuncoes_serie_" + cod + ".csv",
    rodape: ["Total da Educação"].concat(ANOS.map(a => { const x = LINHA.get(cod + "|" + a); return x && !nulo(x.desp_educacao_empenhada) ? brlCompacto(x.desp_educacao_empenhada) : "—"; })) }));
  return card;
}
function cardEvolucaoMunicipio(cod) {
  const mun = ehMunicipio(cod), linhas = ANOS.map(a => ({ ano: a, r: LINHA.get(cod + "|" + a) || {} }));
  const card = h("article", { class: "card largo", id: "card-evolucao-mun" }, cabecalho("Evolução da despesa em Educação, " + ANOS[0] + "–" + ANOS[ANOS.length - 1], {
    simples: mun ? "O gasto total e o gasto por matrícula, ano a ano. Valores nominais, sem descontar a inflação." : "O gasto total, ano a ano. Valores nominais, sem descontar a inflação.",
    fonte: { itens: () => ANOS.map(a => { const x = LINHA.get(cod + "|" + a) || {}; return { indicador: "desp_educacao_empenhada", ano: a, detalhe: String(a), q: x.q_dca_ie,
      valor: nulo(x.desp_educacao_empenhada) ? null : brl(x.desp_educacao_empenhada) }; }) } }));
  const ms = mun ? [METRICAS.desp, METRICAS.pm] : [METRICAS.desp];
  const grade = h("div", { class: ms.length === 2 ? "par-graficos" : "" }), cs = cores();
  for (const m of ms) {
    const g = areaGrafico("Evolução de " + m.rotulo + " de " + nomeEnte(cod) + ".", "baixo");
    grade.append(h("div", {}, h("h4", {}, m.curto), g.caixa));
    if (temChart()) {
      const op = opcoesBase(cs, eixoY(m));
      op.plugins.tooltip.callbacks = { title: i => "Exercício " + i[0].label, label: c => " " + fmtMetricaCheio(m, c.parsed.y) };
      setTimeout(() => desenhar("mun-evol-" + m.campo, g.cv, { type: "line", data: { labels: ANOS, datasets: [serieLinha(m.curto, linhas.map(l => l.r[m.campo]), 0)] },
        options: op, plugins: [plugCrosshair] }), 0);
    }
  }
  card.append(grade, blocoTabela("evolução", [
    { rotulo: "Ano", valor: l => l.ano },
    { rotulo: "Empenhada (R$)", num: true, valor: l => l.r.desp_educacao_empenhada, fmt: brl },
    { rotulo: "Liquidada (R$)", num: true, valor: l => l.r.desp_educacao_liquidada, fmt: brl },
    { rotulo: "Paga (R$)", num: true, valor: l => l.r.desp_educacao_paga, fmt: brl },
    { rotulo: "Matrículas (rede municipal)", num: true, valor: l => l.r.tcees_alunos, fmt: nf },
    { rotulo: "Por matrícula (R$)", num: true, valor: l => l.r.desp_educacao_por_matricula, fmt: brl },
    { rotulo: "Per capita (R$)", num: true, valor: l => l.r.desp_educacao_per_capita, fmt: brl },
    { rotulo: "% da despesa do ente", num: true, valor: l => l.r.desp_educacao_pct_total, fmt: v => nf(v, 2) + "%" },
  ], linhas, "evolucao_" + cod + ".csv", { inicio: 0, busca: false, destacar: l => l.ano === estado.ano }));
  return card;
}
function cardBimestralMunicipio(cod, ano) {
  const bims = [1, 2, 3, 4, 5, 6], linhas = bims.map(b => ({ b, x: BIM.get(cod + "|" + ano + "|" + b) }));
  const card = h("article", { class: "card largo", id: "card-bimestral-mun" }, cabecalho("Execução ao longo de " + ano, {
    simples: "Quanto já tinha sido empenhado e liquidado em educação ao fim de cada bimestre. Curva que sobe só no fim do ano indica gasto concentrado em novembro e dezembro.",
    nota: "RREO Anexo 02, valores acumulados até o bimestre.",
    fonte: { itens: () => linhas.filter(l => l.x).map(l => ({ indicador: "empenhada_acum", ano, detalhe: String(l.b), observacao: "tipo de RREO: " + l.x.tipo_rreo, q: l.x.q, valor: brl(l.x.empenhada_acum) })) } }));
  if (!linhas.some(l => l.x)) { card.append(h("p", {}, chipEstado("semdado"), " Nenhum bimestre publicado em " + ano + ".")); return card; }
  const cs = cores(), g = areaGrafico("Execução bimestral em " + ano + ", empenhado e liquidado acumulados.", "baixo");
  card.append(legendaSeries([{ cor: cs.serie[0], forma: FORMAS[0], rotulo: "Empenhada acumulada" }, { cor: cs.serie[1], forma: FORMAS[1], rotulo: "Liquidada acumulada" }]), g.caixa);
  if (temChart()) {
    const op = opcoesBase(cs, tickMoeda);
    op.plugins.tooltip.callbacks = { label: c => " " + c.dataset.label + ": " + brl(c.parsed.y) };
    setTimeout(() => desenhar("mun-bim", g.cv, { type: "line", data: { labels: bims.map(b => b + "º bimestre"), datasets: [
      serieLinha("Empenhada acumulada", linhas.map(l => l.x && l.x.empenhada_acum), 0), serieLinha("Liquidada acumulada", linhas.map(l => l.x && l.x.liquidada_acum), 1)] },
      options: op, plugins: [plugCrosshair] }), 0);
  }
  card.append(blocoTabela("execução bimestral", [
    { rotulo: "Bimestre", valor: l => l.b + "º" }, { rotulo: "Tipo de RREO", valor: l => l.x ? l.x.tipo_rreo : null },
    { rotulo: "Dotação atualizada (R$)", num: true, valor: l => l.x && l.x.dotacao_atualizada, fmt: brl },
    { rotulo: "Empenhada acum. (R$)", num: true, valor: l => l.x && l.x.empenhada_acum, fmt: brl },
    { rotulo: "Liquidada acum. (R$)", num: true, valor: l => l.x && l.x.liquidada_acum, fmt: brl },
    { rotulo: "Empenhada ÷ dotação", num: true, valor: l => l.x && l.x.dotacao_atualizada > 0 ? 100 * l.x.empenhada_acum / l.x.dotacao_atualizada : null, fmt: v => nf(v, 1) + "%" },
  ], linhas, "bimestral_" + cod + "_" + ano + ".csv", { inicio: 0, busca: false }));
  return card;
}
function cardFluxo(cod, ano) {
  const r = LINHA.get(cod + "|" + ano) || {}, nome = nomeEnte(cod), arestas = FLUXO.get(chaveEA(cod, ano)) || [];
  const card = h("article", { class: "card largo", id: "card-fluxo" }, cabecalho("Com que dinheiro, para qual etapa: fonte de recursos → subfunção — " + nome + ", " + ano, {
    simples: "Cada faixa liga a origem do dinheiro (à esquerda) à etapa de ensino em que foi gasto (à direita); a largura é o valor. Passe o ponteiro sobre uma faixa para ver o valor.",
    nota: "Cada empenho da função 12 carrega a fonte de recursos que o paga (MSC). É a ligação declarada pelo próprio município — não uma estimativa proporcional. A fonte 500 junta impostos próprios e transferências de impostos: a contabilidade não os separa.",
    limitacao: "Fluxo fonte",
    fonte: { itens: () => [{ indicador: "fluxo_fonte_subfuncao", ano, detalhe: "todas as fontes e subfunções", q: r.q_msc, valor: brl(arestas.reduce((t, a) => t + a.empenhada, 0)) },
      { indicador: "msc_educacao_empenhada", ano, q: r.q_msc, valor: nulo(r.msc_empenhada) ? null : brl(r.msc_empenhada) }] } }));
  if (!arestas.length) {
    const motivo = r.fontes_msc === "local" ? "Em " + ano + " o município usava códigos de fonte locais, anteriores à padronização nacional: não há tradução segura, então o fluxo não é desenhado."
      : r.status_msc && r.status_msc !== "ok" ? "A MSC não está disponível (" + r.status_msc + ")." : "Sem despesa da função 12 na MSC.";
    card.append(h("p", {}, chipEstado("semdado"), " " + motivo));
    return card;
  }
  const grupos = META.grupos_fonte || {};
  const origens = ORDEM_GRUPO.map(g => ({ id: g, rotulo: (grupos[g] || g).replace(/ \(fontes? [^)]*\)/, ""), slot: SLOT_ORIGEM[g] }));
  const somaSub = sf => arestas.filter(a => a.subfuncao === sf).reduce((t, a) => t + a.empenhada, 0);
  const destinos = [...new Set(arestas.map(a => a.subfuncao))].sort((a, b) => somaSub(b) - somaSub(a)).map(sf => ({ id: sf, rotulo: nomeSubfuncao(sf) }));
  const porGrupo = new Map();
  arestas.forEach(a => { const k = a.grupo + "|" + a.subfuncao; porGrupo.set(k, (porGrupo.get(k) || 0) + a.empenhada); });
  const links = [...porGrupo].map(([k, v]) => ({ de: k.split("|")[0], para: k.split("|")[1], valor: v }));
  card.append(h("div", { class: "grafico-svg" }, redesenhavel(() => sankey({ origens, destinos, arestas: links, formatar: brlCompacto, titulo: "Fluxo fonte → subfunção de " + nome }))));
  card.append(legendaSlots(origens.map(o => ({ rotulo: o.rotulo, slot: o.slot }))));
  if (!nulo(r.msc_empenhada) && !nulo(r.desp_educacao_empenhada)) card.append(h("p", { class: "nota" }, Math.abs(r.msc_empenhada - r.desp_educacao_empenhada) <= 1
    ? "Conferência: o total do fluxo (" + brl(r.msc_empenhada) + ") bate ao centavo com a função 12 do DCA."
    : "Atenção: o total da MSC (" + brl(r.msc_empenhada) + ") difere da função 12 do DCA (" + brl(r.desp_educacao_empenhada) + ") em " + brl(r.msc_empenhada - r.desp_educacao_empenhada) + "."));
  card.append(blocoTabela("fonte × subfunção", [
    { rotulo: "Fonte de recursos", valor: a => a.fonte + " — " + ((META.nome_fonte || {})[a.fonte] || "fonte " + a.fonte) },
    { rotulo: "Grupo", valor: a => (grupos[a.grupo] || a.grupo).split(" (")[0] },
    { rotulo: "Subfunção", valor: a => a.subfuncao + " — " + nomeSubfuncao(a.subfuncao) },
    { rotulo: "Empenhado (R$)", num: true, valor: a => a.empenhada, fmt: brl },
  ], arestas.slice().sort((a, b) => ORDEM_GRUPO.indexOf(a.grupo) - ORDEM_GRUPO.indexOf(b.grupo) || b.empenhada - a.empenhada), "fluxo_" + cod + "_" + ano + ".csv", { inicio: 0 }));
  return card;
}
function cardNatureza(cod, ano) {
  const r = LINHA.get(cod + "|" + ano) || {}, nome = nomeEnte(cod), linhas = NATUREZA.get(chaveEA(cod, ano)) || [];
  const card = h("article", { class: "card largo", id: "card-natureza" }, cabecalho("Com o quê: pessoal, custeio e investimento — " + nome + ", " + ano, {
    simples: "O gasto em Educação pelo tipo de despesa: salários e encargos, custeio (serviços, material, alimentação, transporte) e investimentos (obras e equipamentos).",
    nota: "Natureza econômica de cada empenho da função 12 (MSC, Nível 2): categoria pelo grupo da natureza de despesa e pelo elemento.",
    fonte: { itens: () => [{ indicador: "natureza_economica", ano, detalhe: "categoria pelo grupo e pelo elemento", q: r.q_msc, valor: brl(linhas.reduce((t, l) => t + l.empenhada, 0)) }] } }));
  if (!linhas.length) { card.append(h("p", {}, chipEstado("semdado"), " A MSC não está disponível para " + ano + ".")); return card; }
  const total = linhas.reduce((t, l) => t + l.empenhada, 0);
  const cats = META.categorias_natureza || {}, subcats = META.subcategorias_natureza || {}, elementos = META.elementos || {};
  const porSub = new Map();
  linhas.forEach(l => { const k = l.categoria + "|" + l.subcategoria; const a = porSub.get(k) || { categoria: l.categoria, subcategoria: l.subcategoria, empenhada: 0 };
    a.empenhada += l.empenhada; porSub.set(k, a); });
  const itens = [];
  for (const c of ["pessoal", "custeio", "investimento", "outras"]) {
    const doGrupo = [...porSub.values()].filter(x => x.categoria === c).sort((a, b) => b.empenhada - a.empenhada);
    if (!doGrupo.length) continue;
    const somaC = doGrupo.reduce((t, x) => t + x.empenhada, 0);
    itens.push({ grupo: cats[c] || c, detalhe: brlCompacto(somaC) + " · " + nf(100 * somaC / total, 1) + "%" });
    doGrupo.forEach(x => itens.push({ nome: subcats[x.subcategoria] || x.subcategoria, valor: x.empenhada }));
  }
  card.append(barrasHorizontais(itens, total, { rotulo: "Despesa por natureza econômica" }));
  card.append(blocoTabela("natureza por elemento", [
    { rotulo: "Categoria", valor: l => cats[l.categoria] || l.categoria },
    { rotulo: "Subcategoria", valor: l => subcats[l.subcategoria] || l.subcategoria },
    { rotulo: "Elemento de despesa", valor: l => l.elemento + " — " + (elementos[l.elemento] || "ver Portaria 163/2001") },
    { rotulo: "Empenhado (R$)", num: true, valor: l => l.empenhada, fmt: brl },
    { rotulo: "Liquidado (R$)", num: true, valor: l => l.liquidada, fmt: brl },
    { rotulo: "Pago (R$)", num: true, valor: l => l.paga, fmt: brl },
  ], linhas.slice().sort((a, b) => b.empenhada - a.empenhada), "natureza_" + cod + "_" + ano + ".csv", { inicio: 0, rodape: ["", "", "Total", brl(total), "", ""] }));
  return card;
}
function secaoDespesa(destino, cod, ano, r) {
  const mun = ehMunicipio(cod);
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" },
    cardSubfuncoes(cod, ano, r), cardEvolucaoMunicipio(cod), cardMatrizSubfuncoes(cod), cardBimestralMunicipio(cod, ano),
    mun ? cardFluxo(cod, ano) : null, mun ? cardNatureza(cod, ano) : null)));
  if (!mun) destino.append(h("p", { class: "nota" }, "Fluxo por fonte de recursos e natureza econômica vêm da MSC dos municípios e não se aplicam ao Estado."));
}

/* ============================================================== demais seções */
function secaoNivel3(destino, cod, ano) {
  destino.append(h("p", { class: "cab-visao" }, comTermos("Nível 3 é o detalhe mais fino do gasto: quem recebeu, em qual ação do orçamento, com que fonte de recursos e o que foi comprado. Os dados são os que o município declarou ao TCE-ES, conferidos contra a DCA.")));
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" },
    cardNivel3Credores(cod, ano), cardNivel3Acoes(cod, ano), cardNivel3Fontes(cod, ano), cardNivel3Conselhos(cod, ano), cardNivel3Itens(cod, ano), cardNivel3Limites(cod))));
}
function secaoProgramas(destino, cod, ano) {
  const grade = h("div", { class: "grade" }, cardProgramasDoMunicipio(cod), ...cardsCncaMunicipio(cod, ano));
  if (ARQUIVO_CNCA) grade.append(h("article", { class: "card largo", id: "card-cnca-evidencias" }, cabecalho("Evidências da fiscalização do CNCA — " + nomeEnte(cod), {
    simples: "O papel de trabalho da fiscalização do financiamento do CNCA fica num arquivo separado. Lá está a ficha de evidências deste município, questão por questão." }),
    h("p", {}, linkCnca({ v: "municipio", m: cod }, "Abrir a ficha de evidências do CNCA de " + nomeEnte(cod) + " ↗"))));
  destino.append(h("section", { class: "bloco" }, grade));
}

function renderMunicipio(destino) {
  if (!ENTES.has(estado.municipio)) estado.municipio = MUNICIPIOS[0].cod_ibge;
  const cod = estado.municipio, ano = estado.ano, r = LINHA.get(cod + "|" + ano) || {};
  const secoes = secoesDo(cod);
  if (!secoes.some(s => s.id === estado.secao)) estado.secao = "resumo";
  destino.append(h("div", { class: "cab-visao" },
    h("h2", {}, nomeEnte(cod), h("span", { class: "muted small" }, "  " + (ehMunicipio(cod) ? "código IBGE " : "UF ") + cod + " · exercício " + ano)),
    h("p", {}, "O dossiê do município: situação nos mínimos legais, de onde vem e para onde vai o dinheiro da educação, quem recebeu, as obras, as escolas e os programas federais."),
    h("p", { class: "small" }, ehMunicipio(cod) ? linkPara({ v: "panorama", e: [...new Set([cod, ...estado.sel])].slice(0, MAX_COMPARAR).join(",") }, "Comparar com outros municípios no Panorama") : null)));
  destino.append(h("nav", { class: "secoes", "aria-label": "Seções do dossiê" }, h("ul", {}, secoes.map(s =>
    h("li", {}, h("a", { href: hrefPara({ s: s.id, esc: null }), "aria-current": s.id === estado.secao ? "page" : null }, s.rotulo))))));
  if (r.status_dca && r.status_dca !== "ok" && ["resumo", "despesa"].includes(estado.secao))
    destino.append(h("div", { class: "callout sinal" }, h("strong", {}, "Sem dado de despesa por função em " + ano + ". "), "Situação da DCA: " + r.status_dca + ". Os campos ficam vazios — nada é estimado."));
  const corpo = h("div", { id: "secao-" + estado.secao });
  ({ resumo: () => secaoResumo(corpo, cod, ano, r), conformidade: () => secaoConformidade(corpo, cod, ano, r), receita: () => secaoReceita(corpo, cod, ano, r),
     despesa: () => secaoDespesa(corpo, cod, ano, r), nivel3: () => secaoNivel3(corpo, cod, ano), obras: () => corpo.append(h("section", { class: "bloco" }, cardNivel3Obras(cod))),
     escolas: () => renderSecaoEscolas(corpo, cod, ano), programas: () => secaoProgramas(corpo, cod, ano) })[estado.secao]();
  destino.append(corpo);
}
