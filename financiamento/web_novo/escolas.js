"use strict";
/* ============================================================================
   Escolas — o dinheiro que chega a cada escola pública, ao lado do que o Censo
   diz dela. É uma seção do dossiê do município (decisão D9). Três canais, os
   únicos em dado aberto que nomeiam o recebedor: PDDE (FNDE → unidade
   executora), repasse do município ao conselho escolar (empenhos do TCE-ES) e
   obra no prédio (contratações do TCE-ES). O vínculo recebedor → escola é pelo
   NOME: cada um tem nota e método, e o que é ambíguo fica de fora.

   Também aqui: os cards automáticos do CNCA usados em Programas federais.
   ========================================================================== */

const RECURSOS_ESCOLA = agrupar(expandir(D.escolas_recursos), r => r.co_entidade);
const ESCOLAS_MUN = agrupar([...ESCOLAS.values()], e => e.cod_ibge);
const VINCULOS_ESCOLA = agrupar(VINCULOS.filter(v => v.co_entidade), v => v.co_entidade);
const PO_CNCA = "000C", PO_ALFA = "0007";
const ROT_CANAL = { pdde: "PDDE (FNDE)", repasse_municipal: "Repasse do município", obra: "Obra no prédio" };
const REDES = { todas: "Municipal e estadual", municipal: "Só rede municipal", estadual: "Só rede estadual" };
const INFRA = [["internet", "internet"], ["biblioteca", "biblioteca"], ["lab_informatica", "laboratório de informática"], ["quadra", "quadra"],
  ["agua_potavel", "água potável"], ["esgoto", "esgoto (rede)"], ["rampas", "rampas de acessibilidade"]];
/** Zero aqui é "nenhum repasse ligado à escola", não ausência de dado da fonte. */
const moedaOuNenhum = v => nulo(v) || !v ? h("span", { class: "muted" }, "nenhum") : brl(v);

function recursosNoAno(co, ano) {
  const rs = (RECURSOS_ESCOLA.get(co) || []).filter(r => r.ano === ano);
  const soma = f => rs.filter(f).reduce((t, r) => t + (r.valor || 0), 0);
  return { rs, pdde: soma(r => r.canal === "pdde"), cnca: soma(r => r.canal === "pdde" && (r.po === PO_CNCA || r.po === PO_ALFA)),
    municipal: soma(r => r.canal === "repasse_municipal"), obra: soma(r => r.canal === "obra") };
}

function kpisEscolas(ano, escolas) {
  const r = escolas.map(e => ({ e, x: recursosNoAno(e.co_entidade, ano) }));
  const com = f => r.filter(l => l.x[f] > 0), soma = f => r.reduce((t, l) => t + l.x[f], 0);
  const mat = escolas.reduce((t, e) => t + (e.matriculas || 0), 0);
  return h("div", { class: "kpis" },
    kpi("Escolas públicas ativas no Censo", nf(escolas.length), nf(mat) + " matrículas · " + escolas.filter(e => e.rede === "municipal").length + " municipais, " + escolas.filter(e => e.rede === "estadual").length + " estaduais"),
    kpi("PDDE ligado a uma escola — " + ano, brlCompacto(soma("pdde")), com("pdde").length + " escola(s) com repasse identificada(s) no Censo"),
    kpi("…do qual para alfabetização (CNCA e antecessor)", brlCompacto(soma("cnca")), com("cnca").length + " escola(s) · planos 000C e 0007 do PDDE"),
    kpi("Repasse do município a conselhos — " + ano, EMPENHOS_COLETADOS ? brlCompacto(soma("municipal")) : "não coletado",
      EMPENHOS_COLETADOS ? com("municipal").length + " escola(s) identificada(s)" : "empenhos do TCE-ES não coletados", { nd: !EMPENHOS_COLETADOS }));
}

