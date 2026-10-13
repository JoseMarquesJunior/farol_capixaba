"""Proveniência por registro: de que consulta exata saiu cada número.

Todo valor do dataset final aponta para uma ou mais `Consulta`s — a requisição
reproduzível (URL com os parâmetros, ou o arquivo no FTP), o instante da coleta
e o arquivo do cache bruto que guarda a resposta original. A `localizacao`
(anexo/linha/coluna, item do demonstrativo) e o `calculo` de cada indicador
vêm do catálogo em `indicadores.py`, o mesmo que o painel mostra no botão
"ver fonte". É isso que faz o painel servir de evidência — o equivalente da
nota de rodapé de um papel de trabalho —, e não só de ilustração.

O `id` de uma consulta depende só da requisição (fonte + URL), então é estável
entre execuções: a comparação de duas extrações casa os registros por ele.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .config import BRUTO

#: "Governo do ES" é o SIGEFES (execução da esfera estadual, publicada pela SEFAZ no
#: mesmo portal CKAN do Tribunal) e NÃO se confunde com "TCE-ES": são órgãos diferentes,
#: e atribuir o dado ao Tribunal seria erro de proveniência. "Diário Oficial" cobre o
#: Querido Diário e o DOM-ES/AMUNES.
FONTES_VALIDAS = ("SICONFI", "SIOPE", "FNDE", "TCE-ES", "Censo", "INEP",
                  "Governo do ES", "Diário Oficial")


@dataclass(frozen=True, slots=True)
class Consulta:
    """Uma requisição a uma fonte, como foi feita e quando."""

    fonte: str        # SICONFI | SIOPE | FNDE | TCE-ES | Censo | INEP
    recurso: str      # dca, rreo, msc_orcamentaria, extrato_entregas, siope_rreo_anexo8, cgu_transferencias, ica_resultados_municipios
    descricao: str    # "DCA-Anexo I-E, exercício 2024" — para gente ler
    url: str          # reproduz a consulta (sem paginação)
    obtido_em: str    # ISO 8601, UTC — o instante ORIGINAL da coleta, preservado pelo cache
    arquivo: str      # caminho do cache bruto, relativo a financiamento/dados/bruto
    metodo: str = "GET"
    sha256: str | None = None  # do arquivo baixado, quando a fonte é um arquivo (PDF, ZIP)

    def __post_init__(self) -> None:
        if self.fonte not in FONTES_VALIDAS:
            raise ValueError(f"fonte inválida: {self.fonte!r}")

    @property
    def id(self) -> str:
        return hashlib.sha1(f"{self.fonte}|{self.metodo}|{self.url}".encode("utf-8")).hexdigest()[:12]


def caminho_relativo(arquivo: Path, base: Path = BRUTO) -> str:
    """Caminho do cache relativo a `dados/bruto`, com barras normais (igual em qualquer SO)."""
    try:
        return arquivo.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return arquivo.as_posix()


class Registro:
    """Coleção de consultas usadas numa execução, sem repetição.

    Thread-safe: as coletas rodam em paralelo e registram ao mesmo tempo.
    """

    def __init__(self) -> None:
        self._por_id: dict[str, Consulta] = {}
        self._trava = threading.Lock()

    def adicionar(self, consulta: Consulta) -> str:
        with self._trava:
            atual = self._por_id.get(consulta.id)
            # Mesma requisição vista duas vezes: fica a coleta mais antiga (a do cache).
            if atual is None or consulta.obtido_em < atual.obtido_em:
                self._por_id[consulta.id] = consulta
        return consulta.id

    def juntar(self, outras: Iterable[Consulta]) -> None:
        for c in outras:
            self.adicionar(c)

    def __contains__(self, cid: str) -> bool:
        return cid in self._por_id

    def __getitem__(self, cid: str) -> Consulta:
        return self._por_id[cid]

    def __len__(self) -> int:
        return len(self._por_id)

    def todas(self) -> list[Consulta]:
        return sorted(self._por_id.values(), key=lambda c: (c.fonte, c.recurso, c.url))

    def extraido_em(self, fonte: str | None = None) -> dict[str, str | None]:
        """Primeira e última coleta (de uma fonte, ou de todas)."""
        tempos = [c.obtido_em for c in self._por_id.values() if fonte is None or c.fonte == fonte]
        return {"primeira": min(tempos, default=None), "ultima": max(tempos, default=None), "consultas": len(tempos)}

    def como_linhas(self) -> list[dict[str, Any]]:
        return [{"id": c.id, **asdict(c)} for c in self.todas()]


def juntar_ids(*ids: Any) -> str:
    """Ids de consulta num campo só ("a;b;c"), sem repetição e em ordem estável.

    Aceita id solto, "a;b" já juntado, listas — e ignora vazio/NaN (linha sem
    consulta, como um município que não publicou).
    """
    vistos: list[str] = []
    for item in ids:
        if isinstance(item, str):
            candidatos: Iterable[Any] = [item]
        elif isinstance(item, (list, tuple, set)):
            candidatos = item
        else:
            continue
        for cid in candidatos:
            if not isinstance(cid, str):
                continue
            for parte in cid.split(";"):
                if parte and parte not in vistos:
                    vistos.append(parte)
    return ";".join(vistos)
