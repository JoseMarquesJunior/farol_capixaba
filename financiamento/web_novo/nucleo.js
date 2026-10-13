"use strict";
/* ============================================================================
   Núcleo sem dado: formatação, criação de elementos, os quatro estados, a
   tabela, o CSV, o tooltip e o redesenho em redimensionamento. Vale para os dois
   arquivos gerados (o painel e o papel de trabalho do CNCA).
   Todo texto vindo dos dados entra por textContent — nunca innerHTML.
   ========================================================================== */

/* ------------------------------------------------------------------ formato */
const $ = (s, r = document) => r.querySelector(s);
const nf = (v, d = 0) => new Intl.NumberFormat("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d }).format(v);
const brl = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
const dataBR = iso => iso ? iso.slice(0, 10).split("-").reverse().join("/") : "—";
const dataHoraBR = iso => iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";
const nulo = v => v === null || v === undefined || (typeof v === "number" && Number.isNaN(v));
const semAcento = s => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function brlCompacto(v) {
  const a = Math.abs(v);
  if (a >= 1e9) return "R$ " + nf(v / 1e9, 2) + " bi";
  if (a >= 1e6) return "R$ " + nf(v / 1e6, 1) + " mi";
  if (a >= 1e3) return "R$ " + nf(v / 1e3, 0) + " mil";
  return brl(v);
}
/** Rótulo curto para eixo: "R$ 200 mi", "R$ 1 bi" (sem casas quando redondo). */
function tickMoeda(v) {
  const a = Math.abs(v), sem = x => nf(x, Number.isInteger(x) ? 0 : 1);
  if (a >= 1e9) return "R$ " + sem(v / 1e9) + " bi";
  if (a >= 1e6) return "R$ " + sem(v / 1e6) + " mi";
  if (a >= 1e3) return "R$ " + sem(v / 1e3) + " mil";
  return "R$ " + nf(v, 0);
}
const pct = (v, d = 1) => nulo(v) ? "sem dado" : nf(v, d) + "%";
/** Variação com seta e sinal, sem cor: aumentar não é bom nem ruim por si. */
const variacao = v => nulo(v) ? "sem dado" : (v >= 0 ? "↑ +" : "↓ −") + nf(Math.abs(v), 1) + "%";

/** Cria elemento: h("div", {class:"x"}, "texto", outroNo). Texto sempre como nó de texto. */
function h(tag, attrs, ...filhos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos.flat(Infinity)) {
    if (f === null || f === undefined || f === false) continue;
    el.append(f instanceof Node ? f : document.createTextNode(String(f)));
  }
  return el;
}
const limpar = el => { while (el.firstChild) el.removeChild(el.firstChild); return el; };

function cores() {
  const cs = getComputedStyle(document.documentElement);
  const v = n => cs.getPropertyValue(n).trim();
  return { surface: v("--surface"), ink: v("--ink"), ink2: v("--ink-2"), grid: v("--grid"), axis: v("--axis"),
    neutro: v("--neutral-mark"), serie: [v("--s1"), v("--s2"), v("--s3"), v("--s4")],
    descumpre: v("--st-descumpre-barra"), sinal: v("--st-sinal-barra"),
    // Canvas não entende var(): a fonte e o branco do rótulo dentro da barra
    // têm de ser lidos dos tokens aqui.
    fonte: v("--tc-fonte"), sobreSerie: v("--tc-primaria-txt"), pesoMedio: v("--tc-peso-medio") };
}

function campo(rotulo, controle) {
  const id = controle.id || ("c" + Math.random().toString(36).slice(2, 8));
  controle.id = id;
  return h("div", { class: "campo" }, h("label", { for: id }, rotulo), controle);
}

/* ------------------------------------------------------------------- estados
   Quatro estados com significado fixo nos dois arquivos (decisão D6 da
   auditoria). Vermelho é SÓ regra legal descumprida; divergência entre fontes,
   atraso e obra parada são "sinal a verificar", em âmbar. Cada estado sai com
   cor, símbolo e palavra — nunca só a cor. */
