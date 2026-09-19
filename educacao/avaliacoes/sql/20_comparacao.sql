-- Visões que juntam resultado de avaliação com o Censo, no grão em que cada
-- fonte permite juntar.
--
-- São visões, não tabelas: não materializam nada e não comprometem nenhuma
-- decisão de modelagem dimensional — essas estão listadas em
-- educacao/avaliacoes/pendencias.md e ainda não foram tomadas.
--
-- Duas advertências valem para todas:
--
--   * a avaliação é bienal e o Censo é anual. A junção é por ano exato, então
--     só há linha nos anos de edição. Nada é propagado para o ano seguinte;
--   * a etapa da avaliação e a etapa do Censo não são a mesma granularidade.
--     A matrícula que aparece ao lado é a da etapa correspondente mais próxima,
--     para dar ordem de grandeza — não é o denominador do indicador.

-- IDEB por escola, com o que o Censo diz da mesma escola no mesmo ano.
CREATE OR REPLACE VIEW stg.v_ideb_censo AS
SELECT i.co_entidade,
       i.ano,
       i.etapa,
       i.rede,
       i.ideb_observado,
       i.ideb_projecao,
       i.ideb_observado - i.ideb_projecao        AS distancia_da_meta,
       i.nota_media,
       i.nota_matematica,
       i.nota_portugues,
       i.indicador_rendimento,
       i.aprovacao,
       e.no_entidade,
       e.co_municipio,
       e.tp_dependencia,
       e.tp_localizacao,
       CASE i.etapa
           WHEN 'anos_iniciais' THEN m.qt_mat_fund_ai
           WHEN 'anos_finais'   THEN m.qt_mat_fund_af
           WHEN 'ensino_medio'  THEN m.qt_mat_med
       END                                        AS matricula_na_etapa,
       m.qt_mat_bas                               AS matricula_total,
       e.in_internet,
       e.in_biblioteca,
       e.in_laboratorio_informatica,
       e.in_quadra_esportes
FROM stg.ideb_escola i
LEFT JOIN stg.escola e
       ON e.co_entidade = i.co_entidade AND e.nu_ano_censo = i.ano
LEFT JOIN stg.matricula m
       ON m.co_entidade = i.co_entidade AND m.nu_ano_censo = i.ano;

COMMENT ON VIEW stg.v_ideb_censo IS
    'IDEB por escola e etapa ao lado dos atributos do Censo do mesmo ano. '
    'LEFT JOIN de propósito: o IDEB comeca em 2005 e o Censo carregado comeca '
    'em 2007, então as edições de 2005 ficam sem contraparte';

-- ENEM por Escola, com o Censo do mesmo ano.
CREATE OR REPLACE VIEW stg.v_enem_censo AS
SELECT n.co_entidade,
       n.ano,
       n.media_total,
       n.media_mt,
       n.media_lp,
       n.media_red,
       n.participantes,
       n.matriculas                               AS matriculas_enem,
       n.taxa_participacao,
       n.inse,
       n.taxa_aprovacao,
       n.taxa_abandono,
       e.no_entidade,
       e.co_municipio,
       e.tp_dependencia,
       e.tp_localizacao,
       m.qt_mat_med                               AS matricula_medio_censo,
       m.qt_mat_bas                               AS matricula_total
FROM stg.enem_escola n
LEFT JOIN stg.escola e
       ON e.co_entidade = n.co_entidade AND e.nu_ano_censo = n.ano
LEFT JOIN stg.matricula m
       ON m.co_entidade = n.co_entidade AND m.nu_ano_censo = n.ano;

-- SAEB por município, com a matrícula do Censo agregada no mesmo grão.
-- `matriculados_censo` é o que o próprio SAEB publica e cobre só as escolas
-- avaliadas; `matricula_censo_completa` é o total do município. A razão entre
-- os dois é a cobertura da avaliação.
CREATE OR REPLACE VIEW stg.v_saeb_censo AS
SELECT s.co_municipio,
       s.ano,
       s.etapa,
       s.escolas,
       s.presentes,
       s.taxa_participacao,
       s.media_lp,
       s.media_mt,
       s.matriculados_censo,
       c.matricula_censo_completa,
       round(100.0 * s.matriculados_censo / nullif(c.matricula_censo_completa, 0), 1)
                                                  AS cobertura_pct
FROM stg.saeb_municipio s
LEFT JOIN (
    SELECT e.co_municipio,
           m.nu_ano_censo AS ano,
           sum(m.qt_mat_fund_ai) AS ai,
           sum(m.qt_mat_fund_af) AS af,
           sum(m.qt_mat_med)     AS em,
           sum(m.qt_mat_bas)     AS bas
    FROM stg.matricula m
    JOIN stg.escola e
      ON e.co_entidade = m.co_entidade AND e.nu_ano_censo = m.nu_ano_censo
    GROUP BY 1, 2
) t ON t.co_municipio = s.co_municipio AND t.ano = s.ano
LEFT JOIN LATERAL (
    SELECT CASE
               WHEN s.etapa = '5EF' THEN t.ai
               WHEN s.etapa = '9EF' THEN t.af
               ELSE t.em
           END AS matricula_censo_completa
) c ON true;

-- PAEBES agregado por escola, etapa e disciplina.
-- A média é sobre quem foi de fato avaliado. A regra de agregação ainda não foi
-- conferida contra o que a SEDU publica — ver pendencias.md, item 5.
CREATE OR REPLACE VIEW stg.v_paebes_escola AS
SELECT p.co_entidade,
       p.ano,
       p.etapa,
       p.disciplina,
       count(*)                                        AS previstos,
       count(*) FILTER (WHERE p.presente)              AS presentes,
       count(*) FILTER (WHERE p.avaliado)              AS avaliados,
       round(avg(p.proficiencia) FILTER (WHERE p.avaliado), 1) AS proficiencia_media,
       round(avg(p.ise) FILTER (WHERE p.avaliado), 3)  AS ise_medio,
       max(p.rede)                                     AS rede,
       max(p.co_municipio)                             AS co_municipio
FROM stg.paebes_aluno p
GROUP BY p.co_entidade, p.ano, p.etapa, p.disciplina;

COMMENT ON VIEW stg.v_paebes_escola IS
    'PAEBES agregado de aluno para escola. Atenção: as disciplinas se sobrepõem '
    '(Ciências da Natureza convive com Química, Física e Biologia), então somar '
    'avaliados entre disciplinas conta o mesmo aluno mais de uma vez';
