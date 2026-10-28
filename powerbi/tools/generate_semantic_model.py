"""Regenerate the PistaDigital semantic model (TMDL) from the INE indicator definitions.

The INDICATORS table below mirrors flows-code/pistadigital/flows/ine_*_flow.py.
When an indicator is added or its schema changes, update INDICATORS and run:

    python3 powerbi/tools/generate_semantic_model.py
    python3 powerbi/tools/validate_semantic_model.py
"""
import os, re, shutil, uuid

# TMDL writes an identifier bare when it is a plain name, and quotes it otherwise.
# Power BI Desktop re-saves the model this way, so matching it keeps a regenerate
# a no-op against the committed .tmdl files.
_BARE = re.compile(r"[^\W\d][\w-]*", re.UNICODE)


def q(name):
    """Identifier as TMDL writes it: bare when it can be, quoted when it cannot."""
    return name if _BARE.fullmatch(name) else f"'{name}'"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "PistaDigital.SemanticModel")
DEF = os.path.join(MODEL, "definition")

_n = [0]
def tag(key=None):
    """Stable lineageTag. Positional by default; pass `key` to pin one by name.

    The positional counter means inserting an entity shifts every tag after it,
    which rewrites the lineageTags of unrelated entities. Anything added after the
    model was first generated should pass an explicit key so the sequence — and
    therefore the relationships at the end of it — stays put.
    """
    if key is None:
        _n[0] += 1
        key = _n[0]
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"pistadigital-{key}"))

def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

# geo profiles
MUN = ["nuts_i", "nuts_ii", "nuts_iii", "distrito", "municipio"]
REG = ["nuts_i", "nuts_ii"]

# indicator, monthly, value column, geo, extra dims, display name, measure, format, agg
IND = [
    ("0008350", False, "superficie_unidades_territoriais", MUN, [],
     "Superfície das unidades territoriais", "Superfície (km²)", "#,0.00", "SUM"),
    ("0009183", False, "dormidas", MUN, ["local_residencia"],
     "Dormidas por país de residência", "Dormidas (residência)", "#,0", "SUM"),
    ("0009808", True, "dormidas", REG, ["tipo_alojamento", "subtipo_alojamento"],
     "Dormidas mensais por tipo de alojamento (NUTS 2013)", "Dormidas mensais (tipo)", "#,0", "SUM"),
    ("0009812", True, "hospedes", REG, ["tipo_alojamento", "subtipo_alojamento"],
     "Hóspedes mensais por tipo de alojamento (NUTS 2013)", "Hóspedes mensais (tipo)", "#,0", "SUM"),
    ("0009873", False, "establecimento_de_alojamento_turistico", MUN,
     ["tipo_alojamento", "subtipo_alojamento", "classificacao"],
     "Estabelecimentos de alojamento turístico", "Estabelecimentos", "#,0", "SUM"),
    ("0009874", False, "quartos", MUN, ["tipo_alojamento", "subtipo_alojamento", "classificacao"],
     "Quartos em alojamento turístico", "Quartos (tipo)", "#,0", "SUM"),
    ("0009876", False, "hospedes", MUN, ["tipo_alojamento", "subtipo_alojamento", "classificacao"],
     "Hóspedes por tipo de alojamento", "Hóspedes (tipo)", "#,0", "SUM"),
    ("0009877", False, "dormidas", MUN, ["tipo_alojamento", "subtipo_alojamento", "classificacao"],
     "Dormidas por tipo de alojamento", "Dormidas (tipo)", "#,0", "SUM"),
    ("0009880", False, "estada_media", MUN, ["tipo_alojamento", "subtipo_alojamento", "classificacao"],
     "Estada média por tipo de alojamento", "Estada média INE (tipo)", "#,0.00", "AVERAGE"),
    ("0009929", False, "rendimento_medio_por_quarto", MUN,
     ["tipo_alojamento", "subtipo_alojamento", "classificacao"],
     "Rendimento médio por quarto", "RevPAR médio INE", '#,0.00 "€"', "AVERAGE"),
    ("0009930", False, "hospedes", MUN, ["local_residencia"],
     "Hóspedes por país de residência", "Hóspedes (residência)", "#,0", "SUM"),
    ("0010735", True, "dormidas", MUN, ["segmento_alojamento"],
     "Dormidas mensais por segmento", "Dormidas mensais (segmento)", "#,0", "SUM"),
    ("0010736", True, "hospedes", MUN, ["segmento_alojamento"],
     "Hóspedes mensais por segmento", "Hóspedes mensais (segmento)", "#,0", "SUM"),
    ("0011140", False, "estada_media", MUN, ["local_residencia"],
     "Estada média por país de residência", "Estada média INE (residência)", "#,0.00", "AVERAGE"),
    ("0012093", True, "hospedes", REG, ["tipo_alojamento", "subtipo_alojamento"],
     "Hóspedes mensais por tipo de alojamento (NUTS 2024)", "Hóspedes mensais (tipo, NUTS 2024)", "#,0", "SUM"),
]

def tname(i):
    return f"{i[5]} ({i[0]})"

# ------------------------------------------------------------------ fact tables
def leaf_steps(extra):
    """Power Query steps that keep only the most detailed row of each branch.

    The flows store every level of INE's breakdowns, with "Total" for the levels
    a row does not reach, and the base measures SUM. A parent row is dropped only
    when this table actually has children under it, so a branch INE does not break
    down further (Alojamento local, Pousadas) keeps its own row. Ends in `Folhas`.
    """
    steps, conds = [], []
    if "tipo_alojamento" in extra:
        sel = ['"tipo_alojamento"', '"subtipo_alojamento"']
        if "classificacao" in extra:
            sel.append('"classificacao"')
        steps += [f"    Combinacoes = Table.Buffer(Table.Distinct(Table.SelectColumns(Regiao, {{{', '.join(sel)}}}))),",
                  '    TiposComSubtipo = List.Buffer(List.Distinct(Table.SelectRows(Combinacoes, each [subtipo_alojamento] <> "Total")[tipo_alojamento])),']
        conds += ['[tipo_alojamento] <> "Total"',
                  '([subtipo_alojamento] <> "Total" or not List.Contains(TiposComSubtipo, [tipo_alojamento]))']
        if "classificacao" in extra:
            steps += ['    SubtiposComClasse = List.Buffer(List.Distinct(Table.SelectRows(Combinacoes, each [classificacao] <> "Total")[subtipo_alojamento])),']
            conds += ['([classificacao] <> "Total" or [subtipo_alojamento] = "Total"'
                      ' or not List.Contains(SubtiposComClasse, [subtipo_alojamento]))']
    if "local_residencia" in extra:
        # Total > Portugal | Estrangeiro > países. The labels carry no codes, so
        # "Estrangeiro" is dropped only when country rows exist to replace it.
        steps += ['    ComPaises = not Table.IsEmpty(Table.SelectRows(Regiao, each not List.Contains({"Total", "Portugal", "Estrangeiro"}, [local_residencia]))),']
        conds += ['[local_residencia] <> "Total"',
                  '([local_residencia] <> "Estrangeiro" or not ComPaises)']
    if "segmento_alojamento" in extra:
        conds += ['[segmento_alojamento] <> "Total"']
    if not conds:
        return ["    Folhas = Regiao,"]
    return steps + ["    Folhas = Table.SelectRows(Regiao, each " + " and ".join(conds) + "),"]


