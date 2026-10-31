"""Alentejo em números: chapters and the municipal table."""

from .. import measures as m
from ..queries import (
    latest,
    param_text,
    param_year,
    LITORAL,
    REFERENCE_YEAR,
    RESIDENCE_AGGREGATES,
    TERRITORIES,
    _alentejo_monthly,
    _by_year,
    _check,
    _check_territory,
    _complete_years,
    _index,
    _monthly_values,
    _num,
    _segment,
    _territory,
    _years_with,
)


def alentejo_em_numeros(frames, ano, territory):
    territory = _check_territory(territory)
    acc = _territory(frames["acc"], territory)
    total = _segment(acc, "Total")
    years = _years_with(total, "dormidas")
    _check(ano, years, "ano")

    regions = frames["regions"]
    portugal = regions[(regions["nuts_i"] == "Portugal") & (regions["nuts_ii"] == "Total")]
    portugal_years = set(_complete_years(portugal))
    alentejo_nights = _by_year(total, "dormidas")
    portugal_nights = {y: v for y, v in _by_year(portugal, "dormidas").items() if y in portugal_years}
    evolution_years = [y for y in years if y <= ano]
    first_year = evolution_years[0]
    recovery_years = [y for y in evolution_years if y >= REFERENCE_YEAR]

    monthly, municipal_sum = _alentejo_monthly(frames, territory)
    season_year = m.latest_year(_complete_years(monthly), ano)
    season = _monthly_values(monthly, season_year) if season_year else []
    season_total = sum(season) if season else None

    municipal = _territory(frames["monthly"], territory)
    coast_year = m.latest_year(_complete_years(municipal), ano)
    coast, inland = [], []
    if coast_year:
        coast = _monthly_values(municipal[municipal["nuts_iii"] == LITORAL], coast_year)
        inland = _monthly_values(municipal[municipal["nuts_iii"] != LITORAL], coast_year)

    def shares(values):
        valid = [v for v in values if v is not None]
        total_value = sum(valid) if valid else None
        return [m.ratio(v, total_value) * 100 if m.ratio(v, total_value) is not None else None for v in values]

    markets = _territory(frames["markets"], territory)
    sums = markets.groupby(["local_residencia", "ano"])["hospedes"].sum(min_count=1)
    foreign = []
    for residence in sums.index.get_level_values(0).unique():
        if residence in RESIDENCE_AGGREGATES:
            continue
        value = _num(sums.get((residence, ano)))
        if value is not None:
            foreign.append({
                "mercado": residence,
                "hospedes": value,
                "cresc_2019": m.growth(value, _num(sums.get((residence, REFERENCE_YEAR)))),
            })
    foreign.sort(key=lambda r: -r["hospedes"])
    domestic = m.ratio(_num(sums.get(("Portugal", ano))), _num(sums.get(("Total", ano))))

    area = frames["area"].set_index("municipio")["area"]
    region_area = _num(area[area.index.isin(set(total["municipio"]))].sum(min_count=1))
    alentejo_year, portugal_year = alentejo_nights.get(ano), portugal_nights.get(ano)
    year_rows = total[total["ano"] == ano].sort_values(["nuts_iii", "municipio"])
    revpar_published = bool(year_rows["revpar"].notna().any())
    table = [
        {
            "municipio": r.municipio,
            "nuts_iii": r.nuts_iii,
            "dormidas": _num(r.dormidas),
            "hospedes": _num(r.hospedes),
            "estada": m.ratio(_num(r.dormidas), _num(r.hospedes)),
            "dormidas_km2": m.ratio(_num(r.dormidas), _num(area.get(r.municipio))),
            "revpar": _num(r.revpar),
        }
        for r in year_rows.itertuples()
    ]

    return {
        "ano": ano,
        "territorio": TERRITORIES[territory],
        "destaques": {
            "dormidas": alentejo_year,
            "dormidas_portugal": portugal_year,
            # Portugal nights per Alentejo night: "1 in N nights in Portugal".
            "uma_em": m.ratio(portugal_year, alentejo_year),
            "quota_residentes": None if domestic is None else domestic * 100,
            "pico_vale": _peak_low(season) if season_total else None,
        },
        "evolucao": {
            "anos": evolution_years,
            "base": first_year,
            "alentejo": [_index(alentejo_nights, first_year).get(y) for y in evolution_years],
            "portugal": [_index(portugal_nights, first_year).get(y) for y in evolution_years],
            "dormidas": {str(y): alentejo_nights.get(y) for y in evolution_years},
        },
        "recuperacao": _recovery(alentejo_nights, portugal_nights, recovery_years),
        "densidade": {
            "alentejo": m.ratio(alentejo_year, region_area),
            "portugal": m.ratio(portugal_year, frames["info"].get("area_portugal")),
        },
        "sazonalidade": {
            "ano": season_year,
            "quotas": shares(season),
            "soma_municipal": municipal_sum,
            "indicadores": m.seasonality(season) if season_total else None,
        },
        "litoral_interior": {
            "ano": coast_year,
            "litoral": shares(coast),
            "interior": shares(inland),
        },
        "mercados": foreign[:8],
        "tabela": table,
        "revpar_publicado": revpar_published,
    }


def _peak_low(season):
    """Peak and low month (index 0..11) of twelve monthly values and their ratio."""
    peak, low = season.index(max(season)), season.index(min(season))
    return {"pico": peak, "vale": low, "razao": m.ratio(season[peak], season[low])}


def _recovery(alentejo, portugal, years):
    """Index 2019 = 100 for both series and the first year after 2020 back at 100."""
    if len(years) < 2 or years[0] != REFERENCE_YEAR:
        return {"anos": [], "base": REFERENCE_YEAR, "alentejo": [], "portugal": [],
                "recuperou_alentejo": None, "recuperou_portugal": None}
    series = {}
    for name, values in (("alentejo", alentejo), ("portugal", portugal)):
        index = _index(values, REFERENCE_YEAR)
        series[name] = [index.get(y) for y in years]
        series["recuperou_" + name] = next(
            (y for y in years if y > 2020 and index.get(y) is not None and index[y] >= 100), None)
    return {"anos": years, "base": REFERENCE_YEAR, **series}


ROUTE = "numeros"


def route(frames, params):
    """Answer /api/numeros from the parsed query string."""
    return alentejo_em_numeros(frames, param_year(params, "ano", latest(frames, "anos_anuais")),
                               param_text(params, "terr", "2024"))
