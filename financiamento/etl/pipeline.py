"""Orquestrador do ETL: SICONFI + SIOPE + FNDE + TCE-ES + Censo (+ dados manuais) → dataset com proveniência.

Uso, a partir da raiz do repositório::

    python -m financiamento.etl.pipeline                        # tudo; detecta o último exercício
    python -m financiamento.etl.pipeline --anos 2021-2025
    python -m financiamento.etl.pipeline --fontes siope         # religa só o SIOPE; as demais leem o cache
    python -m financiamento.etl.pipeline --sem-empenhos         # TCE-ES sem os empenhos (~600 MB por ano)
    python -m financiamento.etl.pipeline --atualizar vazios     # refaz só o que veio vazio
    python -m financiamento.etl.pipeline --estrito              # sai com erro se uma conferência falhar

Cada fonte roda ISOLADA: se uma falha, o erro vai para `meta.fontes_status` e o
pipeline segue com as outras. Fonte fora de `--fontes` roda em modo `offline`
(só o cache): o que nunca foi coletado aparece como "não coletado", nada é
preenchido. Cada execução grava uma versão em `dados/processado/historico/`,
comparável com a anterior (`python -m financiamento.etl.comparar`).

Saídas em `financiamento/dados/processado/` — ver `etl/README.md`.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Any, Callable, Iterable

import pandas as pd

from . import anexos as mod_anexos
from . import cnca as mod_cnca
from . import composicao
from . import entes as mod_entes
from . import entregas as mod_entregas
from . import escolas as mod_escolas
from . import fnde as mod_fnde
from . import historico, ica as mod_ica, indicadores, manuais, msc as mod_msc, parsing, programas
from . import siconfi as mod_siconfi
from . import siope as mod_siope
from . import tcees as mod_tcees
from .anexos import AnexosExercicio
from .cliente import ClienteSiconfi, ErroSiconfi, NaoColetado, Resposta
from .config import (
    BASE_URL,
    BIMESTRES,
    LIMITE_COBERTURA_EXERCICIO,
    N_EXERCICIOS,
    PROCESSADO,
    TIPOS_RREO,
)
from .entes import Ente
from .proveniencia import Consulta, Registro, caminho_relativo

log = logging.getLogger(__name__)

MINIMO_MDE_PCT = 25.0  # art. 212 da Constituição: 25% da receita de impostos e transferências
TOLERANCIA_FECHAMENTO = 1.00  # R$: soma das funções vs total do anexo (arredondamento de centavos)
TOLERANCIA_RREO_DCA_PCT = 0.5  # % de diferença entre o 6º bimestre do RREO e a DCA que ainda é "confere"

SCHEMA = 2
FONTES_DISPONIVEIS = ("siconfi", "siope", "fnde", "tcees", "censo", "inep")

FONTES = [
    {"id": "siconfi", "rotulo": "SICONFI — API de Dados Abertos do Tesouro Nacional",
     "url": "https://apidatalake.tesouro.gov.br/docs/siconfi/",
     "usado_para": "Despesa por função e subfunção (DCA Anexo I-E, RREO Anexo 02), receita por categoria (RREO Anexo 01), "
                   "FUNDEB (DCA Anexo I-C e MSC), natureza econômica e fonte de recursos (MSC orçamentária), "
                   "entregas de RREO/RGF/DCA (/extrato_entregas), população do exercício"},
    {"id": "siope", "rotulo": "SIOPE (FNDE) — RREO Anexo 8 em PDF, no FTP público do FNDE",
     "url": "https://www.fnde.gov.br/siope/relatoriosMunicipais.jsp",
     "usado_para": "Índice legal de MDE (art. 212 CF, mín. 25%) e do FUNDEB na remuneração (mín. 70%), receita de "
                   "impostos, despesa com educação. Extraído de PDF (ftp://ftp.fnde.gov.br/web/siope/RREO/): fonte sem SLA"},
    {"id": "fnde", "rotulo": "FNDE — repasses publicados pela CGU (Portal da Transparência, download em lote)",
     "url": mod_fnde.URL_DOC,
     "usado_para": "Salário-educação, PNAE, PNATE e PDDE pagos a cada município (lado federal), por mês; PDDE por "
                   "escola (unidade executora) e plano orçamentário — é daí que sai o repasse do CNCA (PO 000C)"},
    {"id": "tcees", "rotulo": "TCE-ES — dados abertos do Tribunal de Contas (dados.es.gov.br)", "url": mod_tcees.PORTAL,
     "usado_para": "Índice de MDE apurado pelo Tribunal e matrículas da rede municipal, prazos das remessas mensais, "
                   "contratos de obra da Educação (com prédio, situação e medições), empenhos da função 12 (credor, ação, "
                   "fonte, conselhos escolares, FUNPAES), dotação por ação e os ITENS contratados na Educação (descrição, "
                   "unidade, quantidade, preço unitário e o que foi medido)"},
    {"id": "censo", "rotulo": "Censo Escolar (INEP) e avaliações — banco local do NEDUC",
     "url": "https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/censo-escolar",
     "usado_para": "Cadastro das escolas públicas (nome, rede, localização, matrículas, infraestrutura), IDEB e PAEBES — "
                   "a ponta onde o recurso chega; e as matrículas da rede municipal por etapa (ensino fundamental e "
                   "médio), denominador do R$ por matrícula das subfunções 12.361 e 12.362 no ranking"},
    {"id": "mec", "rotulo": "MEC — Painel de Monitoramento do CNCA",
     "url": "https://www.gov.br/mec/pt-br/centrais-de-conteudo/paineis-de-monitoramento-e-indicadores/painel-monitoramento-cnca",
     "usado_para": "Adesão municipal ao CNCA — registro manual"},
    {"id": "inep", "rotulo": "INEP — Avaliação da Alfabetização: Indicador Criança Alfabetizada (ICA) por município",
     "url": mod_ica.PAGINA,
     "usado_para": "Indicador oficial de meta do CNCA: % de alunos da rede municipal acima de 743 pontos na escala Saeb ao fim "
                   "do 2º ano (2023, 2024, 2025) e a meta pactuada de cada município até 2030 — planilha oficial verificada "
                   "por SHA-256; lógica de coleta reaproveitada de luizmaibashi/painel-alfabetizacao-cgu (MIT)"},
]

LIMITACOES = [
    "MDE (art. 212 CF): o SICONFI NÃO publica o RREO Anexo 08 por API (a lista de anexos pula 05, 08 e 12; reconfirmado em "
    "2026-09-22). O índice legal vem do SIOPE, cujos relatórios HTML exigem reCAPTCHA; o painel lê o mesmo demonstrativo no "
    "PDF que o SIOPE publica no FTP do FNDE. É fonte sem SLA (o layout mudou em 2023 e em 2024): cada percentual é conferido "
    "contra os valores da própria linha, e o que não fecha vira aviso. Registro manual só preenche lacuna do SIOPE.",
    "EC 119/2022 (art. 119 do ADCT): o descumprimento do art. 212 em 2020 e 2021 não gera responsabilização se o ente "
    "complementou a diferença até 2023. Por isso, em 2023, o 'valor exigido' do SIOPE inclui a compensação pendente de quem "
    "a tinha — e o painel mostra, além do % do ano, se o aplicado alcançou o exigido com a compensação.",
    "FUNDEB: a receita vem da MSC (natureza identificada pelos códigos do DCA Anexo I-C, casados pelo nome) e é conferida "
    "contra o DCA I-C e o SIOPE. Fundo + complementação da União (VAAF/VAAT/VAAR). A participação 'receita do FUNDEB ÷ despesa "
    "em Educação' é pelo lado da receita; a aplicação legal (70%) vem do SIOPE.",
    "Despesa da função Educação (função 12) é a EMPENHADA, exceto intra-orçamentárias — escopo comum ao DCA Anexo I-E, ao "
    "RREO Anexo 02 e à MSC (modalidade 91 excluída). Valores nominais, sem deflator.",
    "Fluxo fonte → subfunção: a fonte de recursos padronizada da STN aparece na MSC dos municípios do ES a partir de 2022; em "
    "2021 eles usavam códigos locais de 8 dígitos, que não se traduzem sem a tabela da época — o diagrama de 2021 fica "
    "indisponível (e diz por quê). A fonte 500 junta impostos próprios e transferências de impostos: a contabilidade não os "
    "separa, e dividir seria estimar.",
    "Repasses do FNDE: são o lado FEDERAL (o que a União pagou, por mês de pagamento), publicado pela CGU. O PDDE vai quase "
    "todo direto às escolas (unidades executoras) e não transita pelo orçamento municipal — é mostrado à parte. A CGU limita "
    "o volume de downloads: mês não baixado aparece como não coletado e entra numa próxima execução.",
    "Entregas (RREO, RGF, DCA): a API não traz prazo; ele é calculado pela LRF (arts. 51, 52 e 55). A data do extrato é a do "
    "status ATUAL: relatório retificado mostra a data da retificação, então atraso só é afirmado para status 'homologado'.",
    "Nível 3 (qual obra, qual fornecedor, qual escola): vem dos dados abertos do TCE-ES, que são DECLARATÓRIOS (remessas do "
    "CidadES). Empenhos: a soma da função 12 é conferida contra o DCA I-E; credor pessoa física aparece agregado. O painel "
    "mostra os 15 maiores credores de cada município-ano; a lista completa está no recorte em cache. O \"ver detalhamento\" "
    "de um credor ou de uma ação cruza os dois: mostra os 8 maiores credores de cada ação e soma os demais numa linha "
    "\"(demais)\" — nenhum valor some da soma, mas o nome do credor pequeno não aparece no painel.",
    "__ITENS__",
    "Escolas: nenhuma fonte financeira traz o código INEP. O vínculo recebedor → escola do Censo é feito pelo NOME (e "
    "município), com nota e método registrados em escolas_vinculos.csv; o que é ambíguo fica sem vínculo, não é chutado. "
    "Obras são ligadas ao prédio pelo bem vinculador (nome e coordenada). Em que cada escola gastou o PDDE não está em dado "
    "aberto (a escola presta contas ao FNDE).",
    "MDE em três apurações: SIOPE (declarado pelo município ao FNDE), TCE-ES (apurado pelo Tribunal) e registro manual. "
    "Divergem por critério (restos a pagar, cancelamentos, glosas); o painel mostra as três e destaca quando uma fica abaixo "
    "de 25% e a outra não.",
    "Obras: o retrato é o ATUAL (situação e medições na data da coleta), não o do exercício; o exercício de um contrato é o "
    "ano de assinatura.",
    "Nota fiscal: continua fora. Os itens dizem O QUE foi contratado e o que foi medido; quem emitiu a nota, com que número "
    "e em que data está no portal da transparência do município. Os portais são heterogêneos e sem padrão de dados — o "
    "painel registra o endereço conferido de cada um (e a documentação da API, onde existe) em vez de raspar 78 sites.",
    "Por matrícula: o denominador é a coluna \"Alunos\" do recurso \"Educação\" do TCE-ES — as matrículas da rede MUNICIPAL "
    "que o Tribunal usa na aplicação por aluno. Foi conferido contra a soma do Censo Escolar por município (ver as "
    "conferências cruzadas). Vale só para municípios: o recurso não cobre o Estado, e a rede estadual não entra no "
    "denominador de um município. Diferente do per capita, este denominador muda todo ano. No ranking por tipo de despesa, "
    "o Ensino Fundamental (12.361) e o Ensino Médio (12.362) são divididos pelas matrículas da PRÓPRIA etapa na rede "
    "municipal (Censo Escolar do mesmo ano, mesma base do total); as demais subfunções seguem divididas pelo total. O "
    "numerador é a classificação contábil do município: gasto transversal (transporte, merenda, administração) lançado "
    "numa subfunção infla o valor por matrícula dela.",
    "ICA (CNCA): é o indicador oficial de meta — % de alunos da rede municipal acima de 743 pontos na escala Saeb ao fim do "
    "2º ano —, publicado pelo INEP por município numa planilha verificada por SHA-256; não é o Saeb amostral. Município sem "
    "valor aparece como 'sem dado publicado', nunca como 0%. Metas são as pactuadas pelo MEC/INEP para cada município; a "
    "comparação é de cada município com a própria meta, não entre estados.",
    "Financiamento do CNCA é fragmentado e só parte está em dado aberto: o PDDE-CNCA (CGU, PO 000C) vai à ESCOLA, não ao "
    "município, e a escola presta contas ao FNDE; o CKAN do FNDE exige token (401 em 2026-09-23); as bolsas da Renalfa aos "
    "articuladores e a adesão formal não têm base consultável por município — são campos manuais, a preencher por ofício à "
    "SEDU-ES ou questionário (método do TCE-PB). O sinal de risco da página cruza critério declarado com valor recebido e é "
    "achado a investigar, não conclusão: os pesos da fórmula de repasse não são públicos e o painel não os infere.",
    "__POPULACAO__",
    "O Estado é mostrado à parte e não entra em soma nem ranking dos municípios: parte da despesa estadual em Educação "
    "é transferida a municípios, e somar os dois contaria o mesmo recurso duas vezes. As fontes do painel de auditoria "
    "(MSC, SIOPE, FNDE, entregas) cobrem só os municípios.",
    "Defasagem: a DCA de um exercício é entregue no ano seguinte; o RREO do 6º bimestre, até 30 dias após o fim do exercício. "
    "Município que não entregou aparece como 'sem dado', nunca como zero. O 6º bimestre do RREO pode diferir da DCA "
    "por retificações — a diferença é exibida.",
    "Municípios pequenos publicam o RREO no tipo 'RREO Simplificado' (mesmo nome de anexo); o ETL tenta os dois tipos.",
    "Módulo CNCA: o repasse é AUTOMÁTICO (PDDE, plano orçamentário 000C, escola a escola; e ação 0509/PO 0014 ao Estado). "
    "Adesão e indicador de alfabetização seguem MANUAIS, com fonte e data de verificação. O Saeb do 2º ano é amostral: "
    "município sem resultado tem 'sem amostra suficiente', não 0% de alfabetizados. Os pesos dos critérios de repasse não são "
    "públicos e não são recalculados. Onde o município gastou: só o que ele identificou como FUNPAES nos empenhos.",
]

DOCUMENTACAO = [
    {"fonte": "SICONFI", "rotulo": "API de Dados Abertos do SICONFI (Tesouro Nacional)", "url": "https://apidatalake.tesouro.gov.br/docs/siconfi/"},
    {"fonte": "SIOPE", "rotulo": "SIOPE — relatórios municipais (FNDE)", "url": mod_siope.URL_FORMULARIO},
    {"fonte": "SIOPE", "rotulo": "FTP do FNDE com os RREO gerados pelo SIOPE", "url": f"ftp://{mod_siope.FTP_HOST}{mod_siope.FTP_PASTA}/"},
    {"fonte": "FNDE", "rotulo": "Portal da Transparência (CGU) — download de dados de transferências", "url": mod_fnde.URL_DOC},
    {"fonte": "TCE-ES", "rotulo": "Dados abertos do TCE-ES (organização no portal dados.es.gov.br)", "url": mod_tcees.PORTAL},
    {"fonte": "TCE-ES", "rotulo": "API CKAN do portal (package_show)", "url": mod_tcees.CKAN + "/api/3/action/package_show?id=tcees-empenho"},
    {"fonte": "Censo", "rotulo": "Censo Escolar — microdados (INEP)",
     "url": "https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar"},
    {"fonte": "INEP", "rotulo": "Avaliação da Alfabetização — resultados e metas por município (edição 2025)", "url": mod_ica.PAGINA},
    {"fonte": "INEP", "rotulo": "Planilha oficial baixada (SHA-256 " + mod_ica.SHA256[:16] + "…)", "url": mod_ica.URL},
]


def texto_populacao(anual: pd.DataFrame) -> str:
    """Limitação sobre a população, com o que os dados realmente mostram."""
    m = anual[anual["esfera"] == "M"].pivot(index="cod_ibge", columns="ano", values="populacao")
    iguais = [(a - 1, a) for a in sorted(m.columns) if a - 1 in m.columns and m[a].notna().any() and (m[a] == m[a - 1]).all()]
    pares = " e entre ".join(f"{a} e {b}" for a, b in iguais)
    trecho = f"idêntica entre {pares} em todos os municípios; " if iguais else ""
    return ("População: é a que o SICONFI reporta em cada exercício (não a do IBGE/SIDRA). Nos dados atuais está " + trecho +
            "ela só muda a cada dois exercícios e, quando muda, pode mudar bastante. Parte da variação anual do per capita "
            "é mudança do denominador, não do gasto. A integração direta com o IBGE/SIDRA ficou como extensão.")


# ------------------------------------------------------------- exercício-alvo

def texto_itens(resumo: pd.DataFrame, anos: list[int]) -> str:
    """Limitação sobre os itens contratados, com a cobertura medida nesta execução."""
    base = ("Itens contratados (o que foi comprado): vêm do recurso \"Itens - <ano>\" das contratações do TCE-ES. "
            "Uma linha de item entra no recorte da Educação por três regras da própria fonte — unidade gestora de "
            "educação (secretaria ou fundo), contratação com SetorBeneficiado \"Educação\", ou instrumento de obra da "
            "Educação. O CNPJ da contratada NÃO é usado como regra: casar item com credor da função 12 pelo CNPJ "
            "traria quase metade dos itens de todo o Estado, porque quem vende à educação também vende ao resto da "
            "prefeitura. ")
    if resumo.empty:
        return base + "Nenhum item coletado nesta execução."
    por_ano = resumo.groupby("ano")["cod_ibge"].nunique()
    sem_arquivo = [a for a in anos if a not in por_ano.index]
    cobertura = "; ".join(f"{a}: {n} município(s)" for a, n in por_ano.items())
    fora = (f"Os arquivos de Itens começam em 2022, então {', '.join(str(a) for a in sem_arquivo)} só aparece(m) por "
            "contrato ainda vigente declarado depois. " if sem_arquivo else "")
    return (base + "A cobertura é parcial e desigual, e é isto que ela é: " + cobertura + ". " + fora +
            "Município que compra tudo pela unidade gestora da prefeitura, sem marcar o setor beneficiado, aparece só "
            "com os itens das obras — ausência aqui não é ausência de compra.")


def parse_anos(texto: str) -> list[int]:
    """`2021-2025` ou `2022,2024` -> lista ordenada de anos."""
    anos: set[int] = set()
    for parte in texto.split(","):
        if "-" in parte:
            a, b = (int(x) for x in parte.split("-"))
            anos.update(range(a, b + 1))
        else:
            anos.add(int(parte))
    return sorted(anos)


def detectar_ultimo_exercicio(
    cliente: ClienteSiconfi, entes: list[Ente], referencias: list[Ente], hoje: date
) -> int:
    """Exercício mais recente com DCA já entregue por boa parte dos entes.

    Amostra um a cada oito municípios (as consultas ficam no cache e são
    reaproveitadas na coleta). Um exercício é "publicado" com cobertura >=
    `LIMITE_COBERTURA_EXERCICIO` — nem todo município publica em dia, então
    exigir 100% recusaria exercícios utilizáveis.
    """
    municipios = [e for e in entes if e.esfera == "M"]
    amostra = municipios[::8]
    for ano in range(hoje.year - 1, hoje.year - 8, -1):
        try:
            anexos = mod_anexos.descobrir(cliente, ano, referencias)
        except (parsing.ErroParsing, NaoColetado):
            log.info("exercício %s: sem anexos publicados na referência (ou fora do cache) — ignorado", ano)
            continue

        def publicou(e: Ente) -> bool:
            try:
                return bool(cliente.consultar("dca", an_exercicio=ano, id_ente=e.cod_ibge, no_anexo=anexos.dca_despesa_funcao).itens)
            except NaoColetado:
                return False

        com_dado = sum(publicou(e) for e in amostra)
        cobertura = com_dado / len(amostra)
        log.info("exercício %s: DCA em %d/%d da amostra (%.0f%%)", ano, com_dado, len(amostra), 100 * cobertura)
        if cobertura >= LIMITE_COBERTURA_EXERCICIO:
            return ano
    raise RuntimeError("nenhum exercício recente com DCA publicada")


# ------------------------------------------------------------------- coleta

def _pct(a: float | None, b: float | None) -> float | None:
    return None if a is None or not b else round(100.0 * a / b, 4)


def _consulta(cliente: ClienteSiconfi, endpoint: str, params: dict[str, Any], r: Resposta, descricao: str) -> Consulta:
    return Consulta(fonte="SICONFI", recurso=endpoint, descricao=descricao, url=cliente.url_completa(endpoint, params),
                    obtido_em=r.obtido_em, arquivo=caminho_relativo(r.arquivo))


def coletar_anual(
    cliente: ClienteSiconfi, ente: Ente, ano: int, anexos: AnexosExercicio
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str], list[Consulta], dict[str, list[str]]]:
    """Uma linha ente × exercício, o detalhe por subfunção, as consultas e as contas do FUNDEB."""
    linha: dict[str, Any] = {"cod_ibge": ente.cod_ibge, "ente": ente.nome, "esfera": ente.esfera, "ano": ano}
    p_ie = {"an_exercicio": ano, "id_ente": ente.cod_ibge, "no_anexo": anexos.dca_despesa_funcao}
    p_ic = {"an_exercicio": ano, "id_ente": ente.cod_ibge, "no_anexo": anexos.dca_receita}
    try:
        ie = cliente.consultar("dca", **p_ie)
        ic = cliente.consultar("dca", **p_ic)
    except NaoColetado:
        return {**linha, "status_dca": "nao_coletado", "status_fundeb": "nao_coletado"}, [], [], [], {}
    except ErroSiconfi as exc:
        log.error("%s %s: %s", ente.nome, ano, exc)
        return {**linha, "status_dca": "falha_consulta", "status_fundeb": "falha_consulta"}, [], [], [], {}

    c_ie = _consulta(cliente, "dca", p_ie, ie, f"DCA ({anexos.dca_despesa_funcao}), exercício {ano}")
    c_ic = _consulta(cliente, "dca", p_ic, ic, f"DCA ({anexos.dca_receita}), exercício {ano}")
    linha["q_dca_ie"], linha["q_dca_ic"] = c_ie.id, c_ic.id
    obtidos = [ie.obtido_em, ic.obtido_em]
    edu = parsing.educacao_dca(ie.itens) if ie.itens else None
    linha["status_dca"] = "ok" if edu else ("sem_dado_publicado" if not ie.itens else "funcao_ausente")
    linha["populacao"] = parsing.populacao(ie.itens or ic.itens)
    subfuncoes: list[dict[str, Any]] = []
    if edu:
        soma, total = parsing.soma_funcoes_dca(ie.itens)
        difs = [abs(soma.get(k, 0.0) - v) for k, v in total.items() if k in ("empenhada", "liquidada", "paga")]
        linha["fechamento_dca_ok"] = bool(difs) and max(difs) <= TOLERANCIA_FECHAMENTO
        linha["desp_educacao_empenhada"] = edu.get("empenhada")
        linha["desp_educacao_liquidada"] = edu.get("liquidada")
        linha["desp_educacao_paga"] = edu.get("paga")
        linha["desp_total_empenhada"] = edu.get("total_empenhada")

        subfuncoes = [{"cod_ibge": ente.cod_ibge, "ano": ano, "q": c_ie.id, **s} for s in parsing.subfuncoes_dca(ie.itens)]
        somado = sum(s.get("empenhada", 0.0) for s in subfuncoes)
        linha["n_subfuncoes"] = len(subfuncoes)
        linha["subfuncoes_fecham"] = abs(somado - (edu.get("empenhada") or 0.0)) <= TOLERANCIA_FECHAMENTO

    fundeb = parsing.fundeb_dca(ic.itens) if ic.itens else None
    linha["status_fundeb"] = "ok" if fundeb else ("sem_dado_publicado" if not ic.itens else "sem_linha_fundeb")
    if fundeb:
        linha["fundeb_receita"] = fundeb["receita"]
        linha["fundeb_complementacao_uniao"] = fundeb.get("complementacao_uniao")
        linha["fundeb_contribuicao"] = fundeb.get("contribuicao")
    contas = parsing.contas_fundeb_dca(ic.itens) if ic.itens else {}
    return linha, subfuncoes, obtidos, [c_ie, c_ic], contas


def coletar_bimestral(
    cliente: ClienteSiconfi, ente: Ente, ano: int, anexos: AnexosExercicio
) -> tuple[list[dict[str, Any]], list[int], list[str], list[Consulta]]:
    """Educação acumulada por bimestre no RREO Anexo 02.

    Para cada bimestre tenta primeiro o tipo que funcionou no anterior e depois
    o outro (`RREO` / `RREO Simplificado`). Devolve (linhas, bimestres com falha
    de consulta, instantes de coleta, consultas que trouxeram dado).
    """
    linhas: list[dict[str, Any]] = []
    falhas: list[int] = []
    obtidos: list[str] = []
    consultas: list[Consulta] = []
    preferido: str | None = None
    for bim in BIMESTRES:
        ordem = ([preferido] if preferido else []) + [t for t in TIPOS_RREO if t != preferido]
        for tipo in ordem:
            params = {"an_exercicio": ano, "nr_periodo": bim, "co_tipo_demonstrativo": tipo,
                      "no_anexo": anexos.rreo_despesa_funcao, "co_esfera": ente.esfera, "id_ente": ente.cod_ibge}
            try:
                r = cliente.consultar("rreo", **params)
            except NaoColetado:
                break
            except ErroSiconfi as exc:
                log.error("%s %s bim %s (%s): %s", ente.nome, ano, bim, tipo, exc)
                falhas.append(bim)
                break
            obtidos.append(r.obtido_em)
            if valores := (parsing.educacao_rreo(r.itens) if r.itens else None):
                c = _consulta(cliente, "rreo", params, r, f"{anexos.rreo_despesa_funcao} ({tipo}), {bim}º bimestre de {ano}")
                consultas.append(c)
                linhas.append({"cod_ibge": ente.cod_ibge, "ano": ano, "bimestre": bim, "tipo_rreo": tipo, "q": c.id, **valores})
                preferido = tipo
                break
    return linhas, falhas, obtidos, consultas


def _executar(funcao, tarefas: list[tuple], trabalhadores: int, rotulo: str) -> list:
    """Roda `funcao(*t)` para cada tarefa em paralelo, preservando a ordem, com log de progresso."""
    resultados = []
    with ThreadPoolExecutor(max_workers=trabalhadores) as pool:
        futuros = [pool.submit(funcao, *t) for t in tarefas]
        for i, f in enumerate(futuros, 1):
            resultados.append(f.result())
            if i % 100 == 0 or i == len(futuros):
                log.info("%s: %d/%d", rotulo, i, len(futuros))
    return resultados


def _isolada(nome: str, funcao: Callable[..., Any], *args: Any, **kw: Any) -> tuple[Any, str | None]:
    """Roda uma fonte inteira; exceção vira erro registrado, não queda do pipeline."""
    try:
        return funcao(*args, **kw), None
    except Exception as exc:  # noqa: BLE001 — é exatamente o isolamento pedido: uma fonte não derruba as demais
        log.exception("fonte %s falhou; o pipeline segue sem ela", nome)
        return None, f"{type(exc).__name__}: {exc}"


# ------------------------------------------------------------- composição

def _juntar_mde(anual: pd.DataFrame, mde: list[dict[str, Any]]) -> pd.DataFrame:
    """Anexa o percentual de MDE registrado manualmente (só registros verificados)."""
    reg = pd.DataFrame([r for r in mde if r["verificado"] and r["valor"] is not None],
                       columns=["cod_ibge", "ano", "valor", "fonte", "verificado_em"])
    reg = reg.astype({"cod_ibge": "int64", "ano": "int64"})  # vazio nasce `object`; o merge exige o mesmo tipo
    reg = reg.rename(columns={"valor": "mde_aplicado_pct", "fonte": "mde_fonte", "verificado_em": "mde_verificado_em"})
    if reg.duplicated(["cod_ibge", "ano"]).any():
        raise manuais.ErroManuais("mde_aplicado_pct tem mais de um registro para o mesmo município e ano")
    anual = anual.merge(reg, on=["cod_ibge", "ano"], how="left")
    anual["mde_situacao"] = anual["mde_aplicado_pct"].map(lambda v: "sem_dado" if pd.isna(v) else "informado_manual")
    # `object` para aceitar True/False/None sem transformar "sem dado" em False.
    anual["mde_abaixo_minimo"] = anual["mde_aplicado_pct"].map(
        lambda v: None if pd.isna(v) else bool(v < MINIMO_MDE_PCT)
    ).astype(object)
    return anual


def montar_anual(linhas: list[dict[str, Any]], bimestral: pd.DataFrame, mde: list[dict[str, Any]]) -> pd.DataFrame:
    anual = pd.DataFrame(linhas)
    for coluna in ("populacao", "desp_educacao_empenhada", "desp_educacao_liquidada", "desp_educacao_paga",
                   "desp_total_empenhada", "fundeb_receita", "fundeb_complementacao_uniao", "fundeb_contribuicao",
                   "fechamento_dca_ok", "n_subfuncoes", "subfuncoes_fecham", "q_dca_ie", "q_dca_ic"):
        if coluna not in anual:
            anual[coluna] = pd.NA
    anual["populacao"] = anual["populacao"].astype("Int64")
    for c in ("desp_educacao_empenhada", "desp_educacao_liquidada", "desp_educacao_paga", "desp_total_empenhada",
              "fundeb_receita", "fundeb_complementacao_uniao", "fundeb_contribuicao"):
        anual[c] = pd.to_numeric(anual[c], errors="coerce")

    # Indicadores. Divisão com NaN/0 no denominador vira NaN, nunca zero.
    pop = anual["populacao"].astype("float").where(lambda s: s > 0)
    anual["desp_educacao_per_capita"] = (anual["desp_educacao_empenhada"] / pop).round(2)
    anual["desp_educacao_pct_total"] = (
        100 * anual["desp_educacao_empenhada"] / anual["desp_total_empenhada"].where(lambda s: s > 0)
    ).round(4)
    anual["fundeb_liquido"] = anual["fundeb_receita"] - anual["fundeb_contribuicao"]
    anual["fundeb_pct_desp_educacao"] = (
        100 * anual["fundeb_receita"] / anual["desp_educacao_empenhada"].where(lambda s: s > 0)
    ).round(4)

    # Conferência cruzada: 6º bimestre do RREO contra o fechamento da DCA.
    bim = bimestral if "q" in bimestral.columns else bimestral.assign(q=None)
    b6 = bim[bim["bimestre"] == 6][["cod_ibge", "ano", "empenhada_acum", "tipo_rreo", "q"]].rename(
        columns={"empenhada_acum": "rreo_b6_empenhada", "tipo_rreo": "tipo_rreo_b6", "q": "q_rreo_b6"})
    anual = anual.merge(b6, on=["cod_ibge", "ano"], how="left")
    anual["dif_rreo_dca_pct"] = (
        100 * (anual["rreo_b6_empenhada"] - anual["desp_educacao_empenhada"]) / anual["desp_educacao_empenhada"].where(lambda s: s > 0)
    ).round(4)

    n_bim = bimestral.groupby(["cod_ibge", "ano"]).size().rename("n_bimestres_rreo").reset_index()
    anual = anual.merge(n_bim, on=["cod_ibge", "ano"], how="left")
    anual["n_bimestres_rreo"] = anual["n_bimestres_rreo"].fillna(0).astype(int)

    anual = _juntar_mde(anual, mde)
    ordem = ["cod_ibge", "ente", "esfera", "ano", "populacao", "status_dca", "status_fundeb",
             "desp_educacao_empenhada", "desp_educacao_liquidada", "desp_educacao_paga", "desp_total_empenhada",
             "desp_educacao_per_capita", "desp_educacao_pct_total",
             "fundeb_receita", "fundeb_complementacao_uniao", "fundeb_contribuicao", "fundeb_liquido",
             "fundeb_pct_desp_educacao",
             "mde_aplicado_pct", "mde_situacao", "mde_abaixo_minimo", "mde_fonte", "mde_verificado_em",
             "rreo_b6_empenhada", "dif_rreo_dca_pct", "tipo_rreo_b6", "n_bimestres_rreo", "fechamento_dca_ok",
             "n_subfuncoes", "subfuncoes_fecham", "q_dca_ie", "q_dca_ic", "q_rreo_b6"]
    return anual[ordem].sort_values(["esfera", "cod_ibge", "ano"], ascending=[False, True, True]).reset_index(drop=True)


def _ordenar_subfuncoes(subfuncoes: pd.DataFrame, anual: pd.DataFrame) -> pd.DataFrame:
    """Ordena o detalhe por ente, ano e valor, e acrescenta a participação na Educação."""
    if subfuncoes.empty:
        return subfuncoes
    base = anual[["cod_ibge", "ano", "ente", "esfera", "desp_educacao_empenhada"]]
    s = subfuncoes.merge(base, on=["cod_ibge", "ano"], how="left")
    s["pct_educacao"] = (100 * s["empenhada"] / s["desp_educacao_empenhada"].where(lambda x: x > 0)).round(4)
    s = s.drop(columns=["desp_educacao_empenhada"])
    if "q" not in s:
        s["q"] = None
    colunas = ["cod_ibge", "ente", "esfera", "ano", "codigo", "nome", "empenhada", "liquidada", "paga", "pct_educacao", "q"]
    return s[colunas].sort_values(["esfera", "cod_ibge", "ano", "empenhada"],
                                  ascending=[False, True, True, False]).reset_index(drop=True)


def catalogo_subfuncoes(subfuncoes: pd.DataFrame) -> list[dict[str, Any]]:
    """Subfunções distintas, da maior para a menor despesa somada nos municípios.

    Dá ao painel uma ordem estável: a mesma subfunção ocupa a mesma posição em
    qualquer município e exercício.
    """
    if subfuncoes.empty:
        return []
    mun = subfuncoes[subfuncoes["esfera"] == "M"]
    agregado = (mun.groupby(["codigo", "nome"], as_index=False)
                .agg(total_empenhada=("empenhada", "sum"), ente_anos=("empenhada", "size")))
    return agregado.sort_values("total_empenhada", ascending=False).to_dict("records")


def verificacoes(anual: pd.DataFrame, falhas_rreo: list[dict[str, Any]]) -> dict[str, Any]:
    """Conferências automáticas de consistência, exibidas no dashboard e no README."""
    com_dca = anual[anual["status_dca"] == "ok"]
    fech = com_dca[com_dca["fechamento_dca_ok"].astype("boolean").fillna(False).eq(False)]
    comparaveis = com_dca[com_dca["dif_rreo_dca_pct"].notna()]
    fora = comparaveis[comparaveis["dif_rreo_dca_pct"].abs() > TOLERANCIA_RREO_DCA_PCT]
    sub_falhas = com_dca[com_dca["subfuncoes_fecham"].astype("boolean").fillna(False).eq(False)]
    return {
        "subfuncoes_fecham": {
            "descricao": "Soma das subfunções da Educação = despesa da função 12 (tolerância R$ 1,00)",
            "conferidos": int(len(com_dca)),
            "falhas": sub_falhas[["cod_ibge", "ente", "ano"]].to_dict("records"),
        },
        "fechamento_dca": {
            "descricao": "Soma das funções do DCA Anexo I-E confere com o total do anexo (tolerância R$ 1,00)",
            "conferidos": int(len(com_dca)),
            "falhas": fech[["cod_ibge", "ente", "ano"]].to_dict("records"),
        },
        "rreo_vs_dca": {
            "descricao": f"Despesa empenhada em Educação: RREO 6º bimestre vs DCA (tolerância {TOLERANCIA_RREO_DCA_PCT}%)",
            "comparaveis": int(len(comparaveis)),
            "divergentes": int(len(fora)),
            "maiores": fora.reindex(fora["dif_rreo_dca_pct"].abs().sort_values(ascending=False).index)
                           .head(10)[["cod_ibge", "ente", "ano", "dif_rreo_dca_pct"]].to_dict("records"),
        },
        "falhas_consulta_rreo": falhas_rreo,
        "codigos_ibge_7_digitos": bool(anual[anual["esfera"] == "M"]["cod_ibge"].astype(str).str.fullmatch(r"\d{7}").all()),
    }


def cobertura(anual: pd.DataFrame) -> pd.DataFrame:
    colunas = ["cod_ibge", "ente", "esfera", "ano", "status_dca", "status_fundeb", "n_bimestres_rreo", "tipo_rreo_b6",
               "mde_situacao", "status_msc", "fontes_msc", "status_siope"]
    return anual.reindex(columns=colunas).copy()


def _json_limpo(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame -> lista de dicts JSON-seguros (NaN/NA viram null)."""
    return json.loads(df.to_json(orient="records", force_ascii=False))


