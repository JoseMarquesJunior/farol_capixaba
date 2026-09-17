# analises

Scripts exploratórios e geoespaciais, separados do pipeline do Censo, que vive
em [`educacao/`](../educacao).

## Convenção

Os scripts são executados **a partir da raiz do repositório**, como todo o
resto do projeto:

```powershell
python analises/visualizar_escolas.py
```

Os caminhos dentro deles são relativos à raiz — tanto os insumos do pipeline
(`educacao/data/...`) quanto os arquivos desta pasta (`analises/...`).

## O que é versionado

Só os `.py`. Os `.xlsx` e `.html` ficam fora do git (~162 MB): os HTML são
saída reproduzível dos próprios scripts, e as planilhas são insumos ou
resultados intermediários.

## Dependências

Estes scripts usam `pandas`, `geopandas`, `plotly`, `numpy` e `geopy`, que
**não estão instalados** no `.venv` atual — o ambiente tem só o necessário
para o pipeline do Censo. O bloco correspondente está comentado em
[`requirements.txt`](../requirements.txt); descomente antes de rodá-los.

## Arquivos

| Script | O que faz |
|---|---|
| `tratamento_microdados_censo_educacao.py` | Extrai escolas do ES do Censo 2025 e geocodifica endereços |
| `visualizar_escolas.py` | Mapa das escolas do ES com matrículas |
| `visualizar_geodados.py` | Mapa dos setores censitários do ES |
| `merge_setores_com_dados_demograficos.py` | Cruza setores censitários, demografia do IBGE e escolas |

| Dado | Origem |
|---|---|
| `escolas_ES.xlsx`, `escolas_ES_ativas.xlsx` | gerados pelos scripts acima |
| `bairros.xlsx`, `setores.xlsx` | insumos do IBGE |
| `*.html` | mapas gerados |
