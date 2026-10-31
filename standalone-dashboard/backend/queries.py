"""Load the INE tables and build the payload of each dashboard.

The frames cover the Alentejo NUTS II region in the NUTS 2013 geography stored
by the flows (it includes Lezíria do Tejo). The NUTS 2024 territory is the same
set of municipalities without Lezíria do Tejo.

Data rules from docs/ine_dicionario_dados.sql:
- totals come from the INE total rows (tipo_alojamento = 'Total',
  local_residencia = 'Total'); detail rows never add up to them;
- ratios (estada média, RevPAR) are recomputed or weighted, never summed;
- NULL is a confidential value, not zero.
"""

import threading
import time

import pandas as pd
from sqlalchemy import text

from . import measures as m


ALENTEJO = "Alentejo"
LEZIRIA = "Lezíria do Tejo"
LITORAL = "Alentejo Litoral"
REFERENCE_YEAR = 2019
MONTHS = [f"{month:02d}" for month in range(1, 13)]
DAYS_PER_YEAR = 365
# Municipalities with fewer rooms at the start of a period give unstable growth rates.
MIN_ROOMS_FOR_GAP = 20

TERRITORIES = {
    "2024": "Alentejo NUTS 2024",
    "2013": "Alentejo NUTS 2013 (com Lezíria do Tejo)",
}

TER_LABEL = "Turismo no Espaço Rural e de Habitação"
SEGMENTS = {
    "Total": ("Total", "Total", "Total"),
    "Hotelaria": ("Hotelaria", "Total", "Total"),
    "Alojamento local": ("Alojamento local", "Alojamento Local", "Alojamento Local"),
    "TER e habitação": ("Turismo no espaço rural e de habitação", TER_LABEL, TER_LABEL),
}

REVPAR_CATEGORIES = [
    ("Todos os tipos", SEGMENTS["Total"]),
    ("Hotelaria", SEGMENTS["Hotelaria"]),
    ("Hotéis 5★", ("Hotelaria", "Hotéis", "5 estrelas")),
    ("Hotéis 4★", ("Hotelaria", "Hotéis", "4 estrelas")),
    ("Hotéis 3★", ("Hotelaria", "Hotéis", "3 estrelas")),
    ("Apartamentos turísticos", ("Hotelaria", "Apartamentos turísticos", "Total")),
    ("Alojamento local", SEGMENTS["Alojamento local"]),
    ("TER e habitação", SEGMENTS["TER e habitação"]),
]

RESIDENCE_AGGREGATES = {"Total", "Portugal", "Estrangeiro", "Outros"}

ACCOMMODATION_TABLES = {
    "estabelecimentos": ("ine_0009873_ds", "establecimento_de_alojamento_turistico"),
    "quartos": ("ine_0009874_ds", "quartos"),
    "hospedes": ("ine_0009876_ds", "hospedes"),
    "dormidas": ("ine_0009877_ds", "dormidas"),
    "revpar": ("ine_0009929_ds", "rendimento_medio_por_quarto"),
}
ACCOMMODATION_KEYS = [
    "municipio", "nuts_iii", "ano",
    "tipo_alojamento", "subtipo_alojamento", "classificacao",
]

MARKETS_SQL = """
SELECT municipio, nuts_iii, local_residencia, ano, h.hospedes, d.dormidas
FROM ine_0009930_ds h
FULL JOIN ine_0009183_ds d
    USING (nuts_i, nuts_ii, nuts_iii, distrito, municipio, local_residencia, ano)
WHERE nuts_ii = :nuts_ii AND municipio <> 'Total'
"""

# ine_0010735_ds also holds aggregate rows labelled municipio = 'Total' for some
# years only; they are excluded and the region is summed from municipalities.
# segmento_alojamento keeps the INE labels: 'Total', 'Hotelaria',
# 'Alojamento local', 'Turismo no espaço rural e de habitação'.
MONTHLY_SQL = """
SELECT municipio, nuts_iii, segmento_alojamento, ano, mes, d.dormidas, h.hospedes
FROM ine_0010735_ds d
FULL JOIN ine_0010736_ds h
    USING (nuts_i, nuts_ii, nuts_iii, distrito, municipio, segmento_alojamento, ano, mes)
WHERE nuts_ii = :nuts_ii AND municipio <> 'Total'
"""

