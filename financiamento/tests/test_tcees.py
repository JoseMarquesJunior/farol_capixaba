"""TCE-ES (dados abertos): parsers, prazos, obras, empenhos e o cliente com recorte. Sem rede."""

import gzip
import io
import json
import zipfile
from datetime import datetime, timezone

import pandas as pd
import pytest

from financiamento.etl import tcees

MUN = tcees.Municipios({3200102: "Afonso Cláudio", 3205309: "Vitória"})


def test_numero_brasileiro_e_vazio_nunca_vira_zero():
    s = tcees.num_br(pd.Series(["1.234,56", ",00", "", "-10,5"]))
    assert s[0] == pytest.approx(1234.56) and s[1] == 0.0 and pd.isna(s[2]) and s[3] == pytest.approx(-10.5)


def test_municipio_pelo_nome_como_o_tribunal_escreve():
    assert MUN.cod("AFONSO CLAUDIO") == 3200102 and MUN.cod("Vitória") == 3205309 and MUN.cod("Serra") is None


def test_le_arquivo_pequeno_em_utf16(tmp_path):
    p = tmp_path / "bens.dat.gz"
    with gzip.open(p, "wb") as f:
        f.write("NomeBemVinculador;Latitude\nEMEF São José;-20,1\n".encode("utf-16"))
    df = tcees.ler_dat(tcees.Arquivo("bens", "u", "t", p))
    assert df.loc[0, "NomeBemVinculador"] == "EMEF São José"


def test_mde_apurado_pelo_tribunal():
    df = pd.DataFrame({"Ano": ["2024", "2024"], "Municipio": ["Vitória", "Cidade Fora"], "Aplicacao": ["1.000,00", "1,00"],
                       "AplicacaoPercentual": ["24,90", "30"], "Alunos": ["100", "1"], "AplicacaoPorAluno": ["10,00", "1"],
                       "MesUltimoEnvio": ["12", "12"], "ReceitaFUNDEB": ["500,00", "1"]})
    m = tcees.mde_tcees(df, MUN)
    assert len(m) == 1                                           # município fora do ES não entra
    r = m.iloc[0]
    assert r.cod_ibge == 3205309 and r.ano == 2024 and r.tcees_mde_pct == pytest.approx(24.9)


def test_prazo_das_remessas_vem_da_fonte():
    df = pd.DataFrame({"Município": ["Vitória"] * 5, "UnidadeGestora": ["PMV", "PMV", "Câmara", "PMV", "Câmara"],
                       "Mes": ["1", "2", "3", "9", "2"], "Ano": ["2026"] * 5,
                       "DataHomologacao": ["2026-02-10 10:00:00", "2026-03-20 10:00:00", "", "", "2026-03-01 09:00:00"],
                       "DataLimite": ["2026-02-15 23:59:59", "2026-03-17 23:59:59", "2026-04-15 23:59:59", "2026-10-15 23:59:59",
                                      "2026-03-17 23:59:59"]})
    d = tcees.remessas_pcm(df, MUN, datetime(2026, 5, 15, 15, tzinfo=timezone.utc))
    assert list(d["situacao"]) == ["no_prazo", "com_atraso", "nao_homologada", "prazo_aberto", "no_prazo"]
    assert d["dias_atraso"].iloc[1] == 3                           # 2,4 dias arredonda para cima
    assert d["dias_atraso"].iloc[2] == 29                          # desde o limite até a coleta
    r = tcees.resumo_pcm(d).iloc[0]
    assert (r.pcm_remessas, r.pcm_com_atraso, r.pcm_nao_homologadas, r.pcm_ugs) == (5, 1, 1, 2)


def test_ug_que_nunca_homologou_na_janela_nao_vira_atraso():
    df = pd.DataFrame({"Município": ["Vitória"] * 3, "UnidadeGestora": ["Fundo X"] * 3, "Mes": ["1", "2", "3"],
                       "Ano": ["2026"] * 3, "DataHomologacao": [""] * 3,
                       "DataLimite": ["2026-02-15 23:59:59", "2026-03-17 23:59:59", "2026-04-15 23:59:59"]})
    d = tcees.remessas_pcm(df, MUN, datetime(2026, 5, 15, tzinfo=timezone.utc))
    assert set(d["situacao"]) == {"ug_sem_remessa"} and d["dias_atraso"].isna().all()
    r = tcees.resumo_pcm(d).iloc[0]
    assert (r.pcm_remessas, r.pcm_nao_homologadas, r.pcm_ugs_sem_remessa) == (0, 0, 1)


