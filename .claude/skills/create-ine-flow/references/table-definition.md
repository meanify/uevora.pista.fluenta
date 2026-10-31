# Retrieving a table definition from PostgreSQL

Read this only when the user did not supply DDL, or asked you to verify it
against the database. Inspection is read-only: it must never create, alter,
or write to a live table.

## Connection

Reuse [database.get_engine()](../../../../flows-code/pistadigital/utils/database.py)
and, if variables are not set, the
[environment loader](../../../../flows-code/pistadigital/cli/environment.py).
Credentials come from `PISTA_DB_HOSTNAME`, `PISTA_DB_PORTNUMBER`,
`PISTA_DB_NAME`, `PISTA_DB_USERNAME`, and `PISTA_DB_PASSWORD`. Never print
them, the environment, `.env`, or the engine URL — tool output is logged.
Dispose of any engine you create.

## Inspecting one table

Use `sqlalchemy.inspect(engine)` with explicit `schema` and `table_name` for
columns, primary key, unique/check/foreign-key constraints, and indexes. Only
list tables when the name is genuinely unknown.

To reconstruct DDL, reflect just that table and compile it with the engine's
dialect:

```python
from sqlalchemy import MetaData, Table
from sqlalchemy.schema import CreateTable, CreateIndex

with engine.connect() as connection:
    table = Table(name, MetaData(), schema=schema,
                  autoload_with=connection, resolve_fks=False)
print(CreateTable(table).compile(dialect=engine.dialect))
for index in table.indexes:
    print(CreateIndex(index).compile(dialect=engine.dialect))
```

Reflection keeps lengths, nullability, defaults, and types well enough for a
flow, but it is not a full-fidelity backup. If exact DDL is required and
`pg_dump` is already installed, use a schema-only dump of the named table
(`--schema-only --no-owner --no-privileges -t schema.table`) with credentials
from the environment (`PGPASSWORD` or a pgpass file), never on the command line.
Don't install tooling just for this.

## Sample rows

Only if rows are genuinely needed: select the useful columns with bound
parameters `ano = :year` (and `mes = :month` for monthly tables) and
`LIMIT 3`. Use reflected identifiers rather than interpolating user input.
No full-table scans or unfiltered extracts.

## When access fails

Report the failure (without credentials) and fall back to supplied DDL, or ask
the user for it. Do not invent a schema.
