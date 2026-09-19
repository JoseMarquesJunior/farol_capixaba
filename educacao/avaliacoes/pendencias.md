# Pendências das avaliações — decisões que pedem raciocínio pesado

Pontos encontrados durante a construção do pipeline que **não** devem ser
resolvidos no impulso. Cada um muda o resultado analítico se for decidido
errado, e nenhum tem resposta óbvia a partir do dado sozinho.

---

## 1. Ponte entre `dw.dim_etapa` e as etapas das avaliações

Quatro vocabulários de etapa convivem, em granularidades diferentes:

| fonte | etapas |
|---|---|
| Censo (`dw.dim_etapa`) | Infantil, Fund. AI, Fund. AF, Médio, EJA, Profissional, Especial |
| IDEB | anos iniciais, anos finais, ensino médio |
| SAEB | 2EF, 5EF, 9EF, EMT, EMI, EM |
| PAEBES | 5º EF, 9º EF, 3ª série EM |

Não é um de-para 1:1. O IDEB "anos iniciais" cobre 1º a 5º, mas é calculado
sobre a aprovação de todas as cinco séries e a proficiência só do 5º. O SAEB
separa EM total (`EM`), técnico (`EMT`) e integrado (`EMI`), que se sobrepõem
do mesmo jeito que as matrículas do Censo se sobrepõem.

**A decidir:** se a ponte é uma dimensão própria (`dim_etapa_avaliada`) com
tabela de correspondência para `dim_etapa`, ou se as duas viram uma só com
níveis de granularidade. Envolve decidir o que significa comparar "matrícula
nos anos iniciais" com "IDEB dos anos iniciais".

---

## 2. Política do decodificador da máscara municipal do SAEB

O alinhamento ordenado resolve o ES com exatidão (78 municípios mascarados
contra 78 do IBGE, nas quatro edições testadas). Mas nacionalmente **2 a 11
UFs divergem em contagem** conforme a edição (2015 é a pior: 11 UFs).

**Resolvido para o ES (2026-09-18).** O decodificador exige igualdade estrita e
aborta sem ela (`saeb.construir_mascara`). O ES fecha nas cinco edições (78 =
78). A tradução foi validada contra sinal independente: o SAEB publica
`NU_MATRICULADOS_CENSO_*`, que vem do Censo, e comparando com o Censo já
carregado, por município:

| edição | tradução correta (AI) | correta (AF) | deslocada em 1 (AI) |
|---|---|---|---|
| 2015 | 0,9942 | 0,9894 | 0,1575 |
| 2017 | 0,9956 | 0,9924 | 0,1574 |
| 2019 | 0,9951 | 0,9942 | 0,1505 |
| 2021 | 0,9953 | 0,9938 | 0,1377 |
| 2023 | 0,9929 | 0,9939 | 0,1313 |

Em 2023, quando o Censo passa a publicar a matrícula por série, a comparação
direta 5º x 5º dá 0,9938 e 9º x 9º dá 0,9913. O controle deslocado em uma única
posição derruba a correlação para ~0,15, o que mostra que o teste discrimina.

**Continua em aberto** apenas a política nacional: fora do ES, de 1 a 11 UFs
divergem em contagem conforme a edição. Só importa se o escopo deixar de ser ES.

---

## 3. O que `VL_NOTA_*` do IDEB realmente é

O IDEB publica `VL_NOTA_MATEMATICA`, `VL_NOTA_PORTUGUES` e `VL_NOTA_MEDIA`.
O rótulo humano da terceira é "Nota Média Padronizada (N)" — ou seja, a nota
**padronizada para a escala 0–10** que entra no produto N × P. As duas
primeiras estão provavelmente na escala SAEB (~0–500), mas isso **não foi
verificado**.

**Resolvido (2026-09-18).** Medido em `stg.ideb_escola`, sobre 15.861 linhas:

| medida | faixa observada | escala |
|---|---|---|
| `nota_matematica` | 140,9 – 403,2 | SAEB, 0–500 |
| `nota_portugues` | 129,4 – 363,5 | SAEB, 0–500 |
| `nota_media` | 2,41 – 9,70 | padronizada 0–10 (o N) |
| `indicador_rendimento` | 0,11 – 1,00 | o P |
| `ideb_observado` | 0,5 – 9,7 | N × P |
| `stg.saeb_municipio.media_lp/mt` | 179 – 355 | SAEB, 0–500 |
| `stg.paebes_aluno.proficiencia` | 86,6 – 484,2 | 0–500 |

Ou seja: `nota_matematica` e `nota_portugues` do IDEB **são** proficiência na
escala SAEB e comparam-se direto com `stg.saeb_municipio` e com o PAEBES, sem
conversão. `nota_media` não — é a padronização 0–10.

A identidade `ideb_observado = nota_media × indicador_rendimento` confere em
**15.860 de 15.860 linhas** dentro de 0,1 (100%), o que valida de quebra toda a
cadeia de despivotagem: se alguma medida tivesse sido atribuída à coluna errada,
essa conta não fecharia.

---

## 4. Grão temporal: avaliação bienal contra Censo anual

IDEB e SAEB só existem em anos ímpares; ENEM por Escola é anual mas acaba em
2015; PAEBES só tem 2025. O grão escolhido foi escola × ano.

**A decidir:** se o fato de avaliação só tem linha nos anos de edição (e a
junção com o Censo é feita na consulta), ou se há uma visão que propaga a
última medição conhecida para os anos intermediários. A segunda é conveniente
e perigosa: propagar IDEB de 2023 para 2024 parece dado e não é.

---

## 5. Agregação do PAEBES de aluno para escola

O PAEBES vem no grão aluno × disciplina, com 378.564 linhas e 124.631 alunos.
Duas complicações:

* as disciplinas se sobrepõem: `Ciências da Natureza` (43.424) convive com
  `Química` (28.626), `Física` (28.626) e `Biologia` (28.626) — somar tudo
  conta o mesmo aluno mais de uma vez;
* há `FL_PREVISTO`, `FL_PRESENTE`, `FL_AVALIADO`, `FL_PUB_DEDUCAO` e
  `FL_PUB_TRANSFERIDO`. Qual combinação define o denominador da média da
  escola não é óbvio, e a escolha muda a proficiência publicada.

**A decidir:** a regra de agregação, conferida contra algum resultado
divulgado pela SEDU para a mesma edição, para não inventar uma média que não
corresponde ao que o estado publica.

---

## 6. Escolas do IDEB fora do recorte do Censo carregado

O Censo está carregado de 2007 a 2025, mas o IDEB começa em **2005**. Escolas
que aparecem no IDEB de 2005 e 2006 e fecharam antes de 2007 não têm linha em
`dw.dim_escola`.

**Medido (2026-09-18):** o problema é minúsculo e está todo em 2005.

| arquivo | escolas ES | fora de `dim_escola` | onde |
|---|---|---|---|
| anos finais | 911 | 1 | só na edição 2005 |
| anos iniciais | 1.159 | 4 | só na edição 2005 |
| ensino médio | 376 | 0 | — |
| ENEM por Escola | 500 | 0 | — |

De 2007 em diante o casamento é **100% em todas as edições**. São 5 escolas
que existiam em 2005 e fecharam antes do Censo de 2007.

**A decidir:** entre (a) acrescentá-las a `dim_escola` com `primeiro_ano=2005`
e uma marca de procedência "IDEB", (b) deixar `fato_ideb` sem FK, ou (c) começar
a série de avaliação em 2007. A (a) é a única que não descarta dado real, mas
mexe numa dimensão que hoje é definida pelo Censo. Só morde na etapa do `dw`;
em `raw` não há restrição, então a carga pode seguir antes da decisão.
