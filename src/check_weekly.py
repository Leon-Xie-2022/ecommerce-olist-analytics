"""Scripted acceptance checks for src/weekly_report.py. Runs everything in a temporary folder, so the
real output/weekly/ is not touched. Writes docs/weekly_ops/evidence/check_weekly_results.md.

    python src/check_weekly.py

Checks
  1. Two consecutive cut-offs publish and are kept side by side.
  2. Re-running the same cut-off gives byte-identical data files and does not add rows.
  3. Missing input file          -> exit 2, previous outputs unchanged.
  4. Missing required column     -> exit 2, previous outputs unchanged.
  5. Duplicate primary key       -> exit 2, previous outputs unchanged.
  6. Output folder in use        -> exit 4, previous outputs unchanged.
  7. latest/ in use              -> exit 4, period folder AND latest/ both keep the previous run.
  8. Duplicate payment row       -> exit 2 (key is order_id + payment_sequential).
  9. Extra payment row on an order in the follow-up list, bought before the window
                                 -> exit 3 (exceptions vs mart reconciliation).
 10. Unreadable (corrupt) input  -> exit 2, logged as FAILED, no staging folder left.
 11. Week with no deliveries     -> publishes; counts 0, late rate blank, all reconciliations PASS.
 12. Invalid parameters          -> exit 2 before anything runs.
 13. Point-in-time: a snapshot of the inputs that physically removes everything dated after the cut-off
     (and drops order_status) gives exactly the same outputs as the full data.
"""
import csv
import hashlib
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import duckdb

from config import PROCESSED_DIR, PROJECT_ROOT

PY = sys.executable
SCRIPT = PROJECT_ROOT / "src" / "weekly_report.py"
DATA_FILES = ["weekly_summary.csv", "route_diagnosis.csv", "exceptions.csv", "reconciliation.csv"]
INPUTS = ["orders", "order_items", "payments", "customers", "sellers"]
RESULTS_PATH = PROJECT_ROOT / "docs" / "weekly_ops" / "evidence" / "check_weekly_results.md"
AS_OF_1, AS_OF_2 = "2018-03-11", "2018-03-18"


def run_report(out_dir, as_of, input_dir=None, extra=()):
    cmd = [PY, str(SCRIPT), "--as-of", as_of, "--output-dir", str(out_dir), *extra]
    if input_dir:
        cmd += ["--input-dir", str(input_dir)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    lines = p.stderr.strip().splitlines() or p.stdout.strip().splitlines() or [""]
    return p.returncode, lines[0]


def folder_hashes(folder):
    """sha256 of every data file in a folder (run_info.csv and the manifest hold timestamps, so excluded)."""
    return {f: hashlib.sha256((folder / f).read_bytes()).hexdigest() for f in DATA_FILES if (folder / f).exists()}


def snapshot_all(out_dir):
    return {name: folder_hashes(out_dir / name) for name in [f"as_of={AS_OF_1}", f"as_of={AS_OF_2}", "latest"]}


def manifests(out_dir):
    """Raw bytes of each run manifest: they change on every publish (run ID), so equal = not republished."""
    return {name: (out_dir / name / "run_manifest.json").read_bytes()
            for name in [f"as_of={AS_OF_1}", f"as_of={AS_OF_2}", "latest"]}


def leftovers(out_dir):
    """Staging or backup folders left behind by a failed run."""
    return sorted(p.name for p in out_dir.iterdir() if p.name.startswith(".staging") or p.name.endswith(".old"))


def copy_inputs(dest):
    dest.mkdir(parents=True)
    for t in INPUTS:
        shutil.copy2(PROCESSED_DIR / f"{t}.parquet", dest / f"{t}.parquet")
    return dest


def rewrite_parquet(path, sql):
    con = duckdb.connect()
    con.execute(f"CREATE TABLE t AS {sql.format(src=repr(path.as_posix()))}")
    path.unlink()
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT parquet)")
    con.close()


