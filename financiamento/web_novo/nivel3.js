"use strict";
/* ============================================================================
   TCE-ES no painel: o Nível 3 da despesa (credor, ação, fonte detalhada, repasse
   a conselho escolar, item contratado, obra). Dados DECLARATÓRIOS (remessas do
   CidadES): o painel mostra o que o município informou ao Tribunal, com a
   consulta de origem em cada "ver fonte".
   ========================================================================== */

const PCM_LINHAS = expandir(D.pcm);
const OBRAS_EDU = agrupar(expandir(D.obras), o => o.cod_ibge);
const CREDORES_EA = agrupar(expandir(D.credores), r => chaveEA(r.cod_ibge, r.ano));
const ACOES_EA = agrupar(expandir(D.acoes), r => chaveEA(r.cod_ibge, r.ano));
const FONTES_DET_EA = agrupar(expandir(D.fontes_det), r => chaveEA(r.cod_ibge, r.ano));
const CONSELHOS_EA = agrupar(expandir(D.conselhos), r => chaveEA(r.cod_ibge, r.ano));
const DOTACAO_EA = agrupar(expandir(D.dotacao), r => chaveEA(r.cod_ibge, r.ano));
const CREDOR_ACAO_EA = agrupar(expandir(D.credor_acao), r => chaveEA(r.cod_ibge, r.ano));
const ITENS_EA = agrupar(expandir(D.itens), r => chaveEA(r.cod_ibge, r.ano));
const ITENS_RESUMO = new Map(expandir(D.itens_resumo).map(r => [chaveEA(r.cod_ibge, r.ano), r]));
const ITENS_CONTRATADA_EA = agrupar(expandir(D.itens_contratada), r => chaveEA(r.cod_ibge, r.ano));
const CONTRATACOES = new Map(expandir(D.contratacoes).map(c => [c.contratacao, c]));
const ITENS_COLETADOS = !!(D.itens && D.itens.linhas && D.itens.linhas.length);
const VINCULO_ITEM = {
  ug_educacao: "unidade gestora de educação",
  setor_educacao: "contratação com setor beneficiado \"Educação\"",
  obra_educacao: "instrumento de obra da Educação",
};
const ESCOLAS = new Map(expandir(D.escolas).map(e => [e.co_entidade, e]));
const VINCULOS = expandir(D.escolas_vinculos);
const VINCULO_POR_ORIGEM = new Map(VINCULOS.map(v => [v.fonte + "|" + v.origem, v]));
const EMPENHOS_COLETADOS = !!(D.credores && D.credores.linhas && D.credores.linhas.length);
const DOTACAO_COLETADA = !!(D.dotacao && D.dotacao.linhas && D.dotacao.linhas.length);

function fmtDoc(doc) {
  const d = String(doc || "").replace(/\D/g, "");
  if (d.length === 14) return d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
  return doc || "—";
}

/* ------------------------------------------------------------ situação da obra
   Obra parada é "sinal a verificar" (âmbar), não descumprimento: o vermelho fica
   reservado a regra legal descumprida. "Paralisação presumida" é inferida pelo
   Tribunal (obra sem medição recente), não declarada pelo município. */
function classeObra(sit) {
  const t = semAcento(sit);
  if (/presumida/.test(t)) return "presumida";
  if (/paralisada|interrompida/.test(t)) return "paralisada";
  if (/nao iniciada/.test(t)) return "nao_iniciada";
  if (/execucao/.test(t)) return "execucao";
  if (/concluida/.test(t)) return "concluida";
  return "outra";
}
function seloObra(sit) {
  const c = classeObra(sit), titulo = sit || "";
  if (c === "paralisada") return chipEstado("sinal", "paralisada (declarada)", titulo);
  if (c === "presumida") return chipEstado("sinal", "paralisação presumida (TCE-ES)", titulo);
  if (c === "nao_iniciada") return h("span", { class: "est est-neutro", title: titulo }, "○ não iniciada");
  if (c === "execucao") return h("span", { class: "est est-neutro", title: titulo }, "▶ em execução");
  if (c === "concluida") return chipEstado("cumpre", "concluída" + (sit ? " · " + sit.replace(/^Conclu[íi]da e /, "") : ""), titulo);
  return chipEstado("semdado", "situação não identificada", titulo);
}
const obraParada = o => ["paralisada", "presumida"].includes(classeObra(o.situacao));
function bensDe(o) { try { return JSON.parse(o.bens || "[]"); } catch (e) { return []; } }
/** Link de mapa para a coordenada informada pelo TCE-ES (centroide do bem vinculador). */
function linkMapa(lat, lon, rotulo) {
  if (nulo(lat) || nulo(lon)) return null;
  return h("a", { href: "https://www.openstreetmap.org/?mlat=" + lat + "&mlon=" + lon + "#map=17/" + lat + "/" + lon,
    target: "_blank", rel: "noopener noreferrer", title: "Coordenada informada: " + lat + ", " + lon }, (rotulo || "ver no mapa") + " ↗");
}
function avisoNaoColetado(oque) {
  return h("p", {}, chipEstado("semdado", "não coletado"), " " + oque + " não foram coletados nesta versão do painel.");
}
const avisoEmpenhos = () => avisoNaoColetado("Os empenhos do TCE-ES");

/* ===================================================== detalhamento (Nível 3)
   A tabela de credores e a de ações mostram cada uma um lado do empenho. O
   diálogo junta os dois — quem recebeu, em qual ação, com que elemento e que
   fonte — e acrescenta o que a contratação diz ter comprado. O vínculo empenho ↔
   contratação é por CNPJ e município (o empenho do TCE-ES não traz o contrato):
   os itens aparecem numa seção à parte, rotulada como indício. */
