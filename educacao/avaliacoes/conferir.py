"""Conferências de consistência da camada `stg` das avaliações.

`validar.py` confere o **catálogo** contra os arquivos: nomes e ordem de coluna.
Este módulo confere o **dado carregado** contra o que ele tem de satisfazer para
estar certo. São as verificações que fiz à mão durante a construção, guardadas
aqui para poderem ser repetidas — cada uma existe porque havia uma forma
plausível de errar em silêncio.

Uso::

    python -m educacao.avaliacoes.conferir
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from ..config.database import get_connection

#: Séries que cada etapa do IDEB tem de apresentar.
SERIES = {
    "anos_iniciais": [1, 2, 3, 4, 5],
    "anos_finais": [6, 7, 8, 9],
    "ensino_medio": [1, 2, 3, 4],
}

#: Escolas avaliadas sem contraparte em dw.dim_escola. São cinco: quatro do
#: IDEB, com medida real só na edição de 2005, e uma do PAEBES. As quatro
#: fecharam antes do Censo de 2007, que é onde a carga do Censo começa; elas
#: ainda aparecem nas edições seguintes da planilha porque o INEP projeta a
#: meta uma vez, a partir da linha de base, e a publica para toda a trajetória
#: — inclusive de escola que já fechou. Meta não é medição, e por isso a
#: conferência ignora as linhas que só têm `ideb_projecao`.
ORFAS_ESPERADAS = 5

CORRELACAO_MINIMA = 0.95
CORRELACAO_CONTROLE_MAXIMA = 0.50


@dataclass(slots=True)
class Conferencia:
    nome: str
    ok: bool
    detalhe: str


def _identidade_ideb(cursor) -> Conferencia:
    """IDEB = N x P.

    Se alguma medida tivesse sido atribuída à coluna errada durante a
    despivotagem, esta conta não fecharia.
    """

    cursor.execute(
        """
        SELECT count(*),
               count(*) FILTER (
                   WHERE abs(ideb_observado
                             - round(nota_media * indicador_rendimento, 1)) <= 0.1)
        FROM stg.ideb_escola
        WHERE ideb_observado IS NOT NULL
          AND nota_media IS NOT NULL
          AND indicador_rendimento IS NOT NULL
        """
    )
    total, batem = cursor.fetchone()
    return Conferencia(
        "IDEB = nota_media x indicador_rendimento",
        total > 0 and batem == total,
        f"{batem:,} de {total:,} linhas dentro de 0,1",
    )


def _series_por_etapa(cursor) -> Conferencia:
    """As séries lidas do rótulo humano são as que a etapa deve ter."""

    cursor.execute(
        """
        SELECT etapa, array_agg(DISTINCT serie ORDER BY serie)
        FROM stg.ideb_aprovacao_serie GROUP BY etapa ORDER BY etapa
        """
    )
    divergentes = []
    for etapa, series in cursor.fetchall():
        if SERIES.get(etapa) != list(series):
            divergentes.append(f"{etapa}={list(series)} (esperado {SERIES.get(etapa)})")
    return Conferencia(
        "séries do IDEB por etapa",
        not divergentes,
        "; ".join(divergentes) if divergentes else "anos_iniciais 1-5, "
        "anos_finais 6-9, ensino_medio 1-4",
    )


def _mascara_saeb(cursor) -> Conferencia:
    """A máscara municipal traduzida bate com o Censo; a deslocada, não.

    O SAEB publica a matrícula segundo o Censo. Se a tradução estivesse errada,
    município grande cairia em município pequeno e a correlação desabaria — é o
    que o controle deslocado demonstra.
    """

    cursor.execute(
        """
        WITH censo AS (
            SELECT e.co_municipio, m.nu_ano_censo AS ano,
                   sum(m.qt_mat_fund_ai) AS ai
            FROM stg.matricula m
            JOIN stg.escola e
              ON e.co_entidade = m.co_entidade AND e.nu_ano_censo = m.nu_ano_censo
            GROUP BY 1, 2
        ),
        mapa AS (
            SELECT ano, id_municipio_saeb, co_municipio,
                   lead(co_municipio) OVER (
                       PARTITION BY ano ORDER BY id_municipio_saeb) AS deslocado
            FROM stg.saeb_mascara_municipio
        ),
        saeb AS (
            SELECT co_municipio, ano,
                   max(matriculados_censo) FILTER (WHERE etapa = '5EF') AS m5
            FROM stg.saeb_municipio GROUP BY 1, 2
        )
        SELECT min(t.certo), max(t.control)
        FROM (
            SELECT s.ano,
                   corr(s.m5::float8, c.ai::float8) AS certo,
                   (SELECT corr(s2.m5::float8, c2.ai::float8)
                      FROM saeb s2
                      JOIN mapa mp ON mp.ano = s2.ano AND mp.co_municipio = s2.co_municipio
                      JOIN censo c2 ON c2.co_municipio = mp.deslocado AND c2.ano = s2.ano
                     WHERE s2.ano = s.ano) AS control
            FROM saeb s JOIN censo c USING (co_municipio, ano)
            GROUP BY s.ano
        ) t
        """
    )
    certo, controle = cursor.fetchone()
    if certo is None:
        return Conferencia("máscara municipal do SAEB", False, "sem dado para comparar")
    ok = certo >= CORRELACAO_MINIMA and controle <= CORRELACAO_CONTROLE_MAXIMA
    return Conferencia(
        "máscara municipal do SAEB",
        ok,
        f"pior correlação traduzida {certo:.4f}; melhor do controle "
        f"deslocado {controle:.4f}",
    )


def _mascara_completa(cursor) -> Conferencia:
    """Toda edição do SAEB tem os 78 municípios do ES traduzidos."""

    cursor.execute(
        """
        SELECT ano, count(*) FROM stg.saeb_mascara_municipio
        GROUP BY ano ORDER BY ano
        """
    )
    linhas = cursor.fetchall()
    cursor.execute("SELECT count(*) FROM dw.dim_municipio")
    esperado = cursor.fetchone()[0]
    ruins = [f"{ano}={n}" for ano, n in linhas if n != esperado]
    return Conferencia(
        "cobertura da máscara do SAEB",
        bool(linhas) and not ruins,
        "; ".join(ruins) if ruins else
        f"{len(linhas)} edições, {esperado} municípios cada",
    )


def _escolas_no_censo(cursor) -> Conferencia:
    """Toda escola com medição real existe em dw.dim_escola.

    Conta escolas, não pares escola-ano, e ignora as linhas que só carregam
    `ideb_projecao`: a meta é publicada para toda a trajetória mesmo depois de
    a escola fechar, e contá-la faria uma escola encerrada em 2005 aparecer
    como problema em nove edições seguidas.
    """

    cursor.execute(
        """
        SELECT count(*) FROM (
            SELECT DISTINCT co_entidade FROM stg.ideb_escola
             WHERE coalesce(ideb_observado, nota_media, aprovacao,
                            indicador_rendimento) IS NOT NULL
            UNION
            SELECT DISTINCT co_entidade FROM stg.enem_escola
            UNION
            SELECT DISTINCT co_entidade FROM stg.paebes_aluno
        ) a
        WHERE NOT EXISTS (
            SELECT 1 FROM dw.dim_escola d WHERE d.co_entidade = a.co_entidade
        )
        """
    )
    orfas = cursor.fetchone()[0]
    return Conferencia(
        "escolas avaliadas presentes em dw.dim_escola",
        orfas <= ORFAS_ESPERADAS,
        f"{orfas} escola(s) sem dimensão (tolerado até {ORFAS_ESPERADAS}: "
        f"4 do IDEB encerradas em 2005, 1 do PAEBES)",
    )


def _escalas(cursor) -> Conferencia:
    """As notas do IDEB, do SAEB e do PAEBES estão na mesma escala 0-500."""

    cursor.execute(
        """
        SELECT (SELECT max(nota_matematica) FROM stg.ideb_escola),
               (SELECT max(media_mt)       FROM stg.saeb_municipio),
               (SELECT max(proficiencia)   FROM stg.paebes_aluno),
               (SELECT max(nota_media)     FROM stg.ideb_escola)
        """
    )
    ideb, saeb, paebes, padronizada = cursor.fetchone()
    faixa = [v for v in (ideb, saeb, paebes) if v is not None]
    ok = all(100 < v < 500 for v in faixa) and (
        padronizada is None or padronizada <= 10
    )
    return Conferencia(
        "escalas de proficiência",
        ok,
        f"máximos: IDEB {ideb:.0f}, SAEB {saeb:.0f}, PAEBES {paebes:.0f}; "
        f"nota_media padronizada até {padronizada:.1f}",
    )


def _sem_duplicata(cursor) -> Conferencia:
    """As chaves primárias das tabelas de stg não têm repetição.

    Redundante com as PK declaradas, mas barato: se alguma tabela for recriada
    sem chave, esta conferência ainda pega.
    """

    alvos = {
        "stg.ideb_escola": "co_entidade, ano, etapa",
        "stg.enem_escola": "co_entidade, ano",
        "stg.saeb_municipio": "co_municipio, ano, etapa",
        "stg.paebes_aluno": "cd_aluno, ano, disciplina",
    }
    ruins = []
    for tabela, chave in alvos.items():
        cursor.execute(
            f"SELECT count(*) FROM (SELECT {chave} FROM {tabela}"
            f" GROUP BY {chave} HAVING count(*) > 1) d"
        )
        duplicadas = cursor.fetchone()[0]
        if duplicadas:
            ruins.append(f"{tabela}={duplicadas}")
    return Conferencia(
        "chaves sem duplicata",
        not ruins,
        "; ".join(ruins) if ruins else f"{len(alvos)} tabelas conferidas",
    )


CONFERENCIAS = (
    _identidade_ideb,
    _series_por_etapa,
    _mascara_saeb,
    _mascara_completa,
    _escolas_no_censo,
    _escalas,
    _sem_duplicata,
)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    resultados = []
    with get_connection() as conexao, conexao.cursor() as cursor:
        for conferencia in CONFERENCIAS:
            resultados.append(conferencia(cursor))

    for r in resultados:
        print(f"  {'ok   ' if r.ok else 'FALHA'} {r.nome:<44} {r.detalhe}")

    falhas = [r for r in resultados if not r.ok]
    print()
    print(f"{len(resultados) - len(falhas)}/{len(resultados)} conferências passam")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
