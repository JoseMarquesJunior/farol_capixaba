"""RREO Anexo 01 (Balanço Orçamentário): de onde vem a receita, por bimestre.

Consulta (uma por município, exercício e bimestre; tenta os dois tipos)::

    /rreo?an_exercicio=<ano>&nr_periodo=<1..6>&co_tipo_demonstrativo=<RREO|RREO Simplificado>
         &no_anexo=RREO-Anexo 01&co_esfera=M&id_ente=<IBGE7>

Estrutura REAL (conferida em 2026-09-22, Vitória 2024 "RREO" e Afonso Cláudio
2024 "RREO Simplificado"): os mesmos 15 campos de `/rreo` e `/dca` (ver
`parsing.py`), uma linha por conta × coluna. Na receita, as colunas são
"PREVISÃO INICIAL", "PREVISÃO ATUALIZADA (a)", "No Bimestre (b)", "% (b/a)",
**"Até o Bimestre (c)"** (a realizada acumulada no ano — é a usada), "% (c/a)"
e "SALDO (a-c)". O `cod_conta` é um identificador SEMÂNTICO estável
(`Impostos`, `TransferenciasCorrentes`…), igual nos dois tipos de RREO; o
Simplificado só traz menos linhas. Nenhum `cod_conta` se repete com valores
diferentes (o bloco intra-orçamentário tem nomes próprios).

O Anexo 01 NÃO detalha FPM, ICMS nem FUNDEB: agrega por origem (União,
Estados, "outras instituições públicas" — onde cai o FUNDEB desde o ementário
de 2022). Por isso o FUNDEB vem da MSC e as transferências do FNDE, da CGU.
Conferência: em Vitória 2024, `Impostos` = 1.247.123.412,89, idêntico ao item 1
("receita de impostos") do Anexo 8 do SIOPE.
"""

from __future__ import annotations

from typing import Any, Iterable

from .cliente import ClienteSiconfi, ErroSiconfi, NaoColetado
from .config import BIMESTRES, TIPOS_RREO
from .entes import Ente
from .parsing import _unico, norm
from .proveniencia import Consulta, caminho_relativo

ANEXO = "RREO-Anexo 01"

#: cod_conta → chave interna. A ordem é a do demonstrativo.
LINHAS = {
    "ReceitasExcetoIntraOrcamentarias": "receita_total",
    "ReceitasCorrentes": "receitas_correntes",
    "ReceitaTributaria": "receita_tributaria",
    "Impostos": "impostos",
    "Taxas": "taxas",
    "ContribuicaoDeMelhoria": "contribuicao_melhoria",
    "ReceitaDeContribuicoes": "contribuicoes",
    "ReceitaPatrimonial": "receita_patrimonial",
    "ReceitaDeServicos": "receita_servicos",
    "TransferenciasCorrentes": "transferencias_correntes",
    "TransferenciasCorrentesDaUniaoEDeSuasEntidades": "transf_correntes_uniao",
    "TransferenciasCorrentesDosEstadosEDoDistritoFederalEDeSuasEntidades": "transf_correntes_estados",
    "TransferenciasCorrentesDeOutrasInstituicoesPublicas": "transf_correntes_outras_publicas",
    "TransferenciasCorrentesDeInstituicoesPrivadas": "transf_correntes_privadas",
    "OutrasTransferenciasCorrentes": "transf_correntes_demais",
    "OutrasReceitasCorrentes": "outras_receitas_correntes",
    "ReceitasDeCapital": "receitas_capital",
    "ReceitasDeOperacoesDeCredito": "operacoes_credito",
    "AlienacaoDeBens": "alienacao_bens",
    "TransferenciasDeCapital": "transferencias_capital",
    "TransferenciasDeCapitalDaUniaoEDeSuasEntidades": "transf_capital_uniao",
    "TransferenciasDeCapitalDosEstadosEDoDistritoFederalEDeSuasEntidades": "transf_capital_estados",
}
CHAVES = tuple(LINHAS.values())
_COLUNA_REALIZADA = "ate o bimestre"


def receita_a01(itens: Iterable[dict[str, Any]]) -> dict[str, float] | None:
    """Receita realizada até o bimestre, por linha do Anexo 01. `None` se o anexo não tem receita.

    Linha que o ente não traz fica FORA do dicionário (sem dado, não zero).
    """
    por_conta: dict[str, list[dict[str, Any]]] = {}
    for l in itens:
        if l.get("cod_conta") in LINHAS and norm(l.get("coluna")).startswith(_COLUNA_REALIZADA):
            por_conta.setdefault(l["cod_conta"], []).append(l)
    saida = {LINHAS[c]: v for c, ls in por_conta.items() if (v := _unico(ls, f"A01 {c}")) is not None}
    return saida if "receita_total" in saida else None


def coletar_ano(
    cliente: ClienteSiconfi, ente: Ente, ano: int
) -> tuple[list[dict[str, Any]], list[int], list[Consulta]]:
    """Os seis bimestres de um ente. Devolve (linhas, bimestres com falha, consultas).

    Como no Anexo 02: tenta primeiro o tipo de RREO que funcionou no bimestre
    anterior, depois o outro. Só a consulta que TROUXE o dado entra na
    proveniência da linha — a do outro tipo, vazia, é só tentativa.
    """
    linhas: list[dict[str, Any]] = []
    falhas: list[int] = []
    consultas: list[Consulta] = []
    preferido: str | None = None
    for bim in BIMESTRES:
        ordem = ([preferido] if preferido else []) + [t for t in TIPOS_RREO if t != preferido]
        for tipo in ordem:
            params = {"an_exercicio": ano, "nr_periodo": bim, "co_tipo_demonstrativo": tipo,
                      "no_anexo": ANEXO, "co_esfera": ente.esfera, "id_ente": ente.cod_ibge}
            try:
                r = cliente.consultar("rreo", **params)
            except NaoColetado:
                break
            except ErroSiconfi:
                falhas.append(bim)
                break
            if valores := (receita_a01(r.itens) if r.itens else None):
                c = Consulta(fonte="SICONFI", recurso="rreo",
                             descricao=f"{ANEXO} ({tipo}), {bim}º bimestre de {ano}",
                             url=cliente.url_completa("rreo", params), obtido_em=r.obtido_em,
                             arquivo=caminho_relativo(r.arquivo))
                consultas.append(c)
                linhas.append({"cod_ibge": ente.cod_ibge, "ano": ano, "bimestre": bim, "tipo_rreo": tipo,
                               "q": c.id, **valores})
                preferido = tipo
                break
    return linhas, falhas, consultas
