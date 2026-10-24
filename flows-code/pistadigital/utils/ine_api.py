"""Shared access to INE indicator data, metadata, and annual periods."""

import re
from typing import Any

import requests


METADATA_URL = (
    "https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp"
)
DATA_URL = "https://www.ine.pt/ine/json_indicador/pindica.jsp"


def annual_dimension_labels(metadata: Any, year: int) -> dict[str, dict[str, str]]:
    """Read annual metadata categories and require the exact requested period."""
    dimensions = _dimension_labels(metadata, "Anual")
    if f"S7A{year}" not in dimensions.get("1", {}):
        raise ValueError(f"Year {year} is not listed in the period categories.")
    return dimensions


def _dimension_labels(metadata: Any, frequency: str) -> dict[str, dict[str, str]]:
    indicators = metadata if isinstance(metadata, list) else [metadata]
    if len(indicators) != 1 or not isinstance(indicators[0], dict):
        raise ValueError("Metadata must contain exactly one indicator.")
    indicator = indicators[0]
    if indicator.get("Periodic") != frequency:
        description = "annual" if frequency == "Anual" else "monthly"
        raise ValueError(f"Indicator metadata must declare {description} frequency.")
    dimension_data = indicator.get("Dimensoes")
    if not isinstance(dimension_data, dict):
        raise ValueError("Metadata is missing dimensions.")
    groups = dimension_data.get("Categoria_Dim")
    if not isinstance(groups, list):
        raise ValueError("Metadata is missing dimension categories.")
    dimensions: dict[str, dict[str, str]] = {}
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("Metadata contains an invalid dimension group.")
        for categories in group.values():
            if not isinstance(categories, list):
                raise ValueError("Metadata contains an invalid category list.")
            for category in categories:
                if not isinstance(category, dict):
                    raise ValueError("Metadata contains an invalid category.")
                dimension = category.get("dim_num")
                code = category.get("categ_cod")
                label = category.get("categ_dsg")
                if (
                    dimension is None or code is None
                    or not isinstance(label, str) or not label.strip()
                ):
                    raise ValueError("Metadata contains an incomplete category.")
                mapping = dimensions.setdefault(str(dimension), {})
                code, label = str(code), label.strip()
                if code in mapping and mapping[code] != label:
                    raise ValueError(f"Conflicting labels for category {code}.")
                mapping[code] = label
    return dimensions


def monthly_dimension_labels(metadata: Any, year: int, month: int):
    """Require the verified monthly category and retain its response label."""
    dimensions = _dimension_labels(metadata, "Mensal")
    if f"S3A{year:04d}{month:02d}" not in dimensions.get("1", {}):
        raise ValueError(f"Month {year:04d}-{month:02d} is not published.")
    return dimensions


def available_monthly_periods(metadata: Any) -> list[tuple[int, int]]:
    """Read the S3A monthly encoding used by verified monthly INE flows."""
    dimensions = _dimension_labels(metadata, "Mensal")
    periods = []
    for code in dimensions.get("1", {}):
        match = re.fullmatch(r"S3A([0-9]{4})(0[1-9]|1[0-2])", code)
        if not match or int(match[1]) == 0:
            raise ValueError(f"Unsupported monthly period code: {code!r}")
        periods.append((int(match[1]), int(match[2])))
    if not periods:
        raise ValueError("No monthly periods found in INE metadata.")
    return sorted(periods)


def monthly_records(payload: Any, year: int, month: int, period_label: str):
    """Require only the selected Portuguese month label, without relabelling."""
    indicators = payload if isinstance(payload, list) else [payload]
    if len(indicators) != 1 or not isinstance(indicators[0], dict):
        raise ValueError("Data response must contain exactly one indicator.")
    data = indicators[0].get("Dados")
    if not isinstance(data, dict) or set(data) != {period_label}:
        raise ValueError(f"API must return only requested month {period_label}.")
    records = data[period_label]
    if not isinstance(records, list):
        raise ValueError("Requested period must contain a list of records.")
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("Data contains a record that is not an object.")
        for key, expected in (("anocod", year), ("mescod", month)):
            if key in row and (
                isinstance(row[key], bool)
                or str(row[key]) not in (str(expected), f"{expected:02d}")
            ):
                raise ValueError(f"Record {key} does not match requested month.")
    return records


