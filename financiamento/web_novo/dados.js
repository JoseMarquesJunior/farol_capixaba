"use strict";
/* ============================================================================
   O dataset embutido e os índices sobre ele. Escrito para aguentar o dataset
   reduzido do papel de trabalho do CNCA (só meta e entes): toda tabela ausente
   vira lista vazia, em vez de derrubar a página.
   ========================================================================== */
const D = JSON.parse(document.getElementById("dataset").textContent);
const META = D.meta;
const ANOS = META.anos || [];
const MAX_COMPARAR = 4;
const FORMAS = ["circle", "rect", "triangle", "rectRot"]; // canal secundário além da cor

const ENTES = new Map((D.entes || []).map(e => [e.cod_ibge, e]));
const MUNICIPIOS = (D.entes || []).filter(e => e.esfera === "M");
const COD_ESTADO = ((D.entes || []).find(e => e.esfera === "E") || {}).cod_ibge;
const LINHA = new Map((D.anual || []).map(r => [r.cod_ibge + "|" + r.ano, r]));
const BIM = new Map();
for (const b of D.bimestral || []) BIM.set(b.cod_ibge + "|" + b.ano + "|" + b.bimestre, b);
const SUB = new Map();  // cod_ibge|ano -> [subfunções, da maior para a menor]
for (const s of D.subfuncoes || []) {
  const k = s.cod_ibge + "|" + s.ano;
  if (!SUB.has(k)) SUB.set(k, []);
  SUB.get(k).push(s);
}
const CATALOGO_SUB = D.catalogo_subfuncoes || [];
const NOME_SUB = new Map(CATALOGO_SUB.map(s => [s.codigo, s.nome]));
const nomeEnte = cod => (ENTES.get(cod) || {}).nome || String(cod);

/** Expande uma tabela colunar do dataset: nomes uma vez, linhas em listas e, para
 *  as colunas de texto repetitivo, índices num dicionário de valores distintos. */
function expandir(t) {
  if (!t || !t.colunas) return [];
  const dic = t.dicionario || {};
  return t.linhas.map(l => {
    const o = {};
    t.colunas.forEach((c, i) => { const v = l[i]; o[c] = dic[c] && v !== null && v !== undefined ? dic[c][v] : v; });
    return o;
  });
}
function agrupar(linhas, chave) {
  const m = new Map();
  for (const l of linhas) { const k = chave(l); if (!m.has(k)) m.set(k, []); m.get(k).push(l); }
  return m;
}
const chaveEA = (cod, ano) => cod + "|" + ano;
const CONSULTAS = new Map(expandir(D.consultas).map(c => [c.id, { ...c, url: (c.url_base || "") + (c.url_resto || "") }]));
const SIOPE = new Map(expandir(D.siope).map(s => [chaveEA(s.cod_ibge, s.ano), s]));
const ORIGEM = agrupar(expandir(D.origem), o => chaveEA(o.cod_ibge, o.ano));
const FLUXO = agrupar(expandir(D.fluxo), f => chaveEA(f.cod_ibge, f.ano));
const NATUREZA = agrupar(expandir(D.natureza), n => chaveEA(n.cod_ibge, n.ano));
const ENTREGAS = agrupar(expandir(D.entregas), e => chaveEA(e.cod_ibge, e.ano));
const REPASSES = agrupar(expandir(D.repasses), r => chaveEA(r.cod_ibge, r.ano));

/** Cor fixa por ORIGEM do recurso, igual em todo o painel (a cor segue a entidade). */
const SLOT_ORIGEM = { impostos: 0, impostos_proprios: 0, fundeb: 1, federal: 2, federal_especifica: 2, outras: 3 };
const ORDEM_ORIGEM = ["impostos_proprios", "fundeb", "federal_especifica", "outras"];
const ORDEM_GRUPO = ["impostos", "fundeb", "federal", "outras"];

const NOME_SUBFUNCAO_CURTO = { "361": "Ensino fundamental", "365": "Educação infantil", "122": "Administração geral",
  "367": "Educação especial", "366": "Educação de jovens e adultos", "362": "Ensino médio", "363": "Ensino profissional",
  "364": "Ensino superior", "306": "Alimentação e nutrição", "368": "Educação básica", "782": "Transporte rodoviário" };
