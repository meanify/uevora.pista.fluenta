-- =============================================================================
-- Pista Digital (Universidade de Évora) — Tabelas INE: DDL e dicionário de dados
-- =============================================================================
--
-- Um único ficheiro com todas as tabelas criadas pelos fluxos INE, em sintaxe
-- PostgreSQL. Cada tabela é descrita por:
--   * um bloco de cabeçalho: indicador de origem, periodicidade, granularidade,
--     valor de negócio e notas de utilização;
--   * a instrução CREATE TABLE, idêntica a CREATE_TABLE_SQL em
--     flows-code/pistadigital/flows/ine_<código>_flow.py (fonte de verdade);
--   * instruções COMMENT ON TABLE / COLUMN, para que as mesmas descrições
--     fiquem disponíveis no catálogo da base de dados (psql \d+, Power BI,
--     DBeaver, ...).
--
-- O ficheiro é idempotente: CREATE TABLE IF NOT EXISTS nunca altera uma tabela
-- existente e COMMENT ON apenas substitui descrições. Executá-lo cria as
-- tabelas em falta e (re)escreve a documentação; nunca altera dados.
-- Nota: os comentários substituem os da versão inglesa
-- (docs/ine_data_dictionary.sql); fica na base de dados a última executada.
--
-- As tabelas residem no esquema por omissão da ligação (`public` na
-- configuração habitual); o Power BI lê-as do esquema `public` através do DSN
-- "Pista Digital".
--
-- -----------------------------------------------------------------------------
-- Convenções comuns (aplicam-se a todas as tabelas abaixo)
-- -----------------------------------------------------------------------------
-- Origem       Instituto Nacional de Estatística (INE), API JSON pública
--              (www.ine.pt); uma tabela por código de indicador (`varcd`).
-- Nomenclatura ine_<código do indicador com 7 dígitos>_ds.
-- Carregamento Cada execução processa exatamente um período. Numa única
--              transação apaga o período (anual: ano = A; mensal: ano = A AND
--              mes = 'MM') e insere as linhas acabadas de obter. Os restantes
--              períodos não são tocados. Se o INE não devolver linhas, o
--              período guardado é mantido.
--              Agendamento: DAGs Airflow em flows-code/dags/ (ano corrente e
--              dois anos anteriores); histórico completo via
--              scripts/reload-ine-flows.sh.
-- Etiquetas    Todas as colunas de dimensão guardam a designação em português
--              do INE (não o código), como VARCHAR (sem preenchimento com
--              espaços). São NOT NULL e fazem parte da chave primária.
-- Geografia    NUTS 2013, salvo indicação em contrário (0012093 usa NUTS 2024).
--              As tabelas municipais guardam apenas linhas de município
--              (geocódigo INE com 7 caracteres): os agregados Portugal /
--              NUTS I / II / III são excluídos, pelo que as colunas
--              geográficas nunca contêm 'Total' nessas tabelas. As tabelas
--              regionais (só NUTS I/II) guardam apenas linhas NUTS II.
--              `distrito` é derivado do código do município (dígitos DDCC) e
--              não é uma dimensão do INE.
-- Alojamento   tipo_alojamento / subtipo_alojamento / classificacao são os 3
--              níveis da hierarquia de alojamento do INE (prefixos de código
--              com 2, 4 e 6 caracteres). Mantêm-se apenas o total do INE
--              ('Total' nas três colunas) e as categorias mais detalhadas; os
--              subtotais intermédios são excluídos. Quando uma categoria não
--              tem nível inferior, as colunas seguintes repetem a sua
--              designação.
--              Normalização aplicada pelos fluxos:
--                - tipo 'Alojamento local' -> subtipo e classificacao =
--                  'Alojamento Local';
--                - tipo que contém 'rural' -> subtipo e classificacao =
--                  'Turismo no Espaço Rural e de Habitação';
--                - tipo que contém 'habitação' (sem 'rural') -> apenas
--                  classificacao = 'Turismo no Espaço Rural e de Habitação'.
--              IMPORTANTE: o INE oculta muitos valores municipais por
--              segredo estatístico, pelo que as linhas de detalhe NÃO somam o
--              total. Use tipo_alojamento = 'Total' para totais e exclua-o
--              para desagregações. Nunca some linhas de detalhe para obter um
--              total.
-- Métricas     Guardadas como float4/REAL. NULL significa que o INE não
--              publicou valor (confidencial, não disponível ou não aplicável:
--              '', '..', 's.r.', 'x'); zero é um zero real. Os rácios
--              (estada_media, rendimento_medio_por_quarto) são médias
--              publicadas pelo INE e não devem ser somados; para agregados use
--              medidas ponderadas.
-- Auditoria    create_date e update_date recebem ambos a data da execução.
--              Como o período é substituído por inteiro em cada recarga,
--              create_date é a data do último carregamento desse período e não
--              da primeira inserção.
-- Período      ano = ano de referência. mes (só tabelas mensais) = mês com
--              zero à esquerda, '01'..'12', guardado como CHAR(2); filtre-o
--              sempre como texto (mes = '08') em conjunto com ano.
-- =============================================================================


