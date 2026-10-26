"""Regenerate the PistaDigital semantic model (TMDL) from the INE indicator definitions.

The INDICATORS table below mirrors flows-code/pistadigital/flows/ine_*_flow.py.
When an indicator is added or its schema changes, update INDICATORS and run:

    python3 powerbi/tools/generate_semantic_model.py
    python3 powerbi/tools/validate_semantic_model.py
"""
import os, shutil, uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "PistaDigital.SemanticModel")
DEF = os.path.join(MODEL, "definition")

_n = [0]
def tag():
    _n[0] += 1
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"pistadigital-{_n[0]}"))

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
     "Quartos em alojamento turístico", "Quartos", "#,0", "SUM"),
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
def fact_tmdl(ind):
    code, monthly, value, geo, extra, disp, meas, fmt, agg = ind
    name, src = tname(ind), f"ine_{code}_ds"
    text_cols = geo + extra
    L = [f"table '{name}'", f"\tlineageTag: {tag()}", ""]
    if agg == "AVERAGE":
        L += ["\t/// Média simples publicada pelo INE. Para um valor ponderado "
              "use as medidas equivalentes de '_Medidas'."]
    L += [f"\tmeasure '{meas}' = {agg}('{name}'[{value}])",
          f"\t\tformatString: {fmt}", f"\t\tlineageTag: {tag()}", ""]

    def col(cname, dtype, summarize="none", fs=None, hidden=False, desc=None):
        o = [f"\tcolumn {cname}" if cname.islower() and " " not in cname else f"\tcolumn '{cname}'"]
        if desc:
            o.insert(0, f"\t/// {desc}")
        o += [f"\t\tdataType: {dtype}"]
        if hidden:
            o += ["\t\tisHidden"]
        if fs:
            o += [f"\t\tformatString: {fs}"]
        o += [f"\t\tlineageTag: {tag()}", f"\t\tsummarizeBy: {summarize}", f"\t\tsourceColumn: {cname}", ""]
        return o

    for c in text_cols:
        L += col(c, "string")
    L += col("ano", "int64", "none", "0")
    if monthly:
        L += col("mes", "string")
        L += col("Data", "dateTime", "none", "yyyy-mm-dd", hidden=True,
                 desc="Primeiro dia do mês, usado para ligar ao Calendário.")
    L += col(value, "double", "sum" if agg == "SUM" else "average", fmt)
    L += col("create_date", "dateTime", "none", "yyyy-mm-dd", hidden=True)
    L += col("update_date", "dateTime", "none", "yyyy-mm-dd", hidden=True)
    L += col("GeoKey" if geo is MUN else "NutsIIKey", "string", hidden=True)
    if geo is MUN:
        L += col("NutsIIKey", "string", hidden=True)

    # Power Query
    trims = ", ".join(f'{{"{c}", Text.Trim, type text}}' for c in text_cols)
    m = ["let",
         f'    Origem = Fonte{{[Schema="public", Item="{src}"]}}[Data],',
         f"    Texto = Table.TransformColumns(Origem, {{{trims}}}),"]
    if monthly:
        m += ['    Mes = Table.TransformColumns(Texto, {{"mes", Text.Trim, type text}}),',
              '    ComData = Table.AddColumn(Mes, "Data", each #date([ano], '
              'Number.FromText([mes]), 1), type date),']
        base = "ComData"
    else:
        base = "Texto"
    keyexpr = ' & "|" & '.join(f"[{c}]" for c in geo)
    m += [f'    GeoKey = Table.AddColumn({base}, "{"GeoKey" if geo is MUN else "NutsIIKey"}", '
          f"each {keyexpr}, type text),"]
    if geo is MUN:
        m += ['    NutsII = Table.AddColumn(GeoKey, "NutsIIKey", each [nuts_i] & "|" & [nuts_ii], type text)']
        m += ["in", "    NutsII"]
    else:
        m += ["in", "    GeoKey"]
    L += [f"\tpartition '{name}' = m", "\t\tmode: import", "\t\tsource ="]
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


