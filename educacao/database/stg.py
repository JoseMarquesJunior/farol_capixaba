"""Modelo da camada `stg`: os 19 anos falando o vocabulário de 2025.

Três coisas acontecem aqui:

* **decomposição** — de 2007 a 2024 o INEP publica um arquivo largo único, com
  escola, matrícula, docente, turma e gestor na mesma linha. A stg o reparte nas
  entidades que 2025 separou, usando o catálogo como mapa coluna -> entidade;
* **de-para** — variáveis renomeadas passam a viver sob um nome só, e as que
  deixaram de ser publicadas são reconstituídas (educacao/metadata/de_para.yml);
* **harmonização de tipo** — colunas cujo tipo muda entre anos convergem para
  um tipo único, com a conversão declarada no de-para.

Toda variável já coletada vira coluna, nula nos anos em que não existiu. Nada
é descartado: quem consulta a stg vê a série inteira, e o nulo diz "não
coletado naquele ano".

Sem particionamento: com o recorte do Espírito Santo são ~4 mil escolas por ano,
algo como 80 mil linhas em 19 anos. Particionar só acrescentaria complexidade.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from psycopg import sql

from ..config.database import get_connection
from ..config.logging import configure_logger
from ..metadata.canonico import ANO_REFERENCIA, carregar_catalogos
from ..metadata.de_para import DePara
from ..metadata.de_para import carregar as carregar_de_para

logger = configure_logger(__name__)

SCHEMA = "stg"

#: Chave natural de cada tabela da stg.
CHAVES = {
    "escola": ("nu_ano_censo", "co_entidade"),
    "matricula": ("nu_ano_censo", "co_entidade"),
    "docente": ("nu_ano_censo", "co_entidade"),
    "turma": ("nu_ano_censo", "co_entidade"),
    "gestor": ("nu_ano_censo", "co_entidade"),
    "curso_tecnico": (
        "nu_ano_censo",
        "co_entidade",
        "id_area_curso_profissional",
        "co_curso_educ_profissional",
    ),
}

_PREFIXO_TABELA = (
    ("QT_MAT", "matricula"),
    ("QT_DOC", "docente"),
    ("QT_TUR", "turma"),
    ("QT_GEST", "gestor"),
)

#: Colunas de chave. Existem em todas as seis tabelas de 2025 e no arquivo
#: largo, então não podem ser atribuídas a uma tabela só: são replicadas em
#: cada tabela da stg.
CHAVES_GLOBAIS = {chave.upper() for chaves in CHAVES.values() for chave in chaves}


@dataclass(slots=True)
class ColunaStg:
    nome: str
    tabela: str
    tipo: str
    descricao: str | None
    #: ano -> expressão SQL que a alimenta a partir de raw; ausente = nula
    origens: dict[int, str] = field(default_factory=dict)


def _tabela_de(nome: str, tabela_2025: dict[str, str], de_para: DePara) -> str:
    canonico = de_para.canonizar(nome)
    if canonico in tabela_2025:
        return tabela_2025[canonico]
    if nome in de_para.derivadas:
        return de_para.derivadas[nome].tabela
    for prefixo, tabela in _PREFIXO_TABELA:
        if nome.startswith(prefixo):
            return tabela
    return "escola"


def montar() -> tuple[dict[str, list[ColunaStg]], dict[int, dict[str, str]]]:
    """Devolve (colunas por tabela da stg, mapa ano -> {tabela stg: tabela raw})."""

    de_para = carregar_de_para()
    catalogos = carregar_catalogos()

    tabela_2025: dict[str, str] = {}
    for tabela in catalogos[ANO_REFERENCIA]["tabelas"]:
        for variavel in tabela["variaveis"]:
            if variavel["nome"] not in CHAVES_GLOBAIS:
                tabela_2025[variavel["nome"]] = tabela["nome"]

    colunas: dict[str, ColunaStg] = {}
    fontes: dict[int, dict[str, str]] = {}
    #: (ano, tabela raw) -> {nome da variável: definição}
    por_raw: dict[tuple[int, str], dict[str, dict]] = {}

    for ano in sorted(catalogos):
        fontes[ano] = {}
        for tabela in catalogos[ano]["tabelas"]:
            por_raw[(ano, tabela["tabela_raw"])] = {
                variavel["nome"]: variavel for variavel in tabela["variaveis"]
            }
            for variavel in tabela["variaveis"]:
                nome = variavel["nome"]
                if nome in CHAVES_GLOBAIS:
                    continue
                canonico = de_para.canonizar(nome)
                destino = _tabela_de(nome, tabela_2025, de_para)
                fontes[ano].setdefault(destino, tabela["tabela_raw"])

                harmonizado = de_para.tipos_harmonizados.get(canonico)
                tipo = harmonizado.tipo if harmonizado else variavel["tipo_postgres"]

                coluna = colunas.get(canonico)
                if coluna is None:
                    coluna = ColunaStg(
                        nome=canonico,
                        tabela=destino,
                        tipo=tipo,
                        descricao=variavel["descricao"],
                    )
                    colunas[canonico] = coluna
                elif variavel["descricao"]:
                    coluna.descricao = variavel["descricao"]

                bruta = nome.lower()
                coluna.origens[ano] = harmonizado.sql(bruta) if harmonizado else bruta

    # Derivadas: preenchem os anos em que a variável deixou de ser publicada.
    for nome, derivada in de_para.derivadas.items():
        coluna = colunas.get(nome)
        if coluna is None:
            continue
        for ano, catalogo in catalogos.items():
            if ano in coluna.origens:
                continue
            disponivel = any(
                variavel["nome"] == derivada.origem
                for tabela in catalogo["tabelas"]
                for variavel in tabela["variaveis"]
            )
            if disponivel:
                coluna.origens[ano] = derivada.sql

    # Chaves: replicadas em cada tabela da stg, com origem no raw que alimenta
    # aquela tabela naquele ano.
    for tabela_stg, chaves in CHAVES.items():
        for posicao, chave in enumerate(chaves):
            nome = chave.upper()
            coluna: ColunaStg | None = None
            for ano, mapa in sorted(fontes.items()):
                origem = mapa.get(tabela_stg)
                if origem is None:
                    continue
                variavel = por_raw.get((ano, origem), {}).get(nome)
                if variavel is None:
                    continue
                harmonizado = de_para.tipos_harmonizados.get(nome)
                if coluna is None:
                    coluna = ColunaStg(
                        nome=nome,
                        tabela=tabela_stg,
                        tipo=(
                            harmonizado.tipo
                            if harmonizado
                            else variavel["tipo_postgres"]
                        ),
                        descricao=variavel["descricao"],
                    )
                    colunas[f"{tabela_stg}#{posicao}#{nome}"] = coluna
                coluna.origens[ano] = (
                    harmonizado.sql(nome.lower()) if harmonizado else nome.lower()
                )

    por_tabela: dict[str, list[ColunaStg]] = {nome: [] for nome in CHAVES}
    for coluna in colunas.values():
        por_tabela[coluna.tabela].append(coluna)
    for tabela_stg, lista in por_tabela.items():
        ordem_chave = {
            chave.upper(): posicao
            for posicao, chave in enumerate(CHAVES[tabela_stg])
        }
        lista.sort(key=lambda c: (ordem_chave.get(c.nome, len(ordem_chave)), c.nome))

    return por_tabela, fontes


def create_table(tabela: str, colunas: list[ColunaStg]) -> sql.Composed:
    definicoes = [
        sql.SQL("{} {}").format(
            sql.Identifier(coluna.nome.lower()), sql.SQL(coluna.tipo)
        )
        for coluna in colunas
    ]
    presentes = {coluna.nome.lower() for coluna in colunas}
    chave = [c for c in CHAVES[tabela] if c in presentes]
    if chave:
        definicoes.append(
            sql.SQL("PRIMARY KEY ({})").format(
                sql.SQL(", ").join(sql.Identifier(c) for c in chave)
            )
        )
    return sql.SQL("CREATE TABLE IF NOT EXISTS {}.{} (\n    {}\n)").format(
        sql.Identifier(SCHEMA),
        sql.Identifier(tabela),
        sql.SQL(",\n    ").join(definicoes),
    )


def transformacao(
    ano: int, tabela: str, colunas: list[ColunaStg], origem_raw: str
) -> sql.Composed:
    """INSERT INTO stg.<tabela> SELECT ... FROM raw.<origem>, para um ano."""

    presentes = [coluna for coluna in colunas if ano in coluna.origens]
    return sql.SQL(
        "INSERT INTO {destino} ({colunas})\nSELECT {expressoes}\nFROM {origem}"
    ).format(
        destino=sql.Identifier(SCHEMA, tabela),
        colunas=sql.SQL(", ").join(sql.Identifier(c.nome.lower()) for c in presentes),
        expressoes=sql.SQL(",\n       ").join(
            sql.SQL("{} AS {}").format(
                sql.SQL(coluna.origens[ano]), sql.Identifier(coluna.nome.lower())
            )
            for coluna in presentes
        ),
        origem=sql.Identifier("raw", origem_raw),
    )


def carregar(anos: list[int] | None = None) -> None:
    """Executa as transformações de raw para stg, ano a ano.

    Idempotente por ano: apaga o que já existe daquele ano antes de reinserir.
    """

    por_tabela, fontes = montar()

    with get_connection() as conexao:
        for ano in sorted(fontes):
            if anos and ano not in anos:
                continue
            for tabela, colunas in por_tabela.items():
                origem = fontes[ano].get(tabela)
                if origem is None:
                    continue
                with conexao.cursor() as cursor:
                    cursor.execute(
                        sql.SQL(
                            "DELETE FROM {} WHERE nu_ano_censo = %s"
                        ).format(sql.Identifier(SCHEMA, tabela)),
                        (ano,),
                    )
                    cursor.execute(transformacao(ano, tabela, colunas, origem))
                    gravadas = cursor.rowcount
                conexao.commit()
                logger.info(
                    "stg.%-14s %s  %6s linhas  <- raw.%s",
                    tabela,
                    ano,
                    f"{gravadas:,}",
                    origem,
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Modelo e DDL da camada stg")
    parser.add_argument("--aplicar", action="store_true", help="Cria as tabelas")
    parser.add_argument(
        "--carregar", action="store_true", help="Executa as transformações de raw"
    )
    parser.add_argument("--ano", type=int, help="Restringe --carregar a um ano")
    parser.add_argument(
        "--transformacao",
        type=int,
        metavar="ANO",
        help="Imprime o SQL de carga do ano",
    )
    args = parser.parse_args()

    por_tabela, fontes = montar()

    if args.transformacao:
        with get_connection() as conexao:
            for tabela, colunas in por_tabela.items():
                origem = fontes.get(args.transformacao, {}).get(tabela)
                if origem is None:
                    continue
                comando = transformacao(
                    args.transformacao, tabela, colunas, origem
                )
                print(comando.as_string(conexao) + ";\n")
        return

    if args.aplicar:
        with get_connection() as conexao:
            with conexao.cursor() as cursor:
                for tabela, colunas in por_tabela.items():
                    cursor.execute(create_table(tabela, colunas))
                    logger.info("stg.%s criada (%s colunas)", tabela, len(colunas))
            conexao.commit()
        return

    if args.carregar:
        carregar([args.ano] if args.ano else None)
        return

    for tabela, colunas in por_tabela.items():
        anos = {ano for coluna in colunas for ano in coluna.origens}
        print(
            f"  stg.{tabela:14} {len(colunas):4} colunas   "
            f"anos {min(anos)}-{max(anos)}"
        )


if __name__ == "__main__":
    main()
