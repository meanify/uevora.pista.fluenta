"""Validated transformations for INE geographic and metric fields."""

from math import isfinite

from pistadigital.utils.distritos import DISTRITOS


def metric_value(raw_value):
    """Preserve zero and represent unavailable INE metrics as null."""
    if raw_value is None or (
        isinstance(raw_value, str) and raw_value in ("", "..", "s.r.", "x")
    ):
        return None
    if isinstance(raw_value, bool):
        raise ValueError(f"Malformed numeric value: {raw_value!r}")
    try:
        value = float(str(raw_value).replace(",", "."))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Malformed numeric value: {raw_value!r}") from exc
    if not isfinite(value):
        raise ValueError(f"Malformed numeric value: {raw_value!r}")
    return value


def nuts_i_ii_fields(geocode, geography):
    """Map verified NUTS I/II prefixes using the source's own geography version."""
    if geocode not in geography or (geocode != "PT" and len(geocode) not in (1, 2)):
        raise ValueError(f"Unsupported NUTS I/II geography code: {geocode!r}")
    if geocode == "PT":
        return {"nuts_i": geography[geocode], "nuts_ii": "Total"}
    return {
        "nuts_i": geography[geocode[:1]],
        "nuts_ii": geography[geocode] if len(geocode) == 2 else "Total",
    }


def nuts_2013_fields(geocode, geography):
    """Map verified NUTS-2013 prefixes and seven-character municipality codes."""
    if geocode not in geography or len(geocode) not in (1, 2, 3, 7):
        raise ValueError(f"Unsupported NUTS-2013 geography code: {geocode!r}")
    if geocode == "PT":
        return dict(
            nuts_i=geography[geocode], nuts_ii="Total", nuts_iii="Total",
            distrito="Total", municipio="Total",
        )
    municipality = len(geocode) == 7
    return {
        "nuts_i": geography[geocode[:1]],
        "nuts_ii": geography[geocode[:2]] if len(geocode) >= 2 else "Total",
        "nuts_iii": geography[geocode[:3]] if len(geocode) >= 3 else "Total",
        "distrito": DISTRITOS[geocode[-4:-2]] if municipality else "Total",
        "municipio": geography[geocode] if municipality else "Total",
    }


def nuts_i_ii_accommodation_fields(row, dimensions):
    """Map the verified monthly regional accommodation breakdown."""
    if row["dim_3"] != "T" and len(row["dim_3"]) not in (2, 4):
        raise ValueError("Only accommodation types/subtypes are supported.")
    accommodation = accommodation_fields(row["dim_3"], dimensions["3"])
    return {
        **nuts_i_ii_fields(row["geocod"], dimensions["2"]),
        "tipo_alojamento": accommodation["tipo_alojamento"],
        "subtipo_alojamento": accommodation["subtipo_alojamento"],
    }


def filter_detail_rows(frame, records, dimensions):
    """Drop API aggregates: coarser geocodes and intermediate accommodation codes.

    The accommodation total ``T`` is kept because INE suppresses many detailed
    municipal values, so the detail rows do not add up to it.
    """
    geocode_length = (
        7 if "municipio" in frame.columns else 2 if "nuts_ii" in frame.columns else None
    )
    accommodation = "tipo_alojamento" in frame.columns
    codes = dimensions.get("3", {})
    leaves = {"T"} | {code for code in codes if code != "T" and not any(
        other != code and other.startswith(code) for other in codes
    )}
    keep = [
        (geocode_length is None
         or (row["geocod"] != "PT" and len(row["geocod"]) == geocode_length))
        and (not accommodation or row["dim_3"] in leaves)
        for row in records
    ]
    return frame.loc[keep].reset_index(drop=True)


def accommodation_fields(code, labels):
    """Map the INE hierarchy and normalize local/rural accommodation labels.

    Levels below the API code repeat that code's own label.
    """
    if code not in labels or (code != "T" and len(code) not in (2, 4, 6)):
        raise ValueError(f"Unsupported accommodation code: {code!r}")
    fields = {
        "tipo_alojamento": labels[code[:2]],
        "subtipo_alojamento": labels[code[:4]],
        "classificacao": labels[code],
    }
    accommodation_type = fields["tipo_alojamento"].lower()
    if accommodation_type == "alojamento local":
        fields["classificacao"] = "Alojamento Local"
        fields["subtipo_alojamento"] = "Alojamento Local"
    else:
        rural_label = "Turismo no Espaço Rural e de Habitação"
        if "rural" in accommodation_type or "habitação" in accommodation_type:
            fields["classificacao"] = rural_label
        if "rural" in accommodation_type:
            fields["subtipo_alojamento"] = rural_label
    return fields
