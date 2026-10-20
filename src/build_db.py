"""Load the clean Parquet files into a local DuckDB database (data/processed/olist.duckdb),
then build the analysis mart by running sql/mart/*.sql in file-name order.

Run after src/clean.py:  python src/build_db.py
"""
import duckdb

from config import DB_PATH, PROCESSED_DIR, SQL_DIR

TABLES = ["orders", "order_items", "payments", "reviews", "customers", "products", "sellers"]


def main():
    con = duckdb.connect(str(DB_PATH))
    print("clean tables")
    for name in TABLES:
        path = (PROCESSED_DIR / f"{name}.parquet").as_posix()
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_parquet('{path}')")
        n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        print(f"  {name:<16} {n:>9,} rows")

    print("mart tables")
    for sql_file in sorted((SQL_DIR / "mart").glob("*.sql")):
        con.execute(sql_file.read_text(encoding="utf-8"))
        table = sql_file.stem.split("_", 1)[1]  # 01_fct_orders.sql -> fct_orders
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table:<16} {n:>9,} rows")
    con.close()
    print(f"database: {DB_PATH}")


if __name__ == "__main__":
    main()
