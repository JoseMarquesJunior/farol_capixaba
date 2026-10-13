"use strict";
/* ============================================================================
   Visão 3 — Programas federais. Desenhada SÓ a partir de programas.yaml:
   acrescentar um programa é acrescentar um bloco de config, não código.
   ========================================================================== */

const ROT_ACESSO = { api: "API", manual: "somente manual", hibrido: "híbrido (API + manual)" };
const ROT_GRAN = { municipio: "município", escola: "escola", estado: "estado" };
const ROT_DISP = {
  sem_serie_automatizavel: "sem série temporal automatizável",
  api_indisponivel: "API/portal indisponível para consulta automática",
  sem_fonte_carregada: "nenhuma fonte carregada",
  automatico: "automático — coletado pelo ETL",
};

function programasKPIs(p) {
  const box = h("div", { class: "kpis tres" });
  const com = municipiosComRegistro(p);
  box.append(kpi("Municípios com algum campo verificado", com.size + " de " + MUNICIPIOS.length,
    com.size ? "os demais aparecem como “sem dado carregado”" : "nenhum registro manual neste programa ainda",
    { prog: true, nd: !com.size }));

  for (const c of p.campos) {
    const regs = todosRegistros(p.id, c.id).filter(r => r.verificado && (!c.serie || !r.automatico || r.ano === estado.ano));
    const municipios = new Set(regs.map(r => r.cod_ibge));
    if (c.kpi) {
      const ult = new Map();
      regs.forEach(r => { const a = ult.get(r.cod_ibge); if (!a || (r.ano || 0) >= (a.ano || 0)) ult.set(r.cod_ibge, r); });
      const positivos = [...ult.values()].filter(r => r.valor === c.kpi.valor).length;
      box.append(regs.length
        ? kpi(c.kpi.rotulo, positivos + " de " + ult.size, "entre os verificados · " + (MUNICIPIOS.length - ult.size) + " sem registro", { prog: true })
        : kpi(c.kpi.rotulo, "n/d", "0 de " + MUNICIPIOS.length + " verificados", { prog: true, nd: true }));
    } else if (c.tipo === "moeda") {
      const total = regs.reduce((s, r) => s + (r.valor || 0), 0);
      box.append(regs.length
        ? kpi(c.rotulo + (c.origem === "api" ? " — " + estado.ano : " (soma registrada)"), brlCompacto(total),
            municipios.size + " município(s)" + (c.origem === "api" ? " · automático" : " · " + regs.length + " registro(s)"), { prog: true })
        : kpi(c.rotulo, "n/d", "nenhum valor registrado — " + (ROT_DISP[c.disponibilidade] || "dado manual"), { prog: true, nd: true }));
    }
  }
  return box;
}

function cardIdentidade(p) {
  return h("article", { class: "card" },
    h("header", {}, h("h3", {}, p.nome), h("p", { class: "nota" }, p.descricao)),
    h("div", { class: "faixa" },
      h("span", { class: "item" }, "Repasse: " + p.fundo_repasse),
      h("span", { class: "item" }, "Acesso: " + (ROT_ACESSO[p.acesso] || p.acesso)),
      h("span", { class: "item" }, "Granularidade: " + (ROT_GRAN[p.granularidade] || p.granularidade))),
    h("p", { class: "nota" },
      h("span", { class: "badge api" }, "Automático"), " = coletado pelo ETL, com a consulta no “ver fonte”. ",
      h("span", { class: "badge manual" }, "Manual · verificado em <data>"), " = registro digitado por quem consultou a fonte. ",
      h("span", { class: "badge nada" }, "Sem dado carregado"), " = ninguém registrou o valor aqui (não significa zero, nem que a fonte não o tenha)."));
}

function cardIndicadorMeta(p) {
  const im = p.indicador_meta;
  const card = h("article", { class: "card" }, h("header", {}, h("h3", {}, "Indicador de meta"),
    h("p", { class: "nota" }, im.rotulo + (im.limiar_pontos ? " — limiar de " + im.limiar_pontos + " pontos na escala do Saeb" : "") + ". Fonte: " + im.fonte + ".")));
  if (im.nota_limiar) card.append(h("div", { class: "callout info" }, im.nota_limiar));
  card.append(h("div", { class: "rodape-card" }, h("strong", {}, "Limitação do indicador: "), im.nota_rodape));
  return card;
}

function cardCriterios(p) {
  if (!p.criterios_repasse) return null;
  return h("article", { class: "card" }, h("header", {}, h("h3", {}, "Critérios de repasse declarados")),
    h("ul", { class: "lista" }, p.criterios_repasse.declarados.map(c => h("li", {}, c))),
    h("div", { class: "callout" }, p.criterios_repasse.nota));
}