-- =============================================================================
-- ine_0008350_ds — Superfície das unidades territoriais
-- =============================================================================
-- Indicador      0008350, anual.
-- Granularidade  Uma linha por município e ano.
-- Valor          Área (km²) de cada município. Denominador dos indicadores de
--                densidade e pressão (p. ex. dormidas ou quartos por km²),
--                usados para comparar a intensidade turística entre
--                territórios de dimensões diferentes.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0008350_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(128) NOT NULL,
    municipio varchar(128) NOT NULL,
    ano int4 NOT NULL,
    superficie_unidades_territoriais float4 NULL,
    create_date date NULL,
    update_date date NULL,
    CONSTRAINT ine_0008350_ds_pkey PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, ano
    )
);

COMMENT ON TABLE ine_0008350_ds IS 'INE 0008350 (anual): área de cada município em km2, geografia NUTS 2013. Denominador dos indicadores de densidade e pressão turística.';
COMMENT ON COLUMN ine_0008350_ds.nuts_i IS 'Região NUTS I (NUTS 2013), p. ex. Continente.';
COMMENT ON COLUMN ine_0008350_ds.nuts_ii IS 'Região NUTS II (NUTS 2013), p. ex. Alentejo.';
COMMENT ON COLUMN ine_0008350_ds.nuts_iii IS 'Sub-região NUTS III (NUTS 2013), p. ex. Alentejo Central.';
COMMENT ON COLUMN ine_0008350_ds.distrito IS 'Distrito (ou ilha das regiões autónomas) derivado do código do município; não é uma dimensão do INE.';
COMMENT ON COLUMN ine_0008350_ds.municipio IS 'Município (concelho).';
COMMENT ON COLUMN ine_0008350_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0008350_ds.superficie_unidades_territoriais IS 'Superfície da unidade territorial em quilómetros quadrados (km2). NULL quando não publicado.';
COMMENT ON COLUMN ine_0008350_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0008350_ds.update_date IS 'Data do (último) carregamento do período.';


-- =============================================================================
-- ine_0009183_ds — Dormidas por local de residência
-- =============================================================================
-- Indicador      0009183, anual.
-- Granularidade  Uma linha por município, país de residência e ano.
-- Valor          Dormidas nos estabelecimentos de alojamento turístico
--                desagregadas pelo país de residência do hóspede. Mostra que
--                mercados emissores geram mais noites em cada município,
--                apoiando a promoção dirigida e a análise de dependência de
--                mercados.
-- Notas          local_residencia inclui o total do INE e Portugal; use a
--                linha de total em vez de somar países.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0009183_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(64) NOT NULL,
    municipio varchar(64) NOT NULL,
    local_residencia varchar(128) NOT NULL,
    ano int4 NOT NULL,
    dormidas float4 NULL,
    create_date date NULL,
    update_date date NULL,
    CONSTRAINT ine_0009183_ds_pkey PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, local_residencia, ano
    )
);

COMMENT ON TABLE ine_0009183_ds IS 'INE 0009183 (anual): dormidas em alojamento turístico por município (NUTS 2013) e país de residência do hóspede. Análise de mercados emissores.';
COMMENT ON COLUMN ine_0009183_ds.nuts_i IS 'Região NUTS I (NUTS 2013).';
COMMENT ON COLUMN ine_0009183_ds.nuts_ii IS 'Região NUTS II (NUTS 2013).';
COMMENT ON COLUMN ine_0009183_ds.nuts_iii IS 'Sub-região NUTS III (NUTS 2013).';
COMMENT ON COLUMN ine_0009183_ds.distrito IS 'Distrito derivado do código do município; não é uma dimensão do INE.';
COMMENT ON COLUMN ine_0009183_ds.municipio IS 'Município (concelho).';
COMMENT ON COLUMN ine_0009183_ds.local_residencia IS 'País (ou grupo de países) de residência do hóspede, com a designação do INE, incluindo o total.';
COMMENT ON COLUMN ine_0009183_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0009183_ds.dormidas IS 'Número de dormidas (noites passadas pelos hóspedes). NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0009183_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0009183_ds.update_date IS 'Data do (último) carregamento do período.';


-- =============================================================================
-- ine_0009808_ds — Dormidas mensais por tipo de alojamento (NUTS I/II, 2013)
-- =============================================================================
-- Indicador      0009808, mensal.
-- Granularidade  Uma linha por região NUTS II, tipo/subtipo de alojamento,
--                ano e mês.
-- Valor          Dormidas mensais ao nível regional. Principal fonte para a
--                análise de sazonalidade (picos, época baixa, variação
--                homóloga) e para comparar a região com outras NUTS II.
-- Notas          Sem colunas de município nem classificacao. Filtre ano E mes.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0009808_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    tipo_alojamento varchar(64) NOT NULL,
    subtipo_alojamento varchar(64) NOT NULL,
    ano INTEGER NOT NULL,
    mes CHAR(2) NOT NULL,
    dormidas REAL,
    create_date DATE,
    update_date DATE,
    PRIMARY KEY (nuts_i, nuts_ii, tipo_alojamento, subtipo_alojamento, ano, mes)
);

