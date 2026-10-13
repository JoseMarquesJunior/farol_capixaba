# Fase 0 — reconhecimento das fontes para o painel de evidências do CNCA

Levantamento de **23/09/2026** para o painel descrito em
[`prompt-dashboard-evidencias-cnca.md`](prompt-dashboard-evidencias-cnca.md): responder às
questões Q1–Q6 da matriz de planejamento e às 49 perguntas do questionário com dado público
ou do próprio TCE-ES, **sem depender das respostas dos municípios**.

Três frentes foram delegadas ao subagente `api-explorer` (TCE-ES e Estado; federal; documental
e contratos). **Todo achado que decide o mapeamento foi depois conferido diretamente na fonte
ou nos dados**, e parte das conclusões dos relatórios mudou nessa conferência — está anotado
caso a caso abaixo. Os números aqui foram medidos, não presumidos.

> **O que este relatório conclui em uma frase:** o CNCA **não é identificável** na
> contabilidade municipal do ES — não há fonte, complemento de fonte, programa ou ação que o
> nomeie —, de modo que as questões de execução financeira (Q3 e Q4) só podem ser respondidas
> por **proxy declaradamente fraco**, enquanto o lado do **repasse** (federal e estadual) é
> rastreável com precisão. Isso desloca o centro de gravidade do painel.

---

## 1. O achado central: o CNCA não tem código próprio na despesa municipal

A pergunta que o prompt marcou como decisiva — *existe complemento específico para CNCA, PAR ou
alfabetização?* — tem resposta **não**, e ela se sustenta em três medições independentes.

### 1.1 Na tabela oficial de fontes do TCE-ES

`TABELA-DE-FONTES-DE-RECURSOS-E-COMPLEMENTO-DAS-FONTES-_2025.xlsx` (HTTP 200, 44.772 bytes,
baixada e lida aqui). Três abas: `GRUPO DE FONTE_DEST_RECURSOS` (13 linhas),
`FONTES DE RECURSOS 2025` (147 linhas) e `COMPLEM FONTES 2025 (MARCADOR)` (54 linhas).

Busca sem distinção de maiúsculas ou acentos nas três abas inteiras:

| Termo | Ocorrências |
|---|---|
| CNCA, CRIANÇA ALFABETIZADA, ALFABETIZ | **0** |
| PLANO DE AÇÕES ARTICULADAS | **0** |
| PAES, FUNPAES, RENALFA, CANTINHO | **0** |
| PDDE | **1** — a fonte 551, e só ela |

A tabela de **complementos** tem 54 linhas e nenhuma é de programa federal: são MDE (`1001`),
ASPS (`1002`), FUNDEB 70% (`1070`), postergação de dívida (`1010`), benefícios previdenciários
(`1111`–`2211`), emendas parlamentares (`3101`–`3221`, `EPIS`/`EPIE`/`EPIO`/`EPBS`/`EPBE`/`EPBO`),
compensação de precatórios (`5001`) e o genérico **`AAAA` — "Complemento de Fonte/Destinação de
Recursos Genérico… a ser utilizado quando não for aplicável a utilização dos demais
complementos"**.

As fontes da educação que existem, com a descrição oficial:

| Fonte | Nome |
|---|---|
| 500-0025 | Receita de impostos e de transferência de impostos — MDE |
| 540-0070 / 540-0030 | Transferências do FUNDEB — 70% / 30% |
| 550 | Transferência do salário-educação |
| **551** | Transferências do FNDE referentes ao **PDDE** |
| 552 / 553 | FNDE — PNAE / PNATE |
| **569** | **Outras transferências de recursos do FNDE** |
| 570 / 571 / 572 | Convênios vinculados à educação — União / Estado / municípios |
| 573 | Royalties vinculados à educação (Lei 12.858/2013) |
| 574 | Operações de crédito vinculadas à educação |
| 575 | Outras transferências de convênios vinculados à educação |
| **576** | **Transferências de recursos dos Estados para programas de educação** |
| 599 | Outros recursos vinculados à educação |

> *Correção ao relatório do subagente:* ele leu a segunda coluna da aba de fontes ("0000",
> "0025", "0070") como se fosse o complemento da fonte e concluiu, por exemplo, que a fonte 500
> usa complemento `0025`. Não é: `0025` é o desdobramento da própria fonte (500-0025 = MDE),
> e a aba de complementos é outra, transcrita acima. A resposta final — não há código de CNCA —
> coincide, mas por caminho diferente.

