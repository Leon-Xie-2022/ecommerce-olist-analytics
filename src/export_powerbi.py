"""Export the mart tables and the cohort table to Parquet for the Power BI report.

Output: data/processed/powerbi/*.parquet (not committed). The Power BI project reads this folder
through its DataFolder parameter.

Run after src/build_db.py:  python src/export_powerbi.py
"""
import duckdb

from config import DB_PATH, PROCESSED_DIR, SQL_DIR

OUT_DIR = PROCESSED_DIR / "powerbi"
TABLES = ["fct_orders", "fct_order_items", "dim_customer", "dim_date"]
# Cohort repeat rates are computed in SQL (observation-window logic) and loaded as a ready table.
QUERIES = {"cohort_retention": SQL_DIR / "metrics" / "08_cohort_retention.sql"}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    for name in TABLES:
        path = (OUT_DIR / f"{name}.parquet").as_posix()
        con.execute(f"COPY {name} TO '{path}' (FORMAT parquet)")
        print(f"wrote {name}.parquet")
    for name, sql_file in QUERIES.items():
        query = sql_file.read_text(encoding="utf-8").strip().rstrip(";")
        path = (OUT_DIR / f"{name}.parquet").as_posix()
        con.execute(f"COPY ({query}) TO '{path}' (FORMAT parquet)")
        print(f"wrote {name}.parquet")
    con.close()
    print(f"folder: {OUT_DIR}")


if __name__ == "__main__":
    main()
