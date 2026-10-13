"use strict";
/* ===========================================================================
   CNCA — Evidências da fiscalização do financiamento (arquivo separado)
   ---------------------------------------------------------------------------
   Papel de trabalho da fiscalização do Compromisso Nacional Criança
   Alfabetizada nos 78 municípios do ES. Saiu do painel geral para um arquivo
   próprio (decisão D3): é instrumento de uma fiscalização específica, com ciclo
   de atualização próprio, e não se confunde com o painel público.

   Três regras que valem para a página inteira:
     · nenhuma célula diz "achado" — diz indício, e a legenda repete isso;
     · lacuna nunca aparece como zero: aparece como "sem dado público", com o
       motivo e o caminho alternativo;
     · o que vale para os 78 é dito UMA vez, como constatação, e não 78 vezes
       no mapa.
   =========================================================================== */

const CN = (() => {
  const el = document.getElementById("dataset-cnca");
  try { return JSON.parse(el.textContent); } catch (e) { return { meta: { ausente: true, motivo: String(e) } }; }
})();
const CN_AUSENTE = !!(CN.meta || {}).ausente;
const ARQUIVO_PAINEL = "novo_dashboard.html";

const CN_STATUS = (CN.meta || {}).status || {};
const CN_TIPOS = (CN.meta || {}).tipos_evidencia || {};
const CN_ANOS = (CN.meta || {}).anos || [];
const CN_QUESTOES = CN.questoes || [];
const CN_ACHADOS = CN_QUESTOES.flatMap(q => q.achados.map(a => ({ ...a, questao: q.id })));
const CN_ACHADO = new Map(CN_ACHADOS.map(a => [a.id, a]));
const CN_PERGUNTAS = CN.perguntas || [];
const CN_CONSTATACOES = CN.constatacoes || [];
const CN_MUNICIPIOS = CN.municipios || [];
const CN_NOME = new Map(CN_MUNICIPIOS.map(m => [m.cod_ibge, m.nome]));

/* Ordem de gravidade: ordena o mapa e escolhe o status "pior" de um município
   num achado com vários anos. */
const CN_ORDEM = { indicio_risco: 0, inconclusivo: 1, sem_dado_publico: 2, sem_indicio: 3 };
const CN_CLASSE = { indicio_risco: "st-risco", inconclusivo: "st-inconc", sem_dado_publico: "st-semdado", sem_indicio: "st-ok" };
/* Símbolo além da cor. "Sem dado público" era um ponto (·), quase invisível no
   mapa; virou um traço. */
const CN_SIMBOLO = { indicio_risco: "▲", inconclusivo: "◆", sem_dado_publico: "–", sem_indicio: "○" };
const CN_SIGNIFICADO = {
  indicio_risco: "o dado público mostra um sinal de risco que merece verificação",
  inconclusivo: "há algum dado, mas ele não permite concluir nem num sentido nem noutro",
  sem_dado_publico: "não há dado público que responda — o caminho é o questionário ou o ofício",
  sem_indicio: "o dado público não mostra sinal de risco",
};
const CN_TIPO_SIMBOLO = { direta: "=", proxy: "≈", indicio: "?", documental: "§", inferencia: "~", indisponivel: "—" };
const CN_TIPO_SIGNIFICADO = { direta: "o dado mede exatamente o que o achado pergunta", proxy: "o dado mede algo próximo, não a coisa em si",
  indicio: "sinal que exige revisão humana", documental: "depende de ler um documento (ato, portaria, diário oficial)",
  inferencia: "conclusão descritiva a partir de vários dados", indisponivel: "não há dado público" };

const CN_EV = CN.evidencias || [];
const CN_POR_MUN_ACHADO = new Map();
for (const e of CN_EV) {
  const k = e.municipio_ibge + "|" + e.achado_id;
  if (!CN_POR_MUN_ACHADO.has(k)) CN_POR_MUN_ACHADO.set(k, []);
  CN_POR_MUN_ACHADO.get(k).push(e);
}
const cnIndices = agrupar(CN.indices || [], r => r.cod_ibge + "|" + r.ano);
const cnRestos = agrupar(CN.restos || [], r => r.cod_ibge + "|" + r.ano);
const cnPdde = agrupar(CN.pdde || [], r => r.cod_ibge + "|" + r.ano);
const cnEstadoRep = agrupar(CN.estado || [], r => r.cod_ibge + "|" + r.ano);
const cnContratos = agrupar(CN.contratos || [], r => r.cod_ibge);
const cnBuscas = agrupar(CN.buscas_manuais || [], r => r.cod_ibge);

/* O "ver fonte" desta página é o MESMO do painel (fonte.js): os indicadores e as
   consultas da matriz entram nos catálogos que aquele diálogo consulta. */
for (const c of (CN.consultas || [])) if (!CONSULTAS.has(c.id)) CONSULTAS.set(c.id, c);
META.indicadores = META.indicadores || {};
for (const a of CN_ACHADOS) for (const i of (a.indicadores || [])) {
  if (!META.indicadores[i.id]) META.indicadores[i.id] = { rotulo: i.rotulo, fonte: i.fonte, unidade: i.unidade, localizacao: i.fonte, calculo: i.formula };
}