COMMENT ON TABLE ine_0009808_ds IS 'INE 0009808 (mensal): dormidas por região NUTS II (NUTS 2013) e tipo/subtipo de alojamento. Sazonalidade regional.';
COMMENT ON COLUMN ine_0009808_ds.nuts_i IS 'Região NUTS I (NUTS 2013).';
COMMENT ON COLUMN ine_0009808_ds.nuts_ii IS 'Região NUTS II (NUTS 2013). Só são guardadas linhas NUTS II.';
COMMENT ON COLUMN ine_0009808_ds.tipo_alojamento IS 'Tipo de alojamento (nível 1); Total para o total do INE.';
COMMENT ON COLUMN ine_0009808_ds.subtipo_alojamento IS 'Subtipo de alojamento (nível 2); repete o tipo quando não há nível inferior. Normalizado para alojamento local e rural.';
COMMENT ON COLUMN ine_0009808_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0009808_ds.mes IS 'Mês de referência, texto com zero à esquerda 01..12.';
COMMENT ON COLUMN ine_0009808_ds.dormidas IS 'Número de dormidas no mês. NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0009808_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0009808_ds.update_date IS 'Data do (último) carregamento do período.';


-- =============================================================================
-- ine_0009812_ds — Hóspedes mensais por tipo de alojamento (NUTS I/II, 2013)
-- =============================================================================
-- Indicador      0009812, mensal.
-- Granularidade  Uma linha por região NUTS II, tipo/subtipo de alojamento,
--                ano e mês.
-- Valor          Hóspedes mensais ao nível regional. Em conjunto com
--                ine_0009808_ds (dormidas) dá a estada média regional por mês
--                e o perfil sazonal da procura.
-- Notas          Mesma estrutura de ine_0012093_ds, mas com designações
--                NUTS 2013.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0009812_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    tipo_alojamento varchar(64) NOT NULL,
    subtipo_alojamento varchar(64) NOT NULL,
    ano INTEGER NOT NULL,
    mes CHAR(2) NOT NULL,
    hospedes REAL,
    create_date DATE,
    update_date DATE,
    PRIMARY KEY (nuts_i, nuts_ii, tipo_alojamento, subtipo_alojamento, ano, mes)
);

COMMENT ON TABLE ine_0009812_ds IS 'INE 0009812 (mensal): hóspedes por região NUTS II (NUTS 2013) e tipo/subtipo de alojamento. Sazonalidade regional da procura.';
COMMENT ON COLUMN ine_0009812_ds.nuts_i IS 'Região NUTS I (NUTS 2013).';
COMMENT ON COLUMN ine_0009812_ds.nuts_ii IS 'Região NUTS II (NUTS 2013). Só são guardadas linhas NUTS II.';
COMMENT ON COLUMN ine_0009812_ds.tipo_alojamento IS 'Tipo de alojamento (nível 1); Total para o total do INE.';
COMMENT ON COLUMN ine_0009812_ds.subtipo_alojamento IS 'Subtipo de alojamento (nível 2); repete o tipo quando não há nível inferior. Normalizado para alojamento local e rural.';
COMMENT ON COLUMN ine_0009812_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0009812_ds.mes IS 'Mês de referência, texto com zero à esquerda 01..12.';
COMMENT ON COLUMN ine_0009812_ds.hospedes IS 'Número de hóspedes (entradas) no mês. NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0009812_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0009812_ds.update_date IS 'Data do (último) carregamento do período.';


-- =============================================================================
-- ine_0009873_ds — Estabelecimentos de alojamento turístico
-- =============================================================================
-- Indicador      0009873, anual.
-- Granularidade  Uma linha por município, tipo / subtipo / classificação de
--                alojamento e ano.
-- Valor          Oferta: número de estabelecimentos de alojamento turístico.
--                Mede a dimensão e a composição da oferta (hotelaria,
--                alojamento local, turismo rural, ...) e a sua evolução.
-- Notas          O nome da métrica mantém a grafia original "establecimento".
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0009873_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(64) NOT NULL,
    municipio varchar(64) NOT NULL,
    tipo_alojamento varchar(64) NOT NULL,
    subtipo_alojamento varchar(64) NOT NULL,
    classificacao varchar(64) NOT NULL,
    ano int4 NOT NULL,
    establecimento_de_alojamento_turistico float4 NULL,
    create_date date NULL,
    update_date date NULL,
    CONSTRAINT ine_0009873_ds_pkey PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, tipo_alojamento,
        subtipo_alojamento, classificacao, ano
    )
);

