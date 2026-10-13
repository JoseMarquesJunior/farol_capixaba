# Fase 4 — o painel de evidências do CNCA

A aba **CNCA — Evidências** substitui a antiga "CNCA — Auditoria", como decidido na revisão da
Fase 1. A diferença não é de aparência: a aba anterior era um **checklist que o auditor
preenchia a mão**, guardado no `localStorage` do navegador; esta é **papel de trabalho gerado
pelo ETL**, em que cada célula sai da tabela de evidências e leva ao registro bruto que a
originou.

```powershell
python -m financiamento.etl.evidencias --anos 2021-2025   # gera dados/processado/dataset_cnca.json
python -m financiamento.build_dashboard                    # embute e monta dashboard.html
python docs/identidade_tcees/conferir_cnca.py              # confere as 6 visões num Chromium
```

---

## 1. As seis visões

| Visão | O que responde |
|---|---|
| **Matriz** | As 6 questões e seus 23 achados, cada um com o tipo de evidência, a distribuição dos 78 municípios por status e a contagem de indícios. Abre com as **constatações** — o que vale para os 78 e é dito uma vez |
| **Mapa de evidências** | 78 linhas × 23 achados, cor e símbolo por status. Clicar num município abre a ficha dele |
| **Ficha do município** | Todas as evidências daquele ente, por questão, com valor, status, a ressalva do indicador e o "ver fonte". Abaixo, os números que respondem perguntas direto: os quatro índices de P24, a cobertura do PDDE de P21, os repasses estaduais de P18, as contratações de P47/P48 e as buscas manuais pendentes no diário |
| **Perguntas (P1–P49)** | Uma linha por pergunta do questionário, com o que o dado público responde **antes** das respostas dos municípios — que é o que permite confrontá-las quando chegarem |
| **Cobertura** | Quanto da matriz o dado alcança, os 10 limiares com a distribuição real que os justifica, e as limitações estruturais |
| **Exportar** | CSV do papel de trabalho, com as colunas de proveniência preenchidas |

---

## 2. As três regras que a tela inteira obedece

**Nenhuma célula diz "achado".** O vocabulário é indício de risco, sem indício, inconclusivo e
sem dado público — e a legenda, presente em todas as visões, repete que quem transforma indício
em achado é o auditor, com o documento na mão. A conferência automatizada falha se a palavra
"achado confirmado" (ou equivalente) aparecer na tela.

**Lacuna nunca vira zero.** Onde não há dado, a célula diz "sem dado público" e a nota diz por
quê e qual é o caminho alternativo. Isso é conferido nos dois lados: o ETL garante que nenhuma
linha `sem_dado_publico` carrega valor, e a conferência do navegador exige que a ficha de um
município mostre ao menos uma lacuna como tal.

**O que vale para os 78 é dito uma vez.** As três constatações (C3.1, C4.3, C4.5) abrem a visão
da matriz, com a medida que as sustenta e a consequência para a auditoria. Elas saem do mapa de
calor de propósito: apontar 78 vezes uma característica da classificação orçamentária brasileira
faria parecer que cada município fez algo diferente dos outros.

---

## 3. Decisões de construção

**O dataset do CNCA é separado do dataset geral.** `dataset_cnca.json` (5,1 MB) é embutido num
segundo bloco `<script type="application/json">`, e o painel geral não precisa ser regerado para
a matriz mudar. Faltar o arquivo é situação normal — quem só rodou o pipeline geral ainda não
gerou a matriz —, e nesse caso a aba monta dizendo quais comandos rodar, em vez de derrubar a
montagem inteira do painel.

**O "ver fonte" é o mesmo da página inteira.** Em vez de um diálogo parecido só para esta aba,
os indicadores e as consultas da matriz entram nos catálogos globais que `abrirFonte` consulta
(`META.indicadores` e `CONSULTAS`). Um só comportamento de proveniência no produto. A **ressalva
do indicador** vai junto como observação: quem abre a fonte de um proxy precisa ler o que ele
não prova.

**Cor nunca é o único canal.** Cada status tem cor, **símbolo** (▲ ◆ · ○) e texto. As quatro
cores reusam as severidades do `#alerta` do Painel de Controle do TCE-ES, para que o mesmo tipo
de fato tenha a mesma cor nos dois sistemas. O CSS só consome tokens: nenhum hex, raio ou sombra
solto, como no resto do arquivo.

**O dataset carrega o `q` além do endpoint já resolvido.** Parece redundante e não é: o CSV
precisa da proveniência legível, e o painel precisa do id para reabrir a consulta inteira no
"ver fonte". A primeira versão resolvia a proveniência em colunas e descartava o `q` — o
diálogo abria vazio em 4.120 linhas, e foi a conferência automatizada que pegou.

---

## 4. A conferência

[`docs/identidade_tcees/conferir_cnca.py`](identidade_tcees/conferir_cnca.py) substitui a
conferência da aba anterior (que testava persistência no `localStorage`) e verifica o que hoje
importa, num Chromium de verdade:

* as seis visões renderizam **sem erro de console**;
* a tela não usa vocabulário que confunda indício com achado, e diz "indício";
* a ficha de um município mostra ao menos uma lacuna como "sem dado público";
* o "ver fonte" de uma evidência abre e mostra a consulta reproduzível — procurando uma que
  **tenha** consulta, porque achado documental sem ato localizado não tem requisição por trás,
  e o diálogo dele mostra só a fórmula e a ressalva, o que é correto;
* o CSV exportado traz as colunas de proveniência, e nenhuma linha com valor sai sem elas.

Resultado da última execução: **7.332 linhas no CSV, 4.120 com valor, nenhuma sem proveniência**,
seis visões renderizadas, zero erro de console. Os screenshots ficam em
`docs/identidade_tcees/conferencia/`.

---

## 5. O que o painel ainda não faz

* **Não recebe as respostas do questionário.** Quando elas chegarem, a visão "Perguntas" é o
  lugar natural para pôr resposta declarada ao lado do que o dado diz — é para isso que ela foi
  construída assim.
* **Não tem mapa geográfico.** O "mapa de evidências" é município × achado, não cartográfico. A
  geografia não ajuda a ler esta matriz.
* **Não guarda anotação do auditor.** A aba anterior guardava checklist e observações no
  navegador, com o aviso de que ficavam só naquele dispositivo. Se a equipe quiser isso de volta,
  vale decidir antes **onde** deve ficar — o `localStorage` perdia tudo ao trocar de máquina, e
  era a maior fragilidade da aba antiga.
