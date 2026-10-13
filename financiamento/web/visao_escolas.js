"use strict";
/* ============================================================================
   Visão Escolas — o dinheiro que chega a cada escola pública, ao lado do que o
   Censo Escolar diz dela (matrículas, infraestrutura, IDEB, PAEBES).
   Três canais, os únicos em dado aberto que nomeiam o recebedor:
     PDDE (FNDE → unidade executora, por plano orçamentário — inclui o CNCA),
     repasse do município ao conselho escolar (empenhos do TCE-ES),
     obra no prédio (contratações do TCE-ES, bem vinculador).
   O vínculo recebedor → escola é pelo NOME (nenhuma fonte financeira traz o
   código INEP): cada um tem nota e método, e o que é ambíguo fica de fora.
   Também aqui: o bloco automático do CNCA para a visão Programas.
   ========================================================================== */

const RECURSOS_ESCOLA = agrupar(expandir(D.escolas_recursos), r => r.co_entidade);
const ESCOLAS_MUN = agrupar([...ESCOLAS.values()], e => e.cod_ibge);
const VINCULOS_ESCOLA = agrupar(VINCULOS.filter(v => v.co_entidade), v => v.co_entidade);
const PO_CNCA = "000C", PO_ALFA = "0007";
const ROT_CANAL = { pdde: "PDDE (FNDE)", repasse_municipal: "Repasse do município", obra: "Obra no prédio" };
/** Zero aqui é "nenhum repasse ligado à escola", não ausência de dado da fonte. */
const moedaOuTraco = v => nulo(v) || !v ? "—" : brl(v);
const INFRA = [["internet", "internet"], ["biblioteca", "biblioteca"], ["lab_informatica", "lab. informática"], ["quadra", "quadra"],
  ["agua_potavel", "água potável"], ["esgoto", "esgoto (rede)"], ["rampas", "rampas"]];

const municipioEscolas = () => {
  if (!estado.municipio || ENTES.get(estado.municipio).esfera !== "M") estado.municipio = MUNICIPIOS[0].cod_ibge;
  return estado.municipio;
};
/** Recursos da escola no ano, por canal (PDDE separado em CNCA e demais POs). */
function recursosNoAno(co, ano) {
  const rs = (RECURSOS_ESCOLA.get(co) || []).filter(r => r.ano === ano);
  const soma = f => rs.filter(f).reduce((s, r) => s + (r.valor || 0), 0);
  return { rs, pdde: soma(r => r.canal === "pdde"), cnca: soma(r => r.canal === "pdde" && (r.po === PO_CNCA || r.po === PO_ALFA)),
    municipal: soma(r => r.canal === "repasse_municipal"), obra: soma(r => r.canal === "obra") };
}

function escolasFiltros(destino) {
  const rede = h("select", { id: "f-rede-esc", onchange: e => { estado.rede = e.target.value; estado.escola = null; render(); } },
    h("option", { value: "todas" }, "Municipal e estadual"), h("option", { value: "municipal" }, "Só rede municipal"), h("option", { value: "estadual" }, "Só rede estadual"));
  rede.value = estado.rede;
  destino.append(h("div", { class: "linha" },
    campo("Município (onde a escola fica)", seletorEnte("f-mun-esc", municipioEscolas(), cod => { estado.municipio = cod; estado.escola = null; render(); })),
    campo("Exercício", seletorAno("f-ano-esc", estado.ano, v => { estado.ano = v; render(); })),
    campo("Rede", rede)));
}