COMMENT ON TABLE ine_0009873_ds IS 'INE 0009873 (anual): número de estabelecimentos de alojamento turístico por município (NUTS 2013) e tipo/subtipo/classificação de alojamento. Oferta de alojamento.';
COMMENT ON COLUMN ine_0009873_ds.nuts_i IS 'Região NUTS I (NUTS 2013).';
COMMENT ON COLUMN ine_0009873_ds.nuts_ii IS 'Região NUTS II (NUTS 2013).';
COMMENT ON COLUMN ine_0009873_ds.nuts_iii IS 'Sub-região NUTS III (NUTS 2013).';
COMMENT ON COLUMN ine_0009873_ds.distrito IS 'Distrito derivado do código do município; não é uma dimensão do INE.';
COMMENT ON COLUMN ine_0009873_ds.municipio IS 'Município (concelho).';
COMMENT ON COLUMN ine_0009873_ds.tipo_alojamento IS 'Tipo de alojamento (nível 1); Total para o total do INE.';
COMMENT ON COLUMN ine_0009873_ds.subtipo_alojamento IS 'Subtipo de alojamento (nível 2); repete o nível superior quando não há nível inferior. Normalizado para alojamento local e rural.';
COMMENT ON COLUMN ine_0009873_ds.classificacao IS 'Classificação (nível 3), p. ex. categoria em estrelas; repete o nível superior quando não há nível inferior. Normalizada para alojamento local e rural.';
COMMENT ON COLUMN ine_0009873_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0009873_ds.establecimento_de_alojamento_turistico IS 'Número de estabelecimentos de alojamento turístico. NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0009873_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0009873_ds.update_date IS 'Data do (último) carregamento do período.';


-- =============================================================================
-- ine_0009874_ds — Quartos em estabelecimentos de alojamento turístico
-- =============================================================================
-- Indicador      0009874, anual.
-- Granularidade  Uma linha por município, tipo / subtipo / classificação de
--                alojamento e ano.
-- Valor          Oferta: capacidade de alojamento em quartos. Base dos
--                indicadores de capacidade de carga e pressão turística
--                (quartos por km² com ine_0008350_ds, dormidas por quarto com
--                ine_0009877_ds).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0009874_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(64) NOT NULL,
    municipio varchar(64) NOT NULL,
    tipo_alojamento varchar(64) NOT NULL,
    subtipo_alojamento varchar(64) NOT NULL,
    classificacao varchar(64) NOT NULL,
    ano int4 NOT NULL,
    quartos float4 NULL,
    create_date date NULL,
    update_date date NULL,
    CONSTRAINT ine_0009874_ds_pkey PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, tipo_alojamento,
        subtipo_alojamento, classificacao, ano
    )
);

COMMENT ON TABLE ine_0009874_ds IS 'INE 0009874 (anual): número de quartos em alojamento turístico por município (NUTS 2013) e tipo/subtipo/classificação de alojamento. Capacidade de alojamento.';
COMMENT ON COLUMN ine_0009874_ds.nuts_i IS 'Região NUTS I (NUTS 2013).';
COMMENT ON COLUMN ine_0009874_ds.nuts_ii IS 'Região NUTS II (NUTS 2013).';
COMMENT ON COLUMN ine_0009874_ds.nuts_iii IS 'Sub-região NUTS III (NUTS 2013).';
COMMENT ON COLUMN ine_0009874_ds.distrito IS 'Distrito derivado do código do município; não é uma dimensão do INE.';
COMMENT ON COLUMN ine_0009874_ds.municipio IS 'Município (concelho).';
COMMENT ON COLUMN ine_0009874_ds.tipo_alojamento IS 'Tipo de alojamento (nível 1); Total para o total do INE.';
COMMENT ON COLUMN ine_0009874_ds.subtipo_alojamento IS 'Subtipo de alojamento (nível 2); repete o nível superior quando não há nível inferior. Normalizado para alojamento local e rural.';
COMMENT ON COLUMN ine_0009874_ds.classificacao IS 'Classificação (nível 3); repete o nível superior quando não há nível inferior. Normalizada para alojamento local e rural.';
COMMENT ON COLUMN ine_0009874_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0009874_ds.quartos IS 'Número de quartos. NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0009874_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0009874_ds.update_date IS 'Data do (último) carregamento do período.';


-- =============================================================================
-- ine_0009876_ds — Hóspedes por tipo de alojamento
-- =============================================================================
-- Indicador      0009876, anual.
-- Granularidade  Uma linha por município, tipo / subtipo / classificação de
--                alojamento e ano.
-- Valor          Procura: número de hóspedes por município e tipo de
--                alojamento. Mostra que segmentos de alojamento atraem
--                visitantes e, com ine_0009877_ds, a duração da estada.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0009876_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(64) NOT NULL,
    municipio varchar(64) NOT NULL,
    tipo_alojamento varchar(64) NOT NULL,
    subtipo_alojamento varchar(64) NOT NULL,
    classificacao varchar(64) NOT NULL,
    ano int4 NOT NULL,
    hospedes float4 NULL,
    create_date date NULL,
    update_date date NULL,
    CONSTRAINT ine_0009876_ds_pkey PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, tipo_alojamento,
        subtipo_alojamento, classificacao, ano
    )
);

