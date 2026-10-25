"""Annual INE average revenue per room, retaining the existing _ds schema."""

from pistadigital.utils.ine_annual import process_annual_indicator
from pistadigital.utils.ine_output import create_indicator_table
from pistadigital.utils.ine_transform import accommodation_fields, nuts_2013_fields


INDICATOR = "0009929"
MONTHLY = False
TABLE_NAME = f"ine_{INDICATOR}_ds"
VALUE_COLUMN = "rendimento_medio_por_quarto"
COLUMN_LENGTHS = {
    "nuts_i": 64, "nuts_ii": 64, "nuts_iii": 64, "distrito": 64,
    "municipio": 64, "tipo_alojamento": 64, "subtipo_alojamento": 128,
    "classificacao": 64,
}
SCHEMA_COLUMNS = [
    *COLUMN_LENGTHS, "ano", VALUE_COLUMN, "create_date", "update_date",
]
CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    nuts_i varchar(64) NOT NULL,
    nuts_ii varchar(64) NOT NULL,
    nuts_iii varchar(64) NOT NULL,
    distrito varchar(64) NOT NULL,
    municipio varchar(64) NOT NULL,
    tipo_alojamento varchar(64) NOT NULL,
    subtipo_alojamento varchar(128) NOT NULL,
    classificacao varchar(64) NOT NULL,
    ano int4 NOT NULL,
    {VALUE_COLUMN} float4 NULL,
    create_date timestamp NULL,
    update_date timestamp NULL,
    CONSTRAINT {TABLE_NAME}_pkey PRIMARY KEY (
        nuts_i, nuts_ii, nuts_iii, distrito, municipio, tipo_alojamento,
        subtipo_alojamento, classificacao, ano
    )
);
"""


def criar_tabela():
    """Create the indicator table without loading records."""
    create_indicator_table(TABLE_NAME, CREATE_TABLE_SQL)


def transform_dimensions(row, dimensions):
    return {
        **nuts_2013_fields(row["geocod"], dimensions["2"]),
        **accommodation_fields(row["dim_3"], dimensions["3"]),
    }


def processar_indicador_ine(
    varcd=INDICATOR, ano=2024, exportar_csv=True, gravar_bd=False, caminho_csv=None,
):
    """Process one year using the existing average-revenue schema."""
    return process_annual_indicator(
        varcd, ano, exportar_csv, gravar_bd, caminho_csv,
        indicator=INDICATOR, table_name=TABLE_NAME,
        create_table_sql=CREATE_TABLE_SQL, columns=SCHEMA_COLUMNS,
        lengths=COLUMN_LENGTHS, metric=VALUE_COLUMN,
        transform_dimensions=transform_dimensions, required_dimensions=(
            "2", "3"),
    )


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    processar_indicador_ine()