function kpisEscolas(cod, ano, escolas) {
  const r = escolas.map(e => ({ e, x: recursosNoAno(e.co_entidade, ano) }));
  const com = f => r.filter(l => l.x[f] > 0);
  const soma = f => r.reduce((s, l) => s + l.x[f], 0);
  const mat = escolas.reduce((s, e) => s + (e.matriculas || 0), 0);
  return h("div", { class: "kpis" },
    kpi("Escolas públicas no Censo", nf(escolas.length), nf(mat) + " matrículas · " + escolas.filter(e => e.rede === "municipal").length + " municipais, " + escolas.filter(e => e.rede === "estadual").length + " estaduais"),
    kpi("PDDE identificado por escola — " + ano, brlCompacto(soma("pdde")), com("pdde").length + " escola(s) com repasse ligado ao Censo"),
    kpi("…do qual alfabetização (CNCA 000C e PDDE-Alfabetização 0007)", brlCompacto(soma("cnca")), com("cnca").length + " escola(s)"),
    kpi("Repasse do município a conselhos — " + ano, EMPENHOS_COLETADOS ? brlCompacto(soma("municipal")) : "n/d",
      EMPENHOS_COLETADOS ? com("municipal").length + " escola(s) identificada(s)" : "empenhos do TCE-ES não coletados", { nd: !EMPENHOS_COLETADOS }));
}

function cardTabelaEscolas(cod, ano, escolas) {
  const nome = ENTES.get(cod).nome;
  const card = h("article", { class: "card largo" }, cabecalho("Escolas de " + nome + " — recursos identificados em " + ano + " e resultados",
    "Uma linha por escola pública ativa (Censo). Clique no nome para ver tudo o que chegou à escola, ano a ano, com a fonte. Vazio = nenhum repasse LIGADO à escola (pode haver repasse a um recebedor que não foi identificado no Censo — lista no fim).",
    { itens: () => [{ indicador: "escola_recurso", ano, detalhe: "escolas de " + nome, q: escolas.flatMap(e => recursosNoAno(e.co_entidade, ano).rs.map(r => r.q)).concat([(escolas[0] || {}).q]).join(";") }] }));
  const linhas = escolas.map(e => ({ e, x: recursosNoAno(e.co_entidade, ano) }))
    .sort((a, b) => (b.x.pdde + b.x.municipal) - (a.x.pdde + a.x.municipal) || a.e.nome.localeCompare(b.e.nome, "pt-BR"));
  const porAluno = l => l.e.matriculas > 0 && (l.x.pdde + l.x.municipal) > 0 ? (l.x.pdde + l.x.municipal) / l.e.matriculas : null;
  const obraNoPredio = l => (RECURSOS_ESCOLA.get(l.e.co_entidade) || []).filter(r => r.canal === "obra").reduce((s, r) => s + r.valor, 0) || null;
  const ideb = (v, a) => nulo(v) ? "—" : nf(v, 1) + (a ? " (" + a + ")" : "");
  const colunas = [
    { rotulo: "Escola", valor: l => l.e.nome, render: l => h("span", {}, botaoEscola(l.e.co_entidade), h("br"), h("span", { class: "nota" }, "INEP " + l.e.co_entidade + " · " + l.e.rede)) },
    { rotulo: "Matrículas", num: true, valor: l => l.e.matriculas, fmt: v => nf(v) },
    { rotulo: "PDDE (R$)", num: true, valor: l => l.x.pdde || null, render: l => moedaOuTraco(l.x.pdde) },
    { rotulo: "…alfabetização: CNCA/0007 (R$)", num: true, valor: l => l.x.cnca || null, render: l => moedaOuTraco(l.x.cnca) },
    { rotulo: "Repasse municipal (R$)", num: true, valor: l => l.x.municipal || null,
      render: l => EMPENHOS_COLETADOS ? moedaOuTraco(l.x.municipal) : "n/d" },
    { rotulo: "R$ por aluno (PDDE + municipal)", num: true, valor: porAluno, render: l => moedaOuTraco(porAluno(l)) },
    { rotulo: "Obra no prédio (contratos, R$)", num: true, valor: obraNoPredio, render: l => moedaOuTraco(obraNoPredio(l)) },
    { rotulo: "IDEB anos iniciais", num: true, valor: l => l.e.ideb_ai, render: l => ideb(l.e.ideb_ai, l.e.ideb_ai_ano) },
    { rotulo: "IDEB anos finais", num: true, valor: l => l.e.ideb_af, render: l => ideb(l.e.ideb_af, l.e.ideb_af_ano) },
    { rotulo: "PAEBES 5º ano LP / MT", num: true, valor: l => l.e.paebes_5_lp,
      render: l => nulo(l.e.paebes_5_lp) && nulo(l.e.paebes_5_mt) ? "—" : (nulo(l.e.paebes_5_lp) ? "—" : nf(l.e.paebes_5_lp, 0)) + " / " + (nulo(l.e.paebes_5_mt) ? "—" : nf(l.e.paebes_5_mt, 0)) },
  ];
  card.append(tabela(colunas, linhas, "Escolas de " + nome + ", " + ano, { destacar: l => l.e.co_entidade === estado.escola }),
    botaoCSV("escolas_" + cod + "_" + ano + ".csv", colunas, linhas));
  card.append(h("p", { class: "nota" }, "IDEB e PAEBES: último resultado da escola no banco do NEDUC (ano entre parênteses). O PAEBES do 5º ano só está carregado para " +
    (Math.max(0, ...escolas.map(e => e.paebes_ano || 0)) || "nenhum ano") + ". Resultados são contexto, não efeito do repasse: o painel não estabelece relação causal."));
  return card;
}