COMMENT ON TABLE ine_0009876_ds IS 'INE 0009876 (anual): hóspedes em alojamento turístico por município (NUTS 2013) e tipo/subtipo/classificação de alojamento. Procura turística.';
COMMENT ON COLUMN ine_0009876_ds.nuts_i IS 'Região NUTS I (NUTS 2013).';
COMMENT ON COLUMN ine_0009876_ds.nuts_ii IS 'Região NUTS II (NUTS 2013).';
COMMENT ON COLUMN ine_0009876_ds.nuts_iii IS 'Sub-região NUTS III (NUTS 2013).';
COMMENT ON COLUMN ine_0009876_ds.distrito IS 'Distrito derivado do código do município; não é uma dimensão do INE.';
COMMENT ON COLUMN ine_0009876_ds.municipio IS 'Município (concelho).';
COMMENT ON COLUMN ine_0009876_ds.tipo_alojamento IS 'Tipo de alojamento (nível 1); Total para o total do INE.';
COMMENT ON COLUMN ine_0009876_ds.subtipo_alojamento IS 'Subtipo de alojamento (nível 2); repete o nível superior quando não há nível inferior. Normalizado para alojamento local e rural.';
COMMENT ON COLUMN ine_0009876_ds.classificacao IS 'Classificação (nível 3); repete o nível superior quando não há nível inferior. Normalizada para alojamento local e rural.';
COMMENT ON COLUMN ine_0009876_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0009876_ds.hospedes IS 'Número de hóspedes (entradas). NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0009876_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0009876_ds.update_date IS 'Data do (último) carregamento do período.';


-- =============================================================================
-- ine_0009877_ds — Dormidas por tipo de alojamento
-- =============================================================================
-- Indicador      0009877, anual.
-- Granularidade  Uma linha por município, tipo / subtipo / classificação de
--                alojamento e ano.
-- Valor          Procura: dormidas, o principal indicador de volume da
--                atividade turística num município. Usado em rankings,
--                crescimento, quota por segmento de alojamento e indicadores
--                de pressão.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0009877_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(64) NOT NULL,
    municipio varchar(64) NOT NULL,
    tipo_alojamento varchar(64) NOT NULL,
    subtipo_alojamento varchar(128) NOT NULL,
    classificacao varchar(64) NOT NULL,
    ano int4 NOT NULL,
    dormidas float4 NULL,
    create_date date NULL,
    update_date date NULL,
    CONSTRAINT ine_0009877_ds_pkey PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, tipo_alojamento,
        subtipo_alojamento, classificacao, ano
    )
);

COMMENT ON TABLE ine_0009877_ds IS 'INE 0009877 (anual): dormidas em alojamento turístico por município (NUTS 2013) e tipo/subtipo/classificação de alojamento. Principal indicador de volume turístico.';
COMMENT ON COLUMN ine_0009877_ds.nuts_i IS 'Região NUTS I (NUTS 2013).';
COMMENT ON COLUMN ine_0009877_ds.nuts_ii IS 'Região NUTS II (NUTS 2013).';
COMMENT ON COLUMN ine_0009877_ds.nuts_iii IS 'Sub-região NUTS III (NUTS 2013).';
COMMENT ON COLUMN ine_0009877_ds.distrito IS 'Distrito derivado do código do município; não é uma dimensão do INE.';
COMMENT ON COLUMN ine_0009877_ds.municipio IS 'Município (concelho).';
COMMENT ON COLUMN ine_0009877_ds.tipo_alojamento IS 'Tipo de alojamento (nível 1); Total para o total do INE.';
COMMENT ON COLUMN ine_0009877_ds.subtipo_alojamento IS 'Subtipo de alojamento (nível 2, até 128 caracteres); repete o nível superior quando não há nível inferior. Normalizado para alojamento local e rural.';
COMMENT ON COLUMN ine_0009877_ds.classificacao IS 'Classificação (nível 3); repete o nível superior quando não há nível inferior. Normalizada para alojamento local e rural.';
COMMENT ON COLUMN ine_0009877_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0009877_ds.dormidas IS 'Número de dormidas (noites passadas pelos hóspedes). NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0009877_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0009877_ds.update_date IS 'Data do (último) carregamento do período.';


-- =============================================================================
-- ine_0009880_ds — Estada média por tipo de alojamento
-- =============================================================================
-- Indicador      0009880, anual.
-- Granularidade  Uma linha por município, tipo / subtipo / classificação de
--                alojamento e ano.
-- Valor          Estada média (noites por hóspede) publicada pelo INE.
--                Indica a profundidade da visita: estadas curtas de passagem
--                vs. estadas de destino, por segmento de alojamento.
-- Notas          Rácio: não somar nem fazer a média entre linhas. Para
--                agregados calcule sum(dormidas) / sum(hospedes) a partir de
--                ine_0009877_ds e ine_0009876_ds.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0009880_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(64) NOT NULL,
    municipio varchar(64) NOT NULL,
    tipo_alojamento varchar(64) NOT NULL,
    subtipo_alojamento varchar(128) NOT NULL,
    classificacao varchar(64) NOT NULL,
    ano int4 NOT NULL,
    estada_media float4 NULL,
    create_date date NULL,
    update_date date NULL,
    CONSTRAINT ine_0009880_ds_pkey PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, tipo_alojamento,
        subtipo_alojamento, classificacao, ano
    )
);

