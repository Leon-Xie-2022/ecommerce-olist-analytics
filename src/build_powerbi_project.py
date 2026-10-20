"""Generate the Power BI project (PBIP: TMDL semantic model + PBIR report) in powerbi/.

The model reads the Parquet files written by src/export_powerbi.py. The DataFolder parameter is set to
this machine's data/processed/powerbi/ folder, so rerun this script after cloning the repo elsewhere.

Once the project has been opened and saved in Power BI Desktop, Desktop becomes the source of truth;
rerunning this script overwrites the model and report definitions.

Run:  python src/build_powerbi_project.py   then open powerbi/OlistDashboard.pbip in Power BI Desktop
"""
import json
import shutil
import uuid

from config import PROCESSED_DIR, PROJECT_ROOT

NAME = "OlistDashboard"
PBI_DIR = PROJECT_ROOT / "powerbi"
MODEL_DIR = PBI_DIR / f"{NAME}.SemanticModel"
REPORT_DIR = PBI_DIR / f"{NAME}.Report"
DATA_FOLDER = str(PROCESSED_DIR / "powerbi") + "\\"
BASE_THEME = "CY24SU10"
MEASURE_TABLE = "_Measures"  # "Measures" is a reserved table name in Power BI

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"

# --------------------------------------------------------------------------------------------
# Semantic model
# --------------------------------------------------------------------------------------------

# Power Query type -> TMDL dataType
TYPES = {"text": "string", "int": "int64", "num": "double", "bool": "boolean", "date": "dateTime"}

# table -> (filter step or None, [(column, type, formatString or None, hidden)])
TABLES = {
    "fct_orders": ("each [is_complete_month]", [
        ("order_id", "text", None, True),
        ("customer_unique_id", "text", None, True),
        ("customer_state", "text", None, False),
        ("order_status", "text", None, False),
        ("is_valid", "bool", None, False),
        ("purchase_date", "date", "yyyy-mm-dd", False),
        ("n_items", "int", "0", False),
        ("product_value", "num", "#,0.00", False),
        ("freight_value", "num", "#,0.00", False),
        ("payment_value", "num", "#,0.00", False),
        ("main_payment_type", "text", None, False),
        ("max_installments", "int", "0", False),
        ("is_delivered", "bool", None, False),
        ("delivery_days", "int", "0", False),
        ("promised_days", "int", "0", False),
        ("days_late", "int", "0", False),
        ("review_score", "int", "0", False),
        ("is_late", "bool", None, False),
        ("delivery_bucket", "text", None, False),
        ("order_type", "text", None, False),
        ("is_return_order", "bool", None, False),
    ]),
    "fct_order_items": ("each [is_complete_month]", [
        ("order_id", "text", None, True),
        ("seller_id", "text", None, True),
        ("category", "text", None, False),
        ("seller_state", "text", None, False),
        ("is_valid", "bool", None, False),
        ("price", "num", "#,0.00", False),
        ("freight_value", "num", "#,0.00", False),
    ]),
    "dim_customer": (
        "each [cohort_month] >= #date(2017, 1, 1) and [cohort_month] <= #date(2018, 8, 1)", [
            ("customer_unique_id", "text", None, True),
            ("cohort_month", "date", "yyyy-mm", False),
            ("n_orders", "int", "0", False),
            ("n_purchase_days", "int", "0", False),
            ("first_order_state", "text", None, False),
            ("is_repeat_customer", "bool", None, False),
        ]),
    "dim_date": ("each [is_complete_month]", [
        ("date", "date", "yyyy-mm-dd", False),
        ("month_start", "date", "yyyy-mm", False),
        ("year_month", "text", None, False),
        ("year", "int", "0", False),
        ("month", "int", "0", False),
    ]),
    "cohort_retention": (None, [
        ("cohort", "text", None, False),
        ("cohort_size", "int", "#,0", False),
        ("months_observed", "int", "0", False),
        ("repeat_1m_pct", "num", "0.00", False),
        ("repeat_3m_pct", "num", "0.00", False),
        ("repeat_6m_pct", "num", "0.00", False),
        ("repeat_12m_pct", "num", "0.00", False),
    ]),
}

