# Fase 2 — necessidades e resultados

O que a rede **tem** (Censo Escolar), o que ela **alcança** (ICA do INEP) e quanto do recurso do
CNCA chega por aluno de alfabetização. Cobre os achados A2.1, A2.2, A5.4 e A6.1 e as perguntas
P7, P19, P21, P27 e P39.

```powershell
python -m financiamento.etl.censo_alfabetizacao              # retrato do Censo (banco ou cache)
python -m financiamento.etl.evidencias --anos 2021-2025      # recompõe a tabela de evidências
python -m pytest financiamento/tests                         # 343 testes, sem rede e sem banco
```

---

## 1. O corte que faltava: a etapa

O painel geral traz o cadastro de escolas, mas não desce à **etapa**. O CNCA é sobre o 1º e o 2º
ano do ensino fundamental, então [`etl/censo_alfabetizacao.py`](../etl/censo_alfabetizacao.py)
extrai do banco do NEDUC o que o programa exige:

| O que | De onde | Cobertura real |
|---|---|---|
| Matrículas de 1º e 2º ano | `stg.matricula.qt_mat_fund_ai_1` e `_ai_2` | **2023 em diante** |
| Turmas de 1º e 2º ano | `stg.turma.qt_tur_fund_ai_1` e `_ai_2` | **só 2025** |
| Salas de aula utilizadas | `stg.escola.qt_salas_utilizadas` | 2021–2025 |
| Biblioteca ou sala de leitura | `in_biblioteca`, `in_sala_leitura`, `in_biblioteca_sala_leitura` | 2021–2025 |

**Os dois cortes por ano escolar começam em exercícios diferentes, e isso foi medido no banco,
não deduzido do leiaute.** A matrícula desdobra 1º e 2º ano desde 2023; a turma, só em 2025 — em
2021–2024 o Censo publica apenas o total dos anos iniciais. Onde a coluna não existe o módulo
devolve **NA**, e o indicador diz "não existe neste exercício", nunca zero. Somar zeros produziria
"nenhuma turma de alfabetização em 2024", que é falso.

O retrato fica em `dados/bruto/censo/alfabetizacao.csv.gz`, com o SQL e o instante da extração no
`.json` ao lado — a execução é reproduzível sem o banco, e sem o banco os indicadores saem como
"sem dado" em vez de sumir.

**Espaço de leitura** reúne os três marcadores do Censo, não só `in_biblioteca`: a escola pequena
que tem sala de leitura e não tem biblioteca conta. E o denominador é a **rede que alfabetiza** —
escolas municipais em atividade com matrícula nos anos iniciais —, não a rede inteira.

---

## 2. O que os dados dizem

> Nenhum indicador desta fase classifica município. Todos saem como **inconclusivos**: o Censo
> mede o que a rede tem, não o que o município sabe sobre ela, e a correlação entre recurso e
> resultado é descritiva.

### A2.1 — valor de referência do Cantinho da Leitura

Salas de aula utilizadas em escolas municipais com anos iniciais × **R$ 1.235** (Resolução
CD/FNDE nº 22/2023):

| Ano | Salas na rede municipal do ES | Valor de referência |
|---|---|---|
| 2021 | 9.831 | R$ 12,14 mi |
| 2023 | 10.145 | R$ 12,53 mi |
| 2025 | **10.627** | **R$ 13,12 mi** |

Mediana por município em 2025: **R$ 80.275**. É estimativa de ordem de grandeza de **uma** das
ações do CNCA — não a necessidade total do município, e não diz se o município a conhece. Serve
para confrontar P27.

Para dimensionar: o PDDE-CNCA pago às escolas do ES em 2025 foi de **R$ 0,32 mi**, contra um valor
de referência de R$ 13,12 mi só para o Cantinho da Leitura. A distância entre os dois números é,
por si, matéria para Q6.

### A2.2 — o que a rede tem

| Indicador | Município-anos com dado | Exercícios |
|---|---|---|
| Matrículas de 1º e 2º ano | 234 | 2023–2025 |
| Turmas de 1º e 2º ano | 78 | só 2025 |
| Escolas com espaço de leitura | 390 | 2021–2025 |

Em 2025: **93.186 matrículas** de 1º e 2º ano e **4.302 turmas** na rede municipal do ES.

**Espaço de leitura**: mediana de **50%** das escolas municipais com anos iniciais; em 2025,
**34 municípios** estão abaixo de 50%. Esse número é o contraponto direto do valor de referência
do Cantinho da Leitura — metade das escolas que alfabetizam não tem biblioteca nem sala de
leitura declarada ao Censo.

### A5.4 — recurso por aluno × ICA

| Ano | Municípios com as duas pontas | Mediana | Mínimo | Máximo |
|---|---|---|---|---|
| 2023 | 76 | **R$ 46,19** | R$ 9,72 | R$ 82,33 |
| 2024 | 46 | R$ 7,55 | R$ 0,40 | R$ 90,23 |
| 2025 | 50 | R$ 6,21 | R$ 0,54 | R$ 46,70 |

A queda de 2023 para 2024 é a mesma do repasse (R$ 4,11 mi → R$ 0,31 mi), agora por aluno. A
dispersão dentro de cada ano é grande — em 2024, de R$ 0,40 a R$ 90,23 por aluno —, e o MEC não
publica os pesos dos critérios de repasse, então **não dá para dizer se essa dispersão é
focalização ou não**. O painel mostra os dois lados e não infere.

**ICA da rede municipal** (edição 2025 do INEP, 234 município-anos):

| Ano | Mediana | Municípios abaixo de 70% |
|---|---|---|
| 2023 | 74% | 27 |
| 2024 | 80% | 14 |
| 2025 | **83%** | **2** |

