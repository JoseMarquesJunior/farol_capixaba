"use strict";
/* ============================================================================
   Visão "Fornecedores": o grafo bipartido município × fornecedor.
   Cada quadrado é um município; cada círculo, uma empresa (raiz do CNPJ) que
   recebeu empenhos da Educação de ao menos N municípios no recorte.

   Depois da auditoria de UX (26/10/2026): a figura vem logo abaixo de uma frase
   de resumo — os indicadores foram para o painel lateral, que é o "estado vazio"
   da seleção; a busca e a disposição ficam na barra da figura, não na barra fixa.
   ========================================================================== */
const FV = { grafo: null, ag: null, visiveis: null, cartao: null };

function filtroAtual() { return { mercado: estado.mercado, ano: estado.ano, fonte: estado.fonte, tipos: estado.tipos }; }
function rotuloAno(i) { return i === null ? ANOS[0] + "–" + ANOS[ANOS.length - 1] : String(ANOS[i]); }
function rotuloFonte(i) { return i === null ? "todas as origens" : FONTES[i].rotulo; }

/* ------------------------------------------------------------ controles */
/** Mercado com o valor de cada um no recorte — ajuda a escolher. */
function seletorMercado(valor, aoMudar, filtroBase) {
  const total = id => agregar({ ...filtroBase, mercado: id }).total;
  const s = h("select", { onchange: e => aoMudar(e.target.value) },
    h("option", { value: "todos" }, "Todos os mercados — " + brlCompacto(total("todos"))),
    MERCADOS.map(m => [m, total(m.id)]).sort((a, b) => b[1] - a[1]).map(([m, v]) => h("option", { value: m.id }, m.rotulo + " — " + brlCompacto(v))));
  s.value = valor;
  return s;
}
function seletorAno() {
  const s = h("select", { onchange: e => ajustar({ ano: e.target.value === "" ? null : +e.target.value }) },
    h("option", { value: "" }, ANOS[0] + "–" + ANOS[ANOS.length - 1]), ANOS.map((a, i) => h("option", { value: String(i) }, String(a))));
  s.value = estado.ano === null ? "" : String(estado.ano);
  return s;
}
function seletorFonte() {
  const s = h("select", { onchange: e => ajustar({ fonte: e.target.value === "" ? null : +e.target.value }) },
    h("option", { value: "" }, "Todas"), FONTES.map((f, i) => h("option", { value: String(i) }, f.rotulo)));
  s.value = estado.fonte === null ? "" : String(estado.fonte);
  return s;
}
function seletorSimples(valor, opcoes, aoMudar) {
  const s = h("select", { onchange: e => aoMudar(e.target.value) }, opcoes.map(([v, r]) => h("option", { value: String(v) }, r)));
  s.value = String(valor);
  return s;
}
/** Tipos de credor: caixa que continua aberta enquanto se marcam as opções. */
function campoTipos() {
  const marcados = TIPOS.filter(t => estado.tipos.has(t.id));
  const resumo = marcados.length === TIPOS.length ? "todos" : marcados.length === 2 && estado.tipos.has("empresa") && estado.tipos.has("terceiro")
    ? "empresas e terceiro setor" : marcados.length + " de " + TIPOS.length;
  const caixas = TIPOS.map(t => h("label", { class: "opcao" },
    h("input", { type: "checkbox", checked: estado.tipos.has(t.id) ? true : null, onchange: e => {
      const novo = new Set(estado.tipos);
      if (e.target.checked) novo.add(t.id); else novo.delete(t.id);
      if (!novo.size) { e.target.checked = true; return; }
      UI.tiposAberto = true;
      ajustar({ tipos: novo });
    } }), t.rotulo, t.id === "conselho" ? h("span", { class: "muted small" }, " — só nas somas; cada um atende uma escola") : null));
  const det = h("details", { class: "tipos-credor", open: UI.tiposAberto ? true : null },
    h("summary", { "aria-label": "Tipos de credor: " + resumo }, resumo),
    h("div", { class: "opcoes" }, caixas, h("button", { type: "button", class: "leve", onclick: () => { det.open = false; } }, "Fechar")));
  det.addEventListener("toggle", () => { UI.tiposAberto = det.open; });
  return h("div", { class: "campo" }, h("span", { class: "rotulo-campo", "aria-hidden": "true" }, "Tipos de credor"), det);
}