def fact_tmdl(ind):
    code, monthly, value, geo, extra, disp, meas, fmt, agg = ind
    name, src = tname(ind), f"ine_{code}_ds"
    text_cols = geo + extra
    L = [f"table {q(name)}", f"\tlineageTag: {tag()}", ""]
    if agg == "AVERAGE":
        L += ["\t/// Média simples publicada pelo INE. Para um valor ponderado "
              "use as medidas equivalentes de '_Medidas'."]
    L += [f"\tmeasure {q(meas)} = {agg}('{name}'[{value}])",
          f"\t\tformatString: {fmt}", f"\t\tlineageTag: {tag()}", ""]

    def col(cname, dtype, summarize="none", fs=None, hidden=False, desc=None,
            auto_summarize=False):
        o = [f"\tcolumn {q(cname)}"]
        if desc:
            o.insert(0, f"\t/// {desc}")
        o += [f"\t\tdataType: {dtype}"]
        if hidden:
            o += ["\t\tisHidden"]
        if fs:
            o += [f"\t\tformatString: {fs}"]
        if auto_summarize:
            summarize = "sum"
        o += [f"\t\tlineageTag: {tag()}", f"\t\tsummarizeBy: {summarize}",
              f"\t\tsourceColumn: {cname}", ""]
        if auto_summarize:
            # Desktop picked the summarization rather than the author.
            o += ["\t\tannotation SummarizationSetBy = Automatic", ""]
        if dtype == "dateTime":
            # Desktop tags every imported date column with its source type.
            o += ["\t\tannotation UnderlyingDateTimeDataType = Date", ""]
        return o

    for c in text_cols:
        L += col(c, "string")
    # In the monthly indicators `ano` sits beside `mes` as a plain column, and
    # Desktop summarises it; in the annual ones it is the relationship key.
    L += col("ano", "int64", "none", "0", auto_summarize=monthly)
    if monthly:
        L += col("mes", "string")
        L += col("Data", "dateTime", "none", "yyyy-mm-dd", hidden=True,
                 desc="Primeiro dia do mês, usado para ligar ao Calendário.")
    # An averaged indicator keeps AVERAGE in its base measure; the column default
    # is Desktop's own, which is why it reads `sum` rather than `average`.
    L += col(value, "double", "sum", fmt, auto_summarize=(agg == "AVERAGE"))
    L += col("create_date", "dateTime", "none", "yyyy-mm-dd", hidden=True)
    L += col("update_date", "dateTime", "none", "yyyy-mm-dd", hidden=True)
    L += col("GeoKey" if geo is MUN else "NutsIIKey", "string", hidden=True)
    if geo is MUN:
        L += col("NutsIIKey", "string", hidden=True)

    # Power Query
    # Text values arrive already trimmed: the flows strip INE labels before writing.
    # Region filter comes first so it folds into the ODBC query: only that
    # NUTS II is imported, and every dimension built from the facts follows.
    # Municipal facts also carry the NUTS II / NUTS III aggregates as rows with
    # municipio = "Total"; the measures SUM, so those would count twice.
    keep = "[nuts_ii] = RegiaoNUTSII"
    if geo is MUN:
        keep += ' and [municipio] <> "Total"'
    m = ["let",
         f'    Origem = Fonte{{[Name = "{src}", Kind = "Table"]}}[Data],',
         f"    Regiao = Table.SelectRows(Origem, each {keep}),"]
    m += leaf_steps(extra)
    if monthly:
        m += ['    ComData = Table.AddColumn(Folhas, "Data", each #date([ano], '
              'Number.FromText([mes]), 1), type date),']
        base = "ComData"
    else:
        base = "Folhas"
    keyexpr = ' & "|" & '.join(f"[{c}]" for c in geo)
    m += [f'    GeoKey = Table.AddColumn({base}, "{"GeoKey" if geo is MUN else "NutsIIKey"}", '
          f"each {keyexpr}, type text)" + ("," if geo is MUN else "")]
    if geo is MUN:
        m += ['    NutsII = Table.AddColumn(GeoKey, "NutsIIKey", each [nuts_i] & "|" & [nuts_ii], type text)']
        m += ["in", "    NutsII"]
    else:
        m += ["in", "    GeoKey"]
    L += [f"\tpartition {q(name)} = m", "\t\tmode: import", "\t\tsource ="]
    L += ["\t\t\t\t" + line for line in m]
    L += [""]
    return "\n".join(L) + "\n"


for ind in IND:
    put(f"{DEF}/tables/{tname(ind).replace('/', '-')}.tmdl", fact_tmdl(ind))

MUN_T = [tname(i) for i in IND if i[3] is MUN]
REG_T = [tname(i) for i in IND if i[3] is REG]
MONTHLY_T = [tname(i) for i in IND if i[1]]
ANNUAL_T = [tname(i) for i in IND if not i[1]]
TIPO_T = [tname(i) for i in IND if "tipo_alojamento" in i[4]]
RESID_T = [tname(i) for i in IND if "local_residencia" in i[4]]
SEG_T = [tname(i) for i in IND if "segmento_alojamento" in i[4]]


