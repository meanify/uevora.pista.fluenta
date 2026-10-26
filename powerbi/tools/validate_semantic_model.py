"""Structural checks on the generated TMDL: references, balance, duplicates."""
import glob, os, re, sys

DEF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "PistaDigital.SemanticModel", "definition")
errs, warns = [], []

tables = {}      # table -> set(columns)
measures = {}    # measure -> table
mexpr = []       # (table, measure, expression text)
partitions = []  # (table, kind, source text)

name_re = re.compile(r"^(?:table|column|measure|partition)\s+(?:'([^']+)'|(\S+))")


def obj_name(line):
    m = name_re.match(line.strip())
    return (m.group(1) or m.group(2)) if m else None


for path in sorted(glob.glob(f"{DEF}/tables/*.tmdl")):
    lines = open(path, encoding="utf-8").read().split("\n")
    tname = None
    cur_measure = None
    cur_partition = None
    buf = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("table "):
            tname = obj_name(s)
            if tname in tables:
                errs.append(f"duplicate table {tname!r}")
            tables[tname] = set()
            if os.path.basename(path) != f"{tname}.tmdl":
                warns.append(f"{os.path.basename(path)} does not match table {tname!r}")
        elif s.startswith("column "):
            c = obj_name(s)
            if c in tables[tname]:
                errs.append(f"duplicate column {tname!r}[{c}]")
            tables[tname].add(c)
            cur_measure = cur_partition = None
        elif s.startswith("measure "):
            if cur_measure:
                mexpr.append((tname, cur_measure, "\n".join(buf)))
            cur_measure = obj_name(s)
            if cur_measure in measures:
                errs.append(f"duplicate measure {cur_measure!r}")
            measures[cur_measure] = tname
            buf = [s.split("=", 1)[1] if "=" in s else ""]
            cur_partition = None
        elif s.startswith("partition "):
            if cur_measure:
                mexpr.append((tname, cur_measure, "\n".join(buf)))
                cur_measure = None
            cur_partition = (tname, "m" if s.rstrip().endswith("= m") else "calculated")
            buf = []
        elif cur_measure is not None:
            if re.match(r"^(formatString|lineageTag|displayFolder|isHidden|///|annotation|changedProperty)", s):
                mexpr.append((tname, cur_measure, "\n".join(buf)))
                cur_measure = None
                buf = []
            else:
                buf.append(s)
        elif cur_partition is not None:
            if s in ("mode: import", "source =") or s.startswith("mode:"):
                continue
            buf.append(s)
    if cur_measure:
        mexpr.append((tname, cur_measure, "\n".join(buf)))
    if cur_partition:
        partitions.append((cur_partition[0], cur_partition[1], "\n".join(buf)))

# ---- balance check
def balance(txt, label):
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    in_str = False
    i = 0
    while i < len(txt):
        ch = txt[i]
        if ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch in "([{":
                stack.append(ch)
            elif ch in pairs:
                if not stack or stack[-1] != pairs[ch]:
                    errs.append(f"unbalanced {ch!r} in {label}")
                    return
                stack.pop()
        i += 1
    if stack:
        errs.append(f"unclosed {''.join(stack)} in {label}")
    if in_str:
        errs.append(f"unterminated string in {label}")


for t, kind, src in partitions:
    balance(src, f"partition {t!r} ({kind})")
for t, mn, ex in mexpr:
    balance(ex, f"measure {mn!r} on {t!r}")

# ---- DAX reference check: 'Table'[Column] and bare [Name]
ref_re = re.compile(r"'([^']+)'\[([^\]]+)\]")
bare_re = re.compile(r"(?<!')\[([^\]]+)\]")

def check_refs(txt, label, home=None):
    for tbl, col in ref_re.findall(txt):
        if tbl not in tables:
            errs.append(f"{label}: unknown table '{tbl}'")
        elif col not in tables[tbl] and col not in measures:
            errs.append(f"{label}: unknown column '{tbl}'[{col}]")
    cleaned = ref_re.sub("", txt)
    for nm in bare_re.findall(cleaned):
        if nm in measures or (home and nm in tables.get(home, ())):
            continue
        # column names introduced by SELECTCOLUMNS/ADDCOLUMNS/CALENDAR inside the same expression
        if f'"{nm}"' in txt or nm in ("Date",):
            continue
        errs.append(f"{label}: unresolved reference [{nm}]")


for t, mn, ex in mexpr:
    check_refs(ex, f"measure {mn!r}", home=t)
for t, kind, src in partitions:
    if kind == "calculated":
        check_refs(src, f"calculated table {t!r}", home=t)

# ---- relationships
rel_txt = open(f"{DEF}/relationships.tmdl", encoding="utf-8").read()
rels = re.findall(r"relationship\s+(\S+)(.*?)(?=\nrelationship |\Z)", rel_txt, re.S)
seen = set()
for rid, body in rels:
    if rid in seen:
        errs.append(f"duplicate relationship id {rid}")
    seen.add(rid)
    ends = re.findall(r"(fromColumn|toColumn):\s*'([^']+)'\.'([^']+)'", body)
    if len(ends) != 2:
        errs.append(f"relationship {rid}: expected fromColumn and toColumn, got {len(ends)}")
        continue
    for side, tbl, col in ends:
        if tbl not in tables:
            errs.append(f"relationship {rid}: unknown table '{tbl}'")
        elif col not in tables[tbl]:
            errs.append(f"relationship {rid}: unknown column '{tbl}'[{col}]")

# ---- model refs
model = open(f"{DEF}/model.tmdl", encoding="utf-8").read()
refs = set(re.findall(r"^ref table '([^']+)'", model, re.M))
for t in tables:
    if t not in refs:
        errs.append(f"table {t!r} is not referenced in model.tmdl")
for r in refs - set(tables):
    errs.append(f"model.tmdl references missing table {r!r}")

# ---- expressions referenced by M partitions
expr_txt = open(f"{DEF}/expressions.tmdl", encoding="utf-8").read()
exprs = set(re.findall(r"^expression (\w+)", expr_txt, re.M))
for t, kind, src in partitions:
    if kind == "m":
        for tok in re.findall(r"\b(Fonte|Servidor|BaseDados)\b", src):
            if tok not in exprs:
                errs.append(f"partition {t!r} uses undefined expression {tok}")

print(f"tables={len(tables)} measures={len(measures)} relationships={len(rels)} "
      f"partitions={len(partitions)}")
for w in warns:
    print("WARN:", w)
for e in errs:
    print("ERROR:", e)
sys.exit(1 if errs else 0)