def _compacta(df: pd.DataFrame, colunas: list[str], dicionario: Iterable[str] = ()) -> dict[str, Any]:
    """Tabela grande em forma colunar (nomes uma vez, linhas como listas) — o painel expande.

    Colunas em `dicionario` (texto muito repetido: situação, categoria, descrição da
    consulta…) viram índices numa lista de valores distintos. Só o JSON embutido é
    compactado; os CSVs de `dados/processado/` têm tudo por extenso.
    """
    d = df.reindex(columns=colunas).copy()
    dic: dict[str, list[Any]] = {}
    for c in dicionario:
        valores = list(pd.unique(d[c].dropna()))
        dic[c] = [v.item() if hasattr(v, "item") else v for v in valores]
        indice = {v: i for i, v in enumerate(valores)}
        d[c] = d[c].map(lambda v: None if pd.isna(v) else indice[v]).astype("Int64")
    return {"colunas": colunas, "dicionario": dic, "linhas": json.loads(d.to_json(orient="values", force_ascii=False))}


def _consultas_partidas(registro: Registro) -> pd.DataFrame:
    """Consultas com a URL em (base até a última "/" antes da query, resto)."""
    df = pd.DataFrame(registro.como_linhas(), columns=["id", "fonte", "recurso", "descricao", "url", "obtido_em",
                                                       "arquivo", "metodo", "sha256"])
    partes = df["url"].str.extract(r"^([^?]*/)(.*)$")
    return df.assign(url_base=partes[0], url_resto=partes[1])


