"use strict";
/* ============================================================================
   Visão "Receita → aplicação" — de onde vem o recurso da Educação e onde ele é
   aplicado, em três níveis que não se confundem:
     Nível 1  função/subfunção (DCA I-E; e o fluxo fonte → subfunção da MSC)
     Nível 2  natureza econômica (MSC: pessoal, custeio, investimento)
     Nível 3  item específico (credor, ação nomeada, obra, conselho escolar) —
              dos dados abertos do TCE-ES, declaratórios (ver nivel3.js).
   ========================================================================== */

const valorDe = (v, fmt) => nulo(v) ? "sem dado" : (fmt || brl)(v);
const municipioFluxo = () => {
  if (!estado.municipio || ENTES.get(estado.municipio).esfera !== "M") estado.municipio = MUNICIPIOS[0].cod_ibge;
  return estado.municipio;
};

function fluxoFiltros(destino) {
  const selMun = estado.sel.filter(c => ENTES.get(c).esfera === "M");
  const linha = h("div", { class: "linha" },
    campo("Município", seletorEnte("f-mun-fluxo", municipioFluxo(), cod => { estado.municipio = cod; render(); })),
    campo("Exercício", seletorAno("f-ano-fluxo", estado.ano, v => { estado.ano = v; render(); })),
    campo("Comparar lado a lado (até " + MAX_COMPARAR + ")", seletorEnte("f-comp-fluxo", "", cod => { adicionar(cod); render(); },
      { vazio: "Adicionar município…", limpaApos: true })));
  const chips = h("div", { class: "chips", "aria-live": "polite" });
  if (!selMun.length) chips.append(h("span", { class: "dica" }, "Escolha municípios para comparar a estrutura de receita e de gasto lado a lado."));
  selMun.forEach(cod => chips.append(h("span", { class: "chip" }, ENTES.get(cod).nome,
    h("button", { type: "button", "aria-label": "Remover " + ENTES.get(cod).nome, onclick: () => { remover(cod); render(); } }, "×"))));
  destino.append(linha, chips);
}

/* -------------------------------------------------- origem da receita (Fase 1) */
function origemDe(cod, ano) {
  const linhas = ORIGEM.get(chaveEA(cod, ano)) || [];
  return Object.fromEntries(linhas.map(o => [o.categoria, o]));
}

function cardOrigemReceita(cod, ano) {
  const o = origemDe(cod, ano), total = o.total && o.total.valor, nome = ENTES.get(cod).nome;
  const itensFonte = () => ORDEM_ORIGEM.concat(["total"]).filter(c => o[c]).map(c => ({
    indicador: c === "total" ? "receita_a01" : "origem_receita", ano, detalhe: c === "total" ? "ReceitasExcetoIntraOrcamentarias" : (META.origens[c] || {}).rotulo,
    q: o[c].q, valor: valorDe(o[c].valor), observacao: c === "total" ? null : "fonte: " + o[c].fonte + " — " + (META.origens[c] || {}).localizacao }));
  const card = h("article", { class: "card largo" }, cabecalho("De onde vem a receita — " + nome + ", " + ano,
    "Receita realizada no ano (exceto intra-orçamentária), em quatro origens que não se sobrepõem. \"Outras\" é calculada por diferença e fica vazia se faltar qualquer parcela.",
    { itens: itensFonte }));
  if (nulo(total)) { card.append(h("p", {}, h("span", { class: "badge nada" }, "Sem dado"), " Anexo 01 do RREO (6º bimestre) não publicado para " + ano + ".")); return card; }
  const partes = ORDEM_ORIGEM.map(c => ({ rotulo: (META.origens[c] || {}).rotulo || c, valor: o[c] ? o[c].valor : null, slot: SLOT_ORIGEM[c], c }));
  card.append(barra100(partes, brl), legendaSlots(partes.map(p => ({ rotulo: p.rotulo.split(" (")[0], slot: p.slot }))));
  const colunas = [
    { rotulo: "Origem", valor: p => p.rotulo },
    { rotulo: "Valor (R$)", num: true, valor: p => p.valor, fmt: brl },
    { rotulo: "% da receita", num: true, valor: p => nulo(p.valor) ? null : 100 * p.valor / total, fmt: v => nf(v, 1) + "%" },
    { rotulo: "Fonte do número", valor: p => o[p.c] ? o[p.c].fonte : "", render: p => h("span", { class: "nota" }, o[p.c] ? o[p.c].fonte : "—") },
  ];
  card.append(tabela(colunas, partes, "Origem da receita de " + nome + ", " + ano, { inteira: true, rodape: ["Receita total (Anexo 01)", brl(total), "100%", "SICONFI — RREO Anexo 01"] }));
  if (o.outras && o.outras.valor < 0) card.append(h("div", { class: "callout warn" }, "As parcelas somam mais que a receita total: as fontes não fecham entre si para este município. É sinal a investigar."));
  card.append(cruzamentoFnde(cod, ano));
  return card;
}

