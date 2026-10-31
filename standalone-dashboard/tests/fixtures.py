"""Small synthetic frames with the same shape as queries.load_frames().

Alentejo: Évora and Mora (Alentejo Central) and Santarém (Lezíria do Tejo,
outside the NUTS 2024 Alentejo). Years 2023 and 2024. Portugal adds a
municipality outside the Alentejo, so national values are larger.
"""

import pandas as pd

from backend import queries


MONTHS = [f"{m:02d}" for m in range(1, 13)]
AL = queries.SEGMENTS["Alojamento local"]
TOTAL = queries.SEGMENTS["Total"]
HOTELARIA = queries.SEGMENTS["Hotelaria"]


def accommodation_rows():
    rows = []
    # (municipio, nuts_iii, ano, segment, quartos, hospedes, dormidas, revpar)
    data = [
        ("Évora", "Alentejo Central", 2023, TOTAL, 1000, 500, 1000, 50.0),
        ("Évora", "Alentejo Central", 2024, TOTAL, 1100, 600, 1300, None),
        ("Évora", "Alentejo Central", 2023, AL, 200, None, 150, 30.0),
        ("Évora", "Alentejo Central", 2024, AL, 250, None, 200, None),
        ("Mora", "Alentejo Central", 2023, TOTAL, 100, 50, 100, 20.0),
        ("Mora", "Alentejo Central", 2024, TOTAL, 100, 50, 120, None),
        ("Mora", "Alentejo Central", 2023, AL, 50, None, None, None),
        ("Mora", "Alentejo Central", 2024, AL, 50, None, None, None),
        ("Santarém", queries.LEZIRIA, 2023, TOTAL, 400, 300, 600, 40.0),
        ("Santarém", queries.LEZIRIA, 2024, TOTAL, 400, 300, 700, None),
    ]
    for municipio, nuts3, ano, seg, rooms, guests, nights, revpar in data:
        rows.append({
            "municipio": municipio, "nuts_iii": nuts3, "ano": ano,
            "tipo_alojamento": seg[0], "subtipo_alojamento": seg[1], "classificacao": seg[2],
            "estabelecimentos": 10, "quartos": rooms, "hospedes": guests,
            "dormidas": nights, "revpar": revpar,
        })
    return pd.DataFrame(rows, dtype=object).astype({
        "ano": int, "estabelecimentos": float, "quartos": float,
        "hospedes": float, "dormidas": float, "revpar": float})


def national_rows(acc):
    """Portugal = the three Alentejo municipalities plus 10x Évora elsewhere."""
    keys = ["ano", "tipo_alojamento", "subtipo_alojamento", "classificacao"]
    columns = ["estabelecimentos", "quartos", "hospedes", "dormidas"]
    elsewhere = acc[acc["municipio"] == "Évora"].copy()
    elsewhere[columns] = elsewhere[columns] * 10
    both = pd.concat([acc, elsewhere])
    national = both.groupby(keys, as_index=False)[columns].sum(min_count=1)
    revpar = both.dropna(subset=["revpar"]).assign(peso=lambda f: f["revpar"] * f["quartos"])
    revpar = revpar.groupby(keys, as_index=False).agg(
        peso=("peso", "sum"), quartos=("quartos", "sum"), municipios=("municipio", "count"))
    revpar["revpar"] = revpar["peso"] / revpar["quartos"]
    revpar["ano_quartos"] = revpar["ano"]
    return national, revpar.drop(columns=["peso", "quartos"])


def frames():
    acc = accommodation_rows()
    monthly_seg = pd.DataFrame([
        {"municipio": name, "nuts_iii": nuts3, "segmento_alojamento": seg, "ano": ano, "mes": mes,
         "dormidas": float(i + 1) * scale, "hospedes": float(i + 1) * scale / 2}
        for name, nuts3 in (("Évora", "Alentejo Central"), ("Santarém", queries.LEZIRIA))
        for seg, scale in (("Total", 1.0), ("Hotelaria", 0.6), ("Alojamento local", 0.4))
        for ano in (2023, 2024) for i, mes in enumerate(MONTHS)
    ])
    regions_tipo = pd.DataFrame([
        {"nuts_i": nuts1, "nuts_ii": region, "tipo_alojamento": tipo, "subtipo_alojamento": "Total",
         "ano": ano, "mes": mes, "dormidas": 10.0 * scale * share, "hospedes": 5.0 * scale * share}
        for nuts1, region, scale in (("Continente", "Alentejo", 1), ("Continente", "Norte", 3),
                                     ("Portugal", "Total", 4))
        for tipo, share in (("Total", 1.0), ("Hotelaria", 0.7))
        for ano in (2023, 2024) for mes in MONTHS
    ])
    markets = pd.DataFrame([
        {"municipio": name, "nuts_iii": nuts3, "local_residencia": res, "ano": ano,
         "hospedes": guests, "dormidas": guests * 2}
        for name, nuts3 in (("Évora", "Alentejo Central"), ("Santarém", queries.LEZIRIA))
        for ano in (2023, 2024)
        for res, guests in (("Total", 100.0), ("Portugal", 60.0), ("Estrangeiro", 40.0),
                            ("Espanha", 30.0), ("França", 10.0))
    ])
    pt_markets = pd.DataFrame([
        {"local_residencia": res, "ano": ano, "hospedes": guests, "dormidas": guests * 2}
        for ano in (2023, 2024)
        for res, guests in (("Total", 1000.0), ("Portugal", 300.0), ("Estrangeiro", 700.0),
                            ("Espanha", 100.0), ("França", 200.0))
    ])
    area = pd.DataFrame({"municipio": ["Évora", "Mora", "Santarém"], "ano": [2022] * 3,
                         "area": [10.0, 5.0, 20.0]})
    pt_acc, pt_revpar = national_rows(acc)
    result = {
        "acc": acc, "markets": markets, "monthly_seg": monthly_seg, "regions_tipo": regions_tipo,
        "area": area, "pt_acc": pt_acc, "pt_revpar": pt_revpar, "pt_markets": pt_markets,
        "info": {"area_portugal": 135.0, "atualizado": "2026-10-31", "atualizado_por_tabela": {}},
    }
    return queries.add_derived_frames(result)
