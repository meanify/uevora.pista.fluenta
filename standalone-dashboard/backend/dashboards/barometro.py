"""Barómetro do empresário: one municipality and segment, month by month.

The municipal months come from 0010735 (nights) and 0010736 (guests), which
start in 2020; the last year is partial. Alentejo (NUTS 2013) and Portugal
come from the regional tables 0009808/0009812 for the same accommodation type,
so their totals are the published ones, not sums of municipalities.
"""

from .. import measures as m
from ..queries import (
    ALENTEJO,
    BadRequest,
    MONTHLY_SEGMENTS,
    SEGMENTS,
    _check,
    _complete_years,
    _monthly_values,
    _num,
    latest_month,
    param_text,
)


ROUTE = "barometro"
SEGMENT_LABELS = {key: label for label, key in MONTHLY_SEGMENTS.items()}
# Rows shown in "Onde há margem para crescer".
MAX_GAPS = 5
# Gaps that round to 0,0 p.p. on screen are not shown as room to grow.
MIN_GAP_PP = 0.05


def _month_keys(monthly):
    """'YYYY-MM' of every month with any published municipal nights, oldest first."""
    rows = monthly.loc[monthly["dormidas"].notna(), ["ano", "mes"]].drop_duplicates()
    return [f"{ano}-{mes}" for ano, mes in sorted(zip(rows["ano"], rows["mes"]))]


def _region(frames, segment, portugal=False):
    """Regional monthly rows of the accommodation type that matches the segment."""
    tipo, subtipo, _ = SEGMENTS[segment]
    rows = frames["regions_tipo"]
    where = rows["nuts_i"] == "Portugal" if portugal else rows["nuts_ii"] == ALENTEJO
    return rows[where & (rows["tipo_alojamento"] == tipo) & (rows["subtipo_alojamento"] == subtipo)]


def _shares(values):
    """Share of each month in the year (%), only when all twelve are published."""
    if any(v is None for v in values) or not sum(values):
        return None
    total = sum(values)
    return [v / total * 100 for v in values]


def _value(frame, year, month, column="dormidas"):
    return _monthly_values(frame, year, column)[month - 1] if year is not None else None


def barometro(frames, municipio, segmento, ano, mes):
    seg = frames["monthly_seg"]
    _check(municipio, set(seg["municipio"]), "municipio")
    _check(segmento, SEGMENTS, "seg")
    if f"{ano}-{mes:02d}" not in _month_keys(frames["monthly"]):
        raise BadRequest(f"Valor inválido para mes: {ano}-{mes:02d}")
    place = seg[seg["municipio"] == municipio]
    nuts3 = place["nuts_iii"].iloc[0]
    own = place[place["segmento_alojamento"] == SEGMENT_LABELS[segmento]]
    alentejo, portugal = _region(frames, segmento), _region(frames, segmento, portugal=True)

    nights = _value(own, ano, mes)
    alentejo_nights = _value(alentejo, ano, mes)

    # Profile, weakest month and gaps use the latest complete year of the
    # municipality up to the selected one; the regions use the same year.
    own_years = [y for y in _complete_years(own) if y <= ano]
    region_years = [y for y in _complete_years(alentejo) if y <= ano]
    profile_year = own_years[-1] if own_years else (region_years[-1] if region_years else None)
    profile = {
        name: _shares(_monthly_values(frame, profile_year)) if profile_year else None
        for name, frame in ((municipio, own), ("Alentejo (NUTS 2013)", alentejo), ("Portugal", portugal))
    }
    own_profile, region_profile = profile[municipio], profile["Alentejo (NUTS 2013)"]
    weakest = None
    if own_profile:
        low = min(range(12), key=lambda i: own_profile[i])
        weakest = {"mes": low + 1, "quota": own_profile[low]}
    gaps = []
    if own_profile and region_profile:
        gaps = sorted(
            ({"mes": i + 1, "concelho": own_profile[i], "alentejo": region_profile[i],
              "dif_pp": own_profile[i] - region_profile[i]}
             for i in range(12) if own_profile[i] - region_profile[i] <= -MIN_GAP_PP),
            key=lambda r: r["dif_pp"])

    current, previous = _monthly_values(own, ano), _monthly_values(own, ano - 1)
    years = sorted(int(y) for y in seg["ano"].unique())
    last = latest_month(frames["monthly"])

    return {
        "municipio": municipio,
        "nuts_iii": nuts3,
        "segmento": segmento,
        "ano": ano,
        "mes": mes,
        "ultimo_mes": last,
        "kpis": {
            "dormidas": nights,
            "dormidas_var": m.growth(nights, _value(own, ano - 1, mes)),
            "alentejo_var": m.growth(alentejo_nights, _value(alentejo, ano - 1, mes)),
            "estada": m.ratio(nights, _value(own, ano, mes, "hospedes")),
            "peso": (lambda r: None if r is None else r * 100)(m.ratio(nights, alentejo_nights)),
            "mes_fraco": weakest,
        },
        "perfil": {
            "ano": profile_year,
            "series": [{"nome": name, "valores": values} for name, values in profile.items()],
        },
        # Only months published in both years; the rest stay None.
        "homologa": {
            "ano": ano,
            "ano_anterior": ano - 1,
            "valores": [m.growth(c, p) for c, p in zip(current, previous)],
            "meses_comparados": sum(1 for c, p in zip(current, previous)
                                    if c is not None and p is not None),
        },
        "calendario": [{"nome": str(year), "valores": _monthly_values(own, year)} for year in years],
        "margem": gaps[:MAX_GAPS],
        "margem_total": len(gaps),
    }


def _param_month(params, default):
    value = param_text(params, "mes", default)
    try:
        ano, mes = (int(part) for part in value.split("-"))
    except ValueError as exc:
        raise BadRequest(f"Valor inválido para mes: {value!r}") from exc
    return ano, mes


def route(frames, params):
    """Answer /api/barometro from the parsed query string (mes = 'YYYY-MM')."""
    last = latest_month(frames["monthly"])
    if last is None:
        raise BadRequest("Sem dados mensais municipais.")
    ano, mes = _param_month(params, f"{last['ano']}-{last['mes']:02d}")
    return barometro(frames, param_text(params, "municipio", "Évora"),
                     param_text(params, "seg", "Total"), ano, mes)