/* ------------------------------------------------------------------ estado */
const estadoCn = { visao: "matriz", municipio: null, ano: null, achado: null, soRisco: false, ir: null, filtrosAbertos: false };
/* `titulo` vira o h2 da visão; Ficha e Perguntas escrevem o próprio. */
const CN_VISOES = [
  { id: "matriz", rotulo: "Matriz", titulo: "Matriz de planejamento — as questões e seus achados", render: cnRenderMatriz },
  { id: "mapa", rotulo: "Mapa de evidências", titulo: "Mapa de evidências — os 78 municípios em cada achado", render: cnRenderMapa },
  { id: "municipio", rotulo: "Ficha do município", render: cnRenderMunicipio },
  { id: "perguntas", rotulo: "Perguntas (P1–P49)", render: cnRenderPerguntas },
  { id: "cobertura", rotulo: "Cobertura", titulo: "Cobertura — quanto da matriz o dado público alcança", render: cnRenderCobertura },
  { id: "exportar", rotulo: "Exportar", titulo: "Exportar o papel de trabalho", render: cnRenderExportar },
  { id: "como-ler", rotulo: "Como ler", titulo: "Como ler o papel de trabalho", render: cnRenderComoLer },
];
function cnHashDe(e) {
  const p = new URLSearchParams({ v: e.visao });
  if (e.ano) p.set("ano", e.ano);
  if (e.municipio) p.set("m", e.municipio);
  if (e.achado) p.set("ach", e.achado);
  if (e.soRisco) p.set("risco", "1");
  if (e.ir) p.set("ir", e.ir);
  return "#" + p.toString();
}
function cnLerHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  estadoCn.visao = CN_VISOES.some(v => v.id === p.get("v")) ? p.get("v") : "matriz";
  const ano = parseInt(p.get("ano"), 10);
  estadoCn.ano = CN_ANOS.includes(ano) ? ano : null;
  const m = parseInt(p.get("m"), 10);
  if (CN_NOME.has(m)) estadoCn.municipio = m;
  estadoCn.achado = CN_ACHADO.has(p.get("ach")) ? p.get("ach") : null;
  estadoCn.soRisco = p.get("risco") === "1";
  estadoCn.ir = p.get("ir") || null;
}
const cnEstadoCom = m => ({ ...estadoCn, ir: null, ...m });
const hrefCn = m => cnHashDe(cnEstadoCom(m));
const linkCn = (m, texto, attrs) => h("a", { href: hrefCn(m), ...(attrs || {}) }, texto);
function irCn(m) { const novo = hrefCn(m); if (novo === location.hash) cnRender(); else location.hash = novo; }
function ajustarCn(m) { Object.assign(estadoCn, m); history.replaceState(null, "", cnHashDe(estadoCn)); cnRender(); }
const hrefGlossario = id => hrefCn({ visao: "como-ler", ir: "g-" + id });
const hrefPainel = params => ARQUIVO_PAINEL + "#" + new URLSearchParams(params).toString();
const rotuloAno = () => estadoCn.ano ? String(estadoCn.ano) : "todos (pior status de cada município)";

/* ------------------------------------------------------------- elementos */
function cnChip(status, texto) {
  return h("span", { class: "cn-chip " + CN_CLASSE[status], title: CN_SIGNIFICADO[status] || "" },
    h("span", { "aria-hidden": "true" }, CN_SIMBOLO[status]), " " + (texto || CN_STATUS[status] || status));
}
function cnLegenda() {
  return h("div", { class: "legenda-estados", role: "note", "aria-label": "Como ler os status" }, h("strong", {}, "Como ler: "),
    Object.keys(CN_ORDEM).map(k => h("span", { class: "item" }, cnChip(k), h("span", { class: "muted small" }, CN_SIGNIFICADO[k]))),
    h("p", { class: "small", style: "flex-basis:100%;margin:4px 0 0" }, "Nenhuma célula é achado de auditoria: é indício, e quem o transforma em achado é o auditor, com o documento na mão. Lacuna aparece como “sem dado público”, com o motivo — nunca como zero."));
}
function cnStatusDe(cod, achadoId, ano) {
  const linhas = (CN_POR_MUN_ACHADO.get(cod + "|" + achadoId) || []).filter(l => ano == null || l.ano == null || l.ano === ano);
  return linhas.length ? linhas.slice().sort((a, b) => CN_ORDEM[a.status] - CN_ORDEM[b.status])[0] : null;
}
function cnContagem(achadoId, ano) {
  const c = { indicio_risco: 0, inconclusivo: 0, sem_dado_publico: 0, sem_indicio: 0 };
  for (const m of CN_MUNICIPIOS) { const s = cnStatusDe(m.cod_ibge, achadoId, ano); if (s) c[s.status]++; }
  return c;
}
function cnBarraStatus(c) {
  const total = Object.values(c).reduce((t, v) => t + v, 0) || 1;
  const texto = Object.entries(c).filter(([, v]) => v).map(([k, v]) => v + " " + (CN_STATUS[k] || k).toLowerCase()).join(", ");
  return h("div", {}, h("div", { class: "cn-barra", role: "img", "aria-label": texto },
    ["indicio_risco", "inconclusivo", "sem_dado_publico", "sem_indicio"].filter(k => c[k]).map(k =>
      h("span", { class: "cn-fatia " + CN_CLASSE[k], style: "width:" + (c[k] / total * 100).toFixed(2) + "%", title: c[k] + " " + CN_STATUS[k] }))),
    h("span", { class: "nota" }, texto));
}
function cnTipo(a) {
  return h("span", { class: "cn-tipo", title: (CN_TIPO_SIGNIFICADO[a.tipo_evidencia] || "") + " · confiança " + a.confianca },
    h("span", { "aria-hidden": "true" }, CN_TIPO_SIMBOLO[a.tipo_evidencia] + " "), CN_TIPOS[a.tipo_evidencia] || a.tipo_evidencia);
}
/* O "ver fonte" de uma evidência leva a ressalva do indicador como observação:
   quem abre a fonte de um proxy precisa ler o que ele não prova. */
