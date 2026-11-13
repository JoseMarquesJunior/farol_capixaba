"use strict";
/* ============================================================================
   Orquestra o painel simplificado: estado (município e exercício no endereço),
   menu lateral fixo com as seções da página e o conteúdo contínuo — tudo de um
   município numa rolagem só, sem abas.

   O endereço guarda o estado (#m=…&ano=…&ir=…): qualquer tela pode ser
   compartilhada. Trocar de município entra no histórico (o Voltar desfaz);
   trocar o exercício só substitui o endereço. Clicar numa seção do menu rola
   até ela, sem remontar a página.
   ========================================================================== */

const estado = { municipio: null, ano: META.ano_mais_recente, ir: null };

const SECOES_PAGINA = [
  { id: "sec-resumo", rotulo: "Resumo", titulo: true, render: secaoResumo },
  { id: "sec-receita", rotulo: "Receita", titulo: true, render: secaoReceita },
  { id: "sec-despesa", rotulo: "Despesa", titulo: true, render: secaoDespesa },
  { id: "sec-nivel3", rotulo: "Quem recebeu e o que foi comprado", titulo: true, render: secaoNivel3 },
];

/* ------------------------------------------------------------------ endereço */
function hashDe(e) {
  const p = new URLSearchParams();
  if (e.municipio) p.set("m", e.municipio);
  if (e.ano !== META.ano_mais_recente) p.set("ano", e.ano);
  if (e.ir) p.set("ir", e.ir);
  return "#" + p.toString();
}
function lerHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  const m = parseInt(p.get("m"), 10);
  if (ENTES.has(m) && ehMunicipio(m)) estado.municipio = m;
  const ano = parseInt(p.get("ano"), 10);
  estado.ano = ANOS.includes(ano) ? ano : META.ano_mais_recente;
  estado.ir = p.get("ir") || null;
}
/** Estado resultante de uma mudança, sem aplicá-la. Chaves: m, ano, ir. */
function estadoCom(mudancas) {
  const e = { ...estado, ir: null };
  if ("m" in mudancas) e.municipio = mudancas.m;
  if ("ano" in mudancas) e.ano = mudancas.ano;
  if ("ir" in mudancas) e.ir = mudancas.ir;
  return e;
}
const hrefPara = mudancas => hashDe(estadoCom(mudancas));
function linkPara(mudancas, texto, attrs) { return h("a", { href: hrefPara(mudancas), ...(attrs || {}) }, texto); }
/** Navegação que entra no histórico (o Voltar do navegador desfaz). */
function irPara(mudancas) { const novo = hrefPara(mudancas); if (novo === location.hash) render(); else location.hash = novo; }
/** Ajuste fino que NÃO entra no histórico: o exercício. */
function ajustar(mudancas) {
  Object.assign(estado, mudancas);
  history.replaceState(null, "", hashDe(estado));
  const rolagem = scrollY;
  render();
  scrollTo(0, rolagem);
}

/* ------------------------------------------------------------------ menu */
function renderMenu() {
  const seletores = limpar($("#seletores"));
  seletores.append(
    campo("Município", seletorEnte("f-mun", estado.municipio, cod => irPara({ m: cod }))),
    campo("Exercício", seletorAno("f-ano", estado.ano, v => ajustar({ ano: v }))));
  limpar($("#nav-secoes ul")).append(...SECOES_PAGINA.map(s => h("li", {},
    h("a", { href: hrefPara({ ir: s.id }), "data-sec": s.id }, s.rotulo))));
  // O seletor do painel novo marca o "mais recente"; aqui ele é o último completo, e o corrente é parcial.
  for (const o of $("#f-ano").options) {
    const a = +o.value;
    if (a === ANO_PARCIAL) o.textContent = a + " (parcial)";
    else if (a === META.ano_mais_recente && ANO_PARCIAL) o.textContent = a + " (último completo)";
  }
}
/** Marca no menu a seção visível durante a rolagem. */
let observadorSecoes = null;
function observarSecoes() {
  if (observadorSecoes) observadorSecoes.disconnect();
  const links = SECOES_PAGINA.map(s => $('#nav-secoes a[data-sec="' + s.id + '"]')).filter(Boolean);
  const marcar = id => links.forEach(a => a.setAttribute("aria-current", a.dataset.sec === id ? "true" : "false"));
  if (typeof IntersectionObserver === "undefined") { marcar(SECOES_PAGINA[0].id); return; }
  const visiveis = new Map();
  observadorSecoes = new IntersectionObserver(entradas => {
    for (const e of entradas) visiveis.set(e.target.id, e.isIntersecting);
    const primeira = SECOES_PAGINA.find(s => visiveis.get(s.id));
    if (primeira) marcar(primeira.id);
  }, { rootMargin: "-10% 0px -55% 0px" });
  for (const s of SECOES_PAGINA) { const el = document.getElementById(s.id); if (el) observadorSecoes.observe(el); }
}
/** No celular o menu gruda no topo: a altura dele vira a folga das âncoras. */
function medirMenu() {
  const menu = $(".menu-lateral");
  const fixoNoTopo = matchMedia("(max-width: 900px)").matches;
  document.documentElement.style.setProperty("--altura-contexto", (fixoNoTopo && menu ? menu.offsetHeight : 0) + "px");
}

