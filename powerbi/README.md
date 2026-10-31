# Pista Digital – Power BI template

Power BI Project (PBIP / PBIR) following
[design/pistadigital.uevora.pt-DESIGN.md](../design/pistadigital.uevora.pt-DESIGN.md),
over the INE indicators produced by [flows-code](../flows-code/README.md).

## Open

1. Power BI Desktop → Options → Preview features → enable **Power BI Project (.pbip) save option**
   and **Store reports using enhanced metadata format (PBIR)**.
2. Open `PistaDigital.pbip`, `dashboards/sazonalidade.pbip` or `dashboards/turismo_alentejo.pbip`
   (see *Turismo Alentejo report*).
3. Sign in to PostgreSQL with the database user when prompted (see Connection).

## Connection

Every table reads the PostgreSQL database the flows write to with Power BI's
built-in **PostgreSQL connector** (`PostgreSQL.Database(Servidor, BaseDados)`), and
the model is refreshed in the Power BI Service through the on-premises data
gateway cluster `pistadigital`. Two Power Query parameters hold the target;
credentials are supplied by Power BI itself and never stored in these files:

| Parameter | Matches | Example |
|---|---|---|
| `Servidor` | `PISTA_DB_HOSTNAME`:`PISTA_DB_PORTNUMBER` | `pistadb.pistadigital.uevora.pt:30392` |
| `BaseDados` | `PISTA_DB_NAME` | `pista` |

- **Power BI Desktop:** nothing to install; sign in with the database user when
  prompted (*Database* authentication).
- **Power BI Service:** in the `pistadigital` gateway cluster, add a **PostgreSQL**
  connection with server = `Servidor`, database = `BaseDados` and the database
  credentials. Then, in the semantic model settings → *Gateway and cloud
  connections*, map the PostgreSQL data source to it. An ODBC connection does not
  match this source and the refresh fails.

The model imports **all of Portugal**. The territory is chosen in the report: the
existing pages carry a page filter `'Região NUTS II'[NUTS II] = "Alentejo"`, and
Portugal is the same measure with the geography filters removed (see
*Comparação territorial*). The municipal indicators use NUTS 2013, where Alentejo
still includes Lezíria do Tejo; `Geografia[NUTS II (2024)]` gives the current
delimitation. 0012093 is published in NUTS 2024.

What the flows store, and what the queries keep, is described in *INE totals and
detail* below.

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

The PostgreSQL/gateway connection above is not a blocker: the model is import mode, so
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

The model lives in `dashboards/sazonalidade.SemanticModel` and is a star schema:
hidden fact tables, conformed dimensions, every measure in `_Medidas`, and four
calculation groups for comparisons (focus município, territory, time, peers).
`dashboards/turismo_alentejo.SemanticModel` is a copy for the *Turismo Alentejo*
report: only `.platform` (name and `logicalId`) differs. Apply every model change to
both and check with `diff -r` that `definition/` stays identical. It is built to serve the seven dashboards in
[`mockups/`](mockups/README.md) (see *Mockup coverage*).

### Conventions

- **Measures** are PascalCase without accents (`DormidasPorKm2`,
  `EstadaMediaTipo`); domain acronyms stay as written (`RevPAR`, `YoY`,
  `MoM`, `HHI`). Visuals keep a readable label through each field's display name.
- **Tables and dimension columns** keep readable Portuguese names.
- **Fact tables** are named after the indicator; the INE code and source table are
  in the description. Every fact column is hidden (`summarizeBy: none`): visuals
  slice by dimensions and aggregate through measures. The model has
  *discourage implicit measures* on (required by the calculation groups).
- **Display folders** in `_Medidas`: Território, Oferta, Procura\Dormidas,
  Procura\Hóspedes, Procura\Estada média, Desempenho, Oferta e procura, Mercados,
  Pressão turística, Sazonalidade, Comparação entre pares, Formatação\….

### INE totals and detail

The flows keep, for every breakdown, INE's published **total row** and the most
detailed categories (README of the repository, *Accommodation flows*). Because INE
suppresses many municipal values, the detail does **not** add up to the total.
The queries therefore keep both, and each dimension carries a hidden `Nível`:

| Dimension | Nível 1 | Nível 2 | Nível 3 |
|---|---|---|---|
| `Tipo de alojamento` | Total | categoria detalhada | — |
| `Segmento de alojamento` | Total | segmento | — |
| `Residência` | Total | Estrangeiro | Portugal, cada país estrangeiro |

