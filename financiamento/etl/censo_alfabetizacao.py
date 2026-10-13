"""Censo Escolar no recorte da alfabetização: 1º e 2º ano, salas e sala de leitura.

O painel geral já traz o cadastro de escolas (`etl/escolas.py`). A matriz do CNCA
precisa de um corte que ele não faz — **a etapa** —, porque o programa é sobre o
1º e o 2º ano do ensino fundamental, e não sobre a rede inteira:

============================  =========================================================
O que                         De onde
============================  =========================================================
Matrículas de 1º e 2º ano     ``stg.matricula.qt_mat_fund_ai_1`` e ``_ai_2``
Turmas de 1º e 2º ano         ``stg.turma.qt_tur_fund_ai_1`` e ``_ai_2``
Salas de aula utilizadas      ``stg.escola.qt_salas_utilizadas``
Biblioteca ou sala de leitura ``stg.escola.in_biblioteca``, ``in_sala_leitura``,
                              ``in_biblioteca_sala_leitura``, ``qt_salas_leitura``
============================  =========================================================

**As colunas por ano escolar aparecem em exercícios diferentes** (medido no banco do
NEDUC em 23/09/2026, e não presumido do leiaute):

* **matrícula** de 1º e 2º ano: de **2023** em diante;
* **turma** de 1º e 2º ano: **só em 2025** — em 2021-2024 o Censo traz apenas o total
  dos anos iniciais (`qt_tur_fund_ai`), sem desdobrar o ano escolar.

Nos exercícios sem a coluna o módulo devolve **NA, nunca zero**, e quem consome tem
de dizer que o indicador não existe ali. Somar zeros produziria "nenhuma turma de
alfabetização em 2024", que é falso.

O retrato fica em ``dados/bruto/censo/`` ao lado do do painel geral, com o SQL e o
instante da extração no ``.json``, para a execução ser reproduzível sem o banco.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd

from .config import BRUTO, PROCESSADO
from .escolas import PASTA_CACHE, URL_BANCO
from .proveniencia import Consulta, Registro, caminho_relativo

log = logging.getLogger(__name__)

#: Valor por sala de aula do Cantinho da Leitura, Resolução CD/FNDE nº 22/2023.
VALOR_CANTINHO_POR_SALA = 1235.00

#: Primeiro exercício em que cada corte por ANO ESCOLAR existe no Censo. Medido no
#: banco, não lido do leiaute: matrícula desdobra 1º/2º ano desde 2023; turma, só em 2025.
PRIMEIRO_ANO = {"matriculas": 2023, "turmas": 2025}

REDE = {2: "estadual", 3: "municipal"}

SQL = {
    "alfabetizacao": """
        select e.nu_ano_censo as ano, e.co_entidade, e.co_municipio, e.tp_dependencia,
               e.tp_situacao_funcionamento,
               e.qt_salas_utilizadas, e.qt_salas_leitura,
               e.in_biblioteca, e.in_sala_leitura, e.in_biblioteca_sala_leitura,
               m.qt_mat_fund_ai, m.qt_mat_fund_ai_1, m.qt_mat_fund_ai_2,
               t.qt_tur_fund_ai, t.qt_tur_fund_ai_1, t.qt_tur_fund_ai_2
        from stg.escola e
        left join stg.matricula m
               on m.co_entidade = e.co_entidade and m.nu_ano_censo = e.nu_ano_censo
        left join stg.turma t
               on t.co_entidade = e.co_entidade and t.nu_ano_censo = e.nu_ano_censo
        where e.nu_ano_censo >= 2021 and e.tp_dependencia in (2, 3)""",
}

COLUNAS_ESCOLA = ["ano", "co_entidade", "cod_ibge", "rede", "em_atividade", "salas_utilizadas",
                  "salas_leitura", "tem_biblioteca", "tem_sala_leitura", "mat_anos_iniciais",
                  "mat_1_ano", "mat_2_ano", "turmas_anos_iniciais", "turmas_1_ano", "turmas_2_ano"]


class ErroCenso(RuntimeError):
    """O retrato do Censo não está disponível nem no banco nem no cache."""


@dataclass
class ResultadoCenso:
    escolas: pd.DataFrame = field(default_factory=pd.DataFrame)
    municipio: pd.DataFrame = field(default_factory=pd.DataFrame)
    consulta: Consulta | None = None
    avisos: list[dict[str, Any]] = field(default_factory=list)

    @property
    def tabelas(self) -> dict[str, pd.DataFrame]:
        return {"cnca_censo_escolas": self.escolas, "cnca_censo_municipio": self.municipio}


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ extração

def extrair(*, atualizar: str = "nao") -> tuple[pd.DataFrame, Consulta | None, str | None]:
    """Retrato do Censo por escola — do banco, ou do cache quando ele não responde.

    A conexão vem de `educacao/.env`, que não é versionado. Sem banco e sem cache, o
    módulo devolve tabela vazia e um aviso: o painel diz "sem dado" nesses indicadores
    em vez de exibir zero.
    """
    arquivo = PASTA_CACHE / "alfabetizacao.csv.gz"
    meta = PASTA_CACHE / "alfabetizacao.json"
    usar_cache = atualizar in {"nao", "offline", "vazios"} and arquivo.exists() and meta.exists()
    aviso = None

    if not usar_cache:
        if atualizar == "offline":
            return pd.DataFrame(), None, "Censo (alfabetização) não coletado: modo offline, sem retrato em cache"
        try:
            from dotenv import load_dotenv
            load_dotenv(BRUTO.parent.parent.parent / "educacao" / ".env")
            from educacao.config.database import get_connection
            with get_connection() as conn:
                bruto = pd.read_sql_query(SQL["alfabetizacao"], conn)
        except Exception as exc:                    # noqa: BLE001 — banco fora não derruba o painel
            if arquivo.exists() and meta.exists():
                aviso = f"banco do Censo indisponível ({type(exc).__name__}); usado o retrato em cache"
                usar_cache = True
            else:
                return pd.DataFrame(), None, f"Censo (alfabetização) indisponível: {type(exc).__name__}: {exc}"
        else:
            PASTA_CACHE.mkdir(parents=True, exist_ok=True)
            with gzip.open(arquivo, "wt", encoding="utf-8", newline="") as f:
                bruto.to_csv(f, index=False)
            meta.write_text(json.dumps({"obtido_em": _agora(), "banco": URL_BANCO,
                                        "consulta": " ".join(SQL["alfabetizacao"].split()),
                                        "linhas": len(bruto)}, ensure_ascii=False, indent=1), encoding="utf-8")

    if usar_cache:
        bruto = pd.read_csv(arquivo)
    d = json.loads(meta.read_text(encoding="utf-8"))
    # O fragmento no fim da URL identifica ESTA consulta: o id de uma `Consulta` é o
    # hash de fonte+método+url, e sem ele esta extração colidiria com a do painel geral,
    # que consulta o mesmo banco com outro SQL.
    consulta = Consulta(fonte="Censo", recurso="censo_alfabetizacao",
                        descricao="Censo Escolar (NEDUC): matrículas e turmas de 1º e 2º ano, salas e sala de leitura",
                        url=f"{URL_BANCO}#alfabetizacao", obtido_em=d["obtido_em"],
                        arquivo=caminho_relativo(arquivo), metodo="SQL")
    return bruto, consulta, aviso


# ------------------------------------------------------------------ preparo

def preparar(bruto: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por escola × ano, com nomes internos e o que falta como NA."""
    if bruto.empty:
        return pd.DataFrame(columns=COLUNAS_ESCOLA)
    d = pd.DataFrame({
        "ano": pd.to_numeric(bruto["ano"], errors="coerce").astype("Int64"),
        "co_entidade": pd.to_numeric(bruto["co_entidade"], errors="coerce").astype("Int64"),
        "cod_ibge": pd.to_numeric(bruto["co_municipio"], errors="coerce").astype("Int64"),
        "rede": pd.to_numeric(bruto["tp_dependencia"], errors="coerce").map(REDE),
        # 1 = em atividade, na codificação do Censo.
        "em_atividade": pd.to_numeric(bruto["tp_situacao_funcionamento"], errors="coerce") == 1,
        "salas_utilizadas": pd.to_numeric(bruto["qt_salas_utilizadas"], errors="coerce"),
        "salas_leitura": pd.to_numeric(bruto["qt_salas_leitura"], errors="coerce"),
        "mat_anos_iniciais": pd.to_numeric(bruto["qt_mat_fund_ai"], errors="coerce"),
        "mat_1_ano": pd.to_numeric(bruto["qt_mat_fund_ai_1"], errors="coerce"),
        "mat_2_ano": pd.to_numeric(bruto["qt_mat_fund_ai_2"], errors="coerce"),
        "turmas_anos_iniciais": pd.to_numeric(bruto["qt_tur_fund_ai"], errors="coerce"),
        "turmas_1_ano": pd.to_numeric(bruto["qt_tur_fund_ai_1"], errors="coerce"),
        "turmas_2_ano": pd.to_numeric(bruto["qt_tur_fund_ai_2"], errors="coerce"),
    })
    # "Tem espaço de leitura" reúne os três marcadores do Censo: biblioteca, sala de
    # leitura, e a biblioteca que também é sala de leitura. Exigir só `in_biblioteca`
    # deixaria de fora a escola pequena que tem sala de leitura e não tem biblioteca.
    marcas = [pd.to_numeric(bruto[c], errors="coerce").fillna(0) == 1
              for c in ("in_biblioteca", "in_sala_leitura", "in_biblioteca_sala_leitura")]
    d["tem_biblioteca"] = marcas[0]
    d["tem_sala_leitura"] = marcas[0] | marcas[1] | marcas[2]
    return d.reindex(columns=COLUNAS_ESCOLA)


