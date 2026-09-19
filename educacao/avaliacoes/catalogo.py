"""Catálogo das avaliações: o cabeçalho real casado com o dicionário.

Mesmo princípio do catálogo do Censo — **o arquivo manda, o dicionário
enriquece**. O cabeçalho publicado define quais colunas existem e em que ordem;
o dicionário acrescenta descrição, tipo e domínio. Quando os dois discordam, o
arquivo vence, e uma coluna do arquivo sem entrada no dicionário é erro, não
detalhe: `casar()` levanta exceção em vez de gravar um catálogo incompleto.

As quatro fontes chegam aqui de jeitos diferentes:

* **SAEB**, **ENEM** e **PAEBES** são CSV com dicionário `.xlsx`, e o casamento
  é por nome — ignorando caixa, porque o SAEB escreve ``Nivel_0_LP5`` no
  dicionário e ``NIVEL_0_LP5`` no arquivo;
* **IDEB** não tem dicionário. Suas colunas são interpretadas em `ideb.py` a
  partir do cabeçalho de três andares da planilha, e entram aqui já resolvidas.

O catálogo vai para `educacao/avaliacoes/catalog/<fonte>.json`, versionado, do
mesmo jeito que o do Censo.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from ..config.logging import configure_logger
from ..config.settings import AVALIACOES_DIR
from ..metadata.tipos import tipo_inteiro
from ..metadata.verificacao import Medicao, ajustar_tipo, medir_texto
from . import ideb as mod_ideb
from .dicionario import LAYOUTS, LinhaDicionario, ler

logger = configure_logger(__name__)

DIRETORIO_CATALOGO = Path(__file__).resolve().parent / "catalog"

#: Tipos declarados pelas fontes -> PostgreSQL. O Censo usa Num/Char/Data
#: (`metadata.tipos`); aqui aparecem ainda o vocabulário do PAEBES e o
#: `decimal`, que nenhuma fonte do Censo tem.
_TIPOS = {
    "num": None,  # depende do tamanho: resolvido por tipo_inteiro
    "char": "TEXT",
    "inteiro": "INTEGER",
    "texto": "TEXT",
    "decimal": "NUMERIC",
    "data": "TEXT",
}


#: O vocabulário do PAEBES traduzido para o do Censo, para que `ajustar_tipo`
#: — que só conhece Num/Char/Data — possa conferir o tipo contra os dados.
_EQUIVALENTE_CENSO = {
    "inteiro": "num",
    "decimal": "num",
    "texto": "char",
}


def tipo_postgres(tipo_original: str | None, tamanho: int | None) -> str:
    if not tipo_original:
        return "TEXT"
    chave = tipo_original.strip().casefold()
    if chave == "num":
        return tipo_inteiro(tamanho)
    if chave == "char":
        return f"VARCHAR({tamanho})" if tamanho and tamanho <= 255 else "TEXT"
    return _TIPOS.get(chave, "TEXT")


@dataclass(slots=True)
class VariavelAvaliacao:
    nome: str
    ordem: int
    tipo_postgres: str
    descricao: str | None = None
    tipo_original: str | None = None
    tamanho: int | None = None
    dominio: list[dict] = field(default_factory=list)
    ajuste_tipo: str | None = None

    @property
    def coluna(self) -> str:
        return self.nome.lower()

    def to_dict(self) -> dict:
        return {
            "nome": self.nome,
            "coluna": self.coluna,
            "ordem": self.ordem,
            "tipo_postgres": self.tipo_postgres,
            "tipo_original": self.tipo_original,
            "tamanho": self.tamanho,
            "descricao": self.descricao,
            "ajuste_tipo": self.ajuste_tipo,
            "dominio": self.dominio,
        }


@dataclass(slots=True)
class TabelaAvaliacao:
    fonte: str
    nome: str
    arquivo: str
    delimitador: str
    encoding: str
    edicoes: list[int] = field(default_factory=list)
    variaveis: list[VariavelAvaliacao] = field(default_factory=list)

    @property
    def tabela_raw(self) -> str:
        return f"{self.fonte}_{self.nome}"

    def to_dict(self) -> dict:
        return {
            "fonte": self.fonte,
            "nome": self.nome,
            "tabela_raw": self.tabela_raw,
            "arquivo": self.arquivo,
            "delimitador": self.delimitador,
            "encoding": self.encoding,
            "edicoes": self.edicoes,
            "total_variaveis": len(self.variaveis),
            "variaveis": [v.to_dict() for v in self.variaveis],
        }


# --------------------------------------------------------------- leitura bruta


def cabecalho_csv(caminho: Path, delimitador: str, encoding: str) -> list[str]:
    """Primeira linha do CSV, seja ele solto ou único membro de um ZIP."""

    if caminho.suffix.lower() == ".zip":
        with zipfile.ZipFile(caminho) as pacote:
            nome = next(n for n in pacote.namelist() if n.lower().endswith(".csv"))
            with pacote.open(nome) as arquivo:
                texto = io.TextIOWrapper(arquivo, encoding=encoding, newline="")
                linha = next(csv.reader(texto, delimiter=delimitador))
    else:
        with caminho.open(encoding=encoding, newline="") as arquivo:
            linha = next(csv.reader(arquivo, delimiter=delimitador))
    return [campo.strip().lstrip("﻿") for campo in linha]


def medir(caminho: Path, delimitador: str, encoding: str) -> dict[str, Medicao]:
    """Mede os dados reais de um CSV, esteja ele solto ou dentro de um ZIP."""

    if caminho.suffix.lower() == ".zip":
        with zipfile.ZipFile(caminho) as pacote:
            nome = next(n for n in pacote.namelist() if n.lower().endswith(".csv"))
            with pacote.open(nome) as arquivo:
                texto = io.TextIOWrapper(arquivo, encoding=encoding, newline="")
                return medir_texto(texto, delimitador)
    with caminho.open(encoding=encoding, newline="") as arquivo:
        return medir_texto(arquivo, delimitador)


def dicionario_de_zip(caminho: Path, fonte: str) -> list[LinhaDicionario]:
    """Lê o dicionário `.xlsx` que vive dentro do próprio pacote da fonte."""

    with zipfile.ZipFile(caminho) as pacote:
        nome = next(n for n in pacote.namelist() if n.lower().endswith(".xlsx"))
        conteudo = pacote.read(nome)
    temporario = DIRETORIO_CATALOGO / f".{fonte}_dicionario.xlsx"
    temporario.parent.mkdir(parents=True, exist_ok=True)
    temporario.write_bytes(conteudo)
    try:
        return ler(temporario, LAYOUTS[fonte])
    finally:
        temporario.unlink(missing_ok=True)


# ------------------------------------------------------------------- casamento


def casar(
    fonte: str,
    nome: str,
    arquivo: Path,
    cabecalho: list[str],
    dicionario: list[LinhaDicionario],
    delimitador: str,
    encoding: str,
    edicoes: list[int],
) -> TabelaAvaliacao:
    """Casa o cabeçalho real com o dicionário. Levanta se sobrar coluna órfã."""

    por_nome = {linha.nome.casefold(): linha for linha in dicionario}

    orfas = [coluna for coluna in cabecalho if coluna.casefold() not in por_nome]
    if orfas:
        raise ValueError(
            f"{fonte}/{nome}: {len(orfas)} coluna(s) do arquivo sem entrada no "
            f"dicionário: {orfas[:8]}"
        )

    # O tipo declarado não é confiável: o SAEB declara `Num` em
    # PC_FORMACAO_DOCENTE_FINAL, que traz 58.2. Vale o que está no arquivo.
    medicoes = medir(arquivo, delimitador, encoding)

    variaveis = []
    for ordem, coluna in enumerate(cabecalho, start=1):
        descrita = por_nome[coluna.casefold()]
        declarado = tipo_postgres(descrita.tipo_original, descrita.tamanho)
        medicao = medicoes.get(coluna)
        ajuste = None
        if medicao is not None:
            original = (descrita.tipo_original or "").strip().casefold()
            declarado, ajuste = ajustar_tipo(
                declarado, _EQUIVALENTE_CENSO.get(original, original), medicao
            )
            # Vírgula decimal não entra em NUMERIC pelo COPY. A coluna fica
            # TEXT em `raw`, fiel ao arquivo, e vira número na `stg` — a mesma
            # solução dada às datas SAS do Censo.
            if medicao.decimais_virgula:
                declarado = "TEXT"
                ajuste = (
                    f"{medicao.decimais_virgula:,} valores com vírgula decimal; "
                    "convertida para número na stg"
                )
            # Acima de 18 dígitos não há inteiro que garanta caber: `tipo_inteiro`
            # devolve BIGINT porque não tem o que oferecer acima dele. Os códigos
            # do PAEBES chegam a 19 dígitos, e NUMERIC não tem teto.
            elif declarado == "BIGINT" and medicao.max_digitos > 18:
                declarado = "NUMERIC(38)"
                ajuste = (
                    f"a amostra chega a {medicao.max_digitos} dígitos, "
                    "acima do que qualquer inteiro garante"
                )
        variaveis.append(
            VariavelAvaliacao(
                nome=coluna,
                ordem=ordem,
                tipo_postgres=declarado,
                descricao=descrita.descricao,
                tipo_original=descrita.tipo_original,
                tamanho=descrita.tamanho,
                dominio=[v.to_dict() for v in descrita.dominio],
                ajuste_tipo=ajuste,
            )
        )

    # Documentado mas não publicado: no PAEBES são os campos de identificação
    # pessoal, retirados antes da divulgação. Vale registrar, não falhar.
    presentes = {c.casefold() for c in cabecalho}
    nao_publicadas = [d.nome for d in dicionario if d.nome.casefold() not in presentes]
    if nao_publicadas:
        logger.info(
            "%s/%s: %d variável(is) no dicionário e ausentes do arquivo: %s",
            fonte,
            nome,
            len(nao_publicadas),
            ", ".join(nao_publicadas),
        )

    return TabelaAvaliacao(
        fonte=fonte,
        nome=nome,
        arquivo=arquivo.relative_to(AVALIACOES_DIR.parent.parent).as_posix(),
        delimitador=delimitador,
        encoding=encoding,
        edicoes=edicoes,
        variaveis=variaveis,
    )


# --------------------------------------------------------------- por fonte


def catalogar_saeb() -> list[TabelaAvaliacao]:
    tabelas = []
    for caminho in sorted((AVALIACOES_DIR / "saeb").glob("escola_*.csv")):
        ano = int(caminho.stem.split("_")[-1])
        # 2015 e 2017 saíram com vírgula; de 2019 em diante, ponto e vírgula.
        delimitador = "," if ano <= 2017 else ";"
        cabecalho = cabecalho_csv(caminho, delimitador, "latin-1")
        dicionario = ler(
            AVALIACOES_DIR / "saeb" / f"dicionario_{ano}.xlsx",
            LAYOUTS["saeb"],
            aba="TS_ESCOLA",
        )
        tabelas.append(
            casar("saeb", f"escola_{ano}", caminho, cabecalho, dicionario,
                  delimitador, "latin-1", [ano])
        )
    return tabelas


def catalogar_enem() -> list[TabelaAvaliacao]:
    caminho = AVALIACOES_DIR / "enem" / "enem_por_escola_2005_2015.zip"
    cabecalho = cabecalho_csv(caminho, ";", "latin-1")
    dicionario = dicionario_de_zip(caminho, "enem")
    return [
        casar("enem", "por_escola", caminho, cabecalho, dicionario,
              ";", "latin-1", list(range(2005, 2016)))
    ]


def catalogar_paebes() -> list[TabelaAvaliacao]:
    caminho = AVALIACOES_DIR / "paebes" / "paebes_2025.zip"
    cabecalho = cabecalho_csv(caminho, ";", "latin-1")
    dicionario = dicionario_de_zip(caminho, "paebes")
    return [
        casar("paebes", "aluno_2025", caminho, cabecalho, dicionario,
              ";", "latin-1", [2025])
    ]


def catalogar_ideb() -> list[TabelaAvaliacao]:
    """O IDEB não tem dicionário: as colunas vêm resolvidas de `ideb.py`."""

    tabelas = []
    for caminho in mod_ideb.arquivos("escolas") + mod_ideb.arquivos("municipios"):
        problemas = mod_ideb.verificar_series(caminho)
        if problemas:
            raise ValueError(f"ideb/{caminho.stem}: {problemas}")

        workbook, worksheet = mod_ideb.abrir_planilha(caminho)
        try:
            cabecalho = mod_ideb.localizar_cabecalho(worksheet)
        finally:
            workbook.close()

        variaveis = [
            VariavelAvaliacao(
                nome=nome,
                ordem=indice + 1,
                tipo_postgres="TEXT",
                descricao="Coluna de identificação da planilha do IDEB",
            )
            for nome, indice in sorted(cabecalho.identificacao.items(), key=lambda p: p[1])
        ]
        for coluna in cabecalho.medidas:
            qualificador = (
                f"{coluna.serie}ª série"
                if coluna.serie
                else (coluna.disciplina or "total da etapa")
            )
            variaveis.append(
                VariavelAvaliacao(
                    nome=coluna.nome,
                    ordem=coluna.indice + 1,
                    tipo_postgres="NUMERIC",
                    descricao=f"{coluna.medida} — {qualificador} — edição {coluna.edicao}",
                )
            )
        variaveis.sort(key=lambda v: v.ordem)

        tabelas.append(
            TabelaAvaliacao(
                fonte="ideb",
                nome=caminho.stem,
                arquivo=caminho.relative_to(AVALIACOES_DIR.parent.parent).as_posix(),
                delimitador="",
                encoding="",
                edicoes=sorted({c.edicao for c in cabecalho.medidas}),
                variaveis=variaveis,
            )
        )
    return tabelas


CATALOGADORES = {
    "ideb": catalogar_ideb,
    "enem": catalogar_enem,
    "saeb": catalogar_saeb,
    "paebes": catalogar_paebes,
}


def construir(fontes: list[str] | None = None) -> dict[str, list[TabelaAvaliacao]]:
    return {
        fonte: funcao()
        for fonte, funcao in CATALOGADORES.items()
        if not fontes or fonte in fontes
    }


def gravar(catalogos: dict[str, list[TabelaAvaliacao]]) -> None:
    DIRETORIO_CATALOGO.mkdir(parents=True, exist_ok=True)
    for fonte, tabelas in catalogos.items():
        destino = DIRETORIO_CATALOGO / f"{fonte}.json"
        destino.write_text(
            json.dumps(
                {"fonte": fonte, "tabelas": [t.to_dict() for t in tabelas]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        total = sum(len(t.variaveis) for t in tabelas)
        logger.info(
            "catalog/%s.json — %d tabela(s), %d variáveis", fonte, len(tabelas), total
        )


def carregar(fonte: str) -> dict:
    caminho = DIRETORIO_CATALOGO / f"{fonte}.json"
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} não existe; rode python -m educacao.avaliacoes.catalogo"
        )
    return json.loads(caminho.read_text(encoding="utf-8"))


def main() -> None:
    import argparse
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Constrói o catálogo das avaliações")
    parser.add_argument("--fonte", action="append", help="Restringe a uma fonte")
    args = parser.parse_args()

    gravar(construir(args.fonte))


if __name__ == "__main__":
    main()
