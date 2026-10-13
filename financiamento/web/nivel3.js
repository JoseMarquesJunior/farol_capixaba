"use strict";
/* ============================================================================
   TCE-ES no painel: Nível 3 da despesa (credor, ação, fonte detalhada, repasse a
   conselho escolar, obra) e a conformidade junto ao Tribunal (MDE apurado pelo
   TCE-ES, prazos da prestação de contas mensal, obras paradas).
   Dados DECLARATÓRIOS (remessas do CidadES): o painel mostra o que o município
   informou ao Tribunal, com a consulta de origem em cada "ver fonte".
   ========================================================================== */

const PCM_LINHAS = expandir(D.pcm);
const OBRAS_EDU = agrupar(expandir(D.obras), o => o.cod_ibge);
const CREDORES_EA = agrupar(expandir(D.credores), r => chaveEA(r.cod_ibge, r.ano));
const ACOES_EA = agrupar(expandir(D.acoes), r => chaveEA(r.cod_ibge, r.ano));
const FONTES_DET_EA = agrupar(expandir(D.fontes_det), r => chaveEA(r.cod_ibge, r.ano));
const CONSELHOS_EA = agrupar(expandir(D.conselhos), r => chaveEA(r.cod_ibge, r.ano));
const OBRAS_EMP_EA = agrupar(expandir(D.obras_empenhos), r => chaveEA(r.cod_ibge, r.ano));
const DOTACAO_EA = agrupar(expandir(D.dotacao), r => chaveEA(r.cod_ibge, r.ano));
/* Credor × ação e itens contratados: o "ver detalhamento" de um credor ou de uma ação. */
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

const semAcento = s => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
function fmtDoc(doc) {
  const d = String(doc || "").replace(/\D/g, "");
  if (d.length === 14) return d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
  return doc || "—";
}

/* ------------------------------------------------------------ situação da obra */
/** Classe da situação declarada no TCE-ES. "Paralisação presumida" é inferida pelo
 *  Tribunal (obra sem medição recente), não declarada pelo município. */
function classeObra(sit) {
  const s = semAcento(sit);
  if (/presumida/.test(s)) return "presumida";
  if (/paralisada|interrompida/.test(s)) return "paralisada";
  if (/nao iniciada/.test(s)) return "nao_iniciada";
  if (/execucao/.test(s)) return "execucao";
  if (/concluida/.test(s)) return "concluida";
  return "outra";
}
const ROT_CLASSE_OBRA = {
  paralisada: "✖ paralisada", presumida: "⚠ paralisação presumida (TCE-ES)", nao_iniciada: "○ não iniciada",
  execucao: "▶ em execução", concluida: "✔ concluída", outra: "situação não identificada",
};
function seloObra(sit) {
  const c = classeObra(sit);
  const classe = c === "paralisada" ? "badge crit" : c === "presumida" || c === "nao_iniciada" ? "badge aviso" : c === "concluida" ? "badge api" : "badge nada";
  return h("span", { class: classe, title: sit || "" }, ROT_CLASSE_OBRA[c] + (c === "concluida" && sit ? " · " + sit.replace(/^Conclu[íi]da e /, "") : ""));
}
const obraParada = o => ["paralisada", "presumida"].includes(classeObra(o.situacao));
function bensDe(o) { try { return JSON.parse(o.bens || "[]"); } catch (e) { return []; } }
/** Link de mapa para a coordenada informada pelo TCE-ES (centroide do bem vinculador). */
function linkMapa(lat, lon, rotulo) {
  if (nulo(lat) || nulo(lon)) return null;
  return h("a", { href: "https://www.openstreetmap.org/?mlat=" + lat + "&mlon=" + lon + "#map=17/" + lat + "/" + lon,
    target: "_blank", rel: "noopener noreferrer", title: "Coordenada informada ao TCE-ES: " + lat + ", " + lon }, rotulo || "mapa");
}
/* ===================================================== "ver detalhamento" (Nível 3)

   A tabela de credores e a de ações mostram cada uma um lado do empenho. O diálogo
   abaixo junta os dois — quem recebeu, em qual ação, com que elemento e que fonte —
   e acrescenta o que a contratação diz ter comprado. O vínculo empenho ↔ contratação
   é por CNPJ e município, porque o empenho do TCE-ES não traz o número do contrato:
   por isso os itens aparecem numa seção à parte, rotulada como indício.
   ============================================================================== */

const CNPJ = doc => String(doc || "").replace(/\D/g, "");

/** Linhas de credor × ação de um município-ano, opcionalmente de um credor ou de uma ação. */
function credorAcaoDe(cod, ano, { credor, acao } = {}) {
  return (CREDOR_ACAO_EA.get(chaveEA(cod, ano)) || [])
    .filter(r => (credor === undefined || r.credor === credor) && (acao === undefined || String(r.CodigoAcao) === String(acao)))
    .slice().sort((a, b) => b.empenhada - a.empenhada);
}
/** Itens embutidos de uma contratada (CNPJ), no município-ano. */
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
  { rotulo: "Qtd.", num: true, valor: i => i.quantidade, render: i => nulo(i.quantidade) ? "—" : nf(i.quantidade, 2) },
  { rotulo: "Valor unitário", num: true, valor: i => i.valor_unitario, render: i => nulo(i.valor_unitario) ? "—" : brl(i.valor_unitario) },
  { rotulo: "Valor total", num: true, valor: i => i.valor_total, render: i => nulo(i.valor_total) ? "—" : brl(i.valor_total) },
  { rotulo: "Medido", num: true, valor: i => i.valor_medido,
    render: i => nulo(i.valor_medido) ? h("span", { class: "muted" }, "sem medição") : brl(i.valor_medido) },
  { rotulo: "Contratação", valor: i => i.contratacao, render: i => { const c = CONTRATACOES.get(i.contratacao);
    return h("span", {}, h("code", {}, i.contratacao || "—"), c && c.objeto ? h("div", { class: "nota" }, String(c.objeto).slice(0, 120)) : null); } },
];

function itensFonteItem(cod, ano, itens) {
  return itens.map(i => ({ indicador: "item_contratado", ano, detalhe: "contratação " + i.contratacao + " · " + String(i.descricao).slice(0, 80),
    q: i.q, valor: nulo(i.valor_total) ? null : brl(i.valor_total),
    observacao: "vínculo com a Educação: " + (VINCULO_ITEM[i.vinculo] || i.vinculo) + "; unidade gestora " + (i.ug || "—") }));
}

