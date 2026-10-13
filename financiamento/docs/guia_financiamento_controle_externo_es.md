# Financiamento da educação e controle externo no Espírito Santo

**Guia de referência para a fiscalização** — as fontes de receita, as despesas, o marco
normativo, os índices e os testes que o dado público sustenta, com exemplos medidos nos
78 municípios capixabas e no Estado, exercícios de 2021 a 2025.

> **De onde vêm os números deste guia.** Todos os valores citados foram extraídos do
> dataset do painel de financiamento (`financiamento/dados/processado/`), cuja coleta
> está descrita no [README](../README.md) e cuja proveniência — endpoint, parâmetros,
> anexo/linha/coluna, cálculo e instante da coleta — está registrada linha a linha em
> `consolidado.csv` (170.999 registros). Coleta de **22 e 23 de setembro de 2026**.
> Nenhum número aqui é estimativa: quando a fonte não responde, o guia diz que não
> responde, em vez de preencher a lacuna.
>
> **Nada neste documento é achado de auditoria.** Os exemplos são *indícios* e
> ilustrações de método. Um achado exige contraditório, exame documental e juízo
> técnico que o dado público, sozinho, não produz. A seção [§6.5](#65-o-que-o-dado-público-não-responde)
> lista explicitamente o que não se pode afirmar com estas fontes.

---

## Sumário

1. [O desenho: três caixas de dinheiro que não se confundem](#1-o-desenho-três-caixas-de-dinheiro-que-não-se-confundem)
2. [As fontes de financiamento](#2-as-fontes-de-financiamento)
3. [As despesas](#3-as-despesas)
4. [O marco normativo](#4-o-marco-normativo)
5. [Os índices](#5-os-índices)
6. [A auditoria: como o dado vira (ou não vira) achado](#6-a-auditoria-como-o-dado-vira-ou-não-vira-achado)
7. [Uma trilha completa: Guaçuí, 2024](#7-uma-trilha-completa-guaçuí-2024)
8. [Roteiro de testes](#8-roteiro-de-testes)
9. [Anexos](#9-anexos)

---

## 1. O desenho: três caixas de dinheiro que não se confundem

O erro mais comum ao examinar financiamento da educação é tratar "dinheiro da educação"
como um número só. Não é. Há **três conjuntos de recursos**, com regras de origem,
destinação, apuração e prestação de contas diferentes, e o mesmo município tem números
distintos — todos corretos — para cada um deles.

| | **MDE** | **FUNDEB** | **Transferências federais específicas** |
|---|---|---|---|
| **Origem** | Receita resultante de impostos (próprios + transferidos) | Cesta de impostos estaduais e municipais + complementação da União | Contribuição do salário-educação e orçamento do FNDE |
| **Regra** | Aplicar ≥ 25% (art. 212 da CF) | Aplicar tudo em educação básica; ≥ 70% em remuneração de profissionais (art. 212-A, XI) | Cada programa tem sua própria regra (PNAE, PNATE, PDDE…) |
| **Quem apura** | SIOPE (RREO Anexo 8) e o TCE-ES | SIOPE e o TCE-ES | FNDE, por prestação de contas própria |
| **Natureza** | Piso de aplicação | Fundo contábil redistributivo | Transferência vinculada a programa |

E há um quarto número, mais amplo que os três: a **função 12 (Educação)** da
classificação funcional, que é tudo o que o ente empenhou em educação, venha de onde
vier, conte ou não para o mínimo.

**O mesmo município, o mesmo ano, quatro números diferentes** — Guaçuí, 2024:

| Número | Valor | O que é |
|---|---:|---|
| Função 12 empenhada (DCA Anexo I-E) | R$ 58.481.741,01 | tudo que o município gastou em educação |
| Despesa total com educação (SIOPE, Anexo 8) | R$ 61.839.621,03 | o que o município declarou ao SIOPE |
| Despesa para fins de limite do MDE | R$ 18.273.129,77 | o que conta para os 25% |
| Mínimo exigido (25% da base) | R$ 20.374.142,85 | o piso constitucional |

A distância entre R$ 58,5 milhões gastos e R$ 18,3 milhões computados no MDE **não é
erro**: é o desenho da regra. O MDE exclui o que o FUNDEB já custeia, exclui merenda,
exclui transporte quando classificado como assistência, e desconta as deduções previstas
em lei. Quem compara "gasto em educação" com "25%" chega a uma conclusão errada nos dois
sentidos possíveis.

---

## 2. As fontes de financiamento

### 2.1 Impostos e transferências de impostos — a base do MDE

O art. 212 da Constituição manda aplicar 25% **"da receita resultante de impostos,
compreendida a proveniente de transferências"**. As quatro palavras finais são o ponto:
a base não é o que o município arrecada, é o que ele arrecada **mais** o que recebe de
cota-parte de impostos da União e do Estado (FPM, cota-parte do ICMS, do IPVA, do IPI-Exp,
ITR, e a compensação da LC 87/1996).

Para a maioria dos municípios capixabas, a parte própria é minoritária — e em vários
deles é quase irrelevante:

**Impostos próprios como fração da base do MDE, 78 municípios, 2024** *(fonte: SIOPE, RREO Anexo 8)*

| | Impostos próprios | Base do MDE | Próprios / base |
|---|---:|---:|---:|
| **Mediana dos 78 municípios** | — | — | **12,4%** |
| Governador Lindenberg | R$ 3.124.229,10 | R$ 54.117.813,00 | 5,8% |
| Ponto Belo | R$ 1.850.551,31 | R$ 31.336.054,81 | 5,9% |
| Divino de São Lourenço | R$ 1.889.139,70 | R$ 29.361.641,80 | 6,4% |
| … | | | |
| Guarapari | R$ 136.734.398,90 | R$ 304.117.748,30 | 45,0% |
| Presidente Kennedy | R$ 55.317.631,30 | R$ 107.932.329,10 | 51,3% |
| Vitória | R$ 1.247.123.412,90 | R$ 2.395.368.833,60 | 52,1% |
| **Vila Velha** | R$ 659.329.376,40 | R$ 1.151.214.962,70 | **57,3%** |

No agregado dos 78 municípios, os impostos próprios subiram de 28,2% da base em 2021
para 32,1% em 2025 — mas a mediana municipal continua em torno de 12%. **Consequência
para a fiscalização:** num município pequeno, a base do MDE é determinada por repasses
que ele não controla. Uma queda do FPM derruba o valor absoluto do mínimo exigido sem
que nada tenha mudado na gestão; e um aumento inesperado de arrecadação no fim do
exercício eleva o piso quando já quase não há tempo de empenhar. Esse é um dos motivos
legítimos da concentração de empenho em novembro e dezembro examinada em
[§5.4](#54-índices-de-execução).

**A base do MDE nos 78 municípios** *(SIOPE, R$ bilhões)*

| Ano | Impostos próprios | Base do MDE | Aplicado em MDE | Exigido (25%) | % agregado |
|---|---:|---:|---:|---:|---:|
| 2021 | 2,66 | 9,44 | 2,51 | 2,36 | 26,58% |
| 2022 | 3,22 | 11,09 | 3,15 | 2,77 | 28,39% |
| 2023 | 3,87 | 12,31 | 3,51 | 3,11 | 28,51% |
| 2024 | 4,56 | 14,22 | 3,99 | 3,55 | 28,06% |
| 2025 | 5,06 | 15,76 | 4,30 | 3,94 | 27,27% |

Em 2025 os municípios do ES aplicaram **R$ 360 milhões acima do piso** — folga de pouco
mais de 2 pontos percentuais no agregado. Folga agregada, porém, não diz nada sobre o
município individual: em 2024, com o agregado em 28,06%, Guaçuí ficou em 22,42%.

### 2.2 FUNDEB

O FUNDEB é um **fundo contábil de âmbito estadual**: não tem personalidade jurídica, não
tem conta única nacional. Cada estado tem o seu, formado por percentuais fixos de uma
cesta de impostos estaduais e municipais. Os entes **contribuem** e **recebem** de volta
segundo o número de matrículas ponderado por etapa, modalidade e tipo de atendimento.
Contribuir mais do que se recebe não é irregularidade — é o mecanismo redistributivo
funcionando.

**FUNDEB nos 78 municípios do ES** *(SIOPE, R$ bilhões)*

| Ano | Destinado ao FUNDEB (contribuição) | Recebido | Saldo líquido |
|---|---:|---:|---:|
| 2021 | 1,32 | 2,80 | +1,48 |
| 2022 | 1,52 | 3,24 | +1,72 |
| 2023 | 1,62 | 3,58 | +1,96 |
| 2024 | 1,86 | 4,24 | +2,38 |
| 2025 | 2,05 | 4,76 | +2,71 |

O conjunto dos municípios capixabas é **receptor líquido**: recebe mais do que contribui,
porque a diferença vem da parcela estadual da cesta e da complementação da União. Em
Guaçuí, 2024: contribuiu R$ 12.858.923,74, recebeu R$ 41.374.587,43 — líquido de
R$ 28.515.663,69, dos quais R$ 6.623.741,24 de complementação da União.

**A complementação da União** tem três canais, criados pela EC 108/2020 e regulados pela
Lei 14.113/2020, que somam no mínimo 23% do total dos fundos:

| Canal | Peso | Critério |
|---|---|---|
| **VAAF** — valor anual por aluno | 10 p.p. | complementa os fundos estaduais cujo valor por aluno fica abaixo da média nacional |
| **VAAT** — valor anual total por aluno | 10,5 p.p. | considera **todas** as receitas vinculadas à educação do ente, não só o fundo; alcança municípios pobres em estados ricos |
| **VAAR** — valor anual por aluno por resultado | 2,5 p.p. | condicionado a indicadores de atendimento e aprendizagem e ao cumprimento de condicionalidades de gestão |

O VAAT é o que mudou o jogo para o controle externo, por duas razões. Primeira: ele
olha a receita **total** vinculada à educação do município, e não apenas o que passa pelo
fundo — o que torna a qualidade da declaração ao SIOPE determinante do valor recebido.
Segunda: os recursos do VAAT têm **destinações mínimas próprias** (parcela obrigatória em
educação infantil e parcela obrigatória em despesas de capital), verificáveis de forma
independente do mínimo dos 70%.

> **Confirmar antes de citar.** Os percentuais das destinações mínimas do VAAT e a
> numeração dos artigos da Lei 14.113/2020 foram alterados desde a edição original (entre
> outras, pela Lei 14.276/2021). Consulte o texto consolidado vigente antes de usar um
> percentual específico em papel de trabalho. O desenho geral descrito acima é estável.

**O que mudou em relação ao FUNDEF/FUNDEB anterior, e que ainda gera erro de análise:**
o fundo antigo (Lei 11.494/2007) exigia 60% para **remuneração do magistério**. O atual
exige **70% para profissionais da educação básica em efetivo exercício** — universo mais
amplo, que inclui, por exemplo, profissionais de apoio. Série histórica que atravesse
2020 e compare os dois percentuais como se fossem o mesmo indicador está comparando
coisas diferentes.

### 2.3 Transferências federais específicas

São recursos do FNDE, em grande parte originados da contribuição social do
salário-educação (art. 212, §5º, da CF). Não entram na base do MDE e, em regra, não
podem ser usados para cumpri-lo.

**Repasses federais aos municípios do ES** *(fonte: CGU, Portal da Transparência — lado pagador; R$ milhões)*

| Programa | 2021 | 2022 | 2023 | 2024 | 2025 | Total |
|---|---:|---:|---:|---:|---:|---:|
| Salário-educação | 121,3 | 139,2 | 169,6 | 263,9 | 282,8 | **976,8** |
| Complementação FUNDEB | — | 97,1 | 139,1 | 273,1 | 317,2 | **826,5** |
| PNAE (alimentação escolar) | 58,5 | 49,1 | 72,2 | 73,2 | 78,5 | **331,5** |
| PDDE (dinheiro direto na escola) | 33,0 | 33,5 | 28,9 | 28,2 | 30,4 | **153,9** |
| PNATE (transporte escolar) | 13,4 | 15,2 | 17,3 | 15,6 | 12,3 | **73,8** |
| Outras do FNDE | — | — | — | 38,2 | 21,8 | **60,0** |

**Uma armadilha de conciliação.** Esses valores são o **lado federal**, por mês de
pagamento. O mesmo programa aparece com outro valor na contabilidade do município (MSC,
fontes 550–553) e um terceiro na declaração ao SIOPE, porque o município e o SIOPE
incluem os **rendimentos de aplicação financeira** da conta do programa, e a CGU não.
Divergência entre os três é esperada; divergência **grande** é que merece exame.

**O PDDE quase não transita pelo orçamento municipal.** Ele é pago diretamente às
unidades executoras — conselhos escolares, caixas escolares, associações de pais e
mestres —, que têm CNPJ próprio e prestam contas ao FNDE, não ao município. Nos dados do
ES, R$ 153,9 milhões em 2021–2025 foram pagos a **2.301 unidades executoras**. Para o
controle externo isso significa que o PDDE **não aparece** na despesa da função 12 do
município e não pode ser auditado pelos empenhos municipais.

### 2.4 Outras fontes

- **Recursos próprios não vinculados** (a categoria "outras" da tabela de origem) — a
  maior fatia da receita municipal total: R$ 17,78 bilhões em 2025, contra R$ 5,06 bi de
  impostos próprios e R$ 4,70 bi de FUNDEB. Inclui as transferências de impostos (FPM,
  cota-parte do ICMS), royalties, receitas patrimoniais e de serviços. Parte dela compõe
  a base do MDE; parte não.
- **Convênios e programas estaduais.** No ES o canal estadual identificável nos dados
  abertos é o **FUNPAES** (Fundo de Apoio à Educação do Estado), reconhecível pelo nome
  na ação, no programa ou no detalhamento da fonte:

  | Ano | Municípios | Lançamentos | Empenhado | Pago |
  |---|---:|---:|---:|---:|
  | 2022 | 7 | 31 | R$ 4.503.400,00 | R$ 2.035.835,00 |
  | 2023 | 9 | 69 | R$ 17.054.312,00 | R$ 9.185.436,00 |
  | 2024 | 10 | 54 | R$ 23.337.171,00 | R$ 16.861.798,00 |

  Exemplo concreto (Alto Rio Novo, 2023): "REFORMA E AMPLIAÇÃO DA EMEF GUSTAVO AMBRUST",
  fonte 701, credor CONSTRUTORA BICU LTDA — R$ 1.506.420,00 empenhados e R$ 655.255,55
  pagos no exercício. A defasagem entre empenhado e pago em obra é normal (a medição
  precede o pagamento); o que se examina é se ela persiste por exercícios.

  **Limitação:** a identificação do FUNPAES é **por nome**, não por código. Município que
  registre o convênio estadual sem nomeá-lo não aparece nesta contagem. Ausência aqui não
  é ausência de recurso estadual.

### 2.5 O quadro de receita, em uma tabela

**Origem da receita total dos 78 municípios** *(R$ milhões; "outras" é calculada por diferença)*

| Origem | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|
| Impostos próprios | 2.662,6 | 3.221,4 | 3.872,1 | 4.562,5 | 5.056,9 |
| FUNDEB | 2.788,2 | 3.196,4 | 3.546,8 | 4.206,5 | 4.699,5 |
| Federais específicas | 193,6 | 204,0 | 259,5 | 353,0 | 373,8 |
| Outras | 10.562,4 | 13.111,8 | 14.970,9 | 16.562,7 | 17.777,7 |
| **Total** | **16.206,7** | **19.733,6** | **22.649,3** | **25.684,7** | **27.907,9** |

---

## 3. As despesas

Toda despesa pública é classificada em vários eixos simultâneos. Os quatro que importam
aqui respondem a perguntas diferentes, e confundi-los é a origem de boa parte das
análises erradas.

| Eixo | Pergunta que responde | Onde está |
|---|---|---|
| **Funcional** (função, subfunção) | Em que área? | DCA Anexo I-E |
| **Natureza da despesa** (categoria, grupo, modalidade, elemento) | Em que tipo de gasto? | MSC / empenhos |
| **Fonte de recursos** | Com dinheiro de quem? | MSC / empenhos |
| **Programática** (programa, ação) | Dentro de qual política? | PPA/LOA, dados do TCE-ES |

### 3.1 Função e subfunção

A **função 12** é Educação. As subfunções repartem-na por etapa:

**Municípios do ES — despesa empenhada por subfunção** *(DCA Anexo I-E, R$ milhões)*

| Subfunção | 2021 | 2022 | 2023 | 2024 | 2025 | Total |
|---|---:|---:|---:|---:|---:|---:|
| 12.361 Ensino Fundamental | 2.513,6 | 3.074,8 | 3.658,5 | 4.428,9 | 4.614,6 | **18.290,4** |
| 12.365 Educação Infantil | 1.255,2 | 1.584,4 | 1.920,8 | 2.154,1 | 2.341,2 | **9.255,7** |
| 12.122 Administração Geral | 321,1 | 595,2 | 521,8 | 655,5 | 738,7 | **2.832,3** |
| Demais subfunções | 93,4 | 129,6 | 136,8 | 134,6 | 164,9 | **659,3** |
| 12.367 Educação Especial | 37,9 | 72,3 | 95,0 | 124,6 | 146,7 | **476,4** |
| 12.364 Ensino Superior | 32,0 | 37,6 | 46,8 | 64,1 | 52,5 | **233,0** |
| 12.362 Ensino Médio | 17,2 | 33,7 | 41,7 | 43,8 | 50,1 | **186,4** |
| 12.366 EJA | 16,2 | 21,4 | 22,0 | 19,4 | 20,8 | **99,8** |
| 12.368 Educação Básica | 3,1 | 5,7 | 20,1 | — | — | **28,9** |
| 12.363 Ensino Profissional | 0,2 | 0,8 | 1,0 | 1,2 | 1,2 | **4,3** |

Três leituras que a tabela sustenta:

1. **O município capixaba gasta onde a Constituição mandou que gastasse.** Fundamental e
   Infantil são 85,9% do total — coerente com o art. 211, §2º, que atribui aos municípios a
   atuação prioritária no ensino fundamental e na educação infantil.
2. **Ensino Médio e Superior na despesa municipal merecem exame.** São R$ 186,4 milhões e
   R$ 233,0 milhões em cinco anos, em subfunções cuja competência é, respectivamente,
   estadual e federal/estadual. Não é irregular por si — o art. 211, §2º, permite atuação
   em outros níveis **desde que atendidas plenamente as necessidades da área prioritária
   e com recursos acima dos percentuais mínimos**. É exatamente essa condição que o teste
   deve verificar.
3. **Administração Geral (12.122) cresceu 130% em cinco anos**, mais rápido que o total.
   Vale examinar o que está sendo classificado ali.

O Estado do ES tem perfil espelhado, como esperado: Ensino Médio (R$ 5,87 bi em cinco
anos) quase empata com Ensino Fundamental (R$ 5,91 bi), este último resultado do estoque
histórico de escolas estaduais de fundamental ainda não municipalizadas.

### 3.2 Natureza econômica

**Municípios do ES — despesa da função 12 por categoria** *(MSC, R$ milhões e % do ano)*

| Categoria | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|
| Pessoal e encargos | 2.537,2 *(59,1%)* | 3.132,9 *(56,4%)* | 3.620,7 *(56,0%)* | 4.035,9 *(52,9%)* | 4.450,2 *(54,7%)* |
| Custeio | 1.294,4 *(30,2%)* | 1.908,7 *(34,4%)* | 2.242,9 *(34,7%)* | 2.759,0 *(36,2%)* | 2.985,9 *(36,7%)* |
| Investimento | 447,0 *(10,4%)* | 503,9 *(9,1%)* | 601,0 *(9,3%)* | 831,3 *(10,9%)* | 694,4 *(8,5%)* |

**Pessoal é a maior parte da despesa e a menos visível no dado aberto.** Os empenhos do
TCE-ES não trazem a lotação do servidor, de modo que **não é possível calcular custo de
pessoal por escola** a partir das fontes usadas aqui. Isso limita qualquer análise de
custo-aluno por unidade: o numerador exclui mais da metade do gasto.

**Composição do custeio, 2021–2025** *(R$ milhões)*

| Subcategoria | Total | O que costuma haver aí |
|---|---:|---|
| Serviços de terceiros — PJ | 4.234,8 | transporte escolar terceirizado, limpeza, vigilância, manutenção |
| Auxílios (elementos 46/49) | 1.801,3 | auxílio-alimentação e transporte de servidores |
| Material de consumo | 1.708,2 | gêneros alimentícios, material escolar, expediente |
| Locação de mão de obra | 1.161,5 | merendeiras, auxiliares, porteiros terceirizados |
| Outras despesas correntes | 848,9 | — |
| Transferências a entidades sem fins lucrativos | 529,0 | **creches conveniadas e filantrópicas** |
| Distribuição gratuita | 492,3 | kits escolares, uniformes |
| Serviços de terceiros — PF | 253,6 | — |
| TIC | 161,0 | — |

A linha de **transferências a entidades sem fins lucrativos** (modalidade de aplicação
50) merece atenção particular: R$ 529 milhões em cinco anos. É o canal das creches
conveniadas, regido pelo art. 213 da CF e pelo marco regulatório das organizações da
sociedade civil. Exige verificação de plano de trabalho, prestação de contas e, no caso
de vagas de educação infantil, de que a entidade atenda aos requisitos do art. 213, I e II.

**Investimento por elemento, 2021–2025:** obras e instalações (elemento 51)
R$ 1.754,9 milhões; equipamentos e material permanente (elemento 52) R$ 1.017,5 milhões.

### 3.3 Fonte de recursos → destino

Cada empenho carrega o código da fonte que o paga. A ligação entre origem e destino é,
portanto, **declarada pelo município**, não estimada por proporção — é o dado mais forte
disponível para a pergunta "com dinheiro de quem isso foi pago?".

**Municípios do ES — despesa da função 12 por grupo de fonte** *(MSC, R$ milhões)*

| Grupo de fonte | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|
| FUNDEB (540–543) | 2.955,8 | 3.370,9 | 3.973,4 | 4.417,2 |
| Impostos (500) | 1.679,8 | 2.056,6 | 2.298,7 | 2.530,6 |
| Federais específicas (550–553, 569) | 249,6 | 333,8 | 380,0 | 465,3 |
| Outras | 649,7 | 703,4 | 973,9 | 717,4 |

**Duas limitações que mudam a leitura.** A primeira: esse recorte **só existe de 2022 em
diante**. Em 2021, 77 dos 78 municípios ainda usavam códigos locais de 8 dígitos, antes
da padronização da STN (Portaria STN nº 710/2021) — o painel diz "sem dado" em vez de
converter por palpite. A segunda: a **fonte 500 junta impostos próprios e transferências
de impostos**. A contabilidade não os separa, e dividi-los seria estimativa.

### 3.4 O que é e o que não é MDE

Esta é a distinção que mais produz divergência entre a apuração do município e a do
Tribunal. A LDB (Lei 9.394/1996) define nos arts. 70 e 71.

**Art. 70 — conta como MDE** (despesas para a consecução dos objetivos básicos das
instituições educacionais): remuneração e aperfeiçoamento do pessoal docente e demais
profissionais da educação; aquisição, manutenção, construção e conservação de instalações
e equipamentos necessários ao ensino; uso e manutenção de bens vinculados ao sistema;
levantamentos estatísticos e estudos voltados à melhoria do ensino; realização de
atividades-meio necessárias ao funcionamento dos sistemas; concessão de bolsas de estudo
a alunos de escolas públicas e privadas; amortização e custeio de operações de crédito
destinadas ao ensino; aquisição de material didático-escolar e manutenção de programas
de transporte escolar.

**Art. 71 — NÃO conta como MDE:**

| Inciso | Não é MDE | Por que isso importa na prática |
|---|---|---|
| I | Pesquisa não vinculada às instituições de ensino | raro nos municípios |
| II | Subvenção a instituições de caráter assistencial, desportivo ou cultural | separa escola de entidade assistencial |
| III | Formação de quadros para a administração pública | — |
| IV | **Programas suplementares de alimentação, assistência médico-odontológica, farmacêutica e psicológica, e outras formas de assistência social** | **a merenda escolar não é MDE** — é uma das reclassificações mais frequentes |
| V | **Obras de infraestrutura, ainda que beneficiem a rede escolar** | pavimentar a rua da escola não é MDE |
| VI | Pessoal docente e demais trabalhadores **em desvio de função** ou em atividade alheia à MDE | exige confronto entre lotação e atividade real |

Os incisos IV e V são a fonte clássica de glosa. E note a assimetria: merenda **não é
MDE**, mas **é** despesa da função 12 e **pode** ser custeada com FUNDEB e com PNAE. O
mesmo real aparece como despesa legítima num demonstrativo e como despesa glosada no
outro. Não há contradição — há regras diferentes para perguntas diferentes.

### 3.5 O nível do item: credor, ação, contrato, obra

Nenhuma fonte **nacional** publica a despesa da educação empenho a empenho. No Espírito
Santo, os dados abertos do TCE-ES publicam — é a vantagem estrutural de quem audita neste
estado. O dado é **declaratório** (o que o município remete via CidadES), e o que lhe dá
lastro é o cruzamento: a soma dos empenhos da função 12 bate ao centavo com o DCA Anexo
I-E em **354 de 365 município-anos** testados.

O que isso abre:

- **Credores.** Exemplo (Guaçuí, 2024): a COOP. DE TRANSPORTE DA REGIÃO SUL — COOPERSULES
  recebeu R$ 5.319.692,92 empenhados em 81 empenhos, no elemento "outros serviços de
  terceiros — pessoa jurídica". É o terceiro maior credor da educação do município,
  atrás apenas de duas rubricas de folha.
- **Ações orçamentárias**, com dotação inicial, dotação atualizada e empenhado — o teste
  de orçado × executado ([§5.4](#54-índices-de-execução)).
- **Itens contratados**, com descrição, unidade, quantidade e **preço unitário** — a base
  de qualquer comparação de preços entre municípios ([§6.3](#63-os-testes-que-o-dado-sustenta)).
- **Obras**, com objeto, contratada, valor inicial e atual, situação, vigência, medições,
  aditivos e links do contrato e do edital.
- **Repasses do município a conselhos escolares** — o "PDDE municipal".

**Cobertura dos itens, e por que ela é desigual.** São 121.534 itens da Educação em
2022–2025, R$ 4,86 bilhões contratados, em 77 dos 78 municípios. Mas o recorte da
Educação depende de três marcas que a própria fonte precisa afirmar: a unidade gestora
ser de educação, a contratação ter `SetorBeneficiado = Educação`, ou o instrumento ser
obra da Educação. O campo `SetorBeneficiado` vem **vazio em 90% das contratações** (só as
obras o preenchem por obrigação) e apenas **22 municípios têm unidade gestora própria de
educação**. Município que compra pela unidade gestora da prefeitura sem marcar o setor
**não aparece**.

> **Regra de leitura:** ausência de item **não é ausência de compra**.

---

## 4. O marco normativo

### 4.1 Constituição Federal

| Dispositivo | Conteúdo | Uso na fiscalização |
|---|---|---|
| **Art. 205–208** | Direito à educação; dever do Estado; educação básica obrigatória dos 4 aos 17 anos | fundamenta testes de cobertura e de vaga |
| **Art. 211** | Regime de colaboração. §2º: municípios atuam **prioritariamente** no ensino fundamental e na educação infantil. §3º: estados no fundamental e médio. §7º: padrão mínimo de qualidade (CAQ), incluído pela EC 108/2020 | base do exame de despesa municipal em ensino médio/superior |
| **Art. 212** | **25%** da receita resultante de impostos em MDE (União: 18%) | o mínimo central |
| **Art. 212, §5º** | Salário-educação como fonte adicional | origem dos repasses do FNDE |
| **Art. 212-A** | FUNDEB permanente (EC 108/2020). Inciso V: complementação da União ≥ 23%, nos canais VAAF/VAAT/VAAR. Inciso XI: **≥ 70%** para remuneração dos profissionais da educação básica em efetivo exercício | o segundo mínimo |
| **Art. 213** | Recursos públicos às escolas públicas, podendo dirigir-se a escolas comunitárias, confessionais e filantrópicas | exame das creches conveniadas |
| **Art. 214** | Plano Nacional de Educação | metas e prazos |
| **ADCT, art. 119** (EC 119/2022) | Quem não cumpriu o art. 212 em **2020 e 2021** pode compensar a diferença **até 2023**, sem responsabilização | decisivo para avaliar os exercícios de 2020–2021 |

**A EC 119/2022 na prática.** Dez municípios do ES ficaram abaixo de 25% em 2021 — ano
coberto pela emenda. O teste correto para esses casos não é o percentual de 2021 isolado,
e sim se a compensação foi feita até 2023. Nos dados, **7 municípios tinham diferença a
compensar em 2023**; dois deles não alcançaram o valor exigido com a compensação incluída,
embora seu percentual do próprio ano de 2023 estivesse acima de 25%:

| Município | Aplicado em 2023 | Exigido com a compensação | % do ano |
|---|---:|---:|---:|
| Guarapari | R$ 71,2 milhões | R$ 83,0 milhões | acima de 25% |
| Ibatiba | R$ 15,9 milhões | R$ 19,6 milhões | acima de 25% |

Quem olhasse apenas o percentual de 2023 concluiria que ambos estavam em ordem.

### 4.2 LDB — Lei 9.394/1996

Arts. 68 a 77 tratam dos recursos financeiros. Os operacionais são o **art. 70** (o que é
MDE), o **art. 71** (o que não é) e o **art. 69, §5º**, que fixa prazo para o repasse dos
recursos vinculados ao órgão gestor da educação — um teste de tempestividade
frequentemente esquecido.

### 4.3 FUNDEB — Lei 14.113/2020

Regulamenta o art. 212-A. Trata da composição dos fundos, da ponderação por etapa e
modalidade, dos três canais de complementação, das destinações mínimas do VAAT, do
controle social pelos conselhos do FUNDEB e do regime de aplicação do saldo remanescente
ao fim do exercício. Substituiu a Lei 11.494/2007, que regulava o FUNDEB anterior.

**Para séries históricas:** o corte é 2020/2021. Antes, 60% para magistério (Lei
11.494/2007); depois, 70% para profissionais da educação básica (art. 212-A, XI).

### 4.4 LRF e os prazos — LC 101/2000

| Relatório | Prazo | Fundamento |
|---|---|---|
| **RREO** (bimestral) | 30 dias após o encerramento do bimestre | art. 52 |
| **RGF** (quadrimestral; semestral por opção dos municípios com menos de 50 mil habitantes) | 30 dias após o encerramento do período | art. 55, §2º, e art. 63 |
| **Contas anuais (DCA)** | até 30 de abril do ano seguinte | art. 51, §1º, I |

Prazo que cai em fim de semana **não é prorrogado** — a LRF não prevê prorrogação.

**Entregas ao SICONFI, 78 municípios** *(Prefeitura e Câmara; extrato de entregas)*

| Ano | No prazo | Com atraso | Retificado | Municípios com ≥ 1 atraso | Atraso médio | Atraso máximo |
|---|---:|---:|---:|---:|---:|---:|
| 2021 | 477 | 378 | 59 | 75 | 34,9 dias | 241 dias |
| 2022 | 466 | 337 | 107 | 74 | 38,2 dias | 424 dias |
| 2023 | 529 | 334 | 39 | 72 | 33,5 dias | 251 dias |
| 2024 | 549 | 330 | 29 | 70 | 37,7 dias | 297 dias |
| 2025 | 563 | 322 | 15 | 67 | 25,4 dias | 129 dias |

O atraso é **generalizado e quase sempre pequeno**: a maior parte é de poucos dias, o que
torna a contagem bruta de atrasos um indicador pobre. O que discrimina é a **cauda**. Os
maiores atrasos medidos:

| Município | Ano | Poder | Relatório | Período | Prazo | Entregue | Atraso |
|---|---|---|---|---|---|---|---:|
| Iúna | 2022 | Câmara | RGF | 1º | 30/05/2022 | 28/07/2023 | **424 dias** |
| São Domingos do Norte | 2022 | Prefeitura | RREO | 6º | 30/01/2023 | 06/12/2023 | 310 dias |
| Iúna | 2022 | Câmara | RGF | 2º | 30/09/2022 | 28/07/2023 | 301 dias |
| Jerônimo Monteiro | 2024 | Prefeitura | RREO | 1º | 30/03/2024 | 21/01/2025 | 297 dias |

Por tipo de relatório, em 2021–2025: o **DCA é entregue no prazo** (350 de 390), enquanto
RREO (901 atrasos) e RGF (766) concentram o problema. Faz sentido — a conta anual tem
consequência imediata para o ente; os bimestrais, não.

> **Cuidado metodológico.** A data do extrato é a do **status atual**. Uma retificação
> substitui a data original, de modo que **não se pode afirmar atraso de relatório
> retificado** — por isso a coluna "retificado" fica separada, e não somada aos atrasos.

### 4.5 Contabilidade e classificação

| Norma | O que fixa |
|---|---|
| **Lei 4.320/1964** | Normas gerais de direito financeiro; estágios da despesa — empenho (arts. 58–61), liquidação (arts. 62–63), pagamento (art. 64); restos a pagar (art. 36) |
| **Portaria Interministerial STN/SOF nº 163/2001** | Natureza da despesa: categoria, grupo, modalidade de aplicação, elemento |
| **Portaria STN nº 710/2021** e atualizações | Padronização das fontes/destinações de recursos — a que tornou possível o fluxo fonte→destino de 2022 em diante |
| **MCASP / PCASP** | Plano de contas e procedimentos contábeis aplicados ao setor público |

**Os três estágios importam para a leitura de qualquer número.** *Empenhado* é o
compromisso; *liquidado* é o reconhecimento de que o serviço foi prestado ou o bem
entregue; *pago* é a saída do caixa. O MDE é apurado sobre despesa empenhada, o que
significa que **empenhar no fim do exercício cumpre o mínimo formalmente**, ainda que
nada tenha sido entregue. Daí a relevância do teste de restos a pagar
([§5.4](#54-índices-de-execução)).

> **Um equívoco comum.** A "classe 3/4" relevante para separar corrente de capital é a
> **categoria econômica da natureza da despesa**. No PCASP, as classes 3 e 4 são as
> variações patrimoniais (VPD/VPA) — outra coisa inteiramente.

### 4.6 Contratos e obras

**Lei 14.133/2021** (e, para contratos ainda regidos por ela, a Lei 8.666/1993): projeto
básico, pesquisa de preços, limites de aditivo (25% em regra, 50% para reforma de
edifício), fiscalização do contrato e recebimento provisório e definitivo.

Para obras de educação no ES, os dados abertos do TCE-ES trazem valor inicial e atual,
número de aditivos, medições e situação — o que permite testar **acréscimo contratual**
diretamente:

| Município | Objeto (resumido) | Valor inicial | Valor atual | Acréscimo | Aditivos |
|---|---|---:|---:|---:|---:|
| Vila Valério | Reforma da antiga creche EMEI Otília Breda de Martins | R$ 140.804,40 | R$ 349.972,68 | **+148,6%** | 7 |
| Presidente Kennedy | Reforma e ampliação de 3 unidades (EMEIEF São Salvador e outras) | R$ 3.422.214,40 | R$ 7.310.530,12 | +113,6% | 11 |
| Iconha | Reforma e ampliação da EMPEF Marcelino Biancardi e quadra | R$ 5.687.446,85 | R$ 11.522.476,12 | +102,6% | 3 |
| Presidente Kennedy | Mesmo objeto acima, outra contratada | R$ 6.672.457,43 | R$ 13.359.837,93 | +100,2% | **21** |
| Vitória | Registro de preços — manutenção de unidades de ensino (lotes 1–3) | R$ 24.049.991,25 | R$ 47.164.399,28 | +96,1% | 3 |

> **Não conclua irregularidade a partir desta tabela.** Registro de preços e contratos
> com escopo aberto admitem acréscimo por natureza; parte dos aditivos é de prazo, não de
> valor; e reforma tem limite legal mais alto. O que a tabela produz é **uma lista de
> contratos a examinar**, com o documento já linkado. Um contrato com 21 aditivos e valor
> dobrado é uma pergunta, não uma resposta.

### 4.7 Normativos do TCE-ES

- **Lei Complementar Estadual nº 621/2012** — Lei Orgânica do Tribunal.
- **IN TC nº 68/2020** — CidadES / Prestação de Contas Municipal: a remessa mensal cujo
  cumprimento é medido em [§5.4](#54-índices-de-execução).
- **Resolução TC nº 358/2021** — tratamento de dados pessoais (LGPD). É o fundamento de
  não nominar pessoa física nos produtos: no painel, credores pessoa física são agregados
  numa linha única, nunca identificados.
- **Resolução TC nº 379/2024** — encerramento de sistema de acompanhamento de obras.

### 4.8 Programas federais e o CNCA

- **PNAE** — alimentação escolar (Lei 11.947/2009), com a exigência de no mínimo 30% em
  gêneros da agricultura familiar.
- **PNATE** — transporte escolar.
- **PDDE** — Lei 11.947/2009, pago diretamente às unidades executoras.
- **CNCA — Compromisso Nacional Criança Alfabetizada**: Decreto nº 11.556/2023 (o art. 12
  trata das obrigações dos entes aderentes), Portaria MEC nº 1.774/2023 e Resolução
  CD/FNDE nº 22/2023 (PDDE-Alfabetização). No ES, os repasses do CNCA chegam por dois
  canais distintos: **PDDE-CNCA** diretamente às escolas (plano orçamentário 000C) e
  **apoio ao Estado** (planos 0509/0014).

---

## 5. Os índices

### 5.1 Os mínimos legais

**MDE — 25% da receita resultante de impostos** (art. 212 da CF). Apurado pelo SIOPE, no
RREO Anexo 8, e separadamente pelo TCE-ES.

*Abaixo do mínimo, 2021–2025, apuração do SIOPE:*

| Município | Ano | SIOPE | TCE-ES |
|---|---|---:|---:|
| Guarapari | 2021 | 18,81% | 18,63% |
| São Mateus | 2021 | 19,32% | 19,32% |
| Conceição da Barra | 2021 | 21,72% | 20,25% |
| Linhares | 2021 | 22,29% | 22,29% |
| Rio Bananal | 2021 | 23,14% | 23,14% |
| Ibatiba | 2021 | 23,88% | 23,75% |
| Alegre | 2021 | 24,40% | 24,34% |
| Bom Jesus do Norte | 2021 | 24,50% | 24,31% |
| Castelo | 2021 | 24,77% | 24,77% |
| Água Doce do Norte | 2021 | 24,86% | 24,81% |
| **Guaçuí** | **2024** | **22,42%** | **22,42%** |
| **Linhares** | **2024** | **24,98%** | 25,02% |

Os dez casos de 2021 estão cobertos pela EC 119/2022 (ver [§4.1](#41-constituição-federal)).
Os de 2024 **não estão** — e Guaçuí é o único em que as duas apurações concordam
exatamente sobre o descumprimento.

*Distribuição do MDE (SIOPE), 78 municípios:*

| Ano | Mínimo | Mediana | Máximo | Média |
|---|---:|---:|---:|---:|
| 2021 | 18,81% | 26,96% | 31,60% | 26,75% |
| 2022 | 25,14% | 28,82% | 40,54% | 29,60% |
| 2023 | 25,00% | 28,91% | 43,79% | 29,59% |
| 2024 | 22,42% | 27,10% | 38,77% | 27,94% |
| 2025 | 25,08% | 27,02% | 34,50% | 27,58% |

Note o **empilhamento logo acima de 25%**: o mínimo de 2023 é 25,00% e o de 2025 é
25,08%. O piso constitucional funciona, na prática, como a meta — não como o piso.

**FUNDEB — 70% na remuneração dos profissionais da educação básica** (art. 212-A, XI).

Abaixo de 70%: seis municípios, todos em 2021 — Apiacá (66,00%), Castelo (68,10%),
Conceição da Barra (68,40%), Jerônimo Monteiro (68,91%), Afonso Cláudio (69,48%) e
Aracruz (69,72%). **Nenhum de 2022 a 2025.**

Mas a distribuição revela o oposto do problema:

| Ano | Mínimo | Mediana | Máximo |
|---|---:|---:|---:|
| 2021 | 66,00% | 72,53% | 99,41% |
| 2022 | 70,00% | 78,50% | **100,00%** |
| 2023 | 70,00% | 81,60% | **100,00%** |
| 2024 | 70,02% | 80,77% | **100,00%** |
| 2025 | 70,15% | 80,27% | **100,00%** |

**Município com 100,00% do FUNDEB em remuneração é um sinal, não uma virtude.** Significa
que nada do fundo sobrou para material, transporte, manutenção ou investimento — e, se o
percentual é exatamente 100,00%, significa provavelmente que a declaração classificou
como remuneração tudo o que o fundo pagou. Vale o mesmo para os mínimos exatos de 70,00%.
Os dois extremos merecem exame; o meio da distribuição, não.

### 5.2 Índices de resultado

| Índice | O que mede | Periodicidade | Observação para o ES |
|---|---|---|---|
| **IDEB** | Fluxo × proficiência (SAEB), anos iniciais e finais | bienal | série deslocada: o IDEB de um ano refere-se ao SAEB do ano anterior |
| **ICA** | % de alunos alfabetizados ao fim do 2º ano (corte de 743 pontos no SAEB) | anual | indicador do CNCA; metas pactuadas até 2030 |
| **SAEB** | Proficiência | bienal | no ES, utilizável por município (não por escola, no recorte disponível) |
| **PAEBES** | Avaliação estadual capixaba | anual | no banco local, carregado para o 5º ano de 2025 |

**ICA nos 78 municípios do ES** *(INEP; % de alunos alfabetizados ao fim do 2º ano)*

| Ano | Mínimo | Mediana | Máximo | Média |
|---|---:|---:|---:|---:|
| 2023 | 46 | 74 | 92 | 73,6 |
| 2024 | 57 | 80 | 95 | 78,2 |
| 2025 | 64 | 83 | 99 | 83,6 |

Em 2025, os extremos: Serra (64), Cariacica (68) e Apiacá (71) na base; Águia Branca (99),
Mantenópolis (97), Laranja da Terra e Alto Rio Novo (96) no topo. A meta pactuada
converge para 80 em 2030 em todos os municípios — o que significa que **vários já a
superaram**, e que a meta, para estes, deixou de ser informativa.

> **Não estabeleça relação causal entre repasse e resultado.** Serra e Cariacica têm as
> duas maiores redes municipais do estado e os dois menores ICA; Águia Branca e
> Mantenópolis têm redes pequenas e os maiores. Tamanho da rede, perfil socioeconômico e
> participação na avaliação explicam boa parte disso. Um painel pode mostrar dinheiro e
> resultado lado a lado; uma conclusão de que um causa o outro exige desenho de pesquisa
> que estes dados não sustentam.

### 5.3 Índices de custo

Dois denominadores, que medem coisas diferentes:

- **Por matrícula** — despesa em educação ÷ matrículas da rede municipal. É o mais
  próximo do serviço prestado e o único cujo denominador muda todo ano.
- **Per capita** — despesa em educação ÷ população. A população do SICONFI só muda a cada
  dois exercícios, o que cria degraus artificiais na série.

**Despesa em educação por matrícula, 2025** — média R$ 18.156, mediana R$ 17.829.

| Extremos inferiores | | Extremos superiores | |
|---|---:|---|---:|
| Cariacica | R$ 11.337,05 | Ibitirama | R$ 24.086,07 |
| Guarapari | R$ 11.343,44 | Mucurici | R$ 24.124,34 |
| Viana | R$ 11.631,29 | Marilândia | R$ 24.838,01 |
| Barra de São Francisco | R$ 12.127,06 | Divino de São Lourenço | R$ 28.855,25 |
| Linhares | R$ 12.381,84 | **Presidente Kennedy** | **R$ 61.057,52** |

Presidente Kennedy gasta **3,4 vezes a mediana** por matrícula. A explicação é de
receita, não de gestão: o município é o maior beneficiário de royalties de petróleo do
estado, e seus impostos próprios são 51,3% da base do MDE — perfil de município rico com
rede pequena. O indicador é válido; a leitura ingênua ("gasta melhor") não é.

Na outra ponta, o custo baixo das redes grandes da Região Metropolitana reflete ganho de
escala real e, possivelmente, subfinanciamento — são hipóteses concorrentes que o número
sozinho não separa.

> O denominador de matrículas usado é a coluna `Alunos` do recurso *Educação* do TCE-ES,
> **conferida contra a soma do Censo Escolar** por município: bateu em 78 de 78, ao aluno.
> O Estado fica sem este indicador — a fonte do Tribunal cobre apenas municípios.

### 5.4 Índices de execução

Aqui estão os indicadores que mais discriminam entre municípios, e os menos usados.

**a) Orçado × executado.** No conjunto das ações da Educação, a execução é alta e estável
(90–94% da dotação atualizada). Mas isolando as **ações de obra**, ela despenca:

| Ano | Dotação atualizada | Empenhado | Execução | Liquidado |
|---|---:|---:|---:|---:|
| 2021 | R$ 326,6 mi | R$ 180,3 mi | **55,2%** | R$ 153,6 mi |
| 2022 | R$ 533,8 mi | R$ 299,7 mi | **56,1%** | R$ 226,3 mi |
| 2023 | R$ 785,5 mi | R$ 424,8 mi | **54,1%** | R$ 286,8 mi |
| 2024 | R$ 844,0 mi | R$ 588,3 mi | **69,7%** | R$ 470,1 mi |
| 2025 | R$ 845,1 mi | R$ 528,6 mi | **62,5%** | R$ 425,9 mi |

Em cinco anos, R$ 3,33 bilhões orçados em ações de obra contra R$ 2,02 bilhões empenhados.
Casos individuais extremos (2024–2025, ações com dotação ≥ R$ 5 milhões):

| Município | Ano | Ação | Dotação atualizada | Empenhado | Execução |
|---|---|---|---:|---:|---:|
| Cariacica | 2024 | Aprimorar a infraestrutura tecnológica da rede municipal | R$ 6.062.676,00 | R$ 0,00 | **0,0%** |
| Castelo | 2024 | Investimentos — Educação Infantil | R$ 5.212.800,00 | R$ 0,00 | **0,0%** |
| Ecoporanga | 2025 | Construção, melhoria e reforma da rede física do fundamental | R$ 6.319.905,60 | R$ 364.634,00 | 5,8% |
| Aracruz | 2024 | Construção, reforma, ampliação e equipamentos do fundamental | R$ 15.804.620,60 | R$ 1.667.692,80 | 10,6% |
| Anchieta | 2025 | Construção, reforma, ampliação de prédios escolares | R$ 10.889.485,00 | R$ 1.614.960,90 | 14,8% |

**b) Concentração de empenho em novembro e dezembro** (subfunção 361, base ≥ R$ 1 milhão).
Se a despesa fosse uniforme, novembro e dezembro seriam ~16,7%.

| Ano | Mediana | Máximo |
|---|---:|---:|
| 2021 | 23,8% | 47,8% |
| 2022 | 16,5% | 30,5% |
| 2023 | 14,2% | 26,2% |
| 2024 | 17,2% | 32,3% |
| 2025 | 18,7% | 37,9% |

Maiores concentrações medidas: João Neiva 2021 (47,8% — R$ 5,45 mi de R$ 11,41 mi),
Vila Valério 2021 (43,3%), Montanha 2021 (41,6%), Vitória 2021 (37,7% — R$ 100,7 mi de
R$ 266,8 mi), Ibiraçu 2025 (37,9%).

> **Julgue contra a mediana do próprio exercício, não contra um número fixo.** 2021 foi
> um ano atípico em todo o estado (mediana 23,8%), por razões que atravessaram todos os
> municípios. Um município com 25% em 2021 era mediano; o mesmo 25% em 2023 estaria bem
> acima da mediana de 14,2%.

**c) Restos a pagar antigos ainda em movimentação.** Empenhos de exercícios distantes que
continuam sendo liquidados, pagos ou cancelados:

| Município | Ano de empenho | Movimentado | Idade |
|---|---|---:|---:|
| Vila Velha | 2018 | R$ 8.607.327,00 | 6 anos |
| Vila Velha | 2019 | R$ 6.341.254,00 | 6 anos |
| Vila Velha | 2017 | R$ 979.899,00 | 7 anos |
| Conceição da Barra | 2017 | R$ 550.289,00 | 7 anos |

São 397 lançamentos em 63 municípios, com empenhos de origem que remontam a 2011.
Cancelamentos de restos a pagar não processados da função 12 somaram R$ 75,5 milhões em
2025 e R$ 69,0 milhões em 2023. **Restos a pagar cancelados anos depois, em despesa que
compôs o MDE do exercício de origem, é um dos testes mais produtivos que existem** — e um
dos motivos pelos quais a apuração do TCE-ES diverge da do SIOPE.

> **Limitação medida:** as colunas de *inscrição* em restos a pagar vêm zeradas nesta
> extração da MSC, de modo que não se pode calcular a razão cancelado/inscrito. Os valores
> de cancelamento e a idade são confiáveis; a taxa, não. Use os primeiros.

**d) Remessa mensal ao TCE-ES** (CidadES/PCM, IN TC 68/2020; janela de 08/2025 a 08/2026):

| Situação | Ocorrências |
|---|---:|
| No prazo | 7.213 |
| Prazo ainda aberto | 2.256 |
| **UG sem nenhuma remessa na janela** | **935** |
| Homologada com atraso | 87 |
| Vencida sem homologação | 32 |

As 935 ocorrências de "UG sem remessa" correspondem a 55 unidades gestoras de 11
municípios que **nunca** aparecem homologadas na janela inteira. O padrão sugere conta
consolidada em outra unidade gestora — e por isso são contadas **à parte**, não como
atraso. É uma pergunta a confirmar com o Tribunal, não um achado.

---

## 6. A auditoria: como o dado vira (ou não vira) achado

### 6.1 As fontes e o que cada uma aguenta

| Fonte | O que dá | Natureza | Limite duro |
|---|---|---|---|
| **SICONFI** (Tesouro) | DCA, RREO, MSC, extrato de entregas | declaratório, nacional | **não publica o RREO Anexo 08** — o MDE não está lá |
| **SIOPE** (FNDE) | RREO Anexo 8: MDE e FUNDEB 70% já apurados | declaratório | só por **PDF** em FTP; layout mudou 2× em cinco anos |
| **CGU** (Portal da Transparência) | repasses federais pagos | efetivo (lado pagador) | não inclui rendimentos; limita downloads |
| **TCE-ES** (CKAN) | empenhos, dotação, contratações, itens, obras, medições, remessas | declaratório, estadual | arquivo de 2023 **não traz dezembro** para 25 municípios |
| **Censo Escolar** (INEP) | matrículas, docentes, infraestrutura por escola | censitário | nenhuma fonte financeira traz o código INEP |
| **INEP/ICA** | alfabetização ao fim do 2º ano | amostral/censitário | — |

**Um achado de reconhecimento que muda o método:** o endpoint `/rreo` do SICONFI, filtrado
por `no_anexo=RREO-Anexo 08`, devolve **zero itens** — testado em municípios de portes
diferentes e em cinco exercícios. Consultando sem filtro, a lista vai de 01 a 14 **pulando
05, 08 e 12**. O Anexo 08 é declarado ao SIOPE e não chega à API do Tesouro. **Consequência:
o SIOPE é a fonte primária do MDE.** E não se pode estimar MDE a partir da função 12 — ela
inclui gastos que não contam (ver [§3.4](#34-o-que-é-e-o-que-não-é-mde)).

### 6.2 Por que as fontes divergem — e o que fazer com isso

Divergência entre fontes declaratórias é **o estado normal**, não a exceção. O que a
torna útil é tratá-la como *sinal a investigar*, nunca como erro de uma delas.

| Conferência | Resultado |
|---|---|
| Soma das subfunções = despesa da função 12 (DCA) | 395 de 395 ente-anos |
| Função 12: MSC × DCA Anexo I-E | 388 de 390 ao centavo |
| FUNDEB: MSC × DCA Anexo I-C | **390 de 390 ao centavo** |
| Função 12: soma dos empenhos do TCE-ES × DCA I-E | 354 de 365 município-anos |
| FUNDEB: SIOPE (principal) × DCA I-C | 350 de 390 |
| **MDE: TCE-ES × SIOPE** (tolerância 0,5 p.p.) | **289 de 390** — divergem em 101 |
| Função 12 × total do SIOPE | 129 de 390 iguais |

**A divergência mais relevante é a do MDE.** As duas apurações discordam em 101 de 390
município-anos, e em **13 delas a discordância atravessa o mínimo** — uma fonte abaixo de
25%, a outra acima:

| Município | Ano | SIOPE | TCE-ES | Diferença |
|---|---|---:|---:|---:|
| Guaçuí | 2021 | 26,03% | 22,11% | −3,92 p.p. |
| Vila Velha | 2021 | 29,36% | 24,61% | −4,75 p.p. |
| Ibiraçu | 2023 | 28,58% | 24,83% | −3,75 p.p. |
| Mimoso do Sul | 2023 | 25,56% | 22,83% | −2,73 p.p. |
| Laranja da Terra | 2023 | 25,00% | 24,04% | −0,96 p.p. |
| Montanha | 2024 | 25,57% | 24,90% | −0,67 p.p. |
| Muniz Freire | 2024 | 25,83% | 24,49% | −1,34 p.p. |
| Pedro Canário | 2024 | 25,00% | 24,15% | −0,85 p.p. |
| São Gabriel da Palha | 2024 | 26,17% | 24,53% | −1,64 p.p. |
| Linhares | 2024 | 24,98% | 25,02% | +0,04 p.p. |
| Brejetuba | 2025 | 25,78% | 24,55% | −1,23 p.p. |
| Ibatiba | 2025 | 25,14% | 24,97% | −0,17 p.p. |
| Iúna | 2025 | 25,08% | 24,85% | −0,23 p.p. |

Duas observações. **Primeira: a divergência é assimétrica** — em 12 dos 13 casos o
Tribunal apura *menos* que o SIOPE, o que é coerente com uma apuração que glosa despesas
e considera cancelamentos de restos a pagar que o sistema declaratório do FNDE não vê.
**Segunda: Linhares 2024 é caso de fronteira** (0,04 p.p.), dentro do ruído de
arredondamento — tratá-lo como os demais seria exagero.

As causas prováveis, a confirmar caso a caso: critério de restos a pagar, cancelamentos,
glosas de despesa do art. 71 da LDB, tratamento dos rendimentos de aplicação e data de
corte da apuração. **Nenhuma das duas apurações é "a verdadeira"** — são metodologias
diferentes, e a diferença é a matéria-prima do trabalho.

### 6.3 Os testes que o dado sustenta

**Teste 1 — preço unitário entre municípios.** É o uso mais potente dos dados de itens do
TCE-ES. Procurando descrições **idênticas** que aparecem em vários municípios:

| Item (descrição idêntica) | Unidade | Municípios | Preço mín. | Mediana | Preço máx. | Razão |
|---|---|---:|---:|---:|---:|---:|
| **Calha em chapa galvanizada, largura 40 cm** | Metro | **12** | R$ 72,81 | R$ 249,84 | R$ 311,46 | **4,3×** |
| Calha em chapa galvanizada, largura 40 cm | Outra | 5 | R$ 132,73 | R$ 238,86 | R$ 313,19 | 2,4× |
| Retirada de estrutura de madeira do telhado | m² | 8 | R$ 11,37 | R$ 34,14 | R$ 38,67 | 3,4× |
| Tapume telha metálica ondulada galvalume | Outra | 5 | R$ 105,64 | R$ 211,40 | R$ 273,76 | 2,6× |
| Grade de ferro em barra chata, com chumbamento | m² | 7 | R$ 226,15 | R$ 402,00 | R$ 474,65 | 2,1× |
| Forro de gesso acabamento liso | m² | 10 | R$ 48,16 | R$ 59,68 | R$ 78,68 | 1,6× |
| Camiseta escolar manga curta | Unidade | 5 | R$ 21,00 | R$ 21,00 | R$ 23,20 | 1,1× |

A calha galvanizada é o exemplo didático: **item de descrição padronizada (vocabulário
SINAPI), mesma unidade, 12 municípios, e preço que varia 4,3 vezes**. Isso não prova
sobrepreço — composições de custo diferem por região, acesso, altura, BDI e data-base —
mas define com precisão onde pedir a planilha orçamentária e a pesquisa de preços.

**Teste 2 — o que se comprou realmente foi entregue.** Dos 121.534 itens, apenas **24.060
têm medição registrada**. Contratado não é entregue: R$ 4,86 bilhões contratados contra
R$ 1,11 bilhão medido.

**Teste 3 — o objeto é mesmo de educação?** Os dois maiores itens da Educação do estado
**não são de ensino**: cartão-alimentação de servidores contratado pela unidade gestora da
educação da Serra (2025: 360.000 unidades a R$ 927,90 = R$ 334.044.000,00; 2024:
R$ 84.480.000,00). Cariacica tem contratações equivalentes (R$ 52,1 mi e R$ 47,3 mi em
2023). O benefício é devido — a questão é de **classificação**: benefício de servidor da
prefeitura inteira empenhado pela unidade gestora da educação distorce qualquer indicador
de custo-aluno e pode contaminar a base do MDE.

Para contraste, na mesma lista: Cariacica, 2025, "preparo e distribuição de alimentação
nas unidades escolares — almoço parcial", 4.000.000 de refeições a **R$ 7,56** cada =
R$ 30.240.000,00, contratado junto ao Consórcio Público da Região Polinorte. Esse é gasto
de educação de verdade, e o preço unitário é diretamente comparável entre municípios.

**Teste 4 — transporte escolar por quilômetro.** Recorte dos itens com unidade em km:

| Município | Itens | Km contratados | Valor | Mín. | Mediana | Máx. |
|---|---:|---:|---:|---:|---:|---:|
| Aracruz | 144 | 1.471.866 | R$ 14.650.881,73 | R$ 2,00 | R$ 10,38 | R$ 44,00 |
| Jaguaré | 242 | 1.209.975 | R$ 13.817.075,59 | R$ 0,88 | R$ 8,60 | R$ 35,10 |
| Alegre | 225 | 1.316.591 | R$ 11.532.640,79 | R$ 2,33 | R$ 8,39 | R$ 66,53 |
| Vitória | 76 | 1.191.565 | R$ 8.293.520,75 | R$ 0,93 | R$ 5,22 | R$ 130,80 |
| Vila Velha | 42 | 1.075.273 | R$ 5.701.230,15 | R$ 1,00 | R$ 5,19 | R$ 9,99 |
| Jerônimo Monteiro | 6 | 21.923 | R$ 502.414,04 | R$ 14,66 | **R$ 22,88** | R$ 26,36 |

A mediana de Jerônimo Monteiro (R$ 22,88/km) é **4,4 vezes** a de Vila Velha (R$ 5,19) e
2,2 vezes a de Aracruz. Rota rural, veículo pequeno e estrada não pavimentada justificam
diferença — justificam *esta* diferença é o que se vai verificar. Note também a dispersão
**interna**: Vitória vai de R$ 0,93 a R$ 130,80 por km no mesmo município, o que aponta
para heterogeneidade de lote (ou erro de unidade na declaração) antes de apontar para
preço.

**Teste 5 — obras paradas.** Retrato atual: 765 contratos de obra da Educação em
municípios, R$ 2,00 bilhões.

| Situação | Contratos | Valor |
|---|---:|---:|
| **Paralisação presumida** (classificação do TCE-ES, por falta de medição) | 337 | R$ 907,5 mi |
| Não iniciada | 240 | R$ 580,9 mi |
| Concluída e recebida provisoriamente | 76 | R$ 82,6 mi |
| Em execução | 51 | R$ 318,0 mi |
| Não identificada | 33 | R$ 62,4 mi |
| Concluída e recebida definitivamente | 11 | R$ 7,9 mi |
| **Interrompida** (declarada) | 10 | R$ 17,1 mi |
| Concluída e não recebida | 5 | R$ 16,2 mi |
| **Paralisada** (declarada) | 2 | R$ 3,1 mi |

Somadas, paralisadas e presumidas são **349 obras, R$ 927,8 milhões, em 60 municípios**.
As maiores:

| Município | Objeto | Valor | % medido | Última medição |
|---|---|---:|---:|---|
| Vila Velha | Centro Integrado Familiar, bairro Araçás | R$ 22.495.616,24 | 100,8% | 01/08/2025 |
| Vila Velha | Unidade de ensino Prof.ª Nair Dias Barbosa, Ponta da Fruta | R$ 21.442.158,69 | 59,9% | 30/04/2026 |
| Serra | EMEF no bairro Cidade Pomar | R$ 19.330.352,86 | 55,1% | 31/05/2026 |
| Serra | Reconstrução da EMEF Jardim Bela Vista | R$ 18.057.875,82 | 47,1% | 31/12/2024 |
| Serra | EMEF no bairro Jardim Tropical | R$ 17.494.442,15 | 105,3% | 31/05/2026 |

> **Leia com cuidado.** "Paralisação presumida" é **classificação do Tribunal** por
> ausência de medição recente, não declaração do município — separe-a das 12 declaradas.
> E duas linhas acima têm **percentual medido acima de 100%** (100,8% e 105,3%), o que
> indica aditivo não refletido no valor de referência ou inconsistência na remessa: são
> registros a esclarecer antes de qualquer uso.

**Teste 6 — o dinheiro que chega à escola.** Três canais nomeiam o recebedor:

1. **PDDE** (federal, direto à unidade executora) — R$ 161,0 mi identificados por escola
   em 2021–2025;
2. **Repasse do município ao conselho escolar** — R$ 403,2 mi;
3. **Obra no prédio da escola** — R$ 96,9 mi.

*Repasses municipais a conselhos escolares:*

| Ano | Municípios | Conselhos distintos | Valor |
|---|---:|---:|---:|
| 2021 | 26 | 591 | R$ 90,4 mi |
| 2022 | 32 | 690 | R$ 114,0 mi |
| 2023 | 36 | 738 | R$ 76,3 mi |
| 2024 | 39 | 790 | R$ 95,5 mi |
| 2025 | 39 | 829 | R$ 92,0 mi |

Em 2025, Vitória repassou R$ 32,9 milhões a 91 conselhos; Vila Velha, R$ 21,7 mi a 110;
Serra, R$ 17,3 mi a 118; Cariacica, R$ 8,2 mi a 119. **Metade dos municípios do ES não
repassa nada diretamente às escolas** — o que é decisão de política, não irregularidade,
mas define quem tem e quem não tem autonomia financeira na ponta.

### 6.4 Proveniência: o que transforma um número em evidência

Cada valor precisa carregar, junto de si: o endpoint e os parâmetros da consulta, o anexo
/ linha / coluna (ou o item do demonstrativo **daquele exercício**, já que o layout muda),
o cálculo aplicado, o instante da coleta e o arquivo bruto que guarda a resposta original,
com hash. É o equivalente da nota de rodapé de um papel de trabalho — sem isso, o número
é afirmação, não evidência.

Um exemplo real, a linha completa de `mde_pct` para Guaçuí 2024:

```
valor          22.42
unidade        %
fonte          SIOPE
localizacao    RREO Anexo 8 gerado pelo SIOPE (PDF), 6º bimestre:
               aplicação em MDE sobre a receita de impostos, coluna "% APLICADO"
calculo        percentual apurado pelo SIOPE; conferido = 25 × aplicado ÷ exigido
observacao     item 29 — APLICAÇÃO EM MDE SOBRE A RECEITA LÍQUIDA DE IMPOSTOS
endpoint       ftp://ftp.fnde.gov.br/web/siope/RREO/RREO_Municipal_320230_6_2024.pdf
parametros     RREO_Municipal_320230_6_2024.pdf
obtido_em      2026-09-22T12:43:47+00:00
arquivo_cache  siope/2024/RREO_Municipal_320230_6_2024.pdf
```

Note o campo `observacao`: **"item 29"**. O número do item no Anexo 8 do SIOPE mudou três
vezes em cinco anos (itens 1–54 em 2021–2022, 1–45 em 2023, 1–40 em 2024–2025). Por isso
os itens são localizados pelo **rótulo**, nunca pelo número, e o número encontrado é
registrado como observação. Papel de trabalho que cite "item 29 do Anexo 8" sem dizer o
exercício aponta para o lugar errado em outro ano.

### 6.5 O que o dado público não responde

Registrar isto é parte do método. Não se pode obter das fontes usadas aqui:

1. **Custo de pessoal por escola.** O vínculo do servidor no TCE-ES não traz lotação — e
   pessoal é mais da metade da despesa.
2. **Em que cada escola gastou o PDDE.** A unidade executora presta contas ao FNDE.
3. **A nota fiscal.** Número, data e emitente não estão em dado aberto do TCE-ES.
4. **A ligação certa empenho ↔ contrato.** O empenho não traz o número do contrato. A
   ponte usada é o CNPJ da contratada no mesmo município e exercício: é **indício, não
   identidade**.
5. **O item dos municípios que compram pela unidade gestora da prefeitura** sem marcar o
   setor beneficiado.
6. **O código INEP nas fontes financeiras.** O vínculo recebedor → escola é feito **pelo
   nome**, com regras explícitas; o ambíguo fica sem vínculo. Taxas alcançadas: 1.915 de
   2.301 unidades executoras do PDDE (83%), 715 de 890 conselhos escolares (80%) e apenas
   20 de 69 prédios de obra (29%).
7. **Dezembro de 2023 para 25 municípios** — o arquivo de empenhos publicado pelo TCE-ES
   não o traz. O ano é marcado como **incompleto**, e não como divergência.
8. **Séries de remessa mensal anteriores a 08/2025** — a fonte só cobre a janela recente.

E um alerta encontrado no próprio dado, que ilustra a postura: **Conceição da Barra
declarou receita patrimonial de −R$ 1,24 milhão** no RREO Anexo 01 de 2021 — o único valor
negativo onde o indicador não o admite. Não foi corrigido nem descartado: foi registrado
como item a esclarecer na fonte.

---

## 7. Uma trilha completa: Guaçuí, 2024

Município de 28.727 habitantes, 4.382 matrículas na rede municipal. Escolhido porque é o
**único caso recente em que as duas apurações independentes do MDE concordam exatamente
sobre o descumprimento** — o que isola a análise da divergência metodológica.

### Passo 1 — O mínimo não foi atingido, e as duas fontes concordam

| | Valor |
|---|---:|
| Receita resultante de impostos (base do MDE) | R$ 81.496.571,39 |
| 25% da base = mínimo exigido | R$ 20.374.142,85 |
| Aplicado em MDE | R$ 18.273.129,77 |
| **Percentual aplicado** | **22,42%** |
| **Diferença para o mínimo** | **R$ 2.101.013,08** |
| MDE apurado pelo TCE-ES | 22,42% (divergência: 0,00 p.p.) |

*Verificação aritmética:* 18.273.129,77 ÷ 81.496.571,39 = 22,4220%. E 0,25 ×
81.496.571,39 = 20.374.142,85, idêntico ao valor exigido declarado na fonte. A apuração
fecha.

### Passo 2 — De onde veio o dinheiro

| Origem | Valor |
|---|---:|
| Impostos próprios | R$ 12.894.433,05 |
| FUNDEB | R$ 41.374.587,43 |
| Transferências federais específicas | R$ 2.997.749,22 |
| Outras | R$ 109.710.102,81 |
| **Receita total** | **R$ 166.976.872,51** |

Os impostos próprios são **15,8% da base do MDE** de R$ 81,5 milhões — o restante são
transferências de impostos. No FUNDEB: contribuiu R$ 12.858.923,74, recebeu
R$ 41.374.587,43, com R$ 6.623.741,24 de complementação da União. Salário-educação:
R$ 2.283.083,51. PNAE: R$ 720.053,93. PNATE: R$ 123.170,16. PDDE: **R$ 0,00**.

### Passo 3 — Onde foi aplicado

*Por subfunção:* Ensino Fundamental R$ 39.279.923,87 (67,2%) e Educação Infantil
R$ 19.201.817,14 (32,8%). Nada em outras subfunções — perfil concentrado, coerente com a
competência municipal.

*Por natureza:* pessoal R$ 29.248.344,65; custeio R$ 18.174.970,22; investimento
R$ 11.058.426,14. O investimento é **18,9% da despesa** — 1,7 vez a média dos
municípios do ES no mesmo exercício (10,9% em 2024).

*Por fonte:* FUNDEB (540) R$ 34.568.061; outras (599) R$ 7.938.016; impostos (500)
R$ 6.189.488; FUNDEB (542) R$ 5.308.382; federais (550) R$ 2.996.047.

### Passo 4 — Para quem

| Credor | Empenhado | Elemento |
|---|---:|---|
| Pessoal efetivo FUNDEB 70% | R$ 10.577.850,05 | vencimentos e vantagens fixas |
| Pessoal contratado educação FUNDEB 70% | R$ 7.521.769,76 | contratação por tempo determinado |
| **COOP. DE TRANSPORTE DA REGIÃO SUL — COOPERSULES** | **R$ 5.319.692,92** | outros serviços de terceiros — PJ |
| Pessoal efetivo creche FUNDEB 70% | R$ 3.379.311,62 | vencimentos e vantagens fixas |
| Pessoal contratado creches FUNDEB 70% | R$ 3.162.680,07 | auxílio-alimentação |
| Pessoal efetivo pré-escola FUNDEB 70% | R$ 2.419.378,59 | vencimentos e vantagens fixas |
| CIMOVEIS COMERCIO DE MOVEIS LTDA | R$ 1.896.119,64 | equipamento e material permanente |
| CONSTRUTORA OURO BRANCO EIRELI | R$ 1.892.690,81 | obras e instalações |

### Passo 5 — O que isso abre para a fiscalização

O município ficou R$ 2,10 milhões abaixo do mínimo constitucional, **sem cobertura da EC
119/2022** (que alcança apenas 2020 e 2021). Simultaneamente:

- cumpriu o mínimo do FUNDEB com folga (**72,91%** contra 70%);
- investiu 18,9% da despesa da educação — proporção alta, e investimento **conta para o
  MDE** (art. 70 da LDB), o que torna o descumprimento menos trivial de explicar;
- a divergência função 12 × SIOPE é de **−5,74%**, dentro do usual;
- o ICA foi de **77%**, acima da meta pactuada do município para o ano;
- tem **8 entregas com atraso** contra 3 no prazo no exercício.

As perguntas que a trilha produz — nenhuma delas respondida pelo dado:

1. Houve glosa de despesa declarada como MDE? Em quê?
2. A diferença de R$ 2,10 milhões foi reconhecida e compensada no exercício seguinte?
3. O contrato de transporte (R$ 5,32 milhões, terceiro maior credor da educação) tem
   preço por quilômetro compatível com o dos vizinhos? *(ver [Teste 4](#63-os-testes-que-o-dado-sustenta))*
4. Como o município chegou a 18,9% de investimento e ainda assim não atingiu os 25%?
5. Por que 8 de 11 entregas do exercício foram fora do prazo?

**Esse é o produto correto de uma análise de dados em controle externo:** não uma
conclusão, mas uma lista curta de perguntas precisas, cada uma com o documento de origem
já identificado.

---

## 8. Roteiro de testes

Ordem sugerida, do mais barato ao mais caro. As referências entre parênteses apontam para
a seção que descreve o teste e os dados que o alimentam.

**Conformidade — obrigatórios**

1. MDE ≥ 25% nas **duas** apurações (SIOPE e TCE-ES). Divergência que atravessa o mínimo
   é prioridade. *([§5.1](#51-os-mínimos-legais), [§6.2](#62-por-que-as-fontes-divergem--e-o-que-fazer-com-isso))*
2. Exercícios de 2020–2021: verificar **compensação da EC 119/2022 até 2023**, e não o
   percentual isolado. *([§4.1](#41-constituição-federal))*
3. FUNDEB ≥ 70% em remuneração. Examinar também os **extremos superiores** — 100,00% é
   sinal. *([§5.1](#51-os-mínimos-legais))*
4. Destinações mínimas do VAAT (educação infantil e despesas de capital), quando o ente
   recebe complementação-VAAT. *([§2.2](#22-fundeb))*
5. Entregas RREO / RGF / DCA no prazo, examinando a **cauda**, não a contagem.
   *([§4.4](#44-lrf-e-os-prazos--lc-1012000))*
6. Remessas mensais ao CidadES. Separar "UG sem remessa" de atraso. *([§5.4](#54-índices-de-execução))*

**Composição e classificação**

7. Despesa em subfunções fora da competência municipal (12.362, 12.364) — verificar a
   condição do art. 211, §2º. *([§3.1](#31-função-e-subfunção))*
8. Itens do art. 71 da LDB computados no MDE — merenda, infraestrutura urbana, assistência
   social, pessoal em desvio de função. *([§3.4](#34-o-que-é-e-o-que-não-é-mde))*
9. Objeto alheio à educação empenhado pela unidade gestora da educação — o caso do
   cartão-alimentação. *([Teste 3](#63-os-testes-que-o-dado-sustenta))*
10. Transferências a entidades sem fins lucrativos (modalidade 50): plano de trabalho,
    prestação de contas, requisitos do art. 213 da CF. *([§3.2](#32-natureza-econômica))*

**Execução**

11. Orçado × executado nas ações de obra. *([§5.4](#54-índices-de-execução))*
12. Concentração de empenho em nov+dez, **contra a mediana do próprio exercício**.
13. Restos a pagar antigos ainda em movimentação e cancelamentos de despesa que compôs o
    MDE do exercício de origem.
14. Empenhado × liquidado × pago por credor relevante.

**Contratos, obras e preços**

15. Obras paralisadas e presumidamente paralisadas — separar as duas categorias.
    *([Teste 5](#63-os-testes-que-o-dado-sustenta))*
16. Acréscimo contratual acumulado contra os limites legais. *([§4.6](#46-contratos-e-obras))*
17. Preço unitário de itens de descrição idêntica entre municípios.
    *([Teste 1](#63-os-testes-que-o-dado-sustenta))*
18. Contratado × medido — o que foi comprado foi entregue? *([Teste 2](#63-os-testes-que-o-dado-sustenta))*
19. Transporte escolar: custo por quilômetro, dentro e entre municípios.
    *([Teste 4](#63-os-testes-que-o-dado-sustenta))*

**Escola e resultado**

20. Repasse a conselhos escolares: existe? a quantos? com que ação orçamentária?
    *([Teste 6](#63-os-testes-que-o-dado-sustenta))*
21. Recursos identificados por escola × matrículas, infraestrutura e resultado — **como
    contexto**, sem inferência causal. *([§5.2](#52-índices-de-resultado))*

---

## 9. Anexos

### Anexo A — Glossário

| Termo | Significado |
|---|---|
| **MDE** | Manutenção e Desenvolvimento do Ensino — o conjunto de despesas que satisfaz o art. 70 da LDB e conta para o mínimo do art. 212 da CF |
| **Receita resultante de impostos** | Base de cálculo do MDE: impostos próprios **mais** transferências de impostos recebidas |
| **FUNDEB** | Fundo de Manutenção e Desenvolvimento da Educação Básica — fundo contábil estadual, redistributivo por matrícula |
| **VAAF / VAAT / VAAR** | Os três canais da complementação da União ao FUNDEB: por valor aluno do fundo, por valor aluno total do ente, e por resultado |
| **Função / subfunção** | Classificação funcional da despesa. Educação é a função 12 |
| **Natureza da despesa** | Código de 8 dígitos: categoria, grupo, modalidade de aplicação, elemento |
| **Fonte / destinação de recursos** | Código que identifica a origem do dinheiro que paga cada empenho |
| **Empenhado / liquidado / pago** | Os três estágios da despesa (Lei 4.320/1964) |
| **Restos a pagar** | Despesa empenhada e não paga até 31 de dezembro; *processados* se já liquidados, *não processados* se não |
| **UG** | Unidade gestora — secretaria, fundo ou autarquia que executa orçamento próprio |
| **DCA** | Declaração de Contas Anuais, enviada ao SICONFI |
| **RREO / RGF** | Relatório Resumido da Execução Orçamentária (bimestral) e Relatório de Gestão Fiscal (quadrimestral ou semestral) |
| **MSC** | Matriz de Saldos Contábeis — remessa mensal de saldos ao SICONFI |
| **SIOPE** | Sistema de Informações sobre Orçamentos Públicos em Educação (FNDE) |
| **CidadES** | Sistema de prestação de contas do TCE-ES |
| **UEx** | Unidade executora — entidade com CNPJ próprio (conselho escolar, caixa escolar, APM) que recebe o PDDE |
| **ICA** | Indicador Criança Alfabetizada — % de alunos alfabetizados ao fim do 2º ano |
| **CNCA** | Compromisso Nacional Criança Alfabetizada |
| **FUNPAES** | Fundo de Apoio à Educação do Estado do Espírito Santo |
| **Bem vinculador** | No cadastro de contratações do TCE-ES, o imóvel a que a obra se vincula — com coordenada geográfica |

### Anexo B — Onde buscar cada número

| Pergunta | Fonte | Localização exata |
|---|---|---|
| Quanto o ente gastou em educação? | SICONFI | DCA Anexo I-E, conta "12 — Educação" |
| Em que etapa de ensino? | SICONFI | DCA Anexo I-E, por subfunção |
| Em pessoal, custeio ou investimento? | SICONFI | MSC, classe 6, contas 622130100–622130700 |
| Com dinheiro de que fonte? | SICONFI | MSC, fonte de recursos por empenho (2022+) |
| Cumpriu os 25%? | **SIOPE** | RREO **Anexo 8**, 6º bimestre — **não está no SICONFI** |
| Cumpriu os 70% do FUNDEB? | SIOPE | RREO Anexo 8 |
| Quanto recebeu do FNDE? | CGU | Portal da Transparência, download mensal |
| Quanto recebeu de FUNDEB? | SICONFI | MSC conta 621200000, conferido contra DCA Anexo I-C |
| Entregou os relatórios no prazo? | SICONFI | `/extrato_entregas` |
| Para quem pagou? | TCE-ES | Empenhos dos municípios, função 12 |
| Em qual ação orçamentária? | TCE-ES | Empenhos + Despesas (dotação) |
| O que comprou, e por quanto a unidade? | TCE-ES | Contratações + Itens (2022+) |
| A obra anda? | TCE-ES | Contratações + Instrumentos com medições e alterações |
| Remeteu a prestação de contas mensal? | TCE-ES | Prestação de Contas Municipal (janela recente) |
| Quantos alunos, e em que escolas? | INEP | Censo Escolar |
| Qual o resultado de alfabetização? | INEP | Planilha oficial do ICA |

### Anexo C — Reprodução

A partir da raiz do repositório:

```powershell
python -m financiamento.etl.pipeline        # coleta as seis fontes (usa cache)
python -m financiamento.build_dashboard     # monta financiamento/dashboard.html
python -m financiamento.etl.comparar        # o que mudou entre as duas últimas extrações
```

Dataset consolidado, um número por linha com a proveniência na própria linha:
`financiamento/dados/processado/consolidado.csv`.

Documentos relacionados neste repositório:

- [`README.md`](../README.md) — o painel, as fontes, as conferências e as limitações
- [`etl/README.md`](../etl/README.md) — operação do pipeline e cache
- [`docs/fase0_reconhecimento.md`](fase0_reconhecimento.md) — o que cada API aguenta, medido
- [`docs/mapeamento_dados_tcees.md`](mapeamento_dados_tcees.md) — levantamento dos dados abertos do TCE-ES
- [`config/matriz_cnca.yaml`](../config/matriz_cnca.yaml) — matriz de evidências da fiscalização do CNCA

---

*Dados coletados em 22–23 de setembro de 2026. Exercícios de 2021 a 2025, 78 municípios do
Espírito Santo e o Governo do Estado. Os números refletem o que as fontes publicavam na
data da coleta; declarações retificadas depois disso não estão refletidas aqui.*