function cnFonte(ev) {
  const a = CN_ACHADO.get(ev.achado_id) || {}, ind = (a.indicadores || []).find(i => i.id === ev.indicador) || {};
  const detalhe = [ev.ano ? String(ev.ano) : null, CN_NOME.get(ev.municipio_ibge)].filter(Boolean).join(" · ");
  return botaoFonte((ind.rotulo || ev.indicador || a.enunciado) + (ev.ano ? " — " + ev.ano : ""),
    [{ indicador: ev.indicador, ano: ev.ano, detalhe, observacao: [ev.nota, ...(a.ressalvas || [])].filter(Boolean).join(" "), q: ev.q }], true);
}
function cnValor(ev, ind) {
  if (nulo(ev.valor)) return semDado();
  return ind.unidade === "R$" ? brl(ev.valor) : ind.unidade === "%" ? pct(ev.valor) : nf(ev.valor, Number.isInteger(ev.valor) ? 0 : 2) + (ind.unidade && ind.unidade !== "ocorrências" ? " " + ind.unidade : "");
}

/* ------------------------------------------------------------- 1. matriz */
function cnRenderMatriz(raiz) {
  raiz.append(cnLegenda());
  if (CN_CONSTATACOES.length) {
    const card = h("article", { class: "card largo", id: "constatacoes" }, cabecalho("Constatações — o que vale para os 78 municípios, dito uma vez", {
      simples: "Quando uma característica atinge todos os municípios por igual, ela não vira 78 indícios individuais no mapa: fica aqui, para o texto do relatório. Abra cada uma para ver a medida e a consequência." }));
    for (const c of CN_CONSTATACOES) card.append(h("details", { class: "cn-constatacao" },
      h("summary", {}, c.id + " — " + c.enunciado),
      h("p", {}, h("strong", {}, "Medido: "), c.medida),
      h("p", { class: "nota" }, h("strong", {}, "Abrangência: "), c.abrangencia, " · ", h("strong", {}, "Fonte: "), c.fonte),
      h("p", {}, h("strong", {}, "Consequência: "), c.consequencia)));
    raiz.append(card);
  }
  for (const q of CN_QUESTOES) {
    const card = h("article", { class: "card largo", id: "questao-" + q.id }, cabecalho(q.id + " — " + q.enunciado, { simples: q.nota || null }));
    card.append(tabela([
      { rotulo: "Achado", valor: a => a.id, render: a => linkCn({ visao: "mapa", achado: a.id }, a.id, { title: "Ver este achado no mapa" }) },
      { rotulo: "Enunciado", valor: a => a.enunciado, render: a => h("span", {}, a.enunciado, a.constatacao ? h("span", { class: "nota" }, " (ver constatação " + a.constatacao + ")") : null) },
      { rotulo: "Evidência", valor: a => CN_TIPOS[a.tipo_evidencia] || a.tipo_evidencia, render: cnTipo },
      { rotulo: "Distribuição dos 78 municípios", valor: a => cnContagem(a.id, estadoCn.ano).indicio_risco, ordenavel: false, render: a => cnBarraStatus(cnContagem(a.id, estadoCn.ano)) },
      { rotulo: "Indícios", num: true, valor: a => cnContagem(a.id, estadoCn.ano).indicio_risco, render: a => { const n = cnContagem(a.id, estadoCn.ano).indicio_risco; return h("span", { class: n ? "cn-forte" : "" }, String(n)); } },
    ], q.achados, q.id + " — achados", { inicio: 0, busca: false, fixarPrimeira: false, csv: "matriz_" + q.id + ".csv" }));
    raiz.append(card);
  }
}

/* --------------------------------------------------------------- 2. mapa */
function cnRenderMapa(raiz) {
  raiz.append(cnLegenda());
  const ano = estadoCn.ano;
  const achados = estadoCn.soRisco ? CN_ACHADOS.filter(a => cnContagem(a.id, ano).indicio_risco > 0) : CN_ACHADOS;
  const card = h("article", { class: "card largo", id: "mapa" }, cabecalho("Mapa de evidências — município × achado", {
    simples: "Cada linha é um município, cada coluna um achado da matriz; a célula mostra o status " + (ano ? "no exercício de " + ano : "no pior exercício da série") +
      ". Clique no código de um achado para destacar a coluna, ou no nome do município para abrir a ficha dele." }));
  card.append(h("div", { class: "cn-filtros" }, h("label", {}, h("input", { type: "checkbox", checked: estadoCn.soRisco,
    onchange: e => ajustarCn({ soRisco: e.target.checked }) }), "Mostrar só achados com algum indício")));
  const foco = estadoCn.achado && achados.some(a => a.id === estadoCn.achado) ? CN_ACHADO.get(estadoCn.achado) : null;
  if (foco) {
    const c = cnContagem(foco.id, ano);
    card.append(h("div", { class: "callout info cn-achado-foco", role: "status" }, h("strong", {}, "Coluna em destaque — " + foco.id + ": "), foco.enunciado, " ",
      h("span", {}, "(", cnTipo(foco), ") "), cnBarraStatus(c), " ", linkCn({ achado: null }, "tirar o destaque")));
  }
  const tab = h("table", { class: "cn-mapa" }, h("caption", { class: "sr-only" }, "Status de cada município em cada achado da matriz, " + rotuloAno()));
  const cab = h("tr", {}, h("th", { class: "cn-mun", scope: "col" }, "Município"));
  for (const a of achados) {
    const ativa = foco && a.id === foco.id;
    cab.append(h("th", { class: "cn-col" + (ativa ? " cn-ativa" : ""), scope: "col", id: "col-" + a.id.replace(".", "-") },
      h("button", { type: "button", title: a.enunciado, "aria-pressed": String(!!ativa), "aria-label": a.id + " — " + a.enunciado + (ativa ? " (em destaque)" : ""),
        onclick: () => ajustarCn({ achado: ativa ? null : a.id }) }, a.id)));
  }
  tab.append(h("thead", {}, cab));
  const corpo = h("tbody");
  for (const m of CN_MUNICIPIOS) {
    const tr = h("tr", {}, h("th", { scope: "row", class: "cn-mun" }, linkCn({ visao: "municipio", municipio: m.cod_ibge }, m.nome)));
    for (const a of achados) {
      const s = cnStatusDe(m.cod_ibge, a.id, ano), ativa = foco && a.id === foco.id;
      // A cor fica na CÉLULA (a zebra está na linha): nenhuma linha perde a cor do status.
      tr.append(h("td", { class: "cn-cel " + (s ? CN_CLASSE[s.status] : "") + (ativa ? " cn-ativa" : ""),
        title: m.nome + " · " + a.id + ": " + (s ? CN_STATUS[s.status] : "sem linha") + (s && s.nota ? " — " + s.nota : "") },
        s ? [h("span", { "aria-hidden": "true" }, CN_SIMBOLO[s.status]), h("span", { class: "sr-only" }, CN_STATUS[s.status])] : h("span", { class: "sr-only" }, "sem linha")));
    }
    corpo.append(tr);
  }
  tab.append(corpo);
  card.append(h("div", { class: "cn-rolagem", tabindex: "0", role: "region", "aria-label": "Mapa de evidências (rola nos dois sentidos)" }, tab));
  card.append(h("details", { class: "tab" }, h("summary", {}, "O que é cada coluna (" + achados.length + " achados)"),
    h("ul", { class: "lista" }, achados.map(a => h("li", {}, linkCn({ achado: a.id }, a.id), " — " + a.enunciado)))));
  raiz.append(card);
  if (foco) setTimeout(() => { const th = document.getElementById("col-" + foco.id.replace(".", "-")); if (th) th.scrollIntoView({ inline: "center", block: "nearest" }); }, 0);
}

