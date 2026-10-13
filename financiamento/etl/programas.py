"""Carrega e valida `programas.yaml` — a config declarativa dos programas."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config import PROGRAMAS

ACESSOS = {"api", "manual", "hibrido"}
GRANULARIDADES = {"municipio", "escola", "estado"}
TIPOS_CAMPO = {"categorico", "moeda", "percentual", "quantidade"}
ORIGENS = {"api", "manual"}
_OBRIGATORIAS_PROGRAMA = ("id", "nome", "fundo_repasse", "acesso", "granularidade", "indicador_meta", "campos")


class ErroProgramas(ValueError):
    """`programas.yaml` está malformado."""


def carregar(caminho: Path = PROGRAMAS) -> list[dict[str, Any]]:
    """Lista de programas validados (dicts prontos para virar JSON)."""
    with open(caminho, encoding="utf-8") as f:
        bruto = yaml.safe_load(f) or {}
    programas = bruto.get("programas") or []
    ids: set[str] = set()
    for p in programas:
        _validar_programa(p, ids)
    return programas


def _validar_programa(p: dict[str, Any], ids: set[str]) -> None:
    for chave in _OBRIGATORIAS_PROGRAMA:
        if chave not in p:
            raise ErroProgramas(f"programa {p.get('id', '?')!r}: falta a chave {chave!r}")
    if p["id"] in ids:
        raise ErroProgramas(f"programa repetido: {p['id']!r}")
    ids.add(p["id"])
    if p["acesso"] not in ACESSOS:
        raise ErroProgramas(f"{p['id']}: acesso {p['acesso']!r} fora de {sorted(ACESSOS)}")
    if p["granularidade"] not in GRANULARIDADES:
        raise ErroProgramas(f"{p['id']}: granularidade {p['granularidade']!r} fora de {sorted(GRANULARIDADES)}")

    campos: set[str] = set()
    for c in p["campos"]:
        if c.get("id") in campos:
            raise ErroProgramas(f"{p['id']}: campo repetido {c.get('id')!r}")
        campos.add(c.get("id"))
        if c.get("tipo") not in TIPOS_CAMPO:
            raise ErroProgramas(f"{p['id']}.{c.get('id')}: tipo {c.get('tipo')!r} fora de {sorted(TIPOS_CAMPO)}")
        if c.get("origem") not in ORIGENS:
            raise ErroProgramas(f"{p['id']}.{c.get('id')}: origem {c.get('origem')!r} fora de {sorted(ORIGENS)}")
        if c["tipo"] == "categorico" and not c.get("valores_validos"):
            raise ErroProgramas(f"{p['id']}.{c['id']}: campo categórico exige valores_validos")
        if c.get("kpi"):
            if c["kpi"].get("valor") not in (c.get("valores_validos") or []):
                raise ErroProgramas(f"{p['id']}.{c['id']}: kpi.valor precisa estar em valores_validos")
            if not c["kpi"].get("rotulo"):
                raise ErroProgramas(f"{p['id']}.{c['id']}: kpi exige 'rotulo'")
        rotulos = c.get("rotulos_valores")
        if rotulos and set(rotulos) != set(c.get("valores_validos") or []):
            raise ErroProgramas(f"{p['id']}.{c['id']}: rotulos_valores deve cobrir exatamente valores_validos")
    if p["indicador_meta"].get("id") not in campos:
        raise ErroProgramas(f"{p['id']}: indicador_meta.id precisa ser um dos campos")

    # Checklist de governança (opcional): itens que o auditor marca em campo. Não é dado
    # importado — é o roteiro de verificação, declarado aqui para não virar código.
    ids_check: set[str] = set()
    for item in p.get("checklist_governanca") or []:
        if not item.get("id") or not item.get("texto"):
            raise ErroProgramas(f"{p['id']}: item do checklist exige 'id' e 'texto'")
        if item["id"] in ids_check:
            raise ErroProgramas(f"{p['id']}: item do checklist repetido {item['id']!r}")
        ids_check.add(item["id"])