/* ------------------------------------------------------------------ página */
function render() {
  REDESENHOS.length = 0;
  esconderDica();
  if (!ENTES.has(estado.municipio)) estado.municipio = MUNICIPIOS[0].cod_ibge;
  const cod = estado.municipio, ano = estado.ano, r = LINHA.get(cod + "|" + ano) || {};
  document.title = nomeEnte(cod) + " · Financiamento da educação no ES — simplificado";
  renderMenu();
  const main = limpar($("#conteudo"));
  main.append(h("div", { class: "cab-visao" },
    h("h2", {}, nomeEnte(cod), h("span", { class: "muted small" }, "  código IBGE " + cod + " · exercício " + rotuloAno(cod, ano)))));
  if (r.status_despesa !== "ok")
    main.append(h("div", { class: "callout sinal" }, h("strong", {}, "Sem dado de despesa em " + ano + ". "), "O TCE-ES não publicou a despesa deste município no exercício. Os campos ficam vazios — nada é estimado."));
  else if (ehParcial(ano) && r.ultimo_mes)
    main.append(h("div", { class: "callout" }, h("strong", {}, "Exercício em andamento. "),
      "Valores de janeiro a " + MES_EXTENSO[r.ultimo_mes - 1] + " de " + ano + ", com os meses que o município já enviou ao TCE-ES. " +
      "A variação compara com o mesmo período de " + (ano - 1) + ", e o ranking, só com os municípios que enviaram os mesmos meses."));
  for (const s of SECOES_PAGINA) {
    const secao = h("section", { id: s.id, class: "secao-pagina" });
    if (s.titulo) secao.append(h("h2", { class: "titulo-secao" }, s.rotulo));
    s.render(secao, cod, ano, r);
    main.append(secao);
  }
  observarSecoes();
  medirMenu();
}

/** Depois de navegar: vai à âncora pedida ou ao topo do conteúdo. */
function posicionar(antes) {
  if (estado.ir) {
    const el = document.getElementById(estado.ir);
    if (el) { el.classList.add("alvo"); el.scrollIntoView({ block: "start" }); if (el.tabIndex >= 0 || el.hasAttribute("tabindex")) el.focus({ preventScroll: true }); }
    estado.ir = null;
    history.replaceState(null, "", hashDe(estado));
    return;
  }
  if (antes && antes.m !== estado.municipio) {
    const main = $("#conteudo");
    main.focus({ preventScroll: true });
    scrollTo(0, main.getBoundingClientRect().top + scrollY - 8);
  }
}

function iniciar() {
  lerHash();
  if (!estado.municipio) {
    // Partida neutra: a maior rede municipal (matrículas) do último exercício completo.
    const maior = MUNICIPIOS.map(e => LINHA.get(e.cod_ibge + "|" + META.ano_mais_recente)).filter(x => x && !nulo(x.tcees_alunos))
      .sort((a, b) => b.tcees_alunos - a.tcees_alunos)[0];
    estado.municipio = maior ? maior.cod_ibge : MUNICIPIOS[0].cod_ibge;
  }
  const irInicial = estado.ir;
  history.replaceState(null, "", hashDe(estado));
  $("#carimbo").textContent = "Última atualização dos dados: " + dataBR(META.gerado_em) + ".";
  limpar($("#como-ler-topo")).append(
    h("p", { class: "small" }, "Cada número tem o botão ", h("strong", {}, "ⓘ ver fonte"), ", que mostra de onde ele saiu. Siglas sublinhadas abrem a definição. ",
      "A ressalva de cada gráfico fica em \"Como é calculado\"."),
    h("p", { class: "small" }, semDado("sem dado"), " quer dizer que a fonte não publicou o valor — nunca que ele é zero."));
  for (const dlg of document.querySelectorAll("dialog")) dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });  // clique fora fecha
  estado.ir = irInicial;
  render();
  posicionar(null);
  addEventListener("hashchange", () => {
    const antes = { m: estado.municipio, ano: estado.ano };
    lerHash();
    if (antes.m !== estado.municipio || antes.ano !== estado.ano) render();
    posicionar(antes);
  });
  let largura = innerWidth, espera;
  addEventListener("resize", () => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      medirMenu();
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
