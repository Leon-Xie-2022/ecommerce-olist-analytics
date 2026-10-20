"""Run SQL files against the DuckDB database, print the result and save it as CSV in reports/tables/.

A file may contain several statements; only the last one's result is printed and saved.

Usage:
    python src/run_sql.py sql/metrics/01_monthly_orders_and_value.sql
    python src/run_sql.py sql/metrics/*.sql
"""
import glob
import sys
from pathlib import Path

import duckdb
import pandas as pd

from config import DB_PATH, REPORTS_DIR

TABLES_DIR = REPORTS_DIR / "tables"


def run_file(con, path):
    result = con.sql(Path(path).read_text(encoding="utf-8"))
    return result.df() if result is not None else None


def main(paths):
    sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    for path in paths:
        df = run_file(con, path)
        print(f"\n== {path}")
        if df is None:
            continue
        print(df.to_string(index=False))
        out = TABLES_DIR / f"{Path(path).stem}.csv"
        df.to_csv(out, index=False)
        print(f"-> {out.relative_to(REPORTS_DIR.parent).as_posix()}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    # PowerShell does not expand wildcards, so expand them here.
    main([p for arg in sys.argv[1:] for p in sorted(glob.glob(arg)) or [arg]])