function filtrosFornecedores() {
  const base = { ano: estado.ano, fonte: estado.fonte, tipos: estado.tipos };
  return [
    campo("Mercado", seletorMercado(estado.mercado, v => ajustar({ mercado: v }), base)),
    campo("Exercício", seletorAno()),
    campo("Origem do recurso", seletorFonte()),
    campo("Alcance mínimo", seletorSimples(estado.min, [[2, "2+ municípios"], [3, "3+ municípios"], [5, "5+ municípios"], [10, "10+ municípios"], [20, "20+ municípios"]], v => ajustar({ min: +v }))),
    campoTipos(),
  ];
}
function recorteFornecedores() {
  return [h("strong", {}, ROTULO_MERCADO(estado.mercado)), " · ", h("strong", {}, rotuloAno(estado.ano)), " · origem: ",
    h("strong", {}, rotuloFonte(estado.fonte)), " · fornecedores de ", h("strong", {}, estado.min + "+ municípios")];
}
function recorteCurtoFornecedores() { return ROTULO_MERCADO(estado.mercado) + " · " + rotuloAno(estado.ano); }

/* ------------------------------------------------------------ montagem */
function posicoes(lay, disp) {
  const p = new Map();
  const arr = lay[disp] || lay.mapa;
  lay.nos.forEach((f, i) => p.set(f, [arr[2 * i], arr[2 * i + 1]]));
  const mun = disp === "forca" && lay.forca_municipios && lay.forca_municipios.length === MUN.length * 2
    ? MUN.map((_, i) => [lay.forca_municipios[2 * i], lay.forca_municipios[2 * i + 1]]) : MUN.map(m => [m.x, m.y]);
  return { p, mun };
}
function raioPorValor(v, max) { return 2.2 + 11 * Math.sqrt(Math.max(0, v) / (max || 1)); }

function dadosGrafoFornecedores(ag) {
  const c = coresGrafo();
  const lay = DADOS.layouts[estado.mercado];
  const { p, mun } = posicoes(lay, estado.disp);
  const visiveis = [...ag.porForn.values()].filter(x => p.has(x.f) && x.k >= estado.min && FORN[x.f].tipo !== "conselho")
    .sort((a, b) => b.emp - a.emp);
  const maxV = visiveis.length ? Math.max(...visiveis.map(x => x.emp)) : 1;
  // Por afinidade, o município leva a cor e a letra da sua comunidade (a da aba "Municípios
  // conectados"): é o que mostra se os grupos que as forças formaram são os mercados regionais.
  const com = estado.disp === "forca" ? DADOS.projecoes[estado.mercado].comunidade : null;
  const nos = MUN.map((m, i) => ({ id: "m:" + m.cod, x: mun[i][0], y: mun[i][1], r: 5, forma: "q",
    cor: com ? (corCom(com[i], c) || c.ink2) : c.municipio, letraNo: com && com[i] >= 0 ? letraCom(com[i]) : null,
    rotulo: m.nome, i, tipo: "m" }));
  const idx = new Map();
  visiveis.forEach((x, j) => {
    const [px, py] = p.get(x.f);
    const alc = alcanceDe(x.k);
    idx.set(x.f, nos.length);
    nos.push({ id: "f:" + FORN[x.f].raiz, x: px, y: py, r: raioPorValor(x.emp, maxV), forma: PUBLICOS.has(FORN[x.f].tipo) ? "anel" : "c",
      cor: c.alcance[alc], borda: alc === 0 ? c.bordaAlc1 : null, rotulo: FORN[x.f].nome, prio: j < 25 ? 10 - j / 5 : 1, f: x.f, tipo: "f" });
  });
  const ligs = [];
  let maxE = 0, nLig = 0;
  for (const x of visiveis) for (const l of x.ligs) if (l.emp > 0.005) { maxE = Math.max(maxE, l.emp); nLig++; }
  // Muitas linhas viram uma mancha: a transparência cai com a raiz do número de ligações.
  const alfaLigacoes = Math.max(0.05, Math.min(0.32, 0.32 * Math.sqrt(1200 / Math.max(1, nLig))));
  for (const x of visiveis) for (const l of x.ligs) {
    if (!(l.emp > 0.005)) continue;
    ligs.push({ a: l.m, b: idx.get(x.f), w: 0.35 + 2.4 * Math.sqrt(l.emp / (maxE || 1)), cor: c.neutro, alfa: alfaLigacoes });
  }
  const fundo = estado.disp === "mapa" ? fundoMapa() : null;
  return { nos, arestas: ligs, fundo, visiveis };
}