function cardOrigem(p) {
  return h("article", { class: "card largo" },
    h("header", {}, h("h3", {}, "De onde vem cada campo"), h("p", { class: "nota" }, "Origem de cada campo e, quando manual, o que foi tentado e por que não é automático.")),
    tabela([
      { rotulo: "Campo", valor: c => c.rotulo, render: c => h("strong", {}, c.rotulo) },
      { rotulo: "Origem", valor: c => c.origem, render: c => h("span", { class: c.origem === "api" ? "badge api" : "badge manual" }, c.origem === "api" ? "API" : "Manual") },
      { rotulo: "Fonte automática", valor: c => c.disponibilidade, render: c => ROT_DISP[c.disponibilidade] || "—" },
      { rotulo: "Nota", valor: c => c.nota_fonte, render: c => c.nota_fonte || "—" },
    ], p.campos, "Origem dos campos", { inteira: true }));
}

function cardTodosMunicipios(p) {
  const card = h("article", { class: "card largo" }, h("header", {},
    h("h3", {}, "Situação de cada município"),
    h("p", { class: "nota" }, "Clique no nome para abrir a ficha completa do município.")));
  const com = municipiosComRegistro(p);
  const linhas = municipiosPorNome().map(e => ({ e, temRegistro: com.has(e.cod_ibge) }));

  const filtro = h("select", { "aria-label": "Filtrar municípios", onchange: () => refazer() },
    h("option", { value: "todos" }, "Todos (" + MUNICIPIOS.length + ")"),
    h("option", { value: "com" }, "Com registro (" + com.size + ")"),
    h("option", { value: "sem" }, "Sem nenhum registro (" + (MUNICIPIOS.length - com.size) + ")"));
  const corpo = h("div");
  const cols = [{
    rotulo: "Município", valor: l => l.e.nome,
    render: l => h("button", { type: "button", class: "leve", style: "padding:0;min-height:auto;text-align:left",
      onclick: () => { estado.municipio = l.e.cod_ibge; irPara("municipio"); } }, l.e.nome),
  }].concat(p.campos.map(c => ({
    rotulo: c.rotulo,
    valor: l => registrosDe(p.id, c.id, l.e.cod_ibge).map(r => r.situacao === "sem_amostra" ? "sem amostra" : rotuloValor(c, r.valor)).join(" | "),
    render: l => celulaCampo(p, c, l.e.cod_ibge),
  })));
  function refazer() {
    const f = filtro.value;
    const sel = linhas.filter(l => f === "todos" || (f === "com" ? l.temRegistro : !l.temRegistro));
    limpar(corpo).append(tabela(cols, sel, "Municípios no programa " + p.nome),
      botaoCSV("programa_" + p.id + ".csv", cols, sel));
  }
  card.append(h("div", { style: "max-width:260px;margin:6px 0" }, campo("Filtrar", filtro)), corpo);
  refazer();
  return card;
}

function cardReferencias(p) {
  return h("article", { class: "card largo" },
    h("header", {}, h("h3", {}, "Referências e fontes do programa")),
    h("ul", { class: "lista" }, (p.referencias || []).map(r =>
      h("li", {}, h("a", { href: r.url, target: "_blank", rel: "noopener noreferrer" }, r.rotulo), r.nota ? " — " + r.nota : ""))),
    h("div", { class: "rodape-card" }, "Todo campo marcado como manual foi digitado a partir da fonte citada no próprio registro, com a data em que foi consultada. Para registrar: dados_manuais.yaml → programas → " + p.id + "."));
}

function renderProgramas(destino) {
  if (!D.programas.length) { destino.append(h("p", { class: "muted" }, "Nenhum programa configurado em programas.yaml.")); return; }
  if (!estado.programa || !D.programas.some(p => p.id === estado.programa)) estado.programa = D.programas[0].id;
  const p = D.programas.find(x => x.id === estado.programa);

  if (D.programas.length > 1) {
    destino.append(h("div", { class: "abas", role: "tablist", "aria-label": "Programas" }, D.programas.map(x =>
      h("button", { type: "button", role: "tab", "aria-selected": String(x.id === estado.programa),
        onclick: () => { estado.programa = x.id; render(); } }, x.nome.split(" — ")[0]))));
  }
  destino.append(h("div", { class: "linha", style: "max-width:260px" },
    campo("Exercício", seletorAno("f-ano-prog", estado.ano, v => { estado.ano = v; render(); }))));
  destino.append(programasKPIs(p));
  const modulo = p.modulo_automatico === "cnca" && typeof cardsCnca === "function" ? cardsCnca(p) : [];
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" },
    cardIdentidade(p), cardIndicadorMeta(p), ...modulo, cardCriterios(p), cardOrigem(p), cardTodosMunicipios(p), cardReferencias(p))));
}