def _obras():
    base = {"NomeEsferaAdministrativaReferencia": "Vitória", "IdentificacaoContratacao": "C1", "ChaveInstrumento": "K1",
            "NomeUnidadeGestoraReferenciaInstrumento": "SEME", "NomeUnidadeGestoraReferencia": "PMV",
            "ObjetoInstrumento": "Reforma da EMEF A", "ObjetoContratacao": "x", "NomeContratado": "Construtora X ",
            "NumeroIdentificacaoContratado1": "12345678000199", "ValorTotalInstrumento": "1.000,00",
            "ValorAtualContratacao": "", "SituacaoObra": "Paralisação presumida", "TipoIntervencao": "Reforma",
            "DataAssinaturaInstrumentoContratacao": "2024-03-01T00:00:00", "FimVigenciaContrato": "2025-03-01",
            "UrlInstrumentoContratacao": "http://c", "UrlEdital": "", "SetorBeneficiado": "Educação"}
    return pd.DataFrame([base, {**base, "ChaveInstrumento": "K2", "IdentificacaoContratacao": "C2", "SetorBeneficiado": "Saúde"}])


def test_obras_da_educacao_com_predio_e_medicoes():
    bens = pd.DataFrame({"IdentificacaoContratacao": ["C1"], "NomeBemVinculador": ["EMEF A"], "ObjetoIntervencao": ["Educacional"],
                         "LatitudeCentroide": ["-20.3"], "LongitudeCentroide": ["-40.3"]})
    med = pd.DataFrame({"ChaveInstrumento": ["K1", "K1", "K1"], "NumeroMedicao": ["1", "1", "2"], "AnoMedicao": ["2024"] * 3,
                        "ValorTotalMedicao": ["100,00", "100,00", "150,00"], "ValorPagamento": ["100,00", "100,00", "0"],
                        "DataFimMedicao": ["2024-05-01", "2024-05-01", "2024-07-01"],
                        "NumeroTermoContratualAlteracao": ["", "", "1"], "AnoTermoContratualAlteracao": ["", "", "2024"],
                        "ValorTotalContratacaoAlteracao": ["", "", "0"]})
    o = tcees.obras_educacao(_obras(), bens, med, MUN)
    assert len(o) == 1                                             # só o setor Educação
    r = o.iloc[0]
    assert r.valor == 1000.0                                       # sem valor atual: o inicial
    assert json.loads(r.bens)[0] == {"nome": "EMEF A", "categoria": "Educacional", "lat": -20.3, "lon": -40.3}
    assert r.medicoes == 2 and r.valor_medido == 250.0            # medição repetida conta uma vez
    assert r.pct_medido == 25.0 and r.aditivos == 1 and r.ultima_medicao == "2024-07-01"