/** Os repasses do FNDE vistos por três fontes: quem pagou (CGU), o que o município registrou (MSC) e declarou (SIOPE). */
function cruzamentoFnde(cod, ano) {
  const rep = REPASSES.get(chaveEA(cod, ano)) || [], r = LINHA.get(cod + "|" + ano) || {}, s = SIOPE.get(chaveEA(cod, ano)) || {};
  let msc = {};
  try { msc = JSON.parse(r.receita_fnde_msc || "{}"); } catch (e) { msc = {}; }
  const cgu = (prog, destino) => { const x = rep.filter(p => p.programa === prog && (!destino || p.destino === destino)); return x.length ? x.reduce((t, p) => t + p.valor, 0) : null; };
  const linhas = [
    { rotulo: "Salário-educação", cgu: cgu("salario_educacao", "municipio"), msc: msc["550"], siope: s.salario_educacao, prog: "salario_educacao" },
    { rotulo: "PNAE — alimentação escolar", cgu: cgu("pnae", "municipio"), msc: msc["552"], siope: s.pnae, prog: "pnae" },
    { rotulo: "PNATE — transporte escolar", cgu: cgu("pnate", "municipio"), msc: msc["553"], siope: s.pnate, prog: "pnate" },
    { rotulo: "PDDE — pago ao município", cgu: cgu("pdde", "municipio"), msc: msc["551"], siope: s.pdde, prog: "pdde" },
  ];
  const escolas = cgu("pdde", "escolas");
  const fonteLinha = l => botaoFonte(l.rotulo + " — " + ENTES.get(cod).nome + ", " + ano, () => [
    { indicador: "repasse_fnde", ano, detalhe: (META.programas_fnde || {})[l.prog], q: rep.filter(p => p.programa === l.prog).map(p => p.q).join(";"), valor: valorDe(l.cgu) },
    { indicador: "receita_fonte_msc", ano, detalhe: { salario_educacao: "550", pnae: "552", pnate: "553", pdde: "551" }[l.prog], q: r.q_msc, valor: valorDe(l.msc) },
    { indicador: "siope", ano, detalhe: l.prog, q: r.q_siope, valor: valorDe(l.siope) }]);
  const bloco = h("div", { class: "subbloco" }, h("h4", {}, "Repasses do FNDE: três olhares sobre o mesmo dinheiro"),
    h("p", { class: "nota" }, "Pago pela União (CGU, por mês de pagamento) × registrado pelo município na contabilidade (MSC, fontes 550–553) × declarado ao FNDE (SIOPE, receitas adicionais). " +
      "A MSC e o SIOPE incluem os rendimentos de aplicação da conta do programa (o SIOPE diz isso no próprio rótulo); a CGU mostra só o repasse — por isso as duas primeiras costumam ser um pouco maiores. Diferença grande, ou na direção oposta, é sinal."),
    tabela([
      { rotulo: "Programa", valor: l => l.rotulo },
      { rotulo: "Pago (CGU)", num: true, valor: l => l.cgu, fmt: brl },
      { rotulo: "Registrado (MSC)", num: true, valor: l => l.msc, fmt: brl },
      { rotulo: "Declarado (SIOPE)", num: true, valor: l => l.siope, fmt: brl },
      { rotulo: "Fonte", valor: () => "", render: fonteLinha },
    ], linhas, "Repasses do FNDE em três fontes", { inteira: true }));
  if (!nulo(escolas)) bloco.append(h("p", { class: "nota" }, h("strong", {}, "PDDE pago direto às escolas: " + brl(escolas) + ". "),
    "Vai às unidades executoras (caixas escolares), não transita pelo orçamento municipal — por isso não entra na receita do município."));
  const fs = (META.fontes_status || {}).FNDE || {};
  if (fs.meses !== undefined && fs.meses_esperados !== undefined && fs.meses < fs.meses_esperados) {
    bloco.append(h("div", { class: "callout warn" }, "Repasses da CGU carregados para " + fs.meses + " de " + fs.meses_esperados +
      " meses (a CGU limita o volume de downloads; os demais entram numa próxima execução). Exercícios com meses faltando ficam subestimados na coluna \"Pago\"."));
  }
  return bloco;
}