RELATIONSHIPS = [
    ("fct_orders", "purchase_date", "dim_date", "date"),
    ("fct_order_items", "order_id", "fct_orders", "order_id"),
    ("fct_orders", "customer_unique_id", "dim_customer", "customer_unique_id"),
]

# name -> (DAX, formatString, description). Definitions match docs/metric_definitions.md.
MEASURES = {
    "Valid Orders": (
        "CALCULATE(COUNTROWS(fct_orders), fct_orders[is_valid] = TRUE())",
        "#,0", "Orders excluding canceled and unavailable"),
    "Product Value": (
        "CALCULATE(SUM(fct_orders[product_value]), fct_orders[is_valid] = TRUE())",
        "#,0", "Sum of item prices of valid orders (BRL); not company revenue"),
    "Freight Value": (
        "CALCULATE(SUM(fct_orders[freight_value]), fct_orders[is_valid] = TRUE())",
        "#,0", "Freight charged on valid orders (BRL)"),
    "AOV": (
        "DIVIDE(\n    [Product Value],\n"
        "    CALCULATE(COUNTROWS(fct_orders), fct_orders[is_valid] = TRUE(), fct_orders[n_items] > 0)\n)",
        "#,0.00", "Average product value per valid order with items (BRL)"),
    "Product Value MoM %": (
        "VAR CurrentValue = [Product Value]\n"
        "VAR PreviousValue = CALCULATE([Product Value], DATEADD(dim_date[date], -1, MONTH))\n"
        "RETURN\n    IF(NOT ISBLANK(PreviousValue), DIVIDE(CurrentValue - PreviousValue, PreviousValue))",
        "0.0%", "Change in product value vs the previous month"),
    "Delivered Orders": (
        "CALCULATE(COUNTROWS(fct_orders), fct_orders[is_delivered] = TRUE())",
        "#,0", "Status delivered and a recorded delivery date"),
    "Late Orders": (
        "CALCULATE(COUNTROWS(fct_orders), fct_orders[is_late] = TRUE())",
        "#,0", "Delivered after the estimated date (calendar days)"),
    "Late Rate": (
        "DIVIDE([Late Orders], [Delivered Orders])",
        "0.0%", "Late orders / delivered orders"),
    "Avg Delivery Days": (
        "CALCULATE(AVERAGE(fct_orders[delivery_days]), fct_orders[is_delivered] = TRUE())",
        "0.0", "Days from purchase to delivery"),
    "Avg Review Score": (
        "CALCULATE(AVERAGE(fct_orders[review_score]), fct_orders[is_valid] = TRUE())",
        "0.00", "Average 1-5 review score of valid reviewed orders"),
    "Avg Review Score (Delivered)": (
        "CALCULATE(AVERAGE(fct_orders[review_score]), fct_orders[is_delivered] = TRUE())",
        "0.00", "Average review score of delivered orders; used with delivery outcome"),
    # IN {1, 2} rather than <= 2: in DAX, BLANK() <= 2 is TRUE, which would count unreviewed orders.
    "Low Review Share": (
        "DIVIDE(\n"
        "    CALCULATE(COUNTROWS(fct_orders), fct_orders[is_valid] = TRUE(), fct_orders[review_score] IN {1, 2}),\n"
        "    CALCULATE(COUNT(fct_orders[review_score]), fct_orders[is_valid] = TRUE())\n)",
        "0.0%", "Share of 1-2 star reviews among reviewed valid orders"),
    "Low Review Share (Delivered)": (
        "DIVIDE(\n"
        "    CALCULATE(COUNTROWS(fct_orders), fct_orders[is_delivered] = TRUE(), fct_orders[review_score] IN {1, 2}),\n"
        "    CALCULATE(COUNT(fct_orders[review_score]), fct_orders[is_delivered] = TRUE())\n)",
        "0.0%", "Share of 1-2 star reviews among reviewed delivered orders"),
    "Customers": (
        "CALCULATE(DISTINCTCOUNT(fct_orders[customer_unique_id]), fct_orders[is_valid] = TRUE())",
        "#,0", "Distinct people (customer_unique_id) with a valid order"),
    "Returning Order Share": (
        "DIVIDE(\n"
        "    CALCULATE(COUNTROWS(fct_orders), fct_orders[is_return_order] = TRUE()),\n"
        "    [Valid Orders]\n)",
        "0.0%", "Valid orders placed on a later day than the customer's first purchase"),
    "Repeat Customer Share": (
        "DIVIDE(\n"
        "    CALCULATE(COUNTROWS(dim_customer), dim_customer[is_repeat_customer] = TRUE()),\n"
        "    COUNTROWS(dim_customer)\n)",
        "0.0%", "Customers (cohorts 2017-01..2018-08) who bought on 2+ different days"),
    "Item Product Value": (
        "CALCULATE(SUM(fct_order_items[price]), fct_order_items[is_valid] = TRUE())",
        "#,0", "Item-level product value, for category and seller analysis"),
    "Category Share": (
        "DIVIDE([Item Product Value], CALCULATE([Item Product Value], ALL(fct_order_items[category])))",
        "0.0%", "Category product value / all categories"),
}


