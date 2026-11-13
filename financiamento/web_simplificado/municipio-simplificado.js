"use strict";
/* ============================================================================
   Seções do painel simplificado — o dossiê do município numa página contínua:
   Resumo (com o fluxo fonte → subfunção em primeiro), Receita (com o detalhe
   de "outras receitas" quando pesam), Despesa e Quem recebeu.

   Os cards vêm do painel novo (web_novo/municipio.js e panorama.js), adaptados:
   sem mínimos constitucionais, sem entregas e remessas e sem os estágios
   liquidado/pago na visão por subfunção. Todos os números vêm dos dados abertos
   do TCE-ES (etl/simplificado.py); o exercício corrente entra parcial.
   ========================================================================== */

const ehMunicipio = cod => (ENTES.get(cod) || {}).esfera === "M";
const origemDe = (cod, ano) => Object.fromEntries((ORIGEM.get(chaveEA(cod, ano)) || []).map(o => [o.categoria, o]));
/** Receita do ano pelos grupos da natureza: a lente que permite abrir "outras receitas". */
const RECEITA_ANO = new Map(expandir(D.receita_anual).map(r => [chaveEA(r.cod_ibge, r.ano), r]));

/* ------------------------------------------------------ exercício parcial
   O exercício corrente entra com os meses que cada município já enviou ao
   TCE-ES. Ele fica fora das séries anuais (uma queda que é só falta de meses
   enganaria), compara-se com o mesmo período do ano anterior e só se ranqueia
   entre municípios que enviaram os mesmos meses. */
const ANO_PARCIAL = META.ano_parcial || null;
const ANOS_COMPLETOS = ANOS.filter(a => a !== ANO_PARCIAL);
const MES_CURTO = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MES_EXTENSO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const ehParcial = ano => ano === ANO_PARCIAL;
const ultimoMes = (cod, ano) => (LINHA.get(cod + "|" + ano) || {}).ultimo_mes;
/** "2026 (jan–set)" no exercício parcial; o ano sozinho nos demais. */
function rotuloAno(cod, ano) {
  const m = ultimoMes(cod, ano);
  return ehParcial(ano) && m ? ano + " (jan–" + MES_CURTO[m - 1] + ")" : String(ano);
}
/** Posição no ranking; no exercício parcial, só entre os municípios com os mesmos meses enviados. */
function posicaoComparavel(m, cod, ano) {
  if (!ehParcial(ano)) return posicaoNoRanking(m, cod, ano);
  const mes = ultimoMes(cod, ano);
  const com = MUNICIPIOS.filter(e => ultimoMes(e.cod_ibge, ano) === mes).map(e => ({ cod: e.cod_ibge, v: valorMetrica(m, e.cod_ibge, ano) }))
    .filter(x => !nulo(x.v)).sort((a, b) => b.v - a.v);
  const i = com.findIndex(x => x.cod === cod);
  return i < 0 ? null : { pos: i + 1, de: com.length, mes };
}
const fraseRankingComparavel = (p, oque) => !p ? "fora do ranking" :
  p.pos + "º maior " + oque + " entre " + p.de + " municípios" + (p.mes ? " com dados até " + MES_EXTENSO[p.mes - 1] : "");
// As notas das métricas do painel novo citam o demonstrativo do Tesouro; aqui a fonte é o TCE-ES.
METRICAS.desp.nota = "Despesa empenhada na função 12 (Educação), exceto intra-orçamentárias, como o município a informou ao TCE-ES. Valores nominais.";
METRICAS.pm.nota = "Despesa empenhada em Educação ÷ matrículas da rede municipal (coluna \"Alunos\" do recurso \"Educação\" do TCE-ES).";

/* --------------------------------------------- fontes de recursos nomeadas
   O dataset nomeia as fontes ligadas à educação (meta.nome_fonte). As demais —
   as que o painel completo soma em "outras fontes" — recebem aqui o nome curto
   da tabela padronizada da STN (Portaria STN nº 710/2021, atualizada até a
   Portaria nº 1.701/2025), para que uma fonte relevante, como os royalties em
   Presidente Kennedy, apareça nomeada no gráfico. Fora das duas listas, vale o
   nome que o próprio TCE-ES publica (meta.nome_fonte_tcees). */