const CNPJ = doc => String(doc || "").replace(/\D/g, "");
function credorAcaoDe(cod, ano, { credor, acao } = {}) {
  return (CREDOR_ACAO_EA.get(chaveEA(cod, ano)) || [])
    .filter(r => (credor === undefined || r.credor === credor) && (acao === undefined || String(r.CodigoAcao) === String(acao)))
    .slice().sort((a, b) => b.empenhada - a.empenhada);
}
function itensDaContratada(cod, ano, cnpj) {
  const d = CNPJ(cnpj);
  return d ? (ITENS_EA.get(chaveEA(cod, ano)) || []).filter(i => CNPJ(i.cnpj_contratada) === d) : [];
}
function resumoDaContratada(cod, ano, cnpj) {
  const d = CNPJ(cnpj);
  return d ? (ITENS_CONTRATADA_EA.get(chaveEA(cod, ano)) || []).find(c => CNPJ(c.cnpj_contratada) === d) : null;
}
const COLUNAS_ITEM_DETALHE = [
  { rotulo: "Item contratado", valor: i => i.descricao || "(sem descrição)" },
  { rotulo: "Unidade", valor: i => i.unidade },
  { rotulo: "Qtd.", num: true, valor: i => i.quantidade, fmt: v => nf(v, 2) },
  { rotulo: "Valor unitário", num: true, valor: i => i.valor_unitario, fmt: brl },
  { rotulo: "Valor total", num: true, valor: i => i.valor_total, fmt: brl },
  { rotulo: "Medido", num: true, valor: i => i.valor_medido, render: i => nulo(i.valor_medido) ? semDado("sem medição") : brl(i.valor_medido) },
  { rotulo: "Contratação", valor: i => i.contratacao, render: i => { const c = CONTRATACOES.get(i.contratacao);
    return h("span", {}, h("code", {}, i.contratacao || "—"), c && c.objeto ? h("div", { class: "nota" }, String(c.objeto).slice(0, 120)) : null); } },
];
function itensFonteItem(cod, ano, itens) {
  return itens.map(i => ({ indicador: "item_contratado", ano, detalhe: "contratação " + i.contratacao + " · " + String(i.descricao).slice(0, 80),
    q: i.q, valor: nulo(i.valor_total) ? null : brl(i.valor_total),
    observacao: "vínculo com a Educação: " + (VINCULO_ITEM[i.vinculo] || i.vinculo) + "; unidade gestora " + (i.ug || "—") }));
}
function secaoItensDoCredor(cod, ano, credor, nomeCredor) {
  const cnpj = CNPJ(credor);
  if (!ITENS_COLETADOS) return avisoNaoColetado("Os itens das contratações do TCE-ES");
  if (!cnpj) return h("p", { class: "nota" }, "Credor sem CNPJ (pessoa física agregada ou linha de resumo): não há contratação a cruzar.");
  const resumo = resumoDaContratada(cod, ano, cnpj), itens = itensDaContratada(cod, ano, cnpj);
  if (!resumo && !itens.length) {
    const outros = ANOS.filter(a => a !== ano && resumoDaContratada(cod, a, cnpj));
    return h("p", { class: "nota" }, "Nenhuma contratação da Educação deste CNPJ com instrumento de " + ano + " neste município. ",
      outros.length
        ? h("span", {}, "Há contratação dele em ", h("strong", {}, outros.join(", ")),
            " — o exercício do item é o do contrato, então um empenho de " + ano + " pode se referir a contrato assinado antes. Troque o exercício para ver os itens.")
        : "Pode ser compra feita pela unidade gestora da prefeitura sem setor beneficiado marcado — o recorte não a alcança.");
  }
  const bloco = h("div", {}, h("div", { class: "callout info" }, h("strong", {}, "Vínculo por CNPJ, não por contrato. "),
    "O empenho do TCE-ES não traz o número do contrato. O que segue são as contratações da Educação do mesmo CNPJ, no mesmo município e exercício — indício forte de a que se refere o empenho, não prova."));
  if (resumo) bloco.append(h("p", {}, h("strong", {}, brl(resumo.valor_contratado)), " contratados em ", nf(resumo.itens), " item(ns), ",
    nf(resumo.contratacoes), " contratação(ões)", nulo(resumo.valor_medido) || !resumo.valor_medido ? "" : " · " + brl(resumo.valor_medido) + " medidos", "."));
  if (itens.length) {
    bloco.append(tabela(COLUNAS_ITEM_DETALHE, itens.slice().sort((a, b) => b.valor_total - a.valor_total),
      "Itens contratados de " + nomeCredor + ", " + ano, { inicio: 5, csv: "itens_" + cnpj + "_" + ano + ".csv" }));
    if (resumo && resumo.itens > itens.length) bloco.append(h("p", { class: "nota" }, "Estes são os itens desta contratada que entraram no painel (os maiores do município no ano). A lista completa, com " +
      nf(resumo.itens) + " itens, está no arquivo tcees_itens.csv do conjunto de dados do painel."));
  }
  return bloco;
}
/** Diálogo de detalhamento. `alvo` = {tipo: "credor"|"acao", …}. */
function abrirDetalhe(cod, ano, alvo) {
  const dlg = $("#dialogo-detalhe");
  limpar(dlg);
  const nome = nomeEnte(cod), ehCredor = alvo.tipo === "credor";
  const linhas = credorAcaoDe(cod, ano, ehCredor ? { credor: alvo.credor } : { acao: alvo.acao });
  const titulo = ehCredor ? alvo.nome : alvo.codigo + " - " + alvo.nome;
  const total = linhas.reduce((t, r) => t + (r.empenhada || 0), 0);
  const colunas = ehCredor
    ? [{ rotulo: "Ação do orçamento", valor: r => r.CodigoAcao + " - " + r.NomeAcao, render: r => h("span", {}, h("span", { class: "muted" }, r.CodigoAcao + " "), r.NomeAcao) },
       { rotulo: "Elemento de despesa", valor: r => r.elemento || "—" },
       { rotulo: "Fonte de recursos", valor: r => r.fonte || "—" },
       { rotulo: "Empenhado (R$)", num: true, valor: r => r.empenhada, fmt: brl },
       { rotulo: "Pago (R$)", num: true, valor: r => r.paga, fmt: brl }]
    : [{ rotulo: "Credor", valor: r => r.credor_nome, render: r => r.credor === "(demais)" ? h("span", { class: "muted" }, r.credor_nome + " (" + nf(r.demais) + ")") : r.credor_nome },
       { rotulo: "CNPJ", valor: r => r.credor, render: r => /^\d/.test(String(r.credor)) ? fmtDoc(r.credor) : "—" },
       { rotulo: "Elemento de despesa", valor: r => r.elemento || "—" },
       { rotulo: "Fonte de recursos", valor: r => r.fonte || "—" },
       { rotulo: "Empenhado (R$)", num: true, valor: r => r.empenhada, fmt: brl },
       { rotulo: "Pago (R$)", num: true, valor: r => r.paga, fmt: brl }];
  const corpo = h("div", { class: "fonte-corpo" });
  if (!EMPENHOS_COLETADOS) corpo.append(avisoEmpenhos());
  else if (!linhas.length) corpo.append(h("p", {}, chipEstado("semdado", "sem empenho"),
    ehCredor ? " Este credor não tem empenho da função 12 em " + ano + " com ação identificada."
      : " Nenhum empenho da função 12 nesta ação em " + ano + ". Se a ação tem dotação, ela foi orçada e não executada."));
  else {
    corpo.append(h("p", {}, h("strong", {}, brl(total)), " empenhado(s) em " + linhas.length + " linha(s)."),
      tabela(colunas, linhas, titulo + " — detalhamento", { inicio: 8, csv: "detalhe_" + (ehCredor ? "credor_" + alvo.credor : "acao_" + alvo.codigo) + "_" + cod + "_" + ano + ".csv" }));
    if (linhas.some(r => r.credor === "(demais)")) corpo.append(h("p", { class: "nota" }, "A linha \"Demais credores da ação\" soma os credores fora dos 8 maiores daquela ação: o valor está completo, os nomes não."));
  }
  corpo.append(h("h3", {}, "O que foi comprado"));
  if (ehCredor) corpo.append(secaoItensDoCredor(cod, ano, alvo.credor, alvo.nome));
  else {
    const cnpjs = [...new Set(linhas.map(r => CNPJ(r.credor)).filter(Boolean))];
    const itens = cnpjs.flatMap(c => itensDaContratada(cod, ano, c));
    corpo.append(itens.length
      ? h("div", {}, h("p", { class: "nota" }, "Itens das contratações da Educação dos credores acima (vínculo por CNPJ e município, não por contrato)."),
        tabela(COLUNAS_ITEM_DETALHE, itens.sort((a, b) => b.valor_total - a.valor_total), "Itens dos credores da ação", { inicio: 5 }))
      : h("p", { class: "nota" }, ITENS_COLETADOS
        ? "Nenhum item de contratação da Educação casou com os credores desta ação neste município e exercício."
        : "Os itens das contratações do TCE-ES não foram coletados nesta versão do painel."));
  }
  const portal = ((D.dados_manuais || {}).portais || []).find(p => p.cod_ibge === cod && p.verificado);
  corpo.append(h("p", { class: "nota" }, "Nota fiscal, empresa por nota e data de pagamento não estão no dado aberto do TCE-ES. ",
    portal ? h("span", {}, "No portal da transparência de " + nome + ": ",
      portal.url ? h("a", { href: portal.url, target: "_blank", rel: "noopener noreferrer" }, portal.url) : null,
      portal.api ? [portal.url ? " · " : "", h("a", { href: portal.api, target: "_blank", rel: "noopener noreferrer" }, "documentação da API")] : null)
      : h("span", {}, "O portal da transparência de " + nome + " ainda não está cadastrado no painel.")));
  const itensFonte = () => linhas.map(r => ({ indicador: "empenho_credor_acao", ano,
    detalhe: "ação " + r.CodigoAcao + " - " + r.NomeAcao + " · " + r.credor + " — " + r.credor_nome, q: r.q,
    valor: brl(r.empenhada), observacao: "elemento mais frequente: " + (r.elemento || "—") + "; fonte " + (r.fonte || "—") }))
    .concat(ehCredor ? itensFonteItem(cod, ano, itensDaContratada(cod, ano, alvo.credor)) : []);
  dlg.append(
    h("header", {}, h("h2", { id: "detalhe-titulo" }, "Detalhamento — " + titulo),
      h("button", { type: "button", class: "leve fechar", "aria-label": "Fechar", onclick: () => dlg.close() }, "×")),
    h("p", { class: "nota" }, nome + " · exercício " + ano + " · empenhos da função 12 declarados ao TCE-ES"),
    corpo, h("footer", {}, botaoFonte(titulo + " — " + nome + ", " + ano, itensFonte)));
  if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
}
function botaoDetalhe(texto, cod, ano, alvo) {
  return h("button", { type: "button", class: "link detalhe", "aria-haspopup": "dialog",
    title: "Ver detalhamento: ação, elemento, fonte e itens contratados", onclick: () => abrirDetalhe(cod, ano, alvo) }, texto);
}
/** Nome de escola que leva ao detalhe dela, na seção Escolas do município. */
function linkEscola(co, texto) {
  const e = ESCOLAS.get(co);
  if (!e) return h("span", { class: "muted" }, texto || "—");
  return linkPara({ v: "municipio", m: e.cod_ibge, s: "escolas", esc: co }, texto || e.nome);
}

