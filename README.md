# Fluenta Pista Flows

> **Current INE CLI instructions:** see the
> [Flows Code README](flows-code/README.md) for installation, CSV/database
> examples, transactional year/month replacement, Airflow setup, and
> troubleshooting. Only annual indicator `0009929` is currently registered in
> the CLI, writing to `ine_0009929_ds`. The older INE architecture and indicator
> catalogue below are historical and do not describe the current CLI.

Fluenta is a Latin word that means flows, currents, streams. This is the name of the project that will take data from Lime Survey and INE and take to PISTA Digital

This project has multiple components:
- **Airflow**: the platform to execute the flows to move data (see `k8s/airflow`)
- **Flows Code** (`flows-code/`): the Python ETL code and the DAGs that run it
- **Flows INE** (`flows-ine/`): the legacy Apache Hop pipelines the Python ETL replaces

## Configuration

All credentials come from environment variables. Set them however you prefer:

- `flows-code/.env` — loaded automatically by the ETL modules (requires `python-dotenv`)
- `flows-code/set-variables.sh` — `source` it for an interactive shell
- Airflow — injected by the DAGs from the `pista_db` connection

Both files are git-ignored; never commit real credentials.

```bash
# PISTA Digital DB
PISTA_DB_HOSTNAME=
PISTA_DB_PORTNUMBER=
PISTA_DB_NAME=
PISTA_DB_USERNAME=
PISTA_DB_PASSWORD=
# Lime Survey
LIME_SURVEY_URL=
LIME_SURVEY_USERNAME=
LIME_SURVEY_PASSWORD=
PISTAFLOWS_EXPORTS_PATH=
# Optional, used by the INE modules when run from the command line
INE_YEAR=2024
INE_MONTH=
```

## INE ETL

Each INE indicator has a module in `flows-code/pistadigital/utils/ine_<indicator>.py`
and a DAG in `flows-code/dags/dags_ine_<indicator>.py`. The modules share
`pistadigital/utils/common.py`, which holds the database connection, the INE API
calls, the code decomposition rules, the distrito lookup and the ETL orchestrator —
so each indicator module is only its constants, its `CREATE TABLE` and a transform.

Data is written to `ine_test_<indicator>` tables. The source `ine_<indicator>`
tables and the Hop staging `ine_<indicator>_pt` tables are never written to.

### Annual indicators

| Indicator | Value column | Grain |
| --- | --- | --- |
| 0009183 | dormidas | município + país de residência |
| 0009873 | establecimento_de_alojamento_turistico | município + tipo/subtipo/classificação |
| 0009874 | quartos | município + tipo/subtipo/classificação |
| 0009876 | hospedes | município + tipo/subtipo/classificação |
| 0009877 | dormidas | município + tipo/subtipo/classificação |
| 0009880 | estada_media | município + tipo/subtipo/classificação |
| 0009929 | rendimento_medio_por_quarto | município + tipo/subtipo/classificação |
| 0009930 | hospedes | município + país de residência |
| 0011140 | estada_media | município + país de residência |
| 0011142 | proporcao_de_dormidas | município + segmento |

### Monthly indicators

| Indicator | Value column | Grain |
| --- | --- | --- |
| 0009808 | dormidas | NUTS II + tipo/subtipo |
| 0009812 | hospedes | NUTS II + tipo/subtipo |
| 0009814 | proveitos_de_aponsento_milhares_euros | NUTS II + tipo/subtipo |
| 0010735 | dormidas | município + segmento |
| 0010736 | hospedes | município + segmento |
| 0012093 | hospedes | NUTS II + tipo/subtipo (NUTS 2024) |

Monthly tables carry an extra `mes` column (zero-padded, `'01'`..`'12'`).

### Running locally

```bash
cd flows-code
pip install -r requirements.txt

# annual indicator, year from INE_YEAR (default 2024)
python -m pistadigital.utils.ine_0011142

# monthly indicator: a single month, or every month published for the year
INE_YEAR=2024 INE_MONTH=3 python -m pistadigital.utils.ine_0009808
INE_YEAR=2024              python -m pistadigital.utils.ine_0009808
```

From Python:

```python
from pistadigital.utils import ine_0011142, ine_0009808

ine_0011142.extract_and_load(year=2024)
ine_0009808.extract_and_load(year=2024, month=3)   # one month
ine_0009808.extract_and_load(year=2024)            # all published months
```

### Load semantics

A run always cleans before it writes, inside a single transaction:

- annual — `DELETE FROM <table> WHERE ano = :year`, then insert
- monthly — deletes only the months being loaded, so a single-month run never
  touches the rest of the year

### Freshness and gap detection

INE reports `DataUltimaAtualizacao` in the metadata response and lists every
published period; the tables record `update_date` and the periods already loaded.
`common.plan_refresh()` compares the two:

```python
from pistadigital.utils import common

plan = common.plan_refresh("0009808", "ine_test_0009808",
                           monthly=True, years=[2025, 2026])
plan.needs_run           # INE republished since our load, or periods missing
plan.missing             # e.g. [(2025, 1), (2025, 2), ...]
plan.ine_last_update     # date INE last published
plan.table_last_update   # MAX(update_date) in our table
```

`common.run_etl(..., skip_if_current=True)` uses the same comparison to return
early instead of reloading when the requested periods are present and INE has
not republished. Note that `DataUltimaAtualizacao` is indicator-wide, not
per-period, so `plan.missing` is the precise signal.

### Airflow DAGs

Annual indicators generate one DAG per year (current year plus the two previous),
scheduled monthly:

```
ine_<indicator>_<year>          # e.g. ine_0011142_2024
```

Monthly indicators generate two flavours:

```
ine_<indicator>_monthly         # loads the last published month (2-month lag)
ine_<indicator>_<year>          # reloads every month published for that year
```

Each task runs in a `PythonVirtualenvOperator` and receives the database
credentials from the `pista_db` Airflow connection.

```bash
airflow dags trigger ine_0011142_2024
airflow dags trigger ine_0009808_monthly
```
