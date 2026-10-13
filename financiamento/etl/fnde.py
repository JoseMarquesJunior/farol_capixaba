"""Repasses do FNDE aos municípios do ES (salário-educação, PNAE, PNATE, PDDE),
pelo lado de quem PAGA — como a CGU publica no Portal da Transparência.

**Por que não o portal do FNDE.** Em 2026-09-22: `fnde.gov.br/dadosabertos`
redireciona ao dados.gov.br, cuja API exige token (HTTP 401); a consulta de
liberações do FNDE (SIGEF) exige reCAPTCHA; e a API do Portal da Transparência
exige chave. O que é aberto e completo é o DOWNLOAD EM LOTE mensal da CGU, sem
token::

    https://portaldatransparencia.gov.br/download-de-dados/transferencias/<AAAAMM>
    → (302) https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/transferencias/<AAAAMM>_Transferencias.zip

Estrutura REAL (conferida em 2026-09-22 nos arquivos 202401 e 202404): um ZIP
(2–6 MB) com um CSV `;`, latin-1, 36 colunas, todas as transferências federais
do país no mês (223 mil linhas em abril/2024). As usadas::

    ANO / MÊS, TIPO TRANSFERÊNCIA, TIPO FAVORECIDO, UF, CÓDIGO MUNICÍPIO SIAFI,
    NOME MUNICÍPIO, CÓDIGO ÓRGÃO SIAFI, NOME ÓRGÃO, AÇÃO, NOME AÇÃO,
    CÓDIGO FAVORECIDO, NOME FAVORECIDO, VALOR TRANSFERIDO ("146003,84")

Ações da educação básica achadas nos dados do ES (abril/2024) — não presumidas:
`0369` salário-educação, `00PI` PNAE, `0969` PNATE, `0515` PDDE e `00SB`
complementação da União ao FUNDEB. O **PDDE vai quase todo para as escolas**
(`TIPO FAVORECIDO` = "Entidades Sem Fins Lucrativos": as unidades executoras),
não para a prefeitura — por isso não aparece na receita do município e é
mostrado à parte. O município vem por nome e código SIAFI (não IBGE); a ligação
é pelo nome, conferida contra a lista dos 78 do `/entes`.

Cache: o ZIP inteiro não é guardado (seria ~250 MB para cinco anos). Fica o
recorte do ES em `dados/bruto/fnde/<ano>/transferencias_<AAAAMM>_ES.csv.gz`,
com um `.json` ao lado: URL, URL final, instante, tamanho e SHA-256 do ZIP
original — o que permite provar que o recorte veio daquele arquivo.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests

from .config import BRUTO, PROCESSADO
from .parsing import norm
from .proveniencia import Consulta, Registro, caminho_relativo

log = logging.getLogger(__name__)

URL_MES = "https://portaldatransparencia.gov.br/download-de-dados/transferencias/{aaaamm}"
URL_DOC = "https://portaldatransparencia.gov.br/download-de-dados/transferencias"
PASTA_CACHE = BRUTO / "fnde"
ORGAO_FNDE = "26298"

#: Ação orçamentária federal → (programa, rótulo). Conferido nos dados (ver docstring).
ACOES = {
    "0369": ("salario_educacao", "Salário-educação (cota municipal)"),
    "00PI": ("pnae", "PNAE — alimentação escolar"),
    "0969": ("pnate", "PNATE — transporte escolar"),
    "0515": ("pdde", "PDDE — dinheiro direto na escola"),
    "00SB": ("fundeb_complementacao", "Complementação da União ao FUNDEB"),
}
PROGRAMAS = {**{v[0]: v[1] for v in ACOES.values()}, "outras_fnde": "Outras transferências do FNDE"}

#: "Quem recebeu": o próprio município (prefeitura, secretaria ou fundo) ou as
#: escolas (unidades executoras, entidades sem fins lucrativos).
DESTINOS = {"municipio": "Município (prefeitura, secretaria ou fundo)", "escolas": "Escolas (unidades executoras)",
            "outros": "Outros favorecidos"}

COLUNAS = {  # nome normalizado no CSV → nome interno
    "ano / mes": "ano_mes", "tipo favorecido": "tipo_favorecido", "uf": "uf",
    "codigo municipio siafi": "cod_siafi", "nome municipio": "municipio", "codigo orgao siafi": "orgao",
    "acao": "acao", "nome acao": "nome_acao", "codigo plano orcamentario": "po", "nome plano orcamentario": "po_nome",
    "codigo favorecido": "cod_favorecido", "nome favorecido": "favorecido", "valor transferido": "valor",
}

#: O CNCA é identificado pelo PLANO ORÇAMENTÁRIO da ação federal — achado nos dados
#: do ES em 2026-09-22, não presumido:
#:   0515 PDDE, PO 000C "PDDE - COMPROMISSO NACIONAL CRIANCA ALFABETIZADA"  → escolas
#:   0515 PDDE, PO 0007 "PDDE - ALFABETIZACAO" (antecessor, 2021–2022)      → escolas
#:   0509 Apoio ao Desenvolvimento da Educação Básica, PO 0014 "COMPROMISSO NACIONAL
#:        CRIANCA ALFABETIZADA"                                            → Estado (SEDU)
PO_PDDE_CNCA = "000C"
PO_PDDE_ALFABETIZACAO = "0007"
ACAO_APOIO_EB, PO_CNCA_ESTADO = "0509", "0014"


class ErroFnde(RuntimeError):
    """Falha de download depois das tentativas (não cacheada)."""


class ServidorRecusou(ErroFnde):
    """A CGU passou a recusar downloads (HTTP 403/405/429).

    Visto em 2026-09-22 depois de ~30 ZIPs em três minutos: todos os meses,
    inclusive os que tinham baixado antes, passaram a dar 405. É limite de
    volume, não ausência do arquivo — então a coleta para de insistir e os
    meses restantes ficam para uma próxima execução (o cache guarda os já baixados).
    """


_RECUSA = {403, 405, 429}


@dataclass(frozen=True, slots=True)
class Mes:
    aaaamm: str
    url: str
    obtido_em: str
    recorte: Path | None      # CSV.gz do ES; None se o mês não existe (ou modo offline sem cache)
    zip_sha256: str | None = None
    linhas_es: int = 0
    existe: bool = True


class ClienteTransparencia:
    """Baixa o ZIP mensal, recorta o ES e guarda o recorte + os metadados do ZIP."""

    def __init__(self, pasta: Path = PASTA_CACHE, *, atualizar: str = "nao", tentativas: int = 3,
                 timeout: tuple[float, float] = (15.0, 300.0), pausa: float = 20.0) -> None:
        if atualizar not in {"nao", "vazios", "tudo", "offline"}:
            raise ValueError(f"atualizar inválido: {atualizar!r}")
        self.pasta, self.atualizar, self.tentativas, self.timeout = pasta, atualizar, tentativas, timeout
        self.pausa = pausa            # segundos entre dois downloads (a CGU limita volume)
        self.recusou = False          # depois de uma recusa, não se baixa mais nada nesta execução
        self._ultimo_download = 0.0
        self.sessao = requests.Session()
        self.sessao.headers["User-Agent"] = "neduc-financiamento/1.0 (auditoria TCE-ES)"

    def _meta(self, aaaamm: str) -> Path:
        return self.pasta / aaaamm[:4] / f"transferencias_{aaaamm}_ES.json"

    def obter(self, aaaamm: str) -> Mes:
        meta = self._meta(aaaamm)
        url = URL_MES.format(aaaamm=aaaamm)
        if self.atualizar != "tudo" and meta.exists():
            d = json.loads(meta.read_text(encoding="utf-8"))
            recorte = meta.with_suffix(".csv.gz")
            if not (self.atualizar == "vazios" and not d["existe"]) and (not d["existe"] or recorte.exists()):
                return Mes(aaaamm, d["url"], d["obtido_em"], recorte if d["existe"] else None, d.get("zip_sha256"),
                           d.get("linhas_es", 0), d["existe"])
        if self.atualizar == "offline":
            return Mes(aaaamm, url, "", None, existe=False)
        if self.recusou:
            raise ServidorRecusou(f"{url}: não tentado — a CGU recusou um download anterior nesta execução")
        ultimo: Exception | None = None
        for tentativa in range(1, self.tentativas + 1):
            espera = self.pausa - (time.monotonic() - self._ultimo_download)
            if espera > 0:
                time.sleep(espera)
            try:
                return self._baixar(aaaamm, url, meta)
            except ServidorRecusou:
                self.recusou = True
                raise
            except (requests.RequestException, zipfile.BadZipFile, OSError) as exc:
                ultimo = exc
                log.warning("CGU %s: %s (tentativa %d)", aaaamm, exc, tentativa)
                time.sleep(5.0 * tentativa)
        raise ErroFnde(f"{url}: falhou após {self.tentativas} tentativas: {ultimo}")

    def _baixar(self, aaaamm: str, url: str, meta: Path) -> Mes:
        self._ultimo_download = time.monotonic()
        with self.sessao.get(url, timeout=self.timeout, stream=True, allow_redirects=True) as r:
            if r.status_code == 404:
                return self._gravar(meta, {"url": url, "url_final": r.url, "obtido_em": _agora(), "existe": False})
            if r.status_code in _RECUSA:
                raise ServidorRecusou(f"{r.url}: HTTP {r.status_code} — a CGU recusou o download (limite de volume); "
                                      f"os meses restantes ficam para a próxima execução")
            r.raise_for_status()
            h = hashlib.sha256()
            with tempfile.TemporaryDirectory() as tmp:
                zpath = Path(tmp) / "mes.zip"
                with open(zpath, "wb") as f:
                    for bloco in r.iter_content(1 << 20):
                        h.update(bloco)
                        f.write(bloco)
                tamanho = zpath.stat().st_size
                with zipfile.ZipFile(zpath) as z:
                    nome_csv = next(n for n in z.namelist() if n.lower().endswith(".csv"))
                    recorte, total, es, colunas = _recortar_es(z, nome_csv, meta.with_suffix(".csv.gz"))
        return self._gravar(meta, {"url": url, "url_final": r.url, "obtido_em": _agora(), "existe": True,
                                   "zip_bytes": tamanho, "zip_sha256": h.hexdigest(), "csv": nome_csv,
                                   "linhas_total": total, "linhas_es": es, "colunas": colunas}, recorte)

    @staticmethod
    def _gravar(meta: Path, corpo: dict[str, Any], recorte: Path | None = None) -> Mes:
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(json.dumps(corpo, ensure_ascii=False, indent=1), encoding="utf-8")
        return Mes(meta.stem.split("_")[1], corpo["url"], corpo["obtido_em"], recorte, corpo.get("zip_sha256"),
                   corpo.get("linhas_es", 0), corpo["existe"])


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _recortar_es(z: zipfile.ZipFile, nome_csv: str, destino: Path) -> tuple[Path, int, int, list[str]]:
    """Lê o CSV do ZIP em blocos e grava só as linhas com UF = ES (UTF-8, gzip)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".tmp")
    total = es = 0
    colunas: list[str] = []
    with z.open(nome_csv) as bruto, gzip.open(temporario, "wt", encoding="utf-8", newline="") as saida:
        for i, bloco in enumerate(pd.read_csv(bruto, sep=";", encoding="latin-1", dtype=str, chunksize=100_000,
                                              keep_default_na=False)):
            if i == 0:
                colunas = list(bloco.columns)
            uf = next(c for c in bloco.columns if norm(c) == "uf")
            total += len(bloco)
            sel = bloco[bloco[uf] == "ES"]
            es += len(sel)
            sel.to_csv(saida, sep=";", index=False, header=(i == 0))
    temporario.replace(destino)
    return destino, total, es, colunas


