"use strict";
/* ============================================================================
   Panorama do ES — o gasto em Educação dos 78 municípios: no que se gasta,
   comparação lado a lado, evolução, ranking, execução no ano e cobertura.

   Decisão D5: a despesa aparece SEMPRE em dois pares — o valor absoluto (que
   mede o tamanho da rede) e o valor por matrícula (que mede o esforço por aluno)
   —, em valores nominais. Os outros indicadores ficam no seletor.
   ========================================================================== */

const INDICADORES_PANORAMA = { par: "Despesa em Educação — absoluta e por matrícula", pc: METRICAS.pc.rotulo, pct: METRICAS.pct.rotulo,
  fundeb: METRICAS.fundeb.rotulo, admin: METRICAS.admin.rotulo };
const metricasPanorama = () => estado.metrica === "par" || !METRICAS[estado.metrica] ? [METRICAS.desp, METRICAS.pm] : [METRICAS[estado.metrica]];

function adicionar(cod) {
  if (!ENTES.has(cod) || estado.sel.includes(cod) || estado.sel.length >= MAX_COMPARAR) return;
  const usados = new Set(estado.sel.map(c => estado.slot.get(c)));
  let livre = 0; while (usados.has(livre)) livre++;
  estado.slot.set(cod, livre);  // quem sai não repinta quem fica
  estado.sel.push(cod);
}
function remover(cod) { estado.sel = estado.sel.filter(c => c !== cod); estado.slot.delete(cod); }
/** Os municípios de porte mais parecido (matrículas da rede municipal) com `cod`. */
function paresPorPorte(cod, ano, quantos) {
  const base = (LINHA.get(cod + "|" + ano) || {}).tcees_alunos;
  if (nulo(base) || base <= 0) return [];
  return MUNICIPIOS.map(e => ({ cod: e.cod_ibge, a: (LINHA.get(e.cod_ibge + "|" + ano) || {}).tcees_alunos }))
    .filter(x => x.cod !== cod && !estado.sel.includes(x.cod) && x.a > 0)
    .sort((x, y) => Math.abs(Math.log(x.a / base)) - Math.abs(Math.log(y.a / base))).slice(0, quantos).map(x => x.cod);
}
function legendaEntes(entes) {
  const cs = cores();
  return legendaSeries(entes.map(cod => ({ cor: cs.serie[estado.slot.get(cod)], forma: FORMAS[estado.slot.get(cod)], rotulo: nomeEnte(cod) })));
}

function panoramaFiltros(destino) {
  const indicador = h("select", { id: "f-metrica", onchange: e => ajustar({ metrica: e.target.value }) },
    Object.entries(INDICADORES_PANORAMA).map(([k, v]) => h("option", { value: k }, v)));
  indicador.value = INDICADORES_PANORAMA[estado.metrica] ? estado.metrica : "par";
  const baseMun = estado.sel.find(c => (ENTES.get(c) || {}).esfera === "M");
  const vagas = MAX_COMPARAR - estado.sel.length;
  // Element.append escreveria "null" como texto: os botões condicionais são filtrados antes.
  destino.append(...[
    campo("Exercício", seletorAno("f-ano", estado.ano, v => ajustar({ ano: v }))),
    campo("Indicador", indicador),
    campo("Comparar (até " + MAX_COMPARAR + ")", seletorEnte("f-ente", "", cod => { adicionar(cod); ajustar({}); },
      { vazio: vagas > 0 ? "Adicionar município…" : "Máximo atingido", comEstado: true, limpaApos: true })),
    baseMun && vagas > 0 ? h("button", { type: "button", class: "leve", title: "Pelo número de matrículas da rede municipal",
      onclick: () => { paresPorPorte(baseMun, estado.ano, vagas).forEach(adicionar); ajustar({}); } }, "+ porte parecido com " + nomeEnte(baseMun)) : null,
    estado.sel.length ? h("button", { type: "button", class: "leve", onclick: () => { estado.sel = []; estado.slot.clear(); ajustar({}); } }, "Limpar comparação") : null].filter(Boolean));
}
/** Os entes em comparação, com a chave de cor e forma de cada um. Fica no conteúdo, não na
 *  barra fixa: o recorte ("comparando …") já os nomeia, e a barra não precisa de uma linha a mais. */
function chipsComparacao() {
  const chips = h("div", { class: "chips", role: "group", "aria-label": "Municípios em comparação" },
    h("span", { class: "dica" }, estado.sel.length ? "Em comparação:" : "Nenhum município em comparação — escolha até " + MAX_COMPARAR + " no filtro \"Comparar\"."));
  estado.sel.forEach(cod => {
    const k = estado.slot.get(cod), chave = chaveLinha(cores().serie[k], FORMAS[k]);
    chave.classList.add("chave");
    chips.append(h("span", { class: "chip" }, chave, nomeEnte(cod),
      h("button", { type: "button", "aria-label": "Tirar " + nomeEnte(cod) + " da comparação", onclick: () => { remover(cod); ajustar({}); } }, "×")));
  });
  return chips;
}
const panoramaRecorte = () => ["exercício ", h("strong", {}, String(estado.ano)), " · ", h("strong", {}, INDICADORES_PANORAMA[estado.metrica] || INDICADORES_PANORAMA.par),
  estado.sub ? [" · ranking só de ", h("strong", {}, rotuloSubfuncao(estado.sub))] : null,
  estado.sel.length ? [" · comparando ", h("strong", {}, estado.sel.map(nomeEnte).join(", "))] : " · nenhum município em comparação"];

