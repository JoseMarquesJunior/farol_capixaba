# Fase 1 — execução financeira

O que a Fase 1 entrega, o que ela mediu e o que ela **não** consegue medir, para as questões Q3 e
Q4 da matriz e as perguntas P17, P21, P24–P33 e P42 do questionário.

Rodou **inteira sobre o cache** — 2,6 milhões de empenhos e 5 arquivos de dotação já baixados —,
sem uma requisição de rede. Tudo o que está aqui é reprodutível com dois comandos, a partir da
raiz do repositório:

```powershell
python -m financiamento.etl.execucao    --anos 2021-2025   # agregados, do cache
python -m financiamento.etl.evidencias  --anos 2021-2025   # tabela de evidências
python -m pytest financiamento/tests                       # 317 testes, sem rede
```

---

## 1. O que foi construído

| Arquivo | O que é |
|---|---|
| [`config/matriz_cnca.yaml`](../config/matriz_cnca.yaml) | A matriz inteira como configuração: 6 questões, **23 achados**, **49 perguntas**, 25 indicadores, 9 limiares parametrizáveis e as ressalvas que vão à tela junto de cada número |
| [`etl/matriz.py`](../etl/matriz.py) | Carrega e **valida** o YAML. Falha alto em achado que aponta para pergunta inexistente, limiar citado e não declarado, proxy sem ressalva, status fora do vocabulário |
| [`etl/execucao.py`](../etl/execucao.py) | Os cortes que o painel geral não produzia: mês a mês, por fonte com restos a pagar, elemento dentro da fonte, data do primeiro empenho, ação que nomeia alfabetização, idade do resto a pagar, dotação por fonte |
| [`etl/evidencias.py`](../etl/evidencias.py) | A tabela longa do papel de trabalho: uma linha por município × achado × indicador, com status, tipo de evidência, confiança e proveniência completa |
| `dados/evidencias/` | `evidencias_cnca.csv` e `.parquet` (3.744 linhas), `cobertura_achados.csv`, `cobertura_perguntas.csv`, `indices_execucao.csv`, `restos_a_pagar.csv`, `cobertura_pdde.csv` |

**Onde os arquivos ficam.** O prompt pedia `data/raw/`, `data/staging/` e `data/evidence/`. Essas
três camadas já existem no projeto como `dados/bruto/` (imutável, com SHA-256 por arquivo) e
`dados/processado/`; criar uma árvore paralela duplicaria 640 MB de cache e contrariaria o
"reaproveite, não duplique" do próprio prompt. A camada de evidências ficou em
`dados/evidencias/`, no mesmo idioma das outras. `config/matriz_cnca.yaml` manteve o nome pedido.

---

## 2. O que a Fase 1 descobriu sobre o dado (e que a Fase 0 não tinha visto)

### O arquivo de empenhos tem dois tipos de linha, e não diz isso

Medido nos 2,6 milhões de linhas de 2021–2025:

| Tipo de linha | Empenhada / Liquidada / Paga | Colunas de restos a pagar |
|---|---|---|
| `AnoEmpenho == AnoReferencia` (execução do exercício) | **preenchidas** | zeradas, exceto a inscrição (`RPPExercicio`, `RPNPExercicio`), que só aparece na última parte do ano |
| `AnoEmpenho < AnoReferencia` (movimento de restos a pagar) | **zeradas** | preenchidas: `RPNPLiquidado`, `RPNPPago`, `RPPPago`, `RPNPCancelado`, `RPPCancelado` |

Só numa das partes de 2022 há **10.221 linhas** de exercícios anteriores, com R$ 152,8 mi de RP
não processado liquidado e R$ 83,2 mi de RP processado pago. Somar `Empenhada` nelas dá **zero** —
quem fizer isso conclui que os municípios do ES não têm restos a pagar. O módulo trata os dois
tipos separadamente, e há teste para isso.

### Sete das treze colunas de restos a pagar vêm sempre vazias

