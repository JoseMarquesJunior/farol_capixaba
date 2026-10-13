"use strict";
/* ============================================================================
   Programas federais. Desenhada SÓ a partir de programas.yaml: acrescentar um
   programa é acrescentar um bloco de config, não código.

   O que mudou: o dado automático (repasse, ICA) e o registro manual (adesão,
   articuladores) são contados À PARTE. Antes a aba dizia "78/78 verificados"
   enquanto o KPI dizia "adesão: 0 de 78 verificados" — o mesmo verbo para duas
   coisas diferentes.
   ========================================================================== */

const ROT_ACESSO = { api: "automático (API)", manual: "somente manual", hibrido: "misto (automático + manual)" };
const ROT_GRAN = { municipio: "município", escola: "escola", estado: "estado" };
const ROT_DISP = {
  sem_serie_automatizavel: "sem série automatizável",
  api_indisponivel: "sem consulta automática disponível",
  sem_fonte_carregada: "nenhuma fonte carregada",
  automatico: "automático — coletado pelo painel",
};
const programaAtual = () => D.programas.find(x => x.id === estado.programa) || D.programas[0];

function programasFiltros(destino) {
  if (D.programas.length > 1) {
    const s = h("select", { id: "f-programa", onchange: e => irPara({ p: e.target.value }) }, D.programas.map(p => h("option", { value: p.id }, p.nome.split(" — ")[0])));
    s.value = (programaAtual() || {}).id;
    destino.append(campo("Programa", s));
  }
  destino.append(campo("Exercício", seletorAno("f-ano", estado.ano, v => ajustar({ ano: v }))));
}
const programasRecorte = () => [h("strong", {}, ((programaAtual() || {}).nome || "").split(" — ")[0]), " · exercício ", h("strong", {}, String(estado.ano)), " · os 78 municípios"];

/** Um campo de programa num município: o registro mais recente em destaque, os anteriores recolhidos. */
function celulaCampo(p, campo_, cod) {
  const regs = registrosDe(p.id, campo_.id, cod);
  if (!regs.length) return h("span", { class: "badge nada" }, campo_.origem === "api" ? "sem dado na fonte" : "sem registro");
  const linha = r => h("div", { class: "celula-reg" },
    r.situacao === "sem_amostra" ? h("strong", {}, "sem amostra suficiente") : r.situacao === "sem_dado" ? h("strong", {}, "a fonte não publicou o valor")
      : h("strong", {}, rotuloValor(campo_, r.valor)), campo_.serie && r.ano ? " (" + r.ano + ")" : "", " ", badgeRegistro(r),
    r.automatico && r.q && r.situacao !== "sem_dado" ? [" ", botaoFonte(campo_.rotulo + " — " + nomeEnte(cod) + ", " + r.ano,
      () => [{ indicador: r.indicador || "cnca_pdde", ano: r.ano, detalhe: r.detalhe || "000C", q: r.q, valor: rotuloValor(campo_, r.valor) }], true)] : null,
    h("span", { class: "fonte" }, r.fonte + (r.observacao ? " — " + r.observacao : "")));
  const [primeiro, ...resto] = regs;
  return h("div", {}, linha(primeiro), resto.length ? h("details", {}, h("summary", { class: "small" }, resto.length + " registro(s) anterior(es)"), resto.map(linha)) : null);
}
function cardProgramasDoMunicipio(cod) {
  const card = h("article", { class: "card largo", id: "card-programas-mun" }, cabecalho("Programas federais em " + nomeEnte(cod), {
    simples: "O que se sabe sobre a participação do município nos programas federais acompanhados. Campo automático vem da fonte oficial; campo manual depende de alguém registrar o que consultou.",
    nota: "\"sem registro\" significa que ninguém registrou o valor ainda — não que seja zero." }));
  if (!D.programas.length) { card.append(h("p", { class: "muted" }, "Nenhum programa configurado.")); return card; }
  for (const p of D.programas) {
    card.append(h("h4", {}, p.nome), tabela([
      { rotulo: "Campo", valor: l => l.rotulo, render: l => h("span", {}, h("strong", {}, l.rotulo), h("br"), h("span", { class: "nota" }, l.origem === "api" ? "automático" : "registro manual")) },
      { rotulo: "Situação", valor: () => "", ordenavel: false, render: l => celulaCampo(p, l, cod) },
    ], p.campos, "Programa " + p.nome + " em " + nomeEnte(cod), { inicio: 0, busca: false, fixarPrimeira: false }));
  }
  card.append(h("p", { class: "rodape-card" }, linkPara({ v: "programas" }, "Ver o programa nos 78 municípios")));
  return card;
}

