---
name: create-ine-flow
description: "Create, extend, or investigate INE indicator ETL flows in this project (INE API → CSV/PostgreSQL, CLI, Airflow). Use whenever the user mentions an INE indicator code (e.g. 9873, 0009929), adding or mapping an INE indicator to a table, its DDL, whether an indicator is annual or monthly, or wiring a new INE flow into the CLI or a DAG — even for a quick question about an indicator's dimensions or periods."
---

# Create an INE flow

New flows reuse existing helpers while keeping schemas and dimension mappings
indicator-specific. Work from the workspace root. Read [workspace navigation](../../../agents.md)
and [review criteria](../../../CODING_STANDARDS.md). Never write to a live
database while investigating or validating — the shared tables feed production.

**Scope to the request.** If the user only asks a question (frequency,
dimensions, latest period, table shape), answer after step 1 (and step 2 if
the table matters) and stop: no code, no repository changes.

**Flow creation includes scheduling.** Create the flow module, CLI registration,
a dedicated `flows-code/dags/dags_ine_<code>.py` entry point, tests, and README
updates together. Omit the DAG only if the user explicitly requests no DAG;
do not wait for a separate scheduling request. Creating files does not authorize
deployment, triggering tasks, or production database writes.

**Multiple indicators:** keep the requested order unless told otherwise.
Complete metadata, one-period inspection, implementation, tests, and live
CSV-only verification for one indicator before starting the next. Report
completed versus blocked codes separately; one failed endpoint is not evidence
that every indicator is unavailable.

## 1. Verify the indicator and its frequency

Normalize ASCII digit codes to exactly seven digits, preserving their numeric
identity: `9930` becomes `0009930`, not `0000930`; `9874` becomes `0009874`.
Reject non-digits and codes longer than seven digits. Show the normalized code
when investigating a suspected code-format issue.

Use the existing project interpreter; check its path before concluding it is
missing. From the workspace root it is `.venv/bin/python`; after
`cd flows-code` it is `../.venv/bin/python`. A shell's directory change does not
persist into another tool call.

Summarize metadata with the bundled script
rather than printing raw JSON — the category catalogue can hold hundreds of
municipalities, and the script reports only names, `Periodic`, first/latest
period, per-dimension counts, a few sample codes, label lengths, and the
period codes matching a requested year/month:

```bash
.venv/bin/python -I .agents/skills/create-ine-flow/scripts/ine_summary.py meta --code <code> --year <y> [--month <m>]
```

Use `--file <path>` instead of `--code` for saved responses (for example when
the INE API is unreachable). Saved fixtures must identify their indicator and
period; invented fixtures are not proof of a live source contract. Then decide:

- **Annual** (`Periodic` Anual): one `ano`; no month. The existing helper
  `fetch_annual_indicator_data` sends `Dim1=S7A<year>` — confirm that code is
  in the metadata.
- **Monthly** (Mensal): needs `ano` and `mes`; take the exact period code from
  the metadata (never guess its encoding) and don't reuse the annual helper.
- **Quarterly, mixed, or unclear**: stop and ask. Silently treating them as
  annual or monthly loads wrong periods.

Confirm Dim1 really is the reference period. If no period was requested, use
the latest *published* one and say so.
The summary script's `--dim1` assumes the verified period is dimension 1; for
another dimension, use an explicitly constructed `DimN` request instead.
Printed period matches are candidates for inspection, not proof of a monthly
encoding; verify the exact code/label pair in the metadata.

To inspect records, request exactly one verified period from the API (not all
history sliced locally — that downloads far more than needed) and summarize:

```bash
.venv/bin/python -I .agents/skills/create-ine-flow/scripts/ine_summary.py data --code <code> --dim1 <period-code> --year <y>
```

For monthly data, also supply `--month <m>` and
`--period-key <exact-response-key>` verified from the source/fixture. A metadata
category code and a response period key need not have the same encoding.

It prints period keys, record count, fields, 3 samples, distinct codes per
dimension, non-numeric `valor` markers, zeros, and duplicate keys. If the
response contains other periods, the selector is wrong — fix the request
rather than relabelling data. Never run `--all-years` while investigating.

**Transient API failures:** use explicit timeouts and status/JSON checks.
Retry one normalized code serially with a bounded attempt count (initial
request plus at most two retries); respect `Retry-After` for HTTP 429. Do not
hammer all codes in parallel or repeat the same batch indefinitely. Keep
already verified metadata and period data in local temporary files during
the task so a later timeout does not force repeated downloads. Report the
exact failed stage (metadata, data, or output) and normalized code. If still
blocked, continue only with supplied/previously verified evidence sufficient
for that indicator; otherwise request the missing bounded metadata/sample.
Do not invent dimensions, substitute another indicator, or claim a live check
passed from mocks alone.

