"""Dados manuais e config de programas: validação rígida, sem aceitar erro em silêncio."""

import textwrap
from pathlib import Path

import pytest
import yaml

from financiamento.etl import manuais, programas
from financiamento.etl.manuais import ErroManuais
from financiamento.etl.programas import ErroProgramas

MUNICIPIOS = {3205309, 3200102}


@pytest.fixture(scope="module")
def catalogo():
    return programas.carregar()


def _yaml(tmp_path: Path, texto: str) -> Path:
    p = tmp_path / "manuais.yaml"
    p.write_text(textwrap.dedent(texto), encoding="utf-8")
    return p


def test_arquivo_real_carrega_e_nao_traz_nenhum_valor_verificado(catalogo):
    """O arquivo entregue tem só marcadores: nada foi inventado."""
    from financiamento.etl.config import DADOS_MANUAIS
    d = manuais.carregar(catalogo, set(range(3200000, 3300000)), DADOS_MANUAIS)
    registros = [r for campos in d["programas"].values() for lista in campos.values() for r in lista]
    assert registros and not any(r["verificado"] for r in registros)
    assert d["mde"] == []
    # Portais: só entra endereço conferido, e todo portal preenchido tem data de verificação.
    assert len(d["portais"]) == 78
    for p in d["portais"]:
        assert p["verificado"] == bool(p["url"] or p["api"])
        assert not p["verificado"] or p["verificado_em"]


def test_portal_com_api_documentada(tmp_path, catalogo):
    """`api` é ponteiro para quem for buscar item e nota à mão; exige data como a url."""
    p = _yaml(tmp_path, """
        nivel3:
          portais_transparencia:
            - {cod_ibge: 3205309, url: "https://transparencia.exemplo.gov.br/",
               api: "https://ws.exemplo.gov.br/help/", verificado_em: 2026-09-22}
    """)
    r = manuais.carregar(catalogo, MUNICIPIOS, p)["portais"][0]
    assert r["verificado"] and r["api"] == "https://ws.exemplo.gov.br/help/"

    sem_data = _yaml(tmp_path, """
        nivel3:
          portais_transparencia:
            - {cod_ibge: 3205309, url: null, api: "https://ws.exemplo.gov.br/help/", verificado_em: null}
    """)
    with pytest.raises(ErroManuais, match="verificado_em"):
        manuais.carregar(catalogo, MUNICIPIOS, sem_data)

    fora = _yaml(tmp_path, """
        nivel3:
          portais_transparencia:
            - {cod_ibge: 3205309, url: null, api: "ws.exemplo.gov.br", verificado_em: 2026-09-22}
    """)
    with pytest.raises(ErroManuais, match="api deve começar com http"):
        manuais.carregar(catalogo, MUNICIPIOS, fora)


def test_registro_valido(tmp_path, catalogo):
    p = _yaml(tmp_path, """
        programas:
          cnca:
            adesao:
              - {cod_ibge: 3205309, valor: aderido, fonte: "Painel MEC", verificado_em: 2026-09-21}
    """)
    r = manuais.carregar(catalogo, MUNICIPIOS, p)["programas"]["cnca"]["adesao"][0]
    assert r["verificado"] and r["situacao"] == "informado" and r["verificado_em"] == "2026-09-21"


def test_marcador_sem_valor_nao_conta_como_verificado(tmp_path, catalogo):
    p = _yaml(tmp_path, """
        programas:
          cnca:
            adesao:
              - {cod_ibge: 3205309, valor: null, fonte: null, verificado_em: null}
    """)
    r = manuais.carregar(catalogo, MUNICIPIOS, p)["programas"]["cnca"]["adesao"][0]
    assert not r["verificado"] and r["situacao"] == "nao_verificado" and r["valor"] is None


@pytest.mark.parametrize("registro, trecho", [
    ("{cod_ibge: 3205309, valor: aderido}", "exige 'fonte' e 'verificado_em'"),
    ("{cod_ibge: 3205309, valor: aderido, fonte: X}", "exige 'fonte' e 'verificado_em'"),
    ("{cod_ibge: 3205309, valor: talvez, fonte: X, verificado_em: 2026-09-21}", "fora de"),
    ("{cod_ibge: 1234567, valor: aderido, fonte: X, verificado_em: 2026-09-21}", "não é um dos municípios do ES"),
    ("{cod_ibge: 3205309, valor: aderido, fonte: X, verificado_em: ontem}", "AAAA-MM-DD"),
])
def test_adesao_invalida(tmp_path, catalogo, registro, trecho):
    p = _yaml(tmp_path, f"programas:\n  cnca:\n    adesao:\n      - {registro}\n")
    with pytest.raises(ErroManuais, match=trecho):
        manuais.carregar(catalogo, MUNICIPIOS, p)


