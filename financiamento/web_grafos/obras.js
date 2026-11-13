"use strict";
/* ============================================================================
   Visão "Obras": contratada × município nas obras da Educação que os municípios
   declararam ao TCE-ES (CidadES). A linha tem o estilo da situação do contrato;
   a contratada com obra parada em dois ou mais municípios leva o anel ⚑ — sinal
   a verificar, não irregularidade por si.
   ========================================================================== */
const OBRAS = (() => {
  const o = DADOS.obras;
  const obj = t => t.linhas.map(l => Object.fromEntries(t.colunas.map((c, i) => [c, l[i]])));
  const contratadas = obj(o.contratadas), contratos = obj(o.contratos);
  return { contratadas, contratos, layout: o.layout, idx: new Map(contratadas.map((c, i) => [c.id, i])) };
})();
const CONTRATADA_DO_FORNECEDOR = new Map(OBRAS.contratadas.map((c, i) => [c.f, i]).filter(([f]) => f !== null && f !== undefined));
const SITUACOES = META.situacoes_obra;
const ROTULO_SIT = Object.fromEntries(SITUACOES.map(s => [s.id, s.rotulo]));
const PARADAS = new Set(["presumida", "paralisada"]);
const PRIORIDADE_SIT = ["paralisada", "presumida", "nao_iniciada", "execucao", "concluida", "nao_identificada"];
const OV = { grafo: null, cartao: null, por: null };

function estiloSit(sit, c) {
  return {
    presumida: { cor: c.sinal, alfa: 0.85, w: 1.8, traco: [6, 3] },
    paralisada: { cor: c.sinal, alfa: 0.95, w: 2.6, traco: null },
    nao_iniciada: { cor: c.neutro, alfa: 0.6, w: 1.2, traco: [2, 3] },
    execucao: { cor: c.exec, alfa: 0.75, w: 1.6, traco: null },
    concluida: { cor: c.neutro, alfa: 0.55, w: 1.2, traco: null },
    nao_identificada: { cor: c.neutro, alfa: 0.5, w: 1, traco: [1, 3] },
  }[sit];
}
function contratosFiltrados() {
  const ok = estado.sit === "todas" ? () => true : estado.sit === "paradas" ? x => PARADAS.has(x.sit) : x => x.sit === estado.sit;
  return OBRAS.contratos.filter(ok);
}
function resumoContratadas(lista) {
  const por = new Map();
  for (const x of lista) {
    let r = por.get(x.c);
    if (!r) { r = { c: x.c, contratos: [], muns: new Set(), munsParadas: new Set(), valor: 0, valorParado: 0 }; por.set(x.c, r); }
    r.contratos.push(x); r.muns.add(x.m); r.valor += x.valor_n || 0;
    if (PARADAS.has(x.sit)) { r.munsParadas.add(x.m); r.valorParado += x.valor_n || 0; }
  }
  for (const r of por.values()) r.sinal = r.munsParadas.size >= 2;
  return por;
}
const rotuloSitFiltro = () => estado.sit === "todas" ? "todas as situações" : estado.sit === "paradas" ? "só as paradas" : ROTULO_SIT[estado.sit].toLowerCase();

function filtrosObras() {
  return [
    campo("Situação do contrato", seletorSimples(estado.sit, [["todas", "Todas"], ["paradas", "Só paradas (presumida ou declarada)"], ...SITUACOES.map(s => [s.id, s.rotulo])], v => ajustar({ sit: v }))),
    campo("Contratada com obra em", seletorSimples(estado.minObras, [[1, "1 município ou mais"], [2, "2 municípios ou mais"], [3, "3 municípios ou mais"]], v => ajustar({ minObras: +v }))),
  ];
}
function recorteObras() {
  return [h("strong", {}, "Obras da Educação declaradas ao TCE-ES"), " · ", h("strong", {}, rotuloSitFiltro()),
    " · contratadas com obra em ", h("strong", {}, estado.minObras + "+ município(s)")];
}
function recorteCurtoObras() { return "Obras · " + rotuloSitFiltro(); }

