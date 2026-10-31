"""Noites e quartos: demand, supply and the balance between them.

Three tabs from one payload: procura (nights, guests), oferta (rooms,
establishments) and equilíbrio (nights per room). Indicators with missing
years in the Alentejo (rooms 2025, establishments 2024) use the latest year up
to the selected one and return that year.
"""

from .. import measures as m
from ..queries import (
    latest,
    param_text,
    param_year,
    portugal,
    ALENTEJO,
    MIN_ROOMS_FOR_GAP,
    MONTHLY_SEGMENTS,
    REFERENCE_YEAR,
    SEGMENTS,
    TERRITORIES,
    _by_year,
    _check,
    _check_territory,
    _index,
    _monthly_values,
    _num,
    _pooled,
    _segment,
    _territory,
    _total,
    _years_with,
)


TYPES = [key for key in SEGMENTS if key != "Total"]
TER = "TER e habitação"
# Hotelaria subtypes with a star classification; Pousadas have none.
STAR_SUBTYPES = ["Hotéis", "Hotéis-apartamentos", "Apartamentos turísticos", "Aldeamentos turísticos"]
STAR_CLASSES = [
    ("5★", ["5 estrelas"]),
    ("4★", ["4 estrelas"]),
    ("3★", ["3 estrelas"]),
    ("1–2★", ["1 estrela", "2 estrelas"]),
]
POUSADAS = ("Hotelaria", "Pousadas/Quintas da Madeira", "Total")
# A gap within this many p.p. reads as balanced growth.
BALANCED_GAP = 2
TABLE_ROWS = 4  # largest and smallest gaps shown in the imbalance table


# --- helpers -------------------------------------------------------------------

def _at(rows, year):
    return rows[rows["ano"] == year] if year is not None else rows.iloc[0:0]


def _sum(rows, year, column):
    return _total(_at(rows, year), column)


def _latest_with(rows, columns, year):
    """Latest year up to year in which every column has a published value."""
    years = set.intersection(*(set(_years_with(rows, c)) for c in columns))
    return m.latest_year(sorted(years), year)


def _previous_with(rows, columns, year):
    return None if year is None else _latest_with(rows, columns, year - 1)


def _pt(national, year, column):
    if year is None or year not in national.index:
        return None
    return _num(national.at[year, column])


def _pt_ratio(national, year, numerator, denominator):
    return m.ratio(_pt(national, year, numerator), _pt(national, year, denominator))


def _base_year(years, end):
    """2019 when it is before end, else the first year before end."""
    earlier = [y for y in years if end is not None and y < end]
    return REFERENCE_YEAR if REFERENCE_YEAR in earlier else (earlier[0] if earlier else None)


def supply_demand_index(rows):
    """Nights and rooms indexed to the first year with both (= 100)."""
    nights, rooms = _by_year(rows, "dormidas"), _by_year(rows, "quartos")
    years = sorted(set(nights) | set(rooms))
    base = next((y for y in years if nights.get(y) is not None and rooms.get(y) is not None), None)
    if base is None:
        return {"base": None, "anos": years, "dormidas": [None] * len(years),
                "quartos": [None] * len(years)}
    nights_index, rooms_index = _index(nights, base), _index(rooms, base)
    return {"base": base, "anos": years,
            "dormidas": [nights_index.get(y) for y in years],
            "quartos": [rooms_index.get(y) for y in years]}


def _monthly(frames, territory, segment, year):
    """Twelve months of nights and guests for the Alentejo and a segment.

    NUTS 2013 uses the regional tables 0009808/0009812 (exact, since 2017);
    NUTS 2024 sums the municipal months of 0010735/0010736 (since 2020),
    leaving confidential municipal months out.
    """
    if territory == "2013":
        tipo, subtipo, _ = SEGMENTS[segment]
        rows = frames["regions_tipo"]
        rows = rows[(rows["nuts_ii"] == ALENTEJO) & (rows["tipo_alojamento"] == tipo)
                    & (rows["subtipo_alojamento"] == subtipo)]
    else:
        label = {key: name for name, key in MONTHLY_SEGMENTS.items()}[segment]
        rows = _territory(frames["monthly_seg"], territory)
        rows = rows[rows["segmento_alojamento"] == label]
    return {
        "dormidas": _monthly_values(rows, year, "dormidas"),
        "hospedes": _monthly_values(rows, year, "hospedes"),
        "soma_municipal": territory != "2013",
    }


