"""SIOPE (FNDE): RREO Anexo 8 (MDE) em PDF — índice legal de MDE e FUNDEB 70%.

**Por que PDF, e não o HTML dos "Relatórios Municipais".** Em 2026-09-22 todos
os relatórios de https://www.fnde.gov.br/siope/relatoriosMunicipais.jsp
(`dadosInformadosMunicipio.do`, `relatorioRREOMunicipal2006.do`,
`indicadoresFinanceirosEEducacionais.do`, `demonstrativoFuncaoEducacao.do`)
exigem reCAPTCHA — e contornar CAPTCHA não é opção. O próprio formulário do RREO
aponta o arquivo que o SIOPE gera, publicado no FTP aberto do FNDE::

    ftp://ftp.fnde.gov.br/web/siope/RREO/RREO_Municipal_<IBGE6>_<bimestre>_<ano>.pdf

`IBGE6` = código IBGE sem o dígito verificador (Vitória 3205309 → 320530). O
FTP tem os 78 municípios do ES de 2010 a 2026, bimestres 1 a 6. Usa-se o 6º
bimestre (o exercício fechado). É a "Tabela 8.3 — Demonstrativo das Receitas e
Despesas com MDE — Municípios", com os percentuais JÁ APURADOS pelo SIOPE.

**Fonte sem SLA.** O layout muda: 2021–2022 numeram os itens de 1 a 54, 2023 de
1 a 45, 2024–2025 de 1 a 40. Por isso os itens são achados pelo RÓTULO, não
pelo número, e cada indicador é conferido por dentro (o percentual declarado
tem de bater com o recalculado a partir dos valores da mesma linha). Qualquer
falha — arquivo ausente, PDF ilegível, rótulo não achado, conferência que não
fecha — vira AVISO do município-ano; nunca derruba o pipeline.

Rótulos usados (sem acento/caixa; a numeração varia por exercício):

======================================================  =====================================
Rótulo no Anexo 8                                       Campo
======================================================  =====================================
"1- RECEITA DE IMPOSTOS"                                receita de impostos próprios (b)
"TOTAL DA RECEITA RESULTANTE DE IMPOSTOS (1 + 2)"       receita resultante de impostos (b)
"TOTAL DESTINADO AO FUNDEB"                             contribuição ao FUNDEB (b)
"TOTAL DAS RECEITAS DO FUNDEB RECEBIDAS" (2023+) /      FUNDEB recebido (b)
"RECEITAS RECEBIDAS DO FUNDEB" (2021–2022)
"MÍNIMO DE 70% DO FUNDEB NA REMUNERAÇÃO …"              exigido, aplicado, considerado, %
"TOTAL DAS DESPESAS PARA FINS DE LIMITE"                despesa com MDE considerada no limite
"APLICAÇÃO EM MDE SOBRE A RECEITA [LÍQUIDA] DE          exigido, aplicado, %
IMPOSTOS"
"Salário-Educação", "PDDE", "PNAE", "PNATE"             receitas adicionais (b)
"TOTAL GERAL DAS DESPESAS COM EDUCAÇÃO"                 despesa total com educação (empenhada)
"VALOR NÃO COMPLEMENTADO DO TOTAL NÃO APLICADO EM MDE   compensação da EC 119/2022 embutida no
EM 2020 E 2021" (só 2023)                               valor exigido (última coluna)
======================================================  =====================================

**EC 119/2022.** Em 2023, o valor exigido do limite de MDE inclui o que o
município deixou de aplicar em 2020–2021 e ainda devia compensar; o % aplicado
não (continua sobre a receita líquida de impostos). Achado em cinco municípios
do ES: por isso a conferência desconta a compensação, e o painel mostra os dois
fatos — o % do ano e se o valor aplicado alcançou o exigido com a compensação.
"""

from __future__ import annotations

import argparse
import ftplib
import hashlib
import io
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .config import BRUTO, PROCESSADO
from .parsing import norm
from .proveniencia import Consulta, Registro, caminho_relativo

log = logging.getLogger(__name__)