/* -------------------------------------------------------------------- KPIs */
function panoramaKPIs() {
  const ano = estado.ano, mun = linhasMun(ano);
  const ok = mun.filter(r => !nulo(r.desp_educacao_empenhada));
  const soma = ok.reduce((t, r) => t + r.desp_educacao_empenhada, 0);
  const est = COD_ESTADO && LINHA.get(COD_ESTADO + "|" + ano);
  const comMat = ok.filter(r => r.tcees_alunos > 0);
  const mats = comMat.reduce((t, r) => t + r.tcees_alunos, 0), despMat = comMat.reduce((t, r) => t + r.desp_educacao_empenhada, 0);
  const porMat = comMat.map(r => r.desp_educacao_por_matricula).filter(v => !nulo(v)).sort((a, b) => a - b);
  const mediana = porMat.length ? (porMat.length % 2 ? porMat[(porMat.length - 1) / 2] : (porMat[porMat.length / 2 - 1] + porMat[porMat.length / 2]) / 2) : null;
  const box = h("div", { class: "kpis", role: "region", "aria-label": "Números do panorama em " + ano });
  box.append(kpi("Despesa em Educação dos municípios, " + ano, ok.length ? brlCompacto(soma) : "sem dado",
    ok.length + " de " + MUNICIPIOS.length + " municípios com dado · empenhada" + (est && !nulo(est.desp_educacao_empenhada) ? " · o Estado, à parte: " + brlCompacto(est.desp_educacao_empenhada) : ""), { nd: !ok.length }));
  box.append(kpi("Por matrícula, no conjunto dos municípios", mats ? brl(despMat / mats) : "sem dado",
    mats ? "mediana entre os municípios: " + brl(mediana) + " · " + comMat.length + " municípios com matrículas" : "", { nd: !mats }));
  const ant = ano - 1;
  if (ANOS.includes(ant)) {
    const comuns = ok.filter(r => { const p = LINHA.get(r.cod_ibge + "|" + ant); return p && !nulo(p.desp_educacao_empenhada); });
    const a = comuns.reduce((t, r) => t + r.desp_educacao_empenhada, 0), b = comuns.reduce((t, r) => t + LINHA.get(r.cod_ibge + "|" + ant).desp_educacao_empenhada, 0);
    box.append(comuns.length && b > 0 ? kpi("Variação da despesa, " + ant + " → " + ano, variacao(100 * (a - b) / b), "nominal, sem descontar a inflação · " + comuns.length + " municípios com dado nos dois anos")
      : kpi("Variação da despesa", "sem dado", "nenhum município com dado nos dois exercícios", { nd: true }));
  } else box.append(kpi("Variação da despesa", "—", ano + " é o primeiro exercício da série", { nd: true }));
  box.append(kpi("Matrículas na rede municipal, " + ano, mats ? nf(mats) : "sem dado", "fonte: TCE-ES, conferida contra o Censo Escolar", { nd: !mats }));
  return box;
}

/* ------------------------------------------------------ no que se gasta */
const COLUNAS_SUB = [
  { rotulo: "Código", valor: i => i.codigo },
  { rotulo: "Subfunção", valor: i => i.nome },
  { rotulo: "Empenhada (R$)", num: true, valor: i => i.empenhada, fmt: brl },
  { rotulo: "Liquidada (R$)", num: true, valor: i => i.liquidada, fmt: brl },
  { rotulo: "Paga (R$)", num: true, valor: i => i.paga, fmt: brl },
  { rotulo: "% da Educação", num: true, valor: i => i.pct_educacao, fmt: v => nf(v, 2) + "%" },
];
function barrasSubfuncao(itens, total, marcar) {
  return barrasHorizontais(itens.map(i => ({ nome: i.nome, codigo: i.codigo, valor: i.empenhada, atencao: marcar && SUB_FORA_DA_PRIORIDADE.has(i.codigo) })), total,
    { rotulo: "Despesa por subfunção", rotuloAtencao: "fora da prioridade municipal" });
}
function notaForaPrioridade() {
  return h("p", { class: "nota" }, h("span", { class: "chave-ret", style: "background:repeating-linear-gradient(135deg," + cores().serie[1] + " 0 4px," + cores().surface + " 4px 6px);vertical-align:-1px" }),
    " Barra listrada: subfunção fora da prioridade municipal (art. 211 da Constituição). Não é irregularidade por si — é ponto a verificar caso a caso.");
}
function cardNoQueSeGasta() {
  const ano = estado.ano, cods = MUNICIPIOS.map(e => e.cod_ibge);
  const card = h("article", { class: "card largo", id: "card-subfuncoes-es" }, cabecalho("No que os municípios gastam — Educação por subfunção, " + ano, {
    simples: "Como os 78 municípios dividem o gasto com educação entre as etapas de ensino. O município cuida sobretudo do ensino fundamental e da educação infantil.",
    nota: "Soma dos 78 municípios. As subfunções são o detalhe da função 12 no DCA Anexo I-E e somam exatamente o total da Educação. O Estado fica de fora.",
    fonte: { itens: () => [{ indicador: "subfuncao_empenhada", ano, detalhe: "todas as subfunções da função 12, soma dos " + cods.length + " municípios", q: qAnual("q_dca_ie", cods, ano) }] } }));
  const agregado = new Map();
  for (const e of MUNICIPIOS) for (const sf of subDe(e.cod_ibge, ano)) {
    const a = agregado.get(sf.codigo) || { codigo: sf.codigo, nome: sf.nome, empenhada: 0, liquidada: 0, paga: 0, municipios: 0 };
    a.empenhada += sf.empenhada || 0; a.liquidada += sf.liquidada || 0; a.paga += sf.paga || 0; a.municipios++;
    agregado.set(sf.codigo, a);
  }
  const itens = [...agregado.values()].sort((a, b) => b.empenhada - a.empenhada);
  if (!itens.length) { card.append(h("p", {}, chipEstado("semdado"), " Sem detalhe por subfunção neste exercício.")); return card; }
  const total = itens.reduce((t, i) => t + i.empenhada, 0);
  itens.forEach(i => { i.pct_educacao = total > 0 ? 100 * i.empenhada / total : null; });
  card.append(barrasSubfuncao(itens, total, true));
  const fora = itens.filter(i => SUB_FORA_DA_PRIORIDADE.has(i.codigo));
  if (fora.length) card.append(notaForaPrioridade(), h("p", { class: "nota" }, "Em " + ano + ": " + fora.map(i => i.nome.toLowerCase() + " em " + i.municipios + " município(s), " + brlCompacto(i.empenhada)).join("; ") + "."));
  card.append(blocoTabela("subfunções", COLUNAS_SUB.slice(0, 5).concat([{ rotulo: "Municípios com a subfunção", num: true, valor: i => i.municipios }]), itens,
    "subfuncoes_es_" + ano + ".csv", { inicio: 0, rodape: ["", "Total", brl(total), "", "", ""] }));
  return card;
}

