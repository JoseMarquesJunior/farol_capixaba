# ETL do financiamento da educação

Extrai de seis fontes — **SICONFI**, **SIOPE**, **FNDE** (via CGU), **TCE-ES** (dados
abertos do Tribunal), o **Censo Escolar** do banco local do NEDUC e o **ICA** do INEP
(planilha oficial da Avaliação da Alfabetização) —, compõe os
indicadores de auditoria e grava em `../dados/processado/` um dataset em que cada
número carrega a consulta de onde saiu. O que o painel mostra, o que a Fase 0
descobriu e as limitações estão no [README do módulo](../README.md).

## Rodar

Tudo **a partir da raiz do repositório**:

```powershell
python -m financiamento.etl.pipeline                        # as seis fontes; detecta o último exercício publicado
python -m financiamento.etl.pipeline --anos 2021-2025       # ou fixa os anos (2023,2024 também vale)
python -m financiamento.build_dashboard                     # regenera financiamento/dashboard.html
python -m financiamento.etl.comparar                        # compara as duas últimas extrações
```

### Opções do pipeline

| Opção | Efeito |
|---|---|
| `--fontes siconfi,siope,fnde,tcees,censo,inep` (padrão: as seis) | fontes que **podem usar a rede** (ou o banco); as demais rodam em modo `offline` (só o cache) |
| `--atualizar nao` (padrão) | usa o cache; só consulta o que falta |
| `--atualizar vazios` | refaz apenas respostas vazias (município que publicou depois, PDF que apareceu no FTP) |
| `--atualizar tudo` | ignora o cache das fontes de `--fontes` e consulta de novo |
| `--sem-rreo` | pula o RREO Anexo 02 bimestral |
| `--sem-empenhos` | TCE-ES sem os empenhos e as despesas agregadas (~460 MB de ZIP para 2021–2025) |
| `--sem-medicoes` | TCE-ES sem o arquivo de medições das obras (1,2 GB lido em fluxo) |
| `--sem-itens` | TCE-ES sem as contratações e os itens contratados (~1,1 GB lido em fluxo para 2022–2025) |
| `--trabalhadores N` | consultas em paralelo ao SICONFI (padrão 6; o ritmo global limita a taxa de qualquer forma) |
| `--estrito` | sai com código 1 se uma conferência, a validação ou uma fonte falhar (útil em CI) |

### Religar uma fonte sozinha

Cada fonte tem seu script. Ele coleta (ou lê do cache), extrai, confere e grava as
saídas **da fonte** em `dados/processado/fontes/<fonte>/`, sem tocar as outras:

```powershell
python -m financiamento.etl.siconfi --anos 2021-2025 [--atualizar vazios|tudo|offline] [--trabalhadores 4]
python -m financiamento.etl.siope   --anos 2021-2025 [--atualizar ...]
python -m financiamento.etl.fnde    --anos 2021-2025 [--atualizar ...]
python -m financiamento.etl.tcees   --anos 2021-2025 [--atualizar ...] [--sem-empenhos] [--sem-medicoes] [--sem-itens]
python -m financiamento.etl.ica     [--atualizar tudo|offline]      # ICA do INEP: uma planilha, hash SHA-256 conferido
```

O Censo não tem script avulso: `escolas.py` lê o banco na primeira execução (ou com
`--fontes censo --atualizar tudo`) e guarda o retrato em `dados/bruto/censo/`.

Para levar a atualização ao painel: `python -m financiamento.etl.pipeline --fontes <fonte>`
(as outras fontes são relidas do cache, em ~1,5 minuto) e `python -m financiamento.build_dashboard`.

**Isolamento.** No pipeline, cada fonte roda dentro de uma proteção: se ela levantar
qualquer erro, o pipeline registra o erro em `meta.fontes_status`, segue com tabelas
vazias para essa fonte e grava o resto normalmente. O painel mostra a situação de cada
fonte no rodapé. Dentro das fontes, a falha também é granular: um PDF ilegível ou um
mês que não baixou vira aviso daquele município-ano ou mês, não da fonte inteira.

## Atualizar os dados