COMMENT ON TABLE ine_0009880_ds IS 'INE 0009880 (anual): estada média (noites por hóspede) em alojamento turístico por município (NUTS 2013) e tipo/subtipo/classificação de alojamento. Rácio - não somar.';
COMMENT ON COLUMN ine_0009880_ds.nuts_i IS 'Região NUTS I (NUTS 2013).';
COMMENT ON COLUMN ine_0009880_ds.nuts_ii IS 'Região NUTS II (NUTS 2013).';
COMMENT ON COLUMN ine_0009880_ds.nuts_iii IS 'Sub-região NUTS III (NUTS 2013).';
COMMENT ON COLUMN ine_0009880_ds.distrito IS 'Distrito derivado do código do município; não é uma dimensão do INE.';
COMMENT ON COLUMN ine_0009880_ds.municipio IS 'Município (concelho).';
COMMENT ON COLUMN ine_0009880_ds.tipo_alojamento IS 'Tipo de alojamento (nível 1); Total para o total do INE.';
COMMENT ON COLUMN ine_0009880_ds.subtipo_alojamento IS 'Subtipo de alojamento (nível 2, até 128 caracteres); repete o nível superior quando não há nível inferior. Normalizado para alojamento local e rural.';
COMMENT ON COLUMN ine_0009880_ds.classificacao IS 'Classificação (nível 3); repete o nível superior quando não há nível inferior. Normalizada para alojamento local e rural.';
COMMENT ON COLUMN ine_0009880_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0009880_ds.estada_media IS 'Estada média em noites (dormidas / hóspedes) publicada pelo INE. Não aditiva. NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0009880_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0009880_ds.update_date IS 'Data do (último) carregamento do período.';


-- =============================================================================
-- ine_0009929_ds — Rendimento médio por quarto (RevPAR)
-- =============================================================================
-- Indicador      0009929, anual.
-- Granularidade  Uma linha por município, tipo / subtipo / classificação de
--                alojamento e ano.
-- Valor          Rendimento médio por quarto disponível (RevPAR, euros)
--                publicado pelo INE. Mede o desempenho económico da oferta de
--                alojamento, combinando ocupação e preço.
-- Notas          Rácio: não somar. Ao contrário das restantes tabelas, as
--                colunas de auditoria são timestamp em vez de date.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0009929_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(64) NOT NULL,
    municipio varchar(64) NOT NULL,
    tipo_alojamento varchar(64) NOT NULL,
    subtipo_alojamento varchar(128) NOT NULL,
    classificacao varchar(64) NOT NULL,
    ano int4 NOT NULL,
    rendimento_medio_por_quarto float4 NULL,
    create_date timestamp NULL,
    update_date timestamp NULL,
    CONSTRAINT ine_0009929_ds_pkey PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, tipo_alojamento,
        subtipo_alojamento, classificacao, ano
    )
);

COMMENT ON TABLE ine_0009929_ds IS 'INE 0009929 (anual): rendimento médio por quarto disponível (RevPAR, EUR) por município (NUTS 2013) e tipo/subtipo/classificação de alojamento. Rácio - não somar.';
COMMENT ON COLUMN ine_0009929_ds.nuts_i IS 'Região NUTS I (NUTS 2013).';
COMMENT ON COLUMN ine_0009929_ds.nuts_ii IS 'Região NUTS II (NUTS 2013).';
COMMENT ON COLUMN ine_0009929_ds.nuts_iii IS 'Sub-região NUTS III (NUTS 2013).';
COMMENT ON COLUMN ine_0009929_ds.distrito IS 'Distrito derivado do código do município; não é uma dimensão do INE.';
COMMENT ON COLUMN ine_0009929_ds.municipio IS 'Município (concelho).';
COMMENT ON COLUMN ine_0009929_ds.tipo_alojamento IS 'Tipo de alojamento (nível 1); Total para o total do INE.';
COMMENT ON COLUMN ine_0009929_ds.subtipo_alojamento IS 'Subtipo de alojamento (nível 2, até 128 caracteres); repete o nível superior quando não há nível inferior. Normalizado para alojamento local e rural.';
COMMENT ON COLUMN ine_0009929_ds.classificacao IS 'Classificação (nível 3); repete o nível superior quando não há nível inferior. Normalizada para alojamento local e rural.';
COMMENT ON COLUMN ine_0009929_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0009929_ds.rendimento_medio_por_quarto IS 'Rendimento médio por quarto disponível (RevPAR) em euros, publicado pelo INE. Não aditivo. NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0009929_ds.create_date IS 'Timestamp (data da execução) do (último) carregamento do período.';
COMMENT ON COLUMN ine_0009929_ds.update_date IS 'Timestamp (data da execução) do (último) carregamento do período.';


-- =============================================================================
-- ine_0009930_ds — Hóspedes por local de residência
-- =============================================================================
-- Indicador      0009930, anual.
-- Granularidade  Uma linha por município, país de residência e ano.
-- Valor          Hóspedes por país de residência: número de visitantes que
--                cada mercado emissor traz ao município (peso do mercado
--                interno vs. externo, principais mercados estrangeiros).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0009930_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(64) NOT NULL,
    municipio varchar(64) NOT NULL,
    local_residencia varchar(64) NOT NULL,
    ano int4 NOT NULL,
    hospedes float4 NULL,
    create_date date NULL,
    update_date date NULL,
    CONSTRAINT ine_0009930_ds_pkey PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, local_residencia, ano
    )
);