def union(tables, cols):
    """cols: list of (output name, source column)."""
    parts = []
    for t in tables:
        sel = ", ".join(f'"{o}", \'{t}\'[{s}]' for o, s in cols)
        parts.append(f"            SELECTCOLUMNS('{t}', {sel})")
    if len(parts) == 1:
        return parts[0].strip()
    return "UNION(\n" + ",\n".join(parts) + "\n        )"


def calc_table(name, dax, cols, desc=None, data_category=None, pinned=False):
    L = []
    if desc:
        L += [f"/// {desc}"]
    L += [f"table {q(name)}",
          f"\tlineageTag: {tag(f'tabela-{name}' if pinned else None)}"]
    if data_category:
        L += [f"\tdataCategory: {data_category}"]
    L += [""]
    for cname, dtype, summarize, hidden, key, *rest in cols:
        col_category = rest[0] if rest else None
        L += [f"\tcolumn {q(cname)}", f"\t\tdataType: {dtype}"]
        if hidden:
            L += ["\t\tisHidden"]
        if key:
            L += ["\t\tisKey"]
        L += [f"\t\tlineageTag: {tag(f'coluna-{name}-{cname}' if pinned else None)}"]
        if col_category:
            L += [f"\t\tdataCategory: {col_category}"]
        L += [f"\t\tsummarizeBy: {summarize}",
              f"\t\tsourceColumn: [{cname}]", ""]
    L += [f"\tpartition {q(name)} = calculated", "\t\tmode: import"]
    if "\n" in dax:
        L += ["\t\tsource ="] + ["\t\t\t\t" + line for line in dax.split("\n")]
    else:
        L += [f"\t\tsource = {dax}"]
    L += [""]
    return "\n".join(L) + "\n"


# Ano: conformed across every indicator
ano_dax = f"""VAR Anos =
    DISTINCT(
        {union([tname(i) for i in IND], [("Ano", "ano")])}
    )
RETURN
    ADDCOLUMNS(Anos, "Década", INT([Ano] / 10) * 10)"""
put(f"{DEF}/tables/Ano.tmdl", calc_table(
    "Ano", ano_dax,
    [("Ano", "int64", "none", False, True), ("Década", "int64", "none", False, False)],
    "Dimensão de ano, conforme a todos os indicadores (anuais e mensais)."))

# Calendario: month grain derived from the monthly facts
cal_dax = f"""VAR Datas =
    DISTINCT(
        {union(MONTHLY_T, [("Data", "Data")])}
    )
// Sem dados mensais (tabelas vazias ou falha no refresh), usa o ano corrente.
VAR Inicio = DATE(YEAR(COALESCE(MINX(Datas, [Data]), TODAY())), 1, 1)
VAR Fim = EOMONTH(COALESCE(MAXX(Datas, [Data]), TODAY()), 0)
RETURN
    ADDCOLUMNS(
        CALENDAR(Inicio, Fim),
        "Ano", YEAR([Date]),
        "Mês", MONTH([Date]),
        "Nome do mês", FORMAT([Date], "mmmm"),
        "Ano-Mês", FORMAT([Date], "yyyy-mm"),
        "Trimestre", "T" & FORMAT([Date], "q")
    )"""
put(f"{DEF}/tables/Calendário.tmdl", calc_table(
    "Calendário", cal_dax,
    [("Date", "dateTime", "none", False, True), ("Ano", "int64", "none", False, False),
     ("Mês", "int64", "none", False, False), ("Nome do mês", "string", "none", False, False),
     ("Ano-Mês", "string", "none", False, False), ("Trimestre", "string", "none", False, False)],
    "Calendário diário cobrindo os indicadores mensais. Os factos mensais ligam ao dia 1 de cada mês.",
    data_category="Time"))

# Geografia: municipality grain, union of every municipality-grain fact
geo_cols = [("GeoKey", "GeoKey"), ("NUTS I", "nuts_i"), ("NUTS II", "nuts_ii"),
            ("NUTS III", "nuts_iii"), ("Distrito", "distrito"), ("Município", "municipio"),
            ("NutsIIKey", "NutsIIKey")]
# The model carries no coordinates, so map visuals depend on Power BI geocoding the
# names. A bare "Évora" is ambiguous worldwide; the country-qualified column below
# resolves reliably and is the one to drop on a map.
geo_dax = (f"ADDCOLUMNS(\n    DISTINCT(\n        {union(MUN_T, geo_cols)}\n    ),\n"
           '    "Município (mapa)", [Município] & ", Portugal"\n)')
put(f"{DEF}/tables/Geografia.tmdl", calc_table(
    "Geografia", geo_dax,
    [("GeoKey", "string", "none", True, True), ("NUTS I", "string", "none", False, False),
     ("NUTS II", "string", "none", False, False), ("NUTS III", "string", "none", False, False),
     ("Distrito", "string", "none", False, False, "StateOrProvince"),
     ("Município", "string", "none", False, False),
     ("Município (mapa)", "string", "none", False, False, "Place"),
     ("NutsIIKey", "string", "none", True, False)],
    "Geografia ao nível do município, construída a partir de todos os indicadores municipais."))

# RegiaoNutsII: covers both the municipality facts (via Geografia) and the NUTS II only facts
reg_parts = [
    '        SELECTCOLUMNS(\'Geografia\', "NutsIIKey", \'Geografia\'[NutsIIKey], '
    '"NUTS I", \'Geografia\'[NUTS I], "NUTS II", \'Geografia\'[NUTS II])']
for t in REG_T:
    reg_parts.append(
        f'        SELECTCOLUMNS(\'{t}\', "NutsIIKey", \'{t}\'[NutsIIKey], '
        f'"NUTS I", \'{t}\'[nuts_i], "NUTS II", \'{t}\'[nuts_ii])')
reg_dax = "DISTINCT(\n    UNION(\n" + ",\n".join(reg_parts) + "\n    )\n)"
put(f"{DEF}/tables/Região NUTS II.tmdl", calc_table(
    "Região NUTS II", reg_dax,
    [("NutsIIKey", "string", "none", True, True), ("NUTS I", "string", "none", False, False),
     ("NUTS II", "string", "none", False, False)],
    "Dimensão NUTS II conforme aos indicadores municipais e aos indicadores só com NUTS I/II. "
    "Só contém a região do parâmetro RegiaoNUTSII."))

