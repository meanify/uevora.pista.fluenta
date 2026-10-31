"""Pulso do Alentejo: volume, seasonality and weight of the region in Portugal."""

from .. import measures as m
from ..queries import (
    latest,
    param_text,
    param_year,
    portugal,
    REFERENCE_YEAR,
    SEGMENTS,
    TERRITORIES,
    TOURISM_TERRITORIES,
    _alentejo_monthly,
    _by_year,
    _check,
    _check_territory,
    _complete_years,
    _index,
    _monthly_values,
    _num,
    _revpar_estimate,
    _segment,
    _territory,
    _total,
    _years_with,
)

# Accommodation types of the rooms mix (SEGMENTS keys).
MIX_TYPES = ["Hotelaria", "Alojamento local", "TER e habitação"]
MIX_UNASSIGNED = "Não atribuído (conf.)"
# Years of the month x year heatmap, ending at the selected year.
HEATMAP_YEARS = 7


def _diff(current, previous):
    return None if current is None or previous is None else current - previous


def _pct(value):
    return None if value is None else value * 100


def _portugal_monthly(frames):
    """Portugal's monthly nights from 0009808: the Portugal row, else the sum of NUTS II."""
    regions = frames["regions"]
    rows = regions[(regions["nuts_i"] == "Portugal") & (regions["nuts_ii"] == "Total")]
    if rows["dormidas"].notna().any():
        return rows[["ano", "mes", "dormidas"]]
    rows = regions[regions["nuts_ii"] != "Total"]
    return rows.groupby(["ano", "mes"], as_index=False)["dormidas"].sum(min_count=1)


def _annual_complete(monthly):
    """Annual sums of the years with the twelve months published."""
    return {year: sum(_monthly_values(monthly, year)) for year in _complete_years(monthly)}


def _jul_sep(values):
    if not values or not all(m.is_number(v) for v in values) or not sum(values):
        return None
    return sum(values[6:9]) / sum(values) * 100


def _seasonality_row(label, year, values):
    indicators = m.seasonality(values)
    if indicators is None:
        return None
    return {"nome": label, "ano": year, **indicators, "quota_jul_set": _jul_sep(values)}


def _domestic_share(rows, year):
    """Share of nights by residents in Portugal, from the INE total rows."""
    rows = rows[rows["ano"] == year]
    domestic = _total(rows[rows["local_residencia"] == "Portugal"], "dormidas")
    everyone = _total(rows[rows["local_residencia"] == "Total"], "dormidas")
    return _pct(m.ratio(domestic, everyone))


def _tourism_territories(total, ano):
    """Growth of nights of each tourism territory over municipalities published in both years."""
    result = []
    for name, members in TOURISM_TERRITORIES.items():
        rows = total[total["municipio"].isin(members)]
        now = rows[rows["ano"] == ano].set_index("municipio")["dormidas"]
        before = rows[rows["ano"] == ano - 1].set_index("municipio")["dormidas"]
        both = [c for c in members if _num(now.get(c)) is not None and _num(before.get(c)) is not None]
        result.append({
            "territorio": name,
            "municipios": members,
            "variacao": m.growth(sum(_num(now[c]) for c in both), sum(_num(before[c]) for c in both))
            if both else None,
            "omitidos": [c for c in members if c not in both],
        })
    return result


def _rooms_mix(total_acc, national, ano):
    """Share of rooms by accommodation type, Alentejo vs Portugal, latest rooms year <= ano."""
    year = m.latest_year(_years_with(_segment(total_acc, "Total"), "quartos"), ano)
    if year is None:
        return None

    def shares(rooms_of):
        # Confidential municipal values leave part of the total unassigned to a type.
        everyone = rooms_of("Total")
        values = [_pct(m.ratio(rooms_of(t), everyone)) for t in MIX_TYPES]
        known = [v for v in values if v is not None]
        return values + [max(0.0, 100 - sum(known)) if known else None]

    def alentejo(segment):
        rows = _segment(total_acc, segment)
        return _total(rows[rows["ano"] == year], "quartos")

    def country(segment):
        rows = _segment(national, SEGMENTS[segment])
        return _total(rows[rows["ano"] == year], "quartos")

    return {"ano": year, "tipos": MIX_TYPES + [MIX_UNASSIGNED], "alentejo": shares(alentejo), "portugal": shares(country)}


