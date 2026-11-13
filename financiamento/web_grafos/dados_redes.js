"use strict";
/* ============================================================================
   Dados das redes: o JSON embutido (gerado por `etl/grafos.py`) e as somas que
   as visões usam. Tudo é calculado aqui, no navegador, a partir das ligações
   município × fornecedor × mercado com os valores por exercício e origem — por
   isso qualquer combinação de filtros dá números que fecham entre si.
   ========================================================================== */
const DADOS = JSON.parse(document.getElementById("dados-redes").textContent);
const CONFIG = JSON.parse(document.getElementById("config-redes").textContent);
const META = DADOS.meta;
const ANOS = META.anos;
const MERCADOS = META.mercados;
const MERCADO = Object.fromEntries(MERCADOS.map((m, i) => [m.id, { ...m, i }]));
const ROTULO_MERCADO = id => id === "todos" ? "Todos os mercados" : (MERCADO[id] || {}).rotulo || id;
const FONTES = META.fontes;
const TIPOS = META.tipos;
const ROTULO_TIPO = Object.fromEntries(TIPOS.map(t => [t.id, t.rotulo]));
const MUN = DADOS.municipios;
const IDX_MUN = new Map(MUN.map((m, i) => [m.cod, i]));
const FORN = DADOS.fornecedores.linhas.map(l => ({ raiz: l[0], nome: l[1], tipo: l[2], cnpjs: l[3] ? String(l[3]).split(";") : [] }));
const IDX_FORN = new Map(FORN.map((f, i) => [f.raiz, i]));
const AR = DADOS.arestas;
const NA = AR.m.length;
const ACOES = DADOS.acoes;
const PUBLICOS = new Set(["publico", "concessionaria"]);

/** Faixas de alcance do fornecedor (nº de municípios atendidos no recorte). */
const ALCANCES = [
  { id: 0, rotulo: "local (2 a 4 municípios)", min: 2, max: 4 },
  { id: 1, rotulo: "regional (5 a 14)", min: 5, max: 14 },
  { id: 2, rotulo: "estadual (15 ou mais)", min: 15, max: Infinity },
];
const alcanceDe = k => k >= 15 ? 2 : k >= 5 ? 1 : 0;

/* --------------------------------------------------------------- formato */
function fmtCnpj(d) {
  const s = String(d || "").replace(/\D/g, "");
  if (s.length === 14) return s.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
  if (s.length === 8) return s.replace(/^(\d{2})(\d{3})(\d{3})$/, "$1.$2.$3");
  return String(d || "");
}
const pct0 = v => nulo(v) ? "sem dado" : nf(v, v < 10 ? 1 : 0) + "%";
function classeHhi(v) {
  if (nulo(v)) return "sem dado";
  // Faixas do Guia de Análise de Atos de Concentração do CADE (e do DOJ/FTC, 2010).
  return v < 1500 ? "baixa" : v <= 2500 ? "moderada" : "alta";
}
const nomeMun = i => MUN[i] ? MUN[i].nome : "?";

/* ------------------------------------------------------------- recorte
   filtro = { mercado: "todos"|id, ano: null|índice em ANOS, fonte: null|índice, tipos: Set } */
const _cache = new Map();
function chaveFiltro(fl) { return [fl.mercado, fl.ano, fl.fonte, [...fl.tipos].sort().join(",")].join("|"); }

/** Ligações município × fornecedor no recorte, com as somas por fornecedor e por município. */
function agregar(fl) {
  const chave = chaveFiltro(fl);
  if (_cache.has(chave)) return _cache.get(chave);
  const ki = fl.mercado === "todos" ? -1 : MERCADO[fl.mercado].i;
  const ligacoes = new Map();
  for (let i = 0; i < NA; i++) {
    if (ki >= 0 && AR.k[i] !== ki) continue;
    const f = AR.f[i];
    if (!fl.tipos.has(FORN[f].tipo)) continue;
    const v = AR.v[i];
    let emp = 0, pag = 0;
    for (let j = 0; j < v.length; j += 4) {
      if (fl.ano !== null && v[j] !== fl.ano) continue;
      if (fl.fonte !== null && v[j + 1] !== fl.fonte) continue;
      emp += v[j + 2]; pag += v[j + 3];
    }
    if (!(emp > 0.005 || pag > 0.005)) continue;
    const id = AR.m[i] * 100000 + f;
    let l = ligacoes.get(id);
    if (!l) { l = { m: AR.m[i], f, emp: 0, pag: 0, acao: null, _a: -Infinity, nAcoes: 0, mercados: [] }; ligacoes.set(id, l); }
    l.emp += emp; l.pag += pag; l.nAcoes += AR.n_acoes[i]; l.mercados.push([AR.k[i], emp]);
    if (emp > l._a) { l._a = emp; l.acao = AR.acao[i]; }
  }
  const lista = [...ligacoes.values()];
  const porForn = new Map(), porMun = new Map();
  for (const l of lista) {
    let f = porForn.get(l.f);
    if (!f) { f = { f: l.f, emp: 0, pag: 0, ligs: [] }; porForn.set(l.f, f); }
    f.emp += l.emp; f.pag += l.pag; f.ligs.push(l);
    let m = porMun.get(l.m);
    if (!m) { m = { m: l.m, emp: 0, pag: 0, ligs: [] }; porMun.set(l.m, m); }
    m.emp += l.emp; m.pag += l.pag; m.ligs.push(l);
  }
  for (const f of porForn.values()) f.k = f.ligs.filter(l => l.emp > 0.005).length;
  let total = 0, compartilhado = 0;
  for (const m of porMun.values()) {
    const pos = m.ligs.filter(l => l.emp > 0.005);
    m.nForn = pos.length;
    m.hhi = hhiDe(pos.map(l => l.emp));
    const maior = pos.reduce((a, b) => (!a || b.emp > a.emp ? b : a), null);
    m.maior = maior;
    m.maiorPct = maior && m.emp > 0 ? maior.emp / m.emp * 100 : null;
    m.compartilhado = pos.filter(l => porForn.get(l.f).k >= 2).reduce((s, l) => s + l.emp, 0);
    total += Math.max(0, m.emp); compartilhado += m.compartilhado;
  }
  const r = { lista, porForn, porMun, total, compartilhado };
  _cache.set(chave, r);
  return r;
}
function hhiDe(valores) {
  const v = valores.filter(x => x > 0), s = v.reduce((a, b) => a + b, 0);
  if (!v.length || s <= 0) return null;
  return v.reduce((a, x) => a + (x / s * 100) ** 2, 0);
}

