-- Camadas do banco. O banco em si (educacao_dw) é criado fora daqui:
--   createdb -E UTF8 educacao_dw

-- Catálogo de metadados materializado, gerado a partir de educacao/metadata/catalog.
CREATE SCHEMA IF NOT EXISTS meta;

-- Fiel ao arquivo: uma tabela por ano x tabela, colunas na ordem do CSV,
-- tipos do catálogo, sem chave nem NOT NULL. Restrição aqui só rejeitaria
-- dado real do INEP; consistência é assunto da camada stg.
CREATE SCHEMA IF NOT EXISTS raw;

-- Harmonização entre anos: nomes, tipos e tabelas no desenho de 2025.
CREATE SCHEMA IF NOT EXISTS stg;

-- Modelo dimensional para análise.
CREATE SCHEMA IF NOT EXISTS dw;

-- Controle de execução do pipeline.
CREATE SCHEMA IF NOT EXISTS etl;

COMMENT ON SCHEMA meta IS 'Catálogo de metadados do Censo Escolar (2007-2025)';
COMMENT ON SCHEMA raw  IS 'Microdados fiéis ao arquivo publicado pelo INEP, filtrados para o ES';
COMMENT ON SCHEMA stg  IS 'Camada harmonizada entre anos';
COMMENT ON SCHEMA dw   IS 'Modelo dimensional';
COMMENT ON SCHEMA etl  IS 'Controle de carga';