/* ============================================================ NÍVEL 3 (dossiê) */
/** Soma dos empenhos × DCA: a conferência que dá lastro ao Nível 3. */
function conferenciaEmpenhos(r) {
  if (nulo(r.tcees_emp_empenhada) || nulo(r.desp_educacao_empenhada)) return null;
  if (r.tcees_emp_meses_ausentes) {
    return h("div", { class: "callout sinal" }, h("strong", {}, "Ano incompleto na fonte: "),
      "o arquivo de empenhos publicado pelo TCE-ES não traz o(s) mês(es) " + r.tcees_emp_meses_ausentes + " de " + r.ano +
      " para este município. A soma dos empenhos (" + brl(r.tcees_emp_empenhada) + ") fica abaixo da função 12 do DCA (" +
      brl(r.desp_educacao_empenhada) + ") por falta de dado, não por divergência.");
  }
  const dif = r.tcees_emp_empenhada - r.desp_educacao_empenhada, rel = r.desp_educacao_empenhada ? 100 * dif / r.desp_educacao_empenhada : 0;
  const ok = Math.abs(dif) <= 1;
  return h("div", { class: "callout" + (ok || Math.abs(rel) < 0.5 ? "" : " sinal") },
    h("strong", {}, "Conferência: "), "soma dos empenhos da função 12 no TCE-ES = " + brl(r.tcees_emp_empenhada) + "; DCA = " + brl(r.desp_educacao_empenhada) +
    (ok ? " — batem ao centavo." : " — diferença de " + brl(dif) + " (" + (rel > 0 ? "+" : "") + nf(rel, 2) + "%). As remessas ao Tribunal e ao Tesouro podem divergir por retificação."));
}