### 1.2 Nos 2,6 milhões de empenhos da educação

Varredura de **2.622.030 linhas** da função 12, os 78 municípios, 2021–2025, direto no cache do
projeto (`dados/bruto/tcees/empenhos/`, que guarda as 58 colunas originais do recorte).

Buscando `ALFABETIZ|CRIANÇA ALFAB|CNCA|RENALFA|CANTINHO` em nome de programa, de ação e de
detalhamento da fonte: **uma única combinação, em um único município** — Vila Velha, programa
"GESTÃO DE PROGRAMAS PEDAGÓGICOS", ação "EDUCAÇÃO DE JOVENS E ADULTOS – EJA E PRO…", 4 linhas.
É EJA, não CNCA.

Isso confirma e amplia o que o levantamento anterior tinha visto numa amostra de 2024
([`mapeamento_dados_tcees.md` §4.2](mapeamento_dados_tcees.md)): agora são cinco exercícios
inteiros, não quatro meses.

### 1.3 Na fonte 551 (PDDE), que quase não existe no orçamento municipal

| Ano | Fonte 551 — municípios / valor | Fonte 569 — municípios / valor |
|---|---|---|
| 2021 | 0 / R$ 0 | 0 / R$ 0 |
| 2022 | 0 / R$ 0 | 0 / R$ 0 |
| 2023 | 31 / **R$ 0,41 mi** | 60 / R$ 9,44 mi |
| 2024 | 35 / **R$ 0,34 mi** | 63 / R$ 27,05 mi |
| 2025 | 25 / **R$ 0,56 mi** | 65 / R$ 45,95 mi |

R$ 1,31 milhão de PDDE em cinco anos, nos 78 municípios somados — contra R$ 193,7 mi que a CGU
mostra pagos às unidades executoras do ES no mesmo período. **O PDDE não transita pelo orçamento
municipal**: vai direto ao conselho escolar, que presta contas ao FNDE. Medir execução do
PDDE-CNCA pela fonte 551 mediria ~0,7% do dinheiro.

As duas fontes só aparecem **a partir de 2023** — antes disso o ES usava codificação local, o que
é coerente com o que o projeto já registrou sobre a MSC (padrão STN nos municípios do ES desde
2022, com 2021 em códigos de 8 dígitos).

---

## 2. O que muda no mapeamento da seção 4 do prompt

| Achado / pergunta | Como o prompt previa | O que o reconhecimento mostrou | Tipo de evidência agora |
|---|---|---|---|
| **A3.1** (CNCA no PPA/LOA/QDD) | dotação em fonte 551/569 + complemento específico, subfunção 361 | não há complemento de CNCA; 551 é irrelevante; resta 569 (que mistura PAR com todo o resto do FNDE) e busca textual no nome da ação | **proxy fraco** — e o painel precisa dizer que a ausência não prova ausência de dotação |
| **A4.1** (baixa execução) | executado ÷ recebido nas fontes correspondentes | o "recebido" (CGU) é preciso; o "executado" não é isolável para o CNCA | **proxy** sobre a fonte 569, nunca sobre o CNCA |
| **A4.2** (dessincronia repasse × empenho) | defasagem em dias entre repasse e primeiro empenho | `DataEmissao` **não existe** nos arquivos de 2021–2023; existe e vem preenchida em 100% de 2024 e 2025 | **proxy, só 2024–2025** |
| **A4.3** (despesa incompatível) | elemento **ou histórico** do empenho | **o empenho do TCE-ES não tem campo de histórico** (confirmado no dicionário oficial do dataset) | só por elemento e nome da ação — **indício fraco**, revisão humana obrigatória |
| **A4.4** (concentração no fim do ciclo) | % da execução em nov–dez | medível para os 78 municípios em todos os anos, na subfunção 361 | **direta** (sobre a subfunção, não sobre o CNCA) |
| **P25, P26** (restos a pagar) | RP processados nas fontes 551/569, com idade | as colunas de RP existem em todos os anos, mas **`RPPTransferido` vem sempre vazia**: a idade sai do `AnoEmpenho`, e o dinheiro está em linhas de exercícios anteriores (ver Fase 1 §2) | **direta** (sobre a fonte) |
| **P24** (quatro índices) | empenhado/dotação, pago/dotação… | a dotação está em `despesas-municipios` (`PrevisaoInicial`, `PrevisaoAtualizada`), que **não traz o complemento de fonte** | **direta** por fonte e ação; não por CNCA |
| **P18** (recursos estaduais) | filtrar SIGEFES pela UG SEDU/FUNPAES — *hipótese a testar* | **hipótese confirmada, e melhor do que se esperava** (§4) | **quase direta**, município a município |
| **A1.1–A1.5** (atos de designação) | Querido Diário + DOM-ES | Querido Diário cobre **3 dos 78**; DOM-ES exige navegador headless (§5) | **documental de cobertura baixa** |
| **Bolsas Renalfa** | ação federal 00O0 | não aparece nas transferências da CGU no ES | **indisponível**, como já se supunha |

