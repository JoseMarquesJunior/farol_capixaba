# Prompt — Dashboard de evidências da fiscalização "Financiamento do CNCA" (TCE-ES)

> Salve este arquivo no repositório (ex.: `docs/prompt-dashboard-evidencias-cnca.md`), junto com a matriz de planejamento e o questionário em `docs/fiscalizacao-cnca/`. No Claude Code, peça: *"Leia docs/prompt-dashboard-evidencias-cnca.md e execute fase por fase, parando ao fim de cada fase para eu revisar."*

---

## 1. Contexto e objetivo

Estou em uma fiscalização de acompanhamento do TCE-ES sobre o **financiamento do Compromisso Nacional Criança Alfabetizada (CNCA)** nos 78 municípios do Espírito Santo. Temos:

- uma **matriz de planejamento** com 6 questões de auditoria (Q1–Q6) e os possíveis achados de cada uma;
- um **questionário** (Microsoft Forms, 49 perguntas) enviado aos responsáveis pela educação municipal.

Crie uma **nova página/dashboard**, separada das já existentes no projeto, cujo objetivo é **responder às questões da matriz e às perguntas do questionário com dados e evidências de bases públicas ou do próprio TCE-ES, de forma independente das respostas dos municípios**. As respostas ao questionário ainda não estão disponíveis e **não fazem parte deste escopo**: o questionário serve aqui apenas como roteiro das perguntas a serem respondidas com dados.

Princípios obrigatórios:

- **Fato ≠ indício ≠ inferência.** Toda evidência precisa dizer se é medida direta, proxy ou inferência, e qual o grau de confiança. Nunca transformar proxy em achado.
- **Proveniência por registro.** Cada número carrega fonte, endpoint/arquivo, parâmetros, data de extração e hash do arquivo bruto. O dashboard é papel de trabalho, não vitrine.
- **Lacunas explícitas.** Se uma pergunta não pode ser respondida por dados, o dashboard diz isso, diz por quê e diz qual o caminho alternativo (questionário, ofício, análise documental). Nunca preencher com zero ou estimativa silenciosa.
- **Não inventar códigos, endpoints ou colunas.** Tudo o que está marcado como "verificar" abaixo deve ser confirmado na Fase 0 antes de ser usado.

---

## 2. Insumos da fiscalização

### 2.1 Matriz de planejamento (questões de auditoria e possíveis achados)

| Questão | Enunciado resumido | Possíveis achados |
|---|---|---|
| **Q1** | Governança municipal do CNCA formalmente estruturada (responsáveis, atribuições, articulação, comunicação, supervisão) | A1.1 sem responsável designado por ato formal · A1.2 atribuições não definidas · A1.3 sem Articulador Municipal / Renalfa · A1.4 sem atribuições formais dos articuladores · A1.5 acúmulo de funções · A1.6 sem canais de comunicação com Renalfa · A1.7 sem rotinas de implementação e supervisão |
| **Q2** | Planejamento dos recursos baseado nas necessidades da rede e alinhado às diretrizes pedagógicas | A2.1 desconhecimento dos recursos necessários · A2.2 sem mapeamento de necessidades (infraestrutura, materiais, turmas) · A2.3 sem Plano de Ações do CNCA · A2.4 plano desalinhado das diretrizes |
| **Q3** | Planejamento e disponibilidade dos recursos financeiros conforme necessidades, instrumentos de planejamento e cronograma | A3.1 ausência/inadequação do CNCA no PPA, LOA e QDD |
| **Q4** | Execução regular, tempestiva, compatível com a finalidade e articulada ao cronograma pedagógico | A4.1 baixa execução · A4.2 dessincronia entre liberação financeira e cronograma pedagógico · A4.3 despesas incompatíveis com as regras do CNCA · A4.4 concentração da execução no fim do ciclo · A4.5 sem conciliação bancária mensal / sem controle de rendimentos |
| **Q5** | Monitoramento da execução financeira e dos resultados pedagógicos | A5.1 sem indicadores formais · A5.2 indicadores não usados na decisão · A5.3 sem fóruns de análise crítica · A5.4 sem integração execução financeira × resultado pedagógico · A5.5 sem medidas corretivas |
| **Q6** | Suficiência dos recursos disponíveis e executados para os resultados de alfabetização | A6.1 desconhecimento dos recursos necessários *(o arquivo da matriz termina aqui; a lista de achados de Q6 pode estar incompleta — deixe a estrutura aberta para eu completar)* |