`RPPTransferido`, `RPNPTransferido`, `RPNPBloqueado`, `RPNPRecebido`, `RPNPRestabelecido` e
`RPPRecebido` estão no dicionário oficial do TCE-ES e **não são publicadas**. Declarar não é
publicar: usar `RPPTransferido` para responder P25 devolveria "nenhum município tem restos a pagar
de exercícios anteriores" em 78 de 78 — um achado inventado a partir de uma coluna em branco.

A idade do RP é medida pelo `AnoEmpenho`, que é dado real. Resultado: **312 município-anos, em 56
municípios**, movimentaram no exercício restos a pagar **processados** de empenhos de dois ou mais
anos atrás. Nas fontes 551/569, 7 município-anos.

### `escolas.csv` é cadastro, não série

Uma linha por escola (3.440), com `ano_censo` sendo o último exercício em que ela apareceu no
Censo. Tratá-la como série anual daria denominador zero em 2021–2024 e cobertura do PDDE acima de
qualquer coisa. O denominador de P21 é o cadastro de **2.610 escolas municipais em atividade**, o
mesmo para todos os exercícios, e a coluna `denominador` diz isso em cada linha.

### Dois erros de programação que a conferência pegou

Registrados porque os dois produziriam número plausível e errado:

* **regex em maiúsculas sobre texto minúsculo.** `parsing.norm` devolve minúsculas sem acento; as
  regex de "alfabetização" estavam em maiúsculas e não casavam com nada. A primeira execução disse
  **"zero municípios nomeiam alfabetização no orçamento"** — que é quase a conclusão certa, o que
  a tornava especialmente perigosa. A medida correta é 4 ações com dotação, em 3 municípios;
* **código de fonte lido como número.** `pd.read_csv` transformava a fonte `"569"` em inteiro, e
  todo filtro por código devolvia vazio. A4.2 e A4.3 saíram inteiramente como "sem dado público"
  na primeira rodada. Há teste para os dois casos.

---

## 3. Conferências de consistência

| Conferência | Resultado |
|---|---|
| Municípios na tabela de evidências | **78**, e nenhum some entre as camadas |
| Soma por fonte × total do painel geral (função 12) | fecha **ao centavo** nos cinco exercícios: 4.289,83 mi (2021), 5.552,30, 6.154,83, 7.626,31 e 8.130,51 mi (2025) |
| Empenhado na dotação × empenhado nos empenhos, fonte 569 | idêntico em 2024 e 2025; diverge R$ 1,13 mi em **2023**, exatamente o ano em que o arquivo de empenhos não traz dezembro para 25 municípios |
| Status fora do vocabulário | nenhum |
| Toda linha com valor tem proveniência | sim |
| Linha `sem_dado_publico` com valor preenchido | **zero** — lacuna não virou número |

---

## 4. O que os dados dizem, achado por achado

> Nada abaixo é achado de auditoria. São indícios, e cada um carrega na própria linha o que
> mede e o que não prova.

### A3.1 — previsão do CNCA no PPA, LOA e QDD (390 município-anos)

| Status | Município-anos | O que significa |
|---|---|---|
| Indício de risco | **181** | Nenhuma ação nomeia alfabetização **e** não há dotação na fonte 569 |
| Inconclusivo | **206** | Há dotação na fonte 569, mas nenhuma ação a nomeia — o recurso existe, a rastreabilidade não |
| Sem indício | **3** | Há ação nomeada com dotação |

Os 3 "sem indício" são de 2021–2022 e, lidos um a um, são **EJA e Brasil Alfabetizado** — não o
CNCA. Em 2023–2025, período do CNCA, **nenhum município do ES tem ação orçamentária que nomeie
alfabetização**. Em 2025, 70 dos 78 têm dotação na fonte 569.

Esse par de números é o resultado mais forte da fase: o dinheiro federal existe no orçamento
municipal e não é identificável como CNCA em lugar nenhum dele.

### A4.1 — baixa execução na fonte 569

| Ano | Municípios com base | Mediana da execução | Abaixo de 70% |
|---|---|---|---|
| 2023 | 67 | 91,6% | 28 |
| 2024 | 69 | 77,4% | 33 |
| 2025 | 70 | 80,0% | 31 |