/* ------------------------------------------------------ comparação */
function cardComparacao() {
  const ano = estado.ano;
  const card = h("article", { class: "card largo", id: "card-comparacao" }, cabecalho("Comparação lado a lado — " + ano, {
    simples: "Os municípios escolhidos no filtro \"Comparar\", lado a lado. Para comparar redes de tamanhos diferentes, olhe os valores por matrícula e as participações em %.",
    nota: "Per capita divide pela população do município (que o SICONFI só atualiza a cada dois exercícios); por matrícula divide pelas matrículas da rede municipal no ano (TCE-ES, conferidas contra o Censo). \"sem dado\" é ausência na fonte, nunca zero.",
    fonte: { itens: () => estado.sel.flatMap(cod => { const r = LINHA.get(cod + "|" + ano) || {}, nome = nomeEnte(cod); return [
      { indicador: "desp_educacao_empenhada", ano, detalhe: nome, q: r.q_dca_ie, valor: nulo(r.desp_educacao_empenhada) ? null : brl(r.desp_educacao_empenhada) },
      { indicador: "fundeb_receita", ano, detalhe: nome, q: r.q_dca_ic, valor: nulo(r.fundeb_receita) ? null : brl(r.fundeb_receita) },
      nulo(r.desp_educacao_por_matricula) ? null : { indicador: "desp_educacao_por_matricula", ano, detalhe: nome, q: [r.q_dca_ie, r.q_tcees_mde].filter(Boolean).join(";"), valor: brl(r.desp_educacao_por_matricula) },
      { indicador: "origem_receita", ano, detalhe: nome, q: (ORIGEM.get(chaveEA(cod, ano)) || []).map(o => o.q).join(";") },
      { indicador: "natureza_economica", ano, detalhe: nome, q: r.q_msc }].filter(Boolean); }) } }));
  if (!estado.sel.length) { card.append(h("p", { class: "muted" }, "Escolha municípios no filtro \"Comparar\", no alto da página.")); return card; }
  const origemDe_ = (c) => Object.fromEntries((ORIGEM.get(chaveEA(c, ano)) || []).map(o => [o.categoria, o]));
  const share = (parte, total) => nulo(parte) || !total ? null : 100 * parte / total;
  const nat = (c, cat) => { const l = NATUREZA.get(chaveEA(c, ano)) || []; const t = l.reduce((a, x) => a + x.empenhada, 0); return l.length ? share(l.filter(x => x.categoria === cat).reduce((a, x) => a + x.empenhada, 0), t) : null; };
  const sub = (c, cods_) => { const l = SUB.get(c + "|" + ano) || []; const t = l.reduce((a, x) => a + (x.empenhada || 0), 0); return l.length ? share(l.filter(x => cods_.includes(x.codigo)).reduce((a, x) => a + x.empenhada, 0), t) : null; };
  const orig = (c, k) => { const o = origemDe_(c); return share(o[k] && o[k].valor, o.total && o.total.valor); };
  const r_ = c => LINHA.get(c + "|" + ano) || {};
  const pctF = v => nf(v, 1) + "%";
  const def = [
    ["Tamanho", "População do exercício", c => r_(c).populacao, v => nf(v)],
    ["Tamanho", "Matrículas na rede municipal", c => r_(c).tcees_alunos, v => nf(v)],
    ["Gasto", "Despesa em Educação (empenhada)", c => r_(c).desp_educacao_empenhada, brl],
    ["Gasto", "Por matrícula (R$/matrícula)", c => r_(c).desp_educacao_por_matricula, brl],
    ["Gasto", "Per capita (R$/hab.)", c => r_(c).desp_educacao_per_capita, brl],
    ["Gasto", "Educação em % da despesa total", c => r_(c).desp_educacao_pct_total, v => nf(v, 2) + "%"],
    ["Receita", "Receita total (Anexo 01)", c => (origemDe_(c).total || {}).valor, brlCompacto],
    ["Receita", "…impostos próprios", c => orig(c, "impostos_proprios"), pctF],
    ["Receita", "…FUNDEB", c => orig(c, "fundeb"), pctF],
    ["Receita", "…transferências federais específicas", c => orig(c, "federal_especifica"), pctF],
    ["Receita", "FUNDEB líquido (recebido − contribuição)", c => r_(c).fundeb_liquido, brl],
    ["Onde gasta", "…ensino fundamental (12.361)", c => sub(c, ["12.361"]), pctF],
    ["Onde gasta", "…educação infantil (12.365)", c => sub(c, ["12.365"]), pctF],
    ["Onde gasta", "…administração geral (12.122)", c => sub(c, ["12.122"]), pctF],
    ["Com o quê", "…pessoal", c => nat(c, "pessoal"), pctF],
    ["Com o quê", "…custeio", c => nat(c, "custeio"), pctF],
    ["Com o quê", "…investimento", c => nat(c, "investimento"), pctF],
    ["Mínimos legais", "% MDE — SIOPE (mín. 25%)", c => r_(c).mde_aplicado_pct, v => nf(v, 2) + "%"],
    ["Mínimos legais", "% MDE — TCE-ES (mín. 25%)", c => r_(c).tcees_mde_pct, v => nf(v, 2) + "%"],
    ["Mínimos legais", "% FUNDEB na remuneração (mín. 70%)", c => r_(c).fundeb70_pct, v => nf(v, 2) + "%"],
  ];
  const cols = [{ rotulo: "Grupo", valor: l => l[0] }, { rotulo: "Indicador", valor: l => l[1] }].concat(estado.sel.map(cod => ({
    rotulo: nomeEnte(cod), num: true, valor: l => l[2](cod), render: l => { const v = l[2](cod); return nulo(v) ? semDado() : l[3](v); } })));
  const barras = h("div", { class: "comparacao-barras" }, estado.sel.filter(c => ENTES.get(c).esfera === "M").map(c => {
    const o = origemDe_(c);
    return h("div", { class: "linha-barra" }, h("span", { class: "nome" }, nomeEnte(c)),
      barra100(ORDEM_ORIGEM.map(k => ({ rotulo: (META.origens[k] || {}).rotulo || k, valor: o[k] ? o[k].valor : null, slot: SLOT_ORIGEM[k] })), brl));
  }));
  card.append(h("h4", {}, "De onde vem a receita de cada um"), barras,
    legendaSlots(ORDEM_ORIGEM.map(k => ({ rotulo: ((META.origens[k] || {}).rotulo || k).split(" (")[0], slot: SLOT_ORIGEM[k] }))),
    tabela(cols, def, "Comparação lado a lado, " + ano, { inicio: 0, busca: false, csv: "comparacao_" + ano + ".csv", fixarPrimeira: false }));
  if (estado.sel.includes(COD_ESTADO)) card.append(h("p", { class: "nota" }, "O Estado fica sem matrículas e sem estrutura de receita: essas fontes cobrem só os municípios."));
  return card;
}

