"""Estruturas do catálogo de metadados do Censo Escolar."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ValorDominio:
    """Par código/rótulo extraído da coluna 'Categoria' do dicionário.

    `codigo` é None nas linhas de ressalva, como
    "- Não aplicável para escolas públicas".
    """

    codigo: str | None
    rotulo: str

    def to_dict(self) -> dict:
        return {"codigo": self.codigo, "rotulo": self.rotulo}


@dataclass(slots=True)
class Variavel:
    """Uma coluna de um arquivo de microdados, na ordem em que aparece nele."""

    nome: str
    ordem: int
    descricao: str | None
    tipo_original: str | None
    tamanho: int | None
    tipo_postgres: str
    dominio: list[ValorDominio] = field(default_factory=list)
    nota: str | None = None
    anos_coleta: list[int] = field(default_factory=list)
    ajuste_tipo: str | None = None

    @property
    def coluna(self) -> str:
        """Nome da coluna no PostgreSQL."""
        return self.nome.lower()

    def to_dict(self) -> dict:
        return {
            "nome": self.nome,
            "coluna": self.coluna,
            "ordem": self.ordem,
            "descricao": self.descricao,
            "tipo_original": self.tipo_original,
            "tamanho": self.tamanho,
            "tipo_postgres": self.tipo_postgres,
            "ajuste_tipo": self.ajuste_tipo,
            "nota": self.nota,
            "anos_coleta": self.anos_coleta,
            "dominio": [valor.to_dict() for valor in self.dominio],
        }


@dataclass(slots=True)
class Tabela:
    """Um arquivo de microdados de um ano, já casado com sua aba no dicionário."""

    ano: int
    nome: str
    arquivo: Path
    aba: str
    delimitador: str
    encoding: str
    variaveis: list[Variavel] = field(default_factory=list)

    @property
    def tabela_raw(self) -> str:
        return f"{self.nome}_{self.ano}"

    def to_dict(self, raiz: Path) -> dict:
        return {
            "nome": self.nome,
            "tabela_raw": self.tabela_raw,
            "arquivo": self.arquivo.relative_to(raiz).as_posix(),
            "aba": self.aba,
            "delimitador": self.delimitador,
            "encoding": self.encoding,
            "total_variaveis": len(self.variaveis),
            "variaveis": [variavel.to_dict() for variavel in self.variaveis],
        }


@dataclass(slots=True)
class CatalogoAno:
    """Catálogo completo de um ano do Censo."""

    ano: int
    dicionario: Path
    tabelas: list[Tabela] = field(default_factory=list)

    def to_dict(self, raiz: Path) -> dict:
        return {
            "ano": self.ano,
            "dicionario": self.dicionario.relative_to(raiz).as_posix(),
            "tabelas": [tabela.to_dict(raiz) for tabela in self.tabelas],
        }