function fraseObras(contratosVis, visiveis) {
  const todas = resumoContratadas(OBRAS.contratos);
  const sinal = [...todas.values()].filter(r => r.sinal);
  const valorParado = OBRAS.contratos.filter(x => PARADAS.has(x.sit)).reduce((s, x) => s + (x.valor_n || 0), 0);
  const parados = OBRAS.contratos.filter(x => PARADAS.has(x.sit)).length;
  return "Os municípios declararam " + nf(OBRAS.contratos.length) + " contratos de obra da Educação, de " + nf(OBRAS.contratadas.length) + " empresas. "
    + nf(parados) + " estão parados (" + brlCompacto(valorParado) + "), e " + sinal.length + " contratadas têm obra parada em dois ou mais municípios."
    + (contratosVis.length !== OBRAS.contratos.length ? " A figura mostra " + nf(contratosVis.length) + " contratos de " + nf(visiveis.length) + " contratadas." : "");
}

function renderObras(main) {
  guardarVista(OV.chaveVista, OV.grafo);
  const c = coresGrafo();
  const lista = contratosFiltrados(), por = resumoContratadas(lista);
  const visiveis = [...por.values()].filter(r => r.muns.size >= estado.minObras);
  const vis = new Set(visiveis.map(r => r.c));
  const contratosVis = lista.filter(x => vis.has(x.c));
  OV.por = por;
  main.append(botaoIrParaFigura(() => OV.grafo),
    h("section", { class: "cab-visao compacta" }, h("h2", {}, "Quem executa as obras da Educação"), h("p", { class: "frase" }, fraseObras(contratosVis, visiveis))));
  const itensBusca = visiveis.map(r => ({ texto: OBRAS.contratadas[r.c].nome, sub: fmtCnpj(OBRAS.contratadas[r.c].docs.split(";")[0]) + " · " + r.contratos.length + " contrato(s)",
    digitos: OBRAS.contratadas[r.c].docs, sel: "c:" + OBRAS.contratadas[r.c].id })).concat(MUN.map(m => ({ texto: m.nome, sub: "município", sel: "m:" + m.cod })));
  const cartao = cartaoGrafo({
    id: "card-rede-obras",
    ferramentas: [
      campoBuscaRede(itensBusca, "Buscar na figura", "Contratada, CNPJ ou município…"),
      alternador("Disposição", estado.dispObras, [["mapa", "Mapa do ES"], ["forca", "Afinidade"]], v => ajustar({ dispObras: v })),
      h("span", { class: "espaco" }),
      botaoFonte(null, () => ["obras da Educação", META.q_obras, ["Recurso \"Obras e serviços de engenharia\" do TCE-ES: SetorBeneficiado com \"Educação\", município do ES.",
        "Situação = SituacaoObra; valor = valor atual do contrato (ou o inicial, sem atual); medições e aditivos do recurso de instrumentos contratuais.",
        "Contratada = raiz do CNPJ (8 dígitos) do contratado."], null]),
    ],
    legenda: legendaObras(c),
    notas: h("details", { class: "tab notas-figura" }, h("summary", {}, "Sobre a situação dos contratos"),
      h("p", { class: "nota" }, "\"Paralisação presumida\" é classificação do TCE-ES por falta de medição recente — não é declaração do município. \"Paralisada\" e \"interrompida\" são declaradas. Quando um par município–contratada tem vários contratos, a linha mostra a situação mais grave. Tamanho do círculo = valor dos contratos no recorte.")),
  });
  OV.cartao = cartao;
  main.append(cartao.card);
  OV.grafo = new Grafo(cartao.tela, { descricao: "Rede de obras da Educação: " + visiveis.length + " contratadas. As tabelas abaixo trazem os mesmos dados.", aoPassar: dicaObras, aoClicar: n => irPara({ sel: n ? n.id : null }) });
  cartao.tela.append(cartao.faixa);
  OV.grafo.definir(dadosGrafoObras(visiveis, contratosVis, c));
  OV.chaveVista = "o|" + estado.dispObras;
  restaurarVista(OV.chaveVista, OV.grafo);
  if (!visiveis.length) OV.grafo.aviso(h("div", {}, h("p", {}, "Nenhuma contratada neste recorte."), linkPara({ sit: "todas", minObras: 1 }, "Mostrar todas as obras")));
  main.append(cardTabelaContratadas(visiveis), cardTabelaContratos(contratosVis));
  selecionarObras(estado.sel, true);
}
function dadosGrafoObras(visiveis, contratos, c) {
  const L = OBRAS.layout, arr = L[estado.dispObras] || L.mapa;
  const pos = new Map(L.nos.map((ci, i) => [ci, [arr[2 * i], arr[2 * i + 1]]]));
  const mun = estado.dispObras === "forca" && L.forca_municipios ? MUN.map((_, i) => [L.forca_municipios[2 * i], L.forca_municipios[2 * i + 1]]) : MUN.map(m => [m.x, m.y]);
  const nos = MUN.map((m, i) => ({ id: "m:" + m.cod, x: mun[i][0], y: mun[i][1], r: 5, forma: "q", cor: c.municipio, rotulo: m.nome, i, tipo: "m" }));
  const maxV = Math.max(1, ...visiveis.map(r => r.valor));
  const idx = new Map();
  visiveis.slice().sort((a, b) => b.valor - a.valor).forEach((r, j) => {
    const p = pos.get(r.c);
    if (!p) return;
    idx.set(r.c, nos.length);
    nos.push({ id: "c:" + OBRAS.contratadas[r.c].id, x: p[0], y: p[1], r: raioPorValor(r.valor, maxV), forma: "c", cor: c.ink2, marca: r.sinal ? c.sinal : null,
      rotulo: OBRAS.contratadas[r.c].nome, prio: j < 20 ? 10 - j / 4 : 1, ci: r.c, tipo: "c" });
  });
  const pares = new Map();
  for (const x of contratos) {
    const ch = x.m + "-" + x.c, ant = pares.get(ch);
    if (!ant || PRIORIDADE_SIT.indexOf(x.sit) < PRIORIDADE_SIT.indexOf(ant.sit)) pares.set(ch, x);
  }
  const arestas = [];
  for (const x of pares.values()) {
    if (!idx.has(x.c)) continue;
    const e = estiloSit(x.sit, c);
    arestas.push({ a: x.m, b: idx.get(x.c), ...e, corRealce: e.cor });
  }
  return { nos, arestas, fundo: estado.dispObras === "mapa" ? fundoMapa() : null };
}
function legendaObras(c) {
  const linha = (sit) => { const e = estiloSit(sit, c); return svgRaiz({ viewBox: "0 0 26 12", width: "26", height: "12", "aria-hidden": "true" },
    svgEl("line", { x1: 1, y1: 6, x2: 25, y2: 6, stroke: e.cor, "stroke-width": Math.max(1.5, e.w), "stroke-dasharray": e.traco ? e.traco.join(" ") : "none", opacity: Math.max(0.7, e.alfa) })); };
  return h("div", { class: "rede-legenda", role: "note", "aria-label": "Legenda" },
    h("span", {}, svgRaiz({ viewBox: "0 0 14 14", width: "14", height: "14", "aria-hidden": "true" }, svgEl("rect", { x: 2, y: 2, width: 10, height: 10, fill: c.municipio })), "município"),
    h("span", {}, svgRaiz({ viewBox: "0 0 18 18", width: "18", height: "18", "aria-hidden": "true" }, svgEl("circle", { cx: 9, cy: 9, r: 5, fill: c.ink2 }), svgEl("circle", { cx: 9, cy: 9, r: 7.5, fill: "none", stroke: c.sinal, "stroke-width": 2 })), "⚑ contratada com obra parada em 2+ municípios"),
    SITUACOES.map(s => h("span", {}, linha(s.id), s.rotulo)));
}
function dicaObras(n) {
  if (n.tipo === "m") {
    const cs = OBRAS.contratos.filter(x => x.m === n.i);
    return [cs.length + " contrato(s) de obra", n.rotulo + " — município", cs.filter(x => PARADAS.has(x.sit)).length + " parado(s)"];
  }
  const r = OV.por.get(n.ci);
  return [brl(r.valor), OBRAS.contratadas[n.ci].nome, r.contratos.length + " contrato(s) em " + r.muns.size + " município(s)" + (r.munsParadas.size ? " · parada em " + r.munsParadas.size : "")];
}