# NUTS II regions (NUTS 2013) plus the Portugal row (nuts_i = 'Portugal',
# nuts_ii = 'Total'), every accommodation type.
REGIONS_SQL = """
SELECT nuts_i, nuts_ii, tipo_alojamento, subtipo_alojamento, ano, mes, d.dormidas, h.hospedes
FROM ine_0009808_ds d
LEFT JOIN ine_0009812_ds h
    USING (nuts_i, nuts_ii, tipo_alojamento, subtipo_alojamento, ano, mes)
"""

# Portugal = sum of every municipality's published value. Confidential
# municipal values are missing, so these are close lower bounds, except for the
# total rows, which the INE rarely suppresses.
NATIONAL_SQL = """
SELECT ano, tipo_alojamento, subtipo_alojamento, classificacao, SUM({column}) AS {name}
FROM {table}
WHERE municipio <> 'Total'
GROUP BY ano, tipo_alojamento, subtipo_alojamento, classificacao
"""

# Published municipal values for the national RevPAR (see national_revpar).
NATIONAL_REVPAR_SQL = """
SELECT nuts_ii, municipio, tipo_alojamento, subtipo_alojamento, classificacao, ano,
    {column} AS {name}
FROM {table}
WHERE municipio <> 'Total' AND {column} IS NOT NULL
"""

NATIONAL_MARKETS_SQL = """
SELECT local_residencia, ano, SUM(h.hospedes) AS hospedes, SUM(d.dormidas) AS dormidas
FROM ine_0009930_ds h
FULL JOIN ine_0009183_ds d
    USING (nuts_i, nuts_ii, nuts_iii, distrito, municipio, local_residencia, ano)
WHERE municipio <> 'Total'
GROUP BY local_residencia, ano
"""

NATIONAL_AREA_SQL = """
SELECT SUM(area) AS area FROM (
    SELECT DISTINCT ON (municipio, distrito) superficie_unidades_territoriais AS area
    FROM ine_0008350_ds
    WHERE superficie_unidades_territoriais IS NOT NULL
    ORDER BY municipio, distrito, ano DESC
) latest
"""

# Last load date of every table, for the page footers.
DASHBOARD_TABLES = (
    "0008350", "0009183", "0009808", "0009812", "0009873", "0009874", "0009876",
    "0009877", "0009929", "0009930", "0010735", "0010736",
)
UPDATED_SQL = " UNION ALL ".join(
    f"SELECT '{code}' AS tabela, MAX(update_date)::date AS atualizado FROM ine_{code}_ds"
    for code in DASHBOARD_TABLES
)

# Tourism territories: own groupings of municipalities, not INE geographies.
# The mockup does not list Serra de São Mamede; its members here are an assumption.
TOURISM_TERRITORIES = {
    "Alqueva": ["Reguengos de Monsaraz", "Mourão", "Moura", "Portel", "Alandroal"],
    "Costa Vicentina": ["Odemira"],
    "Comporta": ["Grândola", "Alcácer do Sal"],
    "Património UNESCO": ["Évora", "Elvas"],
    "Serra de São Mamede": ["Marvão", "Castelo de Vide", "Portalegre"],
}

# segmento_alojamento of the monthly municipal tables -> SEGMENTS key.
MONTHLY_SEGMENTS = {
    "Total": "Total",
    "Hotelaria": "Hotelaria",
    "Alojamento local": "Alojamento local",
    "Turismo no espaço rural e de habitação": "TER e habitação",
}

AREA_SQL = """
SELECT DISTINCT ON (municipio)
    municipio, ano, superficie_unidades_territoriais AS area
FROM ine_0008350_ds
WHERE nuts_ii = :nuts_ii AND superficie_unidades_territoriais IS NOT NULL
ORDER BY municipio, ano DESC
"""