const NOME_FONTE_STN = {
  "502": "Recursos não vinculados da compensação de impostos",
  "572": "Transferências de municípios — convênios vinculados à educação",
  "575": "Outros convênios e instrumentos congêneres vinculados à educação",
  "576": "Transferências dos estados para programas de educação",
  "669": "Outros recursos vinculados à assistência social",
  "700": "Outros convênios ou instrumentos congêneres da União",
  "701": "Outros convênios ou instrumentos congêneres dos estados",
  "704": "Compensações financeiras da União pela exploração de recursos naturais (royalties)",
  "705": "Compensações financeiras dos estados pela exploração de recursos naturais (royalties)",
  "706": "Transferência especial da União (emendas individuais, art. 166-A)",
  "708": "Compensação financeira de recursos minerais (CFEM)",
  "709": "Compensação financeira de recursos hídricos",
  "711": "Demais transferências obrigatórias não decorrentes de repartição de receitas",
  "715": "Transferências ao setor cultural — LC 195/2022 (audiovisual)",
  "716": "Transferências ao setor cultural — LC 195/2022 (demais setores)",
  "718": "Auxílio financeiro — outorga de crédito tributário de ICMS (EC 123/2022)",
  "720": "Participações da União na exploração de petróleo e gás (FEP, Lei 9.478/1997)",
  "721": "Cessão onerosa de petróleo (Lei 13.885/2019)",
  "749": "Outras vinculações de transferências",
  "750": "Contribuição de intervenção no domínio econômico (CIDE)",
  "751": "Contribuição para o custeio da iluminação pública (COSIP)",
  "753": "Taxas, contribuições e preços públicos vinculados",
  "754": "Recursos de operações de crédito",
  "755": "Alienação de bens e ativos — administração direta",
  "759": "Recursos vinculados a fundos",
  "799": "Outras vinculações legais",
  "899": "Outros recursos vinculados",
};
const nomeFonteSTN = f => (META.nome_fonte || {})[f] || NOME_FONTE_STN[f] || (META.nome_fonte_tcees || {})[f] || null;
/** Fonte de "outras" com ao menos esta fração da despesa do ano ganha nó próprio no fluxo. */
const LIMIAR_FONTE_RELEVANTE = 0.05;
/** "Outras receitas" com ao menos esta fração da receita total ganham o detalhamento. */
const LIMIAR_OUTRAS_RELEVANTES = 0.2;
/** Fontes do grupo "outras" que pesam e têm nome: [[fonte, valor], …], da maior para a menor.
 *  Usada pelo fluxo do Resumo. */
function fontesPromovidas(arestas) {
  const total = arestas.reduce((t, a) => t + a.empenhada, 0);
  const porFonte = new Map();
  for (const a of arestas) if (a.grupo === "outras") porFonte.set(a.fonte, (porFonte.get(a.fonte) || 0) + a.empenhada);
  return [...porFonte].filter(([f, v]) => v >= LIMIAR_FONTE_RELEVANTE * total && nomeFonteSTN(f)).sort((a, b) => b[1] - a[1]);
}

/** Dobra sob um <details> a primeira tabela aberta de um card compartilhado
 *  (nivel3.js), opcionalmente pondo um gráfico no lugar dela. O pedido desta
 *  versão prioriza gráficos: a tabela continua ali, completa, mas recolhida. */
function priorizarGrafico(card, resumo, grafico) {
  // Enxugamento: a conferência que BATE (callout neutro) e a menção a arquivos do
  // conjunto de dados, que não acompanham este protótipo, saem do card. O que
  // diverge (callout de sinal) continua.
  for (const c of card.querySelectorAll(":scope > .callout:not(.sinal)")) c.remove();
  for (const p of card.querySelectorAll(":scope > p.nota")) if (/\.csv\b/.test(p.textContent)) p.remove();
  const bloco = card.querySelector(":scope > .tabela-bloco");
  if (!bloco) return card;
  const det = h("details", { class: "tab" }, h("summary", {}, resumo));
  bloco.replaceWith(det);
  if (grafico) det.before(grafico);
  det.append(bloco);
  return card;
}

/* ------------------------------------------------- subfunções (sem estágios)
   A pedido do leiaute simplificado, a visão por subfunção traz só a despesa
   empenhada — sem as colunas de liquidado e pago. */