/** Seção "o que a contratação diz ter comprado", com o aviso de que o vínculo é por CNPJ. */
function secaoItensDoCredor(cod, ano, credor, nomeCredor) {
  const cnpj = CNPJ(credor);
  if (!ITENS_COLETADOS) {
    return h("p", { class: "nota" }, h("span", { class: "badge nada" }, "Não coletado"),
      " Os itens das contratações do TCE-ES não entraram nesta execução.");
  }
  if (!cnpj) {
    return h("p", { class: "nota" }, "Credor sem CNPJ (pessoa física agregada ou linha de resumo): não há contratação a cruzar.");
  }
  const resumo = resumoDaContratada(cod, ano, cnpj), itens = itensDaContratada(cod, ano, cnpj);
  if (!resumo && !itens.length) {
    // O exercício do item é o do INSTRUMENTO: contrato de 2024 pago em 2025 aparece em 2024.
    const outros = ANOS.filter(a => a !== ano && resumoDaContratada(cod, a, cnpj));
    return h("p", { class: "nota" }, "Nenhuma contratação da Educação deste CNPJ com instrumento de " + ano + " neste município. ",
      outros.length
        ? h("span", {}, "Há contratação dele em ", h("strong", {}, outros.join(", ")),
            " — o exercício do item é o do instrumento contratual, então empenho de " + ano +
            " pode se referir a contrato assinado antes. Troque o exercício no filtro para ver os itens.")
        : "Pode ser compra feita pela unidade gestora da prefeitura sem setor beneficiado marcado — o recorte não a alcança (ver limitações).");
  }
  const bloco = h("div", {}, h("div", { class: "callout" }, h("strong", {}, "Vínculo por CNPJ, não por contrato. "),
    "O empenho do TCE-ES não traz o número do contrato. O que segue são as contratações da Educação do mesmo CNPJ, no mesmo município e exercício — " +
    "indício forte de a que se refere o empenho, não prova de identidade entre os dois valores."));
  if (resumo) {
    bloco.append(h("p", {}, h("strong", {}, brl(resumo.valor_contratado)), " contratados em ", nf(resumo.itens), " item(ns), ",
      nf(resumo.contratacoes), " contratação(ões)", nulo(resumo.valor_medido) || !resumo.valor_medido ? "" : " · " + brl(resumo.valor_medido) + " medidos", "."));
  }
  if (itens.length) {
    bloco.append(tabelaExpansivel(COLUNAS_ITEM_DETALHE, itens.slice().sort((a, b) => b.valor_total - a.valor_total),
      "Itens contratados de " + nomeCredor + ", " + ano, { inteira: true, inicio: 5 }),
      botaoCSV("itens_" + cnpj + "_" + ano + ".csv", COLUNAS_ITEM_DETALHE, itens));
    if (resumo && resumo.itens > itens.length) {
      bloco.append(h("p", { class: "nota" }, "Estes são os itens desta contratada que entraram no painel (os maiores do município-ano). " +
        "Os " + nf(resumo.itens) + " itens completos estão em ", h("code", {}, "dados/processado/tcees_itens.csv"), "."));
    }
  }
  return bloco;
}