# ------------------------------------------------------------------ parsing

def ler_recorte(caminho: Path) -> pd.DataFrame:
    """Recorte do ES com as colunas usadas, nomes internos e valor numérico."""
    df = pd.read_csv(caminho, sep=";", dtype=str, keep_default_na=False, encoding="utf-8")
    renomear = {c: COLUNAS[norm(c)] for c in df.columns if norm(c) in COLUNAS}
    faltam = set(COLUNAS.values()) - set(renomear.values())
    if faltam:
        raise ValueError(f"{caminho.name}: colunas ausentes {sorted(faltam)}")
    df = df.rename(columns=renomear)[list(COLUNAS.values())]
    df["valor"] = pd.to_numeric(df["valor"].str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
                                errors="coerce")
    return df


def classificar(df: pd.DataFrame) -> pd.DataFrame:
    """Marca programa e destino; descarta o que não é repasse do FNDE a município."""
    programa = df["acao"].map(lambda a: ACOES.get(a, (None,))[0])
    programa = programa.where(programa.notna(), df["orgao"].map(lambda o: "outras_fnde" if o == ORGAO_FNDE else None))
    tipo = df["tipo_favorecido"].map(norm)
    destino = pd.Series("outros", index=df.index)
    destino[tipo.str.contains("municipal") | (tipo == "administracao publica")] = "municipio"
    destino[tipo.str.contains("sem fins lucrativos")] = "escolas"
    estadual = tipo.str.contains("estadual")
    return df.assign(programa=programa, destino=destino)[programa.notna() & ~estadual]