const COLUNAS_SUB = [
  { rotulo: "Código", valor: i => i.codigo },
  { rotulo: "Subfunção", valor: i => i.nome },
  { rotulo: "Despesa (R$)", num: true, valor: i => i.empenhada, fmt: brl },
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

/* ================================================================ resumo */
function emResumo(cod, ano, r) {
  const nome = nomeEnte(cod);
  if (nulo(r.desp_educacao_empenhada)) return h("p", { class: "em-resumo" }, "O TCE-ES não publicou despesa em Educação de " + nome + " em " + ano + ". Nada é estimado.");
  const quando = ehParcial(ano) && r.ultimo_mes ? "de janeiro a " + MES_EXTENSO[r.ultimo_mes - 1] + " de " + ano : "em " + ano;
  let frase = nome + " empenhou " + brlCompacto(r.desp_educacao_empenhada) + " em Educação " + quando;
  if (!nulo(r.desp_educacao_pct_total)) frase += " — " + nf(r.desp_educacao_pct_total, 1) + "% de toda a sua despesa";
  if (!nulo(r.desp_educacao_por_matricula)) frase += ", ou " + brl(r.desp_educacao_por_matricula) + " por matrícula da rede municipal";
  return h("p", { class: "em-resumo" }, frase + ".");
}
function fichaKPIs(cod, ano, r) {
  const mun = ehMunicipio(cod), box = h("div", { class: "kpis" });
  const pos = m => mun ? posicaoComparavel(m, cod, ano) : null;
  box.append(kpi("Despesa em Educação, " + rotuloAno(cod, ano), nulo(r.desp_educacao_empenhada) ? "sem dado" : brlCompacto(r.desp_educacao_empenhada),
    "empenhada, função 12" + (mun ? " · " + fraseRankingComparavel(pos(METRICAS.desp), "gasto total") : ""), { nd: nulo(r.desp_educacao_empenhada) }));
  box.append(kpi("Por matrícula", nulo(r.desp_educacao_por_matricula) ? "sem dado" : brl(r.desp_educacao_por_matricula),
    (nulo(r.tcees_alunos) ? "sem matrículas na fonte" : nf(r.tcees_alunos) + " matrículas na rede municipal") +
      (mun && !nulo(r.desp_educacao_por_matricula) ? " · " + fraseRankingComparavel(pos(METRICAS.pm), "gasto por matrícula") : ""), { nd: nulo(r.desp_educacao_por_matricula) }));
  // No exercício parcial, a comparação é com os mesmos meses do ano anterior.
  const ant = LINHA.get(cod + "|" + (ano - 1));
  const base = ehParcial(ano) ? r.desp_educacao_empenhada_ant_periodo : ant && ant.desp_educacao_empenhada;
  const periodo = ehParcial(ano) && r.ultimo_mes ? " (jan–" + MES_CURTO[r.ultimo_mes - 1] + ")" : "";
  if (!nulo(base) && base > 0 && !nulo(r.desp_educacao_empenhada))
    box.append(kpi("Variação, " + (ano - 1) + periodo + " → " + ano + periodo, variacao(100 * (r.desp_educacao_empenhada - base) / base),
      "nominal, sem descontar a inflação · de " + brlCompacto(base)));
  else box.append(kpi("Variação anual", "—", ANOS.includes(ano - 1) ? "sem dado em " + (ano - 1) : ano + " é o primeiro exercício da série", { nd: true }));
  return box;
}

/** Fluxo fonte de recursos → subfunção. Primeiro item do Resumo; as fontes
 *  relevantes de "outras" aparecem com nome próprio em vez de somadas. */
function cardFluxo(cod, ano) {
  const r = LINHA.get(cod + "|" + ano) || {}, nome = nomeEnte(cod), arestas = FLUXO.get(chaveEA(cod, ano)) || [];
  const card = h("article", { class: "card largo", id: "card-fluxo" }, cabecalhoEnxuto("Com que dinheiro, para qual etapa: fonte de recursos → subfunção — " + nome + ", " + rotuloAno(cod, ano), {
    simples: "Cada faixa liga a origem do dinheiro (à esquerda) à etapa de ensino em que foi gasto (à direita); a largura é o valor. Passe o ponteiro sobre uma faixa para ver o valor.",
    nota: "Cada empenho da função 12 carrega a fonte de recursos que o paga, como o município a informou ao TCE-ES. É a ligação declarada pelo próprio município — não uma estimativa proporcional. A fonte 500 junta impostos próprios e transferências de impostos: a contabilidade não os separa. Os nomes das fontes seguem a tabela padronizada da STN (Portaria STN nº 710/2021, atualizada).",
    limitacao: "Fluxo fonte",
    fonte: { itens: () => [{ indicador: "fluxo_fonte_subfuncao", ano, detalhe: "todas as fontes e subfunções", q: r.q_despesa, valor: brl(arestas.reduce((t, a) => t + a.empenhada, 0)) }] } }));
  if (!arestas.length) {
    const motivo = r.fontes === "local" ? "Em " + ano + " os dados do TCE-ES trazem os códigos de fonte anteriores à padronização nacional, que nos dados do Tribunal vale a partir de 2023: não há tradução segura, então o fluxo não é desenhado."
      : "O TCE-ES não publicou despesa da função 12 deste município em " + ano + ".";
    card.append(h("p", {}, chipEstado("semdado"), " " + motivo));
    return card;
  }
  const grupos = META.grupos_fonte || {}, rotuloGrupo = g => (grupos[g] || g).replace(/ \(fontes? [^)]*\)/, "");
  // Fontes de "outras" que pesam: cada uma vira uma origem própria, nomeada; o
  // resto continua agregado. Fonte sem nome conhecido não é promovida — rótulo
  // inventado seria pior que "demais fontes".
  const promovidas = fontesPromovidas(arestas).map(([f]) => f);
  const setPromovidas = new Set(promovidas);
  const idOrigem = a => a.grupo === "outras" && setPromovidas.has(a.fonte) ? "f:" + a.fonte : a.grupo;
  const origens = ORDEM_GRUPO.filter(g => g !== "outras").map(g => ({ id: g, rotulo: rotuloGrupo(g), slot: SLOT_ORIGEM[g] }))
    .concat(promovidas.map(f => ({ id: "f:" + f, rotulo: f + " — " + nomeFonteSTN(f), slot: SLOT_ORIGEM.outras })))
    .concat([{ id: "outras", rotulo: promovidas.length ? "Demais fontes de \"outras\"" : rotuloGrupo("outras"), slot: SLOT_ORIGEM.outras }]);
  const somaSub = sf => arestas.filter(a => a.subfuncao === sf).reduce((t, a) => t + a.empenhada, 0);
  const destinos = [...new Set(arestas.map(a => a.subfuncao))].sort((a, b) => somaSub(b) - somaSub(a)).map(sf => ({ id: sf, rotulo: nomeSubfuncao(sf) }));
  const porOrigem = new Map();
  arestas.forEach(a => { const k = idOrigem(a) + "|" + a.subfuncao; porOrigem.set(k, (porOrigem.get(k) || 0) + a.empenhada); });
  const links = [...porOrigem].map(([k, v]) => ({ de: k.split("|")[0], para: k.split("|")[1], valor: v }));
  card.append(h("div", { class: "grafico-svg" }, redesenhavel(() => sankey({ origens, destinos, arestas: links, formatar: brlCompacto, titulo: "Fluxo fonte → subfunção de " + nome }))));
  card.append(legendaSlots(origens.map(o => ({ rotulo: o.rotulo, slot: o.slot }))));
  if (promovidas.length) card.append(h("p", { class: "nota" }, "As fontes nomeadas com código à esquerda pertencem ao grupo \"outras\" e aparecem separadas por pesarem ao menos " +
    nf(100 * LIMIAR_FONTE_RELEVANTE, 0) + "% da despesa do ano: " + promovidas.map(f => f + " — " + nomeFonteSTN(f)).join("; ") + "."));
  card.append(blocoTabela("fonte × subfunção", [
    { rotulo: "Fonte de recursos", valor: a => a.fonte + " — " + (nomeFonteSTN(a.fonte) || "fonte " + a.fonte) },
    { rotulo: "Grupo", valor: a => rotuloGrupo(a.grupo).split(" (")[0] },
    { rotulo: "Subfunção", valor: a => a.subfuncao + " — " + nomeSubfuncao(a.subfuncao) },
    { rotulo: "Empenhado (R$)", num: true, valor: a => a.empenhada, fmt: brl },
  ], arestas.slice().sort((a, b) => ORDEM_GRUPO.indexOf(a.grupo) - ORDEM_GRUPO.indexOf(b.grupo) || b.empenhada - a.empenhada), "fluxo_" + cod + "_" + ano + ".csv", { inicio: 0 }));
  return card;
}

