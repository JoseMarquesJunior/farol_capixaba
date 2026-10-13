"use strict";
/* ============================================================================
   "Ver fonte" — a nota de rodapé do papel de trabalho. Para cada número de um
   card: o indicador, ONDE ele está na fonte (anexo, linha, coluna ou item do
   demonstrativo), COMO é calculado e as CONSULTAS exatas (URL com parâmetros,
   instante da coleta, arquivo do cache bruto, SHA-256 quando é arquivo).
   Tudo vem do dataset: o painel não consulta nada. O link da consulta só abre
   a fonte numa aba nova, por decisão de quem clica.
   ========================================================================== */

const MAX_CONSULTAS_VISIVEIS = 4;

function localizacaoDe(indicador, ano, detalhe) {
  const meta = META.indicadores[indicador];
  if (!meta) return "";
  const ax = META.anexos[String(ano)] || {};
  return meta.localizacao.replaceAll("{anexo_ie}", ax.dca_despesa_funcao || "DCA-Anexo I-E")
    .replaceAll("{anexo_ic}", ax.dca_receita || "DCA-Anexo I-C")
    .replaceAll("{anexo_a02}", ax.rreo_despesa_funcao || "RREO-Anexo 02")
    .replaceAll("{detalhe}", detalhe || "…");
}

/** Ids "a;b;c" (ou lista) → consultas conhecidas, sem repetição. */
function consultasDe(q) {
  const ids = (Array.isArray(q) ? q : [q]).filter(Boolean).flatMap(x => String(x).split(";")).filter(Boolean);
  return [...new Set(ids)].map(id => CONSULTAS.get(id)).filter(Boolean)
    .sort((a, b) => a.fonte.localeCompare(b.fonte) || a.url.localeCompare(b.url));  // meses e bimestres em ordem
}

function parametrosDaUrl(url) {
  try {
    const u = new URL(url);
    const p = [...u.searchParams.entries()];
    return p.length ? p : [["arquivo", u.pathname.split("/").pop()]];
  } catch (e) { return []; }
}

/* ---------------------------------------------- PDF da fonte, dentro da página

   A consulta do SIOPE aponta para ftp://ftp.fnde.gov.br — esquema que o Chrome
   removeu na versão 95 e o Firefox na 90. Clicar no link não faz nada, e o FNDE
   não publica esses arquivos por HTTP anônimo. O PDF vai embutido na página
   (build_dashboard.pdfs_embutidos): o índice diz quais existem e quanto pesam, e
   o bloco de base64, que é grande, só é lido no primeiro clique — parseá-lo na
   abertura atrasaria o painel inteiro por causa de um botão que talvez ninguém
   use nesta sessão. */
const PDFS_INDICE = (() => {
  const bloco = document.getElementById("pdfs-indice");
  try { return bloco ? JSON.parse(bloco.textContent) : {}; } catch (e) { return {}; }
})();
let PDFS = null;

function pdfEmbutido(arquivo) {
  if (PDFS === null) {
    const bloco = document.getElementById("pdfs");
    try { PDFS = bloco ? JSON.parse(bloco.textContent) : {}; } catch (e) { PDFS = {}; }
  }
  return PDFS[arquivo] || null;
}

/** Abre o PDF embutido numa aba nova. Vai por blob: porque o navegador bloqueia
 *  navegação de topo para data:; blob: funciona também em file://. */