* **Novo exercício publicado:** rode o pipeline sem `--anos`. Ele testa `ano_atual − 1`
  para trás e escolhe o mais recente em que ao menos 50% dos entes já entregaram a DCA
  (`LIMITE_COBERTURA_EXERCICIO` em `config.py`); a janela é de 5 exercícios.
* **Município que entregou depois / PDF que apareceu depois:** `--atualizar vazios`.
  Respostas vazias são cacheadas de propósito ("não publicou" é um fato).
* **A CGU recusou downloads** (aviso "servidor recusou"): rode de novo mais tarde,
  `python -m financiamento.etl.fnde --anos ...`. Os meses já baixados ficam no cache; o
  cliente espera 20 s entre ZIPs e para na primeira recusa, sem insistir.
* **O SIOPE republicou um demonstrativo** (retificação): `python -m financiamento.etl.siope
  --anos <ano> --atualizar tudo`. A data de publicação no FTP fica registrada.
* **Dado manual novo** (MDE de reserva, CNCA, portal municipal): edite
  `../dados_manuais.yaml` e rode o pipeline; o arquivo é validado e erro de digitação para
  o ETL com a mensagem do registro.
* **Mudou o nome de um anexo:** o ETL avisa (`nome de anexo mudou`) e segue com o nome achado.
* **O TCE-ES publicou arquivos novos** (o portal troca os arquivos de lugar a cada carga):
  `python -m financiamento.etl.tcees --anos <anos> --atualizar tudo`. Os recursos são achados
  pelo NOME no catálogo do dataset (`package_show`), não por URL fixa; o catálogo fica em
  `dados/bruto/tcees/_catalogo/`.
* **Censo novo no banco do NEDUC:** `python -m financiamento.etl.pipeline --fontes censo --atualizar tudo`.

## O que entra, de cada fonte

### SICONFI (`apidatalake.tesouro.gov.br/ords/siconfi/tt`)

| Endpoint | Parâmetros | Para quê | Módulo |
|---|---|---|---|
| `/entes` | — | 78 municípios + Estado (código 32) | `entes.py` |
| `/dca` | `an_exercicio, id_ente, no_anexo=DCA-Anexo I-E` | despesa por função e subfunção (Nível 1) | `pipeline.py`, `parsing.py` |
| `/dca` | `… no_anexo=DCA-Anexo I-C` | FUNDEB e os códigos das contas do FUNDEB | `parsing.py` |
| `/rreo` | `an_exercicio, nr_periodo, co_tipo_demonstrativo, no_anexo=RREO-Anexo 02, co_esfera, id_ente` | execução bimestral da função 12 | `pipeline.py` |
| `/rreo` | `… no_anexo=RREO-Anexo 01` | receita por categoria, seis bimestres | `rreo_receita.py` |
| `/msc_orcamentaria` | `id_ente, an_referencia, me_referencia=12, co_tipo_matriz=MSCC, classe_conta=6, id_tv=ending_balance, limit=5000` | FUNDEB, natureza econômica (Nível 2), fluxo fonte → subfunção | `msc.py` |
| `/extrato_entregas` | `id_ente, an_referencia` | entregas de RREO, RGF e DCA × prazos da LRF | `entregas.py` |

O RREO é tentado nos dois tipos (`RREO` e `RREO Simplificado`), começando pelo que
funcionou no bimestre anterior. `/anexos-relatorios` não responde; os nomes de anexo
são lidos nos dados (`anexos.py`). O cliente espaça as requisições de todas as threads
e, num HTTP 429, respeita `Retry-After` ou espera 15, 30, 60 s… — e faz as outras
threads esperarem junto.

### SIOPE (FNDE) — `siope.py`

`ftp://ftp.fnde.gov.br/web/siope/RREO/RREO_Municipal_<IBGE6>_6_<ano>.pdf` (6º bimestre),
lido com `pypdf`. Os itens do demonstrativo são achados pelo rótulo (o layout mudou em
2023 e em 2024), e cada percentual é conferido contra a própria linha. Os relatórios
HTML do SIOPE exigem reCAPTCHA e não são usados.

### FNDE via CGU — `fnde.py`

