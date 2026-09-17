# Projeto educacao

Arquitetura de dados do Censo Escolar: data lake local + PostgreSQL.

## Escopo

- **Anos: 2007 a 2025.** É a faixa com dicionário de dados `.xlsx` estruturado.
  De 1995 a 2006 os microdados usam outro layout (`CENSOESC_<ano>.CSV`,
  delimitador `|`, nomenclatura legada) e só têm PDF como documentação.
- **Recorte geográfico: Espírito Santo**, aplicado na carga.

## Estrutura

```
educacao/
├─ config/          conexão, caminhos e log
├─ metadata/        catálogo derivado do dicionário do INEP
│  ├─ catalog/      o catálogo gerado (JSON, versionado)
│  └─ de_para.yml   relações das variáveis descontinuadas
├─ etl/             extração e carga para raw
├─ database/        modelo do banco
│  └─ sql/          DDL de schemas, meta, etl e dw
└─ data/            data lake local (fora do git)
   ├─ raw/          ZIPs originais do INEP
   └─ extracted/    arquivos extraídos
```

Fora deste diretório, na raiz do repositório:

- [`docs/`](../docs) — o site **Farol Capixaba da Educação**, publicado pelo
  GitHub Pages. Não mexa na estrutura sem conferir o Pages.
- [`analises/`](../analises) — scripts exploratórios e geoespaciais, com seus
  insumos e mapas. Não fazem parte do pipeline.
- `modulos/` — utilitários geo e de plotagem compartilhados.
- As três pastas de entregas fechadas (`eliminação_da_concorrência`,
  `infra_Bom_Jesus_do_Norte`, `reordenamento_da_rede`), que têm repositório
  próprio e ficam fora deste.

## Catálogo de metadados

O catálogo é a fundação de tudo o que vem depois: é dele que saem os
`CREATE TABLE`, os tipos de cada coluna e os domínios de valores.

```powershell
python -m educacao.metadata.catalogo            # gera catalog/<ano>.json
python -m educacao.metadata.catalogo --ano 2025 # um ano só
python -m educacao.metadata.canonico            # gera catalog/canonical.json
python -m educacao.metadata.validar             # confere catálogo x arquivos
```

### Como ele é montado

**O cabeçalho do CSV é a verdade** sobre quais colunas existem e em que ordem.
O dicionário apenas enriquece cada coluna com descrição, tipo, tamanho, domínio
e histórico de coleta.

O caminho inverso não funciona: a matriz "Coleta por ano" do dicionário registra
o que foi *coletado na pesquisa*, não o que saiu no arquivo publicado. Em 2015
ela marca 699 variáveis para um arquivo de 370 colunas, e na aba
`Tabela_Curso_Técnico` de 2025 a matriz sequer tem coluna para 2025. Com o CSV
mandando, os 19 anos fecham sem exceção: 26 tabelas, 7.797 colunas, zero órfãs.

### Conferência de tipos

O dicionário só distingue `Num`, `Char` e `Data`, e a coluna `Tam.` nem sempre
corresponde ao arquivo. Antes de gravar, `verificacao.py` mede os dados reais e
promove o tipo quando o declarado não comporta o valor. Todo ajuste fica em
`ajuste_tipo`, no próprio catálogo. Os 24 ajustes encontrados:

| Coluna | Anos | Declarado | Final | Motivo |
|---|---|---|---|---|
| `LATITUDE`, `LONGITUDE` | 2025 | `Num(20)` | `NUMERIC` | são decimais (`-11.9309573`) |
| `NU_TELEFONE` | 2007–2010 | `Num(8)` | `TEXT` | valores com espaço (`627 1146`) |
| `NU_DDD`, `NU_TELEFONE` | 2015–2022 | `Num` | `TEXT` | `.` (ausente do SAS) e notação científica (`9.8467E8`) |
| `NO_ENTIDADE` (curso técnico) | 2023–2024 | `Num(8)` | `TEXT` | contém o nome da escola |

A sujeira em colunas numéricas está confinada a `NU_TELEFONE` e `NU_DDD`:
varredura integral de 2015, 2022 e 2025 não achou nada fora delas. Por isso
`COPY ... NULL ''` basta para todo o resto.

### Defeitos conhecidos do dicionário do INEP

- **`CO_ENTIDADE` e `NO_ENTIDADE` trocados** na aba de Curso Técnico (2023,
  2024, 2025): o código é declarado `Char(100)` e o nome, `Num(8)`. O catálogo
  reproduz o declarado — `raw` é fiel à fonte. O acerto (cast para `INTEGER`)
  é da camada `stg`.
