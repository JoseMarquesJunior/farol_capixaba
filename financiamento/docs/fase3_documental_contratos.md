# Fase 3 — documental, contratos e recursos estaduais

Os achados de governança (Q1), o plano de alfabetização (A2.3), o fórum de análise crítica
(A5.3), as contratações de formação (P47, P48) e o regime de colaboração com o Estado (P18).

```powershell
python -m financiamento.etl.contratos                      # classifica contratações da Educação
python -m financiamento.etl.diarios   --atualizar tudo     # Querido Diário + índice do DOM-ES
python -m financiamento.etl.estado    --anos 2023-2025     # SIGEFES: repasses do Estado
python -m financiamento.etl.evidencias --anos 2021-2025
python -m pytest financiamento/tests                       # 360 testes, sem rede
```

---

## 1. O lado estadual: a hipótese do prompt se confirmou (P18)

O prompt tratava isto como *hipótese a testar* — "filtrar despesas estaduais pela UG
SEDU/FUNPAES e modalidade de transferência a municípios". Ela se confirmou, e a evidência
subiu de **proxy** para **quase direta**.

[`etl/estado.py`](../etl/estado.py) lê o arquivo do SIGEFES (~1,4 GB por exercício, 71 colunas)
**em fluxo**, guardando só as linhas da função 12 com modalidade de aplicação 40, 41 ou 42 —
as três que significam "saiu do Estado para o município". Do arquivo inteiro sobram cerca de
5 mil linhas por ano; o recorte fica no cache com o SHA-256 do original ao lado.

| Ano | Municípios alcançados | Empenhado pelo Estado | …do qual FUNPAES | FUNPAES em % |
|---|---|---|---|---|
| 2023 | **78** | R$ 430,0 mi | R$ 91,7 mi | 21% |
| 2024 | **78** | R$ 377,2 mi | R$ 105,6 mi | 28% |
| 2025 | 77 | R$ 719,7 mi | **R$ 418,4 mi** | **58%** |

O FUNPAES quadruplicou em dois exercícios e passou a responder por quase 60% do que o Estado
transfere aos municípios na educação. É o número mais relevante que a Fase 3 produziu para Q6:
o braço financeiro do PAES — dentro do qual o CNCA é implementado no ES — cresceu enquanto o
PDDE-CNCA às escolas caía de R$ 4,11 mi (2023) para R$ 0,32 mi (2025).

**A taxa de casamento é medida, não presumida:** **99,0%** do valor foi atribuído a um município
pelo nome do favorecido — 13.706 linhas por nome exato e 287 por similaridade (só os dois casos
de grafia abaixo). Restam 11 favorecidos e R$ 15,14 mi em
`cnca_estado_nao_identificados.csv`, com o nome original — nunca descartados em silêncio.

### A grafia do Estado não é a do IBGE

Ao olhar a tabela dos não identificados, dois favorecidos somavam **R$ 9,3 milhões**:

* `PREFEITURA MUNICIPAL DE DIVINO SÃO LOURENÇO` — o IBGE escreve "Divino **de** São Lourenço";
* `PREFEITURA MUNICIPAL DE GOVERNADOR LINDEMBERG` — o IBGE escreve "Linde**n**berg".

Uma preposição e uma letra. O módulo passou a tentar, quando nenhum nome casa inteiro, um
casamento por **similaridade** com limiar de 0,90 — alto o bastante para que "Cooperativa de
Transportes da Região Sul" e "Fundo Estadual de Saúde" continuem sem casar, e o método usado
fica gravado na coluna `metodo_casamento` de cada linha, para quem revisa saber quais vieram daí.

### O que o download tem de frágil

O arquivo de **2024** caiu no meio na primeira tentativa (`IncompleteRead` depois de ~290 MB de
1,4 GB) e entrou na segunda. O leitor em fluxo **não repete o download** quando a conexão quebra
— o de ZIP do TCE-ES repete, este não —, então o ano que falha fica para a execução seguinte,
com o aviso registrado. É limitação conhecida, não silêncio, e vale corrigir se o download
passar a falhar com frequência.

Cada exercício leva de 20 a 30 minutos para ser lido em fluxo. Uma vez em cache, reprocessar os
três leva segundos — é o que permitiu refazer o casamento por nome sem rebaixar 4 GB.

### Um defeito que a codificação escondia

O leitor em fluxo do projeto assumia **latin-1**, que é o encoding dos arquivos do TCE-ES. O do
SIGEFES é **UTF-8 com BOM**. Ler UTF-8 como latin-1 não falha: produz mojibake — e o nome do
favorecido em mojibake não casa com município nenhum, o que teria zerado P18 sem nenhum erro
aparente. `recorte_csv_fluxo` ganhou o parâmetro `encoding`, com latin-1 como padrão para não
mexer no que já funcionava.

---

## 2. Contratações de formação e material (P47, P48)

[`etl/contratos.py`](../etl/contratos.py) classifica o **objeto** das contratações da Educação
já recortadas pelo pipeline geral — o único rastro que existe, já que o empenho do TCE-ES não
traz histórico nem número de contrato.

| Categoria | Contratações | Municípios | Valor | Responde P47 |
|---|---|---|---|---|
| Assessoria ou consultoria pedagógica | 13 | 8 | **R$ 15,08 mi** | sim |
| Formação continuada (sem menção à alfabetização) | 8 | 7 | R$ 0,33 mi | não |
| Material didático estruturado ou apostilado | 1 | 1 | R$ 0,28 mi | não |
| Menciona alfabetização (revisão humana) | 6 | 4 | R$ 0,21 mi | não |

