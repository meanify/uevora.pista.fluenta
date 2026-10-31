-- =============================================================================
-- Pista Digital (Universidade de Évora) — INE tables: DDL and data dictionary
-- =============================================================================
--
-- One file with every table the INE flows create, in PostgreSQL syntax. Each
-- table is described by:
--   * a header block: source indicator, frequency, grain, business value and
--     usage notes;
--   * the CREATE TABLE statement, identical to CREATE_TABLE_SQL in
--     flows-code/pistadigital/flows/ine_<code>_flow.py (the source of truth);
--   * COMMENT ON TABLE / COLUMN statements, so the same descriptions are
--     available in the database catalog (psql \d+, Power BI, DBeaver, ...).
--
-- The file is idempotent: CREATE TABLE IF NOT EXISTS never alters an existing
-- table, and COMMENT ON only replaces descriptions. Running it creates missing
-- tables and (re)writes the documentation; it never changes data.
--
-- Tables live in the connection's default schema (`public` in the standard
-- setup); Power BI reads them from `public` through the "Pista Digital" DSN.
--
-- -----------------------------------------------------------------------------
-- Shared conventions (apply to every table below)
-- -----------------------------------------------------------------------------
-- Source       Instituto Nacional de Estatística (INE), public JSON API
--              (www.ine.pt), one table per indicator code (`varcd`).
-- Naming       ine_<7-digit indicator code>_ds.
-- Load model   A run processes exactly one period. In a single transaction it
--              deletes the period (annual: ano = Y; monthly: ano = Y AND
--              mes = 'MM') and inserts the freshly fetched rows. Other periods
--              are untouched. If INE returns no rows, the stored period is kept.
--              Scheduling: Airflow DAGs in flows-code/dags/ (current year and
--              two previous years); full history via scripts/reload-ine-flows.sh.
-- Labels       All dimension columns hold the Portuguese INE label (not the
--              code), as VARCHAR (no padding). They are NOT NULL and part of
--              the primary key.
-- Geography    NUTS 2013 unless stated otherwise (0012093 uses NUTS 2024).
--              Municipal tables keep only municipality rows (7-character INE
--              geocode): Portugal / NUTS I / II / III aggregates are dropped,
--              so geography columns never contain 'Total' there. Regional
--              tables (NUTS I/II only) keep only NUTS II rows.
--              `distrito` is derived from the municipality code (DTCC digits)
--              and is not an INE dimension.
-- Accommodation
--              tipo_alojamento / subtipo_alojamento / classificacao are the 3
--              levels of INE's accommodation hierarchy (code prefixes of 2, 4
--              and 6 characters). Only the INE total ('Total' in all three
--              columns) and the most detailed categories are kept;
--              intermediate subtotals are dropped. When a category has no
--              deeper level, the lower columns repeat its label.
--              Normalisation applied by the flows:
--                - tipo 'Alojamento local'  -> subtipo and classificacao =
--                  'Alojamento Local';
--                - tipo containing 'rural' -> subtipo and classificacao =
--                  'Turismo no Espaço Rural e de Habitação';
--                - tipo containing 'habitação' (not 'rural') -> classificacao
--                  only = 'Turismo no Espaço Rural e de Habitação'.
--              IMPORTANT: INE suppresses many municipal values for statistical
--              confidentiality, so detail rows do NOT add up to the total.
--              Use tipo_alojamento = 'Total' for totals and exclude it for
--              breakdowns. Never sum detail rows to obtain a total.
-- Metrics      Stored as float4/REAL. NULL means INE published no value
--              (confidential, not available or not applicable: '', '..',
--              's.r.', 'x'); zero is a real zero. Ratios (estada_media,
--              rendimento_medio_por_quarto) are INE-published averages and
--              must not be summed; for aggregates use weighted measures.
-- Audit        create_date and update_date are both set to the run date. As a
--              period is fully replaced on reload, create_date is the date of
--              the latest load of that period, not of first insertion.
-- Period       ano = reference year. mes (monthly tables only) = zero-padded
--              month '01'..'12' stored as CHAR(2); always filter it as a
--              string (mes = '08') together with ano.
-- =============================================================================


