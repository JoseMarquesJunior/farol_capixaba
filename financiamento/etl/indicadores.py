"""Catálogo dos indicadores: o que cada número é, de onde sai e como é calculado.

Fonte única das descrições de proveniência. O dataset consolidado copia daqui a
`localizacao` e o `calculo` de cada registro; o painel mostra o mesmo texto no
"ver fonte"; e a validação usa `negativo` para saber onde valor negativo é
esperado (um saldo, uma diferença) e onde seria erro.

Placeholders em `localizacao`: {anexo_ie}, {anexo_ic}, {anexo_a02} (nomes de anexo
do exercício, descobertos nos dados) e {detalhe} (subfunção, fonte, programa…).
"""

from __future__ import annotations

from typing import Any

# Colunas e contas citadas literalmente, como vêm da API.
_IE = "DCA ({anexo_ie})"
_IC = "DCA ({anexo_ic})"
_A01 = "RREO-Anexo 01, coluna \"Até o Bimestre (c)\""
_MSC = "MSC orçamentária (MSCC, classe 6, dezembro, ending_balance)"
_SIOPE = "RREO Anexo 8 gerado pelo SIOPE (PDF), 6º bimestre"
_CGU = "Portal da Transparência (CGU), arquivos mensais de transferências, recorte UF=ES"
_TCE = "Dados abertos do TCE-ES (dados.es.gov.br)"
_ICA = ("Planilha oficial do INEP \"resultados_e_metas_municipios_2025_3.xlsx\" (Avaliação da Alfabetização, "
        "edição 2025), aba \"Divulgação Alfabet Municipio\", verificada por SHA-256")
_TCE_EMP = _TCE + " — \"Empenhos dos municípios\" (recorte da função 12)"