#: Itens embutidos no painel por município-ano (os maiores por valor contratado). A
#: tabela inteira, sem corte e com a descrição por extenso, está em
#: dados/processado/tcees_itens.csv — o painel diz isso e oferece o CSV.
ITENS_POR_MUNICIPIO_ANO = 25
#: A descrição de item do TCE-ES chega a 250 caracteres (o município repete o nome, a
#: especificação e a marca). No JSON embutido ela é cortada; o CSV mantém o texto inteiro.
DESCRICAO_ITEM_MAX = 150
#: O objeto da contratação tem 206 caracteres em média; no painel é só um subtítulo.
OBJETO_CONTRATACAO_MAX = 120


def contratacoes_do_painel(contratacoes: pd.DataFrame) -> pd.DataFrame:
    """Contratações com o objeto encurtado — o painel só o usa como subtítulo do item."""
    if contratacoes.empty:
        return contratacoes
    d = contratacoes.copy()
    d["objeto"] = _encurtar(d["objeto"], OBJETO_CONTRATACAO_MAX)
    return d


def _encurtar(coluna: pd.Series, limite: int) -> pd.Series:
    texto = coluna.astype("string")
    cortado = texto.str.slice(0, limite)
    return cortado.where(texto.str.len().le(limite), cortado + "…")