@pytest.mark.parametrize("registro, trecho", [
    ("{cod_ibge: 3205309, valor: 2, fonte: X, verificado_em: 2026-09-21}", "exige 'ano'"),
    ("{cod_ibge: 3205309, ano: 2025, valor: -1, fonte: X, verificado_em: 2026-09-21}", "maior ou igual a zero"),
    ("{cod_ibge: 3205309, ano: 2025, valor: 1.5, fonte: X, verificado_em: 2026-09-21}", "quantidade deve ser inteiro"),
    ("{cod_ibge: 3205309, ano: 2025, valor: dois, fonte: X, verificado_em: 2026-09-21}", "deve ser numérico"),
    ("{cod_ibge: 3205309, ano: 2025, situacao: chutei, fonte: X, verificado_em: 2026-09-21}", "não permitida"),
])
def test_articuladores_bolsa_invalido(tmp_path, catalogo, registro, trecho):
    p = _yaml(tmp_path, f"programas:\n  cnca:\n    articuladores_bolsa:\n      - {registro}\n")
    with pytest.raises(ErroManuais, match=trecho):
        manuais.carregar(catalogo, MUNICIPIOS, p)


def test_quantidade_zero_e_resposta_valida(tmp_path, catalogo):
    """Zero articuladores é "verificou e não há" — diferente do marcador sem valor."""
    p = _yaml(tmp_path, """
        programas:
          cnca:
            articuladores_bolsa:
              - {cod_ibge: 3200102, ano: 2025, valor: 0, fonte: "Ofício SEDU 12/2026", verificado_em: 2026-09-21}
              - {cod_ibge: 3205309, ano: null, valor: null, fonte: null, verificado_em: null}
    """)
    regs = manuais.carregar(catalogo, MUNICIPIOS, p)["programas"]["cnca"]["articuladores_bolsa"]
    assert regs[0]["verificado"] and regs[0]["valor"] == 0 and regs[0]["situacao"] == "informado"
    assert not regs[1]["verificado"] and regs[1]["situacao"] == "nao_verificado"


def test_sem_amostra_e_diferente_de_zero(tmp_path):
    """Campo percentual manual com `situacoes`: "sem amostra" é afirmação verificada, sem valor."""
    cfg = tmp_path / "p.yaml"
    cfg.write_text(yaml.safe_dump({"programas": [{
        "id": "x", "nome": "X", "fundo_repasse": "F", "acesso": "manual", "granularidade": "municipio",
        "indicador_meta": {"id": "taxa"},
        "campos": [{"id": "taxa", "rotulo": "Taxa", "tipo": "percentual", "origem": "manual", "serie": True,
                    "situacoes": ["informado", "sem_amostra"]}]}]}, allow_unicode=True), encoding="utf-8")
    catalogo = programas.carregar(cfg)
    p = _yaml(tmp_path, """
        programas:
          x:
            taxa:
              - {cod_ibge: 3200102, ano: 2023, situacao: sem_amostra, fonte: "INEP", verificado_em: 2026-09-21}
    """)
    r = manuais.carregar(catalogo, MUNICIPIOS, p)["programas"]["x"]["taxa"][0]
    assert r["situacao"] == "sem_amostra" and r["valor"] is None and r["verificado"]
    with pytest.raises(ErroManuais, match="não pode ter valor"):
        manuais.carregar(catalogo, MUNICIPIOS, _yaml(tmp_path, """
            programas:
              x:
                taxa:
                  - {cod_ibge: 3200102, ano: 2023, situacao: sem_amostra, valor: 0, fonte: "INEP", verificado_em: 2026-09-21}
        """))


def test_mde_manual_valido_e_invalido(tmp_path, catalogo):
    ok = _yaml(tmp_path, """
        financiamento_geral:
          mde_aplicado_pct:
            - {cod_ibge: 3205309, ano: 2024, valor: 26.4, fonte: "SIOPE", verificado_em: 2026-09-21}
    """)
    assert manuais.carregar(catalogo, MUNICIPIOS, ok)["mde"][0]["valor"] == 26.4
    ruim = _yaml(tmp_path, """
        financiamento_geral:
          mde_aplicado_pct:
            - {cod_ibge: 3205309, ano: 2024, valor: -3, fonte: "SIOPE", verificado_em: 2026-09-21}
    """)
    with pytest.raises(ErroManuais, match="fora de 0–100"):
        manuais.carregar(catalogo, MUNICIPIOS, ruim)


