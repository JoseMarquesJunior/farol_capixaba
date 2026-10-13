# Roteiro — apresentação do painel de financiamento da educação

**Formato:** 15–20 min, demo ao vivo.
**Plateia:** chefia + colegas técnicos.
**Objetivo da sala:** sair com aval para seguir — e com os técnicos confiando no método.

> Regra que vale para a apresentação inteira: **nada aqui é conclusão de
> irregularidade.** São fatos apurados nas fontes oficiais, com a fonte de cada
> número à mão. Repita isso pelo menos duas vezes. É o que separa este trabalho
> de uma denúncia mal-feita — e é o que protege você na primeira pergunta hostil.

---

## Antes da sala (10 min de preparo)

- [ ] Abrir `dashboard.html` no navegador **antes** de entrar. São 18 MB: leva
      alguns segundos para montar. Não faça isso na frente de todo mundo.
- [ ] Deixar **três abas** já abertas, nestes endereços (o painel guarda o estado na URL):
      1. `dashboard.html#v=conformidade&ano=2024`
      2. `dashboard.html#v=fluxo&ano=2025&m=3205002` (Serra)
      3. `dashboard.html#v=escolas&ano=2025&m=3201308` (Cariacica)
- [ ] Testar o botão **"ver fonte"** uma vez. É o momento decisivo da demo; se
      falhar ao vivo, a apresentação perde o eixo.
- [ ] Zoom do navegador em **110–125%**. A base tipográfica é 14px (a mesma do
      Painel de Controle) — lê bem no monitor, mal no projetor.
- [ ] Ter o número da coleta na ponta da língua: **dados coletados em 22/09/2026**,
      exercícios **2021–2025**, **78 municípios + Estado**.

---

## 0:00–1:30 · Abertura: um número que ninguém espera

Não comece por "eu construí um painel". Comece pelo achado.

> "Em 2025, o maior item contratado dentro da função Educação no Espírito Santo
> não é ensino. É cartão-alimentação de servidores: 360 mil unidades a R$ 927,90,
> R$ 334 milhões, contratado pela unidade gestora da educação da Serra.
> Isso pode ser perfeitamente legal. O ponto é outro: **até agora ninguém
> conseguia ver isso sem abrir contrato por contrato.**"

Pausa. Então:

> "O que eu vou mostrar em quinze minutos é de onde vem e para onde vai o dinheiro
> da educação nos 78 municípios — com a fonte exata de cada número."

**Gancho reserva** (se preferir algo menos sensível a mal-entendido):

> "337 obras da educação estão em paralisação presumida pelo Tribunal — sem
> medição recente. Somadas às 12 declaradas paradas, são R$ 927,8 milhões em
> 60 municípios."

---

## 1:30–3:30 · O problema que isso resolve

Três frases, sem slides:

1. **O dado existe, mas está espalhado.** SICONFI, SIOPE, FNDE, CGU, TCE-ES,
   Censo Escolar — cada um com seu formato, sua janela e seu critério.
2. **Conferir um número exigia refazer o caminho à mão.** E quando duas fontes
   discordavam, não havia como saber qual olhar.
3. **Sem isso, a pergunta "este município cumpriu o mínimo?" tinha resposta
   demorada e frágil.**

Feche com o que mudou:

> "O painel responde isso em segundos — e mostra a conta, a fonte e a data da
> coleta de cada valor."

---

## 3:30–12:30 · Demo (4 paradas + 1 opcional)

> Fale **enquanto** navega. Não narre a interface ("aqui eu clico em…"), narre o
> raciocínio ("a pergunta agora é se as duas apurações concordam").

### Parada 1 — Conformidade (aba 1) · ~2 min

Abre já nesta visão. Aponte a faixa de KPIs no topo:

- **MDE abaixo de 25%** — pelo SIOPE e **pelo TCE-ES**, lado a lado.
- **Declarações em atraso** — de 67 a 75 municípios por ano com ao menos um
  relatório homologado fora do prazo; de 40 a 51 com atraso acima de 30 dias.
- **Maior divergência entre fontes.**

O ponto forte desta parada é o símbolo **⚑**:

> "Este sinal aparece quando o SIOPE diz que o município cumpriu o mínimo e a
> apuração do TCE-ES diz que não — ou o contrário. São **12 município-anos**
> nessa situação. Pedro Canário em 2024: o Tribunal apura 24,15%, o SIOPE apura
> 25,00%. **Não estou dizendo quem está certo.** Estou dizendo que existe uma
> divergência de critério que alguém precisa esclarecer — e até hoje ela estava
> invisível porque ninguém comparava as duas apurações."

Este é o argumento mais forte da apresentação para a plateia técnica. Não corra.