-- =============================================================================
-- ine_0008350_ds — Superfície das unidades territoriais
-- =============================================================================
-- Indicator   0008350, annual.
-- Grain       One row per municipality per year.
-- Value       Land area (km²) of each municipality. Denominator for density
--             and pressure indicators (e.g. overnight stays or rooms per km²)
--             used to compare tourism intensity between territories of
--             different sizes.
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

COMMENT ON TABLE ine_0008350_ds IS 'INE 0008350 (annual): area of each municipality in km2, NUTS 2013 geography. Denominator for tourism density and pressure indicators.';
COMMENT ON COLUMN ine_0008350_ds.nuts_i IS 'NUTS I region label (NUTS 2013), e.g. Continente.';
COMMENT ON COLUMN ine_0008350_ds.nuts_ii IS 'NUTS II region label (NUTS 2013), e.g. Alentejo.';
COMMENT ON COLUMN ine_0008350_ds.nuts_iii IS 'NUTS III sub-region label (NUTS 2013), e.g. Alentejo Central.';
COMMENT ON COLUMN ine_0008350_ds.distrito IS 'District (or autonomous-region island) derived from the municipality code; not an INE dimension.';
COMMENT ON COLUMN ine_0008350_ds.municipio IS 'Municipality (concelho) label.';
COMMENT ON COLUMN ine_0008350_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0008350_ds.superficie_unidades_territoriais IS 'Area of the territorial unit in square kilometres (km2). NULL when not published.';
COMMENT ON COLUMN ine_0008350_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0008350_ds.update_date IS 'Date the period was (last) loaded.';


-- =============================================================================
-- ine_0009183_ds — Dormidas por local de residência
-- =============================================================================
-- Indicator   0009183, annual.
-- Grain       One row per municipality, country of residence and year.
-- Value       Overnight stays in tourist accommodation broken down by the
--             guest's country of residence. Shows which source markets
--             generate the most nights in each municipality, supporting
--             market-targeted promotion and dependency analysis.
-- Notes       local_residencia includes the INE total and Portugal; use the
--             total row for totals rather than summing countries.
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

COMMENT ON TABLE ine_0009183_ds IS 'INE 0009183 (annual): overnight stays in tourist accommodation by municipality (NUTS 2013) and guest country of residence. Source-market analysis.';
COMMENT ON COLUMN ine_0009183_ds.nuts_i IS 'NUTS I region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009183_ds.nuts_ii IS 'NUTS II region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009183_ds.nuts_iii IS 'NUTS III sub-region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009183_ds.distrito IS 'District derived from the municipality code; not an INE dimension.';
COMMENT ON COLUMN ine_0009183_ds.municipio IS 'Municipality (concelho) label.';
COMMENT ON COLUMN ine_0009183_ds.local_residencia IS 'Guest country (or group of countries) of residence, as labelled by INE, including the total.';
COMMENT ON COLUMN ine_0009183_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0009183_ds.dormidas IS 'Number of overnight stays (nights spent by guests). NULL when confidential or not published.';
COMMENT ON COLUMN ine_0009183_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0009183_ds.update_date IS 'Date the period was (last) loaded.';


-- =============================================================================
-- ine_0009808_ds — Dormidas mensais por tipo de alojamento (NUTS I/II, 2013)
-- =============================================================================
-- Indicator   0009808, monthly.
-- Grain       One row per NUTS II region, accommodation type/subtype, year
--             and month.
-- Value       Monthly overnight stays at regional level. Main source for
--             seasonality analysis (peaks, low season, year-on-year change)
--             and for comparing the region against other NUTS II regions.
-- Notes       No municipality or classificacao columns. Filter ano AND mes.
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

COMMENT ON TABLE ine_0009808_ds IS 'INE 0009808 (monthly): overnight stays by NUTS II region (NUTS 2013) and accommodation type/subtype. Regional seasonality.';
COMMENT ON COLUMN ine_0009808_ds.nuts_i IS 'NUTS I region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009808_ds.nuts_ii IS 'NUTS II region label (NUTS 2013). Only NUTS II rows are stored.';
COMMENT ON COLUMN ine_0009808_ds.tipo_alojamento IS 'Accommodation type (level 1); Total for the INE total.';
COMMENT ON COLUMN ine_0009808_ds.subtipo_alojamento IS 'Accommodation subtype (level 2); repeats the type label when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009808_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0009808_ds.mes IS 'Reference month, zero-padded string 01..12.';
COMMENT ON COLUMN ine_0009808_ds.dormidas IS 'Number of overnight stays in the month. NULL when confidential or not published.';
COMMENT ON COLUMN ine_0009808_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0009808_ds.update_date IS 'Date the period was (last) loaded.';