function fraseFornecedores(ag, visiveis) {
  const valorRede = visiveis.reduce((s, x) => s + x.emp, 0);
  const maior = visiveis.slice().sort((a, b) => b.k - a.k || b.emp - a.emp)[0];
  const altas = [...ag.porMun.values()].filter(m => m.hhi !== null && m.hhi > 2500).length;
  const onde = (estado.mercado === "todos" ? "Somando todos os mercados" : "Em " + ROTULO_MERCADO(estado.mercado).toLowerCase())
    + (estado.ano === null ? ", de " + rotuloAno(null) : ", em " + rotuloAno(estado.ano)) + (estado.fonte === null ? "" : ", com recursos de " + FONTES[estado.fonte].rotulo.split(" (")[0]);
  if (!visiveis.length) return onde + ", nenhuma empresa atende " + estado.min + " municípios ou mais.";
  return onde + ", " + nf(visiveis.length) + " empresas vendem a " + estado.min + " municípios ou mais e ficam com "
    + pct0(ag.total > 0 ? valorRede / ag.total * 100 : null) + " do que os municípios empenharam a pessoas jurídicas (" + brlCompacto(ag.total) + "). "
    + "A de maior alcance, " + FORN[maior.f].nome + ", atende " + maior.k + ". Em " + altas + " dos 78 municípios esse mercado é concentrado.";
}