Every base measure sums only the **most aggregate level visible** in the filter
context (`MIN([Nível])`): with no filter on the dimension it returns the published
Total; filtered to Hotelaria it sums the Hotelaria categories; `Tipo de residente =
Não Residentes` reads the `Estrangeiro` row, not the sum of the countries. Above the
municipality, totals are sums of the published municipal values (lower bounds where
INE suppressed a value). Ratios are never summed: estada média is dormidas ÷
hóspedes (the published estada média tables 0009880 and 0011140 are not loaded:
they are the same ratio and cannot be aggregated), and `RevPAR` is the
room-weighted mean of the published municipal values.

Geographic aggregate rows are dropped (`municipio <> "Total"`, `nuts_ii <> "Total"`),
so no sum counts a night once per level. Municipal facts keep only their keys,
categories and values: the geography columns live in `Geografia` alone. Portugal in the NUTS II monthly tables is
the sum of the regions.

### Fact tables

| Tabela | INE | Grão | Medida base |
|---|---|---|---|
| Superfície das unidades territoriais | 0008350 | Município / ano | `SuperficieKm2` |
| Dormidas por país de residência | 0009183 | Município / ano / residência | `DormidasResidencia` |
| Hóspedes por país de residência | 0009930 | Município / ano / residência | `HospedesResidencia` |
| Estabelecimentos de alojamento turístico | 0009873 | Município / ano / tipo | `Estabelecimentos` |
| Quartos em alojamento turístico | 0009874 | Município / ano / tipo | `Quartos` |
| Hóspedes por tipo de alojamento | 0009876 | Município / ano / tipo | `HospedesTipo` |
| Dormidas por tipo de alojamento | 0009877 | Município / ano / tipo | `DormidasTipo` |
| Rendimento médio por quarto | 0009929 | Município / ano / tipo | `RevPAR` |
| Dormidas mensais por segmento | 0010735 | Município / mês / segmento | `DormidasMensaisSegmento` |
| Hóspedes mensais por segmento | 0010736 | Município / mês / segmento | `HospedesMensaisSegmento` |
| Dormidas mensais por tipo de alojamento (NUTS 2013) | 0009808 | NUTS II / mês / tipo | `DormidasMensaisTipo` |
| Hóspedes mensais por tipo de alojamento (NUTS 2013) | 0009812 | NUTS II / mês / tipo | `HospedesMensaisTipo` |
| Hóspedes mensais por tipo de alojamento (NUTS 2024) | 0012093 | NUTS II / mês / tipo | `HospedesMensaisTipoNuts2024` |

### Dimensions

- **Ano** and **Calendário** (daily `Data`, marked as date table; `Ano` filters it).
- **Geografia** — loaded in Power Query from the distinct geography of the
  municipal INE tables (not a DAX copy of the facts). Município grain, all of Portugal: `NUTS I | NUTS II | NUTS III |
  Distrito | Município`, plus `NUTS II (2024)` (Lezíria do Tejo, Oeste and Médio
  Tejo → Oeste e Vale do Tejo; AML → Grande Lisboa / Península de Setúbal),
  `Território turístico` (Alqueva, Costa Vicentina, Comporta, Património UNESCO,
  Serra de São Mamede — edit the `TerritoriosTuristicos` query; the Lisbon split
  is the `PeninsulaSetubal` list) and `Litoral ou interior` (Alentejo only). Hierarchy NUTS II
  › NUTS III › Município. The NUTS 2024 Alentejo is `Geografia[NUTS II (2024)] =
  "Alentejo"`; the NUTS II monthly tables (0009808/0009812) only exist in NUTS 2013,
  so for NUTS 2024 monthly nights use the municipal `DormidasMensaisSegmento`.
- **Região NUTS II** — all NUTS II regions with a `Versão NUTS` column (2013 for
  `Geografia`, 0009808 and 0009812; 2024 for 0012093, whose keys start `2024|`).
  «Alentejo» exists in both versions with different territories: filter
  `Versão NUTS` when a visual mixes them. The NUTS II monthly tables hang off this
  dimension only, so município or NUTS III slicers do not filter them.
- **Tipo de alojamento** — tipo › subtipo › classificação (stars), keyed by
  `TipoKey`, across the nine indicators that publish them; the NUTS II monthly
  tables have no classificação and read «Total».
- **Segmento de alojamento** — Total, Hotelaria, Alojamento local, TER e habitação.
  It filters the monthly segment tables directly and the annual ones through
  `Tipo de alojamento` (snowflake), so one slicer drives both.
