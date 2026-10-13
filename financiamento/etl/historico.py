"""Versões da extração: reexecutar e comparar com uma anterior.

Cada execução do pipeline grava em `dados/processado/historico/<AAAAMMDDTHHMMSSZ>/`
um retrato do dataset consolidado (`consolidado.csv.gz`) e um `manifesto.json`
(exercícios, situação de cada fonte, contagens, SHA-256). Comparar duas versões
casa os registros pela chave estável — município, exercício, período,
indicador e detalhe — e diz o que é novo, o que sumiu, o que mudou de valor e o
que foi só reextraído (mesmo valor, coleta mais nova)::

    python -m financiamento.etl.comparar                     # as duas últimas versões
    python -m financiamento.etl.comparar --antes 20260922T120000Z --depois 20260930T090000Z
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .config import PROCESSADO

HISTORICO = PROCESSADO / "historico"
CHAVE = ["cod_ibge", "ano", "periodo", "indicador", "detalhe"]
TOLERANCIA = 0.005  # diferença de valor abaixo disto é arredondamento, não mudança


def gravar_versao(consolidado: pd.DataFrame, manifesto: dict[str, Any], pasta: Path = HISTORICO) -> str:
    """Retrato do consolidado desta execução. Devolve o id da versão."""
    versao = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino = pasta / versao
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / "consolidado.csv.gz"
    consolidado.to_csv(arquivo, index=False, encoding="utf-8", compression={"method": "gzip", "mtime": 0})
    corpo = {"versao": versao, "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "registros": int(len(consolidado)), "sha256_consolidado": hashlib.sha256(arquivo.read_bytes()).hexdigest(),
             **manifesto}
    (destino / "manifesto.json").write_text(json.dumps(corpo, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return versao


def versoes(pasta: Path = HISTORICO) -> list[str]:
    return sorted(p.name for p in pasta.glob("*T*Z") if (p / "consolidado.csv.gz").exists())


def ler(versao: str, pasta: Path = HISTORICO) -> pd.DataFrame:
    return pd.read_csv(pasta / versao / "consolidado.csv.gz", dtype={"periodo": "string", "detalhe": "string"})


def comparar(antes: pd.DataFrame, depois: pd.DataFrame, tolerancia: float = TOLERANCIA) -> pd.DataFrame:
    """Registro a registro: novo, removido, alterado, reextraído (mesmo valor) ou igual."""
    colunas = CHAVE + ["valor", "obtido_em", "rotulo", "ente"]

    def preparar(df: pd.DataFrame) -> pd.DataFrame:
        d = df.reindex(columns=colunas).copy()
        for c in ("periodo", "detalhe"):
            d[c] = d[c].astype("string").fillna("")
        return d.drop_duplicates(CHAVE, keep="last")

    m = preparar(antes).merge(preparar(depois), on=CHAVE, how="outer", suffixes=("_antes", "_depois"), indicator=True)
    dif = m["valor_depois"] - m["valor_antes"]
    situacao = pd.Series("igual", index=m.index)
    situacao[m["_merge"] == "right_only"] = "novo"
    situacao[m["_merge"] == "left_only"] = "removido"
    ambos = m["_merge"] == "both"
    situacao[ambos & (dif.abs() > tolerancia)] = "alterado"
    situacao[ambos & (dif.abs() <= tolerancia) & (m["obtido_em_antes"] != m["obtido_em_depois"])] = "reextraido"
    m["situacao"] = situacao
    m["diferenca"] = dif.round(4)
    m["diferenca_pct"] = (100 * dif / m["valor_antes"].where(m["valor_antes"] != 0)).round(4)
    m["rotulo"] = m["rotulo_depois"].fillna(m["rotulo_antes"])
    m["ente"] = m["ente_depois"].fillna(m["ente_antes"])
    return m[CHAVE + ["ente", "rotulo", "situacao", "valor_antes", "valor_depois", "diferenca", "diferenca_pct",
                      "obtido_em_antes", "obtido_em_depois"]]


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Compara duas versões do dataset consolidado.")
    p.add_argument("--antes", help="id da versão anterior (padrão: a penúltima)")
    p.add_argument("--depois", help="id da versão nova (padrão: a última)")
    args = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # console do Windows (cp1252) não pode derrubar o comando
        sys.stdout.reconfigure(errors="replace")
    todas = versoes()
    if len(todas) < 2 and not (args.antes and args.depois):
        print(f"é preciso ao menos duas versões em {HISTORICO} (há {len(todas)})", file=sys.stderr)
        return 1
    antes, depois = args.antes or todas[-2], args.depois or todas[-1]
    r = comparar(ler(antes), ler(depois))
    saida = HISTORICO / f"comparacao_{antes}_{depois}.csv"
    r[r["situacao"] != "igual"].to_csv(saida, index=False, encoding="utf-8")
    print(f"{antes} -> {depois}")
    print(r["situacao"].value_counts().to_string())
    mudou = r[r["situacao"].isin(["alterado", "novo", "removido"])]
    if not mudou.empty:
        print("\npor indicador:")
        print(mudou.groupby(["indicador", "situacao"]).size().unstack(fill_value=0).to_string())
    print(f"\ndetalhe em {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