/* ------------------------------------------------------ evolução */
function cardEvolucao() {
  const ms = metricasPanorama(), par = ms.length === 2;
  const card = h("article", { class: "card largo", id: "card-evolucao" }, cabecalho("Evolução, " + ANOS[0] + "–" + ANOS[ANOS.length - 1] + (par ? " — em R$ e por matrícula" : " — " + ms[0].rotulo), {
    simples: par ? "Como o gasto de cada município escolhido mudou ano a ano: à esquerda o total em reais, à direita o gasto por aluno matriculado. Valores nominais, sem descontar a inflação."
      : ms[0].rotulo + ", ano a ano, para os municípios escolhidos.",
    nota: ms.map(m => m.nota).join(" "),
    fonte: { itens: () => estado.sel.flatMap(cod => ms.flatMap(m => ANOS.map(a => ({ indicador: indicadorDaMetrica(m), ano: a, detalhe: nomeEnte(cod) + ", " + a, q: qDaMetrica(m, cod, a) })))) } }));
  if (!estado.sel.length) { card.append(h("p", { class: "muted" }, "Escolha municípios no filtro \"Comparar\" para ver a evolução.")); return card; }
  card.append(legendaEntes(estado.sel));
  const grade = h("div", { class: par ? "par-graficos" : "" });
  const cs = cores();
  for (const m of ms) {
    const { cv, caixa } = areaGrafico("Evolução de " + m.rotulo + " para " + estado.sel.map(nomeEnte).join(", ") + ".");
    grade.append(h("div", {}, par ? h("h4", {}, m.curto) : null, caixa));
    if (temChart()) {
      const op = opcoesBase(cs, eixoY(m));
      op.plugins.tooltip.callbacks = { label: c => " " + c.dataset.label + ": " + fmtMetricaCheio(m, c.parsed.y) };
      setTimeout(() => desenhar("evol-" + m.campo, cv, { type: "line",
        data: { labels: ANOS, datasets: estado.sel.map(cod => serieLinha(nomeEnte(cod), ANOS.map(a => valorMetrica(m, cod, a)), estado.slot.get(cod))) },
        options: op, plugins: [plugCrosshair] }), 0);
    }
  }
  card.append(grade);
  const linhas = [];
  estado.sel.forEach(cod => ANOS.forEach(a => linhas.push({ cod, ano: a, r: LINHA.get(cod + "|" + a) || {} })));
  card.append(blocoTabela("evolução", [
    { rotulo: "Ente", valor: l => nomeEnte(l.cod) }, { rotulo: "Ano", valor: l => l.ano },
    ...ms.map(m => ({ rotulo: m.rotulo, num: true, valor: l => valorMetrica(m, l.cod, l.ano), fmt: v => fmtMetricaCheio(m, v) })),
    { rotulo: "Matrículas (rede municipal)", num: true, valor: l => l.r.tcees_alunos, fmt: nf },
    { rotulo: "População", num: true, valor: l => l.r.populacao, fmt: nf },
    { rotulo: "Situação da DCA", valor: l => l.r.status_dca || "sem linha" },
  ], linhas, "evolucao_" + estado.metrica + ".csv", { inicio: 0 }));
  return card;
}

