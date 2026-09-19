# Avaliações

Resultados de avaliação alinhados ao Censo Escolar: IDEB, ENEM por Escola, SAEB
e PAEBES, recortados no Espírito Santo.

A arquitetura é a mesma do Censo — catálogo → `raw` → `stg` — e o princípio
também: **o arquivo publicado manda, o dicionário enriquece**.

## O que cada fonte permite

| fonte | grão | chave da escola | casa com `dw.dim_escola` | período |
|---|---|---|---|---|
| **IDEB** | escola × edição | `ID_ESCOLA` | **100%** | 2005–2025 (EM: 2017–2025) |
| **ENEM por Escola** | escola × ano | `CO_ESCOLA_EDUCACENSO` | **100%** | 2005–2015 |
| **PAEBES** | aluno × disciplina | `CD_ESCOLA` | **99,9%** | 2025 |
| **SAEB** | *município* × edição | mascarada | — | 2015–2023 |

Fora do escopo: os microdados completos do ENEM (~14 GB, sem código de escola
desde a anonimização LGPD) e a série histórica do PAEBES 2008–2024, que não é
aberta.

## Como rodar

```powershell
python -m educacao.avaliacoes.fontes --listar     # o que existe e o que falta
python -m educacao.avaliacoes.fontes              # baixa o que falta (~555 MB)
python -m educacao.avaliacoes.catalogo            # gera catalog/<fonte>.json
python -m educacao.avaliacoes.validar             # confere catálogo x arquivos
python -m educacao.avaliacoes.ddl --aplicar       # cria as tabelas de raw
python -m educacao.avaliacoes.carga               # carrega raw, filtrado no ES
python -m educacao.avaliacoes.stg --aplicar --carregar
```

Tudo é idempotente. A carga só repete o que mudou: compara o sha256 do arquivo
**e** confere se a tabela ainda tem o que aquele arquivo gravou — sem a segunda
conferência, um `DROP TABLE` faria a carga pular uma tabela vazia.

## Três armadilhas que o código trava

### 1. No IDEB, o nome da coluna não diz a série

O sufixo do nome de máquina é posição ordinal dentro da etapa, não número de
série. Nos anos iniciais há **cinco séries para quatro sufixos numéricos**: o
INEP manteve a numeração do fundamental de oito anos e pendurou o 1º ano na
coluna `_SI`.

```
VL_APROVACAO_2005_SI_4  ->  1º ao 5º ano (total)
VL_APROVACAO_2005_SI    ->  1º ano
VL_APROVACAO_2005_1     ->  2º ano        <- e não o 1º
VL_APROVACAO_2005_4     ->  5º ano
```

Ler o sufixo — o reflexo óbvio — deslocaria a série inteira dos anos iniciais em
um ano, sem erro e sem nada visível no resultado. Quem manda na série é o rótulo
humano da planilha; o nome de máquina manda na medida e no ano da edição, porque
o rótulo de grupo vem com nota de rodapé colada (`Nota SAEB - 20211` é a edição
de 2021). `ideb.verificar_series()` confere, edição a edição, se as séries lidas
são exatamente as que a etapa deve ter, e a carga para se não forem.

### 2. O identificador de escola do SAEB é irreversível

`ID_ESCOLA` é chave sequencial embaralhada, regerada a cada edição: não liga ao
Censo **nem entre edições do próprio SAEB**. Por isso o SAEB só entra no grão
município.

A perda é pequena, porque a nota do SAEB por escola já vem no IDEB
(`nota_matematica`, `nota_portugues`), com código real. Do SAEB aproveita-se o
que o IDEB não traz: distribuição por nível de proficiência, INSE e formação
docente.

`ID_MUNICIPIO`, ao contrário, **preserva a ordem**, o que revela uma renumeração
sequencial da lista ordenada por código IBGE. Quando a contagem bate — 78 = 78
no ES, nas cinco edições — o alinhamento posicional é a única correspondência
possível. `saeb.construir_mascara()` exige a igualdade e aborta sem ela.

A tradução foi validada contra sinal independente: o SAEB publica
`NU_MATRICULADOS_CENSO_*`, que vem do Censo. Comparando com o Censo carregado,
por município:

| edição | tradução correta | deslocada em 1 posição |
|---|---|---|
| 2015 | 0,9942 | 0,1575 |
| 2017 | 0,9956 | 0,1574 |
| 2019 | 0,9951 | 0,1505 |
| 2021 | 0,9953 | 0,1377 |
| 2023 | 0,9929 | 0,1313 |

### 3. Um pacote do IDEB por etapa basta

O pacote de 2025 dos anos iniciais e finais já traz as onze edições desde 2005,
e é **superconjunto** do pacote de 2015: 1.159 contra 937 escolas no ES, nenhuma
perdida. Baixar o histórico à parte é trabalho jogado fora — e ainda traria
planilhas sem linha de nomes de máquina.

## Escalas, medidas

| medida | faixa | escala |
|---|---|---|
| `ideb_escola.nota_matematica` / `nota_portugues` | 129 – 403 | SAEB, 0–500 |
| `ideb_escola.nota_media` | 2,4 – 9,7 | padronizada 0–10 (o N) |
| `ideb_escola.indicador_rendimento` | 0,11 – 1,00 | o P |
| `ideb_escola.ideb_observado` | 0,5 – 9,7 | N × P |
| `saeb_municipio.media_lp` / `media_mt` | 179 – 355 | SAEB, 0–500 |
| `paebes_aluno.proficiencia` | 86,6 – 484,2 | 0–500 |

As notas do IDEB, as médias do SAEB e a proficiência do PAEBES estão todas na
mesma família de escala e comparam-se direto. `nota_media` não — é a
padronização 0–10.

A identidade `ideb_observado = nota_media × indicador_rendimento` confere em
**15.860 de 15.860 linhas**, o que valida a despivotagem inteira: se alguma
medida tivesse ido para a coluna errada, a conta não fecharia.

## Camadas

```
raw.ideb_escola          187.207   IDEB longo: uma linha por medida publicada
raw.ideb_municipio        57.591
raw.enem_por_escola        3.813
raw.saeb_escola_<ano>      ~1.200   por edição, escola mascarada
raw.paebes_aluno_2025    378.564

stg.ideb_escola           19.354   largo por medida; PK (escola, ano, etapa)
stg.ideb_aprovacao_serie  75.187   a série vem do rótulo, não do sufixo
stg.ideb_municipio         5.503   PK inclui rede: o IDEB municipal é por rede
stg.enem_escola            3.813
stg.saeb_mascara_municipio           a tradução da máscara, por edição
stg.saeb_municipio                   médias ponderadas pelos presentes
stg.saeb_municipio_nivel             distribuição por nível de proficiência
stg.paebes_aluno         378.564
```

O IDEB entra em `raw` já em formato longo. É a única fonte em que `raw` não
reproduz o formato do arquivo, e de propósito: as 135 colunas largas por edição
existem porque são cômodas numa planilha, não porque descrevem o dado.

## Comparação com o Censo

Quatro visões juntam avaliação e Censo no grão em que cada fonte permite:

```sql
stg.v_ideb_censo      -- IDEB + atributos e matrícula da escola no mesmo ano
stg.v_enem_censo      -- ENEM por Escola + Censo
stg.v_saeb_censo      -- SAEB por município + matrícula, com % de cobertura
stg.v_paebes_escola   -- PAEBES agregado de aluno para escola
```

São visões, não tabelas: não comprometem nenhuma decisão de modelagem
dimensional, que é o que ainda está em aberto.

Duas advertências valem para todas:

- **a avaliação é bienal e o Censo é anual.** A junção é por ano exato, então só
  há linha nos anos de edição. Nada é propagado para o ano seguinte;
- **a etapa da avaliação e a etapa do Censo não são a mesma granularidade.** A
  matrícula ao lado dá ordem de grandeza; não é o denominador do indicador.

## O que ainda não foi decidido

[`pendencias.md`](pendencias.md) lista as decisões que mudam o resultado
analítico e não têm resposta óbvia no dado: a ponte entre as etapas das quatro
fontes e a `dim_etapa` do Censo, a regra de agregação do PAEBES, o tratamento
das cinco escolas de 2005 que antecedem o Censo carregado e a política temporal
do fato. Estão registradas em vez de resolvidas no impulso — é por isso que a
camada `dw` das avaliações ainda não existe.