- **`QT_DOC_BAS_ESPEC_BIL_SURDOS`** está no CSV de Docente de 2025 mas marcada
  como não coletada em 2025 na matriz de anos. Irrelevante para a carga, já que
  quem manda é o cabeçalho do arquivo.
- **Datas em formato SAS** (`10FEB2025:00:00:00`). O PostgreSQL aceita
  `'10FEB2025'::date` mas **rejeita** a forma completa, então colunas `Data`
  entram em `raw` como `TEXT` e são convertidas em `stg`.

### Modelo canônico

`canonical.json` cruza os 19 anos: 1.053 variáveis no total, 93 descontinuadas
(48 saíram em 2022, 45 em 2024) e 4 com tipo variável entre anos. As
descontinuadas — `IN_FUND`, `IN_EJA_FUND`, `IN_ESP_CC`... — não têm equivalente
no desenho de 2025 e precisam de de-para manual antes da harmonização.

## Banco de dados

```powershell
python -m educacao.database.aplicar --limpar-legado  # schemas + meta + etl
python -m educacao.database.ddl --aplicar            # cria as tabelas de raw
python -m educacao.database.ddl --ano 2025           # só imprime o DDL
```

### Camadas

| Schema | Papel |
|---|---|
| `meta` | Catálogo materializado: layout, tipos e domínios consultáveis em SQL |
| `raw` | Fiel ao arquivo do INEP, já filtrado para o ES |
| `stg` | Harmonização entre anos, no desenho de 2025 |
| `dw` | Modelo dimensional |
| `etl` | Controle de carga |

### Convenções

- **Tabela**: `raw.<tabela>_<ano>` no singular — `raw.escola_2025`,
  `raw.matricula_2025`, `raw.curso_tecnico_2023`.
- **Coluna**: o nome do INEP em minúsculo, sem renomear nada.
- **Ordem**: idêntica à do CSV, para o `COPY` casar posicionalmente.
- **Tipos**: os do catálogo, já conferidos contra os dados.
- **Sem restrições em `raw`**: nem chave primária, nem `NOT NULL`, nem
  checagem de domínio. Em uma camada que existe para ser fiel à fonte, uma
  restrição só serviria para rejeitar dado real do INEP e travar a carga.
  Consistência é assunto da `stg`.
- **Comentários**: cada tabela e cada coluna carregam a descrição do
  dicionário, e as colunas com tipo ajustado dizem por quê. `\d+ raw.escola_2025`
  no psql mostra tudo.

O DDL não é escrito à mão: sai do catálogo. Conferência de aceitação —
7.797 colunas no catálogo, 7.797 no banco, zero divergências de nome, tipo
ou ordem.

### Filtro do Espírito Santo

Em 2007–2024 todas as tabelas têm `CO_UF`, então o filtro é direto. Em **2025
só `escola` tem** — `docente`, `matricula`, `turma`, `gestor` e `curso_tecnico`
trazem apenas `CO_ENTIDADE`. A carga de 2025 é, portanto, em duas fases:

1. `escola_2025` por `CO_UF = 32`;
2. as demais por pertencimento ao conjunto de `CO_ENTIDADE` resultante.

O filtro é aplicado durante o streaming para o `COPY`, não depois: nada do
resto do Brasil chega a entrar no banco.

## Carga (raw)

```powershell
python -m educacao.etl.carga              # todos os anos
python -m educacao.etl.carga --ano 2025
python -m educacao.etl.carga --forcar     # recarrega mesmo já tendo entrado
```

O `COPY` lê direto do CSV do INEP — nenhum arquivo intermediário em disco — e o
filtro do ES é aplicado linha a linha no caminho para o banco. Resultado da
carga completa: **5.072.382 linhas percorridas, 91.587 gravadas (1,81%)**, em 26
tabelas, sem falhas.

O filtro usa `CO_UF = 32` onde a coluna existe e o prefixo de `CO_ENTIDADE`
nas cinco tabelas de 2025 que só trazem o código da escola. A equivalência foi
conferida: das 214.192 escolas do Brasil em 2025, as 3.847 do ES têm código
iniciado em 32 e nenhuma escola de outra UF tem. Depois da carga, zero códigos
órfãos nas cinco tabelas dependentes.

Cada carga grava o sha256 do arquivo em `etl.carga`: repetir o comando não
recarrega o que já entrou, e uma republicação do INEP muda o hash.

### Série de escolas no ES