COMMENT ON TABLE ine_0009930_ds IS 'INE 0009930 (anual): hóspedes em alojamento turístico por município (NUTS 2013) e país de residência do hóspede. Análise de mercados emissores.';
COMMENT ON COLUMN ine_0009930_ds.nuts_i IS 'Região NUTS I (NUTS 2013).';
COMMENT ON COLUMN ine_0009930_ds.nuts_ii IS 'Região NUTS II (NUTS 2013).';
COMMENT ON COLUMN ine_0009930_ds.nuts_iii IS 'Sub-região NUTS III (NUTS 2013).';
COMMENT ON COLUMN ine_0009930_ds.distrito IS 'Distrito derivado do código do município; não é uma dimensão do INE.';
COMMENT ON COLUMN ine_0009930_ds.municipio IS 'Município (concelho).';
COMMENT ON COLUMN ine_0009930_ds.local_residencia IS 'País (ou grupo de países) de residência do hóspede, com a designação do INE, incluindo o total.';
COMMENT ON COLUMN ine_0009930_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0009930_ds.hospedes IS 'Número de hóspedes (entradas). NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0009930_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0009930_ds.update_date IS 'Data do (último) carregamento do período.';


-- =============================================================================
-- ine_0010735_ds — Dormidas mensais por segmento de alojamento
-- =============================================================================
-- Indicador      0010735, mensal.
-- Granularidade  Uma linha por município, segmento de alojamento, ano e mês.
-- Valor          Dormidas mensais ao nível municipal: sazonalidade e variação
--                homóloga de cada município, por segmento.
-- Notas          As designações de segmento_alojamento mantêm-se exatamente
--                como publicadas pelo INE (sem normalização), incluindo o
--                total do INE. Filtre ano E mes.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0010735_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(64) NOT NULL,
    municipio varchar(64) NOT NULL,
    segmento_alojamento varchar(64) NOT NULL,
    ano INTEGER NOT NULL,
    mes CHAR(2) NOT NULL,
    dormidas REAL,
    create_date DATE,
    update_date DATE,
    PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, segmento_alojamento, ano, mes
    )
);

COMMENT ON TABLE ine_0010735_ds IS 'INE 0010735 (mensal): dormidas por município (NUTS 2013) e segmento de alojamento. Sazonalidade municipal.';
COMMENT ON COLUMN ine_0010735_ds.nuts_i IS 'Região NUTS I (NUTS 2013).';
COMMENT ON COLUMN ine_0010735_ds.nuts_ii IS 'Região NUTS II (NUTS 2013).';
COMMENT ON COLUMN ine_0010735_ds.nuts_iii IS 'Sub-região NUTS III (NUTS 2013).';
COMMENT ON COLUMN ine_0010735_ds.distrito IS 'Distrito derivado do código do município; não é uma dimensão do INE.';
COMMENT ON COLUMN ine_0010735_ds.municipio IS 'Município (concelho).';
COMMENT ON COLUMN ine_0010735_ds.segmento_alojamento IS 'Segmento de alojamento com a designação do INE (sem alterações), incluindo o total.';
COMMENT ON COLUMN ine_0010735_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0010735_ds.mes IS 'Mês de referência, texto com zero à esquerda 01..12.';
COMMENT ON COLUMN ine_0010735_ds.dormidas IS 'Número de dormidas no mês. NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0010735_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0010735_ds.update_date IS 'Data do (último) carregamento do período.';


-- =============================================================================
-- ine_0010736_ds — Hóspedes mensais por segmento de alojamento
-- =============================================================================
-- Indicador      0010736, mensal.
-- Granularidade  Uma linha por município, segmento de alojamento, ano e mês.
-- Valor          Hóspedes mensais ao nível municipal. Com ine_0010735_ds dá a
--                estada média mensal por município.
-- Notas          Mesmas dimensões e chaves de ine_0010735_ds.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0010736_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(64) NOT NULL,
    municipio varchar(64) NOT NULL,
    segmento_alojamento varchar(64) NOT NULL,
    ano INTEGER NOT NULL,
    mes CHAR(2) NOT NULL,
    hospedes REAL,
    create_date DATE,
    update_date DATE,
    PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, segmento_alojamento, ano, mes
    )
);

COMMENT ON TABLE ine_0010736_ds IS 'INE 0010736 (mensal): hóspedes por município (NUTS 2013) e segmento de alojamento. Sazonalidade municipal.';
COMMENT ON COLUMN ine_0010736_ds.nuts_i IS 'Região NUTS I (NUTS 2013).';
COMMENT ON COLUMN ine_0010736_ds.nuts_ii IS 'Região NUTS II (NUTS 2013).';
COMMENT ON COLUMN ine_0010736_ds.nuts_iii IS 'Sub-região NUTS III (NUTS 2013).';
COMMENT ON COLUMN ine_0010736_ds.distrito IS 'Distrito derivado do código do município; não é uma dimensão do INE.';
COMMENT ON COLUMN ine_0010736_ds.municipio IS 'Município (concelho).';
COMMENT ON COLUMN ine_0010736_ds.segmento_alojamento IS 'Segmento de alojamento com a designação do INE (sem alterações), incluindo o total.';
COMMENT ON COLUMN ine_0010736_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0010736_ds.mes IS 'Mês de referência, texto com zero à esquerda 01..12.';
COMMENT ON COLUMN ine_0010736_ds.hospedes IS 'Número de hóspedes (entradas) no mês. NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0010736_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0010736_ds.update_date IS 'Data do (último) carregamento do período.';