# TipoAlojamento
# TipoKey is not a source column on the facts, so build it inline
tipo_parts = [f'        SELECTCOLUMNS(\'{t}\', '
              f'"TipoKey", \'{t}\'[tipo_alojamento] & "|" & \'{t}\'[subtipo_alojamento], '
              f'"Tipo de alojamento", \'{t}\'[tipo_alojamento], '
              f'"Subtipo de alojamento", \'{t}\'[subtipo_alojamento])'
              for t in TIPO_T]
tipo_dax = "DISTINCT(\n    UNION(\n" + ",\n".join(tipo_parts) + "\n    )\n)"
put(f"{DEF}/tables/Tipo de alojamento.tmdl", calc_table(
    "Tipo de alojamento", tipo_dax,
    [("TipoKey", "string", "none", True, True), ("Tipo de alojamento", "string", "none", False, False),
     ("Subtipo de alojamento", "string", "none", False, False)],
    "Tipo e subtipo de alojamento, conforme aos indicadores que os publicam. "
    "A classificação (estrelas) fica local a cada indicador."))

# Residencia / Segmento: single column dimensions
put(f"{DEF}/tables/Residência.tmdl", calc_table(
    "Residência", "DISTINCT(\n    " + union(RESID_T, [("Local de residência", "local_residencia")]) + "\n)",
    [("Local de residência", "string", "none", False, True)],
    "País ou local de residência dos hóspedes."))
put(f"{DEF}/tables/Segmento de alojamento.tmdl", calc_table(
    "Segmento de alojamento", "DISTINCT(\n    " + union(SEG_T, [("Segmento", "segmento_alojamento")]) + "\n)",
    [("Segmento", "string", "none", False, True)],
    "Segmento de alojamento dos indicadores mensais municipais."))

# ------------------------------------------------------------------ disconnected tables
# Deliberately unrelated to anything. The município choice must not filter the model:
# the peer visuals, the peer average and the choropleth all have to keep showing every
# território while one of them is singled out. Selection is read with SELECTEDVALUE and
# applied as conditional formatting, never as filter context. Do not add a relationship
# here, and do not put 'Geografia'[Município] on the pages that use these.
put(f"{DEF}/tables/Município selecionado.tmdl", calc_table(
    "Município selecionado",
    'DISTINCT(SELECTCOLUMNS(\'Geografia\', "Município", \'Geografia\'[Município]))',
    [("Município", "string", "none", False, True)],
    "Tabela desligada que guarda o município em foco. Não filtra o modelo: "
    "serve para realçar um território entre os pares."))

put(f"{DEF}/tables/Métrica de pressão.tmdl", calc_table(
    "Métrica de pressão",
    'DATATABLE(\n    "Métrica", STRING,\n    {\n'
    '        {"Dormidas por km²"},\n        {"Hóspedes por km²"}\n    }\n)',
    [("Métrica", "string", "none", False, True)],
    "Tabela desligada com as métricas da página de pressão turística."))

# The model imports a single NUTS II (RegiaoNUTSII), so the focus sits one level
# down: one NUTS III picked out among the region's other sub-regions.
put(f"{DEF}/tables/Sub-região em foco.tmdl", calc_table(
    "Sub-região em foco",
    'DISTINCT(SELECTCOLUMNS(\'Geografia\', "NUTS III", \'Geografia\'[NUTS III]))',
    [("NUTS III", "string", "none", False, True)],
    "Tabela desligada que guarda a sub-região em foco. Não filtra o modelo: serve "
    "para realçar uma NUTS III entre as outras, como 'Município selecionado' faz "
    "para os municípios.",
    pinned=True))
_stale = f"{DEF}/tables/Região em foco.tmdl"
if os.path.exists(_stale):
    os.remove(_stale)

# ------------------------------------------------------------------ measure table
def m(name, expr, fmt, desc=None, pinned=False):
    L = []
    if desc:
        L += [f"\t/// {desc}"]
    lines = expr.split("\n")
    if len(lines) == 1:
        L += [f"\tmeasure {q(name)} = {expr}"]
    else:
        L += [f"\tmeasure {q(name)} ="]
        # Keep space indentation so nested DAX stays readable; tab prefixes in the
        # source literals are only there for alignment inside this file.
        L += ["\t\t\t" + ln.rstrip().lstrip("\t") for ln in lines]
    if fmt:
        L += [f"\t\tformatString: {fmt}"]
    L += [f"\t\tlineageTag: {tag(f'medida-{name}' if pinned else None)}", ""]
    return L

T9877, T9876 = tname(IND[7]), tname(IND[6])
T9183, T9930 = tname(IND[1]), tname(IND[10])
T10735, T10736 = tname(IND[11]), tname(IND[12])
T9874, T9873 = tname(IND[5]), tname(IND[4])

ML = ["/// Medidas derivadas e comparações entre indicadores.", f"table {q('_Medidas')}",
      f"\tlineageTag: {tag()}", ""]
ML += m("Estada média ponderada (tipo)",
        f"DIVIDE([Dormidas (tipo)], [Hóspedes (tipo)])", "#,0.00",
        "Dormidas / hóspedes do mesmo grão. Preferir a esta medida a média simples do INE.")
ML += m("Estada média ponderada (residência)",
        f"DIVIDE([Dormidas (residência)], [Hóspedes (residência)])", "#,0.00",
        "Dormidas / hóspedes por país de residência.")
ML += m("Estada média mensal ponderada (segmento)",
        f"DIVIDE([Dormidas mensais (segmento)], [Hóspedes mensais (segmento)])", "#,0.00")
ML += m("Quartos por estabelecimento", "DIVIDE([Quartos (tipo)], [Estabelecimentos])", "#,0.00")
ML += m("Dormidas (ano anterior)",
        "VAR AnoAtual = SELECTEDVALUE('Ano'[Ano])\n"
        "RETURN\n"
        "    IF(\n"
        "        NOT ISBLANK(AnoAtual),\n"
        "        CALCULATE([Dormidas (tipo)], REMOVEFILTERS('Ano'), 'Ano'[Ano] = AnoAtual - 1)\n"
        "    )", "#,0",
        "Dormidas do ano anterior. Requer um único ano no contexto de filtro.")
ML += m("Dormidas YoY %",
        "VAR Atual = [Dormidas (tipo)]\n"
        "\t\tVAR Anterior = [Dormidas (ano anterior)]\n"
        "\t\tRETURN DIVIDE(Atual - Anterior, Anterior)", "0.0%")
