"use strict";
/* ============================================================================
   Glossário e ressalvas do painel simplificado.

   Esta versão não tem seção de metodologia. O que dela importa para ler os
   números certo continua na página de outro jeito:
   · as siglas sublinhadas abrem a definição ali mesmo (glossario.js), só para
     os termos que esta versão usa;
   · a ressalva de cada card fica dentro do "Como é calculado" do próprio card
     (textoLimitacao), em vez de um link para uma seção à parte.
   ========================================================================== */

/* ------------------------------------------------------------- glossário
   Só os termos que aparecem nesta versão ficam clicáveis; os demais (MDE,
   SIOPE, remessas, obras…) voltam a ser texto comum nesta página. Os
   demonstrativos federais também saem: todos os números desta versão vêm dos
   dados abertos do TCE-ES. Algumas definições do painel novo citam regras ou
   medidas que esta versão não trata: aqui elas ganham uma redação sem elas. */
const TERMOS_SIMPLIFICADO = new Set([
  "fundeb", "funcao12", "estagios", "intra", "fonte-recursos",
  "natureza", "niveis", "credor", "uex", "pdde", "pnae", "pnate", "salario-educacao", "fnde",
  "inep", "censo", "tcees", "por-matricula", "nominal", "ausencias",
]);
const DEFINICAO_SIMPLIFICADA = {
  fundeb: "Fundo de cada estado formado por parte dos impostos do estado e dos municípios e redistribuído entre eles conforme o número de matrículas, com complementação da União. Para o município, é uma das principais receitas da educação.",
  niveis: "Graus de detalhe da despesa neste painel. Nível 1: função e subfunção (em que etapa de ensino). Nível 2: natureza econômica (pessoal, custeio, investimento). Nível 3: quem recebeu, em qual ação do orçamento e o que foi comprado.",
  ausencias: "Ausências diferentes, nenhuma igual a zero. Sem dado: a fonte não publicou o valor. Não coletado: este painel não baixou o dado nesta versão.",
  "por-matricula": "Forma de comparar municípios de tamanhos diferentes: a despesa em Educação dividida pelas matrículas da rede municipal. É a medida mais próxima do serviço prestado.",
  tcees: "Órgão de controle externo que fiscaliza as contas do Estado e dos 78 municípios. Todos os números deste painel vêm dos dados abertos que o Tribunal publica com o que os municípios lhe informam.",
};
for (const [sigla, id] of [...SIGLA_PARA_TERMO]) if (!TERMOS_SIMPLIFICADO.has(id)) SIGLA_PARA_TERMO.delete(sigla);
for (const [id, def] of Object.entries(DEFINICAO_SIMPLIFICADA)) if (TERMO.has(id)) TERMO.get(id).def = def;

/* ------------------------------------------------------------ ressalvas */
const LIMITACOES_SIMPLIFICADO = {
  "Despesa": "É a despesa empenhada na função 12 (Educação) que o município informou ao TCE-ES, sem as operações entre órgãos da própria prefeitura (intra-orçamentárias). Os valores não descontam a inflação.",
  "Fluxo fonte": "Nos dados do TCE-ES, a fonte padronizada nacional aparece a partir de 2023: em 2021 e 2022 os municípios usavam os códigos anteriores, e o gráfico desses anos fica indisponível. Uma fonte do grupo \"outras\" com ao menos 5% da despesa do ano aparece com o próprio nome.",
  "Outras receitas": "Quando \"outras receitas\" pesam ao menos 20% da receita, são abertas pela natureza da receita; a última parcela é calculada por diferença. A natureza não separa royalties das demais transferências correntes: a parte deles que paga a educação aparece nomeada no fluxo do Resumo. Os repasses do FNDE são o que o município registrou como recebido.",
  "Nível 3": "Os dados vêm do TCE-ES e são declarados pelo próprio município; a soma dos empenhos é conferida contra a despesa agregada que o Tribunal publica.",
  "Conselhos": "Nenhuma fonte financeira traz o código da escola: o conselho é ligado à escola do Censo Escolar pelo nome, dentro do município. Quando o nome é ambíguo, a ligação não é feita.",
  "Itens contratados": "Só entram as contratações que a própria fonte liga à Educação (unidade gestora de educação, setor beneficiado \"Educação\" ou obra da Educação), a partir de 2022. A cobertura é parcial: ausência aqui não é ausência de compra.",
  "Por matrícula": "Por matrícula divide a despesa pelas matrículas da rede municipal informadas ao TCE-ES (conferidas com o Censo Escolar).",
};
const textoLimitacao = chave => (chave && LIMITACOES_SIMPLIFICADO[chave]) || null;

/** Cabeçalho de card desta versão: título, frase simples opcional, botão de
 *  fonte, e a nota técnica junto com a ressalva sempre recolhidas em "Como é
 *  calculado" — mesmo sem frase simples, o que o cabeçalho padrão não faz. */
function cabecalhoEnxuto(titulo, o) {
  const cab = cabecalho(titulo, { simples: o.simples, fonte: o.fonte });
  const partes = [o.nota, textoLimitacao(o.limitacao)].filter(Boolean);
  if (partes.length) cab.firstChild.append(h("details", { class: "tecnico" }, h("summary", {}, "Como é calculado"),
    ...partes.map(t => h("p", { class: "nota" }, comTermos(t)))));
  return cab;
}
/** O mesmo, por fora, para os cards compartilhados com o painel novo (nivel3.js). */
function anexarLimitacao(card, chave) {
  const t = textoLimitacao(chave), corpo = card.querySelector(".cab-card > div");
  if (!t || !corpo) return card;
  let det = corpo.querySelector("details.tecnico");
  if (!det) { det = h("details", { class: "tecnico" }, h("summary", {}, "Como é calculado")); corpo.append(det); }
  det.append(h("p", { class: "nota" }, comTermos(t)));
  return card;
}