Duas consequências de método:

1. **O painel não pode ter uma coluna "execução do CNCA" por município.** O que ele pode ter é
   "execução na fonte 569", "execução na subfunção 361" e "repasse recebido", cada uma com o
   rótulo do que de fato mede. Transformar qualquer uma delas em "achado de baixa execução do
   CNCA" seria exatamente o que o princípio *fato ≠ indício ≠ inferência* proíbe.
2. **O centro de gravidade se desloca do gasto para o repasse.** O que é rastreável com
   precisão é o dinheiro que *chega*: PDDE-CNCA por escola (CGU), repasse ao Estado (CGU) e
   transferência do Estado ao município (SIGEFES). O que é opaco é o que o município *faz* com
   ele. Isso é, em si, um achado de auditoria — e deve aparecer no painel como tal, não como
   lacuna técnica.

---

## 3. O que o dado do TCE-ES traz de fato

Dicionário oficial do dataset `tcees-empenho` (recurso "Dicionário de dados", CSV de 6.147 bytes,
baixado e lido): **58 campos**. Os que o prompt supunha e não existem, e os que existem e o
prompt não previa:

| Campo | Situação |
|---|---|
| `Historico` / descrição do empenho | **não existe** — nem no dicionário, nem no arquivo |
| Número do contrato no empenho | **não existe** (já registrado no levantamento anterior) |
| `CodigoComplementoFontesDestinacoesRecursos` | existe, mas **só nos arquivos de 2024 em diante**; em 2021–2023 a coluna não está no leiaute |
| `DataEmissao`, `AnoCompetencia` | idem — só 2024+ |
| `CodigoGrupoFonte` / `NomeGrupoFonte` | existe: separa exercício corrente de exercícios anteriores |
| 13 colunas de restos a pagar | declaradas: `RPNPExercicio`, `RPPExercicio`, `RPNPTransferido`, `RPPTransferido`, `RPNPBloqueado`, `RPNPLiquidado`, `RPNPPago`, `RPPPago`, `RPNPCancelado`, `RPPCancelado`, `RPNPRecebido`, `RPNPRestabelecido`, `RPPRecebido`. **Sete delas vêm sempre vazias** — ver Fase 1 §2, que mede quais e mostra onde o dinheiro do RP realmente está |
| `CodigoSubElemento` / `DescricaoSubElemento` | existe — desce um nível abaixo do elemento |

Distribuição real do complemento de fonte nas 1,56 milhão de linhas de 2024–2025:

| Complemento | Linhas | O que é |
|---|---|---|
| `1001` | 626.020 | MDE |
| `AAAA` | 576.200 | **genérico** ("quando não for aplicável nenhum dos demais") |
| `1070` | 356.264 | FUNDEB 70% |
| `1111`, `EPBO`, `3110`, `EPIO`, `3210`, `1002` | 1.493 | previdência, emendas |

Ou seja: fora de MDE e FUNDEB, **o complemento de fonte no ES é genérico em quase todos os
casos**. Ele não serve para identificar programa nenhum.

### `tcees-contratacoes`

Não existe recurso "Dicionário de dados" nesse dataset (diferente de `tcees-empenho`, que tem).
Os 40 campos do recurso *Contratações* foram lidos no cabeçalho do próprio arquivo. Para o painel
importam `ObjetoContratacao` (é esse o nome do campo de objeto), `SetorBeneficiado`,
`ValorTotalContratacao`, `ModalidadeLicitacao` e `NumeroIdentificacaoContratacaoPNCP` — que é a
ponte com o PNCP. **Não há campo de fonte de recursos nem de programa na contratação**: ligar um
contrato de formação em alfabetização à fonte que o pagou continua sendo cruzamento por CNPJ e
exercício, ou seja, indício.