def _by_nuts3(rows, year, column):
    year_rows = _at(rows, year)
    result = []
    for name, group in year_rows.groupby("nuts_iii"):
        result.append({"nuts_iii": name, "valor": _total(group, column),
                       "conf": int(group[column].isna().sum())})
    return sorted(result, key=lambda r: -(r["valor"] or 0))


def _change(rows, columns, year, column, national=None):
    """Value in year, its growth on the previous year with data, and Portugal's."""
    previous = _previous_with(rows, columns, year)
    value = _sum(rows, year, column)
    result = {"valor": value, "ano": year, "ano_anterior": previous,
              "var": m.growth(value, _sum(rows, previous, column))}
    if national is not None:
        result["pt_var"] = m.growth(_pt(national, year, column), _pt(national, previous, column))
        result["pt"] = _pt(national, year, column)
    return result


def _class_cells(hotel, label):
    """Hotelaria rows of a star class (every star subtype) or the Pousadas."""
    if label == "Pousadas":
        return _segment(hotel, POUSADAS)
    stars = dict(STAR_CLASSES)[label]
    return hotel[hotel["subtipo_alojamento"].isin(STAR_SUBTYPES) & hotel["classificacao"].isin(stars)]


def _reading(gap, nights_per_room, region_nights_per_room):
    """Short reading of a municipality's gap and use of its rooms."""
    if abs(gap) < BALANCED_GAP:
        return "Equilibrado"
    above = (nights_per_room is not None and region_nights_per_room is not None
             and nights_per_room >= region_nights_per_room)
    if gap > 0:
        return "Procura a pressionar" if above else "Espaço para crescer"
    return "Oferta em expansão" if above else "Oferta em excesso"


# --- tabs ----------------------------------------------------------------------

def _procura(frames, acc, territory, segment, year):
    rows = _segment(acc, segment)
    national = portugal(frames, segment)
    nights = _change(rows, ["dormidas"], year, "dormidas", national)
    guests = _change(rows, ["hospedes"], year, "hospedes", national)
    stay_year = _latest_with(rows, ["dormidas", "hospedes"], year)
    stay_previous = _previous_with(rows, ["dormidas", "hospedes"], stay_year)
    stay = _pooled(_at(rows, stay_year), "dormidas", "hospedes")
    stay_before = _pooled(_at(rows, stay_previous), "dormidas", "hospedes")

    markets = _territory(frames["markets"], territory)
    market_year = m.latest_year(_years_with(markets, "dormidas"), year)
    wide = _at(markets, market_year).pivot_table(
        index="municipio", columns="local_residencia", values="dormidas", aggfunc="sum")
    international = None
    if {"Total", "Estrangeiro"} <= set(wide.columns):
        share = _pooled(wide, "Estrangeiro", "Total")
        international = None if share is None else share * 100

    monthly = _monthly(frames, territory, segment, year)
    published = [(i, v) for i, v in enumerate(monthly["dormidas"]) if v is not None]
    peak = None
    if published:
        month, value = max(published, key=lambda p: p[1])
        complete = len(published) == 12
        share = m.ratio(value, sum(v for _, v in published)) if complete else None
        peak = {"mes": month + 1, "valor": value, "quota": None if share is None else share * 100}

    types = []
    for name in TYPES:
        type_rows = _segment(acc, name)
        types.append({
            "tipo": name,
            "valor": _sum(type_rows, year, "dormidas"),
            "anterior": _sum(type_rows, year - 1, "dormidas"),
            "estada": _pooled(_at(type_rows, year), "dormidas", "hospedes"),
        })

    top = _at(rows, year).dropna(subset=["dormidas"]).nlargest(8, "dormidas")
    return {
        "kpis": {
            "dormidas": nights,
            "hospedes": guests,
            "estada": {"valor": stay, "ano": stay_year, "ano_anterior": stay_previous,
                       "delta": None if stay is None or stay_before is None else stay - stay_before,
                       "pt": _pt_ratio(national, stay_year, "dormidas", "hospedes")},
            "quota_internacional": {"valor": international, "ano": market_year},
            "pico": peak,
        },
        "mensal": monthly,
        "nuts3": _by_nuts3(rows, year, "dormidas"),
        "tipos": types,
        "top": [{"municipio": r.municipio, "valor": _num(r.dormidas)} for r in top.itertuples()],
    }