/** Diálogo de detalhamento. `alvo` = {tipo: "credor"|"acao", …}. */
function abrirDetalhe(cod, ano, alvo) {
  const dlg = $("#dialogo-detalhe");
  limpar(dlg);
  const nome = ENTES.get(cod).nome;
  const ehCredor = alvo.tipo === "credor";
  const linhas = credorAcaoDe(cod, ano, ehCredor ? { credor: alvo.credor } : { acao: alvo.acao });
  const titulo = ehCredor ? alvo.nome : alvo.codigo + " - " + alvo.nome;
  const total = linhas.reduce((s, r) => s + (r.empenhada || 0), 0);

  const colunas = ehCredor
    ? [{ rotulo: "Ação do orçamento", valor: r => r.CodigoAcao + " - " + r.NomeAcao,
         render: r => h("span", {}, h("span", { class: "muted" }, r.CodigoAcao + " "), r.NomeAcao) },
       { rotulo: "Elemento de despesa", valor: r => r.elemento || "—" },
       { rotulo: "Fonte", valor: r => r.fonte || "—" },
       { rotulo: "Empenhado (R$)", num: true, valor: r => r.empenhada, fmt: brl },
       { rotulo: "Pago (R$)", num: true, valor: r => r.paga, fmt: brl }]
    : [{ rotulo: "Credor", valor: r => r.credor_nome,
         render: r => r.credor === "(demais)" ? h("span", { class: "muted" }, r.credor_nome + " (" + nf(r.demais) + ")") : r.credor_nome },
       { rotulo: "CNPJ", valor: r => r.credor, render: r => /^\d/.test(String(r.credor)) ? fmtDoc(r.credor) : "—" },
       { rotulo: "Elemento de despesa", valor: r => r.elemento || "—" },
       { rotulo: "Fonte", valor: r => r.fonte || "—" },
       { rotulo: "Empenhado (R$)", num: true, valor: r => r.empenhada, fmt: brl },
       { rotulo: "Pago (R$)", num: true, valor: r => r.paga, fmt: brl }];

  const corpo = h("div", { class: "fonte-corpo" });
  if (!EMPENHOS_COLETADOS) {
    corpo.append(avisoEmpenhos());
  } else if (!linhas.length) {
    corpo.append(h("p", {}, h("span", { class: "badge nada" }, "Sem empenho"),
      ehCredor ? " Este credor não tem empenho da função 12 em " + ano + " com ação identificada."
        : " Nenhum empenho da função 12 nesta ação em " + ano + ". Se a ação tem dotação, ela foi orçada e não executada — é isso que o dado diz."));
  } else {
    corpo.append(h("p", {}, h("strong", {}, brl(total)), " empenhado(s) em " + linhas.length + " linha(s)."),
      tabelaExpansivel(colunas, linhas, titulo + " — detalhamento", { inteira: true, inicio: 8 }),
      botaoCSV("detalhe_" + (ehCredor ? "credor_" + alvo.credor : "acao_" + alvo.codigo) + "_" + cod + "_" + ano + ".csv", colunas, linhas));
    if (linhas.some(r => r.credor === "(demais)")) {
      corpo.append(h("p", { class: "nota" }, "A linha \"Demais credores da ação\" soma os credores fora dos 8 maiores daquela ação: o valor está completo, os nomes não."));
    }
  }
  corpo.append(h("h3", {}, "O que foi comprado"));
  if (ehCredor) {
    corpo.append(secaoItensDoCredor(cod, ano, alvo.credor, alvo.nome));
  } else {
    const cnpjs = [...new Set(linhas.map(r => CNPJ(r.credor)).filter(Boolean))];
    const itens = cnpjs.flatMap(c => itensDaContratada(cod, ano, c));
    corpo.append(itens.length
      ? h("div", {}, h("p", { class: "nota" }, "Itens das contratações da Educação dos credores acima (vínculo por CNPJ e município, não por contrato)."),
        tabelaExpansivel(COLUNAS_ITEM_DETALHE, itens.sort((a, b) => b.valor_total - a.valor_total),
          "Itens dos credores da ação", { inteira: true, inicio: 5 }))
      : h("p", { class: "nota" }, ITENS_COLETADOS
        ? "Nenhum item de contratação da Educação casou com os credores desta ação no recorte deste município e exercício."
        : "Os itens das contratações do TCE-ES não entraram nesta execução."));
  }
  const portal = ((D.dados_manuais || {}).portais || []).find(p => p.cod_ibge === cod && p.verificado);
  corpo.append(h("p", { class: "nota" }, "Nota fiscal, empresa por nota e data de pagamento não estão no dado aberto do TCE-ES. ",
    portal ? h("span", {}, "No portal de " + nome + ": ",
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
    corpo,
    h("footer", {}, botaoFonte(titulo + " — " + nome + ", " + ano, itensFonte)));
  if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
}

/** Botão que abre o detalhamento de um credor ou de uma ação, no texto da própria célula. */
function botaoDetalhe(texto, cod, ano, alvo) {
  return h("button", { type: "button", class: "link detalhe", "aria-haspopup": "dialog",
    title: "Ver detalhamento: ação, elemento, fonte e itens contratados", onclick: () => abrirDetalhe(cod, ano, alvo) }, texto);
}

function botaoEscola(co, texto) {
  const e = ESCOLAS.get(co);
  if (!e) return h("span", { class: "muted" }, texto || "—");
  return h("button", { type: "button", class: "link", onclick: () => { estado.municipio = e.cod_ibge; estado.escola = co; irPara("escolas"); } },
    texto || e.nome);
}

/* ======================================================= CONFORMIDADE (TCE-ES) */

/** Prestação de contas mensal ao TCE-ES — a janela que o Tribunal publica (não o exercício). */
function cardRemessasTcees() {
  const card = h("article", { class: "card largo", id: "card-remessas-tcees" }, cabecalho(
    "Prestação de contas mensal ao TCE-ES — prazos",
    "Cada unidade gestora (prefeitura, câmara, fundos, autarquias) envia a remessa mensal ao Tribunal. A DATA-LIMITE vem na própria fonte; " +
    "atraso = homologação depois do limite. \"Não homologada\" = prazo vencido sem homologação na data da coleta, numa UG que homologa outros meses. " +
    "UG sem nenhuma remessa homologada na janela inteira é contada à parte: o padrão é o de conta consolidada em outra UG, não de atraso (a confirmar com o Tribunal).",
    { itens: () => [{ indicador: "remessa_tcees_atraso_dias", ano: META.ano_mais_recente, detalhe: "todas as UGs dos municípios",
      q: [...new Set(PCM_LINHAS.map(r => r.q).filter(Boolean))].join(";") }] }));
  const vencidas = PCM_LINHAS.filter(r => r.situacao !== "prazo_aberto" && r.situacao !== "ug_sem_remessa");
  const semRemessa = agrupar(PCM_LINHAS.filter(r => r.situacao === "ug_sem_remessa"), r => r.cod_ibge);
  if (!vencidas.length) { card.append(h("p", {}, h("span", { class: "badge nada" }, "Sem dado"), " Recurso do TCE-ES não coletado nesta execução.")); return card; }
  const per = vencidas.map(r => r.ano * 100 + r.mes), ini = Math.min(...per), fim = Math.max(...per);
  const mesAno = v => String(v % 100).padStart(2, "0") + "/" + Math.floor(v / 100);
  const porMun = agrupar(vencidas, r => r.cod_ibge);
  const linhas = MUNICIPIOS.map(e => {
    const rs = porMun.get(e.cod_ibge) || [];
    const atr = rs.filter(r => r.situacao === "com_atraso"), nh = rs.filter(r => r.situacao === "nao_homologada");
    const sr = [...new Set((semRemessa.get(e.cod_ibge) || []).map(r => r.ug))];
    return { e, rs, atr, nh, sr, ugs: new Set(rs.map(r => r.ug)).size, maior: Math.max(0, ...atr.concat(nh).map(r => r.dias_atraso || 0)) };
  }).filter(l => !estado.alertas || l.atr.length || l.nh.length)
    .sort((a, b) => b.nh.length - a.nh.length || b.maior - a.maior || b.atr.length - a.atr.length);
  const comProblema = linhas.filter(l => l.atr.length || l.nh.length).length;
  card.append(h("p", {}, "Janela publicada pelo TCE-ES: remessas de ", h("strong", {}, mesAno(ini)), " a ", h("strong", {}, mesAno(fim)),
    " (o Tribunal publica só os meses recentes — anos anteriores não estão no arquivo). ",
    h("strong", {}, String(comProblema)), " município(s) com remessa atrasada ou não homologada."));
  const itemRem = r => h("li", {}, h("strong", {}, r.ug), " · " + String(r.mes).padStart(2, "0") + "/" + r.ano + ": limite " + dataBR(r.limite) + ", " +
    (r.situacao === "nao_homologada" ? "não homologada (" + nf(r.dias_atraso || 0) + " dias desde o limite)" : "homologada " + dataBR(r.homologacao) + " (" + nf(r.dias_atraso || 0) + " dias)"));
  const colunas = [
    { rotulo: "Município", valor: l => l.e.nome },
    { rotulo: "UGs", num: true, valor: l => l.ugs },
    { rotulo: "Remessas vencidas", num: true, valor: l => l.rs.length },
    { rotulo: "Com atraso", num: true, valor: l => l.atr.length },
    { rotulo: "Não homologadas", num: true, valor: l => l.nh.length, render: l => l.nh.length ? h("strong", { class: "flag-abaixo" }, "✖ " + l.nh.length) : "0" },
    { rotulo: "Maior atraso (dias)", num: true, valor: l => l.maior || null, render: l => l.maior ? nf(l.maior) : "—" },
    { rotulo: "UGs sem remessa na janela", num: true, valor: l => l.sr.length,
      render: l => l.sr.length ? h("details", {}, h("summary", {}, String(l.sr.length)), h("ul", { class: "lista" }, l.sr.map(u => h("li", {}, u)))) : "0" },
    { rotulo: "Quais", valor: l => l.atr.concat(l.nh).map(r => r.ug + " " + r.mes + "/" + r.ano).join("; "),
      render: l => (l.atr.length + l.nh.length) ? h("details", {}, h("summary", {}, (l.atr.length + l.nh.length) + " remessa(s)"),
        h("ul", { class: "lista" }, l.nh.concat(l.atr).slice(0, 40).map(itemRem))) : "—" },
    { rotulo: "Fonte", valor: () => "", render: l => botaoFonte(l.e.nome + " — prestação de contas mensal ao TCE-ES",
      () => [{ indicador: "remessa_tcees_atraso_dias", ano: Math.floor(fim / 100), detalhe: l.e.nome + " (todas as UGs)", q: (l.rs[0] || {}).q }]) },
  ];
  card.append(tabela(colunas, linhas, "Prestação de contas mensal ao TCE-ES", { classeLinha: l => l.nh.length ? "alerta" : l.atr.length ? "atencao" : null }),
    botaoCSV("remessas_tcees.csv", colunas.filter(c => c.rotulo !== "Fonte"), linhas));
  return card;
}

/** Obras da Educação paradas ou não iniciadas — retrato atual, todos os municípios. */
function cardObrasParadas() {
  const k = META.kpis_obras || {};
  const todas = [...OBRAS_EDU.values()].flat();
  const card = h("article", { class: "card largo", id: "card-obras-paradas" }, cabecalho(
    "Obras da Educação paradas ou não iniciadas — retrato atual",
    "Contratos de obra com setor beneficiado \"Educação\" declarados ao TCE-ES, na situação da data da coleta (não a do exercício). " +
    "\"Paralisação presumida\" é a classificação do Tribunal para obra sem medição recente.",
    { itens: () => [{ indicador: "obra_educacao", ano: META.ano_mais_recente, detalhe: "todos os contratos da Educação", q: (todas[0] || {}).q }] }));
  if (!todas.length) { card.append(h("p", {}, h("span", { class: "badge nada" }, "Sem dado"), " Contratações do TCE-ES não coletadas nesta execução.")); return card; }
  card.append(h("div", { class: "kpis" },
    kpi("Contratos de obra da Educação", nf(k.contratos || todas.length), (k.municipios || "–") + " municípios · " + brlCompacto(k.valor || 0)),
    kpi("Paralisadas (declarado)", nf(k.declaradas || 0), "situação \"Paralisada\" ou \"Interrompida\""),
    kpi("Paralisação presumida", nf(k.presumidas || 0), "sem medição recente, segundo o TCE-ES · " + brlCompacto(k.paralisadas_valor || 0) + " com as declaradas"),
    kpi("Não iniciadas", nf(k.nao_iniciadas || 0), "contrato assinado, obra não começou")));
  const filtro = h("select", { "aria-label": "Situação", onchange: () => refazer() },
    h("option", { value: "parada" }, "Paralisadas e presumidas"), h("option", { value: "nao_iniciada" }, "Não iniciadas"),
    h("option", { value: "todas" }, "Todas as situações"));
  const corpo = h("div");
  const colunas = [
    { rotulo: "Município", valor: o => ENTES.get(o.cod_ibge).nome, render: o => h("button", { type: "button", class: "link",
      onclick: () => { estado.municipio = o.cod_ibge; irPara("fluxo"); } }, ENTES.get(o.cod_ibge).nome) },
    { rotulo: "Objeto", valor: o => o.objeto, render: o => h("span", { title: o.objeto }, String(o.objeto || "").slice(0, 110) + (String(o.objeto || "").length > 110 ? "…" : "")) },
    { rotulo: "Contratada", valor: o => o.contratado },
    { rotulo: "Valor atual (R$)", num: true, valor: o => o.valor, fmt: brl },
    { rotulo: "Situação", valor: o => o.situacao, render: o => seloObra(o.situacao) },
    { rotulo: "Assinatura", num: true, valor: o => o.assinatura, fmt: dataBR },
    { rotulo: "Medido", num: true, valor: o => o.pct_medido, render: o => nulo(o.valor_medido) ? "—" : nf(o.pct_medido || 0, 0) + "% · última " + dataBR(o.ultima_medicao) },
    { rotulo: "Fonte", valor: () => "", render: o => botaoFonte("Obra " + o.contratacao, () => itensFonteObra(o)) },
  ];
  function refazer() {
    const f = filtro.value;
    const sel = todas.filter(o => f === "todas" || (f === "parada" ? obraParada(o) : classeObra(o.situacao) === "nao_iniciada"))
      .sort((a, b) => (b.valor || 0) - (a.valor || 0));
    limpar(corpo).append(h("p", { class: "nota" }, sel.length + " contrato(s), " + brl(sel.reduce((s, o) => s + (o.valor || 0), 0)) + ", do maior para o menor valor."),
      tabela(colunas, sel, "Obras da Educação", { classeLinha: o => classeObra(o.situacao) === "paralisada" ? "alerta" : obraParada(o) ? "atencao" : null }),
      botaoCSV("obras_educacao_" + f + ".csv", colunas.filter(c => c.rotulo !== "Fonte"), sel));
  }
  card.append(h("div", { style: "max-width:280px;margin:6px 0" }, campo("Mostrar", filtro)), corpo);
  refazer();
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

/* ============================================================ NÍVEL 3 (fluxo) */

function avisoEmpenhos() {
  return h("p", {}, h("span", { class: "badge nada" }, "Não coletado"),
    " Os empenhos do TCE-ES (~600 MB por ano) não entraram nesta execução. Para coletar: ",
    h("code", {}, "python -m financiamento.etl.pipeline --fontes tcees"), ".");
}
/** Soma dos empenhos × DCA: a conferência que dá lastro ao Nível 3. */
function conferenciaEmpenhos(r) {
  if (nulo(r.tcees_emp_empenhada) || nulo(r.desp_educacao_empenhada)) return null;
  if (r.tcees_emp_meses_ausentes) {
    return h("div", { class: "callout warn" }, h("strong", {}, "Ano incompleto na fonte: "),
      "o arquivo de empenhos publicado pelo TCE-ES não traz o(s) mês(es) " + r.tcees_emp_meses_ausentes + " de " + r.ano +
      " para este município. A soma dos empenhos (" + brl(r.tcees_emp_empenhada) + ") fica abaixo da função 12 do DCA (" +
      brl(r.desp_educacao_empenhada) + ") por falta de dado, não por divergência. Credores e ações abaixo cobrem só os meses publicados.");
  }
  const dif = r.tcees_emp_empenhada - r.desp_educacao_empenhada, rel = r.desp_educacao_empenhada ? 100 * dif / r.desp_educacao_empenhada : 0;
  const ok = Math.abs(dif) <= 1;
  return h("div", { class: "callout" + (ok || Math.abs(rel) < 0.5 ? "" : " warn") },
    h("strong", {}, "Conferência: "), "soma dos empenhos da função 12 no TCE-ES = " + brl(r.tcees_emp_empenhada) + "; DCA I-E = " + brl(r.desp_educacao_empenhada) +
    (ok ? " — batem ao centavo." : " — diferença de " + brl(dif) + " (" + (rel > 0 ? "+" : "") + nf(rel, 2) + "%). Remessas ao Tribunal e ao Tesouro podem divergir por retificação."));
}

function cardNivel3Credores(cod, ano) {
  const nome = ENTES.get(cod).nome, r = LINHA.get(cod + "|" + ano) || {};
  const linhas = (CREDORES_EA.get(chaveEA(cod, ano)) || []).slice().sort((a, b) => b.empenhada - a.empenhada);
  const contratadas = new Set((OBRAS_EDU.get(cod) || []).map(o => String(o.cnpj_contratado || "").replace(/\D/g, "")).filter(Boolean));
  const card = h("article", { class: "card largo" }, cabecalho("Nível 3 — quem recebeu: maiores credores da Educação, " + nome + ", " + ano,
    "Empenhos da função 12 declarados ao TCE-ES (exceto intra-orçamentários), somados por credor. Os 15 maiores; pessoas físicas (CPF) aparecem numa linha só.",
    { itens: () => linhas.map(c => ({ indicador: "empenho_credor", ano, detalhe: c.credor + " — " + c.credor_nome, q: c.q, valor: brl(c.empenhada),
      observacao: "elemento mais frequente: " + c.elemento + "; fonte " + c.fonte })).concat(nulo(r.tcees_emp_empenhada) ? [] :
      [{ indicador: "tcees_emp_empenhada", ano, q: r.q_tcees_emp, valor: brl(r.tcees_emp_empenhada) }]) }));
  if (!EMPENHOS_COLETADOS) { card.append(avisoEmpenhos()); return card; }
  if (!linhas.length) { card.append(h("p", {}, h("span", { class: "badge nada" }, "Sem dado"), " Nenhum empenho da função 12 de " + nome + " em " + ano + " nos dados do TCE-ES.")); return card; }
  const conf = conferenciaEmpenhos(r);
  if (conf) card.append(conf);
  const total = r.tcees_emp_empenhada || linhas.reduce((s, c) => s + c.empenhada, 0);
  card.append(barrasSubfuncao(linhas.map(c => ({ nome: c.credor_nome, codigo: c.pessoa_fisica ? "CPF" : fmtDoc(c.credor), empenhada: c.empenhada })), total));
  const colunas = [
    { rotulo: "Credor", valor: c => c.credor_nome, render: c => h("span", {},
      botaoDetalhe(c.credor_nome, cod, ano, { tipo: "credor", credor: c.credor, nome: c.credor_nome }),
      contratadas.has(String(c.credor).replace(/\D/g, "")) ? [" ", h("span", { class: "badge aviso", title: "Contratada de obra da Educação neste município (contratações do TCE-ES)" }, "contratada de obra")] : null) },
    { rotulo: "CNPJ", valor: c => c.credor, render: c => c.pessoa_fisica ? "—" : fmtDoc(c.credor) },
    { rotulo: "Empenhado (R$)", num: true, valor: c => c.empenhada, fmt: brl },
    { rotulo: "Pago (R$)", num: true, valor: c => c.paga, fmt: brl },
    { rotulo: "% da Educação", num: true, valor: c => total ? 100 * c.empenhada / total : null, fmt: v => nf(v, 1) + "%" },
    { rotulo: "Empenhos", num: true, valor: c => c.empenhos },
    { rotulo: "Elemento mais frequente", valor: c => c.elemento },
    { rotulo: "Fonte", valor: () => "", render: c => botaoFonte(c.credor_nome + " — " + ano, () => [{ indicador: "empenho_credor", ano,
      detalhe: c.credor + " — " + c.credor_nome, q: c.q, valor: brl(c.empenhada), observacao: "elemento mais frequente: " + c.elemento + "; fonte " + c.fonte }]) },
  ];
  card.append(h("p", { class: "nota" }, "Clique no nome do credor para ver em que ações ele aparece, com que elemento e que fonte — e o que as contratações da Educação desse CNPJ dizem ter comprado."));
  card.append(blocoTabela("credores", colunas, linhas, "credores_" + cod + "_" + ano + ".csv"));
  return card;
}

function cardNivel3Acoes(cod, ano) {
  const nome = ENTES.get(cod).nome;
  const dot = DOTACAO_EA.get(chaveEA(cod, ano)) || [], emp = ACOES_EA.get(chaveEA(cod, ano)) || [];
  const card = h("article", { class: "card largo" }, cabecalho("Nível 3 — em quê: ações do orçamento, orçado × executado, " + nome + ", " + ano,
    "Ação orçamentária com o NOME dado pelo município (\"Construção da EMEF…\", \"Transporte escolar…\"). Dotação atualizada × empenhado, do agregado de despesas do TCE-ES; ações com obra em destaque.",
    { itens: () => dot.map(a => ({ indicador: "dotacao_atualizada", ano, detalhe: "ação " + a.CodigoAcao + " - " + a.NomeAcao, q: a.q, valor: brl(a.PrevisaoAtualizada) }))
      .concat(emp.map(a => ({ indicador: "empenho_acao", ano, detalhe: "ação " + a.CodigoAcao + " - " + a.NomeAcao, q: a.q, valor: brl(a.empenhada) }))) }));
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
    card.append(h("p", { class: "nota" }, "Dotação não coletada: só o executado (empenhos)."));
  }
  linhas = linhas.filter(l => Math.abs(l.atualizada || 0) + Math.abs(l.empenhada || 0) > 0.005).sort((a, b) => (b.atualizada || b.empenhada) - (a.atualizada || a.empenhada));
  if (!linhas.length) { card.append(h("p", {}, h("span", { class: "badge nada" }, "Sem dado"), " Sem ações da função 12 para " + nome + " em " + ano + ".")); return card; }
  const tot = linhas.reduce((s, l) => ({ at: s.at + (l.atualizada || 0), em: s.em + (l.empenhada || 0) }), { at: 0, em: 0 });
  const obras = linhas.filter(l => l.obra), baixa = obras.filter(l => l.atualizada > 0 && l.empenhada / l.atualizada < 0.5);
  card.append(h("p", {}, dot.length ? ["Dotação atualizada ", h("strong", {}, brl(tot.at)), " · "] : null, "empenhado ", h("strong", {}, brl(tot.em)),
    tot.at ? " (" + nf(100 * tot.em / tot.at, 1) + "% executado)." : ".",
    obras.length ? " " + obras.length + " ação(ões) de obra; " + baixa.length + " com menos de metade da dotação empenhada." : ""));
  const execucao = l => nulo(l.atualizada) || !l.atualizada ? null : 100 * l.empenhada / l.atualizada;
  const colunas = [
    { rotulo: "Ação", valor: l => l.codigo + " - " + l.nome, render: l => h("span", {}, h("span", { class: "muted" }, l.codigo + " "),
      botaoDetalhe(l.nome, cod, ano, { tipo: "acao", acao: l.codigo, codigo: l.codigo, nome: l.nome }),
      l.obra ? [" ", h("span", { class: "badge aviso" }, "obra")] : null) },
    { rotulo: "Dotação inicial (R$)", num: true, valor: l => l.inicial, fmt: brl },
    { rotulo: "Dotação atualizada (R$)", num: true, valor: l => l.atualizada, fmt: brl },
    { rotulo: "Empenhado (R$)", num: true, valor: l => l.empenhada, fmt: brl },
    { rotulo: "Pago (R$)", num: true, valor: l => l.paga, fmt: brl },
    { rotulo: "Executado", num: true, valor: execucao, render: l => { const v = execucao(l); if (nulo(v)) return "—";
      return h("span", { class: "mini-exec" }, h("span", { class: "trilho" }, h("span", { class: "fill", style: "width:" + Math.min(100, Math.max(0, v)) + "%" })), " " + nf(v, 0) + "%"); } },
  ];
  card.append(h("p", { class: "nota" }, "Clique no nome da ação para ver quem recebeu, com que elemento e que fonte — e o que as contratações dizem ter comprado."));
  card.append(tabelaExpansivel(colunas, linhas, "Ações da Educação — " + nome + ", " + ano,
    { inicio: 12, classeLinha: l => l.obra && execucao(l) !== null && execucao(l) < 50 ? "atencao" : null,
      rodape: ["Total (" + linhas.length + " ações)", "", brl(tot.at), brl(tot.em), "", ""] }));
  card.append(botaoCSV("acoes_" + cod + "_" + ano + ".csv", colunas, linhas));
  return card;
}

function cardNivel3Fontes(cod, ano) {
  const nome = ENTES.get(cod).nome;
  const linhas = (FONTES_DET_EA.get(chaveEA(cod, ano)) || []).slice().sort((a, b) => b.empenhada - a.empenhada);
  const card = h("article", { class: "card" }, cabecalho("Nível 3 — com que dinheiro: fonte e detalhamento, " + ano,
    "Fonte de recursos com o detalhamento que o município informa ao TCE-ES (convênio, programa estadual, FUNPAES…).",
    { itens: () => linhas.slice(0, 30).map(f => ({ indicador: "empenho_fonte", ano, detalhe: "fonte " + f.CodigoFonteReduzida + ", detalhamento " + f.CodigoDetalhamento + " (" + f.NomeDetalhamento + ")", q: f.q, valor: brl(f.empenhada) })) }));
  if (!EMPENHOS_COLETADOS) { card.append(avisoEmpenhos()); return card; }
  if (!linhas.length) { card.append(h("p", {}, h("span", { class: "badge nada" }, "Sem dado"))); return card; }
  const total = linhas.reduce((s, f) => s + f.empenhada, 0);
  const colunas = [
    { rotulo: "Fonte", valor: f => f.CodigoFonteReduzida + " " + f.NomeFonteReduzida, render: f => h("span", {}, h("span", { class: "muted" }, f.CodigoFonteReduzida + " "), f.NomeFonteReduzida) },
    { rotulo: "Detalhamento", valor: f => f.CodigoDetalhamento + " " + f.NomeDetalhamento, render: f => h("span", {}, h("span", { class: "muted" }, f.CodigoDetalhamento + " "), f.NomeDetalhamento) },
    { rotulo: "Empenhado (R$)", num: true, valor: f => f.empenhada, fmt: brl },
    { rotulo: "%", num: true, valor: f => total ? 100 * f.empenhada / total : null, fmt: v => nf(v, 1) + "%" },
  ];
  card.append(tabelaExpansivel(colunas, linhas, "Fontes detalhadas — " + nome + ", " + ano, { inteira: true }));
  card.append(botaoCSV("fontes_detalhadas_" + cod + "_" + ano + ".csv", colunas, linhas));
  return card;
}

function cardNivel3Conselhos(cod, ano) {
  const nome = ENTES.get(cod).nome;
  const linhas = (CONSELHOS_EA.get(chaveEA(cod, ano)) || []).slice().sort((a, b) => b.empenhada - a.empenhada);
  const card = h("article", { class: "card" }, cabecalho("Nível 3 — para qual escola: repasses do município a conselhos escolares, " + ano,
    "Dinheiro MUNICIPAL entregue à escola (programas locais de autonomia financeira), identificado pelo credor do empenho. A escola é ligada ao Censo pelo nome.",
    { itens: () => linhas.map(c => ({ indicador: "repasse_conselho_escolar", ano, detalhe: c.credor + " — " + c.credor_nome, q: c.q, valor: brl(c.empenhada) })) }));
  if (!EMPENHOS_COLETADOS) { card.append(avisoEmpenhos()); return card; }
  if (!linhas.length) { card.append(h("p", {}, h("span", { class: "badge nada" }, "Nenhum"), " Sem empenho a conselho escolar, caixa escolar ou associação de escola em " + ano + ". O município pode não ter programa próprio de repasse às escolas.")); return card; }
  const total = linhas.reduce((s, c) => s + c.empenhada, 0);
  const vinc = c => VINCULO_POR_ORIGEM.get("conselho|" + cod + "|" + c.credor);
  const colunas = [
    { rotulo: "Conselho (credor)", valor: c => c.credor_nome },
    { rotulo: "Escola no Censo", valor: c => { const v = vinc(c); return v && v.co_entidade ? (ESCOLAS.get(v.co_entidade) || {}).nome : ""; },
      render: c => { const v = vinc(c); return v && v.co_entidade ? botaoEscola(v.co_entidade) : h("span", { class: "muted", title: v ? v.metodo : "" }, "não identificada"); } },
    { rotulo: "Empenhado (R$)", num: true, valor: c => c.empenhada, fmt: brl },
    { rotulo: "Pago (R$)", num: true, valor: c => c.paga, fmt: brl },
  ];
  const comEscola = linhas.filter(c => { const v = vinc(c); return v && v.co_entidade; }).length;
  card.append(h("p", {}, h("strong", {}, brl(total)), " a " + linhas.length + " conselho(s)" +
      (linhas.length ? " · " + comEscola + " ligado(s) a uma escola do Censo" : "") + "."),
    tabelaExpansivel(colunas, linhas, "Repasses a conselhos escolares — " + nome + ", " + ano, { inteira: true }),
    botaoCSV("conselhos_" + cod + "_" + ano + ".csv", colunas, linhas));
  return card;
}

function cardNivel3Obras(cod) {
  const nome = ENTES.get(cod).nome;
  const obras = (OBRAS_EDU.get(cod) || []).slice().sort((a, b) => (b.assinatura || "").localeCompare(a.assinatura || ""));
  const card = h("article", { class: "card largo" }, cabecalho("Nível 3 — em que obra: contratos de obra da Educação, " + nome,
    "Todos os contratos com setor beneficiado \"Educação\" declarados ao TCE-ES, com o prédio (bem vinculador), a situação atual e as medições. Retrato da data da coleta.",
    { itens: () => obras.flatMap(itensFonteObra) }));
  if (!obras.length) { card.append(h("p", {}, h("span", { class: "badge nada" }, "Nenhum"), " Sem contrato de obra da Educação declarado ao TCE-ES.")); return card; }
  const valor = obras.reduce((s, o) => s + (o.valor || 0), 0), paradas = obras.filter(obraParada);
  card.append(h("p", {}, h("strong", {}, obras.length + " contrato(s)"), ", " + brl(valor) + ". ",
    paradas.length ? h("span", { class: "flag-abaixo" }, "⚠ " + paradas.length + " paralisado(s) ou com paralisação presumida (" + brlCompacto(paradas.reduce((s, o) => s + (o.valor || 0), 0)) + ").") : "Nenhum paralisado."));
  const vincObra = (o, i) => VINCULO_POR_ORIGEM.get("obra|" + o.chave + "#" + i);
  const lista = h("div", { class: "lista-obras" });
  for (const o of obras) {
    const bens = bensDe(o);
    lista.append(h("details", { class: "obra" + (obraParada(o) ? " parada" : "") },
      h("summary", {}, h("span", { class: "obra-tit" }, String(o.objeto || "(sem objeto)").slice(0, 140)), " ", seloObra(o.situacao),
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
            linkMapa(b.lat, b.lon), v && v.co_entidade ? [" · escola no Censo: ", botaoEscola(v.co_entidade)] : null); })) : "não informado"),
        h("dt", {}, "Documentos"), h("dd", {}, o.url_contrato ? h("a", { href: o.url_contrato, target: "_blank", rel: "noopener noreferrer" }, "contrato") : "—",
          o.url_edital ? [" · ", h("a", { href: o.url_edital, target: "_blank", rel: "noopener noreferrer" }, "edital")] : null)),
      botaoFonte("Obra " + o.contratacao + " — " + nome, () => itensFonteObra(o))));
  }
  card.append(lista);
  const colunas = [
    { rotulo: "Contratação", valor: o => o.contratacao }, { rotulo: "Objeto", valor: o => o.objeto }, { rotulo: "Contratada", valor: o => o.contratado },
    { rotulo: "CNPJ", valor: o => o.cnpj_contratado }, { rotulo: "Valor atual", valor: o => o.valor }, { rotulo: "Situação", valor: o => o.situacao },
    { rotulo: "Assinatura", valor: o => o.assinatura }, { rotulo: "Medições", valor: o => o.medicoes }, { rotulo: "Valor medido", valor: o => o.valor_medido },
    { rotulo: "Última medição", valor: o => o.ultima_medicao }, { rotulo: "Contrato (URL)", valor: o => o.url_contrato },
  ];
  card.append(botaoCSV("obras_" + cod + ".csv", colunas, obras));
  return card;
}

