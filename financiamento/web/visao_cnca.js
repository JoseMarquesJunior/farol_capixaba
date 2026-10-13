"use strict";
/* ===========================================================================
   CNCA — Evidências da fiscalização (TCE-ES)
   ---------------------------------------------------------------------------
   Papel de trabalho da fiscalização do financiamento do Compromisso Nacional
   Criança Alfabetizada nos 78 municípios do ES. Substitui a aba anterior
   ("CNCA — Auditoria"), que era um checklist manual: aqui cada célula sai da
   tabela de evidências produzida pelo ETL, e leva ao registro bruto.

   Seis visões, na ordem em que a equipe usa:
     1. Matriz        — as 6 questões, cada achado com a distribuição por status
     2. Mapa          — município × achado, cor por status, ícone por tipo
     3. Município     — a ficha completa de um ente
     4. Perguntas     — o que o dado responde de cada uma das 49
     5. Cobertura     — quanto da matriz o dado público alcança
     6. Exportar      — CSV do papel de trabalho, com proveniência

   Três regras que valem para a tela inteira:
     · nenhuma célula diz "achado" — diz indício, e a legenda repete isso;
     · lacuna nunca aparece como zero: aparece como "sem dado público", com o
       motivo e o caminho alternativo na própria célula;
     · o que vale para os 78 é dito UMA vez, como constatação, e não 78 vezes
       no mapa de calor.
   =========================================================================== */

const CN = (() => {
  const el = document.getElementById("dataset-cnca");
  try { return JSON.parse(el.textContent); } catch (e) { return { meta: { ausente: true, motivo: String(e) } }; }
})();
const CN_AUSENTE = !!(CN.meta || {}).ausente;

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

/* Ordem de gravidade: é ela que ordena o mapa e escolhe o status "pior" de um
   município num achado com vários anos. "Sem dado" não é melhor nem pior que
   "inconclusivo" — é outra coisa —, mas precisa de uma posição estável. */
const CN_ORDEM = { indicio_risco: 0, inconclusivo: 1, sem_dado_publico: 2, sem_indicio: 3 };
const CN_CLASSE = { indicio_risco: "st-risco", inconclusivo: "st-inconc",
                    sem_dado_publico: "st-semdado", sem_indicio: "st-ok" };
/* Símbolo além da cor — o painel não codifica informação só por cor. */
const CN_SIMBOLO = { indicio_risco: "▲", inconclusivo: "◆", sem_dado_publico: "·", sem_indicio: "○" };
const CN_TIPO_SIMBOLO = { direta: "=", proxy: "≈", indicio: "?", documental: "§",
                          inferencia: "~", indisponivel: "—" };

/* --------------------------------------------------------------- índices */

const CN_EV = CN.evidencias || [];
const CN_POR_ACHADO = new Map();      // achado -> linhas
const CN_POR_MUN_ACHADO = new Map();  // "cod|achado" -> linhas
for (const e of CN_EV) {
  if (!CN_POR_ACHADO.has(e.achado_id)) CN_POR_ACHADO.set(e.achado_id, []);
  CN_POR_ACHADO.get(e.achado_id).push(e);
  const k = e.municipio_ibge + "|" + e.achado_id;
  if (!CN_POR_MUN_ACHADO.has(k)) CN_POR_MUN_ACHADO.set(k, []);
  CN_POR_MUN_ACHADO.get(k).push(e);
}
const cnIndices = agrupar(CN.indices || [], r => r.cod_ibge + "|" + r.ano);
const cnRestos = agrupar(CN.restos || [], r => r.cod_ibge + "|" + r.ano);
const cnPdde = agrupar(CN.pdde || [], r => r.cod_ibge + "|" + r.ano);
const cnEstado = agrupar(CN.estado || [], r => r.cod_ibge + "|" + r.ano);
const cnContratos = agrupar(CN.contratos || [], r => r.cod_ibge);
const cnBuscas = agrupar(CN.buscas_manuais || [], r => r.cod_ibge);

const cnEstado_ = { visao: "matriz", municipio: null, ano: null, achado: null, so_risco: false };

/* Status do município num achado, considerando o ano escolhido (ou todos). */
function cnStatusDe(cod, achadoId, ano) {
  const linhas = (CN_POR_MUN_ACHADO.get(cod + "|" + achadoId) || [])
    .filter(l => ano == null || l.ano == null || l.ano === ano);
  if (!linhas.length) return null;
  return linhas.slice().sort((a, b) => CN_ORDEM[a.status] - CN_ORDEM[b.status])[0];
}

