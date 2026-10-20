"""Check raw Olist tables, write clean Parquet files and a data-quality report.

Raw files are never modified. Rows are not dropped here: problems are either fixed when the fix is
unambiguous (column typos, missing category translations) or flagged so each metric can decide how
to treat them. Hard failures (duplicate keys, orphan foreign keys) stop the script.

Run: python src/clean.py
"""
import sys
from datetime import date

import pandas as pd

from config import PROCESSED_DIR, RAW_DIR, RAW_FILES, REPORTS_DIR

ID_COLS = ["order_id", "customer_id", "customer_unique_id", "product_id", "seller_id", "review_id"]
ZIP_COLS = ["customer_zip_code_prefix", "seller_zip_code_prefix"]

DATE_COLS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
    "reviews": ["review_creation_date", "review_answer_timestamp"],
}

# Two categories in products have no row in the translation file; translated by hand.
MISSING_TRANSLATIONS = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_and_food_preparers",
}


def load_raw(name):
    """Read one raw CSV; IDs and zip prefixes stay text so leading zeros are kept."""
    path = RAW_DIR / RAW_FILES[name]
    header = pd.read_csv(path, nrows=0).columns
    dtype = {c: "string" for c in header if c in ID_COLS + ZIP_COLS}
    return pd.read_csv(path, dtype=dtype, parse_dates=DATE_COLS.get(name, []))


class QualityLog:
    """Collects check results for the report. `hard=True` checks must pass or the script stops."""

    def __init__(self):
        self.rows = []

    def add(self, table, check, n_bad, action, hard=False):
        status = "PASS" if n_bad == 0 else ("FAIL" if hard else "WARN")
        self.rows.append(
            {"table": table, "check": check, "rows": int(n_bad), "status": status, "action": action}
        )

    def failures(self):
        return [r for r in self.rows if r["status"] == "FAIL"]


def n_duplicate_keys(df, cols):
    return int(df.duplicated(subset=cols).sum())


def n_orphans(child, parent, col):
    """Child rows whose foreign key has no match in the parent table."""
    return int((~child[col].isin(parent[col])).sum())


def run_checks(t, log):
    orders, items, pays, reviews = t["orders"], t["order_items"], t["payments"], t["reviews"]

    # Primary keys
    for name, cols in [
        ("orders", ["order_id"]),
        ("customers", ["customer_id"]),
        ("products", ["product_id"]),
        ("sellers", ["seller_id"]),
        ("order_items", ["order_id", "order_item_id"]),
        ("payments", ["order_id", "payment_sequential"]),
        ("reviews", ["review_id", "order_id"]),
        ("category_translation", ["product_category_name"]),
    ]:
        log.add(name, f"duplicate primary key ({', '.join(cols)})",
                n_duplicate_keys(t[name], cols), "stop if any", hard=True)

    # Foreign keys
    for child, parent, col in [
        ("orders", "customers", "customer_id"),
        ("order_items", "orders", "order_id"),
        ("order_items", "products", "product_id"),
        ("order_items", "sellers", "seller_id"),
        ("payments", "orders", "order_id"),
        ("reviews", "orders", "order_id"),
    ]:
        log.add(child, f"orphan {col} (not in {parent})",
                n_orphans(t[child], t[parent], col), "stop if any", hard=True)

    # Coverage: orders without child rows
    log.add("orders", "order has no items", n_orphans(orders, items, "order_id"),
            "keep; excluded from value metrics automatically (no item value)")
    log.add("orders", "order has no payment", n_orphans(orders, pays, "order_id"),
            "keep; payment metrics treat as missing")
    log.add("orders", "order has no review", n_orphans(orders, reviews, "order_id"),
            "keep; review metrics use reviewed orders only")

    # Multiplicity that causes join fan-out
    log.add("reviews", "order has 2+ reviews", int((reviews["order_id"].value_counts() > 1).sum()),
            "reduce to one review per order before joining (latest review)")
    log.add("reviews", "review_id shared by 2+ orders",
            int((reviews["review_id"].value_counts() > 1).sum()),
            "keep; review_id alone is not a key")
    log.add("payments", "order has 2+ payment rows", int((pays["order_id"].value_counts() > 1).sum()),
            "sum to one row per order before joining")

    # Status vs dates
    delivered = orders["order_status"] == "delivered"
    log.add("orders", "status delivered but no delivery date",
            (delivered & orders["order_delivered_customer_date"].isna()).sum(),
            "flag; excluded from delivery-time metrics")
    log.add("orders", "status canceled but has delivery date",
            ((orders["order_status"] == "canceled") & orders["order_delivered_customer_date"].notna()).sum(),
            "flag; not counted as delivered")

    # Date order
    for later, earlier, action in [
        ("order_approved_at", "order_purchase_timestamp", "report only"),
        ("order_delivered_carrier_date", "order_approved_at",
         "flag_carrier_before_approval; likely recording lag, carrier date not used in metrics"),
        ("order_delivered_carrier_date", "order_purchase_timestamp",
         "keep; carrier date not used in metrics"),
        ("order_delivered_customer_date", "order_delivered_carrier_date",
         "keep; delivery time is measured from purchase, not from hand-over"),
        ("order_delivered_customer_date", "order_purchase_timestamp", "report only"),
    ]:
        log.add("orders", f"{later} < {earlier}", (orders[later] < orders[earlier]).sum(), action)

    # Values
    log.add("order_items", "price <= 0", (items["price"] <= 0).sum(), "report only")
    log.add("order_items", "freight_value = 0", (items["freight_value"] == 0).sum(),
            "keep; free shipping is plausible")
    log.add("payments", "payment_value = 0", (pays["payment_value"] == 0).sum(),
            "keep; mostly vouchers and not_defined rows, no effect on sums")
    log.add("payments", "payment_type = not_defined", (pays["payment_type"] == "not_defined").sum(),
            "keep; value 0")

    # Item value vs payment value per order
    item_total = items.groupby("order_id")[["price", "freight_value"]].sum().sum(axis=1)
    pay_total = pays.groupby("order_id")["payment_value"].sum()
    both = pd.concat([item_total.rename("items"), pay_total.rename("pay")], axis=1, join="inner")
    diff = (both["pay"] - both["items"]).round(2)
    log.add("orders", "payment total differs from items price + freight by > 0.01",
            (diff.abs() > 0.01).sum(),
            "keep; product value and payment value reported as separate metrics")

    # Products
    products = t["products"]
    log.add("products", "missing category", products["product_category_name"].isna().sum(),
            "category_en = 'unknown'")
    untranslated = set(products["product_category_name"].dropna()) - set(
        t["category_translation"]["product_category_name"])
    log.add("products", "category without English translation", len(untranslated),
            "translated by hand in clean.py")
    log.add("products", "weight_g = 0 or missing",
            ((products["product_weight_g"] == 0) | products["product_weight_g"].isna()).sum(),
            "keep; dimensions not used in metrics")