function renderFornecedores(main) {
  const fl = filtroAtual(), ag = agregar(fl);
  guardarVista(FV.chaveVista, FV.grafo);
  FV.ag = ag;
  const dg = dadosGrafoFornecedores(ag);
  FV.visiveis = dg.visiveis;
  main.append(botaoIrParaFigura(() => FV.grafo),
    h("section", { class: "cab-visao compacta" }, h("h2", {}, "Quem fornece a quem"), h("p", { class: "frase" }, fraseFornecedores(ag, dg.visiveis))));

  const itensBusca = dg.visiveis.map(x => ({ texto: FORN[x.f].nome, sub: fmtCnpj(FORN[x.f].raiz) + " · " + x.k + " municípios", digitos: FORN[x.f].raiz + " " + FORN[x.f].cnpjs.join(" "), sel: "f:" + FORN[x.f].raiz }))
    .concat(MUN.map(m => ({ texto: m.nome, sub: "município", sel: "m:" + m.cod })));
  const cartao = cartaoGrafo({
    id: "card-rede-fornecedores",
    ferramentas: [
      campoBuscaRede(itensBusca, "Buscar na figura", "Empresa, CNPJ ou município…"),
      alternador("Disposição", estado.disp, [["mapa", "Mapa do ES", "Municípios no lugar; fornecedor entre os municípios que atende"], ["forca", "Afinidade", "Perto quem compra dos mesmos fornecedores"]], v => ajustar({ disp: v })),
      h("label", { class: "opcao-ferramenta" }, h("input", { type: "checkbox", checked: estado.ligacoes === "todas" ? true : null,
        onchange: e => { estado.ligacoes = e.target.checked ? "todas" : "sel"; history.replaceState(null, "", hashDe(estado)); FV.grafo.mostrarLigacoes(!e.target.checked); } }), "Todas as ligações"),
      h("span", { class: "espaco" }),
      botaoFonte(null, () => ["rede de fornecedores, " + rotuloAno(estado.ano), qEmpenhos(fl), passosRede(), null]),
    ],
    legenda: legendaFornecedores(),
    notas: h("details", { class: "tab notas-figura" }, h("summary", {}, "Como a figura foi desenhada"),
      h("p", { class: "nota" }, estado.disp === "mapa"
        ? "Mapa do ES: cada município no seu lugar; cada fornecedor no centro de gravidade dos municípios que atende, ponderado pela raiz quadrada do valor (um contrato grande não cola o fornecedor num município só), e afastado dos vizinhos até não haver sobreposição. Fornecedor estadual cai no meio do estado; regional, perto da sua região."
        : "Afinidade: ForceAtlas2 (Jacomy et al., 2014) a partir da disposição do mapa — quem compra dos mesmos fornecedores fica perto, independente da distância. Não há eixo: distância é afinidade, não quilômetro. Os quadrados têm a cor e a letra da comunidade do município (aba Municípios conectados)."),
      h("p", { class: "nota" }, "A disposição foi calculada uma vez no ETL, com semente fixa, para todo o período: mudar o exercício ou a origem esconde e redimensiona os nós, mas não os move. Tamanho do círculo = valor recebido no recorte; cor = alcance; linha = houve empenho.")),
  });
  FV.cartao = cartao;
  main.append(cartao.card);
  FV.grafo = new Grafo(cartao.tela, {
    descricao: "Rede de fornecedores: " + MUN.length + " municípios e " + dg.visiveis.length + " empresas. As tabelas abaixo trazem os mesmos dados.",
    aoPassar: dicaFornecedores, aoClicar: n => irPara({ sel: n ? n.id : null }), letras: estado.disp === "forca", soSelecao: estado.ligacoes === "sel",
  });
  cartao.tela.append(cartao.faixa);
  FV.grafo.definir(dg);
  FV.chaveVista = "f|" + estado.mercado + "|" + estado.disp;
  restaurarVista(FV.chaveVista, FV.grafo);
  if (!dg.visiveis.length) FV.grafo.aviso(h("div", {}, h("p", {}, "Nenhuma empresa atende " + estado.min + " municípios ou mais neste recorte."),
    estado.min > 2 ? linkPara({ min: 2 }, "Mostrar as de 2 municípios ou mais") : linkPara({ mercado: "todos", ano: null, fonte: null }, "Voltar a todos os mercados")));
  main.append(cardTabelaFornecedores(ag, dg.visiveis), cardConcentracao(ag, fl));
  selecionarFornecedores(estado.sel, true);
}
function kpi(rotulo, valor, det, opcoes) {
  const o = opcoes || {};
  return h("div", { class: "kpi" + (o.classe ? " " + o.classe : "") }, h("span", { class: "rot" }, rotulo), h("span", { class: "val" + (o.texto ? " texto" : "") }, valor),
    h("span", { class: "det" }, det));
}
function passosRede(extra) {
  return [
    "Abra o recorte da função 12 do ano no cache (arquivo abaixo: CSV com \";\", UTF-8, vírgula decimal).",
    "Fique com as linhas do município (coluna EsferaAdministrativa), sem a modalidade 91 (CodigoModalidade ≠ 91, operações intraorçamentárias) e fora do grupo de natureza 1 (pessoal).",
    "Fornecedor = os 8 primeiros dígitos de CodigoCredorFornecedor, só onde NomeIdentificacao = CNPJ.",
    estado.mercado === "todos" ? "Mercado: todos (a soma dos mercados abaixo)." : "Mercado " + ROTULO_MERCADO(estado.mercado) + ": " + MERCADO[estado.mercado].regra + ".",
    estado.fonte === null ? "Origem: todas." : "Origem " + FONTES[estado.fonte].rotulo + ": pelo nome da fonte (NomeFonteReduzida) — ver a metodologia.",
    "Some a coluna Empenhada (e Paga, para o pago).",
    ...(extra || []),
  ];
}
function svgEl(tag, attrs) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}
/** <svg> no namespace certo (o h() cria elementos HTML, e um "svg" HTML não desenha nada). */
function svgRaiz(attrs, ...filhos) {
  const el = svgEl("svg", attrs);
  for (const f of filhos.flat(Infinity)) if (f) el.append(f);
  return el;
}
function legendaFornecedores() {
  const c = coresGrafo();
  const bola = (cor, anel, borda) => svgRaiz({ viewBox: "0 0 14 14", "aria-hidden": "true", width: "14", height: "14" },
    anel ? svgEl("circle", { cx: 7, cy: 7, r: 5, fill: "none", stroke: cor, "stroke-width": 2.5 }) : svgEl("circle", { cx: 7, cy: 7, r: 5.5, fill: cor, stroke: borda || "none", "stroke-width": 1.2 }));
  const quad = cor => svgRaiz({ viewBox: "0 0 14 14", width: "14", height: "14", "aria-hidden": "true" }, svgEl("rect", { x: 2, y: 2, width: 10, height: 10, fill: cor }));
  const P = DADOS.projecoes[estado.mercado];
  const comunidades = [...new Set(P.comunidade.filter(x => x >= 0))].sort((a, b) => a - b);
  return h("div", { class: "rede-legenda", role: "note", "aria-label": "Legenda" },
    estado.disp === "forca"
      ? comunidades.map(x => h("span", {}, quad(corCom(x, c) || c.ink2), "município da comunidade " + letraCom(x)))
      : h("span", {}, quad(c.municipio), "município"),
    ALCANCES.map(a => h("span", {}, bola(c.alcance[a.id], false, a.id === 0 ? c.bordaAlc1 : null), "fornecedor " + a.rotulo)),
    h("span", {}, bola(c.ink2, true), "órgão público ou concessionária"),
    h("span", {}, svgRaiz({ viewBox: "0 0 22 12", width: "22", height: "12", "aria-hidden": "true" }, svgEl("line", { x1: 1, y1: 6, x2: 21, y2: 6, stroke: c.destaque, "stroke-width": 2.5 })), "ligações do nó selecionado"));
}
function dicaFornecedores(n) {
  const ag = FV.ag;
  if (n.tipo === "m") {
    const d = ag.porMun.get(n.i);
    return [d ? brl(d.emp) : "sem empenho a pessoa jurídica no recorte", n.rotulo + " — município", d ? d.nForn + " fornecedores · concentração " + classeHhi(d.hhi) : ""];
  }
  const x = ag.porForn.get(n.f);
  return [brl(x.emp), FORN[n.f].nome, "atende " + x.k + " municípios · " + ROTULO_TIPO[FORN[n.f].tipo].toLowerCase()];
}

