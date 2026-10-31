"""One-period processing shared by annual INE indicator modules."""

from datetime import date
import logging

import pandas as pd

from pistadigital.utils.ine_api import (
    annual_dimension_labels, annual_records, fetch_annual_indicator_data,
    fetch_indicator_metadata,
)
from pistadigital.utils.ine_output import (
    replace_period_data, validate_annual_frame, validate_period, write_csv,
)
from pistadigital.utils.ine_transform import filter_detail_rows, metric_value


logger = logging.getLogger("pista.fluenta.ine")


def process_annual_indicator(
    varcd, ano, exportar_csv, gravar_bd, caminho_csv, *,
    indicator, table_name, create_table_sql, columns, lengths, metric,
    transform_dimensions, required_dimensions,
):
    """Fetch one verified annual period and validate before producing outputs."""
    validate_period(ano)
    if varcd != indicator:
        raise ValueError(f"This module only supports indicator {indicator}.")
    if caminho_csv is not None and not exportar_csv:
        raise ValueError("caminho_csv requires exportar_csv=True.")
    logger.info("Processing INE indicator %s for year %s.", varcd, ano)
    metadata = fetch_indicator_metadata(varcd)
    try:
        dimensions = annual_dimension_labels(metadata, ano)
        for dimension in required_dimensions:
            if dimension not in dimensions:
                raise ValueError(f"Metadata is missing dimension {dimension}.")
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid INE metadata ({varcd}, {ano}): {exc}") from exc
    payload = fetch_annual_indicator_data(varcd, ano)
    try:
        records = annual_records(payload, ano)
        today = date.today().isoformat()
        frame = pd.DataFrame([
            {
                **transform_dimensions(row, dimensions),
                "ano": ano,
                metric: metric_value(row.get("valor")),
                "create_date": today,
                "update_date": today,
            }
            for row in records
        ], columns=columns)
        validate_annual_frame(frame, columns, lengths, ano)
        frame = filter_detail_rows(frame, records, dimensions)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid INE response ({varcd}, {ano}): {exc}") from exc
    if gravar_bd:
        replace_period_data(frame, table_name, create_table_sql, ano)
    if exportar_csv:
        write_csv(
            frame, caminho_csv if caminho_csv is not None
            else f"ine_{varcd}_{ano}_tratado.csv",
        )
    logger.info("Processed INE %s, year %s: %d records.", varcd, ano, len(frame))
    return frame