class BadRequest(ValueError):
    """A dashboard parameter outside the values offered by the data."""


def _read(connection, sql, **params):
    return pd.read_sql(text(sql), connection, params=params)


def national_revpar(revpar, rooms):
    """Portugal's RevPAR per year and category, weighted by rooms.

    Each municipality's RevPAR is weighted by its rooms of the same category
    from the latest year, not after the RevPAR year, in which they were
    published: rooms years are loaded unevenly across regions.
    """
    keys = ["nuts_ii", "municipio", "tipo_alojamento", "subtipo_alojamento", "classificacao"]
    rooms = rooms.rename(columns={"ano": "ano_quartos"}).sort_values("ano_quartos")
    paired = pd.merge_asof(
        revpar.sort_values("ano"), rooms, left_on="ano", right_on="ano_quartos",
        by=keys, direction="backward").dropna(subset=["quartos"])
    paired["peso"] = paired["revpar"] * paired["quartos"]
    grouped = paired.groupby(["ano", "tipo_alojamento", "subtipo_alojamento", "classificacao"])
    result = grouped.agg(peso=("peso", "sum"), quartos=("quartos", "sum"),
                         municipios=("municipio", "count"), ano_quartos=("ano_quartos", "max"))
    result["revpar"] = result["peso"] / result["quartos"]
    return result.drop(columns=["peso", "quartos"]).reset_index()


def add_derived_frames(frames):
    """Add the 'Total' views: monthly (from monthly_seg) and regions (from regions_tipo)."""
    seg = frames["monthly_seg"]
    frames["monthly"] = seg.loc[
        seg["segmento_alojamento"] == "Total",
        ["municipio", "nuts_iii", "ano", "mes", "dormidas"]].reset_index(drop=True)
    tipo = frames["regions_tipo"]
    frames["regions"] = tipo.loc[
        (tipo["tipo_alojamento"] == "Total") & (tipo["subtipo_alojamento"] == "Total"),
        ["nuts_i", "nuts_ii", "ano", "mes", "dormidas", "hospedes"]].reset_index(drop=True)
    return frames


def load_frames(engine):
    """Read every table the dashboards use.

    Frames:
    - acc, markets, area: Alentejo municipalities (NUTS 2013), annual;
    - monthly_seg: Alentejo municipalities by month and segment (nights, guests);
      monthly: the same, segment 'Total', nights only;
    - regions_tipo: NUTS II regions and Portugal by month and accommodation type;
      regions: the same, type 'Total';
    - pt_acc, pt_revpar, pt_markets: Portugal, annual (sums of municipalities);
    - info: dict with the national area and the last update date.
    """
    params = {"nuts_ii": ALENTEJO}
    keys = ["ano", "tipo_alojamento", "subtipo_alojamento", "classificacao"]
    with engine.connect() as connection:
        accommodation = national = None
        for name, (table, column) in ACCOMMODATION_TABLES.items():
            frame = _read(
                connection,
                f"SELECT {', '.join(ACCOMMODATION_KEYS)}, {column} AS {name} "
                f"FROM {table} WHERE nuts_ii = :nuts_ii AND municipio <> 'Total'",
                **params,
            )
            accommodation = frame if accommodation is None else accommodation.merge(
                frame, on=ACCOMMODATION_KEYS, how="outer")
            if name == "revpar":
                continue
            frame = _read(connection, NATIONAL_SQL.format(table=table, column=column, name=name))
            national = frame if national is None else national.merge(frame, on=keys, how="outer")
        updated = _read(connection, UPDATED_SQL)
        frames = {
            "acc": accommodation,
            "markets": _read(connection, MARKETS_SQL, **params),
            "monthly_seg": _read(connection, MONTHLY_SQL, **params),
            "regions_tipo": _read(connection, REGIONS_SQL),
            "area": _read(connection, AREA_SQL, **params),
            "pt_acc": national,
            "pt_revpar": national_revpar(
                _read(connection, NATIONAL_REVPAR_SQL.format(
                    table="ine_0009929_ds", column="rendimento_medio_por_quarto", name="revpar")),
                _read(connection, NATIONAL_REVPAR_SQL.format(
                    table="ine_0009874_ds", column="quartos", name="quartos"))),
            "pt_markets": _read(connection, NATIONAL_MARKETS_SQL),
        }
        national_area = _read(connection, NATIONAL_AREA_SQL)["area"].iloc[0]
    for frame in frames.values():
        frame["ano"] = frame["ano"].astype(int)
    add_derived_frames(frames)
    last = updated["atualizado"].dropna()
    frames["info"] = {
        "area_portugal": _num(national_area),
        "atualizado": last.max().isoformat() if len(last) else None,
        "atualizado_por_tabela": {
            r.tabela: (r.atualizado.isoformat() if pd.notna(r.atualizado) else None)
            for r in updated.itertuples()
        },
    }
    return frames