| | | | | |
|---|---|---|---|---|
| 2007: 3.821 | 2008: 3.732 | 2009: 3.661 | 2010: 3.516 | 2011: 4.568 |
| 2012: 4.535 | 2013: 4.406 | 2014: 4.351 | 2015: 4.342 | 2016: 4.307 |
| 2017: 4.266 | 2018: 4.258 | 2019: 4.086 | 2020: 4.041 | 2021: 4.035 |
| 2022: 4.047 | 2023: 4.037 | 2024: 3.970 | 2025: 3.847 | |

O salto de 2010 para 2011 acompanha a mudança nacional de escopo do Censo
(200.876 para 242.147 escolas no Brasil); a fatia do ES fica em 1,8–1,9% o
tempo todo.

## Camada stg

```powershell
python -m educacao.metadata.de_para           # valida o de-para contra o catálogo
python -m educacao.database.stg               # resumo do modelo
python -m educacao.database.stg --aplicar     # cria as tabelas
python -m educacao.database.stg --carregar    # executa as transformações
python -m educacao.database.stg --transformacao 2015   # imprime o SQL de carga
```

| Tabela | Colunas | Linhas | Anos |
|---|---|---|---|
| `stg.escola` | 368 | 77.826 | 2007–2025 |
| `stg.matricula` | 253 | 76.965 | 2007–2025 |
| `stg.docente` | 156 | 76.965 | 2007–2025 |
| `stg.turma` | 190 | 76.965 | 2007–2025 |
| `stg.gestor` | 65 | 3.046 | 2025 |
| `stg.curso_tecnico` | 20 | 1.757 | 2023–2025 |

### O de-para foi conferido contra o dado

Onde o indicador nativo e a contagem coexistem, a regra de derivação tem que
reproduzir o indicador. Em **73.966 linhas comparáveis, zero divergências** para
`in_bas`, `in_fund`, `in_inf`, `in_med`, `in_esp` e `in_eja_fund`. A série de
`in_fund` atravessa a descontinuação sem degrau: 1.997 (2023), 1.959 (2024),
1.930 (2025) — os dois primeiros nativos, o último derivado.

O join que o defeito do dicionário quebraria também fecha: 1.757 de 1.757 linhas
de `stg.curso_tecnico` casam com `stg.escola` por `co_entidade`.

### O que a stg faz

1. **Decompõe** o arquivo largo de 2007–2024 nas entidades que 2025 separou.
   `INSERT INTO stg.matricula ... FROM raw.escola_2015` é a decomposição em ação.
2. **Aplica o de-para** de `educacao/metadata/de_para.yml`.
3. **Harmoniza tipos** que variam entre anos.

Toda variável já coletada vira coluna, nula nos anos em que não existiu. Nada é
descartado — o nulo diz "não coletado naquele ano", não "zero".

Sem particionamento: com o recorte do ES são ~4 mil escolas por ano, ~80 mil
linhas em 19 anos. Particionar só acrescentaria complexidade.

### O de-para

As 93 variáveis descontinuadas foram classificadas uma a uma, com base na
descrição das duas pontas no dicionário — **não** por semelhança de nome:

| Relação | Quantas | Exemplo |
|---|---|---|
| `renomeadas` | 11 | `QT_MAT_MED_CT` → `QT_MAT_MED_IFTP_CT` (CT virou Itinerário Formativo Técnico e Profissional) |
| `derivadas` | 34 | `IN_FUND` a partir de 2025 = `(qt_mat_fund > 0)` |
| `sem_equivalente` | 48 | `IN_EQUIP_FAX`, `QT_SALAS_EXISTENTES` |