ML += m("Dormidas mensais (mês anterior)",
        "CALCULATE([Dormidas mensais (segmento)], "
        "DATEADD('Calendário'[Date], -1, MONTH))", "#,0")
ML += m("Dormidas mensais MoM %",
        "VAR Atual = [Dormidas mensais (segmento)]\n"
        "\t\tVAR Anterior = [Dormidas mensais (mês anterior)]\n"
        "\t\tRETURN DIVIDE(Atual - Anterior, Anterior)", "0.0%")
ML += m("Noites-quarto disponíveis",
        "SUMX(\n"
        "\t\tVALUES('Ano'[Ano]),\n"
        "\t\tCALCULATE([Quartos (tipo)])\n"
        "\t\t\t* (DATEDIFF(DATE('Ano'[Ano], 1, 1), DATE('Ano'[Ano], 12, 31), DAY) + 1)\n"
        "\t)", "#,0",
        "Capacidade anual: quartos × dias do ano, somada ano a ano para suportar "
        "várias seleções de ano.")
ML += m("Ocupação estimada",
        "DIVIDE([Dormidas (tipo)], [Noites-quarto disponíveis])", "0.0%",
        "Aproximação à ocupação: dormidas ÷ noites-quarto disponíveis. As dormidas "
        "do INE são noites de hóspede, não de quarto, pelo que um quarto partilhado "
        "conta mais do que uma vez e o valor pode passar os 100%. Serve para "
        "comparar municípios, não como taxa de ocupação oficial.")
# --- per-km² measures.
# 0008350 publishes 2004-2022 and its DAG is capped at 2022 (PUBLISHED_YEAR_CAPS),
# so dividing by the surface of the *selected* year blanks out every ratio from
# 2023 onwards — exactly the years these pages are about. The area is pinned to the
# last published year instead: municipal areas barely change, and pinning one year
# also stops the surface being summed once per year over a multi-year selection.
# Show 'Ano da superfície' next to any of these so the área's vintage is disclosed.
ML += m("Ano da superfície",
        "MAXX(\n"
        "    FILTER(\n"
        "        CALCULATETABLE(VALUES('Ano'[Ano]), REMOVEFILTERS('Ano')),\n"
        "        NOT ISBLANK([Superfície (km²)])\n"
        "    ),\n"
        "    'Ano'[Ano]\n"
        ")", "#,0",
        "Último ano com superfície publicada (2022 enquanto o INE não publicar "
        "a série NUTS-2024). É o ano que todas as medidas «por km²» usam.")
ML += m("Superfície (km², último ano)",
        "VAR AnoArea = [Ano da superfície]\n"
        "RETURN\n"
        "    CALCULATE(\n"
        "        [Superfície (km²)],\n"
        "        REMOVEFILTERS('Ano'),\n"
        "        'Ano'[Ano] = AnoArea\n"
        "    )", "#,0.00",
        "Superfície do último ano publicado, independente do ano selecionado. "
        "Denominador de todas as medidas «por km²».")
ML += m("Dormidas por km²",
        "DIVIDE([Dormidas (tipo)], [Superfície (km², último ano)])", "#,0.00",
        "Intensidade turística: dormidas anuais por quilómetro quadrado. "
        "A área é a do último ano publicado, não a do ano selecionado.")
ML += m("Hóspedes por km²",
        "DIVIDE([Hóspedes (tipo)], [Superfície (km², último ano)])", "#,0.00")
ML += m("Quartos por km²",
        "DIVIDE([Quartos (tipo)], [Superfície (km², último ano)])", "#,0.00",
        "Capacidade licenciada por quilómetro quadrado. Ler ao lado de "
        "[Dormidas por km²] para separar carga de capacidade.")
ML += m("Estabelecimentos por km²",
        "DIVIDE([Estabelecimentos], [Superfície (km², último ano)])", "#,0.00")
# --- comparison measures for the three comparison pages.
# All read the focus município from the disconnected 'Município selecionado' and
# restrict the comparison set to municípios that actually report the metric: a
# fixed denominator would rank a território against ones that never reported.
def pares(metric):
    """VAR block: focus município, its NUTS III peers, and those reporting `metric`."""
    return (
        "VAR Sel = SELECTEDVALUE('Município selecionado'[Município])\n"
        "VAR NutsSel =\n"
        "    CALCULATE(\n"
        "        SELECTEDVALUE('Geografia'[NUTS III]),\n"
        "        REMOVEFILTERS('Geografia'),\n"
        "        'Geografia'[Município] = Sel\n"
        "    )\n"
        "VAR Pares =\n"
        "    CALCULATETABLE(\n"
        "        VALUES('Geografia'[Município]),\n"
        "        REMOVEFILTERS('Geografia'),\n"
        "        'Geografia'[NUTS III] = NutsSel\n"
        "    )\n"
        f"VAR ComDados = FILTER(Pares, NOT ISBLANK(CALCULATE([{metric}])))\n")


def posicao(metric):
    """Dense descending rank of the focus município among the peers that report."""
    return (
        pares(metric) +
        "VAR ValorSel =\n"
        "    CALCULATE(\n"
        f"        [{metric}],\n"
        "        REMOVEFILTERS('Geografia'),\n"
        "        'Geografia'[Município] = Sel\n"
        "    )\n"
        "RETURN\n"
        "    IF(\n"
        "        NOT ISBLANK(ValorSel),\n"
        f"        RANKX(ComDados, CALCULATE([{metric}]), ValorSel, DESC, DENSE)\n"
        "    )")


PARES = pares("Ocupação estimada")

ML += m("Pares com dados",
        PARES + "RETURN COUNTROWS(ComDados)", "#,0",
        "Quantos municípios do grupo de pares reportam ocupação no contexto atual. "
        "Mostrar sempre junto da posição: «5.º de 12», nunca «5.º» sozinho.")
ML += m("Média de pares (ocupação)",
        PARES + "RETURN AVERAGEX(ComDados, CALCULATE([Ocupação estimada]))", "0.0%",
        "Média da ocupação estimada no grupo de pares (mesma NUTS III), contando "
        "apenas os municípios que reportam.")
ML += m("Posição no grupo de pares",
        posicao("Ocupação estimada"), "#,0",
        "Posição do município em foco dentro do grupo de pares, por ocupação estimada. "
        "Em branco se o próprio município não reportar.")