function cardDetalheEscola(co) {
  const e = ESCOLAS.get(co);
  if (!e) return null;
  const rs = (RECURSOS_ESCOLA.get(co) || []).slice().sort((a, b) => (b.ano || 0) - (a.ano || 0) || a.canal.localeCompare(b.canal));
  const vinc = VINCULOS_ESCOLA.get(co) || [];
  const card = h("article", { class: "card largo destaque-escola", id: "detalhe-escola" }, cabecalho(e.nome + " — tudo o que chegou à escola",
    "INEP " + co + " · rede " + e.rede + " · " + ENTES.get(e.cod_ibge).nome + " · Censo " + (e.ano_censo || "—") + ". Valores por ano e canal; cada linha tem a consulta de origem.",
    { itens: () => rs.map(r => ({ indicador: "escola_recurso", ano: r.ano, detalhe: "INEP " + co + " · " + (r.canal === "pdde" ? "PDDE " + r.po + " (" + r.po_nome + ")" : ROT_CANAL[r.canal]),
      q: r.q, valor: brl(r.valor), observacao: r.detalhe || null })).concat([{ indicador: "escola_recurso", ano: estado.ano, detalhe: "cadastro da escola (Censo)", q: e.q }]) }));
  card.append(h("div", { class: "faixa" },
    h("span", { class: "item" }, nf(e.matriculas || 0) + " matrículas"), h("span", { class: "item" }, nf(e.docentes || 0) + " docentes"),
    INFRA.map(([c, rot]) => h("span", { class: "item" }, (e[c] === 1 || e[c] === true ? "✔ " : e[c] === 0 || e[c] === false ? "✖ sem " : "? ") + rot)),
    linkMapa(e.lat, e.lon, "localização (Censo)")));
  if (!rs.length) card.append(h("p", {}, h("span", { class: "badge nada" }, "Nenhum repasse ligado a esta escola"),
    " nas fontes do painel. Pode haver repasse a uma unidade executora que não foi identificada no Censo (ver a lista de não identificadas)."));
  else {
    const anos = [...new Set(rs.map(r => r.ano).filter(a => !nulo(a)))].sort();
    const porAno = anos.map(a => ({ a, ...recursosNoAno(co, a) }));
    card.append(h("div", { class: "tabela-wrap inteira" }, tabela([
      { rotulo: "Ano", valor: l => l.a },
      { rotulo: "PDDE total (R$)", num: true, valor: l => l.pdde || null, render: l => moedaOuTraco(l.pdde) },
      { rotulo: "…alfabetização: CNCA/0007 (R$)", num: true, valor: l => l.cnca || null, render: l => moedaOuTraco(l.cnca) },
      { rotulo: "Repasse municipal (R$)", num: true, valor: l => l.municipal || null, render: l => moedaOuTraco(l.municipal) },
      { rotulo: "Obras assinadas (R$)", num: true, valor: l => l.obra || null, render: l => moedaOuTraco(l.obra) },
    ], porAno, "Recursos por ano — " + e.nome, { inteira: true })));
    const colunas = [
      { rotulo: "Ano", valor: r => r.ano },
      { rotulo: "Canal", valor: r => ROT_CANAL[r.canal] },
      { rotulo: "Programa / detalhe", valor: r => r.canal === "pdde" ? r.po + " — " + r.po_nome : r.detalhe,
        render: r => r.canal === "pdde" ? h("span", {}, h("strong", {}, r.po), " " + r.po_nome,
          r.po === PO_CNCA ? [" ", h("span", { class: "badge api" }, "CNCA")] : r.po === PO_ALFA ? [" ", h("span", { class: "badge api" }, "antecessor do CNCA")] : null)
          : r.canal === "obra" ? h("span", {}, "contrato(s) " + String(r.detalhe || "").split(";").length) : (r.detalhe || "—") },
      { rotulo: "Valor (R$)", num: true, valor: r => r.valor, fmt: brl },
      { rotulo: "Fonte", valor: () => "", render: r => botaoFonte(e.nome + " — " + ROT_CANAL[r.canal] + " " + r.ano, () => [{ indicador: "escola_recurso", ano: r.ano,
        detalhe: "INEP " + co + " · " + (r.canal === "pdde" ? "PDDE " + r.po + " (" + r.po_nome + ")" : ROT_CANAL[r.canal]), q: r.q, valor: brl(r.valor), observacao: r.detalhe || null }]) },
    ];
    card.append(blocoTabela("repasses da escola", colunas, rs, "escola_" + co + ".csv"));
  }
  const obrasDaEscola = [];
  for (const o of OBRAS_EDU.get(e.cod_ibge) || []) bensDe(o).forEach((b, i) => { const v = VINCULO_POR_ORIGEM.get("obra|" + o.chave + "#" + i); if (v && v.co_entidade === co) obrasDaEscola.push(o); });
  if (obrasDaEscola.length) card.append(h("h4", {}, "Obras no prédio"), h("ul", { class: "lista" }, [...new Set(obrasDaEscola)].map(o =>
    h("li", {}, String(o.objeto || "").slice(0, 140), " · ", seloObra(o.situacao), " · " + brl(o.valor || 0) + (nulo(o.pct_medido) ? "" : " · " + nf(o.pct_medido, 0) + "% medido")))));
  card.append(h("details", { class: "tab" }, h("summary", {}, "Como a escola foi identificada (" + vinc.length + " vínculo(s))"),
    h("ul", { class: "lista" }, vinc.map(v => h("li", {}, h("strong", {}, ({ pdde: "PDDE", conselho: "Conselho (empenhos)", obra: "Obra" })[v.fonte] + ": "),
      v.nome_origem + " → " + v.metodo + " (nota " + nf(v.nota || 0, 2) + ")")))));
  card.append(h("button", { type: "button", class: "leve", onclick: () => { estado.escola = null; render(); } }, "Fechar detalhe"));
  return card;
}