### 2.2 Questionário (blocos)

- **Bloco 1 — Identificação (P1–P6):** município, respondente, cargo, e-mail, tempo na função, setores que responderam. *Contém dados pessoais.*
- **Bloco 2 — Governança e planejamento (P7–P17):** plano municipal do CNCA; coordenador designado (P8–P11); estágio de implementação (P12); articulador municipal, cargo e exclusividade (P13–P15); apoio da Renalfa (P16); ações do PATe/PAR com dotação no PPA/LDO/LOA (P17).
- **Bloco 3 — Financiamento (P18–P34):** fontes recebidas (PAR, PDDE Cantinho da Leitura/material, bolsas Renalfa, formação continuada, recursos estaduais em regime de colaboração, recursos próprios) (P18); complementação com recurso próprio e motivo (P19–P20); % de escolas com PDDE ligado ao CNCA (P21); segregação dos recursos (P22); periodicidade de acompanhamento (P23); indicadores de execução usados (P24); restos a pagar processados antigos e ligados ao CNCA (P25–P26); capacidade de estimar recursos necessários (P27); incorporação ao orçamento (P28); valores orçados e executados 2023–2026 (P29–P32); sistema que isola despesas do 1º e 2º ano (P33); controle das bolsas Renalfa (P34).
- **Bloco 4 — Monitoramento (P35–P43):** estágio das ações em 2026 e causas de atraso (P35–P36); três principais obstáculos (P37); ações em risco (P38); cruzamento gasto × resultado de alfabetização (P39); percepção sobre a Renalfa (P40); inventário/tombamento de materiais e cantinhos (P41); dotação para premiação de boas práticas, art. 12 do Decreto 11.556/2023 (P42); canais de divulgação (P43).
- **Bloco 5 — Riscos e oportunidades (P44–P49):** risco de descontinuidade e justificativa (P44–P45); uso do AVAMEC (P46); contratação de consultorias de formação e valor (P47–P48); campo aberto (P49).

---

## 3. Fontes de dados (o que já foi verificado e o que falta verificar)

### 3.1 Reaproveitar o que já existe no projeto
Antes de qualquer coisa, **inventarie o repositório**: pipelines já construídos (SICONFI, Censo Escolar/Base dos Dados, IBGE SIDRA, FNDE CKAN, ICA/CNCA, design tokens do Painel de Controle). Reaproveite módulos, cache e tokens visuais; não duplique.

### 3.2 Dados do próprio TCE-ES (fonte mais rica — prioridade)

| Fonte | O que traz | Status |
|---|---|---|
| **dados.es.gov.br (CKAN), conjuntos do TCE-ES** vindos do CidadES: `tcees-empenho` (2020–2026, com dicionário), `despesas-municipios` (2013–2026), `receitas-municipios`, `tcees-contratacoes` (2022–2026: contratações, instrumentos, itens, atas), `obrigacoes`, `tcees-despesas-com-saude-educacao-e-pessoal-...` | Empenhos por município com fonte de recursos, histórico, credor; contratos | Confirmado que existem. **Verificar colunas no dicionário** (especialmente fonte, complemento de fonte, ação, subfunção, elemento, histórico, datas de empenho/liquidação/pagamento) |
| **CidadES – PCM (IN 68/2020, leiautes em tcees.tc.br/cidades/orientacoes/)** | `PPA`, `PPAPROG`, `LDO`, `LOA`, `LOAPROG`, `PRATIVOE` (ações), `BALANCORR` (balancete por conta-corrente com fonte/destinação), `CONCIBAN` (conciliação bancária mensal, obrigatória desde 2025), `HISTEMPENHO`, `CDDR`, remessa de contratação | Acesso interno. Tornar a camada de dados **plugável**: usar dados.es.gov.br por padrão e, se eu fornecer extrações internas do CidadES, usá-las no lugar. **Confirmar os nomes dos arquivos no leiaute original** |
| **Tabela de Fontes de Recursos e Complemento das Fontes do TCE-ES** (xlsx anual, ex. 2025: `tcees.tc.br/wp-content/uploads/formidable/181/TABELA-DE-FONTES-DE-RECURSOS-E-COMPLEMENTO-DAS-FONTES-_2025.xlsx`; há versão 2026 e Portaria 49/2026) | Detalhamento de fonte exigido pelo TCE-ES | **Verificar se existe complemento específico para CNCA, PAR ou alfabetização.** Isso decide se a execução do CNCA é rastreável com precisão ou só por aproximação |