-- =============================================================================
-- ine_0011140_ds — Estada média por local de residência
-- =============================================================================
-- Indicador      0011140, anual.
-- Granularidade  Uma linha por município, país de residência e ano.
-- Valor          Estada média (noites por hóspede) por mercado emissor: que
--                mercados ficam mais tempo, apoiando a priorização de
--                mercados.
-- Notas          Rácio: não somar. Para agregados use
--                sum(ine_0009183_ds.dormidas) / sum(ine_0009930_ds.hospedes).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0011140_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(64) NOT NULL,
    municipio varchar(64) NOT NULL,
    local_residencia varchar(64) NOT NULL,
    ano int4 NOT NULL,
    estada_media float4 NULL,
    create_date date NULL,
    update_date date NULL,
    CONSTRAINT ine_0011140_ds_pkey PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, local_residencia, ano
    )
);

COMMENT ON TABLE ine_0011140_ds IS 'INE 0011140 (anual): estada média (noites por hóspede) por município (NUTS 2013) e país de residência do hóspede. Rácio - não somar.';
COMMENT ON COLUMN ine_0011140_ds.nuts_i IS 'Região NUTS I (NUTS 2013).';
COMMENT ON COLUMN ine_0011140_ds.nuts_ii IS 'Região NUTS II (NUTS 2013).';
COMMENT ON COLUMN ine_0011140_ds.nuts_iii IS 'Sub-região NUTS III (NUTS 2013).';
COMMENT ON COLUMN ine_0011140_ds.distrito IS 'Distrito derivado do código do município; não é uma dimensão do INE.';
COMMENT ON COLUMN ine_0011140_ds.municipio IS 'Município (concelho).';
COMMENT ON COLUMN ine_0011140_ds.local_residencia IS 'País (ou grupo de países) de residência do hóspede, com a designação do INE, incluindo o total.';
COMMENT ON COLUMN ine_0011140_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0011140_ds.estada_media IS 'Estada média em noites (dormidas / hóspedes) publicada pelo INE. Não aditiva. NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0011140_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0011140_ds.update_date IS 'Data do (último) carregamento do período.';


-- =============================================================================
-- ine_0012093_ds — Hóspedes mensais por tipo de alojamento (NUTS I/II, 2024)
-- =============================================================================
-- Indicador      0012093, mensal.
-- Granularidade  Uma linha por região NUTS II, tipo/subtipo de alojamento,
--                ano e mês.
-- Valor          Hóspedes mensais ao nível regional na geografia NUTS 2024
--                (a divisão regional atual do INE). Substitui
--                ine_0009812_ds para os períodos recentes.
-- Notas          As designações vêm da NUTS 2024 e não são diretamente
--                comparáveis com as tabelas NUTS 2013 (algumas regiões NUTS II
--                mudaram em 2024).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ine_0012093_ds (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    tipo_alojamento varchar(64) NOT NULL,
    subtipo_alojamento varchar(64) NOT NULL,
    ano INTEGER NOT NULL,
    mes CHAR(2) NOT NULL,
    hospedes REAL,
    create_date DATE,
    update_date DATE,
    PRIMARY KEY (nuts_i, nuts_ii, tipo_alojamento, subtipo_alojamento, ano, mes)
);

COMMENT ON TABLE ine_0012093_ds IS 'INE 0012093 (mensal): hóspedes por região NUTS II (NUTS 2024) e tipo/subtipo de alojamento. Sazonalidade regional da procura na geografia NUTS atual.';
COMMENT ON COLUMN ine_0012093_ds.nuts_i IS 'Região NUTS I (NUTS 2024).';
COMMENT ON COLUMN ine_0012093_ds.nuts_ii IS 'Região NUTS II (NUTS 2024). Só são guardadas linhas NUTS II.';
COMMENT ON COLUMN ine_0012093_ds.tipo_alojamento IS 'Tipo de alojamento (nível 1); Total para o total do INE.';
COMMENT ON COLUMN ine_0012093_ds.subtipo_alojamento IS 'Subtipo de alojamento (nível 2); repete o tipo quando não há nível inferior. Normalizado para alojamento local e rural.';
COMMENT ON COLUMN ine_0012093_ds.ano IS 'Ano de referência.';
COMMENT ON COLUMN ine_0012093_ds.mes IS 'Mês de referência, texto com zero à esquerda 01..12.';
COMMENT ON COLUMN ine_0012093_ds.hospedes IS 'Número de hóspedes (entradas) no mês. NULL quando confidencial ou não publicado.';
COMMENT ON COLUMN ine_0012093_ds.create_date IS 'Data do (último) carregamento do período.';
COMMENT ON COLUMN ine_0012093_ds.update_date IS 'Data do (último) carregamento do período.';
