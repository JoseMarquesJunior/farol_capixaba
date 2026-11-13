"use strict";
/* ============================================================================
   Visão "Municípios conectados": a projeção do grafo bipartido. Dois municípios
   se ligam quando compram do mesmo fornecedor; cada fornecedor reparte uma
   unidade de ligação entre os municípios que atende (peso de Newman, 1/(k−1)).
   As comunidades (Louvain) são os mercados regionais que os dados mostram —
   comparados às regiões imediatas e intermediárias do IBGE.
   Recorte FIXO: 2021–2025, empresas e terceiro setor, todas as origens.
   ========================================================================== */
const MV = { grafo: null, cartao: null, P: null, por: null };
const LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
const letraCom = c => c < 0 ? "—" : LETRAS[c] || String(c + 1);
const FILTRO_PROJECAO = () => ({ mercado: estado.mercado, ano: null, fonte: null, tipos: new Set(META.tipos_padrao) });

function corCom(c, cores) { return c < 0 ? null : c < 3 ? cores.com[c] : cores.comOutra; }

function filtrosMunicipios() {
  const base = { ano: null, fonte: null, tipos: new Set(META.tipos_padrao) };
  return [campo("Mercado", seletorMercado(estado.mercado, v => ajustar({ mercado: v }), base))];
}
function recorteMunicipios() {
  return [h("strong", {}, ROTULO_MERCADO(estado.mercado)), " · ", h("strong", {}, ANOS[0] + "–" + ANOS[ANOS.length - 1]),
    " · empresas e terceiro setor · todas as origens ", h("span", { class: "muted" }, "(recorte fixo das comunidades)")];
}
function recorteCurtoMunicipios() { return ROTULO_MERCADO(estado.mercado) + " · comunidades"; }

function paresDe(P) {
  const por = MUN.map(() => []);
  for (const [a, b, w, n] of P.pares) { por[a].push({ o: b, w, n }); por[b].push({ o: a, w, n }); }
  for (const l of por) l.sort((x, y) => y.w - x.w || y.n - x.n);
  return por;
}
function leituraAri(v) {
  if (v === null || v === undefined) return "não dá para comparar";
  return v >= 0.6 ? "coincidem bastante" : v >= 0.3 ? "coincidem em parte" : v >= 0.1 ? "pouco têm a ver" : "não têm relação";
}
function fraseMunicipios(P) {
  const onde = estado.mercado === "todos" ? "Somando todos os mercados" : "Em " + ROTULO_MERCADO(estado.mercado).toLowerCase();
  if (!P.n_comunidades) return onde + ", os municípios quase não dividem fornecedores: não se formam grupos.";
  return onde + ", os municípios se dividem em " + P.n_comunidades + " comunidades de fornecedores"
    + (P.modularidade !== null && P.modularidade >= 0.3 ? ", bem separadas" : ", que se sobrepõem bastante")
    + ". Elas " + leituraAri(P.ari_intermediaria) + " com as regiões intermediárias do IBGE"
    + (P.ari_intermediaria === null ? "" : " (índice " + nf(P.ari_intermediaria, 2) + ", em que 1 seria igual)") + ".";
}

