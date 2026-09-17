"""Leitura e validação do de-para das variáveis descontinuadas.

O de-para é escrito à mão (é julgamento semântico, não dedução), então precisa
de uma trava: toda relação declarada aqui é conferida contra o catálogo. Se o
INEP republicar um dicionário, ou se alguém escrever um nome errado, a
divergência aparece em `validar()` em vez de virar coluna nula no meio da stg.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .catalogo import DIRETORIO_CATALOGO
from .canonico import ANO_REFERENCIA, carregar_catalogos

ARQUIVO_DE_PARA = Path(__file__).resolve().parent / "de_para.yml"


@dataclass(slots=True)
class Derivada:
    nome: str
    origem: str
    tabela: str
    expressao: str

    @property
    def sql(self) -> str:
        return self.expressao.format(origem=self.origem.lower())


@dataclass(slots=True)
class TipoHarmonizado:
    nome: str
    tipo: str
    conversao: str
    motivo: str

    def sql(self, coluna: str) -> str:
        return self.conversao.strip().format(col=coluna)


@dataclass(slots=True)
class DePara:
    renomeadas: dict[str, str] = field(default_factory=dict)
    derivadas: dict[str, Derivada] = field(default_factory=dict)
    sem_equivalente: dict[str, str] = field(default_factory=dict)
    tipos_harmonizados: dict[str, TipoHarmonizado] = field(default_factory=dict)

    @property
    def cobertas(self) -> set[str]:
        return set(self.renomeadas) | set(self.derivadas) | set(self.sem_equivalente)

    def canonizar(self, nome: str) -> str:
        """Nome pelo qual a variável é conhecida na stg."""
        return self.renomeadas.get(nome, nome)


def carregar(caminho: Path = ARQUIVO_DE_PARA) -> DePara:
    bruto = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    padrao = bruto.get("expressao_padrao", "({origem} > 0)::smallint")

    derivadas = {
        nome: Derivada(
            nome=nome,
            origem=definicao["origem"],
            tabela=definicao["tabela"],
            expressao=definicao.get("expressao", padrao),
        )
        for nome, definicao in (bruto.get("derivadas") or {}).items()
    }

    sem_equivalente = {
        nome: grupo["motivo"].strip()
        for grupo in (bruto.get("sem_equivalente") or [])
        for nome in grupo["variaveis"]
    }

    tipos = {
        nome: TipoHarmonizado(
            nome=nome,
            tipo=definicao["tipo"],
            conversao=definicao["conversao"],
            motivo=definicao["motivo"].strip(),
        )
        for nome, definicao in (bruto.get("tipos_harmonizados") or {}).items()
    }

    return DePara(
        renomeadas=dict(bruto.get("renomeadas") or {}),
        derivadas=derivadas,
        sem_equivalente=sem_equivalente,
        tipos_harmonizados=tipos,
    )


def validar(
    de_para: DePara | None = None, diretorio: Path = DIRETORIO_CATALOGO
) -> list[str]:
    """Confere o de-para contra o catálogo. Devolve a lista de problemas."""

    de_para = de_para or carregar()
    catalogos = carregar_catalogos(diretorio)
    problemas: list[str] = []

    # Nomes existentes em cada ano, e a tabela de cada variável em 2025.
    por_ano: dict[int, set[str]] = {}
    tabela_2025: dict[str, str] = {}
    for ano, catalogo in catalogos.items():
        nomes = set()
        for tabela in catalogo["tabelas"]:
            for variavel in tabela["variaveis"]:
                nomes.add(variavel["nome"])
                if ano == ANO_REFERENCIA:
                    tabela_2025[variavel["nome"]] = tabela["nome"]
        por_ano[ano] = nomes

    descontinuadas = {
        nome
        for ano, nomes in por_ano.items()
        for nome in nomes
        if nome not in por_ano.get(ANO_REFERENCIA, set())
    }

    duplicadas = (
        (set(de_para.renomeadas) & set(de_para.derivadas))
        | (set(de_para.renomeadas) & set(de_para.sem_equivalente))
        | (set(de_para.derivadas) & set(de_para.sem_equivalente))
    )
    for nome in sorted(duplicadas):
        problemas.append(f"{nome}: declarada em mais de uma seção")

    for nome in sorted(de_para.cobertas - descontinuadas):
        problemas.append(f"{nome}: no de-para mas não é descontinuada")

    for nome in sorted(descontinuadas - de_para.cobertas):
        problemas.append(f"{nome}: descontinuada e ausente do de-para")

    for antigo, novo in sorted(de_para.renomeadas.items()):
        if novo not in tabela_2025:
            problemas.append(f"{antigo} -> {novo}: destino não existe em {ANO_REFERENCIA}")

    for nome, derivada in sorted(de_para.derivadas.items()):
        tabela = tabela_2025.get(derivada.origem)
        if tabela is None:
            problemas.append(
                f"{nome}: origem {derivada.origem} não existe em {ANO_REFERENCIA}"
            )
        elif tabela != derivada.tabela:
            problemas.append(
                f"{nome}: origem {derivada.origem} está em '{tabela}', "
                f"não em '{derivada.tabela}'"
            )

    return problemas


def main() -> int:
    de_para = carregar()
    problemas = validar(de_para)

    print(
        f"  renomeadas={len(de_para.renomeadas)} "
        f"derivadas={len(de_para.derivadas)} "
        f"sem_equivalente={len(de_para.sem_equivalente)} "
        f"total={len(de_para.cobertas)}"
    )
    for problema in problemas:
        print(f"  FALHA {problema}")
    if not problemas:
        print("  de-para íntegro contra o catálogo")
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