function cnContagem(achadoId, ano) {
  const c = { indicio_risco: 0, inconclusivo: 0, sem_dado_publico: 0, sem_indicio: 0 };
  for (const m of CN_MUNICIPIOS) {
    const s = cnStatusDe(m.cod_ibge, achadoId, ano);
    if (s) c[s.status]++;
  }
  return c;
}

/* Quantos municípios têm ao menos um indício no exercício — o número da aba. */
function cncaResumo(ano) {
  if (CN_AUSENTE) return { risco: 0, municipios: 0 };
  const comRisco = new Set();
  for (const e of CN_EV) {
    if (e.status === "indicio_risco" && (ano == null || e.ano == null || e.ano === ano)) comRisco.add(e.municipio_ibge);
  }
  return { risco: comRisco.size, municipios: CN_MUNICIPIOS.length };
}

/* ------------------------------------------------------------- elementos */

function cnLegenda() {
  const box = h("div", { class: "cn-legenda" });
  box.append(h("strong", {}, "Como ler: "));
  for (const [k, rot] of Object.entries(CN_STATUS)) {
    box.append(h("span", { class: "cn-chip " + CN_CLASSE[k] }, CN_SIMBOLO[k] + " " + rot));
  }
  box.append(h("p", { class: "cn-aviso" },
    "Nenhuma célula é achado de auditoria: é indício, e quem o transforma em achado é o auditor, " +
    "com o documento na mão. Célula vazia de dado aparece como “sem dado público”, com o motivo — " +
    "nunca como zero."));
  return box;
}

function cnBadge(status, texto) {
  return h("span", { class: "cn-chip " + CN_CLASSE[status] },
    CN_SIMBOLO[status] + " " + (texto || CN_STATUS[status] || status));
}

function cnBarraStatus(contagem, total) {
  const barra = h("div", { class: "cn-barra", role: "img",
    "aria-label": Object.entries(contagem).map(([k, v]) => v + " " + CN_STATUS[k]).join(", ") });
  for (const k of ["indicio_risco", "inconclusivo", "sem_dado_publico", "sem_indicio"]) {
    const v = contagem[k] || 0;
    if (!v) continue;
    barra.append(h("span", { class: "cn-fatia " + CN_CLASSE[k],
      style: "width:" + (v / total * 100).toFixed(2) + "%", title: v + " " + CN_STATUS[k] }));
  }
  return barra;
}

/* O "ver fonte" desta aba é o MESMO da página inteira (`abrirFonte`, em fonte.js) —
   um só comportamento de proveniência no produto, e não dois parecidos. Para isso,
   os indicadores e as consultas da matriz entram nos catálogos globais que aquele
   diálogo consulta: `META.indicadores` (rótulo, onde está na fonte, cálculo) e
   `CONSULTAS` (a requisição reproduzível). O dataset geral não os conhece, porque
   esta matriz tem ciclo de coleta próprio. */
for (const c of (CN.consultas || [])) if (!CONSULTAS.has(c.id)) CONSULTAS.set(c.id, c);
for (const a of CN_ACHADOS) {
  for (const i of (a.indicadores || [])) {
    if (META.indicadores[i.id]) continue;
    META.indicadores[i.id] = { rotulo: i.rotulo, tema: "cnca", fonte: i.fonte,
      unidade: i.unidade, localizacao: i.fonte, calculo: i.formula };
  }
}

function cnConsultasDe(q) {
  return consultasDe(q);
}

/* O "ver fonte" de uma evidência: a consulta que produziu o número, mais a fórmula
   e a ressalva do indicador. A ressalva vai como observação de propósito — quem
   abre a fonte de um proxy precisa ler o que ele não prova. */
function cnFonte(ev) {
  const a = CN_ACHADO.get(ev.achado_id) || {};
  const ind = (a.indicadores || []).find(i => i.id === ev.indicador) || {};
  const detalhe = [ev.ano ? String(ev.ano) : null, CN_NOME.get(ev.municipio_ibge)]
    .filter(Boolean).join(" · ");
  const observacao = [ev.nota, ...(a.ressalvas || [])].filter(Boolean).join(" ");
  return botaoFonte((ind.rotulo || ev.indicador || a.enunciado) + (ev.ano ? " — " + ev.ano : ""),
    [{ indicador: ev.indicador, ano: ev.ano, detalhe, observacao, q: ev.q }]);
}