/* ---------------------------------------------------------- fluxo (Sankey) */
function cardFluxo(cod, ano) {
  const r = LINHA.get(cod + "|" + ano) || {}, nome = ENTES.get(cod).nome;
  const arestas = FLUXO.get(chaveEA(cod, ano)) || [];
  const card = h("article", { class: "card largo" }, cabecalho("Fluxo: fonte de recursos → subfunção da Educação — " + nome + ", " + ano,
    "Cada empenho da função 12 carrega a fonte de recursos que o paga (MSC). É a ligação declarada pelo próprio município entre a origem e o destino do dinheiro — não uma estimativa proporcional.",
    { itens: () => [{ indicador: "fluxo_fonte_subfuncao", ano, detalhe: "todas as fontes e subfunções", q: r.q_msc, valor: brl(arestas.reduce((t, a) => t + a.empenhada, 0)) },
                    { indicador: "msc_educacao_empenhada", ano, q: r.q_msc, valor: valorDe(r.msc_empenhada) }] }));
  if (!arestas.length) {
    const motivo = r.fontes_msc === "local" ? "Em " + ano + " o município usava códigos de fonte locais (8 dígitos), anteriores à padronização da STN: não há tradução segura, então o fluxo não é desenhado."
      : r.status_msc && r.status_msc !== "ok" ? "MSC não disponível (" + r.status_msc + ")." : "Sem despesa da função 12 na MSC.";
    card.append(h("p", {}, h("span", { class: "badge nada" }, "Sem fluxo"), " " + motivo));
    return card;
  }
  const grupos = META.grupos_fonte || {};
  const origens = ORDEM_GRUPO.map(g => ({ id: g, rotulo: (grupos[g] || g).replace(/ \(fontes? [^)]*\)/, ""), slot: SLOT_ORIGEM[g] }));
  const subs = [...new Set(arestas.map(a => a.subfuncao))];
  const somaSub = s_ => arestas.filter(a => a.subfuncao === s_).reduce((t, a) => t + a.empenhada, 0);
  const destinos = subs.sort((a, b) => somaSub(b) - somaSub(a)).map(sf => ({ id: sf, rotulo: nomeSubfuncao(sf) }));
  const porGrupo = new Map();
  arestas.forEach(a => { const k = a.grupo + "|" + a.subfuncao; porGrupo.set(k, (porGrupo.get(k) || 0) + a.empenhada); });
  const links = [...porGrupo].map(([k, v]) => ({ de: k.split("|")[0], para: k.split("|")[1], valor: v }));
  card.append(h("div", { class: "grafico-svg" }, sankey({ origens, destinos, arestas: links, formatar: brlCompacto, titulo: "Fluxo fonte → subfunção de " + nome })));
  card.append(legendaSlots(origens.map(o => ({ rotulo: o.rotulo, slot: o.slot }))));
  const conferencia = !nulo(r.msc_empenhada) && !nulo(r.desp_educacao_empenhada)
    ? (Math.abs(r.msc_empenhada - r.desp_educacao_empenhada) <= 1 ? "O total do fluxo (" + brl(r.msc_empenhada) + ") bate ao centavo com a função 12 do DCA."
      : "Atenção: o total da MSC (" + brl(r.msc_empenhada) + ") difere da função 12 do DCA (" + brl(r.desp_educacao_empenhada) + ") em " + brl(r.msc_empenhada - r.desp_educacao_empenhada) + ".") : "";
  card.append(h("p", { class: "nota" }, conferencia + " A fonte 500 junta impostos próprios e transferências de impostos (FPM, ICMS…): a contabilidade não os separa, e dividir seria estimar."));
  const colunas = [
    { rotulo: "Fonte de recursos", valor: a => a.fonte + " — " + ((META.nome_fonte || {})[a.fonte] || "fonte " + a.fonte) },
    { rotulo: "Grupo", valor: a => ((grupos[a.grupo] || a.grupo).split(" (")[0]) },
    { rotulo: "Subfunção", valor: a => a.subfuncao + " — " + nomeSubfuncao(a.subfuncao) },
    { rotulo: "Empenhado (R$)", num: true, valor: a => a.empenhada, fmt: brl },
  ];
  const ordenadas = arestas.slice().sort((a, b) => ORDEM_GRUPO.indexOf(a.grupo) - ORDEM_GRUPO.indexOf(b.grupo) || b.empenhada - a.empenhada);
  card.append(blocoTabela("fonte × subfunção", colunas, ordenadas, "fluxo_" + cod + "_" + ano + ".csv"));
  return card;
}

