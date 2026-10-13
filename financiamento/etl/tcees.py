"""TCE-ES (dados abertos em dados.es.gov.br): Nível 3 da despesa, obras, o índice de
MDE apurado pelo Tribunal e os prazos das remessas ao Tribunal.

Portal CKAN aberto, sem token. Os recursos são achados pelo NOME dentro de cada
dataset (``/api/3/action/package_show?id=<dataset>``), não por URL fixa — o
TCE-ES troca arquivos de lugar a cada atualização. Estrutura REAL conferida em
2026-09-22 (ver ``docs/mapeamento_dados_tcees.md``); CSVs com ``;``, latin-1
(bens vinculadores em UTF-16), decimal com vírgula.

=============================================  ==============================================================
Recurso (dataset)                              Uso e campos
=============================================  ==============================================================
Educação (despesas com saúde, educação…)       MDE apurado pelo TCE-ES: ``Ano, Municipio, Aplicacao,
                                               AplicacaoPercentual, Alunos, AplicacaoPorAluno,
                                               MesUltimoEnvio, ReceitaFUNDEB`` (2009 em diante)
Prestação de Contas Municipal (obrigacoes)     prazos: ``Município, UnidadeGestora, Mes, Ano,
                                               DataHomologacao, DataLimite`` — o prazo VEM na fonte
Obras e serviços de Engenharia (contratações)  contratos de obra: ``SetorBeneficiado``, objeto, contratada,
                                               valores, ``SituacaoObra``, URLs, ``ChaveInstrumento``
Bens vinculadores (contratações)               o prédio de cada contratação: nome, categoria
                                               (``ObjetoIntervencao``), centroide (lat/lon)
Instrumentos com medições e alterações         1,2 GB: aditivos e medições por ``ChaveInstrumento`` —
                                               lido em fluxo, fica só o das obras da educação
Contratações (contratações)                    97 MB: a licitação/contratação inteira —
                                               ``IdentificacaoContratacao, SetorBeneficiado, ObjetoContratacao,
                                               ModalidadeLicitacao, UrlEdital, ValorTotalContratacao``; lido em
                                               fluxo, fica só o da Educação (ver `contratacoes_educacao`)
Itens - <ano> (contratações)                   65–390 MB por ano, 2022 em diante: o ITEM comprado —
                                               ``DescricaoItem, UnidadeMedida, QuantidadeItemContratado,
                                               ValorUnitarioItemContratado, ValorTotalItemContratado``, as
                                               quantidades medidas, a contratada e a ``ChaveInstrumento``;
                                               lido em fluxo, fica só o da Educação
Empenhos dos municípios (2020+)                3–5 ZIPs por ano (~700 MB de CSV cada); linha = empenho ×
                                               mês de referência (movimento do mês); fica só a função 12.
                                               O layout muda: 2021–2023 trazem ``Ano``/``Mes``; 2024 em
                                               diante, ``AnoReferencia``/``MesReferencia`` (+ competência
                                               e data de emissão) — os dois são aceitos
Despesas dos municípios (agregado)             mesma classificação, sem credor, com a DOTAÇÃO
                                               (``PrevisaoInicial``, ``PrevisaoAtualizada``); fica a função 12
=============================================  ==============================================================

Os dados são declaratórios (remessas do CidadES). Cache em ``dados/bruto/tcees/``:
arquivo pequeno guardado inteiro (gzip); arquivo grande guardado como RECORTE da
Educação, com o SHA-256 e o tamanho do arquivo original no ``.json`` ao lado —
o que prova de onde o recorte saiu sem guardar 10 GB.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import logging
import re
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

import pandas as pd
import requests

from .config import BRUTO, PROCESSADO
from .parsing import norm
from .proveniencia import Consulta, Registro, caminho_relativo, juntar_ids

log = logging.getLogger(__name__)

CKAN = "https://dados.es.gov.br"
PORTAL = "https://dados.es.gov.br/organization/tcees-tribunal-de-contas-do-estado-do-espirito-santo"
PASTA_CACHE = BRUTO / "tcees"
BRASILIA = timezone(timedelta(hours=-3))

#: chave → (dataset, padrão do nome do recurso). O padrão é regex sobre o nome normalizado.
RECURSOS = {
    "educacao": ("tcees-despesas-com-saude-educacao-e-pessoal-receita-corrente-liquida-e-endividamento", r"^educacao$"),
    "pcm": ("obrigacoes", r"prestacao de contas municipal"),
    "obras": ("tcees-contratacoes", r"^obras e servicos de engenharia$"),
    "bens": ("tcees-contratacoes", r"^bens vinculadores$"),
    "medicoes": ("tcees-contratacoes", r"medicoes e alteracoes"),
    "contratacoes": ("tcees-contratacoes", r"^contratacoes$"),
}
DATASET_CONTRATACOES = "tcees-contratacoes"
DATASET_EMPENHOS = "tcees-empenho"
DATASET_DESPESAS = "despesas-municipios"


class ErroTcees(RuntimeError):
    """Falha de download depois das tentativas (não cacheada)."""


class ServidorRecusou(ErroTcees):
    """HTTP 403/405/429: para de baixar nesta execução (o que já está no cache vale)."""


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def num_br(serie: pd.Series) -> pd.Series:
    """'1.234,56' / '1234,56' / ',00' → float (vazio vira NaN, nunca zero)."""
    s = serie.astype("string").str.strip().replace("", pd.NA)
    return pd.to_numeric(s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False), errors="coerce")


# ------------------------------------------------------------------ cliente

@dataclass(frozen=True, slots=True)
class Arquivo:
    chave: str
    url: str
    obtido_em: str
    caminho: Path | None          # arquivo (ou recorte) no cache
    sha256: str | None = None     # do arquivo ORIGINAL baixado
    tamanho: int | None = None
    recorte: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def consulta(self, descricao: str) -> Consulta:
        return Consulta(fonte="TCE-ES", recurso=f"tcees_{self.chave.split('/')[0]}", metodo="GET (dados abertos CKAN)",
                        descricao=descricao, url=self.url, obtido_em=self.obtido_em,
                        arquivo=caminho_relativo(self.caminho) if self.caminho else "", sha256=self.sha256)


class ClienteTcees:
    """Baixa recursos do portal com cache; recorta os grandes enquanto baixa."""

    def __init__(self, pasta: Path | None = None, *, atualizar: str = "nao", tentativas: int = 3,
                 pausa: float = 3.0, timeout: tuple[float, float] = (20.0, 600.0)) -> None:
        if atualizar not in {"nao", "vazios", "tudo", "offline"}:
            raise ValueError(f"atualizar inválido: {atualizar!r}")
        pasta = pasta or PASTA_CACHE
        self.pasta, self.atualizar, self.tentativas, self.pausa, self.timeout = pasta, atualizar, tentativas, pausa, timeout
        self.sessao = requests.Session()
        self.sessao.headers["User-Agent"] = "neduc-financiamento/1.0 (auditoria TCE-ES)"
        self.recusou = False
        self._ultimo = 0.0
        self._catalogos: dict[str, list[dict[str, Any]]] = {}

    # --------------------------------------------------------------- catálogo
    def recursos(self, dataset: str) -> list[dict[str, Any]]:
        """Recursos de um dataset (nome, url, datas), com cache do catálogo."""
        if dataset in self._catalogos:
            return self._catalogos[dataset]
        meta = self.pasta / "_catalogo" / f"{dataset}.json"
        if meta.exists() and self.atualizar != "tudo":
            self._catalogos[dataset] = json.loads(meta.read_text(encoding="utf-8"))["recursos"]
            return self._catalogos[dataset]
        if self.atualizar == "offline":
            return []
        r = self._get(f"{CKAN}/api/3/action/package_show", params={"id": dataset})
        recursos = [{"id": x["id"], "nome": x.get("name") or "", "url": x["url"], "formato": x.get("format"),
                     "tamanho": x.get("size"), "modificado": x.get("last_modified") or x.get("metadata_modified")}
                    for x in r.json()["result"]["resources"]]
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(json.dumps({"dataset": dataset, "obtido_em": _agora(), "recursos": recursos},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
        self._catalogos[dataset] = recursos
        return recursos

    def achar(self, dataset: str, padrao: str) -> dict[str, Any] | None:
        rx = re.compile(padrao)
        achados = [x for x in self.recursos(dataset) if rx.search(norm(x["nome"]))]
        return achados[0] if achados else None

    # ------------------------------------------------------------------- rede
    def _get(self, url: str, **kw: Any) -> requests.Response:
        if self.recusou:
            raise ServidorRecusou(f"{url}: não tentado — o portal recusou um download anterior")
        ultimo: Exception | None = None
        for tentativa in range(1, self.tentativas + 1):
            espera = self.pausa - (time.monotonic() - self._ultimo)
            if espera > 0:
                time.sleep(espera)
            self._ultimo = time.monotonic()
            try:
                r = self.sessao.get(url, timeout=self.timeout, allow_redirects=True, **kw)
                if r.status_code in {403, 405, 429}:
                    self.recusou = True
                    raise ServidorRecusou(f"{url}: HTTP {r.status_code}")
                r.raise_for_status()
                return r
            except ServidorRecusou:
                raise
            except requests.RequestException as exc:
                ultimo = exc
                log.warning("TCE-ES %s: %s (tentativa %d)", url, exc, tentativa)
                time.sleep(5.0 * tentativa)
        raise ErroTcees(f"{url}: falhou após {self.tentativas} tentativas: {ultimo}")

    def _baixar(self, url: str, destino: Path) -> tuple[str, int]:
        """Arquivo inteiro para `destino`, com nova tentativa também quando a conexão cai
        no MEIO do corpo (o `_get` só cobre o início da resposta). Devolve (SHA-256, bytes)."""
        ultimo: Exception | None = None
        for tentativa in range(1, self.tentativas + 1):
            h = hashlib.sha256()
            try:
                with self._get(url, stream=True) as r, open(destino, "wb") as f:
                    for bloco in r.iter_content(1 << 20):
                        h.update(bloco)
                        f.write(bloco)
                return h.hexdigest(), destino.stat().st_size
            except ServidorRecusou:
                raise
            except requests.RequestException as exc:
                ultimo = exc
                log.warning("TCE-ES %s: conexão caiu durante o download (%s), tentativa %d", url, exc, tentativa)
                time.sleep(10.0 * tentativa)
        raise ErroTcees(f"{url}: download interrompido {self.tentativas} vezes: {ultimo}")

    # ------------------------------------------------------------------ cache
    def _meta(self, chave: str) -> Path:
        return self.pasta / f"{chave}.json"

    def _do_cache(self, chave: str) -> Arquivo | None:
        meta = self._meta(chave)
        if self.atualizar == "tudo" or not meta.exists():
            return None
        d = json.loads(meta.read_text(encoding="utf-8"))
        caminho = self.pasta / d["arquivo"] if d.get("arquivo") else None
        if caminho is not None and not caminho.exists():
            return None
        return Arquivo(chave, d["url"], d["obtido_em"], caminho, d.get("sha256"), d.get("tamanho"), d.get("recorte", False),
                       d.get("extra", {}))

    def _gravar(self, a: Arquivo) -> Arquivo:
        meta = self._meta(a.chave)
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(json.dumps({"url": a.url, "obtido_em": a.obtido_em,
                                    "arquivo": a.caminho.relative_to(self.pasta).as_posix() if a.caminho else None,
                                    "sha256": a.sha256, "tamanho": a.tamanho, "recorte": a.recorte, "extra": a.extra},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
        return a

    def _nao_coletado(self, chave: str, url: str = "") -> Arquivo:
        return Arquivo(chave, url, "", None)

    # -------------------------------------------------------------- arquivos
    def pequeno(self, chave: str) -> Arquivo:
        """Recurso pequeno, guardado inteiro (gzip)."""
        if (a := self._do_cache(chave)) is not None:
            return a
        dataset, padrao = RECURSOS[chave]
        rec = self.achar(dataset, padrao)
        if self.atualizar == "offline" or rec is None:
            return self._nao_coletado(chave, rec["url"] if rec else "")
        r = self._get(rec["url"])
        dados = r.content
        destino = self.pasta / f"{chave}.dat.gz"
        destino.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(destino, "wb") as f:
            f.write(dados)
        return self._gravar(Arquivo(chave, rec["url"], _agora(), destino, hashlib.sha256(dados).hexdigest(), len(dados),
                                    extra={"recurso": rec["nome"], "dataset": dataset, "modificado": rec.get("modificado")}))

    def recorte_zip(self, chave: str, url: str, filtro: Callable[[pd.DataFrame], pd.DataFrame], extra: dict[str, Any]) -> Arquivo:
        """ZIP grande → baixa para um temporário, lê o CSV em blocos e guarda só o que `filtro` deixar."""
        if (a := self._do_cache(chave)) is not None:
            return a
        if self.atualizar == "offline":
            return self._nao_coletado(chave, url)
        destino = self.pasta / f"{chave}.csv.gz"
        destino.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            zpath = Path(tmp) / "a.zip"
            sha256, tamanho = self._baixar(url, zpath)
            total = mantidas = 0
            with zipfile.ZipFile(zpath) as z:
                nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
                temporario = destino.with_suffix(".tmp")
                with z.open(nome) as bruto, gzip.open(temporario, "wt", encoding="utf-8", newline="") as saida:
                    for i, bloco in enumerate(pd.read_csv(bruto, sep=";", encoding="latin-1", dtype=str, chunksize=200_000,
                                                          keep_default_na=False)):
                        total += len(bloco)
                        sel = filtro(bloco)
                        mantidas += len(sel)
                        sel.to_csv(saida, sep=";", index=False, header=(i == 0))
                temporario.replace(destino)
        return self._gravar(Arquivo(chave, url, _agora(), destino, sha256, tamanho, True,
                                    {**extra, "csv": nome, "linhas_total": total, "linhas_mantidas": mantidas}))

    def recorte_csv_fluxo(self, chave: str, url: str, manter: Callable[[dict[str, str]], Any], extra: dict[str, Any],
                          coluna_extra: str | None = None, encoding: str = "latin-1") -> Arquivo:
        """CSV enorme sem ZIP → lê o fluxo HTTP linha a linha e guarda só as linhas que `manter` aceitar.

        Com `coluna_extra`, o valor devolvido por `manter` (qualquer coisa verdadeira) é gravado
        numa coluna a mais: é assim que o recorte dos itens guarda POR QUE cada linha entrou.

        `encoding` existe porque nem tudo no portal é latin-1: os arquivos do TCE-ES são,
        mas o do SIGEFES (esfera estadual, publicado pela SEFAZ no mesmo CKAN) é UTF-8 com
        BOM. Ler UTF-8 como latin-1 não falha — produz mojibake —, e o nome do favorecido
        em mojibake não casa com nenhum município.
        """
        if (a := self._do_cache(chave)) is not None:
            return a
        if self.atualizar == "offline":
            return self._nao_coletado(chave, url)
        h = hashlib.sha256()
        destino = self.pasta / f"{chave}.csv.gz"
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_suffix(".tmp")
        total = mantidas = tamanho = 0

        class _Hash(io.RawIOBase):  # conta e faz o hash do que passa, sem guardar
            def __init__(self, raw):
                self.raw = raw
            def readable(self):
                return True
            def readinto(self, b):
                nonlocal tamanho
                dados = self.raw.read(len(b))
                if not dados:
                    return 0
                h.update(dados)
                tamanho += len(dados)
                b[:len(dados)] = dados
                return len(dados)

        with self._get(url, stream=True) as r, gzip.open(temporario, "wt", encoding="utf-8", newline="") as saida:
            r.raw.decode_content = True
            texto = io.TextIOWrapper(io.BufferedReader(_Hash(r.raw), 1 << 20), encoding=encoding, newline="")
            leitor = csv.DictReader(texto, delimiter=";")
            campos = list(leitor.fieldnames or []) + ([coluna_extra] if coluna_extra else [])
            escritor = csv.DictWriter(saida, fieldnames=campos, delimiter=";", extrasaction="ignore")
            escritor.writeheader()
            for linha in leitor:
                total += 1
                if (marca := manter(linha)):
                    if coluna_extra:
                        linha[coluna_extra] = "" if marca is True else str(marca)
                    escritor.writerow(linha)
                    mantidas += 1
        temporario.replace(destino)
        return self._gravar(Arquivo(chave, url, _agora(), destino, h.hexdigest(), tamanho, True,
                                    {**extra, "linhas_total": total, "linhas_mantidas": mantidas}))


def ler_dat(a: Arquivo, encoding: str = "latin-1") -> pd.DataFrame:
    """Recurso pequeno do cache → DataFrame (texto)."""
    with gzip.open(a.caminho, "rb") as f:
        dados = f.read()
    if dados[:2] in (b"\xff\xfe", b"\xfe\xff"):
        encoding = "utf-16"
    elif dados[:3] == b"\xef\xbb\xbf":
        encoding = "utf-8-sig"
    return pd.read_csv(io.BytesIO(dados), sep=";", encoding=encoding, dtype=str, keep_default_na=False)


def ler_recorte(a: Arquivo) -> pd.DataFrame:
    return pd.read_csv(a.caminho, sep=";", encoding="utf-8", dtype=str, keep_default_na=False)


# ---------------------------------------------------------------- municípios

class Municipios:
    """Nome do município (como o TCE-ES escreve) → código IBGE, conferido contra os 78."""

    def __init__(self, nomes_ibge: dict[int, str]):
        self.por_nome = {norm(n): c for c, n in nomes_ibge.items()}

    def cod(self, nome: Any) -> int | None:
        return self.por_nome.get(norm(nome))


# ------------------------------------------------------------------ parsers

def mde_tcees(df: pd.DataFrame, mun: Municipios) -> pd.DataFrame:
    """CSV "Educação" → município × ano com o índice de MDE apurado pelo TCE-ES."""
    d = pd.DataFrame({
        "cod_ibge": df["Municipio"].map(mun.cod), "ano": pd.to_numeric(df["Ano"], errors="coerce"),
        "tcees_mde_aplicado": num_br(df["Aplicacao"]), "tcees_mde_pct": num_br(df["AplicacaoPercentual"]),
        "tcees_alunos": pd.to_numeric(df["Alunos"], errors="coerce"),
        "tcees_mde_por_aluno": num_br(df["AplicacaoPorAluno"]),
        "tcees_mes_ultimo_envio": pd.to_numeric(df["MesUltimoEnvio"], errors="coerce"),
        "tcees_receita_fundeb": num_br(df["ReceitaFUNDEB"]),
    })
    return d[d["cod_ibge"].notna()].astype({"cod_ibge": int, "ano": int})


def remessas_pcm(df: pd.DataFrame, mun: Municipios, hoje: datetime) -> pd.DataFrame:
    """Prestação de Contas Mensal: uma linha por UG × mês, com prazo DA FONTE e atraso.

    UG sem NENHUMA homologação na janela publicada (~100 secretarias e fundos, todos
    os meses vazios) não é tratada como atrasada: o padrão é o de unidade cuja conta
    vai consolidada em outra UG. Fica como `ug_sem_remessa`, a confirmar com o Tribunal.

    A fonte repete UG × mês (416 linhas em 2025–2026, sobretudo em Vila Velha e no
    Estado; não há código de UG para distinguir). Fica a linha HOMOLOGADA — contar as
    duas afirmaria atraso que a própria fonte desmente.
    """
    col_mun = next(c for c in df.columns if norm(c) == "municipio")
    homolog = pd.to_datetime(df["DataHomologacao"].str[:19], errors="coerce")
    limite = pd.to_datetime(df["DataLimite"].str[:19], errors="coerce")
    agora = pd.Timestamp(hoje.astimezone(BRASILIA).replace(tzinfo=None))
    d = pd.DataFrame({"cod_ibge": df[col_mun].map(mun.cod), "ug": df["UnidadeGestora"],
                      "ano": pd.to_numeric(df["Ano"], errors="coerce"), "mes": pd.to_numeric(df["Mes"], errors="coerce"),
                      "homologacao": homolog, "limite": limite})
    d = d[d["cod_ibge"].notna()].astype({"cod_ibge": int})
    atraso = (d["homologacao"] - d["limite"]).dt.total_seconds() / 86400
    d["situacao"] = "no_prazo"
    d.loc[atraso > 0, "situacao"] = "com_atraso"
    d.loc[d["homologacao"].isna() & (d["limite"] < agora), "situacao"] = "nao_homologada"
    d.loc[d["homologacao"].isna() & (d["limite"] >= agora), "situacao"] = "prazo_aberto"
    d["dias_atraso"] = atraso.clip(lower=0).apply(lambda x: None if pd.isna(x) else int(-(-x // 1)))  # arredonda para cima
    d.loc[d["situacao"] == "nao_homologada", "dias_atraso"] = ((agora - d["limite"]).dt.days).astype("Int64")
    d = d.sort_values("homologacao").drop_duplicates(["cod_ibge", "ug", "ano", "mes"], keep="first").sort_index()
    nunca = d.groupby(["cod_ibge", "ug"])["homologacao"].transform(lambda s: s.isna().all())
    d.loc[nunca & d["situacao"].isin(["nao_homologada", "prazo_aberto"]), "situacao"] = "ug_sem_remessa"
    d.loc[d["situacao"] == "ug_sem_remessa", "dias_atraso"] = None
    return d


def resumo_pcm(d: pd.DataFrame) -> pd.DataFrame:
    if d.empty:
        return pd.DataFrame(columns=["cod_ibge", "ano", "pcm_remessas", "pcm_com_atraso", "pcm_nao_homologadas",
                                     "pcm_maior_atraso_dias", "pcm_ugs", "pcm_ugs_sem_remessa"])
    g = d.groupby(["cod_ibge", "ano"])
    return pd.DataFrame({
        "pcm_remessas": g["situacao"].apply(lambda s: int((s != "ug_sem_remessa").sum())),
        "pcm_com_atraso": g["situacao"].apply(lambda s: int((s == "com_atraso").sum())),
        "pcm_nao_homologadas": g["situacao"].apply(lambda s: int((s == "nao_homologada").sum())),
        "pcm_maior_atraso_dias": g["dias_atraso"].max(), "pcm_ugs": g["ug"].nunique(),
        "pcm_ugs_sem_remessa": g.apply(lambda x: x.loc[x["situacao"] == "ug_sem_remessa", "ug"].nunique(),
                                       include_groups=False),
    }).reset_index()


EDUCACAO = re.compile(r"educa")


def obras_educacao(obras: pd.DataFrame, bens: pd.DataFrame, medicoes: pd.DataFrame | None, mun: Municipios) -> pd.DataFrame:
    """Contratos de obra com setor beneficiado "Educação", dos municípios, com o prédio e as medições."""
    o = obras[obras["SetorBeneficiado"].map(norm).str.contains(EDUCACAO)].copy()
    o["cod_ibge"] = o["NomeEsferaAdministrativaReferencia"].map(mun.cod)
    o = o[o["cod_ibge"].notna()]
    d = pd.DataFrame({
        "cod_ibge": o["cod_ibge"].astype(int), "chave": o["ChaveInstrumento"], "contratacao": o["IdentificacaoContratacao"],
        "ug": o["NomeUnidadeGestoraReferenciaInstrumento"].where(o["NomeUnidadeGestoraReferenciaInstrumento"] != "",
                                                                 o["NomeUnidadeGestoraReferencia"]),
        "objeto": o["ObjetoInstrumento"].where(o["ObjetoInstrumento"].str.strip() != "", o["ObjetoContratacao"]).str.strip(),
        "contratado": o["NomeContratado"].str.strip(), "cnpj_contratado": o["NumeroIdentificacaoContratado1"].str.strip(),
        "valor_inicial": num_br(o["ValorTotalInstrumento"]), "valor_atual": num_br(o["ValorAtualContratacao"]),
        "situacao": o["SituacaoObra"].str.strip(), "tipo_intervencao": o["TipoIntervencao"].str.strip(),
        "assinatura": o["DataAssinaturaInstrumentoContratacao"].str[:10], "fim_vigencia": o["FimVigenciaContrato"].str[:10],
        "url_contrato": o["UrlInstrumentoContratacao"].str.strip(), "url_edital": o["UrlEdital"].str.strip(),
    })
    d["valor"] = d["valor_atual"].fillna(d["valor_inicial"])
    d = d.drop_duplicates("chave")
    # Prédio (bem vinculador) de cada contratação — um contrato pode ter vários.
    if not bens.empty:
        b = bens.assign(lat=num_br(bens["LatitudeCentroide"].str.replace(".", ",", regex=False)),
                        lon=num_br(bens["LongitudeCentroide"].str.replace(".", ",", regex=False)))
        por = b.groupby("IdentificacaoContratacao").apply(
            lambda g: json.dumps([{"nome": n.strip(), "categoria": c.strip(), "lat": None if pd.isna(la) else round(la, 6),
                                   "lon": None if pd.isna(lo) else round(lo, 6)}
                                  for n, c, la, lo in zip(g["NomeBemVinculador"], g["ObjetoIntervencao"], g["lat"], g["lon"])],
                                 ensure_ascii=False), include_groups=False).rename("bens")
        d = d.merge(por, left_on="contratacao", right_index=True, how="left")
    else:
        d["bens"] = None
    # Medições e aditivos.
    if medicoes is not None and not medicoes.empty:
        m = medicoes.assign(v_med=num_br(medicoes["ValorTotalMedicao"]), v_pag=num_br(medicoes["ValorPagamento"]),
                            v_adit=num_br(medicoes["ValorTotalContratacaoAlteracao"]))
        med = m[m["NumeroMedicao"].str.strip() != ""].drop_duplicates(["ChaveInstrumento", "NumeroMedicao", "AnoMedicao"])
        adit = m[m["NumeroTermoContratualAlteracao"].str.strip() != ""].drop_duplicates(
            ["ChaveInstrumento", "NumeroTermoContratualAlteracao", "AnoTermoContratualAlteracao"])
        agg = pd.DataFrame({
            "medicoes": med.groupby("ChaveInstrumento").size(), "valor_medido": med.groupby("ChaveInstrumento")["v_med"].sum(),
            "valor_pago_medicoes": med.groupby("ChaveInstrumento")["v_pag"].sum(),
            "ultima_medicao": med.groupby("ChaveInstrumento")["DataFimMedicao"].max().str[:10],
            "aditivos": adit.groupby("ChaveInstrumento").size(),
        })
        d = d.merge(agg, left_on="chave", right_index=True, how="left")
        d["pct_medido"] = (100 * d["valor_medido"] / d["valor"].where(d["valor"] > 0)).round(1)
    return d.reset_index(drop=True)


# ---------------------------------------------- contratações e itens (o que foi comprado)

#: Colunas do recorte de contratações que o painel usa (o arquivo tem 40).
COLUNAS_CONTRATACAO = ["cod_ibge", "ano", "contratacao", "ug", "objeto", "setor", "modalidade", "tipo", "situacao",
                       "url_edital", "valor_estimado", "valor_total", "vinculo", "q"]
#: Uma linha por item contratado, com o que dele foi medido.
COLUNAS_ITEM = ["cod_ibge", "ano", "contratacao", "chave", "ug", "lote", "item", "descricao", "unidade", "quantidade",
                "valor_unitario", "valor_total", "contratada", "cnpj_contratada", "medicoes", "quantidade_medida",
                "valor_medido", "aditivos", "valor_alterado", "vinculo", "q"]
#: Por que a linha entrou no recorte da Educação, da mais forte para a mais fraca.
VINCULO_ITEM = {
    "ug_educacao": "unidade gestora de educação (secretaria ou fundo municipal de educação)",
    "setor_educacao": "contratação com SetorBeneficiado \"Educação\"",
    "obra_educacao": "instrumento de obra com setor beneficiado \"Educação\"",
}


def _vinculo_educacao(linha: dict[str, str], ids_educacao: set[str], chaves_obra: set[str]) -> str | None:
    """Regra que põe uma linha de contratação/item na Educação — ou None.

    Só regras que a própria fonte afirma. O CNPJ da contratada NÃO entra: medido em
    2022, casar item com credor da função 12 pelo CNPJ traria 47% de todos os itens do
    Estado (a empresa que vende à educação também vende ao resto da prefeitura).
    """
    if EDUCACAO.search(norm(linha.get("NomeUnidadeGestoraReferencia"))):
        return "ug_educacao"
    if linha.get("IdentificacaoContratacao") in ids_educacao:
        return "setor_educacao"
    if linha.get("ChaveInstrumento") in chaves_obra:
        return "obra_educacao"
    return None


def filtro_contratacoes(mun: Municipios) -> Callable[[dict[str, str]], str | None]:
    """Filtro do recorte de *Contratações*: município do ES + UG de educação ou setor Educação."""
    def manter(linha: dict[str, str]) -> str | None:
        if mun.cod(linha.get("NomeEsferaAdministrativa")) is None:
            return None
        if EDUCACAO.search(norm(linha.get("NomeUnidadeGestoraReferencia"))):
            return "ug_educacao"
        return "setor_educacao" if EDUCACAO.search(norm(linha.get("SetorBeneficiado"))) else None
    return manter


def filtro_itens(mun: Municipios, ids_educacao: set[str], chaves_obra: set[str]) -> Callable[[dict[str, str]], str | None]:
    """Filtro do recorte de *Itens - <ano>*: município do ES + uma das regras de `VINCULO_ITEM`."""
    def manter(linha: dict[str, str]) -> str | None:
        if mun.cod(linha.get("EsferaAdministrativa")) is None:
            return None
        return _vinculo_educacao(linha, ids_educacao, chaves_obra)
    return manter


def contratacoes_educacao(df: pd.DataFrame, mun: Municipios) -> pd.DataFrame:
    """Recorte de *Contratações* → contratações municipais da Educação, normalizadas."""
    if df.empty:
        return pd.DataFrame(columns=COLUNAS_CONTRATACAO)
    d = pd.DataFrame({
        "cod_ibge": df["NomeEsferaAdministrativa"].map(mun.cod),
        "ano": pd.to_numeric(df["AnoReferencia"], errors="coerce"),
        "contratacao": df["IdentificacaoContratacao"].str.strip(),
        "ug": df["NomeUnidadeGestoraReferencia"].str.strip(), "objeto": df["ObjetoContratacao"].str.strip(),
        "setor": df["SetorBeneficiado"].str.strip(), "modalidade": df["ModalidadeLicitacao"].str.strip(),
        "tipo": df["TipoContratacao"].str.strip(), "situacao": df["SituacaoContratacao"].str.strip(),
        "url_edital": df["UrlEdital"].str.strip(), "valor_estimado": num_br(df["ValorEstimado"]),
        "valor_total": num_br(df["ValorTotalContratacao"]),
        "vinculo": df["vinculo"] if "vinculo" in df else "setor_educacao",
    })
    d = d[d["cod_ibge"].notna() & d["ano"].notna()].astype({"cod_ibge": int, "ano": int})
    # A mesma contratação vem repetida por mês de referência: fica a declaração mais recente.
    d = d.drop_duplicates("contratacao", keep="last")
    return d.reindex(columns=COLUNAS_CONTRATACAO).reset_index(drop=True)


def itens_educacao(df: pd.DataFrame, mun: Municipios) -> pd.DataFrame:
    """Recorte de *Itens - <ano>* → uma linha por item contratado, com o medido somado.

    O arquivo repete o item: uma linha traz o CONTRATADO (sem medição nem alteração) e
    uma linha a mais por medição (com ``DescricaoItem`` vazia) e por termo de alteração.
    O exercício do item é o do INSTRUMENTO (como nas obras, onde o exercício é o da
    assinatura), não o da remessa — assim o mesmo item não conta duas vezes quando
    reaparece no arquivo do ano seguinte por causa de uma medição nova.
    """
    if df.empty:
        return pd.DataFrame(columns=COLUNAS_ITEM)
    d = df.copy()
    d["cod_ibge"] = d["EsferaAdministrativa"].map(mun.cod)
    d = d[d["cod_ibge"].notna()].copy()
    if d.empty:
        return pd.DataFrame(columns=COLUNAS_ITEM)
    d["cod_ibge"] = d["cod_ibge"].astype(int)
    d["ano"] = pd.to_numeric(d["AnoInstrumentoContratacao"], errors="coerce")
    for alternativa in ("AnoEdital", "AnoReferencia"):
        d["ano"] = d["ano"].fillna(pd.to_numeric(d[alternativa], errors="coerce"))
    d = d[d["ano"].notna()]
    if d.empty:
        return pd.DataFrame(columns=COLUNAS_ITEM)
    d["ano"] = d["ano"].astype(int)
    d["_chave"] = d["ChaveInstrumento"].str.strip() + "|" + d["CodigoLote"].str.strip() + "|" + d["CodigoItem"].str.strip()
    med_n = d["NumeroMedicao"].str.strip() != ""
    alt_n = d["NumeroTermoContratualAlteracao"].str.strip() != ""

    base = d[~med_n & ~alt_n].drop_duplicates("_chave", keep="first")
    item = pd.DataFrame({
        "cod_ibge": base["cod_ibge"], "ano": base["ano"], "contratacao": base["IdentificacaoContratacao"].str.strip(),
        "chave": base["ChaveInstrumento"].str.strip(), "ug": base["NomeUnidadeGestoraReferencia"].str.strip(),
        "lote": base["CodigoLote"].str.strip(), "item": base["CodigoItem"].str.strip(),
        "descricao": base["DescricaoItem"].str.strip().str.replace(r"\s+", " ", regex=True),
        "unidade": base["UnidadeMedida"].str.strip(), "quantidade": num_br(base["QuantidadeItemContratado"]),
        "valor_unitario": num_br(base["ValorUnitarioItemContratado"]), "valor_total": num_br(base["ValorTotalItemContratado"]),
        "contratada": base["NomeContratado1"].str.strip(), "cnpj_contratada": base["NumeroIdentificacaoContratado1"].str.strip(),
        "vinculo": base["vinculo"] if "vinculo" in base else "ug_educacao",
    }).set_index(base["_chave"])

    med = d[med_n].drop_duplicates(["_chave", "NumeroMedicao", "AnoMedicao"])
    if not med.empty:
        g = med.assign(q_med=num_br(med["QuantidadeItemMedido"]), v_med=num_br(med["ValorTotalItemMedido"])).groupby("_chave")
        item["medicoes"] = g.size()
        item["quantidade_medida"] = g["q_med"].sum()
        item["valor_medido"] = g["v_med"].sum()
    alt = d[alt_n].drop_duplicates(["_chave", "NumeroTermoContratualAlteracao", "AnoTermoContratualAlteracao"])
    if not alt.empty:
        g = alt.assign(v_alt=num_br(alt["ValorTotalItemAlterado"])).groupby("_chave")
        item["aditivos"] = g.size()
        item["valor_alterado"] = g["v_alt"].sum()
    return item.reindex(columns=COLUNAS_ITEM).reset_index(drop=True)


COLUNAS_ITENS_RESUMO = ["cod_ibge", "ano", "itens", "contratacoes", "contratadas", "valor_contratado", "valor_medido",
                        "vinculos", "q"]
COLUNAS_ITENS_CONTRATADA = ["cod_ibge", "ano", "cnpj_contratada", "contratada", "itens", "contratacoes",
                            "valor_contratado", "valor_medido", "q"]


def agregados_itens(partes: Iterable[pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Junta os recortes anuais, tira a repetição entre anos e monta as tabelas do painel.

    Cada parte já traz o `q` da SUA consulta (o arquivo de onde a linha veio) — o exercício
    do item é o do instrumento, que não é necessariamente o do arquivo, então a proveniência
    não pode ser deduzida do ano. Um item de contrato plurianual aparece no arquivo de cada
    ano em que teve medição: fica UMA linha (a do arquivo mais antigo, que declarou o
    contratado) e as medições de todos os anos somadas.
    """
    partes = [p for p in partes if not p.empty]
    if not partes:
        return {"itens": pd.DataFrame(columns=COLUNAS_ITEM),
                "itens_resumo": pd.DataFrame(columns=COLUNAS_ITENS_RESUMO),
                "itens_contratada": pd.DataFrame(columns=COLUNAS_ITENS_CONTRATADA)}
    d = pd.concat(partes, ignore_index=True)
    grupo = ["chave", "lote", "item"]
    somas = {c: d.groupby(grupo)[c].sum(min_count=1) for c in
             ("medicoes", "quantidade_medida", "valor_medido", "aditivos", "valor_alterado")}
    d = d.drop_duplicates(grupo, keep="first")          # as partes vêm em ordem de ano
    indice = pd.MultiIndex.from_frame(d[grupo])
    for c, s in somas.items():
        d[c] = s.reindex(indice).to_numpy()
    d = d.sort_values(["cod_ibge", "ano", "valor_total"], ascending=[True, True, False]).reset_index(drop=True)

    chave = ["cod_ibge", "ano"]
    junta = lambda s: juntar_ids(*sorted(set(s.dropna())))
    resumo = d.groupby(chave, as_index=False).agg(
        itens=("item", "size"), contratacoes=("contratacao", "nunique"), contratadas=("cnpj_contratada", "nunique"),
        valor_contratado=("valor_total", "sum"), valor_medido=("valor_medido", "sum"),
        vinculos=("vinculo", lambda s: ",".join(sorted(set(s.dropna())))), q=("q", junta))
    com_cnpj = d[d["cnpj_contratada"].astype("string").str.strip().fillna("").ne("")]
    por_contratada = com_cnpj.groupby(chave + ["cnpj_contratada", "contratada"], as_index=False).agg(
        itens=("item", "size"), contratacoes=("contratacao", "nunique"),
        valor_contratado=("valor_total", "sum"), valor_medido=("valor_medido", "sum"), q=("q", junta))
    return {"itens": d.reindex(columns=COLUNAS_ITEM),
            "itens_resumo": resumo.reindex(columns=COLUNAS_ITENS_RESUMO),
            "itens_contratada": por_contratada.reindex(columns=COLUNAS_ITENS_CONTRATADA)}