class DashboardData:
    """Thread-safe cache of the frames, reloaded after ttl seconds."""

    def __init__(self, engine_factory, ttl=1800):
        self._engine_factory = engine_factory
        self._ttl = ttl
        self._lock = threading.Lock()
        self._frames = None
        self._loaded_at = 0.0

    def frames(self, refresh=False):
        with self._lock:
            stale = time.time() - self._loaded_at > self._ttl
            if self._frames is None or stale or refresh:
                self._frames = load_frames(self._engine_factory())
                self._loaded_at = time.time()
            return self._frames

    @property
    def loaded_at(self):
        return self._loaded_at


# --- frame helpers ----------------------------------------------------------

def _num(value):
    """Convert pandas/numpy scalars to float, with NaN/None as None."""
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if m.is_number(value) else None


def _territory(frame, territory):
    if territory == "2024":
        return frame[frame["nuts_iii"] != LEZIRIA]
    return frame


def _segment(frame, key):
    tipo, subtipo, classificacao = key if isinstance(key, tuple) else SEGMENTS[key]
    return frame[
        (frame["tipo_alojamento"] == tipo)
        & (frame["subtipo_alojamento"] == subtipo)
        & (frame["classificacao"] == classificacao)
    ]


def _years_with(frame, column):
    return sorted(int(y) for y in frame.loc[frame[column].notna(), "ano"].unique())


def _total(frame, column):
    return _num(frame[column].sum(min_count=1))


def _pooled(frame, numerator, denominator):
    """Ratio of sums over rows where both values were published."""
    both = frame[frame[numerator].notna() & frame[denominator].notna()]
    return m.ratio(_total(both, numerator), _total(both, denominator))


def _by_year(frame, column):
    sums = frame.groupby("ano")[column].sum(min_count=1)
    return {int(year): _num(value) for year, value in sums.items()}


def _monthly_values(frame, year, column="dormidas"):
    """Twelve values for year, ordered jan..dec, None where missing."""
    rows = frame[frame["ano"] == year].groupby("mes")[column].sum(min_count=1)
    return [_num(rows.get(month)) for month in MONTHS]


def _complete_years(frame, column="dormidas"):
    years = []
    for year in sorted(frame["ano"].unique()):
        if all(v is not None for v in _monthly_values(frame, int(year), column)):
            years.append(int(year))
    return years


def _alentejo_monthly(frames, territory):
    """Monthly Alentejo nights and whether the series is a municipal sum.

    NUTS 2013 uses the regional table 0009808 (exact, since 2017). NUTS 2024
    has no regional table for nights, so the municipal months of 0010735
    (since 2020) are summed; confidential municipal months are left out.
    """
    if territory == "2013":
        regions = frames["regions"]
        return regions[regions["nuts_ii"] == ALENTEJO][["ano", "mes", "dormidas"]], False
    monthly = _territory(frames["monthly"], territory)
    return monthly.groupby(["ano", "mes"], as_index=False)["dormidas"].sum(min_count=1), True


