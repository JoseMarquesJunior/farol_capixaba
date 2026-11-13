"use strict";
/* ============================================================================
   Dossiê da empresa: "Análise profunda" e "Análise com IA".

   A parte "Na rede" usa só o dado embutido e funciona até com o arquivo aberto
   direto. O dossiê e a IA precisam do servidor local (servidor_redes.py), que
   guarda tudo em disco: pedir de novo devolve o que já foi feito — sem ir às
   fontes e sem gastar tokens. Só "Atualizar dossiê" e "Refazer análise" refazem.
   ========================================================================== */
const SERVIDOR = { verificado: false, ok: false, ia: false, modelo: null };
const EV = { raiz: null, geracao: 0 };

async function api(caminho, corpo) {
  const r = await fetch(caminho, { method: corpo ? "POST" : "GET", headers: { "X-Redes": "1", "Content-Type": "application/json" },
    body: corpo ? JSON.stringify(corpo) : undefined });
  return { status: r.status, corpo: await r.json().catch(() => ({})) };
}
async function verificarServidor() {
  if (SERVIDOR.verificado) return SERVIDOR;
  SERVIDOR.verificado = true;
  if (!location.protocol.startsWith("http")) return SERVIDOR;
  try {
    const { status, corpo } = await api("/api/status");
    SERVIDOR.ok = status === 200; SERVIDOR.ia = !!corpo.ia_disponivel; SERVIDOR.modelo = corpo.modelo;
  } catch (e) { SERVIDOR.ok = false; }
  return SERVIDOR;
}
/** Acompanha uma tarefa do servidor, mostrando as etapas, até terminar. */
async function acompanhar(tid, caixa, geracao) {
  for (;;) {
    await new Promise(r => setTimeout(r, 1200));
    if (geracao !== EV.geracao) return null;          // o usuário saiu da página
    const { corpo: t } = await api("/api/tarefa/" + tid);
    anexar(limpar(caixa), h("ol", { class: "etapas" }, (t.etapas || []).map((e, i, a) => h("li", { class: i === a.length - 1 && t.estado === "rodando" ? "atual" : null }, e.texto))));
    if (t.estado !== "rodando") return t;
  }
}

function filtrosEmpresa() { return null; }
function recorteEmpresa() { const n = nomeEmpresa(); return [h("strong", {}, "Dossiê"), " de ", h("strong", {}, n)]; }
function recorteCurtoEmpresa() { return "Dossiê"; }
function raizEmpresa() { return (estado.sel || "").startsWith("f:") ? estado.sel.slice(2) : null; }
function nomeEmpresa() {
  const raiz = raizEmpresa(), f = IDX_FORN.get(raiz);
  if (f !== undefined) return FORN[f].nome;
  const c = OBRAS.contratadas.find(x => x.id === raiz);
  return c ? c.nome : "empresa " + fmtCnpj(raiz || "");
}
function botaoAcao(rotulo, aoClicar, opcoes) {
  const o = opcoes || {};
  return h("button", { type: "button", class: "botao-acao" + (o.secundario ? " secundario" : ""), disabled: o.desativado ? true : null, title: o.titulo || null, onclick: aoClicar }, rotulo);
}

/* ------------------------------------------------------------ página */
function renderEmpresa(main) {
  const raiz = raizEmpresa();
  EV.raiz = raiz; EV.geracao++;
  const geracao = EV.geracao;
  if (!raiz) { main.append(h("p", {}, "Empresa não informada."), linkPara({ visao: "fornecedores", sel: null }, "← Voltar à rede")); return; }
  const f = IDX_FORN.get(raiz);
  main.append(h("p", { class: "voltar-lado" }, linkPara({ visao: "fornecedores", sel: "f:" + raiz }, "← Voltar à rede de fornecedores")),
    h("section", { class: "cab-visao compacta" }, h("h2", {}, nomeEmpresa()),
      h("p", { class: "frase" }, "CNPJ raiz " + fmtCnpj(raiz) + (f !== undefined ? " · " + ROTULO_TIPO[FORN[f].tipo] : "")
        + ". O que a empresa recebeu da Educação, o que os dados abertos dizem dela e o que os documentos mostram — com a fonte de cada informação. São pontos para orientar a verificação, não conclusões.")));
  main.append(cardNaRede(raiz, f));
  const caixaDossie = h("div", {}), caixaIa = h("div", {});
  main.append(h("article", { class: "card dossie", id: "card-dossie" }, h("header", {}, h("h3", {}, "Análise profunda — dossiê da empresa"),
      h("p", { class: "simples" }, "Contratos no TCE-ES, preços comparados com outros municípios, cadastro na Receita, sanções, PNCP e diários oficiais. Não usa IA. Fica gravado: abrir de novo não refaz a coleta.")), caixaDossie),
    h("article", { class: "card dossie", id: "card-ia" }, h("header", {}, h("h3", {}, "Análise com IA"),
      h("p", { class: "simples" }, "O Claude lê os contratos, editais e publicações do dossiê e aponta o que verificar primeiro, citando documento, página e trecho — cada trecho é conferido no documento. Antes de chamar, a página mostra quanto vai custar.")), caixaIa));
  verificarServidor().then(s => {
    if (geracao !== EV.geracao) return;
    if (!s.ok) {
      const aviso = () => h("div", { class: "callout" }, h("strong", {}, "Precisa do servidor local. "), "Esta parte busca dados nas fontes públicas e grava os resultados no computador. Rode:",
        h("pre", {}, h("code", {}, "python -m financiamento.servidor_redes --abrir")), "e use a página que ele abre (http://127.0.0.1:8765/).");
      anexar(caixaDossie, aviso()); anexar(caixaIa, aviso());
      return;
    }
    carregarDossie(raiz, caixaDossie, caixaIa, geracao, false);
  });
}