/* ------------------------------------------------------------- 1. matriz */

function cnRenderMatriz(raiz) {
  raiz.append(cnLegenda());
  if (CN_CONSTATACOES.length) {
    const card = h("article", { class: "card largo" },
      h("h3", {}, "Constatações — o que vale para os 78, dito uma vez"),
      h("p", { class: "nota" },
        "Quando uma característica atinge todos os municípios por igual, apontá-la 78 vezes " +
        "transformaria um fato sobre a classificação orçamentária em 78 indícios individuais. " +
        "Estas afirmações saem do mapa de calor e vão para o texto do relatório."));
    for (const c of CN_CONSTATACOES) {
      card.append(h("div", { class: "cn-constatacao" },
        h("h4", {}, c.id + " — " + c.enunciado),
        h("p", { class: "cn-medida" }, h("strong", {}, "Medido: "), c.medida),
        h("p", { class: "nota" }, h("strong", {}, "Abrangência: "), c.abrangencia,
          " · ", h("strong", {}, "Fonte: "), c.fonte),
        h("p", { class: "cn-consequencia" }, h("strong", {}, "Consequência: "), c.consequencia)));
    }
    raiz.append(card);
  }

  for (const q of CN_QUESTOES) {
    const card = h("article", { class: "card largo" }, h("h3", {}, q.id + " — " + q.enunciado));
    if (q.nota) card.append(h("p", { class: "nota" }, q.nota));
    const tab = h("table", {},
      h("thead", {}, h("tr", {},
        h("th", {}, "Achado"), h("th", {}, "Evidência"), h("th", {}, "Distribuição dos 78 municípios"),
        h("th", { class: "num" }, "Indícios"))));
    const corpo = h("tbody", {});
    for (const a of q.achados) {
      const c = cnContagem(a.id, cnEstado_.ano);
      const total = Object.values(c).reduce((s, v) => s + v, 0) || 1;
      const tipo = h("span", { class: "cn-tipo", title: (CN_TIPOS[a.tipo_evidencia] || a.tipo_evidencia) +
        " · confiança " + a.confianca }, CN_TIPO_SIMBOLO[a.tipo_evidencia] + " " +
        (CN_TIPOS[a.tipo_evidencia] || a.tipo_evidencia));
      const nome = h("td", {},
        h("button", { type: "button", class: "link", onclick: () => { cnEstado_.achado = a.id; cnEstado_.visao = "mapa"; renderCnca(); } },
          a.id),
        " ", a.enunciado);
      if (a.constatacao) nome.append(h("span", { class: "cn-nota-const" }, " ver constatação " + a.constatacao));
      corpo.append(h("tr", {}, nome, h("td", {}, tipo), h("td", {}, cnBarraStatus(c, total)),
        h("td", { class: "num " + (c.indicio_risco ? "cn-forte" : "") }, String(c.indicio_risco))));
    }
    tab.append(corpo);
    card.append(tab);
    raiz.append(card);
  }
}

/* --------------------------------------------------------------- 2. mapa */

function cnRenderMapa(raiz) {
  raiz.append(cnLegenda());
  const achados = cnEstado_.so_risco
    ? CN_ACHADOS.filter(a => cnContagem(a.id, cnEstado_.ano).indicio_risco > 0)
    : CN_ACHADOS;
  const card = h("article", { class: "card largo" },
    h("h3", {}, "Mapa de evidências — município × achado"),
    h("p", { class: "nota" },
      "Cada célula é o status do município naquele achado" +
      (cnEstado_.ano ? " no exercício de " + cnEstado_.ano : " no pior exercício da série") +
      ". Clique para abrir a ficha do município."));
  const filtros = h("div", { class: "cn-filtros" },
    h("label", {}, h("input", { type: "checkbox", checked: cnEstado_.so_risco,
      onchange: e => { cnEstado_.so_risco = e.target.checked; renderCnca(); } }),
      " só achados com algum indício"));
  card.append(filtros);

  const tab = h("table", { class: "cn-mapa" });
  const cab = h("tr", {}, h("th", { class: "cn-mun" }, "Município"));
  for (const a of achados) cab.append(h("th", { class: "cn-vert", title: a.enunciado }, a.id));
  tab.append(h("thead", {}, cab));
  const corpo = h("tbody", {});
  for (const m of CN_MUNICIPIOS) {
    const tr = h("tr", {}, h("th", { scope: "row", class: "cn-mun" },
      h("button", { type: "button", class: "link",
        onclick: () => { cnEstado_.municipio = m.cod_ibge; cnEstado_.visao = "municipio"; renderCnca(); } },
        m.nome)));
    for (const a of achados) {
      const s = cnStatusDe(m.cod_ibge, a.id, cnEstado_.ano);
      tr.append(h("td", { class: "cn-cel " + (s ? CN_CLASSE[s.status] : ""),
        title: m.nome + " · " + a.id + ": " + (s ? CN_STATUS[s.status] : "sem linha") +
               (s && s.nota ? " — " + s.nota : "") },
        s ? CN_SIMBOLO[s.status] : ""));
    }
    corpo.append(tr);
  }
  tab.append(corpo);
  card.append(h("div", { class: "cn-rolagem" }, tab));
  raiz.append(card);
}

