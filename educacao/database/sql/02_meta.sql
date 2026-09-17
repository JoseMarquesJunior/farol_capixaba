-- Catálogo de metadados. Espelha educacao/metadata/catalog/*.json para que o
-- layout de cada ano possa ser consultado em SQL, junto dos próprios dados.

CREATE TABLE IF NOT EXISTS meta.tabela (
    ano              SMALLINT NOT NULL,
    tabela           TEXT     NOT NULL,
    tabela_raw       TEXT     NOT NULL,
    arquivo          TEXT     NOT NULL,
    aba              TEXT     NOT NULL,
    delimitador      TEXT     NOT NULL,
    encoding         TEXT     NOT NULL,
    total_variaveis  SMALLINT NOT NULL,
    PRIMARY KEY (ano, tabela)
);

CREATE TABLE IF NOT EXISTS meta.variavel (
    ano            SMALLINT NOT NULL,
    tabela         TEXT     NOT NULL,
    nome           TEXT     NOT NULL,
    coluna         TEXT     NOT NULL,
    ordem          SMALLINT NOT NULL,
    descricao      TEXT,
    tipo_original  TEXT,
    tamanho        SMALLINT,
    tipo_postgres  TEXT     NOT NULL,
    ajuste_tipo    TEXT,
    nota           TEXT,
    PRIMARY KEY (ano, tabela, nome),
    FOREIGN KEY (ano, tabela)
        REFERENCES meta.tabela (ano, tabela) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_meta_variavel_nome ON meta.variavel (nome);

-- Domínio de valores, extraído da coluna 'Categoria' do dicionário.
-- codigo é NULL nas ressalvas ("- Não aplicável para escolas públicas").
CREATE TABLE IF NOT EXISTS meta.dominio (
    ano       SMALLINT NOT NULL,
    tabela    TEXT     NOT NULL,
    variavel  TEXT     NOT NULL,
    ordem     SMALLINT NOT NULL,
    codigo    TEXT,
    rotulo    TEXT     NOT NULL,
    PRIMARY KEY (ano, tabela, variavel, ordem),
    FOREIGN KEY (ano, tabela, variavel)
        REFERENCES meta.variavel (ano, tabela, nome) ON DELETE CASCADE
);

-- Visão transversal aos 19 anos.
CREATE TABLE IF NOT EXISTS meta.variavel_canonica (
    nome               TEXT     PRIMARY KEY,
    coluna             TEXT     NOT NULL,
    descricao          TEXT,
    tabela_referencia  TEXT,
    descontinuada      BOOLEAN  NOT NULL,
    primeiro_ano       SMALLINT NOT NULL,
    ultimo_ano         SMALLINT NOT NULL,
    tipo_postgres      TEXT     NOT NULL,
    tipo_varia         BOOLEAN  NOT NULL
);

COMMENT ON COLUMN meta.variavel_canonica.tabela_referencia IS
    'Tabela no desenho de 2025; NULL quando a variável foi descontinuada';
COMMENT ON COLUMN meta.variavel_canonica.tipo_varia IS
    'Verdadeiro quando o tipo PostgreSQL muda entre anos e a harmonização exige cast';

-- Anos em que a variável aparece de fato no arquivo publicado.
CREATE TABLE IF NOT EXISTS meta.presenca (
    nome  TEXT     NOT NULL REFERENCES meta.variavel_canonica (nome) ON DELETE CASCADE,
    ano   SMALLINT NOT NULL,
    PRIMARY KEY (nome, ano)
);
