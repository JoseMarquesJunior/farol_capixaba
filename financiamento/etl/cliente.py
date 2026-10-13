"""Cliente da API do SICONFI: paginação, novas tentativas e cache bruto em disco.

Cada consulta vira um arquivo `dados/bruto/<ano>/<endpoint>/<slug>.json.gz` com
a resposta exatamente como a API a devolveu, mais a requisição e o instante da
coleta. Reexecutar o ETL relê o cache em vez de consultar a API — é isso que
dá reprodutibilidade e trilha de auditoria.

Uma resposta VAZIA também é cacheada: "o ente não publicou" é um fato, e é
diferente de "a consulta falhou" (essa levanta `ErroSiconfi` e não é cacheada).

Limite de taxa: a API devolve HTTP 429 sob rajada (em 2026-09-22, depois de ~20
páginas seguidas da MSC). O cliente espaça as requisições de TODAS as threads
(`intervalo_minimo`) e, num 429, respeita `Retry-After` ou espera 15 s, 30 s,
60 s… — e faz as outras threads esperarem junto.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import requests

from .config import BASE_URL, BRUTO

log = logging.getLogger(__name__)

#: Estados HTTP que valem uma nova tentativa. O ORDS do Tesouro devolve 5xx
#: com frequência sob carga.
_TEMPORARIOS = {429, 500, 502, 503, 504}
_PARAMETROS_DE_PAGINA = {"offset", "limit"}


class ErroSiconfi(RuntimeError):
    """A consulta falhou depois de esgotar as tentativas."""


class NaoColetado(ErroSiconfi):
    """Modo `offline`: a consulta não está no cache e a rede não pode ser usada.

    Não é falha da fonte: é o que acontece ao religar só uma fonte e deixar as
    outras lendo o cache — o que nunca foi coletado aparece como "não coletado".
    """


MODOS_ATUALIZAR = ("nao", "vazios", "tudo", "offline")


@dataclass(frozen=True, slots=True)
class Resposta:
    """Itens de uma consulta (já concatenando as páginas) e sua procedência."""

    itens: list[dict[str, Any]]
    obtido_em: str
    do_cache: bool
    arquivo: Path


class ClienteSiconfi:
    """Consulta a API e mantém o cache bruto.

    `atualizar` controla o uso do cache: "nao" (padrão) relê tudo que existe;
    "vazios" refaz só as respostas vazias (útil quando o ente publicou depois);
    "tudo" ignora o cache; "offline" só lê o cache e nunca usa a rede.
    """

    def __init__(
        self,
        pasta_bruto: Path = BRUTO,
        *,
        atualizar: str = "nao",
        tentativas: int = 5,
        timeout: tuple[float, float] = (10.0, 180.0),
        base_url: str = BASE_URL,
        intervalo_minimo: float = 0.15,
    ) -> None:
        if atualizar not in MODOS_ATUALIZAR:
            raise ValueError(f"atualizar inválido: {atualizar!r}")
        self.pasta_bruto = pasta_bruto
        self.atualizar = atualizar
        self.tentativas = tentativas
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")
        self.intervalo_minimo = intervalo_minimo
        self._local = threading.local()
        self._trava_ritmo = threading.Lock()
        self._proxima = 0.0  # instante (monotônico) liberado para a próxima requisição

    # ------------------------------------------------------------------ cache

    def caminho(self, endpoint: str, params: Mapping[str, Any]) -> Path:
        """Arquivo de cache de uma consulta (deterministico a partir dos parâmetros).

        O ano da pasta vem de `an_exercicio` (RREO, DCA) ou `an_referencia` (MSC,
        extrato de entregas): o cache fica organizado por ano e por endpoint.
        """
        chave_ano = next((k for k in ("an_exercicio", "an_referencia") if k in params), None)
        ano = params.get(chave_ano) if chave_ano else None
        pasta = self.pasta_bruto / (str(ano) if ano is not None else "_sem_exercicio") / endpoint
        chaves = sorted(k for k in params if k != chave_ano and k not in _PARAMETROS_DE_PAGINA)
        slug = "__".join(f"{k}={params[k]}" for k in chaves) or "todos"
        slug = re.sub(r"[^A-Za-z0-9=._-]+", "_", slug)
        return pasta / f"{slug}.json.gz"

    def _ler_cache(self, arquivo: Path) -> Resposta | None:
        if self.atualizar == "tudo" or not arquivo.exists():
            return None
        try:
            with gzip.open(arquivo, "rt", encoding="utf-8") as f:
                corpo = json.load(f)
        except (OSError, ValueError) as exc:
            log.warning("cache ilegível, será refeito: %s (%s)", arquivo.name, exc)
            return None
        if self.atualizar == "vazios" and not corpo["itens"]:
            return None
        return Resposta(corpo["itens"], corpo["obtido_em"], True, arquivo)

    @staticmethod
    def _gravar_cache(arquivo: Path, corpo: dict[str, Any]) -> None:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = arquivo.with_suffix(".tmp")
        with gzip.open(temporario, "wt", encoding="utf-8") as f:
            json.dump(corpo, f, ensure_ascii=False)
        temporario.replace(arquivo)  # troca atômica: nunca fica um cache pela metade

    # ------------------------------------------------------------------- rede

    def _sessao(self) -> requests.Session:
        # Uma sessão por thread: `requests.Session` não é documentada como thread-safe.
        if not hasattr(self._local, "sessao"):
            self._local.sessao = requests.Session()
            self._local.sessao.headers["User-Agent"] = "neduc-financiamento/1.0 (auditoria TCE-ES)"
        return self._local.sessao

    def _aguardar_vez(self) -> None:
        """Espaça as requisições de todas as threads por `intervalo_minimo`."""
        with self._trava_ritmo:
            agora = time.monotonic()
            espera = self._proxima - agora
            self._proxima = max(agora, self._proxima) + self.intervalo_minimo
        if espera > 0:
            time.sleep(espera)

    def _frear_todos(self, segundos: float) -> None:
        """Depois de um 429, ninguém consulta antes de `segundos` — não só a thread que levou."""
        with self._trava_ritmo:
            self._proxima = max(self._proxima, time.monotonic() + segundos)

    def _pagina(self, endpoint: str, params: Mapping[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        ultimo: Exception | None = None
        for tentativa in range(1, self.tentativas + 1):
            espera = 2.0**tentativa
            try:
                self._aguardar_vez()
                r = self._sessao().get(url, params=params, timeout=self.timeout)
                if r.status_code == 429:
                    pedido = r.headers.get("Retry-After", "")
                    espera = float(pedido) if pedido.isdigit() else min(15.0 * 2 ** (tentativa - 1), 240.0)
                    self._frear_todos(espera)
                if r.status_code in _TEMPORARIOS:
                    raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
                r.raise_for_status()
                # Decodifica explicitamente: a API serve UTF-8 e deixar o requests
                # adivinhar o charset já corrompeu acentos neste projeto.
                return json.loads(r.content.decode("utf-8"))
            except (requests.RequestException, ValueError) as exc:
                ultimo = exc
                if tentativa < self.tentativas:
                    log.warning("%s %s: %s — nova tentativa em %.0fs", endpoint, dict(params), exc, espera)
                    time.sleep(espera)
        raise ErroSiconfi(f"{endpoint} {dict(params)} falhou após {self.tentativas} tentativas: {ultimo}")

    def url_completa(self, endpoint: str, params: Mapping[str, Any]) -> str:
        """A URL exata que reproduz a consulta (sem paginação) — para a trilha de auditoria."""
        publicos = {k: v for k, v in params.items() if k not in _PARAMETROS_DE_PAGINA}
        return requests.Request("GET", f"{self.base_url}/{endpoint}", params=publicos).prepare().url

    def consultar(self, endpoint: str, **params: Any) -> Resposta:
        """Devolve todos os itens de `endpoint` para os parâmetros dados.

        `limit` pode ir nos parâmetros (a MSC aceita 5000 por página, contra 1000
        do padrão); ele e `offset` não entram na chave do cache.
        """
        arquivo = self.caminho(endpoint, params)
        if (em_cache := self._ler_cache(arquivo)) is not None:
            return em_cache
        if self.atualizar == "offline":
            raise NaoColetado(f"{endpoint} {dict(params)}: não está no cache (modo offline)")

        itens: list[dict[str, Any]] = []
        deslocamento = 0
        while True:
            pagina = self._pagina(endpoint, {**params, "offset": deslocamento})
            itens.extend(pagina["items"])
            if not pagina.get("hasMore"):
                break
            passo = pagina.get("limit") or len(pagina["items"])
            if not passo:  # proteção contra laço infinito com paginação malformada
                raise ErroSiconfi(f"{endpoint} {dict(params)}: hasMore sem limit")
            deslocamento += passo

        obtido_em = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._gravar_cache(
            arquivo,
            {
                "endpoint": endpoint,
                "params": dict(params),
                "url": f"{self.base_url}/{endpoint}",
                "obtido_em": obtido_em,
                "total_itens": len(itens),
                "itens": itens,
            },
        )
        return Resposta(itens, obtido_em, False, arquivo)