def mapa_municipios(nomes_ibge: dict[int, str]) -> dict[str, int]:
    """Nome normalizado → IBGE, a partir da lista oficial (`/entes`)."""
    return {norm(nome): cod for cod, nome in nomes_ibge.items()}


COLUNAS_ESCOLA = ["cod_ibge", "ano", "po", "po_nome", "cnpj_uex", "uex", "destino", "valor", "meses", "q"]
COLUNAS_CNCA_ESTADO = ["ano", "mes", "favorecido", "cnpj", "valor", "q"]


def pdde_por_escola(df: pd.DataFrame) -> pd.DataFrame:
    """PDDE (ação 0515) linha a linha, com o plano orçamentário e a unidade executora.

    Mantém as linhas sem município (escolas da rede estadual): `cod_ibge` vazio,
    para não sumirem do total do CNCA no ES.
    """
    p = df[df["acao"] == "0515"]
    tipo = p["tipo_favorecido"].map(norm)
    destino = pd.Series("outros", index=p.index)
    destino[tipo.str.contains("sem fins lucrativos")] = "escolas"
    destino[tipo.str.contains("municipal") | (tipo == "administracao publica")] = "municipio"
    destino[tipo.str.contains("estadual")] = "estado"
    return p.assign(destino=destino)


def cnca_estado(df: pd.DataFrame) -> pd.DataFrame:
    """Repasse do CNCA ao Estado: ação 0509, plano orçamentário 0014."""
    return df[(df["acao"] == ACAO_APOIO_EB) & (df["po"] == PO_CNCA_ESTADO)]


