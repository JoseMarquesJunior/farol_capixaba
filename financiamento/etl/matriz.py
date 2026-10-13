"""A matriz de evidências da fiscalização do CNCA: carrega e valida `config/matriz_cnca.yaml`.

O YAML é a fonte única do que cada achado da matriz de planejamento e cada
pergunta do questionário significam, de que indicador saem e com que ressalva
vão à tela. O ETL não decide nada disso: ele lê daqui.

A validação é estrita de propósito. Um achado que aponte para uma pergunta que
não existe, um indicador sem fórmula ou um limiar citado numa regra e ausente de
``parametros`` são erros de configuração que, calados, viram número errado no
papel de trabalho — e é mais barato falhar na carga.

Vocabulário (ver seção 5 do prompt da fiscalização):

* ``tipo_evidencia`` — o que o número É: medida direta, proxy, indício,
  documental, inferência, ou indisponível;
* ``status`` — o que o número DIZ sobre aquele município naquele achado:
  indício de risco, sem indício, inconclusivo ou sem dado público.

Nenhuma regra deste arquivo produz "achado": produz indício.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import yaml

from .config import PASTA

MATRIZ = PASTA / "config" / "matriz_cnca.yaml"

#: O que um número é. Ver o cabeçalho do YAML.
TIPOS_EVIDENCIA = ("direta", "proxy", "indicio", "documental", "inferencia", "indisponivel")

#: O que ele diz sobre o município. "achado" não está aqui, e não deve estar.
STATUS = ("indicio_risco", "sem_indicio", "inconclusivo", "sem_dado_publico")

ROTULO_STATUS = {
    "indicio_risco": "Indício de risco",
    "sem_indicio": "Sem indício",
    "inconclusivo": "Inconclusivo",
    "sem_dado_publico": "Sem dado público",
}

ROTULO_TIPO = {
    "direta": "Medida direta",
    "proxy": "Proxy",
    "indicio": "Indício (revisão humana)",
    "documental": "Documental",
    "inferencia": "Inferência (descritiva)",
    "indisponivel": "Sem dado público",
}

CONFIANCAS = ("alta", "media", "baixa")

EVIDENCIA_PERGUNTA = ("direta", "proxy", "parcial", "indisponivel")


class ErroMatriz(ValueError):
    """Configuração inválida em `config/matriz_cnca.yaml`."""


@dataclass(frozen=True, slots=True)
class Indicador:
    """Um número que o painel calcula, com a fórmula que o produz."""

    id: str
    rotulo: str
    formula: str
    fonte: str
    nivel: str          # municipio | municipio_ano | escola | estado
    unidade: str
    achado: str


@dataclass(frozen=True, slots=True)
class Achado:
    """Um possível achado da matriz de planejamento, e o que o dado diz dele."""

    id: str
    enunciado: str
    questao: str
    perguntas: tuple[str, ...]
    fase: int
    tipo_evidencia: str
    confianca: str
    indicadores: tuple[Indicador, ...]
    regra: dict[str, str]
    ressalvas: tuple[str, ...]
    caminho_alternativo: str | None
    #: Id da constatação que cobre este achado no universo. Quando existe, o achado
    #: NÃO produz indício individual — a afirmação é feita uma vez, para os 78.
    constatacao: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def automatizavel(self) -> bool:
        """Tem ao menos um indicador que o ETL calcula nesta versão."""
        return self.tipo_evidencia != "indisponivel" and bool(self.indicadores)


@dataclass(frozen=True, slots=True)
class Pergunta:
    """Uma pergunta do questionário e o que o dado público responde dela."""

    id: str
    bloco: int
    enunciado: str
    tipo: str
    opcoes: tuple[str, ...]
    achados: tuple[str, ...]
    evidencia: str
    responde_com: str
    dados_pessoais: bool


@dataclass(frozen=True, slots=True)
class Constatacao:
    """O que vale para o universo inteiro, e por isso é dito uma vez só.

    Quando uma característica atinge os 78 municípios por igual, apontá-la 78 vezes
    transforma um fato sobre a classificação orçamentária num mapa de calor cheio de
    indícios individuais — e o município que aparece nele não fez nada diferente dos
    outros. A constatação sai do mapa e vai para o texto, com a medida que a sustenta.
    """

    id: str
    questao: str
    achados: tuple[str, ...]
    enunciado: str
    medida: str
    fonte: str
    abrangencia: str
    consequencia: str


@dataclass(frozen=True, slots=True)
class Questao:
    id: str
    enunciado: str
    nota: str | None
    achados: tuple[Achado, ...]


@dataclass(frozen=True, slots=True)
class Matriz:
    """A matriz inteira, validada."""

    fiscalizacao: dict[str, Any]
    parametros: dict[str, dict[str, Any]]
    limitacoes: dict[str, str]
    questoes: tuple[Questao, ...]
    perguntas: tuple[Pergunta, ...]
    constatacoes: tuple[Constatacao, ...] = ()

    # ------------------------------------------------------------- acesso
    @property
    def achados(self) -> tuple[Achado, ...]:
        return tuple(a for q in self.questoes for a in q.achados)

    def achado(self, id_: str) -> Achado:
        for a in self.achados:
            if a.id == id_:
                return a
        raise KeyError(id_)

    def pergunta(self, id_: str) -> Pergunta:
        for p in self.perguntas:
            if p.id == id_:
                return p
        raise KeyError(id_)

    def indicadores(self) -> Iterator[Indicador]:
        for a in self.achados:
            yield from a.indicadores

    def param(self, nome: str) -> Any:
        """Valor de um limiar. Falha alto se não existir — limiar mudo é pior que erro."""
        try:
            return self.parametros[nome]["valor"]
        except KeyError as e:
            raise ErroMatriz(f"parâmetro inexistente: {nome!r}") from e

    def achados_da_fase(self, fase: int) -> tuple[Achado, ...]:
        return tuple(a for a in self.achados if a.fase == fase)

    def cobertura(self) -> dict[str, Any]:
        """Quanto da matriz o dado público alcança — a base da visão 5 do painel."""
        por_tipo: dict[str, int] = {}
        for a in self.achados:
            por_tipo[a.tipo_evidencia] = por_tipo.get(a.tipo_evidencia, 0) + 1
        por_evidencia: dict[str, int] = {}
        for p in self.perguntas:
            por_evidencia[p.evidencia] = por_evidencia.get(p.evidencia, 0) + 1
        return {
            "achados": len(self.achados),
            "achados_por_tipo": por_tipo,
            "achados_automatizaveis": sum(1 for a in self.achados if a.automatizavel),
            "perguntas": len(self.perguntas),
            "perguntas_por_evidencia": por_evidencia,
            "perguntas_com_dados_pessoais": sum(1 for p in self.perguntas if p.dados_pessoais),
            "questoes": len(self.questoes),
            "constatacoes": len(self.constatacoes),
            "achados_cobertos_por_constatacao": sum(1 for a in self.achados if a.constatacao),
        }


# --------------------------------------------------------------------- carga

_RX_ACHADO = re.compile(r"^A\d+\.\d+$")
_RX_PERGUNTA = re.compile(r"^P\d+$")
_RX_PARAM = re.compile(r"parametros\.([a-z0-9_]+)")


def _texto(d: dict[str, Any], chave: str, onde: str, *, obrigatorio: bool = True) -> str:
    v = d.get(chave)
    if v is None or (isinstance(v, str) and not v.strip()):
        if obrigatorio:
            raise ErroMatriz(f"{onde}: falta {chave!r}")
        return ""
    if not isinstance(v, str):
        raise ErroMatriz(f"{onde}: {chave!r} deve ser texto, recebi {type(v).__name__}")
    return " ".join(v.split())


def _indicador(d: dict[str, Any], achado: str) -> Indicador:
    onde = f"achado {achado}, indicador {d.get('id')!r}"
    if not isinstance(d, dict):
        raise ErroMatriz(f"achado {achado}: indicador deve ser um mapa")
    nivel = _texto(d, "nivel", onde)
    if nivel not in ("municipio", "municipio_ano", "escola", "estado"):
        raise ErroMatriz(f"{onde}: nivel inválido: {nivel!r}")
    return Indicador(id=_texto(d, "id", onde), rotulo=_texto(d, "rotulo", onde),
                     formula=_texto(d, "formula", onde), fonte=_texto(d, "fonte", onde),
                     nivel=nivel, unidade=_texto(d, "unidade", onde), achado=achado)


def _achado(d: dict[str, Any], questao: str, parametros: dict[str, Any]) -> Achado:
    id_ = _texto(d, "id", f"questão {questao}")
    onde = f"achado {id_}"
    if not _RX_ACHADO.match(id_):
        raise ErroMatriz(f"{onde}: id fora do padrão A<n>.<n>")
    if d.get("questao_matriz") != questao:
        raise ErroMatriz(f"{onde}: questao_matriz {d.get('questao_matriz')!r} não bate com a questão {questao}")
    tipo = _texto(d, "tipo_evidencia", onde)
    if tipo not in TIPOS_EVIDENCIA:
        raise ErroMatriz(f"{onde}: tipo_evidencia inválido: {tipo!r} (use um de {TIPOS_EVIDENCIA})")
    confianca = _texto(d, "confianca", onde)
    if confianca not in CONFIANCAS:
        raise ErroMatriz(f"{onde}: confianca inválida: {confianca!r}")
    fase = d.get("fase")
    if fase not in (1, 2, 3):
        raise ErroMatriz(f"{onde}: fase deve ser 1, 2 ou 3, recebi {fase!r}")

    regra = d.get("regra_classificacao") or {}
    if not isinstance(regra, dict) or not regra:
        raise ErroMatriz(f"{onde}: regra_classificacao vazia")
    for st in regra:
        if st not in STATUS:
            raise ErroMatriz(f"{onde}: status inválido em regra_classificacao: {st!r}")
    # Um limiar citado numa regra e ausente de `parametros` vira classificação silenciosamente
    # errada. Melhor falhar aqui.
    for texto in regra.values():
        for nome in _RX_PARAM.findall(str(texto)):
            if nome not in parametros:
                raise ErroMatriz(f"{onde}: regra cita parametros.{nome}, que não existe")

    indicadores = tuple(_indicador(i, id_) for i in (d.get("indicadores") or []))
    if tipo != "indisponivel" and not indicadores:
        raise ErroMatriz(f"{onde}: tipo {tipo!r} exige ao menos um indicador (use 'indisponivel' se não houver)")

    ressalvas = tuple(" ".join(str(r).split()) for r in (d.get("ressalvas") or []))
    if tipo in ("proxy", "indicio", "inferencia") and not ressalvas:
        raise ErroMatriz(f"{onde}: tipo {tipo!r} exige ressalva — proxy sem ressalva vira achado na leitura")

    conhecidos = {"id", "enunciado", "questao_matriz", "perguntas_questionario", "fase", "tipo_evidencia",
                  "confianca", "indicadores", "regra_classificacao", "ressalvas", "caminho_alternativo",
                  "constatacao"}
    return Achado(
        id=id_, enunciado=_texto(d, "enunciado", onde), questao=questao,
        perguntas=tuple(d.get("perguntas_questionario") or []), fase=int(fase),
        tipo_evidencia=tipo, confianca=confianca, indicadores=indicadores, regra=dict(regra),
        ressalvas=ressalvas, caminho_alternativo=_texto(d, "caminho_alternativo", onde, obrigatorio=False) or None,
        constatacao=_texto(d, "constatacao", onde, obrigatorio=False) or None,
        extras={k: v for k, v in d.items() if k not in conhecidos},
    )


def _pergunta(d: dict[str, Any]) -> Pergunta:
    id_ = _texto(d, "id", "pergunta")
    onde = f"pergunta {id_}"
    if not _RX_PERGUNTA.match(id_):
        raise ErroMatriz(f"{onde}: id fora do padrão P<n>")
    ev = _texto(d, "evidencia", onde)
    if ev not in EVIDENCIA_PERGUNTA:
        raise ErroMatriz(f"{onde}: evidencia inválida: {ev!r}")
    bloco = d.get("bloco")
    if bloco not in (1, 2, 3, 4, 5):
        raise ErroMatriz(f"{onde}: bloco deve ser de 1 a 5, recebi {bloco!r}")
    return Pergunta(id=id_, bloco=int(bloco), enunciado=_texto(d, "enunciado", onde),
                    tipo=_texto(d, "tipo", onde), opcoes=tuple(d.get("opcoes") or []),
                    achados=tuple(d.get("achados") or []), evidencia=ev,
                    responde_com=_texto(d, "responde_com", onde),
                    dados_pessoais=bool(d.get("dados_pessoais", False)))


def _constatacao(d: dict[str, Any]) -> Constatacao:
    id_ = _texto(d, "id", "constatação")
    onde = f"constatação {id_}"
    return Constatacao(id=id_, questao=_texto(d, "questao_matriz", onde),
                       achados=tuple(d.get("achados") or []), enunciado=_texto(d, "enunciado", onde),
                       medida=_texto(d, "medida", onde), fonte=_texto(d, "fonte", onde),
                       abrangencia=_texto(d, "abrangencia", onde),
                       consequencia=_texto(d, "consequencia", onde))


def carregar(caminho: Path | None = None) -> Matriz:
    """Lê o YAML, valida e devolve a matriz. Falha alto em qualquer inconsistência."""
    caminho = caminho or MATRIZ
    if not caminho.exists():
        raise ErroMatriz(f"matriz não encontrada: {caminho}")
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        raise ErroMatriz(f"{caminho}: o YAML deve ser um mapa")
    if dados.get("esquema") != 1:
        raise ErroMatriz(f"{caminho}: esquema {dados.get('esquema')!r} desconhecido (esperado 1)")

    parametros = dados.get("parametros") or {}
    for nome, p in parametros.items():
        if not isinstance(p, dict) or "valor" not in p:
            raise ErroMatriz(f"parâmetro {nome!r}: falta 'valor'")
        if not p.get("descricao"):
            raise ErroMatriz(f"parâmetro {nome!r}: falta 'descricao' — limiar sem explicação não é calibrável")

    questoes = []
    for q in dados.get("questoes") or []:
        qid = _texto(q, "id", "questão")
        questoes.append(Questao(id=qid, enunciado=_texto(q, "enunciado", f"questão {qid}"),
                                nota=_texto(q, "nota", f"questão {qid}", obrigatorio=False) or None,
                                achados=tuple(_achado(a, qid, parametros) for a in (q.get("achados") or []))))
    perguntas = tuple(_pergunta(p) for p in (dados.get("perguntas") or []))
    constatacoes = tuple(_constatacao(c) for c in (dados.get("constatacoes") or []))

    m = Matriz(fiscalizacao=dados.get("fiscalizacao") or {}, parametros=parametros,
               limitacoes={k: " ".join(str(v).split()) for k, v in (dados.get("limitacoes_estruturais") or {}).items()},
               questoes=tuple(questoes), perguntas=perguntas, constatacoes=constatacoes)
    _conferir_referencias(m)
    return m


def _conferir_referencias(m: Matriz) -> None:
    """Achado ↔ pergunta têm de casar nos dois sentidos, e os ids têm de ser únicos."""
    ids_achado = [a.id for a in m.achados]
    if len(set(ids_achado)) != len(ids_achado):
        repetidos = sorted({i for i in ids_achado if ids_achado.count(i) > 1})
        raise ErroMatriz(f"achados repetidos: {repetidos}")
    ids_pergunta = [p.id for p in m.perguntas]
    if len(set(ids_pergunta)) != len(ids_pergunta):
        repetidos = sorted({i for i in ids_pergunta if ids_pergunta.count(i) > 1})
        raise ErroMatriz(f"perguntas repetidas: {repetidos}")

    conhecidas, conhecidos = set(ids_pergunta), set(ids_achado)
    for a in m.achados:
        if faltam := set(a.perguntas) - conhecidas:
            raise ErroMatriz(f"achado {a.id} aponta para pergunta inexistente: {sorted(faltam)}")
    for p in m.perguntas:
        if faltam := set(p.achados) - conhecidos:
            raise ErroMatriz(f"pergunta {p.id} aponta para achado inexistente: {sorted(faltam)}")

    ids_const = {c.id for c in m.constatacoes}
    for c in m.constatacoes:
        if faltam := set(c.achados) - conhecidos:
            raise ErroMatriz(f"constatação {c.id} aponta para achado inexistente: {sorted(faltam)}")
    for a in m.achados:
        if a.constatacao and a.constatacao not in ids_const:
            raise ErroMatriz(f"achado {a.id} aponta para constatação inexistente: {a.constatacao!r}")
        # Um achado coberto por constatação não pode, ao mesmo tempo, marcar município
        # a município: seria dizer a mesma coisa duas vezes, uma delas injustamente.
        if a.constatacao and "indicio_risco" in a.regra:
            raise ErroMatriz(f"achado {a.id} é coberto pela constatação {a.constatacao} e não pode "
                             f"gerar indício individual — remova 'indicio_risco' da regra")

    ids_ind = [i.id for i in m.indicadores()]
    if len(set(ids_ind)) != len(ids_ind):
        # Um indicador pode ser reaproveitado entre achados, mas então tem de ter id próprio:
        # dois indicadores com o mesmo id e fórmulas diferentes produziriam evidência ambígua.
        porid: dict[str, set[str]] = {}
        for i in m.indicadores():
            porid.setdefault(i.id, set()).add(i.formula)
        ambiguos = sorted(k for k, v in porid.items() if len(v) > 1)
        if ambiguos:
            raise ErroMatriz(f"indicadores com mesmo id e fórmulas diferentes: {ambiguos}")
