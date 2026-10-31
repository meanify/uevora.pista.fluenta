"""Pure dashboard measures, independent of the database."""

import math


def is_number(value):
    """Return True for finite numbers; NULL/NaN values are INE confidential."""
    return isinstance(value, (int, float)) and not math.isnan(value)


def ratio(numerator, denominator):
    """Divide published values, returning None when either side is missing."""
    if not is_number(numerator) or not is_number(denominator) or not denominator:
        return None
    return numerator / denominator


def growth(current, previous):
    """Percentage change from previous to current."""
    value = ratio(current, previous)
    return None if value is None else (value - 1) * 100


def gini(values):
    """Gini coefficient of non-negative values (0 = evenly distributed)."""
    if len(values) < 2 or not all(is_number(v) for v in values):
        return None
    total = sum(values)
    if total <= 0:
        return None
    n = len(values)
    differences = sum(abs(a - b) for a in values for b in values)
    return differences / (2 * n * total)


def seasonality(monthly):
    """Seasonality indicators for twelve monthly values ordered jan..dec."""
    if len(monthly) != 12 or not all(is_number(v) for v in monthly):
        return None
    total = sum(monthly)
    return {
        "pico_vale": ratio(max(monthly), min(monthly)),
        "quota_jun_set": ratio(sum(monthly[5:9]), total) * 100 if total else None,
        "gini": gini(monthly),
    }


def hhi(values):
    """Herfindahl-Hirschman index of shares in percentage points (0..10000)."""
    values = [v for v in values if is_number(v)]
    total = sum(values)
    if total <= 0:
        return None
    return sum((v / total * 100) ** 2 for v in values)


def weighted_mean(pairs):
    """Mean of (value, weight) pairs, skipping pairs with missing parts."""
    usable = [(v, w) for v, w in pairs if is_number(v) and is_number(w) and w > 0]
    weight = sum(w for _, w in usable)
    if not weight:
        return None
    return sum(v * w for v, w in usable) / weight


def latest_year(years, year):
    """Most recent year in years that is not after year."""
    eligible = [y for y in years if y <= year]
    return max(eligible) if eligible else None


QUADRANT_ACTIONS = {
    "Estrelas": "Reforçar promoção",
    "De passagem": "Alongar a estada com rotas e pacotes",
    "Fiéis": "Fidelizar e manter presença",
    "A rever": "Rever investimento",
}


def quadrant(growth_value, stay, growth_reference, stay_reference):
    """Classify a market against the reference growth and average stay."""
    if not all(is_number(v) for v in (growth_value, stay, growth_reference, stay_reference)):
        return None
    if growth_value >= growth_reference:
        return "Estrelas" if stay >= stay_reference else "De passagem"
    return "Fiéis" if stay >= stay_reference else "A rever"