FTP_HOST = "ftp.fnde.gov.br"
FTP_PASTA = "/web/siope/RREO"
BIMESTRE_ANUAL = 6
PASTA_CACHE = BRUTO / "siope"
URL_FORMULARIO = "https://www.fnde.gov.br/siope/relatoriosMunicipais.jsp"
MINIMO_MDE_PCT = 25.0
MINIMO_FUNDEB_PROFISSIONAIS_PCT = 70.0

#: Diferença tolerada (pontos percentuais) entre o % declarado no PDF e o recalculado.
TOLERANCIA_PCT = 0.02


def ibge6(cod_ibge: int) -> str:
    """Código IBGE de 7 dígitos → 6 dígitos (sem o verificador), como o SIOPE usa."""
    texto = str(cod_ibge)
    if not re.fullmatch(r"\d{7}", texto):
        raise ValueError(f"código IBGE de município deve ter 7 dígitos: {cod_ibge!r}")
    return texto[:6]


def nome_arquivo(cod_ibge: int, ano: int, bimestre: int = BIMESTRE_ANUAL) -> str:
    return f"RREO_Municipal_{ibge6(cod_ibge)}_{bimestre}_{ano}.pdf"


def url_ftp(cod_ibge: int, ano: int, bimestre: int = BIMESTRE_ANUAL) -> str:
    return f"ftp://{FTP_HOST}{FTP_PASTA}/{nome_arquivo(cod_ibge, ano, bimestre)}"


# ---------------------------------------------------------------- download + cache

class ErroSiope(RuntimeError):
    """Falha de rede no FTP depois das tentativas (não cacheada)."""


@dataclass(frozen=True, slots=True)
class Arquivo:
    """Um PDF do SIOPE no cache, ou a constatação (também cacheada) de que não existe."""

    existe: bool
    url: str
    obtido_em: str
    pdf: Path | None
    tamanho: int | None = None
    sha256: str | None = None
    modificado_ftp: str | None = None  # MDTM do servidor: quando o FNDE publicou/atualizou
    do_cache: bool = False


