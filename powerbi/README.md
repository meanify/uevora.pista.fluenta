# Pista Digital – Power BI template

Power BI Project (PBIP / PBIR) following
[design/pistadigital.uevora.pt-DESIGN.md](../design/pistadigital.uevora.pt-DESIGN.md),
over the INE indicators produced by [flows-code](../flows-code/README.md).

## Open

1. Power BI Desktop → Options → Preview features → enable **Power BI Project (.pbip) save option**
   and **Store reports using enhanced metadata format (PBIR)**.
2. Open `PistaDigital.pbip`.
3. Make sure the `Pista Digital` ODBC DSN exists (see Connection), then sign in with the database user.

## Connection

The model reads the PostgreSQL database the flows write to through an ODBC
DSN, and is refreshed in the Power BI Service through the on-premises data
gateway cluster `pistadigital`. Two Power Query parameters hold the target, and
credentials are supplied by Power BI itself — never stored in these files:

| Parameter | Matches | Example |
|---|---|---|
| `DSN` | System DSN pointing at `PISTA_DB_HOSTNAME`:`PISTA_DB_PORTNUMBER` | `Pista Digital` |
| `BaseDados` | `PISTA_DB_NAME` | `pista` |

A third parameter, `RegiaoNUTSII` (default `Alentejo`), scopes the model to one
NUTS II region. Every fact query filters `nuts_ii` on it straight after `Fonte`,
so the filter folds into the ODBC query and only that region is imported; the
calculated dimensions (`Geografia`, `Região NUTS II`, …) follow. The municipal
indicators use NUTS 2013, where Alentejo still includes Lezíria do Tejo; 0012093
uses NUTS 2024, where it does not.

The flows store every level of INE's breakdowns, with `Total` for the levels a
row does not reach, while the base measures `SUM`. So each query also keeps only
the most detailed row of each branch: municipalities (no NUTS II / NUTS III
totals), and the leaves of the accommodation, residence and segment breakdowns.
A parent is dropped only when the table has children under it, so a branch INE
does not break down further (Alojamento local, Pousadas) keeps its own row — that
row still reads `Total` in the columns it does not reach. `Estrangeiro` is dropped
in favour of the countries. Averaged indicators (`Estada média INE`, `RevPAR médio
INE`) therefore average the leaves, not INE's published total; use the weighted
measures in `_Medidas` for an overall figure.

All tables load through the shared `Fonte` query, so the connection is defined once.

- **Power BI Desktop:** create a 64-bit System DSN named `Pista Digital` (PostgreSQL
  Unicode driver) on the authoring machine.
- **Power BI Service:** every machine in the `pistadigital` gateway cluster needs
  the same `Pista Digital` System DSN. In the gateway cluster, add an ODBC connection
  with connection string `dsn=Pista Digital` and the database credentials. Then, in the
  semantic model settings → *Gateway and cloud connections*, map the data source
  to that connection.

## Publish to web

*Publish to web* makes the report **anonymously readable by anyone with the
link**, and search engines index it. The embed exposes the whole semantic model,
not just the visuals on the page, so prefer *Embed for your organization* unless
public access is the actual goal.

Nothing in this project blocks it. Checked against the documented blockers:

| Blocker | This project |
|---|---|
| Row-level security | None — no roles in the semantic model |
| Live connection (AS, AAS) | No — all tables are `mode: import` |
| Shared semantic model | No — `definition.pbir` references the model `byPath`, so the report owns it in the same workspace |
| R, Python, ArcGIS, Q&A visuals | None — only `textbox`, `pageNavigator`, `slicer`, `card`, `barChart`, `scatterChart`, `map`, `pivotTable` |
| Custom (AppSource) visuals | None — `PistaDigitalTheme.json` is a theme, not a visual |

The ODBC/gateway connection above is not a blocker: the model is import mode, so
the `pistadigital` gateway serves only scheduled refresh. Only DirectQuery with
single sign-on is unsupported.

If the option is still greyed out, it is one of these, and neither lives in these
files:

1. **Tenant setting** — Fabric admin portal → *Tenant settings* → *Export and
   sharing* → *Publish to web*. Disabled, set to *Allow existing codes only*, or
   restricted to a security group you are not in. Requires an admin.
