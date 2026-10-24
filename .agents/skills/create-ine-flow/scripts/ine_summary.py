"""Compact, token-bounded summaries of INE metadata and data responses.

Usage (stdlib only; run with the project's Python):
  python ine_summary.py meta --code 9873 [--year 2024 [--month 3]]
  python ine_summary.py meta --file meta.json [--year 2024 [--month 3]]
  python ine_summary.py data --file data.json --year 2024
  python ine_summary.py data --code 9873 --dim1 S7A2024 --year 2024
  python ine_summary.py data --file monthly.json --year 2024 --month 3 --period-key <key>

Prints only what is needed to design a flow: never the full catalogue or
every record. Network requests use explicit timeouts and fail loudly.
"""

import argparse
from collections import Counter
import json
import sys
import urllib.parse
import urllib.request

BASE = "https://www.ine.pt/ine/json_indicador/"
MONTHS_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
             "agosto", "setembro", "outubro", "novembro", "dezembro"]
SAMPLE = 5


def indicator_code(value):
    if not value.isascii() or not value.isdigit() or len(value) > 7:
        raise argparse.ArgumentTypeError("Indicator must contain 1 to 7 ASCII digits.")
    return value.zfill(7)


def load(args, kind):
    if args.file:
        with open(args.file, encoding="utf-8") as handle:
            return json.load(handle)
    code = args.code
    if kind == "meta":
        url = f"{BASE}pindicaMeta.jsp?varcd={code}&lang=PT"
    else:
        if not args.dim1:
            sys.exit("data --code requires --dim1 <verified period code>")
        url = (f"{BASE}pindica.jsp?op=2&varcd={code}&lang=PT&"
               + urllib.parse.urlencode({"Dim1": args.dim1}))
    with urllib.request.urlopen(url, timeout=args.timeout) as response:
        if response.status != 200:
            sys.exit(f"HTTP {response.status} for {url}")
        return json.load(response)


def first(payload):
    if isinstance(payload, list):
        if len(payload) != 1:
            raise ValueError("Expected exactly one indicator object.")
        payload = payload[0]
    if not isinstance(payload, dict):
        raise ValueError("Expected an indicator object.")
    return payload


def period_matches(code, label, year, month):
    text = f"{code} {label}".lower()
    if month is None:
        return str(year) in text
    return (f"{year}{month:02d}" in code
            or (str(year) in text and MONTHS_PT[month - 1] in text))


def summarize_meta(meta, year, month):
    info = first(meta)
    aliases = {
        "IndicadorNome": "IndicadorDsg",
        "DataUltimaAtualizacao": "DataUltimoAtualizacao",
    }
    for key in ("IndicadorCod", "IndicadorNome", "Periodic", "PrimeiroPeriodo",
                "UltimoPeriodo", "UnidadeMedida", "DataUltimaAtualizacao"):
        value = info.get(key)
        if value is None and key in aliases:
            value = info.get(aliases[key])
        print(f"{key}: {value}")
    dims = info["Dimensoes"]
    names = {str(d["dim_num"]): d.get("abrv") for d in dims.get("Descricao_Dim", [])}
    cats = {}
    for group in dims["Categoria_Dim"]:
        for items in group.values():
            for item in items:
                cats.setdefault(str(item["dim_num"]), []).append(
                    (str(item["categ_cod"]), str(item["categ_dsg"]).strip()))
    for num in sorted(cats, key=int):
        items = cats[num]
        print(f"\nDim{num}: {names.get(num)} - {len(items)} categories")
        shown = items if len(items) <= SAMPLE else items[:3] + items[-2:]
        for code, label in shown:
            print(f"  {code} = {label}")
        lengths = [len(label) for _, label in items]
        print(f"  label length max {max(lengths)}; code lengths "
              f"{sorted(Counter(len(c) for c, _ in items).items())}")
    if year is not None:
        period = cats.get("1", [])
        hits = [(c, l) for c, l in period if period_matches(c, l, year, month)]
        wanted = f"{year}" + (f"-{month:02d}" if month else "")
        print(f"\nDim1 categories matching {wanted}: {hits or 'NONE'}")


def summarize_data(payload, year, month, period_key=None):
    data = first(payload)
    print("top-level keys:", sorted(data))
    if "Sucesso" in data:
        print("Sucesso:", json.dumps(data["Sucesso"], ensure_ascii=False)[:200])
    elements = data.get("Dados")
    if isinstance(elements, dict):
        print("period keys:", list(elements))
        expected_key = period_key if period_key is not None else str(year)
        if set(elements) != {expected_key}:
            raise ValueError(f"Expected only response period {expected_key!r}.")
        records = elements[expected_key]
    elif isinstance(elements, list):
        records = elements
    else:
        sys.exit(f"Unexpected Dados shape: {type(elements).__name__}")
    if not isinstance(records, list) or any(
        not isinstance(record, dict) for record in records
    ):
        raise ValueError("The requested period must contain a list of objects.")
    for record in records:
        if isinstance(elements, list):
            required = ("anocod", "mescod") if month is not None else ("anocod",)
            if any(field not in record for field in required):
                raise ValueError("List-form records must identify their period.")
        for field, expected in (("anocod", year), ("mescod", month)):
            if expected is not None and field in record:
                value = record[field]
                if isinstance(value, bool) or str(value) not in (
                    str(expected), f"{expected:02d}",
                ):
                    raise ValueError(f"Record {field} does not match {expected}.")
    print("records:", len(records))
    if not records:
        return
    fields = sorted({k for r in records for k in r})
    print("fields:", fields)
    for record in records[:3]:
        print("  sample:", json.dumps(record, ensure_ascii=False))
    for field in fields:
        if field == "geocod" or field.startswith("dim_") and not field.endswith("_t"):
            values = Counter(str(r.get(field)) for r in records)
            print(f"{field}: {len(values)} distinct, e.g. {list(values)[:SAMPLE]}")
    markers = Counter()
    for r in records:
        raw = str(r.get("valor", "")).strip()
        try:
            float(raw.replace(",", "."))
        except ValueError:
            markers[raw or "<empty>"] += 1
    zeros = sum(str(r.get("valor", "")).strip() in ("0", "0,0", "0.0") for r in records)
    print("non-numeric valor:", dict(markers) or "none", "| zeros:", zeros)
    key_fields = [f for f in fields if f == "geocod"
                  or f.startswith("dim_") and not f.endswith("_t")]
    keys = Counter(tuple(r.get(f) for f in key_fields) for r in records)
    print(f"duplicate {key_fields} keys:", sum(n - 1 for n in keys.values() if n > 1))
    print("period validation: passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["meta", "data"])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file")
    source.add_argument("--code", type=indicator_code)
    parser.add_argument("--dim1", help="Verified period category code (data only).")
    parser.add_argument("--year", type=int)
    parser.add_argument("--month", type=int, choices=range(1, 13))
    parser.add_argument("--period-key", help="Exact verified response period key.")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive.")
    if args.year is not None and not 1 <= args.year <= 9999:
        parser.error("--year must be between 1 and 9999.")
    if args.month is not None and args.year is None:
        parser.error("--month requires --year.")
    if args.kind == "data":
        if args.year is None:
            parser.error("Data inspection requires --year.")
        if args.month is not None and args.period_key is None:
            parser.error("Monthly data inspection requires --period-key.")
    payload = load(args, args.kind)
    if args.kind == "meta":
        summarize_meta(payload, args.year, args.month)
    else:
        summarize_data(payload, args.year, args.month, args.period_key)


if __name__ == "__main__":
    main()