def _oferta(frames, acc, segment, year):
    rows = _segment(acc, segment)
    national = portugal(frames, segment)
    establishments_year = m.latest_year(_years_with(rows, "estabelecimentos"), year)
    rooms_year = m.latest_year(_years_with(rows, "quartos"), year)
    size_year = _latest_with(rows, ["quartos", "estabelecimentos"], year)

    area = frames["area"]
    area = area[area["municipio"].isin(set(acc["municipio"]))]
    rooms_area = _at(rows, rooms_year).merge(area[["municipio", "area"]], on="municipio")

    total_rooms = _segment(acc, "Total")
    ter_rooms = _segment(acc, TER)
    ter_year = _latest_with(total_rooms, ["quartos"], year)
    ter_share = m.ratio(_sum(ter_rooms, ter_year, "quartos"), _sum(total_rooms, ter_year, "quartos"))
    pt_total, pt_ter = portugal(frames, "Total"), portugal(frames, TER)
    pt_ter_share = m.ratio(_pt(pt_ter, ter_year, "quartos"), _pt(pt_total, ter_year, "quartos"))

    years = sorted(set(_years_with(acc, "quartos")))
    rooms_by_type = [{"tipo": name, "valores": [_by_year(_segment(acc, name), "quartos").get(y) for y in years]}
                     for name in TYPES]

    establishments_by_type = []
    est_total = _segment(acc, "Total")
    est_latest = m.latest_year(_years_with(est_total, "estabelecimentos"), year)
    est_base = _base_year(_years_with(est_total, "estabelecimentos"), est_latest)
    for name in TYPES:
        type_rows = _segment(acc, name)
        establishments_by_type.append({
            "tipo": name,
            "base": _sum(type_rows, est_base, "estabelecimentos"),
            "valor": _sum(type_rows, est_latest, "estabelecimentos"),
        })

    # Star classes: sums of the published municipal values only. Rooms by class
    # are almost all confidential in the Alentejo, establishments mostly not,
    # so both are returned with the share of the hotelaria total they cover.
    hotel_rows = acc[acc["tipo_alojamento"] == "Hotelaria"]
    hotel_years = {c: m.latest_year(_years_with(_segment(hotel_rows, "Hotelaria"), c), year)
                   for c in ("estabelecimentos", "quartos")}
    classification = {"anos": hotel_years, "classes": []}
    for label in [label for label, _ in STAR_CLASSES] + ["Pousadas"]:
        entry = {"classe": label}
        for column, column_year in hotel_years.items():
            cells = _class_cells(_at(hotel_rows, column_year), label)
            entry[column] = _total(cells, column)
            entry[column + "_publicados"] = int(cells[column].notna().sum())
        classification["classes"].append(entry)
    for column, column_year in hotel_years.items():
        hotel_total = _sum(_segment(hotel_rows, "Hotelaria"), column_year, column)
        covered = sum(c[column] or 0 for c in classification["classes"])
        classification["total_" + column] = hotel_total
        classification["cobertura_" + column] = m.ratio(covered, hotel_total)

    size_by_type = []
    for name in TYPES:
        type_rows = _segment(acc, name)
        type_year = _latest_with(type_rows, ["quartos", "estabelecimentos"], year)
        size_by_type.append({"tipo": name, "ano": type_year,
                             "valor": _pooled(_at(type_rows, type_year), "quartos", "estabelecimentos")})

    return {
        "kpis": {
            "estabelecimentos": _change(rows, ["estabelecimentos"], establishments_year, "estabelecimentos"),
            "quartos": _change(rows, ["quartos"], rooms_year, "quartos"),
            "quartos_estab": {"valor": _pooled(_at(rows, size_year), "quartos", "estabelecimentos"),
                              "ano": size_year,
                              "pt": _pt_ratio(national, size_year, "quartos", "estabelecimentos")},
            "quartos_km2": {"valor": _pooled(rooms_area, "quartos", "area"), "ano": rooms_year,
                            "pt": m.ratio(_pt(national, rooms_year, "quartos"),
                                          frames["info"].get("area_portugal"))},
            "peso_ter": {"valor": None if ter_share is None else ter_share * 100, "ano": ter_year,
                         "pt": None if pt_ter_share is None else pt_ter_share * 100},
        },
        "quartos_tipo": {"anos": years, "series": rooms_by_type},
        "nuts3": _by_nuts3(rows, rooms_year, "quartos"),
        "estab_tipo": {"base": est_base, "ano": est_latest, "tipos": establishments_by_type},
        "classificacao": classification,
        "dimensao": size_by_type,
    }


