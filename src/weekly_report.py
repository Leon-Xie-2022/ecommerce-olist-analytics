"""Produce the weekly delivery operations report for one historical cut-off date.

Runs sql/weekly/*.sql on the clean Parquet inputs, checks the results, and only then publishes them:
    output/weekly/as_of=<date>/      this period's CSVs and run_manifest.json (replaced on re-run)
    output/weekly/latest/            copy of the last published run, read by the Excel workbook
    output/weekly/run_log.csv        one line per attempt, successful or not
A failed input check or reconciliation leaves both folders exactly as they were.

Usage:
    python src/weekly_report.py --as-of 2018-03-11
    python src/weekly_report.py --as-of 2018-03-18 --set min_route_sample=50 --label CR-001
        (a labelled run goes to output/weekly/what_if/<label>/as_of=<date>/ and does not touch latest/)

Exit codes: 0 published, 2 configuration or input problem, 3 reconciliation failed, 4 output folder in use,
5 unexpected data/database error. On any failure nothing is published: the period folder and latest/ are
both kept at their previous version (or both rolled back), and the attempt is logged.
"""
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import time
import tomllib
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb

from config import PROJECT_ROOT, SQL_DIR

CONFIG_PATH = PROJECT_ROOT / "config" / "weekly_report.toml"
WEEKLY_SQL_DIR = SQL_DIR / "weekly"

# Input tables and the columns the weekly SQL reads. order_status is deliberately absent.
REQUIRED_COLUMNS = {
    "orders": ["order_id", "customer_id", "order_purchase_timestamp", "order_approved_at",
               "order_delivered_carrier_date", "order_delivered_customer_date",
               "order_estimated_delivery_date"],
    "order_items": ["order_id", "order_item_id", "seller_id", "shipping_limit_date", "price",
                    "freight_value"],
    "payments": ["order_id", "payment_sequential", "payment_value"],
    "customers": ["customer_id", "customer_state"],
    "sellers": ["seller_id", "seller_state"],
}
# An order may legitimately have several payment rows, so payments are unique per (order, sequence),
# not per order. A batch loaded twice breaks these keys and stops the run before any money is summed.
PRIMARY_KEYS = {"orders": ["order_id"], "order_items": ["order_id", "order_item_id"],
                "payments": ["order_id", "payment_sequential"],
                "customers": ["customer_id"], "sellers": ["seller_id"]}

# Output tables (created by the SQL files) -> file name.
OUTPUTS = {
    "weekly_summary": "weekly_summary.csv",
    "route_diagnosis": "route_diagnosis.csv",
    "exceptions": "exceptions.csv",
    "reconciliation": "reconciliation.csv",
}
INT_PARAMS = ["window_days", "min_route_sample", "max_overdue_days", "p1_min_days_overdue",
              "p2_min_days_overdue"]
RUN_LOG_FIELDS = ["run_id", "started_at", "as_of_date", "label", "status", "exit_code", "message",
                  "output_folder", "published_latest", "seconds"]


class RunError(Exception):
    """A controlled failure. published=True only if a rollback could not restore the previous outputs."""

    def __init__(self, message, exit_code, published=False):
        super().__init__(message)
        self.exit_code = exit_code
        self.published = published


class ConfigError(Exception):
    pass


