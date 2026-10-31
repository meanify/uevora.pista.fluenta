"""Raio-X do concelho: one municipality compared with its peers."""

from .. import measures as m
from ..queries import (
    ALENTEJO,
    latest,
    param_text,
    param_year,
    REFERENCE_YEAR,
    RESIDENCE_AGGREGATES,
    _by_year,
    _check,
    _index,
    _monthly_values,
    _num,
    _pooled,
    _segment,
    _total,
    _years_with,
)


def raio_x(frames, municipio, ano):
    acc = frames["acc"]
    total = _segment(acc, "Total")
    names = set(total["municipio"])
    _check(municipio, names, "municipio")
    _check(ano, _years_with(total, "dormidas"), "ano")
    nuts3 = total.loc[total["municipio"] == municipio, "nuts_iii"].iloc[0]
    peers = sorted(set(total.loc[total["nuts_iii"] == nuts3, "municipio"]))
    area = frames["area"].set_index("municipio")["area"]

    rooms_year = m.latest_year(_years_with(total, "quartos"), ano)
    year_rows = total[total["ano"] == ano].set_index("municipio")
    room_rows = total[total["ano"] == rooms_year].set_index("municipio")
    local = _segment(acc, "Alojamento local")
    local_rooms = local[local["ano"] == rooms_year].set_index("municipio")["quartos"]

    def value(rows, name, column):
        return _num(rows[column].get(name)) if name in rows.index else None

    pressure = [
        {
            "municipio": name,
            "dormidas_km2": m.ratio(value(year_rows, name, "dormidas"), _num(area.get(name))),
        }
        for name in peers
    ]
    pressure.sort(key=lambda r: -(r["dormidas_km2"] or 0))
    others = [name for name in peers if name != municipio]
    other_rows = year_rows.loc[year_rows.index.intersection(others)]
    other_area = sum(_num(area.get(n)) or 0 for n in other_rows.index[other_rows["dormidas"].notna()])

    monthly = frames["monthly"]
    own_months = _monthly_values(monthly[monthly["municipio"] == municipio], ano)
    # Peers add up only municipalities with all twelve months published, so a
    # confidential month never shows up as a dip. The Alentejo row is the
    # published regional total (0009808, NUTS 2013), not a municipal sum.
    complete_peers = [
        name for name in others
        if all(v is not None for v in _monthly_values(monthly[monthly["municipio"] == name], ano))
    ]
    peer_months = _monthly_values(monthly[monthly["municipio"].isin(complete_peers)], ano) \
        if complete_peers else [None] * 12
    regions = frames["regions"]
    region_months = _monthly_values(regions[regions["nuts_ii"] == ALENTEJO], ano)
    monthly_years = _years_with(monthly, "dormidas")
    peak = None
    if all(v is not None for v in own_months) and sum(own_months):
        top = max(range(12), key=lambda i: own_months[i])
        peak = {"mes": top + 1, "quota": own_months[top] / sum(own_months) * 100}

    markets = frames["markets"]
    markets = markets[markets["ano"] == ano]
    own = markets[markets["municipio"] == municipio].set_index("local_residencia")["hospedes"]
    region = markets.groupby("local_residencia")["hospedes"].sum(min_count=1)
    own_total, region_total = _num(own.get("Total")), _num(region.get("Total"))
    # Portugal is reported apart: its share gap is usually far larger than any
    # foreign market's and would flatten the chart.
    def share_gap(residence):
        own_share = m.ratio(_num(own.get(residence)), own_total)
        region_share = m.ratio(_num(region.get(residence)), region_total)
        return None if own_share is None or region_share is None else (own_share - region_share) * 100

    differences, confidential = [], 0
    for residence in region.index:
        if residence in RESIDENCE_AGGREGATES:
            continue
        own_value = _num(own.get(residence))
        if own_value is None:
            confidential += 1
            continue
        gap = share_gap(residence)
        if gap is not None:
            differences.append({"mercado": residence, "dif_pp": gap})
    differences.sort(key=lambda r: -abs(r["dif_pp"]))
    differences = sorted(differences[:8], key=lambda r: -r["dif_pp"])

    years = _years_with(total, "dormidas")
    base = REFERENCE_YEAR if REFERENCE_YEAR in years else years[0]
    evolution = {
        municipio: _by_year(total[total["municipio"] == municipio], "dormidas"),
        nuts3: _by_year(total[total["nuts_iii"] == nuts3], "dormidas"),
        "Alentejo (NUTS 2013)": _by_year(total, "dormidas"),
    }

    own_nights, own_guests = value(year_rows, municipio, "dormidas"), value(year_rows, municipio, "hospedes")
    return {
        "municipio": municipio,
        "nuts_iii": nuts3,
        "ano": ano,
        "ano_quartos": rooms_year,
        "ano_area": _num(frames["area"].set_index("municipio")["ano"].get(municipio)),
        "kpis": {
            "dormidas": own_nights,
            "dormidas_km2": m.ratio(own_nights, _num(area.get(municipio))),
            "dormidas_km2_pares": m.ratio(_total(other_rows, "dormidas"), other_area),
            "quartos_km2": m.ratio(value(room_rows, municipio, "quartos"), _num(area.get(municipio))),
            "peso_al": (lambda r: None if r is None else r * 100)(
                m.ratio(_num(local_rooms.get(municipio)), value(room_rows, municipio, "quartos"))),
            "estada": m.ratio(own_nights, own_guests),
            "estada_pares": _pooled(other_rows, "dormidas", "hospedes"),
            "pico": peak,
        },
        "pressao": pressure,
        "calendario": [
            {"nome": municipio, "valores": own_months},
            {"nome": "Pares", "valores": peer_months},
            {"nome": "Alentejo (NUTS 2013)", "valores": region_months},
        ],
        "calendario_pares": {"completos": len(complete_peers), "total": len(others)},
        "mensal_desde": monthly_years[0] if monthly_years else None,
        "mercados": differences,
        "mercados_confidenciais": confidential,
        "portugal_dif_pp": share_gap("Portugal"),
        "evolucao": {
            "anos": years,
            "base": base,
            "series": [{"nome": name, "valores": [_index(s, base).get(y) for y in years]}
                       for name, s in evolution.items()],
        },
    }


ROUTE = "raio-x"


def route(frames, params):
    """Answer /api/raio-x from the parsed query string."""
    return raio_x(frames, param_text(params, "municipio", "Évora"),
                  param_year(params, "ano", latest(frames, "anos_anuais")))