function cardNaRede(raiz, f) {
  if (f === undefined) return h("article", { class: "card" }, h("h3", {}, "Na rede"), h("p", { class: "muted" }, "Esta empresa não recebeu empenhos da Educação nas redes (aparece só nas obras)."));
  const todos = { mercado: "todos", ano: null, fonte: null, tipos: new Set(TIPOS.map(t => t.id)) };
  const x = agregar(todos).porForn.get(f), perfil = perfilFornecedor(f, todos);
  const muns = x ? x.ligs.filter(l => l.emp > 0.005).sort((a, b) => b.emp - a.emp) : [];
  const merc = [...perfil.porMercado.entries()].filter(([, v]) => v > 0.005).sort((a, b) => b[1] - a[1]);
  return h("article", { class: "card", id: "card-na-rede" }, h("header", {}, h("h3", {}, "Na rede — empenhos da Educação, " + ANOS[0] + "–" + ANOS[ANOS.length - 1]),
      h("p", { class: "simples" }, "Do dado embutido na página (empenhos declarados ao TCE-ES).")),
    h("div", { class: "grade-dossie" },
      h("div", {}, resumoLado([["Empenhado", x ? brlCompacto(x.emp) : "—", x ? brl(x.emp) + " · pago " + brlCompacto(x.pag) : null],
        ["Municípios", nf(muns.length), muns.slice(0, 4).map(l => nomeMun(l.m)).join(", ") + (muns.length > 4 ? "…" : "")]]),
        h("h4", {}, "Por exercício"), barrasSimples(ANOS.map((a, i) => [String(a), perfil.porAno[i]]), null)),
      h("div", {}, h("h4", {}, "Por mercado"), barrasSimples(merc.map(([k, v]) => [MERCADOS[k].rotulo, v]), null),
        h("h4", {}, "Por origem do recurso"), barrasSimples(FONTES.map((o, i) => [o.rotulo.split(" (")[0], perfil.porFonte[i]]), null))),
    h("details", { class: "tab" }, h("summary", {}, "Municípios (" + muns.length + ")"), tabela([
      { rotulo: "Município", valor: l => nomeMun(l.m) }, { rotulo: "Empenhado", valor: l => l.emp, num: true, fmt: brl }, { rotulo: "Pago", valor: l => l.pag, num: true, fmt: brl },
      { rotulo: "Ação principal", valor: l => l.acao === null ? "" : ACOES[l.acao], classe: "small" }], muns, "Municípios", { inicio: 0, busca: false, csv: "empenhos_" + raiz + ".csv" })));
}

/* ------------------------------------------------------------ dossiê */
async function carregarDossie(raiz, caixa, caixaIa, geracao, atualizar, repetirFalhas) {
  anexar(limpar(caixa), h("p", { class: "muted" }, atualizar || repetirFalhas ? "Indo de novo às fontes…" : "Procurando o dossiê gravado…"));
  let { status, corpo } = atualizar || repetirFalhas ? { status: 404 } : await api("/api/dossie/" + raiz);
  if (status === 200) corpo._reaproveitado = true;     // veio do disco
  if (status !== 200) {
    const r = await api("/api/dossie/" + raiz, { atualizar, repetir_falhas: !!repetirFalhas });
    if (r.status === 200) corpo = r.corpo.resultado;
    else {
      const etapas = h("div", {});
      anexar(limpar(caixa), h("p", {}, h("strong", {}, "Montando o dossiê — "), "as fontes públicas podem levar até alguns minutos (o PNCP é lento)."), etapas);
      const t = await acompanhar(r.corpo.tarefa, etapas, geracao);
      if (!t) return;
      if (t.estado === "erro") { anexar(limpar(caixa), h("p", { class: "callout descumpre" }, "A montagem falhou: " + t.erro)); return; }
      corpo = t.resultado;
    }
  }
  if (geracao !== EV.geracao) return;
  mostrarDossie(raiz, caixa, caixaIa, corpo, geracao);
}
function mostrarDossie(raiz, caixa, caixaIa, d, geracao) {
  anexar(limpar(caixa), ...vistaDossie(d, () => carregarDossie(raiz, caixa, caixaIa, EV.geracao, true), () => carregarDossie(raiz, caixa, caixaIa, EV.geracao, false, true),
    (alvo, refazer) => procurarFaltantes(raiz, caixa, caixaIa, alvo, EV.geracao, refazer)));
  carregarIa(raiz, caixaIa, d, geracao);
}

/* ------------------------------------------------------------ documentos faltantes */
/** Mesmo critério de etl/dossie.py (especifico): o link aponta um documento, não a página inicial de um portal. */
function linkEspecifico(u) {
  if (typeof u !== "string" || !u.startsWith("http")) return false;
  let p; try { p = new URL(u); } catch (e) { return false; }
  if (p.search && /\d{3,}/.test(p.search)) return true;
  return /\.pdf$|\/pdf\/|visualizacoes|\/arquivos?\/|\/download|\d{4,}/i.test(p.pathname.replace(/\/$/, "") + p.hash);
}
function linksDoc(x) {
  return h("span", { class: "links-doc" }, [["contrato", x.url_contrato], ["publicação", x.url_publicacao], ["edital", x.url_edital]]
    .filter(([, u]) => u && u.startsWith("http"))
    .map(([r, u]) => linkEspecifico(u) ? h("a", { href: u, target: "_blank", rel: "noopener" }, r)
      : h("a", { href: u, target: "_blank", rel: "noopener", class: "generico", title: "Link genérico: leva à página inicial do portal, não ao documento" }, r + ": portal")));
}
function semDocumento(c) { return (c.contratos || []).filter(x => !linkEspecifico(x.url_contrato) && !linkEspecifico(x.url_publicacao)); }

