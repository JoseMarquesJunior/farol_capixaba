"""Confirmação do nome dos anexos em cada exercício.

O enunciado pede confirmar o nome do anexo por `/anexos-relatorios`. Em
2026-09-21 esse endpoint não respondeu em nenhuma variante testada (com e sem
filtro, com `limit=5`: nada em 100 s). Em vez de depender dele, o nome é lido
NOS DADOS de um município de referência, pelo conteúdo do anexo, não pelo
rótulo: o anexo de despesa por função é o que carrega a conta
`RREO2TotalDespesas`; o da DCA é o que tem "Total Geral da Despesa por Função"
com a coluna "Despesas Empenhadas" (o `I-G` tem o mesmo rótulo, mas colunas de
restos a pagar). O resultado é conferido contra os nomes esperados em `config`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace

from .cliente import ClienteSiconfi
from .config import (
    ANEXO_DCA_DESPESA_FUNCAO,
    ANEXO_DCA_RECEITA,
    ANEXO_RREO_DESPESA_FUNCAO,
)
from .entes import Ente
from .parsing import ErroParsing, norm

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnexosExercicio:
    ano: int
    rreo_despesa_funcao: str
    dca_despesa_funcao: str
    dca_receita: str
    referencia: int
    #: Diferenças em relação aos nomes esperados em `config` (vazio = tudo igual).
    divergencias: tuple[str, ...] = field(default=())


def _unico(nomes: set[str], o_que: str, ano: int) -> str:
    if len(nomes) != 1:
        raise ErroParsing(f"{ano}: esperava um único anexo de {o_que}, achei {sorted(nomes) or 'nenhum'}")
    return next(iter(nomes))


def descobrir(cliente: ClienteSiconfi, ano: int, referencias: list[Ente]) -> AnexosExercicio:
    """Nome dos três anexos usados, em `ano`, lidos dos dados.

    `referencias` são tentadas em ordem até uma entregar os três anexos.
    """
    erros: list[str] = []
    for ente in referencias:
        try:
            dca = cliente.consultar("dca", an_exercicio=ano, id_ente=ente.cod_ibge).itens
            rreo = cliente.consultar(
                "rreo", an_exercicio=ano, nr_periodo=6, co_tipo_demonstrativo="RREO",
                co_esfera="M", id_ente=ente.cod_ibge,
            ).itens
            achado = AnexosExercicio(
                ano=ano,
                rreo_despesa_funcao=_unico(
                    {l["anexo"] for l in rreo if l["cod_conta"] == "RREO2TotalDespesas"}, "despesa por função (RREO)", ano),
                dca_despesa_funcao=_unico(
                    {l["anexo"] for l in dca
                     if norm(l["rotulo"]) == "total geral da despesa por funcao"
                     and norm(l["coluna"]) == "despesas empenhadas"}, "despesa por função (DCA)", ano),
                dca_receita=_unico(
                    {l["anexo"] for l in dca
                     if str(l["cod_conta"]).startswith("RO1.7")
                     and norm(l["coluna"]) == "receitas brutas realizadas"}, "receita (DCA)", ano),
                referencia=ente.cod_ibge,
            )
        except ErroParsing as exc:
            erros.append(f"{ente.nome}: {exc}")
            continue

        esperados = {
            "rreo_despesa_funcao": ANEXO_RREO_DESPESA_FUNCAO,
            "dca_despesa_funcao": ANEXO_DCA_DESPESA_FUNCAO,
            "dca_receita": ANEXO_DCA_RECEITA,
        }
        divergencias = tuple(
            f"{campo}: esperado {esp!r}, encontrado {getattr(achado, campo)!r}"
            for campo, esp in esperados.items() if getattr(achado, campo) != esp
        )
        for d in divergencias:
            log.warning("%s: nome de anexo mudou — %s", ano, d)
        return replace(achado, divergencias=divergencias)
    raise ErroParsing(f"{ano}: nenhum município de referência entregou os anexos ({'; '.join(erros)})")
