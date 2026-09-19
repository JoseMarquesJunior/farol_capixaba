-- Camada `stg` das avaliações: cada fonte com chave que casa com o Censo.
--
-- O grão alvo é escola x ano, o mesmo de dw.fato_escola_ano, exceto no SAEB,
-- cujo identificador de escola é mascarado e irreversível — ali o grão possível
-- é município x ano (ver educacao/avaliacoes/saeb.py).
--
-- As avaliações são bienais e o Censo é anual: estas tabelas só têm linha nos
-- anos em que houve edição. Nada é propagado para os anos intermediários.

-- ------------------------------------------------------------------- IDEB

CREATE TABLE IF NOT EXISTS stg.ideb_escola (
    co_entidade           INTEGER  NOT NULL,
    ano                   SMALLINT NOT NULL,
    etapa                 VARCHAR(16) NOT NULL,
    co_municipio          INTEGER,
    no_entidade           VARCHAR(150),
    rede                  VARCHAR(20),
    aprovacao             NUMERIC,
    indicador_rendimento  NUMERIC,
    nota_matematica       NUMERIC,
    nota_portugues        NUMERIC,
    nota_media            NUMERIC,
    ideb_observado        NUMERIC,
    ideb_projecao         NUMERIC,
    PRIMARY KEY (co_entidade, ano, etapa)
);

COMMENT ON TABLE stg.ideb_escola IS
    'IDEB por escola, etapa e edição. Uma linha por (escola, ano, etapa)';
COMMENT ON COLUMN stg.ideb_escola.aprovacao IS
    'Taxa de aprovação do total da etapa; as séries ficam em stg.ideb_aprovacao_serie';
COMMENT ON COLUMN stg.ideb_escola.indicador_rendimento IS
    'Indicador de rendimento (P), o fator de fluxo do IDEB';
COMMENT ON COLUMN stg.ideb_escola.nota_media IS
    'Nota média padronizada (N); é ela que multiplica P para dar o IDEB';
COMMENT ON COLUMN stg.ideb_escola.ideb_projecao IS
    'Meta do 1º ciclo do IDEB; só publicada para as edições de 2007 a 2021';

CREATE TABLE IF NOT EXISTS stg.ideb_aprovacao_serie (
    co_entidade INTEGER  NOT NULL,
    ano         SMALLINT NOT NULL,
    etapa       VARCHAR(16) NOT NULL,
    serie       SMALLINT NOT NULL,
    aprovacao   NUMERIC  NOT NULL,
    PRIMARY KEY (co_entidade, ano, etapa, serie)
);

COMMENT ON TABLE stg.ideb_aprovacao_serie IS
    'Taxa de aprovação por série. A série vem do rótulo humano da planilha: o '
    'sufixo do nome de máquina é posição ordinal e nos anos iniciais está '
    'deslocado (VL_APROVACAO_2005_1 é o 2º ano)';

CREATE TABLE IF NOT EXISTS stg.ideb_municipio (
    co_municipio          INTEGER  NOT NULL,
    ano                   SMALLINT NOT NULL,
    etapa                 VARCHAR(16) NOT NULL,
    no_municipio          VARCHAR(120),
    rede                  VARCHAR(20) NOT NULL,
    aprovacao             NUMERIC,
    indicador_rendimento  NUMERIC,
    nota_matematica       NUMERIC,
    nota_portugues        NUMERIC,
    nota_media            NUMERIC,
    ideb_observado        NUMERIC,
    ideb_projecao         NUMERIC,
    PRIMARY KEY (co_municipio, ano, etapa, rede)
);

COMMENT ON COLUMN stg.ideb_municipio.rede IS
    'O IDEB municipal é publicado por rede (Estadual, Municipal, Pública...), '
    'por isso a rede faz parte da chave';

-- ------------------------------------------------------------------- ENEM

CREATE TABLE IF NOT EXISTS stg.enem_escola (
    co_entidade        INTEGER  NOT NULL,
    ano                SMALLINT NOT NULL,
    co_municipio       INTEGER,
    no_entidade        VARCHAR(150),
    tp_dependencia     SMALLINT,
    tp_localizacao     SMALLINT,
    matriculas         INTEGER,
    participantes      INTEGER,
    taxa_participacao  NUMERIC,
    media_cn           NUMERIC,
    media_ch           NUMERIC,
    media_lp           NUMERIC,
    media_mt           NUMERIC,
    media_red          NUMERIC,
    media_obj          NUMERIC,
    media_total        NUMERIC,
    inse               VARCHAR(20),
    pc_formacao_docente NUMERIC,
    taxa_permanencia   NUMERIC,
    taxa_aprovacao     NUMERIC,
    taxa_reprovacao    NUMERIC,
    taxa_abandono      NUMERIC,
    porte_escola       VARCHAR(40),
    PRIMARY KEY (co_entidade, ano)
);