-- =============================================================================
-- ine_0009812_ds — Hóspedes mensais por tipo de alojamento (NUTS I/II, 2013)
-- =============================================================================
-- Indicator   0009812, monthly.
-- Grain       One row per NUTS II region, accommodation type/subtype, year
--             and month.
-- Value       Monthly guest arrivals at regional level. Combined with
--             ine_0009808_ds (nights) it gives the regional average length of
--             stay per month and the seasonal demand profile.
-- Notes       Same layout as ine_0012093_ds but with NUTS 2013 labels.
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

COMMENT ON TABLE ine_0009812_ds IS 'INE 0009812 (monthly): guests by NUTS II region (NUTS 2013) and accommodation type/subtype. Regional demand seasonality.';
COMMENT ON COLUMN ine_0009812_ds.nuts_i IS 'NUTS I region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009812_ds.nuts_ii IS 'NUTS II region label (NUTS 2013). Only NUTS II rows are stored.';
COMMENT ON COLUMN ine_0009812_ds.tipo_alojamento IS 'Accommodation type (level 1); Total for the INE total.';
COMMENT ON COLUMN ine_0009812_ds.subtipo_alojamento IS 'Accommodation subtype (level 2); repeats the type label when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009812_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0009812_ds.mes IS 'Reference month, zero-padded string 01..12.';
COMMENT ON COLUMN ine_0009812_ds.hospedes IS 'Number of guests (check-ins) in the month. NULL when confidential or not published.';
COMMENT ON COLUMN ine_0009812_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0009812_ds.update_date IS 'Date the period was (last) loaded.';


-- =============================================================================
-- ine_0009873_ds — Estabelecimentos de alojamento turístico
-- =============================================================================
-- Indicator   0009873, annual.
-- Grain       One row per municipality, accommodation type / subtype /
--             classification and year.
-- Value       Supply side: number of tourist accommodation establishments.
--             Measures the size and mix of the accommodation offer (hotels,
--             local accommodation, rural tourism, ...) and its evolution.
-- Notes       The metric name keeps the original spelling "establecimento".
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

COMMENT ON TABLE ine_0009873_ds IS 'INE 0009873 (annual): number of tourist accommodation establishments by municipality (NUTS 2013) and accommodation type/subtype/classification. Accommodation supply.';
COMMENT ON COLUMN ine_0009873_ds.nuts_i IS 'NUTS I region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009873_ds.nuts_ii IS 'NUTS II region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009873_ds.nuts_iii IS 'NUTS III sub-region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009873_ds.distrito IS 'District derived from the municipality code; not an INE dimension.';
COMMENT ON COLUMN ine_0009873_ds.municipio IS 'Municipality (concelho) label.';
COMMENT ON COLUMN ine_0009873_ds.tipo_alojamento IS 'Accommodation type (level 1); Total for the INE total.';
COMMENT ON COLUMN ine_0009873_ds.subtipo_alojamento IS 'Accommodation subtype (level 2); repeats the level above when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009873_ds.classificacao IS 'Classification (level 3), e.g. hotel star rating; repeats the level above when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009873_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0009873_ds.establecimento_de_alojamento_turistico IS 'Number of tourist accommodation establishments. NULL when confidential or not published.';
COMMENT ON COLUMN ine_0009873_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0009873_ds.update_date IS 'Date the period was (last) loaded.';


-- =============================================================================
-- ine_0009874_ds — Quartos em estabelecimentos de alojamento turístico
-- =============================================================================
-- Indicator   0009874, annual.
-- Grain       One row per municipality, accommodation type / subtype /
--             classification and year.
-- Value       Supply side: accommodation capacity in rooms. Basis for
--             carrying-capacity and tourism-pressure indicators (rooms per
--             km² with ine_0008350_ds, nights per room with ine_0009877_ds).
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

