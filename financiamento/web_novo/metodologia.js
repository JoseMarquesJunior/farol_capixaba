"use strict";
/* ============================================================================
   Como ler e metodologia — a documentação dentro do painel. Reúne o que antes
   era um rodapé de 21 parágrafos repetido em todas as visões: como ler os
   estados, o glossário, as fontes e a coleta, as conferências de qualidade e as
   limitações, cada uma com âncora própria. Os cards apontam para a limitação que
   lhes cabe ("Ver limitação").
   ========================================================================== */

/** Âncora da limitação cujo texto começa por `chave` (sem acento, sem caixa). */
function idLimitacao(chave) {
  const k = semAcento(chave);
  const i = (META.limitacoes || []).findIndex(l => semAcento(l).startsWith(k));
  return i < 0 ? "limitacoes" : "lim-" + (i + 1);
}

function cardComoLer() {
  const card = h("article", { class: "card largo", id: "como-ler", tabindex: "-1" }, cabecalho("Como ler este painel", {
    simples: "O painel reúne o que os municípios do Espírito Santo declaram sobre o dinheiro da educação a várias fontes oficiais, e mostra cada número com a fonte de onde saiu." }));
  card.append(h("h4", {}, "Os quatro estados"), h("p", {}, "Toda situação avaliada aparece com cor, símbolo e palavra — nunca só com a cor:"),
    h("ul", { class: "lista" }, Object.keys(ESTADOS).map(k => h("li", {}, chipEstado(k), " ", ESTADOS[k].significado + "."))),
    h("p", { class: "nota" }, "O vermelho fica reservado a regra legal descumprida. Divergência entre duas fontes, atraso e obra parada são sinais que merecem verificação, não conclusões."),
    h("h4", {}, "Quando o dado falta"),
    h("ul", { class: "lista" },
      h("li", {}, semDado("sem dado"), " — a fonte não publicou o valor. Nunca quer dizer zero."),
      h("li", {}, semDado("não coletado"), " — este painel não baixou o dado nesta versão."),
      h("li", {}, semDado("sem registro"), " — campo que depende de alguém registrar à mão, e ninguém registrou ainda."),
      h("li", {}, h("span", { class: "muted" }, "nenhum"), " — há o dado, e ele diz que não houve (por exemplo, nenhum repasse ligado a uma escola).")),
    h("h4", {}, "Três níveis de detalhe da despesa"),
    h("ul", { class: "lista" },
      h("li", {}, h("strong", {}, "Nível 1 — em que etapa: "), "função 12 (Educação) e subfunções, como ensino fundamental e educação infantil."),
      h("li", {}, h("strong", {}, "Nível 2 — com o quê: "), "pessoal, custeio e investimento."),
      h("li", {}, h("strong", {}, "Nível 3 — para quem: "), "credor, ação do orçamento, fonte, item comprado, obra e escola.")),
    h("h4", {}, "Indício não é achado"),
    h("p", {}, "Nada neste painel é conclusão de auditoria. São fatos apurados nas fontes oficiais; quem transforma um sinal em achado é o auditor, com o documento na mão."),
    h("h4", {}, "Valores em reais de cada ano"),
    h("p", {}, "Os valores são nominais: não descontam a inflação. Parte de uma alta de um ano para o outro pode ser só inflação."),
    h("h4", {}, "O botão “ⓘ ver fonte”"),
    h("p", {}, "Cada número tem um botão que mostra onde ele está no documento de origem, como foi calculado e a consulta exata que o obteve, com data e hora da coleta. Dá para copiar a referência e colar no papel de trabalho."));
  return card;
}
function cardGlossario() {
  return h("article", { class: "card largo", id: "glossario", tabindex: "-1" }, cabecalho("Glossário", {
    simples: "As siglas e os termos técnicos usados no painel, em linguagem simples. Nos cards, a primeira ocorrência de cada sigla é clicável e abre a definição ali mesmo." }),
    listaGlossario());
}
function cardFontes() {
  const por = META.extraido_em_por_fonte || {}, st = META.fontes_status || {};
  const situacao = f => { const x = st[f] || {}; return x.ok === false ? "falhou nesta atualização — " + x.erro : x.modo === "offline" ? "lida do cache (sem nova coleta nesta atualização)" : "coletada nesta atualização"; };
  const card = h("article", { class: "card largo", id: "fontes", tabindex: "-1" }, cabecalho("Fontes e coleta", {
    simples: "De onde vêm os dados, quando foram coletados e para que cada fonte é usada. A página não consulta nada na internet: todos os dados vêm embutidos nela." }));
  card.append(tabela([
    { rotulo: "Fonte", valor: f => f },
    { rotulo: "Primeira coleta", num: true, valor: f => (por[f] || {}).primeira, fmt: dataHoraBR },
    { rotulo: "Última coleta", num: true, valor: f => (por[f] || {}).ultima, fmt: dataHoraBR },
    { rotulo: "Consultas", num: true, valor: f => (por[f] || {}).consultas || 0, fmt: nf },
    { rotulo: "Situação", valor: situacao },
  ], ["SICONFI", "SIOPE", "FNDE", "TCE-ES", "Censo", "INEP"], "Extração de cada fonte", { inicio: 0, busca: false, fixarPrimeira: false }),
    h("p", { class: "nota" }, "Horário local do navegador. Dataset processado em " + dataHoraBR(META.gerado_em) + (META.versao ? " (versão " + META.versao + ")" : "") +
      ". Exercícios: " + ANOS.join(", ") + ". O conjunto de dados consolidado, com a proveniência em cada linha, acompanha o painel (arquivo consolidado.csv)."),
    h("h4", {}, "Para que cada fonte é usada"),
    h("ul", { class: "lista" }, (META.fontes || []).map(f => h("li", {}, h("a", { href: f.url, target: "_blank", rel: "noopener noreferrer" }, f.rotulo + " ↗"), " — ", comTermos(f.usado_para)))),
    h("h4", {}, "Documentação das fontes"),
    h("ul", { class: "lista" }, (META.documentacao || []).map(d => h("li", {}, d.fonte + ": ", String(d.url).startsWith("ftp:")
      ? h("span", {}, d.rotulo + " (", h("code", {}, d.url), ")") : h("a", { href: d.url, target: "_blank", rel: "noopener noreferrer" }, d.rotulo + " ↗")))));
  return card;
}
function cardQualidade() {
  const card = h("article", { class: "card largo", id: "qualidade", tabindex: "-1" }, cabecalho("Conferências de qualidade dos dados", {
    simples: "O painel confere uma fonte contra a outra e o próprio processamento. O que não bate é listado aqui — é informação para a auditoria, não defeito escondido.",
    nota: "Tolerância de R$ 1,00 nas conferências ao centavo." }));
  const cc = META.conferencias_cruzadas || {};
  card.append(h("h4", {}, "Uma fonte contra a outra (todos os exercícios)"),
    h("ul", { class: "lista" }, Object.values(cc).map(c => h("li", {}, h("strong", {}, c.descricao + ": "),
      c.comparaveis ? c.batem + " de " + c.comparaveis + " ente-anos batem" : "sem par comparável",
      c.incompletos ? " · " + c.incompletos + " ente-ano(s) fora da conferência: o arquivo do TCE-ES não traz todos os meses" : "",
      c.maiores && c.maiores.length ? h("details", {}, h("summary", {}, "maiores diferenças"),
        h("ul", { class: "lista" }, c.maiores.map(m => h("li", {}, m.ente + " (" + m.ano + "): " + (c.unidade ? nf(m.dif) + " " + c.unidade : brl(m.dif)))))) : null))));
  const v = META.validacao || {}, vf = D.verificacoes || {};
  card.append(h("h4", {}, "Validação do conjunto de dados"), h("ul", { class: "lista" },
    h("li", {}, nf(v.registros || 0) + " registros, cada um com endereço da consulta, parâmetros e instante da coleta; sem proveniência: " + (v.sem_proveniencia ?? "–") + "."),
    h("li", {}, "Código IBGE com 7 dígitos em todos os municípios: " + (v.ibge_7_digitos ? "sim" : "NÃO") + "."),
    h("li", {}, "Valores negativos onde o indicador não admite: " + (v.n_negativos_inesperados || 0) +
      ((v.negativos_inesperados || []).length ? " — " + v.negativos_inesperados.map(n => n.ente + " " + n.ano + ", " + (n.detalhe || n.indicador) + ": " + brl(n.valor)).join("; ") + " (dado da fonte, a revisar)" : "") + "."),
    vf.fechamento_dca ? h("li", {}, "Soma das funções da DCA fecha com o total do anexo: " + (vf.fechamento_dca.conferidos - vf.fechamento_dca.falhas.length) + " de " + vf.fechamento_dca.conferidos + " ente-anos.") : null,
    vf.subfuncoes_fecham ? h("li", {}, "Soma das subfunções fecha com a função 12: " + (vf.subfuncoes_fecham.conferidos - vf.subfuncoes_fecham.falhas.length) + " de " + vf.subfuncoes_fecham.conferidos + ".") : null,
    vf.rreo_vs_dca ? h("li", {}, "RREO do 6º bimestre × DCA: " + (vf.rreo_vs_dca.comparaveis - vf.rreo_vs_dca.divergentes) + " de " + vf.rreo_vs_dca.comparaveis + " dentro de 0,5%" +
      (vf.rreo_vs_dca.divergentes ? "; " + vf.rreo_vs_dca.divergentes + " divergem (retificações entre um e outro)." : ".")) : null));
  const stc = (META.fontes_status || {}).Censo || {};
  const ROT_VINC = { pdde: "Unidades executoras do PDDE", conselho: "Conselhos escolares (credores do município)", obra: "Prédios de obras (bens vinculadores)" };
  if (stc.vinculos) card.append(h("h4", {}, "Ligação recebedor → escola do Censo (pelo nome)"),
    h("ul", { class: "lista" }, Object.entries(stc.vinculos).filter(([, x]) => x.total).map(([f, x]) =>
      h("li", {}, ROT_VINC[f] + ": " + x.casados + " de " + x.total + " identificados (" + nf(100 * x.casados / x.total, 0) + "%); o restante fica sem vínculo, com o nome original."))));
  const avisosTce = (D.avisos || []).filter(a => a.fonte === "TCE-ES"), avisosSiope = (D.avisos || []).filter(a => a.fonte === "SIOPE");
  if (avisosTce.length) card.append(h("details", { class: "tab" }, h("summary", {}, "Avisos do TCE-ES (" + avisosTce.length + ") — arquivo incompleto, recurso que não baixou"),
    h("ul", { class: "lista" }, avisosTce.map(a => h("li", {}, a.aviso)))));
  if (avisosSiope.length) card.append(h("h4", {}, "Conferência interna do PDF do SIOPE que não fechou"),
    h("ul", { class: "lista" }, avisosSiope.map(a => h("li", {}, nomeEnte(a.cod_ibge) + " (" + a.ano + "): " + a.aviso))));
  return card;
}
function cardLimitacoes() {
  return h("article", { class: "card largo", id: "limitacoes", tabindex: "-1" }, cabecalho("Limitações dos dados", {
    simples: "O que os dados não dizem, ou dizem com ressalva. Cada card do painel aponta para a limitação que lhe cabe." }),
    h("ol", { class: "limitacoes" }, (META.limitacoes || []).map((l, i) => h("li", { id: "lim-" + (i + 1), tabindex: "-1" }, comTermos(l)))));
}
function cardSobre() {
  return h("article", { class: "card largo", id: "sobre", tabindex: "-1" }, cabecalho("Sobre este protótipo"),
    h("p", {}, "Painel de apoio à auditoria do financiamento da educação nos 78 municípios do Espírito Santo, construído a partir de dados abertos oficiais. É um protótipo: usa a identidade visual do Painel de Controle do TCE-ES, mas não está integrado a ele."),
    ARQUIVO_CNCA ? h("p", {}, "O papel de trabalho da fiscalização do CNCA fica num arquivo separado: ", linkCnca({}, "evidências da fiscalização do CNCA ↗"), ".") : null);
}

function renderMetodologia(destino) {
  destino.append(h("div", { class: "cab-visao" }, h("h2", {}, "Como ler e metodologia"),
    h("p", {}, "O que cada cor e símbolo quer dizer, o significado das siglas, de onde vêm os dados, como foram conferidos e o que eles não dizem.")));
  const itens = [["como-ler", "Como ler"], ["glossario", "Glossário"], ["fontes", "Fontes e coleta"], ["qualidade", "Qualidade dos dados"], ["limitacoes", "Limitações"], ["sobre", "Sobre"]];
  destino.append(h("nav", { class: "secoes", "aria-label": "Nesta página" }, h("ul", {}, itens.map(([id, t]) => h("li", {}, linkPara({ ir: id }, t))))));
  destino.append(h("section", { class: "bloco" }, h("div", { class: "grade" }, cardComoLer(), cardGlossario(), cardFontes(), cardQualidade(), cardLimitacoes(), cardSobre())));
}