### Parada 2 — "Ver fonte" · ~2 min · **NÃO CORTE ESTA**

Clique no **"ver fonte"** de qualquer KPI.

> "Todo número do painel tem este botão. Ele abre a consulta exata que produziu
> o valor: qual API, quais parâmetros, qual arquivo, em que data foi coletado, e
> qual linha do demonstrativo. Se alguém contestar um número numa reunião, a
> resposta está a um clique."

Se a sala tem gente do TCE-ES ou auditoria, acrescente:

> "É por isso que isto serve como papel de trabalho, e não só como visualização."

### Parada 3 — Receita → aplicação, Serra (aba 2) · ~2,5 min

Mostre o **Sankey**: fonte de recursos → subfunção.

> "Em Serra, 2025: 55% vem do FUNDEB, 37% de impostos próprios, 6% de
> transferências federais. Do outro lado, 60% vai para o ensino fundamental,
> 33% para a educação infantil, 8% para administração geral.
> E isto **não é rateio proporcional** — é a ligação que o próprio município
> declarou empenho a empenho."

Role até os **repasses do FNDE** e mostre as três leituras do mesmo dinheiro:

> "Salário-educação em Serra: a CGU diz que a União pagou R$ 35,9 mi, a
> contabilidade do município registra R$ 40,7 mi e o SIOPE declara R$ 40,7 mi.
> A diferença tem explicação — rendimento de aplicação da conta. O painel mostra
> as três e diz qual é qual, em vez de escolher uma."

### Parada 4 — Nível 3: o que foi comprado · ~2 min

Ainda na visão de fluxo, desça até os **itens contratados**.

> "121.534 itens da educação entre 2022 e 2025. R$ 4,86 bilhões contratados —
> e apenas R$ 1,11 bilhão com medição registrada. Só 24 mil dos 121 mil itens
> têm medição. **Contratado não é entregue**, e agora dá para ver a diferença."

Um exemplo que todo mundo entende:

> "Alimentação escolar em Cariacica, 2025: 4 milhões de refeições a R$ 7,56 cada.
> Com preço unitário na mão, comparar municípios finalmente é possível."

### Parada 5 — Escolas (aba 3) · ~2 min · **corte esta se estiver atrasado**

> "Aqui o dinheiro chega ao CNPJ da escola: PDDE por plano orçamentário, repasse
> do município ao conselho escolar, obra no prédio — ao lado de matrículas,
> infraestrutura, IDEB e PAEBES do Censo. 39 municípios repassaram R$ 92 milhões
> a conselhos escolares em 2025."

---

## 12:30–15:00 · Por que confiar nisto (para os técnicos)

Quatro pontos, rápidos:

1. **Nada é estimado.** Onde a fonte não traz o dado, o painel diz "sem dado" —
   nunca zero. A diferença importa: zero é uma afirmação, ausência não é.
2. **Cache versionado.** A resposta original de cada consulta fica salva. Dá para
   reconstruir qualquer número de qualquer data.
3. **237 testes automatizados**, com fixtures que são respostas reais das fontes.
4. **O pipeline é reexecutável.** Um comando refaz tudo do zero.

Se perguntarem sobre o SIOPE, tenha esta pronta:

> "O SIOPE não tem API aberta — o relatório em HTML exige reCAPTCHA. A mesma
> informação vem do PDF que o FNDE publica em FTP aberto, lido programaticamente.
> Está documentado no código, com o motivo."

---

## 15:00–17:00 · O que ainda não dá para afirmar

**Não pule esta parte.** Apresentar limitações é o que faz a chefia confiar no
resto — e desarma o colega que ia levantar a mão para apontar exatamente isso.

- **Divergência não é irregularidade.** Os 12 município-anos de discordância
  entre SIOPE e TCE-ES são critérios diferentes, não fraude. Precisam de
  esclarecimento junto ao Tribunal.
- **"Paralisação presumida" é classificação do próprio TCE-ES**, por ausência de
  medição recente — não uma obra verificada em campo.
- **Há dado sujo nas fontes**, e o painel aponta em vez de esconder: Conceição da
  Barra declara receita patrimonial negativa no RREO de 2021; o arquivo de
  empenhos de 2023 do TCE-ES não traz dezembro para 25 municípios.
- **55 unidades gestoras de 11 municípios** não têm nenhuma remessa homologada na
  janela — provável conta consolidada em outra UG, **a confirmar com o Tribunal**.

> "Cada um desses pontos está escrito no README, não escondido. Se a gente for
> usar isto para cobrar alguém, é por aqui que a defesa vai atacar — melhor
> chegarmos lá antes."

---

## 17:00–19:00 · O pedido

Seja explícito. Reuniões morrem por falta de pedido claro.

**Pedido principal — escolha um:**