COMMENT ON TABLE ine_0009874_ds IS 'INE 0009874 (annual): number of rooms in tourist accommodation by municipality (NUTS 2013) and accommodation type/subtype/classification. Accommodation capacity.';
COMMENT ON COLUMN ine_0009874_ds.nuts_i IS 'NUTS I region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009874_ds.nuts_ii IS 'NUTS II region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009874_ds.nuts_iii IS 'NUTS III sub-region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009874_ds.distrito IS 'District derived from the municipality code; not an INE dimension.';
COMMENT ON COLUMN ine_0009874_ds.municipio IS 'Municipality (concelho) label.';
COMMENT ON COLUMN ine_0009874_ds.tipo_alojamento IS 'Accommodation type (level 1); Total for the INE total.';
COMMENT ON COLUMN ine_0009874_ds.subtipo_alojamento IS 'Accommodation subtype (level 2); repeats the level above when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009874_ds.classificacao IS 'Classification (level 3); repeats the level above when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009874_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0009874_ds.quartos IS 'Number of rooms. NULL when confidential or not published.';
COMMENT ON COLUMN ine_0009874_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0009874_ds.update_date IS 'Date the period was (last) loaded.';


-- =============================================================================
-- ine_0009876_ds — Hóspedes por tipo de alojamento
-- =============================================================================
-- Indicator   0009876, annual.
-- Grain       One row per municipality, accommodation type / subtype /
--             classification and year.
-- Value       Demand side: number of guests per municipality and type of
--             accommodation. Shows which accommodation segments attract
--             visitors and, with ine_0009877_ds, the length of their stay.
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

COMMENT ON TABLE ine_0009876_ds IS 'INE 0009876 (annual): guests in tourist accommodation by municipality (NUTS 2013) and accommodation type/subtype/classification. Tourism demand.';
COMMENT ON COLUMN ine_0009876_ds.nuts_i IS 'NUTS I region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009876_ds.nuts_ii IS 'NUTS II region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009876_ds.nuts_iii IS 'NUTS III sub-region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009876_ds.distrito IS 'District derived from the municipality code; not an INE dimension.';
COMMENT ON COLUMN ine_0009876_ds.municipio IS 'Municipality (concelho) label.';
COMMENT ON COLUMN ine_0009876_ds.tipo_alojamento IS 'Accommodation type (level 1); Total for the INE total.';
COMMENT ON COLUMN ine_0009876_ds.subtipo_alojamento IS 'Accommodation subtype (level 2); repeats the level above when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009876_ds.classificacao IS 'Classification (level 3); repeats the level above when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009876_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0009876_ds.hospedes IS 'Number of guests (check-ins). NULL when confidential or not published.';
COMMENT ON COLUMN ine_0009876_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0009876_ds.update_date IS 'Date the period was (last) loaded.';


-- =============================================================================
-- ine_0009877_ds — Dormidas por tipo de alojamento
-- =============================================================================
-- Indicator   0009877, annual.
-- Grain       One row per municipality, accommodation type / subtype /
--             classification and year.
-- Value       Demand side: overnight stays, the main volume indicator of
--             tourism activity in a municipality. Used for rankings, growth,
--             market share by accommodation segment and pressure indicators.
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

COMMENT ON TABLE ine_0009877_ds IS 'INE 0009877 (annual): overnight stays in tourist accommodation by municipality (NUTS 2013) and accommodation type/subtype/classification. Main tourism volume indicator.';
COMMENT ON COLUMN ine_0009877_ds.nuts_i IS 'NUTS I region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009877_ds.nuts_ii IS 'NUTS II region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009877_ds.nuts_iii IS 'NUTS III sub-region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009877_ds.distrito IS 'District derived from the municipality code; not an INE dimension.';
COMMENT ON COLUMN ine_0009877_ds.municipio IS 'Municipality (concelho) label.';
COMMENT ON COLUMN ine_0009877_ds.tipo_alojamento IS 'Accommodation type (level 1); Total for the INE total.';
COMMENT ON COLUMN ine_0009877_ds.subtipo_alojamento IS 'Accommodation subtype (level 2, up to 128 chars); repeats the level above when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009877_ds.classificacao IS 'Classification (level 3); repeats the level above when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009877_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0009877_ds.dormidas IS 'Number of overnight stays (nights spent by guests). NULL when confidential or not published.';
COMMENT ON COLUMN ine_0009877_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0009877_ds.update_date IS 'Date the period was (last) loaded.';