2. **Sensitivity label** — a label on the report or semantic model blocks
   publishing. Labels are Service-side metadata and never appear in the PBIP
   files; check the label in the report header in the Service.

You also need to be **admin or member** of the workspace — contributor and viewer
cannot create embed codes.

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
  indicators, so a NUTS II selection filters both families. With `RegiaoNUTSII`
  set it holds a single row.
- **Tipo de alojamento** — tipo + subtipo, across the nine indicators that publish them.
- **Residência**, **Segmento de alojamento** — single-attribute dimensions.

`classificacao` (stars) stays local to each indicator: its domain differs per
indicator, so a shared dimension would be wrong.

### `_Medidas`

Derived measures that span indicators: weighted average stay (dormidas ÷
hóspedes, preferable to the INE simple average), rooms per establishment,
month-on-month variation, and tourism intensity per km².

#### Year-on-year

Every one of the 15 indicators has a pair — a prior-year value and a variance —
generated from its base measure, so the names follow from it: `Hóspedes (tipo)`
gives `Hóspedes (tipo, ano anterior)` and `Hóspedes (tipo) YoY %`. The pair sits
on the indicator's own table, next to its base measure, rather than on `_Medidas`.

Two patterns, because the families hang off different dimensions:

| Family | Previous year read by | Why |
|---|---|---|
| Annual (10 indicators, joined to `Ano`) | swapping the year filter (`REMOVEFILTERS('Ano')`) | no month to preserve; needs a single year in context |
| Monthly (5 indicators, joined to `Calendário`) | `DATEADD('Calendário'[Date], -1, YEAR)` | composes at both grains — the same measure answers "this month vs the same month last year" and "this year vs last year", which the `Ano` pattern cannot once a month is selected |

Two exceptions to the naming, both predating the rest: `Dormidas (tipo)` keeps
`Dormidas (ano anterior)` / `Dormidas YoY %`, and `RevPAR médio INE` keeps
`RevPAR médio (ano anterior)` / `RevPAR YoY %`. Renaming them would break the
report bindings that already point at them.

`Superfície (km²) YoY %` exists for completeness and is almost always blank or
zero — municipality boundaries rarely move, and everything that divides by area
uses `Superfície (km², último ano)` rather than the selected year's value.

The comparison pages add a peer-group family. Each is built from the focus
município in the disconnected `Município selecionado`, over the peers in the same
NUTS III, counting only those that actually report the metric:

| Metric | Rank | Denominator |
|---|---|---|
| `Ocupação estimada` | `Posição no grupo de pares` | `Pares com dados` |
| `Dormidas por km²` | `Posição no grupo de pares (pressão)` | `Pares com dados (pressão)` |
| `RevPAR médio INE` | `Posição no grupo de pares (RevPAR)` | `Pares com dados (RevPAR)` |

Each metric needs its own denominator: a município that reports ocupação may not
report RevPAR, so a shared count would print «3.º de 14» against 11 peers. Always
show a rank next to its denominator — never the rank alone.

`Média de pares (ocupação)` and `Média de pares (estada média)` are the peer
comparators the KPI tiles read against. Both average each peer's own value rather
than pooling the group's numerators and denominators: a pooled ratio is dominated
by the largest município, which is not what "face aos pares" means.

`Percentil de pressão` ranks across every imported município instead (the whole
`RegiaoNUTSII` region), and `Municípios com dados de pressão` is its denominator
(«12, entre 58 municípios»).

`Cor do município em foco` returns a hex string (`#FFAD00` for the focus
município, `#2066BC` for the peers) rather than a 0/1 flag, because *Field value*
conditional formatting reads the measure straight into the fill. It needs
`Geografia[Município]` on the axis to resolve. `Cor da sub-região em foco` is the
same idea one level up, over the disconnected `Sub-região em foco`, and needs
`Geografia[NUTS III]` on the axis.

Each page's header sub-title is a card over a string measure (`Subtítulo · …`),
so the band echoes the current selection instead of repeating a fixed sentence.

### Disconnected tables