/* ------------------------------------------------------ ranking */
/** Tipos de despesa (subfunções da função 12) que o ranking pode isolar, na ordem do
 *  catálogo (da maior para a menor no conjunto dos exercícios). "" = todas. */
const SUBFUNCOES_RANKING = new Map(CATALOGO_SUB.map(s => [s.codigo, s]));
const rotuloSubfuncao = codigo => codigo ? (SUBFUNCOES_RANKING.get(codigo) || {}).nome + " (" + codigo + ")" : "Todas as despesas em Educação (função 12)";
/** O indicador escolhido, restrito a uma subfunção. Devolve null quando o indicador não
 *  se desdobra por subfunção (a participação do FUNDEB é receita, não despesa). */
function metricaDaSubfuncao(m, codigo) {
  const nome = (SUBFUNCOES_RANKING.get(codigo) || {}).nome || ("subfunção " + codigo);
  const base = { nota: "Subfunção " + codigo + " (" + nome + ") da função 12, DCA Anexo I-E, empenhada. Município que não declarou a subfunção aparece como “sem dado”, não como 0. Valores nominais." };
  const v = medida => "__subv:" + codigo + ":" + medida;
  switch (m.campo) {
    case "desp_educacao_empenhada": return { ...base, rotulo: nome + " (R$, empenhada)", curto: "Em R$ (" + nome.toLowerCase() + ")", campo: v("empenhada"), tipo: "moeda" };
    case "desp_educacao_por_matricula": {
      const et = ETAPA_DA_SUBFUNCAO[codigo];
      return et ? { ...base, rotulo: nome + " por matrícula do " + et.etapa + " (R$/matrícula)", curto: "Por matrícula do " + et.etapa + " (R$/matrícula)", campo: v("pm"), tipo: "moeda2",
          nota: base.nota + " Dividido pelas matrículas do " + et.etapa + " na rede municipal, no Censo Escolar do mesmo ano (INEP; a soma de todas as etapas é a mesma base da coluna \"Alunos\" do TCE-ES). " +
            "Município sem matrícula nessa etapa fica sem dado. O numerador é a classificação do próprio município: gasto transversal lançado na subfunção infla o valor." }
        : { ...base, rotulo: nome + " por matrícula (R$/matrícula)", curto: "Por matrícula (R$/matrícula)", campo: v("pm"), tipo: "moeda2",
          nota: base.nota + " Dividido pelas matrículas da rede municipal no exercício (TCE-ES, conferidas contra o Censo) — todas as etapas, não só as da subfunção." };
    }
    case "desp_educacao_per_capita": return { ...base, rotulo: nome + " per capita (R$/hab.)", curto: "Per capita (R$/hab.)", campo: v("pc"), tipo: "moeda2",
      nota: base.nota + " Dividido pela população do exercício, como o SICONFI a reporta." };
    case "desp_educacao_pct_total": return { ...base, rotulo: nome + " em % da despesa total do ente", curto: "% da despesa total", campo: v("pct_total"), tipo: "pct",
      nota: base.nota + " Dividido pela despesa total empenhada do ente (exceto intra-orçamentárias)." };
    case "__sub:12.122": return { ...base, rotulo: nome + " em % da Educação", curto: nome + " (%)", campo: v("pct_educacao"), tipo: "pct" };
    default: return null;
  }
}
/** As métricas do ranking: as do indicador, ou as da subfunção escolhida. Quando o indicador
 *  não se desdobra por subfunção, cai no par R$ e por matrícula da subfunção, com aviso. */