function renderMunicipios(main) {
  guardarVista(MV.chaveVista, MV.grafo);
  const P = DADOS.projecoes[estado.mercado];
  MV.P = P; MV.por = paresDe(P);
  const c = coresGrafo();
  main.append(botaoIrParaFigura(() => MV.grafo),
    h("section", { class: "cab-visao compacta" }, h("h2", {}, "Municípios ligados por fornecedores em comum"), h("p", { class: "frase" }, fraseMunicipios(P))));
  const cartao = cartaoGrafo({
    id: "card-mapa-comunidades",
    ferramentas: [
      campoBuscaRede(MUN.map(m => ({ texto: m.nome, sub: "comunidade " + letraCom(P.comunidade[IDX_MUN.get(m.cod)]) + " · " + m.imediata, sel: "m:" + m.cod })), "Buscar município", "Nome do município…"),
      campo("Ligações por município", seletorSimples(estado.lig, [[1, "a mais forte"], [2, "as 2 mais fortes"], [3, "as 3 mais fortes"], [5, "as 5 mais fortes"], [8, "as 8 mais fortes"]], v => ajustar({ lig: +v }))),
      alternador("Contorno do IBGE", estado.contorno, [["intermediaria", "Intermediárias", "As 4 regiões intermediárias"], ["imediata", "Imediatas", "As 8 regiões imediatas"], ["nenhum", "Nenhum"]], v => ajustar({ contorno: v })),
      h("span", { class: "espaco" }),
      botaoFonte(null, () => ["comunidades de fornecedores", qEmpenhos({ ano: null }), [
        "Para cada fornecedor (raiz do CNPJ; empresas, cooperativas, associações e fundações), liste os municípios com empenho positivo no mercado entre " + ANOS[0] + " e " + ANOS[ANOS.length - 1] + ".",
        "Para cada par de municípios atendidos por um mesmo fornecedor, some 1/(k−1).",
        "Rode Louvain (networkx.community.louvain_communities, resolução " + META.resolucao + ", seed " + META.semente + ") no grafo ponderado.",
        "Compare com a região do IBGE de cada município (índice de Rand ajustado e informação mútua normalizada, só nos municípios com ligação)."],
        "Regiões e malha: IBGE (" + consultasDe(META.q_ibge).map(x => x.descricao).join("; ") + ")."]),
    ],
    legenda: legendaComunidades(P, c),
    notas: h("details", { class: "tab notas-figura" }, h("summary", {}, "Como as comunidades foram achadas"),
      h("p", { class: "nota" }, "Peso da ligação entre dois municípios = soma, sobre os fornecedores que os dois têm em comum, de 1/(k−1), onde k é o número de municípios que o fornecedor atende (Newman, 2001). "
        + "Um fornecedor de 60 municípios quase não liga ninguém; dois municípios que dividem fornecedores locais ficam muito ligados. Comunidades: Louvain (Blondel et al., 2008), resolução " + nf(META.resolucao, 1) + ", semente " + META.semente + " — a mesma divisão a cada execução. "
        + "Só as três maiores comunidades recebem cor; as demais ficam em cinza e se distinguem pela letra. A cor de cada município é a da sua comunidade; o contorno escuro, a divisa das regiões do IBGE.")),
  });
  MV.cartao = cartao;
  main.append(cartao.card);
  MV.grafo = new Grafo(cartao.tela, {
    descricao: "Mapa das comunidades de fornecedores: " + P.n_comunidades + " comunidades nos 78 municípios. As tabelas abaixo trazem os mesmos dados.",
    aoPassar: dicaMunicipios, aoClicar: n => irPara({ sel: n ? n.id : null }), letras: true, zoomRotuloMunicipio: 1.6,
  });
  cartao.tela.append(cartao.faixa);
  MV.grafo.definir(dadosGrafoMunicipios(P, c));
  MV.chaveVista = "m";
  restaurarVista(MV.chaveVista, MV.grafo);
  main.append(cardComunidades(P, c), cardContingencia(P), cardPares(P), cardPontes(P));
  selecionarMunicipios(estado.sel, true);
}