/* ------------------------------------------------------------ seleção */
function selecionarFornecedores(sel, primeiraVez) {
  if (!FV.grafo) return;
  FV.grafo.selecionar(sel, !primeiraVez || !!sel);
  const lado = limpar(FV.cartao.lado);
  if (!sel) { lado.append(ladoInicialFornecedores()); mostrarFaixa(FV.cartao, null); FV.grafo.descrever("Rede de fornecedores, sem seleção."); return; }
  if (sel.startsWith("m:")) {
    const i = IDX_MUN.get(+sel.slice(2)), d = FV.ag.porMun.get(i);
    lado.append(ladoMunicipioForn(i));
    const det = d ? d.nForn + " fornecedores · " + brlCompacto(d.emp) : "sem empenho no recorte";
    mostrarFaixa(FV.cartao, MUN[i] ? MUN[i].nome : "", det);
    if (!primeiraVez && MUN[i]) anunciar("Selecionado: " + MUN[i].nome + ", " + det + ".");
  } else if (sel.startsWith("f:")) {
    const f = IDX_FORN.get(sel.slice(2)), x = f === undefined ? null : FV.ag.porForn.get(f);
    lado.append(ladoFornecedor(f));
    const det = x ? "atende " + x.k + " municípios · " + brlCompacto(x.emp) : "sem empenho no recorte";
    mostrarFaixa(FV.cartao, f === undefined ? "" : FORN[f].nome, det);
    if (!primeiraVez && f !== undefined) anunciar("Selecionado: " + FORN[f].nome + ", " + det + ".");
  }
}
function ladoInicialFornecedores() {
  const ag = FV.ag, vis = FV.visiveis;
  const valorRede = vis.reduce((s, x) => s + x.emp, 0);
  const altas = [...ag.porMun.values()].filter(m => m.hhi !== null && m.hhi > 2500).length;
  const top = vis.slice().sort((a, b) => b.k - a.k || b.emp - a.emp).slice(0, 6);
  return h("div", {},
    h("h3", {}, "Visão geral do recorte"),
    resumoLado([
      ["Empresas na figura", nf(vis.length), "atendem " + estado.min + "+ municípios, de " + nf(ag.porForn.size) + " com empenho"],
      ["Recebido por elas", brlCompacto(valorRede), pct0(ag.total > 0 ? valorRede / ag.total * 100 : null) + " do empenhado a pessoas jurídicas"],
      ["Municípios com mercado concentrado", altas + " de 78", "HHI acima de 2.500 (faixas do CADE)"],
    ]),
    top.length ? [h("h4", {}, "Maior alcance"), h("ol", { class: "lista-sel" }, top.map(x => h("li", {}, linkPara({ sel: "f:" + FORN[x.f].raiz }, FORN[x.f].nome),
      h("span", { class: "muted small" }, " · " + x.k + " municípios · " + brlCompacto(x.emp)))))] : null,
    listaPerguntas(),
    h("p", { class: "nota" }, "Clique num quadrado (município) ou num círculo (empresa). Ctrl + roda do mouse aproxima; com a figura em foco, + e − aproximam, as setas movem e 0 enquadra."));
}
function linhaDl(pares) { return h("dl", { class: "dl-lado" }, pares.filter(Boolean).map(([t, d]) => [h("dt", {}, t), h("dd", {}, d)])); }