def tmdl_column(name, ptype, fmt, hidden, is_key=False):
    lines = [f"\tcolumn {name}", f"\t\tdataType: {TYPES[ptype]}"]
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    if hidden:
        lines.append("\t\tisHidden")
    if is_key:
        lines.append("\t\tisKey")
    lines += ["\t\tsummarizeBy: none", f"\t\tsourceColumn: {name}"]
    if ptype == "date":
        lines += ["", "\t\tannotation UnderlyingDateTimeDataType = Date"]
    return "\n".join(lines) + "\n"


def m_type(ptype):
    return {"text": "type text", "int": "Int64.Type", "num": "type number",
            "bool": "type logical", "date": "type date"}[ptype]


def tmdl_table(table, row_filter, columns):
    is_date_table = table == "dim_date"
    out = [f"table {table}"]
    if is_date_table:
        out.append("\tdataCategory: Time")
    out.append("")
    for name, ptype, fmt, hidden in columns:
        out.append(tmdl_column(name, ptype, fmt, hidden, is_key=is_date_table and name == "date"))

    names = ", ".join(f'"{c[0]}"' for c in columns)
    types = ", ".join(f'{{"{c[0]}", {m_type(c[1])}}}' for c in columns)
    steps = [
        f'Source = Parquet.Document(File.Contents(DataFolder & "{table}.parquet"))',
    ]
    last = "Source"
    if row_filter:
        steps.append(f"Filtered = Table.SelectRows(Source, {row_filter})")
        last = "Filtered"
    steps.append(f"Selected = Table.SelectColumns({last}, {{{names}}})")
    steps.append(f"Typed = Table.TransformColumnTypes(Selected, {{{types}}})")
    m = "\n".join(
        ["\t\t\t\tlet"]
        + [f"\t\t\t\t    {s}," for s in steps[:-1]]
        + [f"\t\t\t\t    {steps[-1]}", "\t\t\t\tin", "\t\t\t\t    Typed"]
    )
    out += [f"\tpartition {table} = m", "\t\tmode: import", "\t\tsource =", m, ""]
    return "\n".join(out) + "\n"


def tmdl_measures():
    out = [f"table {MEASURE_TABLE}", ""]
    for name, (dax, fmt, description) in MEASURES.items():
        out.append(f"\t/// {description}")
        if "\n" in dax:
            body = "\n".join(f"\t\t\t{line}" for line in dax.split("\n"))
            out.append(f"\tmeasure '{name}' = ```\n{body}\n\t\t\t```")
        else:
            out.append(f"\tmeasure '{name}' = {dax}")
        out.append(f"\t\tformatString: {fmt}")
        out.append("")
    out += [
        "\tcolumn Value",
        "\t\tisHidden",
        "\t\tformatString: 0",
        "\t\tsummarizeBy: none",
        "\t\tisNameInferred",
        "\t\tsourceColumn: [Value]",
        "",
        f"\tpartition {MEASURE_TABLE} = calculated",
        "\t\tmode: import",
        "\t\tsource = {0}",
        "",
    ]
    return "\n".join(out) + "\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path, obj):
    write(path, json.dumps(obj, indent=2) + "\n")


