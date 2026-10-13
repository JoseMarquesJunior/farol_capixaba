"""Carrega e valida `dados_manuais.yaml`.

Tudo que não vem de API vive lá, com `fonte` e `verificado_em` por registro,
separado do código de parsing. Um erro de digitação em dado manual não pode
passar em silêncio numa auditoria, então a validação é rígida e para o ETL.

Um registro só conta como VERIFICADO quando tem valor (ou uma situação
explícita como `sem_amostra`) E fonte E data de verificação. Linha com valor
nulo é marcador de "ainda não consultado": existe para facilitar o
preenchimento e aparece no dashboard como "sem dado carregado" — nunca como zero.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import yaml

from .config import DADOS_MANUAIS


class ErroManuais(ValueError):
    """`dados_manuais.yaml` tem registro inválido."""


def _data_iso(valor: Any, onde: str) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, dt.date):  # o YAML converte 2026-09-21 em date sozinho
        return valor.isoformat()
    try:
        return dt.date.fromisoformat(str(valor)).isoformat()
    except ValueError as exc:
        raise ErroManuais(f"{onde}: verificado_em deve ser AAAA-MM-DD, recebi {valor!r}") from exc


def _registro(r: dict[str, Any], campo: dict[str, Any] | None, onde: str, municipios: set[int]) -> dict[str, Any]:
    """Valida e normaliza um registro. `campo` é None para o MDE (percentual 0–100)."""
    if r.get("cod_ibge") not in municipios:
        raise ErroManuais(f"{onde}: cod_ibge {r.get('cod_ibge')!r} não é um dos municípios do ES")
    valor = r.get("valor")
    situacao = r.get("situacao")
    tipo = campo["tipo"] if campo else "percentual"

    if valor is not None:
        if tipo == "categorico":
            if valor not in campo["valores_validos"]:
                raise ErroManuais(f"{onde}: valor {valor!r} fora de {campo['valores_validos']}")
        elif isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ErroManuais(f"{onde}: valor deve ser numérico, recebi {valor!r}")
        elif tipo == "percentual" and not 0 <= valor <= 100:
            raise ErroManuais(f"{onde}: percentual fora de 0–100: {valor}")
        elif tipo == "moeda" and valor < 0:
            raise ErroManuais(f"{onde}: valor monetário negativo: {valor}")
        elif tipo == "quantidade" and (not isinstance(valor, int) or valor < 0):
            # Contagem (ex.: articuladores com bolsa). Zero é resposta válida — "verificou e não há".
            raise ErroManuais(f"{onde}: quantidade deve ser inteiro maior ou igual a zero, recebi {valor!r}")

    if situacao is not None and (not campo or situacao not in campo.get("situacoes", [])):
        raise ErroManuais(f"{onde}: situacao {situacao!r} não permitida para este campo")
    if situacao == "sem_amostra" and valor is not None:
        raise ErroManuais(f"{onde}: 'sem_amostra' não pode ter valor")
    if situacao == "informado" and valor is None:
        raise ErroManuais(f"{onde}: 'informado' exige valor")

    situacao_final = situacao or ("informado" if valor is not None else "nao_verificado")
    afirma_algo = situacao_final != "nao_verificado"
    serie = True if campo is None else campo.get("serie", False)
    ano = r.get("ano")
    if serie and afirma_algo and not isinstance(ano, int):
        raise ErroManuais(f"{onde}: campo em série exige 'ano' inteiro")

    fonte = (r.get("fonte") or "").strip() or None
    verificado_em = _data_iso(r.get("verificado_em"), onde)
    if afirma_algo and not (fonte and verificado_em):
        raise ErroManuais(f"{onde}: registro com valor/situação exige 'fonte' e 'verificado_em'")

    return {
        "cod_ibge": r["cod_ibge"],
        "ano": ano,
        "valor": valor,
        "situacao": situacao_final,
        "fonte": fonte,
        "verificado_em": verificado_em,
        "observacao": (r.get("observacao") or "").strip() or None,
        "verificado": afirma_algo,
    }


def _portal(r: dict[str, Any], onde: str, municipios: set[int]) -> dict[str, Any]:
    """Portal da transparência de um município (Nível 3: fora do escopo automatizável).

    Só um link verificado por alguém: URL http(s) e data de verificação. Nada é
    deduzido do nome do município — endereço inventado seria pior que nenhum.

    `api` é a documentação da API do portal, quando ele publica uma. Não vale como
    portal sozinha: o campo é um ponteiro para quem for buscar item e nota fiscal
    à mão, não uma fonte que o pipeline consulte.
    """
    if r.get("cod_ibge") not in municipios:
        raise ErroManuais(f"{onde}: cod_ibge {r.get('cod_ibge')!r} não é um dos municípios do ES")

    def _url(campo: str) -> str | None:
        v = (r.get(campo) or "").strip() or None
        if v is not None and not v.lower().startswith(("http://", "https://")):
            raise ErroManuais(f"{onde}: {campo} deve começar com http:// ou https://, recebi {v!r}")
        return v

    url, api = _url("url"), _url("api")
    verificado_em = _data_iso(r.get("verificado_em"), onde)
    if (url or api) and not verificado_em:
        raise ErroManuais(f"{onde}: portal com url ou api exige 'verificado_em'")
    return {"cod_ibge": r["cod_ibge"], "url": url, "api": api, "verificado_em": verificado_em,
            "observacao": (r.get("observacao") or "").strip() or None, "verificado": bool(url or api)}


def carregar(
    programas: list[dict[str, Any]],
    municipios: set[int],
    caminho: Path = DADOS_MANUAIS,
) -> dict[str, Any]:
    """Devolve `{"mde": [...], "programas": {programa: {campo: [registros]}}, "portais": [...]}`."""
    with open(caminho, encoding="utf-8") as f:
        bruto = yaml.safe_load(f) or {}

    portais = [_portal(r, f"nivel3.portais_transparencia[{i}]", municipios)
               for i, r in enumerate((bruto.get("nivel3") or {}).get("portais_transparencia") or [])]
    repetidos = {p["cod_ibge"] for p in portais if sum(q["cod_ibge"] == p["cod_ibge"] for q in portais) > 1}
    if repetidos:
        raise ErroManuais(f"nivel3.portais_transparencia: município repetido {sorted(repetidos)}")

    mde = [
        _registro(r, None, f"mde_aplicado_pct[{i}]", municipios)
        for i, r in enumerate((bruto.get("financiamento_geral") or {}).get("mde_aplicado_pct") or [])
    ]
    por_programa: dict[str, dict[str, list[dict[str, Any]]]] = {}
    declarados = {p["id"]: {c["id"]: c for c in p["campos"]} for p in programas}
    for pid, campos in (bruto.get("programas") or {}).items():
        if pid not in declarados:
            raise ErroManuais(f"programa {pid!r} em dados_manuais.yaml não existe em programas.yaml")
        por_programa[pid] = {}
        for cid, registros in (campos or {}).items():
            if cid not in declarados[pid]:
                raise ErroManuais(f"campo {pid}.{cid} em dados_manuais.yaml não existe em programas.yaml")
            if declarados[pid][cid]["origem"] != "manual":
                raise ErroManuais(f"campo {pid}.{cid} vem de API; não aceita dado manual")
            por_programa[pid][cid] = [
                _registro(r, declarados[pid][cid], f"{pid}.{cid}[{i}]", municipios)
                for i, r in enumerate(registros or [])
            ]
    return {"mde": mde, "programas": por_programa, "portais": portais}