function secaoFaltantes(d, procurar) {
  const sem = semDocumento(d.contratos), f = d.faltantes;
  const caixa = h("div", {});
  const valorSem = sem.reduce((s, x) => s + (x.valor_atual || 0), 0);
  const titulo = h("h4", {}, "Documentos faltantes");
  if (!sem.length) return h("section", { class: "dossie-secao", id: "secao-faltantes" }, titulo,
    h("p", { class: "small" }, chipEstado("cumpre", "todos os contratos têm link"), " Todo contrato da empresa no TCE-ES tem link específico de contrato ou de publicação."));
  const cab = h("p", { class: "small" }, h("strong", {}, nf(sem.length) + " de " + nf(d.contratos.contratos.length) + " contrato(s)"), " sem link para o contrato nem para a publicação"
    + (valorSem ? " — " + brlCompacto(valorSem) + " em valor atual" : "") + ". Sem esses documentos a análise não vê objeto, cláusulas, aditivos nem preços: é o que mais limita a leitura.");
  if (!f) {
    anexar(caixa, h("div", { class: "estimativa" },
      h("p", { class: "small" }, "A busca tenta, para os maiores contratos sem documento:"),
      h("ul", { class: "lista small" },
        h("li", {}, h("strong", {}, "PNCP por órgão: "), "os contratos que a prefeitura publicou no PNCP em torno da data de assinatura, casados pelo CNPJ da empresa."),
        h("li", {}, h("strong", {}, "Diário Oficial dos Municípios (DOM-ES): "), "lê as edições da assinatura até três semanas depois e procura o extrato com o CNPJ, o nome e o número do contrato. Cada edição é lida uma vez e serve às outras empresas."),
        h("li", {}, h("strong", {}, "Rotas manuais: "), "onde procurar no portal do município, os termos de busca e um modelo de pedido pela Lei de Acesso à Informação.")),
      h("p", { class: "small muted" }, "Não usa IA. Leva de 1 a 5 minutos por contrato na primeira vez (as edições do Diário são grandes); depois fica gravado."),
      h("div", { class: "acoes-lado" }, botaoAcao("Procurar documentos faltantes", () => procurar(caixa, false)))));
    return h("section", { class: "dossie-secao", id: "secao-faltantes" }, titulo, cab, caixa,
      tabelaSemDoc(sem, "Contratos sem documento"));
  }
  const buscados = new Set(f.itens.map(r => r.contrato.chave));
  anexar(caixa,
    h("p", { class: "nota meta-dossie" }, "Busca gravada em " + dataHoraBR(f.gerado_em) + ": " + nf(f.procurados) + " contrato(s) procurado(s), "
      + nf(f.encontrados) + " com documento achado. Regra: " + f.regra + ". ",
      h("button", { type: "button", class: "link", onclick: () => { if (confirm("Procurar de novo? Vai às fontes outra vez (as edições do Diário já lidas são reaproveitadas).")) procurar(caixa, true); } }, "Procurar de novo")),
    f.itens.map(cartaoFaltante));
  const resto = sem.filter(x => !buscados.has(x.chave));
  return h("section", { class: "dossie-secao", id: "secao-faltantes" }, titulo, cab, caixa,
    resto.length ? tabelaSemDoc(resto, "Outros contratos sem documento, não procurados (" + resto.length + ")") : null);
}
function tabelaSemDoc(lista, titulo) {
  return h("details", { class: "tab" }, h("summary", {}, titulo + (titulo.includes("(") ? "" : " (" + lista.length + ")")), tabela([
    { rotulo: "Município", valor: x => x.municipio }, { rotulo: "Contrato", valor: x => x.numero }, { rotulo: "Assinatura", valor: x => x.assinatura, fmt: dataBR },
    { rotulo: "Valor atual", valor: x => x.valor_atual, num: true, fmt: brl }, { rotulo: "Unidade", valor: x => x.ug, classe: "small" }], lista, titulo, { inicio: 0, busca: false }));
}
const ESTADO_ROTA = { encontrado: ["cumpre", "achado"], nao_encontrado: ["semdado", "não achado"], erro: ["sinal", "falhou"], nao_aplicavel: ["semdado", "não se aplica"] };
function cartaoFaltante(r) {
  const c = r.contrato;
  const paginas = r.rotas.flatMap(x => x.paginas || []), pncp = r.rotas.flatMap(x => x.contratos_pncp || []), docsPncp = r.rotas.filter(x => x.rota.startsWith("PNCP")).flatMap(x => x.documentos || []);
  const pedido = h("textarea", { class: "pedido-lai", readonly: true, rows: 6, "aria-label": "Modelo de pedido de acesso à informação" }, r.modelo_pedido);
  return h("article", { class: "faltante" + (r.situacao === "encontrado" ? " achado" : "") },
    h("div", { class: "insight-topo" }, chipEstado(r.situacao === "encontrado" ? "cumpre" : "sinal", r.situacao === "encontrado" ? "documento achado" : "ainda sem documento")),
    h("h5", {}, c.municipio + " — contrato " + c.numero + (c.valor_atual ? " · " + brl(c.valor_atual) : "")),
    h("p", { class: "small muted" }, (c.ug || "") + " · assinado em " + dataBR(c.assinatura) + (c.arp ? " · ata " + c.arp : "") + " · " + (c.objeto || "").slice(0, 160)),
    h("ul", { class: "lista small rotas" }, r.rotas.map(x => { const [e, t] = ESTADO_ROTA[x.situacao] || ["semdado", x.situacao];
      return h("li", {}, chipEstado(e, t), " ", h("strong", {}, x.rota + ": "), x.detalhe || ""); })),
    paginas.length ? h("div", {}, h("p", { class: "small" }, h("strong", {}, "No Diário Oficial:")), h("ul", { class: "lista-fatos" }, paginas.map(p => h("li", {},
      h("span", { class: "txt" }, h("q", {}, p.trecho.slice(0, 420) + (p.trecho.length > 420 ? "…" : "")), h("span", { class: "small muted" }, " — DOM-ES de " + p.data + ", edição " + p.edicao + ", p. " + p.pagina + (p.casa_numero ? "" : " (casou pelo valor, não pelo número)"))),
      h("span", { class: "acoes-fato" }, h("a", { href: p.url, target: "_blank", rel: "noopener" }, "página em PDF"), " ", h("a", { href: p.visualizar, target: "_blank", rel: "noopener" }, "na edição")))))) : null,
    pncp.length ? h("p", { class: "small" }, h("strong", {}, "No PNCP: "), pncp.map(x => x.numero + "/" + x.ano + " · " + brl(x.valor) + (x.casa_numero ? " (mesmo número)" : "")).join("; "),
      docsPncp.length ? [" · ", docsPncp.map(x => h("a", { href: x.url, target: "_blank", rel: "noopener" }, x.tipo.replace("PNCP: ", "")))] : null) : null,
    h("details", { class: "tab" }, h("summary", {}, "Onde procurar à mão (" + r.orientacao.length + ")"),
      h("ol", { class: "lista small" }, r.orientacao.map(o => h("li", {}, h("strong", {}, o.onde + ": "), o.como + " ", h("a", { href: o.url, target: "_blank", rel: "noopener" }, "abrir"))))),
    h("details", { class: "tab" }, h("summary", {}, "Modelo de pedido ao órgão (Lei de Acesso à Informação)"),
      h("p", { class: "small muted" }, "Para o e-SIC do município ou para a requisição de auditoria. Um extrato no Diário confirma partes, valor e data, mas não substitui o contrato e os aditivos."),
      pedido, h("div", {}, botaoAcao("Copiar o texto", ev => copiarTexto(r.modelo_pedido, ev.currentTarget, pedido), { secundario: true }))));
}
function copiarTexto(texto, botao, campo) {
  const ok = () => { botao.textContent = "Copiado"; anunciar("Texto copiado"); setTimeout(() => { botao.textContent = "Copiar o texto"; }, 2000); };
  const alternativa = () => { campo.select(); try { document.execCommand("copy"); ok(); } catch (e) { anunciar("Selecione o texto e copie com Ctrl+C"); } };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(texto).then(ok, alternativa); else alternativa();
}
async function procurarFaltantes(raiz, caixaDossie, caixaIa, alvo, geracao, refazer) {
  const etapas = h("div", {});
  anexar(limpar(alvo), h("p", {}, h("strong", {}, "Procurando — "), "PNCP por órgão e edições do Diário Oficial. A primeira leitura de cada edição é a parte lenta."), etapas);
  const r = await api("/api/faltantes/" + raiz, { refazer: !!refazer });
  let d;
  if (r.status === 200) d = r.corpo.resultado;
  else if (r.status === 202) {
    const t = await acompanhar(r.corpo.tarefa, etapas, geracao);
    if (!t) return;
    if (t.estado === "erro") { anexar(limpar(alvo), h("p", { class: "callout descumpre" }, "A busca falhou: " + t.erro)); return; }
    d = t.resultado;
  } else { anexar(limpar(alvo), h("p", { class: "callout descumpre" }, r.corpo.erro || "Erro " + r.status)); return; }
  if (geracao !== EV.geracao) return;
  mostrarDossie(raiz, caixaDossie, caixaIa, d, geracao);
  const s = document.getElementById("secao-faltantes");
  if (s) s.scrollIntoView({ block: "start" });
  anunciar("Busca dos documentos faltantes concluída: " + d.faltantes.encontrados + " de " + d.faltantes.procurados + " com documento achado");
}