`https://portaldatransparencia.gov.br/download-de-dados/transferencias/<AAAAMM>` → ZIP com
o CSV nacional do mês (`;`, latin-1). Guarda-se o recorte `UF = ES`. Ações usadas:
`0369` salário-educação, `00PI` PNAE, `0969` PNATE, `0515` PDDE, `00SB` complementação
do FUNDEB, e as demais do órgão FNDE (26298) como "outras". Município ligado pelo nome
(conferido contra os 78 do `/entes`); linha sem município é repasse a escola estadual e
fica fora, contada no status.

### TCE-ES — `tcees.py` (dados.es.gov.br, CKAN aberto, sem token)

| Recurso (dataset) | Guardado | Para quê |
|---|---|---|
| "Educação" (`tcees-despesas-com-saude-educacao-…`) | inteiro | % de MDE apurado pelo Tribunal (terceira apuração, ao lado do SIOPE e do manual) |
| "Prestação de Contas Municipal" (`obrigacoes`) | inteiro | remessa mensal de cada UG ao Tribunal, com a **data-limite na própria fonte** |
| "Obras e serviços de Engenharia" e "Bens vinculadores" (`tcees-contratacoes`) | inteiros | contratos de obra com setor beneficiado Educação, o prédio (nome e centroide) e a situação |
| "Instrumentos contratuais com medições e alterações" (`tcees-contratacoes`) | **recorte** (lido em fluxo, 1,2 GB → só as obras da Educação) | medições e aditivos de cada obra |
| "Contratações" (`tcees-contratacoes`) | **recorte** (97 MB → só as da Educação) | a contratação: objeto, setor beneficiado, modalidade, valor; dá as chaves do recorte dos itens |
| "Itens - \<ano\>" (`tcees-contratacoes`), um por ano de 2022 | **recorte** (65–390 MB cada → só os da Educação) | **o item comprado**: descrição, unidade, quantidade, preço unitário, valor total e o medido |
| "Empenhos dos municípios" (`tcees-empenho`), 3–5 ZIPs por ano | **recorte** (função 12) | Nível 3: credor, ação nomeada, fonte com detalhamento, repasses a conselhos escolares, FUNPAES |
| "Despesas dos municípios" (`despesas-municipios`), 1 ZIP por ano | **recorte** (função 12) | dotação inicial e atualizada por ação (orçado × executado) |

O recorte guarda, no `.json` ao lado, a URL, o instante, o **SHA-256 e o tamanho do
arquivo original** e as linhas lidas × mantidas — prova de onde ele saiu sem guardar
10 GB. Os CSVs vêm com `;`, latin-1 (bens vinculadores em UTF-16) e vírgula decimal.
HTTP 403/405/429 para a coleta na hora (`ServidorRecusou`); o que já está no cache vale.

### Censo Escolar — `escolas.py` (PostgreSQL local do NEDUC)

Lê `dw.dim_escola` + `dw.fato_escola_ano` (escolas municipais e estaduais ativas desde
2021, com matrículas e infraestrutura), `stg.v_ideb_censo` e `stg.v_paebes_escola`, e
guarda o retrato em `dados/bruto/censo/*.csv.gz` + `censo_escolas.json` (instante e as
consultas SQL). Sem banco, usa o retrato; sem os dois, a visão Escolas diz que não há
cadastro — e o resto do painel sai normalmente.

**Recorte da Educação nos itens.** Três regras, todas da própria fonte: a **unidade gestora**
da linha é secretaria ou fundo municipal de educação; a **contratação** tem
`SetorBeneficiado = Educação`; ou o **instrumento** é uma obra da Educação. Cada linha guarda
qual regra a trouxe (`vinculo`). O CNPJ da contratada foi testado como quarta regra e
descartado: medido no arquivo de 2022, casar o CNPJ com os credores da função 12 traria 47%
de todos os itens do Estado — quem vende à educação também vende ao resto da prefeitura. Ele
segue sendo usado no painel para cruzar credor com contratação num detalhamento **rotulado
como indício**, nunca para decidir o que entra no recorte. O exercício do item é o do
**instrumento contratual**, não o do arquivo, e o item de contrato plurianual conta uma vez
só, com as medições de todos os anos somadas.