const ESTADOS = {
  descumpre: { simbolo: "✖", rotulo: "descumpre",
    significado: "regra legal descumprida — mínimo constitucional abaixo, ou obrigação com prazo vencido e ainda não cumprida" },
  sinal: { simbolo: "⚑", rotulo: "sinal a verificar",
    significado: "atraso, divergência entre fontes ou obra parada — merece verificação, mas não é irregularidade por si" },
  cumpre: { simbolo: "✔", rotulo: "cumpre", significado: "a regra foi cumprida no período" },
  semdado: { simbolo: "—", rotulo: "sem dado", significado: "a fonte não traz o dado — nunca quer dizer zero" },
};
const ORDEM_ESTADO = { descumpre: 0, sinal: 1, semdado: 2, cumpre: 3 };

function chipEstado(chave, texto, titulo) {
  const e = ESTADOS[chave] || ESTADOS.semdado;
  return h("span", { class: "est est-" + (ESTADOS[chave] ? chave : "semdado"), title: titulo || e.significado },
    h("span", { "aria-hidden": "true" }, e.simbolo), " ", texto || e.rotulo);
}
function legendaEstados(chaves) {
  return h("div", { class: "legenda-estados", role: "note", "aria-label": "Como ler os estados" },
    h("strong", {}, "Como ler: "),
    (chaves || Object.keys(ESTADOS)).map(k => h("span", { class: "item" }, chipEstado(k), h("span", { class: "muted small" }, ESTADOS[k].significado))));
}
/** Pior estado de uma lista (descumpre > sinal > sem dado > cumpre). */
function piorEstado(lista) {
  const validos = lista.filter(Boolean);
  if (!validos.length) return "semdado";
  return validos.slice().sort((a, b) => ORDEM_ESTADO[a] - ORDEM_ESTADO[b])[0];
}
/** "sem dado" em itálico cinza — ausência nunca é mostrada como zero. */
const semDado = texto => h("span", { class: "valor-sem-dado" }, texto || "sem dado");

/* ------------------------------------------------------------------ CSV
   Separador ";" e vírgula decimal, como o Excel em português espera (decisão
   D7). O mesmo formato nos dois arquivos — antes o painel usava "," e ponto, e o
   CNCA, ";" com ponto. */