Cada comparação é do município com ele mesmo — nunca entre estados, porque cada edição tem sua
régua. Onde há queda no ICA **e** recurso do CNCA identificado no exercício, a linha sai marcada
como **prioridade de exame**, não como achado.

### A6.1 — recurso próprio

Parcela do empenho da função 12 vinda de fonte própria (impostos vinculados à educação e FUNDEB):

| Ano | Mediana | Código de fonte usado |
|---|---|---|
| 2021 | 87,1% | 111/112/113 (codificação local do ES) |
| 2022 | 78,2% | 111/112/113 |
| 2023 | 76,7% | 500/540 (padrão STN) |
| 2024 | 71,7% | 500/540 |
| 2025 | 74,3% | 500/540 |

**Os códigos mudam em 2023** — até 2022 o ES usava a codificação local. A primeira versão do
indicador usava só 500/540 e devolveu "0% de recurso próprio" em 2021 e 2022, o que teria
aparecido no painel como um município que não gasta nada da educação com recurso próprio. Está
corrigido, com teste.

O indicador **não distingue** complementação ao CNCA de manutenção ordinária da rede: quase toda a
despesa da educação municipal sai dessas fontes. Serve de contraste com P19/P20.

Transferências do FNDE recebidas pelos 78 municípios em 2021–2025: **R$ 2,42 bilhões** (todas as
ações — salário-educação, PNAE, PNATE, PDDE; não é recurso do CNCA).

---

## 3. Conferências

| Conferência | Resultado |
|---|---|
| Municípios no retrato do Censo | **78**, nos cinco exercícios |
| Escolas × ano no retrato | 16.486 linhas, 3.441 escolas distintas |
| Linhas `sem_dado_publico` com valor preenchido | **zero** |
| Linhas com valor e sem proveniência | **zero** |
| Tabela de evidências | **6.864 linhas**, 78 municípios, 17 achados com linha |

A conferência de proveniência pegou uma regressão: as consultas desta matriz (o Censo no recorte
da alfabetização, e o primeiro repasse do FNDE) não estavam em `consultas.csv`, que é escrito pelo
pipeline geral — 1.092 linhas saíram com valor e sem proveniência. Agora cada módulo grava as suas
em `dados/processado/cnca_consultas.csv`, e a camada de evidências lê os dois arquivos. A consulta
do Censo ganhou um fragmento na URL (`#alfabetizacao`) porque o id de uma consulta é o hash de
fonte + método + URL, e sem ele esta extração colidiria com a do painel geral, que consulta o
mesmo banco com outro SQL.

---

## 4. Cobertura depois da Fase 2

| Situação | Achados |
|---|---|
| Calculado | **9** — A2.1, A2.2, A3.1, A4.1, A4.2, A4.3, A4.4, A5.4, A6.1 |
| Sem dado público (resposta final) | 8 — A1.3, A1.5, A1.6, A2.4, A4.5, A5.1, A5.2, A5.5 |
| Pendente da Fase 3 | 6 — A1.1, A1.2, A1.4, A1.7, A2.3, A5.3 |

Os 6 pendentes são todos documentais: dependem de diário oficial, e a Fase 0 mediu que o Querido
Diário cobre 3 dos 78 municípios. É a fase com o teto mais baixo, e convém saber disso antes de
começá-la.

---

## 5. As duas decisões da revisão anterior, implementadas

**A4.4 passou a comparar com a mediana do exercício.** A distribuição real (subfunção 361, base
≥ R$ 1 mi) mostrou por quê:

| Ano | Mediana | Limiar fixo de 25% marcaria | Percentil 75 marcaria | Mediana + 10 p.p. com piso de 20% marca |
|---|---|---|---|---|
| 2021 | 24,4% | 34 | 20 | **10** |
| 2022 | 16,4% | 6 | 20 | 5 |
| 2023 | 13,3% | 2 | 20 | **2** |
| 2024 | 16,5% | 7 | 20 | 4 |
| 2025 | 18,1% | 13 | 20 | 4 |

O limiar fixo marca 34 municípios em 2021 contra 2 em 2023 — diferença que é do ano, não da
gestão. O percentil marca exatamente 20 todo ano, por construção: é ranking, não achado. O
critério adotado marca **25 município-anos, 18 municípios distintos, 4 deles reincidentes** — que
é a lista por onde começar. O painel mostra a mediana do exercício ao lado de cada valor.

**A3.1 virou constatação única.** A ausência de identificação do CNCA na classificação
orçamentária vale para os 78, e passou a ser dita uma vez, em `constatacoes` no YAML da matriz:

> **C3.1** — O CNCA não é identificável na classificação orçamentária de nenhum dos 78 municípios
> do ES. […] Em 2023–2025, nenhuma ação da função 12 cita alfabetização, CNCA, Renalfa ou Cantinho
> da Leitura; as quatro ações nomeadas de 2021–2025 são de EJA e Brasil Alfabetizado, em três
> municípios, e somam R$ 87,3 mil. A Tabela de Fontes do TCE-ES de 2025 não tem nenhuma entrada de
> CNCA, PAR ou alfabetização em suas 147 fontes e 54 complementos.

A3.1 deixou de gerar indício individual: os 181 de antes viraram zero, e o que sai por município é
contexto (dotação na fonte 569, ação nomeada). O carregador **recusa** um achado que tenha
constatação e ainda declare `indicio_risco` na regra — dizer a mesma coisa duas vezes, uma delas
injustamente, passou a ser erro de configuração.

Duas outras constatações foram registradas pelo mesmo critério: **C4.5** (conciliação bancária não
está em dado aberto) e **C4.3** (a despesa do 1º e 2º ano não é separável na remessa ao TCE-ES).
Saem do mapa de calor e vão para o texto do relatório.
