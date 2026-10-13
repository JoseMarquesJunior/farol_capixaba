"use strict";
/* ============================================================================
   Glossário — a camada para quem não é do ramo (decisão D3: o cidadão também é
   público). Cada termo tem definição curta, em linguagem simples. Nos cards, a
   primeira ocorrência de cada sigla vira um botão que abre a definição ali
   mesmo (`comTermos`), sem tirar o leitor do lugar; a lista completa fica na
   seção "Como ler e metodologia".

   `siglas` são as grafias reconhecidas no texto (com maiúsculas e acentos
   exatos). Termo sem `siglas` só aparece na lista completa.
   ========================================================================== */

const GLOSSARIO = [
  { id: "mde", termo: "MDE", extenso: "Manutenção e Desenvolvimento do Ensino", siglas: ["MDE"],
    def: "Despesas que a lei reconhece como aplicação em educação (Lei 9.394/1996, arts. 70 e 71): salários dos profissionais, construção e manutenção de escolas, material didático, transporte escolar. A Constituição (art. 212) obriga cada município a aplicar em MDE pelo menos 25% da receita de impostos, incluídas as transferências de impostos que recebe." },
  { id: "receita-impostos", termo: "Receita de impostos", siglas: ["receita de impostos"],
    def: "A base de cálculo dos 25% do MDE: os impostos do próprio município (IPTU, ISS, ITBI…) mais as transferências de impostos que ele recebe (cota do FPM, do ICMS, do IPVA e outras)." },
  { id: "fundeb", termo: "FUNDEB", extenso: "Fundo de Manutenção e Desenvolvimento da Educação Básica e de Valorização dos Profissionais da Educação", siglas: ["FUNDEB"],
    def: "Fundo de cada estado formado por parte dos impostos do estado e dos municípios e redistribuído entre eles conforme o número de matrículas, com complementação da União. Pelo menos 70% do que o município recebe do FUNDEB deve pagar os profissionais da educação básica em efetivo exercício (art. 212-A, XI, da Constituição; Lei 14.113/2020)." },
  { id: "complementacao", termo: "VAAF, VAAT e VAAR", extenso: "complementação da União ao FUNDEB", siglas: ["VAAF", "VAAT", "VAAR", "complementação da União"],
    def: "As três formas do dinheiro federal que complementa o FUNDEB: VAAF, pelo valor anual por aluno do fundo estadual; VAAT, pelo valor anual total por aluno da rede; VAAR, por resultados, para redes que cumprem condições de gestão e melhoram indicadores." },
  { id: "siope", termo: "SIOPE", extenso: "Sistema de Informações sobre Orçamentos Públicos em Educação", siglas: ["SIOPE"],
    def: "Sistema do FNDE em que cada município declara receitas e despesas com educação. O próprio sistema calcula o percentual aplicado em MDE e o do FUNDEB na remuneração, e gera o Anexo 8 do RREO." },
  { id: "anexo8", termo: "Anexo 8 do RREO", siglas: ["Anexo 8", "Anexo 08"],
    def: "O demonstrativo das receitas e despesas com manutenção e desenvolvimento do ensino. É onde estão os percentuais legais de MDE e do FUNDEB. O painel o lê no PDF que o SIOPE gera, porque o SICONFI não o publica de forma automatizável." },
  { id: "siconfi", termo: "SICONFI", extenso: "Sistema de Informações Contábeis e Fiscais do Setor Público Brasileiro", siglas: ["SICONFI"],
    def: "Sistema do Tesouro Nacional onde estados e municípios entregam os relatórios fiscais (RREO e RGF), a declaração anual (DCA) e a matriz de saldos contábeis (MSC)." },
  { id: "rreo", termo: "RREO", extenso: "Relatório Resumido da Execução Orçamentária", siglas: ["RREO"],
    def: "Relatório publicado a cada dois meses (bimestre), com as receitas e despesas acumuladas no ano (Lei de Responsabilidade Fiscal, art. 52)." },
  { id: "rgf", termo: "RGF", extenso: "Relatório de Gestão Fiscal", siglas: ["RGF"],
    def: "Relatório quadrimestral — ou semestral, nos municípios que fizeram essa opção — sobre despesa com pessoal, dívida e os demais limites da Lei de Responsabilidade Fiscal (art. 55)." },
  { id: "dca", termo: "DCA", extenso: "Declaração de Contas Anuais", siglas: ["DCA"],
    def: "O balanço do exercício que o município envia ao Tesouro até 30 de abril do ano seguinte (LRF, art. 51). O Anexo I-E traz a despesa por função e subfunção; o Anexo I-C, as receitas." },
  { id: "msc", termo: "MSC", extenso: "Matriz de Saldos Contábeis", siglas: ["MSC"],
    def: "Arquivo mensal com os saldos da contabilidade do município, enviado ao SICONFI. É ele que liga cada despesa à fonte de recursos que a paga." },
  { id: "lrf", termo: "LRF", extenso: "Lei de Responsabilidade Fiscal", siglas: ["LRF"],
    def: "Lei Complementar 101/2000: regras de planejamento, limites e transparência das contas públicas, incluindo os prazos de entrega do RREO, do RGF e da DCA." },
  { id: "funcao12", termo: "Função 12 e subfunção", siglas: ["função 12", "Função 12"],
    def: "Na classificação da despesa por área de governo, a função 12 reúne todo o gasto em Educação. Subfunção é o detalhe dentro dela: 12.361 Ensino Fundamental, 12.365 Educação Infantil, 12.122 Administração Geral, entre outras." },
  { id: "estagios", termo: "Empenhado, liquidado e pago", siglas: ["empenhada", "empenhado", "empenhos"],
    def: "As três etapas da despesa pública (Lei 4.320/1964): o empenho reserva o dinheiro para um fornecedor; a liquidação confirma que o bem ou serviço foi entregue; o pagamento é a saída do dinheiro. Salvo indicação, o painel usa a despesa empenhada." },
  { id: "dotacao", termo: "Dotação", siglas: ["dotação atualizada", "Dotação atualizada", "dotação"],
    def: "O valor autorizado no orçamento para uma ação. A dotação inicial é a da lei orçamentária; a atualizada inclui os créditos adicionais aprovados durante o ano." },
  { id: "intra", termo: "Intra-orçamentária", siglas: ["intra-orçamentárias", "intra-orçamentária", "intra-orçamentários"],
    def: "Despesa entre órgãos do mesmo ente — por exemplo, a contribuição da prefeitura ao seu próprio instituto de previdência. É excluída para que o mesmo dinheiro não seja contado duas vezes." },
  { id: "fonte-recursos", termo: "Fonte de recursos", siglas: ["fonte de recursos", "fontes de recursos"],
    def: "Código que indica de onde vem o dinheiro que paga cada despesa. No padrão nacional: 500 — impostos sem vinculação; 540 a 543 — FUNDEB; 550 — salário-educação; 551 a 553 — PDDE, PNAE e PNATE; 569 — outras transferências do FNDE." },
  { id: "natureza", termo: "Natureza econômica", siglas: ["natureza econômica"],
    def: "Classificação da despesa pelo que se comprou: pessoal e encargos, custeio (outras despesas correntes) e investimentos (obras e equipamentos)." },
  { id: "niveis", termo: "Níveis 1, 2 e 3", siglas: ["Nível 1", "Nível 2", "Nível 3"],
    def: "Graus de detalhe da despesa neste painel. Nível 1: função e subfunção (em que etapa de ensino). Nível 2: natureza econômica (pessoal, custeio, investimento). Nível 3: quem recebeu, em qual ação, com que fonte, em qual obra ou escola." },
  { id: "credor", termo: "Credor", siglas: ["credores", "credor"],
    def: "Quem recebe o pagamento: empresa, pessoa ou entidade." },
  { id: "restos", termo: "Restos a pagar", siglas: ["restos a pagar", "Restos a pagar"],
    def: "Despesa empenhada num ano e não paga até 31 de dezembro, que passa para o ano seguinte. É processada quando já foi liquidada e não processada quando ainda não foi." },
  { id: "pdde", termo: "PDDE", extenso: "Programa Dinheiro Direto na Escola", siglas: ["PDDE"],
    def: "Programa do FNDE que repassa dinheiro diretamente às escolas públicas, por meio das unidades executoras, para manutenção e projetos pedagógicos. Não passa pelo orçamento do município." },
  { id: "uex", termo: "Unidade executora", extenso: "UEx", siglas: ["UEx", "unidade executora", "unidades executoras"],
    def: "Entidade sem fins lucrativos que representa a escola — conselho escolar, caixa escolar ou associação de pais e mestres — e recebe o PDDE em nome dela." },
  { id: "pnae", termo: "PNAE", extenso: "Programa Nacional de Alimentação Escolar", siglas: ["PNAE"],
    def: "Repasse do FNDE para a merenda escolar, calculado pelo número de alunos." },
  { id: "pnate", termo: "PNATE", extenso: "Programa Nacional de Apoio ao Transporte do Escolar", siglas: ["PNATE"],
    def: "Repasse do FNDE para o transporte de alunos que moram na zona rural." },
  { id: "salario-educacao", termo: "Salário-educação", siglas: ["Salário-educação", "salário-educação"],
    def: "Contribuição social paga pelas empresas sobre a folha de pagamento. Parte é repassada a estados e municípios de acordo com o número de matrículas." },
  { id: "fnde", termo: "FNDE", extenso: "Fundo Nacional de Desenvolvimento da Educação", siglas: ["FNDE"],
    def: "Autarquia do Ministério da Educação que repassa os recursos federais da educação básica: PDDE, PNAE, PNATE, salário-educação e a complementação do FUNDEB." },
  { id: "cgu", termo: "CGU", extenso: "Controladoria-Geral da União", siglas: ["CGU"],
    def: "Mantém o Portal da Transparência, de onde o painel baixa os pagamentos feitos pelo FNDE a cada município e a cada escola." },
  { id: "inep", termo: "INEP", extenso: "Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira", siglas: ["INEP"],
    def: "Responsável pelo Censo Escolar, pelo Saeb, pelo IDEB e pelo Indicador Criança Alfabetizada." },
  { id: "censo", termo: "Censo Escolar", siglas: ["Censo Escolar"],
    def: "Levantamento anual do INEP com todas as escolas do país: rede, localização, matrículas, docentes e infraestrutura." },
  { id: "cnca", termo: "CNCA", extenso: "Compromisso Nacional Criança Alfabetizada", siglas: ["CNCA"],
    def: "Política federal (Decreto 11.556/2023) para que todas as crianças estejam alfabetizadas ao fim do 2º ano do ensino fundamental, com apoio técnico e financeiro da União a estados e municípios." },
  { id: "ica", termo: "ICA", extenso: "Indicador Criança Alfabetizada", siglas: ["ICA"],
    def: "Indicador do INEP: percentual de alunos da rede que, ao fim do 2º ano, atingem 743 pontos ou mais na escala de Língua Portuguesa do Saeb. É o indicador de meta do CNCA." },
  { id: "saeb", termo: "Saeb", extenso: "Sistema de Avaliação da Educação Básica", siglas: ["Saeb"],
    def: "Conjunto de avaliações do INEP que mede o aprendizado dos alunos em Língua Portuguesa e Matemática." },
  { id: "ideb", termo: "IDEB", extenso: "Índice de Desenvolvimento da Educação Básica", siglas: ["IDEB"],
    def: "Indicador do INEP, de 0 a 10, que combina a aprovação escolar com o desempenho dos alunos no Saeb." },
  { id: "paebes", termo: "PAEBES", extenso: "Programa de Avaliação da Educação Básica do Espírito Santo", siglas: ["PAEBES"],
    def: "Avaliação de aprendizagem aplicada pela Secretaria de Estado da Educação do Espírito Santo." },
  { id: "funpaes", termo: "FUNPAES e PAES", extenso: "Fundo de Apoio à Educação do Estado do Espírito Santo", siglas: ["FUNPAES", "PAES"],
    def: "O PAES é o programa estadual de colaboração com os municípios, dentro do qual o CNCA é implementado no Espírito Santo; o FUNPAES é o fundo estadual que repassa recursos aos municípios nesse programa." },
  { id: "renalfa", termo: "Renalfa", siglas: ["Renalfa"],
    def: "Rede de articuladores do CNCA, com bolsistas que apoiam a gestão, a formação e a mobilização nos municípios. As bolsas são pagas pelo FNDE diretamente às pessoas." },
  { id: "po", termo: "Plano orçamentário (PO)", siglas: ["plano orçamentário", "PO"],
    def: "Subdivisão de uma ação do orçamento federal. No PDDE, o plano 000C identifica o repasse do CNCA às escolas; o 0007, o PDDE-Alfabetização que o antecedeu." },
  { id: "ug", termo: "UG", extenso: "Unidade gestora", siglas: ["UGs", "UG"],
    def: "Órgão ou fundo que executa orçamento próprio: prefeitura, câmara, fundo municipal de educação, autarquia." },
  { id: "tcees", termo: "TCE-ES", extenso: "Tribunal de Contas do Estado do Espírito Santo", siglas: ["TCE-ES"],
    def: "Órgão de controle externo que fiscaliza as contas do Estado e dos 78 municípios. Publica em dados abertos o que os municípios lhe informam." },
  { id: "cidades", termo: "CidadES e remessa mensal", siglas: ["CidadES", "homologação", "homologada", "homologadas"],
    def: "O CidadES é o sistema do TCE-ES pelo qual prefeituras, câmaras e fundos enviam a prestação de contas mensal (a remessa). Remessa homologada é a que foi concluída e registrada no sistema; atraso é a homologação depois da data-limite." },
  { id: "bem-vinculador", termo: "Bem vinculador", siglas: ["bem vinculador"],
    def: "No cadastro de contratações do TCE-ES, o imóvel — em geral o prédio da escola — a que um contrato de obra está ligado, com a coordenada geográfica." },
  { id: "presumida", termo: "Paralisação presumida", siglas: ["Paralisação presumida", "paralisação presumida"],
    def: "Classificação do TCE-ES para obra sem medição recente, mesmo que o município não a tenha declarado paralisada. É indício de obra parada, não confirmação." },
  { id: "ec119", termo: "EC 119/2022", siglas: ["EC 119/2022", "EC 119"],
    def: "Emenda Constitucional que isentou de responsabilização os entes que não aplicaram 25% em MDE em 2020 e 2021, durante a pandemia, desde que compensassem a diferença até o fim de 2023." },
  { id: "por-matricula", termo: "Per capita e por matrícula", siglas: ["per capita", "por matrícula"],
    def: "Duas formas de comparar municípios de tamanhos diferentes: per capita divide a despesa pela população; por matrícula, pelas matrículas da rede municipal. Por matrícula é a medida mais próxima do serviço prestado." },
  { id: "nominal", termo: "Valores nominais", siglas: ["nominais", "nominal", "sem deflator"],
    def: "Valores como registrados em cada ano, sem correção pela inflação. Parte de uma alta de um ano para o outro pode ser só inflação." },
  { id: "pp", termo: "p.p. (pontos percentuais)", siglas: ["p.p."],
    def: "Diferença entre dois percentuais. De 25% para 24,5% são 0,5 p.p. a menos — e não 0,5%." },
  { id: "conciliacao", termo: "Conciliação", siglas: ["Conciliação", "conciliação"],
    def: "Comparação do mesmo valor em duas fontes diferentes. Diferença grande é sinal a verificar, não prova de erro." },
  { id: "sha256", termo: "SHA-256", siglas: ["SHA-256"],
    def: "Uma “impressão digital” do arquivo baixado da fonte: se um único byte mudar, o código muda. Permite provar que o arquivo guardado é o mesmo que foi coletado." },
  { id: "indicio", termo: "Indício e achado", siglas: [],
    def: "Indício é um sinal que o dado público mostra e que merece verificação. Achado de auditoria é a conclusão do auditor, com o documento na mão. Nada neste painel é achado." },
  { id: "ausencias", termo: "Sem dado, não coletado, sem registro", siglas: [],
    def: "Três ausências diferentes, nenhuma igual a zero. Sem dado: a fonte não publicou o valor. Não coletado: este painel não baixou o dado nesta versão. Sem registro: campo preenchido à mão que ninguém preencheu ainda." },
];