function dadosGrafoMunicipios(P, c, extraDe) {
  const nos = MUN.map((m, i) => {
    const com = P.comunidade[i], cor = corCom(com, c);
    return { id: "m:" + m.cod, x: m.x, y: m.y, r: 5, forma: cor ? "q" : "anel", cor: cor || c.ink2, rotulo: m.nome, letraNo: com >= 0 ? letraCom(com) : null, i, tipo: "m" };
  });
  const usados = new Set(), arestas = [];
  const maxW = Math.max(1e-9, ...P.pares.map(p => p[2]));
  const ligar = (a, x) => {
    const ch = Math.min(a, x.o) + "-" + Math.max(a, x.o);
    if (usados.has(ch)) return;
    usados.add(ch);
    arestas.push({ a, b: x.o, w: 0.6 + 4.5 * Math.sqrt(x.w / maxW), cor: c.ink, alfa: 0.45, corRealce: c.ink });
  };
  MV.por.forEach((lista, a) => lista.slice(0, estado.lig).forEach(x => ligar(a, x)));
  // O selecionado ganha as suas 10 ligações mais fortes, além das do recorte.
  if (extraDe !== undefined) MV.por[extraDe].slice(0, 10).forEach(x => ligar(extraDe, x));
  const fundo = fundoMapa(i => { const cor = corCom(P.comunidade[i], c); return cor ? { cor, alfa: 0.32 } : { cor: c.mapa, alfa: 1 }; },
    estado.contorno === "nenhum" ? [] : fronteirasProjetadas(estado.contorno));
  return { nos, arestas, fundo };
}
function legendaComunidades(P, c) {
  const tamanhos = new Map();
  P.comunidade.forEach(x => tamanhos.set(x, (tamanhos.get(x) || 0) + 1));
  const ids = [...tamanhos.keys()].filter(x => x >= 0).sort((a, b) => a - b);
  const quad = cor => svgRaiz({ viewBox: "0 0 14 14", width: "14", height: "14", "aria-hidden": "true" }, cor ? svgEl("rect", { x: 1, y: 1, width: 12, height: 12, fill: cor }) : svgEl("rect", { x: 2, y: 2, width: 10, height: 10, fill: "none", stroke: c.ink2, "stroke-width": 2 }));
  return h("div", { class: "rede-legenda", role: "note", "aria-label": "Legenda" },
    ids.map(x => h("span", {}, quad(corCom(x, c)), h("strong", {}, letraCom(x)), " " + tamanhos.get(x) + " municípios")),
    tamanhos.get(-1) ? h("span", {}, quad(null), "sem fornecedor em comum (" + tamanhos.get(-1) + ")") : null,
    estado.contorno === "nenhum" ? null : h("span", {}, svgRaiz({ viewBox: "0 0 22 12", width: "22", height: "12", "aria-hidden": "true" }, svgEl("line", { x1: 1, y1: 6, x2: 21, y2: 6, stroke: c.ink, "stroke-width": 2.5 })),
      "divisa das regiões " + (estado.contorno === "imediata" ? "imediatas" : "intermediárias") + " do IBGE"));
}
function dicaMunicipios(n) {
  const P = MV.P, com = P.comunidade[n.i], top = MV.por[n.i][0];
  return ["Comunidade " + letraCom(com), n.rotulo, top ? "mais ligado a " + nomeMun(top.o) + " (" + top.n + " fornecedores em comum)" : "sem fornecedor em comum"];
}

