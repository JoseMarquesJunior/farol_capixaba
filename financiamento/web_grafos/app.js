"use strict";
/* ============================================================================
   Orquestra a página: estado, endereço (hash), navegação, barra de contexto.
   Trocar de visão ou de seleção é um link (o Voltar do navegador volta);
   trocar um filtro substitui o endereço sem empilhar histórico — e mantém a
   rolagem e o enquadramento da figura onde estavam.
   ========================================================================== */
const VISOES = [
  { id: "fornecedores", rotulo: "Fornecedores", filtros: filtrosFornecedores, recorte: recorteFornecedores, curto: recorteCurtoFornecedores, render: renderFornecedores, selecionar: selecionarFornecedores },
  { id: "municipios", rotulo: "Municípios conectados", filtros: filtrosMunicipios, recorte: recorteMunicipios, curto: recorteCurtoMunicipios, render: renderMunicipios, selecionar: selecionarMunicipios },
  { id: "obras", rotulo: "Obras", filtros: filtrosObras, recorte: recorteObras, curto: recorteCurtoObras, render: renderObras, selecionar: selecionarObras },
  { id: "insights", rotulo: "Insights", filtros: filtrosInsights, recorte: recorteInsights, curto: recorteCurtoInsights, render: renderInsights },
  { id: "empresa", rotulo: "Dossiê da empresa", oculta: true, filtros: null, recorte: recorteEmpresa, curto: recorteCurtoEmpresa, render: renderEmpresa },
  { id: "metodologia", rotulo: "Como ler e metodologia", filtros: null, recorte: () => [h("strong", {}, "a documentação das redes")], curto: () => "Metodologia", render: renderMetodologia },
];
const PADRAO = { visao: "fornecedores", mercado: "todos", ano: null, fonte: null, min: 2, disp: "mapa", tipos: new Set(META.tipos_padrao),
  sel: null, lig: 3, contorno: "intermediaria", sit: "todas", minObras: 1, dispObras: "mapa", ligacoes: "todas", ti: "todos", ir: null };
const estado = { ...PADRAO, tipos: new Set(PADRAO.tipos) };

function hashDe(e) {
  // Os filtros valem entre visões (ir e voltar não os perde); só entra no endereço o que difere do padrão.
  const p = new URLSearchParams({ v: e.visao });
  if (e.mercado !== "todos") p.set("k", e.mercado);
  if (e.ano !== null) p.set("ano", ANOS[e.ano]);
  if (e.fonte !== null) p.set("o", FONTES[e.fonte].id);
  if (e.min !== 2) p.set("min", e.min);
  if (e.disp !== "mapa") p.set("d", e.disp);
  const t = [...e.tipos].sort().join(",");
  if (t !== [...PADRAO.tipos].sort().join(",")) p.set("t", t);
  if (e.lig !== 3) p.set("lig", e.lig);
  if (e.contorno !== "intermediaria") p.set("c", e.contorno);
  if (e.sit !== "todas") p.set("sit", e.sit);
  if (e.minObras !== 1) p.set("mo", e.minObras);
  if (e.dispObras !== "mapa") p.set("do", e.dispObras);
  if (e.ligacoes === "sel") p.set("l", "sel");
  if (e.ti !== "todos") p.set("ti", e.ti);
  if (e.sel) p.set("sel", e.sel);
  if (e.ir) p.set("ir", e.ir);
  return "#" + p.toString();
}
function lerHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  const v = p.get("v");
  estado.visao = VISOES.some(x => x.id === v) ? v : PADRAO.visao;
  const k = p.get("k");
  estado.mercado = k && MERCADO[k] ? k : "todos";
  const ano = ANOS.indexOf(parseInt(p.get("ano"), 10));
  estado.ano = ano >= 0 ? ano : null;
  const o = FONTES.findIndex(f => f.id === p.get("o"));
  estado.fonte = o >= 0 ? o : null;
  const min = parseInt(p.get("min"), 10);
  estado.min = [2, 3, 5, 10, 20].includes(min) ? min : 2;
  estado.disp = p.get("d") === "forca" ? "forca" : "mapa";
  estado.dispObras = p.get("do") === "forca" ? "forca" : "mapa";
  const t = (p.get("t") || "").split(",").filter(x => TIPOS.some(y => y.id === x));
  estado.tipos = new Set(t.length ? t : PADRAO.tipos);
  const lig = parseInt(p.get("lig"), 10);
  estado.lig = [1, 2, 3, 5, 8].includes(lig) ? lig : 3;
  const c = p.get("c");
  estado.contorno = ["intermediaria", "imediata", "nenhum"].includes(c) ? c : "intermediaria";
  const sit = p.get("sit");
  estado.sit = sit === "paradas" || SITUACOES.some(s => s.id === sit) ? sit : "todas";
  const mo = parseInt(p.get("mo"), 10);
  estado.minObras = [1, 2, 3].includes(mo) ? mo : 1;
  estado.ligacoes = p.get("l") === "sel" ? "sel" : "todas";
  estado.ti = ["sinal", "padrao", "contexto"].includes(p.get("ti")) ? p.get("ti") : "todos";
  estado.sel = p.get("sel") || null;
  estado.ir = p.get("ir") || null;
}
const estadoCom = m => ({ ...estado, ...m, tipos: m.tipos || estado.tipos });
function irPara(mudancas) {
  const novo = hashDe(estadoCom(mudancasNormalizadas(mudancas)));
  if (novo === location.hash) render(); else location.hash = novo;
}
function ajustar(mudancas) { Object.assign(estado, mudancas, { ir: null }); history.replaceState(null, "", hashDe(estado)); render(); }