- **Residência** — local de residência, `Tipo de residente` (Residentes / Não
  Residentes / Total) and `Mercado individual` (named foreign countries: the
  universe of HHI, top 3 and growing markets). Portugal has no breakdown, so it
  sits at the country level: «Portugal + Espanha» sums both.

### Comparisons: calculation groups and `Ano base`

Instead of a «Portugal», «região», «índice» or «pares» copy of each measure, four
calculation groups apply to any measure (put the column on a slicer, legend,
matrix columns or a visual filter). They modify every measure in the visual, so in
a scatter they apply to both axes.

| `Foco municipal` (30) | `Comparação territorial` (20) | `Comparação temporal` (10) | `Comparação entre pares` (5) |
|---|---|---|---|
| Contexto atual | Seleção · Sub-região · Região · Portugal | Valor · Valor no ano base | Pares com dados |
| Município em foco | Peso na região · Peso em Portugal | Diferença face ao ano base | Média dos pares |
| | Diferença face à região / a Portugal | Variação face ao ano base | Posição no grupo |
| | Especialização face a Portugal | Índice (ano base = 100) | |

With items of several groups in one visual, the higher precedence is the outer
call: `Portugal` + `Variação face ao ano base` is the variation of Portugal, and
`Município em foco` + `Diferença face à região` is that difference for the focus
município. The reverse nesting is not available: `Peso em Portugal` +
`Diferença face ao ano base` divides the two differences, it is not the change in
the share. `Município em foco` evaluates any measure (text included) for the
`Município selecionado` whatever the `Geografia` filter, so a KPI of the focus
município sits next to a chart of its peers.

Two rules make them safe on any measure:

- Each item evaluates the measure inside `CALCULATE(…, REMOVEFILTERS(<own group>))`,
  so the item is applied once, to the measure as a whole: a ratio such as
  `NoitesPorQuarto` is compared as a ratio, never rebuilt from shifted parts.
- Text measures (`Cor…`, `Subtitulo…`, `MesPicoDormidas`, `MesMaisFracoDormidas`,
  `QuadranteMercado`, `LeituraGapOfertaProcura`) pass through unchanged (except in
  `Foco municipal`), and keep their own format string.

`Ano base` is a disconnected table: «Ano anterior» (also when nothing is selected)
or a fixed year. Time items need a single year in context and return blank
otherwise. Peer items need a single `Município selecionado` and compare it with the
municipalities of its NUTS III that publish the measure.

Measures already bound to report visuals (`DormidasResidenciaYoY`,
`HospedesResidenciaAnoAnterior`, `PosicaoParesRevPAR`, …) are one-line wrappers,
`CALCULATE([Base], <group>[<column>] = "<item>")`, so each comparison is defined once.
For new visuals use the items directly. The exception is a scatter, where an item
would change both axes: `DormidasTipoYoY`, `DormidasMensaisTipoYoY`, `QuartosYoY`
and `CrescimentoHospedesMercado` are explicit growth axes.

### `_Medidas` highlights