function metricasRanking() {
  if (!estado.sub) return { ms: metricasPanorama(), aviso: null };
  const ms = metricasPanorama().map(m => metricaDaSubfuncao(m, estado.sub));
  if (ms.every(Boolean)) return { ms, aviso: null };
  return { ms: [METRICAS.desp, METRICAS.pm].map(m => metricaDaSubfuncao(m, estado.sub)),
    aviso: "O indicador “" + INDICADORES_PANORAMA[estado.metrica] + "” é uma participação da receita e não se desdobra por tipo de despesa: com um tipo escolhido, o ranking mostra o valor em R$ e por matrícula." };
}
function graficoRanking(m, ano, fatia, cv) {
  const cs = cores(), destacar = new Set(), cor = [];
  fatia.forEach((x, i) => { if (estado.sel.includes(x.cod)) { destacar.add(i); cor.push(cs.serie[estado.slot.get(x.cod)]); } else cor.push(cs.neutro); });
  const op = opcoesBase(cs, eixoY(m));
  op.indexAxis = "y"; op.interaction = { mode: "nearest", axis: "y", intersect: false };
  op.layout.padding.right = 84;
  op.scales.x = op.scales.y;
  op.scales.x.ticks = { ...op.scales.x.ticks, maxRotation: 0, autoSkip: true, maxTicksLimit: 5 };
  op.scales.y = { grid: { display: false }, border: { color: cs.axis }, ticks: { color: cs.ink2, font: { size: 12 }, autoSkip: false } };
  op.plugins.tooltip.callbacks = { title: i => fatia[i[0].dataIndex].pos + "º · " + fatia[i[0].dataIndex].nome, label: c => " " + fmtMetricaCheio(m, c.parsed.x) };
  op.plugins.rotulosSelecionados = { destacar, formatar: v => fmtMetrica(m, v) };
  const abrev = n => innerWidth < 600 && n.length > 15 ? n.slice(0, 14) + "…" : n;
  setTimeout(() => desenhar("rank-" + m.campo, cv, { type: "bar",
    data: { labels: fatia.map(x => abrev(x.nome)), datasets: [{ data: fatia.map(x => x.v), backgroundColor: cor, barThickness: 14,
      borderRadius: { topRight: 4, bottomRight: 4, topLeft: 0, bottomLeft: 0 }, borderSkipped: false }] },
    options: op, plugins: [plugRotulos] }), 0);
}
function cardRanking() {
  const { ms, aviso } = metricasRanking(), par = ms.length === 2, ano = estado.ano, sub = estado.sub;
  const nomeSub = sub ? (SUBFUNCOES_RANKING.get(sub) || {}).nome : null;
  const titulo = "Ranking dos municípios, " + ano + (sub ? " — " + nomeSub : "") + (par ? (sub ? ", " : " — ") + "em R$ e por matrícula" : "");
  const card = h("article", { class: "card largo", id: "card-ranking" }, cabecalho(titulo, {
    simples: (par ? "Os mesmos 78 municípios ordenados de duas formas: pelo total gasto (que acompanha o tamanho da rede) e pelo gasto por matrícula (que mede o esforço por aluno)."
      : "Os 78 municípios ordenados por " + ms[0].rotulo.toLowerCase() + ".") +
      (sub ? " Só a despesa em " + nomeSub.toLowerCase() + " (subfunção " + sub + "); quem não declarou essa subfunção fica fora do ranking." : "") + " Os escolhidos para comparação aparecem em cor.",
    nota: "Só municípios: o Estado fica de fora. " + ms.map(m => m.nota).join(" "),
    fonte: { itens: () => ms.map(m => ({ indicador: indicadorDaMetrica(m), ano,
      detalhe: sub ? sub + " - " + nomeSub + (etapaDaMetrica(m) ? " ÷ matrículas do " + etapaDaMetrica(m).etapa : "") : "os " + MUNICIPIOS.length + " municípios",
      observacao: sub ? "os " + MUNICIPIOS.length + " municípios" : null,
      q: MUNICIPIOS.map(e => qDaMetrica(m, e.cod_ibge, ano)).join(";") })) } }));
  const selSub = h("select", { id: "f-sub", onchange: e => ajustar({ sub: e.target.value }) },
    h("option", { value: "" }, rotuloSubfuncao("")), [...SUBFUNCOES_RANKING.keys()].map(c => h("option", { value: c }, rotuloSubfuncao(c))));
  selSub.value = sub;
  const sel = h("select", { id: "f-topo", onchange: e => ajustar({ topo: e.target.value }) },
    h("option", { value: "15" }, "15 maiores"), h("option", { value: "-15" }, "15 menores"), h("option", { value: "todos" }, "Todos"));
  sel.value = estado.topo;
  card.append(h("div", { class: "filtros-card" }, campo("Tipo de despesa", selSub), campo("Mostrar no gráfico", sel)));
  if (aviso) card.append(h("p", { class: "nota" }, aviso));
  const grade = h("div", { class: par ? "par-graficos" : "" });
  const porMetrica = new Map();
  for (const m of ms) {
    const com = MUNICIPIOS.map(e => ({ cod: e.cod_ibge, nome: e.nome, v: valorMetrica(m, e.cod_ibge, ano) })).filter(x => !nulo(x.v)).sort((a, b) => b.v - a.v);
    com.forEach((x, i) => { x.pos = i + 1; });
    porMetrica.set(m, new Map(com.map(x => [x.cod, x])));
    const fatia = estado.topo === "todos" ? com : estado.topo === "-15" ? com.slice(-15) : com.slice(0, 15);
    const { cv, caixa } = areaGrafico("Ranking de " + m.rotulo + " em " + ano + ", " + (estado.topo === "-15" ? "15 menores" : estado.topo === "todos" ? "todos" : "15 maiores") + ".");
    caixa.style.height = Math.max(200, fatia.length * 22 + 50) + "px";
    const posicoes = estado.sel.filter(c => ENTES.get(c).esfera === "M").map(c => { const x = porMetrica.get(m).get(c); return nomeEnte(c) + ": " + (x ? x.pos + "º de " + com.length : "sem dado"); });
    const et = etapaDaMetrica(m);
    grade.append(h("div", {}, par ? h("h4", {}, m.curto) : null,
      com.length ? caixa : h("p", { class: "muted" }, chipEstado("semdado"), " Nenhum município com dado em " + ano +
        (et ? ": a rede municipal não tem matrículas de " + et.etapa + " no Censo Escolar, então não há denominador." : ".")),
      posicoes.length ? h("p", { class: "nota" }, "Posição (1º = maior) — " + posicoes.join(" · ")) : null));
    if (temChart() && fatia.length) graficoRanking(m, ano, fatia, cv);
  }
  card.append(grade);
  const linhas = MUNICIPIOS.map(e => ({ cod: e.cod_ibge, nome: e.nome }));
  const cols = [{ rotulo: "Município", valor: l => l.nome, render: l => linkMunicipio(l.cod, "resumo", l.nome) },
    { rotulo: "Código IBGE", valor: l => l.cod }];
  for (const m of ms) {
    const mapa = porMetrica.get(m);
    cols.push({ rotulo: "Posição — " + m.curto, num: true, valor: l => (mapa.get(l.cod) || {}).pos, fmt: v => v + "º" },
      { rotulo: m.rotulo, num: true, valor: l => (mapa.get(l.cod) || {}).v, fmt: v => fmtMetricaCheio(m, v) });
  }
  if (sub) cols.push({ rotulo: nomeSub + " em % da Educação do município", num: true, fmt: v => nf(v, 2) + "%",
    valor: l => { const s = subDe(l.cod, ano).find(x => x.codigo === sub); return s ? s.pct_educacao : null; } });
  const etapaSub = sub ? ETAPA_DA_SUBFUNCAO[sub] : null;
  if (etapaSub) cols.push({ rotulo: "Matrículas do " + etapaSub.etapa + " (rede municipal, Censo)", num: true, valor: l => (LINHA.get(l.cod + "|" + ano) || {})[etapaSub.campo], fmt: nf });
  cols.push({ rotulo: "Matrículas (rede municipal, total)", num: true, valor: l => (LINHA.get(l.cod + "|" + ano) || {}).tcees_alunos, fmt: nf });
  const denominador = etapaSub ? "matrículas do " + etapaSub.etapa + " na rede municipal (Censo Escolar do mesmo ano)" : "total de matrículas da rede municipal (TCE-ES, conferido contra o Censo)";
  const arquivo = "ranking_" + estado.metrica + (sub ? "_" + sub.replace(".", "-") : "") + "_" + ano;
  const recorte = () => [["Painel", "Financiamento da educação no ES — Panorama do ES, ranking dos municípios"],
    ["Exercício", ano], ["Indicador", INDICADORES_PANORAMA[estado.metrica] || INDICADORES_PANORAMA.par],
    ["Tipo de despesa", rotuloSubfuncao(sub)], ["Denominador do \"por matrícula\"", denominador], ...(aviso ? [["Aviso", aviso]] : []),
    ["Colunas do ranking", ms.map(m => m.rotulo).join(" · ")],
    ["Mostrar no gráfico", (estado.topo === "-15" ? "15 menores" : estado.topo === "todos" ? "todos" : "15 maiores") + " (só no gráfico: a tabela e esta planilha trazem todos os municípios com dado)"],
    ["Municípios em comparação", estado.sel.length ? estado.sel.map(nomeEnte).join(", ") : "nenhum"],
    ["Abrangência", "Os " + MUNICIPIOS.length + " municípios do ES; o Estado fica de fora. Posição 1 = maior valor. Célula vazia = sem dado na fonte, nunca zero."],
    ["Fonte", "SICONFI, DCA Anexo I-E (função 12 e subfunções), despesa empenhada; matrículas da rede municipal: TCE-ES, conferidas contra o Censo Escolar" +
      (etapaSub ? "; matrículas por etapa: Censo Escolar (INEP), rede municipal, mesmo ano" : "") + ". Valores nominais."],
    ["Dados processados em", dataHoraBR(META.gerado_em) + (META.versao ? " (versão " + META.versao + ")" : "")],
    ["Exportado em", dataHoraBR(new Date().toISOString())]];
  card.append(blocoTabela("ranking completo", cols, linhas, arquivo + ".csv",
    { destacar: l => estado.sel.includes(l.cod), ordemInicial: { coluna: 2, direcao: "asc" }, busca: "Buscar município…", xlsx: arquivo + ".xlsx", recorte }));
  return card;
}