def pulso(frames, ano, territory):
    territory = _check_territory(territory)
    acc = _territory(frames["acc"], territory)
    total = _segment(acc, "Total")
    _check(ano, _years_with(total, "dormidas"), "ano")
    nights = _by_year(total, "dormidas")
    guests = _by_year(total, "hospedes")
    pt = portugal(frames)
    pt_nights = {int(y): _num(v) for y, v in pt["dormidas"].items()}
    pt_guests = {int(y): _num(v) for y, v in pt["hospedes"].items()}

    def stay(year):
        return m.ratio(nights.get(year), guests.get(year))

    def national_share(year):
        return _pct(m.ratio(nights.get(year), pt_nights.get(year)))

    markets = _territory(frames["markets"], territory)

    def international_share(year):
        rows = markets[markets["ano"] == year]
        foreign = _total(rows[rows["local_residencia"] == "Estrangeiro"], "dormidas")
        everyone = _total(rows[rows["local_residencia"] == "Total"], "dormidas")
        return _pct(m.ratio(foreign, everyone))

    revpar = _revpar_estimate(acc, "Total", ano)
    revpar_previous = revpar_pt = None
    if revpar:
        previous = _revpar_estimate(acc, "Total", revpar["ano"] - 1)
        if previous and previous["ano"] == revpar["ano"] - 1:
            revpar_previous = previous["valor"]
        revpar_pt = _num(pt["revpar"].get(revpar["ano"])) if "revpar" in pt else None

    share, share_previous = international_share(ano), international_share(ano - 1)
    stay_now, stay_previous = stay(ano), stay(ano - 1)
    quota, quota_previous = national_share(ano), national_share(ano - 1)

    monthly, municipal_sum = _alentejo_monthly(frames, territory)
    available_monthly = sorted(int(y) for y in monthly["ano"].unique())
    series = [
        {"ano": year, "valores": _monthly_values(monthly, year)}
        for year in (ano, ano - 1, REFERENCE_YEAR)
        if year in available_monthly
    ]
    complete = _complete_years(monthly)
    seasonality_years = sorted({REFERENCE_YEAR, ano - 2, ano - 1, ano} & set(complete))
    pt_monthly = _portugal_monthly(frames)
    pt_seasonality = None
    if ano in _complete_years(pt_monthly):
        pt_seasonality = _seasonality_row("Portugal", ano, _monthly_values(pt_monthly, ano))

    heatmap_years = [y for y in available_monthly if ano - HEATMAP_YEARS < y <= ano]

    nuts3 = []
    for name, rows in total.groupby("nuts_iii"):
        by_year = _by_year(rows, "dormidas")
        nuts3.append({"nuts_iii": name, "variacao": m.growth(by_year.get(ano), by_year.get(ano - 1))})

    regions = frames["regions"]
    regions = regions[regions["nuts_ii"] != "Total"]
    positioning = []
    for name, rows in regions.groupby("nuts_ii"):
        if ano not in _complete_years(rows) or ano - 1 not in _complete_years(rows):
            continue
        by_nights = _by_year(rows, "dormidas")
        by_guests = _by_year(rows, "hospedes")
        positioning.append({
            "regiao": name,
            "crescimento": m.growth(by_nights.get(ano), by_nights.get(ano - 1)),
            "estada": m.ratio(by_nights.get(ano), by_guests.get(ano)),
        })

    # Index 2019 = 100: Alentejo from the annual table of the selected territory,
    # Portugal and Centro from the monthly regional table, complete years only.
    pt_annual = _annual_complete(pt_monthly)
    centro_annual = _annual_complete(regions[regions["nuts_ii"] == "Centro"])
    base = REFERENCE_YEAR if REFERENCE_YEAR in nights else min(nights)
    index_years = [y for y in sorted(nights) if min(base, ano) <= y <= max(base, ano)]

    def indexed(values):
        values = _index(values, base)
        return [values.get(y) for y in index_years]

    return {
        "ano": ano,
        "territorio": TERRITORIES[territory],
        "kpis": {
            "dormidas": nights.get(ano),
            "dormidas_var": m.growth(nights.get(ano), nights.get(ano - 1)),
            "dormidas_pt_var": m.growth(pt_nights.get(ano), pt_nights.get(ano - 1)),
            "hospedes": guests.get(ano),
            "hospedes_var": m.growth(guests.get(ano), guests.get(ano - 1)),
            "hospedes_pt_var": m.growth(pt_guests.get(ano), pt_guests.get(ano - 1)),
            "estada": stay_now,
            "estada_dif": _diff(stay_now, stay_previous),
            "estada_pt": m.ratio(pt_nights.get(ano), pt_guests.get(ano)),
            "quota_nacional": quota,
            "quota_nacional_dif": _diff(quota, quota_previous),
            "mercado_interno": _domestic_share(markets, ano),
            "mercado_interno_pt": _domestic_share(frames["pt_markets"], ano),
            "revpar": revpar,
            "revpar_var": m.growth(revpar["valor"], revpar_previous) if revpar else None,
            "revpar_pt": revpar_pt,
            "quota_internacional": share,
            "quota_internacional_dif": _diff(share, share_previous),
            "indice_2019": _index(nights, REFERENCE_YEAR).get(ano),
        },
        "sazonalidade": {"series": series, "soma_municipal": municipal_sum},
        "heatmap": {
            "anos": heatmap_years,
            "linhas": [{"nome": str(y), "valores": _monthly_values(monthly, y)} for y in heatmap_years],
        },
        "nuts3": sorted(nuts3, key=lambda r: -(r["variacao"] or -1e9)),
        "territorios": _tourism_territories(_segment(frames["acc"], "Total"), ano),
        "indice": {
            "base": base,
            "anos": index_years,
            "alentejo": indexed(nights),
            "portugal": indexed(pt_annual),
            "centro": indexed(centro_annual),
        },
        "posicionamento": positioning,
        "mix": _rooms_mix(acc, frames["pt_acc"], ano),
        "indicadores_sazonalidade": [
            {"ano": year, **m.seasonality(_monthly_values(monthly, year)),
             "quota_jul_set": _jul_sep(_monthly_values(monthly, year))}
            for year in seasonality_years
        ],
        "sazonalidade_portugal": pt_seasonality,
    }


ROUTE = "pulso"


def route(frames, params):
    """Answer /api/pulso from the parsed query string."""
    return pulso(frames, param_year(params, "ano", latest(frames, "anos_anuais")),
                 param_text(params, "terr", "2024"))