**Vínculo recebedor → escola.** Nenhuma fonte financeira traz o código INEP: a unidade
executora do PDDE, o conselho escolar credor do município e o bem vinculador da obra
são ligados à escola do Censo pelo **nome**, dentro do mesmo município e da rede que o
nome indica (EMEF → municipal, EEEFM → estadual). Pontuação: fração dos termos
distintivos da origem achados no nome do Censo (limiar 0,75), com desempate pelo
inverso e pelo tipo da escola (EMEF × CMEI); a vantagem sobre o segundo candidato tem
de ser clara. UEx estadual sem município no arquivo da CGU procura na rede estadual
inteira com exigência maior (nome completo). Obra: nome e, se não bastar, distância
do centroide até a escola (≤ 400 m) com nome parcial. Tudo o que não passa fica **sem
vínculo**, com o nome original, em `escolas_vinculos.csv` — nunca é atribuído por palpite.

### INEP — ICA — `ica.py`

Uma planilha oficial por edição (`download.inep.gov.br/avaliacao_da_alfabetizacao/resultados/
resultados_e_metas_municipios_2025_3.xlsx`): taxa de alunos alfabetizados da rede municipal
em 2023, 2024 e 2025 (% acima de 743 pontos na escala Saeb), metas 2024–2030, nível e
participação, para os 5.485 municípios do país. Baixada com tentativas (o servidor derruba a
conexão de forma intermitente) para `dados/bruto/inep/ica/`, com um `.json` ao lado (URL,
instante, tamanho, SHA-256). **O hash é conferido contra o esperado e a coleta para se
divergir** — o INEP republicando a planilha muda o dado, e isso não pode passar em
silêncio; para aceitar a nova versão, atualiza-se `SHA256` em `ica.py` explicitamente. A
leitura usa `header=1` (a primeira linha é o rótulo humano, a segunda o código da variável),
descarta o rodapé sem código de município e recusa código duplicado. O recorte UF=ES sai em
formato longo (município × ano) com `situacao = sem_dado` onde a taxa não foi publicada —
nunca zero —, e município do ES ausente da planilha vira aviso. Lógica de download e
verificação reaproveitada de `luizmaibashi/painel-alfabetizacao-cgu` (MIT).

### CNCA — `cnca.py`

Sem coleta própria: separa, nas tabelas do FNDE, o PDDE de plano orçamentário **000C**
(CNCA) e **0007** (PDDE-Alfabetização, 2021–2022), escola a escola, e o apoio ao Estado
(ação 0509, PO 0014); dos empenhos do TCE-ES, o que o município nomeou como **FUNPAES**.
O repasse por município-ano vira o campo `repasse` (origem `api`) do `programas.yaml`; a
tabela do ICA vira o campo `ica` (também `api`), um registro por município × ano.

## Módulos

| Arquivo | Papel |
|---|---|
| `pipeline.py` | orquestra tudo, isola cada fonte, compõe e grava as saídas e a versão |
| `cliente.py` | cliente do SICONFI: paginação, ritmo global, 429, modos de cache (inclusive `offline`), URL reproduzível |
| `parsing.py` | DCA e RREO Anexo 02: funções puras (função, subfunção, FUNDEB e os códigos das contas do FUNDEB) |
| `rreo_receita.py` | RREO Anexo 01: receita por categoria, por bimestre |
| `msc.py` | MSC: estágios do empenho, natureza econômica (o mapeamento do Nível 2), fonte de recursos, FUNDEB |
| `entregas.py` | extrato de entregas, prazos da LRF, situação de cada obrigação |
| `siconfi.py` | junta receita, MSC e entregas por município-ano (paralelo); script avulso da fonte |
| `siope.py` | download do FTP com cache, extração do PDF por rótulo, conferência interna; script avulso |
| `fnde.py` | download em lote da CGU com recorte do ES, classificação, PDDE por escola e plano orçamentário, recusa do servidor; script avulso |
| `tcees.py` | catálogo CKAN, download com recorte (ZIP e fluxo), MDE do Tribunal, prazos, obras, empenhos, dotação; script avulso |
| `escolas.py` | retrato do Censo, vínculo recebedor → escola, dinheiro por escola |
| `cnca.py` | o módulo automático do CNCA (PDDE 000C/0007, apoio ao Estado, FUNPAES) e os registros `api` do programas.yaml |
| `ica.py` | ICA do INEP: download com hash conferido, leitura da planilha oficial, recorte do ES com "sem dado" explícito; script avulso |
| `proveniencia.py` | `Consulta` (a requisição exata) e o registro das consultas de uma execução |
| `indicadores.py` | catálogo dos indicadores: localização na fonte, cálculo, se admite negativo |
| `composicao.py` | origem da receita, conformidade, conciliação, dataset consolidado, validação |
| `historico.py`, `comparar.py` | versões da extração e comparação entre duas |
| `anexos.py`, `entes.py`, `manuais.py`, `programas.py`, `config.py`, `controle_fundeb.py` | como antes (anexos, entes, dados manuais, programas, constantes, controle I-C × I-HI) |