/* ---------------------------------------------------------- 3. município */

function cnRenderMunicipio(raiz) {
  const cod = cnEstado_.municipio || (CN_MUNICIPIOS[0] || {}).cod_ibge;
  if (!cod) { raiz.append(h("p", {}, "Sem municípios no dataset.")); return; }
  const nome = CN_NOME.get(cod);

  const seletor = h("article", { class: "card largo" },
    h("label", { for: "cn-mun" }, "Município: "),
    h("select", { id: "cn-mun", onchange: e => { cnEstado_.municipio = Number(e.target.value); renderCnca(); } },
      ...CN_MUNICIPIOS.map(m => h("option", { value: String(m.cod_ibge), selected: m.cod_ibge === cod }, m.nome))));
  raiz.append(seletor);

  const ficha = h("article", { class: "card largo" }, h("h3", {}, "Ficha de evidências — " + nome));
  for (const q of CN_QUESTOES) {
    const linhas = [];
    for (const a of q.achados) {
      for (const ev of (CN_POR_MUN_ACHADO.get(cod + "|" + a.id) || [])) {
        if (cnEstado_.ano && ev.ano && ev.ano !== cnEstado_.ano) continue;
        const ind = (a.indicadores || []).find(i => i.id === ev.indicador) || {};
        linhas.push(h("tr", {},
          h("td", {}, a.id), h("td", {}, ind.rotulo || ev.indicador || a.enunciado),
          h("td", { class: "num" }, ev.ano == null ? "—" : String(ev.ano)),
          h("td", { class: "num" }, nulo(ev.valor) ? "sem dado" :
            (ind.unidade === "R$" ? brl(ev.valor) : ind.unidade === "%" ? pct(ev.valor) : nf(ev.valor, 0))),
          h("td", {}, cnBadge(ev.status)),
          h("td", { class: "cn-nota" }, ev.nota || ""),
          h("td", {}, cnFonte(ev))));
      }
    }
    if (!linhas.length) continue;
    ficha.append(h("h4", {}, q.id + " — " + q.enunciado));
    ficha.append(h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Achado"), h("th", {}, "Indicador"), h("th", {}, "Ano"),
        h("th", {}, "Valor"), h("th", {}, "Status"), h("th", {}, "O que isto mede (e não mede)"),
        h("th", {}, "Fonte"))),
      h("tbody", {}, ...linhas)));
  }
  raiz.append(ficha);

  /* Tabelas de pergunta, que não classificam achado mas respondem direto. */
  const extras = h("article", { class: "card largo" }, h("h3", {}, "Números que respondem perguntas do questionário"));
  let algum = false;

  const idx = (CN_ANOS.map(a => (cnIndices.get(cod + "|" + a) || []).filter(r => String(r.fonte).startsWith("(todas"))).flat());
  if (idx.length) {
    algum = true;
    extras.append(h("h4", {}, "P24 — os quatro índices de execução (função 12 inteira)"));
    extras.append(h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Ano"), h("th", {}, "Empenhado ÷ dotação"),
        h("th", {}, "Pago ÷ dotação"), h("th", {}, "Liquidado ÷ empenhado"), h("th", {}, "Pago ÷ liquidado"))),
      h("tbody", {}, ...idx.map(r => h("tr", {}, h("td", {}, String(r.ano)),
        h("td", { class: "num" }, pct(r.indice_execucao_orcamentaria)),
        h("td", { class: "num" }, pct(r.indice_execucao_financeira)),
        h("td", { class: "num" }, pct(r.indice_liquidacao)),
        h("td", { class: "num" }, pct(r.indice_pagamento)))))));
  }

  const pd = CN_ANOS.map(a => (cnPdde.get(cod + "|" + a) || [])).flat();
  if (pd.length) {
    algum = true;
    extras.append(h("h4", {}, "P21 — escolas da rede beneficiadas com PDDE-CNCA"));
    extras.append(h("p", { class: "nota" }, (pd[0] || {}).denominador || ""));
    extras.append(h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Ano"), h("th", {}, "Escolas atendidas"),
        h("th", {}, "Escolas da rede"), h("th", {}, "Cobertura"))),
      h("tbody", {}, ...pd.map(r => h("tr", {}, h("td", {}, String(r.ano)),
        h("td", { class: "num" }, nf(r.escolas_com_pdde_cnca || 0)),
        h("td", { class: "num" }, nulo(r.escolas_rede) ? "sem dado" : nf(r.escolas_rede)),
        h("td", { class: "num" }, pct(r.cobertura_pct)))))));
  }

  const rp = CN_ANOS.map(a => (cnRestos.get(cod + "|" + a) || []))
    .flat().filter(r => ["551", "569"].includes(String(r.fonte)));
  if (rp.length) {
    algum = true;
    extras.append(h("h4", {}, "P25 e P26 — restos a pagar nas fontes 551 e 569"));
    extras.append(h("p", { class: "nota" },
      "A idade NÃO sai de RPPTransferido: essa coluna existe no dicionário do TCE-ES e vem " +
      "sempre vazia nos arquivos dos municípios do ES. Sai do AnoEmpenho — um empenho de ano " +
      "anterior que ainda se move no exercício é, por construção, resto a pagar."));
    extras.append(h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Ano"), h("th", {}, "Fonte"), h("th", {}, "Empenhado"),
        h("th", {}, "RP processado inscrito"), h("th", {}, "% do empenhado"),
        h("th", {}, "Idade máxima"), h("th", {}, "Prolongado"))),
      h("tbody", {}, ...rp.map(r => h("tr", {}, h("td", {}, String(r.ano)), h("td", {}, String(r.fonte)),
        h("td", { class: "num" }, brl(r.empenhada || 0)),
        h("td", { class: "num" }, brl(r.rpp_inscrito || 0)),
        h("td", { class: "num" }, pct(r.rpp_pct_empenhado)),
        h("td", { class: "num" }, nulo(r.rp_idade_maxima) ? "—" : nf(r.rp_idade_maxima) + " anos"),
        h("td", {}, r.rpp_prolongado === true ? "sim" : r.rpp_prolongado === false ? "não" : "não medido"))))));
  }

  const es = CN_ANOS.map(a => (cnEstado.get(cod + "|" + a) || [])).flat();
  if (es.length) {
    algum = true;
    extras.append(h("h4", {}, "P18 — recursos do Estado em regime de colaboração"));
    extras.append(h("p", { class: "nota" },
      "Transferências da esfera estadual (SIGEFES) na função 12, modalidade 40/41/42, com este " +
      "município como favorecido. O casamento é pelo NOME do favorecido — o que não casou está " +
      "em cnca_estado_nao_identificados.csv, nunca descartado em silêncio."));
    extras.append(h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Ano"), h("th", {}, "Empenhado"), h("th", {}, "Pago"),
        h("th", {}, "…do qual FUNPAES (empenhado)"))),
      h("tbody", {}, ...es.map(r => h("tr", {}, h("td", {}, String(r.ano)),
        h("td", { class: "num" }, brl(r.empenhado || 0)), h("td", { class: "num" }, brl(r.pago || 0)),
        h("td", { class: "num" }, brl(r.empenhado_funpaes || 0)))))));
  }

  const ct = cnContratos.get(cod) || [];
  if (ct.length) {
    algum = true;
    extras.append(h("h4", {}, "P47 e P48 — contratações de formação e material"));
    extras.append(h("p", { class: "nota" },
      "Classificação por palavra-chave sobre o objeto da contratação, revisável: cada linha traz " +
      "os termos que a fizeram entrar. Contratação revogada, anulada ou fracassada aparece marcada " +
      "e fica fora do valor de P48."));
    extras.append(h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Ano"), h("th", {}, "Categoria"), h("th", {}, "Objeto"),
        h("th", {}, "Termos que casaram"), h("th", {}, "Valor"), h("th", {}, "Situação"))),
      h("tbody", {}, ...ct.map(r => h("tr", { class: r.sem_efeito ? "cn-riscado" : "" },
        h("td", {}, String(r.ano)), h("td", {}, r.categoria_rotulo),
        h("td", { class: "cn-nota" }, r.objeto),
        h("td", { class: "cn-nota" }, r.termos),
        h("td", { class: "num" }, nulo(r.valor_total) ? "sem dado" : brl(r.valor_total)),
        h("td", {}, r.sem_efeito ? "sem efeito — " + r.situacao : (r.situacao || "")))))));
  }

  const bu = cnBuscas.get(cod) || [];
  if (bu.length) {
    algum = true;
    extras.append(h("h4", {}, "Buscas a fazer à mão no diário oficial"));
    extras.append(h("p", { class: "nota" },
      "Este município não tem diário indexado de forma automatizável. A lista abaixo é o que " +
      "buscar, onde e o que registrar — e vale lembrar: não achar o ato não é achar que ele não existe."));
    extras.append(h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Achado"), h("th", {}, "O que procurar"),
        h("th", {}, "Expressão"), h("th", {}, "Onde"), h("th", {}, "Período"))),
      h("tbody", {}, ...bu.map(r => h("tr", {}, h("td", {}, r.achado_id),
        h("td", {}, r.o_que_procurar), h("td", { class: "cn-nota" }, r.expressao),
        h("td", { class: "cn-nota" }, r.onde), h("td", {}, r.periodo))))));
  }

  if (algum) raiz.append(extras);
}