def _empenhos():
    linha = {c: "" for c in tcees.COLUNAS_EMPENHO}
    linha.update({"Ano": "2024", "Mes": "3", "EsferaAdministrativa": "Vitória", "CodigoSubFuncao": "361", "CodigoAcao": "2001",
                  "NomeAcao": "Manutenção do ensino", "NomePrograma": "Ensino", "CodigoModalidade": "90", "CodigoElemento": "39",
                  "DescricaoElemento": "Serviços PJ", "CodigoFonteReduzida": "1500", "NomeFonteReduzida": "Impostos",
                  "CodigoDetalhamento": "0", "NomeDetalhamento": "Geral", "Empenhada": "100,00", "Liquidada": "80,00",
                  "Paga": "50,00", "NumeroEmpenho": "1", "NomeCredorFornecedor": "Empresa A", "CodigoCredorFornecedor": "111",
                  "NomeIdentificacao": "CNPJ"})
    linhas = [
        linha,
        {**linha, "NumeroEmpenho": "2", "NomeCredorFornecedor": "Maria", "CodigoCredorFornecedor": "999", "NomeIdentificacao": "CPF",
         "Empenhada": "10,00"},
        {**linha, "NumeroEmpenho": "3", "NomeCredorFornecedor": "João", "CodigoCredorFornecedor": "998", "NomeIdentificacao": "CPF",
         "Empenhada": "5,00"},
        {**linha, "NumeroEmpenho": "4", "NomeCredorFornecedor": "CONSELHO DE ESCOLA DA EMEF A", "CodigoCredorFornecedor": "222",
         "Empenhada": "30,00", "NomeAcao": "PMDDE - dinheiro direto na escola"},
        {**linha, "NumeroEmpenho": "5", "NomeDetalhamento": "FUNPAES - Pacto pela aprendizagem", "Empenhada": "20,00",
         "CodigoElemento": "30", "DescricaoElemento": "Material de consumo"},
        {**linha, "NumeroEmpenho": "6", "CodigoModalidade": "91", "Empenhada": "1.000,00"},   # intra: fora
        {**linha, "NumeroEmpenho": "7", "Ano": "", "Empenhada": "1,00"},                    # sem ano: o do arquivo
    ]
    return pd.DataFrame(linhas)


def test_empenhos_agregados_sem_intra_e_com_pessoa_fisica_agregada():
    e = tcees.empenhos(_empenhos(), MUN, 2024)
    assert e["intra"].sum() == 1 and (e["ano"] == 2024).all()
    ag = tcees.agregados_empenhos(e, {2024: "q1"})
    assert ag["total"].iloc[0].tcees_emp_empenhada == pytest.approx(166.0)
    assert ag["total"].iloc[0].tcees_emp_meses == 1                            # só março no exemplo
    assert ag["total"].iloc[0].tcees_emp_meses_ausentes == "1,2,4,5,6,7,8,9,10,11,12"
    cred = ag["credores"].set_index("credor")
    assert cred.loc["(pessoa física)", "empenhada"] == pytest.approx(15.0)   # CPF nunca aparece nominalmente
    assert "999" not in cred.index and "Maria" not in set(ag["credores"]["credor_nome"])
    assert list(ag["conselhos"]["credor"]) == ["222"]
    assert ag["funpaes"]["empenhada"].sum() == pytest.approx(20.0)
    assert (ag["credores"]["q"] == "q1").all()


def test_dotacao_por_acao_marca_obra():
    df = pd.DataFrame({"Ano": ["2024"] * 3, "EsferaAdministrativa": ["Vitória"] * 3, "CodigoModalidade": ["90", "90", "91"],
                       "CodigoAcao": ["1001", "2001", "2001"], "NomeAcao": ["Construção de creche", "Manutenção", "Manutenção"],
                       "CodigoElemento": ["51", "39", "39"], "PrevisaoInicial": ["100,00", "50,00", "999"],
                       "PrevisaoAtualizada": ["120,00", "50,00", "999"], "Empenhada": ["30,00", "50,00", "999"],
                       "Liquidada": ["0", "0", "0"], "Paga": ["0", "0", "0"]})
    d = tcees.dotacao_acoes(df, MUN).set_index("CodigoAcao")
    assert bool(d.loc["1001", "obra"]) and not bool(d.loc["2001", "obra"])
    assert d.loc["2001", "PrevisaoAtualizada"] == 50.0                    # intra (91) fora


# ------------------------------------------------------------------ cliente

class _Resp:
    def __init__(self, status, conteudo=b""):
        self.status_code, self.content, self._c = status, conteudo, conteudo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise tcees.requests.HTTPError(str(self.status_code))

    def iter_content(self, n):
        yield self._c

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _zip_csv(texto):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("dados.csv", texto.encode("latin-1"))
    return b.getvalue()