def itens_do_painel(itens: pd.DataFrame) -> pd.DataFrame:
    """Os maiores itens de cada município-ano, com a descrição encurtada."""
    if itens.empty:
        return itens
    d = itens.sort_values(["cod_ibge", "ano", "valor_total"], ascending=[True, True, False])
    d = d.groupby(["cod_ibge", "ano"], as_index=False, group_keys=False).head(ITENS_POR_MUNICIPIO_ANO).copy()
    d["descricao"] = _encurtar(d["descricao"], DESCRICAO_ITEM_MAX)
    return d


COLUNAS_OBRAS = ["cod_ibge", "chave", "contratacao", "ug", "objeto", "contratado", "cnpj_contratado", "valor_inicial",
                 "valor_atual", "valor", "situacao", "tipo_intervencao", "assinatura", "fim_vigencia", "url_contrato",
                 "url_edital", "bens", "medicoes", "valor_medido", "valor_pago_medicoes", "ultima_medicao", "aditivos",
                 "pct_medido", "q"]


def _dia(df: pd.DataFrame, coluna: str) -> pd.Series | None:
    """Data/hora → "AAAA-MM-DD" (texto), para o JSON do painel."""
    if coluna not in df:
        return None
    return pd.to_datetime(df[coluna], errors="coerce").dt.strftime("%Y-%m-%d")