-- =============================================================================
-- ine_0009880_ds — Estada média por tipo de alojamento
-- =============================================================================
-- Indicator   0009880, annual.
-- Grain       One row per municipality, accommodation type / subtype /
--             classification and year.
-- Value       Average length of stay (nights per guest) as published by INE.
--             Indicates visit depth: short transit stays vs. destination
--             stays, by accommodation segment.
-- Notes       Ratio: do not sum or average across rows. For aggregates,
--             compute sum(dormidas) / sum(hospedes) from ine_0009877_ds and
--             ine_0009876_ds.
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

COMMENT ON TABLE ine_0009880_ds IS 'INE 0009880 (annual): average length of stay (nights per guest) in tourist accommodation by municipality (NUTS 2013) and accommodation type/subtype/classification. Ratio - do not sum.';
COMMENT ON COLUMN ine_0009880_ds.nuts_i IS 'NUTS I region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009880_ds.nuts_ii IS 'NUTS II region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009880_ds.nuts_iii IS 'NUTS III sub-region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009880_ds.distrito IS 'District derived from the municipality code; not an INE dimension.';
COMMENT ON COLUMN ine_0009880_ds.municipio IS 'Municipality (concelho) label.';
COMMENT ON COLUMN ine_0009880_ds.tipo_alojamento IS 'Accommodation type (level 1); Total for the INE total.';
COMMENT ON COLUMN ine_0009880_ds.subtipo_alojamento IS 'Accommodation subtype (level 2, up to 128 chars); repeats the level above when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009880_ds.classificacao IS 'Classification (level 3); repeats the level above when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009880_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0009880_ds.estada_media IS 'Average length of stay in nights (overnight stays / guests) as published by INE. Not additive. NULL when confidential or not published.';
COMMENT ON COLUMN ine_0009880_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0009880_ds.update_date IS 'Date the period was (last) loaded.';


-- =============================================================================
-- ine_0009929_ds — Rendimento médio por quarto (RevPAR)
-- =============================================================================
-- Indicator   0009929, annual.
-- Grain       One row per municipality, accommodation type / subtype /
--             classification and year.
-- Value       Average revenue per available room (RevPAR, euros) as published
--             by INE. Measures the economic performance of the accommodation
--             offer, combining occupancy and price.
-- Notes       Ratio: do not sum. Unlike the other tables, the audit columns
--             are timestamp instead of date.
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

COMMENT ON TABLE ine_0009929_ds IS 'INE 0009929 (annual): average revenue per available room (RevPAR, EUR) by municipality (NUTS 2013) and accommodation type/subtype/classification. Ratio - do not sum.';
COMMENT ON COLUMN ine_0009929_ds.nuts_i IS 'NUTS I region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009929_ds.nuts_ii IS 'NUTS II region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009929_ds.nuts_iii IS 'NUTS III sub-region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009929_ds.distrito IS 'District derived from the municipality code; not an INE dimension.';
COMMENT ON COLUMN ine_0009929_ds.municipio IS 'Municipality (concelho) label.';
COMMENT ON COLUMN ine_0009929_ds.tipo_alojamento IS 'Accommodation type (level 1); Total for the INE total.';
COMMENT ON COLUMN ine_0009929_ds.subtipo_alojamento IS 'Accommodation subtype (level 2, up to 128 chars); repeats the level above when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009929_ds.classificacao IS 'Classification (level 3); repeats the level above when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0009929_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0009929_ds.rendimento_medio_por_quarto IS 'Average revenue per available room (RevPAR) in euros, as published by INE. Not additive. NULL when confidential or not published.';
COMMENT ON COLUMN ine_0009929_ds.create_date IS 'Timestamp (run date) the period was (last) loaded.';
COMMENT ON COLUMN ine_0009929_ds.update_date IS 'Timestamp (run date) the period was (last) loaded.';


-- =============================================================================
-- ine_0009930_ds — Hóspedes por local de residência
-- =============================================================================
-- Indicator   0009930, annual.
-- Grain       One row per municipality, country of residence and year.
-- Value       Guests by country of residence: the number of visitors each
--             source market brings to the municipality (domestic vs.
--             international mix, key foreign markets).
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