def test_programa_ou_campo_inexistente_e_rejeitado(tmp_path, catalogo):
    with pytest.raises(ErroManuais, match="não existe em programas.yaml"):
        manuais.carregar(catalogo, MUNICIPIOS, _yaml(tmp_path, "programas:\n  outro:\n    x: []\n"))
    with pytest.raises(ErroManuais, match="não existe em programas.yaml"):
        manuais.carregar(catalogo, MUNICIPIOS, _yaml(tmp_path, "programas:\n  cnca:\n    inventado: []\n"))


# --------------------------------------------------------------- programas.yaml

def test_cnca_esta_declarado_com_os_campos_esperados(catalogo):
    cnca = next(p for p in catalogo if p["id"] == "cnca")
    assert {c["id"] for c in cnca["campos"]} == {"adesao", "repasse", "ica", "articuladores_bolsa"}
    # O indicador de meta é o ICA (INEP), automático; o corte de 743 pontos está na própria planilha do INEP.
    assert cnca["indicador_meta"]["id"] == "ica" and cnca["indicador_meta"]["limiar_pontos"] == 743
    assert cnca["acesso"] == "hibrido" and cnca["granularidade"] == "municipio"
    origem = {c["id"]: c["origem"] for c in cnca["campos"]}
    assert origem == {"adesao": "manual", "repasse": "api", "ica": "api", "articuladores_bolsa": "manual"}
    assert next(c for c in cnca["campos"] if c["id"] == "articuladores_bolsa")["tipo"] == "quantidade"
    assert cnca["modulo_automatico"] == "cnca"
    # Checklist de governança: ids únicos e cada item com a referência de onde veio (TCE-PB / decreto).
    itens = cnca["checklist_governanca"]
    assert len(itens) == 10 and len({i["id"] for i in itens}) == 10
    assert all(i["texto"] and i["referencia"] for i in itens)
    assert sum("TCE-PB" in i["referencia"] for i in itens) >= 8


def test_novo_programa_so_precisa_de_config(tmp_path):
    """Adicionar um programa = um bloco novo; nenhuma lógica muda."""
    cfg = yaml.safe_dump({"programas": [{
        "id": "novo_mais_educacao", "nome": "Novo Mais Educação", "fundo_repasse": "PDDE", "acesso": "manual",
        "granularidade": "escola", "indicador_meta": {"id": "aprend"},
        "campos": [{"id": "aprend", "rotulo": "Aprendizagem", "tipo": "percentual", "origem": "manual"}],
    }]}, allow_unicode=True)
    p = tmp_path / "p.yaml"
    p.write_text(cfg, encoding="utf-8")
    assert programas.carregar(p)[0]["id"] == "novo_mais_educacao"


@pytest.mark.parametrize("mexer, trecho", [
    (lambda p: p.pop("fundo_repasse"), "falta a chave"),
    (lambda p: p.update(acesso="telepatia"), "acesso"),
    (lambda p: p.update(granularidade="bairro"), "granularidade"),
    (lambda p: p["campos"][0].update(tipo="inventado"), "tipo"),
    (lambda p: p["campos"][0].update(origem="oraculo"), "origem"),
    (lambda p: p["indicador_meta"].update(id="nao_existe"), "indicador_meta.id"),
    (lambda p: p["campos"].append(dict(p["campos"][0])), "campo repetido"),
    (lambda p: p["campos"].append({"id": "d", "rotulo": "D", "tipo": "categorico", "origem": "manual",
                                   "valores_validos": ["sim"], "kpi": {"valor": "sim"}}), "kpi exige 'rotulo'"),
    (lambda p: p["campos"].append({"id": "d", "rotulo": "D", "tipo": "categorico", "origem": "manual",
                                   "valores_validos": ["sim", "nao"], "rotulos_valores": {"sim": "Sim"}}), "rotulos_valores"),
    (lambda p: p.update(checklist_governanca=[{"id": "a"}]), "checklist exige"),
    (lambda p: p.update(checklist_governanca=[{"id": "a", "texto": "T"}, {"id": "a", "texto": "U"}]), "checklist repetido"),
])
def test_config_de_programa_invalida(tmp_path, mexer, trecho):
    p = {"id": "x", "nome": "X", "fundo_repasse": "F", "acesso": "manual", "granularidade": "municipio",
         "indicador_meta": {"id": "c"},
         "campos": [{"id": "c", "rotulo": "C", "tipo": "percentual", "origem": "manual"}]}
    mexer(p)
    arq = tmp_path / "p.yaml"
    arq.write_text(yaml.safe_dump({"programas": [p]}, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ErroProgramas, match=trecho):
        programas.carregar(arq)