function selecionarMunicipios(sel, primeiraVez) {
  if (!MV.grafo) return;
  const i = sel && sel.startsWith("m:") ? IDX_MUN.get(+sel.slice(2)) : undefined;
  MV.grafo.definir(dadosGrafoMunicipios(MV.P, coresGrafo(), i), true);
  MV.grafo.selecionar(i === undefined ? null : sel, !primeiraVez || i !== undefined);
  const lado = limpar(MV.cartao.lado);
  if (i === undefined) { lado.append(ladoInicialMunicipios()); mostrarFaixa(MV.cartao, null); return; }
  lado.append(ladoMunicipioProj(i));
  const com = MV.P.comunidade[i], top = MV.por[i][0];
  const det = "comunidade " + letraCom(com) + (top ? " · mais ligado a " + nomeMun(top.o) : "");
  mostrarFaixa(MV.cartao, MUN[i].nome, det);
  if (!primeiraVez) anunciar("Selecionado: " + MUN[i].nome + ", " + det + ".");
}
function ladoInicialMunicipios() {
  const P = MV.P;
  const fortes = P.pares.slice().sort((a, b) => b[2] - a[2]).slice(0, 5);
  const isolados = P.comunidade.filter(x => x < 0).length;
  return h("div", {}, h("h3", {}, "Visão geral do mercado"),
    resumoLado([
      ["Comunidades", nf(P.n_comunidades), isolados ? isolados + " município(s) sem fornecedor em comum" : "todos dividem fornecedores com algum outro"],
      ["Nitidez da divisão", P.modularidade === null ? "—" : nf(P.modularidade, 2), "modularidade, de 0 a 1; acima de 0,3 é nítida"],
      ["Coincidência com as regiões intermediárias", P.ari_intermediaria === null ? "—" : nf(P.ari_intermediaria, 2), leituraAri(P.ari_intermediaria) + " · imediatas: " + (P.ari_imediata === null ? "—" : nf(P.ari_imediata, 2))],
    ]),
    fortes.length ? [h("h4", {}, "Pares mais ligados"), h("ol", { class: "lista-sel" }, fortes.map(([a, b, w, n]) => h("li", {},
      linkPara({ sel: "m:" + MUN[a].cod }, nomeMun(a)), " e ", linkPara({ sel: "m:" + MUN[b].cod }, nomeMun(b)),
      h("span", { class: "muted small" }, " · " + n + " fornecedores em comum"))))] : null,
    listaPerguntas());
}
function fornecedoresEmComum(a, b) {
  const ag = agregar(FILTRO_PROJECAO());
  const da = ag.porMun.get(a), db = ag.porMun.get(b);
  if (!da || !db) return [];
  const em = new Map(db.ligs.filter(l => l.emp > 0.005).map(l => [l.f, l.emp]));
  return da.ligs.filter(l => l.emp > 0.005 && em.has(l.f)).map(l => ({ f: l.f, a: l.emp, b: em.get(l.f), k: ag.porForn.get(l.f).k }))
    .sort((x, y) => x.k - y.k || (y.a + y.b) - (x.a + x.b));
}
function ladoMunicipioProj(i) {
  const P = MV.P, M = MUN[i], com = P.comunidade[i], c = coresGrafo();
  const membros = MUN.map((_, j) => j).filter(j => j !== i && P.comunidade[j] === com && com >= 0);
  const corpo = h("div", {}, h("p", { class: "voltar-lado" }, linkPara({ sel: null }, "← Visão geral")), h("h3", {}, M.nome),
    h("p", {}, h("span", { class: "chip-com", style: corCom(com, c) ? "--cor:" + corCom(com, c) : null }, "Comunidade " + letraCom(com)),
      h("span", { class: "small muted" }, " · região imediata " + M.imediata + " · intermediária " + M.intermediaria)));
  if (com >= 0) corpo.append(h("details", { class: "tab" }, h("summary", {}, "Os outros " + membros.length + " municípios da comunidade " + letraCom(com)),
    h("p", { class: "small" }, membros.map(nomeMun).join(", ") + ".")));
  const lista = MV.por[i].slice(0, 12);
  if (!lista.length) corpo.append(h("p", { class: "callout" }, "Nenhum fornecedor de " + M.nome + " neste mercado atende outro município."));
  else {
    corpo.append(h("h4", {}, "Com quem mais divide fornecedores"), h("p", { class: "nota" }, "Abra um par para ver quais empresas os dois têm em comum."));
    corpo.append(h("div", { class: "pares-lista" }, lista.map(x => {
      const det = h("details", { class: "par" }, h("summary", {},
        h("span", { class: "nome-par" }, nomeMun(x.o), P.comunidade[x.o] === com && com >= 0 ? "" : h("span", { class: "muted small" }, " · comunidade " + letraCom(P.comunidade[x.o]))),
        h("span", { class: "small muted" }, x.n + " em comum · peso " + nf(x.w, 2))));
      det.addEventListener("toggle", () => {
        if (!det.open || det.dataset.cheio) return;
        det.dataset.cheio = "1";
        const comuns = fornecedoresEmComum(i, x.o);
        anexar(det, h("ul", { class: "lista-sel" }, comuns.slice(0, 12).map(q => h("li", {},
          linkPara({ visao: "fornecedores", sel: "f:" + FORN[q.f].raiz }, FORN[q.f].nome),
          h("span", { class: "muted small" }, " · atende " + q.k + " · " + brlCompacto(q.a) + " aqui, " + brlCompacto(q.b) + " lá")))),
          comuns.length > 12 ? h("p", { class: "nota" }, "e mais " + (comuns.length - 12) + ". Os de menor alcance primeiro: são os que mais pesam na ligação.") : null);
      });
      return det;
    })));
  }
  corpo.append(h("div", { class: "acoes-lado" }, linkPara({ visao: "fornecedores", sel: "m:" + M.cod }, "Fornecedores de " + M.nome + " na rede ›")));
  return corpo;
}