### 3.3 Fontes federais

| Fonte | Uso | Status verificado |
|---|---|---|
| **Ações orçamentárias federais do CNCA** (Nota Técnica Conjunta nº 4/2024/SEB/MEC): **0509** Apoio ao Desenvolvimento da Educação Básica (PAR e TEDs); **0515** Dinheiro Direto na Escola (PDDE, Cantinhos da Leitura); **00O0** Concessão de Bolsas de Apoio à Educação Básica (bolsas Renalfa) | Filtrar repasses federais ligados ao CNCA | Confirmado **apenas para 2023**. **Verificar as ações de 2024–2026** e se há plano orçamentário (PO) próprio do CNCA. Atenção: essas ações não são exclusivas do CNCA — repasse nelas é *proxy*, não prova |
| **Portal da Transparência** | Repasses a municípios por ação | A API (`/api-de-dados/despesas/recursos-recebidos`, token no header `chave-api-dados`) filtra por município mas **não por ação**. Usar o **download mensal de transferências** (`portaldatransparencia.gov.br/download-de-dados/transferencias`), que tem função/programa/ação/favorecido, e filtrar localmente. **Confirmar colunas do arquivo** |
| **FNDE – Liberações (SIMAD/SIGEF)** `fnde.gov.br/pls/simad/internet_fnde.liberacoes_result_pc` | Datas e valores de repasse por programa/município | Consulta HTML, sem exportação confirmada; o firewall do FNDE bloqueia automação agressiva. Scraping gentil (rate limit, cache) ou download manual com hash registrado |
| **PDDE Info** `fnde.gov.br/pddeinfo/` | Por escola/UEx: repasses, **saldo em conta**, situação da prestação de contas; filtro por programa (há "PDDE QUALIDADE"; "Cantinho da Leitura" não aparece como opção própria) | Público; exportação não confirmada. Cantinho da Leitura: Resolução CD/FNDE nº 22/2023, R$ 1.235 por sala |
| **SiGPC Acesso Público** `fnde.gov.br/sigpcadm/sistema.pu?operation=localizar` e dataset `situacao-opc-pdde` (dados.gov.br) | Situação de prestação de contas por programa/município | Público, sem API validada |
| **Fontes STN (Portaria 710/2021, atualizada até Portaria 1.701/2025)** | Rastrear execução municipal por fonte | **551** PDDE · **569** Outras transferências do FNDE (provável para PAR — é inferência, confirmar) · **550** salário-educação · **552** PNAE · **553** PNATE · 570–576 convênios da educação. Prefixo 1 = exercício corrente, 2 = anteriores. CO 1001 (MDE), 1070 (FUNDEB 70%). **Não existe fonte nem CO específico do CNCA** |
| **ICA — Indicador Criança Alfabetizada (INEP)** | Resultado de alfabetização por município (meta oficial do CNCA) | Reaproveitar o módulo já existente ou o pipeline do repositório `luizmaibashi/painel-alfabetizacao-cgu` (MIT, com verificação SHA-256) |
| **Censo Escolar (INEP)** | Matrículas e turmas de 1º e 2º ano da rede municipal; nº de escolas com anos iniciais; salas, biblioteca/sala de leitura | Já no projeto |
| **SICONFI** | MSC orçamentária por fonte e subfunção (361 Ensino Fundamental), RREO | Já no projeto |
| **PNCP** — API `https://pncp.gov.br/api/consulta`, `GET /v1/contratos` (obrigatórios `dataInicial`, `dataFinal` AAAAMMDD, `pagina`; filtro por `cnpjOrgao`; sem filtro por município; `tamanhoPagina` 10–500; usar janelas de ~1 mês) | Contratos de consultoria/formação em alfabetização | Confirmado. Busca textual só no endpoint não documentado `/api/search/` (usar apenas para triagem). **Cobertura incompleta**: municípios até 20 mil habitantes têm até abr/2027 para aderir — complementar com `tcees-contratacoes` |
| **Querido Diário** — `https://api.queridodiario.ok.org.br/gazettes` (`territory_ids`, `querystring`, `published_since`…) | Portarias de designação, leis/decretos de política de alfabetização | Cobre **só Vitória, Vila Velha e Serra** no ES |
| **DOM-ES (AMUNES/DIO-ES)** `ioes.dio.es.gov.br/dom` | Idem, para os demais municípios | Busca por palavra e data, **sem API**. Avaliar scraping respeitoso; se inviável, gerar lista de buscas para execução manual assistida |
| **Governo do ES** — dados.es.gov.br (SEFAZ): despesas SIGEFES 2004–2026, convênios 2009–2026; PAES/FUNPAES (Lei 11.790/2023, Decreto 5.369-R/2023) e bolsas estaduais (Lei 12.116/2024) | Recursos estaduais em regime de colaboração (P18) | Sem dataset específico do PAES. Hipótese a testar: filtrar despesas estaduais pela UG SEDU/FUNPAES e modalidade de transferência a municípios |

