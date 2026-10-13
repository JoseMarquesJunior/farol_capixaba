# Financiamento da educação — municípios do Espírito Santo

Painel de apoio à auditoria (TCE-ES) sobre **de onde vêm** as receitas vinculadas à
educação nos 78 municípios do ES e **onde cada valor é aplicado**. Feito para servir
de evidência, não só de visualização: todo número exibido leva a um botão
**“ver fonte”** que mostra a consulta exata que o produziu — endpoint, parâmetros,
anexo/linha/coluna ou item do demonstrativo, cálculo, instante da coleta e o
arquivo do cache local que guarda a resposta original. É o equivalente da nota de
rodapé de um papel de trabalho.

* **`dashboard.html`** — painel autocontido, sem servidor. Abra no navegador. Leva
  dentro os 390 PDFs do SIOPE que sustentam os números do MDE (daí os 45 MB).
* **`novo_dashboard.html`** e **`novo_cnca_evidencias.html`** — o painel refeito a partir
  da auditoria de UX de 30/09/2026, com o papel de trabalho do CNCA num arquivo à parte.
  Convive com o `dashboard.html`, que não mudou — ver [o painel novo](#o-painel-novo-novo_dashboardhtml).
* **`dados/processado/consolidado.csv`** — o dataset consolidado: **um número por
  linha, com a proveniência na própria linha** (170.141 registros hoje).
* **`dados/bruto/`** — a resposta original de cada consulta, por fonte e exercício.
* **`dados_manuais.yaml`** — tudo que não vem de fonte automatizável, com fonte e data por registro.

Fontes: **SICONFI** (API do Tesouro), **SIOPE** (FNDE; Anexo 8 em PDF), **FNDE**
(repasses publicados pela CGU), **TCE-ES** (dados abertos do Tribunal: empenhos, obras,
MDE apurado, prazos) e o **Censo Escolar** do banco local do NEDUC. O navegador nunca
chama API: o ETL em Python gera o dataset e o HTML o embute (Chart.js vem de CDN, com
versão e hash fixados).

## Como reproduzir

A partir da **raiz do repositório**:

```powershell
python -m pip install -r financiamento/requirements.txt
python -m financiamento.etl.pipeline            # as seis fontes; usa o cache e só consulta o que falta
python -m financiamento.build_dashboard         # monta financiamento/dashboard.html
python -m financiamento.build_novo_dashboard    # monta novo_dashboard.html e novo_cnca_evidencias.html
python -m pytest financiamento/tests            # sem rede
```

Cada fonte **religa sozinha**, sem tocar as outras:

```powershell
python -m financiamento.etl.pipeline --fontes siope     # só o SIOPE usa a rede; SICONFI e FNDE leem o cache
python -m financiamento.etl.siconfi --anos 2021-2025    # só o SICONFI (receita, MSC, entregas)
python -m financiamento.etl.siope   --anos 2021-2025    # só o SIOPE (PDFs do FTP do FNDE)
python -m financiamento.etl.fnde    --anos 2021-2025    # só os repasses do FNDE (CGU)
python -m financiamento.etl.tcees   --anos 2021-2025    # só o TCE-ES (MDE, prazos, obras, medições, empenhos, dotação, itens)
python -m financiamento.etl.ica                         # só o ICA do INEP (planilha oficial, hash SHA-256 conferido)
python -m financiamento.etl.comparar                    # o que mudou entre as duas últimas extrações
```

Uma fonte que falha **não derruba as outras**: o erro vai para
`meta.fontes_status` (e para o rodapé do painel), e o resto do dataset sai normalmente.
A primeira coleta completa leva cerca de duas horas (≈7 mil consultas ao SICONFI, 390
PDFs do SIOPE, 60 arquivos da CGU baixados um a cada 20 s, e ~2,9 GB do TCE-ES: 19 ZIPs
de empenhos, 5 de despesas, o arquivo de medições e os 5 de contratações e itens, lidos
em fluxo); as seguintes leem o cache em ~10 minutos. Operação,
opções e cache em [`etl/README.md`](etl/README.md).

## O painel

| Visão | Responde |
|---|---|
| **Conformidade** (abre aqui) | MDE vs 25% (SIOPE **e** TCE-ES, com ⚑ quando as duas apurações discordam sobre o mínimo) e FUNDEB vs 70%; RREO/RGF/DCA fora do prazo; remessas mensais ao TCE-ES; obras da Educação paradas; conciliação entre fontes |
| **Receita → aplicação** | De onde vem a receita; o fluxo **fonte de recursos → subfunção** (Sankey); pessoal/custeio/investimento; **Nível 3**: maiores credores, ações orçado × executado, fonte com detalhamento, repasses a conselhos escolares, **itens contratados**, obras com prédio e medições; comparação lado a lado. Clicar no nome de um credor ou de uma ação abre o **detalhamento**: em que ações aquele credor aparece (ou quem recebeu naquela ação), com elemento e fonte, e o que as contratações dizem ter comprado |
| **Panorama do ES** | Quanto se gasta, no que, quem gasta mais, execução bimestral, cobertura |
| **Ficha do município** | Tudo de um ente: subfunções, série, execução, FUNDEB em três fontes, mínimos legais, programas |
| **Escolas** | Cada escola pública do município (Censo): PDDE por plano orçamentário (inclusive o CNCA), repasse municipal ao conselho, obra no prédio, R$ por aluno, ao lado de matrículas, infraestrutura, IDEB e PAEBES; e os recebedores que não foram ligados a uma escola |
| **Programas federais** | CNCA: repasse **automático** (PDDE-CNCA por município e por escola, apoio ao Estado, gasto FUNPAES) e ICA do INEP; adesão e bolsa de articulador como registros manuais |
| **CNCA — Evidências** | **Papel de trabalho da fiscalização** do financiamento do CNCA: as 6 questões da matriz de planejamento e seus 23 achados, o mapa município × achado, a ficha de cada ente, o que o dado público responde de cada uma das **49 perguntas** do questionário, e o painel de cobertura. Cada célula leva ao registro bruto. Nada ali é achado de auditoria — é **indício** — ver [a seção própria](#cnca--evidências-da-fiscalização) |

No topo de todas as visões, a faixa de **KPIs de conformidade** do exercício
escolhido: municípios abaixo do mínimo de MDE, com declaração em atraso, a maior
divergência entre fontes e os abaixo de 70% no FUNDEB. Abaixo do mínimo aparece em
vermelho **com símbolo e texto** (✖); divergência entre fontes, que é sinal a
investigar e não irregularidade por si, leva ⚑. Filtros por exercício e município,
comparação de até 4 municípios, tabela e CSV por trás de cada gráfico, tema claro e
escuro. No ranking do Panorama, um seletor de **tipo de despesa** (subfunção da função 12:
ensino fundamental, educação infantil, administração geral…) isola uma etapa, e o botão
**Baixar Excel** gera um `.xlsx` de verdade — escrito pela própria página, sem biblioteca
externa — com a aba "Dados" (cabeçalho fixo, filtro automático) e a aba "Recorte", que
registra exercício, indicador, tipo de despesa, busca e ordenação ativos na hora da exportação. Para **Ensino Fundamental (12.361)** e **Ensino Médio (12.362)**, o "por matrícula" divide pelas
matrículas da própria etapa na rede municipal (Censo Escolar do mesmo ano, `stg.matricula`; a soma das
etapas é a mesma base da coluna "Alunos" do TCE-ES). As demais subfunções seguem divididas pelo total:
são transversais ou não têm etapa no Censo. Como a rede municipal quase não tem ensino médio, esse
ranking por matrícula fica honestamente "sem dado". O endereço guarda o estado (`#v=fluxo&ano=2024&m=3205309`).

A comparação entre municípios tem **dois denominadores**, porque medem coisas
diferentes: **per capita** (÷ população do exercício, que o SICONFI só muda a cada dois
anos) e **por matrícula** (÷ matrículas da rede municipal no ano). Para comparar redes
de tamanhos diferentes, o por matrícula é o mais próximo do serviço prestado — e o
único dos dois cujo denominador muda todo ano. Ele está na comparação lado a lado, na
ficha do município, no seletor de indicador (ranking, evolução, mapa de barras) e na
série histórica de cada ente. O denominador é a coluna `Alunos` do recurso *Educação*
do TCE-ES, **conferida contra a soma do Censo Escolar** por município (ver
[conferências](#como-o-dado-foi-conferido-20212025-22092026)). O Estado fica sem esse
indicador: o recurso do Tribunal cobre só municípios.

Listas longas (conselhos escolares, itens, ações, fontes) começam com as primeiras
linhas e abrem inteiras num botão — Cariacica e Serra chegam a 120 conselhos escolares
num exercício, e o card não deve virar uma rolagem sem fim. O CSV sempre traz tudo.

## O painel novo (`novo_dashboard.html`)

Refeito a partir de uma auditoria de UX/UI do `dashboard.html` (30/09/2026), com fontes
próprios em [`web_novo/`](web_novo/) e montador próprio
([`build_novo_dashboard.py`](build_novo_dashboard.py)). O painel antigo, os fontes dele
em `web/` e o `build_dashboard.py` ficaram intocados; do montador antigo o novo reusa só o
embutimento seguro do dado e os PDFs do SIOPE conferidos por SHA-256. Mesmo dataset, mesma
proveniência, mesmo "ver fonte".

**Decisões tomadas com o usuário** (numeração da auditoria):

| | Decisão |
|---|---|
| D1 | Mantém a identidade do Painel de Controle, com o aviso de protótipo legível |
| D2 | Cor que não passa no contraste AA é escurecida, mesmo se afastando do painel do TCE-ES (tokens marcados `[AA]` em `web_novo/design-tokens.css`) |
| D3 | O cidadão também é público: glossário, frase em linguagem simples em cada card, detalhe técnico recolhível. O CNCA — Evidências foi para `novo_cnca_evidencias.html` |
| D4 | Faixa de KPIs só na Conformidade |
| D5 | Panorama mostra a despesa absoluta **e** por matrícula, lado a lado; valores nominais |
| D6 | SIOPE e TCE-ES com o mesmo peso; vermelho só para regra legal descumprida; toda linha colorida diz o motivo |
| D7 | CSV com `;` e vírgula decimal (Excel em português), nos dois arquivos |
| D8 | Arquivos únicos, autocontidos |
| D9 | Ficha do município + Receita → aplicação + Escolas viraram o **dossiê do município** |

| Visão | Responde |
|---|---|
| **Conformidade** (abre aqui) | Triagem dos 78: seis quadros-resumo e as tabelas de mínimos legais, relatórios ao Tesouro, remessas ao TCE-ES, obras paradas e conciliação — cada linha com situação e motivo |
| **Panorama do ES** | No que se gasta; comparação lado a lado (inclui "+ porte parecido", por matrículas); evolução e ranking em R$ e por matrícula (o ranking filtra por tipo de despesa e exporta Excel com o recorte ativo; Ensino Fundamental e Ensino Médio são divididos pelas matrículas da própria etapa, do Censo); execução no ano; cobertura |
| **Município** | O dossiê, em oito seções com endereço próprio: resumo, conformidade (série 2021–2025 dos mínimos, com a linha do mínimo), receita, despesa, quem recebeu (Nível 3), obras, escolas e programas |
| **Programas federais** | CNCA: repasses automáticos e registro manual contados à parte |
| **Como ler e metodologia** | Estados, tipos de ausência, glossário, fontes, conferências de qualidade e as limitações, cada uma com âncora — os cards apontam para a sua |

O que mudou além da estrutura:
* **Quatro estados com significado fixo**: ✖ descumpre (regra legal), ⚑ sinal a verificar
  (atraso, divergência, obra parada), ✔ cumpre, — sem dado.
* **Histórico de verdade**: trocar de visão, município, seção ou escola é um link, e o
  Voltar do navegador volta à tela anterior. O endereço guarda o estado inteiro.
* **Barra de contexto fixa** com "Você está vendo: …" e os filtros da visão.
* **Uma tabela só**: ordenável, com busca, primeira coluna fixa e "mostrar todas".
* Redimensionar a janela redesenha só os gráficos — não fecha o que estava aberto.
* Gráficos são uma imagem para o leitor de tela (com resumo) e não somam paradas de Tab.
* No papel de trabalho do CNCA: o mapa não perde mais a cor nas linhas pares, a coluna do
  achado fica em destaque ao vir da Matriz, e as notas repetidas viram notas numeradas.

**Versão pública, no site Farol Capixaba da Educação.**
`python -m financiamento.build_novo_dashboard --site` grava também
`docs/financiamento_educacao.html` (na raiz do repositório), linkado da página inicial do
Farol. Ela difere da versão dos auditores em duas coisas: não leva o papel de trabalho do
CNCA nem links para ele, e mascara CPF e telefone de pessoa física nos campos de nome e de
documento (o dado aberto do TCE-ES traz CPF digitado no nome do credor e no lugar do CNPJ
da contratada). A proveniência — consultas, SHA-256, valores — é a mesma. Para atualizar o
site: regerar com `--site` e commitar só `docs/`.

## Identidade visual: alinhada ao Painel de Controle do TCE-ES

O painel segue a identidade visual do [Painel de Controle do
TCE-ES](https://paineldecontrole.tcees.tc.br/), para ser lido como parte da área
temática de Educação e não como um anexo de fora.

**Nada foi estimado a olho.** A identidade foi extraída da página renderizada
com Playwright + Chromium (a página é uma SPA: buscar o HTML sem executar
JavaScript traz só a casca) e do CSS-fonte que o próprio painel serve. O que
saiu dali:

| O que | Onde foi parar |
|---|---|
| Open Sans, base de **14px** (`html { font-size:14px }`) | tipografia de toda a página |
| Azul-marinho `#112b54`, azul `#1b5f9d`, ardósia `#364b60` | marca, títulos, links, abas |
| `.widget` — borda `#f5f5f5`, raio **5px**, sombra `0 0 18px` | todos os cards |
| `#breadcrumb` — fundo `#f9f9f9`, itens separados por **borda vertical**, 14px/600, altura 42px | a trilha "Painel de Controle › Áreas temáticas › Educação › Financiamento" |
| `#alerta.danger/.warning/.success/.info` — barra de 5px à esquerda, raio 2px | **abaixo do mínimo usa exatamente o `.danger` do painel** (`#a94442` sobre `#f2dede`) |
| `.p-datatable.datagrid` — `th` 10px/700, `td` 6px, zebra `#f7f7f7c7` | todas as tabelas |
| `.etiqueta` — rótulo e valor em `#607d8b`, separados só pelo peso | os KPI cards |
| Barra amarela `#f8d96a` à esquerda do título, `font-size:2rem` | título da página |
| `.menu-topo-container` — 55px, fundo branco | a barra de identificação no topo |

Dois conjuntos foram extraídos e **documentados nos tokens sem serem aplicados**,
porque aplicá-los mudaria o significado da cor e não só a aparência — a escala de
notas ISP/IEGM (A `#2f9e23` → D `#e68364`), já que aqui conformidade é binária
(atende ou não ao mínimo legal, e graduar isso seria um juízo que os dados não
sustentam), e o par receita `#486d19` / despesa `#872424`, já que no Sankey daqui
a cor codifica a **origem** do recurso, não o lado do fluxo. Ficam registrados
com o motivo, para quem for integrar decidir.

Os tokens ficam em [`web/design-tokens.css`](web/design-tokens.css), **cada um
anotado com a fonte exata** de onde veio — `[tema]` (variável CSS do PrimeReact
saga-blue), `[css]` (regra do CSS-fonte do painel), `[dom]` (estilo computado
medido) ou `[nosso]` (não observado no painel; traz o motivo). O `estilo.css`
só consome tokens: não há hex, raio, sombra ou família de fonte solto nele.

A evidência completa — scripts de captura, screenshots, `extracao.json`, o
CSS-fonte baixado e o relatório — está em
[`docs/identidade_tcees/`](docs/identidade_tcees/relatorio.md), e é reprodutível:

```bash
pip install playwright && playwright install chromium
python docs/identidade_tcees/capturar.py            # extrai a identidade do painel
python docs/identidade_tcees/conferir_dashboard.py  # confere o resultado aplicado
```

O que **não** foi possível observar está registrado no relatório (§7), em vez de
inventado: nenhuma das rotas medidas renderizou gráfico com dados, então não há
paleta de séries de gráfico observada — a que está aqui é a que o painel já
tinha, validada em contraste, com a primeira série realinhada ao azul do TCE-ES.
O modo escuro também é nosso: o Painel de Controle só tem o tema claro.

### Isto é um protótipo fiel, não um *drop-in* no código do painel

**Incorporar este dashboard como rota/página real dentro do Painel de Controle é
uma tarefa de desenvolvimento separada, a cargo de quem mantém aquele sistema.**
O que está aqui é um **arquivo HTML autocontido** — CSS, JavaScript e dados
embutidos, sem chamada de API no navegador. Ele abre em qualquer máquina com um
duplo-clique, e é exatamente isso que o torna inadequado como fonte para colar
na SPA.

O painel é uma aplicação **React** (PrimeReact com o tema saga-blue, mais
Material-UI em parte dos componentes, empacotada com Vite) — **não Angular**,
como se costuma supor; isso foi verificado nas folhas de estilo que a página
carrega. Integrar de verdade implicaria, do lado de quem mantém o painel:

- **componentizar** as visões em componentes React próprios, no padrão de
  componentes e de estado que o sistema já usa;
- **rotear** a página dentro da árvore de rotas existente, com os mesmos
  parâmetros de URL das outras áreas temáticas (ano, ente, aba);
- **alimentar por backend** — aqui os dados vêm de um JSON de 17 MB embutido,
  gerado pelo pipeline; no painel viriam dos serviços dele, com filtro e
  paginação no servidor;
- **substituir os tokens da ponte** por aquilo que o design system do painel já
  expõe, em vez de manter uma cópia (veja o bloco *ponte* no fim de
  `design-tokens.css`, que existe justamente para tornar essa troca um só lugar);
- **rever os componentes que este dashboard tem e o painel não** — o Sankey
  receita→despesa (o painel já tem um equivalente em "Destino do dinheiro", que
  provavelmente é o que se deve reusar), o diálogo "ver fonte" e a régua do
  mínimo legal.

O papel deste repositório nessa conversa é ser o **pacote de handoff**: o HTML
navegável para validar conteúdo e comportamento com quem audita, os tokens de
design documentados com a procedência de cada valor, e o pipeline que produz os
números com a fonte de cada um. A decisão de o que virar componente, e quando, é
de quem mantém o painel.

## Fase 0 — o que o reconhecimento das fontes descobriu

Feito antes de programar o pipeline, delegado ao subagente `api-explorer` em três
frentes paralelas (SICONFI, MSC, fontes externas). Cada achado crítico foi depois
**conferido diretamente nos dados**: parte das conclusões dos relatórios estava
errada e foi corrigida (a coleta da MSC de Vitória tinha parado em 20 mil linhas
por HTTP 429; um "total da função 12" somava todas as contas da classe 6; a fonte
`25xx` foi lida como intra-orçamentária, quando o 1º dígito indica exercício anterior).

### O RREO Anexo 08 (MDE) no SICONFI: vem vazio

`/rreo?no_anexo=RREO-Anexo 08` devolve **zero itens** — nos dois tipos de RREO, para
capital, município médio e pequeno (Vitória, Cachoeiro, Afonso Cláudio, Colatina),
em todos os exercícios testados (2019, 2021, 2023, 2024, 2025). Consultando o RREO
**sem** filtro de anexo, a lista vai de 01 a 14 **pulando 05, 08 e 12** (Vitória 2024:
3.234 linhas; o RREO Simplificado de Afonso Cláudio traz só 01, 02, 03, 06, 07, 09,
11 e 14). O Anexo 08 é declarado ao SIOPE e não chega à API do SICONFI.
**Consequência: o SIOPE é a fonte primária do MDE e do FUNDEB-remuneração** (Fase 3).
O painel não estima MDE a partir da função 12 — ela inclui gastos que não contam como MDE.

### O que mais se descobriu

| Fonte / endpoint | Achado (conferido em 2026-09-22) | Como o pipeline trata |
|---|---|---|
| `/entes` | Ignora `an_exercicio`; o Estado vem com `uf="BR"` | Estado pelo código 32; população do exercício vem das linhas do DCA |
| `/anexos-relatorios` | Não responde em 120 s (três variantes) | Nome de anexo lido nos próprios dados |
| `/rreo` Anexo 01 | `cod_conta` semântico (`Impostos`, `TransferenciasCorrentes`…), coluna "Até o Bimestre (c)"; não detalha FPM/ICMS/FUNDEB | Categorias do Anexo 01 + FUNDEB da MSC + FNDE da CGU |
| `/msc_orcamentaria` | Seis parâmetros obrigatórios (sem `classe_conta` → 0 linhas); só códigos, sem descrição; `limit` aceita 5000; HTTP 429 sob rajada | Uma consulta por município-ano (dezembro, classe 6); ritmo global e espera em 429 |
| MSC — fonte de recursos | Padrão da STN nos municípios do ES **desde 2022** (77 de 78; em 2021, códigos locais de 8 dígitos) | Fluxo fonte → subfunção em 2022–2025; em 2021 o painel diz por que não há |
| `/extrato_entregas` | Data de homologação (UTC) por instituição × relatório × período; **sem prazo** | Prazo calculado pela LRF; data convertida a Brasília |
| SIOPE (HTML) | Todos os relatórios de `relatoriosMunicipais.jsp` exigem **reCAPTCHA** | Não contornado. Usa o PDF abaixo |
| SIOPE (PDF) | O próprio formulário aponta o FTP aberto do FNDE: `RREO_Municipal_<IBGE6>_<bim>_<ano>.pdf`, 78 municípios, 2010–2026 | 6º bimestre de cada exercício, lido com `pypdf` |
| FNDE dados abertos / SIGEF | `dadosabertos` → dados.gov.br com token (401); liberações do SIGEF com reCAPTCHA | Não usados |
| Portal da Transparência | API exige chave; **download em lote mensal sem token**; limita volume (HTTP 405 depois de ~30 ZIPs rápidos) | Um ZIP a cada 20 s; na primeira recusa, para e deixa o resto para a próxima execução |
| TCE-ES (CKAN) — empenhos | O layout muda: 2021–2023 trazem `Ano`/`Mes`; 2024+ `AnoReferencia`/`MesReferencia`. O arquivo de 2023 **não traz dezembro** para 25 municípios | Os dois layouts entram; o pipeline conta os meses e marca o ano como incompleto |
| TCE-ES (CKAN) — prestação de contas | Só a janela recente (08/2025 em diante); ~100 unidades gestoras nunca aparecem homologadas; 416 linhas repetem UG × mês (sem código de UG para distinguir) | Janela declarada no painel; UG sem nenhuma remessa homologada é contada à parte, não como atraso; na repetição fica a linha homologada |
| TCE-ES (CKAN) — download | Conexão cai no meio de ZIP grande (`IncompleteRead`) | Nova tentativa do download inteiro (a repetição da requisição não basta), com o SHA-256 conferido no fim |

A estrutura real de cada resposta (nomes de campo) está documentada no docstring
do módulo que a lê: `parsing.py` (DCA/RREO), `rreo_receita.py`, `msc.py`,
`entregas.py`, `siope.py`, `fnde.py`.

## De onde vem a receita (Fase 1)

Receita realizada no exercício (exceto intra-orçamentária) em **quatro origens que
não se sobrepõem** — a tabela "origem da receita" por município e ano
(`dados/processado/receita_origem.csv`):

| Origem | Fonte | Onde exatamente |
|---|---|---|
| Impostos próprios (IPTU, ISS, ITBI, IRRF) | SICONFI | RREO Anexo 01, 6º bimestre, `cod_conta = Impostos`, coluna "Até o Bimestre (c)" |
| FUNDEB (fundo + complementação da União) | SICONFI | MSC, conta 621200000 (receita realizada), natureza de receita com os prefixos das contas do FUNDEB **achadas pelo nome no DCA I-C** (2022+: `1751…` fundo, `1715…` complementação; 2021: `175801…`, `171809…`) |
| Transferências federais específicas (salário-educação, PNAE, PNATE, PDDE) | FNDE | CGU, ações `0369`, `00PI`, `0969`, `0515` pagas ao próprio município |
| Outras | calculado | receita total do Anexo 01 − as três acima (fica vazia se faltar qualquer parcela) |

O código do FUNDEB na MSC **não foi adivinhado**: a MSC só traz códigos, então o
pipeline acha as contas do FUNDEB pelo nome no DCA I-C do mesmo exercício e usa o
prefixo delas. Resultado: **FUNDEB da MSC = DCA I-C em 390 de 390 município-anos, ao
centavo.** O mesmo FUNDEB é conferido contra o SIOPE (principal, sem rendimentos):
350 de 390.

Os repasses do FNDE aparecem em **três olhares**: pago pela União (CGU),
registrado pelo município (MSC, fontes 550–553) e declarado ao FNDE (SIOPE). MSC e
SIOPE incluem os rendimentos de aplicação da conta do programa; a CGU, só o repasse.
O **PDDE vai quase todo direto às escolas** (unidades executoras) e não transita pelo
orçamento municipal: é mostrado à parte e fica fora da receita do município. O PDDE
das escolas estaduais vem sem município no arquivo da CGU (5.644 linhas, R$ 39,7 mi
em 2021–2025) e fica fora dos municípios.

## Onde cada valor é aplicado (Fase 2) — três níveis que não se confundem

### Nível 1 — função e subfunção

Reaproveitado do financiamento geral: **DCA Anexo I-E**, função 12, por subfunção
(12.361 Fundamental, 12.365 Infantil, 12.122 Administração Geral…). As subfunções
somam exatamente a função 12 (395 de 395 ente-anos). Somado a ele, o **fluxo fonte de
recursos → subfunção** da MSC: cada empenho da função 12 carrega a fonte que o paga,
então a ligação entre origem e destino é **declarada pelo município**, não estimada
por proporção. O diagrama agrupa as fontes em impostos (fonte 500), FUNDEB
(540–543), transferências federais específicas (550–553, 569) e outras; a tabela
abaixo dele tem cada fonte. A fonte 500 junta impostos próprios e transferências de
impostos (FPM, ICMS…): a contabilidade não os separa, e dividir seria estimar.

### Nível 2 — natureza econômica: o mapeamento de contas usado

Conferido nas respostas reais de Vitória e Afonso Cláudio (2024) antes de generalizar;
está em `etl/msc.py`. Consulta: `/msc_orcamentaria`, MSCC, **classe 6**, dezembro,
`ending_balance` — o acumulado do ano.

**Contas contábeis (PCASP, 9 dígitos na MSC):**

| Conta | Significado | Uso |
|---|---|---|
| `621200000` | 6.2.1.2 Receita realizada | receita por natureza e fonte (FUNDEB, FNDE) |
| `622130100`…`622130700` | 6.2.2.1.3.01–07 Crédito empenhado: a liquidar, em liquidação, liquidado a pagar, liquidado pago, e os inscritos em restos a pagar (05/06 não processados, 07 processados) | **empenhada = 01…07; liquidada = 03+04+07; paga = 04** |
| `6229…`, `63…` | controles paralelos e execução de restos a pagar de anos anteriores | fora |

Em dezembro a inscrição em restos a pagar já moveu o saldo de 01→05 e de 03→07; por
isso as sete contas. **Conferido ao centavo contra o DCA I-E**: função 12 de Afonso
Cláudio 2024 = 49.699.516,59 empenhada, 48.939.943,63 liquidada, 48.708.923,11 paga,
subfunção a subfunção; e em **388 de 390** município-anos (as duas exceções são
divergências reais entre as declarações do município: Anchieta 2022, Santa Maria de
Jetibá 2023). Intra-orçamentária (modalidade 91) fica fora, como no DCA I-E.

**Natureza da despesa → categoria** (natureza de 8 dígitos `CGMMEEDD`: categoria,
grupo, modalidade, elemento; Portaria Interministerial STN/SOF nº 163/2001):

| Categoria | Regra | Subcategorias |
|---|---|---|
| Pessoal e encargos | grupo 1 (`31……`) | inativos e pensionistas (elementos 01, 03, 05); pessoal ativo (demais) |
| Custeio | grupo 3 (`33……`) | modalidade 50 → transferências a entidades sem fins lucrativos (ex.: creches conveniadas); modalidades 71–76 → consórcios; elemento 30 material de consumo; 32 distribuição gratuita; 39 serviços PJ; 36 serviços PF; 37 locação de mão de obra; 40 TIC; 46/49 auxílio-alimentação e transporte; demais |
| Investimentos | grupo 4 (`44……`) | elemento 51 obras e instalações; 52 equipamentos e material permanente; demais |
| Outras | grupos 2, 5, 6 | juros, inversões financeiras, amortização |

Atenção a um equívoco comum: a "classe 3/4" que interessa aqui é a **categoria
econômica da natureza da despesa** (3 corrente, 4 capital). No PCASP, as classes 3 e
4 são variações patrimoniais (VPD/VPA) da matriz patrimonial — outra coisa, não usada.

### Nível 3 — item específico: credor, ação, conselho escolar, obra (TCE-ES)

Não há fonte **nacional** com a despesa por empenho; no ES, há a do Tribunal. Os dados
abertos do TCE-ES (`etl/tcees.py`) trazem o que cada município declara na prestação
de contas mensal (CidadES) — dado **declaratório**, como o do SICONFI e o do SIOPE; o
que lhe dá lastro é o cruzamento:

| No painel | De onde | Conferência |
|---|---|---|
| **Maiores credores** da função 12 (15 por município-ano; pessoa física agregada numa linha, nunca nominal) | *Empenhos dos municípios*, recorte da função 12, sem modalidade 91 | soma dos empenhos × DCA I-E — ver [conferências](#como-o-dado-foi-conferido-20212025-22092026) |
| **Ações** com o nome dado pelo município e **orçado × executado** (dotação inicial e atualizada × empenhado), com as ações de obra em destaque | *Empenhos* e *Despesas dos municípios* (agregado com a dotação) | — |
| **Fonte com detalhamento** (convênio, programa estadual, FUNPAES…) | *Empenhos* | — |
| **Repasses do município a conselhos escolares** (PMDDE e programas semelhantes), ligados à escola do Censo | *Empenhos*: credor identificado pelo nome (conselho de escola, caixa escolar, AEC…) | vínculo por nome, com nota |
| **Obras da Educação**: objeto, contratada, valor inicial e atual, situação, vigência, prédio (bem vinculador, com coordenada e link de mapa), medições (nº, valor medido, % do contrato, última), aditivos, links do contrato e do edital | *Contratações* (obras, bens vinculadores) e *Instrumentos com medições e alterações* (1,2 GB lido em fluxo; fica só o das obras da Educação) | credor da obra nos empenhos (elemento 51) marcado como "contratada de obra" |
| **Itens contratados**: descrição, unidade, quantidade, preço unitário, valor total e o que já foi medido, com a contratada e a contratação | *Contratações* e *Itens - \<ano\>* (65–390 MB por ano, lidos em fluxo; fica só o da Educação) | valor contratado × medido no próprio item |
| **Detalhamento** ao clicar num credor ou numa ação: credor × ação com elemento e fonte, e os itens daquele CNPJ | *Empenhos* (cruzamento credor × ação) e *Itens* | — |

**O item comprado — o que entra e o que não entra.** O recorte da Educação usa três
regras, todas afirmadas pela fonte: a unidade gestora da linha é de educação
(secretaria ou fundo); a contratação tem `SetorBeneficiado = Educação`; ou o instrumento
é uma obra da Educação. Uma quarta regra foi testada e **descartada**: casar o CNPJ da
contratada com os credores da função 12. Medida no arquivo de 2022, ela sozinha traria
47% de todos os itens do Estado — a empresa que vende à educação também vende ao resto
da prefeitura, e o CNPJ não prova que a compra é da educação.

O preço é a cobertura, e ela é desigual: 12.210 itens em 52 municípios em 2022, 42.708 em
67 em 2023, 38.477 em 70 em 2024 e 28.139 em 73 em 2025 — 77 dos 78 municípios em algum
ano. `SetorBeneficiado` vem vazio em 90% das contratações (só as obras o preenchem por
obrigação) e apenas 22 municípios têm unidade gestora própria de educação. Município
que compra pela unidade gestora da prefeitura sem marcar o setor **não aparece** — e
o painel diz isso no card, em vez de mostrar um zero. Os arquivos de *Itens* começam em
2022, e o exercício do item é o do **instrumento contratual**, não o do pagamento: um
contrato de 2024 pago em 2025 aparece em 2024, e o painel avisa quando o CNPJ que você
clicou tem contrato em outro exercício.

O **detalhamento** cruza o que as duas tabelas de Nível 3 mostravam separadas — quem
recebeu, de um lado; em que ação, de outro. Guarda os 8 maiores credores de cada ação e
soma os demais numa linha "(demais)": o total fica inteiro, o nome do credor pequeno é
que não aparece. O empenho do TCE-ES **não traz o número do contrato**, então a ponte
entre empenho e item é o CNPJ da contratada no mesmo município e exercício — o painel a
rotula como indício, não como identidade, numa seção à parte do diálogo.

**Completude da fonte.** O pipeline conta os meses presentes no arquivo de empenhos de
cada município-ano. Quando falta mês (caso do arquivo de 2023, ver abaixo), o painel
diz "ano incompleto na fonte" em vez de mostrar divergência, e a conferência com o DCA
deixa esse município-ano de fora, contado à parte.

**O que continua fora** (card "o que ainda não chega ao painel"): custo de **pessoal por
escola** (o vínculo do servidor no TCE-ES não traz lotação — e a folha é a maior parte
da despesa); **em que cada escola gastou o PDDE** (a unidade executora presta contas ao
FNDE); a **nota fiscal** (número, data e emitente não estão em dado aberto do TCE-ES);
o **item** dos municípios que compram pela unidade gestora da prefeitura sem marcar o
setor beneficiado; e a ligação certa **empenho ↔ contrato**, que só existiria se o
empenho trouxesse o número do contrato.

Isso está no portal da transparência de cada município, que só aparece no painel quando
alguém o conferiu e registrou em `dados_manuais.yaml → nivel3.portais_transparencia` —
endereço deduzido do nome seria pior que nenhum. **Vitória** é o primeiro cadastrado, e
publica uma API REST aberta e documentada
([help](https://wstransparencia.vitoria.es.gov.br/help/), conferida em 22/09/2026, sem
token): `api/despesa/fornecedor` (despesa por favorecido), `api/Licitacao/{id}/LoteItens`
(itens da licitação) e `api/pessoal/lotacao` — a lotação do servidor, justamente o que
falta para custear pessoal por escola. O pipeline **não a consulta**: é uma API por
município, sem padrão entre os 78, e este painel é de coleta em lote com proveniência
por número. Ela fica registrada (campo `api`) e aparece no card de limitações e no
detalhamento, como caminho para quem for buscar à mão.

## Visão por escola (Censo Escolar)

Três canais de dinheiro **nomeiam o recebedor** em dado aberto, e só eles chegam à escola:

1. **PDDE** (CGU): a unidade executora, por plano orçamentário — inclusive o CNCA (000C)
   e o PDDE-Alfabetização (0007); inclui as escolas estaduais, que no arquivo da CGU vêm
   sem município;
2. **repasse do município ao conselho escolar** (empenhos do TCE-ES);
3. **obra no prédio** (contratações do TCE-ES, bem vinculador).

Nenhum deles traz o código INEP. O vínculo com a escola do Censo (`etl/escolas.py`) é
feito pelo **nome**, no mesmo município e na rede que o nome indica: termos
distintivos (sem "conselho", "escola", "EMEF", "prof."…), grafia vizinha só para nomes
longos (KUBITSCHECK × KUBITSCHEK, mas não JOAQUIM × JOAQUINA), desempate pelo tipo
(EMEF × CMEI) e vantagem clara sobre o segundo candidato. Obra: pelo nome do prédio e,
se não bastar, pela distância do centroide até a escola (≤ 400 m) com nome parcial. O
que é ambíguo **fica sem vínculo** e aparece na lista "recebedores não identificados",
com o nome original e o motivo — nunca é atribuído por palpite. Cada vínculo, com nota
e método, está em `dados/processado/escolas_vinculos.csv`.

Taxa de vínculo na execução final: **1.915 de 2.301** unidades executoras do PDDE (83%),
**715 de 890** conselhos escolares credores do município (80%) e **20 de 69** prédios de
obra (29% — o bem vinculador raramente traz nome de escola). Numa amostra de 25 vínculos
conferida à mão, os 25 estavam certos. O dinheiro identificado por escola em 2021–2025
soma R$ 161,0 mi de PDDE, R$ 403,2 mi de repasse municipal e R$ 96,9 mi de contratos de
obra, em 1.947 escolas.

Ao lado do dinheiro, o que o Censo diz da escola: matrículas, docentes,
infraestrutura (internet, biblioteca, laboratório, quadra, água, esgoto, rampas), IDEB
(anos iniciais e finais) e PAEBES do 5º ano (carregado no banco só para 2025). São
contexto: o painel não estabelece relação causal entre repasse e resultado.

## SIOPE — MDE e FUNDEB na remuneração (Fase 3)

Módulo isolado (`etl/siope.py`). Lê o **RREO Anexo 8** que o SIOPE gera, no FTP do
FNDE, com os percentuais **já apurados pelo sistema**: aplicação em MDE sobre a
receita de impostos (mín. 25%, art. 212 da CF) e FUNDEB na remuneração dos
profissionais da educação básica (mín. 70%). Também traz a receita de impostos (e os
impostos próprios à parte), o FUNDEB recebido, as receitas adicionais do FNDE e a
despesa total com educação.

* **Fonte sem SLA, tratada como tal.** O layout mudou duas vezes (itens 1–54 em
  2021–2022, 1–45 em 2023, 1–40 em 2024–2025), então os itens são achados pelo
  **rótulo**, nunca pelo número. Cada percentual é **conferido contra os valores da
  própria linha**. Falha de download, PDF ilegível, rótulo ausente ou conferência que
  não fecha viram **aviso** do município-ano — nunca erro que derruba o pipeline.
  Hoje: 390 de 390 PDFs lidos; 2 avisos genuínos (Santa Teresa e Vila Valério, 2023).
* **EC 119/2022.** Em 2023, o "valor exigido" de quem tinha diferença de 2020–2021 a
  compensar inclui a compensação; o % continua sobre a receita do ano. O parser
  reconhece o item e o painel mostra os dois fatos. Em 2021, a nota lembra que o
  descumprimento de 2020–2021 não gera responsabilização se compensado até 2023
  (art. 119 do ADCT).
* **Marcado como extração de PDF** em todo lugar onde aparece (selo "⚠ extraído de
  PDF (SIOPE)"), com a data da coleta, a de geração do PDF e a de publicação no FTP.
* **Por que não BeautifulSoup.** O PROMPT previa raspar o HTML do SIOPE; todos os
  relatórios HTML exigem reCAPTCHA, e contorná-lo não é opção. A mesma informação é
  publicada pelo FNDE em PDF, em FTP aberto.
* **Os 390 PDFs vão dentro do `dashboard.html`.** O link do "ver fonte" apontava para
  `ftp://`, esquema que o **Chrome removeu na versão 95 e o Firefox na 90** — clicar
  não fazia nada. O FNDE não espelha esses arquivos em HTTP anônimo (porta 443 fechada
  em `ftp.fnde.gov.br`; `/siope/` responde 401), então não há URL que o leitor possa
  abrir. Sem o documento na própria página, o número do MDE ficaria sem a evidência
  que o sustenta: o PDF é embutido em base64, com o **SHA-256 conferido contra a
  proveniência** na montagem (`pdfs_embutidos`, em `build_dashboard.py`), e o diálogo
  traz o botão *abrir PDF*. A URL do FTP continua exibida, como texto, para quem for
  reproduzir a coleta por fora. Custo: a página passou de 23 MB para **45 MB**
  (17,5 MB de PDF viram 23 MB em base64; gzip antes do base64 economizaria só 9%,
  não compensou a complexidade).

## Indicadores de conformidade

| Indicador | Definição | Fonte |
|---|---|---|
| **MDE vs 25%** (art. 212 CF) | % apurado pelo SIOPE; abaixo de 25% em vermelho. Em 2023, também se o aplicado alcançou o exigido com a compensação da EC 119 | SIOPE |
| **MDE pelo TCE-ES** | % apurado pelo Tribunal ao lado do SIOPE, com a diferença em pontos percentuais; ⚑ quando uma apuração fica abaixo de 25% e a outra não. As duas podem divergir por critério (restos a pagar, cancelamentos, glosas) | TCE-ES, recurso "Educação" |
| **FUNDEB vs 70%** | % do FUNDEB na remuneração dos profissionais da educação básica (art. 212-A, XI, CF; Lei 14.113/2020) | SIOPE |
| **Entregas no prazo** | RREO (30 dias após o bimestre, LRF art. 52), RGF (30 dias após o quadrimestre ou semestre, art. 55 §2º e art. 63), DCA (30 de abril, art. 51 §1º, I); Prefeitura e Câmara. Atraso = data de homologação (UTC→Brasília) > prazo. Retificado não é contado como atraso: a data do extrato é a da retificação | SICONFI `/extrato_entregas` |
| **Remessas mensais ao TCE-ES** | Homologação × **data-limite que vem na fonte**, por unidade gestora e mês; "não homologada" = limite vencido sem homologação numa UG que homologa outros meses. UG sem nenhuma remessa homologada na janela inteira é mostrada à parte (padrão de conta consolidada em outra UG), não como atraso | TCE-ES, "Prestação de Contas Municipal" (só a janela recente) |
| **Obras da Educação paradas** | Situação declarada ao TCE-ES; "paralisada/interrompida" (declarado) separado de "paralisação presumida" (classificação do Tribunal para obra sem medição recente) e de "não iniciada". Retrato atual, não do exercício | TCE-ES, contratações |
| **Conciliação função 12 × SIOPE** | (função 12 empenhada no DCA I-E − "total geral das despesas com educação" do Anexo 8) ÷ função 12. Acima de 5% leva ⚑. **Divergência é sinal a investigar, não erro do pipeline**, e é exibida como métrica. A despesa "para fins de limite" do MDE vai ao lado só como contexto (soma a contribuição ao FUNDEB e desconta deduções) | DCA I-E × SIOPE |

## O que os dados mostram hoje (2021–2025) — pontos a verificar

Fatos apurados pelo pipeline em 22/09/2026, que **não são, por si, conclusão de
irregularidade**:

* **MDE abaixo de 25%:** 10 municípios em 2021 (Guarapari 18,81%, São Mateus 19,32%,
  Conceição da Barra 21,72%, Linhares 22,29%, Rio Bananal, Ibatiba, Alegre, Bom Jesus
  do Norte, Castelo, Água Doce do Norte) — ano coberto pela EC 119/2022; e **2 em 2024:
  Guaçuí (22,42%) e Linhares (24,98%)**. Nenhum em 2022, 2023 e 2025.
* **EC 119, compensação em 2023:** 7 municípios tinham diferença a compensar;
  **Guarapari** (aplicou R$ 71,2 mi contra R$ 83,0 mi exigidos) e **Ibatiba** (R$ 15,9 mi
  contra R$ 19,6 mi) ficaram abaixo do exigido com a compensação, embora com % do ano
  acima de 25%.
* **FUNDEB abaixo de 70% na remuneração:** 6 municípios em 2021 (Apiacá 66,00%,
  Castelo, Conceição da Barra, Jerônimo Monteiro, Afonso Cláudio 69,48%, Aracruz);
  nenhum de 2022 a 2025.
* **Entregas:** de 67 a 75 municípios por ano com ao menos um relatório homologado
  depois do prazo; de 40 a 51 com atraso acima de 30 dias; nenhum sem entrega. Quase
  todo município atrasa algum RREO por poucos dias — o painel ordena por gravidade.
* **Conciliação:** de 19 a 26 municípios por ano com divergência acima de 5% entre a
  função 12 e o SIOPE; a maior foi Itapemirim em 2021 (SIOPE 87% acima da função 12).
* **MDE pelo TCE-ES:** a apuração do Tribunal fica abaixo de 25% em 12 municípios em 2021,
  nenhum em 2022, 3 em 2023 (Ibiraçu 24,83%, Laranja da Terra 24,04%, Mimoso do Sul 22,83%),
  5 em 2024 (Guaçuí 22,42%, Montanha, Muniz Freire, Pedro Canário, São Gabriel da Palha) e
  3 em 2025. Em **12 município-anos as duas apurações discordam sobre o mínimo** — uma
  abaixo de 25%, a outra acima (ex.: Pedro Canário 2024, TCE-ES 24,15% × SIOPE 25,00%;
  Vila Velha 2021, 24,61% × 29,36%). É divergência de critério a esclarecer, não conclusão.
* **Obras da Educação (retrato atual):** 765 contratos municipais, R$ 2,00 bi; **12
  paralisadas ou interrompidas declaradas** e **337 em "paralisação presumida"** pelo
  Tribunal (sem medição recente) — juntas, R$ 927,8 mi em 60 municípios; 240 não iniciadas.
* **Orçado × executado nas ações de obra:** R$ 3,33 bi de dotação atualizada em 2021–2025
  contra R$ 2,02 bi empenhados (61%).
* **O que foi comprado (itens, 2022–2025):** 121.534 itens da Educação, em 2.797 contratações
  de 2.306 empresas, **R$ 4,86 bi contratados** e R$ 1,11 bi medidos, em 77 municípios — com
  preço unitário, que é onde a comparação entre municípios fica possível. Os dois maiores
  itens do Estado não são de ensino: cartão-alimentação dos servidores contratado pela
  unidade gestora da educação (Serra, 2025, 360 mil unidades a R$ 927,90 = R$ 334,0 mi;
  2024, R$ 84,5 mi). Alimentação escolar aparece em 942 itens, R$ 928,9 mi — em Cariacica
  (2025), 4 milhões de refeições a **R$ 7,56 cada**, R$ 30,2 mi. Só 24.060 dos 121.534 itens
  têm medição registrada: contratado não é entregue.
* **Repasse do município à escola:** 39 municípios repassaram a conselhos escolares em 2025
  (R$ 92,0 mi); em 2021 eram 26 (R$ 90,4 mi). 889 conselhos distintos aparecem como credores.
* **Prestação de contas mensal ao TCE-ES** (janela de 08/2025 a 08/2026): 87 remessas
  homologadas com atraso e 32 vencidas sem homologação, em 49 municípios; 55 unidades
  gestoras de 11 municípios não têm nenhuma remessa homologada na janela (padrão de conta
  consolidada em outra UG — a confirmar com o Tribunal). A fonte repete UG × mês em 416
  linhas; vale a homologada, senão o painel afirmaria atraso que a própria fonte desmente.
* **A revisar na fonte:** Conceição da Barra declara receita patrimonial de −R$ 1,24 mi
  no RREO Anexo 01 de 2021 (o único valor negativo onde o indicador não o admite). E o
  arquivo de empenhos de 2023 publicado pelo TCE-ES não traz dezembro para 25 municípios.

## Proveniência: como cada número vira evidência

* **No painel:** "ver fonte" em cada card, em cada KPI e em cada linha das tabelas de
  conformidade. Mostra o indicador, onde ele está na fonte (anexo e linha, ou item do
  demonstrativo **daquele exercício**), o cálculo, e cada consulta: link que refaz a
  requisição, parâmetros, instante da coleta, arquivo em `dados/bruto/` e SHA-256
  (PDF e ZIP). O botão "Copiar referência" leva tudo isso em texto para o papel de trabalho.
* **No dataset consolidado** (`dados/processado/consolidado.csv`, UTF-8): uma linha
  por número, com `cod_ibge, ente, ano, periodo, indicador, rotulo, detalhe, valor,
  unidade, fonte, consultas, localizacao, calculo, observacao, fonte_consulta,
  endpoint, parametros, obtido_em, arquivo_cache`. As consultas em si, com descrição e
  hash, estão em `consultas.csv`.
* **Versões:** cada execução grava em `dados/processado/historico/<AAAAMMDDTHHMMSSZ>/`
  o consolidado e um manifesto (fontes, contagens, SHA-256). `python -m
  financiamento.etl.comparar` casa duas versões registro a registro e diz o que é novo,
  o que sumiu, o que mudou de valor e o que foi só reextraído.
* **Cache bruto** (`dados/bruto/`, 208 MB, ~8.194 arquivos): SICONFI em
  `<ano>/<endpoint>/<parâmetros>.json.gz` (resposta original + requisição + instante);
  SIOPE em `siope/<ano>/*.pdf` + `.json` (URL, instante, tamanho, SHA-256, data no FTP);
  FNDE em `fnde/<ano>/transferencias_<AAAAMM>_ES.csv.gz` (recorte do ES) + `.json`
  (URL, SHA-256 e tamanho do ZIP original da CGU); TCE-ES em `tcees/` — arquivos pequenos
  inteiros e, dos grandes (empenhos, despesas, medições, contratações e itens), o
  **recorte da Educação** com o
  SHA-256 e o tamanho do arquivo original no `.json` ao lado, mais as linhas lidas ×
  mantidas; Censo em `censo/*.csv.gz` + o instante e as consultas SQL. Resposta vazia
  também é cacheada: "não publicou" é um fato, diferente de "a consulta falhou".

## Como o dado foi conferido (2021–2025, 22/09/2026)

| Conferência | Resultado |
|---|---|
| Cobertura: DCA, MSC, SIOPE, RREO 6º bim. | 78 de 78 municípios nos cinco exercícios; CGU 60 de 60 meses |
| Soma das funções do DCA I-E = total do anexo | 395 de 395 ente-anos (tolerância R$ 1,00) |
| Soma das subfunções = despesa da função 12 | 395 de 395 |
| Função 12: MSC (6.2.2.1.3.01–07) × DCA I-E | 388 de 390 ao centavo |
| FUNDEB: MSC × DCA I-C | 390 de 390 ao centavo |
| FUNDEB: SIOPE (principal) × DCA I-C | 350 de 390 |
| Função 12 × total do SIOPE | 129 de 390 iguais; o resto é a conciliação exibida |
| RREO 6º bim. × DCA (empenhada em Educação) | 390 de 395 dentro de 0,5% |
| % do SIOPE × recalculado a partir da linha | 388 de 390 (2 avisos) |
| MDE: TCE-ES × SIOPE (0,5 p.p.) | 289 de 390 — as duas apurações divergem em 101; em 12 município-anos uma fica abaixo de 25% e a outra não |
| Função 12: soma dos empenhos do TCE-ES × DCA I-E | 354 de 365 município-anos ao centavo; 25 ficam de fora porque o arquivo do TCE-ES não traz dezembro/2023 |
| Matrículas: "Alunos" do TCE-ES × soma do Censo Escolar por município | 78 de 78 municípios, ao aluno (Censo de 2025) — é o que sustenta usar o número do Tribunal como denominador do R$ por matrícula |
| Vínculo recebedor → escola do Censo | 1.915/2.301 (PDDE), 715/890 (conselhos), 20/69 (prédios de obra); 25 de 25 conferidos à mão |
| ICA (INEP): SHA-256 da planilha × esperado (2026-09-23) | confere (`709c7eeba34d…`); 78 de 78 municípios do ES com valor em 2023, 2024 e 2025 e meta em 2024–2030; 858 registros do INEP no consolidado, todos com consulta de origem |
| Consolidado | IBGE com 7 dígitos em todos os municípios; nenhum registro sem consulta de origem; 1 negativo inesperado (dado da fonte) |

## Limitações — leia antes de citar um número

1. **O SIOPE entra por PDF.** Fonte sem SLA; um novo layout pode esconder um campo (vira
   aviso e "sem dado", nunca número errado em silêncio — a conferência interna existe
   para isso).
2. **Fluxo por fonte só de 2022 em diante** (códigos locais em 2021). A fonte 500 não
   separa impostos próprios de transferências de impostos.
3. **Repasses da CGU são o lado federal, por mês de pagamento**; MSC e SIOPE incluem
   rendimentos. A CGU limita downloads: mês não baixado entra na execução seguinte.
4. **Entregas:** a data do extrato é a do status atual; retificação esconde a data da
   entrega original (por isso não se afirma atraso de relatório retificado). Prazo
   que cai em fim de semana não é prorrogado (a LRF não prevê).
5. **Despesa empenhada, exceto intra-orçamentária**, valores nominais, sem deflator.
6. **População** é a do SICONFI (só muda a cada dois exercícios), não a do IBGE.
7. **O Estado** aparece à parte no financiamento geral; as fontes de auditoria cobrem só municípios.
8. **Nível 3 e escolas vêm de dado declaratório e de vínculo por nome.** O TCE-ES publica o que
   o município remete; o arquivo de empenhos pode vir incompleto (2023, ver acima) — o painel
   conta os meses e diz quando falta. A escola é achada pelo nome (nenhuma fonte financeira traz
   o código INEP); o ambíguo fica sem vínculo. Pessoal por escola e o gasto do PDDE pela escola
   não existem em dado aberto. Dos 78 portais municipais, só o de Vitória está cadastrado.
9. **Defasagem:** a DCA sai no ano seguinte; o painel detecta sozinho o último exercício publicado.
10. **Janelas do TCE-ES:** as remessas mensais só cobrem os meses recentes (o arquivo não tem os
    exercícios anteriores); obras e medições são o retrato da data da coleta.
11. **Itens contratados têm cobertura parcial e desigual** (ver Nível 3): só entra a linha que a
    própria fonte liga à Educação, os arquivos começam em 2022, e município que compra pela
    unidade gestora da prefeitura sem marcar o setor beneficiado não aparece. Ausência de item
    **não é ausência de compra**. O cruzamento credor ↔ item é por CNPJ e município, porque o
    empenho não traz o número do contrato: é indício, não identidade.
12. **Por matrícula** usa as matrículas da rede **municipal** (coluna `Alunos` do TCE-ES). Não é
    comparável ao per capita nem aplicável ao Estado, e não cobre alunos da rede estadual que
    moram no município.

## Estrutura

```
financiamento/
├── dashboard.html              painel final (GERADO; não editar à mão)
├── web/                        fontes da página — edite AQUI e gere de novo
│   ├── index.html              esqueleto, barra/breadcrumb do painel, navegação, KPIs, rodapé
│   ├── design-tokens.css       tokens da identidade do TCE-ES, cada um com a fonte de onde veio
│   ├── estilo.css              layout; consome os tokens, sem valor visual solto
│   ├── comum.js                dataset, estado, formatação, tabelas, Chart.js
│   ├── fonte.js                o "ver fonte" (diálogo de proveniência)
│   ├── sankey.js               Sankey, régua do mínimo legal, barra 100% (SVG próprio)
│   ├── nivel3.js               TCE-ES: Nível 3 (credores, ações, fontes, conselhos, itens, obras), o diálogo de
│   │                           detalhamento credor × ação × item, remessas e obras paradas
│   ├── visao_conformidade.js   visão Conformidade + faixa de KPIs
│   ├── visao_fluxo.js          visão Receita → aplicação (Níveis 1, 2 e 3)
│   ├── visao_panorama.js       visão Panorama
│   ├── visao_municipio.js      visão Ficha do município
│   ├── visao_escolas.js        visão Escolas + os cards automáticos do CNCA
│   ├── visao_programas.js      visão Programas
│   └── visao_cnca.js           visão CNCA — Evidências: matriz, mapa, ficha, perguntas, cobertura, exportação
├── build_dashboard.py          junta web/ + os dois datasets + os PDFs do SIOPE num HTML autocontido
├── etl/                        pipeline, uma fonte por módulo (ver etl/README.md): siconfi, siope, fnde,
│                               tcees, escolas (Censo), ica (INEP), cnca, composicao, indicadores…
│                               e a matriz do CNCA: matriz (carrega o YAML), execucao (agregados),
│                               censo_alfabetizacao, contratos, diarios, estado, evidencias
├── config/matriz_cnca.yaml     a matriz de evidências da fiscalização do CNCA: 6 questões, 23 achados,
│                               49 perguntas, 25 indicadores, 10 limiares e 3 constatações
├── dados_manuais.yaml          registros manuais (MDE de reserva, adesão e articuladores do CNCA, portais municipais)
├── programas.yaml              config declarativa dos programas (campos, indicador de meta, checklist de governança)
├── docs/identidade_tcees/      evidência da identidade visual: scripts de captura, screenshots,
│                               extracao.json, o CSS-fonte do painel, relatorio.md e conferir_cnca.py
├── docs/fiscalizacao-cnca/     os insumos da fiscalização: matriz de planejamento e questionário
├── docs/                       PROMPT.md (escopo), mapeamento_dados_tcees.md (levantamento do TCE-ES)
│                               e fase0…fase4 (o que cada fase mediu, e o que não conseguiu)
├── dados/bruto/                resposta original de cada consulta (cache versionado); inep/ica/ tem a planilha + .json com o hash
├── dados/processado/           CSVs, dataset.json, dataset_cnca.json, consolidado.csv, historico/
├── dados/evidencias/           a tabela longa do papel de trabalho do CNCA (CSV e parquet) e as de cobertura
└── tests/                      360 testes; fixtures são respostas reais das fontes
```

O Sankey e a régua são SVG próprio, e não um plugin do Chart.js, para funcionarem sem
internet, usarem as cores do tema e serem navegáveis por teclado; cada gráfico tem a
tabela gêmea logo abaixo.

## Módulo CNCA e outros programas

O **CNCA — Compromisso Nacional Criança Alfabetizada** tem plano orçamentário próprio
nas transferências federais, e é por ele que o painel o acompanha **automaticamente**
(`etl/cnca.py`, sem coleta nova: separa o que o FNDE e o TCE-ES já trazem):

| O quê | Onde | No painel |
|---|---|---|
| **PDDE-CNCA** às escolas | CGU, ação 0515, **PO 000C** "PDDE - Compromisso Nacional Criança Alfabetizada", pago a cada unidade executora | por município-ano (campo "repasse", origem `api`) e por escola, ligado ao Censo |
| PDDE-Alfabetização (antecessor) | CGU, ação 0515, **PO 0007** (2021–2022) | à parte, na mesma tabela |
| **Apoio ao Estado** (SEDU, que coordena o CNCA no ES) | CGU, ação 0509, **PO 0014** | por mês |
| Em que o município gastou | empenhos do TCE-ES com "FUNPAES" no programa, na ação ou no detalhamento da fonte (no ES, o CNCA é implementado dentro do PAES; o FUNPAES — Lei 10.787/2017 — é o seu braço financeiro para os municípios) | por natureza de despesa, ação e credor |

No ES, em 2021–2025 (valores da CGU, por mês de pagamento):

| Exercício | PDDE às escolas | Unidades executoras | Ao Estado (0509/0014) |
|---|---|---|---|
| 2021 | R$ 5,09 mi (PO 0007, "PDDE - Alfabetização") | 788 | — |
| 2022 | R$ 6,74 mi (PO 0007) | 1.322 | — |
| 2023 | R$ 4,11 mi (PO 000C, CNCA) | 867 | — |
| 2024 | R$ 0,31 mi (PO 000C) | 172 | R$ 0,62 mi |
| 2025 | R$ 0,32 mi (PO 000C) | 230 | R$ 6,47 mi |

O repasse **às escolas** caiu de 2023 para 2024–2025, enquanto o repasse **ao Estado**
subiu: é o que os arquivos da CGU mostram; o painel exibe os dois lados e não infere a
causa. Do lado municipal, R$ 54,5 mi foram empenhados em 2022–2025 com o nome FUNPAES
(10 municípios em 2024, o maior número), sendo R$ 41,1 mi em obras e instalações e
R$ 10,3 mi em equipamento e material permanente.

| Campo | Situação | Por quê |
|---|---|---|
| Adesão municipal | **manual**, 78 marcadores “não consultado” | Painel de Monitoramento do CNCA (MEC) atrás de CAPTCHA; ou ofício à SEDU |
| Repasse (PDDE-CNCA) | **automático** | CGU, plano orçamentário 000C |
| **ICA** — Indicador Criança Alfabetizada | **automático** (desde 2026-09-23) | planilha oficial do INEP, edição 2025, verificada por SHA-256 (`etl/ica.py`); substitui o campo manual "Saeb 2º ano" |
| Articuladores com bolsa (Renalfa) | **manual**, 78 marcadores “não consultado” | sem base aberta por município; ofício à SEDU-ES ou questionário |

* **Onde o CNCA é gasto, o limite:** o PDDE-CNCA é gasto pela **escola** e prestado ao
  FNDE, fora da contabilidade municipal — não há dado aberto por item. Do lado
  municipal, só aparece o que o município **nomeou** como FUNPAES; ausência ali não
  prova que o recurso não foi usado.
* “Sem dado publicado” ≠ “sem dado carregado”: o primeiro é a planilha do INEP lida sem
  o valor daquele município-ano (na edição 2025 não acontece no ES); o segundo é ninguém
  ter registrado um campo manual. Nenhum dos dois vira zero. O limiar de **743 pontos**,
  que o escopo do projeto informava sem conferência, está confirmado na aba "Variáveis" da
  própria planilha do INEP ("percentual de alunos acima de 743 pontos na escala Saeb") e no
  relatório do TCE-PB (Pesquisa Alfabetiza Brasil, Inep/MEC 2023).
* **Adicionar um programa** (Novo Mais Educação, Time de Leitores…): bloco novo em
  `programas.yaml`, registros em `dados_manuais.yaml`, e
  `python -m financiamento.etl.pipeline && python -m financiamento.build_dashboard` —
  nenhuma linha de código de exibição muda. Um bloco automático como o do CNCA
  (`modulo_automatico`) pede código no ETL e um card no painel.
* **O questionário aos municípios**, sugerido nas versões anteriores, virou instrumento: a aba
  **CNCA — Auditoria**, descrita a seguir, é o papel de trabalho que o recebe.

### CNCA — Evidências da fiscalização

A aba **CNCA — Evidências** (`web/visao_cnca.js`) é o papel de trabalho da fiscalização de
acompanhamento do TCE-ES sobre o **financiamento do Compromisso Nacional Criança Alfabetizada**
nos 78 municípios do ES. Ela responde às 6 questões da matriz de planejamento e às 49 perguntas
do questionário **com dado público, antes e independentemente das respostas dos municípios** —
que é o que permite confrontá-las quando chegarem.

Substituiu a aba anterior ("CNCA — Auditoria"), que era um checklist preenchido a mão e guardado
no navegador. A diferença não é de aparência: aqui **cada célula sai do ETL e leva ao registro
bruto** que a originou.

Os insumos da fiscalização estão em [`docs/fiscalizacao-cnca/`](docs/fiscalizacao-cnca/), e o
mapeamento inteiro — 6 questões, **23 achados**, 49 perguntas, 25 indicadores e 10 limiares — é
**configuração**, não código: [`config/matriz_cnca.yaml`](config/matriz_cnca.yaml). A equipe muda
um limiar ali e o painel inteiro muda, sem tocar em Python.

#### O achado que organiza o resto

**O CNCA não é identificável na classificação orçamentária de nenhum dos 78 municípios.**
Conferido em três medições independentes:

* a **Tabela de Fontes e Complementos do TCE-ES de 2025** (147 fontes, 54 complementos) não tem
  nenhuma entrada de CNCA, PAR ou alfabetização;
* nos **2.622.030 empenhos** da função 12 de 2021–2025 há **uma** combinação programa/ação com
  "alfabetiz" — em Vila Velha, e é EJA;
* a **fonte 551 (PDDE)** soma R$ 1,31 mi empenhado nos cinco anos, contra R$ 193,7 mi que a CGU
  mostra pagos às escolas do ES: o PDDE não passa pelo orçamento municipal.

Em 2023–2025, período do CNCA, **nenhuma ação orçamentária do ES nomeia alfabetização**, enquanto
70 dos 78 municípios têm dotação na fonte 569. O dinheiro federal está no orçamento e não é
identificável como CNCA em ponto nenhum dele.

Por isso nenhum indicador do painel se chama "execução do CNCA": eles medem **fonte**,
**subfunção** ou **ação**, e a nota de cada linha repete isso.

#### Constatação, indício, e a diferença entre os dois

Quando uma característica atinge os 78 por igual, apontá-la 78 vezes transformaria um fato sobre
a classificação orçamentária brasileira em 78 indícios individuais — e o município que aparecesse
no mapa de calor não teria feito nada diferente dos outros. Essas afirmações viram
**constatação**: ditas uma vez, com a medida que as sustenta, fora do mapa. São três (C3.1, C4.3,
C4.5), e o carregador **recusa** um achado que tenha constatação e ainda declare `indicio_risco`
na regra.

O que sobra por município é **indício**, nunca achado. O vocabulário é fechado — indício de
risco, sem indício, inconclusivo, sem dado público — e `matriz.py` falha alto se algo fora dele
aparecer.

#### As seis visões

| Visão | O que responde |
|---|---|
| **Matriz** | As 6 questões e seus 23 achados, com tipo de evidência, distribuição dos 78 por status e contagem de indícios. Abre com as constatações |
| **Mapa de evidências** | 78 × 23, cor **e símbolo** por status; clicar abre a ficha do município |
| **Ficha do município** | Todas as evidências do ente, com valor, status, a ressalva do indicador e "ver fonte". Abaixo: os quatro índices de P24, a cobertura do PDDE de P21, os repasses estaduais de P18, as contratações de P47/P48 e as buscas pendentes no diário |
| **Perguntas (P1–P49)** | O que o dado público responde de cada pergunta, com 🔒 nas que coletam dado pessoal |
| **Cobertura** | Quanto da matriz o dado alcança, os limiares com a distribuição que os justifica, e as limitações estruturais |
| **Exportar** | CSV do papel de trabalho, com proveniência por linha |

#### O que os dados dizem

| Achado | Resultado medido |
|---|---|
| **A4.1** baixa execução | Na fonte 569 (proxy do PAR): mediana de 91,6% (2023), 77,4% (2024) e 80,0% (2025); 28 a 33 municípios por ano abaixo de 70% |
| **A4.2** dessincronia | Mediana de **56 dias** entre o repasse do FNDE e o primeiro empenho na fonte; 48 município-anos acima de 90 dias. Só 2024–2025: a data de emissão não existe no leiaute anterior |
| **A4.3** despesa incompatível | 24 municípios com R$ 22,93 mi em elementos atípicos nas fontes 551/569 — **indício para revisão humana**, nunca achado: o empenho do TCE-ES não tem histórico nem número de contrato |
| **A4.4** concentração no fim do ciclo | 25 município-anos, **18 municípios distintos, 4 reincidentes**. O limiar é a **mediana do próprio exercício + 10 p.p.**, com piso de 20% |
| **A2.1** necessidade | Valor de referência do Cantinho da Leitura: **R$ 13,12 mi** para a rede municipal do ES em 2025 (10.627 salas × R$ 1.235), contra R$ 0,32 mi de PDDE-CNCA pago no mesmo ano |
| **A2.2** o que a rede tem | 93.186 matrículas e 4.302 turmas de 1º–2º ano em 2025; **metade** das escolas com anos iniciais não declara biblioteca nem sala de leitura |
| **A5.4** recurso × resultado | PDDE-CNCA por aluno de 1º–2º ano: mediana de R$ 46,19 (2023), R$ 7,55 (2024) e R$ 6,21 (2025). O ICA da rede municipal subiu de 74% para 83% no período. **Correlação descritiva, sem leitura causal** |
| **P18** recursos estaduais | O Estado empenhou R$ 430,0 mi (2023), R$ 377,2 mi (2024) e R$ 719,7 mi (2025) em transferências da educação aos municípios; o **FUNPAES** passou de 21% para 58% disso, enquanto o PDDE-CNCA às escolas caía de R$ 4,11 mi para R$ 0,32 mi |
| **P47/P48** consultorias | **Nenhuma** contratação da Educação no ES tem por objeto formação continuada em alfabetização. Há R$ 15,08 mi em assessoria pedagógica, em 8 municípios |
| **P33** | A despesa do 1º e 2º ano **não é separável** na remessa ao TCE-ES, nos 78. A subfunção 361 é o menor grão que chega ao Tribunal |

#### Cobertura: o número para a metodologia do relatório

Das **49 perguntas**: 7 o dado responde direto, 11 por proxy, 4 em parte e **27 só o questionário,
ofício ou análise documental respondem**. Dos **23 achados**: 15 calculados e 8 com "sem dado
público" como **resposta final** — eles não melhoram em fase nenhuma sem ofício.

Vale ler "calculado" com cuidado: seis dos 15 são documentais e dependem de diário oficial, que
cobre 3 dos 78 municípios. O cálculo existe; o dado, não. O painel mostra as duas coisas separadas.

#### Como reexecutar

```powershell
python -m financiamento.etl.execucao            --anos 2021-2025   # agregados de execução (cache; sem rede)
python -m financiamento.etl.censo_alfabetizacao                    # Censo: 1º e 2º ano, salas, leitura
python -m financiamento.etl.contratos                              # contratações de formação e material
python -m financiamento.etl.diarios             --atualizar tudo   # Querido Diário + índice do DOM-ES
python -m financiamento.etl.estado              --anos 2023-2025   # SIGEFES: repasses do Estado
python -m financiamento.etl.evidencias          --anos 2021-2025   # tabela de evidências + dataset do painel
python -m financiamento.build_dashboard
python docs/identidade_tcees/conferir_cnca.py                      # confere as 6 visões num Chromium
```

Saídas em `dados/evidencias/`: `evidencias_cnca.csv` e `.parquet` (7.332 linhas),
`constatacoes.csv`, `cobertura_achados.csv`, `cobertura_perguntas.csv`, `indices_execucao.csv`,
`restos_a_pagar.csv` e `cobertura_pdde.csv`.

#### O que não dá para saber por dado público

| Lacuna | Por quê | Caminho |
|---|---|---|
| Bolsas da Renalfa por município | Pagas a pessoa física pelo SGB/FNDE; a ação federal 00O0 não aparece por município na CGU | Ofício ao FNDE/SGB ou à SEDU-ES |
| Conciliação bancária e rendimentos (A4.5) | CONCIBAN e BALANCORR não estão em dado aberto | Extração interna do CidadES |
| Previsão do CNCA no PPA/LOA com precisão | Sem complemento de fonte do CNCA; hoje é proxy | Extração interna do CidadES (PPA, LOA, LOAPROG, PRATIVOE) |
| Execução do PDDE-CNCA pela escola | A unidade executora presta contas ao FNDE | Ofício ao FNDE |
| Adesão formal e Selo da Alfabetização | SIMEC sem consulta pública; gov.br responde CAPTCHA | Ofício ao MEC/SIMEC |
| Atos de designação em 75 municípios | O Querido Diário cobre 3 dos 78; o DOM-ES não expõe busca textual | Lista de buscas manuais gerada em `cnca_diarios_buscas_manuais.csv` |

O detalhe de cada fase está em [`docs/fase0_reconhecimento.md`](docs/fase0_reconhecimento.md),
[`fase1_execucao_financeira.md`](docs/fase1_execucao_financeira.md),
[`fase2_necessidades_resultados.md`](docs/fase2_necessidades_resultados.md),
[`fase3_documental_contratos.md`](docs/fase3_documental_contratos.md) e
[`fase4_painel.md`](docs/fase4_painel.md).
## Fontes

* [SICONFI — API de Dados Abertos do Tesouro Nacional](https://apidatalake.tesouro.gov.br/docs/siconfi/) — `/entes`, `/dca`, `/rreo`, `/msc_orcamentaria`, `/extrato_entregas`
* [SIOPE — relatórios municipais (FNDE)](https://www.fnde.gov.br/siope/relatoriosMunicipais.jsp) e o FTP `ftp://ftp.fnde.gov.br/web/siope/RREO/`
* [Portal da Transparência (CGU) — download de dados de transferências](https://portaldatransparencia.gov.br/download-de-dados/transferencias)
* [Dados abertos do TCE-ES (dados.es.gov.br)](https://dados.es.gov.br/organization/tcees-tribunal-de-contas-do-estado-do-espirito-santo) — API CKAN `package_show`; mapeamento em [`docs/mapeamento_dados_tcees.md`](docs/mapeamento_dados_tcees.md)
* [Censo Escolar (INEP)](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar) — via o PostgreSQL local do NEDUC (`educacao_dw`)
* [PAES e FUNPAES (SEDU/ES)](https://paes.sedu.es.gov.br/funpaes)
* [Painel de Monitoramento do CNCA (MEC)](https://www.gov.br/mec/pt-br/centrais-de-conteudo/paineis-de-monitoramento-e-indicadores/painel-monitoramento-cnca)
* [INEP — Avaliação da Alfabetização: resultados e metas por município (ICA), edição 2025](https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/avaliacao-da-alfabetizacao/resultados/2025) — planilha oficial verificada por SHA-256 `709c7eeb…`; lógica de download e verificação reaproveitada de [luizmaibashi/painel-alfabetizacao-cgu](https://github.com/luizmaibashi/painel-alfabetizacao-cgu) (MIT License, © 2026 Luiz Fernando Maibashi)
* [Relatório de levantamento do CNCA — TCE-PB, dez/2024](https://tce.pb.gov.br/wp-content/uploads/2024/12/RELATRIODELEVANTAMENTOCNCA2.pdf) — referência metodológica (questionário aos 223 municípios paraibanos e matriz de oito riscos)
* [Decreto 11.556/2023 — CNCA](https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/decreto/d11556.htm)