function cardTabelaEscolas(cod, ano, escolas) {
  const nome = nomeEnte(cod);
  const card = h("article", { class: "card largo", id: "card-escolas" }, cabecalho("Escolas de " + nome + " — recursos identificados em " + ano + " e resultados", {
    simples: "Uma linha por escola pública ativa: quanto dinheiro chegou a ela no ano, por qual canal, e os resultados de aprendizagem. Clique no nome da escola para ver tudo o que chegou a ela, ano a ano.",
    nota: "\"nenhum\" = nenhum repasse LIGADO à escola — pode haver repasse a um recebedor que não foi identificado no Censo (lista no fim). IDEB e PAEBES: último resultado da escola no banco do NEDUC, com o ano entre parênteses.",
    limitacao: "Escolas",
    fonte: { itens: () => [{ indicador: "escola_recurso", ano, detalhe: "escolas de " + nome, q: escolas.flatMap(e => recursosNoAno(e.co_entidade, ano).rs.map(r => r.q)).concat([(escolas[0] || {}).q]).join(";") }] } }));
  const linhas = escolas.map(e => ({ e, x: recursosNoAno(e.co_entidade, ano) }))
    .sort((a, b) => (b.x.pdde + b.x.municipal) - (a.x.pdde + a.x.municipal) || a.e.nome.localeCompare(b.e.nome, "pt-BR"));
  const porAluno = l => l.e.matriculas > 0 && (l.x.pdde + l.x.municipal) > 0 ? (l.x.pdde + l.x.municipal) / l.e.matriculas : null;
  const obraNoPredio = l => (RECURSOS_ESCOLA.get(l.e.co_entidade) || []).filter(r => r.canal === "obra").reduce((t, r) => t + r.valor, 0) || null;
  const ideb = (v, a) => nulo(v) ? semDado() : nf(v, 1) + (a ? " (" + a + ")" : "");
  const colunas = [
    { rotulo: "Escola", valor: l => l.e.nome, classe: "col-nome",
      render: l => h("span", {}, linkPara({ esc: l.e.co_entidade }, l.e.nome), h("br"), h("span", { class: "nota" }, "INEP " + l.e.co_entidade + " · rede " + l.e.rede)) },
    { rotulo: "Matrículas", num: true, valor: l => l.e.matriculas, fmt: nf },
    { rotulo: "PDDE (R$)", num: true, valor: l => l.x.pdde || null, render: l => moedaOuNenhum(l.x.pdde) },
    { rotulo: "…para alfabetização (R$)", num: true, valor: l => l.x.cnca || null, render: l => moedaOuNenhum(l.x.cnca) },
    { rotulo: "Repasse do município (R$)", num: true, valor: l => l.x.municipal || null, render: l => EMPENHOS_COLETADOS ? moedaOuNenhum(l.x.municipal) : semDado("não coletado") },
    { rotulo: "R$ por aluno (PDDE + município)", num: true, valor: porAluno, render: l => moedaOuNenhum(porAluno(l)) },
    { rotulo: "Obra no prédio (contratos, R$)", num: true, valor: obraNoPredio, render: l => moedaOuNenhum(obraNoPredio(l)) },
    { rotulo: "IDEB anos iniciais", num: true, valor: l => l.e.ideb_ai, render: l => ideb(l.e.ideb_ai, l.e.ideb_ai_ano) },
    { rotulo: "IDEB anos finais", num: true, valor: l => l.e.ideb_af, render: l => ideb(l.e.ideb_af, l.e.ideb_af_ano) },
    { rotulo: "PAEBES 5º ano — Português", num: true, valor: l => l.e.paebes_5_lp, fmt: v => nf(v, 0) },
    { rotulo: "PAEBES 5º ano — Matemática", num: true, valor: l => l.e.paebes_5_mt, fmt: v => nf(v, 0) },
  ];
  // O aviso de não-causalidade fica ANTES das colunas de resultado, não no rodapé do card.
  card.append(h("div", { class: "callout info", role: "note" }, h("strong", {}, "Dinheiro e resultado lado a lado não são causa e efeito. "),
    "Os resultados (IDEB e PAEBES) aparecem como contexto da escola; o painel não estabelece relação entre o repasse e o desempenho."));
  card.append(tabela(colunas, linhas, "Escolas de " + nome + ", " + ano,
    { destacar: l => l.e.co_entidade === estado.escola, busca: "Buscar escola…", csv: "escolas_" + cod + "_" + ano + ".csv" }));
  return card;
}