### 3.4 Sem dado público identificado (vai para questionário, ofício ou análise documental)
Bolsas Renalfa por município/bolsista (pagas pelo SGB/FNDE; não achamos base pública); termos do PAR 4 do CNCA no SIMEC (sem consulta pública); lista de municípios com Selo Nacional Compromisso com a Alfabetização (SIMEC com login); uso do AVAMEC por município; apoio técnico da Renalfa; percepções e causas (P12, P16, P35–P40, P44–P45).

---

## 4. Mapeamento pergunta → evidência (implemente como configuração, não como código fixo)

Crie `config/matriz_cnca.yaml` com esta estrutura para cada achado: `id`, `questao_matriz`, `perguntas_questionario`, `indicadores` (fórmula, fonte, nível), `tipo_evidencia` (direta / proxy / documental / indisponível), `regra_classificacao` (limiares **parametrizáveis**, marcados "a calibrar com a equipe"), `ressalvas`. Assim a equipe ajusta limiares sem mexer no código.

Ponto de partida do mapeamento:

| Achado | Perguntas | Evidência automatizável | Fonte | Tipo |
|---|---|---|---|---|
| A1.1, A1.2 | P8–P11 | Portaria/ato de designação do coordenador do CNCA publicado | Querido Diário (3 municípios), DOM-ES | Documental (busca automatizada; ausência de resultado ≠ ausência de ato) |
| A1.3–A1.5 | P13–P15 | Ato de designação do articulador; acúmulo de funções | DOM-ES; bolsas Renalfa **indisponíveis** | Documental / indisponível |
| A1.6, A1.7 | P16 | — | — | Indisponível (questionário) |
| A2.2 | P7, P21, P27 | Turmas e matrículas de 1º–2º ano; escolas com biblioteca/sala de leitura; salas de aula de anos iniciais × valor do Cantinho da Leitura (R$ 1.235/sala) → **valor de referência estimado** | Censo Escolar; Resolução FNDE 22/2023 | Proxy (estimativa, rotular como tal) |
| A2.3 | P7 | Lei/decreto de Política Municipal de Alfabetização ou plano do CNCA publicado | Diários oficiais | Documental |
| A3.1 | P17, P28 | Ação/programa com "alfabetiz" ou "CNCA" no PPA/LOA/QDD; dotação em fonte 551/569 (+ complemento TCE-ES) em subfunção 361 | CidadES (`PPA`, `LOA`, `LOAPROG`, `PRATIVOE`); `tcees-empenho` | Direta (se houver complemento específico) / proxy |
| A4.1 | P29–P32 | Executado ÷ recebido por ano (recebido: transferências federais nas ações do CNCA; executado: empenhos/pagamentos nas fontes correspondentes) | Portal da Transparência; `tcees-empenho` | Proxy |
| A4.2 | — | Defasagem (dias) entre data do repasse e primeiro empenho/pagamento na fonte correspondente | FNDE Liberações; `tcees-empenho` | Proxy |
| A4.3 | — | Empenhos nas fontes 551/569 com elemento de despesa ou histórico incompatível (ex.: pessoal, obras sem vínculo) — classificação por regras + palavras-chave, sempre para **revisão humana** | `tcees-empenho` | Indício (nunca achado automático) |
| A4.4 | — | % da execução anual concentrada em nov–dez; perfil mensal | `tcees-empenho` / MSC | Direta (sobre a fonte, não só CNCA) |
| A4.5 | P22 | Existência de conta específica e conciliação mensal na fonte; rendimentos | CidadES `CONCIBAN`, `BALANCORR` | Direta (interno) |
| — (P21) | P21 | % das escolas municipais com anos iniciais que receberam PDDE Qualidade/Cantinho | PDDE Info + Censo Escolar | Direta, se o programa for identificável |
| — (PDDE parado) | P41 | Saldo em conta por escola e tempo parado; situação da prestação de contas | PDDE Info; SiGPC | Direta |
| — (RP) | P25, P26 | Restos a pagar processados nas fontes 551/569, com idade | `tcees-empenho` / CidadES | Direta (sobre a fonte) |
| — (índices) | P24 | Calcular os quatro índices do questionário (empenhado/dotação, pago/dotação, liquidado/empenhado, pago/liquidado) por município e ano | CidadES / `tcees-empenho` | Direta |
| — (1º–2º ano) | P33 | Existência de ação/complemento que isole a alfabetização; se não existir, registrar que a despesa não é separável | CidadES | Direta |
| A5.4, A6.x | P39, P44 | Recurso do CNCA por aluno de 1º–2º ano × ICA e sua variação; **correlação descritiva, sem leitura causal** | Censo, ICA, execução | Inferência |
| A6.x | P19, P20 | Despesa com recursos próprios (fontes 500/540, CO 1001) na subfunção 361 vs. transferências FNDE | `tcees-empenho`, MSC | Proxy |
| — (consultorias) | P47, P48 | Contratos com objeto "formação continuada", "alfabetização", "assessoria pedagógica", "material estruturado/apostilado"; valor | `tcees-contratacoes`, PNCP, históricos de empenho | Direta (classificação por palavras-chave revisável) |
| — (estado) | P18 | Transferências SEDU/FUNPAES a cada município | dados.es.gov.br (SIGEFES) | Proxy |
| — (premiação) | P42 | Dotação/ação de premiação em LOA; Selo **indisponível** publicamente | CidadES | Direta / indisponível |