**Nenhuma contratação do ES tem por objeto formação continuada em alfabetização.** As 6 que
citam "alfabetiz" em 3.700 contratações da Educação são, lidas uma a uma: inscrições num
congresso, duas palestras, papelaria e gêneros alimentícios do **Brasil Alfabetizado (EJA)**, e
uma passagem aérea. Nenhuma é o que P47 pergunta.

Essas 6 têm categoria própria — "menciona alfabetização" — justamente para não sumirem: a regra
é que nada que nomeie o programa saia da tela em silêncio, mesmo quando a leitura mostra que
não é o que se procurava.

Cada linha classificada carrega **os termos que a fizeram entrar**, para o auditor confirmar ou
descartar. Contratação revogada, anulada, fracassada ou deserta entra na tabela **marcada** e
fica fora do valor de P48 — somar licitação revogada infla o gasto com algo que não aconteceu.

### Por que o PNCP não é chamado em lote

A API de consulta do PNCP não filtra por UF nem por município: para achar os contratos do ES
seria preciso baixar os ~144 mil contratos mensais do país inteiro. Como `tcees-contratacoes`
já cobre 77 dos 78 municípios, o PNCP fica registrado em `PNCP_CONSULTA` como caminho para
quem for buscar um contrato específico — com a observação, medida, de que o servidor expira em
60 s e responde em 150 s.

---

## 3. Diários oficiais: a cobertura é o limite, não a técnica

[`etl/diarios.py`](../etl/diarios.py) faz três coisas e não finge fazer uma quarta:

1. **busca no Querido Diário** os termos da matriz, nos municípios que ele cobre;
2. **coleta o índice de edições do DOM-ES/AMUNES** — 781 edições, de 25/09/2023 a 23/09/2026;
3. **gera a lista de buscas manuais** para os demais municípios: 390 linhas (78 × 5 achados),
   cada uma com o termo, o endereço, o período e o que registrar.

### O endpoint que o reconhecimento não tinha achado

A Fase 0 concluiu que o DOM-ES não expunha API. Procurando nos scripts da página inicial
apareceu `/apifront/portal/edicoes/ultimas_edicoes.json`, que responde 200 e devolve o índice
de edições com id, data e tipo. **A busca textual continua sem endpoint** — ela é montada no
cliente —, mas o índice torna a varredura *planejável*: sabe-se exatamente quantas edições
existem e quais.

### O serviço saiu do ar durante a coleta

O Querido Diário respondeu 200 no início da sessão e, minutos depois, **503 nos dois endereços**
(`queridodiario.ok.org.br/api` e `api.queridodiario.org.br`). A coleta desta execução registrou
**72 municípios com cobertura "não medida"** e 6 "não coberto".

Isso está tratado como indisponibilidade, e não como achado. Dizer "0 de 78 têm diário" quando
a medição falhou transformaria um problema do serviço numa afirmação sobre os municípios. Na
tabela de evidências, esses 72 saem com a nota:

> *A cobertura de diário deste município não foi medida: a API do Querido Diário não respondeu
> na última coleta. Não se sabe se ele tem diário indexado — e não se afirma que não tem.*

O módulo tenta os dois endereços com espera entre tentativas, e na próxima execução bem-sucedida
a medição entra sozinha. Do reconhecimento da Fase 0, sabe-se que o número real é **3 de 78**
(Vitória, Serra e Vila Velha).

### O que a busca documental pode e não pode dizer

`documental()`, em `etl/evidencias.py`, obedece a duas regras:

* **nenhum município recebe `sem_indicio` por ter aparecido numa busca textual**, e nenhum
  recebe `indicio_risco` por não ter aparecido. Busca em diário é triagem: o resultado é uma
  lista de edições para alguém ler;
* **achado sem termo de busca não é reportado como "nada encontrado"**. É o caso de A1.2, que
  exige *ler* o ato que A1.1 localiza: busca textual não responde se o ato define atribuições.
  Dizer "nada encontrado" ali seria relatar o resultado de uma busca que nunca houve.

Mesmo nos 3 municípios cobertos, a Fase 0 mediu que `"Compromisso Nacional Criança
Alfabetizada"` devolve **zero edições** desde 2023, enquanto "articulador" devolve 866, quase
todas de outro assunto. É por isso que os termos são amplos de propósito e o resultado é rotulado
como triagem.

---

## 4. Cobertura depois da Fase 3

Os 23 achados da matriz estão todos classificados — não há mais nenhum pendente:

| Situação | Achados |
|---|---|
| Calculado | **15** — A1.1, A1.2, A1.4, A1.7, A2.1, A2.2, A2.3, A3.1, A4.1, A4.2, A4.3, A4.4, A5.3, A5.4, A6.1 |
| Sem dado público (resposta final) | 8 — A1.3, A1.5, A1.6, A2.4, A4.5, A5.1, A5.2, A5.5 |

A tabela de evidências tem **7.332 linhas**, 78 municípios, e nenhuma linha com valor sem
proveniência.

Vale ler a coluna "calculado" com cuidado: dos 15, seis são documentais e, com o Querido Diário
fora do ar, todos os seus municípios saem como "sem dado público" — o cálculo existe, o dado não.
Essa é a diferença entre **estar implementado** e **ter resposta**, e o painel de cobertura
mostra as duas coisas separadas.