ML += m("Percentil de pressão",
        "VAR Sel = SELECTEDVALUE('Município selecionado'[Município])\n"
        "VAR Todos =\n"
        "    CALCULATETABLE(VALUES('Geografia'[Município]), REMOVEFILTERS('Geografia'))\n"
        "VAR ComDados = FILTER(Todos, NOT ISBLANK(CALCULATE([Dormidas por km²])))\n"
        "VAR ValorSel =\n"
        "    CALCULATE(\n"
        "        [Dormidas por km²],\n"
        "        REMOVEFILTERS('Geografia'),\n"
        "        'Geografia'[Município] = Sel\n"
        "    )\n"
        "VAR Abaixo =\n"
        "    COUNTROWS(FILTER(ComDados, CALCULATE([Dormidas por km²]) < ValorSel))\n"
        "RETURN\n"
        "    IF(NOT ISBLANK(ValorSel), DIVIDE(Abaixo, COUNTROWS(ComDados)))", "0.0%",
        "Posição relativa do município em foco na distribuição de dormidas por km² "
        "de todos os municípios que reportam.")
ML += m("Índice de sazonalidade",
        "VAR AnoCompleto =\n"
        "    MAXX(\n"
        "        FILTER(\n"
        "            CALCULATETABLE(VALUES('Calendário'[Ano]), REMOVEFILTERS('Calendário')),\n"
        "            CALCULATE(\n"
        "                COUNTROWS(\n"
        "                    FILTER(\n"
        "                        VALUES('Calendário'[Mês]),\n"
        "                        NOT ISBLANK([Dormidas mensais (segmento)])\n"
        "                    )\n"
        "                )\n"
        "            ) = 12\n"
        "        ),\n"
        "        'Calendário'[Ano]\n"
        "    )\n"
        "RETURN\n"
        "    CALCULATE(\n"
        "        VAR PorMes =\n"
        "            ADDCOLUMNS(\n"
        "                VALUES('Calendário'[Mês]),\n"
        "                \"V\", CALCULATE([Dormidas mensais (segmento)])\n"
        "            )\n"
        "        RETURN DIVIDE(MAXX(PorMes, [V]), AVERAGEX(PorMes, [V])),\n"
        "        REMOVEFILTERS('Calendário'),\n"
        "        'Calendário'[Ano] = AnoCompleto\n"
        "    )", "#,0.00",
        "Mês de pico a dividir pela média mensal, no último ano civil completo. "
        "Usa o último ano completo de propósito: um ano cortado a meio é todo pico "
        "e nenhum inverno, o que empolaria justamente o que a página mede.")
ML += m("Ano completo mais recente",
        "MAXX(\n"
        "    FILTER(\n"
        "        CALCULATETABLE(VALUES('Calendário'[Ano]), REMOVEFILTERS('Calendário')),\n"
        "        CALCULATE(\n"
        "            COUNTROWS(\n"
        "                FILTER(\n"
        "                    VALUES('Calendário'[Mês]),\n"
        "                    NOT ISBLANK([Dormidas mensais (segmento)])\n"
        "                )\n"
        "            )\n"
        "        ) = 12\n"
        "    ),\n"
        "    'Calendário'[Ano]\n"
        ")", "#,0",
        "O ano que o índice de sazonalidade usa. Mostrar no título do painel.")
ML += m("Pressão (métrica selecionada)",
        "SWITCH(\n"
        "    SELECTEDVALUE('Métrica de pressão'[Métrica], \"Dormidas por km²\"),\n"
        "    \"Hóspedes por km²\", [Hóspedes por km²],\n"
        "    [Dormidas por km²]\n"
        ")", "#,0.00",
        "Métrica do mapa de pressão, escolhida na tabela desligada.")
# RevPAR year-on-year. Mirrors [Dormidas (ano anterior)]: the previous year is read
# with REMOVEFILTERS so a single-year selection still finds it.
ML += m("RevPAR médio (ano anterior)",
        "VAR AnoAtual = SELECTEDVALUE('Ano'[Ano])\n"
        "RETURN\n"
        "    IF(\n"
        "        NOT ISBLANK(AnoAtual),\n"
        "        CALCULATE([RevPAR médio INE], REMOVEFILTERS('Ano'), 'Ano'[Ano] = AnoAtual - 1)\n"
        "    )", "#,0.00",
        "RevPAR médio do ano anterior. Requer um único ano no contexto de filtro.",
        pinned=True)
ML += m("RevPAR YoY %",
        "VAR Atual = [RevPAR médio INE]\n"
        "VAR Anterior = [RevPAR médio (ano anterior)]\n"
        "RETURN DIVIDE(Atual - Anterior, Anterior)", "0.0%",
        pinned=True)
# Peer rank and denominator for the other two KPI tiles. Each metric needs its own
# pair: a município that reports ocupação may not report RevPAR, so reusing
# [Pares com dados] as the denominator would print «3.º de 14» against 11 peers.
ML += m("Pares com dados (pressão)",
        pares("Dormidas por km²") + "RETURN COUNTROWS(ComDados)", "#,0",
        "Quantos municípios do grupo de pares reportam dormidas por km². "
        "Denominador de [Posição no grupo de pares (pressão)].",
        pinned=True)
ML += m("Posição no grupo de pares (pressão)",
        posicao("Dormidas por km²"), "#,0",
        "Posição do município em foco dentro do grupo de pares, por dormidas por km². "
        "Mostrar sempre com [Pares com dados (pressão)].",
        pinned=True)
ML += m("Pares com dados (RevPAR)",
        pares("RevPAR médio INE") + "RETURN COUNTROWS(ComDados)", "#,0",
        "Quantos municípios do grupo de pares reportam RevPAR. "
        "Denominador de [Posição no grupo de pares (RevPAR)].",
        pinned=True)
ML += m("Posição no grupo de pares (RevPAR)",
        posicao("RevPAR médio INE"), "#,0",
        "Posição do município em foco dentro do grupo de pares, por RevPAR médio. "
        "Mostrar sempre com [Pares com dados (RevPAR)].",
        pinned=True)
# Denominator behind [Percentil de pressão] — «78, entre 308 municípios».
ML += m("Municípios com dados de pressão",
        "VAR Todos =\n"
        "    CALCULATETABLE(VALUES('Geografia'[Município]), REMOVEFILTERS('Geografia'))\n"
        "RETURN\n"
        "    COUNTROWS(FILTER(Todos, NOT ISBLANK(CALCULATE([Dormidas por km²]))))", "#,0",
        "Quantos municípios reportam dormidas por km² no contexto atual. É o "
        "denominador de [Percentil de pressão]: mostrar os dois juntos.",
        pinned=True)