/* ---------------------------------------------------------- 4. perguntas */

function cnRenderPerguntas(raiz) {
  const porBloco = new Map();
  for (const p of CN_PERGUNTAS) {
    if (!porBloco.has(p.bloco)) porBloco.set(p.bloco, []);
    porBloco.get(p.bloco).push(p);
  }
  const rotuloEvid = { direta: "responde direto", proxy: "responde por proxy",
                       parcial: "responde em parte", indisponivel: "só o questionário responde" };
  raiz.append(h("article", { class: "card largo" },
    h("h3", {}, "As 49 perguntas do questionário, e o que o dado já responde"),
    h("p", { class: "nota" },
      "O questionário ainda não foi respondido — esta visão não mostra respostas de município. " +
      "Ela mostra o que o dado público responde de cada pergunta ANTES delas, que é o que permite " +
      "confrontar a resposta quando ela chegar.")));

  for (const [bloco, perguntas] of [...porBloco].sort((a, b) => a[0] - b[0])) {
    const card = h("article", { class: "card largo" }, h("h4", {}, "Bloco " + bloco));
    const corpo = h("tbody", {});
    for (const p of perguntas) {
      corpo.append(h("tr", {},
        h("td", {}, p.id + (p.dados_pessoais ? " 🔒" : "")),
        h("td", {}, p.enunciado),
        h("td", {}, h("span", { class: "cn-chip cn-ev-" + p.evidencia }, rotuloEvid[p.evidencia] || p.evidencia)),
        h("td", { class: "cn-nota" }, p.responde_com),
        h("td", {}, (p.achados || []).join(", "))));
    }
    card.append(h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Nº"), h("th", {}, "Pergunta"), h("th", {}, "Evidência"),
        h("th", {}, "O que o dado responde"), h("th", {}, "Achados"))),
      corpo));
    raiz.append(card);
  }
  raiz.append(h("p", { class: "nota" },
    "🔒 = pergunta que coleta dado pessoal (LGPD e Resolução TC 358/2021). O painel não exibe " +
    "nome, e-mail ou telefone de ninguém, mesmo quando o ato publicado os traz."));
}

