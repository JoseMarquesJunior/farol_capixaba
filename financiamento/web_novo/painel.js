"use strict";
/* ============================================================================
   Orquestra o painel: estado, endereço (hash), navegação, barra de contexto e
   rodapé.

   Navegação com histórico de verdade: trocar de visão, de município, de seção
   ou abrir uma escola é um LINK (a href="#…"), então o botão Voltar do navegador
   leva à tela anterior — antes o painel reescrevia o endereço sem empilhar, e o
   Voltar saía do painel. Ajuste fino (exercício, filtro, indicador, ordenação)
   só substitui o endereço atual, para o Voltar não virar um "desfazer filtro".
   O endereço guarda o estado inteiro: qualquer tela pode ser compartilhada.
   ========================================================================== */

/* A montagem diz se há papel de trabalho do CNCA ao lado (no arquivo local, há; na versão
   publicada no Farol Capixaba, não — ele não é público) e se há um site para onde voltar. */
const CONFIG = (() => { try { return JSON.parse(document.getElementById("config").textContent); } catch (e) { return {}; } })();
const ARQUIVO_CNCA = CONFIG.cnca || null;
const VOLTAR = CONFIG.voltar || null;
const estado = {
  visao: "conformidade", ano: META.ano_mais_recente, filtro: "todos", metrica: "par", topo: "15",
  sub: "",                     // tipo de despesa (subfunção) no ranking; "" = todas
  sel: [], slot: new Map(),    // entes em comparação (a cor segue o ente)
  municipio: null, secao: "resumo", escola: null, rede: "todas", programa: null,
  ir: null,                    // âncora de destino dentro da visão (limitação, termo, card)
  filtrosAbertos: false,       // no celular, a barra de filtros começa recolhida
};
const VISOES = [
  { id: "conformidade", rotulo: "Conformidade", filtros: conformidadeFiltros, recorte: conformidadeRecorte, render: renderConformidade },
  { id: "panorama", rotulo: "Panorama do ES", filtros: panoramaFiltros, recorte: panoramaRecorte, render: renderPanorama },
  { id: "municipio", rotulo: "Município", filtros: municipioFiltros, recorte: municipioRecorte, render: renderMunicipio },
  { id: "programas", rotulo: "Programas federais", filtros: programasFiltros, recorte: programasRecorte, render: renderProgramas },
  { id: "metodologia", rotulo: "Como ler e metodologia", filtros: null, recorte: () => [h("strong", {}, "a documentação do painel")], render: renderMetodologia },
];