/* ------------------------------------------------------------ montagem */
let montado = { visao: null, chave: null };
function chaveMontagem() { return hashDe({ ...estado, sel: null, ir: null, ligacoes: "todas" }); }

function render() {
  lerHash();
  const v = VISOES.find(x => x.id === estado.visao);
  anexar(limpar($("#nav-visoes")), ...VISOES.filter(x => !x.oculta).map(x => h("li", {}, h("a", { href: hashDe({ ...estado, visao: x.id, sel: null, ir: null }), "aria-current": x.id === v.id ? "page" : null }, x.rotulo))),
    CONFIG.painel ? h("li", { class: "externo" }, h("a", { href: CONFIG.painel }, "Painel de financiamento ›")) : null);
  // Barra de contexto: recorte (longo na tela larga, curto no celular) e os filtros que mudam o DADO.
  const wrap = limpar($("#contexto-wrap"));
  const controles = v.filtros ? h("div", { class: "controles", id: "controles" }, v.filtros()) : null;
  anexar(wrap, h("div", { class: "recorte" }, h("span", { class: "longo" }, "Você está vendo: ", v.recorte()), h("span", { class: "curto", "aria-hidden": "true" }, v.curto())),
    controles ? h("button", { type: "button", class: "alternar-filtros leve", "aria-expanded": String($("#contexto").classList.contains("aberta")), "aria-controls": "controles",
      onclick: e => { const ab = $("#contexto").classList.toggle("aberta"); e.target.setAttribute("aria-expanded", String(ab)); medirContexto(); } }, "Filtros") : null,
    controles);
  medirContexto();
  const chave = chaveMontagem();
  if (montado.visao === v.id && montado.chave === chave && v.selecionar) {
    v.selecionar(estado.sel);
    irParaAlvo();
    return;
  }
  // Mesma visão com outro filtro: a página fica onde estava. Outra visão: começa nas abas.
  const mesmaVisao = montado.visao === v.id, rolagem = scrollY;
  const main = limpar($("#conteudo"));
  esconderDica();
  v.render(main);
  montado = { visao: v.id, chave };
  document.title = v.rotulo + " — Redes do financiamento da educação no ES";
  if (mesmaVisao) scrollTo(0, rolagem);
  else { const topoAbas = $("nav.visoes").offsetTop; if (scrollY > topoAbas) scrollTo(0, topoAbas); }
  irParaAlvo();
}
/** `ir` no endereço (link de tabela ou de pergunta): leva até o cartão e sai do endereço. */
function irParaAlvo() {
  if (!estado.ir) return;
  const alvo = estado.ir === "figura" ? $(".rede-card") : $("#card-" + estado.ir);
  estado.ir = null;
  history.replaceState(null, "", hashDe(estado));
  if (alvo) requestAnimationFrame(() => alvo.scrollIntoView({ behavior: MOVIMENTO_REDUZIDO.matches ? "auto" : "smooth", block: "start" }));
}