function ladoFornecedor(f) {
  if (f === undefined) return h("p", {}, "Fornecedor não encontrado.");
  const fl = filtroAtual(), ag = FV.ag, F = FORN[f], x = ag.porForn.get(f);
  const perfil = perfilFornecedor(f, fl);
  const corpo = h("div", {});
  corpo.append(h("p", { class: "voltar-lado" }, linkPara({ sel: null }, "← Visão geral")),
    h("h3", {}, F.nome),
    h("p", { class: "small muted" }, ROTULO_TIPO[F.tipo] + " · CNPJ raiz " + fmtCnpj(F.raiz)));
  if (!x) {
    corpo.append(h("p", { class: "callout" }, "Sem empenho no recorte atual (", ROTULO_MERCADO(estado.mercado), ", ", rotuloAno(estado.ano), "). Troque o mercado ou o exercício."));
  } else {
    corpo.append(resumoLado([
      ["Empenhado", brlCompacto(x.emp), brl(x.emp) + " · pago " + brlCompacto(x.pag)],
      ["Municípios", nf(x.k), x.k >= estado.min ? ALCANCES[alcanceDe(x.k)].rotulo : "abaixo do alcance mínimo: fora da figura"],
      ["Parcela do mercado no ES", pct0(ag.total > 0 ? x.emp / ag.total * 100 : null), "do empenhado a pessoas jurídicas no recorte"],
    ]));
  }
  corpo.append(h("h4", {}, "Por exercício"), barrasSimples(ANOS.map((a, i) => [String(a), perfil.porAno[i]]), estado.ano === null ? null : estado.ano));
  corpo.append(h("h4", {}, "Por origem do recurso"), barrasSimples(FONTES.map((o, i) => [o.rotulo.split(" (")[0], perfil.porFonte[i]]), estado.fonte));
  const merc = [...perfil.porMercado.entries()].filter(([, v]) => Math.abs(v) > 0.005).sort((a, b) => b[1] - a[1]);
  if (merc.length > 1 || estado.mercado === "todos") {
    corpo.append(h("h4", {}, "Em que mercados aparece"), h("ul", { class: "lista-sel" }, merc.map(([k, v]) => h("li", {},
      MERCADOS[k].id === estado.mercado ? h("strong", {}, MERCADOS[k].rotulo) : linkPara({ mercado: MERCADOS[k].id }, MERCADOS[k].rotulo),
      h("span", { class: "muted small" }, " · " + brlCompacto(v))))));
  }
  if (x) {
    const linhas = x.ligs.filter(l => l.emp > 0.005 || l.pag > 0.005).map(l => {
      const dm = ag.porMun.get(l.m);
      return { m: l.m, mun: nomeMun(l.m), emp: l.emp, pag: l.pag, parcela: dm && dm.emp > 0 ? l.emp / dm.emp * 100 : null, acao: l.acao === null ? "" : ACOES[l.acao] };
    }).sort((a, b) => b.emp - a.emp);
    corpo.append(h("h4", {}, "Municípios atendidos (" + linhas.length + ")"), tabela([
      { rotulo: "Município", valor: l => l.mun, render: l => h("div", {}, linkPara({ sel: "m:" + MUN[l.m].cod }, l.mun),
        l.acao ? h("div", { class: "sub-celula" }, l.acao) : null) },
      { rotulo: "Empenhado", valor: l => l.emp, fmt: brlCompacto, csv: l => l.emp, num: true },
      { rotulo: "Parcela", valor: l => l.parcela, fmt: v => pct0(v), num: true },
    ], linhas, "Municípios atendidos por " + F.nome, { inicio: 8, busca: false, fixarPrimeira: false, csv: "municipios_" + F.raiz + ".csv", ordemInicial: { coluna: 1, direcao: "desc" } }));
  }
  if (F.cnpjs.length) corpo.append(h("details", { class: "tab" }, h("summary", {}, "CNPJs (matriz e filiais): " + F.cnpjs.length), h("ul", { class: "lista" }, F.cnpjs.map(c => h("li", {}, h("code", {}, fmtCnpj(c)))))));
  const obra = CONTRATADA_DO_FORNECEDOR.get(f);
  if (obra !== undefined) corpo.append(h("p", {}, linkPara({ visao: "obras", sel: "c:" + OBRAS.contratadas[obra].id }, "Tem obra da Educação no TCE-ES ›")));
  corpo.append(h("p", { class: "acao-dossie" }, linkPara({ visao: "empresa", sel: "f:" + F.raiz }, "Análise profunda ›", { class: "botao-acao" }),
    h("span", { class: "small muted" }, " contratos, preços, cadastro, sanções e documentos — e a análise com IA")));
  corpo.append(h("div", { class: "acoes-lado" }, botaoFonte(null, () => [F.nome + ", " + rotuloAno(estado.ano), qEmpenhos(fl),
    passosRede(["Para este fornecedor: CodigoCredorFornecedor começando por " + F.raiz + "."]), null])));
  return corpo;
}

