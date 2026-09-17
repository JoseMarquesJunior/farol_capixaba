"""Modelo canônico: a união das variáveis de todos os anos, com sua vigência.

Os catálogos por ano dizem o que existe em cada arquivo. Para harmonizar os
anos numa camada única (`stg`) falta a visão transversal: quando cada variável
entrou, quando saiu, em que tabela do desenho de 2025 ela vive e se o tipo
mudou no meio do caminho.

Duas coisas que só aparecem aqui:

* variáveis **descontinuadas** — presentes nos arquivos até certo ano e
  ausentes do dicionário de 2025, como `IN_FUND` e `IN_EJA_FUND`, que não têm
  para onde apontar no modelo novo sem um de-para manual;
* variáveis cujo **tipo mudou** entre anos, que quebram uma tabela unificada
  se forem empilhadas sem conversão.

Uso::

    python -m educacao.metadata.canonico
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from ..config.logging import configure_logger
from .catalogo import DIRETORIO_CATALOGO
from .fontes import ANOS

logger = configure_logger(__name__)

#: Ano cujo desenho de tabelas serve de alvo para a camada `stg`.
ANO_REFERENCIA = 2025


def carregar_catalogos(diretorio: Path = DIRETORIO_CATALOGO) -> dict[int, dict]:
    catalogos = {}
    for ano in ANOS:
        arquivo = diretorio / f"{ano}.json"
        if arquivo.exists():
            catalogos[ano] = json.loads(arquivo.read_text(encoding="utf-8"))
    if not catalogos:
        raise FileNotFoundError(
            f"Nenhum catálogo em {diretorio}. Rode `python -m educacao.metadata.catalogo`."
        )
    return catalogos


def montar(diretorio: Path = DIRETORIO_CATALOGO) -> dict:
    catalogos = carregar_catalogos(diretorio)

    descricao: dict[str, str] = {}
    tabelas: dict[str, set[str]] = defaultdict(set)
    tabela_referencia: dict[str, str] = {}
    presenca: dict[str, set[int]] = defaultdict(set)
    tipos: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))

    for ano in sorted(catalogos):
        for tabela in catalogos[ano]["tabelas"]:
            for variavel in tabela["variaveis"]:
                nome = variavel["nome"]
                presenca[nome].add(ano)
                tabelas[nome].add(tabela["nome"])
                tipos[nome][variavel["tipo_postgres"]].append(ano)
                if variavel["descricao"]:
                    descricao[nome] = variavel["descricao"]
                if ano == ANO_REFERENCIA:
                    tabela_referencia[nome] = tabela["nome"]

    variaveis = []
    for nome in sorted(presenca):
        anos = sorted(presenca[nome])
        usados = tipos[nome]
        # Tipo vigente: o do ano mais recente em que a variável aparece.
        vigente = max(usados.items(), key=lambda item: max(item[1]))[0]
        variaveis.append(
            {
                "nome": nome,
                "coluna": nome.lower(),
                "descricao": descricao.get(nome),
                "tabelas": sorted(tabelas[nome]),
                "tabela_referencia": tabela_referencia.get(nome),
                "descontinuada": ANO_REFERENCIA not in presenca[nome],
                "primeiro_ano": anos[0],
                "ultimo_ano": anos[-1],
                "anos_presentes": anos,
                "tipo_postgres": vigente,
                "tipos_por_ano": (
                    {tipo: sorted(lista) for tipo, lista in usados.items()}
                    if len(usados) > 1
                    else None
                ),
            }
        )

    return {
        "ano_referencia": ANO_REFERENCIA,
        "anos": sorted(catalogos),
        "total_variaveis": len(variaveis),
        "descontinuadas": sum(1 for v in variaveis if v["descontinuada"]),
        "com_tipo_variavel": sum(1 for v in variaveis if v["tipos_por_ano"]),
        "variaveis": variaveis,
    }


def gravar(modelo: dict, diretorio: Path = DIRETORIO_CATALOGO) -> Path:
    diretorio.mkdir(parents=True, exist_ok=True)
    arquivo = diretorio / "canonical.json"
    arquivo.write_text(
        json.dumps(modelo, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return arquivo


def main() -> None:
    modelo = montar()
    arquivo = gravar(modelo)
    logger.info(
        "%s: %s variáveis, %s descontinuadas, %s com tipo variável entre anos",
        arquivo.name,
        modelo["total_variaveis"],
        modelo["descontinuadas"],
        modelo["com_tipo_variavel"],
    )


if __name__ == "__main__":
    main()