const nomeSubfuncao = cod => NOME_SUBFUNCAO_CURTO[cod] || NOME_SUB.get("12." + cod) || ("subfunção " + cod);
/** Subfunções que não são competência típica de município (art. 211 CF). Aparecer
 *  aqui não é irregularidade — é um ponto que merece olhar. */
const SUB_FORA_DA_PRIORIDADE = new Set(["12.362", "12.363", "12.364"]);
const SUB_ADMINISTRACAO = "12.122";

/* ------------------------------------------------------------- métricas */
const METRICAS = {
  desp: { rotulo: "Despesa em Educação (R$, empenhada)", curto: "Em R$ (despesa total)", campo: "desp_educacao_empenhada", tipo: "moeda",
    nota: "Despesa empenhada na função 12 (Educação), exceto intra-orçamentárias — DCA Anexo I-E. Valores nominais." },
  pm: { rotulo: "Despesa em Educação por matrícula (R$/matrícula)", curto: "Por matrícula (R$/matrícula)", campo: "desp_educacao_por_matricula", tipo: "moeda2",
    nota: "Despesa empenhada em Educação ÷ matrículas da rede municipal no exercício (coluna \"Alunos\" do recurso \"Educação\" do TCE-ES, conferida contra o Censo Escolar). Só municípios." },
  pc: { rotulo: "Despesa em Educação per capita (R$/hab.)", curto: "Per capita (R$/hab.)", campo: "desp_educacao_per_capita", tipo: "moeda2",
    nota: "Despesa empenhada em Educação ÷ população do exercício, como o SICONFI a reporta. Essa população só muda a cada dois exercícios: parte da variação anual é mudança do denominador." },
  pct: { rotulo: "Educação em % da despesa total do ente", curto: "% da despesa total", campo: "desp_educacao_pct_total", tipo: "pct",
    nota: "Função 12 ÷ despesa total empenhada do ente (exceto intra-orçamentárias). Não é o índice de MDE." },
  fundeb: { rotulo: "Receita do FUNDEB ÷ despesa em Educação (%)", curto: "FUNDEB ÷ despesa", campo: "fundeb_pct_desp_educacao", tipo: "pct",
    nota: "Receita bruta do FUNDEB recebida (DCA Anexo I-C) ÷ despesa em Educação. É a participação pelo lado da RECEITA — não a despesa custeada pelo FUNDEB." },
  admin: { rotulo: "Administração geral em % da Educação", curto: "Administração geral (%)", campo: "__sub:12.122", tipo: "pct",
    nota: "Subfunção 12.122 (Administração Geral) ÷ despesa em Educação. Município sem essa subfunção declarada aparece como “sem dado”, não como 0%." },
};
const fmtMetrica = (m, v) => nulo(v) ? "sem dado" :
  m.tipo === "moeda" ? brlCompacto(v) : m.tipo === "moeda2" ? brl(v) : nf(v, 1) + "%";
const fmtMetricaCheio = (m, v) => nulo(v) ? "sem dado" :
  m.tipo === "moeda" || m.tipo === "moeda2" ? brl(v) : nf(v, 2) + "%";

/** Subfunções cujo "por matrícula" divide pelas matrículas da PRÓPRIA etapa na rede municipal
 *  (Censo Escolar do mesmo ano), e não pelo total: só o ensino fundamental e o médio. */
const ETAPA_DA_SUBFUNCAO = { "12.361": { campo: "censo_mat_fund", etapa: "ensino fundamental" }, "12.362": { campo: "censo_mat_med", etapa: "ensino médio" } };
const etapaDaMetrica = m => m.campo.startsWith("__subv:") && m.campo.endsWith(":pm") ? ETAPA_DA_SUBFUNCAO[m.campo.split(":")[1]] || null : null;