function secaoResumo(destino, cod, ano, r) {
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" }, cardFluxo(cod, ano))),
    emResumo(cod, ano, r), fichaKPIs(cod, ano, r));
}

/* ================================================================ receita */
function cardOrigemReceita(cod, ano) {
  const o = origemDe(cod, ano), total = o.total && o.total.valor, nome = nomeEnte(cod);
  const card = h("article", { class: "card largo", id: "card-origem" }, cabecalhoEnxuto("De onde vem a receita — " + nome + ", " + rotuloAno(cod, ano), {
    nota: "Receita arrecadada no ano (exceto intra-orçamentária), como o município a informou ao TCE-ES, em quatro origens que não se sobrepõem, separadas pela natureza da receita. \"Outras\" é calculada por diferença.",
    limitacao: "Outras receitas",
    fonte: { itens: () => ORDEM_ORIGEM.concat(["total"]).filter(c => o[c]).map(c => ({ indicador: c === "total" ? "receita_total" : "origem_receita", ano,
      detalhe: c === "total" ? null : (META.origens[c] || {}).rotulo, q: o[c].q, valor: nulo(o[c].valor) ? null : brl(o[c].valor),
      observacao: c === "total" ? null : "fonte: " + o[c].fonte + " — " + (META.origens[c] || {}).localizacao })) } }));
  if (nulo(total)) { card.append(h("p", {}, chipEstado("semdado"), " O TCE-ES não publicou a receita de " + nome + " em " + ano + ".")); return card; }
  const partes = ORDEM_ORIGEM.map(c => ({ rotulo: (META.origens[c] || {}).rotulo || c, valor: o[c] ? o[c].valor : null, slot: SLOT_ORIGEM[c], c }));
  card.append(barra100(partes, brl), legendaSlots(partes.map(p => ({ rotulo: p.rotulo.split(" (")[0], slot: p.slot }))));
  card.append(blocoTabela("origem da receita", [
    { rotulo: "Origem", valor: p => p.rotulo },
    { rotulo: "Valor (R$)", num: true, valor: p => p.valor, fmt: brl },
    { rotulo: "% da receita", num: true, valor: p => nulo(p.valor) ? null : 100 * p.valor / total, fmt: v => nf(v, 1) + "%" },
    { rotulo: "Fonte do número", valor: p => o[p.c] ? o[p.c].fonte : "" },
  ], partes, "origem_" + cod + "_" + ano + ".csv", { inicio: 0, busca: false, fixarPrimeira: false, rodape: ["Receita total", brl(total), "100%", "TCE-ES — Receitas dos municípios"] }));
  if (o.outras && o.outras.valor < 0) card.append(h("div", { class: "callout sinal" }, "As parcelas somam mais que a receita total: as fontes não fecham entre si para este município. É sinal a verificar."));
  const detalhe = detalheOutrasReceitas(cod, ano, o, total);
  if (detalhe) card.append(detalhe);
  return card;
}
/** O que há dentro de "outras receitas", quando elas pesam: as parcelas que a
 *  natureza da receita permite separar sem estimativa. */