function cardNivel3Credores(cod, ano) {
  const nome = nomeEnte(cod), r = LINHA.get(cod + "|" + ano) || {};
  const linhas = (CREDORES_EA.get(chaveEA(cod, ano)) || []).slice().sort((a, b) => b.empenhada - a.empenhada);
  const contratadas = new Set((OBRAS_EDU.get(cod) || []).map(o => CNPJ(o.cnpj_contratado)).filter(Boolean));
  const card = h("article", { class: "card largo", id: "card-credores" }, cabecalho("Quem recebeu: maiores credores da Educação — " + nome + ", " + ano, {
    simples: "As empresas, entidades e pessoas que mais receberam empenhos da Educação no ano. Os pagamentos a pessoas físicas (em geral, a folha) aparecem somados numa linha só.",
    nota: "Empenhos da função 12 declarados ao TCE-ES (exceto intra-orçamentários), somados por credor. Os 15 maiores de cada município-ano.",
    limitacao: "Nível 3",
    fonte: { itens: () => linhas.map(c => ({ indicador: "empenho_credor", ano, detalhe: c.credor + " — " + c.credor_nome, q: c.q, valor: brl(c.empenhada),
      observacao: "elemento mais frequente: " + c.elemento + "; fonte " + c.fonte })).concat(nulo(r.tcees_emp_empenhada) ? [] :
      [{ indicador: "tcees_emp_empenhada", ano, q: r.q_tcees_emp, valor: brl(r.tcees_emp_empenhada) }]) } }));
  if (!EMPENHOS_COLETADOS) { card.append(avisoEmpenhos()); return card; }
  if (!linhas.length) { card.append(h("p", {}, chipEstado("semdado"), " Nenhum empenho da função 12 de " + nome + " em " + ano + " nos dados do TCE-ES.")); return card; }
  const conf = conferenciaEmpenhos(r);
  if (conf) card.append(conf);
  const total = r.tcees_emp_empenhada || linhas.reduce((t, c) => t + c.empenhada, 0);
  card.append(barrasHorizontais(linhas.map(c => ({ nome: c.credor_nome, codigo: c.pessoa_fisica ? "pessoa física" : fmtDoc(c.credor), valor: c.empenhada })), total,
    { rotulo: "Maiores credores da Educação" }));
  const colunas = [
    { rotulo: "Credor", valor: c => c.credor_nome, classe: "col-nome", render: c => h("span", {},
      botaoDetalhe(c.credor_nome, cod, ano, { tipo: "credor", credor: c.credor, nome: c.credor_nome }),
      contratadas.has(CNPJ(c.credor)) ? [" ", h("span", { class: "badge neutro", title: "Também é contratada de obra da Educação neste município" }, "contratada de obra")] : null) },
    { rotulo: "CNPJ", valor: c => c.pessoa_fisica ? "" : c.credor, render: c => c.pessoa_fisica ? "—" : fmtDoc(c.credor) },
    { rotulo: "Empenhado (R$)", num: true, valor: c => c.empenhada, fmt: brl },
    { rotulo: "Pago (R$)", num: true, valor: c => c.paga, fmt: brl },
    { rotulo: "% da Educação", num: true, valor: c => total ? 100 * c.empenhada / total : null, fmt: v => nf(v, 1) + "%" },
    { rotulo: "Empenhos", num: true, valor: c => c.empenhos, fmt: nf },
    { rotulo: "Elemento mais frequente", valor: c => c.elemento },
    colunaFonte(c => c.credor_nome + " — " + ano, c => [{ indicador: "empenho_credor", ano,
      detalhe: c.credor + " — " + c.credor_nome, q: c.q, valor: brl(c.empenhada), observacao: "elemento mais frequente: " + c.elemento + "; fonte " + c.fonte }]),
  ];
  card.append(h("p", { class: "nota" }, "Clique no nome do credor para ver em que ações ele aparece, com que elemento e fonte — e o que as contratações desse CNPJ dizem ter comprado."));
  card.append(tabela(colunas, linhas, "Maiores credores da Educação — " + nome + ", " + ano, { csv: "credores_" + cod + "_" + ano + ".csv" }));
  return card;
}