def _vazios() -> dict[str, Any]:
    """Resultados vazios de cada fonte, para quando ela falha inteira."""
    return {
        "siconfi": mod_siconfi.ResultadoSiconfi(
            pd.DataFrame(columns=mod_siconfi.COLUNAS_RECEITA), pd.DataFrame(columns=mod_siconfi.COLUNAS_MSC),
            pd.DataFrame(columns=mod_siconfi.COLUNAS_FLUXO), pd.DataFrame(columns=mod_siconfi.COLUNAS_NATUREZA),
            pd.DataFrame(columns=["cod_ibge", "ano", "poder", "relatorio", "periodo", "periodicidade", "prazo", "situacao",
                                  "dias_atraso", "data_local", "status", "q"]), Registro()),
        "siope": mod_siope.ResultadoSiope(pd.DataFrame(columns=["cod_ibge", "ano", *mod_siope.CAMPOS, "status_siope",
                                                                "pdf_gerado_em", "pdf_publicado_em", "q", "itens_usados"]),
                                          Registro(), [], {}),
        "fnde": mod_fnde.ResultadoFnde(pd.DataFrame(columns=["cod_ibge", "ano", "programa", "destino", "valor", "meses", "q"]),
                                       Registro(), [], {}, pd.DataFrame(columns=mod_fnde.COLUNAS_ESCOLA),
                                       pd.DataFrame(columns=mod_fnde.COLUNAS_CNCA_ESTADO)),
        "tcees": mod_tcees.ResultadoTcees(pd.DataFrame(), pd.DataFrame(), mod_tcees.resumo_pcm(pd.DataFrame()), pd.DataFrame(),
                                          {}, pd.DataFrame(), Registro(), [], {}),
        "censo": mod_escolas.ResultadoEscolas(pd.DataFrame(columns=mod_escolas.COLUNAS_CADASTRO), pd.DataFrame(),
                                              pd.DataFrame(columns=mod_escolas.COLUNAS_DINHEIRO), Registro(), [], {}),
        "inep": mod_ica.ResultadoIca(pd.DataFrame(columns=mod_ica.COLUNAS_RESULTADO),
                                     pd.DataFrame(columns=mod_ica.COLUNAS_META), Registro(), [], {}),
    }


# --------------------------------------------------------------------- main

