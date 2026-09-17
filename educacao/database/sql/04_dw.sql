-- Modelo dimensional. Grão real: escola x ano, que é o grão do Censo.
--
-- A camada stg mantém os 19 anos harmonizados e largos; aqui o dado vira
-- estrela, com as categorias do INEP viradas dimensão (a partir de meta.dominio)
-- e as matrículas por etapa em formato longo.

-- ---------------------------------------------------------------- dimensões

CREATE TABLE IF NOT EXISTS dw.dim_tempo (
    ano     SMALLINT PRIMARY KEY,
    decada  SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS dw.dim_municipio (
    co_municipio          INTEGER PRIMARY KEY,
    no_municipio          VARCHAR(100) NOT NULL,
    co_mesorregiao        INTEGER,
    no_mesorregiao        VARCHAR(100),
    co_microrregiao       INTEGER,
    no_microrregiao       VARCHAR(100),
    co_regiao_geog_imed   INTEGER,
    no_regiao_geog_imed   VARCHAR(100)
);

COMMENT ON COLUMN dw.dim_municipio.co_regiao_geog_imed IS
    'Região geográfica imediata do IBGE; só publicada a partir de 2024';

-- Identidade da escola. Os atributos que mudam de ano para ano ficam em
-- dw.fato_escola_ano; aqui fica o que identifica e o estado mais recente.
CREATE TABLE IF NOT EXISTS dw.dim_escola (
    co_entidade      INTEGER PRIMARY KEY,
    no_entidade      VARCHAR(100) NOT NULL,
    co_municipio     INTEGER REFERENCES dw.dim_municipio (co_municipio),
    primeiro_ano     SMALLINT NOT NULL,
    ultimo_ano       SMALLINT NOT NULL,
    anos_no_censo    SMALLINT NOT NULL,
    latitude         NUMERIC,
    longitude        NUMERIC
);

COMMENT ON TABLE dw.dim_escola IS
    'Uma linha por escola; nome, município e geo são os do ano mais recente';
COMMENT ON COLUMN dw.dim_escola.anos_no_censo IS
    'Em quantos anos a escola aparece — menor que ultimo_ano-primeiro_ano+1 se houve lacuna';
COMMENT ON COLUMN dw.dim_escola.latitude IS
    'Georreferenciamento só é publicado a partir de 2025';

-- Categorias do INEP, carregadas de meta.dominio.
CREATE TABLE IF NOT EXISTS dw.dim_dependencia (
    tp_dependencia SMALLINT PRIMARY KEY,
    dependencia    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dw.dim_localizacao (
    tp_localizacao SMALLINT PRIMARY KEY,
    localizacao    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dw.dim_situacao (
    tp_situacao_funcionamento SMALLINT PRIMARY KEY,
    situacao                  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dw.dim_categoria_privada (
    tp_categoria_escola_privada SMALLINT PRIMARY KEY,
    categoria_privada           TEXT NOT NULL
);

-- Etapas de ensino. `exclusiva` separa o que particiona do que se sobrepõe:
-- somar linhas exclusivas dá a matrícula regular mais EJA sem dupla contagem;
-- Profissional e Especial são recortes transversais (quem está no médio
-- integrado conta em Médio E em Profissional) e nunca devem ser somados com
-- as etapas.
CREATE TABLE IF NOT EXISTS dw.dim_etapa (
    sk_etapa       SMALLINT PRIMARY KEY,
    etapa          TEXT NOT NULL UNIQUE,
    nivel          TEXT NOT NULL,
    coluna_origem  TEXT NOT NULL,
    ordem          SMALLINT NOT NULL,
    exclusiva      BOOLEAN NOT NULL
);

COMMENT ON COLUMN dw.dim_etapa.exclusiva IS
    'Verdadeiro nas etapas que particionam a matrícula; falso nos recortes que se sobrepõem';

-- ------------------------------------------------------------------- fatos

-- Grão: escola x ano. As medidas de total são as que o INEP publica, sem
-- recalcular — qt_mat_bas é o total do INEP, não a soma das etapas.
CREATE TABLE IF NOT EXISTS dw.fato_escola_ano (
    co_entidade                 INTEGER  NOT NULL REFERENCES dw.dim_escola (co_entidade),
    ano                         SMALLINT NOT NULL REFERENCES dw.dim_tempo (ano),
    co_municipio                INTEGER  REFERENCES dw.dim_municipio (co_municipio),
    tp_dependencia              SMALLINT REFERENCES dw.dim_dependencia (tp_dependencia),
    tp_localizacao              SMALLINT REFERENCES dw.dim_localizacao (tp_localizacao),
    tp_situacao_funcionamento   SMALLINT REFERENCES dw.dim_situacao (tp_situacao_funcionamento),
    tp_categoria_escola_privada SMALLINT REFERENCES dw.dim_categoria_privada (tp_categoria_escola_privada),
    no_entidade                 VARCHAR(100),
    no_bairro                   VARCHAR(100),
    qt_mat_bas                  INTEGER,
    qt_mat_esp                  INTEGER,
    qt_doc_bas                  INTEGER,
    qt_tur_bas                  INTEGER,
    in_agua_potavel             SMALLINT,
    in_energia_rede_publica     SMALLINT,
    in_esgoto_rede_publica      SMALLINT,
    in_internet                 SMALLINT,
    in_biblioteca               SMALLINT,
    in_laboratorio_informatica  SMALLINT,
    in_quadra_esportes          SMALLINT,
    in_acessibilidade_rampas    SMALLINT,
    PRIMARY KEY (co_entidade, ano)
);

COMMENT ON COLUMN dw.fato_escola_ano.qt_mat_bas IS
    'Total de matrículas na educação básica, como o INEP publica; não é a soma de dw.fato_matricula';
COMMENT ON COLUMN dw.fato_escola_ano.qt_mat_esp IS
    'Educação especial é recorte transversal: estes alunos também contam na sua etapa';

-- Grão: escola x ano x etapa.
CREATE TABLE IF NOT EXISTS dw.fato_matricula (
    co_entidade  INTEGER  NOT NULL,
    ano          SMALLINT NOT NULL REFERENCES dw.dim_tempo (ano),
    sk_etapa     SMALLINT NOT NULL REFERENCES dw.dim_etapa (sk_etapa),
    qt_matricula INTEGER  NOT NULL,
    PRIMARY KEY (co_entidade, ano, sk_etapa),
    FOREIGN KEY (co_entidade, ano)
        REFERENCES dw.fato_escola_ano (co_entidade, ano) ON DELETE CASCADE
);

COMMENT ON TABLE dw.fato_matricula IS
    'Matrículas por etapa. Some apenas sobre dim_etapa.exclusiva para evitar dupla contagem';

CREATE INDEX IF NOT EXISTS idx_fato_matricula_etapa ON dw.fato_matricula (sk_etapa, ano);
CREATE INDEX IF NOT EXISTS idx_fato_escola_ano_mun  ON dw.fato_escola_ano (co_municipio, ano);