function cardNaoIdentificadas(cod, ano) {
  const nome = ENTES.get(cod).nome;
  const soltos = VINCULOS.filter(v => v.cod_ibge === cod && !v.co_entidade);
  const card = h("article", { class: "card largo" }, cabecalho("Recebedores de " + nome + " não identificados no Censo",
    "O vínculo é por nome; quando ele é ambíguo (duas escolas com nomes parecidos) ou não passa no limiar, o recebedor fica aqui — com o nome como veio da fonte — em vez de ser atribuído a uma escola por palpite."));
  if (!soltos.length) { card.append(h("p", {}, "Todos os recebedores deste município foram ligados a uma escola do Censo.")); return card; }
  const colunas = [
    { rotulo: "Canal", valor: v => ({ pdde: "PDDE", conselho: "Repasse municipal", obra: "Obra" })[v.fonte] },
    { rotulo: "Nome na fonte", valor: v => v.nome_origem },
    { rotulo: "Por que ficou sem vínculo", valor: v => v.metodo + (v.nota ? " (nota " + nf(v.nota, 2) + ")" : "") },
  ];
  card.append(tabela(colunas, soltos, "Recebedores não identificados — " + nome, { inteira: true }), botaoCSV("nao_identificados_" + cod + ".csv", colunas, soltos));
  return card;
}

