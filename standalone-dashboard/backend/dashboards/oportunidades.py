"""Mapa de oportunidades: demand vs supply growth and RevPAR."""

import pandas as pd

from .. import measures as m
from .noites_quartos import STAR_SUBTYPES, supply_demand_index
from ..queries import (
    latest,
    param_text,
    param_year,
    reference_or_first,
    BadRequest,
    DAYS_PER_YEAR,
    MIN_ROOMS_FOR_GAP,
    REVPAR_CATEGORIES,
    SEGMENTS,
    TERRITORIES,
    _check,
    _check_territory,
    _num,
    _pooled,
    _revpar_estimate,
    _segment,
    _territory,
    _total,
    _years_with,
)


TOP_HOTEL_CATEGORIES = [("Hotelaria", subtype, stars)
                        for subtype in STAR_SUBTYPES for stars in ("4 estrelas", "5 estrelas")]


def _revpar_categories(accommodation, keys, year):
    """Room-weighted RevPAR over several categories, latest published year up to year.

    Rooms by star class are often confidential in the years their RevPAR is
    published, so each municipality and category is weighted by its own latest
    published rooms up to the RevPAR year.
    """
    cells = pd.concat([_segment(accommodation, key) for key in keys])
    revpar_year = m.latest_year(_years_with(cells, "revpar"), year)
    if revpar_year is None:
        return None
    cell = ["municipio", "subtipo_alojamento", "classificacao"]
    rooms = (cells[(cells["ano"] <= revpar_year) & cells["quartos"].notna()]
             .sort_values("ano").groupby(cell).last()[["ano", "quartos"]])
    revpar = cells[(cells["ano"] == revpar_year) & cells["revpar"].notna()].set_index(cell)
    paired = revpar[["revpar"]].join(rooms, how="inner")
    value = m.weighted_mean(zip(paired["revpar"].map(_num), paired["quartos"].map(_num)))
    if value is None:
        return None
    return {
        "valor": value,
        "ano": revpar_year,
        "ano_quartos": int(paired["ano"].max()),
        "ano_quartos_min": int(paired["ano"].min()),
        "municipios": paired.index.get_level_values("municipio").nunique(),
        "sem_quartos": len(revpar) - len(paired),
    }


def oportunidades(frames, inicio, fim, segmento, territory):
    territory = _check_territory(territory)
    _check(segmento, SEGMENTS, "seg")
    acc = _territory(frames["acc"], territory)
    total = _segment(acc, "Total")
    years = sorted(set(_years_with(total, "dormidas")) & set(_years_with(total, "quartos")))
    _check(inicio, years, "inicio")
    _check(fim, years, "fim")
    if inicio >= fim:
        raise BadRequest("O ano inicial tem de ser anterior ao ano final.")
    rows = _segment(acc, segmento)

    def at(year):
        return rows[rows["ano"] == year].set_index("municipio")

    start, end = at(inicio), at(fim)
    gaps = []
    for name in end.index.intersection(start.index):
        rooms0, nights0 = _num(start.at[name, "quartos"]), _num(start.at[name, "dormidas"])
        if rooms0 is None or rooms0 < MIN_ROOMS_FOR_GAP or not nights0:
            continue
        nights_growth = m.growth(_num(end.at[name, "dormidas"]), nights0)
        rooms_growth = m.growth(_num(end.at[name, "quartos"]), rooms0)
        if nights_growth is not None and rooms_growth is not None:
            gaps.append({"municipio": name, "gap": nights_growth - rooms_growth,
                         "cresc_dormidas": nights_growth, "cresc_quartos": rooms_growth})
    gaps.sort(key=lambda r: -r["gap"])
    gap_by_name = {g["municipio"]: g["gap"] for g in gaps}

    total_end = total[total["ano"] == fim]
    shares = []
    for name in SEGMENTS:
        if name == "Total":
            continue
        segment_end = _segment(acc, name)
        segment_end = segment_end[segment_end["ano"] == fim]
        room_share = m.ratio(_total(segment_end, "quartos"), _total(total_end, "quartos"))
        night_share = m.ratio(_total(segment_end, "dormidas"), _total(total_end, "dormidas"))
        shares.append({
            "segmento": name,
            "quartos": None if room_share is None else room_share * 100,
            "dormidas": None if night_share is None else night_share * 100,
        })

    # Every category uses the year of the all-types RevPAR, so bars are comparable.
    revpar = []
    revpar_total = _revpar_estimate(acc, "Total", fim)
    for label, key in REVPAR_CATEGORIES if revpar_total else []:
        estimate = _revpar_estimate(acc, key, revpar_total["ano"], exact=True)
        if estimate:
            revpar.append({"categoria": label, **estimate})

    establishments_year = m.latest_year(_years_with(rows, "estabelecimentos"), fim)
    sizes = at(establishments_year) if establishments_year else end.iloc[0:0]
    scatter = []
    for name in end.index:
        size = m.ratio(_num(sizes["quartos"].get(name)), _num(sizes["estabelecimentos"].get(name)))
        use = m.ratio(_num(end.at[name, "dormidas"]), _num(end.at[name, "quartos"]))
        if size is not None and use is not None:
            scatter.append({"municipio": name, "quartos_estab": size,
                            "dormidas_quarto": use, "gap": gap_by_name.get(name)})

    revenue = None
    if revpar_total:
        revpar_rows = total[total["ano"] == revpar_total["ano"]].set_index("municipio")["revpar"]
        rooms = total[total["ano"] == revpar_total["ano_quartos"]].set_index("municipio")["quartos"]
        covered = [(r, _num(rooms.get(n))) for n, r in revpar_rows.items() if _num(r) is not None]
        covered = [(r, q) for r, q in covered if q]
        all_rooms = _num(rooms.sum(min_count=1))
        revenue = {
            "valor": sum(r * q for r, q in covered) * DAYS_PER_YEAR,
            "ano": revpar_total["ano"],
            "cobertura_quartos": m.ratio(sum(q for _, q in covered), all_rooms),
        }

    return {
        "inicio": inicio,
        "fim": fim,
        "segmento": segmento,
        "territorio": TERRITORIES[territory],
        "ano_estabelecimentos": establishments_year,
        "min_quartos": MIN_ROOMS_FOR_GAP,
        "kpis": {
            "dormidas_quarto": _pooled(end, "dormidas", "quartos"),
            "quartos_estab": _pooled(sizes, "quartos", "estabelecimentos"),
            "revpar_4_5": _revpar_categories(acc, TOP_HOTEL_CATEGORIES, fim),
            "revpar_hotelaria": _revpar_estimate(acc, "Hotelaria", fim),
            "revpar_ter": _revpar_estimate(acc, "TER e habitação", fim),
            "receita": revenue,
        },
        "gap": gaps,
        "quotas": shares,
        "revpar": revpar,
        "dispersao": scatter,
        "indice": supply_demand_index(rows),
    }


ROUTE = "oportunidades"


def route(frames, params):
    """Answer /api/oportunidades from the parsed query string."""
    return oportunidades(
        frames, param_year(params, "inicio", reference_or_first(frames, "anos_oferta_procura")),
        param_year(params, "fim", latest(frames, "anos_oferta_procura")),
        param_text(params, "seg", "Total"), param_text(params, "terr", "2024"))