/* ---------------------------------------------------------- 3. município */
function cnRenderMunicipio(raiz) {
  const cod = estadoCn.municipio || (CN_MUNICIPIOS[0] || {}).cod_ibge;
  if (!cod) { raiz.append(h("p", {}, "Sem municípios no dataset.")); return; }
  const nome = CN_NOME.get(cod);
  raiz.append(h("div", { class: "cab-visao" }, h("h2", {}, "Ficha de evidências — " + nome),
    h("p", {}, "Todas as evidências do município, questão por questão, com o valor, o status e o que o indicador mede — e não mede. ",
      h("a", { href: hrefPainel({ v: "municipio", m: cod }) }, "Ver o dossiê financeiro de " + nome + " no painel ↗"))));
  // Notas repetidas viram notas numeradas: a mesma frase longa não se repete em três linhas seguidas.
  const usos = new Map();
  for (const q of CN_QUESTOES) for (const a of q.achados) for (const ev of (CN_POR_MUN_ACHADO.get(cod + "|" + a.id) || []))
    if (ev.nota) usos.set(ev.nota, (usos.get(ev.nota) || 0) + 1);
  const numeradas = new Map();
  const celulaNota = texto => {
    if (!texto) return h("span", { class: "muted" }, "—");
    if (usos.get(texto) < 2) return h("span", { class: "cn-nota" }, texto);
    if (!numeradas.has(texto)) numeradas.set(texto, numeradas.size + 1);
    return h("span", { class: "cn-nota" }, "Ver nota " + numeradas.get(texto) + " (vale para " + usos.get(texto) + " linhas)");
  };
  for (const q of CN_QUESTOES) {
    const linhas = [];
    for (const a of q.achados) for (const ev of (CN_POR_MUN_ACHADO.get(cod + "|" + a.id) || []))
      if (!(estadoCn.ano && ev.ano && ev.ano !== estadoCn.ano)) linhas.push({ a, ev, ind: (a.indicadores || []).find(i => i.id === ev.indicador) || {} });
    if (!linhas.length) continue;
    const card = h("article", { class: "card largo", id: "ficha-" + q.id }, cabecalho(q.id + " — " + q.enunciado));
    card.append(tabela([
      { rotulo: "Achado", valor: l => l.a.id },
      { rotulo: "Indicador", valor: l => l.ind.rotulo || l.ev.indicador || l.a.enunciado },
      { rotulo: "Ano", num: true, valor: l => l.ev.ano,
        render: l => l.ev.ano == null ? h("span", { class: "muted", title: "Vale para o período inteiro" }, "—") : String(l.ev.ano) },
      { rotulo: "Valor", num: true, valor: l => l.ev.valor, render: l => cnValor(l.ev, l.ind) },
      { rotulo: "Status", valor: l => CN_STATUS[l.ev.status], ordem: l => CN_ORDEM[l.ev.status], render: l => cnChip(l.ev.status) },
      { rotulo: "O que isto mede (e não mede)", valor: l => l.ev.nota || "", ordenavel: false, render: l => celulaNota(l.ev.nota) },
      { rotulo: "Fonte", valor: () => "", csv: false, ordenavel: false, render: l => cnFonte(l.ev) },
    ], linhas, q.id + " — " + nome, { inicio: 0, busca: false, fixarPrimeira: false }));
    raiz.append(card);
  }
  if (numeradas.size) raiz.append(h("article", { class: "card largo", id: "notas" }, cabecalho("Notas que valem para várias linhas"),
    h("ol", { class: "notas" }, [...numeradas.keys()].map(t => h("li", {}, t)))));

  const extras = h("article", { class: "card largo", id: "respostas-diretas" }, cabecalho("Números que respondem perguntas do questionário", {
    simples: "Dados que não classificam um achado, mas respondem diretamente a perguntas do questionário — para confrontar com as respostas do município quando chegarem." }));
  let algum = false;
  const bloco = (titulo, nota, colunas, linhas, legenda) => {
    if (!linhas.length) return;
    algum = true;
    extras.append(h("div", {}, h("h4", {}, titulo), nota ? h("p", { class: "nota" }, nota) : null, tabela(colunas, linhas, legenda || titulo, { inicio: 0, busca: false, fixarPrimeira: false })));
  };
  bloco("P24 — os quatro índices de execução (função 12 inteira)", null, [
    { rotulo: "Ano", valor: r => r.ano }, { rotulo: "Empenhado ÷ dotação", num: true, valor: r => r.indice_execucao_orcamentaria, fmt: v => pct(v) },
    { rotulo: "Pago ÷ dotação", num: true, valor: r => r.indice_execucao_financeira, fmt: v => pct(v) },
    { rotulo: "Liquidado ÷ empenhado", num: true, valor: r => r.indice_liquidacao, fmt: v => pct(v) },
    { rotulo: "Pago ÷ liquidado", num: true, valor: r => r.indice_pagamento, fmt: v => pct(v) },
  ], CN_ANOS.flatMap(a => (cnIndices.get(cod + "|" + a) || []).filter(r => String(r.fonte).startsWith("(todas"))));
  const pd = CN_ANOS.flatMap(a => cnPdde.get(cod + "|" + a) || []);
  bloco("P21 — escolas da rede beneficiadas com PDDE-CNCA", (pd[0] || {}).denominador ? "Denominador: " + pd[0].denominador + "." : null, [
    { rotulo: "Ano", valor: r => r.ano }, { rotulo: "Escolas atendidas", num: true, valor: r => r.escolas_com_pdde_cnca || 0, fmt: nf },
    { rotulo: "Escolas da rede", num: true, valor: r => r.escolas_rede, fmt: nf }, { rotulo: "Cobertura", num: true, valor: r => r.cobertura_pct, fmt: v => pct(v) },
  ], pd);
  bloco("P25 e P26 — restos a pagar nas fontes 551 e 569",
    "A idade sai do ano do empenho: um empenho de ano anterior que ainda se move no exercício é, por construção, resto a pagar. (A coluna própria do TCE-ES para isso vem sempre vazia nos arquivos dos municípios do ES.)", [
    { rotulo: "Ano", valor: r => r.ano }, { rotulo: "Fonte", valor: r => String(r.fonte) },
    { rotulo: "Empenhado", num: true, valor: r => r.empenhada || 0, fmt: brl }, { rotulo: "Restos processados inscritos", num: true, valor: r => r.rpp_inscrito || 0, fmt: brl },
    { rotulo: "% do empenhado", num: true, valor: r => r.rpp_pct_empenhado, fmt: v => pct(v) },
    { rotulo: "Idade máxima", num: true, valor: r => r.rp_idade_maxima, fmt: v => nf(v) + " anos" },
    { rotulo: "Prolongado", valor: r => r.rpp_prolongado === true ? "sim" : r.rpp_prolongado === false ? "não" : "não medido" },
  ], CN_ANOS.flatMap(a => cnRestos.get(cod + "|" + a) || []).filter(r => ["551", "569"].includes(String(r.fonte))));
  bloco("P18 — recursos do Estado em regime de colaboração",
    "Transferências da esfera estadual (SIGEFES) na função 12, modalidades 40, 41 e 42, com este município como favorecido. O casamento é pelo nome do favorecido; o que não casou fica listado à parte no conjunto de dados, nunca descartado.", [
    { rotulo: "Ano", valor: r => r.ano }, { rotulo: "Empenhado", num: true, valor: r => r.empenhado || 0, fmt: brl },
    { rotulo: "Pago", num: true, valor: r => r.pago || 0, fmt: brl }, { rotulo: "…do qual FUNPAES (empenhado)", num: true, valor: r => r.empenhado_funpaes || 0, fmt: brl },
  ], CN_ANOS.flatMap(a => cnEstadoRep.get(cod + "|" + a) || []));
  bloco("P47 e P48 — contratações de formação e material",
    "Classificação por palavra-chave sobre o objeto da contratação, revisável: cada linha traz os termos que a fizeram entrar. Contratação revogada, anulada ou fracassada aparece marcada e fica fora do valor de P48.", [
    { rotulo: "Ano", valor: r => r.ano }, { rotulo: "Categoria", valor: r => r.categoria_rotulo },
    { rotulo: "Objeto", valor: r => r.objeto, render: r => h("span", { class: "cn-nota" }, r.objeto) },
    { rotulo: "Termos que casaram", valor: r => r.termos },
    { rotulo: "Valor", num: true, valor: r => r.valor_total, fmt: brl },
    { rotulo: "Situação", valor: r => r.sem_efeito ? "sem efeito — " + r.situacao : (r.situacao || "") },
  ], cnContratos.get(cod) || []);
  bloco("Buscas a fazer à mão no diário oficial",
    "Este município não tem diário indexado de forma automatizável. A lista é o que buscar, onde e o que registrar — e não achar o ato não é o mesmo que o ato não existir.", [
    { rotulo: "Achado", valor: r => r.achado_id }, { rotulo: "O que procurar", valor: r => r.o_que_procurar },
    { rotulo: "Expressão", valor: r => r.expressao, render: r => h("code", {}, r.expressao) }, { rotulo: "Onde", valor: r => r.onde }, { rotulo: "Período", valor: r => r.periodo },
  ], cnBuscas.get(cod) || []);
  if (algum) raiz.append(extras);
}