def test_recorte_de_zip_guarda_so_o_filtrado_com_hash_do_original(tmp_path, monkeypatch):
    c = tcees.ClienteTcees(tmp_path, pausa=0)
    bruto = _zip_csv("CodigoFuncao;Valor\n12;1\n10;2\n12;3\n")
    monkeypatch.setattr(c.sessao, "get", lambda *a, **k: _Resp(200, bruto))
    a = c.recorte_zip("empenhos/2024/p1", "https://x/p1.zip", tcees.so_educacao, {"filtro": "12"})
    df = tcees.ler_recorte(a)
    assert list(df["Valor"]) == ["1", "3"]
    assert a.extra["linhas_total"] == 3 and a.extra["linhas_mantidas"] == 2
    assert a.sha256 == tcees.hashlib.sha256(bruto).hexdigest() and a.recorte
    # segunda leitura: do cache, sem rede
    monkeypatch.setattr(c.sessao, "get", lambda *a, **k: pytest.fail("não devia baixar de novo"))
    assert tcees.ClienteTcees(tmp_path, atualizar="offline").recorte_zip("empenhos/2024/p1", "u", tcees.so_educacao, {}).obtido_em


def test_recusa_do_portal_para_a_coleta(tmp_path, monkeypatch):
    c = tcees.ClienteTcees(tmp_path, pausa=0)
    chamadas = []
    monkeypatch.setattr(c.sessao, "get", lambda *a, **k: chamadas.append(1) or _Resp(429))
    with pytest.raises(tcees.ServidorRecusou):
        c.recorte_zip("a", "https://x/a.zip", tcees.so_educacao, {})
    with pytest.raises(tcees.ServidorRecusou):
        c.recorte_zip("b", "https://x/b.zip", tcees.so_educacao, {})
    assert len(chamadas) == 1 and c.recusou


def test_offline_sem_cache_e_nao_coletado(tmp_path):
    c = tcees.ClienteTcees(tmp_path, atualizar="offline")
    assert c.recursos("qualquer") == [] and c.pequeno("educacao").obtido_em == ""


def test_executar_offline_sem_cache_vira_aviso_e_nao_quebra(tmp_path, monkeypatch):
    monkeypatch.setattr(tcees, "PASTA_CACHE", tmp_path)
    r = tcees.executar({3205309: "Vitória"}, [2024], atualizar="offline")
    assert r.mde.empty and r.obras.empty and r.status["ok"]
    assert {a["recurso"] for a in r.avisos} >= {"educacao", "pcm", "obras"}


class _RespQuebra(_Resp):
    """Resposta que cai no meio do corpo, como o portal fez com um ZIP de 34 MB."""

    def iter_content(self, n):
        yield self._c[:10]
        raise tcees.requests.exceptions.ChunkedEncodingError("Connection broken: IncompleteRead")


def test_conexao_que_cai_no_meio_do_download_e_tentada_de_novo(tmp_path, monkeypatch):
    c = tcees.ClienteTcees(tmp_path, pausa=0)
    monkeypatch.setattr(tcees.time, "sleep", lambda s: None)
    bruto = _zip_csv("CodigoFuncao;Valor\n12;1\n")
    respostas = iter([_RespQuebra(200, bruto), _Resp(200, bruto)])
    monkeypatch.setattr(c.sessao, "get", lambda *a, **k: next(respostas))
    a = c.recorte_zip("p", "https://x/p.zip", tcees.so_educacao, {})
    assert a.sha256 == tcees.hashlib.sha256(bruto).hexdigest()           # o hash é do download completo


def test_conexao_que_sempre_cai_vira_erro_da_fonte_nao_excecao_solta(tmp_path, monkeypatch):
    c = tcees.ClienteTcees(tmp_path, pausa=0, tentativas=2)
    monkeypatch.setattr(tcees.time, "sleep", lambda s: None)
    monkeypatch.setattr(c.sessao, "get", lambda *a, **k: _RespQuebra(200, b"x" * 100))
    with pytest.raises(tcees.ErroTcees, match="interrompido"):
        c.recorte_zip("p", "https://x/p.zip", tcees.so_educacao, {})


def test_reduzir_por_parte_da_o_mesmo_que_o_ano_inteiro():
    """O recorte vem em 3–5 partes por ano; reduzir parte a parte não pode mudar o total."""
    e = tcees.empenhos(_empenhos(), MUN, 2024)
    inteiro = tcees.agregados_empenhos(e, {2024: "q1"})
    partes = [tcees.reduzir_empenhos(e.iloc[:3]), tcees.reduzir_empenhos(e.iloc[3:])]
    em_partes = tcees.agregados_empenhos(partes, {2024: "q1"})
    for nome, t in inteiro.items():
        a = t.sort_values(list(t.columns)).reset_index(drop=True)
        b = em_partes[nome].sort_values(list(t.columns)).reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_like=True, check_dtype=False)


