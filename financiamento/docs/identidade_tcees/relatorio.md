# Identidade visual do Painel de Controle do TCE-ES — o que foi extraído

Evidência de onde vem cada escolha visual do `dashboard.html` adaptado. Nada
aqui foi estimado a partir de screenshot: os valores são estilos **computados**
lidos do DOM renderizado e regras lidas do **CSS-fonte** servido pelo painel.

- **Página medida:** <https://paineldecontrole.tcees.tc.br/areasTematicas/educacao/visaoGeral/2026/todos/todos/null/null/1>
- **Data da captura:** 2026-09-23
- **Versão do painel:** `2026.9.7.1.8` (impressa sob o logo, veja `viewport.png`)
- **Como reproduzir:** `python docs/identidade_tcees/capturar.py` e
  `python docs/identidade_tcees/capturar_conteudo.py` (Playwright + Chromium)

## Arquivos desta pasta

| Arquivo | O que é |
|---|---|
| `capturar.py` | Abre a URL em Chromium real, espera a SPA, tira screenshots e extrai estilos computados |
| `capturar_conteudo.py` | Segunda passagem: aceita cookies, rola a página e mede 4 rotas |
| `viewport.png` | Viewport inicial 1440×900 — header, menu lateral, breadcrumb, painel |
| `pagina_completa.png` | Página inteira da rota de Educação |
| `home.png`, `educacao_2024.png`, `educacao_2026.png`, `estado.png` | Segunda passagem |
| `extracao.json` | Variáveis CSS, componentes, paleta por frequência, logos, fontes |
| `extracao_conteudo.json` | Medições das 4 rotas |
| `painel_index.css` | **CSS-fonte do painel** (505 KB), baixado de `/css/index-C8qlcENs.css` |
| `conferir_dashboard.py` | Renderiza o `dashboard.html` gerado, mede os tokens aplicados e captura cada visão em `conferencia/` |
| `conferir_cnca.py` | Confere a aba "CNCA — Auditoria": renderização, anotações persistindo no `localStorage` após recarregar, "ver fonte" do ICA e o CSV exportado |
| `conferencia/` | Screenshots do dashboard adaptado, visão a visão (evidência de que a identidade foi aplicada) |

## Achado que muda o enunciado: o painel não é Angular

O prompt desta etapa supunha uma SPA Angular. A stack real, lida das folhas de
estilo carregadas (`extracao.json` → `folhas`) e do DOM, é:

- **PrimeReact** com o tema **saga-blue** (`/Content/css/primereact/resources/themes/saga-blue/theme.css`)
- **Material-UI (MUI)** em parte dos componentes — o DOM traz `MuiPaper-root`,
  `MuiGrid-root`, `MuiListItem-root`, `MuiBreadcrumbs-li`
- **Bootstrap 3.4.1** e **Font Awesome 5.15.4**, ambos via CDN
- Bundle com nome em padrão Vite (`index-C8qlcENs.css`)

Ou seja: **React**, não Angular. Isso está corrigido na nota de integração do
README — muda quem componentiza e como, não o resultado visual.

## 1. Tokens do tema (PrimeReact saga-blue)

Lidos de `getComputedStyle(document.documentElement)` — são variáveis CSS reais
em `:root`, não deduções. Lista completa em `extracao.json` → `varsComputadas`
(168 variáveis; abaixo só as semânticas).

| Variável | Valor |
|---|---|
| `--primary-color` | `#2196f3` |
| `--primary-color-text` | `#ffffff` |
| `--text-color` | `#495057` |
| `--text-color-secondary` | `#6c757d` |
| `--surface-card` / `--surface-a` | `#ffffff` |
| `--surface-ground` / `--surface-b` | `#f8f9fa` |
| `--surface-border` / `--surface-d` | `#dee2e6` |
| `--surface-hover` / `--surface-c` | `#e9ecef` |
| `--border-radius` | `3px` |
| `--focus-ring` | `0 0 0 0.2rem #a6d5fa` |
| `--highlight-bg` | `#e3f2fd` |
| `--content-padding` | `1rem` |
| `--font-family` | stack de sistema (**sobrescrita** — veja §2) |

> O `--font-family` do tema é o stack de sistema do PrimeReact, mas o painel o
> sobrescreve em `html,body`. A fonte que de fato renderiza é Open Sans.

## 2. Tipografia

Do CSS-fonte do painel:

```css
html,body { background-color:#f9f9f9; font-family:Open Sans,sans-serif;
            font-size:14px; font-weight:400 }
html      { font-size:14px }
```

E das folhas carregadas: `https://fonts.googleapis.com/css?family=Open+Sans:300,400,600,700,800&display=swap`.

Confirmado pelos estilos computados (`extracao.json` → `tipografia.familias`):
26 elementos com texto renderizam em `"Open Sans", sans-serif`; os 14 restantes
em `Roboto, Helvetica, Arial` — são componentes MUI que não foram sobrescritos.

| Uso | Valor | Fonte da evidência |
|---|---|---|
| Base rem | **14px** | `html { font-size:14px }` |
| Corpo | 14px / peso 400 | `html,body` |
| Menu de topo | 14px / peso **700** | `.menu-item` |
| Breadcrumb | 14px / peso **600** / line-height 42px | `#breadcrumb .breadcrumb .items` |
| Título de card | 14px / peso **600** | `.widget .widget-heading .widget-title` |
| Cabeçalho de tabela | peso **700** | `.p-datatable.datagrid .p-datatable-thead tr th` |
| Tabela | Open Sans 14px | `#datagrid .p-datatable.datagrid` |

Pesos computados observados: 400 (27×), 700 (10×), 600 (3×).

## 3. Paleta real

Contagem de ocorrências de cada hex no CSS-fonte do painel, com o contexto de
uso de cada uma (o contexto é o que dá o significado, não o hex sozinho).

| Cor | Ocorrências | Onde é usada |
|---|---|---|
| `#112b54` | 36 | Azul-marinho da marca: `.menu-item .title`, `#breadcrumb .items`, títulos de seção, `.loading` |
| `#1b5f9d` | 34 | Azul médio: links do rodapé, `#backToTop`, indicador IEGM, `#dadosAbertos .titulo-icones-conjunto` |
| `#e4e4e4` | 31 | Borda/divisor: `.widget-heading` border-bottom, breadcrumb border-bottom, `.menu-item .title.active` |
| `#364b60` | 28 (+11 de `#354b60`) | Azul-ardósia: texto do breadcrumb, `.widget-title`, ícones |
| `#aaacae` | 26 | Cinza apagado: links do rodapé mobile, `.widget-popover`, base das sombras |
| `#212121` | 26 | Texto forte / `--surface-900` |
| `#f9f9f9` | 18 | Fundo da página e do `.widget-heading` |
| `#607d8b` | 9 | Cinza-azulado dos KPIs (`.etiqueta`) |
| `#f8d96a` | 4 | Amarelo de destaque, barra à esquerda de títulos |

Confirmado no DOM (`extracao.json` → `paleta.texto`): `rgb(17,43,84)` é a cor
de texto mais frequente (21 elementos, todos `span.title`/`a.title` do menu).

## 4. Componentes observados

### 4.1 Card — `.widget`

O contêiner canônico do painel:

```css
.widget { border:1px solid #f5f5f5; border-radius:5px; box-shadow:0 0 18px #aaacae73 }
.widget .widget-heading { background-color:#f9f9f9; border-bottom:1px solid #e4e4e4;
                          padding:5px 10px; display:grid; grid-template-columns:1fr 15px }
.widget .widget-heading .widget-title { color:#364b60; font-size:14px; font-weight:600 }
.widget .widget-body { padding:10px; display:flex; flex-direction:column; align-items:center }
```

Existe também o `p-panel` do PrimeReact, medido no DOM da própria página de
Educação (é o card "Dados sobre escolas públicas…" do `viewport.png`):
header `background #f8f9fa`, `color #495057`, `border-bottom 1px solid #dee2e6`,
altura 44px, Open Sans 14px.

### 4.2 KPI — `.etiqueta`

```css
.etiqueta .conteudo { opacity:.85; align-items:flex-start; padding:10px 0; display:flex }
.etiqueta .conteudo:hover { opacity:1 }
.etiqueta .conteudo .icone-etiqueta    { color:#607d8b; font-size:24px }
.etiqueta .conteudo .descricao-etiqueta { color:#607d8b; font-size:1.3em; font-weight:400 }
.etiqueta .conteudo .valor-etiqueta     { color:#607d8b; font-size:1.3em; font-weight:600 }
```

Padrão: ícone + rótulo + valor na horizontal, tudo no mesmo cinza-azulado, com
o valor distinguido só pelo peso (600 contra 400). **Não há cor de destaque nem
borda colorida no KPI padrão do painel.**

