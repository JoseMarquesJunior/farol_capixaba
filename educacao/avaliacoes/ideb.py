"""Leitura das planilhas do IDEB, que não têm dicionário.

As planilhas são **largas por edição**: uma linha por escola e, para cada uma
das onze edições, um bloco de colunas com taxa de aprovação, nota do SAEB e o
IDEB em si. Este módulo as converte em registros longos
``(escola, edição, medida, qualificador, valor)``.

O cabeçalho é de três andares: uma linha de grupo (``Taxa de Aprovação - 2005``),
uma linha de rótulo por coluna (``3º``, ``Matemática``) e uma linha de nomes de
máquina (``VL_APROVACAO_2005_2``). Nenhum dos três basta sozinho, e a divisão
de autoridade entre eles **não é uma questão de estilo**:

* o **nome de máquina** manda na medida e no ano da edição. O rótulo de grupo
  não serve para o ano porque vem com nota de rodapé colada — a edição de 2021
  aparece como ``Nota SAEB - 20211`` e como ``IDEB 20211 (N x P)``;

* o **rótulo humano** manda na série. O sufixo do nome de máquina é posição
  ordinal dentro da etapa, não número de série, e em nenhuma etapa os dois
  coincidem::

      anos finais    VL_APROVACAO_2005_1  ->  6º ano
      ensino médio   VL_APROVACAO_2017_1  ->  1ª série

  Nos anos iniciais é pior, porque só há quatro sufixos numéricos para cinco
  séries: o INEP manteve a numeração do fundamental de oito anos e pendurou o
  1º ano na coluna ``_SI``, que em toda outra etapa não existe::

      VL_APROVACAO_2005_SI_4  ->  1º ao 5º ano (total)
      VL_APROVACAO_2005_SI    ->  1º ano
      VL_APROVACAO_2005_1     ->  2º ano        <- e não o 1º
      VL_APROVACAO_2005_4     ->  5º ano

  Ler o sufixo em vez do rótulo deslocaria a série inteira dos anos iniciais
  sem produzir nenhum erro visível. `verificar_series()` trava isso conferindo,
  edição a edição, se as séries lidas são exatamente as que a etapa deve ter.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from ..config.logging import configure_logger
from ..config.settings import AVALIACOES_DIR

logger = configure_logger(__name__)

LINHAS_BUSCA = 14
AUSENTE = "-"

_MEDIDAS = (
    ("VL_APROVACAO_", "aprovacao"),
    ("VL_INDICADOR_REND_", "indicador_rendimento"),
    ("VL_NOTA_MATEMATICA_", "nota"),
    ("VL_NOTA_PORTUGUES_", "nota"),
    ("VL_NOTA_MEDIA_", "nota"),
    ("VL_OBSERVADO_", "ideb_observado"),
    ("VL_PROJECAO_", "ideb_projecao"),
)

_DISCIPLINA = {
    "VL_NOTA_MATEMATICA_": "matematica",
    "VL_NOTA_PORTUGUES_": "portugues",
    "VL_NOTA_MEDIA_": "media_padronizada",
}

#: Rótulos que designam o total da etapa, não uma série.
_TOTAIS = ("total", "1º ao 5º ano", "6º a 9º ano", "1ª a 4ª série", "5ª a 8ª série")

_SERIE = re.compile(r"^\s*(\d+)\s*[ºª°]")
_ANO = re.compile(r"(20\d\d)")
_IDENTIFICACAO = ("SG_UF", "CO_MUNICIPIO", "NO_MUNICIPIO", "ID_ESCOLA", "NO_ESCOLA", "REDE")


@dataclass(frozen=True, slots=True)
class ColunaIdeb:
    """Uma coluna de medida da planilha, já interpretada."""

    indice: int
    nome: str
    medida: str
    edicao: int
    #: Série avaliada; None quando a coluna é o total da etapa.
    serie: int | None = None
    disciplina: str | None = None
    rotulo: str | None = None


@dataclass(slots=True)
class Cabecalho:
    linha_grupo: int
    linha_maquina: int
    identificacao: dict[str, int]
    medidas: list[ColunaIdeb]

    @property
    def primeira_linha_dados(self) -> int:
        return self.linha_maquina + 1


def _texto(valor) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _serie_do_rotulo(rotulo: str | None) -> int | None:
    """Número da série a partir do rótulo humano; None quando é o total."""

    if not rotulo:
        return None
    limpo = rotulo.strip().casefold()
    if any(limpo.startswith(t.casefold()) for t in _TOTAIS):
        return None
    achado = _SERIE.match(rotulo.strip())
    return int(achado.group(1)) if achado else None


def _classificar(indice: int, nome: str, rotulo: str | None) -> ColunaIdeb | None:
    for prefixo, medida in _MEDIDAS:
        if not nome.startswith(prefixo):
            continue
        ano = _ANO.search(nome)
        if not ano:
            raise ValueError(f"coluna '{nome}' sem ano de edição no nome")
        return ColunaIdeb(
            indice=indice,
            nome=nome,
            medida=medida,
            edicao=int(ano.group(1)),
            serie=_serie_do_rotulo(rotulo) if medida == "aprovacao" else None,
            disciplina=_DISCIPLINA.get(prefixo),
            rotulo=rotulo,
        )
    return None


def localizar_cabecalho(worksheet) -> Cabecalho:
    """Acha as três linhas do cabeçalho e interpreta cada coluna de medida."""

    linhas = list(worksheet.iter_rows(max_row=LINHAS_BUSCA, values_only=True))

    linha_grupo = linha_maquina = None
    for numero, linha in enumerate(linhas, start=1):
        textos = [t for t in (_texto(v) for v in linha) if t]
        if linha_grupo is None and any(t.startswith("Sigla da UF") for t in textos):
            linha_grupo = numero
        if any(t.startswith("VL_") for t in textos):
            linha_maquina = numero
            break

    if linha_grupo is None or linha_maquina is None:
        raise ValueError(
            f"'{worksheet.title}': cabeçalho não localizado "
            f"(grupo={linha_grupo}, máquina={linha_maquina})"
        )

    maquina = linhas[linha_maquina - 1]
    # O rótulo de cada coluna é o último valor preenchido entre o grupo e a
    # linha de máquina: o bloco de aprovação usa uma linha, o de nota usa outra.
    intermediarias = linhas[linha_grupo : linha_maquina - 1]

    identificacao: dict[str, int] = {}
    medidas: list[ColunaIdeb] = []
    for indice, celula in enumerate(maquina):
        nome = _texto(celula)
        if not nome:
            continue
        if nome in _IDENTIFICACAO:
            identificacao[nome] = indice
            continue
        rotulo = None
        for linha in intermediarias:
            if indice < len(linha) and (valor := _texto(linha[indice])):
                rotulo = valor
        coluna = _classificar(indice, nome, rotulo)
        if coluna is not None:
            medidas.append(coluna)

    faltando = [c for c in ("SG_UF", "CO_MUNICIPIO") if c not in identificacao]
    if faltando:
        raise ValueError(f"'{worksheet.title}': sem as colunas {faltando}")

    return Cabecalho(linha_grupo, linha_maquina, identificacao, medidas)


def abrir_planilha(caminho: Path):
    """Abre a única planilha de dentro do ZIP do IDEB."""

    with zipfile.ZipFile(caminho) as pacote:
        nomes = [n for n in pacote.namelist() if n.lower().endswith(".xlsx")]
        if len(nomes) != 1:
            raise ValueError(f"{caminho.name}: esperava 1 .xlsx, achei {len(nomes)}")
        conteudo = pacote.read(nomes[0])
    workbook = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    return workbook, workbook[workbook.sheetnames[0]]


#: Séries que cada etapa tem de apresentar, por edição.
SERIES_ESPERADAS = {
    "anos_iniciais": {1, 2, 3, 4, 5},
    "anos_finais": {6, 7, 8, 9},
    "ensino_medio": {1, 2, 3, 4},
}


def verificar_series(caminho: Path) -> list[str]:
    """Confere, por edição, se as séries lidas são as que a etapa deve ter.

    É a trava contra uma mudança de layout: se o INEP reordenar as colunas ou
    acrescentar uma série, o conjunto deixa de bater e a carga para, em vez de
    gravar silenciosamente a série errada.
    """

    esperadas = SERIES_ESPERADAS[etapa_do_arquivo(caminho)]
    workbook, worksheet = abrir_planilha(caminho)
    try:
        cabecalho = localizar_cabecalho(worksheet)
    finally:
        workbook.close()

    por_edicao: dict[int, set[int]] = {}
    totais: set[int] = set()
    for coluna in cabecalho.medidas:
        if coluna.medida != "aprovacao":
            continue
        if coluna.serie is None:
            totais.add(coluna.edicao)
        else:
            por_edicao.setdefault(coluna.edicao, set()).add(coluna.serie)

    problemas = []
    for edicao in sorted(por_edicao):
        if por_edicao[edicao] != esperadas:
            faltam = sorted(esperadas - por_edicao[edicao])
            sobram = sorted(por_edicao[edicao] - esperadas)
            problemas.append(
                f"edição {edicao}: séries {sorted(por_edicao[edicao])} "
                f"(faltam {faltam}, sobram {sobram})"
            )
        if edicao not in totais:
            problemas.append(f"edição {edicao}: sem a coluna de total da etapa")
    return problemas


def arquivos(alvo: str = "escolas") -> list[Path]:
    return sorted((AVALIACOES_DIR / "ideb").glob(f"*_{alvo}_*.zip"))


def etapa_do_arquivo(caminho: Path) -> str:
    nome = caminho.stem
    for etapa in ("anos_iniciais", "anos_finais", "ensino_medio"):
        if nome.startswith(etapa):
            return etapa
    raise ValueError(f"não sei a etapa de {caminho.name}")


def main() -> None:
    import argparse
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Estrutura das planilhas do IDEB")
    parser.add_argument("--verificar", action="store_true", help="Confere série x nome")
    args = parser.parse_args()

    for caminho in arquivos("escolas") + arquivos("municipios"):
        workbook, worksheet = abrir_planilha(caminho)
        try:
            cabecalho = localizar_cabecalho(worksheet)
        finally:
            workbook.close()
        edicoes = sorted({c.edicao for c in cabecalho.medidas})
        print(
            f"{caminho.stem:<38} {len(cabecalho.medidas):>3} medidas  "
            f"{len(edicoes):>2} edições {min(edicoes)}-{max(edicoes)}  "
            f"dados a partir da linha {cabecalho.primeira_linha_dados}"
        )
        if args.verificar:
            for divergencia in verificar_series(caminho):
                print(f"      {divergencia}")


if __name__ == "__main__":
    main()