### A matriz de evidências do CNCA

Um subsistema à parte, com ciclo de coleta próprio: ele não entra em `pipeline.py` e não
depende dele para rodar — lê o cache que o pipeline geral já baixou. A ordem importa só
entre `evidencias.py` e os demais: ele é o último.

| Arquivo | Papel |
|---|---|
| `matriz.py` | carrega e **valida** `config/matriz_cnca.yaml`. Falha alto em achado que aponte para pergunta inexistente, limiar citado e não declarado, proxy sem ressalva, status fora do vocabulário, ou achado que tenha constatação e ainda marque indício individual |
| `execucao.py` | os cortes dos empenhos que o painel geral não fazia: mês a mês por subfunção, fonte com restos a pagar, elemento dentro da fonte, data do primeiro empenho, ação que nomeia alfabetização, idade do RP e dotação por fonte. **Sem rede**: lê o recorte já em cache |
| `censo_alfabetizacao.py` | Censo no recorte da alfabetização: matrículas e turmas de 1º e 2º ano, salas, biblioteca e sala de leitura. Retrato em `dados/bruto/censo/alfabetizacao.csv.gz`, reproduzível sem o banco |
| `contratos.py` | classifica o objeto das contratações da Educação por palavra-chave (P47, P48), guardando os termos que fizeram cada uma entrar |
| `diarios.py` | Querido Diário (busca nos municípios cobertos), índice de edições do DOM-ES/AMUNES, e a lista de buscas manuais para os demais |
| `estado.py` | SIGEFES: repasses do Estado aos municípios na função 12 (P18), com o FUNPAES separado e o casamento por nome medido |
| `evidencias.py` | monta a tabela longa do papel de trabalho, classifica cada município × achado e grava o `dataset_cnca.json` do painel |

## Sem dado, falha e não coletado

São três coisas diferentes, e o pipeline as separa:

* **sem dado publicado** — a fonte respondeu vazio (ou o PDF não existe no FTP). Cacheado.
* **falha de consulta** — esgotou as tentativas. **Não** é cacheada; o pipeline segue.
* **não coletado** — modo `offline` e a consulta nunca foi feita. Aparece assim, sem valor.

Em nenhum dos três casos o valor vira zero.

## Saídas (`dados/processado/`)