def fetch_monthly_indicator_data(varcd: str, year: int, month: int) -> Any:
    """Fetch exactly one verified S3A monthly period."""
    try:
        response = requests.get(
            f"{DATA_URL}?op=2&varcd={varcd}&lang=PT"
            f"&Dim1=S3A{year:04d}{month:02d}",
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(
            f"Erro ao obter dados da API do INE ({varcd}, {year}-{month:02d}): {exc}"
        ) from exc


def annual_records(payload: Any, year: int) -> list[dict[str, Any]]:
    """Reject foreign periods and unlabelled list-form annual responses."""
    indicators = payload if isinstance(payload, list) else [payload]
    if len(indicators) != 1 or not isinstance(indicators[0], dict):
        raise ValueError("Data response must contain exactly one indicator.")
    data = indicators[0].get("Dados")
    if isinstance(data, dict):
        if set(data) != {str(year)}:
            raise ValueError(f"API must return only requested year {year}.")
        records = data[str(year)]
    elif isinstance(data, list):
        records = data
        if any(not isinstance(row, dict) or "anocod" not in row for row in records):
            raise ValueError("List-form records must identify their reference year.")
    else:
        raise ValueError("Dados must contain annual records.")
    if not isinstance(records, list):
        raise ValueError("Requested period must contain a list of records.")
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("Data contains a record that is not an object.")
        record_year = row.get("anocod", year)
        if isinstance(record_year, bool) or str(record_year) != str(year):
            raise ValueError(f"Record year does not match requested year {year}.")
    return records


def fetch_annual_indicator_data(varcd: str, year: int) -> Any:
    """Fetch one annual period from the INE public API."""
    try:
        response = requests.get(
            f"{DATA_URL}?op=2&varcd={varcd}&lang=PT&Dim1=S7A{year}",
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(
            f"Erro ao obter dados da API do INE ({varcd}, {year}): {exc}"
        ) from exc


def fetch_indicator_metadata(varcd: str) -> Any:
    """Fetch metadata for an INE indicator."""
    try:
        response = requests.get(
            f"{METADATA_URL}?varcd={varcd}&lang=PT", timeout=120
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(
            f"Erro ao obter metadados da API do INE ({varcd}): {exc}"
        ) from exc


def available_annual_years(metadata: Any) -> list[int]:
    """Return the annual periods explicitly listed in INE indicator metadata."""
    indicators = metadata if isinstance(metadata, list) else [metadata]
    years: set[int] = set()
    for indicator in indicators:
        if not isinstance(indicator, dict):
            continue
        dimensions = indicator.get("Dimensoes")
        if not isinstance(dimensions, dict):
            continue
        categories = dimensions.get("Categoria_Dim", [])
        if not isinstance(categories, list):
            continue
        for category_group in categories:
            if not isinstance(category_group, dict):
                continue
            for category_list in category_group.values():
                if not isinstance(category_list, list):
                    continue
                for category in category_list:
                    if not isinstance(category, dict) or str(
                        category.get("dim_num")
                    ) != "1":
                        continue
                    label = str(category.get("categ_dsg", "")).strip()
                    if re.fullmatch(r"\d{4}", label):
                        years.add(int(label))
                        continue
                    code = str(category.get("categ_cod", ""))
                    match = re.search(r"(\d{4})$", code)
                    if match:
                        years.add(int(match.group(1)))

    if not years:
        raise RuntimeError("No annual periods found in INE indicator metadata.")
    return sorted(years)


def fetch_available_annual_years(varcd: str) -> list[int]:
    """Fetch an indicator's metadata and return its available annual years."""
    return available_annual_years(fetch_indicator_metadata(varcd))