/** Nível 3 — o item comprado: o que as contratações da Educação declaram ao TCE-ES. */
function cardNivel3Itens(cod, ano) {
  const nome = ENTES.get(cod).nome, chave = chaveEA(cod, ano);
  const linhas = (ITENS_EA.get(chave) || []).slice().sort((a, b) => b.valor_total - a.valor_total);
  const resumo = ITENS_RESUMO.get(chave);
  const card = h("article", { class: "card largo" }, cabecalho("Nível 3 — o que foi comprado: itens das contratações da Educação, " + nome + ", " + ano,
    "O item declarado em cada contratação da Educação: descrição, unidade, quantidade, preço unitário e o que já foi medido. " +
    "Cobertura desigual por construção — só entra a linha que a própria fonte liga à Educação (unidade gestora de educação, " +
    "setor beneficiado \"Educação\" ou obra da Educação).",
    { itens: () => itensFonteItem(cod, ano, linhas) }));
  if (!ITENS_COLETADOS) {
    card.append(h("p", {}, h("span", { class: "badge nada" }, "Não coletado"),
      " Os itens das contratações do TCE-ES (~1,1 GB lidos em fluxo) não entraram nesta execução. Para coletar: ",
      h("code", {}, "python -m financiamento.etl.pipeline --fontes tcees"), "."));
    return card;
  }
  if (!linhas.length) {
    // O exercício do item é o do INSTRUMENTO contratual, não o do pagamento.
    const outros = ANOS.filter(a => (ITENS_EA.get(chaveEA(cod, a)) || []).length);
    card.append(h("p", {}, h("span", { class: "badge nada" }, "Sem dado"),
      " Nenhum item com instrumento contratual de " + ano + " em " + nome + ". ",
      outros.length ? h("span", {}, "Este município tem itens em ", h("strong", {}, outros.join(", ")),
        " — o exercício do item é o do instrumento, então um contrato plurianual aparece no ano da assinatura. ") : "",
      "Ausência aqui não é ausência de compra: quem compra pela unidade gestora da prefeitura, sem marcar o setor " +
      "beneficiado, fica fora do recorte. Os empenhos (acima) continuam mostrando o credor, a ação e o elemento."));
    return card;
  }
  // As regras do município-ano inteiro (o resumo), não só as das linhas embutidas.
  const vinculos = resumo && resumo.vinculos ? String(resumo.vinculos).split(",") : [...new Set(linhas.map(i => i.vinculo))];
  card.append(h("div", { class: "kpis" },
    kpi("Itens no recorte", nf(resumo ? resumo.itens : linhas.length),
      (resumo ? nf(resumo.contratacoes) + " contratação(ões) · " + nf(resumo.contratadas) + " contratada(s)" : "")),
    kpi("Valor contratado", brlCompacto(resumo ? resumo.valor_contratado : linhas.reduce((s, i) => s + (i.valor_total || 0), 0)),
      "soma de \"ValorTotalItemContratado\""),
    kpi("Medido", resumo && resumo.valor_medido ? brlCompacto(resumo.valor_medido) : "sem medição",
      "o que a fonte registra como medido nesses itens", { nd: !(resumo && resumo.valor_medido) })));
  card.append(h("div", { class: "callout" }, h("strong", {}, "Como estas linhas entraram: "),
    vinculos.map(v => VINCULO_ITEM[v] || v).join("; ") + ". " +
    "O CNPJ da contratada não é usado como regra — a empresa que vende à educação também vende ao resto da prefeitura, " +
    "e usar o CNPJ traria quase metade dos itens de todo o Estado como se fossem da educação."));
  card.append(tabelaExpansivel(COLUNAS_ITEM_DETALHE, linhas, "Itens contratados — " + nome + ", " + ano, { inteira: true }));
  card.append(botaoCSV("itens_" + cod + "_" + ano + ".csv", COLUNAS_ITEM_DETALHE, linhas));
  if (resumo && resumo.itens > linhas.length) {
    card.append(h("p", { class: "nota" }, "O painel embute os " + linhas.length + " maiores itens de cada município-ano; " +
      "os " + nf(resumo.itens) + " deste exercício, com a descrição por extenso, estão em ",
      h("code", {}, "dados/processado/tcees_itens.csv"), "."));
  }
  return card;
}