/* ---------------------------------------------------------- 4. perguntas */
function cnRenderPerguntas(raiz) {
  const rotuloEvid = { direta: "responde direto", proxy: "responde por aproximação", parcial: "responde em parte", indisponivel: "só o questionário responde" };
  raiz.append(h("div", { class: "cab-visao" }, h("h2", {}, "As 49 perguntas do questionário, e o que o dado já responde"),
    h("p", {}, "O questionário ainda não foi respondido — esta visão não mostra respostas de município. Ela mostra o que o dado público responde de cada pergunta antes delas, que é o que permite confrontar a resposta quando ela chegar.")));
  const porBloco = agrupar(CN_PERGUNTAS, p => p.bloco);
  for (const [bloco, perguntas] of [...porBloco].sort((a, b) => a[0] - b[0])) {
    const card = h("article", { class: "card largo", id: "bloco-" + bloco }, cabecalho("Bloco " + bloco));
    card.append(tabela([
      { rotulo: "Nº", valor: p => p.id, ordem: p => parseInt(String(p.id).slice(1), 10) },
      { rotulo: "Pergunta", valor: p => p.enunciado, render: p => h("span", {}, p.enunciado, p.dados_pessoais ? [" ", h("span", { class: "badge aviso", title: "Pergunta que coleta dado pessoal (LGPD e Resolução TC 358/2021)" }, "dado pessoal")] : null) },
      { rotulo: "Evidência", valor: p => rotuloEvid[p.evidencia] || p.evidencia, render: p => h("span", { class: "cn-chip cn-ev-" + p.evidencia }, rotuloEvid[p.evidencia] || p.evidencia) },
      { rotulo: "O que o dado responde", valor: p => p.responde_com, render: p => h("span", { class: "cn-nota" }, p.responde_com) },
      { rotulo: "Achados", valor: p => (p.achados || []).join(", ") },
    ], perguntas, "Perguntas do bloco " + bloco, { inicio: 0, busca: false, fixarPrimeira: false }));
    raiz.append(card);
  }
  raiz.append(h("p", { class: "nota" }, "Perguntas marcadas como “dado pessoal” coletam dado pessoal (LGPD e Resolução TC 358/2021). O painel não exibe nome, e-mail ou telefone de ninguém, mesmo quando o ato publicado os traz."));
}