function cardNivel3Acoes(cod, ano) {
  const nome = nomeEnte(cod);
  const dot = DOTACAO_EA.get(chaveEA(cod, ano)) || [], emp = ACOES_EA.get(chaveEA(cod, ano)) || [];
  const card = h("article", { class: "card largo", id: "card-acoes" }, cabecalho("Em quê: ações do orçamento, orçado × executado — " + nome + ", " + ano, {
    simples: "Cada ação é um item do orçamento com o nome que o município deu (\"Construção da EMEF…\", \"Transporte escolar…\"). A tabela compara o que foi orçado com o que foi empenhado.",
    nota: "Dotação atualizada × empenhado, do agregado de despesas do TCE-ES. Ações de obra em destaque; obra com menos da metade da dotação empenhada aparece como sinal.",
    fonte: { itens: () => dot.map(a => ({ indicador: "dotacao_atualizada", ano, detalhe: "ação " + a.CodigoAcao + " - " + a.NomeAcao, q: a.q, valor: brl(a.PrevisaoAtualizada) }))
      .concat(emp.map(a => ({ indicador: "empenho_acao", ano, detalhe: "ação " + a.CodigoAcao + " - " + a.NomeAcao, q: a.q, valor: brl(a.empenhada) }))) } }));
  if (!DOTACAO_COLETADA && !EMPENHOS_COLETADOS) { card.append(avisoEmpenhos()); return card; }
  let linhas;
  if (dot.length) {
    const porAcao = new Map();
    for (const a of dot) {
      const k = a.CodigoAcao + "|" + a.NomeAcao, x = porAcao.get(k) || { codigo: a.CodigoAcao, nome: a.NomeAcao, obra: false, inicial: 0, atualizada: 0, empenhada: 0, paga: 0, q: a.q };
      x.obra = x.obra || !!a.obra; x.inicial += a.PrevisaoInicial || 0; x.atualizada += a.PrevisaoAtualizada || 0; x.empenhada += a.Empenhada || 0; x.paga += a.Paga || 0;
      porAcao.set(k, x);
    }
    linhas = [...porAcao.values()];
  } else {
    linhas = emp.map(a => ({ codigo: a.CodigoAcao, nome: a.NomeAcao, obra: /constru|reforma|amplia|obra/.test(semAcento(a.NomeAcao)),
      inicial: null, atualizada: null, empenhada: a.empenhada, paga: a.paga, q: a.q }));
    card.append(h("p", { class: "nota" }, "A dotação não foi coletada: aparece só o executado (empenhos)."));
  }
  linhas = linhas.filter(l => Math.abs(l.atualizada || 0) + Math.abs(l.empenhada || 0) > 0.005).sort((a, b) => (b.atualizada || b.empenhada) - (a.atualizada || a.empenhada));
  if (!linhas.length) { card.append(h("p", {}, chipEstado("semdado"), " Sem ações da função 12 para " + nome + " em " + ano + ".")); return card; }
  const tot = linhas.reduce((t, l) => ({ at: t.at + (l.atualizada || 0), em: t.em + (l.empenhada || 0) }), { at: 0, em: 0 });
  const execucao = l => nulo(l.atualizada) || !l.atualizada ? null : 100 * l.empenhada / l.atualizada;
  const obras = linhas.filter(l => l.obra), baixa = obras.filter(l => l.atualizada > 0 && execucao(l) < 50);
  card.append(h("p", {}, dot.length ? ["Dotação atualizada ", h("strong", {}, brl(tot.at)), " · "] : null, "empenhado ", h("strong", {}, brl(tot.em)),
    tot.at ? " (" + nf(100 * tot.em / tot.at, 1) + "% executado)." : ".",
    obras.length ? " " + obras.length + " ação(ões) de obra; " + baixa.length + " com menos da metade da dotação empenhada." : ""));
  const colunas = [
    { rotulo: "Ação", valor: l => l.codigo + " - " + l.nome, classe: "col-nome", render: l => h("span", {}, h("span", { class: "muted" }, l.codigo + " "),
      botaoDetalhe(l.nome, cod, ano, { tipo: "acao", acao: l.codigo, codigo: l.codigo, nome: l.nome }),
      l.obra ? [" ", h("span", { class: "badge neutro" }, "obra")] : null) },
    { rotulo: "Dotação inicial (R$)", num: true, valor: l => l.inicial, fmt: brl },
    { rotulo: "Dotação atualizada (R$)", num: true, valor: l => l.atualizada, fmt: brl },
    { rotulo: "Empenhado (R$)", num: true, valor: l => l.empenhada, fmt: brl },
    { rotulo: "Pago (R$)", num: true, valor: l => l.paga, fmt: brl },
    { rotulo: "Executado", num: true, valor: execucao, render: l => { const v = execucao(l); if (nulo(v)) return "—";
      return h("span", { class: "mini-exec" }, h("span", { class: "trilho", "aria-hidden": "true" }, h("span", { class: "fill", style: "width:" + Math.min(100, Math.max(0, v)) + "%" })), " " + nf(v, 0) + "%"); } },
  ];
  card.append(h("p", { class: "nota" }, "Clique no nome da ação para ver quem recebeu, com que elemento e fonte — e o que as contratações dizem ter comprado."));
  card.append(tabela(colunas, linhas, "Ações da Educação — " + nome + ", " + ano,
    { inicio: 12, classeLinha: l => l.obra && execucao(l) !== null && execucao(l) < 50 ? "l-sinal" : null, csv: "acoes_" + cod + "_" + ano + ".csv",
      rodape: ["Total (" + linhas.length + " ações)", "", brl(tot.at), brl(tot.em), "", ""] }));
  return card;
}