def por_municipio(escolas: pd.DataFrame, *, rede: str = "municipal") -> pd.DataFrame:
    """Agrega a rede de cada município: matrículas, turmas, salas e espaço de leitura.

    `mat_1_2_ano` e `turmas_1_2_ano` saem **NA** nos exercícios anteriores a 2023, em
    que o Censo não desdobrava o ano escolar — e é isso que o indicador tem de dizer,
    em vez de somar zeros.
    """
    if escolas.empty:
        return pd.DataFrame()
    d = escolas[(escolas["rede"] == rede) & escolas["em_atividade"]].copy()
    if d.empty:
        return pd.DataFrame()
    # Uma escola sem anos iniciais não entra no denominador do espaço de leitura: a
    # pergunta é sobre a rede que alfabetiza, não sobre a rede inteira.
    com_ai = d["mat_anos_iniciais"].fillna(0) > 0
    g = d.groupby(["cod_ibge", "ano"], as_index=False)
    saida = g.agg(
        escolas=("co_entidade", "nunique"),
        mat_anos_iniciais=("mat_anos_iniciais", "sum"),
        salas_utilizadas=("salas_utilizadas", "sum"),
        salas_leitura=("salas_leitura", "sum"),
    )
    # `sum(min_count=1)` preserva o NA: soma de tudo-NA continua NA, e não vira zero.
    por_ano = d.groupby(["cod_ibge", "ano"])[["mat_1_ano", "mat_2_ano", "turmas_1_ano",
                                              "turmas_2_ano", "turmas_anos_iniciais"]].sum(min_count=1).reset_index()
    saida = saida.merge(por_ano, on=["cod_ibge", "ano"], how="left")
    ai = d[com_ai].groupby(["cod_ibge", "ano"], as_index=False).agg(
        escolas_anos_iniciais=("co_entidade", "nunique"),
        escolas_com_leitura=("tem_sala_leitura", "sum"),
        salas_anos_iniciais=("salas_utilizadas", "sum"))
    saida = saida.merge(ai, on=["cod_ibge", "ano"], how="left")

    saida["mat_1_2_ano"] = saida[["mat_1_ano", "mat_2_ano"]].sum(axis=1, min_count=1)
    saida["turmas_1_2_ano"] = saida[["turmas_1_ano", "turmas_2_ano"]].sum(axis=1, min_count=1)
    saida["pct_escolas_com_leitura"] = (saida["escolas_com_leitura"] / saida["escolas_anos_iniciais"] * 100).round(2)
    # Valor de referência do Cantinho da Leitura: ESTIMATIVA de ordem de grandeza para
    # UMA das ações do CNCA, não a necessidade total do município.
    saida["valor_referencia_cantinho"] = (saida["salas_anos_iniciais"] * VALOR_CANTINHO_POR_SALA).round(2)
    return saida.sort_values(["cod_ibge", "ano"]).reset_index(drop=True)


