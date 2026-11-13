"use strict";
/* ============================================================================
   Componentes das três visões de rede (auditoria de UX de 26/10/2026):
   o cartão da figura com a sua barra de ferramentas, a busca com sugestões,
   o alternador, o anúncio para leitor de tela, as perguntas de partida e os
   links de navegação — que são <a href>, não botões: abrem em nova aba,
   entram no histórico e o leitor de tela os anuncia como link.
   ========================================================================== */

/** Estado só da interface (não vai para o endereço). */
const UI = { tiposAberto: false, vistas: new Map() };

/** Mesmas regras do irPara: trocar de visão sem dizer a seleção limpa a seleção. */
function mudancasNormalizadas(m) {
  const x = { ...m };
  if (x.visao && x.visao !== estado.visao && !("sel" in x)) x.sel = null;
  if (!("ir" in x)) x.ir = null;
  return x;
}
function hrefPara(mudancas) { return hashDe(estadoCom(mudancasNormalizadas(mudancas))); }
function linkPara(mudancas, filhos, attrs) {
  return h("a", { href: hrefPara(mudancas), ...(attrs || {}) }, filhos);
}

/** Anúncio curto para leitor de tela (a seleção), no lugar de ler o painel inteiro. */
function anunciar(texto) {
  const r = $("#anuncio");
  if (!r) return;
  r.textContent = "";
  setTimeout(() => { r.textContent = texto; }, 30);
}

/** Alternador de duas ou três opções: rádios nativos com cara de segmentos. */
function alternador(rotulo, valor, opcoes, aoMudar) {
  const nome = "alt-" + Math.random().toString(36).slice(2, 8);
  return h("fieldset", { class: "alternador" }, h("legend", {}, rotulo),
    h("div", { class: "segmentos" }, opcoes.map(([v, r, titulo]) => h("label", { title: titulo || null },
      h("input", { type: "radio", name: nome, value: String(v), checked: String(valor) === String(v) ? true : null, onchange: () => aoMudar(v) }),
      h("span", {}, r)))));
}