function cardNivel3Fontes(cod, ano) {
  const nome = nomeEnte(cod);
  const linhas = (FONTES_DET_EA.get(chaveEA(cod, ano)) || []).slice().sort((a, b) => b.empenhada - a.empenhada);
  const card = h("article", { class: "card", id: "card-fontes" }, cabecalho("Com que dinheiro: fonte e detalhamento — " + nome + ", " + ano, {
    simples: "De onde veio o dinheiro de cada empenho, com o detalhe que o município informa ao Tribunal (convênio, programa estadual, FUNPAES…).",
    fonte: { itens: () => linhas.slice(0, 30).map(f => ({ indicador: "empenho_fonte", ano, detalhe: "fonte " + f.CodigoFonteReduzida + ", detalhamento " + f.CodigoDetalhamento + " (" + f.NomeDetalhamento + ")", q: f.q, valor: brl(f.empenhada) })) } }));
  if (!EMPENHOS_COLETADOS) { card.append(avisoEmpenhos()); return card; }
  if (!linhas.length) { card.append(h("p", {}, chipEstado("semdado"))); return card; }
  const total = linhas.reduce((t, f) => t + f.empenhada, 0);
  card.append(tabela([
    { rotulo: "Fonte", valor: f => f.CodigoFonteReduzida + " " + f.NomeFonteReduzida, render: f => h("span", {}, h("span", { class: "muted" }, f.CodigoFonteReduzida + " "), f.NomeFonteReduzida) },
    { rotulo: "Detalhamento", valor: f => f.CodigoDetalhamento + " " + f.NomeDetalhamento, render: f => h("span", {}, h("span", { class: "muted" }, f.CodigoDetalhamento + " "), f.NomeDetalhamento) },
    { rotulo: "Empenhado (R$)", num: true, valor: f => f.empenhada, fmt: brl },
    { rotulo: "%", num: true, valor: f => total ? 100 * f.empenhada / total : null, fmt: v => nf(v, 1) + "%" },
  ], linhas, "Fontes detalhadas — " + nome + ", " + ano, { inicio: 10, csv: "fontes_detalhadas_" + cod + "_" + ano + ".csv", fixarPrimeira: false }));
  return card;
}

function cardNivel3Conselhos(cod, ano) {
  const nome = nomeEnte(cod);
  const linhas = (CONSELHOS_EA.get(chaveEA(cod, ano)) || []).slice().sort((a, b) => b.empenhada - a.empenhada);
  const card = h("article", { class: "card", id: "card-conselhos" }, cabecalho("Para qual escola: repasses do município a conselhos escolares — " + nome + ", " + ano, {
    simples: "Dinheiro do próprio município entregue diretamente às escolas, por meio dos conselhos ou caixas escolares.",
    nota: "Identificado pelo credor do empenho. A escola é ligada ao Censo Escolar pelo nome; o que é ambíguo fica sem vínculo.",
    fonte: { itens: () => linhas.map(c => ({ indicador: "repasse_conselho_escolar", ano, detalhe: c.credor + " — " + c.credor_nome, q: c.q, valor: brl(c.empenhada) })) } }));
  if (!EMPENHOS_COLETADOS) { card.append(avisoEmpenhos()); return card; }
  if (!linhas.length) { card.append(h("p", {}, "Nenhum empenho a conselho escolar, caixa escolar ou associação de escola em " + ano + ". O município pode não ter programa próprio de repasse às escolas.")); return card; }
  const total = linhas.reduce((t, c) => t + c.empenhada, 0);
  const vinc = c => VINCULO_POR_ORIGEM.get("conselho|" + cod + "|" + c.credor);
  const comEscola = linhas.filter(c => { const v = vinc(c); return v && v.co_entidade; }).length;
  card.append(h("p", {}, h("strong", {}, brl(total)), " a " + linhas.length + " conselho(s) · " + comEscola + " ligado(s) a uma escola do Censo."),
    tabela([
      { rotulo: "Conselho (credor)", valor: c => c.credor_nome, classe: "col-nome" },
      { rotulo: "Escola no Censo", valor: c => { const v = vinc(c); return v && v.co_entidade ? (ESCOLAS.get(v.co_entidade) || {}).nome : ""; },
        render: c => { const v = vinc(c); return v && v.co_entidade ? linkEscola(v.co_entidade) : h("span", { class: "muted", title: v ? v.metodo : "" }, "não identificada"); } },
      { rotulo: "Empenhado (R$)", num: true, valor: c => c.empenhada, fmt: brl },
      { rotulo: "Pago (R$)", num: true, valor: c => c.paga, fmt: brl },
    ], linhas, "Repasses a conselhos escolares — " + nome + ", " + ano, { inicio: 10, csv: "conselhos_" + cod + "_" + ano + ".csv" }));
  return card;
}