const NUM_CSV = new Intl.NumberFormat("pt-BR", { useGrouping: false, maximumFractionDigits: 10 });
function valorCSV(v) {
  if (nulo(v)) return "";
  if (typeof v === "number") return NUM_CSV.format(v);
  if (typeof v === "boolean") return v ? "sim" : "não";
  return String(v);
}
function linhaCSV(valores) {
  return valores.map(v => { const s = valorCSV(v); return /[";\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }).join(";");
}
function baixarTexto(nome, texto, tipo) {
  const url = URL.createObjectURL(new Blob([texto], { type: tipo }));
  const a = h("a", { href: url, download: nome });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const colunaExportavel = c => c.csv !== false && c.rotulo !== "Fonte";
function baixarCSV(nome, colunas, linhas) {
  const cols = colunas.filter(colunaExportavel);
  const corpo = [linhaCSV(cols.map(c => c.rotulo))]
    .concat(linhas.map(l => linhaCSV(cols.map(c => typeof c.csv === "function" ? c.csv(l) : c.valor(l)))));
  baixarTexto(nome, "﻿" + corpo.join("\r\n"), "text/csv;charset=utf-8");
}

/* ------------------------------------------------------------------ XLSX
   Planilha Excel de verdade (.xlsx), escrita aqui mesmo: um zip sem compressão
   com as partes mínimas do Open XML. Sem biblioteca externa, o painel continua
   um arquivo só (decisão D8) e exporta sem rede. Cada planilha leva a aba
   "Dados" (cabeçalho fixo, filtro automático, número como número) e a aba
   "Recorte", que registra os filtros ativos no momento da exportação. */
const CRC32_TABELA = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
  return t;
})();
function crc32(bytes) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < bytes.length; i++) c = CRC32_TABELA[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}
/** Zip "stored" (sem compressão) de arquivos de texto: [{ nome, texto }]. */
function zipSemCompressao(arquivos, tipo) {
  const enc = new TextEncoder(), partes = [], central = [];
  const agora = new Date();
  const dosHora = (agora.getHours() << 11) | (agora.getMinutes() << 5) | (agora.getSeconds() >> 1);
  const dosData = ((agora.getFullYear() - 1980) << 9) | ((agora.getMonth() + 1) << 5) | agora.getDate();
  const u16 = v => [v & 0xFF, (v >>> 8) & 0xFF];
  const u32 = v => [v & 0xFF, (v >>> 8) & 0xFF, (v >>> 16) & 0xFF, (v >>> 24) & 0xFF];
  let desloc = 0;
  for (const a of arquivos) {
    const nome = enc.encode(a.nome), dados = enc.encode(a.texto), crc = crc32(dados);
    const local = new Uint8Array([...u32(0x04034b50), ...u16(20), ...u16(0x0800), ...u16(0), ...u16(dosHora), ...u16(dosData),
      ...u32(crc), ...u32(dados.length), ...u32(dados.length), ...u16(nome.length), ...u16(0)]);
    central.push(new Uint8Array([...u32(0x02014b50), ...u16(20), ...u16(20), ...u16(0x0800), ...u16(0), ...u16(dosHora), ...u16(dosData),
      ...u32(crc), ...u32(dados.length), ...u32(dados.length), ...u16(nome.length), ...u16(0), ...u16(0), ...u16(0), ...u16(0), ...u32(0), ...u32(desloc)]), nome);
    partes.push(local, nome, dados);
    desloc += local.length + nome.length + dados.length;
  }
  const tamCentral = central.reduce((t, p) => t + p.length, 0);
  const fim = new Uint8Array([...u32(0x06054b50), ...u16(0), ...u16(0), ...u16(arquivos.length), ...u16(arquivos.length), ...u32(tamCentral), ...u32(desloc), ...u16(0)]);
  return new Blob([...partes, ...central, fim], { type: tipo });
}
const escaparXml = s => String(s).replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, "")
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
function colunaExcel(i) { let s = ""; for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + (n - 1) % 26) + s; return s; }
/** XML de uma aba a partir de uma matriz de valores (número, texto, booleano ou vazio).
 *  Com `cabecalho`, a primeira linha fica em negrito, congelada e com filtro automático. */
function abaXlsx(matriz, cabecalho) {
  const larguras = [];
  const celula = (v, c, r) => {
    const ref = colunaExcel(c) + (r + 1);
    if (nulo(v) || v === "") return "";
    if (typeof v === "number") {
      if (!Number.isFinite(v)) return "";
      larguras[c] = Math.max(larguras[c] || 0, nf(v, 2).length);
      return '<c r="' + ref + '" s="' + (Number.isInteger(v) ? 0 : 2) + '"><v>' + v + "</v></c>";
    }
    if (typeof v === "boolean") return '<c r="' + ref + '" t="b"><v>' + (v ? 1 : 0) + "</v></c>";
    const s = String(v);
    larguras[c] = Math.max(larguras[c] || 0, Math.min(s.length, 60));
    return '<c r="' + ref + '"' + (r === 0 && cabecalho ? ' s="1"' : "") + ' t="inlineStr"><is><t xml:space="preserve">' + escaparXml(s) + "</t></is></c>";
  };
  const linhas = matriz.map((l, r) => '<row r="' + (r + 1) + '">' + l.map((v, c) => celula(v, c, r)).join("") + "</row>").join("");
  const nCols = Math.max(1, ...matriz.map(l => l.length));
  const cols = "<cols>" + Array.from({ length: nCols }, (_, c) =>
    '<col min="' + (c + 1) + '" max="' + (c + 1) + '" width="' + Math.min(60, Math.max(8, (larguras[c] || 8) + 2)) + '" customWidth="1"/>').join("") + "</cols>";
  const ref = "A1:" + colunaExcel(nCols - 1) + Math.max(1, matriz.length);
  const comFiltro = cabecalho && matriz.length > 1;
  return { ref, comFiltro, xml: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="' + ref + '"/>' +
    (cabecalho ? '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>' : "") +
    cols + "<sheetData>" + linhas + "</sheetData>" + (comFiltro ? '<autoFilter ref="' + ref + '"/>' : "") + "</worksheet>" };
}
const ESTILOS_XLSX = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
  '<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.00"/></numFmts>' +
  '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>' +
  '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>' +
  '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>' +
  '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +
  '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>' +
  '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>' +
  '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></' + 'styleSheet>';  // tag final partida: inteira, encerraria o <style> da página