/* ------------------------------------------------------------------ endereço */
function hashDe(e) {
  const p = new URLSearchParams({ v: e.visao, ano: e.ano });
  if (e.visao === "conformidade" && e.filtro !== "todos") p.set("f", e.filtro);
  if (e.visao === "panorama") { if (e.metrica !== "par") p.set("ind", e.metrica); if (e.topo !== "15") p.set("topo", e.topo); if (e.sub) p.set("sub", e.sub); }
  if (e.municipio) p.set("m", e.municipio);
  if (e.visao === "municipio") {
    if (e.secao !== "resumo") p.set("s", e.secao);
    if (e.secao === "escolas" && e.escola) p.set("esc", e.escola);
    if (e.secao === "escolas" && e.rede !== "todas") p.set("rede", e.rede);
  }
  if (e.visao === "programas" && e.programa) p.set("p", e.programa);
  if (e.sel.length) p.set("e", e.sel.join(","));
  if (e.ir) p.set("ir", e.ir);
  return "#" + p.toString();
}
function lerHash(inicial) {
  const p = new URLSearchParams(location.hash.slice(1));
  let v = p.get("v");
  // Endereços do painel anterior continuam valendo (o roteiro da apresentação usa alguns).
  if (v === "fluxo") { v = "municipio"; if (!p.get("s")) p.set("s", "despesa"); }
  if (v === "escolas") { v = "municipio"; p.set("s", "escolas"); }
  if (v === "cnca") v = "programas";
  estado.visao = VISOES.some(x => x.id === v) ? v : "conformidade";
  const ano = parseInt(p.get("ano"), 10);
  estado.ano = ANOS.includes(ano) ? ano : META.ano_mais_recente;
  estado.filtro = FILTROS_CONFORMIDADE[p.get("f")] ? p.get("f") : p.get("alertas") === "1" ? "alerta" : "todos";
  estado.metrica = INDICADORES_PANORAMA[p.get("ind")] ? p.get("ind") : "par";
  estado.topo = ["15", "-15", "todos"].includes(p.get("topo")) ? p.get("topo") : "15";
  estado.sub = SUBFUNCOES_RANKING.has(p.get("sub")) ? p.get("sub") : "";
  const m = parseInt(p.get("m"), 10);
  if (ENTES.has(m)) estado.municipio = m;
  estado.secao = SECOES.some(s => s.id === p.get("s")) ? p.get("s") : "resumo";
  const esc = parseInt(p.get("esc"), 10);
  estado.escola = ESCOLAS.has(esc) ? esc : null;
  estado.rede = REDES[p.get("rede")] ? p.get("rede") : "todas";
  estado.programa = p.get("p") || null;
  estado.ir = p.get("ir") || null;
  if (p.has("e")) {
    const novos = p.get("e").split(",").map(Number).filter(c => ENTES.has(c));
    estado.sel.filter(c => !novos.includes(c)).forEach(remover);
    novos.forEach(adicionar);
    estado.sel = novos.filter(c => estado.sel.includes(c));
  } else if (!inicial) { estado.sel = []; estado.slot.clear(); }
}
/** Estado resultante de uma mudança, sem aplicá-la. Chaves curtas: v, m, s, esc, p, e, ir. */
function estadoCom(mudancas) {
  const e = { ...estado, sel: estado.sel.slice(), ir: null };
  for (const [k, v] of Object.entries(mudancas)) {
    if (k === "v") { e.visao = v; if (v === "municipio" && estado.visao !== "municipio" && !("s" in mudancas)) e.secao = "resumo"; }
    else if (k === "m") e.municipio = v;
    else if (k === "s") e.secao = v;
    else if (k === "esc") e.escola = v;
    else if (k === "p") e.programa = v;
    else if (k === "ir") e.ir = v;
    else if (k === "e") e.sel = String(v).split(",").map(Number).filter(c => ENTES.has(c));
    else e[k] = v;
  }
  return e;
}
const hrefPara = mudancas => hashDe(estadoCom(mudancas));
function linkPara(mudancas, texto, attrs) { return h("a", { href: hrefPara(mudancas), ...(attrs || {}) }, texto); }
const linkMunicipio = (cod, secao, texto) => linkPara({ v: "municipio", m: cod, s: secao || "resumo", esc: null }, texto || nomeEnte(cod));
/** Navegação que entra no histórico (o Voltar do navegador desfaz). */
function irPara(mudancas) { const novo = hrefPara(mudancas); if (novo === location.hash) render(); else location.hash = novo; }
/** Ajuste fino que NÃO entra no histórico: exercício, filtro, indicador, comparação. */
function ajustar(mudancas) { Object.assign(estado, mudancas); history.replaceState(null, "", hashDe(estado)); render(); }
function hrefCnca(params) {
  if (!ARQUIVO_CNCA) return null;
  const q = new URLSearchParams(Object.entries(params || {}).filter(([, v]) => v !== null && v !== undefined)).toString();
  return ARQUIVO_CNCA + (q ? "#" + q : "");
}
/** Link para o papel de trabalho do CNCA — ou nada, na versão em que ele não acompanha o painel. */
const linkCnca = (params, texto) => ARQUIVO_CNCA ? h("a", { href: hrefCnca(params) }, texto) : null;
const hrefGlossario = id => hrefPara({ v: "metodologia", ir: "g-" + id });
const hrefLimitacao = chave => hrefPara({ v: "metodologia", ir: idLimitacao(chave) });