function detalheOutrasReceitas(cod, ano, o, total) {
  const outras = o.outras && o.outras.valor;
  if (nulo(outras) || outras <= 0 || outras / total < LIMIAR_OUTRAS_RELEVANTES) return null;
  const rb = RECEITA_ANO.get(chaveEA(cod, ano));
  const fundeb = o.fundeb && o.fundeb.valor, fnde = o.federal_especifica && o.federal_especifica.valor;
  if (!rb || nulo(rb.transferencias_correntes) || nulo(fundeb) || nulo(fnde)) return null;
  const tcorr = rb.transferencias_correntes - fundeb - fnde;
  const tcap = rb.transferencias_capital || 0;
  const demais = outras - tcorr - tcap;
  const bloco = h("div", { class: "subbloco" }, h("h4", {}, "Dentro de \"outras receitas\" — " + nf(100 * outras / total, 1) + "% da receita do ano"));
  if (tcorr < 0 || demais < -1) {
    bloco.append(h("div", { class: "callout sinal" }, "As parcelas da receita não fecham com as quatro origens para este município (diferença de " + brl(Math.min(tcorr, demais)) + "). O detalhamento não é mostrado para não somar errado. É sinal a verificar."));
    return bloco;
  }
  const linhas = [
    { rotulo: "Transferências correntes além do FUNDEB e do FNDE — FPM, cotas de ICMS e IPVA, royalties e compensações, SUS e outras", valor: tcorr, como: "Transferências correntes (natureza 1.7) menos FUNDEB e FNDE" },
    { rotulo: "Transferências de capital — convênios e repasses para obras e equipamentos", valor: tcap, como: "Natureza 2.4, linha própria" },
    { rotulo: "Receitas do próprio município fora de impostos — taxas, contribuições, patrimoniais e aplicações, serviços", valor: demais, como: "Diferença (o que resta de \"outras\")" },
  ];
  bloco.append(barrasHorizontais(linhas.map(l => ({ nome: l.rotulo.split(" — ")[0], codigo: nf(100 * l.valor / total, 1) + "% da receita do ano", valor: l.valor })), outras,
    { rotulo: "Dentro de outras receitas" }));
  bloco.append(blocoTabela("dentro de \"outras receitas\"", [
    { rotulo: "Parcela", valor: l => l.rotulo, classe: "col-nome" },
    { rotulo: "Valor (R$)", num: true, valor: l => l.valor, fmt: brl },
    { rotulo: "% da receita", num: true, valor: l => 100 * l.valor / total, fmt: v => nf(v, 1) + "%" },
    { rotulo: "Como foi separada", valor: l => l.como },
  ], linhas, "outras_receitas_" + cod + "_" + ano + ".csv", { inicio: 0, busca: false, fixarPrimeira: false }));
  bloco.append(h("p", { class: "nota" }, "Das transferências correntes do ano (" + brl(rb.transferencias_correntes) + "), " +
    (nulo(rb.transf_correntes_uniao) ? "" : brlCompacto(rb.transf_correntes_uniao) + " vieram da União, ") +
    (nulo(rb.transf_correntes_estados) ? "" : brlCompacto(rb.transf_correntes_estados) + " do Estado ") +
    (nulo(rb.transf_correntes_outras_publicas) ? "" : "e " + brlCompacto(rb.transf_correntes_outras_publicas) + " de outras instituições públicas (estas incluem o FUNDEB)") + "."),
    h("p", {}, botaoFonte("Dentro de outras receitas — " + nomeEnte(cod) + ", " + ano, () => [
      { indicador: "receita_natureza", ano, detalhe: "transferências correntes (1.7)", q: rb.q, valor: brl(rb.transferencias_correntes) },
      { indicador: "receita_natureza", ano, detalhe: "transferências de capital (2.4)", q: rb.q, valor: brl(tcap) },
      { indicador: "origem_receita", ano, detalhe: (META.origens.fundeb || {}).rotulo, q: o.fundeb.q, valor: brl(fundeb) },
      { indicador: "origem_receita", ano, detalhe: (META.origens.federal_especifica || {}).rotulo, q: o.federal_especifica.q, valor: brl(fnde) },
    ])));
  return bloco;
}
function secaoReceita(destino, cod, ano, r) {
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" }, cardOrigemReceita(cod, ano))));
}