### A4.4 já medido

Concentração em nov+dez na subfunção 361, 2024, os 78 municípios: de **−12,5%** (Vila Pavão) a
**32,3%** (São Roque do Canaã); no agregado do Estado, 12,8% (2023) a 25,0% (2021).

O valor negativo não é erro: são anulações de empenho maiores que os empenhos do período. **A
regra de classificação precisa tratar isso explicitamente**, ou o painel apontará "risco" onde há
estorno — e o limiar precisa ser calibrado contra essa distribuição real, não contra um número
redondo escolhido antes de olhar os dados.

---

## 4. O lado estadual: melhor do que a hipótese (P18)

O dataset `despesas` do Governo do ES (SIGEFES, CKAN aberto) tem **71 colunas** e um arquivo de
~1,4 GB por ano (2023, 2024, 2025). Amostra de 32.459 linhas de 2025 lida em fluxo.

Confirmado na amostra:

* existe a unidade gestora **"FUNDO EST. DE APOIO À AMP. E MELH. DAS COND. DE OFERTA DA EDUC.
  INF. E DO ENS. FUND. NO ES"** — o FUNPAES, com nome próprio de UG (72 linhas na amostra);
* existe modalidade de aplicação **40 (transferências a municípios), 41 (fundo a fundo) e 42
  (execução delegada)** — 371 linhas na amostra;
* e, o que decide a pergunta, o campo **`Favorecido` traz o fundo municipal nominalmente**:
  ex. `FUNDO MUNICIPAL DE EDUCAÇÃO INFANTIL E ENSINO FUNDAMENTAL - FMEIEF - FUNDÃO`, com
  `Programa` = "MELHORIA DA QUALIDADE DO ENSINO E DA APRENDIZAGEM NA REDE PÚBLICA COM EQUIDADE" e
  `Acao` = "COOPERAÇÃO ESTADO/MUNICÍPIOS NA IMPLEMENTAÇÃO DE POLÍTICAS DE EDUCAÇÃO".

Então **P18 é respondível município a município**: UG do FUNPAES (ou SEDU) + modalidade 40/41/42
+ favorecido casado com o município. Sobe de *proxy* para evidência quase direta — a ressalva é
o casamento por nome do favorecido, que precisa de taxa de acerto medida antes de ir ao painel,
como o projeto já faz com os conselhos escolares.

Dois extras do SIGEFES que a despesa municipal não tem: `HistoricoDocumento` (o histórico que
falta no empenho do TCE-ES — e é nele que aparecem as 10 linhas com "ALFABETIZ" da amostra) e
`CodigoPlanoOrcamentario`.

O que **não** serve: `portal-da-transparencia-transferencias-para-municipios` traz só repartição
de tributos (ICMS, IPI, IPVA, cota-parte CIDE), sem programa nem fonte; e
`convenios-com-municipios-capixabas` **para em 2020**.

---

## 5. Fontes documentais: a cobertura é o limite, não a técnica

### Querido Diário — 3 dos 78 municípios

Medido hoje na API (`queridodiario.ok.org.br/api`, sem token, responde bem a `requests`):

* `/cities` lista os **78** municípios do ES, mas isso é o cadastro do IBGE, não cobertura;
* **10** têm `publication_urls` (Aracruz, Cachoeiro, Cariacica, Colatina, Guarapari, Linhares,
  São Mateus, Serra, Vila Velha, Vitória);
* **3** têm diário efetivamente coletado (`availability_date` e `level=3`): **Vila Velha** (desde
  2022-07-19, 634 edições desde 2023), **Serra** (2022-10-03, 904) e **Vitória** (2025-01-13,
  1.677).

> **Nota da Fase 3:** o serviço é intermitente. Na coleta de 23/09/2026 as mesmas rotas
> responderam 200 e, minutos depois, **503 nos dois endereços**. O módulo tenta
> `queridodiario.ok.org.br/api` e `api.queridodiario.org.br`, com espera entre tentativas, e
> registra "cobertura não medida" quando nenhum responde — que é diferente de "não tem diário".