/* ------------------------------------------------------------------ moldura */
function renderTrilha(v) {
  const ol = limpar($("#trilha"));
  ["Painel de Controle", "Áreas temáticas", "Educação"].forEach(t => ol.append(h("li", {}, t)));
  ol.append(h("li", {}, linkPara({ v: "conformidade", m: estado.municipio }, "Financiamento")));
  if (v.id === "municipio") ol.append(h("li", {}, linkPara({ v: "municipio", s: "resumo", esc: null }, "Município")),
    h("li", { "aria-current": "page" }, nomeEnte(estado.municipio)));
  else ol.append(h("li", { "aria-current": "page" }, v.rotulo));
}
function renderNavegacao(v) {
  limpar($("#nav-visoes")).append(...VISOES.map(x => h("li", {},
    h("a", { href: hrefPara({ v: x.id, esc: null }), "aria-current": x.id === v.id ? "page" : null }, x.rotulo))),
    ...[ARQUIVO_CNCA ? h("li", { class: "externo" }, linkCnca({}, "Evidências do CNCA ↗")) : null,
      VOLTAR ? h("li", { class: "externo" }, h("a", { href: VOLTAR.href }, "← " + VOLTAR.rotulo)) : null].filter(Boolean));
}
function renderContexto(v) {
  const barra = $("#contexto"), wrap = limpar($("#contexto-wrap"));
  barra.classList.toggle("aberta", estado.filtrosAbertos);
  wrap.append(h("p", { class: "recorte", "aria-live": "polite" }, "Você está vendo: ", h("strong", {}, v.rotulo), " · ", v.recorte()));
  if (!v.filtros) return;
  wrap.append(h("button", { type: "button", class: "leve alternar-filtros", "aria-expanded": String(estado.filtrosAbertos), "aria-controls": "controles",
    onclick: e => { estado.filtrosAbertos = !estado.filtrosAbertos; barra.classList.toggle("aberta", estado.filtrosAbertos);
      e.currentTarget.setAttribute("aria-expanded", String(estado.filtrosAbertos)); medirContexto(); } }, "Filtros"));
  const controles = h("div", { class: "controles", id: "controles", role: "group", "aria-label": "Filtros da visão " + v.rotulo });
  v.filtros(controles);
  wrap.append(controles);
}
function renderRodape() {
  const por = META.extraido_em_por_fonte || {}, ult = f => dataHoraBR((por[f] || {}).ultima);
  limpar($("#rodape")).append(
    h("p", {}, "Painel de apoio à auditoria do financiamento da educação nos municípios do Espírito Santo — protótipo, não integrado ao Painel de Controle do TCE-ES. " +
      "Dados processados em " + dataHoraBR(META.gerado_em) + (META.versao ? " (versão " + META.versao + ")" : "") + ". Última coleta: SICONFI " + ult("SICONFI") +
      " · SIOPE " + ult("SIOPE") + " · FNDE/CGU " + ult("FNDE") + " · TCE-ES " + ult("TCE-ES") + " · INEP " + ult("INEP") + "."),
    h("p", {}, linkPara({ v: "metodologia", ir: "como-ler" }, "Como ler"), " · ", linkPara({ v: "metodologia", ir: "glossario" }, "Glossário"), " · ",
      linkPara({ v: "metodologia", ir: "fontes" }, "Fontes e coleta"), " · ", linkPara({ v: "metodologia", ir: "limitacoes" }, "Limitações dos dados"),
      ARQUIVO_CNCA ? [" · ", linkCnca({}, "Evidências da fiscalização do CNCA ↗")] : null,
      VOLTAR ? [" · ", h("a", { href: VOLTAR.href }, "← " + VOLTAR.rotulo)] : null));
}