`Município selecionado`, `Sub-região em foco` and `Métrica de pressão` have no
relationships on purpose. The first two carry *which* territory is highlighted
without filtering it — a slicer that filtered would remove the very peers the
comparison is against — and the third drives `Pressão (métrica selecionada)`.
Anything reading them resolves to blank until a selection is made.

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

Running it against the committed model is a **byte-for-byte no-op**, so the
generator is safe to run at any time and a non-empty `git diff` afterwards is a
real change, not formatting noise. Keeping it that way means matching how Power
BI Desktop re-saves TMDL:

- **Identifiers** are written bare when they can be (`table Ano`, `column Ano-Mês`)
  and quoted only when they cannot (`table 'Região NUTS II'`). `q()` applies the
  rule: bare when the name matches `[^\W\d][\w-]*`.
- **`compatibilityLevel: 1606`**, `dataAccessOptions` (`legacyRedirects`,
  `returnErrorValuesAsNull`), and the `PBI_QueryGroupOrder` / `PBI_ProTooling`
  annotations are Desktop's and must be emitted.
- **`annotation SummarizationSetBy = Automatic`** marks a column whose
  summarization Desktop chose: the monthly indicators' `ano`, and the value
  column of each averaged indicator. Both read `summarizeBy: sum` as a result —
  see the caveat below.
- **`annotation UnderlyingDateTimeDataType = Date`** goes on every imported
  `dateTime` column, but not on `Calendário[Date]`, which is calculated.

> **`tag()` is a positional counter.** Inserting an entity shifts the
> `lineageTag` of everything generated after it, including the relationships at
> the end. Anything added after the model was first generated passes an explicit
> `tag_key=` so the sequence stays put — follow that for new measures rather than
> relying on where they sit in the list.

Two summarization defaults are Desktop's, not deliberate: `ano` on the five
monthly indicators, and `estada_media` / `rendimento_medio_por_quarto`, all read
`summarizeBy: sum`. Summing a year or an average is meaningless, so the base
measures aggregate explicitly (`AVERAGE(...)`) and never rely on the column
default; only an ad-hoc drag of those columns onto a visual would hit it.

## Layout (1280 × 720)

- **Navigation bar on the left**: x 0–240 (240 px), navy, brand block on top and a
  vertical page navigator below. Selected page is gold, hover is `#154373`.
- Content area: x 240–1280. Header band (navy, 96 px) with a 4 px gold rule, then
  visuals from y 112 and a footnote strip at y 686.
- Every page repeats the same header/brand/navigator. To add a page, duplicate an
  existing one so the navigation bar stays identical; the navigator lists new pages itself.

### Pages

| Page | Content |
|---|---|
| Visão Geral | Placeholder — still to be built |
| Quadro comparativo | Município/pares/ano slicers, 4 KPI cards each with YoY / rank / peer-count sub-cards, peer occupancy bars with the focus município in gold and a peer-average constant line, RevPAR × rooms-per-establishment scatter |
| Pressão turística | Metric/year/município slicers, bubble map of the selected pressure metric with the focus município in gold, pressure-percentile card over its national denominator, load-vs-capacity bars (gold = load, blue = licensed capacity) |
| Sazonalidade | Region/segment/focus-region slicers, month × year matrix heat map of monthly dormidas, summer-peak dependency bars with the focus region in gold, most-recent-complete-year card |
| Info | Placeholder — still to be built |

`Visão Geral` and `Info` still carry the original placeholder in the content area.

## Theme

`PistaDigital.Report/StaticResources/RegisteredResources/PistaDigitalTheme.json`:
navy `#001F44`, gold `#FFAD00`, link `#2066BC`, ink `#1D2127`, hairline `#4E4F50`,
Arial (the site uses Montserrat; the report uses Arial so it renders the same on any machine and in the Service), 0 px corner radius, no shadows, navy table headers.

## `PistaDigital.pbit`

**Out of date.** It still embeds the original single-table placeholder model, not
the semantic model above. Export a fresh one from Desktop (File → Export →
Power BI template) once the project opens correctly.

## Source table naming

Every indicator writes `public.ine_<varcd>_ds`, which is what this model reads.
`tests/test_ine_annual.py` and `tests/test_ine_monthly.py` assert both the name
and that each flow's DDL creates that same table.