function cardDetalheEscola(co) {
  const e = ESCOLAS.get(co);
  if (!e) return null;
  const rs = (RECURSOS_ESCOLA.get(co) || []).slice().sort((a, b) => (b.ano || 0) - (a.ano || 0) || a.canal.localeCompare(b.canal));
  const vinc = VINCULOS_ESCOLA.get(co) || [];
  const card = h("article", { class: "card largo destaque-escola", id: "detalhe-escola", tabindex: "-1" }, cabecalho(e.nome + " — tudo o que chegou à escola", {
    simples: "INEP " + co + " · rede " + e.rede + " · " + nomeEnte(e.cod_ibge) + " · Censo " + (e.ano_censo || "—") + ". Valores por ano e por canal; cada linha tem a consulta de origem.",
    fonte: { itens: () => rs.map(r => ({ indicador: "escola_recurso", ano: r.ano, detalhe: "INEP " + co + " · " + (r.canal === "pdde" ? "PDDE " + r.po + " (" + r.po_nome + ")" : ROT_CANAL[r.canal]),
      q: r.q, valor: brl(r.valor), observacao: r.detalhe || null })).concat([{ indicador: "escola_recurso", ano: estado.ano, detalhe: "cadastro da escola (Censo)", q: e.q }]) } }));
  card.append(h("div", { class: "faixa" },
    h("span", { class: "item" }, nf(e.matriculas || 0) + " matrículas"), h("span", { class: "item" }, nf(e.docentes || 0) + " docentes"),
    INFRA.map(([c, rot]) => h("span", { class: "item" }, e[c] === 1 || e[c] === true ? "✔ tem " + rot : e[c] === 0 || e[c] === false ? "✖ sem " + rot : "sem dado: " + rot)),
    linkMapa(e.lat, e.lon, "localização (Censo)")));
  if (!rs.length) card.append(h("p", {}, "Nenhum repasse ligado a esta escola nas fontes do painel. Pode haver repasse a uma unidade executora que não foi identificada no Censo (ver a lista de não identificados)."));
  else {
    const anos = [...new Set(rs.map(r => r.ano).filter(a => !nulo(a)))].sort();
    card.append(tabela([
      { rotulo: "Ano", valor: l => l.a },
      { rotulo: "PDDE total (R$)", num: true, valor: l => l.pdde || null, render: l => moedaOuNenhum(l.pdde) },
      { rotulo: "…para alfabetização (R$)", num: true, valor: l => l.cnca || null, render: l => moedaOuNenhum(l.cnca) },
      { rotulo: "Repasse do município (R$)", num: true, valor: l => l.municipal || null, render: l => moedaOuNenhum(l.municipal) },
      { rotulo: "Obras assinadas (R$)", num: true, valor: l => l.obra || null, render: l => moedaOuNenhum(l.obra) },
    ], anos.map(a => ({ a, ...recursosNoAno(co, a) })), "Recursos por ano — " + e.nome, { inicio: 0, busca: false, fixarPrimeira: false }));
    card.append(blocoTabela("repasses da escola", [
      { rotulo: "Ano", valor: r => r.ano },
      { rotulo: "Canal", valor: r => ROT_CANAL[r.canal] },
      { rotulo: "Programa / detalhe", valor: r => r.canal === "pdde" ? r.po + " — " + r.po_nome : r.detalhe,
        render: r => r.canal === "pdde" ? h("span", {}, h("strong", {}, r.po), " " + r.po_nome,
          r.po === PO_CNCA ? [" ", h("span", { class: "badge info" }, "CNCA")] : r.po === PO_ALFA ? [" ", h("span", { class: "badge info" }, "antecessor do CNCA")] : null)
          : r.canal === "obra" ? "contrato(s) " + String(r.detalhe || "").split(";").length : (r.detalhe || "—") },
      { rotulo: "Valor (R$)", num: true, valor: r => r.valor, fmt: brl },
      colunaFonte(r => e.nome + " — " + ROT_CANAL[r.canal] + " " + r.ano, r => [{ indicador: "escola_recurso", ano: r.ano,
        detalhe: "INEP " + co + " · " + (r.canal === "pdde" ? "PDDE " + r.po + " (" + r.po_nome + ")" : ROT_CANAL[r.canal]), q: r.q, valor: brl(r.valor), observacao: r.detalhe || null }]),
    ], rs, "escola_" + co + ".csv"));
  }
  const obrasDaEscola = new Set();
  for (const o of OBRAS_EDU.get(e.cod_ibge) || []) bensDe(o).forEach((b, i) => { const v = VINCULO_POR_ORIGEM.get("obra|" + o.chave + "#" + i); if (v && v.co_entidade === co) obrasDaEscola.add(o); });
  if (obrasDaEscola.size) card.append(h("h4", {}, "Obras no prédio"), h("ul", { class: "lista" }, [...obrasDaEscola].map(o =>
    h("li", {}, String(o.objeto || "").slice(0, 140), " · ", seloObra(o.situacao), " · " + brl(o.valor || 0) + (nulo(o.pct_medido) ? "" : " · " + nf(o.pct_medido, 0) + "% medido")))));
  card.append(h("details", { class: "tab" }, h("summary", {}, "Como a escola foi identificada nas fontes (" + vinc.length + " vínculo(s))"),
    h("ul", { class: "lista" }, vinc.map(v => h("li", {}, h("strong", {}, ({ pdde: "PDDE", conselho: "Conselho (empenhos)", obra: "Obra" })[v.fonte] + ": "),
      v.nome_origem + " → " + v.metodo + " (nota " + nf(v.nota || 0, 2) + ")")))));
  card.append(h("div", { class: "acoes-tabela" }, linkPara({ esc: null }, "← Voltar à lista de escolas")));
  return card;
}