def clean_orders(orders):
    out = orders.copy()
    out["purchase_month"] = out["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
    out["flag_delivered_no_date"] = (
        (out["order_status"] == "delivered") & out["order_delivered_customer_date"].isna()
    )
    out["flag_canceled_with_delivery"] = (
        (out["order_status"] == "canceled") & out["order_delivered_customer_date"].notna()
    )
    out["flag_carrier_before_approval"] = (
        out["order_delivered_carrier_date"] < out["order_approved_at"]
    )
    return out


def clean_products(products, translation):
    out = products.rename(columns={
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    })
    mapping = dict(zip(translation["product_category_name"],
                       translation["product_category_name_english"]))
    mapping.update(MISSING_TRANSLATIONS)
    out["product_category_name_english"] = (
        out["product_category_name"].map(mapping).fillna("unknown")
    )
    return out


def write_report(log, tables, clean_tables, path):
    lines = [
        "# Data quality report",
        "",
        f"Generated by `src/clean.py` on {date.today().isoformat()}. "
        "Raw files are not modified; clean Parquet files are written to `data/processed/`.",
        "",
        "PASS = no rows affected. WARN = rows affected, handled as described. "
        "FAIL = hard rule broken (script stops).",
        "",
        "## Row counts",
        "",
        "| Table | Raw rows | Clean rows |",
        "|---|---|---|",
    ]
    for name, df in clean_tables.items():
        lines.append(f"| {name} | {len(tables[name]):,} | {len(df):,} |")
    lines += [
        "",
        "## Checks",
        "",
        "| Table | Check | Rows | Status | Action |",
        "|---|---|---|---|---|",
    ]
    for r in log.rows:
        lines.append(f"| {r['table']} | {r['check']} | {r['rows']:,} | {r['status']} | {r['action']} |")

    orders = clean_tables["orders"]
    monthly = orders.groupby("purchase_month").size()
    lines += [
        "",
        "## Order status",
        "",
        "| Status | Orders |",
        "|---|---|",
    ]
    for status, n in orders["order_status"].value_counts().items():
        lines.append(f"| {status} | {n:,} |")
    lines += [
        "",
        "## Orders per purchase month",
        "",
        "Months with very few orders are partial or data-collection artefacts and are marked "
        "`incomplete` in the SQL metrics (see `docs/metric_definitions.md`).",
        "",
        "| Month | Orders |",
        "|---|---|",
    ]
    for month, n in monthly.items():
        lines.append(f"| {month:%Y-%m} | {n:,} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    names = ["orders", "order_items", "payments", "reviews", "customers", "products", "sellers",
             "category_translation"]
    tables = {name: load_raw(name) for name in names}

    log = QualityLog()
    run_checks(tables, log)

    clean_tables = {
        "orders": clean_orders(tables["orders"]),
        "order_items": tables["order_items"],
        "payments": tables["payments"],
        "reviews": tables["reviews"],
        "customers": tables["customers"],
        "products": clean_products(tables["products"], tables["category_translation"]),
        "sellers": tables["sellers"],
    }

    REPORTS_DIR.mkdir(exist_ok=True)
    write_report(log, tables, clean_tables, REPORTS_DIR / "data_quality_report.md")

    failures = log.failures()
    if failures:
        for r in failures:
            print(f"FAIL  {r['table']}: {r['check']} ({r['rows']} rows)")
        sys.exit("Hard checks failed; clean files not written.")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in clean_tables.items():
        df.to_parquet(PROCESSED_DIR / f"{name}.parquet", index=False)
        print(f"wrote {name}.parquet  ({len(df):,} rows)")
    n_warn = sum(r["status"] == "WARN" for r in log.rows)
    print(f"{len(log.rows)} checks: {len(log.rows) - n_warn} PASS, {n_warn} WARN, 0 FAIL")


if __name__ == "__main__":
    main()