function renderEscolas(destino) {
  const cod = municipioEscolas(), ano = estado.ano;
  const escolas = (ESCOLAS_MUN.get(cod) || []).filter(e => estado.rede === "todas" || e.rede === estado.rede);
  destino.append(h("div", { class: "ficha-topo" }, h("h2", {}, ENTES.get(cod).nome), h("span", { class: "codigo" }, "Código IBGE " + cod + " · exercício " + ano),
    h("button", { type: "button", class: "leve", onclick: () => irPara("fluxo") }, "Receita → aplicação do município →")));
  if (!ESCOLAS.size) {
    destino.append(h("div", { class: "callout warn" }, "O cadastro do Censo não foi carregado nesta execução (banco local do NEDUC indisponível e sem retrato em cache)."));
    return;
  }
  destino.append(kpisEscolas(cod, ano, escolas));
  const detalhe = estado.escola && ESCOLAS.get(estado.escola) && ESCOLAS.get(estado.escola).cod_ibge === cod ? cardDetalheEscola(estado.escola) : null;
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" },
    detalhe, cardTabelaEscolas(cod, ano, escolas), cardNaoIdentificadas(cod, ano))));
  if (detalhe) setTimeout(() => { const el = document.getElementById("detalhe-escola"); if (el) el.scrollIntoView({ block: "start" }); }, 0);
}

/* ================================================== CNCA (visão Programas) */

const CNCA_MUN = (D.cnca || {}).municipio || [];
const CNCA_ESC = expandir((D.cnca || {}).escolas);
const CNCA_EST = (D.cnca || {}).estado || [];
const CNCA_FUNPAES = expandir((D.cnca || {}).funpaes);