def platform(item_type):
    return {
        "$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": item_type, "displayName": NAME},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid5(uuid.NAMESPACE_URL, NAME + item_type))},
    }


def build_model():
    d = MODEL_DIR / "definition"
    if d.exists():
        shutil.rmtree(d)
    write_json(MODEL_DIR / "definition.pbism", {"version": "4.1", "settings": {}})
    write_json(MODEL_DIR / ".platform", platform("SemanticModel"))
    write(d / "database.tmdl", "database\n\tcompatibilityLevel: 1567\n")
    refs = "\n".join(f"ref table {t}" for t in [*TABLES, MEASURE_TABLE])
    query_order = json.dumps(["DataFolder", *TABLES])
    write(d / "model.tmdl",
          "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
          "\tdiscourageImplicitMeasures\n\tsourceQueryCulture: en-US\n\tdataAccessOptions\n"
          "\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
          "annotation __PBI_TimeIntelligenceEnabled = 0\n\n"
          f"annotation PBI_QueryOrder = {query_order}\n\n{refs}\n")
    write(d / "expressions.tmdl",
          f'expression DataFolder = "{DATA_FOLDER}" '
          'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n\n'
          "\tannotation PBI_ResultType = Text\n")
    rels = []
    for from_t, from_c, to_t, to_c in RELATIONSHIPS:
        rel_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{from_t}.{from_c}->{to_t}.{to_c}")
        rels.append(f"relationship {rel_id}\n\tfromColumn: {from_t}.{from_c}\n\ttoColumn: {to_t}.{to_c}\n")
    write(d / "relationships.tmdl", "\n".join(rels))
    for table, (row_filter, columns) in TABLES.items():
        write(d / "tables" / f"{table}.tmdl", tmdl_table(table, row_filter, columns))
    write(d / "tables" / f"{MEASURE_TABLE}.tmdl", tmdl_measures())


# --------------------------------------------------------------------------------------------
# Report (PBIR)
# --------------------------------------------------------------------------------------------

def lit(value):
    return {"expr": {"Literal": {"Value": value}}}


def column(table, col):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}}


def measure(name):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": MEASURE_TABLE}}, "Property": name}}


def projection(field, display=None):
    kind = "Column" if "Column" in field else "Measure"
    entity = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    proj = {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}
    if display:
        proj["displayName"] = display
    return proj


CHARTS = {"lineChart", "barChart", "columnChart", "clusteredBarChart"}

# Card number formatting: (display units, decimals). Unlisted cards use the measure's format string.
CARD_FORMAT = {
    "Valid Orders": ("1D", None),
    "Delivered Orders": ("1D", None),
    "Customers": ("1D", None),
    "Product Value": ("1000000D", "2L"),
}


