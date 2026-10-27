# Pista Digital – Power BI template

Power BI Project (PBIP / PBIR) following
[design/pistadigital.uevora.pt-DESIGN.md](../design/pistadigital.uevora.pt-DESIGN.md),
over the INE indicators produced by [flows-code](../flows-code/README.md).

## Open

1. Power BI Desktop → Options → Preview features → enable **Power BI Project (.pbip) save option**
   and **Store reports using enhanced metadata format (PBIR)**.
2. Open `PistaDigital.pbip`.
3. Make sure the `pista` ODBC DSN exists (see Connection), then sign in with the database user.
4. Install the Montserrat font (Google Fonts) on every machine that edits the report.

## Connection

The model reads the PostgreSQL database the flows write to through an ODBC
DSN, and is refreshed in the Power BI Service through the on-premises data
gateway cluster `pistadigital`. Two Power Query parameters hold the target, and
credentials are supplied by Power BI itself — never stored in these files:

| Parameter | Matches | Example |
|---|---|---|
| `DSN` | System DSN pointing at `PISTA_DB_HOSTNAME`:`PISTA_DB_PORTNUMBER` | `pista` |
| `BaseDados` | `PISTA_DB_NAME` | `pista` |

All tables load through the shared `Fonte` query, so the connection is defined once.

- **Power BI Desktop:** create a 64-bit System DSN named `pista` (PostgreSQL
  Unicode driver) on the authoring machine.
- **Power BI Service:** every machine in the `pistadigital` gateway cluster needs
  the same `pista` System DSN. In the gateway cluster, add an ODBC connection
  with connection string `dsn=pista` and the database credentials. Then, in the
  semantic model settings → *Gateway and cloud connections*, map the data source
  to that connection.

## Semantic model

One fact table per INE indicator, named `<descrição> (<varcd>)`, reading
`public.ine_<varcd>_ds`. Each carries a single base measure.

| Indicador | Grão | Medida base |
|---|---|---|
| Superfície das unidades territoriais (0008350) | Município / ano | Superfície (km²) |
| Dormidas por país de residência (0009183) | Município / ano / residência | Dormidas (residência) |
| Dormidas mensais por tipo de alojamento (NUTS 2013) (0009808) | NUTS II / mês / tipo | Dormidas mensais (tipo) |
| Hóspedes mensais por tipo de alojamento (NUTS 2013) (0009812) | NUTS II / mês / tipo | Hóspedes mensais (tipo) |
| Estabelecimentos de alojamento turístico (0009873) | Município / ano / tipo | Estabelecimentos |
| Quartos em alojamento turístico (0009874) | Município / ano / tipo | Quartos (tipo) |
| Hóspedes por tipo de alojamento (0009876) | Município / ano / tipo | Hóspedes (tipo) |
| Dormidas por tipo de alojamento (0009877) | Município / ano / tipo | Dormidas (tipo) |
| Estada média por tipo de alojamento (0009880) | Município / ano / tipo | Estada média INE (tipo) |
| Rendimento médio por quarto (0009929) | Município / ano / tipo | RevPAR médio INE |
| Hóspedes por país de residência (0009930) | Município / ano / residência | Hóspedes (residência) |
| Dormidas mensais por segmento (0010735) | Município / mês / segmento | Dormidas mensais (segmento) |
| Hóspedes mensais por segmento (0010736) | Município / mês / segmento | Hóspedes mensais (segmento) |
| Estada média por país de residência (0011140) | Município / ano / residência | Estada média INE (residência) |
| Hóspedes mensais por tipo de alojamento (NUTS 2024) (0012093) | NUTS II / mês / tipo | Hóspedes mensais (tipo, NUTS 2024) |

### Shared dimensions

Built as DAX calculated tables from the union of the indicators that publish each
attribute, so every key is guaranteed to match.

- **Ano** — conforme a todos os 15 indicadores. Filter here to slice annual and
  monthly indicators together.
- **Calendário** — daily, marked as the date table, derived from the monthly
  indicators. Monthly facts join on the first day of each month. `Ano` filters
  `Calendário`, so a year selection reaches the monthly facts too; selecting a
  *month* does not filter annual indicators, which have no month.
- **Geografia** — município grain (`NUTS I | NUTS II | NUTS III | Distrito | Município`),
  joined to the 12 municipality-grain indicators.
- **Região NUTS II** — joined to `Geografia` and to the three NUTS II-only
  indicators, so a NUTS II selection filters both families.
- **Tipo de alojamento** — tipo + subtipo, across the nine indicators that publish them.
- **Residência**, **Segmento de alojamento** — single-attribute dimensions.

`classificacao` (stars) stays local to each indicator: its domain differs per
indicator, so a shared dimension would be wrong.

### `_Medidas`

Derived measures that span indicators: weighted average stay (dormidas ÷
hóspedes, preferable to the INE simple average), rooms per establishment,
year-on-year and month-on-month variation, and tourism intensity per km².

### Text handling

The source columns are `bpchar`/`CHAR`, which PostgreSQL blank-pads. Every text
column is trimmed in Power Query, otherwise the dimension keys would not match.

### Regenerating

`tools/generate_semantic_model.py` holds the indicator definitions mirroring
`flows-code/pistadigital/flows/ine_*_flow.py`. After adding an indicator or
changing a schema:

```bash
python3 powerbi/tools/generate_semantic_model.py && python3 powerbi/tools/validate_semantic_model.py
```

The validator checks that every relationship, column and measure reference
resolves, and that DAX and M expressions are balanced. It does not replace
opening the model in Power BI Desktop.

## Layout (1280 × 720)

- Content area: x 0–1040. Header band (navy, 96 px) with a 4 px gold rule.
- **Navigation bar on the right**: x 1040–1280 (240 px), navy, brand block on top and a
  vertical page navigator below. Selected page is gold, hover is `#154373`.
- Every page repeats the same header/brand/navigator. To add a page, duplicate an
  existing one so the navigation bar stays identical; the navigator lists new pages itself.

The four pages carry a placeholder in the content area; the visuals themselves
are still to be built on the model above.

## Theme

`PistaDigital.Report/StaticResources/RegisteredResources/PistaDigitalTheme.json`:
navy `#001F44`, gold `#FFAD00`, link `#2066BC`, ink `#1D2127`, hairline `#4E4F50`,
Montserrat, 0 px corner radius, no shadows, navy table headers.

## `PistaDigital.pbit`

**Out of date.** It still embeds the original single-table placeholder model, not
the semantic model above. Export a fresh one from Desktop (File → Export →
Power BI template) once the project opens correctly.

## Source table naming

Every indicator writes `public.ine_<varcd>_ds`, which is what this model reads.
`tests/test_ine_annual.py` and `tests/test_ine_monthly.py` assert both the name
and that each flow's DDL creates that same table.
