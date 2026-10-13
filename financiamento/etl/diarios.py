"""Diários oficiais: atos de designação e política municipal de alfabetização (Q1, A2.3, A5.3).

Os achados de governança do CNCA só existem em **ato publicado** — portaria que
designa o coordenador, lei ou decreto da Política Municipal de Alfabetização,
ato que institui o comitê. Não há base estruturada disso: há diário oficial.

E aqui a cobertura é o limite, não a técnica. Medido em 23/09/2026:

* **Querido Diário** tem API aberta e boa, mas coletou diário de **3 dos 78**
  municípios do ES — Vitória (desde 2025-01-13), Serra (2022-10-03) e Vila Velha
  (2022-07-19). Outros 7 têm URL de publicação cadastrada e nenhuma edição
  coletada. São 3,8% do universo;
* **DOM-ES/AMUNES** (`ioes.dio.es.gov.br`) publica o diário dos demais municípios,
  mas a busca por palavra é montada no cliente e não há endpoint de busca textual
  exposto. O que existe é o **índice de edições** (`ultimas_edicoes.json`), que
  este módulo coleta: dele sai a lista reproduzível de edições a varrer.

Por isso o módulo faz três coisas e não finge fazer uma quarta:

1. busca no Querido Diário os termos da matriz, nos 3 municípios cobertos;
2. coleta o índice de edições do DOM-ES, para a varredura ser planejável;
3. **gera a lista de buscas** para execução manual assistida nos 75 municípios
   restantes — que é o que o prompt da fiscalização prevê quando o scraping é inviável.

A ausência de resultado NUNCA é evidência de ausência de ato, e cada linha
produzida aqui carrega essa frase.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd
import requests

from .config import BRUTO, PROCESSADO
from .proveniencia import Consulta, Registro, caminho_relativo

log = logging.getLogger(__name__)

PASTA_CACHE = BRUTO / "diarios"
#: O Querido Diário responde nos dois endereços, e eles não são igualmente confiáveis:
#: em 23/09/2026 o proxy `queridodiario.ok.org.br/api` devolvia 503 em `/cities` e 200
#: em `/gazettes`, enquanto o host direto respondia os dois. O módulo tenta em ordem.
BASES_QD = ("https://queridodiario.ok.org.br/api", "https://api.queridodiario.org.br")
API_QD = BASES_QD[0]
DOM_ES = "https://ioes.dio.es.gov.br"
DOM_ES_EDICOES = f"{DOM_ES}/apifront/portal/edicoes/ultimas_edicoes.json"
DOM_ES_BUSCA = f"{DOM_ES}/buscanova"
UA = {"User-Agent": "neduc-financiamento/1.0 (auditoria TCE-ES)"}
PAUSA = 1.5      # segundos entre requisições — scraping gentil, como o prompt pede

#: Os termos de busca, por achado da matriz. São propositalmente amplos: servem de
#: TRIAGEM para leitura humana, nunca de contagem. Medido no Querido Diário nos 3
#: municípios cobertos: "articulador" devolve 866 edições, quase todas de outro assunto.
BUSCAS: dict[str, tuple[str, str]] = {
    "A1.1": ("coordenador do CNCA designado",
             '"Compromisso Nacional Criança Alfabetizada" OR CNCA OR (designa AND alfabetização)'),
    "A1.4": ("articulador municipal do CNCA",
             'articulador AND (alfabetização OR CNCA OR Renalfa)'),
    "A1.7": ("política ou plano municipal de alfabetização",
             '"Política Municipal de Alfabetização" OR (plano AND alfabetização)'),
    "A2.3": ("plano de ações do CNCA",
             '"plano de ações" AND (alfabetização OR CNCA)'),
    "A5.3": ("comitê ou fórum de alfabetização",
             '(comitê OR comissão) AND alfabetização'),
}

#: O que a API do Querido Diário recebe, por achado. Mais estreito que o rótulo acima:
#: a querystring dela não faz booleano complexo, então cada achado leva os termos que
#: valem a pena isolados, e o casamento fino fica na leitura.
TERMOS_QD: dict[str, tuple[str, ...]] = {
    "A1.1": ('"Compromisso Nacional Criança Alfabetizada"', "CNCA"),
    "A1.4": ("articulador",),
    "A1.7": ('"Política Municipal de Alfabetização"', "alfabetização"),
    "A2.3": ('"plano de ações"',),
    "A5.3": ("comitê de alfabetização",),
}

COLUNAS_OCORRENCIA = ["cod_ibge", "municipio", "achado_id", "termo", "data", "edicao",
                      "url", "excerto", "q"]
COLUNAS_COBERTURA = ["cod_ibge", "municipio", "fonte", "situacao", "desde", "edicoes_desde_2023"]


@dataclass
class ResultadoDiarios:
    cobertura: pd.DataFrame = field(default_factory=pd.DataFrame)
    ocorrencias: pd.DataFrame = field(default_factory=pd.DataFrame)
    buscas_manuais: pd.DataFrame = field(default_factory=pd.DataFrame)
    edicoes_dom: pd.DataFrame = field(default_factory=pd.DataFrame)
    consultas: list[Consulta] = field(default_factory=list)
    avisos: list[dict[str, Any]] = field(default_factory=list)

    @property
    def tabelas(self) -> dict[str, pd.DataFrame]:
        return {"cnca_diarios_cobertura": self.cobertura, "cnca_diarios_ocorrencias": self.ocorrencias,
                "cnca_diarios_buscas_manuais": self.buscas_manuais,
                "cnca_diarios_edicoes_dom": self.edicoes_dom}


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _guardar(nome: str, dados: Any) -> None:
    PASTA_CACHE.mkdir(parents=True, exist_ok=True)
    (PASTA_CACHE / nome).write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


def _ler(nome: str) -> Any | None:
    caminho = PASTA_CACHE / nome
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else None


def _get_qd(rota: str, params: dict[str, Any], *, timeout: float = 120,
            tentativas: int = 3) -> requests.Response:
    """GET no Querido Diário, alternando os dois endereços e com espera entre tentativas.

    O serviço devolve 503 de forma intermitente (visto em 23/09/2026: as mesmas rotas
    responderam 200 e, minutos depois, 503 nos dois endereços). Insistir com pausa é o
    bastante para a maioria dos casos; quando não é, quem chama recebe o erro e o
    indicador sai como "sem dado público" — nunca como "nenhum ato encontrado".
    """
    ultimo: Exception | None = None
    for tentativa in range(1, tentativas + 1):
        for base in BASES_QD:
            try:
                r = requests.get(f"{base}/{rota}", headers=UA, params=params, timeout=timeout)
                r.raise_for_status()
                return r
            except Exception as e:                  # noqa: BLE001 — só desiste no fim de tudo
                ultimo = e
                log.debug("querido diário %s em %s (tentativa %d): %s", rota, base, tentativa, e)
        if tentativa < tentativas:
            time.sleep(PAUSA * 4 * tentativa)
    raise RuntimeError(f"Querido Diário não respondeu em nenhum dos endereços "
                       f"após {tentativas} tentativas: {ultimo}")


# ------------------------------------------------------------ Querido Diário

def cobertura_querido_diario(nomes_ibge: dict[int, str], *, atualizar: str = "nao") -> tuple[pd.DataFrame, Consulta | None]:
    """Quais municípios do ES têm diário efetivamente coletado — e não só cadastrado.

    A distinção importa: `/cities` lista os 5.570 municípios do país porque é o
    cadastro do IBGE. Ter diário é ter `availability_date`.
    """
    cache = _ler("qd_cities.json") if atualizar in {"nao", "offline", "vazios"} else None
    if cache is None:
        if atualizar == "offline":
            return pd.DataFrame(columns=COLUNAS_COBERTURA), None
        cache = {"obtido_em": _agora(), "cities": [], "metodo": "cities"}
        try:
            cache["cities"] = _get_qd("cities", {"state_code": "ES"}).json().get("cities", [])
        except Exception as e:                      # noqa: BLE001
            # `/cities` sai do ar sozinho (503 intermitente) enquanto `/gazettes` responde.
            # Contar edições por município é teste MELHOR de cobertura do que o campo de
            # cadastro: `availability_date` é o que o projeto anotou, `total_gazettes` é o
            # que ele de fato tem. Custa 78 requisições espaçadas, e vale a pena.
            log.warning("/cities indisponível (%s); medindo cobertura por contagem de edições", e)
            cache["metodo"] = "gazettes"
            # Uma tentativa por município, e não três: aqui já estamos num laço de 78, e
            # insistir em cada um multiplicaria meia hora de espera quando o serviço está
            # fora. Município que falha sai como "não medido", que é o que ele é.
            for cod, nome in sorted(nomes_ibge.items()):
                try:
                    n = _get_qd("gazettes", {"territory_ids": str(cod), "published_since": "2023-01-01",
                                             "size": 1}, timeout=30, tentativas=1).json().get("total_gazettes", 0)
                except Exception:                   # noqa: BLE001 — um município que falha não derruba o resto
                    n = None
                cache["cities"].append({"territory_id": cod, "territory_name": nome,
                                        "state_code": "ES", "total_gazettes": n})
                time.sleep(PAUSA)
        _guardar("qd_cities.json", cache)

    metodo = cache.get("metodo", "cities")
    consulta = Consulta(fonte="Diário Oficial", recurso=f"querido_diario_{metodo}",
                        descricao=f"Querido Diário — cobertura dos municípios do ES (por {metodo})",
                        url=f"{API_QD}/{metodo}?state_code=ES", obtido_em=cache["obtido_em"],
                        arquivo=caminho_relativo(PASTA_CACHE / "qd_cities.json"))
    linhas = []
    por_id = {str(c.get("territory_id")): c for c in cache["cities"] if c.get("state_code") == "ES"}
    for cod, nome in sorted(nomes_ibge.items()):
        c = por_id.get(str(cod), {})
        n = c.get("total_gazettes")
        tem = bool(c.get("availability_date")) or bool(n)
        if n is None and "availability_date" not in c and metodo == "gazettes":
            situacao = "não medido"
        elif tem:
            situacao = "coletado"
        else:
            situacao = "cadastrado sem edições" if c.get("publication_urls") else "não coberto"
        linhas.append({"cod_ibge": cod, "municipio": nome, "fonte": "Querido Diário",
                       "situacao": situacao, "desde": c.get("availability_date") or None,
                       "edicoes_desde_2023": n})
    return pd.DataFrame(linhas).reindex(columns=COLUNAS_COBERTURA), consulta


def buscar(cod_ibge: int, municipio: str, achado: str, termo: str, *,
           desde: str = "2023-01-01", tamanho: int = 20) -> tuple[list[dict[str, Any]], str]:
    """Uma busca no Querido Diário, num município. Devolve (ocorrências, url da consulta)."""
    params = {"territory_ids": str(cod_ibge), "querystring": termo,
              "published_since": desde, "size": tamanho}
    r = _get_qd("gazettes", params)
    dados = r.json()
    saida = []
    for g in dados.get("gazettes", []):
        excertos = g.get("excerpts") or [""]
        saida.append({"cod_ibge": cod_ibge, "municipio": municipio, "achado_id": achado,
                      "termo": termo, "data": g.get("date"), "edicao": g.get("edition"),
                      "url": g.get("url"), "excerto": " ".join(str(excertos[0]).split())[:400]})
    return saida, r.url


# ------------------------------------------------------------------ DOM-ES

def edicoes_dom_es(*, atualizar: str = "nao") -> tuple[pd.DataFrame, Consulta | None]:
    """Índice de edições do DOM-ES/AMUNES — o que torna a varredura planejável.

    A busca por palavra do portal é montada no cliente e não tem endpoint exposto;
    o índice de edições tem, e é dele que sai a lista do que varrer.
    """
    cache = _ler("dom_es_edicoes.json") if atualizar in {"nao", "offline", "vazios"} else None
    if cache is None:
        if atualizar == "offline":
            return pd.DataFrame(), None
        r = requests.get(DOM_ES_EDICOES, headers=UA, params={"subtheme": "dom"}, timeout=120)
        r.raise_for_status()
        cache = {"obtido_em": _agora(), "itens": r.json().get("itens", [])}
        _guardar("dom_es_edicoes.json", cache)
    consulta = Consulta(fonte="Diário Oficial", recurso="dom_es_edicoes",
                        descricao="DOM-ES/AMUNES — índice de edições publicadas",
                        url=DOM_ES_EDICOES, obtido_em=cache["obtido_em"],
                        arquivo=caminho_relativo(PASTA_CACHE / "dom_es_edicoes.json"))
    itens = cache.get("itens", [])
    if not itens:
        return pd.DataFrame(), consulta
    d = pd.DataFrame(itens)
    d["data"] = pd.to_datetime(d.get("data"), errors="coerce", dayfirst=True)
    return d.sort_values("data", ascending=False).reset_index(drop=True), consulta


def lista_buscas_manuais(cobertura: pd.DataFrame) -> pd.DataFrame:
    """A lista de buscas a fazer à mão, para os municípios sem diário automatizável.

    É o caminho que o prompt da fiscalização prevê quando o scraping é inviável:
    em vez de deixar o achado em branco, entrega-se à equipe o que buscar, onde, e
    o que a busca significa.
    """
    sem = cobertura[cobertura["situacao"] != "coletado"]
    linhas = []
    for r in sem.itertuples(index=False):
        for achado, (rotulo, expressao) in BUSCAS.items():
            linhas.append({
                "cod_ibge": r.cod_ibge, "municipio": r.municipio, "achado_id": achado,
                "o_que_procurar": rotulo, "expressao": expressao,
                "onde": f"{DOM_ES_BUSCA} (DOM-ES/AMUNES), busca por palavra com filtro de data",
                "periodo": "2023-01-01 até hoje",
                "como_registrar": "ato encontrado → anexar ao papel de trabalho e marcar o achado como "
                                  "'sem indício'; nada encontrado → o achado CONTINUA 'sem dado público', "
                                  "porque ausência de resultado não é ausência de ato",
            })
    return pd.DataFrame(linhas)


# --------------------------------------------------------------- execução

def executar(nomes_ibge: dict[int, str], *, atualizar: str = "nao", desde: str = "2023-01-01",
             registro: Registro | None = None) -> ResultadoDiarios:
    res = ResultadoDiarios()
    try:
        res.cobertura, c = cobertura_querido_diario(nomes_ibge, atualizar=atualizar)
        if c is not None:
            res.consultas.append(c)
            if registro is not None:
                registro.adicionar(c)
    except Exception as e:                          # noqa: BLE001
        res.avisos.append({"fonte": "Querido Diário", "aviso": f"cobertura não obtida: {e}"})
        return res

    cobertos = res.cobertura[res.cobertura["situacao"] == "coletado"]
    ocorrencias = []
    for r in cobertos.itertuples(index=False):
        for achado, termos in TERMOS_QD.items():
            for termo in termos:
                try:
                    achadas, url = buscar(int(r.cod_ibge), r.municipio, achado, termo, desde=desde)
                except Exception as e:              # noqa: BLE001 — um termo que falha não derruba o resto
                    res.avisos.append({"fonte": "Querido Diário",
                                       "aviso": f"{r.municipio}/{achado}/{termo}: {e}"})
                    continue
                c = Consulta(fonte="Diário Oficial", recurso="querido_diario_gazettes",
                             descricao=f"Querido Diário — {r.municipio}, {achado}, termo {termo}",
                             url=url, obtido_em=_agora(),
                             arquivo=caminho_relativo(PASTA_CACHE / "qd_cities.json"))
                res.consultas.append(c)
                if registro is not None:
                    registro.adicionar(c)
                for o in achadas:
                    o["q"] = c.id
                ocorrencias += achadas
                time.sleep(PAUSA)
    res.ocorrencias = (pd.DataFrame(ocorrencias).reindex(columns=COLUNAS_OCORRENCIA)
                       if ocorrencias else pd.DataFrame(columns=COLUNAS_OCORRENCIA))

    try:
        res.edicoes_dom, c = edicoes_dom_es(atualizar=atualizar)
        if c is not None:
            res.consultas.append(c)
            if registro is not None:
                registro.adicionar(c)
    except Exception as e:                          # noqa: BLE001
        res.avisos.append({"fonte": "DOM-ES", "aviso": f"índice de edições não obtido: {e}"})

    res.buscas_manuais = lista_buscas_manuais(res.cobertura)
    contagem = res.cobertura["situacao"].value_counts().to_dict()
    n, nao_medido = contagem.get("coletado", 0), contagem.get("não medido", 0)
    if nao_medido:
        # Serviço fora não é cobertura zero. Dizer "0 de 78 têm diário" quando a medição
        # falhou seria transformar uma indisponibilidade em achado sobre os municípios.
        res.avisos.append({"fonte": "Querido Diário", "aviso":
                           f"cobertura NÃO MEDIDA em {nao_medido} de {len(res.cobertura)} municípios: a API "
                           f"não respondeu nesta execução. Isso não significa que eles não têm diário — "
                           f"significa que não se sabe. Rode de novo quando o serviço voltar."})
    res.avisos.append({"fonte": "Querido Diário", "aviso":
                       f"{n} de {len(res.cobertura)} municípios com diário coletado confirmado; "
                       f"{len(res.buscas_manuais)} buscas na lista manual (DOM-ES/AMUNES)"})
    return res


def main(argv: Iterable[str] | None = None) -> int:
    from .evidencias import gravar_consultas
    from .execucao import nomes_municipios

    p = argparse.ArgumentParser(description="Diários oficiais: atos do CNCA (Querido Diário e DOM-ES).")
    p.add_argument("--desde", default="2023-01-01")
    p.add_argument("--atualizar", default="nao", choices=["nao", "vazios", "tudo", "offline"])
    args = p.parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    res = executar(nomes_municipios(), atualizar=args.atualizar, desde=args.desde)
    PROCESSADO.mkdir(parents=True, exist_ok=True)
    for nome, df in res.tabelas.items():
        df.to_csv(PROCESSADO / f"{nome}.csv", index=False, encoding="utf-8")
        print(f"{nome}: {len(df):,} linhas")
    gravar_consultas(res.consultas)
    if not res.ocorrencias.empty:
        print("\nocorrências por achado (triagem, não contagem):")
        print(res.ocorrencias.groupby(["achado_id", "municipio"]).size().to_string())
    for a in res.avisos:
        print(f"  aviso: {a['aviso']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