> "O que eu preciso desta reunião é [ ... ]."

Opções, conforme a sua prioridade real:

- **Validação de conteúdo:** meia hora com [dois colegas] para conferir os
  achados de MDE e conciliação contra o que vocês já conhecem dos municípios.
- **Interlocução com o TCE-ES:** um contato no Tribunal para esclarecer a
  divergência de critério do MDE e o padrão das UGs sem remessa. São as duas
  únicas pendências que não se resolvem do nosso lado.
- **Decisão sobre destino:** isto fica como ferramenta interna do NEDUC ou é
  oferecido para virar página do Painel de Controle?

**Sobre o último ponto**, tenha a resposta pronta — porque vão perguntar:

> "O painel já está com a identidade visual do Painel de Controle do TCE-ES:
> mesma tipografia, mesmas cores, mesmo padrão de card, tabela e alerta. Não foi
> chute — foi extraído do CSS do próprio sistema, e cada escolha está documentada
> com a fonte. **Mas incorporar como página real lá dentro é trabalho de quem
> mantém aquele sistema**: o painel é React, tem roteamento e backend próprios.
> O que eu entrego é um protótipo fiel e um pacote de handoff, não um arquivo
> para colar no código deles."

---

## Perguntas difíceis (e o que responder)

**"Esses dados estão certos?"**
> "Estão conferidos contra a fonte oficial e cada um tem a consulta que o gerou.
> Onde duas fontes oficiais discordam, eu mostro as duas — não escolho uma."

**"Isso não é atribuição do TCE-ES?"**
> "O Tribunal audita. Isto organiza o dado público para que a gente faça as
> perguntas certas — e boa parte dos dados é do próprio TCE-ES."

**"Quanto custa manter?"**
> "É um pipeline em Python que roda por comando e um arquivo HTML. Sem servidor,
> sem banco, sem licença. O custo é o tempo de reexecutar quando as fontes
> atualizam."

**"Por que não Power BI?"**
> "Porque o requisito central era rastreabilidade: cada número com a consulta que
> o produziu, e sem chamada de rede no navegador. O arquivo abre em qualquer
> máquina, inclusive sem internet."

**"E se o número estiver errado?"**
> "Clica em ver fonte. Se o erro for da fonte, está documentado nas limitações.
> Se for meu, o teste que faltou entra na suíte." *(Esta resposta vale ouro com
> plateia técnica — não tente parecer infalível.)*

**"Dá para incluir [outro município / outro ano / outra despesa]?"**
> "Os anos 2021–2025 e os 78 municípios já estão. Escopo novo é questão de rodar
> o pipeline — me diga qual e eu estimo."

---

## Se der errado

- **Dashboard não abre / trava:** tenha `docs/identidade_tcees/conferencia/*.png`
  numa pasta aberta. São screenshots de todas as visões. Continue pelos prints.
- **Projetor ilegível:** aumente o zoom e vá direto para a Parada 1 e a Parada 2.
  As outras três são dispensáveis; essas duas são a apresentação.
- **Acabou o tempo no meio da demo:** pule para "O que ainda não dá para afirmar"
  e para o pedido. Terminar sem pedido é pior que cortar a demo pela metade.

---

## Cola de números (não decore — tenha à vista)

| Fato | Número |
|---|---|
| Cobertura | 78 municípios + Estado, 2021–2025, coleta 22/09/2026 |
| MDE abaixo de 25% | 10 municípios em 2021; 2 em 2024 (Guaçuí 22,42%, Linhares 24,98%) |
| MDE pelo TCE-ES | 12 em 2021, 3 em 2023, 5 em 2024, 3 em 2025 |
| Divergência entre as duas apurações | **12 município-anos** |
| FUNDEB abaixo de 70% | 6 municípios em 2021; nenhum de 2022 a 2025 |
| Entregas fora do prazo | 67 a 75 municípios/ano; 40 a 51 com atraso > 30 dias |
| Conciliação função 12 × SIOPE | 19 a 26 municípios/ano acima de 5% de divergência |
| Obras | 765 contratos, R$ 2,00 bi; 12 paradas + 337 em paralisação presumida = R$ 927,8 mi |
| Itens contratados | 121.534 itens, R$ 4,86 bi contratados, R$ 1,11 bi medidos |
| Conselhos escolares | 39 municípios, R$ 92,0 mi em 2025 |
| Qualidade | 237 testes; cache versionado de toda consulta |

---

## Uma última coisa

O impulso natural é abrir pedindo desculpa pelo que falta. Não faça isso. O
trabalho tem lacunas e elas estão documentadas — mas a sala precisa primeiro
entender **o que passou a ser possível**. As limitações vêm depois, no lugar
certo do roteiro, onde soam como rigor e não como fraqueza.
