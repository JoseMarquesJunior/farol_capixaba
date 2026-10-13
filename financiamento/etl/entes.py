"""Lista dos entes do ES (78 municípios + Estado) a partir de `/entes`."""

from __future__ import annotations

from dataclasses import dataclass

from .cliente import ClienteSiconfi
from .config import COD_ESTADO_ES, N_MUNICIPIOS_ES, UF_MUNICIPIOS
from .parsing import ErroParsing, validar_ibge


@dataclass(frozen=True, slots=True)
class Ente:
    cod_ibge: int
    nome: str
    esfera: str  # "M" município, "E" Estado
    #: População do retrato ATUAL de `/entes` (ele ignora `an_exercicio`). Serve só
    #: para escolher municípios de referência; o per capita usa a população do
    #: exercício, que vem nas linhas de `/rreo` e `/dca`.
    populacao_atual: int | None = None


def listar_entes_es(cliente: ClienteSiconfi) -> list[Ente]:
    """78 municípios do ES + o Estado, validados.

    O Estado não se filtra por `uf` (vem "BR"), e sim pelo código 32. Levanta
    `ErroParsing` se a contagem de municípios não for 78 — melhor parar do que
    seguir com uma lista incompleta e reportar cobertura errada.
    """
    itens = cliente.consultar("entes").itens
    entes: list[Ente] = []
    for i in itens:
        if i["esfera"] == "M" and i["uf"] == UF_MUNICIPIOS:
            entes.append(Ente(validar_ibge(i["cod_ibge"]), i["ente"], "M", i.get("populacao")))
        elif i["esfera"] == "E" and int(i["cod_ibge"]) == COD_ESTADO_ES:
            entes.append(Ente(validar_ibge(i["cod_ibge"], municipio=False), i["ente"], "E", i.get("populacao")))
    n_municipios = sum(e.esfera == "M" for e in entes)
    if n_municipios != N_MUNICIPIOS_ES or not any(e.esfera == "E" for e in entes):
        raise ErroParsing(f"esperava {N_MUNICIPIOS_ES} municípios + Estado do ES; achei {n_municipios} municípios")
    if len({e.cod_ibge for e in entes}) != len(entes):
        raise ErroParsing("códigos IBGE repetidos na lista de entes")
    return sorted(entes, key=lambda e: (e.esfera != "E", e.cod_ibge))