E, mesmo nesses três, a busca por `"Compromisso Nacional Criança Alfabetizada"` desde 2023 devolve
**0 edições**. "CNCA" devolve 25 — e as que inspecionei são outra coisa ("CNC – Centro Náutico",
critérios de pontuação de edital). "alfabetização" devolve 238 e "articulador", 866, os dois com
muito ruído.

**Conclusão para A1.1–A1.5 e A2.3:** a busca automatizada em diário oficial cobre **3,8% do
universo** e, nesse recorte, não encontra o termo do programa. A ausência de resultado não é
evidência de ausência de ato — e o painel tem de dizer isso em cada célula, não em nota de rodapé.

> *Correção ao relatório do subagente:* ele reportou o Querido Diário como inacessível
> (`SEC_E_ILLEGAL_MESSAGE` no handshake). Era o `curl` com schannel do Windows; com `requests`
> a API respondeu HTTP 200 em todas as chamadas. O mesmo vale para o PNCP (§6).

### DOM-ES / DIO-ES — viável só com navegador

`ioes.dio.es.gov.br` **não serve `robots.txt`** (404 em HTML). A página é uma SPA AngularJS: a
busca é montada no cliente, o HTML servido não traz resultado, e o endpoint do backend (que pelos
nomes de campo — `hits.total`, `_source`, `highlight` — parece Elasticsearch) não aparece em
string estática. POST em `/buscanova/` devolve a mesma casca. Sem CAPTCHA observado e sem exigir
sessão.

> **Corrigido na Fase 3:** procurando nos scripts da página inicial (`/theme/Es/js/controllers/
> home.js`) apareceu `/apifront/portal/edicoes/ultimas_edicoes.json`, que responde 200 e devolve o
> **índice de edições** com id, data e tipo — 781 edições de 25/09/2023 a 23/09/2026. A busca
> textual continua sem endpoint exposto, mas o índice torna a varredura planejável. Ver
> [`fase3_documental_contratos.md`](fase3_documental_contratos.md) §3.

Viável, então, **só com navegador headless** — e o projeto já tem Playwright instalado e em uso
em [`docs/identidade_tcees/`](identidade_tcees/relatorio.md), o que torna isso um caminho barato.
Fica para a Fase 3, com rate limit e cache, e com a alternativa de gerar a lista de buscas para
execução manual assistida, como o prompt prevê.

---

## 6. Federal: o que funciona e o que está fechado

| Fonte | Resultado do teste | Consequência |
|---|---|---|
| **CGU — transferências mensais** | funciona sem token; 36 colunas; **`CÓDIGO PLANO ORÇAMENTÁRIO` e `NOME PLANO ORÇAMENTÁRIO` são as colunas 26 e 27** (conferido também no cache local do projeto) | é a espinha dorsal do lado "recebido": PDDE-CNCA por UEx e repasse ao Estado |
| Ação **00O0** (bolsas Renalfa) | zero registros no ES em 03/2025 | as bolsas são pagas a pessoa física; **indisponível** por município → ofício |
| Ações e POs do CNCA **2024–2026** | não confirmados em documento oficial: gov.br/mec respondeu CAPTCHA, in.gov.br e fnde.gov.br/publicacoes caíram | **pendência**. Os POs `000C` (0515) e `0014` (0509) estão confirmados **empiricamente** nos arquivos da CGU até 2025; 2026 continua sem confirmação |
| **PNCP** | **funciona** — mas exige *timeout* longo: expirou em 60 s em quatro tentativas e respondeu em duas tentativas com 150 s. Março/2025: 144.107 contratos no país | usável na Fase 3 |
| PNCP — filtro geográfico | não há parâmetro de UF ou município; mas cada contrato traz `unidadeOrgao.codigoIbge` e `ufSigla` | filtro **no cliente**, mês a mês, ou por `cnpjOrgao` dos 78 municípios |
| PNCP — campos | 41 campos, entre eles `objetoContrato`, `valorGlobal`, `valorInicial`, `dataAssinatura`, `dataVigenciaInicio/Fim`, `orgaoEntidade.cnpj`, `nomeRazaoSocialFornecedor` | dá para classificar objeto por palavra-chave (P47, P48) |
| **SiGPC** | **reCAPTCHA** no HTML | fechado → ofício |
| **FNDE Liberações (SIMAD)** | rota base responde 200 sem CAPTCHA, mas com parâmetros cai em 404 no servidor Oracle interno | **não usável hoje**; a data de liberação continua vindo da CGU (mês de pagamento), não do FNDE (data da parcela) |
| **PDDE Info** | sem CAPTCHA na home; consulta é JS-pesada, sem dado no HTML estático; "Cantinho da Leitura" não aparece como programa próprio | saldo em conta e situação da prestação de contas **não confirmados** → ofício ao FNDE, como o projeto já previa |
| **dados.gov.br** (`situacao-opc-pdde`) | HTTP 401 | fechado sem token |