/* ================================================================ despesa */
function cardSubfuncoes(cod, ano, r) {
  const itens = subDe(cod, ano);
  const card = h("article", { class: "card largo", id: "card-subfuncoes" }, cabecalhoEnxuto("No que foi gasto — Educação por subfunção, " + rotuloAno(cod, ano), {
    nota: "Despesa empenhada: detalhe da função 12 que o município informou ao TCE-ES (Nível 1). As subfunções somam exatamente a despesa em Educação.",
    limitacao: "Despesa",
    fonte: { itens: () => itens.map(i => ({ indicador: "subfuncao_empenhada", ano, detalhe: i.codigo + " - " + i.nome, q: i.q, valor: brl(i.empenhada) }))
      .concat([{ indicador: "desp_educacao_empenhada", ano, q: r.q_despesa, valor: nulo(r.desp_educacao_empenhada) ? null : brl(r.desp_educacao_empenhada) }]) } }));
  if (!itens.length) { card.append(h("p", {}, chipEstado("semdado"), " O TCE-ES não publicou despesa por subfunção deste município em " + ano + ".")); return card; }
  const total = r.desp_educacao_empenhada || itens.reduce((t, i) => t + (i.empenhada || 0), 0);
  card.append(barrasSubfuncao(itens, total, ehMunicipio(cod)));
  const fora = ehMunicipio(cod) ? itens.filter(i => SUB_FORA_DA_PRIORIDADE.has(i.codigo)) : [];
  const admin = itens.find(i => i.codigo === SUB_ADMINISTRACAO);
  if (fora.length) card.append(notaForaPrioridade());
  if (admin) card.append(h("p", { class: "nota" }, "Administração geral concentra " + nf(admin.pct_educacao, 1) + "% da despesa em Educação (" + brlCompacto(admin.empenhada) + ")."));
  card.append(blocoTabela("subfunções", COLUNAS_SUB, itens, "subfuncoes_" + cod + "_" + ano + ".csv", { inicio: 0, busca: false,
    rodape: ["", "Total da função 12", brl(total), "100%"] }));
  return card;
}
/** A série anual vai até o último exercício completo; o parcial só no próprio exercício. */
function notaSemParcial() {
  return ANO_PARCIAL ? h("p", { class: "nota" }, "A série vai até " + ANOS_COMPLETOS[ANOS_COMPLETOS.length - 1] + ": " + ANO_PARCIAL +
    " ainda está em andamento e aparece ao escolher o exercício no menu.") : null;
}
function cardMatrizSubfuncoes(cod) {
  const anos = ANOS_COMPLETOS, anoRef = ehParcial(estado.ano) ? anos[anos.length - 1] : estado.ano;
  const card = h("article", { class: "card largo", id: "card-matriz-sub" }, cabecalhoEnxuto("Subfunção por exercício — despesa empenhada", {
    fonte: { itens: () => anos.map(a => ({ indicador: "subfuncao_empenhada", ano: a, detalhe: "todas as subfunções, " + a, q: (LINHA.get(cod + "|" + a) || {}).q_despesa })) } }));
  const codigos = new Map();
  for (const a of anos) for (const sf of subDe(cod, a)) if (!codigos.has(sf.codigo)) codigos.set(sf.codigo, sf.nome);
  if (!codigos.size) { card.append(h("p", {}, chipEstado("semdado"), " Sem detalhe por subfunção em nenhum exercício carregado.")); return card; }
  const valor = (codigo, a) => { const sf = subDe(cod, a).find(x => x.codigo === codigo); return sf ? sf.empenhada : null; };
  const linhas = [...codigos].map(([codigo, nome]) => ({ codigo, nome })).sort((a, b) => (valor(b.codigo, anoRef) || 0) - (valor(a.codigo, anoRef) || 0));
  // O gráfico leva as maiores subfunções (uma cor e uma forma por série); a
  // matriz completa fica na tabela dobrada logo abaixo.
  const topo = linhas.slice(0, FORMAS.length), cs = cores();
  const g = areaGrafico("Evolução das maiores subfunções de " + nomeEnte(cod) + ".", "baixo");
  card.append(legendaSeries(topo.map((l, i) => ({ cor: cs.serie[i], forma: FORMAS[i], rotulo: l.codigo + " — " + l.nome }))), g.caixa);
  if (temChart()) {
    const op = opcoesBase(cs, tickMoeda);
    op.plugins.tooltip.callbacks = { title: i => "Exercício " + i[0].label, label: c => " " + c.dataset.label + ": " + brl(c.parsed.y) };
    setTimeout(() => desenhar("simp-matriz-" + cod, g.cv, { type: "line",
      data: { labels: anos, datasets: topo.map((l, i) => serieLinha(l.codigo + " — " + l.nome, anos.map(a => valor(l.codigo, a)), i)) },
      options: op, plugins: [plugCrosshair] }), 0);
  }
  if (linhas.length > topo.length) card.append(h("p", { class: "nota" }, "O gráfico traz as " + topo.length + " maiores subfunções de " + anoRef + "; todas estão na tabela."));
  const nota = notaSemParcial();
  if (nota) card.append(nota);
  const colunas = [{ rotulo: "Subfunção", valor: l => l.codigo + " — " + l.nome }].concat(anos.map(a => ({
    rotulo: String(a), num: true, valor: l => valor(l.codigo, a), render: l => { const v = valor(l.codigo, a); return nulo(v) ? h("span", { class: "muted" }, "—") : brlCompacto(v); }, csv: l => valor(l.codigo, a) })));
  card.append(blocoTabela("subfunção por exercício", colunas, linhas, "subfuncoes_serie_" + cod + ".csv", { inicio: 0, busca: false,
    rodape: ["Total da Educação"].concat(anos.map(a => { const x = LINHA.get(cod + "|" + a); return x && !nulo(x.desp_educacao_empenhada) ? brlCompacto(x.desp_educacao_empenhada) : "—"; })) }));
  return card;
}
function cardEvolucaoMunicipio(cod) {
  const anos = ANOS_COMPLETOS;
  const mun = ehMunicipio(cod), linhas = anos.map(a => ({ ano: a, r: LINHA.get(cod + "|" + a) || {} }));
  const card = h("article", { class: "card largo", id: "card-evolucao-mun" }, cabecalhoEnxuto("Evolução da despesa em Educação, " + anos[0] + "–" + anos[anos.length - 1], {
    limitacao: "Por matrícula",
    fonte: { itens: () => anos.map(a => { const x = LINHA.get(cod + "|" + a) || {}; return { indicador: "desp_educacao_empenhada", ano: a, detalhe: String(a), q: x.q_despesa,
      valor: nulo(x.desp_educacao_empenhada) ? null : brl(x.desp_educacao_empenhada) }; }) } }));
  const ms = mun ? [METRICAS.desp, METRICAS.pm] : [METRICAS.desp];
  const grade = h("div", { class: ms.length === 2 ? "par-graficos" : "" }), cs = cores();
  for (const m of ms) {
    const g = areaGrafico("Evolução de " + m.rotulo + " de " + nomeEnte(cod) + ".", "baixo");
    grade.append(h("div", {}, h("h4", {}, m.curto), g.caixa));
    if (temChart()) {
      const op = opcoesBase(cs, eixoY(m));
      op.plugins.tooltip.callbacks = { title: i => "Exercício " + i[0].label, label: c => " " + fmtMetricaCheio(m, c.parsed.y) };
      setTimeout(() => desenhar("mun-evol-" + m.campo, g.cv, { type: "line", data: { labels: anos, datasets: [serieLinha(m.curto, linhas.map(l => l.r[m.campo]), 0)] },
        options: op, plugins: [plugCrosshair] }), 0);
    }
  }
  card.append(grade);
  const nota = notaSemParcial();
  if (nota) card.append(nota);
  card.append(blocoTabela("evolução", [
    { rotulo: "Ano", valor: l => l.ano },
    { rotulo: "Empenhada (R$)", num: true, valor: l => l.r.desp_educacao_empenhada, fmt: brl },
    { rotulo: "Matrículas (rede municipal)", num: true, valor: l => l.r.tcees_alunos, fmt: nf },
    { rotulo: "Por matrícula (R$)", num: true, valor: l => l.r.desp_educacao_por_matricula, fmt: brl },
    { rotulo: "% da despesa do município", num: true, valor: l => l.r.desp_educacao_pct_total, fmt: v => nf(v, 2) + "%" },
  ], linhas, "evolucao_" + cod + ".csv", { inicio: 0, busca: false, destacar: l => l.ano === estado.ano }));
  return card;
}
function cardNatureza(cod, ano) {
  const r = LINHA.get(cod + "|" + ano) || {}, nome = nomeEnte(cod), linhas = NATUREZA.get(chaveEA(cod, ano)) || [];
  const card = h("article", { class: "card largo", id: "card-natureza" }, cabecalhoEnxuto("Com o quê: pessoal, custeio e investimento — " + nome + ", " + rotuloAno(cod, ano), {
    nota: "Natureza econômica de cada empenho da função 12, como o município a informou ao TCE-ES (Nível 2): categoria pelo grupo da natureza de despesa e pelo elemento.",
    fonte: { itens: () => [{ indicador: "natureza_economica", ano, detalhe: "categoria pelo grupo e pelo elemento", q: r.q_despesa, valor: brl(linhas.reduce((t, l) => t + l.empenhada, 0)) }] } }));
  if (!linhas.length) { card.append(h("p", {}, chipEstado("semdado"), " O TCE-ES não publicou despesa deste município em " + ano + ".")); return card; }
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
  ], linhas.slice().sort((a, b) => b.empenhada - a.empenhada), "natureza_" + cod + "_" + ano + ".csv", { inicio: 0, rodape: ["", "", "Total", brl(total)] }));
  return card;
}
function secaoDespesa(destino, cod, ano, r) {
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" },
    cardSubfuncoes(cod, ano, r), cardEvolucaoMunicipio(cod), cardMatrizSubfuncoes(cod), cardNatureza(cod, ano))));
}