INDICADORES: dict[str, dict[str, Any]] = {
    # ---------------------------------------------------------- SICONFI — DCA
    "desp_educacao_empenhada": {
        "rotulo": "Despesa em Educação (empenhada)", "tema": "despesa", "fonte": "SICONFI", "unidade": "R$",
        "localizacao": _IE + ": conta \"12 - Educação\", coluna \"Despesas Empenhadas\"",
        "calculo": "valor da célula (exceto intra-orçamentárias)"},
    "desp_educacao_liquidada": {
        "rotulo": "Despesa em Educação (liquidada)", "tema": "despesa", "fonte": "SICONFI", "unidade": "R$",
        "localizacao": _IE + ": conta \"12 - Educação\", coluna \"Despesas Liquidadas\"", "calculo": "valor da célula"},
    "desp_educacao_paga": {
        "rotulo": "Despesa em Educação (paga)", "tema": "despesa", "fonte": "SICONFI", "unidade": "R$",
        "localizacao": _IE + ": conta \"12 - Educação\", coluna \"Despesas Pagas\"", "calculo": "valor da célula"},
    "desp_total_empenhada": {
        "rotulo": "Despesa total do ente (empenhada)", "tema": "despesa", "fonte": "SICONFI", "unidade": "R$",
        "localizacao": _IE + ": conta \"Despesas Exceto Intraorçamentárias\", coluna \"Despesas Empenhadas\"",
        "calculo": "valor da célula"},
    "populacao": {
        "rotulo": "População do exercício", "tema": "contexto", "fonte": "SICONFI", "unidade": "habitantes",
        "localizacao": _IE + ": campo \"populacao\" das linhas", "calculo": "valor único em todas as linhas do anexo"},
    "desp_educacao_per_capita": {
        "rotulo": "Despesa em Educação per capita", "tema": "despesa", "fonte": "calculado", "unidade": "R$/hab.",
        "localizacao": _IE, "calculo": "despesa em Educação empenhada ÷ população do exercício"},
    "desp_educacao_pct_total": {
        "rotulo": "Educação em % da despesa total", "tema": "despesa", "fonte": "calculado", "unidade": "%",
        "localizacao": _IE, "calculo": "função 12 empenhada ÷ despesa total empenhada × 100"},
    "subfuncao_empenhada": {
        "rotulo": "Despesa em Educação por subfunção (empenhada) — Nível 1", "tema": "aplicacao", "fonte": "SICONFI",
        "unidade": "R$", "localizacao": _IE + ": conta \"{detalhe}\", coluna \"Despesas Empenhadas\"",
        "calculo": "valor da célula; as subfunções somam exatamente a função 12"},
    "fundeb_receita": {
        "rotulo": "Receita do FUNDEB recebida (DCA)", "tema": "receita", "fonte": "SICONFI", "unidade": "R$",
        "localizacao": _IC + ": contas \"Transferências de Recursos do Fundo de Manutenção e Desenvolvimento da "
                              "Educação Básica…\" e \"…de Complementação da União ao Fundo…\", coluna \"Receitas Brutas Realizadas\"",
        "calculo": "fundo + complementação da União (contas casadas pelo nome, não pelo código)"},
    "fundeb_complementacao_uniao": {
        "rotulo": "…da qual complementação da União (DCA)", "tema": "receita", "fonte": "SICONFI", "unidade": "R$",
        "localizacao": _IC + ": conta \"Transferências de Recursos de Complementação da União ao Fundo…\"",
        "calculo": "valor da célula"},
    "fundeb_contribuicao": {
        "rotulo": "Contribuição ao FUNDEB", "tema": "receita", "fonte": "SICONFI", "unidade": "R$",
        "localizacao": _IC + ": conta \"ReceitasExcetoIntraOrcamentarias\", coluna \"Deduções - FUNDEB\"",
        "calculo": "valor da célula"},
    "fundeb_liquido": {
        "rotulo": "FUNDEB líquido (recebido − contribuição)", "tema": "receita", "fonte": "calculado", "unidade": "R$",
        "negativo": True, "localizacao": _IC, "calculo": "receita do FUNDEB − contribuição ao FUNDEB"},
    "fundeb_pct_desp_educacao": {
        "rotulo": "Receita do FUNDEB ÷ despesa em Educação", "tema": "receita", "fonte": "calculado", "unidade": "%",
        "localizacao": _IC + " e " + _IE, "calculo": "receita do FUNDEB ÷ função 12 empenhada × 100"},
    # ----------------------------------------------------------- SICONFI — RREO
    "rreo_b6_empenhada": {
        "rotulo": "Educação no RREO, 6º bimestre (empenhada)", "tema": "despesa", "fonte": "SICONFI", "unidade": "R$",
        "localizacao": "RREO ({anexo_a02}), 6º bimestre: bloco \"RREO2TotalDespesas\", conta \"Educação\", "
                       "coluna \"DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)\"", "calculo": "valor da célula"},
    "dif_rreo_dca_pct": {
        "rotulo": "RREO 6º bimestre × DCA", "tema": "conferencia", "fonte": "calculado", "unidade": "%", "negativo": True,
        "localizacao": "RREO ({anexo_a02}) e " + _IE, "calculo": "(RREO − DCA) ÷ DCA × 100"},
    "empenhada_acum": {
        "rotulo": "Educação empenhada até o bimestre", "tema": "despesa", "fonte": "SICONFI", "unidade": "R$",
        "localizacao": "RREO ({anexo_a02}), bimestre {detalhe}: conta \"Educação\", coluna \"DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)\"",
        "calculo": "valor da célula (acumulado no ano)"},
    "receita_a01": {
        "rotulo": "Receita realizada até o bimestre (Anexo 01)", "tema": "receita", "fonte": "SICONFI", "unidade": "R$",
        "localizacao": _A01 + ", cod_conta \"{detalhe}\"", "calculo": "valor da célula (acumulado no ano)"},
    # ------------------------------------------------------------ SICONFI — MSC
    "fundeb_msc": {
        "rotulo": "Receita do FUNDEB (MSC)", "tema": "receita", "fonte": "SICONFI", "unidade": "R$",
        "localizacao": _MSC + ": conta 621200000 (receita realizada), natureza_receita iniciada pelos prefixos "
                              "achados no DCA I-C para o fundo e a complementação ({detalhe})",
        "calculo": "soma das linhas; conferido contra o DCA I-C e o SIOPE"},
    "receita_fonte_msc": {
        "rotulo": "Receita registrada pelo município, por fonte (MSC)", "tema": "receita", "fonte": "SICONFI", "unidade": "R$",
        "localizacao": _MSC + ": conta 621200000 (receita realizada), fonte_recursos {detalhe}",
        "calculo": "soma das linhas da fonte (3 últimos dígitos de fonte_recursos), exercício corrente e anteriores"},
    "msc_educacao_empenhada": {
        "rotulo": "Despesa em Educação (MSC)", "tema": "conferencia", "fonte": "SICONFI", "unidade": "R$",
        "localizacao": _MSC + ": contas 622130100…622130700, funcao 12, exceto modalidade 91",
        "calculo": "soma das linhas; tem de bater com o DCA I-E"},
    "fluxo_fonte_subfuncao": {
        "rotulo": "Despesa em Educação por fonte de recursos e subfunção", "tema": "aplicacao", "fonte": "SICONFI",
        "unidade": "R$", "localizacao": _MSC + ": contas 622130100…622130700, funcao 12, {detalhe}, exceto modalidade 91",
        "calculo": "soma das linhas (empenhado do ano); fonte = 3 últimos dígitos de fonte_recursos"},
    "natureza_economica": {
        "rotulo": "Despesa em Educação por natureza econômica — Nível 2", "tema": "aplicacao", "fonte": "SICONFI",
        "unidade": "R$", "localizacao": _MSC + ": contas 622130100…622130700, funcao 12, natureza_despesa {detalhe}, "
                                               "exceto modalidade 91",
        "calculo": "soma das linhas; categoria pelo grupo (2º dígito) e pelo elemento (5º–6º) — ver msc.py"},
    # -------------------------------------------------------- SICONFI — entregas
    "entrega_atraso_dias": {
        "rotulo": "Atraso na entrega (dias)", "tema": "conformidade", "fonte": "SICONFI", "unidade": "dias",
        "localizacao": "extrato_entregas: {detalhe}; campo \"data_status\" (UTC, convertido a UTC−3) × prazo legal",
        "calculo": "data da entrega − prazo (LRF arts. 51, 52 e 55); vazio quando no prazo"},
    # ---------------------------------------------------------------- SIOPE
    "siope": {
        "rotulo": "Anexo 8 (MDE) — SIOPE", "tema": "conformidade", "fonte": "SIOPE", "unidade": "R$",
        "localizacao": _SIOPE + ": {detalhe}", "calculo": "valor impresso no demonstrativo (extraído do PDF)"},
    "mde_pct": {
        "rotulo": "% da receita de impostos aplicado em MDE (mín. 25%)", "tema": "conformidade", "fonte": "SIOPE",
        "unidade": "%", "localizacao": _SIOPE + ": {detalhe}, coluna \"% APLICADO\"",
        "calculo": "percentual apurado pelo SIOPE; conferido = 25 × aplicado ÷ exigido"},
    "fundeb70_pct": {
        "rotulo": "% do FUNDEB na remuneração dos profissionais (mín. 70%)", "tema": "conformidade", "fonte": "SIOPE",
        "unidade": "%", "localizacao": _SIOPE + ": {detalhe}, coluna \"% APLICADO\"",
        "calculo": "percentual apurado pelo SIOPE; conferido = 70 × considerado ÷ exigido"},
    "divergencia_funcao12_siope": {
        "rotulo": "Divergência: função 12 (SICONFI) × despesa com educação (SIOPE)", "tema": "conciliacao",
        "fonte": "calculado", "unidade": "%", "negativo": True,
        "localizacao": _IE + " (função 12, empenhada) e " + _SIOPE + " (\"TOTAL GERAL DAS DESPESAS COM EDUCAÇÃO\", empenhada)",
        "calculo": "(função 12 − total do SIOPE) ÷ função 12 × 100 — sinal a investigar, não erro do pipeline"},
    # ------------------------------------------------------------------ FNDE
    "repasse_fnde": {
        "rotulo": "Repasse federal do FNDE", "tema": "receita", "fonte": "FNDE", "unidade": "R$",
        "localizacao": _CGU + ": {detalhe}", "calculo": "soma de \"VALOR TRANSFERIDO\" nos meses do exercício"},
    "cnca_pdde": {
        "rotulo": "CNCA — PDDE pago às escolas do município", "tema": "programa", "fonte": "FNDE", "unidade": "R$",
        "localizacao": _CGU + ": ação 0515 (PDDE), \"CÓDIGO PLANO ORÇAMENTÁRIO\" {detalhe}, UEx do município",
        "calculo": "soma de \"VALOR TRANSFERIDO\" às unidades executoras das escolas do município no exercício"},
    "cnca_estado": {
        "rotulo": "CNCA — apoio pago ao Estado (SEDU)", "tema": "programa", "fonte": "FNDE", "unidade": "R$",
        "localizacao": _CGU + ": ação 0509, plano orçamentário 0014, favorecido {detalhe}",
        "calculo": "\"VALOR TRANSFERIDO\" do mês"},
    # ------------------------------------------------------------ INEP — ICA
    "ica_taxa": {
        "rotulo": "ICA — % de alunos alfabetizados ao fim do 2º ano (rede municipal)", "tema": "programa", "fonte": "INEP",
        "unidade": "%", "localizacao": _ICA + ": linha do município, coluna \"PC_ALUNO_ALFABETIZADO_<ano>\" ({detalhe})",
        "calculo": "valor da célula — percentual de alunos acima de 743 pontos na escala Saeb de Língua Portuguesa, "
                   "como publicado pelo INEP (nenhum recálculo)"},
    "ica_meta": {
        "rotulo": "ICA — meta pactuada para o município no ano", "tema": "programa", "fonte": "INEP", "unidade": "%",
        "localizacao": _ICA + ": linha do município, coluna \"META_FINAL_<ano>\" ({detalhe})",
        "calculo": "valor da célula (meta estabelecida pelo MEC/INEP para o município)"},
    "ica_participacao": {
        "rotulo": "ICA — % de participação dos alunos na avaliação", "tema": "programa", "fonte": "INEP", "unidade": "%",
        "localizacao": _ICA + ": linha do município, coluna \"PC_AVALIADOS_LP\" ({detalhe})",
        "calculo": "valor da célula"},
    # ---------------------------------------------------------------- TCE-ES
    "tcees_mde_pct": {
        "rotulo": "% em MDE apurado pelo TCE-ES", "tema": "conformidade", "fonte": "TCE-ES", "unidade": "%",
        "localizacao": _TCE + " — recurso \"Educação\": coluna \"AplicacaoPercentual\"",
        "calculo": "valor da célula (apuração do Tribunal sobre as remessas do CidadES)"},
    "tcees_mde_aplicado": {
        "rotulo": "Aplicação em MDE apurada pelo TCE-ES", "tema": "conformidade", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _TCE + " — recurso \"Educação\": coluna \"Aplicacao\"", "calculo": "valor da célula"},
    "div_mde_tcees_siope_pp": {
        "rotulo": "MDE: TCE-ES × SIOPE (pontos percentuais)", "tema": "conciliacao", "fonte": "calculado", "unidade": "p.p.",
        "negativo": True, "localizacao": _TCE + " (\"AplicacaoPercentual\") e " + _SIOPE + " (% aplicado em MDE)",
        "calculo": "% do TCE-ES − % do SIOPE; as duas apurações podem divergir por critério (restos a pagar, "
                   "cancelamentos, glosas do Tribunal)"},
    "tcees_emp_empenhada": {
        "rotulo": "Função 12 empenhada — soma dos empenhos do TCE-ES", "tema": "conferencia", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _TCE_EMP + ", CodigoFuncao 12, exceto CodigoModalidade 91",
        "calculo": "soma de \"Empenhada\" (movimento mensal, líquido de anulações); conferida contra o DCA I-E"},
    "remessa_tcees_atraso_dias": {
        "rotulo": "Atraso da prestação de contas mensal ao TCE-ES (dias)", "tema": "conformidade", "fonte": "TCE-ES",
        "unidade": "dias", "localizacao": _TCE + " — recurso \"Prestação de Contas Municipal\": UG × mês {detalhe}, "
                                             "colunas \"DataHomologacao\" e \"DataLimite\"",
        "calculo": "homologação − data-limite (a data-limite VEM na fonte); não homologada = dias desde a data-limite"},
    "obra_educacao": {
        "rotulo": "Contrato de obra da Educação (valor atual)", "tema": "aplicacao", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _TCE + " — \"Obras e serviços de engenharia\" (SetorBeneficiado Educação): {detalhe}, "
                              "coluna \"ValorAtualContratacao\" (ou \"ValorTotalInstrumento\")",
        "calculo": "valor da célula; exercício = ano de assinatura do contrato"},
    "obra_medido": {
        "rotulo": "Obra da Educação — valor medido", "tema": "aplicacao", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _TCE + " — \"Instrumentos contratuais com medições e alterações\": {detalhe}, coluna \"ValorTotalMedicao\"",
        "calculo": "soma das medições distintas (número × ano da medição)"},
    "empenho_credor": {
        "rotulo": "Maiores credores da Educação — Nível 3", "tema": "aplicacao", "fonte": "TCE-ES", "unidade": "R$",
        "negativo": True, "localizacao": _TCE_EMP + ", CodigoFuncao 12: credor {detalhe}",
        "calculo": "soma de \"Empenhada\" do credor no exercício (os 15 maiores; pessoas físicas agregadas numa linha). "
                   "Pode ficar negativa quando o ano só traz a anulação de um empenho"},
    "empenho_acao": {
        "rotulo": "Despesa da Educação por ação do município — Nível 3", "tema": "aplicacao", "fonte": "TCE-ES", "unidade": "R$",
        "negativo": True, "localizacao": _TCE_EMP + ", CodigoFuncao 12: {detalhe}",
        "calculo": "soma de \"Empenhada\" (a ação tem o nome dado pelo município)"},
    "empenho_fonte": {
        "rotulo": "Despesa da Educação por fonte e detalhamento — Nível 3", "tema": "aplicacao", "fonte": "TCE-ES",
        "unidade": "R$", "negativo": True, "localizacao": _TCE_EMP + ", CodigoFuncao 12: {detalhe}",
        "calculo": "soma de \"Empenhada\""},
    "repasse_conselho_escolar": {
        "rotulo": "Repasse do município a conselho escolar", "tema": "aplicacao", "fonte": "TCE-ES", "unidade": "R$",
        "negativo": True, "localizacao": _TCE_EMP + ", CodigoFuncao 12: credor {detalhe}",
        "calculo": "soma de \"Empenhada\" com credor identificado pelo nome (conselho de escola, caixa escolar, AEC…)"},
    "funpaes_empenho": {
        "rotulo": "Gasto identificado como FUNPAES (PAES/CNCA no ES)", "tema": "programa", "fonte": "TCE-ES", "unidade": "R$",
        "negativo": True, "localizacao": _TCE_EMP + ", CodigoFuncao 12, \"FUNPAES\" no programa, na ação ou no "
                                                    "detalhamento da fonte: {detalhe}",
        "calculo": "soma de \"Empenhada\"; só o que o município nomeou como FUNPAES"},
    "dotacao_atualizada": {
        "rotulo": "Dotação atualizada da ação (orçado)", "tema": "aplicacao", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _TCE + " — \"Despesas dos municípios\" (agregado), CodigoFuncao 12, exceto modalidade 91: {detalhe}, "
                              "coluna \"PrevisaoAtualizada\"",
        "calculo": "soma das linhas da ação no exercício"},
    "empenho_credor_acao": {
        "rotulo": "Credor × ação da Educação — Nível 3 (detalhamento)", "tema": "aplicacao", "fonte": "TCE-ES",
        "unidade": "R$", "negativo": True, "localizacao": _TCE_EMP + ", CodigoFuncao 12: {detalhe}",
        "calculo": "soma de \"Empenhada\" do credor DENTRO da ação; os 8 maiores credores de cada ação, com os "
                   "demais somados numa linha \"(demais)\" — nenhum valor some, a cauda fica agregada"},
    "matriculas_rede_municipal": {
        "rotulo": "Matrículas na rede municipal (denominador do R$ por matrícula)", "tema": "contexto", "fonte": "TCE-ES",
        "unidade": "matrículas", "localizacao": _TCE + " — recurso \"Educação\": coluna \"Alunos\"",
        "calculo": "valor da célula: as matrículas da rede municipal que o Tribunal usa na aplicação por aluno. "
                   "Conferido contra a soma do Censo Escolar (INEP) por município — ver conferencias_cruzadas"},
    "matriculas_etapa_censo": {
        "rotulo": "Matrículas da rede municipal por etapa (Censo Escolar)", "tema": "contexto", "fonte": "Censo",
        "unidade": "matrículas",
        "localizacao": "Censo Escolar (INEP) carregado no NEDUC: stg.matricula × stg.escola, escolas da rede municipal "
                       "(TP_DEPENDENCIA = 3) do município, censo do mesmo ano do exercício; coluna QT_MAT_FUND (ensino "
                       "fundamental) ou QT_MAT_MED (ensino médio) — {detalhe}",
        "calculo": "soma das matrículas da etapa nas escolas da rede municipal. A soma de todas as etapas (QT_MAT_BAS) é "
                   "a mesma base da coluna \"Alunos\" do TCE-ES. Zero é zero de verdade: a rede municipal quase não tem "
                   "ensino médio"},
    "subfuncao_por_matricula_etapa": {
        "rotulo": "Despesa da subfunção por matrícula da etapa", "tema": "despesa", "fonte": "calculado",
        "unidade": "R$/matrícula",
        "localizacao": _IE + " (subfunção) e Censo Escolar (matrículas da etapa na rede municipal): {detalhe}",
        "calculo": "despesa empenhada na subfunção ÷ matrículas da etapa correspondente na rede municipal no mesmo ano "
                   "(12.361 Ensino Fundamental ÷ fundamental; 12.362 Ensino Médio ÷ médio). As demais subfunções são "
                   "divididas pelo total de matrículas. Município sem matrícula na etapa fica sem dado — não é zero. O "
                   "numerador é a classificação do próprio município: gasto transversal lançado na subfunção infla o valor"},
    "desp_educacao_por_matricula": {
        "rotulo": "Despesa em Educação por matrícula", "tema": "despesa", "fonte": "calculado", "unidade": "R$/matrícula",
        "localizacao": _IE + " (despesa) e " + _TCE + " — recurso \"Educação\", coluna \"Alunos\" (matrículas)",
        "calculo": "despesa em Educação empenhada ÷ matrículas da rede municipal no exercício. Só municípios: o "
                   "recurso \"Educação\" do TCE-ES não cobre o Estado"},
    # ------------------------------------------- itens contratados (o que foi comprado)
    "item_contratado": {
        "rotulo": "Item contratado na Educação — Nível 3", "tema": "aplicacao", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _TCE + " — \"Itens - <ano>\" das contratações: {detalhe}, coluna \"ValorTotalItemContratado\"",
        "calculo": "valor da célula. Entra no recorte da Educação a linha cuja unidade gestora é de educação, ou cuja "
                   "contratação tem SetorBeneficiado \"Educação\", ou cujo instrumento é obra da Educação; o exercício "
                   "é o do instrumento contratual, não o do arquivo"},
    "item_medido": {
        "rotulo": "Item da Educação — valor medido", "tema": "aplicacao", "fonte": "TCE-ES", "unidade": "R$",
        "localizacao": _TCE + " — \"Itens - <ano>\": {detalhe}, coluna \"ValorTotalItemMedido\"",
        "calculo": "soma das medições distintas do item (número × ano da medição), somadas também entre os arquivos "
                   "anuais quando o contrato é plurianual"},
    # ------------------------------------------------------------ por escola
    "escola_recurso": {
        "rotulo": "Recurso associado a uma escola", "tema": "escola", "fonte": "combinado", "unidade": "R$", "negativo": True,
        "localizacao": "{detalhe}; escola identificada no Censo Escolar (INEP) pelo nome e município — ver escolas.py",
        "calculo": "PDDE: soma do transferido à unidade executora; repasse municipal: empenhado ao conselho escolar; "
                   "obra: valor atual do contrato. O vínculo escola ↔ recebedor é por nome (com nota), não por código"},
    # ------------------------------------------------------ receita por origem
    "origem_receita": {
        "rotulo": "Receita por origem", "tema": "receita", "fonte": "combinado", "unidade": "R$",
        "localizacao": "{detalhe}", "calculo": "ver a categoria; \"outras\" negativa = fontes que não fecham (é relatado)"},
}