def rel(path):
    """Path relative to the project root when possible, for logs and manifests."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_config(path, overrides, as_of=None):
    """Read the TOML config, apply --set overrides and check that the parameters make sense."""
    try:
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"cannot read config {path}: {e}") from e
    for item in overrides:
        key, sep, value = item.partition("=")
        if not sep or key not in cfg:
            raise ConfigError(f"--set {item!r}: expected KEY=VALUE with KEY one of {', '.join(cfg)}")
        cfg[key] = value
    if as_of:
        cfg["as_of_date"] = as_of
    try:
        for key in INT_PARAMS:
            cfg[key] = int(cfg[key])
        cfg["as_of_date"] = date.fromisoformat(str(cfg["as_of_date"]))
    except (KeyError, ValueError) as e:
        raise ConfigError(f"invalid parameter: {e}") from e
    rules = [
        (cfg["window_days"] >= 1, "window_days must be >= 1"),
        (cfg["min_route_sample"] >= 1, "min_route_sample must be >= 1"),
        (cfg["max_overdue_days"] >= 1, "max_overdue_days must be >= 1"),
        (cfg["p2_min_days_overdue"] >= 1, "p2_min_days_overdue must be >= 1"),
        (cfg["p1_min_days_overdue"] > cfg["p2_min_days_overdue"],
         "p1_min_days_overdue must be greater than p2_min_days_overdue"),
        (cfg["p1_min_days_overdue"] <= cfg["max_overdue_days"],
         "p1_min_days_overdue must not exceed max_overdue_days (P1 would always be empty)"),
    ]
    problems = [message for ok, message in rules if not ok]
    if problems:
        raise ConfigError("; ".join(problems))
    return cfg


def check_inputs(con, input_dir):
    """Files present, required columns present, primary keys unique. Returns {table: sha256}."""
    checksums, problems = {}, []
    for table, columns in REQUIRED_COLUMNS.items():
        path = input_dir / f"{table}.parquet"
        if not path.exists():
            problems.append(f"missing input file: {path}")
            continue
        try:
            found = {r[0] for r in con.execute(
                "SELECT name FROM parquet_schema(?) WHERE name <> 'schema'", [path.as_posix()]).fetchall()}
        except duckdb.Error as e:
            problems.append(f"{path.name}: not a readable Parquet file ({type(e).__name__})")
            continue
        missing = [c for c in columns if c not in found]
        if missing:
            problems.append(f"{path.name}: missing column(s) {', '.join(missing)}")
            continue
        con.execute(f"CREATE OR REPLACE VIEW src_{table} AS SELECT * FROM read_parquet('{path.as_posix()}')")
        checksums[table] = sha256(path)
    if problems:
        raise RunError("; ".join(problems), 2)
    for table, key in PRIMARY_KEYS.items():
        cols = ", ".join(key)
        try:
            dupes = con.execute(f"SELECT COUNT(*) - COUNT(DISTINCT ({cols})) FROM src_{table}").fetchone()[0]
        except duckdb.Error as e:
            raise RunError(f"{table}.parquet: cannot be read ({type(e).__name__})", 2) from e
        if dupes:
            raise RunError(f"{table}: {dupes} duplicate key(s) on ({cols})", 2)
    return checksums


def git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "sql", "src", "config"],
                               cwd=PROJECT_ROOT, capture_output=True, text=True).stdout.strip()
        return out + ("+uncommitted" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_outputs(con, cfg):
    """Run the weekly SQL. Returns {table: DataFrame} in a fixed order."""
    for key in ["as_of_date", *INT_PARAMS]:
        value = cfg[key]
        literal = f"DATE '{value.isoformat()}'" if key == "as_of_date" else str(value)
        con.execute(f"SET VARIABLE {key} = {literal}")
    for sql_file in sorted(WEEKLY_SQL_DIR.glob("*.sql")):
        con.execute(sql_file.read_text(encoding="utf-8"))
    return {table: con.execute(f"SELECT * FROM {table}").df() for table in OUTPUTS}


def write_csv(df, path):
    # Booleans as TRUE/FALSE and ISO dates; fixed column order and row order come from the SQL.
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == bool or str(df[col].dtype) == "boolean":
            df[col] = df[col].map({True: "TRUE", False: "FALSE"})
        elif "datetime" in str(df[col].dtype):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def append_run_log(log_path, row):
    new = not log_path.exists()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_LOG_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(row)


def publish_folders(pairs):
    """Swap finished staging folders into place as one unit: pairs = [(staging, target), ...].

    Each target is renamed to <target>.old, then the staging folder takes its name. If Windows refuses any
    rename (a file or the folder is open in another program), every swap already made is undone in reverse
    order, so the period folder and latest/ can never end up on different runs. Raises RunError(4).
    """
    done = []  # (staging, target, backup or None) for the swaps completed so far
    try:
        for staging, target in pairs:
            backup = target.with_name(target.name + ".old")
            if backup.exists():
                shutil.rmtree(backup)
            if target.exists():
                target.rename(backup)
            else:
                backup = None
            try:
                staging.rename(target)
            except OSError:
                if backup is not None:
                    backup.rename(target)
                raise
            done.append((staging, target, backup))
    except OSError as e:
        rollback_problems = []
        for staging, target, backup in reversed(done):
            try:
                target.rename(staging)
                if backup is not None:
                    backup.rename(target)
            except OSError as undo_error:
                rollback_problems.append(f"{rel(target)} ({undo_error.strerror})")
        where = rel(Path(e.filename)) if e.filename else "an output folder"
        message = f"could not replace {where} ({e.strerror}); close any program using it and run again"
        if rollback_problems:
            message += "; ROLLBACK INCOMPLETE for " + ", ".join(rollback_problems)
        raise RunError(message, 4, published=bool(rollback_problems)) from e
    for _, _, backup in done:
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)


def run(args):
    started = time.perf_counter()
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        cfg = load_config(args.config, args.set, args.as_of)
    except ConfigError as e:
        print(f"FAILED (exit 2): configuration error: {e}\nNothing was run or published.", file=sys.stderr)
        return 2
    as_of = cfg["as_of_date"]
    run_id = f"{as_of.isoformat()}_{datetime.now().strftime('%Y%m%dT%H%M%S')}"

    input_dir = PROJECT_ROOT / (args.input_dir or cfg["input_dir"])
    mart_db = PROJECT_ROOT / (args.mart_db or cfg["mart_db"])
    output_root = PROJECT_ROOT / (args.output_dir or cfg["output_dir"])
    folder_name = f"as_of={as_of.isoformat()}"
    if args.label:
        target = output_root / "what_if" / args.label / folder_name
    else:
        target = output_root / folder_name
    publish_latest = not args.label and not args.no_latest
    log_row = {"run_id": run_id, "started_at": started_at, "as_of_date": as_of.isoformat(),
               "label": args.label or "", "output_folder": rel(target),
               "published_latest": publish_latest}

    staging = output_root / f".staging_{run_id}"
    latest_staging = output_root / f".staging_latest_{run_id}"
    con = None
    try:
        con = duckdb.connect()
        checksums = check_inputs(con, input_dir)
        max_purchase = con.execute("SELECT MAX(order_purchase_timestamp) FROM src_orders").fetchone()[0]
        if as_of > max_purchase.date():
            raise RunError(f"as_of_date {as_of} is after the last purchase in the data "
                           f"({max_purchase.date()}); the data cannot describe that day", 2)
        if not mart_db.exists():
            raise RunError(f"missing mart database for reconciliation: {mart_db}", 2)
        try:
            con.execute(f"ATTACH '{mart_db.as_posix()}' AS mart (READ_ONLY)")
        except duckdb.Error as e:
            raise RunError(f"mart database cannot be opened: {rel(mart_db)} ({type(e).__name__})", 2) from e

        tables = build_outputs(con, cfg)
        recon = tables["reconciliation"]
        failed = recon[recon["status"] != "PASS"]

        staging.mkdir(parents=True)
        outputs = {}
        for table, file_name in OUTPUTS.items():
            write_csv(tables[table], staging / file_name)
            outputs[file_name] = {"rows": len(tables[table]), "sha256": sha256(staging / file_name)}
        if len(failed):
            raise RunError(f"{len(failed)} reconciliation check(s) failed: "
                           + "; ".join(failed["check_name"]), 3)

        window_start = tables["weekly_summary"]["window_start"].iloc[0].date()
        params = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in cfg.items()}
        run_info = [
            ("Run ID", run_id),
            ("Cut-off date (as_of_date)", as_of.isoformat()),
            ("Window start (inclusive)", window_start.isoformat()),
            ("Window end (inclusive)", as_of.isoformat()),
            ("Information known", f"events timestamped before {as_of + timedelta(days=1)} 00:00"),
            ("Label", args.label or "official run"),
            *[(f"Parameter: {k}", params[k]) for k in INT_PARAMS],
            ("Reconciliation checks passed", f"{len(recon) - len(failed)}/{len(recon)}"),
            ("Code version (git)", git_commit()),
            ("Generated at", started_at),
            *[(f"Input SHA-256: {t}.parquet", h) for t, h in checksums.items()],
        ]
        with open(staging / "run_info.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(["item", "value"])
            writer.writerows(run_info)

        manifest = {
            "run_id": run_id,
            "started_at": started_at,
            "as_of_date": as_of.isoformat(),
            "window": {"start": window_start.isoformat(), "end": as_of.isoformat(),
                       "both_ends_inclusive": True, "calendar": "dataset-local calendar dates"},
            "label": args.label,
            "parameters": params,
            "code_version": git_commit(),
            "inputs": {f"{t}.parquet": {"sha256": h} for t, h in checksums.items()},
            "mart_db": rel(mart_db),
            "outputs": outputs,
            "checks": {"input_files_and_columns": "PASS", "primary_keys_unique": "PASS",
                       "reconciliation": f"{len(recon) - len(failed)}/{len(recon)} PASS"},
            "seconds": round(time.perf_counter() - started, 2),
        }
        (staging / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        con.close()
        con = None

        # Prepare everything first, then swap the period folder and latest/ together (all or nothing).
        target.parent.mkdir(parents=True, exist_ok=True)
        pairs = [(staging, target)]
        if publish_latest:
            shutil.copytree(staging, latest_staging)
            pairs.append((latest_staging, output_root / "latest"))
        publish_folders(pairs)

        seconds = round(time.perf_counter() - started, 2)
        append_run_log(output_root / "run_log.csv",
                       {**log_row, "status": "SUCCESS", "exit_code": 0, "seconds": seconds,
                        "message": f"{len(recon)}/{len(recon)} reconciliation checks passed"})
        print(f"published {rel(target)}"
              + (" and latest/" if publish_latest else "") + f" in {seconds}s")
        for file_name, info in outputs.items():
            print(f"  {file_name:<22} {info['rows']:>5} rows")
        return 0
    except (RunError, duckdb.Error, OSError) as e:
        if not isinstance(e, RunError):
            # Anything else that fails while reading data, running SQL or writing files is still a logged,
            # controlled failure, not a traceback that leaves staging folders behind.
            e = RunError(f"unexpected {type(e).__name__}: {str(e).splitlines()[0][:300]}", 5)
        if con is not None:
            con.close()
            con = None
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(latest_staging, ignore_errors=True)
        seconds = round(time.perf_counter() - started, 2)
        append_run_log(output_root / "run_log.csv",
                       {**log_row, "status": "FAILED", "exit_code": e.exit_code, "seconds": seconds,
                        "message": str(e), "published_latest": False})
        outcome = ("Outputs may be inconsistent; see the message above." if e.published
                   else "Nothing was published; previous outputs are unchanged.")
        print(f"FAILED (exit {e.exit_code}): {e}\n{outcome}", file=sys.stderr)
        return e.exit_code
    finally:
        if con is not None:
            con.close()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as-of", help="cut-off date YYYY-MM-DD (default: as_of_date in the config)")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="override one config value for this run (repeatable)")
    parser.add_argument("--label", help="what-if run label; output goes to what_if/<label>/")
    parser.add_argument("--input-dir", help="override input_dir (relative to project root)")
    parser.add_argument("--mart-db", help="override mart_db (relative to project root)")
    parser.add_argument("--output-dir", help="override output_dir (relative to project root)")
    parser.add_argument("--no-latest", action="store_true", help="do not update latest/")
    sys.exit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
