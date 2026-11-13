"use strict";
/* Visão "Como ler e metodologia": regras, medidas, conferências e limitações. */

function renderMetodologia(main) {
  const T = META.totais, conf = META.conferencia;
  const sec = (id, titulo, ...filhos) => h("section", { class: "card metodo", id }, h("h3", {}, titulo), ...filhos);
  const p = t => h("p", {}, t);
  const incompletos = META.incompletos || [];
  const porAno = {};
  for (const x of incompletos) (porAno[x.ano] = porAno[x.ano] || []).push(nomeMun(x.m) + " (falta " + x.faltam.join(", ") + ")");

  main.append(h("section", { class: "cab-visao" }, h("h2", {}, "Como ler e metodologia"),
    h("p", {}, "O que cada rede mostra, de onde vem cada número, as regras de classificação, as medidas usadas e o que os dados não dizem.")));
  main.append(
    sec("m-para-que", "Para que servem estas redes",
      p("Um painel de tabelas responde \"quanto\". Um grafo responde \"quem está ligado a quem\" — e é nas ligações que aparecem os padrões que interessam ao controle: "
        + "o fornecedor que vence em dezenas de municípios, o município que depende de uma empresa só, a região onde as mesmas empresas se revezam, a contratada com obra parada em vários lugares."),
      h("ul", { class: "lista" },
        h("li", {}, h("strong", {}, "Fornecedores"), " — grafo bipartido: de um lado os 78 municípios, do outro as empresas que receberam empenhos da Educação. Mostra alcance e concentração."),
        h("li", {}, h("strong", {}, "Municípios conectados"), " — a projeção do grafo anterior: município ligado a município pelos fornecedores em comum. Mostra os mercados regionais."),
        h("li", {}, h("strong", {}, "Obras"), " — contratada ligada a município pelos contratos de obra da Educação, com a situação de cada um.")),
      h("p", { class: "callout sinal" }, h("strong", {}, ESTADOS.sinal.simbolo + " Ligação não é irregularidade. "),
        "Atender muitos municípios é normal para quem vende merenda, papel ou ônibus. Os padrões daqui servem para escolher onde olhar — preço, competitividade das licitações, capacidade da contratada —, nunca como conclusão.")),
    sec("m-como-ler", "Como ler as figuras",
      h("dl", { class: "glossario" },
        h("dt", {}, "Quadrado"), h("dd", {}, "Um município."),
        h("dt", {}, "Círculo"), h("dd", {}, "Uma empresa (ou cooperativa, associação, fundação), identificada pela raiz do CNPJ — os 8 primeiros dígitos, que juntam matriz e filiais. O tamanho é o valor recebido no recorte."),
        h("dt", {}, "Cor do círculo"), h("dd", {}, "O alcance no recorte: local (2 a 4 municípios), regional (5 a 14) ou estadual (15 ou mais). Tons de um mesmo azul, do claro ao escuro."),
        h("dt", {}, "Anel vazado"), h("dd", {}, "Órgão público ou concessionária (energia, água, telefonia) — aparecem só quando o filtro de tipo de credor os inclui."),
        h("dt", {}, "Linha"), h("dd", {}, "Houve empenho daquele município àquele fornecedor no recorte; mais grossa, mais valor. Na rede de municípios, mais grossa = mais fornecedores em comum."),
        h("dt", {}, "No mapa do ES"), h("dd", {}, "Cada município no seu lugar; cada fornecedor no centro de gravidade dos municípios que atende (ponderado pela raiz quadrada do valor), afastado dos vizinhos até não sobrepor."),
        h("dt", {}, "Afinidade"), h("dd", {}, "Disposição por forças (ForceAtlas2): fica perto quem compra dos mesmos fornecedores, longe quem não compra. Não há eixo; distância é afinidade, não quilômetro. Os municípios levam a cor e a letra da sua comunidade."),
        h("dt", {}, "Letra"), h("dd", {}, "Na rede de municípios, a comunidade. As três maiores têm cor; as demais, cinza — a letra é que as distingue, para a cor nunca ser a única pista."),
        h("dt", {}, "Aproximar e mover"), h("dd", {}, "Ctrl (ou ⌘) + roda do mouse aproxima; depois de um clique na figura, só a roda basta. Arrastar move; duplo clique aproxima. No celular, um dedo rola a página e dois dedos movem e aproximam a figura. "
          + "Pelo teclado: o botão \"Ir para a figura\" leva o foco a ela; + e − aproximam, as setas movem, 0 enquadra e Esc limpa a seleção. A busca da barra da figura aceita parte do nome, sem acento, ou os dígitos do CNPJ.")),
      p("Tudo o que está numa figura está também na tabela logo abaixo dela, com busca, ordenação, CSV e Excel. Clicar no nome de uma linha seleciona o nó na figura.")),
    sec("m-dados", "De onde vêm os dados",
      h("ul", { class: "lista" },
        h("li", {}, h("strong", {}, "Empenhos dos municípios (TCE-ES, dados abertos)"), " — o recorte da função 12 (Educação) de " + ANOS[0] + " a " + ANOS[ANOS.length - 1] + " que o pipeline do painel já guarda em cache, com o SHA-256 de cada arquivo original. Linha = empenho × mês; o valor é a soma de \"Empenhada\" (e \"Paga\")."),
        h("li", {}, h("strong", {}, "Obras e serviços de engenharia (TCE-ES)"), " — os contratos com setor Educação nos municípios, com medições e aditivos (a mesma tabela da seção de obras do painel)."),
        h("li", {}, h("strong", {}, "IBGE"), " — a malha municipal do ES e as regiões imediatas e intermediárias de cada município.")),
      tabela([
        { rotulo: "Consulta", valor: c => c.descricao },
        { rotulo: "Fonte", valor: c => c.fonte },
        { rotulo: "Coletada em", valor: c => c.obtido_em, fmt: dataHoraBR },
        { rotulo: "Arquivo no cache", valor: c => c.arquivo, render: c => h("code", {}, c.arquivo || "—") },
        { rotulo: "SHA-256", valor: c => c.sha256 || "", render: c => c.sha256 ? h("code", { class: "small" }, c.sha256.slice(0, 16) + "…") : "—" },
      ], Object.entries(META.consultas).map(([id, c]) => ({ id, ...c })), "Consultas usadas nesta página", { csv: "consultas_redes.csv", inicio: 30 })),
    sec("m-regras", "Regras de classificação",
      h("h4", {}, "O que entra"),
      p("Só a função 12 (Educação), sem a modalidade 91 (operações intraorçamentárias, que repetiriam o valor). O grupo de natureza 1 (pessoal e encargos) fica fora da rede: o credor da folha é o banco, o instituto de previdência ou o próprio ente — não é fornecedor."),
      tabela([{ rotulo: "Parte do empenhado", valor: l => l.r }, { rotulo: "Valor " + ANOS[0] + "–" + ANOS[ANOS.length - 1], valor: l => l.v, num: true, fmt: brl }, { rotulo: "Na rede?", valor: l => l.n }], [
        { r: "Pessoas jurídicas identificadas por CNPJ (fora pessoal)", v: T.pj, n: "sim — são os nós da rede" },
        { r: "Pessoas físicas (CPF)", v: T.pf, n: "não — somadas por município, sem identificar ninguém" },
        { r: "Outros identificadores (\"identificação especial\", \"inscrição genérica\")", v: T.outro, n: "não" },
        { r: "Pessoal e encargos (grupo de natureza 1)", v: T.pessoal, n: "não" },
      ], "O que entra na rede", { busca: false, inicio: 0 }),
      h("h4", {}, "Mercados"),
      p("Cada linha de empenho vai para o primeiro mercado cuja regra casar, pela natureza da despesa (elemento e subelemento) e, quando a natureza é genérica, pelo nome do programa ou da ação. As regras foram conferidas nos subelementos de maior valor de " + ANOS[0] + "–" + ANOS[ANOS.length - 1] + "."),
      tabela([{ rotulo: "Mercado", valor: m => m.rotulo }, { rotulo: "Regra", valor: m => m.regra, classe: "motivo" }], MERCADOS, "Mercados", { busca: false, inicio: 0 }),
      h("h4", {}, "Tipos de credor"),
      p("Pelo nome do credor: conselho ou caixa escolar (e unidade executora); concessionária (energia, água, telefonia); órgão ou entidade pública (prefeitura, secretaria, fundo, previdência, consórcio público, banco público, conselho profissional…); cooperativa, associação, instituto ou fundação; e empresa, o resto. "
        + "A projeção entre municípios e o recorte inicial usam só empresas e terceiro setor."),
      h("h4", {}, "Origem do recurso"),
      p("Pelo nome da fonte reduzida, porque o código mudou em 2023 (111, 112, 122… viraram 500, 540, 552…) e o nome não: FUNDEB; FNDE (salário-educação, PNAE, PNATE e outras transferências do FNDE); Estado (convênios e programas estaduais, como o FUNPAES); impostos e recursos próprios (MDE); e outras (royalties, convênios da União, operações de crédito, alienação de bens).")),
    sec("m-medidas", "Medidas",
      h("dl", { class: "glossario" },
        h("dt", {}, "Alcance"), h("dd", {}, "Número de municípios com empenho positivo ao fornecedor no recorte."),
        h("dt", {}, "Parcela do mercado"), h("dd", {}, "Valor do fornecedor ÷ valor de todas as pessoas jurídicas (dos tipos escolhidos) no mesmo recorte — no ES ou no município."),
        h("dt", {}, "HHI"), h("dd", {}, "Índice de Herfindahl-Hirschman: soma dos quadrados das participações, em %, dos fornecedores de um município (0 a 10.000). Faixas do CADE: até 1.500 baixa; 1.500 a 2.500 moderada; acima, alta."),
        h("dt", {}, "Peso de Newman"), h("dd", {}, "Na rede de municípios, cada fornecedor com k municípios soma 1/(k−1) a cada par que atende (Newman, 2001). Fornecedor estadual quase não liga ninguém; fornecedor dividido só por dois liga muito."),
        h("dt", {}, "Comunidade (Louvain)"), h("dd", {}, "Grupos que maximizam a modularidade (Blondel et al., 2008), com resolução " + nf(META.resolucao, 1) + " e semente " + META.semente + " fixas (networkx). Outra semente ou resolução pode juntar ou separar grupos vizinhos — a divisão é um retrato, não uma fronteira."),
        h("dt", {}, "Modularidade"), h("dd", {}, "Quanto do peso das ligações fica dentro dos grupos além do que se esperaria ao acaso. Acima de 0,3, a divisão é nítida."),
        h("dt", {}, "Índice de Rand ajustado"), h("dd", {}, "Concordância entre duas divisões dos mesmos municípios, descontado o acaso: 1 idênticas, perto de 0 sem relação. Calculado só nos municípios com ligação."),
        h("dt", {}, "Informação mútua normalizada"), h("dd", {}, "Outra medida de concordância entre divisões (0 a 1), menos sensível ao número de grupos."))),
    sec("m-conferencias", "Conferências",
      h("p", {}, conf && conf.ok ? chipEstado("cumpre", "confere") : chipEstado("sinal", "a verificar"), " ",
        "A soma de tudo o que a rede leu — pessoas jurídicas, pessoas físicas, outros identificadores e pessoal — é comparada ao total de empenhos do TCE-ES que o painel de financiamento usa (tcees_empenhos_total.csv): "
        + (conf && conf.municipio_anos ? conf.municipio_anos + " município-anos, maior diferença " + brl(conf.maior_diferenca || 0) + "." : "conferência não disponível.")),
      Object.keys(porAno).length ? h("div", { class: "callout sinal" }, h("strong", {}, ESTADOS.sinal.simbolo + " Meses ausentes no arquivo do TCE-ES. "),
        Object.entries(porAno).map(([a, l]) => h("p", {}, a + ": " + l.length + " municípios — " + l.join("; ") + ".")),
        h("p", {}, "A soma desses anos fica curta para esses municípios; a rede mostra o que o arquivo traz.")) : null),
    sec("m-limitacoes", "Limitações",
      h("ul", { class: "lista limitacoes" },
        h("li", {}, "O dado é declaratório: é o que cada município enviou ao TCE-ES (CidadES). Credor com CNPJ digitado errado vira outro nó."),
        h("li", {}, "A raiz do CNPJ junta matriz e filiais, mas não junta empresas diferentes do mesmo grupo nem dos mesmos sócios — para isso seria preciso o quadro de sócios da Receita Federal (ver abaixo)."),
        h("li", {}, "O nome do credor chega do TCE-ES às vezes sem as letras acentuadas (\"COMRCIO\"); a página mostra a grafia de maior valor entre as que aparecem."),
        h("li", {}, "O mercado é classificado por regra sobre a natureza da despesa e o nome da ação. Ação com nome genérico (\"manutenção das atividades\") leva o empenho para o mercado da natureza, que pode não ser o do objeto real."),
        h("li", {}, "Empenhado não é pago. Cancelamentos aparecem como valor negativo no mês e reduzem a soma."),
        h("li", {}, "A disposição foi calculada para o período inteiro; mudar o exercício esconde nós, mas não os reposiciona."),
        h("li", {}, "A rede de municípios usa só o período inteiro, empresas e terceiro setor e todas as origens. É de propósito: as comunidades precisam de dado suficiente, e trocar o recorte a cada clique mudaria os grupos."),
        h("li", {}, "Pessoa física fica fora da rede. Em muitos municípios pequenos o transporte escolar é de motoristas autônomos: o mercado aparece menos concentrado do que é."))),
    sec("m-outras", "Outras redes que estes dados permitem",
      h("ul", { class: "lista" },
        h("li", {}, h("strong", {}, "Sócios em comum"), " — ligar os fornecedores pelo quadro de sócios e administradores (QSA) dos dados abertos do CNPJ da Receita Federal. Empresas diferentes com os mesmos sócios, vencendo nos mesmos municípios, é o padrão clássico de conluio a verificar."),
        h("li", {}, h("strong", {}, "Concorrentes na mesma licitação"), " — com a lista de participantes de cada certame, a rede empresa × licitação mostra quem sempre disputa junto e quem nunca se enfrenta (rodízio)."),
        h("li", {}, h("strong", {}, "Fluxo do FUNDEB"), " — quem contribui e quem recebe na redistribuição estadual do fundo: rede dirigida município → fundo → município, com o saldo de cada um."),
        h("li", {}, h("strong", {}, "Consórcios e convênios"), " — municípios ligados por consórcios públicos e pelos convênios com o Estado (FUNPAES, transporte)."),
        h("li", {}, h("strong", {}, "Escola × recurso"), " — escolas ligadas às unidades executoras e aos repasses (PDDE federal, repasse municipal), para achar escola que não recebe nada ou que recebe de muitas fontes."),
        h("li", {}, h("strong", {}, "Pares de comparação"), " — cada município ligado aos mais parecidos em porte, receita e perfil de gasto, para comparar resultado (IDEB, alfabetização) entre iguais."))),
    sec("m-reproduzir", "Como reproduzir",
      p("A partir da raiz do repositório, com o cache do pipeline já preenchido:"),
      h("pre", {}, h("code", {}, "python -m financiamento.etl.grafos         # dados/processado/grafos.json e grafos_*.csv\npython -m financiamento.build_grafos        # financiamento/redes_financiamento.html")),
      p("O ETL não consulta o TCE-ES: lê o recorte já guardado. Só o IBGE é baixado, uma vez, para dados/bruto/ibge/. A disposição e as comunidades usam semente fixa: a mesma execução dá a mesma figura.")));
}