#: Categorias da tabela "origem da receita" (Fase 1). Mutuamente exclusivas: somam
#: a receita total do Anexo 01 (exceto intra), com "outras" calculada por diferença.
ORIGENS = {
    "impostos_proprios": {"rotulo": "Impostos próprios (IPTU, ISS, ITBI, IRRF)", "fonte": "SICONFI",
                          "localizacao": _A01 + ", cod_conta \"Impostos\", 6º bimestre"},
    "fundeb": {"rotulo": "FUNDEB (fundo + complementação da União)", "fonte": "SICONFI",
               "localizacao": _MSC + ": receita realizada com natureza do FUNDEB (prefixos do DCA I-C)"},
    "federal_especifica": {"rotulo": "Transferências federais específicas da educação (FNDE: salário-educação, PNAE, PNATE, PDDE)",
                           "fonte": "FNDE",
                           "localizacao": _CGU + ": ações 0369, 00PI, 0969 e 0515 pagas ao próprio município"},
    "outras": {"rotulo": "Outras receitas (demais transferências, taxas, contribuições, patrimoniais, capital…)",
               "fonte": "calculado", "localizacao": "receita total (" + _A01 + ", \"ReceitasExcetoIntraOrcamentarias\") "
                                                     "− as três categorias acima"},
}

def negativo_permitido(indicador: str) -> bool:
    return bool(INDICADORES.get(indicador, {}).get("negativo"))