class ClienteFtpSiope:
    """Baixa os PDFs do FTP do FNDE com cache em `dados/bruto/siope/<ano>/`.

    Cada PDF fica ao lado de um `.json` com URL, instante da coleta, tamanho,
    SHA-256 e data de modificação no servidor. Arquivo inexistente no FTP também
    é cacheado (`existe: false`): "o município não tem o PDF" é um fato, diferente
    de "o FTP falhou". `atualizar` tem os mesmos modos do cliente do SICONFI.
    """

    def __init__(self, pasta: Path = PASTA_CACHE, *, atualizar: str = "nao", tentativas: int = 3,
                 pausa: float = 0.3, timeout: float = 60.0) -> None:
        if atualizar not in {"nao", "vazios", "tudo", "offline"}:
            raise ValueError(f"atualizar inválido: {atualizar!r}")
        self.pasta, self.atualizar, self.tentativas, self.pausa, self.timeout = pasta, atualizar, tentativas, pausa, timeout
        self._ftp: ftplib.FTP | None = None

    def _meta(self, cod_ibge: int, ano: int) -> Path:
        return self.pasta / str(ano) / (nome_arquivo(cod_ibge, ano)[:-4] + ".json")

    def _conexao(self) -> ftplib.FTP:
        if self._ftp is None:
            ftp = ftplib.FTP(FTP_HOST, timeout=self.timeout)
            ftp.login()
            ftp.cwd(FTP_PASTA)
            self._ftp = ftp
        return self._ftp

    def fechar(self) -> None:
        if self._ftp is not None:
            try:
                self._ftp.quit()
            except (OSError, ftplib.Error):
                pass
            self._ftp = None

    def _ler_cache(self, meta: Path) -> Arquivo | None:
        if self.atualizar == "tudo" or not meta.exists():
            return None
        d = json.loads(meta.read_text(encoding="utf-8"))
        if self.atualizar == "vazios" and not d["existe"]:
            return None
        pdf = meta.with_suffix(".pdf")
        if d["existe"] and not pdf.exists():
            return None
        return Arquivo(d["existe"], d["url"], d["obtido_em"], pdf if d["existe"] else None, d.get("tamanho"),
                       d.get("sha256"), d.get("modificado_ftp"), True)

    def baixar(self, cod_ibge: int, ano: int) -> Arquivo:
        meta = self._meta(cod_ibge, ano)
        if (em_cache := self._ler_cache(meta)) is not None:
            return em_cache
        url = url_ftp(cod_ibge, ano)
        if self.atualizar == "offline":
            return Arquivo(False, url, "", None)  # não coletado: quem chama distingue pelo `obtido_em` vazio
        nome = nome_arquivo(cod_ibge, ano)
        ultimo: Exception | None = None
        for tentativa in range(1, self.tentativas + 1):
            try:
                time.sleep(self.pausa)
                ftp = self._conexao()
                try:
                    modificado = ftp.sendcmd(f"MDTM {nome}").split()[-1]
                except ftplib.error_perm as exc:
                    if str(exc).startswith("550"):
                        return self._gravar(meta, Arquivo(False, url, _agora(), None))
                    raise
                buffer = io.BytesIO()
                ftp.retrbinary(f"RETR {nome}", buffer.write)
                dados = buffer.getvalue()
                pdf = meta.with_suffix(".pdf")
                pdf.parent.mkdir(parents=True, exist_ok=True)
                temporario = pdf.with_suffix(".tmp")
                temporario.write_bytes(dados)
                temporario.replace(pdf)
                quando = datetime.strptime(modificado[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                return self._gravar(meta, Arquivo(True, url, _agora(), pdf, len(dados), hashlib.sha256(dados).hexdigest(),
                                                  quando.isoformat(timespec="seconds")))
            except (OSError, EOFError, ftplib.Error) as exc:
                ultimo = exc
                self.fechar()
                log.warning("SIOPE %s: %s (tentativa %d)", nome, exc, tentativa)
                time.sleep(2.0 * tentativa)
        raise ErroSiope(f"{url}: falhou após {self.tentativas} tentativas: {ultimo}")

    @staticmethod
    def _gravar(meta: Path, a: Arquivo) -> Arquivo:
        meta.parent.mkdir(parents=True, exist_ok=True)
        corpo = {"url": a.url, "obtido_em": a.obtido_em, "existe": a.existe, "tamanho": a.tamanho,
                 "sha256": a.sha256, "modificado_ftp": a.modificado_ftp}
        meta.write_text(json.dumps(corpo, ensure_ascii=False, indent=1), encoding="utf-8")
        return a


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ PDF → itens

_MOEDA = re.compile(r"(?<![\d.,])-?\d{1,3}(?:\.\d{3})*,\d{2}(?![\d])")
_ITEM = re.compile(r"^(?P<numero>\d{1,2}(?:\.\d{1,2}){0,3})\s*-\s*(?P<resto>\S.*)$")
_PAGINA = re.compile(r"^=====PAGINA \d+=====$")


def texto_pdf(dados: bytes) -> str:
    """Texto do PDF, página a página (pypdf extrai os acentos corretamente em UTF-8)."""
    from pypdf import PdfReader  # import tardio: só esta fonte depende do pypdf

    leitor = PdfReader(io.BytesIO(dados))
    return "\n".join(p.extract_text() or "" for p in leitor.pages)


def data_geracao_pdf(dados: bytes) -> str | None:
    """`CreationDate` do PDF (quando o SIOPE gerou o demonstrativo), em ISO."""
    from pypdf import PdfReader

    bruto = (PdfReader(io.BytesIO(dados)).metadata or {}).get("/CreationDate")
    achado = re.match(r"D:(\d{14})", str(bruto or ""))
    if not achado:
        return None
    return datetime.strptime(achado[1], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat(timespec="seconds")


def numero_br(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


@dataclass
class Item:
    numero: str
    rotulo: str
    valores: list[float] = field(default_factory=list)

    @property
    def chave(self) -> str:
        return norm(self.rotulo)


def extrair_itens(texto: str) -> list[Item]:
    """Quebra o texto do demonstrativo em itens numerados ("10.1.3- Educação…").

    O rótulo é o texto antes do primeiro valor (pode ocupar várias linhas);
    os valores são os números em formato brasileiro até o próximo item. Texto
    depois dos valores (cabeçalho da tabela seguinte) é descartado.
    """
    itens: list[Item] = []
    atual: Item | None = None
    em_valores = False
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or _PAGINA.match(linha):
            continue
        achado = _ITEM.match(linha)
        if achado:
            atual = Item(achado["numero"], "")
            itens.append(atual)
            em_valores = False
            linha = achado["resto"]
        if atual is None:
            continue
        numeros = list(_MOEDA.finditer(linha))
        if not em_valores:
            corte = numeros[0].start() if numeros else len(linha)
            atual.rotulo = (atual.rotulo + " " + linha[:corte]).strip()
        if numeros:
            em_valores = True
            atual.valores.extend(numero_br(m.group()) for m in numeros)
    return itens


def _achar(itens: list[Item], padrao: str, *, n_valores: int | None = None) -> Item | None:
    """Primeiro item cujo rótulo normalizado casa com `padrao` (regex)."""
    rx = re.compile(padrao)
    for it in itens:
        if rx.search(it.chave) and (n_valores is None or len(it.valores) >= n_valores):
            return it
    return None


@dataclass
class ResultadoPDF:
    valores: dict[str, float | None]
    itens_usados: dict[str, str]           # campo → "item N — rótulo"
    avisos: list[str]


def indicadores(texto: str) -> ResultadoPDF:
    """Extrai os campos do Anexo 8 e confere cada indicador por dentro."""
    itens = extrair_itens(texto)
    v: dict[str, float | None] = {}
    usados: dict[str, str] = {}
    avisos: list[str] = []

    def pegar(campo: str, padrao: str, indice: int, n_min: int) -> Item | None:
        it = _achar(itens, padrao, n_valores=n_min)
        if it is None:
            v[campo] = None
            avisos.append(f"rótulo não encontrado: {campo}")
            return None
        v[campo] = it.valores[indice]
        usados[campo] = f"item {it.numero} — {it.rotulo}"
        return it

    # Receita (colunas: previsão atualizada (a), realizada até o bimestre (b)).
    pegar("receita_impostos_proprios", r"^receita de impostos$", 1, 2)
    pegar("receita_resultante_impostos", r"^total da receita resultante de impostos", 1, 2)
    pegar("destinado_fundeb", r"^total destinado ao fundeb", 1, 2)
    itf = pegar("fundeb_recebido", r"^(total das receitas do fundeb recebidas|receitas recebidas do fundeb)", 1, 2)
    # Só o PRINCIPAL (sem rendimentos de aplicação): é o que o DCA I-C lança como transferência
    # do FUNDEB — os rendimentos vão para a receita patrimonial. Soma os "N.x.1 - Principal"
    # dos quatro blocos (impostos, VAAF, VAAT, VAAR), qualquer que seja o número N do layout.
    v["fundeb_principal"] = None
    if itf:
        nivel = itf.numero.count(".") + 2
        principais = [it for it in itens if it.numero.startswith(itf.numero + ".") and it.numero.count(".") == nivel
                      and it.chave == "principal" and len(it.valores) >= 2]
        if principais:
            v["fundeb_principal"] = round(sum(it.valores[1] for it in principais), 2)
            usados["fundeb_principal"] = "itens " + ", ".join(it.numero for it in principais) + " — Principal"
    for campo, padrao in (("salario_educacao", r"^salario-educacao$"), ("pdde", r"^pdde$"),
                          ("pnae", r"^pnae$"), ("pnate", r"^pnate$")):
        pegar(campo, padrao, 1, 2)

    # Indicador do FUNDEB: exigido, aplicado, considerado após deduções, % aplicado.
    it70 = pegar("fundeb70_exigido", r"^minimo de 70% do fundeb na remuneracao", 0, 4)
    if it70:
        v["fundeb70_aplicado"], v["fundeb70_considerado"], v["fundeb70_pct"] = it70.valores[1:4]
        for c in ("fundeb70_aplicado", "fundeb70_considerado", "fundeb70_pct"):
            usados[c] = usados["fundeb70_exigido"]
        if v["fundeb70_exigido"]:
            recalculado = min(100.0, MINIMO_FUNDEB_PROFISSIONAIS_PCT * v["fundeb70_considerado"] / v["fundeb70_exigido"])
            if abs(recalculado - v["fundeb70_pct"]) > TOLERANCIA_PCT:
                avisos.append(f"FUNDEB 70%: % declarado {v['fundeb70_pct']} ≠ recalculado {recalculado:.2f}")
    else:
        v.update(fundeb70_aplicado=None, fundeb70_considerado=None, fundeb70_pct=None)

    # Limite do art. 212: exigido, aplicado, % aplicado.
    pegar("despesa_mde_limite", r"^total das despesas para fins de limite", 0, 1)
    # EC 119/2022 (só no layout de 2023): o que deixou de ser aplicado em 2020–2021 e
    # tinha de ser compensado entra no VALOR EXIGIDO — mas não no % aplicado, que
    # continua medido contra a receita líquida de impostos. Sem isto, o exigido de
    # quem tinha compensação pendente parece incoerente com o percentual.
    it119 = _achar(itens, r"^valor nao complementado do total nao aplicado em mde", n_valores=1)
    v["mde_compensacao_ec119"] = it119.valores[-1] if it119 else None
    if it119:
        usados["mde_compensacao_ec119"] = f"item {it119.numero} — {it119.rotulo}"
    it25 = pegar("mde_exigido", r"^aplicacao em mde sobre a receita", 0, 3)
    if it25:
        v["mde_aplicado"], v["mde_pct"] = it25.valores[1:3]
        usados["mde_aplicado"] = usados["mde_pct"] = usados["mde_exigido"]
        exigido_do_ano = v["mde_exigido"] - (v["mde_compensacao_ec119"] or 0.0)
        if exigido_do_ano > 0:
            recalculado = MINIMO_MDE_PCT * v["mde_aplicado"] / exigido_do_ano
            if abs(recalculado - v["mde_pct"]) > TOLERANCIA_PCT:
                avisos.append(f"MDE: % declarado {v['mde_pct']} ≠ recalculado {recalculado:.2f}")
        if v.get("despesa_mde_limite") is not None and abs(v["despesa_mde_limite"] - v["mde_aplicado"]) > 1.0:
            avisos.append("MDE: valor aplicado ≠ total das despesas para fins de limite")
    else:
        v.update(mde_aplicado=None, mde_pct=None)

    # Despesa total com educação (dotação, empenhada, liquidada, paga, RPNP): a empenhada.
    pegar("despesa_total_educacao", r"^total geral das despesas com educacao", 1, 4)

    # Conferência de receita: resultante de impostos ≥ impostos próprios.
    if None not in (v.get("receita_resultante_impostos"), v.get("receita_impostos_proprios")):
        if v["receita_resultante_impostos"] + 1.0 < v["receita_impostos_proprios"]:
            avisos.append("receita resultante de impostos menor que a receita de impostos próprios")
    return ResultadoPDF(v, usados, avisos)


# --------------------------------------------------------------------- execução

CAMPOS = ("receita_impostos_proprios", "receita_resultante_impostos", "destinado_fundeb", "fundeb_recebido",
          "fundeb_principal", "salario_educacao", "pdde", "pnae", "pnate", "fundeb70_exigido", "fundeb70_aplicado",
          "fundeb70_considerado", "fundeb70_pct", "despesa_mde_limite", "mde_exigido", "mde_aplicado", "mde_pct",
          "mde_compensacao_ec119", "despesa_total_educacao")


@dataclass
class ResultadoSiope:
    tabela: pd.DataFrame
    consultas: Registro
    avisos: list[dict[str, Any]]
    status: dict[str, Any]


def processar(cliente: ClienteFtpSiope, cod_ibge: int, ano: int) -> tuple[dict[str, Any], Consulta | None, list[str]]:
    """Um município-ano: baixa (ou lê do cache), extrai e confere. Nunca levanta por layout."""
    linha: dict[str, Any] = {"cod_ibge": cod_ibge, "ano": ano}
    arq = cliente.baixar(cod_ibge, ano)
    if not arq.obtido_em:
        return {**linha, "status_siope": "nao_coletado"}, None, []
    if not arq.existe:
        return {**linha, "status_siope": "sem_pdf_publicado"}, None, []
    consulta = Consulta(fonte="SIOPE", recurso="siope_rreo_anexo8", metodo="FTP RETR",
                        descricao=f"RREO Anexo 8 (MDE) gerado pelo SIOPE, 6º bimestre de {ano}",
                        url=arq.url, obtido_em=arq.obtido_em, arquivo=caminho_relativo(arq.pdf), sha256=arq.sha256)
    try:
        dados = arq.pdf.read_bytes()
        texto = texto_pdf(dados)
        r = indicadores(texto)
        gerado = data_geracao_pdf(dados)
    except Exception as exc:  # layout/arquivo: aviso, nunca erro fatal
        return {**linha, "status_siope": "pdf_ilegivel", "q": consulta.id}, consulta, [f"PDF ilegível: {exc}"]
    completos = r.valores.get("mde_pct") is not None and r.valores.get("fundeb70_pct") is not None
    return ({**linha, **r.valores, "status_siope": "ok" if completos else "parcial",
             "pdf_gerado_em": gerado, "pdf_publicado_em": arq.modificado_ftp, "q": consulta.id,
             "itens_usados": json.dumps(r.itens_usados, ensure_ascii=False)},
            consulta, r.avisos)


def executar(municipios: Iterable[int], anos: Iterable[int], *, atualizar: str = "nao") -> ResultadoSiope:
    """Todos os municípios × exercícios. Falha de um não interrompe os outros."""
    cliente = ClienteFtpSiope(atualizar=atualizar)
    registro = Registro()
    linhas: list[dict[str, Any]] = []
    avisos: list[dict[str, Any]] = []
    try:
        for ano in anos:
            for cod in municipios:
                try:
                    linha, consulta, msgs = processar(cliente, cod, ano)
                except ErroSiope as exc:
                    linha, consulta, msgs = {"cod_ibge": cod, "ano": ano, "status_siope": "falha_consulta"}, None, [str(exc)]
                if consulta is not None:
                    registro.adicionar(consulta)
                linhas.append(linha)
                avisos += [{"cod_ibge": cod, "ano": ano, "aviso": m} for m in msgs]
    finally:
        cliente.fechar()
    tabela = pd.DataFrame(linhas)
    for c in CAMPOS + ("status_siope", "pdf_gerado_em", "pdf_publicado_em", "q", "itens_usados"):
        if c not in tabela:
            tabela[c] = None
    contagem = tabela["status_siope"].value_counts().to_dict()
    status = {"fonte": "SIOPE", "ok": True, "linhas": len(tabela), "situacoes": contagem,
              "avisos": len(avisos), "extraido_em": registro.extraido_em("SIOPE")}
    return ResultadoSiope(tabela, registro, avisos, status)


def main(argv: Iterable[str] | None = None) -> int:
    """Religa só o SIOPE: `python -m financiamento.etl.siope --anos 2021-2025`."""
    from . import entes as mod_entes
    from .cliente import ClienteSiconfi
    from .pipeline import parse_anos

    p = argparse.ArgumentParser(description="Coleta o Anexo 8 (MDE) do SIOPE no FTP do FNDE e extrai os indicadores.")
    p.add_argument("--anos", type=parse_anos, required=True)
    p.add_argument("--atualizar", choices=("nao", "vazios", "tudo", "offline"), default="nao")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    lista = mod_entes.listar_entes_es(ClienteSiconfi(atualizar="nao"))
    r = executar([e.cod_ibge for e in lista if e.esfera == "M"], args.anos, atualizar=args.atualizar)
    destino = PROCESSADO / "fontes" / "siope"
    destino.mkdir(parents=True, exist_ok=True)
    r.tabela.to_csv(destino / "siope_anexo8.csv", index=False, encoding="utf-8")
    pd.DataFrame(r.avisos, columns=["cod_ibge", "ano", "aviso"]).to_csv(destino / "avisos.csv", index=False, encoding="utf-8")
    pd.DataFrame(r.consultas.como_linhas()).to_csv(destino / "consultas.csv", index=False, encoding="utf-8")
    print(json.dumps(r.status, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