def calc_table(name, dax, cols, desc=None, data_category=None):
    L = []
    if desc:
        L += [f"/// {desc}"]
    L += [f"table '{name}'", f"\tlineageTag: {tag()}"]
    if data_category:
        L += [f"\tdataCategory: {data_category}"]
    L += [""]
    for cname, dtype, summarize, hidden, key in cols:
        L += [f"\tcolumn '{cname}'", f"\t\tdataType: {dtype}"]
        if hidden:
            L += ["\t\tisHidden"]
        if key:
            L += ["\t\tisKey"]
        L += [f"\t\tlineageTag: {tag()}", f"\t\tsummarizeBy: {summarize}",
              f"\t\tsourceColumn: [{cname}]", ""]
    L += [f"\tpartition '{name}' = calculated", "\t\tmode: import", "\t\tsource ="]
    L += ["\t\t\t\t" + line for line in dax.split("\n")]
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
VAR Inicio = DATE(YEAR(MINX(Datas, [Data])), 1, 1)
VAR Fim = EOMONTH(MAXX(Datas, [Data]), 0)
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
put(f"{DEF}/tables/Geografia.tmdl", calc_table(
    "Geografia", f"DISTINCT(\n    {union(MUN_T, geo_cols)}\n)",
    [("GeoKey", "string", "none", True, True), ("NUTS I", "string", "none", False, False),
     ("NUTS II", "string", "none", False, False), ("NUTS III", "string", "none", False, False),
     ("Distrito", "string", "none", False, False), ("Município", "string", "none", False, False),
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
    "Dimensão NUTS II conforme aos indicadores municipais e aos indicadores só com NUTS I/II."))

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

# ------------------------------------------------------------------ measure table
def m(name, expr, fmt, desc=None):
    L = []
    if desc:
        L += [f"\t/// {desc}"]
    lines = expr.split("\n")
    if len(lines) == 1:
        L += [f"\tmeasure '{name}' = {expr}"]
    else:
        L += [f"\tmeasure '{name}' ="]
        L += ["\t\t\t" + ln.strip() for ln in lines]
    L += [f"\t\tformatString: {fmt}", f"\t\tlineageTag: {tag()}", ""]
    return L

T9877, T9876 = tname(IND[7]), tname(IND[6])
T9183, T9930 = tname(IND[1]), tname(IND[10])
T10735, T10736 = tname(IND[11]), tname(IND[12])
T9874, T9873 = tname(IND[5]), tname(IND[4])

ML = ["/// Medidas derivadas e comparações entre indicadores.", "table '_Medidas'",
      f"\tlineageTag: {tag()}", ""]
ML += m("Estada média ponderada (tipo)",
        f"DIVIDE([Dormidas (tipo)], [Hóspedes (tipo)])", "#,0.00",
        "Dormidas / hóspedes do mesmo grão. Preferir a esta medida a média simples do INE.")
ML += m("Estada média ponderada (residência)",
        f"DIVIDE([Dormidas (residência)], [Hóspedes (residência)])", "#,0.00",
        "Dormidas / hóspedes por país de residência.")
ML += m("Estada média mensal ponderada (segmento)",
        f"DIVIDE([Dormidas mensais (segmento)], [Hóspedes mensais (segmento)])", "#,0.00")
ML += m("Quartos por estabelecimento", "DIVIDE([Quartos], [Estabelecimentos])", "#,0.00")
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
ML += m("Dormidas por km²", f"DIVIDE([Dormidas (tipo)], [Superfície (km²)])", "#,0.00",
        "Intensidade turística: dormidas anuais por quilómetro quadrado.")
ML += m("Hóspedes por km²", f"DIVIDE([Hóspedes (tipo)], [Superfície (km²)])", "#,0.00")
ML += ["\tcolumn '_'", "\t\tdataType: string", "\t\tisHidden",
       f"\t\tlineageTag: {tag()}", "\t\tsummarizeBy: none", "\t\tsourceColumn: [_]", ""]
ML += [f"\tpartition '_Medidas' = calculated", "\t\tmode: import", "\t\tsource =",
       '\t\t\t\tROW("_", BLANK())', ""]
put(f"{DEF}/tables/_Medidas.tmdl", "\n".join(ML) + "\n")

# ------------------------------------------------------------------ relationships
rels = []
def rel(ft, fc, tt, tc, active=True):
    r = [f"relationship {tag()}"]
    if not active:
        r.append("\tisActive: false")
    r += [f"\tfromColumn: '{ft}'.'{fc}'", f"\ttoColumn: '{tt}'.'{tc}'", ""]
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
put(f"{DEF}/relationships.tmdl", "\n".join(rels))

# ------------------------------------------------------------------ expressions
put(f"{DEF}/expressions.tmdl", f"""/// Servidor PostgreSQL, no formato anfitriao:porta (PISTA_DB_HOSTNAME:PISTA_DB_PORTNUMBER).
expression Servidor = "localhost:5432" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
\tlineageTag: {tag()}
\tqueryGroup: 'Parâmetros'

\tannotation PBI_NavigationStepName = Navigation

\tannotation PBI_ResultType = Text

/// Nome da base de dados (PISTA_DB_NAME).
expression BaseDados = "pistadigital" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
\tlineageTag: {tag()}
\tqueryGroup: 'Parâmetros'

\tannotation PBI_NavigationStepName = Navigation

\tannotation PBI_ResultType = Text

/// Ligação partilhada. As credenciais são pedidas pelo Power BI e nunca ficam no ficheiro.
expression Fonte = PostgreSQL.Database(Servidor, BaseDados)
\tlineageTag: {tag()}
\tqueryGroup: 'Parâmetros'

\tannotation PBI_ResultType = Table
""")

# ------------------------------------------------------------------ model + culture
refs = "\n".join(f"ref table '{tname(i)}'" for i in IND)
put(f"{DEF}/model.tmdl", f"""model Model
\tculture: pt-PT
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tsourceQueryCulture: pt-PT

\tannotation PBI_QueryOrder = [{", ".join(f'"{tname(i)}"' for i in IND)}]

queryGroup 'Parâmetros'

{refs}
ref table 'Ano'
ref table 'Calendário'
ref table 'Geografia'
ref table 'Região NUTS II'
ref table 'Tipo de alojamento'
ref table 'Residência'
ref table 'Segmento de alojamento'
ref table '_Medidas'

ref cultureInfo pt-PT
""")
put(f"{DEF}/cultures/pt-PT.tmdl", "cultureInfo pt-PT\n\n\tlinguisticMetadata = {\"Version\": \"1.0.0\", \"Language\": \"pt-PT\"}\n\t\tcontentType: json\n")
put(f"{DEF}/database.tmdl", "database\n\tcompatibilityLevel: 1567\n")
if os.path.exists(f"{DEF}/tables/Exemplo.tmdl"):
    os.remove(f"{DEF}/tables/Exemplo.tmdl")
print("tables:", len(os.listdir(f"{DEF}/tables")), "relationships:", len(rels))