function render() {
  REDESENHOS.length = 0;
  esconderDica();
  const v = VISOES.find(x => x.id === estado.visao) || VISOES[0];
  document.title = (v.id === "municipio" ? nomeEnte(estado.municipio) + " — " : "") + v.rotulo + " · Financiamento da educação no ES";
  renderTrilha(v);
  renderNavegacao(v);
  renderContexto(v);
  v.render(limpar($("#conteudo")));
  renderRodape();
  medirContexto();
}
/** Depois de navegar: vai à âncora pedida, à escola aberta ou ao topo do conteúdo. */
function posicionar(antes) {
  const alvoPorId = id => { const el = document.getElementById(id); if (!el) return false;
    el.classList.add("alvo"); el.scrollIntoView({ block: "start" }); el.focus({ preventScroll: true }); return true; };
  if (estado.ir) {
    if (!alvoPorId(estado.ir)) alvoPorId(estado.ir.startsWith("lim-") ? "limitacoes" : "conteudo");
    estado.ir = null; history.replaceState(null, "", hashDe(estado));
    return;
  }
  if (estado.escola && (!antes || estado.escola !== antes.esc)) { const el = $("#detalhe-escola"); if (el) { el.scrollIntoView({ block: "start" }); el.focus({ preventScroll: true }); } return; }
  if (!antes) return;
  if (antes.esc && !estado.escola && estado.secao === "escolas") { const el = $("#card-escolas"); if (el) el.scrollIntoView({ block: "start" }); return; }
  if (antes.v !== estado.visao || antes.m !== estado.municipio || antes.s !== estado.secao) {
    const main = $("#conteudo");
    main.focus({ preventScroll: true });
    const topo = main.getBoundingClientRect().top + scrollY - ($("#contexto").offsetHeight || 0);
    if (scrollY > topo) scrollTo(0, topo);
  }
}

function iniciar() {
  lerHash(true);
  if (!new URLSearchParams(location.hash.slice(1)).has("e") && !estado.sel.length) {
    // Partida neutra: os três municípios mais populosos do exercício mais recente.
    MUNICIPIOS.map(e => LINHA.get(e.cod_ibge + "|" + META.ano_mais_recente)).filter(r => r && !nulo(r.populacao))
      .sort((a, b) => b.populacao - a.populacao).slice(0, 3).forEach(r => adicionar(r.cod_ibge));
  }
  if (!estado.municipio) estado.municipio = estado.sel.find(c => ehMunicipio(c)) || MUNICIPIOS[0].cod_ibge;
  const irInicial = estado.ir;
  history.replaceState(null, "", hashDe(estado));
  const ultimas = Object.values(META.extraido_em_por_fonte || {}).map(x => x.ultima).filter(Boolean).sort();
  $("#carimbo").textContent = "Dados coletados até " + dataBR(ultimas[ultimas.length - 1] || META.gerado_em) +
    " · exercícios " + ANOS[0] + "–" + ANOS[ANOS.length - 1] + " · " + META.n_municipios + " municípios e o Estado · valores em reais de cada ano, sem correção pela inflação.";
  limpar($("#como-ler-topo")).append(legendaEstados(),
    h("p", { class: "small" }, "Cada número tem o botão ", h("strong", {}, "ⓘ ver fonte"), ", que mostra de onde ele saiu. Siglas sublinhadas abrem a definição. ",
      h("a", { href: hrefPara({ v: "metodologia", ir: "como-ler" }) }, "Guia completo de leitura"), "."));
  for (const dlg of document.querySelectorAll("dialog")) dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });  // clique fora fecha
  estado.ir = irInicial;
  render();
  posicionar(null);
  addEventListener("hashchange", () => {
    const antes = { v: estado.visao, m: estado.municipio, s: estado.secao, esc: estado.escola };
    lerHash(false);
    render();
    posicionar(antes);
  });
  let largura = innerWidth, espera;
  addEventListener("resize", () => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      medirContexto();
      if (Math.abs(innerWidth - largura) < 2) return;  // só a altura mudou (barra do navegador no celular)
      largura = innerWidth;
      redesenharTudo();
    }, 200);
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
}

// `defer` não vale para <script> inline: DOMContentLoaded dispara depois do Chart.js
// (externo, adiado) — e dispara mesmo se o CDN falhar, caso em que os gráficos
// mostram o aviso e as tabelas seguem completas.
function arrancar() {
  try { iniciar(); } catch (e) {
    const main = $("#conteudo");
    limpar(main).append(h("div", { class: "callout descumpre", role: "alert" }, h("strong", {}, "O painel não pôde ser montado. "),
      "Recarregue a página; se o problema continuar, informe a equipe do painel com a mensagem: " + e.message));
    throw e;
  }
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", arrancar); else arrancar();