/** Indicador do catálogo (meta.indicadores) por trás de cada métrica. */
function indicadorDaMetrica(m) {
  if (etapaDaMetrica(m)) return "subfuncao_por_matricula_etapa";
  return ({ desp_educacao_empenhada: "desp_educacao_empenhada", desp_educacao_per_capita: "desp_educacao_per_capita",
    desp_educacao_pct_total: "desp_educacao_pct_total", fundeb_pct_desp_educacao: "fundeb_pct_desp_educacao",
    desp_educacao_por_matricula: "desp_educacao_por_matricula" })[m.campo] || "subfuncao_empenhada";
}
/** Consultas de origem de uma métrica num ente-ano (as derivadas citam os dois lados). */
function qDaMetrica(m, cod, ano) {
  const r = LINHA.get(cod + "|" + ano) || {};
  if (m.campo === "fundeb_pct_desp_educacao") return [r.q_dca_ie, r.q_dca_ic].filter(Boolean).join(";");
  if (etapaDaMetrica(m)) return [r.q_dca_ie, r.q_censo_mat].filter(Boolean).join(";");
  if (m.campo === "desp_educacao_por_matricula" || m.campo.endsWith(":pm")) return [r.q_dca_ie, r.q_tcees_mde].filter(Boolean).join(";");
  return r.q_dca_ie || "";  // a subfunção sai da mesma consulta do DCA I-E que a função 12
}
/** Valor de uma métrica, inclusive as derivadas de subfunção: "__sub:12.122" (% da Educação)
 *  e "__subv:<código>:<medida>" — empenhada, pm (por matrícula), pc (per capita),
 *  pct_total (% da despesa total do ente) ou pct_educacao. Município sem a subfunção
 *  declarada fica sem dado, nunca em zero. */
function valorMetrica(m, cod, ano) {
  if (m.campo.startsWith("__sub:")) {
    const codigo = m.campo.slice(6);
    const achado = (SUB.get(cod + "|" + ano) || []).find(s => s.codigo === codigo);
    return achado ? achado.pct_educacao : null;
  }
  if (m.campo.startsWith("__subv:")) {
    const [, codigo, medida] = m.campo.split(":");
    const s = (SUB.get(cod + "|" + ano) || []).find(x => x.codigo === codigo);
    if (!s || nulo(s.empenhada)) return null;
    const r = LINHA.get(cod + "|" + ano) || {};
    const razao = den => den > 0 ? s.empenhada / den : null;
    const etapa = ETAPA_DA_SUBFUNCAO[codigo];  // fundamental e médio: matrículas da própria etapa
    return medida === "empenhada" ? s.empenhada : medida === "pm" ? razao(etapa ? r[etapa.campo] : r.tcees_alunos) : medida === "pc" ? razao(r.populacao)
      : medida === "pct_total" ? (r.desp_total_empenhada > 0 ? 100 * s.empenhada / r.desp_total_empenhada : null)
      : medida === "pct_educacao" ? s.pct_educacao : null;
  }
  const r = LINHA.get(cod + "|" + ano);
  return r ? r[m.campo] : null;
}
/** Posição do ente entre os municípios (1 = maior valor). */
function posicaoNoRanking(m, cod, ano) {
  const com = MUNICIPIOS.map(e => ({ cod: e.cod_ibge, v: valorMetrica(m, e.cod_ibge, ano) }))
    .filter(x => !nulo(x.v)).sort((a, b) => b.v - a.v);
  const i = com.findIndex(x => x.cod === cod);
  return i < 0 ? null : { pos: i + 1, de: com.length };
}
/** "2º maior gasto per capita entre 78" — a posição sozinha não diz a direção. */
const fraseRanking = (p, oque) => p ? p.pos + "º maior " + oque + " entre " + p.de + " municípios" : "fora do ranking";

/* ------------------------------------------------------------- utilitários */
const linhasMun = ano => MUNICIPIOS.map(e => LINHA.get(e.cod_ibge + "|" + ano)).filter(Boolean);
const subDe = (cod, ano) => SUB.get(cod + "|" + ano) || [];
const municipiosPorNome = () => MUNICIPIOS.slice().sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
const MIN_MDE = () => META.minimo_mde_pct;
const MIN_70 = () => META.minimo_fundeb_profissionais_pct;
const siopeDe = (cod, ano) => SIOPE.get(chaveEA(cod, ano)) || {};
const itemUsado = (cod, ano, campo_) => { try { return JSON.parse(siopeDe(cod, ano).itens_usados || "{}")[campo_]; } catch (e) { return null; } };