function itensFonteObra(o) {
  const ano = parseInt(String(o.assinatura || "").slice(0, 4), 10) || META.ano_mais_recente;
  const itens = [{ indicador: "obra_educacao", ano, detalhe: "contratação " + o.contratacao, q: o.q, valor: brl(o.valor || 0),
    observacao: (o.objeto || "") + " · situação " + (o.situacao || "—") + " · contratada " + (o.contratado || "—") + " (" + fmtDoc(o.cnpj_contratado) + ")" }];
  if (!nulo(o.valor_medido)) itens.push({ indicador: "obra_medido", ano, detalhe: "contratação " + o.contratacao, q: o.q,
    valor: brl(o.valor_medido), observacao: nf(o.medicoes || 0) + " medição(ões), última em " + dataBR(o.ultima_medicao) + (o.aditivos ? " · " + o.aditivos + " aditivo(s)" : "") });
  return itens;
}

function cardNivel3Obras(cod) {
  const nome = nomeEnte(cod);
  const obras = (OBRAS_EDU.get(cod) || []).slice().sort((a, b) => (obraParada(b) - obraParada(a)) || (b.assinatura || "").localeCompare(a.assinatura || ""));
  const card = h("article", { class: "card largo", id: "card-obras" }, cabecalho("Contratos de obra da Educação — " + nome + " (situação atual)", {
    simples: "Todas as obras de escolas e prédios da Educação que o município declarou ao Tribunal, com a situação na data da coleta, as medições e o prédio. As paradas aparecem primeiro.",
    nota: "Contratos com setor beneficiado \"Educação\" declarados ao TCE-ES, com o prédio (bem vinculador), a situação e as medições. Retrato da data da coleta, não do exercício.",
    limitacao: "Obras", fonte: { itens: () => obras.flatMap(itensFonteObra) } }));
  if (!obras.length) { card.append(h("p", {}, "Nenhum contrato de obra da Educação declarado ao TCE-ES.")); return card; }
  const valor = obras.reduce((t, o) => t + (o.valor || 0), 0), paradas = obras.filter(obraParada);
  card.append(h("p", {}, h("strong", {}, obras.length + " contrato(s)"), ", " + brl(valor) + ". ",
    paradas.length ? chipEstado("sinal", paradas.length + " parado(s) ou com paralisação presumida — " + brlCompacto(paradas.reduce((t, o) => t + (o.valor || 0), 0))) : "Nenhum parado."));
  const vincObra = (o, i) => VINCULO_POR_ORIGEM.get("obra|" + o.chave + "#" + i);
  const lista = h("div", { class: "lista-obras" });
  for (const o of obras) {
    const bens = bensDe(o);
    lista.append(h("details", { class: "obra" + (obraParada(o) ? " parada" : "") },
      h("summary", {}, h("span", { class: "obra-tit" }, String(o.objeto || "(sem objeto)").slice(0, 160)), " ", seloObra(o.situacao),
        h("span", { class: "obra-valor" }, brl(o.valor || 0))),
      h("dl", { class: "obra-dl" },
        h("dt", {}, "Contratação"), h("dd", {}, o.contratacao + " · " + (o.ug || "")),
        h("dt", {}, "Contratada"), h("dd", {}, (o.contratado || "—") + " · CNPJ " + fmtDoc(o.cnpj_contratado)),
        h("dt", {}, "Valores"), h("dd", {}, "inicial " + (nulo(o.valor_inicial) ? "—" : brl(o.valor_inicial)) + " · atual " + (nulo(o.valor_atual) ? "—" : brl(o.valor_atual)) +
          (o.aditivos ? " · " + o.aditivos + " aditivo(s)" : "")),
        h("dt", {}, "Prazo"), h("dd", {}, "assinatura " + dataBR(o.assinatura) + " · fim da vigência " + dataBR(o.fim_vigencia)),
        h("dt", {}, "Medições"), h("dd", {}, nulo(o.medicoes) ? "nenhuma medição no arquivo do TCE-ES" :
          nf(o.medicoes) + " medição(ões), " + brl(o.valor_medido || 0) + " medido (" + nf(o.pct_medido || 0, 0) + "% do valor atual) · pago nas medições " + brl(o.valor_pago_medicoes || 0) + " · última em " + dataBR(o.ultima_medicao)),
        h("dt", {}, "Prédio"), h("dd", {}, bens.length ? h("ul", { class: "lista" }, bens.map((b, i) => { const v = vincObra(o, i);
          return h("li", {}, b.nome || "(sem nome)", b.categoria ? h("span", { class: "muted" }, " · " + b.categoria) : null, " ",
            linkMapa(b.lat, b.lon), v && v.co_entidade ? [" · escola no Censo: ", linkEscola(v.co_entidade)] : null); })) : "não informado"),
        h("dt", {}, "Documentos"), h("dd", {}, o.url_contrato ? h("a", { href: o.url_contrato, target: "_blank", rel: "noopener noreferrer" }, "contrato ↗") : "—",
          o.url_edital ? [" · ", h("a", { href: o.url_edital, target: "_blank", rel: "noopener noreferrer" }, "edital ↗")] : null)),
      botaoFonte("Obra " + o.contratacao + " — " + nome, () => itensFonteObra(o))));
  }
  card.append(lista);
  card.append(h("div", { class: "acoes-tabela" }, h("button", { type: "button", class: "leve", onclick: () => baixarCSV("obras_" + cod + ".csv", [
    { rotulo: "Contratação", valor: o => o.contratacao }, { rotulo: "Objeto", valor: o => o.objeto }, { rotulo: "Contratada", valor: o => o.contratado },
    { rotulo: "CNPJ", valor: o => o.cnpj_contratado }, { rotulo: "Valor atual", valor: o => o.valor }, { rotulo: "Situação", valor: o => o.situacao },
    { rotulo: "Assinatura", valor: o => o.assinatura }, { rotulo: "Medições", valor: o => o.medicoes }, { rotulo: "Valor medido", valor: o => o.valor_medido },
    { rotulo: "Última medição", valor: o => o.ultima_medicao }, { rotulo: "Contrato (URL)", valor: o => o.url_contrato }], obras) }, "Baixar CSV")));
  return card;
}

