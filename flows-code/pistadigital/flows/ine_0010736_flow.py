"""Monthly guests by NUTS-2013 geography and accommodation segment."""

from pistadigital.utils.ine_monthly import process_monthly_indicator
from pistadigital.utils.ine_transform import nuts_2013_fields


INDICATOR = "0010736"
MONTHLY = True
TABLE_NAME = f"ine_{INDICATOR}_ds"
VALUE_COLUMN = "hospedes"
COLUMN_LENGTHS = {
    "nuts_i": 64, "nuts_ii": 64, "nuts_iii": 64, "distrito": 64,
    "municipio": 64, "segmento_alojamento": 64,
}
SCHEMA_COLUMNS = [
    *COLUMN_LENGTHS, "ano", "mes", VALUE_COLUMN, "create_date", "update_date",
]
CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(64) NOT NULL,
    municipio varchar(64) NOT NULL,
    segmento_alojamento varchar(64) NOT NULL,
    ano INTEGER NOT NULL,
    mes CHAR(2) NOT NULL,
    {VALUE_COLUMN} REAL,
    create_date DATE,
    update_date DATE,
    PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, segmento_alojamento, ano, mes
    )
)
"""


def transform_dimensions(row, dimensions):
    return {
        **nuts_2013_fields(row["geocod"], dimensions["2"]),
        "segmento_alojamento": dimensions["3"][row["dim_3"]],
    }


def processar_indicador_ine(
    varcd=INDICATOR, ano=2026, exportar_csv=True, gravar_bd=False,
    caminho_csv=None, mes=None,
):
    return process_monthly_indicator(
        varcd, ano, mes, exportar_csv, gravar_bd, caminho_csv,
        indicator=INDICATOR, table_name=TABLE_NAME, create_table_sql=CREATE_TABLE_SQL,
        columns=SCHEMA_COLUMNS, lengths=COLUMN_LENGTHS, metric=VALUE_COLUMN,
        transform_dimensions=transform_dimensions, required_dimensions=(
            "2", "3"),
    )
