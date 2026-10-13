Crie um dashboard HTML autocontido (single-file) que mostre, para os municípios
do Espírito Santo, de onde vêm as receitas vinculadas à educação e onde
especificamente cada valor é aplicado. O uso final é como ferramenta de
trabalho em auditorias do TCE-ES — cada número exibido precisa ser rastreável
até sua fonte exata (endpoint, parâmetros, anexo/linha, data de extração), para
servir como evidência, não só como visualização.

## Fase 0 — reconhecimento (fazer antes de programar o pipeline)

Delegue esta fase ao subagente api-explorer e aguarde o relatório antes de prosseguir.

A API do SICONFI (https://apidatalake.tesouro.gov.br/ords/siconfi/tt/) não tem
documentação pública estável de nomes de coluna. Antes de escrever o parser:

1. GET /entes?an_exercicio=<ano>, filtre esfera municipal do ES → lista de
   id_ente (código IBGE de 7 dígitos) dos 78 municípios + o estado.
2. GET /anexos-relatorios?an_exercicio=<ano>&co_tipo_demonstrativo=RREO (e o
   mesmo para DCA) → confirme os nomes exatos de anexo disponíveis naquele
   exercício. Não assuma nomes fixos, eles variam entre exercícios.
3. Teste GET /rreo com no_anexo="RREO-Anexo 08" (LDB art. 72, Demonstrativo das
   Receitas e Despesas com MDE) para 3-4 municípios do ES. Documente no README
   se os dados vêm populados ou vazios — pela norma do Tesouro, esse anexo é
   declarado ao SIOPE e pode não estar preenchido no SICONFI. Se vier vazio ou
   incompleto para a maioria dos municípios, trate o SIOPE (ver Fase 3) como
   fonte primária desse indicador, não o SICONFI.
4. Documente no código, com comentário, a estrutura real de cada resposta
   (nomes de coluna) assim que confirmada — não generalize antes de testar.

## Fase 1 — de onde vêm as receitas

- GET /rreo com no_anexo="RREO-Anexo 01" (Balanço Orçamentário) por município e
  bimestre → receita realizada por categoria (impostos próprios, transferências
  correntes, transferências de capital).
- Receita do FUNDEB especificamente: teste primeiro se o Anexo 08 traz esse
  valor populado (Fase 0); se não, busque a conta contábil de receita do
  FUNDEB via /msc_orcamentaria (mensal, por id_ente e conta contábil) — a
  conta específica de FUNDEB no plano de contas precisa ser identificada
  inspecionando a resposta da API (peça um exercício de amostra e liste as
  contas com "FUNDEB" na descrição, não adivinhe o código).
- Repasses federais específicos (PDDE, PNAE, PNATE): FNDE Dados Abertos
  (https://www.fnde.gov.br/dadosabertos/, CKAN) ou Portal da Transparência
  (https://api.portaldatransparencia.gov.br, requer token) por município.
- Resultado esperado: uma tabela "origem da receita" por município/ano com
  categoria (imposto próprio, FUNDEB, transferência federal específica,
  outras) e valor.

## Fase 2 — onde cada valor é aplicado (três níveis, não confundir)

**Nível 1 — função/subfunção (automatizável, confiável):**
GET /rreo, no_anexo="RREO-Anexo 02", co_esfera=M, id_ente=<codigo> → despesa
por função (Educação = 12) e subfunção (ensino fundamental, infantil, médio,
EJA). Esse nível já está coberto no pipeline de financiamento geral, reuse-o.

**Nível 2 — natureza econômica (pessoal, custeio, investimento):**
/msc_orcamentaria, mensal, filtrando pelas contas de despesa (classe 3/4 do
PCASP) do ente. Requer mapear quais contas contábeis correspondem a pessoal,
material de consumo, obras/investimento — descubra isso inspecionando a
resposta real da API para 1-2 municípios antes de generalizar, documente o
mapeamento usado no código (não é padronizado o suficiente para assumir sem
checar).

**Nível 3 — item específico (qual obra, qual fornecedor, qual escola):**
NÃO existe fonte nacional padronizada e automatizável para isso. Não tente
simular esse nível com dados agregados. No dashboard, deixe esse nível
explicitamente marcado como "fora do escopo automatizável" com uma nota
apontando para: (a) o portal da transparência do próprio município (link,
quando existir, por município — heterogêneo, sem padrão de dados); (b)
sistemas internos do TCE-ES de acompanhamento de despesa por empenho/credor,
como próximo passo fora deste dashboard.

## Fase 3 — SIOPE como fallback para MDE/FUNDEB-magistério

Se a Fase 0 confirmar que o Anexo 08 não vem populado no SICONFI para os
municípios do ES:

- Estruture um scraper para os Relatórios Municipais do SIOPE
  (https://www.fnde.gov.br/siope/relatoriosMunicipais.jsp), isolado em módulo
  próprio (sem SLA, o layout pode mudar — trate falhas de parsing como aviso,
  não erro fatal que derruba o pipeline inteiro).
- Extraia: receita de impostos, despesa em MDE, % aplicado vs. mínimo de 25%,
  e % do FUNDEB aplicado em remuneração do magistério vs. mínimo de 70%.
- Marque visualmente no dashboard que esse dado vem de scraping (fonte menos
  estável que a API), com data da última extração bem visível.

## Indicadores de conformidade (o que interessa para auditoria)

- % da receita de impostos aplicada em MDE vs. mínimo constitucional de 25%
  (art. 212 CF) — destaque em vermelho municípios abaixo do mínimo.
- % do FUNDEB aplicado em remuneração do magistério vs. mínimo de 70%.
- Completude de prestação de contas: GET /extrato_entregas?id_ente=<codigo>
  &an_referencia=<ano> → sinalize municípios com declaração RREO/RGF/DCA em
  atraso ou não entregue no prazo — é achado clássico de auditoria, direto da
  API, sem precisar calcular nada.
- Reconciliação receita×despesa: para cada município, some despesa por
  função/subfunção (Nível 1) e compare contra a despesa com MDE do Anexo 08
  ou SIOPE — divergências grandes entre as duas fontes são um sinal a
  investigar, não um erro do pipeline; exiba a divergência como métrica, não
  esconda.

## Requisitos técnicos

- Pipeline em Python (requests + pandas + BeautifulSoup para o scraper do
  SIOPE), type hints, docstrings, tratamento de erro por fonte (uma fonte
  falhar não deve derrubar as demais).
- Cache local versionado por ano/fonte (JSON/CSV) para reprodutibilidade — a
  extração deve poder ser reexecutada e comparada com uma anterior.
- Cada registro no dataset final carrega: valor, fonte (SICONFI/SIOPE/FNDE),
  endpoint e parâmetros usados, e timestamp da extração — isso é o que torna
  o dashboard utilizável como evidência de auditoria, não só ilustrativo.
- Testes automatizados: soma de despesa por função bate com o total do
  anexo; código IBGE tem 7 dígitos; nenhum valor negativo inesperado.

## Requisitos do dashboard

- HTML único, autocontido, bibliotecas via CDN (Chart.js ou Plotly.js).
- Diagrama de fluxo receita → despesa (tipo Sankey) por município: origem
  (impostos próprios, FUNDEB, transferências federais específicas) → destino
  (função/subfunção de Educação).
- KPIs no topo: nº de municípios abaixo do mínimo de MDE, nº com declaração
  em atraso, maior divergência receita×despesa.
- Filtro por município e ano; comparação lado a lado entre municípios.
- Cada card/gráfico com um botão ou ícone "ver fonte" que mostra o
  endpoint/anexo/parâmetros exatos usados para aquele número — pense nisso
  como o equivalente de uma nota de rodapé de papel de trabalho de auditoria.
- Nível 3 (item específico) aparece como seção "limitações e próximos passos",
  nunca como dado inventado.
- Rodapé com data/hora da extração de cada fonte e link para a documentação
  de cada API usada.

## Entregáveis

1. Scripts de ETL por fonte (SICONFI, SIOPE, FNDE), com README de como rodar
   e religar cada um independentemente.
2. Dataset processado consolidado (CSV/JSON) com proveniência por registro.
3. dashboard.html.
4. README documentando: o que a Fase 0 descobriu sobre o Anexo 08 no
   SICONFI, o mapeamento de contas contábeis usado no Nível 2, e as
   limitações do Nível 3.