## 2. Reconcile the table definition

Prefer DDL the user supplied; don't assume a `_ds` suffix or a schema. If no
DDL was given or it must be checked against the database, read
[references/table-definition.md](./references/table-definition.md) for the
read-only inspection procedure.

If the user supplies a schema dump, extract only each requested table's exact
`CREATE TABLE` statement. Distinguish the base table from `_pt`, `_ds`, and
monthly variants; preserve metric spelling, lengths, nullability, dates, and
key order. A year-only key does not prove that the source is annual. Keep the
relevant statements available during the task; never ask for DDL already
supplied merely because a large tool response was offloaded.

Then compare the DDL with the frequency: monthly data needs `ano` and `mes` in
the primary key; annual data needs `ano` and no `mes`. If they conflict, stop
and ask how to resolve it (for example adding `mes` to the table and key),
reporting the frequency and period code you found. Don't migrate the table,
drop the month, or build an annual flow on monthly data — each loses data
silently. Also ask about other material conflicts; don't re-ask what the user
already supplied.

## 3. Implement

Read the README sections "Supported indicators", "Adding monthly indicators",
and "INE implementation reference" in
[flows-code/README.md](../../../flows-code/README.md). For annual flows, use
[ine_annual.py](../../../flows-code/pistadigital/utils/ine_annual.py) and compare
[ine_0009930_flow.py](../../../flows-code/pistadigital/utils/ine_0009930_flow.py)
(residence), [ine_0009876_flow.py](../../../flows-code/pistadigital/utils/ine_0009876_flow.py)
(accommodation), or [ine_0008350_flow.py](../../../flows-code/pistadigital/utils/ine_0008350_flow.py)
(geography only). Their shared tests are in
[test_ine_annual.py](../../../flows-code/tests/test_ine_annual.py).
The migrated [9873](../../../flows-code/pistadigital/utils/ine_0009873_flow.py),
[9874](../../../flows-code/pistadigital/utils/ine_0009874_flow.py), and
[9929](../../../flows-code/pistadigital/utils/ine_0009929_flow.py) use the same
runner; their compatibility contracts are tested in
[test_ine_legacy.py](../../../flows-code/tests/test_ine_legacy.py).
Do not reintroduce per-indicator annual orchestration.
Confirm each indicator's dimensions, codes, and geography version independently.

- Create `flows-code/pistadigital/utils/ine_<code>_flow.py` exposing
  `INDICATOR`, `MONTHLY`, `TABLE_NAME`, `CREATE_TABLE_SQL`, and
  `processar_indicador_ine(varcd, ano, exportar_csv, gravar_bd, caminho_csv)`
  (plus `mes` when monthly). Validate arguments before any network or output.
- API access lives in [ine_api.py](../../../flows-code/pistadigital/utils/ine_api.py).
  Annual flows reuse `annual_dimension_labels`, `annual_records`, and
  `fetch_annual_indicator_data` through `process_annual_indicator`. Supply
  `required_dimensions` so malformed metadata fails even for empty periods.
  Monthly flows with the verified S3A encoding reuse
  `monthly_dimension_labels`, `monthly_records`, and
  `fetch_monthly_indicator_data`; compare
  [9808](../../../flows-code/pistadigital/utils/ine_0009808_flow.py).
  Pin the exact request URL in tests rather than guessing the encoding.
- Output goes through `validate_period`, `write_csv`, and `replace_period_data`
  in [ine_output.py](../../../flows-code/pistadigital/utils/ine_output.py). They
  enforce database period consistency, table-name validation, transactional
  replacement, and keeping stored rows when the result is empty — rely on them
  instead of reimplementing. CSV-only runs also need validation: annual flows
  use `annual_records` and `validate_annual_frame` via the annual runner.
  Pass `mes` only for monthly flows. The writer takes
  an unqualified table name; a non-default schema needs a coherent change to the
  shared writer with regression tests.