def _revpar_estimate(accommodation, key, year, exact=False):
    """Room-weighted mean of the municipal RevPAR published for a category.

    INE publishes RevPAR per municipality only; the regional value is an
    estimate weighted by the rooms of the same category. Without exact, the
    latest published year up to year is used.
    """
    rows = _segment(accommodation, key)
    published = _years_with(rows, "revpar")
    revpar_year = (year if year in published else None) if exact else m.latest_year(published, year)
    if revpar_year is None:
        return None
    rooms_year = m.latest_year(_years_with(rows, "quartos"), revpar_year)
    revpar = rows[(rows["ano"] == revpar_year) & rows["revpar"].notna()]
    rooms = rows[rows["ano"] == rooms_year].set_index("municipio")["quartos"] if rooms_year else pd.Series(dtype=float)
    pairs = [(_num(r), _num(rooms.get(name))) for name, r in zip(revpar["municipio"], revpar["revpar"])]
    value = m.weighted_mean(pairs)
    if value is None:
        return None
    return {
        "valor": value,
        "ano": revpar_year,
        "ano_quartos": rooms_year,
        "municipios": sum(1 for v, w in pairs if v is not None and w),
    }


def _index(series, base_year):
    base = series.get(base_year)
    return {year: (m.ratio(value, base) * 100 if m.ratio(value, base) is not None else None)
            for year, value in series.items()}


def _check(value, allowed, name):
    if value not in allowed:
        raise BadRequest(f"Valor inválido para {name}: {value!r}")
    return value


def _check_territory(territory):
    return _check(territory, TERRITORIES, "terr")


# --- dashboards -------------------------------------------------------------

def meta(frames):
    total = _segment(frames["acc"], "Total")
    municipalities = (
        total[["municipio", "nuts_iii"]].drop_duplicates()
        .sort_values(["nuts_iii", "municipio"]).to_dict("records")
    )
    return {
        "anos_anuais": _years_with(total, "dormidas"),
        "anos_mercados": _years_with(frames["markets"], "hospedes"),
        "anos_oferta_procura": sorted(
            set(_years_with(total, "dormidas")) & set(_years_with(total, "quartos"))),
        "anos_mensais": _years_with(frames["monthly"], "dormidas"),
        "ultimo_mes": latest_month(frames["monthly"]),
        "municipios": municipalities,
        "segmentos": list(SEGMENTS),
        "territorios": TERRITORIES,
        "territorios_turisticos": TOURISM_TERRITORIES,
        "atualizado": frames["info"]["atualizado"],
    }


def latest_month(monthly):
    """(ano, mes) of the latest month with any published nights, as {"ano", "mes"}."""
    rows = monthly[monthly["dormidas"].notna()]
    if rows.empty:
        return None
    last = rows.sort_values(["ano", "mes"]).iloc[-1]
    return {"ano": int(last["ano"]), "mes": int(last["mes"])}


def portugal(frames, segment="Total"):
    """Portugal's annual sums for an accommodation segment, indexed by year.

    Columns: estabelecimentos, quartos, hospedes, dormidas, revpar (room-weighted).
    """
    key = segment if isinstance(segment, tuple) else SEGMENTS[segment]
    national = _segment(frames["pt_acc"], key).set_index("ano")
    revpar = _segment(frames["pt_revpar"], key).set_index("ano")["revpar"]
    return national.drop(columns=["tipo_alojamento", "subtipo_alojamento", "classificacao"]).assign(
        revpar=revpar)


# --- request parameters ------------------------------------------------------

def param_year(params, name, default):
    """Integer year from a parsed query string, or default when absent."""
    value = params.get(name, [str(default)])[0]
    try:
        return int(value)
    except ValueError as exc:
        raise BadRequest(f"Valor inválido para {name}: {value!r}") from exc


def param_text(params, name, default):
    return params.get(name, [default])[0]


def latest(frames, key):
    """Most recent year of a meta() year list."""
    return meta(frames)[key][-1]


def reference_or_first(frames, key):
    """2019 when it can start a period of the meta() list, else its first year."""
    years = meta(frames)[key]
    return REFERENCE_YEAR if REFERENCE_YEAR in years[:-1] else years[0]
