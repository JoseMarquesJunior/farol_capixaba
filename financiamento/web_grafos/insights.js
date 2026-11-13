"use strict";
/* ============================================================================
   Visão "Insights": observações sobre as três redes.

   Os FATOS são calculados no ETL (etl/insights.py), de forma determinística, do
   mesmo dado das figuras. A REDAÇÃO, quando existe, foi feita uma vez por um
   modelo Claude a partir só desses fatos — e cada número do texto foi conferido
   contra os fatos citados antes de vir para cá. A página não chama nenhuma API.
   ========================================================================== */
const INS = DADOS.insights || { meta: {}, fatos: [], insights: [], recusados: [] };
const FATO = new Map(INS.fatos.map(f => [f.id, f]));
const TEMAS = { contexto: "Contexto", comunidades: "Comunidades e regiões", concentracao: "Concentração", alcance: "Alcance dos fornecedores",
  crescimento: "Crescimento e novos fornecedores", origem: "Origem do recurso", obras: "Obras" };
const ROTULO_TIPO_INS = { sinal: "sinal a verificar", padrao: "padrão", contexto: "contexto" };

function chipTipoInsight(tipo) {
  if (tipo === "sinal") return chipEstado("sinal", "sinal a verificar");
  return h("span", { class: "badge " + (tipo === "padrao" ? "info" : "neutro") }, ROTULO_TIPO_INS[tipo] || tipo);
}
/** O link de um fato (como o ETL o escreve) no formato do estado da página. */
function mudancasDoFato(link) {
  const m = { visao: link.visao, sel: link.sel || null, ir: link.ir || null, ano: null, fonte: null, min: 2 };
  if (link.mercado) m.mercado = link.mercado;
  if (link.ano) { const i = ANOS.indexOf(link.ano); m.ano = i >= 0 ? i : null; }
  if (link.fonte) { const i = FONTES.findIndex(f => f.id === link.fonte); m.fonte = i >= 0 ? i : null; }
  if (link.sit) m.sit = link.sit;
  if (link.minObras) m.minObras = link.minObras;
  if (link.visao === "fornecedores" && !("tipos" in link)) m.tipos = new Set(META.tipos_padrao);
  return m;
}
function rotuloVisao(v) { return { fornecedores: "na rede de fornecedores", municipios: "nos municípios conectados", obras: "na rede de obras", metodologia: "na metodologia" }[v] || ""; }
function linkDoFato(f, texto) { return linkPara(mudancasDoFato(f.link), texto || "Ver " + rotuloVisao(f.link.visao) + " ›"); }
function fonteDoFato(f) {
  return botaoFonte(null, () => ["fato \"" + f.id + "\"", f.q, ["Fato calculado por financiamento/etl/insights.py (calcular_fatos) a partir de dados/processado/grafos.json — o mesmo dado das figuras.",
    "Os números do fato: " + f.numeros.map(n => n.rotulo + " = " + n.texto).join("; ") + "."], null]);
}

function filtrosInsights() {
  return [campo("Mostrar", seletorSimples(estado.ti, [["todos", "Todos os tipos"], ["sinal", "Só sinais a verificar"], ["padrao", "Só padrões"], ["contexto", "Só contexto"]], v => ajustar({ ti: v })))];
}
function recorteInsights() {
  const r = INS.meta.redacao;
  return [h("strong", {}, r ? nf(INS.insights.length) + " observações" : "Fatos calculados"), " de ", h("strong", {}, nf(INS.fatos.length) + " fatos"),
    estado.ti === "todos" ? "" : [" · ", h("strong", {}, ROTULO_TIPO_INS[estado.ti])]];
}
function recorteCurtoInsights() { return "Insights"; }