/* ---------------------------------------------------------- 5. cobertura */

function cnRenderCobertura(raiz) {
  const cob = CN.cobertura_achados || [];
  const porSituacao = new Map();
  for (const c of cob) porSituacao.set(c.situacao, (porSituacao.get(c.situacao) || 0) + 1);
  const evid = new Map();
  for (const p of CN_PERGUNTAS) evid.set(p.evidencia, (evid.get(p.evidencia) || 0) + 1);

  raiz.append(h("article", { class: "card largo" },
    h("h3", {}, "Painel de cobertura — quanto da matriz o dado público alcança"),
    h("p", { class: "nota" },
      "É o número mais útil desta página para a seção de metodologia do relatório: ele diz, medido, " +
      "o quanto da fiscalização depende dos municípios, de ofício ou de análise documental."),
    h("div", { class: "cn-kpis" },
      ...[...porSituacao].map(([s, n]) => h("div", { class: "cn-kpi" },
        h("span", { class: "cn-kpi-valor" }, String(n)), h("span", { class: "cn-kpi-rotulo" }, s + " (achados)"))),
      ...[...evid].map(([e, n]) => h("div", { class: "cn-kpi" },
        h("span", { class: "cn-kpi-valor" }, String(n)),
        h("span", { class: "cn-kpi-rotulo" }, n + "/" + CN_PERGUNTAS.length + " perguntas: " + e))))));

  const corpo = h("tbody", {});
  for (const c of cob) {
    const a = CN_ACHADO.get(c.achado_id) || {};
    corpo.append(h("tr", {},
      h("td", {}, c.achado_id), h("td", {}, a.enunciado || ""),
      h("td", {}, "fase " + c.fase), h("td", {}, c.situacao),
      h("td", {}, CN_TIPOS[a.tipo_evidencia] || ""),
      h("td", { class: "num cn-forte" }, String(c.n_indicio_risco || 0)),
      h("td", { class: "num" }, String(c.n_inconclusivo || 0)),
      h("td", { class: "num" }, String(c.n_sem_dado_publico || 0)),
      h("td", { class: "num" }, String(c.n_sem_indicio || 0)),
      h("td", { class: "cn-nota" }, (a.ressalvas || []).join(" ")),
      h("td", { class: "cn-nota" }, a.caminho_alternativo || "")));
  }
  raiz.append(h("article", { class: "card largo" },
    h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Achado"), h("th", {}, "Enunciado"), h("th", {}, "Fase"),
        h("th", {}, "Situação"), h("th", {}, "Evidência"), h("th", {}, "Indícios"),
        h("th", {}, "Inconcl."), h("th", {}, "Sem dado"), h("th", {}, "Sem indício"),
        h("th", {}, "Ressalvas"), h("th", {}, "Caminho alternativo"))),
      corpo)));

  const params = (CN.meta || {}).parametros || {};
  const linhasP = Object.entries(params).map(([k, v]) => h("tr", {},
    h("td", {}, k), h("td", { class: "num" }, String(v.valor) + " " + (v.unidade || "")),
    h("td", {}, v.calibrar ? "a calibrar com a equipe" : "fixo"),
    h("td", { class: "cn-nota" }, v.descricao || "")));
  raiz.append(h("article", { class: "card largo" },
    h("h3", {}, "Limiares — todos parametrizáveis"),
    h("p", { class: "nota" },
      "Estão em config/matriz_cnca.yaml. Mudar ali muda o painel inteiro, sem tocar em código. " +
      "A descrição de cada um traz a distribuição real medida, que é o que permite calibrá-lo."),
    h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Parâmetro"), h("th", {}, "Valor"),
        h("th", {}, "Situação"), h("th", {}, "Por quê"))),
      h("tbody", {}, ...linhasP))));

  const lim = (CN.meta || {}).limitacoes || {};
  if (Object.keys(lim).length) {
    raiz.append(h("article", { class: "card largo" },
      h("h3", {}, "Limitações estruturais"),
      ...Object.values(lim).map(t => h("p", { class: "cn-limite" }, t))));
  }
}