/* ------------------------------------------------------------ cartões */
function cardComunidades(P, c) {
  const ag = agregar(FILTRO_PROJECAO());
  const grupos = new Map();
  P.comunidade.forEach((x, i) => { if (x >= 0) { if (!grupos.has(x)) grupos.set(x, []); grupos.get(x).push(i); } });
  const itens = [...grupos.entries()].sort((a, b) => a[0] - b[0]).map(([x, membros]) => {
    const dentro = new Set(membros);
    const forn = [...ag.porForn.values()].map(f => ({ f: f.f, n: f.ligs.filter(l => l.emp > 0.005 && dentro.has(l.m)).length, k: f.k,
      v: f.ligs.filter(l => dentro.has(l.m)).reduce((s, l) => s + l.emp, 0) })).filter(q => q.n >= 2).sort((a, b) => b.n - a.n || b.v - a.v).slice(0, 5);
    const regioes = Object.entries(membros.reduce((o, i) => (o[MUN[i].imediata] = (o[MUN[i].imediata] || 0) + 1, o), {})).sort((a, b) => b[1] - a[1]);
    return h("div", { class: "comunidade" },
      h("h4", {}, h("span", { class: "chip-com", style: corCom(x, c) ? "--cor:" + corCom(x, c) : null }, "Comunidade " + letraCom(x)), " " + membros.length + " municípios"),
      h("p", { class: "small" }, membros.map(nomeMun).sort((a, b) => a.localeCompare(b, "pt-BR")).join(", ") + "."),
      h("p", { class: "small muted" }, "Regiões imediatas: " + regioes.map(([r, n]) => r + " (" + n + ")").join("; ") + "."),
      forn.length ? h("p", { class: "small" }, "Quem mais costura o grupo: ", forn.map((q, j) => [j ? "; " : "",
        linkPara({ visao: "fornecedores", sel: "f:" + FORN[q.f].raiz }, FORN[q.f].nome),
        " (" + q.n + " dos " + membros.length + (q.k > q.n ? ", e mais " + (q.k - q.n) + " fora" : "") + ")"])) : null);
  });
  return h("article", { class: "card", id: "card-comunidades" },
    h("header", {}, h("div", { class: "cab-card" }, h("div", {}, h("h3", {}, "As comunidades, uma a uma"),
      h("p", { class: "simples" }, "Quem está em cada grupo, de que regiões do IBGE vêm e quais fornecedores atendem mais municípios do grupo.")))),
    itens.length ? h("div", { class: "grade-comunidades" }, itens) : h("p", { class: "muted" }, "Neste mercado não há fornecedores em comum suficientes para formar grupos."));
}
function contingencia(P, campo) {
  const regioes = [...new Set(MUN.map(m => m[campo]))].sort((a, b) => a.localeCompare(b, "pt-BR"));
  const coms = [...new Set(P.comunidade)].sort((a, b) => a - b);
  const linhas = coms.map(x => {
    const l = { com: x, rot: x < 0 ? "sem fornecedor em comum" : "Comunidade " + letraCom(x), total: 0 };
    regioes.forEach(r => { l[r] = 0; });
    P.comunidade.forEach((y, i) => { if (y === x) { l[MUN[i][campo]]++; l.total++; } });
    return l;
  });
  const colunas = [{ rotulo: "Comunidade", valor: l => l.rot }].concat(regioes.map(r => ({ rotulo: r, valor: l => l[r], num: true, render: l => l[r] ? h("span", { class: l[r] === Math.max(...linhas.map(z => z[r])) ? "forte" : null }, nf(l[r])) : h("span", { class: "muted" }, "·") })),
    [{ rotulo: "Total", valor: l => l.total, num: true }]);
  return { colunas, linhas };
}
function cardContingencia(P) {
  const a = contingencia(P, "intermediaria"), b = contingencia(P, "imediata");
  return h("article", { class: "card", id: "card-contingencia" },
    h("header", {}, h("div", { class: "cab-card" }, h("div", {}, h("h3", {}, "Comunidades × regiões do IBGE"),
      h("p", { class: "simples" }, "Quantos municípios de cada comunidade estão em cada região. Uma comunidade que cabe numa coluna só é um mercado que segue a região; espalhada, é um mercado que atravessa as divisas.")))),
    h("h4", {}, "Regiões intermediárias"), tabela(a.colunas, a.linhas, "Comunidades por região intermediária", { busca: false, inicio: 0, csv: "comunidades_intermediarias.csv" }),
    h("details", { class: "tab" }, h("summary", {}, "Regiões imediatas (8)"), tabela(b.colunas, b.linhas, "Comunidades por região imediata", { busca: false, inicio: 0, csv: "comunidades_imediatas.csv" })));
}
function cardPares(P) {
  const linhas = P.pares.map(([a, b, w, n]) => ({ a, b, A: nomeMun(a), B: nomeMun(b), w, n, mesmaCom: P.comunidade[a] >= 0 && P.comunidade[a] === P.comunidade[b],
    mesmaImed: MUN[a].imediata === MUN[b].imediata }));
  return h("article", { class: "card", id: "card-pares" },
    h("header", {}, h("div", { class: "cab-card" }, h("div", {}, h("h3", {}, "Pares de municípios mais ligados — " + ROTULO_MERCADO(estado.mercado)),
      h("p", { class: "simples" }, "Todo par que divide ao menos um fornecedor. O peso favorece fornecedores de pouco alcance: dividir uma empresa que só atende os dois pesa 1; dividir uma de 60 municípios pesa 1/59.")))),
    tabela([
      { rotulo: "Município", valor: l => l.A, render: l => linkPara({ sel: "m:" + MUN[l.a].cod, ir: "figura" }, l.A) },
      { rotulo: "Município ", valor: l => l.B, render: l => linkPara({ sel: "m:" + MUN[l.b].cod, ir: "figura" }, l.B) },
      { rotulo: "Peso", valor: l => l.w, num: true, fmt: v => nf(v, 2) },
      { rotulo: "Fornecedores em comum", valor: l => l.n, num: true, fmt: nf },
      { rotulo: "Mesma comunidade", valor: l => l.mesmaCom, fmt: v => v ? "sim" : "não" },
      { rotulo: "Mesma região imediata", valor: l => l.mesmaImed, fmt: v => v ? "sim" : "não" },
    ], linhas, "Pares de municípios", { csv: "pares_municipios.csv", xlsx: "pares_municipios.xlsx", recorte: [["Mercado", ROTULO_MERCADO(estado.mercado)], ["Período", ANOS[0] + "–" + ANOS[ANOS.length - 1]]], ordemInicial: { coluna: 2, direcao: "desc" } }));
}
function cardPontes(P) {
  const ag = agregar(FILTRO_PROJECAO());
  const linhas = [...ag.porForn.values()].filter(f => f.k >= 2).map(f => {
    const coms = new Set(f.ligs.filter(l => l.emp > 0.005).map(l => P.comunidade[l.m]).filter(x => x >= 0));
    return { f: f.f, nome: FORN[f.f].nome, k: f.k, nc: coms.size, coms: [...coms].sort((a, b) => a - b).map(letraCom).join(" "), emp: f.emp };
  }).filter(l => l.nc >= 2);
  return h("article", { class: "card", id: "card-pontes" },
    h("header", {}, h("div", { class: "cab-card" }, h("div", {}, h("h3", {}, "Fornecedores que atravessam comunidades"),
      h("p", { class: "simples" }, "Empresas com clientes em mais de um mercado regional. São as de alcance estadual — e as que, numa licitação, mais facilmente concorrem fora da sua região.")))),
    tabela([
      { rotulo: "Fornecedor", valor: l => l.nome, classe: "col-nome", render: l => linkPara({ visao: "fornecedores", sel: "f:" + FORN[l.f].raiz, ir: "figura" }, l.nome) },
      { rotulo: "Municípios", valor: l => l.k, num: true, fmt: nf },
      { rotulo: "Comunidades", valor: l => l.nc, num: true, fmt: nf },
      { rotulo: "Quais", valor: l => l.coms },
      { rotulo: "Empenhado 2021–2025", valor: l => l.emp, num: true, fmt: brl },
    ], linhas, "Fornecedores que atravessam comunidades", { csv: "fornecedores_ponte.csv", ordemInicial: { coluna: 2, direcao: "desc" } }));
}