/* ------------------------------------------------ Nível 2: natureza econômica */
function cardNatureza(cod, ano) {
  const r = LINHA.get(cod + "|" + ano) || {}, nome = ENTES.get(cod).nome;
  const linhas = NATUREZA.get(chaveEA(cod, ano)) || [];
  const card = h("article", { class: "card largo" }, cabecalho("Nível 2 — natureza econômica da despesa em Educação — " + nome + ", " + ano,
    "Pessoal, custeio e investimento, pela natureza da despesa de cada empenho da função 12 (MSC). O mapeamento natureza → categoria está documentado em etl/msc.py.",
    { itens: () => [{ indicador: "natureza_economica", ano, detalhe: "categoria pelo grupo e pelo elemento", q: r.q_msc, valor: brl(linhas.reduce((t, l) => t + l.empenhada, 0)) }] }));
  if (!linhas.length) { card.append(h("p", {}, h("span", { class: "badge nada" }, "Sem dado"), " MSC não disponível para " + ano + ".")); return card; }
  const total = linhas.reduce((t, l) => t + l.empenhada, 0);
  const cats = META.categorias_natureza || {}, subcats = META.subcategorias_natureza || {}, elementos = META.elementos || {};
  const porSub = new Map();
  linhas.forEach(l => { const k = l.categoria + "|" + l.subcategoria; const a = porSub.get(k) || { categoria: l.categoria, subcategoria: l.subcategoria, empenhada: 0, liquidada: 0, paga: 0 };
    a.empenhada += l.empenhada; a.liquidada += l.liquidada || 0; a.paga += l.paga || 0; porSub.set(k, a); });
  const maior = Math.max(...[...porSub.values()].map(x => x.empenhada), 0);
  const grade = h("div", {});
  for (const c of ["pessoal", "custeio", "investimento", "outras"]) {
    const itens = [...porSub.values()].filter(x => x.categoria === c).sort((a, b) => b.empenhada - a.empenhada);
    if (!itens.length) continue;
    const somaC = itens.reduce((t, x) => t + x.empenhada, 0);
    grade.append(h("h4", { class: "cat-natureza" }, cats[c] || c, h("span", { class: "muted" }, "  " + brlCompacto(somaC) + " · " + nf(100 * somaC / total, 1) + "%")));
    itens.forEach(x => grade.append(h("div", { class: "barra-sub" },
      h("div", { class: "nome" }, subcats[x.subcategoria] || x.subcategoria),
      h("div", { class: "trilho" }, h("div", { class: "fill", style: "width:" + (maior > 0 ? 100 * x.empenhada / maior : 0) + "%" })),
      h("div", { class: "valor" }, h("b", {}, brlCompacto(x.empenhada)), " ", h("span", { class: "pct" }, nf(100 * x.empenhada / total, 1) + "%")))));
  }
  card.append(grade);
  const colunas = [
    { rotulo: "Categoria", valor: l => cats[l.categoria] || l.categoria },
    { rotulo: "Subcategoria", valor: l => subcats[l.subcategoria] || l.subcategoria },
    { rotulo: "Elemento de despesa", valor: l => l.elemento + " — " + (elementos[l.elemento] || "ver Portaria 163/2001") },
    { rotulo: "Empenhado (R$)", num: true, valor: l => l.empenhada, fmt: brl },
    { rotulo: "Liquidado (R$)", num: true, valor: l => l.liquidada, fmt: brl },
    { rotulo: "Pago (R$)", num: true, valor: l => l.paga, fmt: brl },
  ];
  card.append(blocoTabela("natureza por elemento", colunas, linhas.slice().sort((a, b) => b.empenhada - a.empenhada), "natureza_" + cod + "_" + ano + ".csv",
    { rodape: ["", "", "Total", brl(total), "", ""] }));
  return card;
}