function programasKPIs(p) {
  const box = h("div", { class: "kpis" });
  const auto = municipiosComRegistro(p, "api"), manual = municipiosComRegistro(p, "manual");
  box.append(kpi("Municípios com dado automático", auto.size + " de " + MUNICIPIOS.length, "repasse e indicadores coletados das fontes oficiais", { nd: !auto.size }));
  box.append(kpi("Municípios com registro manual", manual.size + " de " + MUNICIPIOS.length,
    manual.size ? "os demais aparecem como \"sem registro\"" : "nenhum registro manual ainda (adesão, articuladores)", { nd: !manual.size }));
  for (const c of p.campos) {
    const regs = todosRegistros(p.id, c.id).filter(r => r.verificado && (!c.serie || !r.automatico || r.ano === estado.ano));
    const municipios = new Set(regs.map(r => r.cod_ibge));
    if (c.kpi) {
      const ult = new Map();
      regs.forEach(r => { const a = ult.get(r.cod_ibge); if (!a || (r.ano || 0) >= (a.ano || 0)) ult.set(r.cod_ibge, r); });
      const positivos = [...ult.values()].filter(r => r.valor === c.kpi.valor).length;
      box.append(regs.length ? kpi(c.kpi.rotulo, positivos + " de " + ult.size, "entre os " + ult.size + " com registro · " + (MUNICIPIOS.length - ult.size) + " sem registro")
        : kpi(c.kpi.rotulo, "sem registro", "0 de " + MUNICIPIOS.length + " registrados · " + (c.origem === "api" ? "fonte automática" : "registro manual pendente"), { nd: true }));
    } else if (c.tipo === "moeda") {
      const total = regs.reduce((t, r) => t + (r.valor || 0), 0);
      box.append(regs.length ? kpi(c.rotulo + (c.origem === "api" ? " — " + estado.ano : ""), brlCompacto(total), municipios.size + " município(s)" + (c.origem === "api" ? " · automático" : " · registro manual"))
        : kpi(c.rotulo, "sem registro", ROT_DISP[c.disponibilidade] || "registro manual pendente", { nd: true }));
    }
  }
  return box;
}
function cardIdentidade(p) {
  return h("article", { class: "card", id: "card-programa" }, cabecalho(p.nome, { simples: p.descricao }),
    h("div", { class: "faixa" },
      h("span", { class: "item" }, "Repasse: " + p.fundo_repasse), h("span", { class: "item" }, "Acesso ao dado: " + (ROT_ACESSO[p.acesso] || p.acesso)),
      h("span", { class: "item" }, "Granularidade: " + (ROT_GRAN[p.granularidade] || p.granularidade))),
    h("p", { class: "nota" }, h("span", { class: "badge api" }, "automático"), " = coletado pelo painel, com a consulta no \"ver fonte\". ",
      h("span", { class: "badge manual" }, "registro manual"), " = digitado por quem consultou a fonte, com a data. ",
      h("span", { class: "badge nada" }, "sem registro"), " = ninguém registrou o valor ainda (não é zero)."));
}
function cardIndicadorMeta(p) {
  const im = p.indicador_meta;
  if (!im) return null;
  const card = h("article", { class: "card", id: "card-meta" }, cabecalho("Indicador de meta", {
    simples: im.rotulo + (im.limiar_pontos ? " — limiar de " + im.limiar_pontos + " pontos na escala do Saeb" : "") + ". Fonte: " + im.fonte + "." }));
  if (im.nota_limiar) card.append(h("div", { class: "callout info" }, im.nota_limiar));
  if (im.nota_rodape) card.append(h("div", { class: "rodape-card" }, h("strong", {}, "Limitação do indicador: "), im.nota_rodape));
  return card;
}
function cardCriterios(p) {
  if (!p.criterios_repasse) return null;
  return h("article", { class: "card", id: "card-criterios" }, cabecalho("Critérios de repasse declarados"),
    h("ul", { class: "lista" }, p.criterios_repasse.declarados.map(c => h("li", {}, c))),
    h("div", { class: "callout" }, p.criterios_repasse.nota));
}
function cardOrigemCampos(p) {
  return h("article", { class: "card largo", id: "card-origem-campos" }, cabecalho("De onde vem cada campo", {
    simples: "Para cada informação do programa: se vem automaticamente de uma fonte oficial ou se depende de registro manual — e, quando manual, por quê." }),
    tabela([
      { rotulo: "Campo", valor: c => c.rotulo, render: c => h("strong", {}, c.rotulo) },
      { rotulo: "Origem", valor: c => c.origem === "api" ? "automático" : "registro manual", render: c => h("span", { class: c.origem === "api" ? "badge api" : "badge manual" }, c.origem === "api" ? "automático" : "registro manual") },
      { rotulo: "Disponibilidade", valor: c => ROT_DISP[c.disponibilidade] || "—" },
      { rotulo: "Nota", valor: c => c.nota_fonte || "—" },
    ], p.campos, "Origem dos campos", { inicio: 0, busca: false, fixarPrimeira: false }));
}
function cardTodosMunicipios(p) {
  const card = h("article", { class: "card largo", id: "card-situacao-programa" }, cabecalho("Situação de cada município", {
    simples: "Um município por linha, com o registro mais recente de cada campo; os anos anteriores ficam recolhidos. Clique no nome para abrir o dossiê do município." }));
  const com = municipiosComRegistro(p);
  const cols = [{ rotulo: "Município", valor: l => l.nome, classe: "col-nome", render: l => linkMunicipio(l.cod_ibge, "programas", l.nome) }]
    .concat(p.campos.map(c => ({ rotulo: c.rotulo, ordenavel: false,
      valor: l => registrosDe(p.id, c.id, l.cod_ibge).map(r => r.situacao === "sem_amostra" ? "sem amostra" : rotuloValor(c, r.valor) + (r.ano ? " (" + r.ano + ")" : "")).join(" | "),
      render: l => celulaCampo(p, c, l.cod_ibge) })));
  card.append(h("p", { class: "nota" }, com.size + " de " + MUNICIPIOS.length + " municípios com algum campo preenchido."),
    tabela(cols, municipiosPorNome(), "Municípios no programa " + p.nome, { busca: "Buscar município…", csv: "programa_" + p.id + ".csv", inicio: 10 }));
  return card;
}
function cardReferencias(p) {
  return h("article", { class: "card largo", id: "card-referencias" }, cabecalho("Referências e fontes do programa"),
    h("ul", { class: "lista" }, (p.referencias || []).map(r => h("li", {}, h("a", { href: r.url, target: "_blank", rel: "noopener noreferrer" }, r.rotulo + " ↗"), r.nota ? " — " + r.nota : ""))),
    h("div", { class: "rodape-card" }, "Todo campo de registro manual foi digitado a partir da fonte citada no próprio registro, com a data em que ela foi consultada."));
}

function renderProgramas(destino) {
  if (!D.programas.length) { destino.append(h("p", { class: "muted" }, "Nenhum programa configurado.")); return; }
  const p = programaAtual();
  estado.programa = p.id;
  destino.append(h("div", { class: "cab-visao" }, h("h2", {}, "Programas federais — " + p.nome.split(" — ")[0] + ", " + estado.ano),
    h("p", {}, "Os repasses e indicadores do programa nos 78 municípios, e o que ainda depende de registro manual.",
      ARQUIVO_CNCA ? [" O papel de trabalho da fiscalização do CNCA fica num ", linkCnca({}, "arquivo separado ↗"), "."] : null)));
  destino.append(programasKPIs(p));
  const modulo = p.modulo_automatico === "cnca" ? cardsCnca() : [];
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" },
    cardIdentidade(p), cardIndicadorMeta(p), ...modulo, cardCriterios(p), cardOrigemCampos(p), cardTodosMunicipios(p), cardReferencias(p))));
}