- Transform: produce exactly the DDL columns in order (an empty frame keeps the
  header); labels come from metadata; keep totals and zeros; map verified
  unavailable/confidential markers (for example `..`, `x`) to null; fail loudly
  on malformed numbers. Check NOT NULL fields, key uniqueness, and `bpchar`
  lengths — never truncate or deduplicate silently. Reuse
  [ine_transform.py](../../../flows-code/pistadigital/utils/ine_transform.py)
  (`metric_value`, `nuts_2013_fields`, `accommodation_fields`) only when the
  verified mapping fits. NUTS-2013 prefixes may contain letters (`11A`); do not
  require all geographic codes to be numeric. Unknown categories/ancestors
  must fail rather than collapse distinct rows into invented totals.
- CSV-only runs never connect to PostgreSQL; with both outputs, write the
  database first. Monthly CSV names include year and month.
- Register the module in `INDICATORS` in
  [cli/ine_flows.py](../../../flows-code/pistadigital/cli/ine_flows.py). It
  already rejects `--month` for annual and `--all-years` for monthly modules;
  check that the default CSV path includes the month for monthly ones.
- Create a dedicated `flows-code/dags/dags_ine_<code>.py` unless explicitly
  excluded. Follow
  [dags_ine_0009930.py](../../../flows-code/dags/dags_ine_0009930.py):
  import `DAG` from `airflow.sdk` so Airflow's default safe-mode scan discovers
  the file, then expose `build_indicator_dags("<code>")` results via
  `globals().update`. Reuse
  [dags_ine.py](../../../flows-code/dags/dags_ine.py) for all INE factory and
  task logic (database-only, compact status, errors propagated).
  Annual entry points call `build_indicator_dags("<code>")` for one DAG per
  year. Monthly entry points call `build_indicator_dags("<code>", monthly=True)`
  for one DAG per year/month, as in
  [dags_ine_0009808.py](../../../flows-code/dags/dags_ine_0009808.py).
  Shared task arguments are `[indicator, year]` or `[indicator, year, month]`.
  Extend [test_ine_dags.py](../../../flows-code/tests/test_ine_dags.py);
  keep operator configuration and dispatch out of entry-point files.
  The shared factory must not register DAGs itself.
  Do not register duplicate DAG IDs. A
  monthly schedule doesn't make an indicator monthly; monthly tasks must pass
  an explicit year and month. Preserve the table's month type (9808 uses padded
  `CHAR(2)`); replacement and bounded table reads must filter both year and month.
  Check the source's latest published year against
  the scheduling window. Historical series such as 8350 (latest verified 2022)
  need an explicit, documented `PUBLISHED_YEAR_CAPS` entry and registration
  tests; do not schedule only unpublished years or assume every source ends
  at the current year. Preserve existing schedules unless changing them is
  part of the request; surface any intentional unpublished-year task failures.
- Update the README supported-indicator table, usage, period behavior, and
  deployment instructions, including the dedicated entry point and any shared
  factory that must be deployed with it. No unrelated refactors.

## 4. Verify

Add focused tests under [flows-code/tests/](../../../flows-code/tests/) using
realistic fixtures, extending `test_ine_annual.py` where its contract fits:
exact period selector and
rejection of foreign periods; exact columns and DDL; hierarchy/totals, null
markers and zeros; malformed and empty responses; CLI code padding, period
flags and output modes; CSV-only without database access; and same-period
replacement, preservation of other periods and empty-result preservation,
and rollback on insert failure on an isolated test database. Verify
database-first ordering, error propagation, and annual `--all-years` with
mocks, not live full-history requests. For every new DAG, test discovery of its
dedicated entry point, expected IDs and year window, no duplicate IDs when
loading all related files, task arguments, database-only output, credential
templates, and error propagation. Run focused tests first, then the INE regressions
when shared helpers or CLI registration changed:

```bash
cd flows-code && ../.venv/bin/python -m unittest discover -s tests -p 'test_ine*.py'
```

If the network is available, smoke-test one published period with CSV-only
output into a temporary directory, check row count, period, columns, key
uniqueness, and lengths locally, then delete it. For a batch, do this per
indicator, not just for one representative flow. Verify the actual CLI path
when changing dispatch or generated filenames. Never run `--database` against production
without explicit authorization.

Finish with: indicator and frequency, sample period used, target table,
dedicated DAG path and generated IDs (or the user's explicit opt-out), the
commands to run, test results, and what was not verified (live loading,
deployment). A flow is not complete without its DAG and registration tests
unless the user explicitly excluded scheduling.

When editing this skill's summary script, run its offline checks from the
workspace root:

```bash
.venv/bin/python -I -m unittest discover -s .agents/skills/create-ine-flow/scripts -p 'test_ine_summary.py'
```