/* --------------------------------------------------- comparação lado a lado */
function cardComparacaoFluxo(ano) {
  const cods = [municipioFluxo(), ...estado.sel.filter(c => ENTES.get(c).esfera === "M" && c !== municipioFluxo())].slice(0, MAX_COMPARAR);
  const card = h("article", { class: "card largo" }, cabecalho("Comparação lado a lado — estrutura da receita e do gasto, " + ano,
    "Participações em %, para comparar municípios de tamanhos diferentes; os valores absolutos estão nas tabelas de cada município.",
    { itens: () => cods.flatMap(c => { const r = LINHA.get(c + "|" + ano) || {}; return [
      { indicador: "origem_receita", ano, detalhe: ENTES.get(c).nome, q: (ORIGEM.get(chaveEA(c, ano)) || []).map(o => o.q).join(";") },
      { indicador: "natureza_economica", ano, detalhe: ENTES.get(c).nome, q: r.q_msc }]; }) }));
  if (cods.length < 2) card.append(h("p", { class: "muted" }, "Adicione municípios no filtro \"Comparar lado a lado\" para ver a estrutura de cada um."));
  const linhasBarra = h("div", { class: "comparacao-barras" });
  for (const c of cods) {
    const o = origemDe(c, ano);
    linhasBarra.append(h("div", { class: "linha-barra" }, h("span", { class: "nome" }, ENTES.get(c).nome),
      barra100(ORDEM_ORIGEM.map(k => ({ rotulo: (META.origens[k] || {}).rotulo || k, valor: o[k] ? o[k].valor : null, slot: SLOT_ORIGEM[k] })), brl)));
  }
  card.append(h("h4", {}, "Origem da receita"), linhasBarra,
    legendaSlots(ORDEM_ORIGEM.map(k => ({ rotulo: ((META.origens[k] || {}).rotulo || k).split(" (")[0], slot: SLOT_ORIGEM[k] }))));
  const share = (parte, total) => nulo(parte) || !total ? null : 100 * parte / total;
  const nat = (c, cat) => { const l = NATUREZA.get(chaveEA(c, ano)) || []; const t = l.reduce((s_, x) => s_ + x.empenhada, 0); return share(l.filter(x => x.categoria === cat).reduce((s_, x) => s_ + x.empenhada, 0), t); };
  const sub = (c, cods_) => { const l = SUB.get(c + "|" + ano) || []; const t = l.reduce((s_, x) => s_ + (x.empenhada || 0), 0); return share(l.filter(x => cods_.includes(x.codigo)).reduce((s_, x) => s_ + x.empenhada, 0), t); };
  const orig = (c, k) => { const o = origemDe(c, ano); return share(o[k] && o[k].valor, o.total && o.total.valor); };
  const def = [
    ["Receita total (R$)", c => (origemDe(c, ano).total || {}).valor, brlCompacto],
    ["…impostos próprios", c => orig(c, "impostos_proprios"), v => nf(v, 1) + "%"],
    ["…FUNDEB", c => orig(c, "fundeb"), v => nf(v, 1) + "%"],
    ["…transferências federais específicas", c => orig(c, "federal_especifica"), v => nf(v, 1) + "%"],
    ["Despesa em Educação (R$)", c => (LINHA.get(c + "|" + ano) || {}).desp_educacao_empenhada, brlCompacto],
    ["…ensino fundamental (12.361)", c => sub(c, ["12.361"]), v => nf(v, 1) + "%"],
    ["…educação infantil (12.365)", c => sub(c, ["12.365"]), v => nf(v, 1) + "%"],
    ["…administração geral (12.122)", c => sub(c, ["12.122"]), v => nf(v, 1) + "%"],
    ["…pessoal", c => nat(c, "pessoal"), v => nf(v, 1) + "%"],
    ["…custeio", c => nat(c, "custeio"), v => nf(v, 1) + "%"],
    ["…investimento", c => nat(c, "investimento"), v => nf(v, 1) + "%"],
    ["% MDE (mín. 25%)", c => (LINHA.get(c + "|" + ano) || {}).mde_aplicado_pct, v => nf(v, 2) + "%"],
    ["% FUNDEB remuneração (mín. 70%)", c => (LINHA.get(c + "|" + ano) || {}).fundeb70_pct, v => nf(v, 2) + "%"],
  ];
  const colunas = [{ rotulo: "Indicador", valor: l => l[0] }].concat(cods.map(c => ({ rotulo: ENTES.get(c).nome, num: true,
    valor: l => l[1](c), render: l => { const v = l[1](c); return nulo(v) ? "sem dado" : l[2](v); } })));
  card.append(tabela(colunas, def, "Comparação lado a lado, " + ano, { inteira: true }),
    botaoCSV("comparacao_fluxo_" + ano + ".csv", colunas, def));
  return card;
}

function renderFluxo(destino) {
  const cod = municipioFluxo(), ano = estado.ano, ente = ENTES.get(cod);
  destino.append(h("div", { class: "ficha-topo" }, h("h2", {}, ente.nome), h("span", { class: "codigo" }, "Código IBGE " + cod + " · exercício " + ano),
    h("button", { type: "button", class: "leve", onclick: () => irPara("municipio") }, "Ficha completa do município →")));
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" },
    cardOrigemReceita(cod, ano), cardFluxo(cod, ano), cardNatureza(cod, ano),
    cardNivel3Credores(cod, ano), cardNivel3Acoes(cod, ano), cardNivel3Fontes(cod, ano), cardNivel3Conselhos(cod, ano),
    cardNivel3Itens(cod, ano), cardNivel3Obras(cod), cardNivel3Limites(cod), cardComparacaoFluxo(ano))));
}
