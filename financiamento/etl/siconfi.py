"""SICONFI — as partes do painel de auditoria que vão além do financiamento geral.

* **Receita por origem** (Fase 1): RREO Anexo 01, seis bimestres — `rreo_receita.py`.
* **FUNDEB recebido** (Fase 1): MSC, identificado pelos códigos do DCA I-C — `msc.py`.
* **Natureza econômica** (Fase 2, Nível 2) e **fluxo fonte → subfunção**: MSC.
* **Completude das entregas** (conformidade): `/extrato_entregas` × LRF — `entregas.py`.

O Nível 1 (despesa por função e subfunção: DCA I-E e RREO Anexo 02) continua no
financiamento geral, em `pipeline.py`, e é reaproveitado — não é refeito aqui.

Religar só o SICONFI (as outras fontes não são tocadas)::

    python -m financiamento.etl.siconfi --anos 2021-2025 [--atualizar vazios]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Mapping

import pandas as pd

from . import entregas, msc, rreo_receita
from .cliente import ClienteSiconfi, ErroSiconfi, NaoColetado
from .config import PROCESSADO
from .entes import Ente
from .proveniencia import Registro

log = logging.getLogger(__name__)

COLUNAS_RECEITA = ["cod_ibge", "ano", "bimestre", "tipo_rreo", "q", *rreo_receita.CHAVES]
COLUNAS_FLUXO = ["cod_ibge", "ano", "grupo", "fonte", "subfuncao", "empenhada", "q"]
COLUNAS_NATUREZA = ["cod_ibge", "ano", "categoria", "subcategoria", "elemento", "empenhada", "liquidada", "paga", "q"]
COLUNAS_MSC = ["cod_ibge", "ano", "status_msc", "fontes_msc", "msc_empenhada", "msc_liquidada", "msc_paga",
               "fundeb_msc_fundo", "fundeb_msc_complementacao", "fundeb_msc_total", "fundeb_msc_por_fonte",
               "fundeb_msc_prefixos", "receita_fnde_msc", "q_msc"]


@dataclass
class ResultadoSiconfi:
    receita_bimestral: pd.DataFrame
    msc: pd.DataFrame           # um registro por município-ano: situação, totais e FUNDEB
    fluxo: pd.DataFrame
    natureza: pd.DataFrame
    entregas: pd.DataFrame
    consultas: Registro
    avisos: list[dict[str, Any]] = field(default_factory=list)
    status: dict[str, Any] = field(default_factory=dict)


def prefixos_fundeb(contas_por_ano: Mapping[int, Iterable[dict[str, list[str]]]]) -> dict[int, tuple[list[str], list[str]]]:
    """Por exercício, os prefixos de natureza do FUNDEB (fundo, complementação).

    Os códigos do ementário são nacionais, não do município: junta-se o que o
    DCA I-C de todos os entes mostrou naquele exercício.
    """
    saida: dict[int, tuple[list[str], list[str]]] = {}
    for ano, lista in contas_por_ano.items():
        fundo: set[str] = set()
        compl: set[str] = set()
        for contas in lista:
            fundo.update(msc.prefixo_natureza(c) for c in contas.get("fundo", []))
            compl.update(msc.prefixo_natureza(c) for c in contas.get("complementacao", []))
        saida[ano] = (sorted(fundo), sorted(compl))
    return saida


def _msc_do_ente(cliente: ClienteSiconfi, ente: Ente, ano: int, prefixos: tuple[list[str], list[str]]
                 ) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, Any, list[str]]:
    linha: dict[str, Any] = {"cod_ibge": ente.cod_ibge, "ano": ano}
    vazio = pd.DataFrame()
    try:
        r, consulta = msc.coletar(cliente, ente.cod_ibge, ano)
    except NaoColetado:
        return {**linha, "status_msc": "nao_coletado"}, vazio, vazio, None, []
    except ErroSiconfi as exc:
        return {**linha, "status_msc": "falha_consulta"}, vazio, vazio, None, [f"MSC: {exc}"]
    if not r.itens:
        return {**linha, "status_msc": "sem_dado_publicado", "q_msc": consulta.id}, vazio, vazio, consulta, []
    avisos: list[str] = []
    despesa = msc.despesa_educacao(r.itens)
    receita = msc.receita_realizada(r.itens)
    fontes = msc.fontes_do_exercicio(despesa)
    fluxo = msc.fluxo_fonte_subfuncao(despesa) if fontes == "padronizada" else pd.DataFrame(columns=COLUNAS_FLUXO)
    natureza = msc.natureza_economica(despesa)
    fundeb = msc.fundeb(receita, *prefixos)
    if fundeb is None and prefixos[0]:
        avisos.append("MSC: nenhuma linha de receita com a natureza do FUNDEB")
    por_fonte = msc.receita_por_fonte(receita)
    resumo = msc.resumo_despesa(despesa)
    linha.update(
        status_msc="ok", fontes_msc=fontes, q_msc=consulta.id,
        msc_empenhada=resumo["empenhada"], msc_liquidada=resumo["liquidada"], msc_paga=resumo["paga"],
        fundeb_msc_fundo=fundeb.fundo if fundeb else None,
        fundeb_msc_complementacao=fundeb.complementacao if fundeb else None,
        fundeb_msc_total=round(fundeb.total, 2) if fundeb else None,
        fundeb_msc_por_fonte=json.dumps(fundeb.por_fonte) if fundeb and fundeb.por_fonte else None,
        fundeb_msc_prefixos=json.dumps({"fundo": prefixos[0], "complementacao": prefixos[1]}),
        # Receita do FNDE registrada pelo próprio município (fontes 550–553 e 569), para cruzar com a CGU.
        receita_fnde_msc=json.dumps({f: v for f, v in por_fonte.items() if f in {"550", "551", "552", "553", "569"}})
        if fontes == "padronizada" else None,
    )
    return linha, fluxo.assign(cod_ibge=ente.cod_ibge, ano=ano, q=consulta.id), \
        natureza.assign(cod_ibge=ente.cod_ibge, ano=ano, q=consulta.id), consulta, avisos


def _tarefa(cliente: ClienteSiconfi, ente: Ente, ano: int, prefixos: tuple[list[str], list[str]], hoje: date
            ) -> dict[str, Any]:
    """Tudo do SICONFI novo para um município-ano (roda em paralelo)."""
    saida: dict[str, Any] = {"consultas": [], "avisos": []}
    linhas, falhas, consultas = rreo_receita.coletar_ano(cliente, ente, ano)
    saida["receita"], saida["consultas"] = linhas, list(consultas)
    if falhas:
        saida["avisos"].append(f"RREO Anexo 01: falha de consulta nos bimestres {falhas}")

    linha_msc, fluxo, natureza, consulta, avisos = _msc_do_ente(cliente, ente, ano, prefixos)
    saida.update(msc=linha_msc, fluxo=fluxo, natureza=natureza)
    saida["avisos"] += avisos
    if consulta is not None:
        saida["consultas"].append(consulta)

    try:
        r, c = entregas.coletar(cliente, ente, ano)
        saida["entregas"] = [{**l, "q": c.id} for l in entregas.situacoes(r.itens, ente.cod_ibge, ano, hoje)]
        saida["consultas"].append(c)
    except NaoColetado:
        saida["entregas"] = []
    except ErroSiconfi as exc:
        saida["entregas"] = []
        saida["avisos"].append(f"extrato de entregas: {exc}")
    return saida


def executar(cliente: ClienteSiconfi, municipios: list[Ente], anos: list[int],
             prefixos: Mapping[int, tuple[list[str], list[str]]], *, trabalhadores: int = 4,
             hoje: date | None = None) -> ResultadoSiconfi:
    """Receita (A01), MSC e entregas de todos os municípios × exercícios."""
    hoje = hoje or date.today()
    registro = Registro()
    tarefas = [(e, a) for a in anos for e in municipios]
    with ThreadPoolExecutor(max_workers=trabalhadores) as pool:
        futuros = [pool.submit(_tarefa, cliente, e, a, prefixos.get(a, ([], [])), hoje) for e, a in tarefas]
        resultados = []
        for i, f in enumerate(futuros, 1):
            resultados.append(f.result())
            if i % 50 == 0 or i == len(futuros):
                log.info("SICONFI (receita, MSC, entregas): %d/%d", i, len(futuros))

    avisos: list[dict[str, Any]] = []
    for (e, a), r in zip(tarefas, resultados):
        registro.juntar(r["consultas"])
        avisos += [{"cod_ibge": e.cod_ibge, "ano": a, "aviso": m} for m in r["avisos"]]

    def _concat(chave: str, colunas: list[str]) -> pd.DataFrame:
        partes = [r[chave] for r in resultados if isinstance(r[chave], pd.DataFrame) and not r[chave].empty]
        return pd.concat(partes, ignore_index=True)[colunas] if partes else pd.DataFrame(columns=colunas)

    receita = pd.DataFrame([l for r in resultados for l in r["receita"]], columns=COLUNAS_RECEITA)
    tabela_msc = pd.DataFrame([r["msc"] for r in resultados]).reindex(columns=COLUNAS_MSC)
    entregas_df = pd.DataFrame([l for r in resultados for l in r["entregas"]])
    status = {
        "fonte": "SICONFI", "ok": True,
        "receita_a01": {"ente_anos_com_6_bimestres": int((receita.groupby(["cod_ibge", "ano"]).size() == 6).sum())},
        "msc": tabela_msc["status_msc"].value_counts().to_dict(),
        "msc_fontes": tabela_msc["fontes_msc"].value_counts().to_dict(),
        "entregas_linhas": len(entregas_df), "avisos": len(avisos),
    }
    return ResultadoSiconfi(receita, tabela_msc, _concat("fluxo", COLUNAS_FLUXO), _concat("natureza", COLUNAS_NATUREZA),
                            entregas_df, registro, avisos, status)


def main(argv: Iterable[str] | None = None) -> int:
    """Religa só o SICONFI (partes de auditoria), gravando em `dados/processado/fontes/siconfi/`."""
    from . import entes as mod_entes
    from . import parsing
    from .pipeline import parse_anos

    p = argparse.ArgumentParser(description="SICONFI: receita (Anexo 01), MSC e entregas dos municípios do ES.")
    p.add_argument("--anos", type=parse_anos, required=True)
    p.add_argument("--atualizar", choices=("nao", "vazios", "tudo", "offline"), default="nao")
    p.add_argument("--trabalhadores", type=int, default=4)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    cliente = ClienteSiconfi(atualizar=args.atualizar, intervalo_minimo=0.25)
    lista = mod_entes.listar_entes_es(cliente)
    municipios = [e for e in lista if e.esfera == "M"]
    contas: dict[int, list[dict[str, list[str]]]] = {}
    for a in args.anos:  # prefixos do FUNDEB: do DCA I-C (cache do financiamento geral)
        for e in municipios:
            try:
                itens = cliente.consultar("dca", an_exercicio=a, id_ente=e.cod_ibge, no_anexo="DCA-Anexo I-C").itens
            except ErroSiconfi:
                continue
            contas.setdefault(a, []).append(parsing.contas_fundeb_dca(itens))
    r = executar(cliente, municipios, args.anos, prefixos_fundeb(contas), trabalhadores=args.trabalhadores)
    destino = PROCESSADO / "fontes" / "siconfi"
    destino.mkdir(parents=True, exist_ok=True)
    for nome, df in (("receita_bimestral", r.receita_bimestral), ("msc", r.msc), ("fluxo_fonte_subfuncao", r.fluxo),
                     ("natureza_economica", r.natureza), ("entregas", r.entregas)):
        df.to_csv(destino / f"{nome}.csv", index=False, encoding="utf-8")
    pd.DataFrame(r.avisos, columns=["cod_ibge", "ano", "aviso"]).to_csv(destino / "avisos.csv", index=False, encoding="utf-8")
    pd.DataFrame(r.consultas.como_linhas()).to_csv(destino / "consultas.csv", index=False, encoding="utf-8")
    print(json.dumps(r.status, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