class Page:
    def __init__(self, name, display_name):
        self.name, self.display_name, self.visuals = name, display_name, []

    def add(self, visual_type, x, y, w, h, roles=None, sort=None, title=None, objects=None,
            data_labels=False):
        """roles: {role: [field or (field, display name)]}. Charts get axis titles hidden,
        because the visual title already says what is plotted."""
        n = len(self.visuals)
        visual = {"visualType": visual_type}
        if roles:
            query = {"queryState": {
                role: {"projections": [projection(*f) if isinstance(f, tuple) else projection(f)
                                       for f in fields]}
                for role, fields in roles.items()}}
            if sort:
                field, direction = sort
                query["sortDefinition"] = {"sort": [{"field": field, "direction": direction}],
                                           "isDefaultSort": False}
            visual["query"] = query
        objects = dict(objects or {})
        if visual_type in CHARTS:
            objects["categoryAxis"] = [{"properties": {"showAxisTitle": lit("false")}}]
            objects["valueAxis"] = [{"properties": {"showAxisTitle": lit("false")}}]
        if data_labels:
            objects["labels"] = [{"properties": {"show": lit("true")}}]
        if objects:
            visual["objects"] = objects
        if title:
            visual["visualContainerObjects"] = {
                "title": [{"properties": {"show": lit("true"), "text": lit(f"'{title}'"),
                                          "fontSize": lit("12D")}}]}
        visual["drillFilterOtherVisuals"] = True
        self.visuals.append({
            "$schema": f"{SCHEMA}/item/report/definition/visualContainer/1.5.0/schema.json",
            "name": f"{self.name}_v{n:02d}",
            "position": {"x": x, "y": y, "z": n * 1000, "height": h, "width": w, "tabOrder": n * 1000},
            "visual": visual,
        })

    def title(self, text, subtitle):
        runs = [{"textRuns": [{"value": text, "textStyle": {"fontWeight": "bold", "fontSize": "20pt"}}]},
                {"textRuns": [{"value": subtitle, "textStyle": {"fontSize": "10pt", "color": "#605E5C"}}]}]
        self.add("textbox", 24, 16, 980, 64, objects={"general": [{"properties": {"paragraphs": runs}}]})

    def cards(self, names, y=96, x0=24, width=1232):
        gap = 16
        w = (width - gap * (len(names) - 1)) // len(names)
        for i, name in enumerate(names):
            labels = {"fontSize": lit("28D")}
            units, decimals = CARD_FORMAT.get(name, (None, None))
            if units:
                labels["labelDisplayUnits"] = lit(units)
            if decimals:
                labels["labelPrecision"] = lit(decimals)
            self.add("card", x0 + i * (w + gap), y, w, 112, roles={"Values": [measure(name)]},
                     objects={"labels": [{"properties": labels}],
                              "categoryLabels": [{"properties": {"fontSize": lit("12D")}}]})

    def state_slicer(self):
        self.add("slicer", 1036, 12, 220, 76, roles={"Values": [column("fct_orders", "customer_state")]},
                 objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}],
                          "header": [{"properties": {"show": lit("false")}}]},
                 title="Customer state")


SUBTITLE = "Olist public data (Brazil), valid orders, complete months 2017-01 to 2018-08. Values in BRL."
TOP, BOTTOM = 224, 704  # chart area


