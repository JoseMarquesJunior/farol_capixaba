-- Controle de carga. Toda execução do COPY registra uma linha aqui, de modo
-- que a carga seja idempotente (não recarrega o que já entrou) e auditável
-- (o que entrou, de qual arquivo, com qual filtro e quantas linhas).

CREATE TABLE IF NOT EXISTS etl.carga (
    id               BIGSERIAL   PRIMARY KEY,
    ano              SMALLINT,
    tabela           TEXT        NOT NULL,
    tabela_raw       TEXT        NOT NULL,
    arquivo          TEXT        NOT NULL,
    sha256           TEXT        NOT NULL,
    filtro           TEXT,
    linhas_lidas     BIGINT,
    linhas_gravadas  BIGINT,
    inicio           TIMESTAMPTZ NOT NULL DEFAULT now(),
    fim              TIMESTAMPTZ,
    status           TEXT        NOT NULL DEFAULT 'em_andamento',
    erro             TEXT,
    CONSTRAINT status_valido
        CHECK (status IN ('em_andamento', 'concluida', 'falhou'))
);

-- `ano` nasceu NOT NULL, quando só o Censo carregava aqui e todo arquivo era
-- de um ano só. As avaliações quebraram isso: uma planilha do IDEB traz onze
-- edições de uma vez, e não há ano único a registrar. Idempotente.
ALTER TABLE etl.carga ALTER COLUMN ano DROP NOT NULL;

COMMENT ON COLUMN etl.carga.ano IS
    'Ano do arquivo, quando ele tem um só. Nulo nas cargas que cobrem várias edições, como o IDEB';
COMMENT ON COLUMN etl.carga.sha256 IS
    'Hash do arquivo de origem: identifica a carga já feita e detecta republicação do INEP';
COMMENT ON COLUMN etl.carga.filtro IS
    'Predicado aplicado durante o streaming, por exemplo CO_UF=32';
COMMENT ON COLUMN etl.carga.linhas_lidas IS
    'Linhas do arquivo percorridas; linhas_gravadas é o que sobrou após o filtro';

CREATE INDEX IF NOT EXISTS idx_carga_sha256 ON etl.carga (sha256);
CREATE INDEX IF NOT EXISTS idx_carga_alvo   ON etl.carga (ano, tabela);

-- Última carga concluída de cada tabela.
CREATE OR REPLACE VIEW etl.ultima_carga AS
SELECT DISTINCT ON (ano, tabela)
       ano,
       tabela,
       tabela_raw,
       arquivo,
       sha256,
       filtro,
       linhas_lidas,
       linhas_gravadas,
       inicio,
       fim,
       fim - inicio AS duracao
FROM etl.carga
WHERE status = 'concluida'
ORDER BY ano, tabela, fim DESC;