@dataclass
class ResultadoFnde:
    tabela: pd.DataFrame           # cod_ibge, ano, programa, destino, valor, meses, q (ids dos meses)
    consultas: Registro
    avisos: list[dict[str, Any]]
    status: dict[str, Any]
    escolas: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=COLUNAS_ESCOLA))       # PDDE por UEx e PO
    estado_cnca: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=COLUNAS_CNCA_ESTADO))


def executar(nomes_ibge: dict[int, str], anos: Iterable[int], *, atualizar: str = "nao",
             hoje: datetime | None = None) -> ResultadoFnde:
    """Todos os meses dos exercícios pedidos (até o mês corrente). Mês que falha vira aviso."""
    hoje = hoje or datetime.now(timezone.utc)
    anos = list(anos)
    cliente = ClienteTransparencia(atualizar=atualizar)
    mapa = mapa_municipios(nomes_ibge)
    registro = Registro()
    partes: list[pd.DataFrame] = []
    escola_partes: list[pd.DataFrame] = []
    estado_partes: list[pd.DataFrame] = []
    avisos: list[dict[str, Any]] = []
    fora_rede = {"linhas": 0, "valor": 0.0}
    for ano in anos:
        for mes in range(1, 13):
            if (ano, mes) >= (hoje.year, hoje.month):
                continue
            aaaamm = f"{ano}{mes:02d}"
            try:
                m = cliente.obter(aaaamm)
            except ErroFnde as exc:
                avisos.append({"ano": ano, "mes": mes, "aviso": str(exc)})
                continue
            if not m.obtido_em:
                avisos.append({"ano": ano, "mes": mes, "aviso": "não coletado (modo offline, sem cache)"})
                continue
            if not m.existe or m.recorte is None:
                avisos.append({"ano": ano, "mes": mes, "aviso": "arquivo do mês não publicado pela CGU"})
                continue
            c = Consulta(fonte="FNDE", recurso="cgu_transferencias", metodo="GET (download em lote)",
                         descricao=f"Portal da Transparência (CGU) — transferências de {mes:02d}/{ano}, recorte UF=ES",
                         url=m.url, obtido_em=m.obtido_em, arquivo=caminho_relativo(m.recorte), sha256=m.zip_sha256)
            registro.adicionar(c)
            try:
                bruto = ler_recorte(m.recorte)
                df = classificar(bruto)
            except (ValueError, KeyError) as exc:
                avisos.append({"ano": ano, "mes": mes, "aviso": f"recorte ilegível: {exc}"})
                continue
            marca = {"ano": ano, "mes": mes, "q": c.id}
            escola_partes.append(pdde_por_escola(bruto).assign(cod_ibge=lambda x: x["municipio"].map(lambda n: mapa.get(norm(n))),
                                                              **marca))
            estado_partes.append(cnca_estado(bruto).assign(**marca))
            df = df.assign(cod_ibge=df["municipio"].map(lambda n: mapa.get(norm(n))), ano=ano, mes=mes, q=c.id)
            # Linha sem município = repasse a escola da REDE ESTADUAL (visto em 2021–2023: PDDE a
            # conselhos de EEEFM). Não é de município nenhum: fica fora, contada no status.
            sem_municipio = df["municipio"].str.strip() == ""
            fora_rede["linhas"] += int(sem_municipio.sum())
            fora_rede["valor"] += float(df.loc[sem_municipio, "valor"].sum())
            sem = sorted(set(df.loc[df["cod_ibge"].isna() & ~sem_municipio, "municipio"]))
            if sem:
                avisos.append({"ano": ano, "mes": mes, "aviso": f"município sem correspondência no IBGE: {sem}"})
            partes.append(df[df["cod_ibge"].notna()])

    colunas = ["cod_ibge", "ano", "programa", "destino", "valor", "meses", "q"]
    if partes:
        tudo = pd.concat(partes, ignore_index=True)
        tudo["cod_ibge"] = tudo["cod_ibge"].astype(int)
        tabela = (tudo.groupby(["cod_ibge", "ano", "programa", "destino"], as_index=False)
                  .agg(valor=("valor", "sum"), meses=("mes", "nunique"), q=("q", lambda s: ";".join(sorted(set(s))))))
        tabela["valor"] = tabela["valor"].round(2)
    else:
        tabela = pd.DataFrame(columns=colunas)
    # PDDE por unidade executora e plano orçamentário (base do CNCA por escola e da visão por escola).
    if escola_partes:
        e = pd.concat(escola_partes, ignore_index=True)
        escolas = (e.groupby(["cod_ibge", "ano", "po", "po_nome", "cod_favorecido", "favorecido", "destino"],
                             as_index=False, dropna=False)
                   .agg(valor=("valor", "sum"), meses=("mes", "nunique"), q=("q", lambda s: ";".join(sorted(set(s))))))
        escolas = escolas.rename(columns={"cod_favorecido": "cnpj_uex", "favorecido": "uex"})
        escolas["valor"] = escolas["valor"].round(2)
        escolas["cod_ibge"] = escolas["cod_ibge"].astype("Int64")
        escolas = escolas[COLUNAS_ESCOLA]
    else:
        escolas = pd.DataFrame(columns=COLUNAS_ESCOLA)
    est = pd.concat(estado_partes, ignore_index=True) if estado_partes else pd.DataFrame()
    estado_cnca_df = (est.rename(columns={"cod_favorecido": "cnpj"})[COLUNAS_CNCA_ESTADO].reset_index(drop=True)
                      if not est.empty else pd.DataFrame(columns=COLUNAS_CNCA_ESTADO))
    esperados = sum(1 for a in anos for m in range(1, 13) if (a, m) < (hoje.year, hoje.month))
    status = {"fonte": "FNDE", "ok": True, "linhas": len(tabela), "meses": len(registro), "meses_esperados": esperados,
              "servidor_recusou": cliente.recusou, "avisos": len(avisos), "extraido_em": registro.extraido_em("FNDE"),
              "rede_estadual_sem_municipio": {"linhas": fora_rede["linhas"], "valor": round(fora_rede["valor"], 2)}}
    return ResultadoFnde(tabela[colunas], registro, avisos, status, escolas, estado_cnca_df)