---

## 7. Reaproveitamento: o que já existe e não deve ser refeito

O painel de financiamento (`financiamento/`) já resolve boa parte da infraestrutura que o prompt
pede, e o novo painel deve entrar como **visão nova sobre a mesma base**, não como projeto
paralelo:

* **cache bruto com proveniência por número** — `dados/bruto/` guarda a resposta original com
  URL, instante e SHA-256; `etl/proveniencia.py` carrega isso até a linha do dataset. É
  exatamente o formato da seção 5 do prompt (`fonte`, `endpoint_ou_arquivo`, `parametros`,
  `data_extracao`, `hash_bruto`);
* **um módulo por fonte, com falha isolada** — `etl/tcees.py`, `etl/fnde.py`, `etl/siconfi.py`,
  `etl/siope.py`, `etl/ica.py`, `etl/escolas.py`, `etl/cnca.py`. A arquitetura da seção 7 do
  prompt já está implementada;
* **2,9 GB do TCE-ES já baixados e recortados**, com as 58 colunas preservadas — a Fase 1 inteira
  pode ser feita **sem uma única requisição de rede**;
* **ICA do INEP** (2023–2025 e metas 2024–2030) verificado por SHA-256, e o **Censo Escolar** no
  PostgreSQL local — Fase 2 já tem os dois lados;
* **tokens de identidade visual do Painel de Controle do TCE-ES**, cada um com a fonte de onde
  veio (`web/design-tokens.css`), e o diálogo "ver fonte" (`web/fonte.js`) — a Fase 4 herda a
  identidade e o botão de proveniência prontos;
* **a aba CNCA — Auditoria** (`web/visao_cnca.js`) já é papel de trabalho com checklist,
  anotações e exportação CSV. O painel novo deve **estender** essa aba ou substituí-la
  conscientemente, não conviver com ela sem que se saiba qual é a boa.

Um cuidado de leitura, para quem for sondar o cache à mão: os recortes em
`dados/bruto/tcees/` são gravados em **UTF-8**, ainda que os arquivos originais do TCE-ES venham
em latin-1. O ETL faz certo (`ler_recorte` usa `encoding="utf-8"`); script avulso que abrir o
recorte como latin-1 vai ver mojibake nos nomes de município — foi o que aconteceu nas primeiras
sondagens desta fase, e não é defeito do pipeline.

---

## 8. Pendências que a Fase 0 deixa em aberto

1. ~~A matriz de planejamento e o questionário não estão no repositório.~~ **Resolvido em
   23/09/2026:** `docs/fiscalizacao-cnca/` recebeu a matriz (`MATRIZ DE PLANEJAMENTO.txt`) e o
   questionário (PDF de 17 páginas do Microsoft Forms, 49 perguntas). A matriz confirma
   **23 achados** — Q1 com 7, Q2 com 4, Q3 com 1, Q4 com 5, Q5 com 5 e **Q6 com apenas 1**
   (A6.1, "falta de conhecimento sobre os recursos necessários", idêntico a A2.1). Q6 termina
   mesmo aí: a lista não estava truncada.
2. **Ações e POs do CNCA em 2026** não confirmados em documento oficial (§6).
3. **CONCIBAN e os leiautes do CidadES** (PPA, LOA, LOAPROG, PRATIVOE, BALANCORR, HISTEMPENHO,
   CDDR) não foram confirmados campo a campo: estão no Anexo IV da IN 68/2020, em PDF, alterado
   pelas Portarias 88/2025, 100/2025, 13/2026, 20/2026 e **49/2026**. O subagente relatou que o
   CONCIBAN seria obrigatório "a partir de 2026", contra o "desde 2025" do prompt — **não confiro
   nenhuma das duas versões**, porque nenhuma foi lida no leiaute. Como essa é uma fonte interna
   (§3.2 do prompt), a camada de dados deve ficar plugável e a confirmação vem com a extração.