/* ---------------------------------------------------------- 5. cobertura */
function cnRenderCobertura(raiz) {
  const cob = CN.cobertura_achados || [];
  const porSituacao = agrupar(cob, c => c.situacao), evid = agrupar(CN_PERGUNTAS, p => p.evidencia);
  const rotuloSituacao = s => s === "calculado" ? "achados com dado público calculado" : s.startsWith("sem dado público") ? "achados sem dado público (só questionário ou ofício)" : "achados — " + s;
  const rotuloEvid = { direta: "perguntas que o dado responde direto", proxy: "perguntas respondidas por aproximação", parcial: "perguntas respondidas em parte", indisponivel: "perguntas que só o questionário responde" };
  raiz.append(h("article", { class: "card largo", id: "cobertura" }, cabecalho("Quanto da matriz o dado público alcança", {
    simples: "É o número mais útil desta página para a seção de metodologia do relatório: diz, medido, o quanto da fiscalização depende dos municípios, de ofício ou de análise documental." }),
    h("div", { class: "cn-kpis" },
      [...porSituacao].map(([s, l]) => h("div", { class: "cn-kpi" }, h("span", { class: "cn-kpi-valor" }, l.length + " de " + cob.length), h("span", { class: "cn-kpi-rotulo" }, rotuloSituacao(s)))),
      [...evid].map(([e, l]) => h("div", { class: "cn-kpi" }, h("span", { class: "cn-kpi-valor" }, l.length + " de " + CN_PERGUNTAS.length), h("span", { class: "cn-kpi-rotulo" }, rotuloEvid[e] || e))))));
  raiz.append(h("article", { class: "card largo", id: "cobertura-achados" }, cabecalho("Cobertura de cada achado"), tabela([
    { rotulo: "Achado", valor: c => c.achado_id, render: c => linkCn({ visao: "mapa", achado: c.achado_id }, c.achado_id) },
    { rotulo: "Enunciado", valor: c => (CN_ACHADO.get(c.achado_id) || {}).enunciado || "" },
    { rotulo: "Fase", valor: c => "fase " + c.fase }, { rotulo: "Situação", valor: c => c.situacao },
    { rotulo: "Evidência", valor: c => CN_TIPOS[(CN_ACHADO.get(c.achado_id) || {}).tipo_evidencia] || "" },
    { rotulo: "Indícios", num: true, valor: c => c.n_indicio_risco || 0 }, { rotulo: "Inconclusivos", num: true, valor: c => c.n_inconclusivo || 0 },
    { rotulo: "Sem dado", num: true, valor: c => c.n_sem_dado_publico || 0 }, { rotulo: "Sem indício", num: true, valor: c => c.n_sem_indicio || 0 },
    { rotulo: "Ressalvas", valor: c => ((CN_ACHADO.get(c.achado_id) || {}).ressalvas || []).join(" "), ordenavel: false, render: c => h("span", { class: "cn-nota" }, ((CN_ACHADO.get(c.achado_id) || {}).ressalvas || []).join(" ")) },
    { rotulo: "Caminho alternativo", valor: c => (CN_ACHADO.get(c.achado_id) || {}).caminho_alternativo || "", ordenavel: false },
  ], cob, "Cobertura de cada achado", { inicio: 0, csv: "cobertura_achados.csv" })));
  const params = Object.entries((CN.meta || {}).parametros || {});
  raiz.append(h("article", { class: "card largo", id: "limiares" }, cabecalho("Limiares — todos ajustáveis", {
    simples: "Os pontos de corte que transformam um número em indício. A descrição de cada um traz a distribuição real medida, que é o que permite calibrá-lo com a equipe." }),
    tabela([
      { rotulo: "Parâmetro", valor: ([k]) => k, render: ([k]) => h("code", {}, k) },
      { rotulo: "Valor", num: true, valor: ([, v]) => v.valor, render: ([, v]) => String(v.valor).replace(".", ",") + " " + (v.unidade || "") },
      { rotulo: "Situação", valor: ([, v]) => v.calibrar ? "a calibrar com a equipe" : "fixo" },
      { rotulo: "Por quê", valor: ([, v]) => v.descricao || "", render: ([, v]) => h("span", { class: "cn-nota" }, v.descricao || "") },
    ], params, "Limiares da matriz", { inicio: 0, busca: false, fixarPrimeira: false })));
  const lim = (CN.meta || {}).limitacoes || {};
  if (Object.keys(lim).length) raiz.append(h("article", { class: "card largo", id: "limitacoes-estruturais" }, cabecalho("Limitações estruturais"),
    ...Object.values(lim).map(t => h("p", { class: "cn-limite" }, comTermos(t)))));
}