function vistaDossie(d, atualizar, repetirFalhas, procurar) {
  const c = d.contratos || {}, cad = d.cadastro || {}, s = d.sancoes || {}, t = d.tcu || {}, p = d.pncp || {}, pr = d.precos || {}, q = d.diarios || {};
  const partes = [];
  partes.push(h("p", { class: "nota meta-dossie" }, (d._reaproveitado ? "Dossiê gravado, reaproveitado (sem nova coleta). " : "Dossiê montado agora. ") + "Gerado em " + dataHoraBR(d.meta.gerado_em) + ". ",
    h("button", { type: "button", class: "link", onclick: () => { if (confirm("Ir de novo a todas as fontes? O dossiê gravado será substituído (não usa IA).")) atualizar(); } }, "Atualizar dossiê")),
    fontesFalhas(d).length ? h("p", { class: "callout sinal" }, ESTADOS.sinal.simbolo + " Fontes que não responderam desta vez: " + fontesFalhas(d).join("; ") + ". ",
      h("button", { type: "button", class: "link", onclick: repetirFalhas }, "Tentar de novo as que falharam por conexão"), " (as que responderam ficam como estão).") : null);
  // Sinais estruturados
  const sinais = (c.resumo && c.resumo.sinais) || {};
  partes.push(h("section", { class: "dossie-secao" }, h("h4", {}, "Contratos no TCE-ES"),
    c.status === "ok" ? [
      resumoLado([["Contratos", nf(c.resumo.contratos), "em " + c.resumo.municipios + " município(s), todos os setores"], ["Valor atual somado", brlCompacto(c.resumo.valor_atual), null],
        ["Com link do contrato", nf(c.resumo.com_link_contrato), "de " + nf(c.resumo.contratos)]]),
      Object.keys(sinais).length ? h("ul", { class: "sinais-lista" }, Object.entries(sinais).map(([k, v]) => h("li", {}, chipEstado("sinal", v.rotulo), " " + v.contratos + " contrato(s)"))) : h("p", { class: "muted small" }, "Nenhum sinal estruturado (adesão a ata, emergência, dispensa, inexigibilidade)."),
      tabela([
        { rotulo: "Município", valor: x => x.municipio }, { rotulo: "Contrato", valor: x => x.numero }, { rotulo: "Objeto", valor: x => x.objeto, classe: "motivo" },
        { rotulo: "Modalidade / base legal", valor: x => [x.modalidade, x.base_legal, x.arp ? "ARP " + x.arp : ""].filter(Boolean).join(" · ") || "—", classe: "small" },
        { rotulo: "Sinal", valor: x => x.sinal ? ROTULO_SINAL_JS[x.sinal] : "", render: x => x.sinal ? chipEstado("sinal", ROTULO_SINAL_JS[x.sinal]) : h("span", { class: "muted" }, "—") },
        { rotulo: "Assinatura", valor: x => x.assinatura, fmt: dataBR }, { rotulo: "Valor atual", valor: x => x.valor_atual, num: true, fmt: brl },
        { rotulo: "Documentos", valor: x => "", csv: false, render: x => linksDoc(x) },
      ], c.contratos, "Contratos da empresa no TCE-ES", { inicio: 10, csv: "contratos_" + d.meta.raiz + ".csv", xlsx: "contratos_" + d.meta.raiz + ".xlsx", classeLinha: x => x.sinal ? "l-sinal" : null }),
      h("p", { class: "nota" }, "\"portal\" = o município informou ao TCE-ES o endereço da página inicial, não o do documento.")]
      : h("p", { class: "muted" }, c.motivo || "Indisponível.")));
  if (c.status === "ok") partes.push(secaoFaltantes(d, procurar));
  // Preços
  partes.push(h("section", { class: "dossie-secao" }, h("h4", {}, "Preço unitário × o mesmo item em outros municípios"),
    pr.status === "ok" && pr.comparaveis_total ? [
      h("p", { class: "small" }, nf(pr.comparaveis_total) + " itens da empresa têm referência em 3 ou mais municípios; " + nf(pr.acima_2x) + " custam o dobro ou mais da mediana. "
        + "Diferença grande pode ser erro de cadastro, especificação diferente ou preço a verificar."),
      tabela([{ rotulo: "Item", valor: x => x.descricao, classe: "motivo" }, { rotulo: "Unid.", valor: x => x.unidade }, { rotulo: "Município", valor: x => x.municipio },
        { rotulo: "Preço", valor: x => x.preco, num: true, fmt: v => brl(v) }, { rotulo: "Mediana dos outros", valor: x => x.mediana_outros, num: true, fmt: v => brl(v) },
        { rotulo: "Razão", valor: x => x.razao, num: true, fmt: v => nf(v, 2) + "×" }, { rotulo: "Municípios de referência", valor: x => x.municipios_outros, num: true },
        { rotulo: "Diferença × quantidade", valor: x => x.diferenca_total, num: true, fmt: brl }],
        pr.comparaveis, "Preços comparados", { inicio: 8, csv: "precos_" + d.meta.raiz + ".csv", classeLinha: x => (x.razao || 0) >= 2 ? "l-sinal" : null }),
      h("p", { class: "nota" }, "Regra: " + pr.regra + ".")] : h("p", { class: "muted small" }, pr.status === "ok" ? "Sem itens comparáveis (os itens do TCE-ES começam em 2022)." : (pr.motivo || "Indisponível."))));
  // Cadastro, sanções, TCU
  partes.push(h("section", { class: "dossie-secao grade-dossie" },
    h("div", {}, h("h4", {}, "Cadastro na Receita Federal"), cad.status === "ok" ? [linhaDl([["Razão social", cad.razao_social], ["Abertura", dataBR(cad.data_inicio_atividade)],
        ["Situação", cad.situacao], ["Atividade principal (CNAE)", cad.cnae], ["Capital social", nulo(cad.capital_social) ? "—" : brl(+cad.capital_social)],
        ["Porte / natureza", (cad.porte || "—") + " · " + (cad.natureza_juridica || "—")], ["Sede", (cad.municipio || "—") + "/" + (cad.uf || "")]]),
        cad.socios && cad.socios.length ? h("details", { class: "tab" }, h("summary", {}, "Sócios e administradores (" + cad.socios.length + ")"), h("ul", { class: "lista" }, cad.socios.map(x => h("li", {}, x.nome + " — " + x.qualificacao + (x.desde ? ", desde " + dataBR(x.desde) : ""))))) : null,
        h("p", { class: "nota" }, "Fonte: " + cad.fonte + ". Sem histórico de nome: o CNPJ pode ter tido outra razão social.")] : h("p", { class: "muted" }, cad.motivo || "Indisponível.")),
    h("div", {}, h("h4", {}, "Sanções e certidões"),
      h("ul", { class: "lista" },
        ["ceis", "cnep"].map(k => h("li", {}, h("strong", {}, k.toUpperCase() + ": "), !s[k] || s[k].status !== "ok" ? "indisponível" : s[k].registros.length ? chipEstado("sinal", s[k].registros.length + " registro(s)") : "nada consta",
          s[k] && s[k].status === "ok" ? h("span", { class: "muted small" }, " (arquivo " + s[k].arquivo_do_dia + ")") : null)),
        t.status === "bloqueado" ? h("li", {}, h("strong", {}, "TCU: "), "consulta recusada pelo firewall do Tribunal — emita a certidão à mão em ", h("a", { href: t.consulta_manual, target: "_blank", rel: "noopener" }, "certidoes-apf.apps.tcu.gov.br")) : null,
        (t.certidoes || []).map(x => h("li", {}, h("strong", {}, "TCU — " + x.tipo + ": "), x.situacao === "NADA_CONSTA" ? "nada consta" : (x.situacao || "—").toLowerCase().replace(/_/g, " ")))),
      ["ceis", "cnep"].some(k => s[k] && s[k].registros && s[k].registros.length) ? h("pre", { class: "small" }, JSON.stringify([...(s.ceis.registros || []), ...(s.cnep.registros || [])], null, 1)) : null)));
  // PNCP e diários
  partes.push(h("section", { class: "dossie-secao" }, h("h4", {}, "Contratos publicados no PNCP"),
    p.status === "ok" ? (p.contratos.length ? tabela([{ rotulo: "Contrato", valor: x => x.titulo, render: x => x.pagina ? h("a", { href: x.pagina, target: "_blank", rel: "noopener" }, x.titulo) : x.titulo },
      { rotulo: "Órgão", valor: x => x.orgao }, { rotulo: "Objeto", valor: x => x.objeto, classe: "motivo" }, { rotulo: "Ano", valor: x => x.ano },
      { rotulo: "Valor", valor: x => x.valor, num: true, fmt: brl }, { rotulo: "Arquivos", valor: x => x.arquivos.length, num: true }], p.contratos, "Contratos no PNCP", { inicio: 6, csv: "pncp_" + d.meta.raiz + ".csv" })
      : h("p", { class: "muted small" }, "Nenhum contrato com esta empresa como fornecedora no PNCP (os municípios publicam lá desde 2024)."))
      : h("p", { class: "muted small" }, "PNCP indisponível: " + (p.motivo || "") + ". Use \"Atualizar dossiê\" para tentar de novo.")));
  partes.push(h("section", { class: "dossie-secao" }, h("h4", {}, "Menções em diários oficiais (Querido Diário)"),
    q.status === "ok" ? (q.mencoes.length ? h("ul", { class: "lista" }, q.mencoes.slice(0, 10).map(x => h("li", {}, h("a", { href: x.url, target: "_blank", rel: "noopener" }, x.municipio + ", " + dataBR(x.data)), x.trechos[0] ? h("span", { class: "small muted" }, " — …" + x.trechos[0] + "…") : null)))
      : h("p", { class: "muted small" }, "Nenhuma menção ao CNPJ.")) : h("p", { class: "muted small" }, "Indisponível."),
    h("p", { class: "nota" }, "Cobertura: só " + (q.cobertura || []).join(", ") + ". Ausência de menção não é prova de nada.")));
  // Obras
  if ((d.obras || []).length) partes.push(h("section", { class: "dossie-secao" }, h("h4", {}, "Obras da Educação"),
    tabela([{ rotulo: "Município", valor: x => x.municipio }, { rotulo: "Objeto", valor: x => x.objeto, classe: "motivo" }, { rotulo: "Situação", valor: x => x.situacao },
      { rotulo: "Valor", valor: x => x.valor, num: true, fmt: brl }, { rotulo: "% medido", valor: x => x.pct_medido, num: true, fmt: v => pct0(v) }, { rotulo: "Aditivos", valor: x => x.aditivos, num: true }],
      d.obras, "Obras", { inicio: 6, classeLinha: x => /paralis/i.test(x.situacao) ? "l-sinal" : null })));
  // Documentos e fontes
  partes.push(h("section", { class: "dossie-secao" }, h("h4", {}, "Documentos encontrados (" + d.documentos.length + ")"),
    h("p", { class: "small" }, "Links específicos de contrato, publicação e edital no TCE-ES e arquivos do PNCP. É o que a Análise com IA tenta ler, nesta ordem."),
    tabela([{ rotulo: "Tipo", valor: x => x.tipo }, { rotulo: "Referência", valor: x => x.referencia, classe: "motivo" }, { rotulo: "Origem", valor: x => x.origem },
      { rotulo: "Link", valor: x => x.url, render: x => h("a", { href: x.url_original, target: "_blank", rel: "noopener" }, "abrir") }], d.documentos, "Documentos", { inicio: 8, csv: "documentos_" + d.meta.raiz + ".csv" }),
    h("details", { class: "tab" }, h("summary", {}, "Fontes consultadas (" + (d.fontes || []).length + ")"),
      tabela([{ rotulo: "Consulta", valor: x => x.nome }, { rotulo: "HTTP", valor: x => x.status }, { rotulo: "Coletada em", valor: x => x.obtido_em, fmt: dataHoraBR },
        { rotulo: "Endereço", valor: x => x.url, classe: "small" }, { rotulo: "Arquivo no cache", valor: x => x.arquivo, render: x => h("code", {}, x.arquivo || "—") },
        { rotulo: "SHA-256", valor: x => x.sha256 || "", render: x => h("code", { class: "small" }, (x.sha256 || "—").slice(0, 16)) }], d.fontes || [], "Fontes", { inicio: 0, busca: false }))));
  return partes;
}
function fontesFalhas(d) {
  const nomes = { cadastro: "cadastro na Receita", tcu: "certidão do TCU", pncp: "PNCP", diarios: "Querido Diário", contratos: "contratos do TCE-ES", precos: "preços" };
  const l = Object.entries(nomes).filter(([k]) => d[k] && ["indisponivel", "erro", "bloqueado"].includes(d[k].status)).map(([k, r]) => r + (d[k].status === "bloqueado" ? " (recusada pelo órgão)" : ""));
  for (const k of ["ceis", "cnep"]) if (d.sancoes && d.sancoes[k] && d.sancoes[k].status !== "ok") l.push(k.toUpperCase());
  return l;
}
const ROTULO_SINAL_JS = { adesao_ata: "adesão a ata (carona)", emergencia: "emergencial", inexigibilidade: "inexigibilidade", dispensa: "dispensa", sem_modalidade: "sem modalidade" };