### 4.3 Breadcrumb — `#breadcrumb`

```css
#breadcrumb .breadcrumb { background-color:#f9f9f9; border-bottom:1px solid #e4e4e4;
                          border-radius:0; padding:0; font-family:Open Sans,sans-serif }
#breadcrumb .breadcrumb .items { color:#112b54; border-right:1px solid #e4e4e4;
                                 padding:0 5px; font-size:14px; font-weight:600;
                                 line-height:42px; display:flex; align-items:center }
#breadcrumb .breadcrumb .items span, #breadcrumb .breadcrumb .items div { color:#364b60 }
#breadcrumb .breadcrumb .items.disabled > * { opacity:.4 }
#breadcrumb { position:sticky; top:0; width:100% }
```

**Trilha real observada** na página de Educação (`viewport.png` e
`extracao.json` → `textoNav`): `Áreas temáticas › Educação ▾ › Visão geral ▾`.
Os itens são separados por **borda vertical**, não por chevron; o primeiro item
está esmaecido (`.disabled`, `opacity .4`); os seguintes trazem uma seta de
dropdown. Cada item tem um ícone à esquerda (`.items .icon`, `color #364b60`,
máx. 22×17px).

### 4.4 Menu de topo — `.menu-item`

```css
.menu-topo-container { background-color:#fff; height:4em; display:flex;
                       justify-content:space-between; align-items:center }
.menu-item { height:55px; font-size:14px; font-weight:700; display:flex; align-items:center }
.menu-item .title { color:#112b54; padding:17px 10px; text-decoration:none }
.menu-item .title.active { background-color:#e4e4e4 }
```

Itens observados: Municípios, Estado, Obrigações, Prestações de contas,
Fiscalizações, Áreas temáticas, Boletins. Cada um com ícone Font Awesome à
esquerda e caret à direita quando tem submenu.

### 4.5 Tabela — `.p-datatable.datagrid`

```css
#datagrid .p-datatable.datagrid { font-family:Open Sans,sans-serif; font-size:14px }
#datagrid .p-datatable.datagrid .p-datatable-thead tr th { padding:10px; font-weight:700; white-space:nowrap }
#datagrid .p-datatable.datagrid .p-datatable-tbody tr td { padding:6px }
#datagrid .p-datatable.datagrid.p-datatable-striped .p-datatable-tbody tr:nth-child(2n) { background:#f7f7f7c7 }
#datagrid .p-datatable.datagrid .p-datatable-tbody tr.municipio-selecionado { background-color:#cfdae3!important }
#datagrid .p-datatable.datagrid .p-datatable-footer,
#datagrid .p-datatable.datagrid .p-datatable-tfoot { font-size:15px; font-weight:600 }
.text-right { text-align:right!important }
```

### 4.6 Alertas — `#alerta`

**Isto responde diretamente ao requisito de "abaixo do mínimo": o painel já tem
uma semântica de alerta própria, e ela é esta.**

```css
#alerta         { border-radius:2px; margin-bottom:20px; padding:10px }
#alerta.danger  { color:#a94442; background-color:#f2dede; border-left:5px solid #ebccd1 }
#alerta.warning { color:#ad741b; background-color:#fcf8e3; border-left:5px solid #ad741b99 }
#alerta.success { color:#3c763d; background-color:#dff0d8; border-left:5px solid #d6e9c6 }
#alerta.info    { color:#315f8f; background-color:#ddeefa; border-left:5px solid #83b0d1 }
```

Padrão: **barra de 5px à esquerda**, fundo claro da mesma matiz, texto escuro,
raio 2px.

### 4.7 Escala de conformidade (notas ISP / IEGM)

O painel classifica desempenho numa escala A→D com cores fixas
(`.circuloNotasIEG`, `.circuloNotasISP`, `#graficoISP`, `.label-*`):

| Nota | Fundo | Borda |
|---|---|---|
| A / A+ | `#2f9e23` | `#26801c` |
| B+ | `#a7d489` | `#2f9e23` |
| B | `#fff8b8` | `#ced05f` |
| C+ / C | `#f4b350` | `#d09844` |
| D | `#e68364` | `#d44242` |

### 4.8 Receita e despesa

Diretamente aplicável a este dashboard — o painel já tem convenção para isso:

```css
#indicadoresConsolidados .secao-receita { color:#486d19 }   /* verde escuro */
#indicadoresConsolidados .secao-despesa { color:#872424 }   /* vinho */
#paginaInicial .table-arrecadao-despesa .conteudo-td.destaque-total-verde    { color:#459d49 }
#paginaInicial .table-arrecadao-despesa .conteudo-td.destaque-total-vermelho { color:#c0392b }
```

Visível em `home.png`: "Receitas 32.0B / 28.9B" em verde e "Despesas 29.3B /
26.3B" em vermelho, peso 700, `font-size:1.9rem`.

### 4.9 Título de seção com barra amarela

```css
.titulo-modal { color:#112b54; border-left:5px solid #f8d96a; padding:5px 15px; font-weight:700 }
```

Visível em `home.png` nos títulos "Educação", "Destino do dinheiro", "Cargos e
empregos", "Limites com educação" — barra amarela vertical à esquerda de um
título azul-marinho em negrito.

### 4.10 Sankey — já existe no painel

```css
#destinoDinheiro .sankeyFuncaoEmpenho { width:100%; white-space:nowrap }
#destinoDinheiro .breadcrumbInterno .checkboxContainer { color:#364b60; font:700 14px Open Sans,sans-serif }
```

O painel já usa um Sankey de fonte → função de empenho na seção "Destino do
dinheiro" (`home.png`). O Sankey receita→despesa deste dashboard é, portanto,
um componente **coerente com o painel**, não uma invenção nossa.

## 5. Forma e elevação

| Token | Valor | Evidência |
|---|---|---|
| Raio de card | `5px` | valor mais frequente no CSS (18×), usado em `.widget` |
| Raio de controle | `3px` | `--border-radius` do tema |
| Raio de alerta | `2px` | `#alerta` |
| Sombra de card | `0 0 18px #aaacae73` | `.widget` |
| Sombra de elevação | `0 2px 1px -1px #aaacae33, 0 1px 1px #aaacae24, 0 1px 3px #aaacae1f` | MUI elevation 1, tintada com `#aaacae` |
| Anel de foco | `0 0 0 0.2rem #a6d5fa` | `--focus-ring` do tema |
| Altura do menu | `55px` | `.menu-item` |
| Padding de conteúdo | `1rem` | `--content-padding` |

## 6. Marca

- **Logo:** `/Content/img/logo-painel.png` — 121×37px, alt "Logo Painel de Controle"
- **Favicon:** `/Content/img/favicon.ico`
- Brasão do TCE-ES e logo "cidades" no canto superior direito do header

Nenhum dos dois é redistribuído neste repositório: o dashboard é autocontido e
não pode depender de imagem hospedada no painel, e reusar a marca do TCE-ES num
protótipo exigiria autorização. O cabeçalho adaptado usa **texto**, não o logo.

## 7. O que NÃO foi possível observar

Registrado por honestidade — nada abaixo foi inventado no dashboard adaptado.

- **Gráficos com dados.** Nenhuma das 4 rotas medidas renderizou KPI, tabela ou
  gráfico com dados (`extracao_conteudo.json`: `etiqueta=0 tabela=0 grafico=0`
  em todas). A rota de Educação carrega só o painel de descrição; a home é
  institucional. Sem isso, **não há paleta de séries de gráfico observada** — o
  dashboard mantém a paleta de dados que já tinha (validada em contraste), só
  realinhando a primeira série ao azul do painel.
- **Modo escuro.** O painel tem só o tema claro. O modo escuro do dashboard é
  extensão nossa, derivada dos tons do painel, e está marcado como tal nos tokens.
- **Estado de hover/foco de linha de tabela** além do `.municipio-selecionado`.

## 8. Decisão sobre a fonte

O painel carrega Open Sans do Google Fonts. Este dashboard é um HTML
autocontido que roda de `file://` e cujo princípio é não chamar rede para dado.
Embutir Open Sans em base64 acrescentaria centenas de KB a um arquivo que já
tem 18 MB.

**Decisão:** usar a pilha `"Open Sans", "Segoe UI", system-ui, sans-serif` —
renderiza em Open Sans em qualquer máquina que a tenha instalada (o caso comum
no TCE-ES, já que o painel a serve) e degrada para a fonte do sistema fora
disso. Se a equipe do painel incorporar o dashboard, a Open Sans já estará
carregada pela página hospedeira e a pilha resolve para ela sem alteração.