/** Nível 3 — o item comprado: o que as contratações da Educação declaram ao TCE-ES. */
function cardNivel3Itens(cod, ano) {
  const nome = nomeEnte(cod), chave = chaveEA(cod, ano);
  const linhas = (ITENS_EA.get(chave) || []).slice().sort((a, b) => b.valor_total - a.valor_total);
  const resumo = ITENS_RESUMO.get(chave);
  const card = h("article", { class: "card largo", id: "card-itens" }, cabecalho("O que foi comprado: itens das contratações da Educação — " + nome + ", " + ano, {
    simples: "O que cada contrato da Educação diz ter comprado: descrição, quantidade, preço unitário e o que já foi medido.",
    nota: "Cobertura desigual por construção: só entra a linha que a própria fonte liga à Educação (unidade gestora de educação, setor beneficiado \"Educação\" ou obra da Educação).",
    limitacao: "Itens contratados", fonte: { itens: () => itensFonteItem(cod, ano, linhas) } }));
  if (!ITENS_COLETADOS) { card.append(avisoNaoColetado("Os itens das contratações do TCE-ES")); return card; }
  if (!linhas.length) {
    const outros = ANOS.filter(a => (ITENS_EA.get(chaveEA(cod, a)) || []).length);
    card.append(h("p", {}, chipEstado("semdado"), " Nenhum item com contrato de " + ano + " em " + nome + ". ",
      outros.length ? h("span", {}, "Este município tem itens em ", h("strong", {}, outros.join(", ")),
        " — o exercício do item é o do contrato, então um contrato plurianual aparece no ano da assinatura. ") : "",
      "Ausência aqui não é ausência de compra: quem compra pela unidade gestora da prefeitura, sem marcar o setor beneficiado, fica fora do recorte."));
    return card;
  }
  const vinculos = resumo && resumo.vinculos ? String(resumo.vinculos).split(",") : [...new Set(linhas.map(i => i.vinculo))];
  card.append(h("div", { class: "kpis" },
    kpi("Itens no recorte", nf(resumo ? resumo.itens : linhas.length), resumo ? nf(resumo.contratacoes) + " contratação(ões) · " + nf(resumo.contratadas) + " contratada(s)" : ""),
    kpi("Valor contratado", brlCompacto(resumo ? resumo.valor_contratado : linhas.reduce((t, i) => t + (i.valor_total || 0), 0)), "soma do valor total dos itens"),
    kpi("Medido", resumo && resumo.valor_medido ? brlCompacto(resumo.valor_medido) : "sem medição", "o que a fonte registra como medido", { nd: !(resumo && resumo.valor_medido) })));
  card.append(h("p", { class: "nota" }, h("strong", {}, "Como estas linhas entraram: "), vinculos.map(v => VINCULO_ITEM[v] || v).join("; ") + ". " +
    "O CNPJ da contratada não é usado como regra — a empresa que vende à educação também vende ao resto da prefeitura."));
  card.append(tabela(COLUNAS_ITEM_DETALHE, linhas, "Itens contratados — " + nome + ", " + ano, { inicio: 10, csv: "itens_" + cod + "_" + ano + ".csv" }));
  if (resumo && resumo.itens > linhas.length) card.append(h("p", { class: "nota" }, "O painel traz os " + linhas.length +
    " maiores itens de cada município no ano; a lista completa deste exercício (" + nf(resumo.itens) + " itens) está no arquivo tcees_itens.csv do conjunto de dados do painel."));
  return card;
}

function cardNivel3Limites(cod) {
  const nome = nomeEnte(cod);
  const portal = ((D.dados_manuais || {}).portais || []).find(p => p.cod_ibge === cod && p.verificado);
  const card = h("article", { class: "card largo", id: "card-limites-n3" }, cabecalho("O que ainda não chega ao painel", {
    simples: "Nem tudo o que se quer saber sobre o gasto está em dado aberto. Estes são os limites conhecidos e onde buscar à mão." }));
  card.append(h("ul", { class: "lista" },
    h("li", {}, h("strong", {}, "Salário por escola: "), "a folha é a maior parte da despesa, mas o vínculo do servidor no TCE-ES não traz a lotação — não há como atribuir salário a uma escola."),
    h("li", {}, h("strong", {}, "O que cada escola fez com o PDDE: "), "a escola presta contas ao FNDE, fora da contabilidade municipal e sem dado aberto por item."),
    h("li", {}, h("strong", {}, "Nota fiscal: "), "número, data e emitente da nota estão no portal da transparência do município, não no dado aberto do TCE-ES."),
    h("li", {}, h("strong", {}, "Empenho ↔ contrato: "), "o empenho não traz o número do contrato. O painel cruza os dois por CNPJ e município, o que é indício, não identidade."),
    h("li", {}, h("strong", {}, "Portal da transparência de " + nome + ": "),
      portal ? h("span", {}, h("a", { href: portal.url, target: "_blank", rel: "noopener noreferrer" }, portal.url), " · conferido em " + dataBR(portal.verificado_em),
        portal.api ? h("div", { class: "nota" }, "API documentada e aberta: ", h("a", { href: portal.api, target: "_blank", rel: "noopener noreferrer" }, portal.api),
          portal.observacao ? " — " + portal.observacao : "", ". O painel não a consulta: é o caminho para buscar nota e item à mão.") : null)
        : "endereço ainda não cadastrado no painel.")));
  return card;
}