/** Os cards automáticos do CNCA — o bloco `modulo_automatico: cnca` do programas.yaml. */
function cardsCnca(p) {
  const ano = estado.ano;
  const noAno = CNCA_MUN.filter(r => r.ano === ano && (r.pdde_cnca > 0 || r.pdde_alfabetizacao > 0));
  const total = noAno.reduce((s, r) => s + (r.pdde_cnca || 0), 0), alfa = noAno.reduce((s, r) => s + (r.pdde_alfabetizacao || 0), 0);
  const escolas = noAno.reduce((s, r) => s + (r.escolas_cnca || 0), 0);
  const estadoAno = CNCA_EST.filter(r => r.ano === ano), estadoTotal = estadoAno.reduce((s, r) => s + r.valor, 0);
  const qMun = noAno.map(r => r.q).join(";");

  const resumo = h("article", { class: "card largo" }, cabecalho("CNCA — repasses automáticos em " + ano,
    "O CNCA tem plano orçamentário próprio nas transferências do FNDE publicadas pela CGU: ação 0515 (PDDE), PO 000C, pago escola a escola; e ação 0509, PO 0014, pago ao Estado (SEDU), que coordena o programa no ES.",
    { itens: () => [{ indicador: "cnca_pdde", ano, detalhe: "000C", q: qMun, valor: brl(total) }].concat(estadoAno.map(r => ({ indicador: "cnca_estado", ano, detalhe: r.favorecido, q: r.q, valor: brl(r.valor) }))) }));
  resumo.append(h("div", { class: "kpis" },
    kpi("PDDE-CNCA às escolas dos municípios", total ? brlCompacto(total) : "R$ 0", noAno.filter(r => r.pdde_cnca > 0).length + " município(s) · " + nf(escolas) + " escola(s) municipais e estaduais", { prog: true }),
    kpi("PDDE-Alfabetização (antecessor, PO 0007)", alfa ? brlCompacto(alfa) : "R$ 0", "programa de 2021–2022", { prog: true, nd: !alfa }),
    kpi("Apoio ao Estado (ação 0509, PO 0014)", estadoTotal ? brlCompacto(estadoTotal) : "R$ 0", estadoAno.length ? estadoAno.map(r => String(r.mes).padStart(2, "0") + "/" + r.ano).join(", ") : "nenhum pagamento no ano", { prog: true, nd: !estadoTotal }),
    kpi("Gasto municipal identificado como FUNPAES", EMPENHOS_COLETADOS ? brlCompacto(CNCA_FUNPAES.filter(r => r.ano === ano).reduce((s, r) => s + r.empenhada, 0)) : "n/d",
      EMPENHOS_COLETADOS ? "empenhos com \"FUNPAES\" no programa, ação ou detalhamento" : "empenhos do TCE-ES não coletados", { prog: true, nd: !EMPENHOS_COLETADOS })));
  const serie = ANOS.map(a => ({ a, v: CNCA_MUN.filter(r => r.ano === a).reduce((s, r) => s + (r.pdde_cnca || 0), 0),
    alfa: CNCA_MUN.filter(r => r.ano === a).reduce((s, r) => s + (r.pdde_alfabetizacao || 0), 0), est: CNCA_EST.filter(r => r.ano === a).reduce((s, r) => s + r.valor, 0) }));
  resumo.append(tabela([
    { rotulo: "Exercício", valor: l => l.a },
    { rotulo: "PDDE-CNCA, escolas dos municípios (R$)", num: true, valor: l => l.v, fmt: brl },
    { rotulo: "PDDE-Alfabetização (R$)", num: true, valor: l => l.alfa, fmt: brl },
    { rotulo: "Apoio ao Estado (R$)", num: true, valor: l => l.est, fmt: brl },
  ], serie, "CNCA por exercício", { inteira: true }),
    h("p", { class: "nota" }, "Mês de pagamento da CGU, não de competência. O PDDE-CNCA inclui escolas estaduais localizadas nos municípios (a unidade executora recebe direto). Em que cada escola gastou não está em dado aberto: ela presta contas ao FNDE."));

  const cod = estado.municipio && ENTES.get(estado.municipio).esfera === "M" ? estado.municipio : null;
  const porMun = h("article", { class: "card largo" }, cabecalho("PDDE-CNCA por município e por escola — " + ano,
    "Soma do que o FNDE pagou às unidades executoras das escolas de cada município. Escolha um município para ver as escolas.",
    { itens: () => noAno.map(r => ({ indicador: "cnca_pdde", ano, detalhe: "000C — " + ENTES.get(r.cod_ibge).nome, q: r.q, valor: brl(r.pdde_cnca || 0) })) }));
  const linhas = noAno.slice().sort((a, b) => (b.pdde_cnca || 0) - (a.pdde_cnca || 0));
  const colunas = [
    { rotulo: "Município", valor: r => ENTES.get(r.cod_ibge).nome, render: r => h("button", { type: "button", class: "link",
      onclick: () => { estado.municipio = r.cod_ibge; render(); } }, ENTES.get(r.cod_ibge).nome) },
    { rotulo: "PDDE-CNCA (R$)", num: true, valor: r => r.pdde_cnca, render: r => moedaOuTraco(r.pdde_cnca) },
    { rotulo: "Escolas", num: true, valor: r => r.escolas_cnca, render: r => r.escolas_cnca ? nf(r.escolas_cnca) : "—" },
    { rotulo: "PDDE-Alfabetização (R$)", num: true, valor: r => r.pdde_alfabetizacao, render: r => moedaOuTraco(r.pdde_alfabetizacao) },
  ];
  porMun.append(linhas.length ? tabela(colunas, linhas, "PDDE-CNCA por município, " + ano, { destacar: r => r.cod_ibge === cod })
    : h("p", {}, h("span", { class: "badge nada" }, "Nenhum repasse"), " do PDDE-CNCA ou do PDDE-Alfabetização em " + ano + "."));
  if (linhas.length) porMun.append(botaoCSV("cnca_municipios_" + ano + ".csv", colunas, linhas));
  if (cod) {
    const doMun = CNCA_ESC.filter(r => r.cod_ibge === cod && r.ano === ano).sort((a, b) => b.valor - a.valor);
    const vinc = r => VINCULO_POR_ORIGEM.get("pdde|" + r.cnpj_uex);
    porMun.append(h("h4", {}, "Escolas de " + ENTES.get(cod).nome + " em " + ano), doMun.length ? tabela([
      { rotulo: "Unidade executora", valor: r => r.uex },
      { rotulo: "Escola no Censo", valor: r => { const v = vinc(r); return v && v.co_entidade ? (ESCOLAS.get(v.co_entidade) || {}).nome : ""; },
        render: r => { const v = vinc(r); return v && v.co_entidade ? botaoEscola(v.co_entidade) : h("span", { class: "muted" }, "não identificada"); } },
      { rotulo: "Programa", valor: r => r.programa === "pdde_cnca" ? "CNCA (000C)" : "Alfabetização (0007)" },
      { rotulo: "Valor (R$)", num: true, valor: r => r.valor, fmt: brl },
      { rotulo: "Fonte", valor: () => "", render: r => botaoFonte(r.uex + " — " + ano, () => [{ indicador: "cnca_pdde", ano, detalhe: r.programa === "pdde_cnca" ? "000C" : "0007",
        q: r.q, valor: brl(r.valor), observacao: "unidade executora " + fmtDoc(r.cnpj_uex) + " — " + r.uex }]) },
    ], doMun, "Escolas com PDDE-CNCA — " + ENTES.get(cod).nome, { inteira: true }) : h("p", { class: "muted" }, "Nenhuma escola do município recebeu em " + ano + "."));
  }

  const fp = CNCA_FUNPAES.filter(r => r.ano === ano && (!cod || r.cod_ibge === cod)).sort((a, b) => b.empenhada - a.empenhada);
  const funpaes = h("article", { class: "card largo" }, cabecalho("Onde o município gastou: FUNPAES (PAES/CNCA no ES) — " + ano + (cod ? ", " + ENTES.get(cod).nome : ", todos os municípios"),
    "No ES, o CNCA é implementado dentro do PAES; o FUNPAES (Lei estadual 10.787/2017) repassa recursos aos municípios. Só aparece aqui o que o município NOMEOU como FUNPAES no programa, na ação ou no detalhamento da fonte dos empenhos.",
    { itens: () => fp.slice(0, 40).map(r => ({ indicador: "funpaes_empenho", ano, detalhe: r.NomeAcao + " · " + r.DescricaoElemento + " · " + r.credor + " — " + r.credor_nome, q: r.q, valor: brl(r.empenhada) })) }));
  if (!EMPENHOS_COLETADOS) funpaes.append(avisoEmpenhos());
  else if (!fp.length) funpaes.append(h("p", {}, h("span", { class: "badge nada" }, "Nenhum empenho identificado"), " como FUNPAES" + (cod ? " em " + ENTES.get(cod).nome : "") + " em " + ano +
    ". Ausência aqui não prova que o recurso não foi usado: o município pode ter registrado com outro nome."));
  else {
    const porElem = agrupar(fp, r => r.DescricaoElemento);
    const itens = [...porElem.entries()].map(([nome, rs]) => ({ nome, codigo: rs.length + " lanç.", empenhada: rs.reduce((s, r) => s + r.empenhada, 0) })).sort((a, b) => b.empenhada - a.empenhada);
    const tot = itens.reduce((s, i) => s + i.empenhada, 0);
    funpaes.append(h("p", {}, h("strong", {}, brl(tot)), " empenhados, por natureza da despesa:"), barrasSubfuncao(itens, tot));
    const colunas = [
      { rotulo: "Município", valor: r => ENTES.get(r.cod_ibge).nome },
      { rotulo: "Ação", valor: r => r.NomeAcao }, { rotulo: "Elemento", valor: r => r.DescricaoElemento },
      { rotulo: "Credor", valor: r => r.credor_nome + (r.credor ? " (" + fmtDoc(r.credor) + ")" : "") },
      { rotulo: "Empenhado (R$)", num: true, valor: r => r.empenhada, fmt: brl }, { rotulo: "Pago (R$)", num: true, valor: r => r.paga, fmt: brl },
    ];
    funpaes.append(blocoTabela("empenhos FUNPAES", colunas, fp, "funpaes_" + (cod || "todos") + "_" + ano + ".csv"));
  }
  return [resumo, porMun, funpaes];
}
