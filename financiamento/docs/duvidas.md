# Dúvidas sobre o painel — respostas

Respondido em 22/09/2026, sobre a versão `20260922T175441Z` do dataset. Cada número abaixo
veio dos arquivos em `dados/processado/` ou do cache em `dados/bruto/`; onde a resposta é
**inferência**, está dito.

---

## 1. O que seria "paralisação presumida" na obra (TCE-ES)?

**O portal não define.** O dataset *Contratações* não traz descrição nos recursos (o `notes`
do pacote é genérico: "Acompanhe informações sobre contratações realizadas pela Administração
Pública") e não há dicionário de dados publicado.

**O que os dados mostram** (765 contratos de obra da Educação, `tcees_obras_educacao.csv`):
a diferença entre "Em execução" e "Paralisação presumida" é **a data da última medição**, e o
corte é limpo:

| Situação | Contratos | Última medição (faixa) | % medido (mediana) |
|---|---|---|---|
| Em execução | 51 | 08/06/2026 a 31/07/2026 | 43% |
| Paralisação presumida | 337 | 09/10/2022 a **03/06/2026** | 92% |
| Paralisada / Interrompida (declarado) | 12 | 31/10/2022 a 18/02/2026 | 8% a 78% |
| Não iniciada | 240 | sem medição | — |

Nenhuma obra "presumida" está sem medição: todas as 337 têm medição, só que **nenhuma nos
~90 dias anteriores à carga**. A leitura (inferência, a confirmar com o Tribunal) é:
*o TCE-ES presume paralisação quando a obra passa um tempo sem medição nova* — é sinal
inferido pelo sistema, não declaração do município. Por isso o painel separa as 12
declaradas das 337 presumidas e não chama as presumidas de "obra parada" sem qualificar.

**Cuidado importante na leitura**: 125 das 337 já têm **99% ou mais do valor medido** e 313
das 337 estão com **vigência vencida**. Boa parte parece obra concluída sem encerramento
formal (recebimento/baixa), não obra abandonada. O número cheio — R$ 927,8 mi em 60
municípios — é o teto do problema, não o problema.

**A perguntar ao TCE-ES**: qual é o prazo exato sem medição que dispara a presunção, e se a
situação é revista quando a obra é recebida.

---

## 2. MDE: diz que nenhum ficou abaixo do mínimo, mas em alguns a União complementou. Por quê?

São **duas regras diferentes, com bases diferentes** — e o mínimo é do *município*, não da
escola (não existe mínimo legal por escola).

**O 25% (art. 212 da CF)** olha só o dinheiro de impostos do próprio município. No Anexo 8 do
SIOPE, que é a fonte do índice, a conta é esta (itens lidos do PDF em cache):

```
22- TOTAL DAS DESPESAS DE MDE CUSTEADAS COM RECURSOS DE IMPOSTOS
23- (+) TOTAL DAS RECEITAS TRANSFERIDAS AO FUNDEB
24 a 27- (−) FUNDEB não utilizado, superávit, restos a pagar sem disponibilidade, cancelamentos
28- = TOTAL DAS DESPESAS PARA FINS DE LIMITE
29- APLICAÇÃO EM MDE SOBRE A RECEITA LÍQUIDA DE IMPOSTOS   → é o % que o painel mostra
```

A complementação da União **não entra nem no numerador nem no denominador**: é transferência
da União, não "receita resultante de impostos".

**A complementação (art. 212-A, V, da CF; EC 108/2020 e Lei 14.113/2020)** existe por outro
motivo: o *valor por aluno* do fundo ou da rede fica abaixo do mínimo nacional, e a União
completa (VAAF, VAAT e VAAR). É indicador de **baixa receita por aluno**, não de
descumprimento — e não é prêmio nem punição pelo esforço próprio.

Os dados deixam isso visível: em **2025, 77 dos 78 municípios** receberam complementação
(R$ 345,2 mi) e **todos aplicaram 25% ou mais**. Em 2024 foram 62 municípios (R$ 278,2 mi),
com MDE de 22,42% a 38,77% — ou seja, quem recebe complementação está dos dois lados do
mínimo:

| Exercício | Municípios com complementação | Total | MDE < 25% (SIOPE) |
|---|---|---|---|
| 2021 | 9 | R$ 17,6 mi | 10 |
| 2022 | 33 | R$ 90,7 mi | 0 |
| 2023 | 49 | R$ 126,4 mi | 0 |
| 2024 | 62 | R$ 278,2 mi | 2 |
| 2025 | 77 | R$ 345,2 mi | 0 |

Observação de fonte: o DCA traz a complementação numa linha só
(`1.7.1.5.00.0.0 — Transferências de Recursos de Complementação da União ao FUNDEB`), **sem
separar VAAF, VAAT e VAAR**. Essa abertura precisaria de outra fonte (FNDE/SIOPE).

---

## 3. Gastos com curso pré-IFES em Vitória: dá para detalhar mais do que esse nível?

**Dá, e o dado já está no cache** — o painel é que mostra o agregado por ação.

O que o painel mostra hoje (ação **10008 — CURSOS PRE IFES**, que só existe em Vitória):

| Exercício | Dotação inicial | Dotação atualizada | Empenhado | Pago |
|---|---|---|---|---|
| 2022 | 100.000 | 50.000 | **0** | 0 |
| 2023 | 10.000 | 2.700 | **0** | 0 |
| 2024 | 10.100 | 100 | **0** | 0 |
| 2025 | 121.120 | 1.011.570 | **891.450** | 852.250 |

Ou seja: por três anos a ação existiu só no orçamento; a execução é de 2025.

Descendo ao empenho no recorte em cache (`dados/bruto/tcees/empenhos/2025/`), o gasto de 2025
é inteiro de **um credor**:

* **ENSINATECH LTDA** — CNPJ 51.325.776/0001-12 — R$ 891.450,00 empenhados;
* elemento **serviços de tecnologia da informação e comunicação — PJ**, subelemento
  **locação de software**;
* fonte **receita de impostos e de transferência de impostos — MDE**;
* subfunção **12.361 (ensino fundamental)**; 2 empenhos, com movimentos em 5 meses
  (jul, set, out, nov e dez).

**Dá para ir um nível além?** Sim, em duas frentes, nenhuma delas coletada ainda:

1. **Item comprado** (descrição, quantidade, valor unitário): está no recurso
   *Itens – 2025* do mesmo dataset de contratações do TCE-ES, quando a despesa passou por
   contrato — ver a dúvida 6;
2. **Nota fiscal e processo**: só no portal da transparência do município.

Dois pontos que o caso levanta e que o painel **não** conclui: curso preparatório pago com
fonte MDE e classificado em ensino fundamental merece checagem de enquadramento (arts. 70 e
71 da LDB), e "locação de software" como objeto de um curso preparatório merece ler o
contrato.

---

## 4. Nas escolas de Vitória, o repasse municipal aumentou muito em 2025. Por quê?

Depende do que está sendo comparado — **no total do município ele caiu em 2025**:

| Exercício | Repasse aos conselhos (empenhado) | Conselhos | Subvenções sociais | Auxílios (capital) | Escolas com auxílio |
|---|---|---|---|---|---|
| 2021 | R$ 16,96 mi | 82 | 15,02 mi | 1,94 mi | 81 |
| 2022 | R$ 26,49 mi | 90 | 24,51 mi | 1,98 mi | 81 |
| 2023 | R$ 26,83 mi | 90 | 24,24 mi | 2,59 mi | 83 |
| 2024 | **R$ 37,85 mi** | 91 | 32,88 mi | 4,98 mi | 90 |
| 2025 | R$ 32,89 mi | 91 | 30,49 mi | 2,40 mi | **57** |

O salto grande foi **2021 → 2024** (o repasse praticamente dobrou). De 2024 para 2025 o total
caiu 13%.

O que aumentou em 2025 foi **por escola**: o dinheiro de capital foi para menos escolas, em
valores bem maiores. Exemplos que aparecem no painel:

| Escola (conselho) | 2024 | 2025 |
|---|---|---|
| CMEI Reinaldo Ridolfi | R$ 259 mil | **R$ 760 mil** |
| EMEF Paulo Roberto Vieira Gomes | R$ 160 mil | **R$ 664 mil** |
| EMEF Padre Anchieta | R$ 422 mil | R$ 592 mil |

Nessas duas primeiras, os auxílios saltaram de R$ 17,6 mil para R$ 176–200 mil por escola, e
as subvenções também subiram. A ação é a mesma desde 2021 (*Autonomia financeira das unidades
de ensino*); a fonte muda de `111` para `500` em 2023, mas isso é a adoção da fonte
padronizada da STN, não dinheiro novo.

Então: **concentração e redistribuição, não aumento do programa**. O critério dessa escolha
não está no dado aberto — é pergunta para a Secretaria (regra de rateio) ou para o processo
de cada repasse.

**Cuidado de leitura na visão Escolas**: só entram os conselhos ligados a uma escola do Censo
— em Vitória, 90 de 97. Os 7 restantes (ex.: "Conselho de Escola da EMEF Orlandina D Almeida
Lucas", que no Censo é "EMEF Orlandina Dalmeida Lucas") aparecem na lista de recebedores não
identificados e no Nível 3, mas **não somam na escola**. Por isso o total da visão Escolas em
2025 (R$ 30,2 mi) é menor que o do município (R$ 32,9 mi).

---

## 5. Viabilidade de um chatbot para responder dúvidas sobre os dados do painel

**Viável, com uma condição de desenho: o modelo não pode responder de memória — só com o
resultado de uma consulta.**

O que joga a favor já existe:

* `consolidado.csv` — 170.141 registros, um número por linha, com indicador, rótulo, valor,
  unidade, localização na fonte, cálculo e as consultas de origem;
* `etl/indicadores.py` — o catálogo que diz o que cada indicador é e como foi calculado;
* `consultas.csv` — a proveniência (URL, instante, arquivo, SHA-256) que o "ver fonte" usa.

Desenho recomendado: carregar o consolidado num SQLite, dar ao modelo **só** a capacidade de
consultar (`SELECT` sobre colunas conhecidas) e obrigá-lo a responder citando indicador +
consulta, como o "ver fonte" faz. Sem consulta, sem número.

* **Responde bem**: "quanto o município X gastou em Y", "quem foram os maiores credores",
  "quais municípios ficaram abaixo de 25%", "quanto a escola Z recebeu de PDDE".
* **Não responde**: perguntas de *por quê* — quatro das seis deste arquivo são desse tipo.
  Duas exigiram abrir o recorte de empenhos, uma exigiu ler o Anexo 8 em PDF e uma não tem
  resposta em dado aberto (o critério de rateio de Vitória). O chatbot precisa dizer "isto
  não está no dado" em vez de inventar causa.
* **Riscos**: número inventado (mitigação: consulta obrigatória e mostrar a linha de origem);
  recorte errado sem avisar — por exemplo somar 2023 sem lembrar que faltam os meses de
  dezembro de 25 municípios, e para isso existe o campo `tcees_emp_meses_ausentes`; e
  confundir "empenhado" com "pago".
* **Esforço**: dias para uma versão restrita a consultas, porque o dado já está pronto e
  documentado. O trabalho caro é montar o conjunto de perguntas de teste com resposta
  conhecida, para saber quando ele regride.

Roda local (os dados estão em disco), chamando a API do Claude; nenhum dado pessoal sai.

---

## 6. Vale pegar os portais da transparência dos municípios, ou já temos dados suficientes?

**Para o Nível 3 — quem recebeu, em qual ação, com que fonte, em qual obra — já temos.** O
que falta é *o item comprado* e a *nota fiscal*. E, antes dos 78 portais, há dois caminhos
padronizados:

1. **Recurso "Itens" do próprio TCE-ES** (mesmo dataset de contratações que já usamos, um
   arquivo por ano, ~390 MB em 2025). Cabeçalho conferido hoje: `DescricaoItem`,
   `UnidadeMedida`, `QuantidadeItemContratado`, `ValorUnitarioItemContratado`,
   `ValorTotalItemContratado`, as quantidades **medidas**, a contratada e a
   `ChaveInstrumento`. Dá para recortar pelas chaves dos contratos da Educação, exatamente
   como já fazemos com as medições — é o maior ganho pelo menor custo, e não depende de
   negociar com ninguém.
2. **PNCP** (portal nacional da Lei 14.133/2021): **51 dos 765** contratos de obra da
   Educação já apontam para `pncp.gov.br`. A pista é real, mas **não confirmei**: no teste de
   hoje a API de consulta devolveu 503 (serviço indisponível).

**Portais municipais ficam como último recurso.** Medindo a heterogeneidade nos endereços que
os próprios municípios declaram ao TCE-ES: **106 domínios distintos** — Diário Oficial
(`ioes.dio.es.gov.br`, 255 links), buckets S3 (115), família `portaltp.com.br` (124),
`portaldecompraspublicas.com.br` e o resto pulverizado em sites próprios. Não há padrão, e
raspar 78 sites é manutenção permanente para um ganho que, na maior parte dos casos, o
recurso "Itens" já entrega.

Ordem de prioridade: **Itens do TCE-ES → PNCP (quando voltar) → portal municipal, só para uma
apuração específica** — e aí com o endereço conferido registrado em
`dados_manuais.yaml → nivel3.portais_transparencia`.

---

## 7. Na aba 'Conformidade', na parte de 'Mínimos legais', qual a diferença entre '% MDE' e % MDE — TCE-ES ? Por que alguns números diferem entre si?

*(respondido em 24/09/2026, sobre a versão `20260923T125540Z` do dataset)*

São **duas apurações do mesmo índice constitucional, feitas por dois órgãos diferentes** —
e **nenhuma das duas é calculada pelo painel**: as duas células são copiadas da fonte.

| | **% MDE** | **% MDE — TCE-ES** |
|---|---|---|
| Quem apura | o **município**, na declaração ao MEC/FNDE | o **TCE-ES**, sobre as remessas do CidadES |
| De onde o painel lê | Anexo 8 do RREO no SIOPE, item **29 — "APLICAÇÃO EM MDE SOBRE A RECEITA LÍQUIDA DE IMPOSTOS"**, coluna "% APLICADO" (PDF no FTP do FNDE) | dataset *Despesas com saúde, educação e pessoal* → recurso **"Educação"**, coluna `AplicacaoPercentual` |
| Base | **uma** declaração anual (RREO do 6º bimestre) | **12** remessas mensais (`MesUltimoEnvio` = 12 nos anos fechados) |
| Anos disponíveis | 2021–2025 | 2009–2026 (o painel usa 2021–2025) |
| No código | `etl/siope.py` (extração do PDF) | `etl/tcees.py:374` |

O painel não recalcula nem arredonda nenhum dos dois. A única conferência que faz é
aritmética, no lado do SIOPE: confere o % declarado contra `25 × aplicado ÷ exigido` e
contra o item 28 ("total das despesas para fins de limite"); quando não bate, grava aviso.

O que **nenhum dos dois é**: o parecer prévio do Tribunal. Os dois são declaratórios — o
que muda é o sistema em que o município declara e quem fecha a conta.

### Por que os números diferem

Na maioria dos casos não diferem. Nos 390 município-anos com as duas apurações
(2021–2025, 78 municípios):

| Diferença (TCE-ES − SIOPE) | Município-anos |
|---|---|
| até 0,5 p.p. | 289 |
| acima de 0,5 p.p. | **101** |
| acima de 1 p.p. | 56 |
| acima de 3 p.p. | 10 |

A mediana é **0,00 p.p.**, e a divergência vai para os dois lados (57 casos com o TCE-ES
abaixo do SIOPE, 44 acima) — não é desconto sistemático de um em relação ao outro.

**Onde está a diferença.** Separando o índice em numerador (o que foi aplicado) e
denominador (a receita de impostos), nos 101 casos divergentes:

* **83** divergem **só no numerador** — mesma receita base, valor aplicado diferente;
* **1** diverge só no denominador (São José do Calçado, 2022);
* **17** nos dois.

Ou seja: as duas fontes concordam sobre **quanta receita de impostos o município teve** e
discordam sobre **quanto disso conta como aplicado em MDE**. Os maiores casos:

| Município | Ano | SIOPE | TCE-ES | Aplicado (SIOPE) | Aplicado (TCE-ES) |
|---|---|---|---|---|---|
| Irupi | 2024 | 33,55% | 25,10% | R$ 16,95 mi | R$ 12,56 mi (−25,9%) |
| Vila Velha | 2021 | 29,36% | 24,61% | R$ 234,36 mi | R$ 196,41 mi (−16,2%) |
| Guaçuí | 2021 | 26,03% | 22,11% | R$ 14,84 mi | R$ 12,60 mi (−15,1%) |
| Muniz Freire | 2023 | 32,54% | 27,77% | R$ 21,00 mi | R$ 17,92 mi (−14,7%) |
| Ibiraçu | 2023 | 28,58% | 24,83% | R$ 11,05 mi | R$ 9,50 mi (−14,0%) |
| São Domingos do Norte | 2022 | 30,56% | 33,90% | R$ 10,81 mi | R$ 12,00 mi (+11,0%) |

**Explicações prováveis — inferência, a confirmar com o Tribunal** (o método do índice do
TCE-ES não está publicado):

1. **Momento da apuração.** O SIOPE é a foto de um PDF gerado numa data; o índice do
   TCE-ES é recomposto das 12 remessas mensais, que o município retifica ao longo do
   tempo. Retificação posterior muda um e não o outro.
2. **Cadeia de deduções do Anexo 8** (itens 23 a 28): soma a contribuição ao FUNDEB e
   desconta FUNDEB não utilizado, superávit, restos a pagar sem disponibilidade
   financeira e cancelamentos. O Tribunal aplica critério próprio sobre as mesmas
   rubricas — inclusive glosas.
3. **Escopo da despesa**: o que cada sistema aceita como despesa de MDE (arts. 70 e 71 da
   LDB) pode não ser o mesmo conjunto de empenhos.

A compensação da EC 119/2022 **não** explica os casos grandes: os 7 município-anos com
compensação têm divergência mediana de 0,00 p.p.

### Como ler isso no painel

* A coluna **"TCE-ES − SIOPE (p.p.)"** é a diferença, com sinal.
* O **⚑** marca o que importa para auditoria: **uma apuração abaixo de 25% e a outra
  não**. São **13 município-anos** — 2 em 2021, 3 em 2023, 5 em 2024, 3 em 2025:

| Município | Ano | SIOPE | TCE-ES |
|---|---|---|---|
| Guaçuí | 2021 | 26,03% | **22,11%** |
| Vila Velha | 2021 | 29,36% | **24,61%** |
| Ibiraçu | 2023 | 28,58% | **24,83%** |
| Laranja da Terra | 2023 | 25,00% | **24,04%** |
| Mimoso do Sul | 2023 | 25,56% | **22,83%** |
| Linhares | 2024 | **24,98%** | 25,02% |
| Montanha | 2024 | 25,57% | **24,90%** |
| Muniz Freire | 2024 | 25,83% | **24,49%** |
| Pedro Canário | 2024 | 25,00% | **24,15%** |
| São Gabriel da Palha | 2024 | 26,17% | **24,53%** |
| Brejetuba | 2025 | 25,78% | **24,55%** |
| Ibatiba | 2025 | 25,14% | **24,97%** |
| Iúna | 2025 | 25,08% | **24,85%** |

Linhares 2024 é o único caso na direção contrária: quem fica abaixo é o SIOPE.

* O cartão **"Municípios abaixo do mínimo de MDE (25%)"** conta pelo **SIOPE** — é o
  índice oficial do art. 212 perante o FNDE. A contagem pelo TCE-ES e o número de casos
  em que as duas discordam sobre o mínimo vêm no subtítulo do cartão.

**O painel não decide qual das duas está certa**, e não deveria: divergência que
atravessa os 25% é justamente o que se leva ao município e ao Tribunal para explicar.


--------
Dúvida: na aba 'Conformidade, temos:
 % aplicado em MDE: apuração do TCE-ES × SIOPE (tolerância de 0,5 p.p.): 289 de 390 ente-anos batem
maiores diferenças
Irupi (2024): -R$ 8,45
Muniz Freire (2023): -R$ 4,77
Vila Velha (2021): -R$ 4,75
...
Esses valores são realmente em reais (R$) ou em percentual?

----
Sugestão: 
- evitar uso de travessões
- No menu 'Como ler este painel': a tag 'sem dado' está na mesma linha da tag 'cumpre'. Avaliar colocar em linha diferente, assim como os outros tags ('descumpre', 'sinal a verificar', 'cumpre')
- na aba 'conformidade', no menu 'Mostrar', avaliar colocar um filtro mostrando apenas municípios 'sem dados'
- nas abas das fontes, verificar texto: simplicar (remover texto 'abre num aba') e explicar melhor o subtítulo
- no grafico que mostra o percentual de MDE (SIOPE e TCE-ES) e FUNDEB, em vez de cruz vermelha quando não atingir o mínimo, use círculos vermelhos