def test_layout_de_2024_com_ano_e_mes_de_referencia():
    """O TCE-ES renomeou as colunas de período em 2024; o parser aceita os dois layouts."""
    novo = _empenhos().rename(columns={"Ano": "AnoReferencia", "Mes": "MesReferencia"}).assign(
        AnoCompetencia="2024", DataEmissao="2024-01-26 00:00:00")
    e = tcees.empenhos(novo, MUN, 2024)
    assert (e["ano"] == 2024).all() and set(e["Mes"]) == {"3"}
    assert tcees.agregados_empenhos(e, {2024: "q"})["total"].iloc[0].tcees_emp_meses == 1


def test_remessa_repetida_na_fonte_fica_com_a_homologada():
    """A fonte repete UG × mês (sem código de UG para distinguir): vale a linha homologada."""
    df = pd.DataFrame({"Município": ["Vitória"] * 2, "UnidadeGestora": ["PMV"] * 2, "Mes": ["1", "1"], "Ano": ["2026"] * 2,
                       "DataHomologacao": ["", "2026-02-10 10:00:00"], "DataLimite": ["2026-02-15 23:59:59"] * 2})
    d = tcees.remessas_pcm(df, MUN, datetime(2026, 5, 15, tzinfo=timezone.utc))
    assert len(d) == 1 and d["situacao"].iloc[0] == "no_prazo"


# ---------------------------------------------- contratações e itens (o que foi comprado)

def _linha_item(**campos):
    base = {"UnidadeGestoraReferencia": "077E0600005",
            "NomeUnidadeGestoraReferencia": "Secretaria Municipal de Educação de Vitória",
            "EsferaAdministrativa": "Vitória", "AnoReferencia": "2024", "MesReferencia": "7",
            "IdentificacaoContratacao": "2023.077E0600002.01.0018", "NumeroEdital": "010", "AnoEdital": "2023",
            "NumeroInstrumentoContratacao": "302", "AnoInstrumentoContratacao": "2023", "CodigoLote": "1",
            "CodigoItem": "1", "DescricaoItem": "MESA  mesa angular de trabalho", "UnidadeMedida": "Unidade",
            "QuantidadeItemContratado": "2,000000", "ValorUnitarioItemContratado": "1.975,000000",
            "ValorTotalItemContratado": "3.950,00", "TipoAlteracao": "", "NumeroTermoContratualAlteracao": "",
            "AnoTermoContratualAlteracao": "", "InicioVigenciaTermoAlteracaoContratual": "",
            "QuantidadeItemAlterado": "", "ValorUnitarioItemAlterado": "", "ValorTotalItemAlterado": "",
            "NumeroMedicao": "", "AnoMedicao": "", "QuantidadeItemMedido": "", "ValorUnitarioItemMedido": "",
            "ValorTotalItemMedido": "", "NumeroIdentificacaoContratado1": "04405032000128",
            "NomeContratado1": "ENGESAN ENGENHARIA LTDA", "NumeroIdentificacaoContratado2": "", "NomeContratado2": "",
            "ChaveInstrumento": "077E0600005-2023.077E0600002.01.0018-010-2023-302-2023", "vinculo": "ug_educacao"}
    return {**base, **campos}