/* ================================== quem recebeu e o que foi comprado */
/** Repasses do município a conselhos escolares, em card de destaque: gráfico,
 *  quadros-resumo e a escola do Censo quando o nome permite a ligação. */
function cardConselhosEscolares(cod, ano) {
  const nome = nomeEnte(cod);
  const linhas = (CONSELHOS_EA.get(chaveEA(cod, ano)) || []).slice().sort((a, b) => b.empenhada - a.empenhada);
  const card = h("article", { class: "card largo", id: "card-conselhos-simp" }, cabecalhoEnxuto("Para qual escola: repasses do município a conselhos escolares — " + nome + ", " + ano, {
    simples: "Dinheiro do próprio município entregue diretamente às escolas, por meio dos conselhos ou caixas escolares. É o trecho do gasto que chega nomeado a uma escola.",
    nota: "Identificado pelo credor do empenho. A escola é ligada ao Censo Escolar pelo nome; o que é ambíguo fica sem vínculo.",
    limitacao: "Conselhos",
    fonte: { itens: () => linhas.map(c => ({ indicador: "repasse_conselho_escolar", ano, detalhe: c.credor + " — " + c.credor_nome, q: c.q, valor: brl(c.empenhada) })) } }));
  if (!EMPENHOS_COLETADOS) { card.append(avisoEmpenhos()); return card; }
  if (!linhas.length) { card.append(h("p", {}, "Nenhum empenho a conselho escolar, caixa escolar ou associação de escola em " + ano + ". O município pode não ter programa próprio de repasse às escolas.")); return card; }
  const total = linhas.reduce((t, c) => t + c.empenhada, 0);
  const vinc = c => VINCULO_POR_ORIGEM.get("conselho|" + cod + "|" + c.credor);
  const escolaDe = c => { const v = vinc(c); return v && v.co_entidade ? (ESCOLAS.get(v.co_entidade) || {}).nome || "" : ""; };
  const comEscola = linhas.filter(c => escolaDe(c)).length;
  card.append(h("div", { class: "kpis" },
    kpi("Repassado a conselhos, " + ano, brlCompacto(total), "empenhos do município a conselhos e caixas escolares"),
    kpi("Conselhos", nf(linhas.length), "credores identificados como conselho ou caixa escolar"),
    kpi("Ligados a uma escola do Censo", nf(comEscola) + " de " + nf(linhas.length), "ligação pelo nome; o ambíguo fica sem vínculo")));
  // O dinheiro chega à escola: ela é o rótulo. O nome do conselho, que em geral
  // repete o da escola, fica só na tabela; aparece no gráfico apenas quando a
  // escola não foi identificada.
  const rotuloDe = c => escolaDe(c) || c.credor_nome;
  const barras = linhas.map(c => ({ nome: rotuloDe(c), codigo: escolaDe(c) ? null : "escola não identificada", valor: c.empenhada }));
  card.append(graficoComMais(barras, total, { rotulo: "Repasses por escola", inicio: LINHAS_INICIAIS_CONSELHOS, unidade: "conselhos" }));
  card.append(blocoTabela("repasses a conselhos escolares", [
    { rotulo: "Escola", valor: rotuloDe, classe: "col-nome", render: c => escolaDe(c) ||
      h("span", {}, c.credor_nome, " ", h("span", { class: "muted", title: (vinc(c) || {}).metodo || "" }, "(escola não identificada)")) },
    { rotulo: "Conselho, como no empenho", valor: c => c.credor_nome },
    { rotulo: "Empenhado (R$)", num: true, valor: c => c.empenhada, fmt: brl },
    { rotulo: "Pago (R$)", num: true, valor: c => c.paga, fmt: brl },
    { rotulo: "% do repassado", num: true, valor: c => total ? 100 * c.empenhada / total : null, fmt: v => nf(v, 1) + "%" },
  ], linhas, "conselhos_" + cod + "_" + ano + ".csv", { inicio: LINHAS_INICIAIS_CONSELHOS }));
  return card;
}
const LINHAS_INICIAIS_CONSELHOS = 10;
/** Barras horizontais que mostram só as `inicio` maiores, com a soma do resto
 *  numa linha de texto (não numa barra: ela achataria as demais) e o botão
 *  "Mostrar todos" / "Mostrar menos". Os itens chegam ordenados do maior ao menor. */