| Need | Measures |
|---|---|
| Oferta | `Estabelecimentos`, `Quartos`, `QuartosPorEstabelecimento`, `HospedesPorEstabelecimento`, `QuotaQuartosTipo` (peso AL/TER, mix) |
| Procura | `DormidasTipo`, `HospedesTipo`, `EstadaMediaTipo`, `QuotaDormidasTipo`, `EstadaMediaMensalTipo` (NUTS II) |
| Oferta e procura | `NoitesPorQuarto` (indicador de referência), `GapOfertaProcura` (p.p. desde o ano base; ≥ 20 quartos), `LeituraGapOfertaProcura` |
| Desempenho | `RevPAR` (ponderado por quartos), `ReceitaEstimadaAlojamento` (RevPAR × quartos × 365), `OcupacaoEstimada` |
| Mercados | `QuotaDormidasResidencia` / `QuotaHospedesResidencia` (peso interno, quota internacional), `QuotaDormidasMercadoEstrangeiro`, `HHIMercados`, `PesoTop3Mercados`, `CrescimentoHospedesMercado`, `MercadosEmCrescimento`, `QuadranteMercado` + `ReferenciaCrescimentoHospedes` / `ReferenciaEstadaMedia` |
| Sazonalidade | `QuotaMesDormidas` (perfil mensal), `IndiceSazonalidadeMensal` (mês máximo = 100), `MesPicoDormidas`, `MesMaisFracoDormidas`, `DormidasMesPico`, `RacioPicoVale`, `QuotaDormidasJunSet`, `QuotaDormidasJulSet`, `GiniMensal`, `TaxaSazonalidade`, `IndiceSazonalidadePico` |
| Pressão e pares | `DormidasPorKm2`, `QuartosPorKm2`, `PercentilPressao`, peers through *Comparação entre pares* (same NUTS III); `EmGrupoDePares` (visual filter = 1: only the focus município's NUTS III) |
| Metadados | `DataAtualizacaoDados`, `AnoBase`, `Subtitulo…`, `Cor…` |

Seasonality measures read the municipal 0010735, so they work for a concelho, a
region in either NUTS version, and Portugal; they need the 12 months where stated.

### Mockup coverage

| Dashboard | Visual | Model |
|---|---|---|
| 01 Pulso | KPIs vs Portugal | base measures + *Portugal*; quota nacional = *Peso em Portugal*; variação = *Variação face ao ano base*; p.p. = *Diferença face ao ano base* |
| | Sazonalidade mensal vs 2019, mês × ano | `DormidasMensaisSegmento` / `DormidasMensaisTipo` by `Calendário[Mês]`, `Ano` |
| | Variação por NUTS III, territórios-chave | *Variação face ao ano base* on `DormidasTipo` by `Geografia[NUTS III]` / `[Território turístico]` |
| | Índice 2019 = 100, posicionamento NUTS II | *Índice (ano base = 100)* with `Ano base` = 2019; *Variação face ao ano base* on `DormidasMensaisTipo` × `EstadaMediaMensalTipo` by `Região NUTS II` |
| | Mix de tipologias, indicadores de sazonalidade | `QuotaQuartosTipo` by segmento × *Seleção/Portugal*; `RacioPicoVale`, `QuotaDormidasJulSet`, `QuotaDormidasJunSet`, `GiniMensal` |
| 02 Raio-X | KPIs, pares, calendário, mercados, evolução | `DormidasPorKm2`, `QuartosPorKm2`, `QuotaQuartosTipo` (AL), `MesPicoDormidas`; `IndiceSazonalidadeMensal`; `QuotaHospedesResidencia` × *Diferença face à região*; *Índice* × *Seleção/Região* |
| 03 Radar | KPIs, matriz, principais mercados, onde dorme, especialização, quadrantes | `QuotaDormidasResidencia`, `HHIMercados`, `PesoTop3Mercados`, `MercadosEmCrescimento`; `CrescimentoHospedesMercado` × `EstadaMediaResidencia` × `DormidasResidencia`; `QuotaDormidasMercadoEstrangeiro`; `QuotaHospedesResidencia` × *Especialização face a Portugal*; `QuadranteMercado` |
| 04 Oportunidades | KPIs, gap, quotas, índice 2015, RevPAR por classificação, dimensão × utilização | `NoitesPorQuarto`, `QuartosPorEstabelecimento`, `RevPAR` by `Classificação`, `ReceitaEstimadaAlojamento`; `GapOfertaProcura`; `QuotaQuartosTipo` / `QuotaDormidasTipo`; *Índice* with `Ano base` = 2015 |
| 05 Em números | capítulos, mapa, tabela | *Índice*, *Peso em Portugal*, `QuotaMesDormidas` by `Litoral ou interior`, `QuotaDormidasResidencia`; `DormidasPorKm2`; matrix of base measures by município |
| 06 Barómetro | KPIs do mês, perfil, YoY por mês, calendário, margem | `DormidasMensaisSegmento`, `EstadaMediaMensalSegmento`, *Peso na região*, `MesMaisFracoDormidas`; `QuotaMesDormidas` × *Seleção/Região/Portugal*; *Variação face ao ano base* on `DormidasMensaisSegmento`; matrix `QuotaMesDormidas` × *Seleção · Região · Diferença face à região* |
| 07 Noites e Quartos | procura, oferta, equilíbrio | base measures by `Segmento`, `Classificação`, `NUTS III`; `NoitesPorQuarto`, `GapOfertaProcura`, `HospedesPorEstabelecimento`; *Índice* (2015) on dormidas and quartos; *Variação face ao ano base* on the concelho scatter |

Not in the INE tables (dashed panels in the mockups): proveitos, ADR, ocupação-cama/
quarto, população residente, RNT/RNAL, SIBS, reputação online. «conf.» for
confidential values is a visual setting: measures return blank, never zero.

### Disconnected tables

`Município selecionado`, `Sub-região em foco`, `Métrica de pressão` and `Ano base`
have no relationships on purpose. The focus tables carry `NUTS II` so their slicers
can be limited to a region (the existing ones are, to Alentejo). `Município
selecionado` is keyed by `GeoKey`, and repeated names (INE has two «Lagoa») carry
their NUTS III in parentheses.

### Text handling

The source columns are `bpchar`/`CHAR`, which PostgreSQL blank-pads. Every text
column is trimmed in Power Query, otherwise the dimension keys would not match.

### Validating

The TMDL is maintained directly (in Desktop or by hand). After a change:

```bash
python3 powerbi/tools/validate_semantic_model.py
```

The validator checks that every relationship, column and measure reference
resolves, that every table is referenced from `model.tmdl`, and that DAX and M
expressions are balanced. It does not replace opening the model in Power BI Desktop.

Without Power BI Desktop the model is checked only structurally: the validator,
plus the reference checks run when editing it. DAX and M are not executed, and the
calculation-group TMDL (`ordinal`, `formatStringDefinition`, no partition) follows
Microsoft's TMDL conventions but has not been loaded by Desktop or by Microsoft's
`TmdlSerializer`. Open and save the project in Desktop before the first publish.

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

## Turismo Alentejo report

`dashboards/turismo_alentejo.pbip` builds the seven dashboards of
[`mockups/`](mockups/README.md) over its own copy of the model, with the mockup
theme (`powerbi_tema_alentejo.json`, registered as `Turismo_no_Alentejo.json`).

- **Pages** are 1280 px wide, as tall as the mockup (980–1830 px) and shown *fit to
  width*, so they scroll like the HTML. Each page repeats a header (brand, horizontal
  page navigator, anil rule), the title block and a footer with `DataAtualizacaoDados`.
- **Pages:** Início, Pulso (visão geral and Alentejo e Portugal on one page), Raio-X,
  Mercados, Oportunidades, Em números, Barómetro, and Noites e Quartos as three
  pages (Procura in the navigator; Oferta and Equilíbrio are hidden and reached with
  the Procura / Oferta / Equilíbrio buttons).
- **Territory:** every data visual carries a visual-level filter
  `'Região NUTS II'[NUTS II] = "Alentejo"` (NUTS 2013) instead of a page filter, so a
  visual can opt out (the NUTS II scatter on Pulso). Portugal and the other
  comparisons come from the calculation groups as visual filters or series.
  On Pulso the «Só NUTS 2024» slicer narrows the municipal indicators to
  `Geografia[NUTS II (2024)] = "Alentejo"`; the NUTS II monthly tables stay NUTS 2013.
- **KPI tiles:** a framed text box with the label, a card with the value and up to
  two small cards below. These are the same measure with *Variação face ao ano base*,
  *Portugal*, *Média dos pares*, etc. as visual filters. Deltas are olive, and red
  when negative. Dashed «Nova fonte» tiles mark indicators that are not in the INE tables.
- **Raio-X:** the município comes from `Município selecionado`. The KPIs, calendar,
  markets and evolution use *Município em foco*; the peer bars and the map use
  `EmGrupoDePares = 1` and colour the focus município with `CorMunicipioEmFoco`.
  Barómetro filters `Geografia[Município]` directly (no peers).
- **Em números:** the five chapters are bookmarks (group *Capítulos*, data not
  captured) that show one chapter's text, chart and buttons and hide the others.
  The tab and *Capítulo anterior/seguinte* buttons call them.
- **Saved selections:** Ano = 2025, Município = Évora, Segmento = Hotelaria,
  Mês = agosto, `Ano base` = 2020 on Oportunidades (as in the mockups). Change them
  in Desktop when a new year is loaded. Charts over years or months ignore the
  year/month slicer (edit interactions). Comparison years fixed by the mockups
  (2015 = 100, 2019 = 100, 2019 vs ano, 2020 →) are visual filters on `Ano base`.
- **Not reproduced:** the dashed reference lines of the market matrix (the
  Alentejo means are shown as cards below it), the «Centro» peer line of the Pulso
  index, the «conf.» label (confidential values are blank), drill-through from
  *Exploração livre*, and colour by gap in the dimension × use scatter.

The report was generated and checked structurally (references, calculation-item
names, interactions, bookmarks, layout overlaps), without Power BI Desktop. Open
and save it in Desktop once: Desktop normalises the PBIR files and reports any
formatting property it does not accept.

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
