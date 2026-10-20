"""Load the clean Parquet files into a local DuckDB database (data/processed/olist.duckdb).

Run after src/clean.py:  python src/build_db.py
"""
import duckdb

from config import DB_PATH, PROCESSED_DIR

TABLES = ["orders", "order_items", "payments", "reviews", "customers", "products", "sellers"]


def main():
    con = duckdb.connect(str(DB_PATH))
    for name in TABLES:
        path = (PROCESSED_DIR / f"{name}.parquet").as_posix()
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_parquet('{path}')")
        n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        print(f"{name:<12} {n:>9,} rows")
    con.close()
    print(f"database: {DB_PATH}")


if __name__ == "__main__":
    main()