/** Pessoa física e outros identificadores do município (fora da rede), no mesmo recorte de mercado/ano/origem. */
function residuaisDe(m, fl) {
  const ki = fl.mercado === "todos" ? -1 : MERCADO[fl.mercado].i;
  const r = { pf: 0, outro: 0 };
  for (const x of DADOS.residuais) {
    if (x[0] !== m || (ki >= 0 && x[1] !== ki) || (fl.ano !== null && x[2] !== fl.ano) || (fl.fonte !== null && x[3] !== fl.fonte)) continue;
    r[x[4]] = (r[x[4]] || 0) + x[5];
  }
  return r;
}

/** Valores de um fornecedor por exercício, por origem e por mercado (respeitando só o filtro de município). */
function perfilFornecedor(f, fl) {
  const porAno = ANOS.map(() => 0), porFonte = FONTES.map(() => 0), porMercado = new Map();
  for (let i = 0; i < NA; i++) {
    if (AR.f[i] !== f) continue;
    const v = AR.v[i];
    for (let j = 0; j < v.length; j += 4) {
      const anoOk = fl.ano === null || v[j] === fl.ano, fonteOk = fl.fonte === null || v[j + 1] === fl.fonte;
      const mercadoOk = fl.mercado === "todos" || AR.k[i] === MERCADO[fl.mercado].i;
      if (mercadoOk && fonteOk) porAno[v[j]] += v[j + 2];
      if (mercadoOk && anoOk) porFonte[v[j + 1]] += v[j + 2];
      if (anoOk && fonteOk) porMercado.set(AR.k[i], (porMercado.get(AR.k[i]) || 0) + v[j + 2]);
    }
  }
  return { porAno, porFonte, porMercado };
}

/* ------------------------------------------------------------ ver fonte */
function consultasDe(ids) {
  return String(ids || "").split(";").filter(Boolean).map(id => ({ id, ...(META.consultas[id] || { descricao: "consulta " + id }) }));
}
function qEmpenhos(fl) {
  const anos = fl.ano === null ? ANOS : [ANOS[fl.ano]];
  return anos.map(a => META.q_empenhos[String(a)] || "").filter(Boolean).join(";");
}
/** Diálogo "ver fonte": as consultas exatas e o passo a passo para refazer o número. */
function abrirFonte(titulo, ids, passos, notas) {
  const d = $("#dialogo-fonte");
  limpar(d);
  const lista = consultasDe(ids);
  anexar(d,
    h("header", {}, h("h2", { id: "fonte-titulo" }, "Fonte — " + titulo),
      h("button", { type: "button", class: "leve fechar", "aria-label": "Fechar", onclick: () => d.close() }, "×")),
    passos && passos.length ? h("section", {}, h("h3", {}, "Como chegar a este número"), h("ol", { class: "lista" }, passos.map(p => h("li", {}, p)))) : null,
    notas ? h("p", { class: "nota" }, notas) : null,
    h("h3", {}, lista.length === 1 ? "Consulta" : lista.length + " consultas"),
    lista.map(c => h("div", { class: "fonte-item" },
      h("h3", {}, c.descricao || c.id),
      h("dl", {},
        h("dt", {}, "Fonte"), h("dd", {}, c.fonte || "—"),
        h("dt", {}, "Endereço"), h("dd", {}, c.url ? h("a", { href: c.url, target: "_blank", rel: "noopener" }, c.url) : "—"),
        h("dt", {}, "Coletado em"), h("dd", {}, dataHoraBR(c.obtido_em)),
        h("dt", {}, "Arquivo no cache"), h("dd", {}, h("code", {}, "financiamento/dados/bruto/" + (c.arquivo || "—"))),
        c.sha256 ? [h("dt", {}, "SHA-256 do original"), h("dd", {}, h("code", {}, c.sha256))] : null,
        h("dt", {}, "Identificador"), h("dd", {}, h("code", {}, c.id))))),
    h("footer", {}, h("span", { class: "nota" }, "O mesmo identificador aparece no painel de financiamento e em dados/processado/consultas.csv.")));
  d.showModal();
}
function botaoFonte(rotulo, fabrica) {
  return h("button", { type: "button", class: "ver-fonte", onclick: () => { const [t, ids, passos, notas] = fabrica(); abrirFonte(t, ids, passos, notas); } }, "ver fonte", rotulo ? " — " + rotulo : null);
}

/** append que achata listas e ignora nulo (o append do DOM escreveria "null" ou "[object …]"). */
function anexar(el, ...filhos) {
  for (const f of filhos.flat(Infinity)) if (f !== null && f !== undefined && f !== false) el.append(f);
  return el;
}