# Highlight for the município em foco. Returns a colour, not a 0/1 flag, because
# «Field value» conditional formatting reads the measure as the fill directly.
ML += m("Cor do município em foco",
        "IF(\n"
        "    SELECTEDVALUE('Geografia'[Município])\n"
        "        = SELECTEDVALUE('Município selecionado'[Município]),\n"
        '    "#FFAD00",\n'
        '    "#2066BC"\n'
        ")", None,
        "Dourado no município em foco, azul nos pares. Ligar ao «Field value» da cor "
        "das barras; exige 'Geografia'[Município] no eixo.",
        pinned=True)
# Peer comparator for the estada média tile. Averages each peer's weighted stay
# rather than pooling dormidas and hóspedes across the group: a pooled ratio is
# dominated by the largest município, which is not what «face aos pares» means.
# Same convention as [Média de pares (ocupação)].
ML += m("Média de pares (estada média)",
        pares("Estada média ponderada (tipo)")
        + "RETURN AVERAGEX(ComDados, CALCULATE([Estada média ponderada (tipo)]))", "#,0.00",
        "Média da estada média ponderada no grupo de pares (mesma NUTS III), "
        "contando apenas os municípios que reportam.",
        pinned=True)
ML += m("Cor da sub-região em foco",
        "IF(\n"
        "    SELECTEDVALUE('Geografia'[NUTS III])\n"
        "        = SELECTEDVALUE('Sub-região em foco'[NUTS III]),\n"
        '    "#FFAD00",\n'
        '    "#2066BC"\n'
        ")", None,
        "Dourado na sub-região em foco, azul nas outras. Ligar ao «Field value» da cor "
        "das barras; exige 'Geografia'[NUTS III] no eixo.",
        pinned=True)
# --- page subtitles ----------------------------------------------------------
# The header band echoes the current selection back to the reader, so each page
# carries one string measure instead of a hardcoded sentence. The region comes
# from the data, so the label follows RegiaoNUTSII without a second edit here.
REGIAO = "VAR Regiao = CALCULATE(SELECTEDVALUE('Região NUTS II'[NUTS II], \"várias regiões\"), ALL('Região NUTS II'))\n"
ML += m("Subtítulo · quadro comparativo",
        REGIAO +
        'VAR Mun = SELECTEDVALUE(\'Município selecionado\'[Município], "município por escolher")\n'
        'VAR Pares = SELECTEDVALUE(\'Geografia\'[NUTS III], "todos os pares")\n'
        "VAR AnoSel = SELECTEDVALUE('Ano'[Ano])\n"
        "RETURN\n"
        '    Regiao & " · " & Mun & " · " & Pares & " · "\n'
        '        & IF(ISBLANK(AnoSel), "todos os anos", FORMAT(AnoSel, "0"))', None,
        "Região · município em foco · grupo de pares · ano, para o cabeçalho da página A.",
        pinned=True)
ML += m("Subtítulo · pressão turística",
        REGIAO +
        'VAR Metrica = SELECTEDVALUE(\'Métrica de pressão\'[Métrica], "Dormidas por km²")\n'
        "VAR AnoSel = SELECTEDVALUE('Ano'[Ano])\n"
        "RETURN\n"
        '    Regiao & " · " & Metrica & " · "\n'
        '        & IF(ISBLANK(AnoSel), "todos os anos", FORMAT(AnoSel, "0"))', None,
        "Região · métrica escolhida · ano, para o cabeçalho da página B.",
        pinned=True)
ML += m("Subtítulo · sazonalidade",
        REGIAO +
        "VAR AnoMin = MIN('Calendário'[Ano])\n"
        "VAR AnoMax = MAX('Calendário'[Ano])\n"
        "RETURN\n"
        '    Regiao & " · Dormidas mensais · " & FORMAT(AnoMin, "0") & " – " & FORMAT(AnoMax, "0")', None,
        "Região · intervalo de anos publicado, para o cabeçalho da página C.",
        pinned=True)

# --- year-on-year, one pair per indicator -------------------------------------
# Two patterns, because the two families hang off different dimensions:
#   * annual indicators join 'Ano', so the previous year is read by swapping the
#     year filter, exactly as [Dormidas (ano anterior)] does;
#   * monthly indicators join 'Calendário' (marked as the date table), so DATEADD
#     over the date column is used instead. It composes at both grains: the same
#     measure answers «this month vs the same month last year» and «this year vs
#     last year», which the 'Ano' pattern cannot do once a month is selected.
# `Dormidas (tipo)` and `RevPAR médio INE` already have their pair above, under
# the shorter names they were first published with.
ALREADY_YOY = {"Dormidas (tipo)", "RevPAR médio INE"}


def yoy_names(meas):
    """Derive the pair's names, keeping the model's parenthetical style."""
    prior = f"{meas[:-1]}, ano anterior)" if meas.endswith(")") else f"{meas} (ano anterior)"
    return prior, f"{meas} YoY %"


for _ind in IND:
    _monthly, _disp, _meas, _fmt = _ind[1], _ind[5], _ind[6], _ind[7]
    if _meas in ALREADY_YOY:
        continue
    _prior, _pct = yoy_names(_meas)
    if _monthly:
        _expr = f"CALCULATE([{_meas}], DATEADD('Calendário'[Date], -1, YEAR))"
    else:
        _expr = ("VAR AnoAtual = SELECTEDVALUE('Ano'[Ano])\n"
                 "RETURN\n"
                 "    IF(\n"
                 "        NOT ISBLANK(AnoAtual),\n"
                 f"        CALCULATE([{_meas}], REMOVEFILTERS('Ano'), 'Ano'[Ano] = AnoAtual - 1)\n"
                 "    )")
    ML += m(_prior, _expr, _fmt,
            f"{_disp} do ano anterior."
            + ("" if _monthly else " Requer um único ano no contexto de filtro."),
            pinned=True)
    ML += m(_pct,
            f"VAR Atual = [{_meas}]\n"
            f"VAR Anterior = [{_prior}]\n"
            "RETURN DIVIDE(Atual - Anterior, Anterior)", "0.0%",
            f"Variação homóloga de [{_meas}]. Em branco sem ano anterior publicado.",
            pinned=True)

