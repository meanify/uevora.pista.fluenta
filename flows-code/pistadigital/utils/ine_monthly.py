"""Single-month orchestration shared by monthly INE indicator modules."""

from datetime import date
import logging

import pandas as pd

from pistadigital.utils.ine_api import (
    fetch_indicator_metadata, fetch_monthly_indicator_data,
    monthly_dimension_labels, monthly_records,
)
from pistadigital.utils.ine_output import replace_period_data, validate_period, write_csv
from pistadigital.utils.ine_transform import metric_value


logger = logging.getLogger("pista.fluenta.ine")


def process_monthly_indicator(
    varcd, ano, mes, exportar_csv, gravar_bd, caminho_csv, *,
    indicator, table_name, create_table_sql, columns, lengths, metric,
    transform_dimensions, required_dimensions,
):
    """Validate a single published month and replace only its year/month."""
    validate_period(ano, mes)
    if mes is None:
        raise ValueError(f"Monthly indicator {indicator} requires mes.")
    if varcd != indicator:
        raise ValueError(f"This module only supports indicator {indicator}.")
    if caminho_csv is not None and not exportar_csv:
        raise ValueError("caminho_csv requires exportar_csv=True.")
    logger.info("Processing INE %s for %s-%02d.", varcd, ano, mes)
    metadata = fetch_indicator_metadata(varcd)
    try:
        dimensions = monthly_dimension_labels(metadata, ano, mes)
        for dimension in required_dimensions:
            if not dimensions.get(dimension):
                raise ValueError(f"Metadata is missing dimension {dimension}.")
        period_label = dimensions["1"][f"S3A{ano:04d}{mes:02d}"]
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid INE metadata ({varcd}, {ano}-{mes:02d}): {exc}") from exc
    payload = fetch_monthly_indicator_data(varcd, ano, mes)
    try:
        rows = monthly_records(payload, ano, mes, period_label)
        today = date.today().isoformat()
        frame = pd.DataFrame([
            {
                **transform_dimensions(row, dimensions),
                "ano": ano, "mes": f"{mes:02d}",
                metric: metric_value(row.get("valor")),
                "create_date": today, "update_date": today,
            } for row in rows
        ], columns=columns)
        for column, length in lengths.items():
            if not frame[column].map(lambda value: isinstance(value, str)).all():
                raise ValueError(f"Column {column} must contain non-null strings.")
            if frame[column].str.len().gt(length).any():
                raise ValueError(f"Values in {column} exceed {length} characters.")
        if frame.duplicated(subset=[*lengths, "ano", "mes"]).any():
            raise ValueError("Transformed records contain duplicate primary keys.")
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid INE response ({varcd}, {ano}-{mes:02d}): {exc}") from exc
    if gravar_bd:
        replace_period_data(frame, table_name, create_table_sql, ano, mes)
    if exportar_csv:
        write_csv(
            frame, caminho_csv if caminho_csv is not None
            else f"ine_{varcd}_{ano}_{mes:02d}_tratado.csv",
        )
    logger.info("Processed INE %s for %s-%02d: %d records.", varcd, ano, mes, len(frame))
    return frame