O caso que mostra por que semelhança de nome não serve: `IN_FUND` ("a escola
oferece Ensino Fundamental") parece casar com `IN_COMUM_FUND_AI`, que na verdade
é "oferece matrícula de aluno com deficiência em classe comum". São coisas
diferentes; a continuidade real de `IN_FUND` vem da contagem de matrículas.

`sem_equivalente` não descarta nada: a coluna existe na stg, preenchida nos anos
em que foi coletada e nula depois. O que não se afirma é equivalência — por
exemplo, `QT_COMPUTADOR` (quantidade, até 2022) e `IN_COMPUTADOR` (presença, de
2023) não são a mesma variável, e somar ou copiar um no outro seria inventar dado.

`python -m educacao.metadata.de_para` confere todas as relações contra o
catálogo: nome inexistente, variável não descontinuada, origem na tabela errada
ou descontinuada esquecida aparecem como falha.

### Tipos harmonizados

Quatro colunas mudam de tipo entre anos e convergem na stg:

| Coluna | stg | Por quê |
|---|---|---|
| `co_entidade` | `INTEGER` | Declarada `Char(100)` na aba de Curso Técnico — o dicionário troca `CO_ENTIDADE` com `NO_ENTIDADE` ali. Sem o cast, o join contra escola falha. |
| `no_entidade` | `VARCHAR(100)` | Mesmo defeito, lado inverso |
| `nu_ddd` | `SMALLINT` | `'.'` (ausente do SAS) de 2015 a 2022 vira nulo |
| `nu_telefone` | `BIGINT` | Idem, mais notação científica (`9.8467E8`) recuperada via `numeric`, e valores com espaço (`627 1146`) que viram nulo |

## Camada dw

```powershell
python -m educacao.database.dw --carregar
```

Grão real: **escola x ano**, que é o grão do próprio Censo.

| Tabela | Linhas | |
|---|---|---|
| `dw.dim_escola` | 5.102 | uma por escola; nome, município e geo do ano mais recente |
| `dw.dim_municipio` | 78 | os 78 municípios do ES, com meso e microrregião |
| `dw.dim_tempo` | 19 | 2007–2025 |
| `dw.dim_etapa` | 9 | etapas e recortes de matrícula |
| `dw.dim_dependencia` / `dim_localizacao` / `dim_situacao` / `dim_categoria_privada` | 4 / 2 / 4 / 5 | carregadas de `meta.dominio` |
| `dw.fato_escola_ano` | 77.826 | escola x ano: FKs, totais e infraestrutura |
| `dw.fato_matricula` | 165.456 | escola x ano x etapa, esparso |

### O cuidado que o modelo carrega

**`qt_mat_bas` não é a soma das etapas.** As categorias do INEP se sobrepõem:
quem está no Ensino Médio Integrado conta em `QT_MAT_MED` **e** em
`QT_MAT_PROF`. No ES de 2025 a soma ingênua excede o total em 46.640
matrículas — um fato que convidasse a somar produziria número errado em
silêncio.

Por isso:

* o total em `fato_escola_ano` é o do INEP, sem recalcular;
* `dim_etapa.exclusiva` marca as sete etapas que particionam a matrícula
  (creche, pré-escola, anos iniciais, anos finais, médio, EJA fundamental,
  EJA médio). Somar só sobre elas não dupla-conta;
* Educação Profissional e Educação Especial entram como **recortes
  transversais**, com `exclusiva = false`, e nunca devem ser somados às etapas.

As subpartições finas foram conferidas em 73.966 linhas sem divergência
(creche+pré=infantil, AI+AF=fundamental, EJA fund+EJA médio=EJA,
esp_cc+esp_ce=especial). `prof_tec+prof_nao_tec=prof` diverge em 189 linhas,
e por isso a Educação Profissional entra inteira, sem subdivisão.

Reconciliação: a soma das etapas exclusivas fica abaixo do total do INEP por
20 a 30 mil matrículas em todos os anos — a educação profissional avulsa, que
não pertence a nenhuma etapa regular.

### Código fora do dicionário

`tp_categoria_escola_privada = 0` aparece em 51.972 escolas-ano entre 2008 e
2021 e **não está no dicionário** — o INEP passou a gravar nulo depois disso.
Não é puramente "não aplicável": 49.627 são escolas públicas, mas 2.345 são
privadas que não informaram. Entra na dimensão como "Não aplicável ou não
informado".

A carga trata isso de forma geral: qualquer código presente no dado e ausente
do dicionário entra com rótulo explícito e um aviso no log, em vez de quebrar
a carga ou sumir silenciosamente.

## Fluxo previsto

```powershell
python -m educacao.metadata.catalogo          # 1. dicionários -> catálogo
python -m educacao.metadata.canonico          # 2. modelo canônico entre anos
python -m educacao.database.aplicar           # 3. schemas + meta + etl
python -m educacao.database.ddl --aplicar     # 4. CREATE TABLE de raw
python -m educacao.etl.carga                  # 5. COPY filtrado para o ES
python -m educacao.database.stg --aplicar     # 6. tabelas da stg
python -m educacao.database.stg --carregar    # 7. harmonização
python -m educacao.database.dw --carregar     # 8. modelo dimensional
```

Verificações, todas com saída própria e código de saída:

```powershell
python -m educacao.metadata.validar    # catálogo x arquivos
python -m educacao.metadata.de_para    # de-para x catálogo
```