/* ------------------------------------------------------------ IA */
async function carregarIa(raiz, caixa, dossie, geracao) {
  const { corpo } = await api("/api/ia/" + raiz);
  if (geracao !== EV.geracao) return;
  limpar(caixa);
  if (dossie) EV.dossie = dossie;
  const aviso = avisoFaltantesIa(EV.dossie, corpo.ultima);
  if (corpo.ultima) { anexar(caixa, aviso, ...vistaIa(corpo.ultima, corpo.historico, true, () => estimarIa(raiz, caixa, geracao, true), () => indicarNormas(raiz, caixa, geracao))); return; }
  anexar(caixa, aviso, h("p", {}, "Ainda não há análise com IA desta empresa. Primeiro a página baixa os documentos e calcula o custo — isso não usa a IA."),
    botaoAcao("Análise com IA", () => estimarIa(raiz, caixa, geracao, false)),
    SERVIDOR.ia ? null : h("p", { class: "callout sinal small" }, ESTADOS.sinal.simbolo + " O servidor está sem credencial da Anthropic: dá para estimar, mas não para analisar. Defina ANTHROPIC_API_KEY e reinicie o servidor."));
}

/** O que falta ler: contratos sem documento, busca não feita, ou documentos achados depois da análise gravada. */
function avisoFaltantesIa(d, ultima) {
  if (!d || !d.contratos || d.contratos.status !== "ok") return null;
  const sem = semDocumento(d.contratos), f = d.faltantes;
  const irBusca = h("button", { type: "button", class: "link", onclick: () => { const s = document.getElementById("secao-faltantes"); if (s) { s.scrollIntoView({ block: "start" }); const b = s.querySelector("button.botao-acao"); if (b) b.focus(); } } }, "Documentos faltantes");
  if (ultima && f && f.encontrados && f.gerado_em > ultima.meta.gerado_em)
    return h("p", { class: "callout sinal small" }, ESTADOS.sinal.simbolo + " A busca achou documento de " + f.encontrados + " contrato(s) depois desta análise. A análise gravada não os leu: refaça para incluí-los (nova chamada, novo custo).");
  if (sem.length && !f)
    return h("p", { class: "callout sinal small" }, ESTADOS.sinal.simbolo + " " + sem.length + " contrato(s) sem documento para ler. Antes de analisar, rode a busca em ", irBusca, " — o que for achado entra na leitura.");
  if (sem.length && f && f.encontrados < f.procurados)
    return h("p", { class: "callout info small" }, (f.procurados - f.encontrados) + " contrato(s) procurado(s) continuam sem documento; a análise diz isso nos limites. Veja os pedidos prontos em ", irBusca, ".");
  return null;
}