2021 e 2022 não entram: a fonte 569 não existia nos empenhos. Mede a fonte, não o CNCA.

### A4.2 — dessincronia entre repasse e empenho (só 2024–2025)

Mediana de **56 dias** entre o primeiro repasse do FNDE ao município e o primeiro empenho na
fonte; **48 município-anos** acima de 90 dias. Outros 50 ficaram inconclusivos por defasagem
negativa (empenho anterior ao primeiro repasse do ano — provável saldo do exercício anterior).
253 de 390 ficam sem dado, quase todos por serem 2021–2023, exercícios sem data de emissão no
leiaute.

A data do repasse é o **mês** de pagamento da CGU, não o dia: o número tem erro de até 30 dias e
não deve ser lido com precisão de dia.

### A4.3 — despesa incompatível (indício, nunca achado)

**24 municípios**, 36 município-anos, R$ 22,93 mi empenhados nas fontes 551/569 em elementos
atípicos para um programa de alfabetização — pessoal, obrigações patronais, obras, imóveis,
despesas de exercícios anteriores.

Atípico não é irregular, e a lista de elementos é parâmetro editável. Como o empenho do TCE-ES não
tem histórico nem número de contrato, cada uma dessas linhas só se resolve com o documento no
município. Vai à tela rotulada para revisão humana.

### A4.4 — concentração no fim do ciclo (o único indicador direto da Q4)

| Ano | Mediana | Acima de 25% | Negativos |
|---|---|---|---|
| 2021 | 23,8% | 34 | 1 |
| 2022 | 16,5% | 6 | 1 |
| 2023 | 14,2% | 2 | 1 |
| 2024 | 17,2% | 7 | 3 |
| 2025 | 18,7% | 13 | 3 |

**A calibração do limiar tem de olhar para esta tabela.** Com 25%, 2021 sozinho responde por
metade dos indícios da série — e 2021 é o ano da pandemia e da mudança de codificação de fontes.
Um limiar fixo trata 2021 e 2023 como se fossem comparáveis, e eles não são.

Os 9 casos negativos são anulações de empenho maiores que os empenhos de nov+dez. Ficam
inconclusivos: não são boa execução.

### P24 — os quatro índices do questionário (função 12 inteira, 2025)

| Índice | Mediana | Mínimo | Máximo |
|---|---|---|---|
| Execução orçamentária (empenhado ÷ dotação) | 94,1% | 74,5% | 99,7% |
| Execução financeira (pago ÷ dotação) | 89,3% | 66,3% | 99,2% |
| Liquidação (liquidado ÷ empenhado) | 97,7% | 82,5% | 100,0% |
| Pagamento (pago ÷ liquidado) | 99,2% | 90,9% | 100,0% |

Calculados para todo município × ano × fonte, e para o total da função 12. Servem para
**confrontar** a resposta de P24 — o município que disser que acompanha esses índices
"especificamente para recursos do CNCA" está descrevendo algo que a classificação orçamentária
dele não permite isolar.

### P21 — cobertura do PDDE-CNCA nas escolas municipais

| Ano | Mediana da cobertura | Municípios com alguma escola atendida |
|---|---|---|
| 2021 | 0% | 0 |
| 2022 | 0% | 0 |
| 2023 | **31,0%** | **76** |
| 2024 | 4,2% | 46 |
| 2025 | 6,1% | 50 |

2021–2022 são zero porque o plano orçamentário do CNCA (000C) ainda não existia — era o PO 0007,
"PDDE - Alfabetização", que a tabela guarda à parte. A queda de 2023 para 2024 é a mesma que o
painel já mostrava em valor (R$ 4,11 mi → R$ 0,31 mi), agora em cobertura de escolas.

### P33 — a despesa do 1º e 2º ano não é separável

Resposta **direta e igual para os 78**: a subfunção 361 é o menor grão que chega ao TCE-ES, e ela
cobre o ensino fundamental inteiro. Município que responder "sim, o sistema gera relatórios
individualizados" está descrevendo um sistema interno que não chega ao CidadES.