function abrirPdf(arquivo, aviso) {
  const b64 = pdfEmbutido(arquivo);
  if (!b64) { if (aviso) aviso.textContent = "PDF não embutido nesta versão da página."; return; }
  const bin = atob(b64), bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  window.open(url, "_blank", "noopener");
  // Revogar já fecharia a aba recém-aberta em alguns navegadores; o objeto morre com a página.
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function linhaConsulta(c) {
  const params = parametrosDaUrl(c.url);
  const ftp = c.url.startsWith("ftp:");
  const bytes = PDFS_INDICE[c.arquivo];
  const aviso = h("span", { class: "nota", "aria-live": "polite" });
  // Link morto não vira link: o ftp:// fica como texto, com a URL exata para quem
  // for reproduzir a coleta por fora (Explorer do Windows, curl, cliente FTP).
  const consulta = ftp
    ? [h("span", { class: "url" }, c.url.split("?")[0]),
       h("div", { class: "nota" }, "ftp:// — navegador não abre mais este esquema; ",
         bytes ? "o documento está embutido nesta página." : "reproduza com um cliente FTP ou curl.")]
    : [h("a", { href: c.url, target: "_blank", rel: "noopener noreferrer", class: "url" }, c.url.split("?")[0])];
  return h("tr", {},
    h("td", {}, h("span", { class: "badge fonte-" + c.fonte.toLowerCase() }, c.fonte), h("br"), h("span", { class: "nota" }, c.descricao)),
    h("td", {}, consulta,
      h("ul", { class: "params" }, params.map(([k, v]) => h("li", {}, h("code", {}, k), " = ", h("code", {}, v))))),
    h("td", { class: "num" }, h("span", { title: c.obtido_em }, dataHoraBR(c.obtido_em)), h("br"), h("span", { class: "nota" }, c.obtido_em)),
    h("td", {}, h("code", { class: "arquivo" }, "dados/bruto/" + c.arquivo),
      c.sha256 ? h("div", { class: "nota", title: c.sha256 }, "SHA-256 " + c.sha256.slice(0, 16) + "…") : null,
      h("div", { class: "nota" }, c.metodo),
      bytes ? h("div", {}, h("button", { type: "button", class: "leve abrir-pdf",
        onclick: () => abrirPdf(c.arquivo, aviso) }, "abrir PDF (" + Math.round(bytes / 1024) + " KB)"), " ", aviso) : null));
}

function tabelaConsultas(consultas) {
  const cab = h("thead", {}, h("tr", {}, ["Fonte", "Consulta (abre numa aba)", "Coletado em", "Evidência no cache"].map(t => h("th", { scope: "col" }, t))));
  const visiveis = consultas.slice(0, MAX_CONSULTAS_VISIVEIS), resto = consultas.slice(MAX_CONSULTAS_VISIVEIS);
  const bloco = h("div", {}, h("div", { class: "tabela-wrap inteira" }, h("table", { class: "consultas" }, cab, h("tbody", {}, visiveis.map(linhaConsulta)))));
  if (resto.length) {
    bloco.append(h("details", { class: "tab" }, h("summary", {}, "Mais " + resto.length + " consulta(s)"),
      h("div", { class: "tabela-wrap" }, h("table", { class: "consultas" }, cab.cloneNode(true), h("tbody", {}, resto.map(linhaConsulta))))));
  }
  return bloco;
}

/** Texto para colar no papel de trabalho. */
function referenciaTexto(titulo, itens) {
  const linhas = [titulo, "Extraído de: painel de financiamento da educação — municípios do ES (versão " + (META.versao || META.gerado_em) + ")", ""];
  for (const it of itens) {
    const meta = META.indicadores[it.indicador] || {};
    linhas.push((meta.rotulo || it.indicador) + (it.detalhe ? " — " + it.detalhe : "") + (it.valor != null ? ": " + it.valor : ""));
    linhas.push("  Onde: " + localizacaoDe(it.indicador, it.ano, it.detalhe));
    linhas.push("  Cálculo: " + (meta.calculo || ""));
    if (it.observacao) linhas.push("  Observação: " + it.observacao);
    for (const c of consultasDe(it.q)) {
      linhas.push("  Consulta: " + c.fonte + " — " + c.descricao);
      linhas.push("    " + c.url);
      linhas.push("    coletado em " + c.obtido_em + " · cache dados/bruto/" + c.arquivo + (c.sha256 ? " · SHA-256 " + c.sha256 : ""));
    }
    linhas.push("");
  }
  return linhas.join("\n");
}

function copiar(texto, aviso) {
  const ok = () => { aviso.textContent = "Referência copiada."; };
  const alternativa = () => {
    const ta = h("textarea", { class: "sr-only", "aria-hidden": "true" }, texto);
    document.body.append(ta); ta.select();
    try { document.execCommand("copy"); ok(); } catch (e) { aviso.textContent = "Não foi possível copiar: selecione o texto manualmente."; }
    ta.remove();
  };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(texto).then(ok, alternativa);
  else alternativa();
}

/**
 * Abre o diálogo de fonte.
 * itens: [{indicador, ano, detalhe?, observacao?, valor?, q}] — `q` = ids de consulta ("a;b") ou lista.
 */
function abrirFonte(titulo, itens) {
  const dlg = $("#dialogo-fonte");
  limpar(dlg);
  const aviso = h("span", { class: "nota", "aria-live": "polite" });
  const corpo = h("div", { class: "fonte-corpo" });
  if (!itens.length) corpo.append(h("p", {}, "Sem número exibido: não há consulta a citar."));
  for (const it of itens) {
    const meta = META.indicadores[it.indicador] || { rotulo: it.indicador, calculo: "" };
    const consultas = consultasDe(it.q);
    corpo.append(h("section", { class: "fonte-item" },
      h("h3", {}, meta.rotulo, it.detalhe ? h("span", { class: "muted" }, " — " + it.detalhe) : null),
      h("dl", {},
        h("dt", {}, "Onde está na fonte"), h("dd", {}, localizacaoDe(it.indicador, it.ano, it.detalhe)),
        h("dt", {}, "Cálculo"), h("dd", {}, meta.calculo),
        it.observacao ? [h("dt", {}, "Observação"), h("dd", {}, it.observacao)] : null,
        meta.fonte === "SIOPE" ? [h("dt", {}, "Estabilidade"), h("dd", {}, h("span", { class: "badge aviso" }, "⚠ extraído de PDF"),
          " — fonte sem SLA; o valor foi conferido contra os demais números da mesma linha do demonstrativo.")] : null),
      consultas.length ? tabelaConsultas(consultas) : h("p", { class: "nota" }, "Número calculado a partir dos acima, ou sem consulta registrada.")));
  }
  dlg.append(
    h("header", {}, h("h2", { id: "fonte-titulo" }, "Fonte — " + titulo),
      h("button", { type: "button", class: "leve fechar", "aria-label": "Fechar", onclick: () => dlg.close() }, "×")),
    h("p", { class: "nota" }, "Cada consulta é reproduzível: a URL refaz a requisição e o arquivo em dados/bruto/ guarda a resposta original, com o instante da coleta."),
    corpo,
    h("footer", {}, h("button", { type: "button", onclick: () => copiar(referenciaTexto(titulo, itens), aviso) }, "Copiar referência"), " ", aviso));
  if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
}

/** Botão "ver fonte" para o cabeçalho de um card. `itens` pode ser função (montada só no clique). */
function botaoFonte(titulo, itens) {
  return h("button", { type: "button", class: "leve ver-fonte", "aria-haspopup": "dialog",
    onclick: () => abrirFonte(titulo, typeof itens === "function" ? itens() : itens) }, "ⓘ ver fonte");
}

/** Cabeçalho padrão de card: título, nota e (opcional) o botão de fonte. */
function cabecalho(titulo, nota, fonte) {
  return h("header", { class: "cab-card" },
    h("div", {}, h("h3", {}, titulo), nota ? h("p", { class: "nota" }, nota) : null),
    fonte ? botaoFonte(fonte.titulo || titulo, fonte.itens) : null);
}

/** Os ids de consulta de uma coluna `q_*` da tabela anual, para um conjunto de entes. */
function qAnual(campo, cods, ano) {
  return cods.map(c => (LINHA.get(c + "|" + ano) || {})[campo]).filter(Boolean).join(";");
}