async function estimarIa(raiz, caixa, geracao, refazer) {
  const etapas = h("div", {});
  anexar(limpar(caixa), h("p", {}, h("strong", {}, "Preparando — "), "baixando os documentos e contando os tokens. Nada é cobrado nesta etapa."), etapas);
  const r = await api("/api/ia/" + raiz + "/estimar", {});
  const t = await acompanhar(r.corpo.tarefa, etapas, geracao);
  if (!t) return;
  if (t.estado === "erro") { anexar(limpar(caixa), h("p", { class: "callout descumpre" }, "A preparação falhou: " + t.erro)); return; }
  const e = t.resultado.estimativa;
  anexar(limpar(caixa), 
    h("div", { class: "estimativa" },
      h("h4", {}, refazer ? "Refazer a análise — custo estimado" : "Custo estimado da análise"),
      resumoLado([["Custo provável", "US$ " + nf(e.custo_usd, 2), e.modelo + " · " + nf(e.tokens_entrada) + " tokens de entrada (" + e.metodo + ") + ~" + nf(e.tokens_saida_previstos) + " de saída"],
        ["Documentos que entram", nf(e.documentos_usados), nf(e.paginas_imagem) + " página(s) escaneada(s) lida(s) como imagem · " + nf(e.caracteres_texto) + " caracteres de texto"],
        ["Documentos que ficam fora", nf(e.documentos_fora), "não baixaram, sem texto ou além do orçamento"]]),
      t.resultado.ja_analisado ? h("p", { class: "callout info small" }, "Este mesmo pedido já foi analisado: confirmar devolve a análise gravada, sem custo.") : null,
      listaDocs("Entram", t.resultado.documentos_usados, x => x.modo + (x.paginas ? ", " + x.paginas + " pág." : "")),
      listaDocs("Ficam fora", t.resultado.documentos_fora, x => x.motivo),
      h("div", { class: "acoes-lado" },
        botaoAcao(refazer ? "Confirmar e refazer (US$ ~" + nf(e.custo_usd, 2) + ")" : "Confirmar e analisar (US$ ~" + nf(e.custo_usd, 2) + ")", () => rodarIa(raiz, caixa, geracao, refazer),
          { desativado: !t.resultado.credencial, titulo: t.resultado.credencial ? null : "Sem credencial da Anthropic no servidor" }),
        botaoAcao("Cancelar", () => carregarIa(raiz, caixa, null, geracao), { secundario: true })),
      t.resultado.credencial ? null : h("p", { class: "small" }, ESTADOS.sinal.simbolo + " Botão desativado: o servidor não tem credencial da Anthropic. Defina ANTHROPIC_API_KEY no terminal e reinicie o servidor (python -m financiamento.servidor_redes).")));
}
function listaDocs(titulo, docs, det) {
  if (!docs.length) return null;
  return h("details", { class: "tab" }, h("summary", {}, titulo + " (" + docs.length + ")"),
    h("ul", { class: "lista small" }, docs.map(x => h("li", {}, h("code", {}, x.id), " " + x.tipo + " — " + x.referencia, h("span", { class: "muted" }, " · " + det(x))))));
}

