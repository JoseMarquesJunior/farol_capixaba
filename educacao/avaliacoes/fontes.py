"""Catálogo das fontes de avaliação e o download de cada uma.

Quatro fontes, com naturezas bem diferentes:

* **IDEB** (INEP) — planilhas `.xlsx` largas por edição. Um pacote por etapa
  basta: o de 2025 já traz a série desde 2005 nos anos iniciais e finais. Traz
  o código INEP da escola;
* **ENEM por Escola** (INEP) — um único CSV longo com 2005 a 2015, também com o
  código INEP. A série termina em 2015, quando o INEP encerrou a divulgação;
* **SAEB** (INEP) — pacotes de 600+ MB dos quais só interessa o `TS_ESCOLA.csv`.
  O identificador de escola é mascarado (ver `saeb.py`);
* **PAEBES** (SEDU/ES) — microdado de aluno por disciplina, com o código INEP da
  escola. Só a edição de 2025 é publicada em dados abertos.

Os arquivos do INEP são servidos com suporte a `Range`, então `baixar_membro()`
extrai um único membro de dentro do ZIP sem baixar o pacote inteiro: são 21 MB
em vez de 662 MB por edição do SAEB.

Uso::

    python -m educacao.avaliacoes.fontes --listar
    python -m educacao.avaliacoes.fontes            # baixa o que falta
    python -m educacao.avaliacoes.fontes --fonte paebes
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
import urllib.request
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from ..config.logging import configure_logger
from ..config.settings import AVALIACOES_DIR

logger = configure_logger(__name__)

TIMEOUT = 600
BLOCO = 1 << 20


@dataclass(frozen=True, slots=True)
class Fonte:
    """Um arquivo a baixar.

    `membro` presente significa que só aquele arquivo de dentro do ZIP nos
    interessa, e que ele deve ser extraído por `Range` em vez de baixado inteiro.
    """

    fonte: str
    nome: str
    url: str
    #: Edições que o arquivo cobre, conferidas no próprio arquivo.
    edicoes: tuple[int, ...] = ()
    membro: str | None = None
    #: Extensão do arquivo gravado. Só precisa ser declarada quando `membro` é
    #: um padrão sem extensão, como "Dicionario", cujo nome real varia por ano.
    extensao: str = ""
    observacao: str = ""

    @property
    def destino(self) -> Path:
        sufixo = self.extensao or Path(self.membro or ".zip").suffix or ".zip"
        return AVALIACOES_DIR / self.fonte / f"{self.nome}{sufixo}"


_IDEB_2025 = "https://download.inep.gov.br/ideb/resultados"
_MICRODADOS = "https://download.inep.gov.br/microdados"
_DADOS_ES = "https://dados.es.gov.br/dataset"

#: O nome do pacote do SAEB não segue padrão: 2021 saiu dividido por nível.
_SAEB_PACOTES = (
    (2015, "microdados_saeb_2015.zip"),
    (2017, "microdados_saeb_2017.zip"),
    (2019, "microdados_saeb_2019.zip"),
    (2021, "microdados_saeb_2021_ensino_fundamental_e_medio.zip"),
    (2023, "microdados_saeb_2023.zip"),
)

#: Edições que cada pacote do IDEB de 2025 carrega. Conferido nos arquivos, não
#: presumido: o pacote de 2025 dos anos iniciais e finais traz a série desde
#: 2005 — e é superconjunto do pacote de 2015, que não tem nenhuma escola a
#: mais (1.159 contra 937 no ES) e ainda vem sem linha de nomes de máquina.
#: Por isso o histórico não precisa ser baixado à parte.
_IDEB_EDICOES = {
    "anos_iniciais": tuple(range(2005, 2026, 2)),
    "anos_finais": tuple(range(2005, 2026, 2)),
    # Ensino Médio por escola só passou a ser divulgado em 2017.
    "ensino_medio": (2017, 2019, 2021, 2023, 2025),
}

FONTES: tuple[Fonte, ...] = (
    # ------------------------------------------------------------------ IDEB
    *(
        Fonte(
            "ideb",
            f"{etapa}_{alvo}_{min(_IDEB_EDICOES[etapa])}_{max(_IDEB_EDICOES[etapa])}",
            f"{_IDEB_2025}/divulgacao_{etapa}_{alvo}_2025.zip",
            edicoes=_IDEB_EDICOES[etapa],
        )
        for etapa in ("anos_iniciais", "anos_finais", "ensino_medio")
        for alvo in ("escolas", "municipios")
    ),
    # ------------------------------------------------------- ENEM por Escola
    Fonte(
        "enem",
        "enem_por_escola_2005_2015",
        f"{_MICRODADOS}/enem_por_escola/2005_a_2015/microdados_enem_por_escola.zip",
        edicoes=tuple(range(2005, 2016)),
        observacao="Série encerrada em 2015 pelo INEP",
    ),
    # ------------------------------------------------------------------ SAEB
    *(
        Fonte(
            "saeb",
            f"escola_{ano}",
            f"{_MICRODADOS}/{pacote}",
            edicoes=(ano,),
            membro="TS_ESCOLA.csv",
            observacao="Identificador de escola mascarado; só serve por município",
        )
        for ano, pacote in _SAEB_PACOTES
    ),
    *(
        Fonte(
            "saeb",
            f"dicionario_{ano}",
            f"{_MICRODADOS}/{pacote}",
            edicoes=(ano,),
            membro="Dicionario",
            extensao=".xlsx",
        )
        for ano, pacote in _SAEB_PACOTES
    ),
    # ---------------------------------------------------------------- PAEBES
    Fonte(
        "paebes",
        "paebes_2025",
        f"{_DADOS_ES}/ba4dc390-3642-4088-a9f8-68fd7f2fda0d/resource"
        "/0c32ba62-befd-435a-91a3-b1c082d02e71/download/avaliacao_paebes_2025.zip",
        edicoes=(2025,),
        observacao="Único ano em dados abertos; 2008-2024 só via CAEd",
    ),
)


def _abrir(url: str, faixa: tuple[int, int] | None = None):
    cabecalhos = {"Range": f"bytes={faixa[0]}-{faixa[1]}"} if faixa else {}
    pedido = urllib.request.Request(url, headers=cabecalhos)
    return urllib.request.urlopen(pedido, timeout=TIMEOUT)


def _tamanho(url: str) -> int:
    pedido = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(pedido, timeout=TIMEOUT) as resposta:
        return int(resposta.headers["Content-Length"])


@dataclass(slots=True)
class _Membro:
    nome: str
    metodo: int
    comprimido: int
    descomprimido: int
    offset: int


def _central_directory(url: str) -> list[_Membro]:
    """Lê o índice do ZIP remoto (que fica no fim do arquivo) por `Range`."""

    tamanho = _tamanho(url)
    cauda = _abrir(url, (max(0, tamanho - 300_000), tamanho - 1)).read()

    fim = cauda.rfind(b"PK\x05\x06")
    if fim < 0:
        raise ValueError(f"{url} não parece um ZIP")
    cd_tamanho, cd_offset = struct.unpack("<II", cauda[fim + 12 : fim + 20])
    if cd_offset == 0xFFFFFFFF:  # ZIP64
        fim64 = cauda.rfind(b"PK\x06\x06")
        cd_tamanho, cd_offset = struct.unpack("<QQ", cauda[fim64 + 40 : fim64 + 56])

    indice = _abrir(url, (cd_offset, cd_offset + cd_tamanho - 1)).read()
    membros: list[_Membro] = []
    pos = 0
    while pos < len(indice) and indice[pos : pos + 4] == b"PK\x01\x02":
        n, m, k = struct.unpack("<HHH", indice[pos + 28 : pos + 34])
        metodo = struct.unpack("<H", indice[pos + 10 : pos + 12])[0]
        comprimido, descomprimido = struct.unpack("<II", indice[pos + 20 : pos + 28])
        offset = struct.unpack("<I", indice[pos + 42 : pos + 46])[0]
        nome = indice[pos + 46 : pos + 46 + n].decode("cp437")
        membros.append(
            _Membro(nome, metodo, comprimido, descomprimido, offset)
        )
        pos += 46 + n + m + k
    return membros


def baixar_membro(url: str, padrao: str, destino: Path) -> int:
    """Extrai um único membro do ZIP remoto. Devolve os bytes gravados."""

    candidatos = [
        m
        for m in _central_directory(url)
        if padrao.lower() in m.nome.lower()
        and m.descomprimido
        # `~$Dicionario...xlsx` é lixo de planilha aberta, não o dicionário.
        and not m.nome.rsplit("/", 1)[-1].startswith("~$")
    ]
    if not candidatos:
        raise FileNotFoundError(f"nenhum membro casa com '{padrao}' em {url}")
    # O .ods é o mesmo conteúdo do .xlsx; preferimos o que sabemos ler.
    membro = min(
        candidatos, key=lambda m: (not m.nome.lower().endswith((".csv", ".xlsx")), m.nome)
    )

    cabecalho = _abrir(url, (membro.offset, membro.offset + 29)).read()
    n, m = struct.unpack("<HH", cabecalho[26:30])
    inicio = membro.offset + 30 + n + m
    bruto = _abrir(url, (inicio, inicio + membro.comprimido - 1)).read()
    dados = zlib.decompress(bruto, -15) if membro.metodo == 8 else bruto

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(dados)
    return len(dados)


def baixar_inteiro(url: str, destino: Path) -> int:
    destino.parent.mkdir(parents=True, exist_ok=True)
    gravados = 0
    with _abrir(url) as resposta, destino.open("wb") as arquivo:
        while pedaco := resposta.read(BLOCO):
            arquivo.write(pedaco)
            gravados += len(pedaco)
    return gravados


def sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for pedaco in iter(lambda: arquivo.read(BLOCO), b""):
            digest.update(pedaco)
    return digest.hexdigest()


def baixar(fonte: Fonte, forcar: bool = False) -> Path:
    destino = fonte.destino
    if destino.exists() and not forcar:
        logger.info("%-8s %-40s já existe", fonte.fonte, fonte.nome)
        return destino

    if fonte.membro:
        gravados = baixar_membro(fonte.url, fonte.membro, destino)
        como = f"membro '{fonte.membro}'"
    else:
        gravados = baixar_inteiro(fonte.url, destino)
        como = "pacote"

    logger.info(
        "%-8s %-40s %7.1f MB  (%s)",
        fonte.fonte,
        fonte.nome,
        gravados / 1048576,
        como,
    )
    return destino


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Baixa as fontes de avaliação")
    parser.add_argument("--fonte", help="Restringe a uma fonte (ideb, enem, saeb, paebes)")
    parser.add_argument("--listar", action="store_true", help="Só mostra o catálogo")
    parser.add_argument("--forcar", action="store_true", help="Rebaixa o que já existe")
    args = parser.parse_args()

    alvos = [f for f in FONTES if not args.fonte or f.fonte == args.fonte]

    if args.listar:
        for f in alvos:
            marca = "✓" if f.destino.exists() else " "
            edicoes = (
                f"{min(f.edicoes)}-{max(f.edicoes)}" if len(f.edicoes) > 1 else str(f.edicoes[0])
            )
            print(f" {marca} {f.fonte:<8} {f.nome:<38} {edicoes:<12} {f.observacao}")
        return

    for fonte in alvos:
        try:
            baixar(fonte, forcar=args.forcar)
        except Exception as erro:  # segue para as outras fontes
            logger.error("falha em %s/%s: %s", fonte.fonte, fonte.nome, erro)


if __name__ == "__main__":
    main()