/* ------------------------------------------------------ execução bimestral */
function cardBimestral() {
  const ano = estado.ano, bims = [1, 2, 3, 4, 5, 6];
  const card = h("article", { class: "card largo", id: "card-bimestral" }, cabecalho("Execução ao longo de " + ano + " — despesa empenhada acumulada em Educação", {
    simples: "Quanto cada município escolhido já tinha empenhado em educação ao fim de cada bimestre do ano. Curva que só sobe no fim do ano indica gasto concentrado em novembro e dezembro.",
    nota: "RREO Anexo 02, valores acumulados até o bimestre (municípios pequenos publicam em \"RREO Simplificado\"). Bimestre sem publicação fica em branco. Em R$.",
    fonte: { itens: () => estado.sel.flatMap(cod => bims.map(b => BIM.get(cod + "|" + ano + "|" + b)).filter(Boolean)
      .map(x => ({ indicador: "empenhada_acum", ano, detalhe: String(x.bimestre), observacao: nomeEnte(cod) + " · " + x.tipo_rreo, q: x.q }))) } }));
  if (!estado.sel.length) { card.append(h("p", { class: "muted" }, "Escolha municípios no filtro \"Comparar\" para ver a execução no ano.")); return card; }
  const valorDe = (cod, b) => { const x = BIM.get(cod + "|" + ano + "|" + b); return x && !nulo(x.empenhada_acum) ? x.empenhada_acum : null; };
  const { cv, caixa } = areaGrafico("Despesa empenhada acumulada por bimestre em " + ano + ".");
  card.append(legendaEntes(estado.sel), caixa);
  if (temChart()) {
    const cs = cores(), op = opcoesBase(cs, tickMoeda);
    op.plugins.tooltip.callbacks = { label: c => " " + c.dataset.label + ": " + brl(c.parsed.y) };
    setTimeout(() => desenhar("bim", cv, { type: "line",
      data: { labels: bims.map(b => b + "º bimestre"), datasets: estado.sel.map(cod => serieLinha(nomeEnte(cod), bims.map(b => valorDe(cod, b)), estado.slot.get(cod))) },
      options: op, plugins: [plugCrosshair] }), 0);
  }
  const linhas = [];
  estado.sel.forEach(cod => bims.forEach(b => linhas.push({ cod, b, x: BIM.get(cod + "|" + ano + "|" + b) })));
  card.append(blocoTabela("execução bimestral", [
    { rotulo: "Ente", valor: l => nomeEnte(l.cod) }, { rotulo: "Bimestre", valor: l => l.b },
    { rotulo: "Tipo de RREO", valor: l => l.x ? l.x.tipo_rreo : null },
    { rotulo: "Dotação atualizada (R$)", num: true, valor: l => l.x && l.x.dotacao_atualizada, fmt: brl },
    { rotulo: "Empenhada acumulada (R$)", num: true, valor: l => l.x && l.x.empenhada_acum, fmt: brl },
    { rotulo: "Liquidada acumulada (R$)", num: true, valor: l => l.x && l.x.liquidada_acum, fmt: brl },
  ], linhas, "bimestral_" + ano + ".csv", { inicio: 0 }));
  return card;
}

