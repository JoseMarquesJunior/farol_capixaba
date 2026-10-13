# Mapeamento — dados abertos do TCE-ES para o painel de financiamento da educação

Levantamento de 22/09/2026 da organização
[TCE-ES no dados.es.gov.br](https://dados.es.gov.br/organization/tcees-tribunal-de-contas-do-estado-do-espirito-santo)
(28 datasets, API CKAN aberta), com amostras baixadas e analisadas. Os números
abaixo foram medidos nos arquivos, não presumidos. Três perguntas guiaram o
levantamento:

1. o que pode entrar no painel;
2. dá para descer a despesa ao **Nível 3** — quanto foi para cada escola, em que obra?
3. como incorporar o **financiamento do CNCA** nos municípios, e em que ele é gasto?

> **Situação (22/09/2026): as três etapas da seção 6 foram implementadas** — módulos
> `etl/tcees.py`, `etl/escolas.py` e `etl/cnca.py`, visões Conformidade, Receita →
> aplicação (Nível 3), Escolas e Programas. O que foi medido na implementação está no
> [README do módulo](../README.md); correções a este levantamento estão marcadas como
> *(corrigido)*.

## 1. Respostas curtas

| Pergunta | Resposta | Onde está |
|---|---|---|
| Despesa no nível do empenho (credor, ação, fonte, elemento) | **Sim**, 2020–2026, todos os 78 municípios | TCE-ES, *Empenhos dos municípios* |
| **O item comprado** (descrição, unidade, quantidade, preço unitário) | **Em parte** — 2022 em diante, 52 a 73 municípios por ano (77 em algum ano), pelas regras da seção 3.2-bis | TCE-ES, *Contratações → Itens - \<ano\>* |
| Nota fiscal (número, data, emitente) | **Não**, em nenhum dado aberto do TCE-ES | portal da transparência do município |
| Em que obra o dinheiro da educação foi alocado | **Sim**: 883 contratos de obra com setor "Educação" (765 municipais, R$ 2,0 bi; 112 do Estado e 6 de consórcios — *corrigido*: eram 771 com os consórcios), com objeto, contratada, valor e **situação da obra**; em parte deles, o prédio exato, com coordenadas | TCE-ES, *Contratações → Obras e serviços de engenharia* e *Bens vinculadores* |
| Quanto foi para cada escola | **Em parte** — três canais identificam a escola; o maior gasto (pessoal) não | PDDE (CGU, já no cache), repasses municipais a conselhos escolares (empenhos), obras com bem vinculador |
| Financiamento do CNCA por município e escola | **Sim**, pelo plano orçamentário federal | CGU (já no cache): PDDE-CNCA escola a escola; repasse ao Estado |
| Em que o dinheiro do CNCA é gasto | **Não, em dado aberto**: o PDDE é gasto pelos conselhos escolares e prestado ao FNDE, fora da contabilidade municipal | — (limitação) |
| Bônus | **Terceira fonte do índice de MDE** (a do TCE-ES), que diverge do SIOPE em 101 de 390 município-anos — em alguns casos atravessando os 25% | TCE-ES, *Despesas com saúde, educação e pessoal* |

## 2. Inventário dos 28 datasets

Relevância para o painel: **A** = alta (entra), **M** = média (complementa), **B** = baixa, **—** = sem uso.

| Dataset | Conteúdo | Grão e anos | Uso |
|---|---|---|---|
| **Empenhos dos municípios** | cada empenho: credor (nome e CNPJ/CPF), UG, unidade orçamentária, função/subfunção, programa e ação (nomes locais), natureza até subelemento, fonte com detalhamento, empenhado/liquidado/pago, restos a pagar | empenho × mês, 2020–2026, ZIPs de 17–43 MB (3–5 por ano); dicionário publicado | **A** — Nível 3 |
| **Contratações** — Obras e serviços de engenharia | contratos de obra: setor beneficiado, objeto, contratada, valores, **situação da obra**, tipo de intervenção, links do edital e do contrato | contrato, 5.089 linhas (9 MB) | **A** — obras |
| **Contratações** — Bens vinculadores | o bem público de cada contratação (nome do prédio, categoria, polígono e centroide) | bem, 645 linhas | **A** — obra → escola |
| **Despesas com saúde, educação e pessoal** — Educação | % aplicado em MDE apurado pelo TCE-ES, aplicação, alunos, aplicação por aluno, receita do FUNDEB | município × ano, **2009–2026** | **A** — conformidade |
| **Informações sobre remessas** — Prestação de Contas Mensal | data de homologação **e data-limite** de cada remessa ao TCE-ES | UG × mês, 13.672 linhas | **A** — prazos |
| **Contratações** — Contratações | a licitação/contratação: objeto, **setor beneficiado**, modalidade, situação, valor estimado e total, edital | contratação, 144.066 linhas (97 MB), 2022–2026 | **A** — chave da Educação para os itens |
| **Contratações** — Itens - \<ano\> | o **item** contratado: descrição, unidade, quantidade, preço unitário e total, o que foi medido, a contratada e a `ChaveInstrumento` | item × medição, um arquivo por ano, 2022–2026, 65–390 MB | **A** — o que foi comprado |
| Contratações — instrumentos, atas | contratos e atas de registro de preços | 47 MB a 713 MB | **M** — ainda não aberto |
| **Contratações** — Instrumentos com medições e alterações | **medições** e aditivos por instrumento | 1,2 GB | **A** — avanço físico-financeiro das obras |
| Despesas dos municípios (agregado) | mesma classificação dos empenhos, sem credor, **com dotação inicial e atualizada** | UG × mês × ação × fonte, 2013–2026 | **M** — orçado × executado |
| Receitas dos municípios | receita por natureza e fonte (CidadES) | 2013–2026 | **M** — conferência com SICONFI |
| Área temática de Pessoal | vínculos (nome, cargo, **UG — sem lotação**), vantagens agregadas por cargo, afastamentos | CSV de ~200 MB por trimestre | **B** — sem custo por escola |
| IEGM | nota do índice e das 7 dimensões (inclui i-Educ) | município, 2015–2018 e 2023 | **M** — contexto |
| Julgamento de contas | pareceres prévios | município × exercício | **M** — contexto |
| Relação de responsáveis | inidôneos, proibidos de contratar, contas irregulares | pessoa/empresa | **M** — cruzar com credores da educação |
| Resultados de fiscalizações | transparência, controle interno, portais (notas 2015–2025) | município | **B** — nota do portal, sem URL |
| Geo Obras | obras cadastradas até jan/2024 (Resolução TC 379/2024 encerrou o sistema) | 250 obras, 23 de educação | **B** — substituído por Contratações |
| Receitas e despesas estaduais | execução da esfera estadual | 2016–2026 | **M** — rastrear o CNCA repassado à SEDU (não aberto aqui) |
| Informações patrimoniais, Previdência, Saneamento, Saúde, Covid-19, Desestatizações, IVF, Atos de pessoal, e-SIC | — | — | — |
| Administração do TCE-ES (orçamento, aquisições, pessoal, acordos, receitas e despesas, outras bases) | dados do próprio Tribunal | — | — |

## 3. Nível 3 — a despesa no detalhe

### 3.1 Empenhos

Amostra analisada: 1º arquivo de 2024 (janeiro–abril): **864.577 linhas, 167.523 na
função 12**, os 78 municípios. Cada linha é a **movimentação do mês**, então o ano é a
soma dos meses. Campos que importam para o painel:

`CodigoUnidadeGestora, UnidadeGestora, EsferaAdministrativa (município),
NomeUnidadeOrcamentaria, CodigoFuncao/SubFuncao, CodigoPrograma/NomePrograma,
CodigoAcao/NomeAcao, CodigoCompleto (natureza de 8 dígitos), Elemento/SubElemento,
CodigoFonteReduzida/NomeFonteReduzida, CodigoDetalhamento/NomeDetalhamento,
CodigoComplementoFontesDestinacoesRecursos, Empenhada, Liquidada, Paga, restos a pagar,
NumeroEmpenho, AnoEmpenho, DataEmissao, NomeCredorFornecedor, CodigoCredorFornecedor`.

O que isso destrava no painel:

* **quem recebeu** o dinheiro da educação (credor e CNPJ), por fonte e elemento — por
  exemplo, as construtoras pagas com FUNDEB, ou os maiores fornecedores de merenda;
* **a ação local nomeada**: vários municípios dão nome de escola ou de obra à ação
  ("REFORMA E AMPLIAÇÃO DA EMEF GUSTAVO AMBRUST", em Alto Rio Novo; 147 ações de
  obra/reforma na amostra), embora a maioria use ação genérica;
* **fonte mais detalhada que a MSC**: o detalhamento separa FUNDEB 70% e 30%,
  convênios estaduais por instrumento (fonte 571), programas estaduais (576),
  royalties (573);
* conferência: a soma da função 12 deve fechar com o DCA I-E e a MSC (a verificar na ingestão).

Limites: **não há histórico** (a descrição do empenho) nem **número do contrato**; a
unidade orçamentária não é a escola (1 de 142 tem nome de escola). A ligação empenho →
contrato → obra é aproximada: mesma UG + mesmo CNPJ do contratado + período.

Volume: ~3 milhões de linhas por ano (todas as funções; ~20% educação), ~150 MB de ZIP
por ano. Não cabe embutido: a ingestão filtraria a função 12, gravaria o detalhe em
CSV/parquet e levaria ao painel só agregados (por ação, fonte, elemento e credor) e os
maiores credores de cada município.

### 3.2 Quanto foi para cada escola — o que existe e o que não existe

| Canal | O que identifica a escola | Tamanho | Situação |
|---|---|---|---|
| **PDDE federal** (todas as modalidades) | CNPJ e nome da unidade executora (conselho da escola) | R$ 193,7 mi em 2021–2025 no ES | **já no cache** da CGU |
| **Repasses municipais a conselhos escolares** (programas municipais de autonomia financeira, como o PMDDE de Alfredo Chaves e o PRODER de Aracruz) | credor do empenho = conselho escolar | 4.009 empenhos, **591 escolas, 27 municípios**, R$ 47,6 mi só em jan–abr/2024 (Serra 19,2 mi, Vitória 15,6 mi, Vila Velha 8,9 mi) | nos empenhos do TCE-ES |
| **Obras com bem vinculador** | nome do prédio + categoria ("Estabelecimentos educacionais — creche, anos iniciais…") + coordenadas | 98 bens educacionais, 65 contratos, **só 14 unidades gestoras** preenchem | nos dados de contratações |
| Pessoal (≈55% da despesa em educação) | — | — | **não existe**: o vínculo não traz lotação |
| Merenda, transporte, material por escola | — | — | não existe no dado aberto |

Para ligar tudo à escola do Censo (código INEP) e aos resultados que o NEDUC já tem
(IDEB, SAEB, PAEBES): casar o nome da escola (conselho escolar, bem vinculador, ação)
com `dw.dim_escola`, por município, e as coordenadas dos bens com as do Censo. É
casamento por nome — precisa de conferência e de uma taxa de acerto medida antes de
ir para o painel.

### 3.2-bis O item comprado (implementado em 22/09/2026)

O recurso **Itens - \<ano\>** fecha a maior lacuna que restava do Nível 3: *o que* foi
comprado. Cabeçalho conferido no arquivo: `DescricaoItem, UnidadeMedida,
QuantidadeItemContratado, ValorUnitarioItemContratado, ValorTotalItemContratado`, as
quantidades e valores **medidos**, `NomeContratado1` com o CNPJ, `IdentificacaoContratacao`
e `ChaveInstrumento`.

Estrutura real do arquivo: uma linha traz o item **contratado** (sem medição nem
alteração) e há uma linha a mais por **medição** (com `DescricaoItem` vazia) e por termo
de alteração — o parser separa as três e soma as medições por item.

**Como se recorta a Educação.** Três regras, todas afirmadas pela própria fonte:

| Regra | O que é | Itens em 2022 | Em 2022–2025 |
|---|---|---|---|
| `ug_educacao` | a unidade gestora da linha é secretaria ou fundo municipal de educação | 9.396 | 82.113 |
| `setor_educacao` | a contratação tem `SetorBeneficiado = Educação` | 2.790 | 36.674 |
| `obra_educacao` | o instrumento é uma obra da Educação (já identificada) | 24 | 2.747 |

Uma quarta regra foi **testada e descartada**: casar o CNPJ da contratada com os credores
da função 12 do mesmo município. Medida no arquivo de 2022, ela sozinha traria **54.247
linhas — 47% de todos os itens do Estado**, incluindo coisas como "limpeza geral de obras
(quadras, praças e jardins)" contratadas pela prefeitura. A empresa que vende à educação
também vende ao resto da prefeitura: o CNPJ não é evidência de que a compra é da educação.
Ele continua sendo usado no painel, mas só para **cruzar credor com contratação num
detalhamento rotulado como indício**, nunca para decidir o que entra no recorte.

**Cobertura, medida na coleta de 22/09/2026:** 121.534 itens em 2022–2025, **R$ 4,86 bi
contratados** e R$ 1,11 bi medidos, em 2.797 contratações de 2.306 empresas. Por ano: 2022,
12.210 itens em 52 municípios; 2023, 42.708 em 67; 2024, 38.477 em 70; 2025, 28.139 em 73 —
**77 dos 78 municípios** aparecem em algum ano. O recorte de 2022 ficou em 9% das linhas do
arquivo. `SetorBeneficiado` vem **vazio em 90%** das contratações (129.554 de 144.066) — só as
obras o preenchem por obrigação —, e apenas 22 municípios têm unidade gestora própria de
educação. Quem compra pela unidade gestora da prefeitura sem marcar o setor fica de fora:
ausência no painel **não é ausência de compra**, e o painel diz isso. O exercício do item é o
do **instrumento contratual**, não o do pagamento: contrato de 2024 pago em 2025 aparece em
2024, e o painel avisa quando o CNPJ tem contrato em outro ano.

### 3.3 Obras

**Contratações → Obras e serviços de engenharia** (atualizado pelo TCE-ES; substitui o
Geo Obras, encerrado em jan/2024):

* 883 contratos com `SetorBeneficiado = Educação`; **771 municipais, nos 78
  municípios, R$ 2,0 bi** em valor atual;
* `SituacaoObra`: **338 "Paralisação presumida"**, 242 não iniciadas, 51 em
  execução, 10 interrompidas, 2 paralisadas, 95 concluídas, 33 não identificadas —
  classificação do próprio TCE-ES (o critério de "presumida" deve ser confirmado com o Tribunal);
* por contrato: objeto, contratada (CNPJ), valor inicial e atual, datas, links do
  edital e do instrumento, tipo e objeto da intervenção; a `ChaveInstrumento` liga aos
  itens e às **medições** (arquivo de 1,2 GB) — daí sai o avanço físico-financeiro;
* **Bens vinculadores** dão o prédio exato, com polígono e centroide: 35 escolas com
  nome ligadas a um contrato de obra (ex.: EMEF Paulo Pereira Gomes, CMEI Prof. Thiago
  Zucoloto Machado). Cobertura ainda baixa.

No painel: lista de obras da educação por município, com a situação em destaque
(paralisada, não iniciada), valor, contratada e, quando houver, o prédio no mapa.

## 4. CNCA — financiamento e aplicação

### 4.1 O que os dados mostram (CGU, já no cache do painel)

O dinheiro do CNCA é identificado pelo **plano orçamentário** da ação federal, e o
favorecido diz qual escola recebeu:

| Ação / plano orçamentário | Favorecido | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| 0515 PDDE / **000C — PDDE Compromisso Nacional Criança Alfabetizada** | conselhos escolares | — | — | 4,11 mi | 0,31 mi | 0,32 mi |
| 0515 PDDE / 0007 — PDDE Alfabetização (antecessor) | conselhos escolares | 5,09 mi | 6,74 mi | — | — | — |
| 0509 Apoio à Educação Básica / **0014 — Compromisso Nacional Criança Alfabetizada** | **Estado (SEDU)** | — | — | — | 0,62 mi | 6,47 mi |

PDDE-CNCA: **1.095 unidades executoras** em escolas dos 78 municípios (municipais e
estaduais), mediana de R$ 3.705 por escola (de R$ 1.235 a R$ 25.935). O repasse ao
Estado segue a lógica de colaboração: no ES, o CNCA é implementado dentro do
**PAES — Pacto pela Aprendizagem no Espírito Santo** (Lei estadual 10.631/2017), ao
qual os 78 municípios aderiram.

### 4.2 Nos municípios

* **Nenhum empenho municipal** menciona CNCA ou alfabetização em fonte, ação ou
  programa na amostra de 2024 — coerente com o fluxo acima: o dinheiro vai às escolas
  (PDDE) e ao Estado, não ao orçamento das prefeituras.
* O braço financeiro do PAES para os municípios é o **FUNPAES** (Fundo Estadual de
  Apoio à Ampliação e Melhoria das Condições de Oferta da Educação Infantil e do Ensino
  Fundamental, Lei estadual 10.787/2017): infraestrutura, equipamentos, tecnologia. Os
  municípios o identificam no nome do programa ou da ação — por exemplo, Colatina
  "CONSTRUÇÃO E REFORMA DE CENTROS DE EDUCAÇÃO INFANTIL – FUNPAES" (R$ 3,7 mi em
  jan–abr/2024), Conceição da Barra "GESTÃO RECURSO FUNPAES". Pelos empenhos dá para
  dizer **em que** o FUNPAES foi gasto (elemento, credor, obra).

### 4.3 Em que o dinheiro do CNCA é gasto — o limite

O PDDE-CNCA é gasto pelos **conselhos escolares**, que prestam contas ao FNDE (fora
da contabilidade municipal e fora destes dados abertos). O repasse ao Estado pode ser
rastreado na execução estadual (dataset *Receitas e despesas estaduais* do TCE-ES),
ainda não aberto nesta análise. O painel pode mostrar **quanto e para quem**; o
**em quê** do PDDE fica como próximo passo (prestação de contas do PDDE no FNDE, ou
questionário às escolas/secretarias, nos moldes do TCE-PB).

## 5. MDE — terceira fonte, com divergências

O CSV *Educação* do TCE-ES (2009–2026) casou com o painel em **390 de 390**
município-anos. A diferença mediana para o SIOPE é zero, mas **101 município-anos
divergem mais de 0,5 p.p.**, e alguns atravessam o mínimo de 25%:

| Município | Ano | TCE-ES | SIOPE |
|---|---|---|---|
| Vila Velha | 2021 | **24,61%** | 29,36% |
| Ibiraçu | 2023 | **24,83%** | 28,58% |
| Mimoso do Sul | 2023 | **22,83%** | 25,56% |
| Laranja da Terra | 2023 | **24,04%** | 25,00% |
| Muniz Freire | 2024 | **24,49%** | 25,83% |
| São Gabriel da Palha | 2024 | **24,53%** | 26,17% |
| Pedro Canário | 2024 | **24,15%** | 25,00% |
| Brejetuba | 2025 | **24,55%** | 25,78% |

As duas fontes são declaratórias, com metodologias próprias (o do TCE-ES vem das
remessas do CidadES). Divergência que atravessa o mínimo constitucional é sinal de
auditoria de primeira ordem — e hoje o painel só vê o SIOPE.

## 6. Proposta de incorporação

| Etapa | O que entra | Fontes | Esforço | Risco |
|---|---|---|---|---|
| **1. Ganhos rápidos** | MDE do TCE-ES como 3ª fonte, com a divergência SIOPE × TCE-ES na Conformidade; prazos das remessas ao TCE-ES (data-limite explícita); obras da educação por município com situação (paralisadas em destaque); módulo CNCA automático (PDDE-CNCA por município e por escola, repasse ao Estado) substituindo os marcadores manuais | TCE-ES (3 arquivos pequenos), CGU (cache) | baixo | baixo |
| **2. Nível 3 no painel** | empenhos da função 12: credores, ações nomeadas, fontes detalhadas, repasses a conselhos escolares, execução do FUNPAES; orçado × executado nas ações de obra | TCE-ES empenhos (~150 MB/ano) e despesas agregadas | médio | volume (pré-processar e embutir só agregados) |
| **3. Visão por escola** | escola (INEP) com PDDE, repasse municipal, obras e o prédio no mapa, ao lado dos resultados (IDEB, SAEB, PAEBES) do NEDUC; avanço físico-financeiro das obras pelas medições | etapas 1–2 + Censo no PostgreSQL + medições (1,2 GB) | alto | casamento por nome (medir a taxa de acerto antes) |

Pontos de cuidado:

* o dado do TCE-ES é **declaratório** (remessas do CidadES), como o do SICONFI e o do
  SIOPE — o que ganha força é o cruzamento entre eles;
* "paralisação presumida" e o método do % de MDE do TCE-ES devem ser confirmados com
  o Tribunal antes de virar KPI;
* bens vinculadores ainda cobrem poucas unidades gestoras: servem para localizar a
  obra quando existem, não para dizer que as demais não têm obra;
* o tamanho do painel (5,5 MB no levantamento, 18 MB com o Nível 3 completo):
  empenho a empenho e item a item não cabem embutidos; o detalhe fica em CSV, e o painel
  embute agregados, os maiores credores e os maiores itens de cada município-ano.

## 7. O que não está nos dados abertos

* custo de pessoal por escola (o vínculo não traz lotação);
* histórico (descrição) do empenho e **número do contrato no empenho** — é o que impede
  ligar empenho a item com certeza; o painel cruza os dois por CNPJ e município e
  rotula o resultado como indício;
* **nota fiscal**: número, data e emitente não estão em dado aberto do TCE-ES;
* o item comprado onde o município não marca o setor beneficiado e compra pela unidade
  gestora da prefeitura (~29 dos 78 municípios, ver 3.2-bis);
* o gasto das escolas com PDDE (prestação de contas das unidades executoras ao FNDE);
* URL dos portais de transparência municipais (a fiscalização de 2025 traz só a nota;
  os links declarados nos contratos — `UrlInstrumentoContratacao` — podem servir de
  ponto de partida, com conferência).

**Onde o município preenche essas lacunas.** Vitória publica uma API REST aberta e
documentada em <https://wstransparencia.vitoria.es.gov.br/help/> (conferida em
22/09/2026, sem token), com `api/despesa/fornecedor?exercicio=&nomeCPFCNPJ=` (despesa
por favorecido), `api/Licitacao/{id}/LoteItens` (itens da licitação) e
`api/pessoal/lotacao` — **lotação do servidor**, justamente o que falta para custear
pessoal por escola. O pipeline não a consulta: é uma API por município, sem padrão entre
os 78, e o painel é de coleta em lote com proveniência por número. Ela fica registrada
em `dados_manuais.yaml → nivel3.portais_transparencia` (campo `api`) e aparece no card
de limitações, como caminho para quem for buscar à mão.

## Fontes

* [Organização TCE-ES no dados.es.gov.br](https://dados.es.gov.br/organization/tcees-tribunal-de-contas-do-estado-do-espirito-santo) — API: `https://dados.es.gov.br/api/3/action/package_search?fq=organization:tcees-tribunal-de-contas-do-estado-do-espirito-santo`
* [Portal da Transparência (CGU) — transferências](https://portaldatransparencia.gov.br/download-de-dados/transferencias) (planos orçamentários do CNCA)
* [PAES — Pacto pela Aprendizagem no Espírito Santo (SEDU)](https://sedu.es.gov.br/paes) e [FUNPAES](https://paes.sedu.es.gov.br/funpaes)
* [Legislação do PAES (SEDU)](https://paes.sedu.es.gov.br/legislacao)