def test_itens_separam_o_contratado_do_medido():
    """O arquivo repete o item: uma linha do contratado e uma por medição (sem descrição)."""
    df = pd.DataFrame([
        _linha_item(),
        _linha_item(DescricaoItem="", QuantidadeItemContratado="", ValorUnitarioItemContratado="",
                    ValorTotalItemContratado="", NumeroMedicao="00001", AnoMedicao="2024",
                    QuantidadeItemMedido="2,000000", ValorTotalItemMedido="3.950,00"),
        _linha_item(CodigoItem="2", DescricaoItem="ARMÁRIO ALTO", ValorTotalItemContratado="48.800,00"),
        _linha_item(EsferaAdministrativa="Cidade Fora", CodigoItem="9"),        # fora do ES: não entra
    ])
    it = tcees.itens_educacao(df, MUN)
    assert len(it) == 2 and set(it["cod_ibge"]) == {3205309}
    primeiro = it[it["item"] == "1"].iloc[0]
    assert primeiro.descricao == "MESA mesa angular de trabalho"                 # espaço duplo colapsado
    assert primeiro.quantidade == pytest.approx(2.0) and primeiro.valor_total == pytest.approx(3950.0)
    assert primeiro.medicoes == 1 and primeiro.valor_medido == pytest.approx(3950.0)
    assert pd.isna(it[it["item"] == "2"].iloc[0].valor_medido)                   # sem medição nunca vira zero
    assert (it["ano"] == 2023).all()                                             # ano do INSTRUMENTO, não do arquivo


def test_item_de_contrato_plurianual_conta_uma_vez_e_soma_as_medicoes():
    """O mesmo item reaparece no arquivo do ano seguinte por causa de uma medição nova."""
    p2023 = tcees.itens_educacao(pd.DataFrame([
        _linha_item(AnoReferencia="2023"),
        _linha_item(AnoReferencia="2023", DescricaoItem="", NumeroMedicao="00001", AnoMedicao="2023",
                    ValorTotalItemMedido="1.000,00")]), MUN).assign(q="q2023")
    p2024 = tcees.itens_educacao(pd.DataFrame([
        _linha_item(AnoReferencia="2024"),
        _linha_item(AnoReferencia="2024", DescricaoItem="", NumeroMedicao="00002", AnoMedicao="2024",
                    ValorTotalItemMedido="2.950,00")]), MUN).assign(q="q2024")
    ag = tcees.agregados_itens([p2023, p2024])
    assert len(ag["itens"]) == 1                                   # uma linha, não duas
    r = ag["itens"].iloc[0]
    assert r.valor_total == pytest.approx(3950.0)                  # o contratado NÃO é somado duas vezes
    assert r.medicoes == 2 and r.valor_medido == pytest.approx(3950.0)
    assert r.q == "q2023"                                          # proveniência do arquivo que declarou o item
    resumo = ag["itens_resumo"].iloc[0]
    assert resumo.itens == 1 and resumo.contratadas == 1 and resumo.valor_contratado == pytest.approx(3950.0)
    assert ag["itens_contratada"].iloc[0].cnpj_contratada == "04405032000128"


def test_agregados_itens_sem_nenhuma_parte_nao_quebra():
    ag = tcees.agregados_itens([])
    assert ag["itens"].empty and list(ag["itens"].columns) == tcees.COLUNAS_ITEM
    assert ag["itens_resumo"].empty and ag["itens_contratada"].empty


def test_vinculo_com_a_educacao_so_pelas_regras_da_fonte():
    """O CNPJ da contratada não é regra: quem vende à educação também vende ao resto."""
    f = tcees.filtro_itens(MUN, {"2024.X.01.0001"}, {"CHAVE-OBRA"})
    prefeitura = _linha_item(NomeUnidadeGestoraReferencia="Prefeitura Municipal de Vitória",
                             IdentificacaoContratacao="2024.X.01.9999", ChaveInstrumento="OUTRA")
    assert f(_linha_item()) == "ug_educacao"
    assert f({**prefeitura, "IdentificacaoContratacao": "2024.X.01.0001"}) == "setor_educacao"
    assert f({**prefeitura, "ChaveInstrumento": "CHAVE-OBRA"}) == "obra_educacao"
    assert f(prefeitura) is None                                    # o CNPJ conhecido, sozinho, não basta
    assert f({**prefeitura, "EsferaAdministrativa": "Cidade Fora"}) is None


