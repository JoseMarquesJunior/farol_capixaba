# Farol Capixaba

Dados e análises sobre a rede de ensino do Espírito Santo.

## O que tem aqui

| | |
|---|---|
| [`docs/`](docs) | O site **Farol Capixaba da Educação**, publicado pelo GitHub Pages |
| [`educacao/`](educacao) | Pipeline do Censo Escolar: dicionário → PostgreSQL → modelo dimensional |
| [`analises/`](analises) | Scripts exploratórios e geoespaciais |
| `modulos/` | Utilitários geo e de plotagem compartilhados |

## O site

`docs/` é servido pelo GitHub Pages em **Settings → Pages → Source: `main` /docs**.
Os três arquivos se linkam por caminho relativo e precisam ficar juntos nessa
pasta — mover qualquer um quebra a navegação do site.

## O pipeline do Censo

19 anos de microdados do Censo Escolar (2007–2025), recortados para o Espírito
Santo, em PostgreSQL. Documentação completa em
[`educacao/readme.md`](educacao/readme.md).

```powershell
python -m pip install -r requirements.txt
python -m educacao.metadata.catalogo       # dicionários -> catálogo
python -m educacao.database.aplicar        # schemas + meta
python -m educacao.database.ddl --aplicar  # tabelas de raw
python -m educacao.etl.carga               # COPY filtrado para o ES
python -m educacao.database.stg --aplicar
python -m educacao.database.stg --carregar
python -m educacao.database.dw --carregar
```

Os comandos rodam a partir da raiz do repositório. A conexão vem de
`educacao/.env`, que não é versionado.

## O que fica fora do git

Os ~13 GB de microdados (`educacao/data/`), os mapas gerados em `analises/`, e
as pastas de entregas fechadas, que têm repositório próprio.