### P42 — premiação de boas práticas (art. 12 do Decreto 11.556/2023)

5 municípios têm ação de premiação com dotação (R$ 1,85 mi em 2021–2025), mas **apenas uma é da
educação**: "PRÊMIO BOAS PRÁTICAS NA EDUCAÇÃO", R$ 30 mil em 2025. As demais são premiações
culturais, artísticas e desportivas. A captura por palavra-chave é ampla de propósito, e a
separação entre as duas coisas é feita na leitura, não no filtro.

---

## 5. Cobertura da matriz depois da Fase 1

| Situação | Achados |
|---|---|
| Calculado (Fase 1) | **5** — A3.1, A4.1, A4.2, A4.3, A4.4 |
| Sem dado público (resposta final) | **8** — A1.3, A1.5, A1.6, A2.4, A4.5, A5.1, A5.2, A5.5 |
| Pendente da Fase 2 | 4 — A2.1, A2.2, A5.4, A6.1 |
| Pendente da Fase 3 | 6 — A1.1, A1.2, A1.4, A1.7, A2.3, A5.3 |

Das 49 perguntas do questionário: **7 diretas**, 11 por proxy, 4 parciais e **27 indisponíveis**.
Esse 27 é o número mais útil da fase para a seção de metodologia do relatório — mais da metade do
questionário só pode ser respondida pelos municípios, por ofício ou por análise documental, e isso
agora está medido, não estimado.

Os 8 "sem dado público" já são **resposta final**, não pendência: a Fase 1 os gravou na tabela de
evidências, uma linha por município, com o motivo e o caminho alternativo. Eles não vão melhorar
em fase nenhuma sem ofício.

---

## 6. O que ficou de fora, e por quê

* **A4.5 (conciliação bancária)** — o CONCIBAN e o BALANCORR não estão em dado aberto. A camada é
  plugável: entregue a extração interna do CidadES, o achado passa de indisponível a direto sem
  mudar o painel. Continua sem confirmação o exercício a partir do qual o CONCIBAN é obrigatório.
* **A3.1 como evidência direta** — depende do PPA/LOA/LOAPROG/PRATIVOE do CidadES. Hoje é proxy.
* **P29–P32 (valores orçados e executados do CNCA)** — não existe valor "do CNCA" no orçamento
  municipal. O painel oferece três números distintos (dotação e empenho na fonte 569, PDDE-CNCA
  recebido), cada um rotulado; a comparação com o que o município responder é o ponto de exame.
  **P32 (2026)** fica fora: o arquivo de empenhos de 2026 no TCE-ES tem só as duas primeiras
  partes publicadas.
* **Execução do PDDE-CNCA** — é gasto pela escola e prestado ao FNDE. O painel mostra o recebido.

---

## 7. Para a equipe calibrar antes da Fase 2

Os 9 limiares estão em `config/matriz_cnca.yaml → parametros`, cada um com `calibrar: true` e a
distribuição real medida na descrição. Mudar ali muda o painel inteiro, sem tocar em código. Os
três que mais mudam o resultado:

1. **`concentracao_fim_ciclo_pct` (hoje 25%)** — ver a tabela de A4.4. Vale decidir se o limiar é
   fixo ou relativo à mediana do exercício;
2. **`execucao_baixa_pct` (hoje 70%)** — com 70%, cerca de 30 municípios por ano entram como
   indício em A4.1. A mediana real está entre 77% e 92%;
3. **`defasagem_dias` (hoje 90)** — com 90 dias, 48 município-anos entram. A mediana é 56.

E uma decisão de método, que é da equipe e não do código: **A3.1 hoje classifica como indício de
risco o município que não tem dotação na fonte 569 nem ação nomeada.** Como não existe forma de
identificar o CNCA no orçamento municipal, esse indício diz mais sobre a classificação
orçamentária brasileira do que sobre o município. Talvez ele deva ser lido como uma constatação
única sobre os 78 — e não como 181 indícios individuais.