# --------------------------------------------------------------- execução

def executar(*, atualizar: str = "nao", registro: Registro | None = None) -> ResultadoCenso:
    bruto, consulta, aviso = extrair(atualizar=atualizar)
    res = ResultadoCenso(consulta=consulta)
    if aviso:
        res.avisos.append({"fonte": "Censo", "aviso": aviso})
    if bruto.empty:
        return res
    if registro is not None and consulta is not None:
        registro.adicionar(consulta)
    res.escolas = preparar(bruto)
    res.municipio = por_municipio(res.escolas)
    if not res.municipio.empty and consulta is not None:
        res.municipio["q"] = consulta.id
        res.escolas["q"] = consulta.id
    anos = sorted(int(a) for a in res.municipio["ano"].dropna().unique())
    for corte, primeiro in PRIMEIRO_ANO.items():
        faltam = [a for a in anos if a < primeiro]
        if faltam:
            res.avisos.append({"fonte": "Censo", "aviso":
                               f"{corte} de 1º e 2º ano não existem no leiaute do Censo em {faltam}: "
                               f"o indicador sai como 'sem dado' nesses exercícios, nunca como zero"})
    return res


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Censo no recorte da alfabetização (1º e 2º ano, salas, leitura).")
    p.add_argument("--atualizar", default="nao", choices=["nao", "vazios", "tudo", "offline"])
    args = p.parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    res = executar(atualizar=args.atualizar)
    PROCESSADO.mkdir(parents=True, exist_ok=True)
    for nome, df in res.tabelas.items():
        df.to_csv(PROCESSADO / f"{nome}.csv", index=False, encoding="utf-8")
        print(f"{nome}: {len(df):,} linhas")
    if res.consulta is not None:
        from .evidencias import gravar_consultas
        gravar_consultas([res.consulta])
    for a in res.avisos:
        print(f"  aviso: {a['aviso']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