function carimbo() {
  const q = Object.values(META.consultas).filter(c => c.fonte === "TCE-ES").map(c => c.obtido_em).sort();
  const coleta = dataBR(q[0]) === dataBR(q[q.length - 1]) ? "coletados em " + dataBR(q[0]) : "coletados entre " + dataBR(q[0]) + " e " + dataBR(q[q.length - 1]);
  return "Empenhos de " + ANOS[0] + " a " + ANOS[ANOS.length - 1] + " declarados ao TCE-ES, " + coleta
    + " · " + nf(FORN.length) + " pessoas jurídicas · página gerada em " + dataHoraBR(META.gerado_em) + ".";
}
function iniciar() {
  $("#carimbo").textContent = carimbo();
  $("#como-ler-topo").append(
    h("p", {}, "Três redes, cada uma numa aba: quem fornece a quem (municípios e empresas), que municípios compram dos mesmos fornecedores, e quem executa as obras da Educação."),
    h("p", {}, "Em todas: quadrado é município, círculo é empresa. Clique num nó para o detalhe; Ctrl + roda do mouse aproxima (ou clique na figura e role); arraste para mover. No celular, dois dedos movem e aproximam. A tabela abaixo de cada figura tem os mesmos dados, com CSV e Excel."),
    h("p", {}, ESTADOS.sinal.simbolo + " Ligação, alcance grande ou concentração alta não são irregularidade: são padrões para orientar a verificação."));
  limpar($("#rodape")).append(
    h("p", {}, carimbo()),
    h("p", {}, "Fontes: Tribunal de Contas do Estado do Espírito Santo (dados abertos em dados.es.gov.br — empenhos dos municípios, obras e serviços de engenharia) e IBGE (malha municipal e divisão regional). "
      + "O dado é o que os municípios declararam ao TCE-ES. Cada número leva ao botão \"ver fonte\" com a consulta exata."),
    h("p", {}, "Protótipo do NEDUC, gerado por python -m financiamento.build_grafos. Não é publicação oficial do TCE-ES."));
  // O "Ir para o conteúdo" é um link de âncora — e o endereço aqui é o estado da página. Sem isto ele zerava os filtros.
  const pular = $(".skip");
  if (pular) pular.addEventListener("click", e => { e.preventDefault(); $("#conteudo").focus(); });
  // A caixa de tipos de credor fecha ao clicar fora ou com Esc.
  document.addEventListener("click", e => {
    const d = $("details.tipos-credor[open]");
    if (d && !d.contains(e.target)) { d.open = false; UI.tiposAberto = false; }
  });
  document.addEventListener("keydown", e => {
    const d = $("details.tipos-credor[open]");
    if (e.key === "Escape" && d) { d.open = false; UI.tiposAberto = false; d.querySelector("summary").focus(); }
  });
  addEventListener("hashchange", render);
  let ultimaLargura = innerWidth;
  addEventListener("resize", () => { if (Math.abs(innerWidth - ultimaLargura) > 40) { ultimaLargura = innerWidth; medirContexto(); } });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { montado = { visao: null, chave: null }; render(); });
  render();
}
iniciar();