/* ---------------------------------------------------------- 6. exportar */

function cnCsv() {
  const cols = ["municipio_ibge", "municipio", "questao_matriz", "achado_id", "pergunta_questionario",
                "indicador", "rotulo", "valor", "unidade", "ano", "status", "tipo_evidencia",
                "confianca", "fonte", "nota", "endpoint_ou_arquivo", "obtido_em", "hash_bruto"];
  const linhas = [cols.join(";")];
  for (const e of CN_EV) {
    const a = CN_ACHADO.get(e.achado_id) || {};
    const ind = (a.indicadores || []).find(i => i.id === e.indicador) || {};
    const c = (cnConsultasDe(e.q) || [])[0] || {};
    const v = {
      municipio_ibge: e.municipio_ibge, municipio: CN_NOME.get(e.municipio_ibge) || "",
      questao_matriz: a.questao || "", achado_id: e.achado_id,
      pergunta_questionario: (a.perguntas || []).join(" "),
      indicador: e.indicador || "", rotulo: ind.rotulo || "",
      valor: nulo(e.valor) ? "" : e.valor, unidade: ind.unidade || "",
      ano: e.ano == null ? "" : e.ano, status: CN_STATUS[e.status] || e.status,
      tipo_evidencia: CN_TIPOS[a.tipo_evidencia] || "", confianca: a.confianca || "",
      fonte: ind.fonte || "", nota: e.nota || "",
      endpoint_ou_arquivo: c.arquivo || c.url || "", obtido_em: c.obtido_em || "",
      hash_bruto: c.sha256 || "",
    };
    linhas.push(cols.map(k => {
      const s = String(v[k] ?? "");
      return /[";\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    }).join(";"));
  }
  return linhas.join("\n");
}

function cnRenderExportar(raiz) {
  raiz.append(h("article", { class: "card largo" },
    h("h3", {}, "Exportar o papel de trabalho"),
    h("p", {},
      "Uma linha por município × achado × indicador, com valor, status, tipo de evidência, " +
      "confiança, a ressalva do indicador e a proveniência completa — endpoint ou arquivo do " +
      "cache, instante da coleta e SHA-256 do arquivo bruto."),
    h("p", { class: "nota" },
      "É o mesmo conteúdo de dados/evidencias/evidencias_cnca.csv, que o ETL grava em CSV e " +
      "parquet. O botão existe para quem está com a página aberta e não com o repositório."),
    h("button", { type: "button", class: "acao", onclick: () => {
      const blob = new Blob(["﻿" + cnCsv()], { type: "text/csv;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "evidencias_cnca_" + new Date().toISOString().slice(0, 10) + ".csv";
      a.click();
      URL.revokeObjectURL(a.href);
    } }, "Baixar evidências (CSV)"),
    h("p", { class: "nota" }, CN_EV.length.toLocaleString("pt-BR") + " linhas de evidência, " +
      CN_MUNICIPIOS.length + " municípios, " + CN_ACHADOS.length + " achados, " +
      CN_PERGUNTAS.length + " perguntas.")));
}

/* ------------------------------------------------------------ orquestra */

const CN_VISOES = [
  { id: "matriz", rotulo: "Matriz", render: cnRenderMatriz },
  { id: "mapa", rotulo: "Mapa de evidências", render: cnRenderMapa },
  { id: "municipio", rotulo: "Ficha do município", render: cnRenderMunicipio },
  { id: "perguntas", rotulo: "Perguntas (P1–P49)", render: cnRenderPerguntas },
  { id: "cobertura", rotulo: "Cobertura", render: cnRenderCobertura },
  { id: "exportar", rotulo: "Exportar", render: cnRenderExportar },
];

function renderCnca() {
  const raiz = limpar($("#conteudo"));
  if (CN_AUSENTE) {
    raiz.append(h("article", { class: "card largo" },
      h("h3", {}, "Matriz de evidências do CNCA — não gerada"),
      h("p", {}, (CN.meta || {}).motivo || "dataset ausente"),
      h("p", { class: "nota" },
        "Rode, a partir da raiz do repositório: python -m financiamento.etl.execucao · " +
        "python -m financiamento.etl.censo_alfabetizacao · python -m financiamento.etl.contratos · " +
        "python -m financiamento.etl.diarios · python -m financiamento.etl.estado · " +
        "python -m financiamento.etl.evidencias · python -m financiamento.build_dashboard")));
    return;
  }
  raiz.append(h("nav", { class: "cn-abas", role: "tablist" },
    ...CN_VISOES.map(v => h("button", { type: "button", role: "tab",
      "aria-selected": String(v.id === cnEstado_.visao),
      onclick: () => { cnEstado_.visao = v.id; renderCnca(); } }, v.rotulo)),
    h("label", { class: "cn-ano" }, "Exercício: ",
      h("select", { onchange: e => { cnEstado_.ano = e.target.value ? Number(e.target.value) : null; renderCnca(); } },
        h("option", { value: "", selected: cnEstado_.ano == null }, "todos (pior status)"),
        ...CN_ANOS.map(a => h("option", { value: String(a), selected: cnEstado_.ano === a }, String(a)))))));
  (CN_VISOES.find(v => v.id === cnEstado_.visao) || CN_VISOES[0]).render(raiz);
}
