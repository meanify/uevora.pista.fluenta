"""Monthly INE overnight stays by NUTS-2013 and accommodation type."""

from pistadigital.utils.ine_monthly import process_monthly_indicator
from pistadigital.utils.ine_transform import nuts_i_ii_accommodation_fields


INDICATOR = "0009808"
MONTHLY = True
TABLE_NAME = "ine_0009808"
VALUE_COLUMN = "dormidas"
COLUMN_LENGTHS = {
    "nuts_i": 64, "nuts_ii": 64, "tipo_alojamento": 64, "subtipo_alojamento": 64,
}
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ine_0009808 (
    nuts_i CHAR(64) NOT NULL,
    nuts_ii CHAR(64) NOT NULL,
    tipo_alojamento CHAR(64) NOT NULL,
    subtipo_alojamento CHAR(64) NOT NULL,
    ano INTEGER NOT NULL,
    mes CHAR(2) NOT NULL,
    dormidas REAL,
    create_date DATE,
    update_date DATE,
    PRIMARY KEY (nuts_i, nuts_ii, tipo_alojamento, subtipo_alojamento, ano, mes)
)
"""
DIMENSIONS = list(COLUMN_LENGTHS)
SCHEMA_COLUMNS = [
    *DIMENSIONS, "ano", "mes", VALUE_COLUMN, "create_date", "update_date",
]
COLUMNS = SCHEMA_COLUMNS


def transform_dimensions(row, dimensions):
    return nuts_i_ii_accommodation_fields(row, dimensions)


def processar_indicador_ine(
    varcd=INDICATOR, ano=2026, exportar_csv=True, gravar_bd=False,
    caminho_csv=None, mes=None,
):
    """Validate and replace only the explicitly selected year and month."""
    return process_monthly_indicator(
        varcd, ano, mes, exportar_csv, gravar_bd, caminho_csv,
        indicator=INDICATOR, table_name=TABLE_NAME, create_table_sql=CREATE_TABLE_SQL,
        columns=SCHEMA_COLUMNS, lengths=COLUMN_LENGTHS, metric=VALUE_COLUMN,
        transform_dimensions=transform_dimensions, required_dimensions=("2", "3"),
    )