function cardNaoIdentificadas(cod) {
  const nome = nomeEnte(cod);
  const soltos = VINCULOS.filter(v => v.cod_ibge === cod && !v.co_entidade);
  const card = h("article", { class: "card largo", id: "card-nao-identificadas" }, cabecalho("Recebedores de " + nome + " não identificados no Censo", {
    simples: "Quem recebeu dinheiro destinado a escolas, mas não pôde ser ligado com segurança a uma escola do Censo. Fica aqui, com o nome como veio da fonte, em vez de ser atribuído por palpite." }));
  if (!soltos.length) { card.append(h("p", {}, "Todos os recebedores deste município foram ligados a uma escola do Censo.")); return card; }
  card.append(tabela([
    { rotulo: "Canal", valor: v => ({ pdde: "PDDE", conselho: "Repasse do município", obra: "Obra" })[v.fonte] },
    { rotulo: "Nome na fonte", valor: v => v.nome_origem },
    { rotulo: "Por que ficou sem vínculo", valor: v => v.metodo + (v.nota ? " (nota " + nf(v.nota, 2) + ")" : "") },
  ], soltos, "Recebedores não identificados — " + nome, { inicio: 10, csv: "nao_identificados_" + cod + ".csv", fixarPrimeira: false }));
  return card;
}

function renderSecaoEscolas(destino, cod, ano) {
  if (!ESCOLAS.size) { destino.append(h("div", { class: "callout sinal" }, "O cadastro do Censo Escolar não foi carregado nesta versão do painel.")); return; }
  const escolas = (ESCOLAS_MUN.get(cod) || []).filter(e => estado.rede === "todas" || e.rede === estado.rede);
  destino.append(kpisEscolas(ano, escolas));
  const detalhe = estado.escola && ESCOLAS.get(estado.escola) && ESCOLAS.get(estado.escola).cod_ibge === cod ? cardDetalheEscola(estado.escola) : null;
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" }, detalhe, cardTabelaEscolas(cod, ano, escolas), cardNaoIdentificadas(cod))));
}

/* ================================================== CNCA (Programas federais) */
const CNCA_MUN = (D.cnca || {}).municipio || [];
const CNCA_ESC = expandir((D.cnca || {}).escolas);
const CNCA_EST = (D.cnca || {}).estado || [];
const CNCA_FUNPAES = expandir((D.cnca || {}).funpaes);