# ------------------------------------------------------------ empenhos (Nível 3)

COLUNAS_EMPENHO = ["Ano", "Mes", "EsferaAdministrativa", "UnidadeGestora", "CodigoSubFuncao",
                   "CodigoPrograma", "NomePrograma", "CodigoAcao", "NomeAcao", "CodigoCompleto", "CodigoModalidade",
                   "CodigoElemento", "DescricaoElemento", "CodigoFonteReduzida", "NomeFonteReduzida", "CodigoDetalhamento",
                   "NomeDetalhamento", "Empenhada", "Liquidada", "Paga", "NumeroEmpenho", "AnoEmpenho",
                   "NomeCredorFornecedor", "CodigoCredorFornecedor", "NomeIdentificacao"]

CONSELHO_ESCOLAR = re.compile(r"conselho (?:de |da |do )?escola|conselho escolar|caixa escolar|associacao (?:de pais|escola)|"
                              r"unidade executora|associacao de apoio a escola")
FUNPAES = re.compile(r"funpaes")


def so_educacao(bloco: pd.DataFrame) -> pd.DataFrame:
    """Filtro do recorte: função 12."""
    return bloco[bloco["CodigoFuncao"].str.strip().isin(["12", "012"])]


def empenhos(df: pd.DataFrame, mun: Municipios, ano: int | None = None) -> pd.DataFrame:
    """Recorte da função 12 → tabela normalizada (valores numéricos, IBGE, exceto intra).

    `ano` (o do arquivo) cobre linha sem ano; o arquivo é anual. O TCE-ES mudou os nomes
    das colunas de período em 2024 (`AnoReferencia`/`MesReferencia`): os dois layouts entram.
    """
    d = df.rename(columns={"AnoReferencia": "Ano", "MesReferencia": "Mes"}).reindex(columns=COLUNAS_EMPENHO).copy()
    d["cod_ibge"] = d["EsferaAdministrativa"].map(mun.cod)
    d = d[d["cod_ibge"].notna()]
    for c in ("Empenhada", "Liquidada", "Paga"):
        d[c] = num_br(d[c]).fillna(0.0)
    d["ano"] = pd.to_numeric(d["Ano"], errors="coerce")
    if ano is not None:
        d["ano"] = d["ano"].fillna(ano)
    d = d[d["ano"].notna()]
    d["ano"] = d["ano"].astype(int)
    d["cod_ibge"] = d["cod_ibge"].astype(int)
    d["intra"] = d["CodigoModalidade"].str.strip() == "91"
    d["credor_nome"] = d["NomeCredorFornecedor"].str.strip()
    d["credor"] = d["CodigoCredorFornecedor"].str.strip()
    return d