/** Monta o .xlsx e o entrega ao navegador. abas: [{ nome, matriz, cabecalho }]. */
function baixarXLSX(nome, abas) {
  const ns = "http://schemas.openxmlformats.org/";
  const folhas = abas.map(a => ({ ...a, ...abaXlsx(a.matriz, a.cabecalho) }));
  const nomeAba = a => escaparXml(String(a.nome).replace(/[\\/?*[\]:]/g, " ").slice(0, 31));
  const arquivos = [
    { nome: "[Content_Types].xml", texto: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="' + ns + 'package/2006/content-types">' +
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>' +
      '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
      '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' +
      folhas.map((_, i) => '<Override PartName="/xl/worksheets/sheet' + (i + 1) + '.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>').join("") + "</Types>" },
    { nome: "_rels/.rels", texto: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="' + ns + 'package/2006/relationships">' +
      '<Relationship Id="rId1" Type="' + ns + 'officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>' },
    { nome: "xl/workbook.xml", texto: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="' + ns + 'spreadsheetml/2006/main" xmlns:r="' + ns + 'officeDocument/2006/relationships">' +
      "<bookViews><workbookView/></bookViews><sheets>" + folhas.map((a, i) => '<sheet name="' + nomeAba(a) + '" sheetId="' + (i + 1) + '" r:id="rId' + (i + 1) + '"/>').join("") + "</sheets>" +
      (folhas.some(a => a.comFiltro) ? "<definedNames>" + folhas.map((a, i) => a.comFiltro ?
        '<definedName name="_xlnm._FilterDatabase" localSheetId="' + i + '" hidden="1">\'' + nomeAba(a) + "'!" + a.ref.replace(/([A-Z]+)(\d+)/g, "$$$1$$$2") + "</definedName>" : "").join("") + "</definedNames>" : "") + "</workbook>" },
    { nome: "xl/_rels/workbook.xml.rels", texto: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="' + ns + 'package/2006/relationships">' +
      folhas.map((_, i) => '<Relationship Id="rId' + (i + 1) + '" Type="' + ns + 'officeDocument/2006/relationships/worksheet" Target="worksheets/sheet' + (i + 1) + '.xml"/>').join("") +
      '<Relationship Id="rId' + (folhas.length + 1) + '" Type="' + ns + 'officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>' },
    { nome: "xl/styles.xml", texto: ESTILOS_XLSX },
    ...folhas.map((a, i) => ({ nome: "xl/worksheets/sheet" + (i + 1) + ".xml", texto: a.xml })),
  ];
  const url = URL.createObjectURL(zipSemCompressao(arquivos, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"));
  const a = h("a", { href: url, download: nome });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
/** A tabela como planilha: as mesmas colunas e linhas do CSV, mais a aba "Recorte"
 *  com os filtros ativos ([rótulo, valor], uma linha cada). */
function baixarPlanilha(nome, colunas, linhas, recorte) {
  const cols = colunas.filter(colunaExportavel);
  const dados = [cols.map(c => c.rotulo)].concat(linhas.map(l => cols.map(c => {
    const v = typeof c.csv === "function" ? c.csv(l) : c.valor(l);
    return typeof v === "boolean" ? (v ? "sim" : "não") : v;
  })));
  baixarXLSX(nome, [{ nome: "Dados", matriz: dados, cabecalho: true },
    { nome: "Recorte", matriz: [["Filtro", "Valor"]].concat(recorte || []), cabecalho: false }]);
}

/* ------------------------------------------------------------------- tabela
   O único componente de tabela dos dois arquivos. Ordena por qualquer coluna
   (aria-sort), busca por texto quando a lista é longa, fixa a primeira coluna
   na rolagem horizontal e começa curta com "mostrar todas" — no lugar da caixa
   de 420px com rolagem própria dentro da página que também rola.

   colunas: [{ rotulo, valor(l), render?(l), fmt?(v), num?, ordenavel?, ordem?(l),
               csv?(l)|false, classe? }]
   opcoes:  { classeLinha(l), destacar(l), rodape:[…], inicio (0 = todas),
              busca: true|false|"placeholder", csv: "arquivo.csv", fixarPrimeira,
              xlsx: "arquivo.xlsx", recorte: [[rótulo, valor], …] | () => […],
              ordemInicial: {coluna, direcao}, legendaVisivel, vazio }        */
const LINHAS_INICIAIS = 15;

function compararValores(a, b) {
  const na = nulo(a) || a === "", nb = nulo(b) || b === "";
  if (na || nb) return na && nb ? 0 : na ? 1 : -1;  // vazio sempre no fim
  if (typeof a === "number" && typeof b === "number") return a - b;
  if (typeof a === "boolean" && typeof b === "boolean") return (a ? 1 : 0) - (b ? 1 : 0);
  return String(a).localeCompare(String(b), "pt-BR", { numeric: true, sensitivity: "base" });
}

function tabela(colunas, linhas, legenda, opcoes) {
  const o = opcoes || {};
  const inicio = o.inicio === 0 ? Infinity : (o.inicio || LINHAS_INICIAIS);
  const fixar = o.fixarPrimeira !== undefined ? o.fixarPrimeira : colunas.length > 3;
  const comBusca = o.busca !== undefined ? !!o.busca : linhas.length > LINHAS_INICIAIS;
  const ordenavel = c => c.ordenavel !== false && c.rotulo !== "Fonte";
  let ordem = o.ordemInicial || null;  // {coluna: índice, direcao: "asc"|"desc"}
  let filtro = "", aberta = false;

  const bloco = h("div", { class: "tabela-bloco" });
  if (!linhas.length) {
    bloco.append(h("p", { class: "muted" }, o.vazio || "Nenhuma linha para mostrar."));
    return bloco;
  }
  const contagem = h("span", { class: "contagem", "aria-live": "polite" });
  const botaoMais = h("button", { type: "button", class: "leve", "aria-expanded": "false", onclick: () => { aberta = !aberta; desenhar(); } });
  const busca = comBusca ? h("input", { type: "search", placeholder: typeof o.busca === "string" ? o.busca : "Buscar nesta tabela…",
    "aria-label": "Buscar em: " + (legenda || "tabela"), oninput: e => { filtro = semAcento(e.target.value.trim()); desenhar(); } }) : null;

  const ths = colunas.map((c, i) => {
    const classes = [c.num ? "num" : "", i === 0 && fixar ? "fixa" : "", c.classe || ""].filter(Boolean).join(" ");
    const th = h("th", { scope: "col", class: classes || null });
    if (ordenavel(c)) {
      th.append(h("button", { type: "button", class: "ordenar", title: "Ordenar por " + c.rotulo,
        onclick: () => {
          ordem = ordem && ordem.coluna === i ? { coluna: i, direcao: ordem.direcao === "asc" ? "desc" : "asc" }
            : { coluna: i, direcao: c.num ? "desc" : "asc" };
          desenhar();
        } }, c.rotulo, h("span", { class: "seta", "aria-hidden": "true" }, "↕")));
    } else th.append(c.rotulo);
    return th;
  });
  const t = h("table", {}, h("caption", { class: o.legendaVisivel ? "visivel" : "sr-only" }, legenda || ""),
    h("thead", {}, h("tr", {}, ths)));
  const tbody = h("tbody");
  t.append(tbody);
  if (o.rodape) t.append(h("tfoot", {}, h("tr", {}, colunas.map((c, i) =>
    h("td", { class: [c.num ? "num" : "", i === 0 && fixar ? "fixa" : ""].filter(Boolean).join(" ") || null }, o.rodape[i] ?? "")))));

  const textoBusca = l => semAcento(colunas.map(c => { const v = c.valor(l); return typeof v === "string" ? v : ""; }).join(" "));
  const indiceBusca = comBusca ? new Map(linhas.map(l => [l, textoBusca(l)])) : null;
  const atual = () => {
    let lista = filtro ? linhas.filter(l => indiceBusca.get(l).includes(filtro)) : linhas.slice();
    if (ordem) {
      const c = colunas[ordem.coluna], chave = c.ordem || c.valor, sinal = ordem.direcao === "asc" ? 1 : -1;
      lista.sort((a, b) => {
        const va = chave(a), vb = chave(b);
        if (nulo(va) || va === "" || nulo(vb) || vb === "") return compararValores(va, vb);
        return sinal * compararValores(va, vb);
      });
    }
    return lista;
  };
  function celula(c, l, i) {
    const bruto = c.valor(l);
    const conteudo = c.render ? c.render(l) : (nulo(bruto) ? semDado() : (c.fmt ? c.fmt(bruto) : bruto));
    const classes = [c.num ? "num" : "", i === 0 && fixar ? "fixa" : "", c.classe || ""].filter(Boolean).join(" ");
    return h("td", { class: classes || null }, conteudo);
  }
  function desenhar() {
    const lista = atual();
    const mostradas = aberta || lista.length <= inicio ? lista : lista.slice(0, inicio);
    limpar(tbody);
    for (const l of mostradas) {
      const classe = (o.classeLinha && o.classeLinha(l)) || (o.destacar && o.destacar(l) ? "destaque" : null);
      tbody.append(h("tr", { class: classe }, colunas.map((c, i) => celula(c, l, i))));
    }
    if (!mostradas.length) tbody.append(h("tr", {}, h("td", { colspan: String(colunas.length), class: "muted" }, "Nenhuma linha corresponde à busca.")));
    ths.forEach((th, i) => {
      const seta = th.querySelector(".seta");
      if (ordem && ordem.coluna === i) {
        th.setAttribute("aria-sort", ordem.direcao === "asc" ? "ascending" : "descending");
        if (seta) seta.textContent = ordem.direcao === "asc" ? "↑" : "↓";
      } else { th.removeAttribute("aria-sort"); if (seta) seta.textContent = "↕"; }
    });
    contagem.textContent = (mostradas.length < lista.length ? "Mostrando " + nf(mostradas.length) + " de " + nf(lista.length) : nf(lista.length) + " linha(s)")
      + (filtro ? " encontradas (de " + nf(linhas.length) + ")" : "") + ".";
    botaoMais.hidden = lista.length <= inicio;
    botaoMais.textContent = aberta ? "Mostrar menos" : "Mostrar todas as " + nf(lista.length) + " linhas";
    botaoMais.setAttribute("aria-expanded", String(aberta));
  }
  const ferramentas = h("div", { class: "tabela-ferramentas" }, busca, contagem,
    h("span", { class: "direita" }, o.csv ? h("button", { type: "button", class: "leve", onclick: () => baixarCSV(o.csv, colunas, atual()) }, "Baixar CSV") : null,
      o.xlsx ? h("button", { type: "button", class: "leve", title: "Planilha com os filtros ativos registrados na aba \"Recorte\"", onclick: () => {
        const lista = atual();
        const extra = [["Busca nesta tabela", filtro ? busca.value : "nenhuma"],
          ["Ordenação", ordem ? colunas[ordem.coluna].rotulo + (ordem.direcao === "asc" ? " (crescente)" : " (decrescente)") : "a da página"],
          ["Linhas exportadas", lista.length + " de " + linhas.length]];
        baixarPlanilha(o.xlsx, colunas, lista, (typeof o.recorte === "function" ? o.recorte() : o.recorte || []).concat(extra));
      } }, "Baixar Excel") : null));
  bloco.append(ferramentas,
    h("div", { class: "tabela-wrap", tabindex: "0", role: "region", "aria-label": legenda || "Tabela" }, t),
    h("div", { class: "acoes-tabela" }, botaoMais));
  desenhar();
  return bloco;
}

/** Tabela recolhida sob "Valores por trás do gráfico" — a tabela gêmea de cada gráfico. */
function blocoTabela(titulo, colunas, linhas, arquivo, opcoes) {
  return h("details", { class: "tab" },
    h("summary", {}, "Valores por trás do gráfico — " + titulo + " (" + nf(linhas.length) + " linhas)"),
    tabela(colunas, linhas, titulo, { csv: arquivo, ...(opcoes || {}) }));
}

/* ------------------------------------------------------------------ tooltip */
let _tooltip = null;
function tooltipSvg() {
  if (!_tooltip) { _tooltip = h("div", { class: "tooltip-svg", "aria-hidden": "true" }); document.body.append(_tooltip); }
  return _tooltip;
}
function mostrarDica(evt, linhas) {
  const t = limpar(tooltipSvg());
  linhas.forEach((l, i) => t.append(h("div", { class: i === 0 ? "valor" : "rotulo" }, l)));
  t.style.display = "block";
  const r = evt.target.getBoundingClientRect();
  const x = evt.clientX !== undefined && evt.clientX !== 0 ? evt.clientX : r.left + r.width / 2;
  const y = evt.clientY !== undefined && evt.clientY !== 0 ? evt.clientY : r.top;
  t.style.left = Math.max(8, Math.min(innerWidth - t.offsetWidth - 8, x + 14)) + "px";
  t.style.top = Math.max(8, Math.min(innerHeight - t.offsetHeight - 8, y + 14)) + "px";
}
function esconderDica() { if (_tooltip) _tooltip.style.display = "none"; }

/* ----------------------------------------------------- redimensionamento
   Redimensionar a janela redesenha SÓ o que depende da largura (os gráficos em
   SVG). Antes a página inteira era remontada: os <details> abertos fechavam, a
   lista expandida encolhia e a rolagem saltava. */
const REDESENHOS = [];
function redesenhavel(fabrica) {
  const caixa = h("div", { class: "redesenhavel" }, fabrica());
  REDESENHOS.push({ caixa, fabrica });
  return caixa;
}
function redesenharTudo() {
  for (const r of REDESENHOS) if (r.caixa.isConnected) limpar(r.caixa).append(r.fabrica());
}
/** A altura da barra fixa vira variável CSS, para as âncoras não ficarem escondidas sob ela. */
function medirContexto() {
  const barra = $(".contexto");
  document.documentElement.style.setProperty("--altura-contexto", (barra ? barra.offsetHeight : 0) + "px");
}
/** Ao imprimir, abre o que está recolhido: o papel impresso não pode perder a tabela. */
addEventListener("beforeprint", () => document.querySelectorAll("main details:not([open])").forEach(d => { d.open = true; d.dataset.abertoParaImprimir = "1"; }));
addEventListener("afterprint", () => document.querySelectorAll("main details[data-aberto-para-imprimir]").forEach(d => { d.open = false; delete d.dataset.abertoParaImprimir; }));