async function rodarIa(raiz, caixa, geracao, refazer) {
  const etapas = h("div", {});
  anexar(limpar(caixa), h("p", {}, h("strong", {}, "Analisando — "), "o Claude está lendo os documentos. Pode levar alguns minutos; o resultado fica gravado."), etapas);
  const r = await api("/api/ia/" + raiz, { confirmado: true, refazer });
  let res;
  if (r.status === 200) res = r.corpo.resultado;
  else if (r.status === 202) {
    const t = await acompanhar(r.corpo.tarefa, etapas, geracao);
    if (!t) return;
    if (t.estado === "erro") { anexar(limpar(caixa), h("p", { class: "callout descumpre" }, "A análise falhou: " + t.erro), botaoAcao("Tentar de novo", () => estimarIa(raiz, caixa, geracao, refazer))); return; }
    res = t.resultado;
  } else { anexar(limpar(caixa), h("p", { class: "callout descumpre" }, r.corpo.erro || "Erro " + r.status)); return; }
  const { corpo } = await api("/api/ia/" + raiz);
  if (geracao !== EV.geracao) return;
  anexar(limpar(caixa), ...vistaIa(res, corpo.historico || [], !!res._reaproveitada, () => estimarIa(raiz, caixa, geracao, true), () => indicarNormas(raiz, caixa, geracao)));
}

/* ------------------------------------------------------------ base normativa */
function blocoNormas(c) {
  const ns = c.normas || [];
  const avisos = c.normas_avisos || [];
  if (!ns.length) return c.tipo === "sinal" ? h("p", { class: "small muted base-normativa vazia" }, "Base normativa: não indicada nesta análise.") : null;
  return h("section", { class: "base-normativa" },
    h("h4", {}, "Base normativa", c.normas_complemento ? h("span", { class: "small muted" }, " — indicada depois, sem reler os documentos") : null),
    ns.map(n => h("div", { class: "norma" },
      h("p", { class: "norma-cab" }, h("a", { href: n.url, target: "_blank", rel: "noopener" }, n.rotulo), h("span", { class: "small muted" }, " · " + redacaoNorma(n))),
      n.aplicacao ? h("p", { class: "norma-aplicacao" }, h("strong", {}, "No caso: "), n.aplicacao) : null,
      textoNorma(n.texto),
      n.nota ? h("p", { class: "small muted" }, n.nota) : null,
      (n.avisos || []).length ? h("p", { class: "small" }, chipEstado("sinal", "conferir"), " " + n.avisos.join("; ")) : null)),
    avisos.filter(x => !ns.some(n => (n.avisos || []).includes(x))).length
      ? h("p", { class: "small muted" }, ESTADOS.sinal.simbolo + " " + avisos.filter(x => !ns.some(n => (n.avisos || []).includes(x))).join("; ")) : null);
}
/** "redação em vigor em 27/12/2024 (dada em 22/12/2023)"; "redação atual" quando a fonte não traz o histórico. */
function redacaoNorma(n) {
  if (!n.versionado) return "redação atual — " + n.fonte;
  let s = "redação em vigor em " + (n.data_referencia ? dataBR(n.data_referencia) : "hoje");
  const vs = n.versoes || [];
  if (n.redacao_desde && vs.length && n.redacao_desde !== vs[0]) s += " (dada em " + dataBR(n.redacao_desde) + ")";
  const depois = n.data_referencia ? vs.filter(v => v > n.data_referencia) : [];
  if (depois.length) s += "; alterado depois, em " + depois.map(dataBR).join(", ");
  return s + " — normas.leg.br";
}
function textoNorma(t) {
  if (!t) return null;
  const q = h("blockquote", { class: "texto-norma" }, t.split("\n").map(l => h("p", { class: /^\s{2,}/.test(l) ? "recuo" : null }, l.trim())));
  return t.length > 700 ? h("details", { class: "tab" }, h("summary", {}, "Texto do dispositivo"), q) : q;
}
async function indicarNormas(raiz, caixa, geracao) {
  const aviso = document.getElementById("aviso-normas") || caixa;
  anexar(limpar(aviso), h("p", { class: "small" }, "Calculando o custo — não usa a IA…"));
  const { status, corpo } = await api("/api/ia/" + raiz + "/normas/estimar", {});
  if (geracao !== EV.geracao) return;
  if (status !== 200) { anexar(limpar(aviso), h("p", { class: "small" }, corpo.erro || "Erro " + status)); return; }
  const e = corpo.estimativa;
  anexar(limpar(aviso),
    h("p", { class: "small" }, h("strong", {}, "Base normativa desta análise — custo estimado US$ " + nf(e.custo_usd, 2) + ". "),
      nf(e.constatacoes) + " constatações, " + nf(e.tokens_entrada) + " tokens de entrada (" + e.metodo + "). Não relê os documentos; o resultado fica gravado ao lado da análise, que não muda."),
    h("div", { class: "acoes-lado" },
      botaoAcao("Confirmar (US$ ~" + nf(e.custo_usd, 2) + ")", () => rodarNormas(raiz, caixa, aviso, geracao), { desativado: !corpo.credencial, titulo: corpo.credencial ? null : "Sem credencial da Anthropic no servidor" }),
      botaoAcao("Cancelar", () => carregarIa(raiz, caixa, null, geracao), { secundario: true })),
    corpo.credencial ? null : h("p", { class: "small" }, "Botão desativado: o servidor não tem credencial da Anthropic (ANTHROPIC_API_KEY)."));
}
async function rodarNormas(raiz, caixa, aviso, geracao) {
  const etapas = h("div", {});
  anexar(limpar(aviso), h("p", { class: "small" }, h("strong", {}, "Indicando a base normativa…")), etapas);
  const r = await api("/api/ia/" + raiz + "/normas", { confirmado: true });
  if (r.status === 202) {
    const t = await acompanhar(r.corpo.tarefa, etapas, geracao);
    if (!t) return;
    if (t.estado === "erro") { anexar(limpar(aviso), h("p", { class: "small" }, "Falhou: " + t.erro)); return; }
  } else if (r.status !== 200) { anexar(limpar(aviso), h("p", { class: "small" }, r.corpo.erro || "Erro " + r.status)); return; }
  carregarIa(raiz, caixa, null, geracao);
}