/** Os cards automáticos do CNCA do Estado inteiro — o bloco `modulo_automatico: cnca` do programas.yaml. */
function cardsCnca() {
  const ano = estado.ano;
  const noAno = CNCA_MUN.filter(r => r.ano === ano && (r.pdde_cnca > 0 || r.pdde_alfabetizacao > 0));
  const total = noAno.reduce((t, r) => t + (r.pdde_cnca || 0), 0), alfa = noAno.reduce((t, r) => t + (r.pdde_alfabetizacao || 0), 0);
  const escolas = noAno.reduce((t, r) => t + (r.escolas_cnca || 0), 0);
  const estadoAno = CNCA_EST.filter(r => r.ano === ano), estadoTotal = estadoAno.reduce((t, r) => t + r.valor, 0);
  const resumo = h("article", { class: "card largo", id: "card-cnca-repasses" }, cabecalho("CNCA — repasses federais em " + ano, {
    simples: "O dinheiro federal do CNCA que se consegue rastrear em dado aberto: o que o FNDE pagou direto às escolas e o apoio pago ao governo do Estado, que coordena o programa no ES.",
    nota: "O CNCA tem plano orçamentário próprio nas transferências do FNDE publicadas pela CGU: ação 0515 (PDDE), PO 000C, pago escola a escola; e ação 0509, PO 0014, pago ao Estado (SEDU). Mês de pagamento da CGU, não de competência.",
    limitacao: "Financiamento do CNCA",
    fonte: { itens: () => [{ indicador: "cnca_pdde", ano, detalhe: "000C", q: noAno.map(r => r.q).join(";"), valor: brl(total) }].concat(estadoAno.map(r => ({ indicador: "cnca_estado", ano, detalhe: r.favorecido, q: r.q, valor: brl(r.valor) }))) } }));
  resumo.append(h("div", { class: "kpis" },
    kpi("PDDE-CNCA às escolas dos municípios", total ? brlCompacto(total) : "R$ 0", noAno.filter(r => r.pdde_cnca > 0).length + " município(s) · " + nf(escolas) + " escola(s), municipais e estaduais"),
    kpi("PDDE-Alfabetização (antecessor, PO 0007)", alfa ? brlCompacto(alfa) : "R$ 0", "programa de 2021–2022", { nd: !alfa }),
    kpi("Apoio ao Estado (ação 0509, PO 0014)", estadoTotal ? brlCompacto(estadoTotal) : "R$ 0", estadoAno.length ? estadoAno.map(r => String(r.mes).padStart(2, "0") + "/" + r.ano).join(", ") : "nenhum pagamento no ano", { nd: !estadoTotal }),
    kpi("Gasto municipal identificado como FUNPAES", EMPENHOS_COLETADOS ? brlCompacto(CNCA_FUNPAES.filter(r => r.ano === ano).reduce((t, r) => t + r.empenhada, 0)) : "não coletado",
      EMPENHOS_COLETADOS ? "empenhos com \"FUNPAES\" no programa, na ação ou no detalhamento" : "empenhos do TCE-ES não coletados", { nd: !EMPENHOS_COLETADOS })));
  const serie = ANOS.map(a => ({ a, v: CNCA_MUN.filter(r => r.ano === a).reduce((t, r) => t + (r.pdde_cnca || 0), 0),
    alfa: CNCA_MUN.filter(r => r.ano === a).reduce((t, r) => t + (r.pdde_alfabetizacao || 0), 0), est: CNCA_EST.filter(r => r.ano === a).reduce((t, r) => t + r.valor, 0) }));
  resumo.append(tabela([
    { rotulo: "Exercício", valor: l => l.a },
    { rotulo: "PDDE-CNCA às escolas (R$)", num: true, valor: l => l.v, fmt: brl },
    { rotulo: "PDDE-Alfabetização (R$)", num: true, valor: l => l.alfa, fmt: brl },
    { rotulo: "Apoio ao Estado (R$)", num: true, valor: l => l.est, fmt: brl },
  ], serie, "CNCA por exercício", { inicio: 0, busca: false, fixarPrimeira: false, csv: "cnca_por_exercicio.csv" }),
    h("p", { class: "nota" }, "O PDDE-CNCA inclui escolas estaduais localizadas nos municípios. Em que cada escola gastou não está em dado aberto: ela presta contas ao FNDE."));

  const porMun = h("article", { class: "card largo", id: "card-cnca-municipios" }, cabecalho("PDDE-CNCA por município — " + ano, {
    simples: "Quanto do PDDE-CNCA foi pago às escolas de cada município. Clique no nome para ver as escolas, no dossiê do município.",
    fonte: { itens: () => noAno.map(r => ({ indicador: "cnca_pdde", ano, detalhe: "000C — " + nomeEnte(r.cod_ibge), q: r.q, valor: brl(r.pdde_cnca || 0) })) } }));
  porMun.append(tabela([
    { rotulo: "Município", valor: r => nomeEnte(r.cod_ibge), classe: "col-nome", render: r => linkMunicipio(r.cod_ibge, "programas", nomeEnte(r.cod_ibge)) },
    { rotulo: "PDDE-CNCA (R$)", num: true, valor: r => r.pdde_cnca || null, render: r => moedaOuNenhum(r.pdde_cnca) },
    { rotulo: "Escolas", num: true, valor: r => r.escolas_cnca || null, fmt: nf },
    { rotulo: "PDDE-Alfabetização (R$)", num: true, valor: r => r.pdde_alfabetizacao || null, render: r => moedaOuNenhum(r.pdde_alfabetizacao) },
  ], noAno.slice().sort((a, b) => (b.pdde_cnca || 0) - (a.pdde_cnca || 0)), "PDDE-CNCA por município, " + ano,
    { busca: "Buscar município…", csv: "cnca_municipios_" + ano + ".csv", vazio: "Nenhum repasse do PDDE-CNCA ou do PDDE-Alfabetização em " + ano + "." }));

  const fp = CNCA_FUNPAES.filter(r => r.ano === ano).sort((a, b) => b.empenhada - a.empenhada);
  const funpaes = h("article", { class: "card largo", id: "card-funpaes" }, cabecalho("Onde os municípios gastaram: FUNPAES — " + ano, {
    simples: "No ES, o CNCA é implementado dentro do PAES, e o FUNPAES repassa recursos estaduais aos municípios. Aqui, o que os municípios registraram como gasto do FUNPAES.",
    nota: "Só aparece o que o município NOMEOU como FUNPAES no programa, na ação ou no detalhamento da fonte dos empenhos. Ausência aqui não prova que o recurso não foi usado: o município pode ter registrado com outro nome.",
    fonte: { itens: () => fp.slice(0, 40).map(r => ({ indicador: "funpaes_empenho", ano, detalhe: r.NomeAcao + " · " + r.DescricaoElemento + " · " + r.credor + " — " + r.credor_nome, q: r.q, valor: brl(r.empenhada) })) } }));
  if (!EMPENHOS_COLETADOS) funpaes.append(avisoEmpenhos());
  else if (!fp.length) funpaes.append(h("p", {}, "Nenhum empenho identificado como FUNPAES em " + ano + "."));
  else funpaes.append(tabelaFunpaes(fp, "funpaes_todos_" + ano + ".csv"));
  return [resumo, porMun, funpaes];
}
function tabelaFunpaes(fp, arquivo) {
  const porElem = agrupar(fp, r => r.DescricaoElemento);
  const itens = [...porElem.entries()].map(([nome, rs]) => ({ nome, codigo: rs.length + " lanç.", valor: rs.reduce((t, r) => t + r.empenhada, 0) })).sort((a, b) => b.valor - a.valor);
  const tot = itens.reduce((t, i) => t + i.valor, 0);
  return h("div", {}, h("p", {}, h("strong", {}, brl(tot)), " empenhados, por natureza da despesa:"), barrasHorizontais(itens, tot, { rotulo: "FUNPAES por natureza da despesa" }),
    blocoTabela("empenhos FUNPAES", [
      { rotulo: "Município", valor: r => nomeEnte(r.cod_ibge) },
      { rotulo: "Ação", valor: r => r.NomeAcao }, { rotulo: "Elemento", valor: r => r.DescricaoElemento },
      { rotulo: "Credor", valor: r => r.credor_nome + (r.credor ? " (" + fmtDoc(r.credor) + ")" : "") },
      { rotulo: "Empenhado (R$)", num: true, valor: r => r.empenhada, fmt: brl }, { rotulo: "Pago (R$)", num: true, valor: r => r.paga, fmt: brl },
    ], fp, arquivo));
}
/** CNCA de um município só — a seção Programas do dossiê. */
function cardsCncaMunicipio(cod, ano) {
  const nome = nomeEnte(cod);
  const doMun = CNCA_ESC.filter(r => r.cod_ibge === cod && r.ano === ano).sort((a, b) => b.valor - a.valor);
  const vinc = r => VINCULO_POR_ORIGEM.get("pdde|" + r.cnpj_uex);
  const escolas = h("article", { class: "card largo", id: "card-cnca-escolas" }, cabecalho("Escolas de " + nome + " com PDDE-CNCA — " + ano, {
    simples: "As escolas do município que receberam o PDDE do CNCA (ou o PDDE-Alfabetização que o antecedeu) no ano, e quanto cada uma recebeu.",
    fonte: { itens: () => doMun.map(r => ({ indicador: "cnca_pdde", ano, detalhe: r.programa === "pdde_cnca" ? "000C" : "0007", q: r.q, valor: brl(r.valor), observacao: "unidade executora " + fmtDoc(r.cnpj_uex) + " — " + r.uex })) } }));
  escolas.append(tabela([
    { rotulo: "Unidade executora", valor: r => r.uex, classe: "col-nome" },
    { rotulo: "Escola no Censo", valor: r => { const v = vinc(r); return v && v.co_entidade ? (ESCOLAS.get(v.co_entidade) || {}).nome : ""; },
      render: r => { const v = vinc(r); return v && v.co_entidade ? linkEscola(v.co_entidade) : h("span", { class: "muted" }, "não identificada"); } },
    { rotulo: "Programa", valor: r => r.programa === "pdde_cnca" ? "CNCA (000C)" : "Alfabetização (0007)" },
    { rotulo: "Valor (R$)", num: true, valor: r => r.valor, fmt: brl },
    colunaFonte(r => r.uex + " — " + ano, r => [{ indicador: "cnca_pdde", ano, detalhe: r.programa === "pdde_cnca" ? "000C" : "0007", q: r.q, valor: brl(r.valor), observacao: "unidade executora " + fmtDoc(r.cnpj_uex) + " — " + r.uex }]),
  ], doMun, "Escolas com PDDE-CNCA — " + nome + ", " + ano, { csv: "cnca_escolas_" + cod + "_" + ano + ".csv", vazio: "Nenhuma escola do município recebeu PDDE-CNCA ou PDDE-Alfabetização em " + ano + "." }));
  const fp = CNCA_FUNPAES.filter(r => r.ano === ano && r.cod_ibge === cod).sort((a, b) => b.empenhada - a.empenhada);
  const funpaes = h("article", { class: "card largo", id: "card-funpaes-mun" }, cabecalho("Gasto de " + nome + " identificado como FUNPAES — " + ano, {
    simples: "O que o município registrou como gasto do FUNPAES, o fundo estadual do programa em que o CNCA é implementado no ES.",
    nota: "Só aparece o que o município nomeou como FUNPAES. Ausência não prova que o recurso não foi usado.",
    fonte: { itens: () => fp.map(r => ({ indicador: "funpaes_empenho", ano, detalhe: r.NomeAcao + " · " + r.DescricaoElemento + " · " + r.credor + " — " + r.credor_nome, q: r.q, valor: brl(r.empenhada) })) } }));
  if (!EMPENHOS_COLETADOS) funpaes.append(avisoEmpenhos());
  else if (!fp.length) funpaes.append(h("p", {}, "Nenhum empenho identificado como FUNPAES em " + nome + " em " + ano + "."));
  else funpaes.append(tabelaFunpaes(fp, "funpaes_" + cod + "_" + ano + ".csv"));
  return [escolas, funpaes];
}