/** Busca com sugestões (combobox ARIA): parte do nome, sem acento, ou dígitos do CNPJ. */
function campoBuscaRede(itens, rotulo, dica) {
  const id = "busca-" + Math.random().toString(36).slice(2, 7);
  const indice = itens.map(it => ({ ...it, chave: semAcento(it.texto), digitos: String(it.digitos || "").replace(/\D/g, "") }));
  const lista = h("ul", { id: id + "-l", role: "listbox", class: "busca-lista", hidden: true, "aria-label": "Sugestões" });
  const entrada = h("input", { type: "search", id: id + "-i", role: "combobox", "aria-autocomplete": "list", "aria-expanded": "false",
    "aria-controls": id + "-l", placeholder: dica || "Buscar…", autocomplete: "off", spellcheck: "false" });
  let atuais = [], ativo = -1;
  const fechar = () => { lista.hidden = true; entrada.setAttribute("aria-expanded", "false"); entrada.removeAttribute("aria-activedescendant"); ativo = -1; };
  const marcar = i => {
    ativo = i;
    [...lista.children].forEach((li, j) => li.setAttribute("aria-selected", String(j === i)));
    if (i >= 0) entrada.setAttribute("aria-activedescendant", id + "-o" + i); else entrada.removeAttribute("aria-activedescendant");
  };
  const escolher = it => { entrada.value = it.texto; fechar(); setTimeout(() => irPara({ sel: it.sel, ...(it.extra || {}) }), 0); };
  function abrir() {
    const q = semAcento(entrada.value.trim());
    const dig = entrada.value.replace(/\D/g, "");
    if (q.length < 2 && dig.length < 3) { fechar(); return; }
    const palavras = q.split(/\s+/).filter(Boolean);
    const comeca = [], contem = [];
    for (const it of indice) {
      const ok = (dig.length >= 3 && it.digitos.includes(dig)) || palavras.every(p => it.chave.includes(p));
      if (!ok) continue;
      (it.chave.startsWith(palavras[0] || "") ? comeca : contem).push(it);
      if (comeca.length >= 8) break;
    }
    atuais = comeca.concat(contem).slice(0, 8);
    limpar(lista);
    if (!atuais.length) lista.append(h("li", { class: "vazio", role: "option", "aria-disabled": "true" }, "Nada encontrado."));
    atuais.forEach((it, i) => lista.append(h("li", { id: id + "-o" + i, role: "option", "aria-selected": "false",
      onmousedown: e => e.preventDefault(), onclick: () => escolher(it) }, h("span", { class: "nome" }, it.texto), it.sub ? h("span", { class: "sub" }, it.sub) : null)));
    lista.hidden = false; entrada.setAttribute("aria-expanded", "true"); marcar(-1);
  }
  entrada.addEventListener("input", abrir);
  entrada.addEventListener("keydown", e => {
    if (e.key === "ArrowDown") { e.preventDefault(); if (lista.hidden) abrir(); marcar(Math.min(atuais.length - 1, ativo + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); marcar(Math.max(-1, ativo - 1)); }
    else if (e.key === "Enter") { const it = atuais[ativo >= 0 ? ativo : 0]; if (it && !lista.hidden) { e.preventDefault(); escolher(it); } }
    else if (e.key === "Escape") { if (!lista.hidden) { e.preventDefault(); fechar(); } }
  });
  entrada.addEventListener("blur", () => setTimeout(fechar, 120));
  return h("div", { class: "campo campo-busca" }, h("label", { for: id + "-i" }, rotulo), h("div", { class: "busca-caixa" }, entrada, lista));
}

/** O cartão da figura: barra de ferramentas, figura + painel lateral, legenda e notas. */
function cartaoGrafo({ id, ferramentas, legenda, notas }) {
  const tela = h("div", { class: "rede-tela" });
  const lado = h("aside", { class: "rede-lado", tabindex: "-1", "aria-label": "Detalhe da seleção" });
  const faixa = h("div", { class: "rede-faixa", hidden: true });
  const card = h("article", { class: "card rede-card", id },
    h("div", { class: "rede-ferramentas", role: "group", "aria-label": "Ferramentas da figura" }, ferramentas),
    h("div", { class: "rede-corpo" }, tela, lado),
    legenda, notas || null);
  return { card, tela, lado, faixa };
}
/** No celular o painel fica abaixo da figura: uma faixa sobre a figura diz o que foi selecionado. */
function mostrarFaixa(c, titulo, detalhe) {
  limpar(c.faixa);
  if (!titulo) { c.faixa.hidden = true; return; }
  c.faixa.hidden = false;
  c.faixa.append(h("div", { class: "faixa-txt" }, h("strong", {}, titulo), detalhe ? h("span", {}, detalhe) : null),
    h("button", { type: "button", class: "leve", onclick: () => { c.lado.scrollIntoView({ behavior: MOVIMENTO_REDUZIDO.matches ? "auto" : "smooth", block: "start" }); c.lado.focus({ preventScroll: true }); } }, "Ver detalhes ↓"),
    linkPara({ sel: null }, "×", { class: "faixa-fechar", "aria-label": "Limpar seleção", title: "Limpar seleção" }));
}
/** Vista (zoom) da figura guardada por visão + disposição, para um filtro não desfazer o enquadramento. */
function guardarVista(chave, grafo) { if (grafo) UI.vistas.set(chave, grafo.vista()); }
function restaurarVista(chave, grafo) { const v = UI.vistas.get(chave); if (v) grafo.restaurar(v); return !!v; }

/** Perguntas de partida: cada uma é um link para o recorte que a responde. */
const PERGUNTAS = [
  { texto: "O que estas redes mostram, em poucas linhas?", m: { visao: "insights" } },
  { texto: "Quem leva o transporte escolar a mais municípios?", m: { visao: "fornecedores", mercado: "transporte", ano: null, fonte: null, min: 2 } },
  { texto: "Onde a merenda depende de um fornecedor só?", m: { visao: "fornecedores", mercado: "alimentacao", ano: null, fonte: null, min: 2, ir: "concentracao" } },
  { texto: "Quem vende material didático para o estado inteiro?", m: { visao: "fornecedores", mercado: "didatico", ano: null, fonte: null, min: 2 } },
  { texto: "Quem recebe dinheiro do FNDE (merenda, transporte, salário-educação)?", m: { visao: "fornecedores", mercado: "todos", fonte: FONTES.findIndex(f => f.id === "fnde"), min: 2 } },
  { texto: "Os mercados seguem as regiões do IBGE?", m: { visao: "municipios", mercado: "todos" } },
  { texto: "Que construtoras têm obra parada em vários municípios?", m: { visao: "obras", sit: "paradas", minObras: 2 } },
];
function listaPerguntas() {
  return h("div", { class: "perguntas" }, h("h4", {}, "Comece por uma pergunta"),
    h("ul", {}, PERGUNTAS.map(p => h("li", {}, linkPara({ ...p.m, sel: null }, p.texto)))));
}

/** Resumo do recorte no painel lateral: valor em destaque, rótulo e detalhe. */
function resumoLado(itens) {
  return h("dl", { class: "resumo-lado" }, itens.filter(Boolean).map(([rot, val, det, extra]) =>
    h("div", { class: "item" + (extra && extra.classe ? " " + extra.classe : "") }, h("dt", {}, rot), h("dd", {}, h("span", { class: "val" }, val), det ? h("span", { class: "det" }, det) : null))));
}
/** Botão discreto que leva o foco direto à figura (pula os filtros e o texto). */
function botaoIrParaFigura(obterGrafo) {
  return h("button", { type: "button", class: "pular-figura", onclick: () => { const g = obterGrafo(); if (g) { g.canvas.scrollIntoView({ block: "center" }); g.canvas.focus(); } } }, "Ir para a figura");
}