const TERMO = new Map(GLOSSARIO.map(t => [t.id, t]));
const SIGLA_PARA_TERMO = new Map(GLOSSARIO.flatMap(t => t.siglas.map(s => [s, t.id])));
const REGEX_TERMOS = new RegExp("(?<![\\p{L}\\p{N}-])(" +
  [...SIGLA_PARA_TERMO.keys()].sort((a, b) => b.length - a.length).map(s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") +
  ")(?![\\p{L}\\p{N}])", "gu");

/** Abre a definição num diálogo pequeno, sem tirar o leitor do lugar. */
function abrirTermo(id) {
  const t = TERMO.get(id), dlg = $("#dialogo-termo");
  if (!t || !dlg) return;
  limpar(dlg);
  const link = typeof hrefGlossario === "function" ? hrefGlossario(id) : null;
  // Element.append escreveria "null" como texto: os opcionais são filtrados antes.
  dlg.append(...[
    h("header", {}, h("h2", { id: "termo-titulo" }, t.termo),
      h("button", { type: "button", class: "leve fechar", "aria-label": "Fechar", onclick: () => dlg.close() }, "×")),
    t.extenso ? h("p", { class: "muted" }, t.extenso) : null,
    h("p", {}, t.def),
    link ? h("p", {}, h("a", { href: link, onclick: () => dlg.close() }, "Ver o glossário completo")) : null].filter(Boolean));
  if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
}
/** Termo clicável no meio do texto. */
function termo(id, texto) {
  const t = TERMO.get(id);
  if (!t) return texto;
  return h("button", { type: "button", class: "termo", title: t.def, "aria-haspopup": "dialog",
    onclick: e => { e.stopPropagation(); abrirTermo(id); } }, texto || t.termo);
}
/**
 * Texto com a primeira ocorrência de cada sigla conhecida transformada em termo
 * clicável. `vistos` (um Set) evita repetir o mesmo termo no mesmo card.
 */
function comTermos(texto, vistos) {
  if (texto === null || texto === undefined) return [];
  const s = String(texto), partes = [];
  let ultimo = 0;
  for (const m of s.matchAll(REGEX_TERMOS)) {
    const id = SIGLA_PARA_TERMO.get(m[1]);
    if (!id || (vistos && vistos.has(id))) continue;
    if (vistos) vistos.add(id);
    partes.push(s.slice(ultimo, m.index), termo(id, m[1]));
    ultimo = m.index + m[1].length;
  }
  partes.push(s.slice(ultimo));
  return partes;
}
/** A lista completa, em ordem alfabética, com âncora por termo. */
function listaGlossario() {
  const ordenados = GLOSSARIO.slice().sort((a, b) => a.termo.localeCompare(b.termo, "pt-BR"));
  return h("dl", { class: "glossario" }, ordenados.map(t => [
    h("dt", { id: "g-" + t.id }, t.termo),
    h("dd", {}, t.extenso ? h("span", { class: "extenso" }, t.extenso) : null, t.def)]));
}