/** Seletor de ente. `comEstado` inclui o Estado num grupo à parte. */
function seletorEnte(id, valor, aoEscolher, opcoes) {
  const o = opcoes || {};
  const s = h("select", { id, onchange: e => { const v = e.target.value; if (v || o.permiteVazio) aoEscolher(v ? +v : null); if (o.limpaApos) e.target.value = ""; } });
  if (o.vazio) s.append(h("option", { value: "" }, o.vazio));
  const g = h("optgroup", { label: "Municípios (" + MUNICIPIOS.length + ")" });
  municipiosPorNome().forEach(x => g.append(h("option", { value: x.cod_ibge }, x.nome)));
  s.append(g);
  if (o.comEstado && COD_ESTADO) {
    s.append(h("optgroup", { label: "Estado (fora de somas e rankings)" },
      h("option", { value: COD_ESTADO }, nomeEnte(COD_ESTADO) + " — Estado")));
  }
  if (valor) s.value = valor;
  return s;
}
function seletorAno(id, valor, aoEscolher) {
  const s = h("select", { id, onchange: e => aoEscolher(+e.target.value) });
  ANOS.slice().reverse().forEach(a => s.append(h("option", { value: a }, a + (a === META.ano_mais_recente ? " (mais recente)" : ""))));
  s.value = valor;
  return s;
}
function kpi(rot, val, det, extra) {
  const x = extra || {};
  return h("div", { class: "kpi" + (x.estado ? " " + x.estado : "") },
    h("div", { class: "rot" }, rot),
    h("div", { class: "val" + (x.nd ? " nd" : "") }, x.estado && ESTADOS[x.estado] ? h("span", { "aria-hidden": "true" }, ESTADOS[x.estado].simbolo + " ") : null, val),
    det ? h("div", { class: "det" }, det) : null,
    x.acoes ? h("div", { class: "acoes-kpi" }, x.acoes) : null);
}

/* ------------------------------------------- registros manuais e automáticos */
/** Registros de um campo de programa: os manuais (dados_manuais.yaml) e, para campo de
 *  origem "api", os automáticos gerados pelo ETL (programas_api), no mesmo formato. */
function todosRegistros(pid, campoId) {
  return [].concat((((D.dados_manuais || {}).programas || {})[pid] || {})[campoId] || [],
    (((D.programas_api || {})[pid] || {})[campoId]) || []);
}
function registrosDe(pid, campoId, cod) {
  return todosRegistros(pid, campoId).filter(r => r.cod_ibge === cod && r.verificado).sort((a, b) => (b.ano || 0) - (a.ano || 0));
}
function rotuloValor(campo_, v) {
  if (campo_.tipo === "categorico") return (campo_.rotulos_valores || {})[v] || String(v);
  if (campo_.tipo === "moeda") return brl(v);
  if (campo_.tipo === "percentual") return nf(v, 1) + "%";
  if (campo_.tipo === "quantidade") return nf(v);
  return String(v);
}
function badgeRegistro(r) {
  if (r.automatico) return h("span", { class: r.situacao === "sem_dado" ? "badge nada" : "badge api" },
    r.situacao === "sem_dado" ? "automático · a fonte não publicou o valor" : "automático" + (r.escolas ? " · " + r.escolas + " escola(s)" : ""));
  return h("span", { class: r.situacao === "sem_amostra" ? "badge aviso" : "badge manual" },
    "registro manual · verificado em " + dataBR(r.verificado_em));
}
/** Municípios com ao menos um campo verificado no programa, separados em automático e manual. */
function municipiosComRegistro(p, origem) {
  const com = new Set();
  for (const campo_ of p.campos) {
    if (origem && (origem === "api") !== (campo_.origem === "api")) continue;
    for (const r of todosRegistros(p.id, campo_.id)) if (r.verificado) com.add(r.cod_ibge);
  }
  return com;
}