COMMENT ON TABLE ine_0009930_ds IS 'INE 0009930 (annual): guests in tourist accommodation by municipality (NUTS 2013) and guest country of residence. Source-market analysis.';
COMMENT ON COLUMN ine_0009930_ds.nuts_i IS 'NUTS I region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009930_ds.nuts_ii IS 'NUTS II region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009930_ds.nuts_iii IS 'NUTS III sub-region label (NUTS 2013).';
COMMENT ON COLUMN ine_0009930_ds.distrito IS 'District derived from the municipality code; not an INE dimension.';
COMMENT ON COLUMN ine_0009930_ds.municipio IS 'Municipality (concelho) label.';
COMMENT ON COLUMN ine_0009930_ds.local_residencia IS 'Guest country (or group of countries) of residence, as labelled by INE, including the total.';
COMMENT ON COLUMN ine_0009930_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0009930_ds.hospedes IS 'Number of guests (check-ins). NULL when confidential or not published.';
COMMENT ON COLUMN ine_0009930_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0009930_ds.update_date IS 'Date the period was (last) loaded.';


-- =============================================================================
-- ine_0010735_ds — Dormidas mensais por segmento de alojamento
-- =============================================================================
-- Indicator   0010735, monthly.
-- Grain       One row per municipality, accommodation segment, year and
--             month.
-- Value       Monthly overnight stays at municipal level: seasonality and
--             year-on-year change for each municipality, by segment.
-- Notes       segmento_alojamento labels are kept exactly as published by INE
--             (no normalisation), including the INE total. Filter ano AND mes.
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

COMMENT ON TABLE ine_0010735_ds IS 'INE 0010735 (monthly): overnight stays by municipality (NUTS 2013) and accommodation segment. Municipal seasonality.';
COMMENT ON COLUMN ine_0010735_ds.nuts_i IS 'NUTS I region label (NUTS 2013).';
COMMENT ON COLUMN ine_0010735_ds.nuts_ii IS 'NUTS II region label (NUTS 2013).';
COMMENT ON COLUMN ine_0010735_ds.nuts_iii IS 'NUTS III sub-region label (NUTS 2013).';
COMMENT ON COLUMN ine_0010735_ds.distrito IS 'District derived from the municipality code; not an INE dimension.';
COMMENT ON COLUMN ine_0010735_ds.municipio IS 'Municipality (concelho) label.';
COMMENT ON COLUMN ine_0010735_ds.segmento_alojamento IS 'Accommodation segment as labelled by INE (unchanged), including the total.';
COMMENT ON COLUMN ine_0010735_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0010735_ds.mes IS 'Reference month, zero-padded string 01..12.';
COMMENT ON COLUMN ine_0010735_ds.dormidas IS 'Number of overnight stays in the month. NULL when confidential or not published.';
COMMENT ON COLUMN ine_0010735_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0010735_ds.update_date IS 'Date the period was (last) loaded.';


-- =============================================================================
-- ine_0010736_ds — Hóspedes mensais por segmento de alojamento
-- =============================================================================
-- Indicator   0010736, monthly.
-- Grain       One row per municipality, accommodation segment, year and
--             month.
-- Value       Monthly guests at municipal level. With ine_0010735_ds gives the
--             monthly average length of stay per municipality.
-- Notes       Same dimensions and keys as ine_0010735_ds.
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

COMMENT ON TABLE ine_0010736_ds IS 'INE 0010736 (monthly): guests by municipality (NUTS 2013) and accommodation segment. Municipal seasonality.';
COMMENT ON COLUMN ine_0010736_ds.nuts_i IS 'NUTS I region label (NUTS 2013).';
COMMENT ON COLUMN ine_0010736_ds.nuts_ii IS 'NUTS II region label (NUTS 2013).';
COMMENT ON COLUMN ine_0010736_ds.nuts_iii IS 'NUTS III sub-region label (NUTS 2013).';
COMMENT ON COLUMN ine_0010736_ds.distrito IS 'District derived from the municipality code; not an INE dimension.';
COMMENT ON COLUMN ine_0010736_ds.municipio IS 'Municipality (concelho) label.';
COMMENT ON COLUMN ine_0010736_ds.segmento_alojamento IS 'Accommodation segment as labelled by INE (unchanged), including the total.';
COMMENT ON COLUMN ine_0010736_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0010736_ds.mes IS 'Reference month, zero-padded string 01..12.';
COMMENT ON COLUMN ine_0010736_ds.hospedes IS 'Number of guests (check-ins) in the month. NULL when confidential or not published.';
COMMENT ON COLUMN ine_0010736_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0010736_ds.update_date IS 'Date the period was (last) loaded.';


