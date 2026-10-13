"""Completude da prestação de contas: `/extrato_entregas` do SICONFI × prazos da LRF.

Consulta (uma por ente e exercício): ``/extrato_entregas?id_ente=<IBGE7>&an_referencia=<ano>``

Estrutura REAL (conferida em 2026-09-22, Vitória, Cachoeiro e Afonso Cláudio,
2023–2024): uma linha por instituição × entregável × período, com os campos::

    exercicio, cod_ibge, populacao, instituicao, entregavel, periodo,
    periodicidade, status_relatorio, data_status, forma_envio, tipo_relatorio

* `instituicao`: "Prefeitura Municipal de … - ES" ou "Câmara de Vereadores de …"
  — o RGF e a MSC são entregues pelas duas; RREO e DCA, só pela Prefeitura.
* `entregavel`: "Balanço Anual (DCA)", "Relatório Resumido de Execução
  Orçamentária" (também para quem publica o RREO Simplificado), "Relatório de
  Gestão Fiscal", "Relatório de Gestão Fiscal Simplificado", "MSC Agregada",
  "MSC Encerramento".
* `periodicidade`: A, B (bimestral), Q (quadrimestral), S (semestral), M.
* `status_relatorio`: HO (homologado), RE (retificado) ou vazio (MSC).
* `data_status`: instante, em UTC, do status ATUAL. **A API não traz prazo** —
  ele sai da lei (abaixo). Se o relatório foi retificado (RE), a data é a da
  retificação, não a da entrega original; por isso atraso só é afirmado para
  status HO, e o RE aparece como "retificado".

Prazos (LRF, Lei Complementar nº 101/2000):
* RREO — até 30 dias após o encerramento do bimestre (art. 52);
* RGF — até 30 dias após o encerramento do quadrimestre ou, na opção do art. 63
  (municípios com menos de 50 mil habitantes), do semestre (art. 55, § 2º);
* DCA — Municípios encaminham as contas à União até 30 de abril do ano seguinte
  (art. 51, § 1º, I).
O instante da entrega é convertido para o horário de Brasília (UTC−3; não há
horário de verão desde 2019) antes de comparar com a data-limite.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

import pandas as pd

from .cliente import ClienteSiconfi, Resposta
from .entes import Ente
from .parsing import norm
from .proveniencia import Consulta, caminho_relativo

ENDPOINT = "extrato_entregas"
BRASILIA = timezone(timedelta(hours=-3))

FUNDAMENTO = {
    "RREO": "LRF, art. 52: até 30 dias após o encerramento do bimestre",
    "RGF": "LRF, art. 55, § 2º: até 30 dias após o encerramento do período (quadrimestre, ou semestre na opção do art. 63)",
    "DCA": "LRF, art. 51, § 1º, I: Municípios encaminham as contas à União até 30 de abril do ano seguinte",
}


def coletar(cliente: ClienteSiconfi, ente: Ente, ano: int) -> tuple[Resposta, Consulta]:
    p = {"id_ente": ente.cod_ibge, "an_referencia": ano}
    r = cliente.consultar(ENDPOINT, **p)
    return r, Consulta(fonte="SICONFI", recurso=ENDPOINT, descricao=f"Extrato de entregas, exercício {ano}",
                       url=cliente.url_completa(ENDPOINT, p), obtido_em=r.obtido_em, arquivo=caminho_relativo(r.arquivo))


# ------------------------------------------------------------------ classificação

def tipo_entregavel(texto: Any) -> str | None:
    """Nome do entregável → RREO / RGF / DCA / MSC (ou None se desconhecido)."""
    t = norm(texto)
    if "resumido" in t or t.startswith("rreo"):
        return "RREO"
    if "gestao fiscal" in t or t.startswith("rgf"):
        return "RGF"
    if "dca" in t or "balanco anual" in t:
        return "DCA"
    if t.startswith("msc"):
        return "MSC"
    return None


def poder(instituicao: Any) -> str:
    t = norm(instituicao)
    if t.startswith("prefeitura"):
        return "Prefeitura"
    if t.startswith("camara"):
        return "Câmara"
    return "Outra"


def _fim_do_mes(ano: int, mes: int) -> date:
    return date(ano, mes, monthrange(ano, mes)[1])


def prazo(tipo: str, ano: int, periodo: int, periodicidade: str | None = None) -> date:
    """Data-limite legal de um relatório (ver docstring do módulo)."""
    if tipo == "RREO":
        return _fim_do_mes(ano, 2 * periodo) + timedelta(days=30)
    if tipo == "RGF":
        meses = 6 if periodicidade == "S" else 4
        return _fim_do_mes(ano, meses * periodo) + timedelta(days=30)
    if tipo == "DCA":
        return date(ano + 1, 4, 30)
    raise ValueError(f"sem prazo definido para {tipo!r}")


def data_local(iso_utc: Any) -> date | None:
    if not iso_utc:
        return None
    instante = datetime.fromisoformat(str(iso_utc).replace("Z", "+00:00"))
    return instante.astimezone(BRASILIA).date()


def situacoes(itens: Iterable[dict[str, Any]], cod_ibge: int, ano: int, hoje: date) -> list[dict[str, Any]]:
    """Uma linha por obrigação esperada (instituição × relatório × período), com a situação.

    Esperado: Prefeitura entrega DCA (1), RREO (6) e RGF; Câmara entrega RGF. A
    periodicidade do RGF (quadrimestral ou semestral) é a que o próprio ente usou
    no ano; sem nenhuma entrega de RGF, assume-se a quadrimestral (a regra geral)
    e isso fica anotado.
    """
    registros = []
    for l in itens:
        tipo = tipo_entregavel(l.get("entregavel"))
        if tipo in {"RREO", "RGF", "DCA"}:
            registros.append({**l, "_tipo": tipo, "_poder": poder(l.get("instituicao"))})

    periodicidade_rgf: dict[str, str] = {}
    for r in registros:
        if r["_tipo"] == "RGF" and r.get("periodicidade") in {"Q", "S"}:
            periodicidade_rgf.setdefault(r["_poder"], r["periodicidade"])

    esperado: list[tuple[str, str, int, str | None, str]] = [("Prefeitura", "DCA", 1, "A", "")]
    esperado += [("Prefeitura", "RREO", b, "B", "") for b in range(1, 7)]
    for pod in ("Prefeitura", "Câmara"):
        per = periodicidade_rgf.get(pod)
        nota = "" if per else "sem RGF no extrato: periodicidade quadrimestral assumida (regra geral)"
        per = per or "Q"
        esperado += [(pod, "RGF", n, per, nota) for n in range(1, (3 if per == "Q" else 2) + 1)]

    saida = []
    for pod, tipo, periodo, periodicidade, nota in esperado:
        achados = [r for r in registros if r["_poder"] == pod and r["_tipo"] == tipo and int(r.get("periodo") or 0) == periodo]
        limite = prazo(tipo, ano, periodo, periodicidade)
        linha: dict[str, Any] = {
            "cod_ibge": cod_ibge, "ano": ano, "poder": pod, "relatorio": tipo, "periodo": periodo,
            "periodicidade": periodicidade, "prazo": limite.isoformat(), "fundamento": FUNDAMENTO[tipo],
            "instituicao": achados[0].get("instituicao") if achados else None, "status": None,
            "data_status": None, "data_local": None, "dias_atraso": None, "observacao": nota or None,
        }
        if not achados:
            linha["situacao"] = "nao_entregue" if hoje > limite else "prazo_aberto"
            if hoje > limite:
                linha["dias_atraso"] = (hoje - limite).days
        else:
            # Mais de um registro (raro): vale o mais antigo — é a entrega, não a retificação.
            primeiro = min(achados, key=lambda r: str(r.get("data_status") or "9999"))
            quando = data_local(primeiro.get("data_status"))
            status = primeiro.get("status_relatorio")
            linha.update(status=status, data_status=primeiro.get("data_status"),
                         data_local=quando.isoformat() if quando else None)
            if status == "RE":
                linha["situacao"] = "retificado"  # a data é da retificação: não prova atraso da entrega
                if quando and quando > limite:
                    linha["observacao"] = "retificado depois do prazo; a data da entrega original não consta do extrato"
            elif quando is None:
                linha["situacao"] = "sem_data"
            elif quando > limite:
                linha["situacao"] = "entregue_com_atraso"
                linha["dias_atraso"] = (quando - limite).days
            else:
                linha["situacao"] = "no_prazo"
        saida.append(linha)
    return saida


SITUACOES_IRREGULARES = ("entregue_com_atraso", "nao_entregue")


def resumo_por_municipio(df: pd.DataFrame) -> pd.DataFrame:
    """Por município e exercício: quantas obrigações em atraso ou não entregues."""
    if df.empty:
        return pd.DataFrame(columns=["cod_ibge", "ano", "obrigacoes", "no_prazo", "com_atraso", "nao_entregues",
                                     "retificados", "maior_atraso_dias", "irregular"])
    g = df.groupby(["cod_ibge", "ano"])
    saida = pd.DataFrame({
        "obrigacoes": g.size(),
        "no_prazo": g["situacao"].apply(lambda s: int((s == "no_prazo").sum())),
        "com_atraso": g["situacao"].apply(lambda s: int((s == "entregue_com_atraso").sum())),
        "nao_entregues": g["situacao"].apply(lambda s: int((s == "nao_entregue").sum())),
        "retificados": g["situacao"].apply(lambda s: int((s == "retificado").sum())),
        "maior_atraso_dias": g["dias_atraso"].max(),
    }).reset_index()
    saida["irregular"] = (saida["com_atraso"] + saida["nao_entregues"]) > 0
    return saida