def point_in_time_snapshot(dest, as_of):
    """Independent re-implementation of 'what a database copy taken at the cut-off would contain'."""
    cutoff = (date.fromisoformat(as_of) + timedelta(days=1)).isoformat()
    con = duckdb.connect()
    src = {t: (PROCESSED_DIR / f"{t}.parquet").as_posix() for t in INPUTS}
    dest.mkdir(parents=True)
    con.execute(f"""
        CREATE TABLE orders AS
        SELECT order_id, customer_id, order_purchase_timestamp,
               CASE WHEN order_approved_at < TIMESTAMP '{cutoff}' THEN order_approved_at END AS order_approved_at,
               CASE WHEN order_delivered_carrier_date < TIMESTAMP '{cutoff}'
                    THEN order_delivered_carrier_date END AS order_delivered_carrier_date,
               CASE WHEN order_delivered_customer_date < TIMESTAMP '{cutoff}'
                    THEN order_delivered_customer_date END AS order_delivered_customer_date,
               order_estimated_delivery_date
        FROM read_parquet('{src["orders"]}')
        WHERE order_purchase_timestamp < TIMESTAMP '{cutoff}'""")
    for t in ["order_items", "payments"]:
        con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_parquet('{src[t]}') "
                    "WHERE order_id IN (SELECT order_id FROM orders)")
    con.execute(f"CREATE TABLE customers AS SELECT * FROM read_parquet('{src['customers']}') "
                "WHERE customer_id IN (SELECT customer_id FROM orders)")
    con.execute(f"CREATE TABLE sellers AS SELECT * FROM read_parquet('{src['sellers']}')")
    for t in INPUTS:
        con.execute(f"COPY {t} TO '{(dest / f'{t}.parquet').as_posix()}' (FORMAT parquet)")
    n_full = con.execute(f"SELECT COUNT(*) FROM read_parquet('{src['orders']}')").fetchone()[0]
    n_snap = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    con.close()
    return n_full, n_snap


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    results = []
    tmp = Path(".")

    def record(name, ok, detail):
        # Hide the machine-specific temporary path in the saved evidence.
        detail = detail.replace(str(tmp), "<tmp>").replace(tmp.as_posix(), "<tmp>")
        results.append((name, "PASS" if ok else "FAIL", detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

    with tempfile.TemporaryDirectory(prefix="weekly_check_") as tmp_name:
        tmp = Path(tmp_name)
        out = tmp / "output"

        # 1. Two periods
        c1, _ = run_report(out, AS_OF_1)
        c2, _ = run_report(out, AS_OF_2)
        h1, h2 = folder_hashes(out / f"as_of={AS_OF_1}"), folder_hashes(out / f"as_of={AS_OF_2}")
        latest = folder_hashes(out / "latest")
        record("Two periods published and kept", c1 == 0 and c2 == 0 and len(h1) == len(h2) == 4
               and h1 != h2 and latest == h2,
               f"exit codes {c1}/{c2}; both folders have 4 data files; latest/ = {AS_OF_2}")

        # 2. Re-run
        rows_before = sum(1 for _ in open(out / f"as_of={AS_OF_2}" / "exceptions.csv", encoding="utf-8"))
        c3, _ = run_report(out, AS_OF_2)
        rows_after = sum(1 for _ in open(out / f"as_of={AS_OF_2}" / "exceptions.csv", encoding="utf-8"))
        same = folder_hashes(out / f"as_of={AS_OF_2}") == h2
        log_lines = sum(1 for _ in open(out / "run_log.csv", encoding="utf-8")) - 1
        record("Re-run is idempotent", c3 == 0 and same and rows_before == rows_after,
               f"identical SHA-256 for all 4 data files; exceptions.csv {rows_before - 1} rows before and "
               f"after; run_log has {log_lines} lines (one per attempt, by design)")

        before = snapshot_all(out)

        # 3. Missing file
        bad = copy_inputs(tmp / "missing_file")
        (bad / "sellers.parquet").unlink()
        code, msg = run_report(out, AS_OF_2, bad)
        record("Missing input file fails safely", code == 2 and snapshot_all(out) == before,
               f"exit {code}; outputs unchanged; message: {msg}")

        # 4. Missing column
        bad = copy_inputs(tmp / "missing_column")
        rewrite_parquet(bad / "orders.parquet",
                        "SELECT * EXCLUDE (order_delivered_customer_date) FROM read_parquet({src})")
        code, msg = run_report(out, AS_OF_2, bad)
        record("Missing required column fails safely", code == 2 and snapshot_all(out) == before,
               f"exit {code}; outputs unchanged; message: {msg}")

        # 5. Duplicate key (e.g. a batch loaded twice)
        bad = copy_inputs(tmp / "duplicate_key")
        rewrite_parquet(bad / "orders.parquet",
                        "SELECT * FROM read_parquet({src}) UNION ALL "
                        "(SELECT * FROM read_parquet({src}) ORDER BY order_id LIMIT 10)")
        code, msg = run_report(out, AS_OF_2, bad)
        record("Duplicate primary key fails safely", code == 2 and snapshot_all(out) == before,
               f"exit {code}; outputs unchanged; message: {msg}")

        # 6. Output folder in use (Windows keeps a lock while a file inside is open)
        handle = open(out / f"as_of={AS_OF_2}" / "weekly_summary.csv", encoding="utf-8")
        try:
            code, msg = run_report(out, AS_OF_2)
        finally:
            handle.close()
        record("Output folder in use fails safely",
               (code == 4 or (code == 0 and sys.platform != "win32")) and snapshot_all(out) == before,
               f"exit {code}; outputs unchanged; message: {msg}")

        # 7. latest/ in use: the period folder must not be published on its own
        before_manifests = manifests(out)
        handle = open(out / "latest" / "weekly_summary.csv", encoding="utf-8")
        try:
            code, msg = run_report(out, AS_OF_1)
        finally:
            handle.close()
        record("latest/ in use rolls back both folders",
               (code == 4 or (code == 0 and sys.platform != "win32"))
               and snapshot_all(out) == before and manifests(out) == before_manifests and not leftovers(out),
               f"exit {code}; as_of={AS_OF_1}/ and latest/ data files and manifests unchanged "
               f"(latest/ still = {AS_OF_2}); no staging or .old folders left; message: {msg}")

        listed = [r for r in csv.DictReader(open(out / f"as_of={AS_OF_2}" / "exceptions.csv", encoding="utf-8"))
                  if r["purchase_date"] < r["window_start"] and float(r["payment_value"] or 0) > 0][0]
        order_id = listed["order_id"]

        # 8. Duplicate payment row (same order_id and payment_sequential)
        bad = copy_inputs(tmp / "duplicate_payment")
        rewrite_parquet(bad / "payments.parquet",
                        "SELECT * FROM read_parquet({src}) UNION ALL "
                        f"SELECT * FROM read_parquet({{src}}) WHERE order_id = '{order_id}'")
        code, msg = run_report(out, AS_OF_2, bad)
        record("Duplicate payment row fails safely", code == 2 and snapshot_all(out) == before,
               f"exit {code}; listed order bought {listed['purchase_date']} (before the window); "
               f"outputs unchanged; message: {msg}")

        # 9. A new payment row with a fresh sequence number passes the key check but changes the money
        bad = copy_inputs(tmp / "extra_payment")
        rewrite_parquet(bad / "payments.parquet",
                        "SELECT * FROM read_parquet({src}) UNION ALL "
                        "SELECT * REPLACE (payment_sequential + 100 AS payment_sequential) "
                        f"FROM read_parquet({{src}}) WHERE order_id = '{order_id}'")
        code, msg = run_report(out, AS_OF_2, bad)
        record("Changed payment of a listed order fails reconciliation", code == 3 and snapshot_all(out) == before,
               f"exit {code}; payment_value {listed['payment_value']} would double; outputs unchanged; "
               f"message: {msg}")

        # 10. Corrupt input file
        bad = copy_inputs(tmp / "corrupt_file")
        (bad / "sellers.parquet").write_bytes(b"this is not a parquet file")
        log_before = (out / "run_log.csv").read_text(encoding="utf-8").splitlines()
        code, msg = run_report(out, AS_OF_2, bad)
        log_after = (out / "run_log.csv").read_text(encoding="utf-8").splitlines()
        logged = len(log_after) == len(log_before) + 1 and ",FAILED,2," in log_after[-1]
        record("Corrupt input file fails safely and is logged",
               code == 2 and logged and snapshot_all(out) == before and not leftovers(out),
               f"exit {code}; one FAILED line added to run_log.csv; no staging folder; message: {msg}")

        # 11. A week with no deliveries (first day of the data)
        empty_out = tmp / "empty_week"
        code, msg = run_report(empty_out, "2016-09-04", extra=["--no-latest"])
        folder = empty_out / "as_of=2016-09-04"
        ok = code == 0
        if ok:
            summary = {r["metric"]: r["value"] for r in csv.DictReader(open(folder / "weekly_summary.csv", encoding="utf-8"))}
            recon = list(csv.DictReader(open(folder / "reconciliation.csv", encoding="utf-8")))
            ok = (float(summary["Orders delivered"]) == 0 and summary["Late rate"] == ""
                  and all(r["status"] == "PASS" for r in recon))
        record("Week with no deliveries publishes", ok,
               f"exit {code}; orders delivered 0, late rate blank (undefined), all reconciliations PASS")

        # 12. Invalid parameters
        codes = []
        for setting in [["--set", "p1_min_days_overdue=2"], ["--set", "min_route_sample=0"],
                        ["--set", "p2_min_days_overdue=-1"]]:
            code, msg = run_report(out, AS_OF_2, extra=setting)
            codes.append(code)
        record("Invalid parameters are rejected", codes == [2, 2, 2] and snapshot_all(out) == before,
               f"exit codes {codes} for p1 below p2, min_route_sample 0, negative p2; last message: {msg}")

        # 13. Point-in-time snapshot gives the same answer
        for as_of in [AS_OF_1, AS_OF_2]:
            snap_dir = tmp / f"snapshot_{as_of}"
            n_full, n_snap = point_in_time_snapshot(snap_dir, as_of)
            snap_out = tmp / f"snapshot_output_{as_of}"
            code, _ = run_report(snap_out, as_of, snap_dir)
            same = folder_hashes(snap_out / f"as_of={as_of}") == folder_hashes(out / f"as_of={as_of}")
            record(f"No future information ({as_of})", code == 0 and same,
                   f"snapshot keeps {n_snap:,} of {n_full:,} orders, nulls later events and drops "
                   f"order_status; all 4 data files identical to the full-data run")

    n_pass = sum(r[1] == "PASS" for r in results)
    lines = ["# Weekly report: scripted check results", "",
             "Generated by `python src/check_weekly.py` (temporary folders; real outputs untouched).", "",
             "| # | Check | Result | Detail |", "|---|---|---|---|"]
    lines += [f"| {i} | {n} | {s} | {d.replace('|', '/')} |" for i, (n, s, d) in enumerate(results, 1)]
    lines += ["", f"**{n_pass}/{len(results)} checks passed.**", ""]
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{n_pass}/{len(results)} checks passed -> {RESULTS_PATH.relative_to(PROJECT_ROOT).as_posix()}")
    sys.exit(0 if n_pass == len(results) else 1)


if __name__ == "__main__":
    main()