-- =============================================================================
-- ine_0011140_ds — Estada média por local de residência
-- =============================================================================
-- Indicator   0011140, annual.
-- Grain       One row per municipality, country of residence and year.
-- Value       Average length of stay (nights per guest) by source market:
--             which markets stay longer, informing market prioritisation.
-- Notes       Ratio: do not sum. For aggregates use
--             sum(ine_0009183_ds.dormidas) / sum(ine_0009930_ds.hospedes).
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

COMMENT ON TABLE ine_0011140_ds IS 'INE 0011140 (annual): average length of stay (nights per guest) by municipality (NUTS 2013) and guest country of residence. Ratio - do not sum.';
COMMENT ON COLUMN ine_0011140_ds.nuts_i IS 'NUTS I region label (NUTS 2013).';
COMMENT ON COLUMN ine_0011140_ds.nuts_ii IS 'NUTS II region label (NUTS 2013).';
COMMENT ON COLUMN ine_0011140_ds.nuts_iii IS 'NUTS III sub-region label (NUTS 2013).';
COMMENT ON COLUMN ine_0011140_ds.distrito IS 'District derived from the municipality code; not an INE dimension.';
COMMENT ON COLUMN ine_0011140_ds.municipio IS 'Municipality (concelho) label.';
COMMENT ON COLUMN ine_0011140_ds.local_residencia IS 'Guest country (or group of countries) of residence, as labelled by INE, including the total.';
COMMENT ON COLUMN ine_0011140_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0011140_ds.estada_media IS 'Average length of stay in nights (overnight stays / guests) as published by INE. Not additive. NULL when confidential or not published.';
COMMENT ON COLUMN ine_0011140_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0011140_ds.update_date IS 'Date the period was (last) loaded.';


-- =============================================================================
-- ine_0012093_ds — Hóspedes mensais por tipo de alojamento (NUTS I/II, 2024)
-- =============================================================================
-- Indicator   0012093, monthly.
-- Grain       One row per NUTS II region, accommodation type/subtype, year
--             and month.
-- Value       Monthly guests at regional level using the NUTS 2024
--             geography (the current INE regional breakdown). Successor view
--             of ine_0009812_ds for recent periods.
-- Notes       Labels come from NUTS 2024 and are not directly comparable with
--             the NUTS 2013 tables (some NUTS II regions changed in 2024).
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

COMMENT ON TABLE ine_0012093_ds IS 'INE 0012093 (monthly): guests by NUTS II region (NUTS 2024) and accommodation type/subtype. Regional demand seasonality on the current NUTS geography.';
COMMENT ON COLUMN ine_0012093_ds.nuts_i IS 'NUTS I region label (NUTS 2024).';
COMMENT ON COLUMN ine_0012093_ds.nuts_ii IS 'NUTS II region label (NUTS 2024). Only NUTS II rows are stored.';
COMMENT ON COLUMN ine_0012093_ds.tipo_alojamento IS 'Accommodation type (level 1); Total for the INE total.';
COMMENT ON COLUMN ine_0012093_ds.subtipo_alojamento IS 'Accommodation subtype (level 2); repeats the type label when there is no deeper level. Normalised for local and rural accommodation.';
COMMENT ON COLUMN ine_0012093_ds.ano IS 'Reference year.';
COMMENT ON COLUMN ine_0012093_ds.mes IS 'Reference month, zero-padded string 01..12.';
COMMENT ON COLUMN ine_0012093_ds.hospedes IS 'Number of guests (check-ins) in the month. NULL when confidential or not published.';
COMMENT ON COLUMN ine_0012093_ds.create_date IS 'Date the period was (last) loaded.';
COMMENT ON COLUMN ine_0012093_ds.update_date IS 'Date the period was (last) loaded.';