function selecionarObras(sel, primeiraVez) {
  if (!OV.grafo) return;
  OV.grafo.selecionar(sel, !primeiraVez || !!sel);
  const lado = limpar(OV.cartao.lado);
  if (!sel) { lado.append(ladoInicialObras()); mostrarFaixa(OV.cartao, null); return; }
  if (sel.startsWith("m:")) {
    const i = IDX_MUN.get(+sel.slice(2));
    lado.append(ladoMunicipioObras(i));
    const cs = OBRAS.contratos.filter(x => x.m === i), det = cs.length + " contrato(s) · " + cs.filter(x => PARADAS.has(x.sit)).length + " parado(s)";
    if (MUN[i]) { mostrarFaixa(OV.cartao, MUN[i].nome, det); if (!primeiraVez) anunciar("Selecionado: " + MUN[i].nome + ", " + det + "."); }
  } else if (sel.startsWith("c:")) {
    const ci = OBRAS.idx.get(sel.slice(2));
    lado.append(ladoContratada(ci));
    if (ci !== undefined) {
      const cs = OBRAS.contratos.filter(x => x.c === ci), det = cs.length + " contrato(s) · " + cs.filter(x => PARADAS.has(x.sit)).length + " parado(s)";
      mostrarFaixa(OV.cartao, OBRAS.contratadas[ci].nome, det);
      if (!primeiraVez) anunciar("Selecionado: " + OBRAS.contratadas[ci].nome + ", " + det + ".");
    }
  }
}
function ladoInicialObras() {
  const todas = resumoContratadas(OBRAS.contratos);
  const sinal = [...todas.values()].filter(r => r.sinal);
  const valorParado = OBRAS.contratos.filter(x => PARADAS.has(x.sit)).reduce((s, x) => s + (x.valor_n || 0), 0);
  const top = sinal.sort((a, b) => b.munsParadas.size - a.munsParadas.size || b.valorParado - a.valorParado).slice(0, 6);
  return h("div", {}, h("h3", {}, "Visão geral das obras"),
    resumoLado([
      ["Contratos", nf(OBRAS.contratos.length), "de " + nf(OBRAS.contratadas.length) + " contratadas, em " + new Set(OBRAS.contratos.map(x => x.m)).size + " municípios"],
      ["Contratadas com obra parada em 2+ municípios", nf(sinal.length), ESTADOS.sinal.simbolo + " " + ESTADOS.sinal.rotulo, { classe: "sinal" }],
      ["Valor dos contratos parados", brlCompacto(valorParado), "paralisação presumida pelo TCE-ES ou declarada"],
    ]),
    top.length ? [h("h4", {}, "Obra parada em mais municípios"), h("ol", { class: "lista-sel" }, top.map(r => h("li", {}, linkPara({ sel: "c:" + OBRAS.contratadas[r.c].id }, OBRAS.contratadas[r.c].nome),
      h("span", { class: "muted small" }, " · parada em " + r.munsParadas.size + " · " + brlCompacto(r.valorParado)))))] : null,
    listaPerguntas());
}
function chipSit(sit) {
  return PARADAS.has(sit) ? chipEstado("sinal", ROTULO_SIT[sit]) : h("span", { class: "badge neutro" }, ROTULO_SIT[sit]);
}
function listaContratos(cs, mostrarMunicipio) {
  return h("div", { class: "lista-obras" }, cs.slice().sort((a, b) => PRIORIDADE_SIT.indexOf(a.sit) - PRIORIDADE_SIT.indexOf(b.sit) || (b.valor_n || 0) - (a.valor_n || 0)).map(x =>
    h("details", { class: "obra" + (PARADAS.has(x.sit) ? " parada" : "") },
      h("summary", {}, h("span", { class: "obra-tit" }, mostrarMunicipio ? nomeMun(x.m) : OBRAS.contratadas[x.c].nome, h("span", { class: "muted small" }, " · " + (x.tipo_intervencao || "obra"))),
        chipSit(x.sit), h("span", { class: "obra-valor" }, nulo(x.valor_n) ? "sem valor" : brl(x.valor_n))),
      h("dl", { class: "obra-dl" },
        h("dt", {}, "Objeto"), h("dd", {}, x.objeto || "—"),
        h("dt", {}, mostrarMunicipio ? "Município" : "Contratada"), h("dd", {}, mostrarMunicipio ? linkPara({ sel: "m:" + MUN[x.m].cod }, nomeMun(x.m)) : linkPara({ sel: "c:" + OBRAS.contratadas[x.c].id }, OBRAS.contratadas[x.c].nome)),
        h("dt", {}, "Unidade gestora"), h("dd", {}, x.ug || "—"),
        h("dt", {}, "Assinatura / fim"), h("dd", {}, dataBR(x.assinatura) + " a " + dataBR(x.fim_vigencia)),
        h("dt", {}, "Medido"), h("dd", {}, nulo(x.pct_medido) ? "sem medição no dado aberto" : pct0(x.pct_medido) + (x.ultima_medicao ? " · última medição em " + dataBR(x.ultima_medicao) : "")),
        h("dt", {}, "Aditivos"), h("dd", {}, nulo(x.aditivos) ? "—" : nf(x.aditivos)),
        h("dt", {}, "Situação no TCE-ES"), h("dd", {}, x.situacao || "—"),
        x.url_contrato && /^https?:/.test(x.url_contrato) ? [h("dt", {}, "Contrato"), h("dd", {}, h("a", { href: x.url_contrato, target: "_blank", rel: "noopener" }, "abrir o documento publicado"))] : null),
      botaoFonte(null, () => ["contrato " + (x.chave || ""), x.q, ["No recurso de obras do TCE-ES, procure ChaveInstrumento = " + (x.chave || "—") + "."], null]))));
}
function ladoContratada(ci) {
  if (ci === undefined) return h("p", {}, "Contratada não encontrada.");
  const C = OBRAS.contratadas[ci], todos = OBRAS.contratos.filter(x => x.c === ci);
  const muns = new Set(todos.map(x => x.m)), parados = todos.filter(x => PARADAS.has(x.sit));
  const munsPar = new Set(parados.map(x => x.m));
  const corpo = h("div", {}, h("p", { class: "voltar-lado" }, linkPara({ sel: null }, "← Visão geral")), h("h3", {}, C.nome), h("p", { class: "small muted" }, C.docs.split(";").map(fmtCnpj).join(" · ")),
    /^\d{8}$/.test(C.id) ? h("p", { class: "acao-dossie" }, linkPara({ visao: "empresa", sel: "f:" + C.id }, "Análise profunda ›", { class: "botao-acao" })) : null);
  if (munsPar.size >= 2) corpo.append(h("p", { class: "callout sinal" }, h("strong", {}, ESTADOS.sinal.simbolo + " Obra parada em " + munsPar.size + " municípios: "), [...munsPar].map(nomeMun).join(", ") + ". Sinal a verificar, não irregularidade por si."));
  corpo.append(resumoLado([["Contratos", nf(todos.length), "em " + muns.size + " município(s)"], ["Valor dos contratos", brlCompacto(todos.reduce((s, x) => s + (x.valor_n || 0), 0)), null],
    ["Parados", parados.length ? nf(parados.length) : "nenhum", parados.length ? brlCompacto(parados.reduce((s, x) => s + (x.valor_n || 0), 0)) + " em contratos parados" : null]]));
  if (C.f !== null && C.f !== undefined) {
    const emp = agregar({ mercado: "todos", ano: null, fonte: null, tipos: new Set(TIPOS.map(t => t.id)) }).porForn.get(C.f);
    const empObras = agregar({ mercado: "obras", ano: null, fonte: null, tipos: new Set(TIPOS.map(t => t.id)) }).porForn.get(C.f);
    corpo.append(h("p", { class: "small" }, "Nos empenhos da Educação " + ANOS[0] + "–" + ANOS[ANOS.length - 1] + ": " + (emp ? brl(emp.emp) + " em " + emp.k + " município(s)" : "nada")
      + (empObras ? ", dos quais " + brl(empObras.emp) + " em obras e manutenção de prédios" : "") + ". ",
      linkPara({ visao: "fornecedores", mercado: "obras", sel: "f:" + FORN[C.f].raiz }, "Ver na rede de fornecedores ›")));
  } else corpo.append(h("p", { class: "small muted" }, "Sem empenho da Educação a este CNPJ em " + ANOS[0] + "–" + ANOS[ANOS.length - 1] + " nos dados do TCE-ES (pode ter sido pago por outra função, como Urbanismo)."));
  corpo.append(h("h4", {}, "Contratos"), listaContratos(todos, true));
  return corpo;
}
function ladoMunicipioObras(i) {
  if (i === undefined) return h("p", {}, "Município não encontrado.");
  const cs = OBRAS.contratos.filter(x => x.m === i);
  const corpo = h("div", {}, h("p", { class: "voltar-lado" }, linkPara({ sel: null }, "← Visão geral")), h("h3", {}, MUN[i].nome),
    resumoLado([["Contratos de obra", nf(cs.length), nf(new Set(cs.map(x => x.c)).size) + " contratada(s)"], ["Parados", nf(cs.filter(x => PARADAS.has(x.sit)).length), null]]));
  corpo.append(cs.length ? listaContratos(cs, false) : h("p", { class: "muted" }, "Nenhum contrato de obra da Educação declarado."));
  const ano = ANOS[ANOS.length - 1];
  corpo.append(h("div", { class: "acoes-lado" },
    CONFIG.painel ? h("a", { href: CONFIG.painel + "#v=municipio&ano=" + ano + "&m=" + MUN[i].cod + "&s=obras" }, "Obras no painel de financiamento ›") : null));
  return corpo;
}
function cardTabelaContratadas(visiveis) {
  const linhas = visiveis.map(r => ({ c: r.c, nome: OBRAS.contratadas[r.c].nome, doc: fmtCnpj(OBRAS.contratadas[r.c].docs.split(";")[0]), muns: r.muns.size, n: r.contratos.length,
    valor: r.valor, paradas: r.contratos.filter(x => PARADAS.has(x.sit)).length, munsPar: r.munsParadas.size, sinal: r.sinal }));
  return h("article", { class: "card", id: "card-contratadas" },
    h("header", {}, h("div", { class: "cab-card" }, h("div", {}, h("h3", {}, "Contratadas na figura"),
      h("p", { class: "simples" }, "Linha em âmbar: obra parada em dois ou mais municípios. O nome leva à contratada na figura.")))),
    tabela([
      { rotulo: "Contratada", valor: l => l.nome, classe: "col-nome", render: l => linkPara({ sel: "c:" + OBRAS.contratadas[l.c].id, ir: "figura" }, l.nome) },
      { rotulo: "CNPJ", valor: l => l.doc },
      { rotulo: "Municípios", valor: l => l.muns, num: true, fmt: nf },
      { rotulo: "Contratos", valor: l => l.n, num: true, fmt: nf },
      { rotulo: "Valor", valor: l => l.valor, num: true, fmt: brl },
      { rotulo: "Contratos parados", valor: l => l.paradas, num: true, fmt: nf },
      { rotulo: "Municípios com obra parada", valor: l => l.munsPar, num: true, fmt: nf },
    ], linhas, "Contratadas de obras da Educação", { classeLinha: l => l.sinal ? "l-sinal" : null, csv: "obras_contratadas.csv", xlsx: "obras_contratadas.xlsx",
      recorte: () => [["Situação", rotuloSitFiltro()], ["Obra em ao menos", estado.minObras + " município(s)"]], ordemInicial: { coluna: 6, direcao: "desc" } }));
}
function cardTabelaContratos(cs) {
  const linhas = cs.map(x => ({ ...x, mun: nomeMun(x.m), contratada: OBRAS.contratadas[x.c].nome, rotSit: ROTULO_SIT[x.sit] }));
  return h("article", { class: "card", id: "card-contratos" },
    h("header", {}, h("div", { class: "cab-card" }, h("div", {}, h("h3", {}, "Contratos no recorte")))),
    tabela([
      { rotulo: "Município", valor: l => l.mun },
      { rotulo: "Contratada", valor: l => l.contratada, classe: "col-nome" },
      { rotulo: "Objeto", valor: l => l.objeto, classe: "motivo" },
      { rotulo: "Tipo", valor: l => l.tipo_intervencao },
      { rotulo: "Situação", valor: l => l.rotSit, render: l => chipSit(l.sit) },
      { rotulo: "Valor", valor: l => l.valor_n, num: true, fmt: brl },
      { rotulo: "% medido", valor: l => l.pct_medido, num: true, fmt: v => pct0(v) },
      { rotulo: "Última medição", valor: l => l.ultima_medicao, fmt: dataBR },
    ], linhas, "Contratos de obras da Educação", { classeLinha: l => PARADAS.has(l.sit) ? "l-sinal" : null, csv: "obras_contratos.csv", xlsx: "obras_contratos.xlsx",
      recorte: () => [["Situação", rotuloSitFiltro()]], ordemInicial: { coluna: 5, direcao: "desc" } }));
}