def build_pages():
    month = column("dim_date", "year_month")
    half = (BOTTOM - TOP - 16) // 2

    overview = Page("overview", "Overview")
    overview.title("Orders & product value", SUBTITLE)
    overview.state_slicer()
    overview.cards(["Valid Orders", "Product Value", "AOV", "Late Rate", "Avg Review Score"])
    overview.add("lineChart", 24, TOP, 760, BOTTOM - TOP,
                 roles={"Category": [month], "Y": [measure("Product Value")]},
                 sort=(month, "Ascending"), title="Product value by purchase month (BRL)")
    overview.add("barChart", 800, TOP, 456, BOTTOM - TOP,
                 roles={"Category": [column("fct_order_items", "category")],
                        "Y": [measure("Item Product Value")]},
                 sort=(measure("Item Product Value"), "Descending"),
                 title="Product value by category (BRL)")

    delivery = Page("delivery", "Delivery & Reviews")
    delivery.title("Delivery performance & reviews", SUBTITLE + " Late = delivered after the estimated date.")
    delivery.state_slicer()
    delivery.cards(["Delivered Orders", "Avg Delivery Days", "Late Rate", "Low Review Share"])
    delivery.add("lineChart", 24, TOP, 600, half,
                 roles={"Category": [month], "Y": [measure("Late Rate")]},
                 sort=(month, "Ascending"), title="Late rate by purchase month")
    bucket = column("fct_orders", "delivery_bucket")
    delivery.add("columnChart", 24, TOP + half + 16, 600, half,
                 roles={"Category": [bucket], "Y": [measure("Avg Review Score (Delivered)")]},
                 sort=(bucket, "Ascending"), data_labels=True,
                 title="Avg review score by delivery outcome (association, not causation)")
    delivery.add("barChart", 640, TOP, 616, half,
                 roles={"Category": [column("fct_orders", "customer_state")], "Y": [measure("Late Rate")]},
                 sort=(measure("Late Rate"), "Descending"), title="Late rate by customer state")
    order_type = column("fct_orders", "order_type")
    delivery.add("clusteredBarChart", 640, TOP + half + 16, 616, half,  # side by side, not stacked
                 roles={"Category": [order_type],
                        "Y": [measure("Low Review Share (Delivered)"), measure("Late Rate")]},
                 sort=(order_type, "Ascending"), data_labels=True,
                 title="Split orders: rarely late, but far more 1-2 star reviews")

    customers = Page("customers", "Customers")
    customers.title("Customers & repeat purchase",
                    SUBTITLE + " Repeat = bought again on a later calendar day.")
    customers.cards(["Customers", "Returning Order Share", "Repeat Customer Share"])
    customers.add("lineChart", 24, TOP, 600, half,
                  roles={"Category": [month], "Y": [measure("Returning Order Share")]},
                  sort=(month, "Ascending"), title="Share of orders from returning customers")
    pay = column("fct_orders", "main_payment_type")
    customers.add("barChart", 24, TOP + half + 16, 600, half,
                  roles={"Category": [pay], "Y": [measure("Valid Orders")]},
                  sort=(measure("Valid Orders"), "Descending"), data_labels=True,
                  title="Valid orders by main payment type")
    cohort = "cohort_retention"
    headers = [("cohort", "Cohort"), ("cohort_size", "Customers"), ("repeat_1m_pct", "1 month %"),
               ("repeat_3m_pct", "3 months %"), ("repeat_6m_pct", "6 months %"),
               ("repeat_12m_pct", "12 months %")]
    customers.add("tableEx", 640, TOP, 616, BOTTOM - TOP,
                  roles={"Values": [(column(cohort, c), label) for c, label in headers]},
                  sort=(column(cohort, "cohort"), "Ascending"),
                  title="Cohort repeat rate: % who bought again within N months (blank = not yet observable)")
    return [overview, delivery, customers]


def build_report():
    d = REPORT_DIR / "definition"
    if d.exists():
        shutil.rmtree(d)
    write_json(REPORT_DIR / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}},
    })
    write_json(REPORT_DIR / ".platform", platform("Report"))
    theme = REPORT_DIR / "StaticResources" / "SharedResources" / "BaseThemes" / f"{BASE_THEME}.json"
    if not theme.exists():
        raise SystemExit(f"Base theme missing: {theme}")
    write_json(d / "version.json", {
        "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })
    write_json(d / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/1.2.0/schema.json",
        "themeCollection": {"baseTheme": {"name": BASE_THEME, "reportVersionAtImport": "5.61",
                                          "type": "SharedResources"}},
        "layoutOptimization": "None",
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources",
                              "items": [{"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json",
                                         "type": "BaseTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True,
                     "useDefaultAggregateDisplayName": True},
    })
    pages = build_pages()
    write_json(d / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.name for p in pages],
        "activePageName": pages[0].name,
    })
    for p in pages:
        write_json(d / "pages" / p.name / "page.json", {
            "$schema": f"{SCHEMA}/item/report/definition/page/1.3.0/schema.json",
            "name": p.name, "displayName": p.display_name, "displayOption": "FitToPage",
            "height": 720, "width": 1280,
        })
        for v in p.visuals:
            write_json(d / "pages" / p.name / "visuals" / v["name"] / "visual.json", v)


def main():
    build_model()
    build_report()
    write_json(PBI_DIR / f"{NAME}.pbip", {
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    print(f"wrote {PBI_DIR / (NAME + '.pbip')}")
    print(f"DataFolder = {DATA_FOLDER}")


if __name__ == "__main__":
    main()