def test_contratacoes_ficam_com_a_declaracao_mais_recente():
    """A mesma contratação vem repetida por mês de referência."""
    base = {"NomeEsferaAdministrativa": "Vitória", "AnoReferencia": "2024",
            "IdentificacaoContratacao": "2024.077.01.0001", "NomeUnidadeGestoraReferencia": "Fundo Municipal de Educação",
            "ObjetoContratacao": "Aquisição de merenda", "SetorBeneficiado": "", "ModalidadeLicitacao": "Pregão Eletrônico",
            "TipoContratacao": "Compras", "SituacaoContratacao": "Licitação Homologada", "UrlEdital": "",
            "ValorEstimado": "100,00", "ValorTotalContratacao": "90,00", "vinculo": "ug_educacao"}
    df = pd.DataFrame([{**base, "MesReferencia": "3"}, {**base, "MesReferencia": "9", "ValorTotalContratacao": "95,00"}])
    c = tcees.contratacoes_educacao(df, MUN)
    assert len(c) == 1 and c.iloc[0].valor_total == pytest.approx(95.0) and c.iloc[0].cod_ibge == 3205309


def _credor_acao_bruto(n, acao="2001"):
    return pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "CodigoAcao": acao, "NomeAcao": "Manutenção",
                          "credor": f"{i:014d}", "credor_nome": f"Empresa {i}", "NomeIdentificacao": "CNPJ",
                          "DescricaoElemento": "Material", "CodigoFonteReduzida": "1500",
                          "empenhada": float(n - i), "liquidada": 0.0, "paga": 0.0, "lancamentos": 1} for i in range(n)])


def test_credor_acao_guarda_os_maiores_e_soma_a_cauda():
    """Nenhum valor some do total: os pequenos viram uma linha "(demais)"."""
    n = tcees.MAIORES_CREDORES + 3
    bruto = _credor_acao_bruto(n)
    d = tcees.credor_acao(bruto, {2024: "q1"})
    # Com uma ação só, o corte que vale é o dos maiores credores do ente.
    assert len(d) == tcees.MAIORES_CREDORES + 1
    resto = d[d["credor"] == "(demais)"].iloc[0]
    assert resto.demais == 3 and resto.elemento is None
    assert d["empenhada"].sum() == pytest.approx(bruto["empenhada"].sum())   # a soma continua inteira
    assert (d["q"] == "q1").all()


def test_credor_grande_espalhado_por_muitas_acoes_nao_some_do_detalhamento():
    """Clicar num credor da tabela tem de mostrar TODAS as ações dele, não só onde é grande."""
    grande = [{"cod_ibge": 3205309, "ano": 2024, "CodigoAcao": f"{2000 + i}", "NomeAcao": f"Ação {i}",
               "credor": "GRANDE", "credor_nome": "Empresa Grande", "NomeIdentificacao": "CNPJ",
               "DescricaoElemento": "Material", "CodigoFonteReduzida": "1500",
               "empenhada": 50.0, "liquidada": 0.0, "paga": 0.0, "lancamentos": 1} for i in range(4)]
    # Em cada ação há 10 credores maiores que ele: pelo corte por ação, ele ficaria de fora.
    outros = [{**g, "credor": f"{j:014d}", "credor_nome": f"Outra {j}", "empenhada": 100.0 + j}
              for g in grande for j in range(10)]
    d = tcees.credor_acao(pd.DataFrame(grande + outros))
    assert set(d.loc[d["credor"] == "GRANDE", "CodigoAcao"]) == {"2000", "2001", "2002", "2003"}
    assert d["empenhada"].sum() == pytest.approx(pd.DataFrame(grande + outros)["empenhada"].sum())


def test_credor_acao_agrega_pessoa_fisica_como_nos_credores():
    bruto = pd.DataFrame([{"cod_ibge": 3205309, "ano": 2024, "CodigoAcao": "2001", "NomeAcao": "Manutenção",
                           "credor": c, "credor_nome": n, "NomeIdentificacao": ident, "DescricaoElemento": "Diárias",
                           "CodigoFonteReduzida": "1500", "empenhada": 10.0, "liquidada": 0.0, "paga": 0.0,
                           "lancamentos": 1}
                          for c, n, ident in (("999", "Maria", "CPF"), ("998", "João", "CPF"), ("111", "Empresa A", "CNPJ"))])
    d = tcees.credor_acao(bruto)
    assert set(d["credor"]) == {"(pessoa física)", "111"}
    assert d.set_index("credor").loc["(pessoa física)", "empenhada"] == pytest.approx(20.0)