/* ---------------------------------------------------------- 6. exportar */
function cnCsv() {
  const cols = ["municipio_ibge", "municipio", "questao_matriz", "achado_id", "pergunta_questionario", "indicador", "rotulo", "valor", "unidade", "ano",
    "status", "tipo_evidencia", "confianca", "fonte", "nota", "endpoint_ou_arquivo", "obtido_em", "hash_bruto"];
  const linhas = [linhaCSV(cols)];
  for (const e of CN_EV) {
    const a = CN_ACHADO.get(e.achado_id) || {}, ind = (a.indicadores || []).find(i => i.id === e.indicador) || {}, c = consultasDe(e.q)[0] || {};
    linhas.push(linhaCSV([e.municipio_ibge, CN_NOME.get(e.municipio_ibge) || "", a.questao || "", e.achado_id, (a.perguntas || []).join(" "),
      e.indicador || "", ind.rotulo || "", e.valor, ind.unidade || "", e.ano, CN_STATUS[e.status] || e.status, CN_TIPOS[a.tipo_evidencia] || "",
      a.confianca || "", ind.fonte || "", e.nota || "", c.arquivo || c.url || "", c.obtido_em || "", c.sha256 || ""]));
  }
  return linhas.join("\r\n");
}
function cnRenderExportar(raiz) {
  raiz.append(h("article", { class: "card largo", id: "exportar" }, cabecalho("Exportar o papel de trabalho", {
    simples: "Uma linha por município × achado × indicador, com valor, status, tipo de evidência, confiança, a ressalva do indicador e a proveniência completa: endereço da consulta ou arquivo guardado, instante da coleta e SHA-256 do arquivo bruto." }),
    h("p", { class: "nota" }, "Separado por ponto e vírgula, com vírgula decimal — abre direto no Excel em português. É o mesmo conteúdo do arquivo evidencias_cnca.csv do conjunto de dados."),
    h("button", { type: "button", class: "primario", onclick: () => baixarTexto("evidencias_cnca_" + new Date().toISOString().slice(0, 10) + ".csv", "﻿" + cnCsv(), "text/csv;charset=utf-8") },
      "Baixar evidências (CSV)"),
    h("p", { class: "nota" }, nf(CN_EV.length) + " linhas de evidência, " + CN_MUNICIPIOS.length + " municípios, " + CN_ACHADOS.length + " achados, " + CN_PERGUNTAS.length + " perguntas.")));
}

/* ---------------------------------------------------------- 7. como ler */
function cnRenderComoLer(raiz) {
  raiz.append(h("article", { class: "card largo", id: "regras" }, cabecalho("Como ler esta página"),
    h("h4", {}, "Os quatro status"), h("ul", { class: "lista" }, Object.keys(CN_ORDEM).map(k => h("li", {}, cnChip(k), " — " + CN_SIGNIFICADO[k] + "."))),
    h("h4", {}, "Os tipos de evidência"), h("ul", { class: "lista" }, Object.keys(CN_TIPO_SIMBOLO).map(k => h("li", {}, h("strong", {}, CN_TIPO_SIMBOLO[k] + " " + (CN_TIPOS[k] || k)), " — " + (CN_TIPO_SIGNIFICADO[k] || "") + "."))),
    h("h4", {}, "Três regras que valem para a página inteira"),
    h("ul", { class: "lista" },
      h("li", {}, "Nenhuma célula diz \"achado\": diz indício. Quem transforma indício em achado é o auditor, com o documento na mão."),
      h("li", {}, "Lacuna nunca aparece como zero: aparece como \"sem dado público\", com o motivo e o caminho alternativo."),
      h("li", {}, "O que vale para os 78 municípios é dito uma vez, como constatação, e não 78 vezes no mapa.")),
    h("h4", {}, "Exercício"), h("p", {}, "Com \"todos os exercícios\", cada célula mostra o pior status do município naquele achado ao longo da série. Escolha um exercício para ver só ele.")));
  raiz.append(h("article", { class: "card largo", id: "glossario" }, cabecalho("Glossário"), listaGlossario()));
}