/* ------------------------------------------------------ cobertura */
function cardCobertura() {
  const ano = estado.ano, mun = linhasMun(ano);
  const card = h("article", { class: "card largo", id: "card-cobertura" }, cabecalho("Cobertura dos dados — " + ano, {
    simples: "Quantos municípios têm cada tipo de dado neste exercício. Quem não tem é listado pelo nome — nunca omitido nem preenchido com zero." }));
  const rot = { sem_dado_publicado: "não publicou", falha_consulta: "falha na consulta", funcao_ausente: "sem a função Educação",
    sem_linha_fundeb: "sem linha de FUNDEB", nao_coletado: "não coletado", sem_pdf_publicado: "sem PDF publicado pelo FNDE",
    pdf_ilegivel: "PDF ilegível", parcial: "PDF lido em parte" };
  const item = (titulo, faltam) => h("li", {}, h("strong", {}, titulo + ": "), (mun.length - faltam.length) + " de " + mun.length +
    (faltam.length ? ". Sem dado: " + faltam.map(r => r.ente + " (" + (rot[r.status] || r.status || "sem linha") + ")").join("; ") + "." : " — nenhum município ausente."));
  const falta = (campo_) => mun.filter(r => r[campo_] !== "ok").map(r => ({ ...r, status: r[campo_] }));
  const semB6 = mun.filter(r => nulo(r.rreo_b6_empenhada)), incompleto = mun.filter(r => r.n_bimestres_rreo < 6);
  card.append(h("ul", { class: "lista" },
    item("DCA (despesa por função)", falta("status_dca")), item("FUNDEB (DCA Anexo I-C)", falta("status_fundeb")),
    item("MSC (natureza e fonte de recursos)", falta("status_msc")), item("SIOPE (Anexo 8 em PDF)", falta("status_siope")),
    h("li", {}, h("strong", {}, "RREO, 6º bimestre: "), (mun.length - semB6.length) + " de " + mun.length +
      (semB6.length ? ". Sem dado: " + semB6.map(r => r.ente).join("; ") + "." : " — nenhum município ausente.") +
      (incompleto.length ? " Com algum bimestre faltando: " + incompleto.length + "." : ""))));
  card.append(h("p", { class: "nota" }, "As conferências de qualidade dos dados (fechamento dos anexos, fontes que se confirmam) estão em ",
    linkPara({ v: "metodologia", ir: "qualidade" }, "Como ler e metodologia"), "."));
  return card;
}

function renderPanorama(destino) {
  destino.append(h("div", { class: "cab-visao" }, h("h2", {}, "Panorama do ES — " + estado.ano),
    h("p", {}, "Quanto os municípios gastam em educação, no que gastam e como se comparam. Os mínimos legais estão na ",
      linkPara({ v: "conformidade" }, "Conformidade"), "."), chipsComparacao()));
  destino.append(panoramaKPIs());
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" },
    cardNoQueSeGasta(), cardComparacao(), cardEvolucao(), cardRanking(), cardBimestral(), cardCobertura())));
}