def _equilibrio(frames, acc, segment, year):
    rows = _segment(acc, segment)
    national = portugal(frames, segment)
    both = ["dormidas", "quartos"]
    end = _latest_with(rows, both, year)
    previous = _previous_with(rows, both, end)
    years = sorted(set(_years_with(rows, "dormidas")) & set(_years_with(rows, "quartos")))
    base = _base_year(years, end)

    nights_per_room = _pooled(_at(rows, end), "dormidas", "quartos")
    nights_growth = m.growth(_sum(rows, end, "dormidas"), _sum(rows, base, "dormidas"))
    rooms_growth = m.growth(_sum(rows, end, "quartos"), _sum(rows, base, "quartos"))
    guests_year = _latest_with(rows, ["hospedes", "estabelecimentos"], year)
    guests_previous = _previous_with(rows, ["hospedes", "estabelecimentos"], guests_year)
    guests_per_est = _pooled(_at(rows, guests_year), "hospedes", "estabelecimentos")

    start_rows, end_rows = _at(rows, base).set_index("municipio"), _at(rows, end).set_index("municipio")
    scatter = []
    for name in end_rows.index.intersection(start_rows.index):
        rooms0, nights0 = _num(start_rows.at[name, "quartos"]), _num(start_rows.at[name, "dormidas"])
        if rooms0 is None or rooms0 < MIN_ROOMS_FOR_GAP or not nights0:
            continue
        rooms1, nights1 = _num(end_rows.at[name, "quartos"]), _num(end_rows.at[name, "dormidas"])
        growth_rooms, growth_nights = m.growth(rooms1, rooms0), m.growth(nights1, nights0)
        if growth_rooms is None or growth_nights is None:
            continue
        gap = growth_nights - growth_rooms
        use = m.ratio(nights1, rooms1)
        scatter.append({"municipio": name, "cresc_quartos": growth_rooms, "cresc_dormidas": growth_nights,
                        "gap": gap, "noites_quarto": use,
                        "leitura": _reading(gap, use, nights_per_room)})
    scatter.sort(key=lambda r: -r["gap"])
    table = scatter if len(scatter) <= 2 * TABLE_ROWS else scatter[:TABLE_ROWS] + scatter[-TABLE_ROWS:]

    types = []
    for name in TYPES:
        type_rows = _segment(acc, name)
        type_end = _latest_with(type_rows, both, year)
        types.append({"tipo": name, "ano": type_end,
                      "valor": _pooled(_at(type_rows, type_end), "dormidas", "quartos"),
                      "base": _pooled(_at(type_rows, base), "dormidas", "quartos") if base else None})

    return {
        "ano": end,
        "base": base,
        "min_quartos": MIN_ROOMS_FOR_GAP,
        "kpis": {
            "noites_quarto": {
                "valor": nights_per_room, "ano": end, "ano_anterior": previous,
                "anterior": _pooled(_at(rows, previous), "dormidas", "quartos"),
                "pt": _pt_ratio(national, end, "dormidas", "quartos"),
            },
            "gap": {"valor": None if nights_growth is None or rooms_growth is None
                    else nights_growth - rooms_growth,
                    "dormidas": nights_growth, "quartos": rooms_growth},
            "hospedes_estab": {
                "valor": guests_per_est, "ano": guests_year, "ano_anterior": guests_previous,
                "var": m.growth(guests_per_est,
                                _pooled(_at(rows, guests_previous), "hospedes", "estabelecimentos")),
                "pt": _pt_ratio(national, guests_year, "hospedes", "estabelecimentos"),
            },
        },
        "indice": supply_demand_index(rows),
        "tipos": types,
        "dispersao": scatter,
        "tabela": table,
    }


def noites_quartos(frames, year, segment, territory):
    territory = _check_territory(territory)
    _check(segment, SEGMENTS, "seg")
    acc = _territory(frames["acc"], territory)
    years = _years_with(_segment(acc, "Total"), "dormidas")
    _check(year, years, "ano")
    return {
        "ano": year,
        "anos": years,
        "segmento": segment,
        "territorio": TERRITORIES[territory],
        "procura": _procura(frames, acc, territory, segment, year),
        "oferta": _oferta(frames, acc, segment, year),
        "equilibrio": _equilibrio(frames, acc, segment, year),
    }


ROUTE = "noites-quartos"


def route(frames, params):
    """Answer /api/noites-quartos from the parsed query string."""
    return noites_quartos(
        frames, param_year(params, "ano", latest(frames, "anos_anuais")),
        param_text(params, "seg", "Total"), param_text(params, "terr", "2024"))