Complete o YAML com todas as 49 perguntas (mesmo as de identificação ou indisponíveis), para que o painel de cobertura seja completo.

---

## 5. Classificação das evidências

Tabela de evidências em formato longo: `municipio_ibge`, `municipio`, `questao_matriz`, `achado_id`, `pergunta_questionario`, `indicador`, `valor`, `unidade`, `ano`, `status`, `tipo_evidencia`, `confianca` (alta/média/baixa), `fonte`, `endpoint_ou_arquivo`, `parametros`, `data_extracao`, `hash_bruto`, `nota`.

Status possíveis por município × achado:

- **Indício de risco** — os dados apontam na direção do possível achado;
- **Sem indício** — os dados apontam no sentido contrário;
- **Inconclusivo** — há dado, mas o proxy é fraco ou há conflito entre fontes;
- **Sem dado público** — depende de questionário, ofício ou documento.

Nenhuma regra gera "achado" — só indício. A linguagem na interface deve refletir isso.

---

## 6. Dashboard (nova página, com a identidade visual já extraída do Painel de Controle)

1. **Visão da matriz:** as 6 questões, cada achado com a distribuição dos 78 municípios por status; clique abre os municípios.
2. **Mapa de calor município × achado:** 78 linhas × achados, cor por status, ícone por tipo de evidência; filtros por região/porte.
3. **Ficha do município:** todas as evidências com fonte; linha do tempo repasse × empenho × pagamento; perfil mensal de execução; escolas com saldo PDDE parado; ICA e tendência; contratos de formação.
4. **Visão por pergunta do questionário (P1–P49):** o que os dados já respondem, resposta baseada em evidência com ressalva, e cobertura.
5. **Painel de cobertura:** quantas perguntas/achados são respondíveis por dados, por proxy ou só por questionário — útil para a seção de metodologia do relatório.
6. **Exportação de papel de trabalho:** CSV/XLSX por município e por achado, com todas as colunas de proveniência.