function graficoComMais(itens, total, o) {
  const caixa = h("div", { class: "barras-com-mais" });
  let aberto = false;
  const desenhar = () => {
    const resto = itens.slice(o.inicio), mostrados = aberto || !resto.length ? itens : itens.slice(0, o.inicio);
    const somaResto = resto.reduce((t, i) => t + (i.valor || 0), 0);
    limpar(caixa).append(barrasHorizontais(mostrados, total, { rotulo: o.rotulo }));
    if (!resto.length) return;
    if (!aberto) caixa.append(h("p", { class: "nota demais" }, h("strong", {}, "Demais " + nf(resto.length) + " " + o.unidade + ": "),
      brlCompacto(somaResto) + (total > 0 ? " · " + nf(100 * somaResto / total, 1) + "% do repassado" : "") + "."));
    caixa.append(h("div", { class: "acoes-tabela" }, h("button", { type: "button", class: "leve", "aria-expanded": String(aberto),
      onclick: () => { aberto = !aberto; desenhar(); } }, aberto ? "Mostrar menos" : "Mostrar todos os " + nf(itens.length))));
  };
  desenhar();
  return caixa;
}
/** Tira de um card compartilhado (nivel3.js) a frase simples do cabeçalho e as
 *  notas cujo texto começa por um dos prefixos dados. */
function semTextos(card, { simples, notas } = {}) {
  if (simples) for (const p of card.querySelectorAll(".cab-card p.simples")) p.remove();
  for (const p of card.querySelectorAll(":scope > p.nota")) if ((notas || []).some(t => p.textContent.startsWith(t))) p.remove();
  return card;
}

/** A conferência do card de credores (nivel3.js) compara os empenhos com o DCA do
 *  painel completo; aqui a comparação é com a despesa agregada do próprio TCE-ES. */
const TROCAS_CONFERENCIA = [
  ["da função 12 do DCA", "da despesa da função 12 publicada pelo TCE-ES"],
  ["; DCA = ", "; despesa agregada do TCE-ES = "],
  ["As remessas ao Tribunal e ao Tesouro podem divergir por retificação.", "Os dois arquivos do TCE-ES podem divergir por retificação ou por mês ainda não processado."],
];
function conferenciaSemDCA(card) {
  for (const c of card.querySelectorAll(":scope > .callout")) {
    const textos = document.createTreeWalker(c, NodeFilter.SHOW_TEXT);
    for (let n = textos.nextNode(); n; n = textos.nextNode())
      n.nodeValue = TROCAS_CONFERENCIA.reduce((t, [de, para]) => t.replace(de, para), n.nodeValue);
  }
  return card;
}

function secaoNivel3(destino, cod, ano) {
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" },
    anexarLimitacao(priorizarGrafico(conferenciaSemDCA(semTextos(cardNivel3Credores(cod, ano), { notas: ["Clique no nome do credor"] })),
      "Tabela de credores — clique no nome para o detalhe por ação e contratação"), "Nível 3"),
    cardConselhosEscolares(cod, ano),
    anexarLimitacao(priorizarGrafico(semTextos(cardNivel3Itens(cod, ano), { simples: true, notas: ["Como estas linhas entraram"] }), "Itens contratados, um a um (tabela completa)"), "Itens contratados"))));
}
