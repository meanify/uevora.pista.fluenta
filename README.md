# Fluenta Pista Flows

Fluenta means flows, currents, streams in Latin. This project moves data from
LimeSurvey and INE into PISTA Digital.

This project has multiple components:
- **Airflow**: scheduling and deployment configuration in [k8s/airflow](k8s/airflow).
- **Flows Code**: Python ETL modules, command-line tools, and DAGs in [flows-code](flows-code).
- **Power BI**: report and semantic model definitions in [powerbi](powerbi).

## Contents

- [Quick start](#quick-start)
- [Supported indicators](#supported-indicators)
- [INE command-line interface](#ine-command-line-interface)
- [Configuration and Airflow](#configuration)
- [Deploying to Airflow](#deploying-to-airflow)
- [INE troubleshooting](#ine-troubleshooting)
- [Lime Survey flows](#lime-survey-flows)
- [INE implementation reference](#ine-implementation-reference)
- [Debugging either CLI](#debugging-either-cli)

There are two families of flows:
- **Lime Survey flows** — export survey answers and load them into PostgreSQL ([module](flows-code/pistadigital/flows/limesurvey_flows.py), [CLI](flows-code/lime_flows.py))
- **INE flows** — extract indicators from the INE public API and load them into PostgreSQL (see [supported indicators](#supported-indicators)).

Indicator-specific INE and LimeSurvey flows live in
[`flows-code/pistadigital/flows`](flows-code/pistadigital/flows); shared
processing and helper modules remain in
[`flows-code/pistadigital/utils`](flows-code/pistadigital/utils).

## Quick start

### Requirements

- Python **3.13.2 or newer**, as declared in [pyproject.toml](flows-code/pyproject.toml).
- Network access to the INE API at `https://www.ine.pt`.
- For database output: a reachable PostgreSQL instance and credentials with
  `CREATE` permission in the target schema and `SELECT`, `INSERT`, and `DELETE`
  permissions on the target table.
- Airflow is only needed to run the DAG, not the standalone CLI.

From the workspace root, create an environment and install the runtime
dependencies:

```bash
cd flows-code
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python ine_flows.py -i 9929 -y 2024 --csv
```

This writes `/tmp/ine_0009929_2024_tratado.csv` by default without
connecting to PostgreSQL. No credentials are required for this example.
All commands below assume you are in `flows-code` with the environment active.
On subsequent visits, activate the existing environment instead of recreating
it. Alternatively, `uv sync` installs the dependencies from
[pyproject.toml](flows-code/pyproject.toml), including Airflow; use `uv run python` instead
of `python` with that environment.

### Supported indicators

| Code | Description | Period | PostgreSQL table |
| --- | --- | --- | --- |
| `0012093` (or `12093`) | Hóspedes por tipo de alojamento (NUTS-2024 I/II) | Monthly | `ine_0012093_ds` |
| `0008350` (or `8350`) | Superfície das unidades territoriais | Annual | `ine_0008350_ds` |
| `0009183` (or `9183`) | Dormidas por local de residência | Annual | `ine_0009183_ds` |
| `0009808` (or `9808`) | Dormidas por tipo de alojamento (NUTS I/II) | Monthly | `ine_0009808_ds` |
| `0009812` (or `9812`) | Hóspedes por tipo de alojamento (NUTS-2013 I/II) | Monthly | `ine_0009812_ds` |
| `0009873` (or `9873`) | Estabelecimentos de alojamento turístico | Annual | `ine_0009873_ds` |
| `0009874` (or `9874`) | Quartos em estabelecimentos de alojamento turístico | Annual | `ine_0009874_ds` |
| `0009876` (or `9876`) | Hóspedes por tipo de alojamento | Annual | `ine_0009876_ds` |
| `0009877` (or `9877`) | Dormidas por tipo de alojamento | Annual | `ine_0009877_ds` |
| `0009880` (or `9880`) | Estada média por tipo de alojamento | Annual | `ine_0009880_ds` |
| `0009929` (or `9929`) | Rendimento médio por quarto | Annual | `ine_0009929_ds` |
| `0009930` (or `9930`) | Hóspedes por local de residência | Annual | `ine_0009930_ds` |
| `0011140` (or `11140`) | Estada média por local de residência | Annual | `ine_0011140_ds` |
| `0010735` (or `10735`) | Dormidas por segmento de alojamento (NUTS-2013) | Monthly | `ine_0010735_ds` |
| `0010736` (or `10736`) | Hóspedes por segmento de alojamento (NUTS-2013) | Monthly | `ine_0010736_ds` |

All listed indicators are registered in the CLI. Monthly indicators accept
`--year` with either `--month` or `--all-months`, or `--all-years-months` for
all published periods. `--all-years` remains annual-only.

All registered flows now define label columns as `VARCHAR(n)`, preserving
their existing length limits without PostgreSQL's fixed-width space padding.
Monthly `mes` codes remain `CHAR(2)`. The schema descriptions below describe
the originally supplied tables; their `CHAR`/`bpchar` label types are superseded
by `VARCHAR` in the flow definitions.
For existing `public.ine_<code>_ds` tables, run
[the label migration](scripts/migrate_ine_labels_to_varchar.sql) in one
transaction. It removes trailing spaces, preserves lengths, row counts and
primary keys, skips missing/already-migrated tables, and leaves legacy tables
without the `_ds` suffix untouched. Dependent views or lock contention cause
the migration to fail rather than being dropped or bypassed. Refresh Power BI
after migration to replace cached padded labels.

Indicator 12093 uses an approved new schema modeled on 9808, with metric
`hospedes REAL`, four `CHAR(64)` label dimensions, `ano INTEGER`, `mes CHAR(2)`,
and nullable date audit columns. Its primary key includes every dimension,
year and month. Labels come from its own NUTS-2024 metadata, not NUTS-2013.
Published periods verified on 2026-10-24 span January 2022 through August 2026.
Its [dedicated DAG](flows-code/dags/dags_ine_0012093.py) uses the shared
[factory](flows-code/dags/dags_ine.py) with `monthly=True`, producing
`ine_0012093_<year>_<MM>` for the current and two prior years.

```bash
python ine_flows.py -i 12093 -y 2026 -m 8 --csv
```

Indicator 9812 uses the same approved monthly column/key layout as 12093,
with NUTS-2013 labels and metric `hospedes`. It targets the new
`public.ine_0009812_monthly`, explicitly **not** the existing year-only
`ine_0009812` or the incompatible `ine_0009812monthly` table.
No existing table is migrated or overwritten. Published periods span January
2017 through August 2026. Its [DAG entry point](flows-code/dags/dags_ine_0009812.py)
produces `ine_0009812_<year>_<MM>` using the shared factory.

```bash
python ine_flows.py -i 9812 -y 2026 -m 8 --csv
```

Indicator 10735 preserves the existing `public.ine_0010735` schema:
five NUTS-2013/district/municipality labels plus `segmento_alojamento`, all
`CHAR(64)`, `ano INTEGER`, `mes CHAR(2)`, `dormidas REAL`, and nullable date
audit columns. The primary key includes all dimensions and both period columns.
Published months span January 2020 through August 2026.
Its [DAG](flows-code/dags/dags_ine_0010735.py) creates `ine_0010735_<year>_<MM>`.

```bash
python ine_flows.py -i 10735 -y 2026 -m 8 --csv
```

Indicator 10736 preserves `public.ine_0010736`, with the same dimensions,
lengths, primary key and dates as 10735, but metric `hospedes REAL`.
Its published months also span January 2020 through August 2026.
Its [DAG](flows-code/dags/dags_ine_0010736.py) creates `ine_0010736_<year>_<MM>`.

```bash
python ine_flows.py -i 10736 -y 2026 -m 8 --csv
```

Indicator 9808 uses the existing `public.ine_0009808` schema: `nuts_i`,
`nuts_ii`, `tipo_alojamento`, and `subtipo_alojamento` are `CHAR(64) NOT NULL`,
`ano` is an integer, and `mes` is `CHAR(2) NOT NULL` (`"01"`–`"12"`).
All six columns form the primary key; `dormidas REAL`, `create_date DATE`,
and `update_date DATE` are nullable. Metadata verified on 2026-10-24 lists
January 2017 through August 2026. The API selector is `Dim1=S3A<YYYY><MM>`;
the response key is the corresponding metadata label, for example
`Agosto de 2026`, not `202608`.

```bash
python ine_flows.py -i 9808 -y 2026 -m 8 --csv
python ine_flows.py -i 9808 -y 2026 -m 8 --database
python ine_flows.py -i 9808 -y 2026 -m 8 --database --csv
```

The default CSV is `/tmp/ine_0009808_2026_08_tratado.csv`.
Database replacement filters **both** `ano = 2026 AND mes = '08'`;
other months/years are preserved, empty results keep existing rows, and failed
inserts roll back. When querying this table, always filter both year and
zero-padded month rather than extracting a whole year.

Indicator 9873 uses the supplied `ine_0009873` schema: eight `bpchar(64)`
dimensions, `ano int4`, the nullable `float4` metric
`establecimento_de_alojamento_turistico` (spelling preserved), and nullable
`date` columns `create_date` and `update_date`. The primary key includes all
eight dimensions and `ano`. Like the existing flow, database operations use
the connection's default schema (`public` in the standard PostgreSQL setup).
The flows can load existing tables or create them if missing. The supplied
tables use `public`; configure the connection's default schema/search path
accordingly. The shared writer uses unqualified table names.

Indicator 9874 uses `public.ine_0009874`: eight `bpchar(64)` dimensions,
`ano int4`, the nullable `float4` metric `quartos`, and nullable `date`
columns `create_date` and `update_date`. Its primary key includes all eight
dimensions and `ano`. INE metadata identifies it as annual, with periods
2017–2025 and reference-period selector `Dim1=S7A<year>`.

```bash
python ine_flows.py -i 9874 -y 2025 --csv
python ine_flows.py -i 9874 -y 2025 --database --csv
python ine_flows.py -i 9874 --all-years --database
```

```bash
python ine_flows.py -i 9873 -y 2024 --csv
python ine_flows.py -i 9873 -y 2024 --database --csv
python ine_flows.py -i 9873 --all-years --database
```

The default CSV paths are `/tmp/ine_0009873_2024_tratado.csv` for 2024
and `/tmp/ine_0009873_all_years_tratado.csv` for all available years.

The other new flows retain the supplied annual schemas: `float4` metrics,
nullable `date` audit columns, and a primary key comprising all dimensions
plus `ano`. Residence labels are `bpchar(128)` for 9183 and `bpchar(64)` for
9930 and 11140. Accommodation subtypes are `bpchar(128)` for 9877 and 9880,
and `bpchar(64)` for 9874 and 9876. Indicator 8350 has no category dimension
and allows 128 characters for district/municipality labels.

INE flows with accommodation-type columns apply the former Power BI
replacements before CSV/database output. Case-insensitive `tipo_alojamento` equal to
`alojamento local` sets both `subtipo_alojamento` and `classificacao` to
`Alojamento Local`. Types containing `rural` set both fields to
`Turismo no Espaço Rural e de Habitação`; types containing `habitação` without
`rural` replace only `classificacao`. Other values and `tipo_alojamento` itself
remain unchanged. This applies to 9873, 9874, 9876, 9877, 9880, and 9929;
monthly regional flows 9808, 9812, and 12093 normalize only
`subtipo_alojamento` because they have no `classificacao` column.

Accommodation flows keep the API total `T` (all three accommodation columns
`Total`) and the most detailed categories: `dim_3` codes without
subcategories in the metadata (e.g. `010115`, `0103`, `02`, `03`).
Intermediate codes (`01`, `0101`, …) are dropped. INE suppresses many
municipal values for confidentiality ("…"), so detail rows do not add up to
`T`: use `tipo_alojamento = "Total"` for totals and exclude it for
breakdowns.
Levels below a detail code repeat its own label, so `0103`
stores `Pousadas/Quintas da Madeira` as `classificacao`.

Flows with a `municipio` column keep only rows whose API `geocod` is a
seven-character municipality code, excluding Portugal, NUTS I, II and III
aggregates from both CSV and database output.
This applies to annual flows 8350, 9183, 9873, 9874, 9876, 9877, 9880, 9929,
9930, and 11140, plus monthly municipal flows 10735 and 10736. Regional
flows 9808, 9812, and 12093 have no municipality column and keep only
two-character NUTS II codes, dropping Portugal and NUTS I rows. Segment labels in 10735/10736 are unchanged.
Shared runners apply filtering after validation, and all output modes use the
same result. Normalization that produces duplicate keys fails explicitly;
rows are never silently deduplicated.

Existing stored data is not automatically changed: rerun the desired periods
to replace them with normalized, municipality-only data where applicable.
Filtered-empty periods retain CSV headers and preserve existing database rows.

To rerun **all registered INE flows for every published period**, use
[reload-ine-flows.sh](scripts/reload-ine-flows.sh) from the repository root:

```bash
# Preview the commands (no network or database access):
sh scripts/reload-ine-flows.sh
# Execute database replacements using configured credentials:
sh scripts/reload-ine-flows.sh --database
```

The script discovers indicators from the CLI registry, using `--all-years`
for annual flows and `--all-years-months` for monthly flows. It uses
`.venv/bin/python` by default; set `PYTHON` to an alternative interpreter if
needed. Existing environment variables and the CLI's optional `.env` files
provide database configuration; the script contains no credentials.

Runs are sequential and stop on the first error. Each nonempty period replaces
that period's stored rows transactionally, including removing old geographic
aggregates. This is **not a whole-database reset**: tables are never truncated,
empty results preserve existing data, and periods no longer published by INE
are not deleted. Earlier periods remain committed if a later period fails;
rerunning safely replaces them again. Full-history runs can take a long time.

Metadata verified on 2026-10-24 lists these available annual periods:

| Indicators | Published periods | Previously verified rows before municipality filtering |
| --- | --- | --- |
| 9874, 9876, 9877, 9880 | 2017–2025 | 2025: 8,600 rows per indicator |
| 9930, 11140 | 2018–2025 | 2025: 17,200 rows per indicator |
| 9183 | 2011–2025 | 2025: 17,200 rows |
| 8350 | 2004–2022 | 2022: 344 rows |

All use `Dim1=S7A<year>`, NUTS-2013 geography, and metadata-derived labels.
The new flows reject unpublished periods, foreign-period responses, duplicate
keys, overlong labels, unknown categories, and malformed numeric values before
either output. Missing metrics remain null and zeros are preserved.

```bash
python ine_flows.py -i 9930 -y 2025 --csv
python ine_flows.py -i 11140 -y 2025 --csv
python ine_flows.py -i 9183 -y 2025 --csv
python ine_flows.py -i 9876 -y 2025 --csv
python ine_flows.py -i 9877 -y 2025 --csv
python ine_flows.py -i 9880 -y 2025 --csv
python ine_flows.py -i 8350 -y 2022 --csv
# Requires configured PostgreSQL credentials:
python ine_flows.py -i 9930 -y 2025 --database
```

Default CSV paths always use the padded code and requested year, for example
`/tmp/ine_0009930_2025_tratado.csv` and `/tmp/ine_0008350_2022_tratado.csv`.
All listed indicators also support mocked/tested annual `--all-years` dispatch;
live verification above fetched just one published year per indicator.

## INE command-line interface

### Common CLI behavior

Both [ine_flows.py](flows-code/ine_flows.py) and [lime_flows.py](flows-code/lime_flows.py) use the same
output and diagnostic options:

This table lists only shared flags, not the required source selectors.
**INE requires `-i/--indicator` and one of `-y/--year`, `--all-years`, or
`--all-years-months`;
LimeSurvey requires `-s/--survey`.** See [all INE options](#all-ine-options) and the
[LimeSurvey-specific options](#limesurvey-specific-options) below.
Note that `-i` means **indicator** for INE but **increment** for LimeSurvey;
use the long names when switching between tools to avoid confusion.

| Option | Both tools |
| --- | --- |
| `--csv` | Write CSV only, without connecting to PostgreSQL. |
| `--database` | Write to PostgreSQL without creating an intermediate CSV. |
| `--database --csv` | Write to both outputs, database first (single-year INE fetches once). |
| `-o`, `--output` | Explicit CSV path; requires CSV output and an existing parent directory. |
| `-d`, `--debug` | Debug logs and processing error tracebacks; still executes the requested flow. |
| `-h`, `--help` | Display usage without contacting either service. |

At least one output must be selected for a normal run. Both tools return
`0` on completion (including empty results), `1` for handled processing/output
errors, and `2` for invalid arguments. With both outputs enabled, a CSV error
does not undo a committed database write.

```bash
# INE selects an indicator and a reference period.
python ine_flows.py -i 9929 -y 2024 --csv --output /tmp/ine.csv
python ine_flows.py -i 9929 -y 2024 --database
python ine_flows.py -i 9929 -y 2024 --database --csv

# LimeSurvey selects a survey and an optional response-ID interval.
python lime_flows.py -s 666914 --csv --output /tmp/survey.csv
python lime_flows.py -s 666914 --database
python lime_flows.py -s 666914 --from-response-id 1 --database --csv
```

The output controls are shared; the data semantics remain source-specific:
INE replaces the reference year/month, while LimeSurvey appends responses
and resumes from the database by default when database output is requested.
INE CSV files use commas; LimeSurvey CSV files retain their existing semicolon
format for compatibility with `load`.
LimeSurvey response exports infer column types across the entire CSV rather
than parser chunks, avoiding mixed-type inference warnings for large surveys.
This uses more parsing memory; numeric and text answers remain intact.

From `flows-code`, run `ine_flows.py` with an indicator, a period selector,
and at least one output option. Short indicator codes such as
`9929` and `9873` are accepted.

```bash
# CSV only: no database connection or credentials required.
python ine_flows.py --indicator 9929 --year 2024 --csv

# Optional explicit CSV path (the parent directory must exist).
python ine_flows.py -i 9929 -y 2024 --csv --output /tmp/ine-2024.csv

# PostgreSQL only, or both outputs.
python ine_flows.py -i 9929 -y 2024 --database
python ine_flows.py -i 9929 -y 2024 --database --csv

# Process every annual period listed in INE metadata. CSV output is combined.
python ine_flows.py -i 9929 --all-years --database
python ine_flows.py -i 9929 --all-years --csv
python ine_flows.py -i 9929 --all-years --database --csv \
  --output /tmp/ine-9929-all-years.csv

# Monthly indicators: one month, all published months in a year, or all history.
python ine_flows.py -i 9808 -y 2024 -m 1 --csv
python ine_flows.py -i 9808 -y 2024 --all-months --csv
python ine_flows.py -i 9808 --all-years-months --database --csv \
  --output /tmp/ine-9808-all-months.csv

python ine_flows.py --help
```

### All INE options

| Option | Purpose |
| --- | --- |
| `-i`, `--indicator` | Required indicator code; leading zeros are optional. |
| `-y`, `--year` | Process one reference year, from 1 to 9999; data must be published by INE. |
| `--all-years` | Process every annual period listed in INE metadata; mutually exclusive with `--year`. |
| `--all-months` | Monthly-only: process every published month of `--year`; cannot be combined with `--month` or either all-years flag. |
| `--all-years-months` | Monthly-only: process every published year/month; cannot be combined with `--year`, `--month`, `--all-months`, or `--all-years`. |
| `-m`, `--month` | Single month from 1 to 12; monthly indicators require this with `--year` unless using a monthly batch flag. Rejected for annual indicators. |
| `--database` | Create the table if necessary and replace the requested period. |
| `--csv` | Export records to CSV; overwrites the destination if it already exists. |
| `-o`, `--output` | Custom CSV path; requires `--csv`. The parent directory must exist. |
| `-d`, `--debug` | Enable debug logging and tracebacks for processing failures. |
| `-h`, `--help` | Show usage and exit without fetching records. |

At least one of `--database` or `--csv` is required. They can be combined.
CSV files use comma delimiters and include a header; missing metrics are
exported as empty cells. `--all-years --csv` combines all available annual
periods into one file; without `--output`, the default is
`/tmp/ine_<indicator>_all_years_tratado.csv`. Database writes still replace each
year independently. All-years mode is for annual indicators only.

Monthly batch modes select only periods listed in INE metadata, oldest first;
they do not attempt missing or unpublished months, including in partial years.
`--all-months` fails if the selected year has no published months.
Both modes combine CSV output into one file, with `--output` supported.
Default paths are `/tmp/ine_<indicator>_<year>_all_months_tratado.csv` and
`/tmp/ine_<indicator>_all_years_months_tratado.csv`.
Database replacement remains independent for each year/month, preserving other
periods. Like annual batches, monthly batches stop at the first failure and
return a nonzero status; earlier database commits remain. The combined CSV is
written only after all selected periods succeed, so a processing failure leaves
any existing destination CSV untouched.

Alternatively, run `python -m pistadigital.cli.ine_flows` with the same options.
The container image copies both `ine_flows.py` and `lime_flows.py`; its default
entry point remains LimeSurvey. Rebuild and redeploy the image after renaming
these scripts, including for the Kubernetes DAG that invokes `lime_flows.py`.
The default single-year CSV path is `/tmp/ine_0009929_2024_tratado.csv`.
Database output uses the `PISTA_DB_*` environment variables below; export them
in the shell before running the CLI. Invalid arguments return exit code 2;
API, database, or file-write failures return exit code 1. Use `--debug` for a
traceback. With both outputs requested, database output happens first; a later
CSV failure is reported but does not undo a committed database transaction.

### Replacing periods

`--database` creates the indicator's table if missing, deletes only the
processing period, then inserts the new records **in one transaction**. For
0009929 the table is `ine_0009929_ds`; for 0009812 it is
`ine_0009812_monthly`. The other indicators use `ine_<padded-code>`
without a suffix, as listed above.
Annual replacement filters `ano = <year>`; monthly replacement filters both
`ano = <year> AND mes = '<MM>'`, using a zero-padded month.
Other years and, for monthly runs, other months are preserved.
An insert failure rolls back the deletion as well.
Empty API results warn and **keep existing database records**, rather than
deleting a period with no replacement data.

For example, rerunning `-i 9929 -y 2024 --database` removes stale 2024 records
and inserts the newly fetched 2024 records. It does not delete 2023 or 2025.
It replaces the whole year's dataset, not only rows matching the incoming
primary keys. Existing table definitions are not migrated by
`CREATE TABLE IF NOT EXISTS`.

Do not schedule overlapping CLI and Airflow writes to the same indicator and
period; this implementation does not serialize concurrent runs.

### Python usage

The underlying function returns a Pandas DataFrame and can be called without
the CLI. Importing it does not start a flow.

```python
from pistadigital.flows.ine_0009929_flow import processar_indicador_ine

# CSV only (the default), without a database connection.
df = processar_indicador_ine(ano=2024)

# Replace the year in PostgreSQL, without exporting CSV.
df = processar_indicador_ine(
    ano=2024, exportar_csv=False, gravar_bd=True
)

# Both outputs, using an explicit path.
df = processar_indicador_ine(
    ano=2024,
    exportar_csv=True,
    gravar_bd=True,
    caminho_csv="/tmp/ine-2024.csv",
)

# Transform only: no database writes or CSV output.
df = processar_indicador_ine(ano=2024, exportar_csv=False)
print(df.head())
```

### Adding monthly indicators

Indicator [9808](flows-code/pistadigital/flows/ine_0009808_flow.py) is the monthly
implementation reference. All monthly modules use
[ine_monthly.py](flows-code/pistadigital/utils/ine_monthly.py) for metadata/period
validation, numeric parsing, schema/key checks, and database-first output.
Keep schemas and dimension mappings in the indicator module; do not copy
monthly orchestration. Annual indicators still reject `--month`.

CSV-only live checks on 2026-10-24 verified August 2026 for the new indicators:

| Indicator | CSV rows | Geography |
| --- | --- | --- |
| 12093 | 117 | NUTS-2024 I/II |
| 9812 | 99 | NUTS-2013 I/II |
| 10735 | 1,376 | NUTS-2013 through municipalities |
| 10736 | 1,376 | NUTS-2013 through municipalities |

All four dedicated DAG files use the shared factory, generate one DAG per
year/month (36 per indicator), and retain the monthly refresh schedule.
Deploy each entry point with [dags_ine.py](flows-code/dags/dags_ine.py) and the application
package, including the new monthly runner. Example IDs:
`ine_0012093_2026_08`, `ine_0009812_2026_08`, `ine_0010735_2026_08`,
and `ine_0010736_2026_08`. Unpublished months fail explicitly; no live schema
creation, loading, or deployment was performed during verification.

Register the new module in `pistadigital.cli.ine_flows.INDICATORS`, expose
`MONTHLY = True`, and implement
`processar_indicador_ine(varcd, ano, exportar_csv, gravar_bd, caminho_csv, mes)`.
The CLI requires `--month 1..12` for such modules. Each invocation processes
one year/month. The module must fetch that month's data, include integer `ano`
and a `mes` column matching the DDL (integer or zero-padded `CHAR(2)`), and
include both in its table's primary key. Pass integer year/month arguments to
`replace_period_data(df, TABLE_NAME, CREATE_TABLE_SQL, ano, mes)` from
`pistadigital.utils.ine_output` so replacement deletes only
`ano = <year> AND mes = <month>`, keeping other months and years intact.
Monthly CSV names should include the month to avoid overwriting other periods.
The writer rejects records outside the requested period before touching the
database.

For example:

```bash
python ine_flows.py -i 9808 -y 2024 -m 3 --database
```

That run must replace March 2024 only, preserving February 2024, April 2024,
and March in other years. Unlike the annual flow, omitting `--month` must fail
rather than silently replacing a whole year.

### INE tests

From `flows-code`, using the project's Python environment:

```bash
PYTHONPATH=. python -m unittest discover -s tests -p 'test_ine*.py' -v
```

From the workspace root, using the existing root-level virtual environment:

```bash
cd flows-code && ../.venv/bin/python -m unittest discover -s tests -p 'test_ine*.py' -v
```

Run the complete suite from the workspace root:

```bash
cd flows-code && ../.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Each command starts at the workspace root independently. If you created the
environment inside `flows-code` using Quick start, activate that environment
and use `python` from `flows-code` instead.

Tests use an in-memory SQLite database for transactional replacement and mock
API responses and Airflow registration; they do not modify a live database.
The [Flow tests workflow](.github/workflows/flow-tests.yml) runs the complete
suite on pushes and pull requests using Python 3.13 and `requirements.txt`.
It does not require service credentials or an Airflow installation. The
workflow runs when these files are published to the owning GitHub
repository with GitHub Actions enabled.

## Configuration

### Deploying to Airflow

The Kubernetes manifests in [k8s/airflow](k8s/airflow) deploy the Airflow
stack into the `fluenta` namespace. Before applying them, review the
environment-specific node names, persistent-volume paths, storage classes, and
secret configuration. Provision credentials through Kubernetes Secrets or an
approved secret manager; do not commit credentials or encryption keys.

Create the namespace, then apply storage, access, database, Redis, and mapping
resources:

```bash
kubectl create namespace fluenta --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/airflow/0_secrets_and_volumes.yaml
kubectl apply -f k8s/airflow/1_airflow_rbac.yaml
kubectl apply -f k8s/airflow/2_airflow_postgres.yaml
kubectl apply -f k8s/airflow/3_airflow_redis.yaml
kubectl apply -f k8s/airflow/6_airflow_configmap.yaml
kubectl rollout status deployment/airflow-postgres -n fluenta
kubectl rollout status deployment/airflow-redis -n fluenta
kubectl apply -f k8s/airflow/4_airflow_dbmigration.yaml
kubectl wait --for=condition=complete job/db-migration -n fluenta --timeout=10m
kubectl apply -f k8s/airflow/5_airflow_airflow.yaml
kubectl apply -f k8s/airflow/7_airflow_logcleaner.yaml
```

To deploy or update the project code, place the DAG files from
[`flows-code/dags`](flows-code/dags) in `/opt/airflow/dags` and the complete
[`pistadigital` package](flows-code/pistadigital) in
`/opt/airflow/dependencies/pistadigital`. The supplied manifests mount a
shared Airflow volume at `/opt/airflow` and set
`PYTHONPATH=/opt/airflow/dependencies`; sync the files through your approved
release process or a pod with that volume mounted. For a manual copy from the
repository root:

```bash
POD="$(kubectl get pods -n fluenta -l app=airflow,service=scheduler \
  -o jsonpath='{.items[0].metadata.name}')"
kubectl exec -n fluenta "$POD" -- \
  mkdir -p /opt/airflow/dags /opt/airflow/dependencies
kubectl cp flows-code/dags/. "fluenta/$POD:/opt/airflow/dags"
kubectl cp flows-code/pistadigital "fluenta/$POD:/opt/airflow/dependencies/"
```

Replace stale deployed files as well as copying updates, particularly obsolete
DAG entry points, to avoid duplicate DAG IDs. The package must be available to
both the DAG processor and task workers.

The current Airflow manifest uses an Airflow image based on Python 3.12, while
the DAG virtualenv operators request Python 3.13.2. Make Python 3.13.2
available to task workers before enabling those DAGs; workers also need to
create virtual environments and install the declared requirements. Create the
`pista_db` Airflow connection before running INE DAGs. The LimeSurvey visitor
DAG also expects a `limesurvey` connection with the remote-control URL in Host
and its username and password in Login and Password. See the database
connection fields below.

After deployment, check that Airflow has parsed the DAGs and inspect scheduler
and DAG-processor logs for import errors:

```bash
kubectl get pods -n fluenta
kubectl exec -n fluenta deployment/airflow-scheduler -- airflow dags list
```

Use the Airflow UI or `airflow dags trigger <dag-id>` to test a DAG. Keep it
paused until its connections, Python runtime, package imports, and database
permissions have been verified.

### INE Airflow tasks

Every INE indicator has a thin DAG entry-point file using
[dags_ine.py](flows-code/dags/dags_ine.py). The shared factory owns scheduling, retries,
virtualenv requirements, credentials, task dispatch, and compact status logging.
It registers no DAGs itself and does not fetch metadata or open database
connections at parse time. Each task calls its indicator's
`processar_indicador_ine` with `exportar_csv=False` and `gravar_bd=True`.
Only a status string is returned, never a DataFrame; API/database errors
propagate so Airflow can retry.

Annual entry points are [9929](flows-code/dags/dags_ine_0009929.py),
[9873](flows-code/dags/dags_ine_0009873.py), [9874](flows-code/dags/dags_ine_0009874.py),
[9930](flows-code/dags/dags_ine_0009930.py), [11140](flows-code/dags/dags_ine_0011140.py),
[9183](flows-code/dags/dags_ine_0009183.py), [9876](flows-code/dags/dags_ine_0009876.py),
[9877](flows-code/dags/dags_ine_0009877.py), [9880](flows-code/dags/dags_ine_0009880.py), and
[8350](flows-code/dags/dags_ine_0008350.py). They use
`globals().update(build_indicator_dags("<code>"))`.
Their IDs remain `ine_<padded-code>_<year>` and task arguments are
`[indicator, year]`. They create missing tables and replace only the requested
year transactionally. For 8350 the window is 2020–2022, capped by
`PUBLISHED_YEAR_CAPS` at the last published year in its NUTS-2013 series. Recheck its
metadata before changing that cap. Other flows retain the existing
current-year/two-previous-years window; a task targeting an unpublished year
fails explicitly rather than loading a different year.

The dedicated [9808 DAG file](flows-code/dags/dags_ine_0009808.py) creates IDs
`ine_0009808_<year>_<MM>` for all twelve months of the current year and two
previous years (36 DAGs), using
`globals().update(build_indicator_dags("0009808", monthly=True))`.
Each task receives `[indicator, year, month]` and processes only that month.
Every API request and database replacement targets that explicit
year/month; it does not aggregate monthly data or delete a whole year.
Tasks targeting unpublished months fail explicitly during metadata validation
before fetching records or writing to the database; they never substitute
the latest month. The existing year/month IDs are preserved by this refactor.

The schedule is `0 6 1 * *` (06:00 on the first day of each month, in the
Airflow-configured DAG timezone), with catchup disabled and one retry after
five minutes.

Configure the connection in the Airflow UI with these fields:

| Airflow connection field | Value / environment variable |
| --- | --- |
| Connection ID | `pista_db` |
| Connection type | Postgres |
| Host | `PISTA_DB_HOSTNAME` |
| Port | `PISTA_DB_PORTNUMBER` |
| Database / schema | `PISTA_DB_NAME` |
| Login | `PISTA_DB_USERNAME` |
| Password | `PISTA_DB_PASSWORD` |

Deploy [dags_ine_0009929.py](flows-code/dags/dags_ine_0009929.py),
[dags_ine_0009873.py](flows-code/dags/dags_ine_0009873.py),
[dags_ine_0009874.py](flows-code/dags/dags_ine_0009874.py), and the desired per-indicator
entry-point files listed above to the configured DAG folder.
For **every INE indicator**, deploy
[dags_ine.py](flows-code/dags/dags_ine.py) alongside its entry-point file;
deploying the factory alone registers no DAGs. It replaces the former
`dags_ine_annual.py` helper; remove that obsolete file from deployed DAG folders.
Do not leave older copies of the per-indicator DAG files under other filenames,
as they could register duplicate IDs. Keep the DAG folder on
the scheduler's and workers' Python import path (Airflow's default).
Make the local `pistadigital` source available to workers, for example
by adding the absolute `flows-code` path to the worker's `PYTHONPATH`.
The worker must provide the Python version configured in the operator
(`3.13.2`) and be able to create its virtual environment and install its
requirements. Do not deploy only the DAG without its imported Python modules.

List available DAG IDs and trigger one of the generated years:

```bash
airflow dags list
# Example when 2024 is within the current-year/two-previous-years window:
airflow dags trigger ine_0009929_2024
airflow dags trigger ine_0009873_2024
airflow dags trigger ine_0009874_2025
airflow dags trigger ine_0009930_2025
airflow dags trigger ine_0008350_2022
airflow dags trigger ine_0009808_2026_08
```

Configure the Airflow connection `pista_db`; its fields are resolved at task
runtime and supplied through `PISTA_DB_*` environment variables. The
`pistadigital` package must be importable in the worker environment (the task
uses `system_site_packages=True`). For standalone Python callers, CSV export
remains enabled by default and can be disabled with `exportar_csv=False`.
Database writes are opt-in with `gravar_bd=True`; CSV-only or processing-only
calls do not create a table or require database credentials.

### Environment Variables

The following environment variables should be set for database operations.
Both CLIs load the optional repository-root `.env`, followed by
`flows-code/.env`, without overriding variables already set. Root `.env`
values therefore take precedence over duplicate values in `flows-code/.env`.
You can also export variables in your shell or, from `flows-code`,
`source set-variables.sh`. Both `.env` and `set-variables.sh` are git-ignored.
Under Airflow, settings are injected from the `pista_db` connection.

Used by **both** families of flows:

- **PISTA_DB_HOSTNAME**: Host of the PISTA Digital database, such as 'pistadb.pistadigital.uevora.pt' (mandatory).
- **PISTA_DB_PORTNUMBER**: Database port number (mandatory).
- **PISTA_DB_NAME**: Database name (mandatory).
- **PISTA_DB_USERNAME**: Username to access the database. Needs write permissions (mandatory).
- **PISTA_DB_PASSWORD**: Password required to authenticate the user (mandatory).

For a local shell, use your actual connection details in place of the example
values. Read the password without putting it in shell history:

```bash
export PISTA_DB_HOSTNAME='localhost'
export PISTA_DB_PORTNUMBER='5432'
export PISTA_DB_NAME='pista'
export PISTA_DB_USERNAME='pista_writer'
printf 'Database password: '
read -r -s PISTA_DB_PASSWORD
printf '\n'
export PISTA_DB_PASSWORD

python ine_flows.py -i 9929 -y 2024 --database
unset PISTA_DB_PASSWORD
```

These commands work in Bash and Zsh. Never commit credentials or put them in
CLI arguments. Both CLIs automatically load the optional `.env` files described
above. Existing Airflow runs obtain credentials from the
connection instead of these interactive commands.

Used by the **Lime Survey** flows only:

- **LIME_SURVEY_URL**: The Lime Survey website, such as 'https://limesurvey.pistadigital.uevora.pt/index.php/admin/remotecontrol' (mandatory).
- **LIME_SURVEY_USERNAME**: The username to access Lime Survey. Needs permission to read surveys (mandatory).
- **LIME_SURVEY_PASSWORD**: Password for the specified user (mandatory).
- **PISTAFLOWS_EXPORTS_PATH**: Path to the folder where exports will be available.

For INE periods, use the CLI's explicit `--year` and, for monthly
indicators, `--month` arguments rather than `INE_YEAR` or `INE_MONTH`.

## INE troubleshooting

| Problem | Action |
| --- | --- |
| `No module named pistadigital` | Run from `flows-code`, or add its absolute path to `PYTHONPATH`. |
| Missing `requests`, `pandas`, `sqlalchemy`, or `psycopg2` | Activate the intended environment and run `python -m pip install -r requirements.txt`. |
| `Missing database settings` | Set all five `PISTA_DB_*` variables in the process environment or `flows-code/.env`; use `--csv` alone if no database output is needed. |
| Invalid port | Use an integer between 1 and 65535. |
| Connection refused, authentication failure, or insufficient privileges | Check database address, network access, credentials, schema search path, and table permissions. |
| Unsupported indicator or `--month` rejected | See the supported-indicator table. Monthly indicators require `--year` and `--month`; annual indicators reject `--month`. |
| Empty result warning | Check the reference year and whether INE has published that period. Existing database records are kept. |
| API timeout, HTTP error, or invalid JSON | Retry later or inspect network/API availability; rerun with `--debug` for details. |
| CSV path does not exist or is not writable | Create the parent directory and check write permissions. |
| CSV failed after a database write | The database transaction may already be committed; rerun with `--csv` only to regenerate the file. |
| Existing table has incompatible columns or types | Apply a deliberate schema migration; table creation does not update an existing schema. |

```bash
python ine_flows.py -i 9929 -y 2024 --database --debug
```

Exit codes: `0` for completion (including empty results), `1` for handled
processing/output failures, and `2` for invalid command-line arguments.
Avoid sharing debug logs without checking them for sensitive data.

## Lime Survey Flows

The logic was implemented to extract data from Lime Survey and to export it to the PostgreSQL database.

### Mappings configuration

Mappings are important to translate survey fields into database columns. All surveuys need to be mapped to it's correpondiong database table.

```bash
survey_mappings = {
    "666914": {
        "table_name": "perfil_visitante_individual_do_posto_turismo_test_load",
        "columns": {
            "id":"id",
            "submitdate":"data_submissao",
            "lastpage":"ultima_pagina",
            "startlanguage":"idioma_inicial",
            "seed":"semente",
            "token":"codigo_acesso",
            "G02Q04":"local_de_residencia",
            "G00Q19":"data",
            "G02Q05":"concelho",
            "G02Q06":"provincia",
            "G02Q07":"pais",
            "G02Q02":"idade",
            "G02Q03":"genero",
            "G02Q08":"nivel_de_escolaridade",
            "G02Q08[other]":"outro_nivel_de_escolaridade",
            "G02Q12":"com_quem_viaja",
            "G02Q12[other]":"com_quem_viaja_outros",
            "G02Q15":"primeira_vez_no_concelho",
            "G02Q14":"noites_no_concelho",
            "G02Q19":"em_que_local_pernoita",
            "G02Q19[other]":"em_que_local_pernoita_outro",
            "G02Q09":"motivo_da_visita",
            "G02Q10":"motivo_primeira_visita",
            "G02Q10[other]":"outro_motivo_primeira_visita",
            "G01Q20":"motivo_segunda_visita",
            "G01Q20[other]":"outro_motivo_segunda_visita",
            "G02Q11":"obtencao_conhecimento_do_concelho",
            "G02Q11[other]":"obtencao_conhecimento_do_concelho_outro",
            "G02Q13":"tipo_de_informacao_que_solicita_no_posto",
            "G02Q16":"curiosidades_sobre_o_visitante",
            "G02Q17":"reclamacoes_do_visitante",
            "G02Q18":"comentarios",
            "firstname":"primeiro_nome",
            "lastname":"ultimo_nome",
            "email":"email",
        },
    },
}
```

### Configuration and output selection

Both command-line tools load the optional repository-root `.env` file on startup,
falling back to `flows-code/.env`. Variables already present in the process
environment take precedence. LimeSurvey requires `LIME_SURVEY_URL`,
`LIME_SURVEY_USERNAME`, and `LIME_SURVEY_PASSWORD`;
database output also requires the five `PISTA_DB_*` settings. Airflow tasks
continue to use the settings supplied by their task environment and do not load
`.env` through the shared flow utilities.
The survey must exist in [survey_mappings](flows-code/pistadigital/mappings/mappings.py).
Only completed responses are processed.

```bash
python lime_flows.py --survey 666914 --csv
python lime_flows.py --survey 666914 --database
python lime_flows.py --survey 666914 --database --csv --output /tmp/responses.csv
python lime_flows.py --help
# Equivalent module entry point:
python -m pistadigital.cli.lime_flows --survey 666914 --csv
```

### LimeSurvey-specific options

These options supplement the [shared output and diagnostic flags](#common-cli-behavior).
The optional positional command accepts `latest`, `export`, `load`, or `all`;
see [Compatibility commands](#compatibility-commands). Without a command,
select outputs using `--database` and/or `--csv`.

| Option | Meaning |
| --- | --- |
| `-s`, `--survey` | Required mapped survey ID. |
| `-f`, `--from-response-id` | Positive first response ID. Without it, CSV-only exports start at ID `1`; database exports resume at `MAX(id) + 1`. |
| `-t`, `--to-response-id` | Optional inclusive upper response ID. When provided, fetch successive intervals through this ID, including intervals with no completed responses. |
| `-i`, `--increment` | Positive response-ID interval step for all exports, default `1000`. Each API interval ends at `start + increment` (inclusive), capped at the last response ID, and the next interval starts at the previous end plus one. |
| `--file` | Input semicolon-delimited CSV for the compatibility `load` command. |

Without `--to-response-id`, an initial ID-only export determines the last
available response ID, then full answers are fetched in successive intervals
through that ID. Gaps and intervals with no completed responses do not stop
the export. Responses created beyond that initial last ID are left for the next
run. CSV-only runs start at response `1` unless
`--from-response-id` is supplied, and never query PostgreSQL. Runs with
`--database` (including both-output runs) resume at `MAX(id) + 1` in the mapped
table, or `1` for an empty existing table. Resume errors fail the flow rather
than silently restarting. For the first load when the table does not exist,
supply `--from-response-id 1` explicitly; the append writer can create a
missing table from the DataFrame, without creating primary keys or other
schema constraints.

Progress is logged at INFO level without requiring `--debug`. All exports
log each batch's start and completion, batch number/total, inclusive response-ID
range, completed-response count, cumulative count, and elapsed seconds.
Empty intervals are logged and processing continues. Without `--to-response-id`,
the initial ID discovery is also logged. Each full-answer request is bounded
by `--increment`, so the default command reports progress between batches.
Transformation, database writes, and CSV writes also have stage logs.
Outputs are still written once after all requested responses are fetched.
The CLI suppresses `citric.session` INFO/DEBUG messages unless `--debug` is
enabled; Citric warnings and errors always remain visible.

```bash
# First load or explicit replay:
python lime_flows.py -s 666914 --from-response-id 1 --increment 1000 --database

# CSV-only export from a specific response ID through the latest response:
python lime_flows.py -s 666914 --from-response-id 142927 \
  --csv --output /tmp/responses.csv

# CSV export through a known last response ID, continuing across empty intervals:
python lime_flows.py -s 666914 --from-response-id 1 --to-response-id 10000 \
  --increment 1000 --csv --output /tmp/responses.csv
```

Database writes append the selected responses in one transaction; they do not
delete a year/month or upsert existing response IDs. Explicitly replaying an
already-loaded range can duplicate records or fail a uniqueness constraint.
An insert failure rolls back that batch. Avoid overlapping writers.

CSV files are UTF-8, semicolon-delimited, with mapped column names and
`create_date`/`update_date`. CLI exports without `--output` are written to
`/tmp/<survey>_answers_<minimum-id>-<maximum-id>.csv`. An explicit `--output`
path is used as given. Airflow and direct Python callers retain their configured
`PISTAFLOWS_EXPORTS_PATH` behavior.
Empty results warn and do not write a CSV or database records.

### Compatibility commands

The existing commands remain available for Docker, DAGs, and shell callers.
Use a compatibility command **or** output flags, not both.

```bash
# CSV-only, equivalent to --csv (starts at 1 unless -f is supplied).
python lime_flows.py export -s 666914 -f 142927 -i 1000

# Both outputs, equivalent to --database --csv (resumes by default).
python lime_flows.py all -s 666914

# Print the NEXT response ID, not the highest existing ID.
python lime_flows.py latest -s 666914

# Append records from a previously generated semicolon-delimited CSV.
python lime_flows.py load -s 666914 --file exports/666914_answers_142927-142938.csv
```

The Python functions `export_answers`, `load_answers`, and `export_and_load`
remain available to existing Airflow callers. `export_answers` now follows
CSV-only behavior and starts at 1 by default; `export_and_load` resumes and
produces both outputs. Use `processar_inquerito` for explicit control:

```python
from pistadigital.flows.limesurvey_flows import processar_inquerito

df = processar_inquerito(
    survey_id="666914",
    from_response_id=1,
    increment=1000,
    exportar_csv=False,
    gravar_bd=True,
)
```

Run both CLI test suites without contacting live services:

```bash
PYTHONPATH=. python -m unittest discover -s tests -p 'test_*.py' -v
```

## INE implementation reference

All annual indicators, including the migrated 9873, 9874, and 9929 modules,
use [process_annual_indicator](flows-code/pistadigital/utils/ine_annual.py).
Indicator modules contain only their schema, dimension transformation, and
the public processing wrapper. Existing defaults, CSV names, table names,
metric spelling, primary keys, string lengths, and date/timestamp types remain
unchanged. The `criar_tabela()` entry points for 9873 and 9929 remain available
and delegate table creation to the shared output helper.

The migrated 9873/9929 flows now apply the same strict validation as other
annual flows: unpublished/foreign periods, unknown categories, duplicate keys,
oversized labels, and malformed/non-finite metrics fail before output rather
than falling back to totals or dropping foreign periods. Valid published
records retain their mapping and values. Empty responses must identify the
requested period (`{"Dados": {"2024": []}}`), and preserve stored data.
Regression coverage is consolidated in
[test_ine_legacy.py](flows-code/tests/test_ine_legacy.py) and
[test_ine_dags.py](flows-code/tests/test_ine_dags.py), alongside the annual, monthly,
CLI, and output suites. The unrelated LimeSurvey DAG is not changed.

| File | Responsibility |
| --- | --- |
| [ine_flows.py](flows-code/ine_flows.py) | Standalone INE CLI entry point. |
| [ine_flows.py](flows-code/pistadigital/cli/ine_flows.py) | Argument validation and registered indicator dispatch. |
| [ine_api.py](flows-code/pistadigital/utils/ine_api.py) | Shared annual/monthly API requests, metadata, period validation, and discovery. |
| [ine_annual.py](flows-code/pistadigital/utils/ine_annual.py) | Single-year orchestration and validation for every annual flow. |
| [ine_monthly.py](flows-code/pistadigital/utils/ine_monthly.py) | Single-month orchestration and validation for every monthly flow, retaining padded CHAR(2) months. |
| [ine_transform.py](flows-code/pistadigital/utils/ine_transform.py) | Verified NUTS-2013/accommodation mapping and numeric parsing. |
| [ine_0009873_flow.py](flows-code/pistadigital/flows/ine_0009873_flow.py) | Annual establishment counts, supplied table schema, transformation, and output selection. |
| [ine_0009874_flow.py](flows-code/pistadigital/flows/ine_0009874_flow.py) | Annual room counts, supplied table schema, transformation, and output selection. |
| [ine_0009929_flow.py](flows-code/pistadigital/flows/ine_0009929_flow.py) | Annual revenue schema and transformation, using the shared runner and existing _ds table. |
| [ine_0009930_flow.py](flows-code/pistadigital/flows/ine_0009930_flow.py), [ine_0011140_flow.py](flows-code/pistadigital/flows/ine_0011140_flow.py), [ine_0009183_flow.py](flows-code/pistadigital/flows/ine_0009183_flow.py) | Indicator-specific annual residence-country schemas and transformations. |
| [ine_0009876_flow.py](flows-code/pistadigital/flows/ine_0009876_flow.py), [ine_0009877_flow.py](flows-code/pistadigital/flows/ine_0009877_flow.py), [ine_0009880_flow.py](flows-code/pistadigital/flows/ine_0009880_flow.py) | Indicator-specific annual accommodation-type schemas and transformations. |
| [ine_0008350_flow.py](flows-code/pistadigital/flows/ine_0008350_flow.py) | Annual territorial-area schema and geography-only transformation. |
| [ine_0009808_flow.py](flows-code/pistadigital/flows/ine_0009808_flow.py) | Monthly overnight stays with explicit year/month isolation and the existing CHAR(2) month schema. |
| [ine_0012093_flow.py](flows-code/pistadigital/flows/ine_0012093_flow.py), [ine_0009812_flow.py](flows-code/pistadigital/flows/ine_0009812_flow.py) | Monthly guest counts by accommodation type using independently verified NUTS-2024/2013 geography. |
| [ine_0010735_flow.py](flows-code/pistadigital/flows/ine_0010735_flow.py), [ine_0010736_flow.py](flows-code/pistadigital/flows/ine_0010736_flow.py) | Monthly overnight stays/guests by municipality and accommodation segment. |
| [ine_output.py](flows-code/pistadigital/utils/ine_output.py) | Shared CSV writing, period validation, and transactional replacement. |
| [database.py](flows-code/pistadigital/utils/database.py) | PostgreSQL environment configuration shared with LimeSurvey. |
| [distritos.py](flows-code/pistadigital/utils/distritos.py) | Shared mapping of district codes to names. |
| [dags_ine_0009929.py](flows-code/dags/dags_ine_0009929.py) | Scheduled annual database loads. |
| [dags_ine_0009873.py](flows-code/dags/dags_ine_0009873.py) | Scheduled annual establishment-count database loads. |
| [dags_ine_0009874.py](flows-code/dags/dags_ine_0009874.py) | Scheduled annual room-count database loads. |
| [dags_ine_0009808.py](flows-code/dags/dags_ine_0009808.py) | One DAG per year/month, passing both period arguments explicitly. |
| [dags_ine_0012093.py](flows-code/dags/dags_ine_0012093.py), [dags_ine_0009812.py](flows-code/dags/dags_ine_0009812.py), [dags_ine_0010735.py](flows-code/dags/dags_ine_0010735.py), [dags_ine_0010736.py](flows-code/dags/dags_ine_0010736.py) | Dedicated monthly indicator entry points using the same year/month factory. |
| [dags_ine_0009930.py](flows-code/dags/dags_ine_0009930.py), [dags_ine_0011140.py](flows-code/dags/dags_ine_0011140.py), [dags_ine_0009183.py](flows-code/dags/dags_ine_0009183.py) | Scheduled annual residence-country loads, one entry-point file per indicator. |
| [dags_ine_0009876.py](flows-code/dags/dags_ine_0009876.py), [dags_ine_0009877.py](flows-code/dags/dags_ine_0009877.py), [dags_ine_0009880.py](flows-code/dags/dags_ine_0009880.py) | Scheduled annual accommodation-type loads, one entry-point file per indicator. |
| [dags_ine_0008350.py](flows-code/dags/dags_ine_0008350.py) | Scheduled annual territorial-area loads, capped at 2022. |
| [dags_ine.py](flows-code/dags/dags_ine.py) | Shared factory and task callable for all annual/monthly INE DAGs; no standalone DAG registration. |

See [Adding monthly indicators](#adding-monthly-indicators) for the extension
contract. A new annual module follows the same contract without `mes` and
exposes `MONTHLY = False`. Register it in the CLI explicitly, provide its
schema and transformation, and add tests for the requested period before
adding a corresponding DAG.

## Debugging either CLI

Debug mode still runs the selected operation and includes a traceback on failure:

```bash
python ine_flows.py -i 9929 -y 2024 --csv --debug
python lime_flows.py -s 666914 --csv --debug
```