Tabelas sempre visíveis por trás dos gráficos. Botão "ver fonte" em cada número.

---

## 7. Arquitetura e padrões

- Python com type hints, docstrings, pandas; um módulo por fonte (`sources/tcees.py`, `sources/transparencia.py`, `sources/fnde.py`, `sources/pncp.py`, `sources/diarios.py`, …), cada um isolado: falha de uma fonte vira aviso, não derruba o pipeline.
- Camadas: `data/raw/` (imutável, com timestamp e SHA-256), `data/staging/`, `data/evidence/` (tabela longa da seção 5).
- Scraping (FNDE, DOM-ES): respeitar robots.txt, rate limit, cache; se bloqueado, registrar e oferecer caminho de download manual com hash.
- Tokens de API (Portal da Transparência) via variável de ambiente, nunca no código.
- Testes: códigos IBGE de 7 dígitos e 78 municípios; somas por fonte batem com totais; nenhum município some entre camadas; classificação reproduzível (mesma entrada → mesma saída).
- Dados pessoais (ex.: nomes em atos de designação, credores pessoa física): nunca exibir além do necessário; preferir agregados, conforme a LGPD e a Resolução TC 358/2021.

---

## 8. Execução em fases (pare ao fim de cada uma)

- **Fase 0 — Reconhecimento (delegar ao subagente `api-explorer`, se existir em `.claude/agents/`):** inventariar o repositório; confirmar colunas dos dicionários de `tcees-empenho` e `tcees-contratacoes`; baixar e ler a Tabela de Fontes e Complementos do TCE-ES 2025/2026 e procurar complemento de CNCA/PAR/alfabetização; confirmar as ações orçamentárias do CNCA em 2024–2026; testar download de transferências do Portal da Transparência e identificar colunas de ação; testar PDDE Info, Liberações FNDE, PNCP, Querido Diário e DOM-ES. **Entregar um relatório `docs/fase0_reconhecimento.md`** dizendo o que funciona, o que não funciona e como isso muda o mapeamento da seção 4.
- **Fase 1 — Execução financeira:** A3.1, A4.1–A4.5, P21, P24–P26, P29–P33.
- **Fase 2 — Necessidades e resultados:** Censo, ICA, custo por aluno, A2.2, A5.4, A6.x.
- **Fase 3 — Documental e contratos:** diários oficiais (A1.x, A2.3), consultorias (P47–P48), recursos estaduais (P18).
- **Fase 4 — Dashboard** (seção 6).

---

## 9. Entregáveis e critérios de aceite

1. `config/matriz_cnca.yaml` completo (6 questões, achados, 49 perguntas).
2. Pipelines por fonte, com cache, hashes e testes.
3. `data/evidence/evidencias_cnca.parquet` (e CSV) no formato da seção 5.
4. Nova página do dashboard com as 6 visões.
5. `docs/fase0_reconhecimento.md` e `README` com: fontes, limitações por achado, o que depende de questionário/ofício, e como reexecutar.
6. Lista sugerida de **ofícios/requisições** para as lacunas (FNDE/SGB para bolsas Renalfa; MEC/SIMEC para termos do PAR 4 e Selo; SEDU-ES para PAES/PATe).

Aceite: para qualquer célula do mapa de calor, eu consigo chegar ao registro bruto que a originou.