function vistaIa(a, historico, reaproveitada, refazer, indicarNormas) {
  const docs = new Map((a.documentos_usados || []).map(x => [x.id, x]));
  const conf = { "conferida": "cumpre", "com ressalvas": "sinal", "não conferível": "semdado" };
  return [
    h("p", { class: "nota meta-dossie" }, (reaproveitada ? "Análise gravada, reaproveitada — nenhum token novo. " : "Análise feita agora e gravada. ")
      + "Gerada em " + dataHoraBR(a.meta.gerado_em) + " por " + a.meta.modelo + (a.meta.fallback ? " (com fallback)" : "") + " · custo US$ " + nf(a.meta.custo_usd || 0, 2)
      + (a.meta.tokens && a.meta.tokens.entrada ? " (" + nf(a.meta.tokens.entrada) + " tokens de entrada, " + nf(a.meta.tokens.saida) + " de saída)" : "") + ". ",
      h("button", { type: "button", class: "link", onclick: refazer }, "Refazer análise (nova chamada, novo custo)")),
    h("div", { class: "callout info" }, h("strong", {}, "Texto redigido por IA. "), "Cada evidência foi procurada no documento citado; a etiqueta de cada constatação diz o resultado. "
      + "O texto de lei não é da IA: vem da fonte oficial, na redação em vigor na data do fato. Confira os documentos antes de usar."),
    a._sem_normas && indicarNormas ? h("div", { class: "callout sinal small", id: "aviso-normas" }, ESTADOS.sinal.simbolo + " Esta análise é anterior à base normativa: "
      + a._sem_normas + " constatação(ões) sem o dispositivo legal. ",
      botaoAcao("Indicar a base normativa", indicarNormas, { secundario: true, titulo: "Lê só as constatações já escritas, os contratos e o catálogo de normas — não relê os documentos" }),
      " (lê só as constatações e os contratos; mostra o custo antes) — ou refaça a análise, que também lê os documentos achados depois.") : null,
    h("p", { class: "resumo-ia" }, a.resumo),
    h("div", { class: "lista-constatacoes" }, (a.constatacoes || []).map(c => h("article", { class: "card insight insight-" + c.tipo },
      h("div", { class: "insight-topo" }, chipTipoInsight(c.tipo), chipEstado(conf[c.conferencia] || "semdado", c.conferencia)),
      h("h3", {}, c.titulo), h("p", {}, c.texto),
      c.proxima_verificacao ? h("p", { class: "proxima" }, h("strong", {}, "Próxima verificação: "), c.proxima_verificacao) : null,
      blocoNormas(c),
      h("details", { class: "tab" }, h("summary", {}, "Evidências (" + c.evidencias.length + ")"),
        h("ul", { class: "lista-fatos" }, c.evidencias.map(ev => {
          const d = docs.get(ev.documento);
          return h("li", {}, h("span", { class: "txt" }, h("q", {}, ev.trecho), h("span", { class: "small muted" }, " — " + (ev.documento === "resumo" ? "resumo do dossiê" : d ? d.tipo + ", " + d.referencia : ev.documento)
            + (ev.pagina ? ", p. " + ev.pagina : "") + " · " + ev.conferencia)),
            d ? h("span", { class: "acoes-fato" }, h("a", { href: d.url_original, target: "_blank", rel: "noopener" }, "abrir documento")) : null);
        }))),
      c.problemas && c.problemas.length ? h("p", { class: "small muted" }, ESTADOS.sinal.simbolo + " " + c.problemas.join("; ")) : null))),
    (a.limites || []).length ? h("div", { class: "dossie-secao" }, h("h4", {}, "Limites apontados pela análise"), h("ul", { class: "lista" }, a.limites.map(x => h("li", {}, x)))) : null,
    h("details", { class: "tab" }, h("summary", {}, "Documentos lidos (" + (a.documentos_usados || []).length + ") e que ficaram fora (" + (a.documentos_fora || []).length + ")"),
      h("ul", { class: "lista small" }, (a.documentos_usados || []).map(x => h("li", {}, h("code", {}, x.id), " " + x.tipo + " — " + x.referencia + " · " + x.modo + " · ", h("a", { href: x.url_original, target: "_blank", rel: "noopener" }, "abrir"))),
        (a.documentos_fora || []).map(x => h("li", { class: "muted" }, h("code", {}, x.id), " " + x.tipo + " — " + x.referencia + " · fora: " + x.motivo)))),
    (a.recusadas || []).length ? h("details", { class: "tab" }, h("summary", {}, "Constatações recusadas pela conferência (" + a.recusadas.length + ")"),
      h("ul", { class: "lista" }, a.recusadas.map(x => h("li", {}, h("strong", {}, x.titulo), " — " + (x.problemas || []).join("; "))))) : null,
    historico.length > 1 ? h("details", { class: "tab" }, h("summary", {}, "Histórico de análises desta empresa (" + historico.length + ")"),
      h("ul", { class: "lista small" }, historico.map(x => h("li", {}, dataHoraBR(x.gerado_em) + " · " + x.modelo + " · " + x.constatacoes + " constatações · US$ " + nf(x.custo_usd || 0, 2) + " · " + x.arquivo)))) : null,
  ];
}