| Arquivo | Conteúdo |
|---|---|
| `consolidado.csv` | **um número por linha, com a proveniência**: indicador, valor, fonte, endpoint, parâmetros, instante da coleta, arquivo do cache, localização na fonte e cálculo. Dos itens contratados entram os que o painel mostra (os maiores de cada município-ano): cada linha do consolidado repete localização, cálculo e consulta por extenso, e os 121 mil itens inteiros somariam ~220 MB de texto repetido — a tabela completa, com a mesma proveniência por linha, está em `tcees_itens.csv` |
| `consultas.csv` | cada consulta da execução: id, fonte, descrição, URL, instante, arquivo, SHA-256 |
| `financiamento_anual.csv` | ente × exercício: despesa, FUNDEB (DCA, MSC e SIOPE), MDE e FUNDEB 70% (SIOPE), entregas, conciliação, ids das consultas |
| `receita_origem.csv` | município × exercício × origem (impostos próprios, FUNDEB, federal específica, outras, total) |
| `receita_bimestral.csv` | RREO Anexo 01: todas as linhas de receita, por bimestre |
| `fluxo_fonte_subfuncao.csv` | MSC: empenhado por fonte de recursos e subfunção |
| `natureza_economica.csv` | MSC: empenhado, liquidado e pago por categoria, subcategoria e elemento |
| `entregas.csv` | uma linha por obrigação (instituição × relatório × período): prazo, entrega, situação, dias |
| `siope_anexo8.csv` | os campos extraídos de cada PDF, os itens usados e as datas do PDF |
| `repasses_fnde.csv` | município × exercício × programa × destino (município ou escolas) |
| `pdde_por_escola.csv` | PDDE por unidade executora, plano orçamentário e exercício (inclui as escolas estaduais, sem município) |
| `cnca_municipio.csv`, `cnca_estado.csv`, `cnca_funpaes.csv` | o módulo CNCA: PDDE-CNCA por município-ano, apoio ao Estado por mês, empenhos FUNPAES |
| `ica_municipios.csv`, `ica_metas.csv` | ICA do INEP: município × ano (taxa, meta, nível, participação, situação, consulta); metas pactuadas 2024–2030 |
| `tcees_mde.csv`, `tcees_remessas_pcm.csv` | MDE apurado pelo TCE-ES; remessas mensais ao Tribunal com prazo e situação |
| `tcees_obras_educacao.csv` | contratos de obra da Educação: objeto, contratada, valores, situação, prédio (JSON), medições, aditivos, links |
| `tcees_empenhos_*.csv` | Nível 3: `credores` (15 maiores por município-ano), `acoes`, `fontes`, `conselhos`, `funpaes`, `obras_empenhos`, `total`, `credor_acao` (os 8 maiores credores de cada ação + "(demais)") |
| `tcees_contratacoes_educacao.csv` | contratações da Educação: objeto, setor, modalidade, valor estimado e total, edital, e por qual regra entraram |
| `tcees_itens.csv` | **um item por linha**: descrição, unidade, quantidade, preço unitário, valor total, medido, contratada, contratação e o vínculo com a Educação |
| `tcees_itens_resumo.csv`, `tcees_itens_contratada.csv` | itens e valor por município-ano; e por contratada (CNPJ), que é o que o detalhamento de um credor consulta |
| `tcees_dotacao_acoes.csv` | dotação inicial e atualizada × empenhado, liquidado e pago, por ação |
| `escolas.csv`, `escolas_vinculos.csv`, `escolas_recursos.csv` | cadastro do Censo; cada vínculo recebedor → escola com nota e método; dinheiro por escola, exercício, canal e plano |
| `despesa_subfuncao.csv`, `execucao_bimestral.csv`, `cobertura.csv` | como antes |
| `avisos.csv` | avisos das fontes (conferência interna do SIOPE, mês não baixado, recurso do TCE-ES que falhou…) |
| `dataset.json` | tudo acima + catálogo dos indicadores, KPIs, conferências e situação das fontes — é o que o painel embute (tabelas grandes em forma colunar) |
| `historico/<versão>/` | `consolidado.csv.gz` + `manifesto.json` de cada execução |
| `fontes/<fonte>/` | saídas dos scripts avulsos de cada fonte |

CSVs em UTF-8, separador vírgula, ponto decimal, valores em reais.

## Versões e comparação

Cada execução do pipeline grava uma versão. `python -m financiamento.etl.comparar`
(ou `--antes <versão> --depois <versão>`) casa os registros pela chave estável —
município, exercício, período, indicador e detalhe — e classifica cada um em *novo*,
*removido*, *alterado* (diferença > 0,005), *reextraído* (mesmo valor, coleta mais nova)
ou *igual*, gravando o detalhe em `historico/comparacao_<antes>_<depois>.csv`.

## Testes

```powershell
python -m pytest financiamento/tests
```

