"""Radar de mercados: source markets, growth and length of stay."""

from .. import measures as m
from ..queries import (
    latest,
    param_text,
    param_year,
    REFERENCE_YEAR,
    RESIDENCE_AGGREGATES,
    TERRITORIES,
    _check,
    _check_territory,
    _num,
    _territory,
    _years_with,
)


def _national(frames):
    """get(residence, year, column) over Portugal's sums of municipalities."""
    sums = frames["pt_markets"].groupby(["local_residencia", "ano"])[["hospedes", "dormidas"]].sum(min_count=1)

    def get(residence, year, column):
        try:
            return _num(sums.loc[(residence, year), column])
        except KeyError:
            return None
    return get


def _domestic_share(get, year):
    """Share (%) of guests living in Portugal."""
    share = m.ratio(get("Portugal", year, "hospedes"), get("Total", year, "hospedes"))
    return None if share is None else share * 100


def _specialisation(top, get, national, year):
    """Location quotient of each market minus 1, in %, sorted from strongest.

    Share of the market among the Alentejo foreign guests divided by its share
    among Portugal's foreign guests; 0 means the same weight as in Portugal.
    """
    rows = []
    for market in top:
        name = market["mercado"]
        local = m.ratio(get(name, year, "hospedes"), get("Estrangeiro", year, "hospedes"))
        country = m.ratio(national(name, year, "hospedes"), national("Estrangeiro", year, "hospedes"))
        quotient = m.ratio(local, country)
        if quotient is not None:
            rows.append({"mercado": name, "quota_alentejo": local * 100, "quota_portugal": country * 100,
                         "indice": (quotient - 1) * 100})
    return sorted(rows, key=lambda r: -r["indice"])


def radar(frames, ano, base, territory):
    territory = _check_territory(territory)
    markets = _territory(frames["markets"], territory)
    _check(ano, [y for y in _years_with(markets, "hospedes") if y >= REFERENCE_YEAR], "ano")
    base_year = {"anterior": ano - 1, "2019": REFERENCE_YEAR}[_check(base, ("anterior", "2019"), "base")]
    sums = markets.groupby(["local_residencia", "ano"])[["hospedes", "dormidas"]].sum(min_count=1)

    def get(residence, year, column):
        try:
            return _num(sums.loc[(residence, year), column])
        except KeyError:
            return None

    countries = [r for r in sums.index.get_level_values(0).unique() if r not in RESIDENCE_AGGREGATES]
    foreign_nights = get("Estrangeiro", ano, "dormidas")
    foreign_guests = get("Estrangeiro", ano, "hospedes")
    growth_reference = m.growth(foreign_guests, get("Estrangeiro", base_year, "hospedes"))
    stay_reference = m.ratio(foreign_nights, foreign_guests)

    ranked = sorted(
        (c for c in countries if get(c, ano, "dormidas") is not None),
        key=lambda c: -get(c, ano, "dormidas"))
    top = []
    for country in ranked[:10]:
        growth_value = m.growth(get(country, ano, "hospedes"), get(country, base_year, "hospedes"))
        stay = m.ratio(get(country, ano, "dormidas"), get(country, ano, "hospedes"))
        share = m.ratio(get(country, ano, "dormidas"), foreign_nights)
        top.append({
            "mercado": country,
            "crescimento": growth_value,
            "estada": stay,
            "dormidas": get(country, ano, "dormidas"),
            "hospedes": get(country, ano, "hospedes"),
            "quota_dormidas": None if share is None else share * 100,
            "quadrante": m.quadrant(growth_value, stay, growth_reference, stay_reference),
        })

    def international(year):
        share = m.ratio(get("Estrangeiro", year, "hospedes"), get("Total", year, "hospedes"))
        return None if share is None else share * 100

    guests_by_country = sorted(
        (get(c, ano, "hospedes") for c in countries if get(c, ano, "hospedes") is not None), reverse=True)
    top3 = m.ratio(sum(guests_by_country[:3]), foreign_guests)

    year_rows = markets[markets["ano"] == ano]
    where = {}
    for market in top:
        rows = year_rows[(year_rows["local_residencia"] == market["mercado"]) & year_rows["dormidas"].notna()]
        rows = rows.sort_values("dormidas", ascending=False).head(5)
        where[market["mercado"]] = [
            {"municipio": r.municipio, "dormidas": _num(r.dormidas)} for r in rows.itertuples()]

    domestic, domestic_pt = _domestic_share(get, ano), _domestic_share(_national(frames), ano)
    quadrants = [
        {"quadrante": name, "acao": action,
         "mercados": [t["mercado"] for t in top if t["quadrante"] == name]}
        for name, action in m.QUADRANT_ACTIONS.items()
    ]
    share_now, share_base = international(ano), international(base_year)
    return {
        "ano": ano,
        "ano_base": base_year,
        "territorio": TERRITORIES[territory],
        "kpis": {
            "quota_internacional": share_now,
            "quota_internacional_dif": None if share_now is None or share_base is None else share_now - share_base,
            "hhi": m.hhi(guests_by_country),
            "top3": None if top3 is None else top3 * 100,
            "em_crescimento": sum(1 for t in top if (t["crescimento"] or 0) > 0),
            "mercados": len(top),
            "quota_interna": domestic,
            "quota_interna_portugal": domestic_pt,
        },
        "referencia": {"crescimento": growth_reference, "estada": stay_reference},
        "mercados": top,
        "onde": where,
        "especializacao": _specialisation(top, get, _national(frames), ano),
        "quadrantes": quadrants,
    }


ROUTE = "radar"


def route(frames, params):
    """Answer /api/radar from the parsed query string."""
    return radar(frames, param_year(params, "ano", latest(frames, "anos_mercados")),
                 param_text(params, "base", "anterior"), param_text(params, "terr", "2024"))