4. **Limiares de classificação** ainda não calibrados — a Fase 1 deve propô-los a partir da
   distribuição medida (como a de nov+dez do §3), marcados "a calibrar com a equipe".

---

## 9. Ofícios que este reconhecimento já justifica

Além dos que o projeto já listava, com o motivo agora medido:

| Destinatário | O que pedir | Por que não dá para obter |
|---|---|---|
| **FNDE / SGB** | bolsas Renalfa por município e bolsista; liberações do PDDE-CNCA por UEx com data e situação da prestação de contas; saldo em conta | ação 00O0 não aparece por município na CGU; SiGPC com reCAPTCHA; SIMAD em 404; dados.gov.br em 401 |
| **MEC / SIMEC** | termos do PAR 4 do CNCA; lista do Selo Nacional Compromisso com a Alfabetização; ações e POs do CNCA em 2026 | sem consulta pública; gov.br responde CAPTCHA a acesso automatizado |
| **SEDU-ES** | adesão de cada município com data do termo; articuladores designados; repasses do FUNPAES por exercício e por município | parte disso o SIGEFES já dá (§4) — o ofício serve para **conferir** o casamento por nome, não para substituí-lo |
| **TCE-ES (interno)** | extrações do CidadES: PPA/LOA/LOAPROG/PRATIVOE (para A3.1 com dotação nomeada), CONCIBAN e BALANCORR (para A4.5) | são os únicos caminhos para A3.1 direto e A4.5, já que o dado aberto não os traz |

---

## 10. Como fica o plano das fases seguintes

* **Fase 1 — execução financeira.** Roda **inteira sobre o cache**, sem rede: A3.1 (busca textual
  na ação + fonte 569, rotulada como proxy), A4.1, A4.2 (só 2024–2025), A4.3 (elemento + ação, só
  como indício), A4.4 (direta), P24, P25, P26. A4.5 fica aguardando o CidadES.
* **Fase 2 — necessidades e resultados.** Censo (turmas e matrículas de 1º–2º ano, salas,
  biblioteca/sala de leitura), valor de referência do Cantinho da Leitura (R$ 1.235/sala,
  Resolução CD/FNDE 22/2023) e ICA, todos já no projeto.
* **Fase 3 — documental e contratos.** SIGEFES para P18 (§4), PNCP e `tcees-contratacoes` para
  P47–P48, Querido Diário nos 3 municípios e DOM-ES via Playwright para os demais.
* **Fase 4 — dashboard**, com as seis visões e o painel de cobertura — que, dado o §1, será o
  mais informativo de todos: ele é quem mostra quanto da matriz o dado público **não** alcança.

---

## Fontes consultadas nesta fase

* [Tabela de Fontes de Recursos e Complemento das Fontes — TCE-ES, 2025](https://www.tcees.tc.br/wp-content/uploads/formidable/181/TABELA-DE-FONTES-DE-RECURSOS-E-COMPLEMENTO-DAS-FONTES-_2025.xlsx)
* [Dicionário de dados do `tcees-empenho`](https://dados.es.gov.br/api/3/action/package_show?id=tcees-empenho) e [`tcees-contratacoes`](https://dados.es.gov.br/api/3/action/package_show?id=tcees-contratacoes) — CKAN aberto
* [`despesas` (SIGEFES) no dados.es.gov.br](https://dados.es.gov.br/api/3/action/package_show?id=despesas)
* [Portal da Transparência (CGU) — download de transferências](https://portaldatransparencia.gov.br/download-de-dados/transferencias)
* [PNCP — API de consulta](https://pncp.gov.br/api/consulta/swagger-ui/index.html) — `GET /v1/contratos`
* [Querido Diário — API](https://queridodiario.ok.org.br/api/cities) — `/cities`, `/gazettes`
* [DOM-ES / DIO-ES](https://ioes.dio.es.gov.br/dom)
* [TCE-ES — orientações do CidadES](https://www.tcees.tc.br/cidades/orientacoes/) (IN 68/2020, Anexo IV e portarias)