251 testes, sem rede. As fixtures em `tests/fixtures/` são **respostas reais** das
fontes: DCA e RREO de Vitória, Afonso Cláudio e Colatina; a MSC de Afonso Cláudio 2024
(recortada); o Anexo 01 nos dois tipos de RREO; o extrato de entregas de Afonso Cláudio
2024; e três PDFs do SIOPE, um por layout (2021, 2023 com a EC 119, 2024). Entre outros:

* **soma da despesa por função = total do anexo** (DCA) e **soma das subfunções = função 12**
  (DCA e MSC); os estágios da MSC batem ao centavo com o DCA;
* **código IBGE com 7 dígitos** (e a conversão para os 6 do SIOPE);
* **nenhum valor negativo inesperado**: a validação do consolidado aponta negativo onde o
  indicador não admite e aceita onde admite (saldo do FUNDEB, diferenças);
* FUNDEB identificado na MSC pelos códigos do DCA; mapeamento natureza → categoria;
* SIOPE: indicadores nos três layouts, compensação da EC 119, percentual adulterado vira
  aviso, rótulo ausente não levanta exceção;
* prazos da LRF (ano bissexto, RGF quadrimestral e semestral, DCA), fuso de Brasília,
  retificação não contada como atraso — e o atraso real da Câmara de Afonso Cláudio no
  RGF do 1º semestre de 2024 (120 dias);
* CGU: PDDE às escolas separado, favorecido estadual fora, plano orçamentário do CNCA
  (000C às escolas, 0014 ao Estado), recusa do servidor interrompe a coleta sem insistir;
* TCE-ES: vírgula decimal e vazio que não vira zero, UTF-16, prazo das remessas vindo da
  fonte (no prazo, com atraso, não homologada, prazo aberto), medição repetida contada uma
  vez, empenho intra fora, pessoa física nunca nominal, recorte de ZIP com o hash do
  original e leitura do cache sem rede;
* itens: a linha do contratado separada das linhas de medição, item de contrato plurianual
  contado uma vez com as medições somadas, o vínculo com a Educação só pelas regras da fonte
  (CNPJ da contratada **não** basta), contratação repetida por mês ficando com a mais recente;
* credor × ação: os maiores guardados, a cauda somada em "(demais)" sem perder valor, pessoa
  física agregada como na tabela de credores;
* matrículas: "Alunos" do TCE-ES conferido contra o Censo, despesa por matrícula e a rede sem
  matrícula que não vira divisão por zero;
* escolas: termos distintivos, desempate por tipo (EMEF × CMEI), ambíguo fica sem vínculo,
  outro município não casa, UEx estadual sem município, obra por coordenada só com nome parcial;
* ICA: planilha sintética no layout do INEP (rótulo humano + código da variável + rodapé)
  lida e recortada; taxa ausente vira `sem_dado` e nunca zero; município do ES ausente vira
  aviso; hash divergente para alto; arquivo já presente não dispara download; modo offline
  sem cache é "não coletado"; consolidado do INEP com proveniência; o campo `ica` recusa dado
  manual e o `articuladores_bolsa` (quantidade) aceita zero e recusa negativo, fração e texto;
  o checklist de governança exige id e texto únicos;
* montagem do HTML: dado embutido com segurança, sem chamada de API, sem `innerHTML`, e
  nenhum nome global repetido entre os scripts da página.

## Cache bruto e git

`dados/bruto/` (≈208 MB, ~8.200 arquivos) é a trilha de auditoria: reexecutar o ETL a
partir dele reproduz o dataset sem tocar nenhuma fonte. `dados/processado/` tem ~372 MB fora do
histórico (o `consolidado.csv` sozinho, ~197 MB, e `tcees_itens.csv`, ~53 MB), mais
~6 MB por versão guardada em `historico/`; o `dashboard.html`
gerado tem ~18 MB, dos quais quase tudo é o dataset embutido. **Nenhum deles está no
`.gitignore`** — versionar ou não é decisão do projeto. Para um painel mais leve, os
cortes ficam em `pipeline.py`: `ITENS_POR_MUNICIPIO_ANO` (itens embutidos por
município-ano) e, em `tcees.py`, `MAIORES_POR_ACAO` e `MAIORES_CREDORES`.