/* ------------------------------------------------------------ moldura */
function cnRenderContexto(v) {
  const barra = $("#contexto"), wrap = limpar($("#contexto-wrap"));
  barra.classList.toggle("aberta", estadoCn.filtrosAbertos);
  wrap.append(h("p", { class: "recorte", "aria-live": "polite" }, "Você está vendo: ", h("strong", {}, v.rotulo), " · exercício ", h("strong", {}, rotuloAno()),
    estadoCn.visao === "municipio" && estadoCn.municipio ? [" · ", h("strong", {}, CN_NOME.get(estadoCn.municipio))] : null,
    estadoCn.visao === "mapa" && estadoCn.achado ? [" · destaque em ", h("strong", {}, estadoCn.achado)] : null));
  wrap.append(h("button", { type: "button", class: "leve alternar-filtros", "aria-expanded": String(estadoCn.filtrosAbertos), "aria-controls": "controles",
    onclick: e => { estadoCn.filtrosAbertos = !estadoCn.filtrosAbertos; barra.classList.toggle("aberta", estadoCn.filtrosAbertos);
      e.currentTarget.setAttribute("aria-expanded", String(estadoCn.filtrosAbertos)); medirContexto(); } }, "Filtros"));
  const ano = h("select", { id: "f-ano", onchange: e => ajustarCn({ ano: e.target.value ? Number(e.target.value) : null }) },
    h("option", { value: "" }, "Todos (pior status de cada município)"), CN_ANOS.slice().reverse().map(a => h("option", { value: String(a) }, String(a))));
  ano.value = estadoCn.ano ? String(estadoCn.ano) : "";
  const controles = h("div", { class: "controles", id: "controles", role: "group", "aria-label": "Filtros" }, campo("Exercício", ano));
  if (estadoCn.visao === "municipio") {
    const mun = h("select", { id: "f-mun", onchange: e => irCn({ municipio: Number(e.target.value) }) },
      CN_MUNICIPIOS.slice().sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR")).map(m => h("option", { value: String(m.cod_ibge) }, m.nome)));
    mun.value = String(estadoCn.municipio || (CN_MUNICIPIOS[0] || {}).cod_ibge);
    controles.append(campo("Município", mun));
  }
  wrap.append(controles);
}
function cnRender() {
  REDESENHOS.length = 0;
  const v = CN_VISOES.find(x => x.id === estadoCn.visao) || CN_VISOES[0];
  document.title = v.rotulo + " · CNCA — evidências da fiscalização";
  limpar($("#trilha")).append(...["Painel de Controle", "Áreas temáticas", "Educação"].map(t => h("li", {}, t)),
    h("li", {}, h("a", { href: ARQUIVO_PAINEL }, "Financiamento")), h("li", {}, linkCn({ visao: "matriz" }, "CNCA — evidências")), h("li", { "aria-current": "page" }, v.rotulo));
  limpar($("#nav-visoes")).append(...CN_VISOES.map(x => h("li", {}, h("a", { href: hrefCn({ visao: x.id }), "aria-current": x.id === v.id ? "page" : null }, x.rotulo))),
    h("li", { class: "externo" }, h("a", { href: ARQUIVO_PAINEL }, "Painel de financiamento ↗")));
  const raiz = limpar($("#conteudo"));
  if (CN_AUSENTE) {
    raiz.append(h("div", { class: "callout sinal", role: "note" }, h("strong", {}, "A matriz de evidências não foi gerada nesta versão. "),
      "O papel de trabalho do CNCA depende de uma etapa própria de processamento, que não foi executada. Informe a equipe do painel."));
    return;
  }
  cnRenderContexto(v);
  if (v.titulo) raiz.append(h("div", { class: "cab-visao" }, h("h2", {}, v.titulo)));
  v.render(raiz);
  medirContexto();
}
function cnPosicionar(antes) {
  if (estadoCn.ir) {
    const el = document.getElementById(estadoCn.ir);
    if (el) { el.classList.add("alvo"); el.scrollIntoView({ block: "start" }); }
    estadoCn.ir = null; history.replaceState(null, "", cnHashDe(estadoCn));
    return;
  }
  if (antes && (antes.v !== estadoCn.visao || antes.m !== estadoCn.municipio)) {
    const main = $("#conteudo"), topo = main.getBoundingClientRect().top + scrollY - ($("#contexto").offsetHeight || 0);
    main.focus({ preventScroll: true });
    if (scrollY > topo) scrollTo(0, topo);
  }
}
function cnIniciar() {
  cnLerHash();
  if (!estadoCn.municipio) estadoCn.municipio = (CN_MUNICIPIOS[0] || {}).cod_ibge || null;
  const irInicial = estadoCn.ir;
  history.replaceState(null, "", cnHashDe(estadoCn));
  const meta = CN.meta || {};
  $("#carimbo").textContent = "Matriz gerada em " + dataHoraBR(meta.gerado_em) + " · exercícios " + (CN_ANOS[0] || "–") + "–" + (CN_ANOS[CN_ANOS.length - 1] || "–") +
    " · " + CN_MUNICIPIOS.length + " municípios · " + CN_ACHADOS.length + " achados em " + CN_QUESTOES.length + " questões · " + CN_PERGUNTAS.length + " perguntas do questionário.";
  for (const dlg of document.querySelectorAll("dialog")) dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });
  estadoCn.ir = irInicial;
  cnRender();
  cnPosicionar(null);
  addEventListener("hashchange", () => {
    const antes = { v: estadoCn.visao, m: estadoCn.municipio };
    cnLerHash(); cnRender(); cnPosicionar(antes);
  });
  let espera;
  addEventListener("resize", () => { clearTimeout(espera); espera = setTimeout(medirContexto, 200); });
}
function cnArrancar() {
  try { cnIniciar(); } catch (e) {
    limpar($("#conteudo")).append(h("div", { class: "callout descumpre", role: "alert" }, h("strong", {}, "A página não pôde ser montada. "),
      "Recarregue; se o problema continuar, informe a equipe do painel com a mensagem: " + e.message));
    throw e;
  }
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", cnArrancar); else cnArrancar();