function ladoMunicipioForn(i) {
  if (i === undefined) return h("p", {}, "Município não encontrado.");
  const fl = filtroAtual(), ag = FV.ag, M = MUN[i], d = ag.porMun.get(i), res = residuaisDe(i, fl);
  const corpo = h("div", {}, h("p", { class: "voltar-lado" }, linkPara({ sel: null }, "← Visão geral")),
    h("h3", {}, M.nome), h("p", { class: "small muted" }, "Região imediata " + M.imediata + " · intermediária " + M.intermediaria));
  if (!d) {
    corpo.append(h("p", { class: "callout" }, "Nenhum empenho a pessoa jurídica dos tipos escolhidos neste recorte."));
  } else {
    corpo.append(resumoLado([
      ["Empenhado a pessoas jurídicas", brlCompacto(d.emp), brl(d.emp)],
      ["Concentração (HHI)", d.hhi === null ? "sem dado" : nf(d.hhi, 0), classeHhi(d.hhi) + (d.maior ? " · maior: " + FORN[d.maior.f].nome + " com " + pct0(d.maiorPct) : "")],
      ["Com fornecedores compartilhados", pct0(d.emp > 0 ? d.compartilhado / d.emp * 100 : null), "do valor vai a quem também atende outros municípios"],
      res.pf ? ["Pessoas físicas (fora da rede)", brlCompacto(res.pf), pct0(res.pf / (d.emp + res.pf) * 100) + " do mercado, sem identificar ninguém"] : null,
    ]));
    const linhas = d.ligs.filter(l => l.emp > 0.005).map(l => ({ f: l.f, nome: FORN[l.f].nome, emp: l.emp, parcela: d.emp > 0 ? l.emp / d.emp * 100 : null,
      k: ag.porForn.get(l.f).k, acao: l.acao === null ? "" : ACOES[l.acao] })).sort((a, b) => b.emp - a.emp);
    corpo.append(h("h4", {}, "Fornecedores do município (" + linhas.length + ")"), tabela([
      { rotulo: "Fornecedor", valor: l => l.nome, render: l => h("div", {},
        l.k >= 2 ? linkPara({ sel: "f:" + FORN[l.f].raiz }, l.nome) : h("span", {}, l.nome),
        h("div", { class: "sub-celula" }, l.k === 1 ? "só atende este município" : "atende " + l.k + " municípios")) },
      { rotulo: "Empenhado", valor: l => l.emp, fmt: brlCompacto, csv: l => l.emp, num: true },
      { rotulo: "Parcela", valor: l => l.parcela, fmt: v => pct0(v), num: true },
    ], linhas, "Fornecedores de " + M.nome, { inicio: 10, busca: linhas.length > 15, fixarPrimeira: false, csv: "fornecedores_" + M.cod + ".csv", ordemInicial: { coluna: 1, direcao: "desc" } }));
  }
  const ano = estado.ano === null ? ANOS[ANOS.length - 1] : ANOS[estado.ano];
  corpo.append(h("div", { class: "acoes-lado" },
    linkPara({ visao: "municipios", sel: "m:" + M.cod }, "Com quem " + M.nome + " divide fornecedores ›"),
    CONFIG.painel ? h("a", { href: CONFIG.painel + "#v=municipio&ano=" + ano + "&m=" + M.cod + "&s=nivel3" }, "Dossiê no painel de financiamento ›") : null,
    botaoFonte(null, () => [M.nome + ", " + rotuloAno(estado.ano), qEmpenhos(fl), passosRede(["Município: EsferaAdministrativa = " + M.nome + "."]), null])));
  return corpo;
}

/** Barras horizontais simples (rótulo, trilho, valor), na grade `.barras` do painel. */
function barrasSimples(pares, destaque) {
  const max = Math.max(0, ...pares.map(p => Math.abs(p[1])));
  if (!(max > 0)) return h("p", { class: "muted small" }, "Sem valor neste recorte.");
  return h("div", { class: "barras compactas" }, pares.map(([rot, v], i) => h("div", { class: "barra-sub" + (destaque === i ? " atual" : "") },
    h("span", { class: "nome" }, rot),
    h("span", { class: "trilho-caixa" }, h("span", { class: "trilho" }, h("span", { class: "fill", style: "width:" + (Math.max(0, v) / max * 100).toFixed(1) + "%" }))),
    h("span", { class: "valor" }, h("b", {}, brlCompacto(v))))));
}