def main(argv: Iterable[str] | None = None) -> int:
    """Religa só o FNDE/CGU: `python -m financiamento.etl.fnde --anos 2021-2025`."""
    from . import entes as mod_entes
    from .cliente import ClienteSiconfi
    from .pipeline import parse_anos

    p = argparse.ArgumentParser(description="Repasses do FNDE aos municípios do ES (download em lote da CGU).")
    p.add_argument("--anos", type=parse_anos, required=True)
    p.add_argument("--atualizar", choices=("nao", "vazios", "tudo", "offline"), default="nao")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    lista = mod_entes.listar_entes_es(ClienteSiconfi(atualizar="nao"))
    r = executar({e.cod_ibge: e.nome for e in lista if e.esfera == "M"}, args.anos, atualizar=args.atualizar)
    destino = PROCESSADO / "fontes" / "fnde"
    destino.mkdir(parents=True, exist_ok=True)
    r.tabela.to_csv(destino / "repasses_fnde.csv", index=False, encoding="utf-8")
    pd.DataFrame(r.avisos).to_csv(destino / "avisos.csv", index=False, encoding="utf-8")
    pd.DataFrame(r.consultas.como_linhas()).to_csv(destino / "consultas.csv", index=False, encoding="utf-8")
    print(json.dumps(r.status, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