function renderInsights(main) {
  const r = INS.meta.redacao;
  const passa = x => estado.ti === "todos" || x.tipo === estado.ti;
  main.append(h("section", { class: "cab-visao compacta" }, h("h2", {}, "Insights"),
    h("p", { class: "frase" }, "O que as três redes mostram, em poucas linhas — cada observação com os fatos de onde saiu, o link para vê-la na figura e a fonte de cada número. "
      + "São pontos para escolher onde olhar, não achados de auditoria.")));
  main.append(r ? h("div", { class: "callout info status-ia" },
      h("strong", {}, "Texto redigido por IA, números conferidos. "),
      "Gerado por " + r.modelo + (r.fallback ? " (com fallback de modelo)" : "") + " em " + dataHoraBR(r.gerado_em) + ", a partir de " + nf(INS.fatos.length) + " fatos calculados. "
      + "Cada número do texto foi comparado com os fatos citados; " + nf(r.aceitos) + " observações passaram e " + nf(r.recusados) + " foram recusadas. Leia como rascunho de quem analisa: confira os fatos antes de citar.",
      INS.meta.aviso ? h("p", { class: "small" }, ESTADOS.sinal.simbolo + " " + INS.meta.aviso) : null)
    : h("div", { class: "callout" }, h("strong", {}, "A redação por IA ainda não foi gerada. "),
      "Abaixo estão os fatos calculados, que já servem de leitura. Para gerar as observações, quem mantém o painel roda o ETL com a credencial da Anthropic na própria máquina (a página nunca chama a API):",
      h("pre", {}, h("code", {}, "python -m financiamento.etl.insights --com-ia")),
      INS.meta.aviso ? h("p", { class: "small" }, ESTADOS.sinal.simbolo + " " + INS.meta.aviso) : null));

  const lista = INS.insights.filter(passa);
  if (r) main.append(h("section", { class: "bloco" }, h("h3", { class: "titulo-secao" }, "Observações"),
    lista.length ? h("div", { class: "grade-insights" }, lista.map(cartaoInsight)) : h("p", { class: "muted" }, "Nenhuma observação deste tipo.")));

  // Os fatos, por tema — sempre presentes, com ou sem IA.
  const porTema = new Map();
  for (const f of INS.fatos.filter(passa)) { if (!porTema.has(f.tema)) porTema.set(f.tema, []); porTema.get(f.tema).push(f); }
  main.append(h("section", { class: "bloco", id: "card-fatos" }, h("h3", { class: "titulo-secao" }, r ? "Todos os fatos calculados" : "Fatos calculados"),
    h("p", { class: "nota" }, "Calculados sem IA, do mesmo dado das figuras: a mesma execução dá os mesmos fatos."),
    [...porTema.entries()].map(([tema, fs]) => h("article", { class: "card fatos-tema" },
      h("header", {}, h("h3", {}, TEMAS[tema] || tema)),
      h("ul", { class: "lista-fatos" }, fs.map(f => h("li", { id: "fato-" + f.id }, chipTipoInsight(f.tipo), " ", h("span", { class: "txt" }, f.texto),
        h("span", { class: "acoes-fato" }, linkDoFato(f), fonteDoFato(f))))))),
    tabelaFatos(INS.fatos.filter(passa))));

  main.append(h("section", { class: "card metodo", id: "card-como-insights" }, h("h3", {}, "Como estas observações são feitas"),
    h("ol", { class: "lista" },
      h("li", {}, h("strong", {}, "Fatos. "), "O ETL calcula, sem IA, os padrões das redes: comunidades e regiões, concentração (HHI) por mercado e município, alcance e valor dos maiores fornecedores, crescimento de 2021 a 2025, novos fornecedores, dinheiro do FNDE, obras paradas. Cada fato guarda os números e a consulta de origem."),
      h("li", {}, h("strong", {}, "Redação. "), "Uma única chamada a um modelo Claude, feita por quem mantém o painel, recebe só a lista de fatos e devolve observações em formato estruturado, citando os fatos usados. O nome de credor com CPF é mascarado antes de sair da máquina. A chave da API nunca está na página."),
      h("li", {}, h("strong", {}, "Verificação. "), "Todo número do texto tem de bater com um número dos fatos citados (com a tolerância do arredondamento escrito); fato citado tem de existir; texto que afirma irregularidade, fraude ou superfaturamento é recusado. O que não passa não aparece aqui."),
      h("li", {}, h("strong", {}, "Atualização. "), "Se os dados mudarem, os fatos mudam e a página avisa que a redação ficou velha — até alguém rodar a redação de novo.")),
    r ? h("dl", { class: "fonte-item-dl" },
      h("dt", {}, "Modelo"), h("dd", {}, r.modelo + (r.modelo !== r.modelo_pedido ? " (pedido: " + r.modelo_pedido + ")" : "") + " · esforço " + r.esforco),
      h("dt", {}, "Requisição"), h("dd", {}, h("code", {}, r.id_requisicao || "—")),
      h("dt", {}, "Hash do prompt"), h("dd", {}, h("code", {}, r.prompt_sha256)),
      h("dt", {}, "Hash dos fatos"), h("dd", {}, h("code", {}, r.fatos_sha256))) : null,
    INS.recusados.length ? h("details", { class: "tab" }, h("summary", {}, "Observações recusadas pela verificação (" + INS.recusados.length + ")"),
      h("ul", { class: "lista" }, INS.recusados.map(x => h("li", {}, h("strong", {}, x.titulo), " — ", (x.problemas || []).join("; "))))) : null));
}

function cartaoInsight(ins) {
  const fatos = (ins.fatos || []).map(id => FATO.get(id)).filter(Boolean);
  const principal = fatos.find(f => f.link && f.link.visao !== "metodologia") || fatos[0];
  return h("article", { class: "card insight insight-" + ins.tipo },
    h("div", { class: "insight-topo" }, chipTipoInsight(ins.tipo), h("span", { class: "badge neutro badge-ia", title: "Texto redigido por um modelo de IA a partir dos fatos abaixo; os números foram conferidos." }, "texto por IA")),
    h("h3", {}, ins.titulo),
    h("p", {}, ins.texto),
    ins.proxima_verificacao ? h("p", { class: "proxima" }, h("strong", {}, "Próxima verificação: "), ins.proxima_verificacao) : null,
    h("div", { class: "insight-acoes" }, principal ? linkDoFato(principal) : null),
    h("details", { class: "tab" }, h("summary", {}, "Fatos usados (" + fatos.length + ")"),
      h("ul", { class: "lista-fatos" }, fatos.map(f => h("li", {}, h("span", { class: "txt" }, f.texto), h("span", { class: "acoes-fato" }, linkDoFato(f), fonteDoFato(f)))))));
}
function tabelaFatos(fatos) {
  return h("details", { class: "tab" }, h("summary", {}, "Os fatos em tabela (" + fatos.length + ")"),
    tabela([
      { rotulo: "Fato", valor: f => f.id },
      { rotulo: "Tema", valor: f => TEMAS[f.tema] || f.tema },
      { rotulo: "Tipo", valor: f => ROTULO_TIPO_INS[f.tipo] },
      { rotulo: "Texto", valor: f => f.texto, classe: "motivo" },
      { rotulo: "Números", valor: f => f.numeros.map(n => n.rotulo + ": " + n.texto).join(" · "), classe: "small" },
    ], fatos, "Fatos calculados", { csv: "fatos_redes.csv", inicio: 0, busca: false }));
}