# Added in Power BI Desktop for transparent fills; its lineageTag is Desktop's own.
ML += ['\tmeasure Transparente = "rgba(0,0,0,0)"',
       "\t\tlineageTag: 169bceb7-9232-46bc-b225-007ca755a4df", ""]

ML += ["\tcolumn _", "\t\tdataType: string", "\t\tisHidden",
       f"\t\tlineageTag: {tag()}", "\t\tsummarizeBy: none", "\t\tsourceColumn: [_]", ""]
ML += ["\tpartition _Medidas = calculated", "\t\tmode: import",
       '\t\tsource = ROW("_", BLANK())', ""]
put(f"{DEF}/tables/_Medidas.tmdl", "\n".join(ML) + "\n")

# ------------------------------------------------------------------ relationships
rels = []
def rel(ft, fc, tt, tc, active=True):
    r = [f"relationship {tag()}"]
    if not active:
        r.append("\tisActive: false")
    r += [f"\tfromColumn: {q(ft)}.{q(fc)}", f"\ttoColumn: {q(tt)}.{q(tc)}", ""]
    rels.append("\n".join(r))

for t in ANNUAL_T:
    rel(t, "ano", "Ano", "Ano")
for t in MONTHLY_T:
    rel(t, "Data", "Calendário", "Date")
rel("Calendário", "Ano", "Ano", "Ano")
for t in MUN_T:
    rel(t, "GeoKey", "Geografia", "GeoKey")
rel("Geografia", "NutsIIKey", "Região NUTS II", "NutsIIKey")
for t in REG_T:
    rel(t, "NutsIIKey", "Região NUTS II", "NutsIIKey")
for t in RESID_T:
    rel(t, "local_residencia", "Residência", "Local de residência")
for t in SEG_T:
    rel(t, "segmento_alojamento", "Segmento de alojamento", "Segmento")
# Each entry already ends in "\n"; the extra one is the blank line Desktop leaves.
put(f"{DEF}/relationships.tmdl", "\n".join(rels) + "\n")

# ------------------------------------------------------------------ expressions
put(f"{DEF}/expressions.tmdl", f"""/// Nome do DSN ODBC (System DSN) que aponta para a base de dados PostgreSQL.
/// Tem de existir com o mesmo nome no PC do Power BI Desktop e nas máquinas do gateway 'pistadigital'.
expression DSN = "Pista Digital" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
\tlineageTag: {tag()}
\tqueryGroup: Parâmetros

\tannotation PBI_NavigationStepName = Navigation

\tannotation PBI_ResultType = Text

/// Nome da base de dados (PISTA_DB_NAME).
expression BaseDados = "pista" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
\tlineageTag: {tag()}
\tqueryGroup: Parâmetros

\tannotation PBI_NavigationStepName = Navigation

\tannotation PBI_ResultType = Text

/// Região NUTS II importada. Todas as tabelas filtram nuts_ii por este valor antes de carregar.
/// Os indicadores municipais usam a NUTS 2013 (o Alentejo inclui a Lezíria do Tejo); o 0012093 usa a NUTS 2024.
expression RegiaoNUTSII = "Alentejo" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
\tlineageTag: {tag("parametro-RegiaoNUTSII")}
\tqueryGroup: Parâmetros

\tannotation PBI_NavigationStepName = Navigation

\tannotation PBI_ResultType = Text

/// Ligação partilhada via ODBC (gateway 'pistadigital'): navegação até ao esquema public.
/// As tabelas leem Fonte{{[Name = "ine_<varcd>", Kind = "Table"]}}[Data].
/// As credenciais são pedidas pelo Power BI e nunca ficam no ficheiro.
expression Fonte =
\t\tlet
\t\t    Origem = Odbc.DataSource("dsn=" & DSN, [HierarchicalNavigation = true]),
\t\t    BaseDeDados = Origem{{[Name = BaseDados, Kind = "Database"]}}[Data],
\t\t    Esquema = BaseDeDados{{[Name = "public", Kind = "Schema"]}}[Data]
\t\tin
\t\t    Esquema
\tlineageTag: {tag()}
\tqueryGroup: Parâmetros

\tannotation PBI_ResultType = Table

""")

# ------------------------------------------------------------------ model + culture
refs = "\n".join(f"ref table {q(tname(i))}" for i in IND)
# PBI_QueryOrder carries the parameter queries after the indicator tables, and
# Desktop writes it without spaces after the commas.
query_order = ",".join(f'"{n}"' for n in
                       [tname(i) for i in IND] + ["DSN", "BaseDados", "RegiaoNUTSII", "Fonte"])
dim_refs = "\n".join(f"ref table {q(n)}" for n in [
    "Ano", "Calendário", "Geografia", "Região NUTS II", "Tipo de alojamento",
    "Residência", "Segmento de alojamento", "Município selecionado",
    "Métrica de pressão", "_Medidas", "Sub-região em foco"])
put(f"{DEF}/model.tmdl", f"""model Model
\tculture: pt-PT
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tsourceQueryCulture: pt-PT
\tdataAccessOptions
\t\tlegacyRedirects
\t\treturnErrorValuesAsNull

queryGroup Parâmetros

\tannotation PBI_QueryGroupOrder = 0

annotation PBI_QueryOrder = [{query_order}]

annotation __PBI_TimeIntelligenceEnabled = 0

annotation PBI_ProTooling = ["DevMode"]

{refs}
{dim_refs}

ref cultureInfo pt-PT

""")
put(f"{DEF}/cultures/pt-PT.tmdl",
    'cultureInfo pt-PT\n'
    '\n'
    '\tlinguisticMetadata =\n'
    '\t\t\t{\n'
    '\t\t\t  "Version": "1.0.0",\n'
    '\t\t\t  "Language": "pt-PT"\n'
    '\t\t\t}\n'
    '\t\tcontentType: json\n'
    '\n')
put(f"{DEF}/database.tmdl", "database\n\tcompatibilityLevel: 1606\n\n")
if os.path.exists(f"{DEF}/tables/Exemplo.tmdl"):
    os.remove(f"{DEF}/tables/Exemplo.tmdl")
print("tables:", len(os.listdir(f"{DEF}/tables")), "relationships:", len(rels))