/* ------------------------------------------------------------ tabelas */
function cardTabelaFornecedores(ag, visiveis) {
  const linhas = visiveis.map(x => {
    const tops = x.ligs.filter(l => l.emp > 0.005).sort((a, b) => b.emp - a.emp).slice(0, 3).map(l => nomeMun(l.m)).join(", ");
    return { f: x.f, nome: FORN[x.f].nome, raiz: fmtCnpj(FORN[x.f].raiz), tipo: ROTULO_TIPO[FORN[x.f].tipo], k: x.k, alcance: ALCANCES[alcanceDe(x.k)].rotulo,
      emp: x.emp, pag: x.pag, parcela: ag.total > 0 ? x.emp / ag.total * 100 : null, tops };
  });
  const recorte = () => [["Mercado", ROTULO_MERCADO(estado.mercado)], ["Exercício", rotuloAno(estado.ano)], ["Origem", rotuloFonte(estado.fonte)],
    ["Mínimo de municípios", estado.min], ["Tipos de credor", [...estado.tipos].map(t => ROTULO_TIPO[t]).join("; ")]];
  return h("article", { class: "card", id: "card-fornecedores" },
    h("header", {}, h("div", { class: "cab-card" }, h("div", {}, h("h3", {}, "Fornecedores na figura"),
      h("p", { class: "simples" }, "Um por linha, com quantos municípios atende e quanto recebeu no recorte. O nome leva ao fornecedor na figura.")))),
    tabela([
      { rotulo: "Fornecedor", valor: l => l.nome, classe: "col-nome", render: l => linkPara({ sel: "f:" + FORN[l.f].raiz, ir: "figura" }, l.nome) },
      { rotulo: "CNPJ (raiz)", valor: l => l.raiz },
      { rotulo: "Tipo", valor: l => l.tipo },
      { rotulo: "Municípios", valor: l => l.k, num: true, fmt: nf },
      { rotulo: "Alcance", valor: l => l.alcance },
      { rotulo: "Empenhado", valor: l => l.emp, num: true, fmt: brl },
      { rotulo: "Pago", valor: l => l.pag, num: true, fmt: brl },
      { rotulo: "Parcela do mercado no ES", valor: l => l.parcela, num: true, fmt: v => pct0(v) },
      { rotulo: "Principais municípios", valor: l => l.tops, classe: "small" },
    ], linhas, "Fornecedores na figura", { csv: "rede_fornecedores.csv", xlsx: "rede_fornecedores.xlsx", recorte, ordemInicial: { coluna: 3, direcao: "desc" } }));
}

function cardConcentracao(ag, fl) {
  const linhas = MUN.map((m, i) => {
    const d = ag.porMun.get(i), res = residuaisDe(i, fl);
    return { i, nome: m.nome, emp: d ? d.emp : null, n: d ? d.nForn : 0, maior: d && d.maior ? FORN[d.maior.f].nome : "", maiorPct: d ? d.maiorPct : null,
      hhi: d ? d.hhi : null, classe: classeHhi(d ? d.hhi : null), comp: d && d.emp > 0 ? d.compartilhado / d.emp * 100 : null, pf: res.pf || 0 };
  });
  const recorte = () => [["Mercado", ROTULO_MERCADO(estado.mercado)], ["Exercício", rotuloAno(estado.ano)], ["Origem", rotuloFonte(estado.fonte)],
    ["Tipos de credor", [...estado.tipos].map(t => ROTULO_TIPO[t]).join("; ")]];
  return h("article", { class: "card", id: "card-concentracao" },
    h("header", {}, h("div", { class: "cab-card" }, h("div", {}, h("h3", {}, "Concentração do mercado em cada município — " + ROTULO_MERCADO(estado.mercado)),
      h("p", { class: "simples" }, "Quanto do mercado do município fica com poucos fornecedores. HHI é a soma dos quadrados das participações (0 a 10.000): até 1.500 é baixa; de 1.500 a 2.500, moderada; acima, alta (faixas do CADE). "
        + "Município pequeno com um só fornecedor de transporte não é, por si, problema — mas é onde vale olhar o preço."),
      h("details", { class: "tecnico" }, h("summary", {}, "Detalhes"), h("p", { class: "nota" }, "Calculado sobre os tipos de credor escolhidos. Pessoa física (CPF) fica fora do índice e aparece somada à parte — muitos municípios contratam transporte escolar de motoristas autônomos."))))),
    tabela([
      { rotulo: "Município", valor: l => l.nome, render: l => linkPara({ sel: "m:" + MUN[l.i].cod, ir: "figura" }, l.nome) },
      { rotulo: "Empenhado (PJ)", valor: l => l.emp, num: true, fmt: brl },
      { rotulo: "Fornecedores", valor: l => l.n, num: true, fmt: nf },
      { rotulo: "Maior fornecedor", valor: l => l.maior, classe: "small" },
      { rotulo: "Parcela do maior", valor: l => l.maiorPct, num: true, fmt: v => pct0(v) },
      { rotulo: "HHI", valor: l => l.hhi, num: true, fmt: v => nf(v, 0) },
      { rotulo: "Concentração", valor: l => l.classe },
      { rotulo: "Com fornecedores compartilhados", valor: l => l.comp, num: true, fmt: v => pct0(v) },
      { rotulo: "Pessoas físicas (fora)", valor: l => l.pf, num: true, fmt: brl },
    ], linhas, "Concentração por município", { csv: "concentracao_municipios.csv", xlsx: "concentracao_municipios.xlsx", recorte, ordemInicial: { coluna: 5, direcao: "desc" } }));
}