def reduzir_empenhos(d: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Uma parte do ano (~90 mil linhas, 150 MB) reduzida ao que os agregados precisam.

    Reduzir parte a parte é o que mantém a memória sob controle: juntar as 19 partes
    de 2021–2025 em memória passaria de 2,5 GB; as reduções somadas ficam em poucos MB.
    Tudo aqui é soma ou contagem, combinável entre partes (ver `agregados_empenhos`).
    """
    e = d[~d["intra"]]
    chave = ["cod_ibge", "ano"]
    conta = dict(empenhada=("Empenhada", "sum"), liquidada=("Liquidada", "sum"), paga=("Paga", "sum"),
                 lancamentos=("Empenhada", "size"))
    cons = e[e["credor_nome"].map(norm).str.contains(CONSELHO_ESCOLAR)]
    texto = (e["NomePrograma"] + " " + e["NomeAcao"] + " " + e["NomeDetalhamento"]).map(norm)
    return {
        # Credor × elemento × fonte: o elemento e a fonte "mais frequentes" saem daqui, por contagem.
        "credores": e.groupby(chave + ["credor", "credor_nome", "NomeIdentificacao", "DescricaoElemento",
                                       "CodigoFonteReduzida"], as_index=False).agg(**conta),
        # Empenhos distintos por credor (um empenho aparece em vários meses, logo em várias partes).
        "empenhos_ids": e[chave + ["credor", "NumeroEmpenho", "AnoEmpenho"]].drop_duplicates(),
        # Credor × ação: o cruzamento que o painel abre ao clicar num credor ou numa ação
        # ("quem recebeu, em qual ação, com que elemento e que fonte", num lugar só).
        "credor_acao": e.groupby(chave + ["CodigoAcao", "NomeAcao", "credor", "credor_nome", "NomeIdentificacao",
                                          "DescricaoElemento", "CodigoFonteReduzida"], as_index=False).agg(**conta),
        "acoes": e.groupby(chave + ["CodigoAcao", "NomeAcao", "CodigoSubFuncao"], as_index=False).agg(**conta),
        "fontes": e.groupby(chave + ["CodigoFonteReduzida", "NomeFonteReduzida", "CodigoDetalhamento",
                                     "NomeDetalhamento"], as_index=False).agg(**conta),
        "conselhos": cons.groupby(chave + ["credor", "credor_nome", "NomeAcao", "CodigoFonteReduzida"],
                                  as_index=False).agg(**conta),
        "funpaes": e[texto.str.contains(FUNPAES)].groupby(
            chave + ["NomeAcao", "DescricaoElemento", "credor", "credor_nome", "CodigoFonteReduzida"],
            as_index=False).agg(**conta),
        "obras_empenhos": e[e["CodigoElemento"].str.strip() == "51"].groupby(
            chave + ["credor", "credor_nome", "NomeAcao"], as_index=False).agg(**conta),
        "meses": e[chave].assign(mes=pd.to_numeric(e["Mes"], errors="coerce")).drop_duplicates(),
    }


def _mais_frequente(g: pd.DataFrame, chave: list[str], coluna: str, nome: str) -> pd.DataFrame:
    """Valor com mais lançamentos em cada grupo (o "elemento mais frequente" do credor)."""
    t = g.groupby(chave + [coluna], as_index=False)["lancamentos"].sum()
    t = t.sort_values("lancamentos", ascending=False).drop_duplicates(chave)
    return t[chave + [coluna]].rename(columns={coluna: nome})


def agregados_empenhos(partes: Any, q_por_ano: dict[int, str]) -> dict[str, pd.DataFrame]:
    """As tabelas do painel, combinando as reduções de cada parte (ou um recorte inteiro)."""
    if isinstance(partes, pd.DataFrame):
        partes = [reduzir_empenhos(partes)]
    partes = list(partes)
    if not partes:
        return {}
    junta = lambda k: pd.concat([p[k] for p in partes], ignore_index=True)
    chave = ["cod_ibge", "ano"]
    q = lambda df: df.assign(q=df["ano"].map(q_por_ano))
    somas = dict(empenhada=("empenhada", "sum"), liquidada=("liquidada", "sum"), paga=("paga", "sum"),
                 lancamentos=("lancamentos", "sum"))
    # Maiores credores (os 15 de cada município-ano); pessoa física (CPF) agregada numa linha.
    bruto = junta("credores")
    cred = bruto.groupby(chave + ["credor", "credor_nome", "NomeIdentificacao"], as_index=False).agg(**somas)
    cred["pessoa_fisica"] = cred["NomeIdentificacao"].str.upper().eq("CPF")
    cred.loc[cred["pessoa_fisica"], ["credor", "credor_nome"]] = ["(pessoa física)", "Pessoas físicas (CPF — agregado)"]
    cred = cred.groupby(chave + ["credor", "credor_nome", "pessoa_fisica"], as_index=False).agg(**somas)
    cred = cred[cred["empenhada"].abs() > 0.005]
    ids = junta("empenhos_ids").drop_duplicates()
    ids["credor"] = ids["credor"].where(~ids["credor"].isin(set(bruto.loc[bruto["NomeIdentificacao"].str.upper().eq("CPF"),
                                                                         "credor"])), "(pessoa física)")
    n_emp = ids.drop_duplicates().groupby(chave + ["credor"], as_index=False).size().rename(columns={"size": "empenhos"})
    cred = cred.merge(n_emp, on=chave + ["credor"], how="left")
    cred = cred.merge(_mais_frequente(bruto, chave + ["credor"], "DescricaoElemento", "elemento"),
                      on=chave + ["credor"], how="left")
    cred = cred.merge(_mais_frequente(bruto, chave + ["credor"], "CodigoFonteReduzida", "fonte"),
                      on=chave + ["credor"], how="left")
    cred["rank"] = cred.groupby(chave)["empenhada"].rank(ascending=False, method="first")
    credores = q(cred[cred["rank"] <= 15].drop(columns=["rank", "lancamentos"]))
    # Ações locais (nome dado pelo município) e fonte com detalhamento.
    acoes = junta("acoes").groupby(chave + ["CodigoAcao", "NomeAcao", "CodigoSubFuncao"], as_index=False).agg(**somas)
    acoes = q(acoes[acoes[["empenhada", "liquidada", "paga"]].abs().sum(axis=1) > 0.005].drop(columns="lancamentos"))
    fontes = junta("fontes").groupby(chave + ["CodigoFonteReduzida", "NomeFonteReduzida", "CodigoDetalhamento",
                                              "NomeDetalhamento"], as_index=False).agg(**somas)
    fontes = q(fontes[fontes["empenhada"].abs() > 0.005].drop(columns=["lancamentos", "liquidada"]))
    # Repasses do município a conselhos escolares — dinheiro municipal por escola.
    bruto_cons = junta("conselhos")
    conselhos = bruto_cons.groupby(chave + ["credor", "credor_nome"], as_index=False).agg(**somas)
    conselhos = conselhos[conselhos["empenhada"].abs() > 0.005]
    conselhos = conselhos.merge(_mais_frequente(bruto_cons, chave + ["credor"], "NomeAcao", "acao"),
                                on=chave + ["credor"], how="left")
    conselhos = q(conselhos.merge(_mais_frequente(bruto_cons, chave + ["credor"], "CodigoFonteReduzida", "fonte"),
                                  on=chave + ["credor"], how="left").drop(columns=["lancamentos", "liquidada"]))
    # FUNPAES (fundo estadual do PAES), identificado pelo município no programa, ação ou detalhamento.
    funpaes = junta("funpaes").groupby(chave + ["NomeAcao", "DescricaoElemento", "credor", "credor_nome",
                                                "CodigoFonteReduzida"], as_index=False).agg(**somas)
    funpaes = q(funpaes[funpaes["empenhada"].abs() > 0.005].drop(columns=["lancamentos", "liquidada"]))
    # Obras e instalações (elemento 51): quem executou — liga aos contratos pelo CNPJ.
    obras_emp = junta("obras_empenhos").groupby(chave + ["credor", "credor_nome", "NomeAcao"], as_index=False).agg(**somas)
    obras_emp = q(obras_emp[obras_emp["empenhada"].abs() > 0.005].drop(columns=["lancamentos", "liquidada"]))
    # Total do ano e completude: quais meses o arquivo do TCE-ES traz (o de 2023 não traz dezembro
    # para parte dos municípios — a soma do ano fica curta, e isso tem de aparecer).
    total = junta("acoes").groupby(chave, as_index=False).agg(tcees_emp_empenhada=("empenhada", "sum"),
                                                              tcees_emp_paga=("paga", "sum"))
    meses = junta("meses").drop_duplicates()
    m = meses.groupby(chave)["mes"].agg(
        tcees_emp_meses="nunique",
        tcees_emp_meses_ausentes=lambda s: ",".join(str(x) for x in range(1, 13) if x not in set(s.dropna().astype(int)))
    ).reset_index()
    total = total.merge(m, on=chave, how="left")
    return {"credores": credores, "acoes": acoes, "fontes": fontes, "conselhos": conselhos, "funpaes": funpaes,
            "obras_empenhos": obras_emp, "total": total, "credor_acao": credor_acao(junta("credor_acao"), q_por_ano)}


#: Credores mostrados no detalhamento de cada ação; o resto vai numa linha "demais".
MAIORES_POR_ACAO = 8
#: Credores do município-ano cujas linhas ficam INTEIRAS, mesmo fora dos maiores de cada
#: ação — são os que a tabela de credores exibe, e clicar neles tem de mostrar tudo.
MAIORES_CREDORES = 15


def credor_acao(bruto: pd.DataFrame, q_por_ano: dict[int, str] | None = None) -> pd.DataFrame:
    """Credor × ação, com os maiores de cada ação (e os maiores credores do ente) nominais.

    É o que sustenta o "ver detalhamento" sem embutir empenho a empenho. Guarda duas
    coisas: os `MAIORES_POR_ACAO` maiores credores DE CADA AÇÃO — para o detalhamento de
    uma ação — e todas as linhas dos `MAIORES_CREDORES` maiores credores DO MUNICÍPIO-ANO
    — para o detalhamento de um credor não vir vazio quando ele espalha o gasto por muitas
    ações. O que sobra vira uma linha "(demais)" por ação: some no valor, não desaparece.
    Pessoa física (CPF) é agregada, como na tabela de credores.
    """
    if bruto.empty:
        return pd.DataFrame(columns=["cod_ibge", "ano", "CodigoAcao", "NomeAcao", "credor", "credor_nome", "elemento",
                                     "fonte", "empenhada", "liquidada", "paga", "demais", "q"])
    d = bruto.copy()
    fisica = d["NomeIdentificacao"].str.upper().eq("CPF")
    d.loc[fisica, ["credor", "credor_nome"]] = ["(pessoa física)", "Pessoas físicas (CPF — agregado)"]
    ente = ["cod_ibge", "ano"]
    chave = ente + ["CodigoAcao", "NomeAcao"]
    somas = dict(empenhada=("empenhada", "sum"), liquidada=("liquidada", "sum"), paga=("paga", "sum"),
                 lancamentos=("lancamentos", "sum"))
    por = d.groupby(chave + ["credor", "credor_nome"], as_index=False).agg(**somas)
    por = por[por[["empenhada", "liquidada", "paga"]].abs().sum(axis=1) > 0.005]
    por = por.merge(_mais_frequente(d, chave + ["credor"], "DescricaoElemento", "elemento"), on=chave + ["credor"], how="left")
    por = por.merge(_mais_frequente(d, chave + ["credor"], "CodigoFonteReduzida", "fonte"), on=chave + ["credor"], how="left")
    por["rank"] = por.groupby(chave)["empenhada"].rank(ascending=False, method="first")
    no_ente = por.groupby(ente + ["credor"], as_index=False)["empenhada"].sum()
    no_ente["rank_ente"] = no_ente.groupby(ente)["empenhada"].rank(ascending=False, method="first")
    por = por.merge(no_ente.drop(columns="empenhada"), on=ente + ["credor"], how="left")
    fica = (por["rank"] <= MAIORES_POR_ACAO) | (por["rank_ente"] <= MAIORES_CREDORES)
    maiores = por[fica].drop(columns=["rank", "rank_ente", "lancamentos"]).assign(demais=0)
    cauda = por[~fica]
    if not cauda.empty:
        resto = cauda.groupby(chave, as_index=False).agg(empenhada=("empenhada", "sum"), liquidada=("liquidada", "sum"),
                                                         paga=("paga", "sum"), demais=("credor", "nunique"))
        resto["credor"], resto["credor_nome"] = "(demais)", "Demais credores da ação"
        resto["elemento"], resto["fonte"] = None, None
        maiores = pd.concat([maiores, resto], ignore_index=True)
    maiores["q"] = maiores["ano"].map(q_por_ano or {})
    return maiores.sort_values(chave + ["empenhada"], ascending=[True, True, True, True, False]).reset_index(drop=True)


def dotacao_acoes(df: pd.DataFrame, mun: Municipios) -> pd.DataFrame:
    """Despesas agregadas (função 12) → dotação × execução por ação, no ano (soma dos meses)."""
    d = df.copy()
    d["cod_ibge"] = d["EsferaAdministrativa"].map(mun.cod)
    d = d[d["cod_ibge"].notna() & (d["CodigoModalidade"].str.strip() != "91")]
    for c in ("PrevisaoInicial", "PrevisaoAtualizada", "Empenhada", "Liquidada", "Paga"):
        d[c] = num_br(d[c]).fillna(0.0)
    d["ano"] = pd.to_numeric(d["Ano"], errors="coerce").astype(int)
    d["cod_ibge"] = d["cod_ibge"].astype(int)
    d["obra"] = (d["CodigoElemento"].str.strip() == "51") | d["NomeAcao"].map(norm).str.contains(r"constru|reforma|amplia|obra")
    return d.groupby(["cod_ibge", "ano", "CodigoAcao", "NomeAcao", "obra"], as_index=False)[
        ["PrevisaoInicial", "PrevisaoAtualizada", "Empenhada", "Liquidada", "Paga"]].sum()


# --------------------------------------------------------------------- execução

@dataclass
class ResultadoTcees:
    mde: pd.DataFrame
    pcm: pd.DataFrame
    pcm_resumo: pd.DataFrame
    obras: pd.DataFrame
    empenhos: dict[str, pd.DataFrame]
    dotacao: pd.DataFrame
    consultas: Registro
    avisos: list[dict[str, Any]]
    status: dict[str, Any]
    q: dict[str, Any] = field(default_factory=dict)   # ids de consulta por recurso (e por ano, nos anuais)
    contratacoes: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=COLUNAS_CONTRATACAO))
    itens: dict[str, pd.DataFrame] = field(default_factory=dict)


def partes_empenhos(cliente: ClienteTcees, anos: Iterable[int]) -> list[tuple[int, dict[str, Any]]]:
    saida = []
    for ano in anos:
        for r in cliente.recursos(DATASET_EMPENHOS):
            achado = re.fullmatch(rf"municipios-despesas-empenhos-(\d)-{ano}", r["nome"].strip())
            if achado and (r.get("tamanho") or 0) != 572:  # 572 bytes = ZIP vazio de mês futuro
                saida.append((ano, r))
    return saida


def recurso_itens(cliente: ClienteTcees, ano: int) -> dict[str, Any] | None:
    """Recurso "Itens - <ano>" do dataset de contratações (existe de 2022 em diante)."""
    return next((r for r in cliente.recursos(DATASET_CONTRATACOES) if norm(r["nome"]) == f"itens - {ano}"), None)


def executar(nomes_ibge: dict[int, str], anos: Iterable[int], *, atualizar: str = "nao", com_empenhos: bool = True,
             com_medicoes: bool = True, com_itens: bool = True, hoje: datetime | None = None) -> ResultadoTcees:
    """Coleta (ou lê do cache) e extrai tudo do TCE-ES. Cada recurso que falha vira aviso."""
    hoje = hoje or datetime.now(timezone.utc)
    anos = list(anos)
    cliente = ClienteTcees(atualizar=atualizar)
    mun = Municipios(nomes_ibge)
    reg = Registro()
    avisos: list[dict[str, Any]] = []
    q: dict[str, Any] = {}

    def tentar(rotulo: str, funcao: Callable[[], Any]) -> Any:
        try:
            return funcao()
        except ErroTcees as exc:
            avisos.append({"recurso": rotulo, "aviso": str(exc)})
        except (ValueError, KeyError, zipfile.BadZipFile, requests.RequestException) as exc:
            avisos.append({"recurso": rotulo, "aviso": f"{type(exc).__name__}: {exc}"})
        return None

    def pequeno(chave: str, descricao: str) -> pd.DataFrame | None:
        a = tentar(chave, lambda: cliente.pequeno(chave))
        if a is None or not a.obtido_em:
            avisos.append({"recurso": chave, "aviso": "não coletado (modo offline sem cache, ou recurso não achado)"})
            return None
        c = a.consulta(descricao)
        reg.adicionar(c)
        q[chave] = c.id
        return tentar(chave, lambda: ler_dat(a))

    df = pequeno("educacao", "TCE-ES — Educação: índice de MDE apurado pelo Tribunal (CidadES)")
    mde = mde_tcees(df, mun) if df is not None else pd.DataFrame()
    df = pequeno("pcm", "TCE-ES — Prestação de Contas Municipal: homologação e data-limite das remessas")
    pcm = remessas_pcm(df, mun, hoje) if df is not None else pd.DataFrame()
    obras_df = pequeno("obras", "TCE-ES — Contratações: obras e serviços de engenharia")
    bens_df = pequeno("bens", "TCE-ES — Contratações: bens vinculadores (o prédio de cada contrato)")

    med = None
    if com_medicoes and obras_df is not None:
        chaves = set(obras_df.loc[obras_df["SetorBeneficiado"].map(norm).str.contains(EDUCACAO), "ChaveInstrumento"])
        rec = tentar("medicoes", lambda: cliente.achar(*RECURSOS["medicoes"]))
        url = rec["url"] if rec else ""
        a = tentar("medicoes", lambda: cliente.recorte_csv_fluxo("medicoes_educacao", url,
                   lambda l: l.get("ChaveInstrumento") in chaves, {"recurso": rec["nome"] if rec else None,
                                                                   "filtro": "ChaveInstrumento das obras da Educação"}))
        if a is not None and a.obtido_em:
            c = a.consulta("TCE-ES — Instrumentos contratuais com medições e alterações (recorte: obras da Educação)")
            reg.adicionar(c)
            q["medicoes"] = c.id
            med = tentar("medicoes", lambda: ler_recorte(a))
    obras = obras_educacao(obras_df, bens_df if bens_df is not None else pd.DataFrame(), med, mun) \
        if obras_df is not None else pd.DataFrame()
    if not obras.empty:
        obras["q"] = juntar_ids(q.get("obras"), q.get("bens"), q.get("medicoes"))
    if not pcm.empty:
        pcm["q"] = q.get("pcm")

    # Contratações e itens: O QUE foi comprado. O recorte das contratações dá as chaves
    # da Educação; os itens de cada ano entram por elas (ver `VINCULO_ITEM`).
    contratacoes = pd.DataFrame(columns=COLUNAS_CONTRATACAO)
    itens: dict[str, pd.DataFrame] = {}
    if com_itens:
        rec = tentar("contratacoes", lambda: cliente.achar(*RECURSOS["contratacoes"]))
        a = tentar("contratacoes", lambda: cliente.recorte_csv_fluxo(
            "contratacoes_educacao", rec["url"] if rec else "", filtro_contratacoes(mun),
            {"recurso": rec["nome"] if rec else None,
             "filtro": "município do ES + unidade gestora de educação ou SetorBeneficiado \"Educação\""},
            coluna_extra="vinculo"))
        if a is not None and a.obtido_em:
            c = a.consulta("TCE-ES — Contratações (recorte: as da Educação nos municípios)")
            reg.adicionar(c)
            q["contratacoes"] = c.id
            if (t := tentar("contratacoes", lambda: ler_recorte(a))) is not None:
                contratacoes = contratacoes_educacao(t, mun).assign(q=c.id)
        ids_educacao = set(contratacoes["contratacao"].dropna())
        chaves_obra = set(obras["chave"].dropna()) if not obras.empty else set()
        q["itens"] = {}
        partes_itens = []
        for ano in anos:
            rec = tentar("itens", lambda: recurso_itens(cliente, ano))
            if rec is None:
                continue        # os arquivos de Itens começam em 2022
            chave = f"itens/{ano}"
            a = tentar(chave, lambda: cliente.recorte_csv_fluxo(
                chave, rec["url"], filtro_itens(mun, ids_educacao, chaves_obra),
                {"recurso": rec["nome"], "filtro": "município do ES + " + "; ".join(VINCULO_ITEM)},
                coluna_extra="vinculo"))
            if a is None or not a.obtido_em:
                continue
            c = a.consulta(f"TCE-ES — Itens das contratações, {ano} (recorte: os da Educação)")
            reg.adicionar(c)
            q["itens"][ano] = c.id
            if (t := tentar(chave, lambda: ler_recorte(a))) is not None:
                if (i := tentar(chave, lambda: itens_educacao(t, mun))) is not None:
                    partes_itens.append(i.assign(q=c.id))
                del t
        itens = agregados_itens(partes_itens)

    agregados: dict[str, pd.DataFrame] = {}
    dot = pd.DataFrame()
    if com_empenhos:
        q["empenhos"], q["despesas"] = {}, {}
        tabelas = []
        for ano, r in (tentar("empenhos", lambda: partes_empenhos(cliente, anos)) or []):
            chave = f"empenhos/{ano}/{r['nome'].strip()}"
            a = tentar(chave, lambda: cliente.recorte_zip(chave, r["url"], so_educacao,
                                                           {"recurso": r["nome"], "filtro": "CodigoFuncao = 12"}))
            if a is None or not a.obtido_em:
                continue
            c = a.consulta(f"TCE-ES — Empenhos dos municípios, {r['nome'].strip()} (recorte: função 12)")
            reg.adicionar(c)
            q["empenhos"].setdefault(ano, []).append(c.id)
            if (t := tentar(chave, lambda: ler_recorte(a))) is not None:
                if (e := tentar(chave, lambda: reduzir_empenhos(empenhos(t, mun, ano)))) is not None:
                    tabelas.append(e)   # a parte inteira é descartada aqui; só a redução fica
                del t
        if tabelas:
            agregados = agregados_empenhos(tabelas, {a: ";".join(ids) for a, ids in q["empenhos"].items()})
            nomes = {c: n for c, n in nomes_ibge.items()}
            for r in agregados["total"].itertuples(index=False):
                if r.tcees_emp_meses_ausentes and r.ano < hoje.year:
                    avisos.append({"recurso": f"empenhos/{r.ano}",
                                   "aviso": f"{nomes.get(r.cod_ibge, r.cod_ibge)}: arquivo do TCE-ES sem o(s) mês(es) "
                                            f"{r.tcees_emp_meses_ausentes} de {r.ano} — soma do ano incompleta"})
        for ano in anos:
            rec = tentar("despesas", lambda: next((x for x in cliente.recursos(DATASET_DESPESAS)
                                                   if norm(x["nome"]) == f"municipios-despesas-{ano}.zip"), None))
            if rec is None:
                continue
            chave = f"despesas/{ano}"
            a = tentar(chave, lambda: cliente.recorte_zip(chave, rec["url"], so_educacao,
                                                           {"recurso": rec["nome"], "filtro": "CodigoFuncao = 12"}))
            if a is None or not a.obtido_em:
                continue
            c = a.consulta(f"TCE-ES — Despesas dos municípios (agregado com dotação), {ano} (recorte: função 12)")
            reg.adicionar(c)
            q["despesas"][ano] = c.id
            if (t := tentar(chave, lambda: ler_recorte(a))) is not None:
                dot = pd.concat([dot, dotacao_acoes(t, mun).assign(q=c.id)], ignore_index=True)

    status = {"fonte": "TCE-ES", "ok": True, "servidor_recusou": cliente.recusou, "avisos": len(avisos),
              "mde_linhas": len(mde), "pcm_linhas": len(pcm), "obras_educacao": len(obras),
              "empenhos_partes": sum(len(v) for v in q.get("empenhos", {}).values()),
              "contratacoes_educacao": len(contratacoes), "itens_educacao": len(itens.get("itens", [])),
              "itens_anos": sorted(q.get("itens", {})), "extraido_em": reg.extraido_em("TCE-ES")}
    return ResultadoTcees(mde, pcm, resumo_pcm(pcm), obras, agregados, dot, reg, avisos, status, q,
                          contratacoes=contratacoes, itens=itens)


def main(argv: Iterable[str] | None = None) -> int:
    """Religa só o TCE-ES: ``python -m financiamento.etl.tcees --anos 2021-2025``."""
    from . import entes as mod_entes
    from .cliente import ClienteSiconfi
    from .pipeline import parse_anos

    p = argparse.ArgumentParser(description="TCE-ES: MDE do Tribunal, prazos, obras e empenhos da Educação.")
    p.add_argument("--anos", type=parse_anos, required=True)
    p.add_argument("--atualizar", choices=("nao", "vazios", "tudo", "offline"), default="nao")
    p.add_argument("--sem-empenhos", action="store_true", help="pula os empenhos e as despesas agregadas (~600 MB)")
    p.add_argument("--sem-medicoes", action="store_true", help="pula o arquivo de medições (1,2 GB lido em fluxo)")
    p.add_argument("--sem-itens", action="store_true", help="pula contratações e itens (~1,1 GB lido em fluxo)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    lista = mod_entes.listar_entes_es(ClienteSiconfi(atualizar="nao"))
    r = executar({e.cod_ibge: e.nome for e in lista if e.esfera == "M"}, args.anos, atualizar=args.atualizar,
                 com_empenhos=not args.sem_empenhos, com_medicoes=not args.sem_medicoes,
                 com_itens=not args.sem_itens)
    destino = PROCESSADO / "fontes" / "tcees"
    destino.mkdir(parents=True, exist_ok=True)
    for nome, df in (("mde_tcees", r.mde), ("remessas_pcm", r.pcm), ("obras_educacao", r.obras), ("dotacao_acoes", r.dotacao),
                     ("contratacoes_educacao", r.contratacoes),
                     *((f"empenhos_{k}", v) for k, v in r.empenhos.items()),
                     *((k, v) for k, v in r.itens.items())):
        df.to_csv(destino / f"{nome}.csv", index=False, encoding="utf-8")
    pd.DataFrame(r.avisos, columns=["recurso", "aviso"]).to_csv(destino / "avisos.csv", index=False, encoding="utf-8")
    pd.DataFrame(r.consultas.como_linhas()).to_csv(destino / "consultas.csv", index=False, encoding="utf-8")
    print(json.dumps(r.status, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