COMMENT ON TABLE stg.enem_escola IS
    'ENEM por Escola, 2005 a 2015. O INEP encerrou a divulgação em 2015 e os '
    'microdados do ENEM que vieram depois não trazem código de escola';

-- ------------------------------------------------------------------- SAEB

CREATE TABLE IF NOT EXISTS stg.saeb_mascara_municipio (
    ano                 SMALLINT NOT NULL,
    id_municipio_saeb   INTEGER  NOT NULL,
    co_municipio        INTEGER  NOT NULL,
    PRIMARY KEY (ano, id_municipio_saeb),
    UNIQUE (ano, co_municipio)
);

COMMENT ON TABLE stg.saeb_mascara_municipio IS
    'Tradução da máscara municipal do SAEB para o código IBGE. A máscara é uma '
    'renumeração sequencial que preserva a ordem, então o alinhamento ordenado '
    'é determinístico quando a contagem bate — o que no ES acontece nas cinco '
    'edições (78 = 78). Ver educacao/avaliacoes/saeb.py';

CREATE TABLE IF NOT EXISTS stg.saeb_municipio (
    co_municipio          INTEGER  NOT NULL,
    ano                   SMALLINT NOT NULL,
    etapa                 VARCHAR(8) NOT NULL,
    escolas               INTEGER  NOT NULL,
    matriculados_censo    INTEGER,
    presentes             INTEGER,
    taxa_participacao     NUMERIC,
    media_lp              NUMERIC,
    media_mt              NUMERIC,
    PRIMARY KEY (co_municipio, ano, etapa)
);

COMMENT ON TABLE stg.saeb_municipio IS
    'SAEB agregado por município. As médias são ponderadas pelo número de '
    'presentes da escola, não médias simples de escola';
COMMENT ON COLUMN stg.saeb_municipio.matriculados_censo IS
    'Matriculados segundo o Censo, como o próprio SAEB publica — serve de '
    'conferência independente contra dw.fato_matricula';

CREATE TABLE IF NOT EXISTS stg.saeb_municipio_nivel (
    co_municipio  INTEGER  NOT NULL,
    ano           SMALLINT NOT NULL,
    etapa         VARCHAR(8) NOT NULL,
    disciplina    VARCHAR(12) NOT NULL,
    nivel         SMALLINT NOT NULL,
    percentual    NUMERIC  NOT NULL,
    PRIMARY KEY (co_municipio, ano, etapa, disciplina, nivel)
);

COMMENT ON TABLE stg.saeb_municipio_nivel IS
    'Distribuição percentual por nível da escala de proficiência, ponderada '
    'pelos presentes de cada escola';

-- ----------------------------------------------------------------- PAEBES

CREATE TABLE IF NOT EXISTS stg.paebes_aluno (
    cd_aluno       BIGINT   NOT NULL,
    ano            SMALLINT NOT NULL,
    disciplina     VARCHAR(30) NOT NULL,
    co_entidade    INTEGER  NOT NULL,
    co_municipio   INTEGER,
    etapa          VARCHAR(60),
    rede           VARCHAR(20),
    turno          VARCHAR(20),
    regional       VARCHAR(60),
    presente       BOOLEAN,
    avaliado       BOOLEAN,
    proficiencia   NUMERIC,
    erro_padrao    NUMERIC,
    padrao_desempenho VARCHAR(30),
    acertos        NUMERIC,
    total_itens    NUMERIC,
    ise            NUMERIC,
    nse            VARCHAR(30),
    PRIMARY KEY (cd_aluno, ano, disciplina)
);

COMMENT ON TABLE stg.paebes_aluno IS
    'PAEBES no grão aluno x disciplina. cd_aluno é o identificador anonimizado '
    'da SEDU; co_entidade é o código INEP real e casa com dw.dim_escola';
COMMENT ON COLUMN stg.paebes_aluno.proficiencia IS
    'Escala 0-500. Vem como texto em raw porque o arquivo usa vírgula decimal';

CREATE INDEX IF NOT EXISTS idx_paebes_aluno_escola
    ON stg.paebes_aluno (co_entidade, ano, disciplina);
CREATE INDEX IF NOT EXISTS idx_ideb_escola_ano
    ON stg.ideb_escola (ano, etapa);
CREATE INDEX IF NOT EXISTS idx_saeb_municipio_ano
    ON stg.saeb_municipio (ano, etapa);