def executar(
    anos: list[int] | None = None,
    *,
    atualizar: str = "nao",
    com_rreo: bool = True,
    trabalhadores: int = 6,
    hoje: date | None = None,
    fontes: Iterable[str] = FONTES_DISPONIVEIS,
    com_empenhos: bool = True,
    com_medicoes: bool = True,
    com_itens: bool = True,
) -> dict[str, Any]:
    """Roda o ETL completo e grava as saídas. Devolve o dataset (também gravado em JSON)."""
    hoje = hoje or date.today()
    fontes = tuple(fontes)
    modo = {f: (atualizar if f in fontes else "offline") for f in FONTES_DISPONIVEIS}
    cliente = ClienteSiconfi(atualizar=modo["siconfi"], intervalo_minimo=0.15)
    lista = mod_entes.listar_entes_es(cliente)
    lista_municipios = [e for e in lista if e.esfera == "M"]
    municipios = {e.cod_ibge for e in lista_municipios}
    referencias = sorted(lista_municipios, key=lambda e: -(e.populacao_atual or 0))[:5]

    catalogo = programas.carregar()
    dados_manuais = manuais.carregar(catalogo, municipios)

    if anos is None:
        ultimo = detectar_ultimo_exercicio(cliente, lista, referencias, hoje)
        anos = list(range(ultimo - N_EXERCICIOS + 1, ultimo + 1))
    log.info("exercícios: %s · fontes com rede: %s", anos, [f for f in fontes] or "nenhuma (tudo do cache)")
    anexos_por_ano = {a: mod_anexos.descobrir(cliente, a, referencias) for a in anos}
    registro = Registro()

    # 1) SICONFI — financiamento geral (Nível 1: função e subfunção), como antes, agora com proveniência.
    tarefas = [(cliente, e, a, anexos_por_ano[a]) for a in anos for e in lista]
    resultados = _executar(coletar_anual, tarefas, trabalhadores, "DCA")
    linhas = [r[0] for r in resultados]
    subfuncoes = pd.DataFrame(
        [s for r in resultados for s in r[1]],
        columns=["cod_ibge", "ano", "q", "codigo", "nome", "empenhada", "liquidada", "paga"],
    )
    obtidos = [t for r in resultados for t in r[2]]
    contas_fundeb: dict[int, list[dict[str, list[str]]]] = {}
    for (_, e, a, _), r in zip(tarefas, resultados):
        registro.juntar(r[3])
        if r[4]:
            contas_fundeb.setdefault(a, []).append(r[4])

    bimestral_linhas: list[dict[str, Any]] = []
    falhas_rreo: list[dict[str, Any]] = []
    if com_rreo:
        for (_, e, a, _), (linhas_b, falhas, obt, cons) in zip(
            tarefas, _executar(coletar_bimestral, tarefas, trabalhadores, "RREO")
        ):
            bimestral_linhas += linhas_b
            obtidos += obt
            registro.juntar(cons)
            if falhas:
                falhas_rreo.append({"cod_ibge": e.cod_ibge, "ente": e.nome, "ano": a, "bimestres": falhas})
    bimestral = pd.DataFrame(bimestral_linhas, columns=[
        "cod_ibge", "ano", "bimestre", "tipo_rreo", "q", "dotacao_atualizada", "empenhada_acum", "liquidada_acum"])

    anual = montar_anual(linhas, bimestral, dados_manuais["mde"])
    subfuncoes = _ordenar_subfuncoes(subfuncoes, anual)
    verif = verificacoes(anual, falhas_rreo)

    # 2–4) As fontes do painel de auditoria, cada uma isolada.
    vazio = _vazios()
    status: dict[str, dict[str, Any]] = {}
    res_sic, erro = _isolada("SICONFI (receita, MSC, entregas)", mod_siconfi.executar, cliente, lista_municipios, anos,
                             mod_siconfi.prefixos_fundeb(contas_fundeb), trabalhadores=min(trabalhadores, 4), hoje=hoje)
    res_sic = res_sic or vazio["siconfi"]
    status["SICONFI"] = {**res_sic.status, "ok": erro is None, "erro": erro, "modo": modo["siconfi"]}
    res_siope, erro = _isolada("SIOPE", mod_siope.executar, sorted(municipios), anos, atualizar=modo["siope"])
    res_siope = res_siope or vazio["siope"]
    status["SIOPE"] = {**res_siope.status, "ok": erro is None, "erro": erro, "modo": modo["siope"]}
    res_fnde, erro = _isolada("FNDE", mod_fnde.executar, {e.cod_ibge: e.nome for e in lista_municipios}, anos,
                              atualizar=modo["fnde"])
    res_fnde = res_fnde or vazio["fnde"]
    status["FNDE"] = {**res_fnde.status, "ok": erro is None, "erro": erro, "modo": modo["fnde"]}
    res_tce, erro = _isolada("TCE-ES", mod_tcees.executar, {e.cod_ibge: e.nome for e in lista_municipios}, anos,
                             atualizar=modo["tcees"], com_empenhos=com_empenhos, com_medicoes=com_medicoes,
                             com_itens=com_itens)
    res_tce = res_tce or vazio["tcees"]
    status["TCE-ES"] = {**res_tce.status, "ok": erro is None, "erro": erro, "modo": modo["tcees"]}
    res_esc, erro = _isolada("Censo", mod_escolas.compor, res_fnde.escolas, res_tce.empenhos.get("conselhos", pd.DataFrame()),
                             res_tce.obras, atualizar=modo["censo"])
    res_esc = res_esc or vazio["censo"]
    status["Censo"] = {**res_esc.status, "ok": erro is None and bool(res_esc.status.get("ok", False)), "erro": erro,
                       "modo": modo["censo"]}
    # INEP — ICA: uma planilha, verificada por hash. Hash divergente é erro da fonte (fica em fontes_status).
    res_ica, erro = _isolada("INEP (ICA)", mod_ica.executar, sorted(municipios), atualizar=modo["inep"])
    res_ica = res_ica or vazio["inep"]
    status["INEP"] = {**res_ica.status, "ok": erro is None, "erro": erro, "modo": modo["inep"]}
    for r in (res_sic.consultas, res_siope.consultas, res_fnde.consultas, res_tce.consultas, res_esc.consultas,
              res_ica.consultas):
        registro.juntar(r.todas())
    status["SICONFI"]["extraido_em"] = registro.extraido_em("SICONFI")
    tab_cnca = mod_cnca.compor(res_fnde.escolas, res_fnde.estado_cnca, res_tce.empenhos.get("funpaes"))

    # 5) Composição.
    anual = composicao.aplicar_msc(anual, res_sic.msc)
    anual = composicao.aplicar_siope(anual, res_siope.tabela)
    anual = composicao.aplicar_entregas(anual, res_sic.entregas)
    anual = composicao.aplicar_tcees(anual, res_tce.mde, res_tce.pcm_resumo, res_tce.obras, res_tce.q,
                                     res_tce.empenhos.get("total"))
    anual = composicao.aplicar_matriculas_etapa(anual, res_esc.matriculas_etapa)
    origem = composicao.receita_origem(res_sic.receita_bimestral, res_sic.msc, res_fnde.tabela, anual,
                                       sorted(municipios), anos)
    anexos_dict = {a: asdict(x) for a, x in anexos_por_ano.items()}
    itens_painel = itens_do_painel(res_tce.itens.get("itens", pd.DataFrame()))
    consolidado = composicao.consolidar(
        composicao.Consolidador(registro, {e.cod_ibge: e.nome for e in lista}, anexos_dict),
        anual=anual, subfuncoes=subfuncoes, bimestral=bimestral, receita_bim=res_sic.receita_bimestral, origem=origem,
        fluxo=res_sic.fluxo, natureza=res_sic.natureza, entregas=res_sic.entregas, siope=res_siope.tabela,
        repasses=res_fnde.tabela,
        # No consolidado entram os itens QUE O PAINEL MOSTRA (os maiores de cada município-ano).
        # Cada linha do consolidado carrega localização, cálculo e a consulta por extenso —
        # os 121 mil itens inteiros somariam ~220 MB de texto repetido. A tabela completa,
        # com a mesma proveniência por linha, fica em tcees_itens.csv.
        tcees={"pcm": res_tce.pcm, "obras": res_tce.obras, "empenhos": res_tce.empenhos, "dotacao": res_tce.dotacao,
               "itens": {**res_tce.itens, "itens": itens_painel}},
        cnca=tab_cnca, escolas=res_esc.escolas, dinheiro_escolas=res_esc.dinheiro,
        ica={"resultados": res_ica.tabela, "metas": res_ica.metas})
    validacao = composicao.validar(consolidado)
    cruzadas = composicao.conferencias_cruzadas(anual, res_esc.escolas)
    kpis = composicao.kpis_conformidade(anual)
    avisos = ([{"fonte": "SICONFI", **a} for a in res_sic.avisos] + [{"fonte": "SIOPE", **a} for a in res_siope.avisos]
              + [{"fonte": "FNDE", **a} for a in res_fnde.avisos]
              + [{"fonte": "TCE-ES", "aviso": f"{a['recurso']}: {a['aviso']}"} for a in res_tce.avisos]
              + [{"fonte": "Censo", "aviso": a} for a in res_esc.avisos]
              + [{"fonte": "INEP", **a} for a in res_ica.avisos])
    emp = res_tce.empenhos
    vazio_df = pd.DataFrame()

    # 6) Saídas.
    PROCESSADO.mkdir(parents=True, exist_ok=True)
    saidas = {
        "financiamento_anual.csv": anual, "despesa_subfuncao.csv": subfuncoes, "execucao_bimestral.csv": bimestral,
        "cobertura.csv": cobertura(anual), "receita_bimestral.csv": res_sic.receita_bimestral,
        "receita_origem.csv": origem, "fluxo_fonte_subfuncao.csv": res_sic.fluxo,
        "natureza_economica.csv": res_sic.natureza, "entregas.csv": res_sic.entregas,
        "siope_anexo8.csv": res_siope.tabela, "repasses_fnde.csv": res_fnde.tabela,
        "pdde_por_escola.csv": res_fnde.escolas, "cnca_municipio.csv": tab_cnca["municipio"],
        "ica_municipios.csv": res_ica.tabela, "ica_metas.csv": res_ica.metas,
        "cnca_estado.csv": tab_cnca["estado"], "cnca_funpaes.csv": tab_cnca["funpaes"],
        "tcees_mde.csv": res_tce.mde, "tcees_remessas_pcm.csv": res_tce.pcm, "tcees_obras_educacao.csv": res_tce.obras,
        "tcees_dotacao_acoes.csv": res_tce.dotacao, "tcees_contratacoes_educacao.csv": res_tce.contratacoes,
        **{f"tcees_empenhos_{k}.csv": v for k, v in emp.items()},
        **{f"tcees_{k}.csv": v for k, v in res_tce.itens.items()},
        "escolas.csv": res_esc.escolas, "escolas_vinculos.csv": res_esc.vinculos, "escolas_recursos.csv": res_esc.dinheiro,
        "matriculas_etapa_censo.csv": res_esc.matriculas_etapa,
        "consolidado.csv": consolidado, "consultas.csv": pd.DataFrame(registro.como_linhas()),
        "avisos.csv": pd.DataFrame(avisos, columns=["fonte", "cod_ibge", "ano", "mes", "aviso"]),
    }
    for nome, df in saidas.items():
        df.to_csv(PROCESSADO / nome, index=False, encoding="utf-8")

    fontes_extraido = {f: registro.extraido_em(f) for f in ("SICONFI", "SIOPE", "FNDE", "TCE-ES", "Censo", "INEP")}
    dataset = {
        "meta": {
            "esquema": SCHEMA,
            "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "extraido_em": {"primeira": min(obtidos, default=None), "ultima": max(obtidos, default=None)},
            "extraido_em_por_fonte": fontes_extraido,
            "fontes_status": json.loads(json.dumps(status, default=str)),
            "anos": anos,
            "ano_mais_recente": max(anos),
            "n_municipios": len(municipios),
            "minimo_mde_pct": MINIMO_MDE_PCT,
            "minimo_fundeb_profissionais_pct": mod_siope.MINIMO_FUNDEB_PROFISSIONAIS_PCT,
            "divergencia_relevante_pct": composicao.DIVERGENCIA_RELEVANTE_PCT,
            "base_url": BASE_URL,
            "anexos": {str(a): x for a, x in anexos_dict.items()},
            "fontes": FONTES,
            "documentacao": DOCUMENTACAO,
            "limitacoes": [{"__POPULACAO__": texto_populacao(anual),
                            "__ITENS__": texto_itens(res_tce.itens.get("itens_resumo", pd.DataFrame()), anos)}.get(l, l)
                           for l in LIMITACOES],
            "indicadores": indicadores.INDICADORES,
            "origens": indicadores.ORIGENS,
            "grupos_fonte": mod_msc.GRUPOS_FONTE,
            "nome_fonte": mod_msc.NOME_FONTE,
            "categorias_natureza": mod_msc.CATEGORIAS,
            "subcategorias_natureza": mod_msc.SUBCATEGORIAS,
            "elementos": mod_msc.NOME_ELEMENTO,
            "programas_fnde": mod_fnde.PROGRAMAS,
            "destinos_fnde": mod_fnde.DESTINOS,
            "fundamento_entregas": mod_entregas.FUNDAMENTO,
            "kpis": kpis,
            "kpis_obras": composicao.kpis_obras(res_tce.obras),
            "canais_escola": mod_escolas.CANAIS,
            "ica_niveis": {str(k): v for k, v in mod_ica.NIVEIS.items()},
            "ica_edicao": res_ica.edicao,
            "ica_limiar_saeb": mod_ica.LIMIAR_SAEB,
            "conferencias_cruzadas": cruzadas,
            "validacao": validacao,
        },
        "entes": [{"cod_ibge": e.cod_ibge, "nome": e.nome, "esfera": e.esfera} for e in lista],
        "anual": _json_limpo(anual.drop(columns=["siope_itens"], errors="ignore")),
        "subfuncoes": _json_limpo(subfuncoes),
        "catalogo_subfuncoes": catalogo_subfuncoes(subfuncoes),
        "bimestral": _json_limpo(bimestral),
        # O painel usa só estas linhas do Anexo 01 (a tabela inteira está em receita_bimestral.csv).
        "receita_bimestral": _compacta(res_sic.receita_bimestral, [
            "cod_ibge", "ano", "bimestre", "tipo_rreo", "q", "receita_total", "impostos", "transferencias_correntes",
            "transf_correntes_uniao", "transf_correntes_estados", "transf_correntes_outras_publicas",
            "transferencias_capital"], dicionario=["tipo_rreo"]),
        "origem": _compacta(origem, ["cod_ibge", "ano", "categoria", "valor", "fonte", "q"], dicionario=["categoria", "fonte"]),
        # fluxo, natureza e entregas: a consulta é uma por município-ano (q_msc, q_extrato na tabela anual).
        "fluxo": _compacta(res_sic.fluxo, ["cod_ibge", "ano", "grupo", "fonte", "subfuncao", "empenhada"],
                           dicionario=["grupo"]),
        "natureza": _compacta(res_sic.natureza, ["cod_ibge", "ano", "categoria", "subcategoria", "elemento", "empenhada",
                                                 "liquidada", "paga"], dicionario=["categoria", "subcategoria"]),
        "entregas": _compacta(res_sic.entregas, ["cod_ibge", "ano", "poder", "relatorio", "periodo", "periodicidade",
                                                 "prazo", "data_local", "situacao", "dias_atraso", "status", "observacao"],
                              dicionario=["poder", "relatorio", "periodicidade", "situacao", "status", "observacao"]),
        "siope": _compacta(res_siope.tabela, ["cod_ibge", "ano", "status_siope", *mod_siope.CAMPOS, "pdf_gerado_em",
                                              "pdf_publicado_em", "itens_usados", "q"],
                           dicionario=["status_siope", "itens_usados"]),
        "repasses": _compacta(res_fnde.tabela, ["cod_ibge", "ano", "programa", "destino", "valor", "meses", "q"],
                              dicionario=["programa", "destino"]),
        # URL partida em base (repetida: vai para o dicionário) + resto; o painel junta as duas.
        "consultas": _compacta(_consultas_partidas(registro),
                               ["id", "fonte", "recurso", "descricao", "url_base", "url_resto", "obtido_em", "arquivo",
                                "metodo", "sha256"], dicionario=["fonte", "recurso", "descricao", "url_base", "metodo"]),
        # TCE-ES: Nível 3 e conformidade junto ao Tribunal.
        "pcm": _compacta(res_tce.pcm.assign(limite=_dia(res_tce.pcm, "limite"), homologacao=_dia(res_tce.pcm, "homologacao")),
                         ["cod_ibge", "ano", "mes", "ug", "limite", "homologacao", "situacao", "dias_atraso"],
                         dicionario=["ug", "situacao"]),
        "obras": _compacta(res_tce.obras, COLUNAS_OBRAS, dicionario=["situacao", "tipo_intervencao", "ug", "q"]),
        "credores": _compacta(emp.get("credores", vazio_df), ["cod_ibge", "ano", "credor", "credor_nome", "pessoa_fisica",
                                                              "empenhada", "liquidada", "paga", "empenhos", "elemento",
                                                              "fonte", "q"],
                              dicionario=["credor", "credor_nome", "elemento", "q"]),
        "acoes": _compacta(emp.get("acoes", vazio_df), ["cod_ibge", "ano", "CodigoAcao", "NomeAcao", "CodigoSubFuncao",
                                                        "empenhada", "liquidada", "paga", "q"],
                           dicionario=["NomeAcao", "CodigoSubFuncao", "q"]),
        "fontes_det": _compacta(emp.get("fontes", vazio_df), ["cod_ibge", "ano", "CodigoFonteReduzida", "NomeFonteReduzida",
                                                              "CodigoDetalhamento", "NomeDetalhamento", "empenhada", "paga",
                                                              "q"], dicionario=["NomeFonteReduzida", "NomeDetalhamento", "q"]),
        "conselhos": _compacta(emp.get("conselhos", vazio_df), ["cod_ibge", "ano", "credor", "credor_nome", "empenhada",
                                                                "paga", "acao", "fonte", "q"],
                               dicionario=["credor", "credor_nome", "acao", "q"]),
        "obras_empenhos": _compacta(emp.get("obras_empenhos", vazio_df), ["cod_ibge", "ano", "credor", "credor_nome",
                                                                          "NomeAcao", "empenhada", "paga", "q"],
                                    dicionario=["credor", "credor_nome", "NomeAcao", "q"]),
        # Credor × ação: o "ver detalhamento" de um credor ou de uma ação, sem empenho a empenho.
        # O mesmo credor aparece em dezenas de ações e o mesmo nome de ação, em dezenas de
        # credores: sem o dicionário nas quatro colunas, esta tabela sozinha passa de 4 MB.
        "credor_acao": _compacta(emp.get("credor_acao", vazio_df), ["cod_ibge", "ano", "CodigoAcao", "NomeAcao", "credor",
                                                                    "credor_nome", "elemento", "fonte", "empenhada",
                                                                    "paga", "demais", "q"],
                                 dicionario=["CodigoAcao", "NomeAcao", "credor", "credor_nome", "elemento", "fonte", "q"]),
        # O que foi comprado: os maiores itens de cada município-ano, o resumo e o total por contratada.
        "itens": _compacta(itens_painel,
                           ["cod_ibge", "ano", "contratacao", "chave", "ug", "descricao", "unidade", "quantidade",
                            "valor_unitario", "valor_total", "contratada", "cnpj_contratada", "medicoes", "valor_medido",
                            "vinculo", "q"],
                           dicionario=["ug", "unidade", "contratada", "cnpj_contratada", "vinculo", "q"]),
        "itens_resumo": _compacta(res_tce.itens.get("itens_resumo", vazio_df), mod_tcees.COLUNAS_ITENS_RESUMO,
                                  dicionario=["vinculos", "q"]),
        "itens_contratada": _compacta(res_tce.itens.get("itens_contratada", vazio_df), mod_tcees.COLUNAS_ITENS_CONTRATADA,
                                      dicionario=["contratada", "q"]),
        # Do objeto da contratação o painel mostra só o começo, como subtítulo do item.
        "contratacoes": _compacta(contratacoes_do_painel(res_tce.contratacoes),
                                  ["cod_ibge", "ano", "contratacao", "ug", "objeto", "modalidade", "url_edital", "q"],
                                  dicionario=["ug", "modalidade", "q"]),
        "dotacao": _compacta(res_tce.dotacao, ["cod_ibge", "ano", "CodigoAcao", "NomeAcao", "obra", "PrevisaoInicial",
                                               "PrevisaoAtualizada", "Empenhada", "Liquidada", "Paga", "q"],
                             dicionario=["NomeAcao", "q"]),
        # CNCA automático.
        "cnca": {
            "municipio": _json_limpo(tab_cnca["municipio"]),
            "estado": _json_limpo(tab_cnca["estado"]),
            "escolas": _compacta(tab_cnca["escolas"], ["cod_ibge", "ano", "programa", "cnpj_uex", "uex", "valor", "meses", "q"],
                                 dicionario=["programa", "q"]),
            "funpaes": _compacta(tab_cnca["funpaes"], ["cod_ibge", "ano", "NomeAcao", "DescricaoElemento", "credor",
                                                       "credor_nome", "CodigoFonteReduzida", "empenhada", "paga", "q"],
                                 dicionario=["NomeAcao", "DescricaoElemento", "q"]),
        },
        # ICA (INEP): taxa por município × ano e metas pactuadas; edição em meta.ica_edicao.
        "ica": {"resultados": _json_limpo(res_ica.tabela), "metas": _json_limpo(res_ica.metas)},
        "programas_api": mod_cnca.programas_api(tab_cnca["municipio"], res_ica.tabela),
        # Escolas (Censo) e o dinheiro que chega a cada uma.
        "escolas": _compacta(res_esc.escolas, mod_escolas.COLUNAS_CADASTRO, dicionario=["rede", "q"]),
        "escolas_recursos": _compacta(res_esc.dinheiro, mod_escolas.COLUNAS_DINHEIRO, dicionario=["canal", "po", "po_nome", "q"]),
        "escolas_vinculos": _compacta(res_esc.vinculos, ["fonte", "origem", "nome_origem", "cod_ibge", "co_entidade", "nota",
                                                         "metodo"], dicionario=["fonte", "metodo"]),
        "avisos": avisos,
        "verificacoes": json.loads(json.dumps(verif, default=int)),
        "programas": catalogo,
        "dados_manuais": dados_manuais,
    }
    # A versão (retrato do consolidado em historico/) vem antes do JSON, para o painel citá-la.
    dataset["meta"]["versao"] = historico.gravar_versao(consolidado, {
        "anos": anos, "fontes_com_rede": list(fontes), "fontes_status": status, "validacao": validacao,
        "extraido_em_por_fonte": fontes_extraido})
    with open(PROCESSADO / "dataset.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, separators=(",", ":"), default=str)
    log.info("gravado em %s (versão %s)", PROCESSADO, dataset["meta"]["versao"])
    return dataset


def _resumo(dataset: dict[str, Any]) -> list[str]:
    a = pd.DataFrame(dataset["anual"])
    m = a[a["esfera"] == "M"]
    linhas = [f"exercícios {dataset['meta']['anos']}, {dataset['meta']['n_municipios']} municípios"]
    for ano, g in m.groupby("ano"):
        linhas.append(f"  {ano}: DCA ok em {(g['status_dca'] == 'ok').sum()}/{len(g)}; "
                      f"MSC ok em {(g['status_msc'] == 'ok').sum()}/{len(g)}; "
                      f"SIOPE ok em {(g['status_siope'] == 'ok').sum()}/{len(g)}; "
                      f"RREO 6 bim em {g['rreo_b6_empenhada'].notna().sum()}/{len(g)}")
    v = dataset["verificacoes"]
    linhas.append(f"fechamento DCA: {len(v['fechamento_dca']['falhas'])} falha(s) em {v['fechamento_dca']['conferidos']}")
    linhas.append(f"subfunções fecham: {len(v['subfuncoes_fecham']['falhas'])} falha(s) em {v['subfuncoes_fecham']['conferidos']}")
    linhas.append(f"RREO vs DCA: {v['rreo_vs_dca']['divergentes']} divergente(s) em {v['rreo_vs_dca']['comparaveis']}")
    for chave, c in dataset["meta"]["conferencias_cruzadas"].items():
        linhas.append(f"{chave}: {c['batem']}/{c['comparaveis']} batem")
    val = dataset["meta"]["validacao"]
    linhas.append(f"consolidado: {val['registros']} registros; IBGE 7 dígitos: {val['ibge_7_digitos']}; "
                  f"negativos inesperados: {val.get('n_negativos_inesperados', 0)}; sem proveniência: {val['sem_proveniencia']}")
    for fonte, s in dataset["meta"]["fontes_status"].items():
        linhas.append(f"fonte {fonte}: {'ok' if s.get('ok') else 'FALHOU — ' + str(s.get('erro'))} (modo {s.get('modo')})")
    return linhas


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--anos", type=parse_anos, help="ex.: 2021-2025 ou 2023,2024 (padrão: os 5 últimos publicados)")
    p.add_argument("--atualizar", choices=("nao", "vazios", "tudo"), default="nao",
                   help="usar o cache (nao), refazer respostas vazias (vazios) ou ignorar o cache (tudo)")
    p.add_argument("--fontes", default=",".join(FONTES_DISPONIVEIS),
                   help="fontes que podem usar a rede, ex.: siope ou siconfi,fnde (as demais só leem o cache)")
    p.add_argument("--sem-rreo", action="store_true", help="pular o RREO bimestral (só DCA)")
    p.add_argument("--sem-empenhos", action="store_true", help="TCE-ES sem empenhos e despesas agregadas (~600 MB/ano)")
    p.add_argument("--sem-medicoes", action="store_true", help="TCE-ES sem o arquivo de medições (1,2 GB lido em fluxo)")
    p.add_argument("--sem-itens", action="store_true", help="TCE-ES sem contratações e itens (~1,1 GB lido em fluxo)")
    p.add_argument("--trabalhadores", type=int, default=6)
    p.add_argument("--estrito", action="store_true", help="sai com código 1 se alguma conferência falhar")
    p.add_argument("-v", "--verboso", action="store_true")
    args = p.parse_args(argv)
    for fluxo in (sys.stdout, sys.stderr):  # console do Windows (cp1252) não pode derrubar o resumo
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(errors="replace")
    fontes = [f.strip() for f in args.fontes.split(",") if f.strip()]
    if invalidas := set(fontes) - set(FONTES_DISPONIVEIS):
        p.error(f"fontes inválidas: {sorted(invalidas)} (use {', '.join(FONTES_DISPONIVEIS)})")

    logging.basicConfig(level=logging.DEBUG if args.verboso else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    dataset = executar(args.anos, atualizar=args.atualizar, com_rreo=not args.sem_rreo, trabalhadores=args.trabalhadores,
                       fontes=fontes, com_empenhos=not args.sem_empenhos, com_medicoes=not args.sem_medicoes,
                       com_itens=not args.sem_itens)
    print("\n".join(_resumo(dataset)))
    v, val = dataset["verificacoes"], dataset["meta"]["validacao"]
    falhou = bool(v["fechamento_dca"]["falhas"] or v["falhas_consulta_rreo"] or not v["codigos_ibge_7_digitos"]
                  or not val["ibge_7_digitos"] or val.get("n_negativos_inesperados") or val["sem_proveniencia"]
                  or not all(s.get("ok") for s in dataset["meta"]["fontes_status"].values()))
    if falhou:
        print("ATENÇÃO: há conferências ou fontes com falha (ver meta.validacao e meta.fontes_status em dataset.json).",
              file=sys.stderr)
    return 1 if (falhou and args.estrito) else 0


if __name__ == "__main__":
    sys.exit(main())