function cardNivel3Limites(cod) {
  const nome = ENTES.get(cod).nome;
  const portal = ((D.dados_manuais || {}).portais || []).find(p => p.cod_ibge === cod && p.verificado);
  const temItens = ITENS_COLETADOS && (ITENS_EA.get(chaveEA(cod, estado.ano)) || []).length > 0;
  const card = h("article", { class: "card largo nivel3" }, cabecalho("Nível 3 — o que ainda não chega ao painel",
    "O Nível 3 acima vem dos dados abertos do TCE-ES (declaratórios). O que continua fora do alcance automatizável:"));
  card.append(h("ul", { class: "lista" },
    h("li", {}, h("strong", {}, "Pessoal por escola: "), "a folha é a maior parte da despesa, mas o vínculo do servidor no TCE-ES não traz a lotação — não há como atribuir salário a uma escola."),
    h("li", {}, h("strong", {}, "O que cada escola fez com o PDDE: "), "a unidade executora presta contas ao FNDE, fora da contabilidade municipal e sem dado aberto por item."),
    h("li", {}, h("strong", {}, "Nota fiscal: "), "número, data e emitente da nota não estão em dado aberto do TCE-ES — estão no portal da transparência do município."),
    h("li", {}, h("strong", {}, "Item comprado: "), temItens
      ? "entrou no painel pelas contratações do TCE-ES (card acima), mas só onde a fonte liga a contratação à Educação; a cobertura é parcial e está no rodapé."
      : "as contratações do TCE-ES trazem o item, mas nenhuma contratação de " + nome + " em " + estado.ano +
        " está ligada à Educação na fonte — aqui ele continua fora."),
    h("li", {}, h("strong", {}, "Empenho ↔ contrato: "), "o empenho do TCE-ES não traz o número do contrato. O painel cruza os dois por CNPJ e município, o que é indício, não identidade."),
    h("li", {}, h("strong", {}, "Portal da transparência de " + nome + ": "),
      portal ? h("span", {}, h("a", { href: portal.url, target: "_blank", rel: "noopener noreferrer" }, portal.url),
        " · conferido em " + dataBR(portal.verificado_em),
        portal.api ? h("div", { class: "nota" }, "API documentada e aberta: ",
          h("a", { href: portal.api, target: "_blank", rel: "noopener noreferrer" }, portal.api),
          portal.observacao ? " — " + portal.observacao : "",
          ". O pipeline não a consulta: é caminho para quem for buscar nota e item à mão.") : null)
        : h("span", {}, "não cadastrado — registre o endereço conferido em ", h("code", {}, "dados_manuais.yaml → nivel3.portais_transparencia"), "."))));
  return card;
}
