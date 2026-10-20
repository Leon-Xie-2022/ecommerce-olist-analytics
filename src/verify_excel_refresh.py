"""Verify that the Excel workbook picks up a new period on Refresh All and matches the SQL output.

For each cut-off in turn: publish it with src/weekly_report.py (so output/weekly/latest/ changes), open
excel/olist_weekly_ops.xlsx in Excel desktop, run Refresh All (excel/refresh_and_read.ps1), and compare
what the workbook shows with the CSV files of that run. Writes
docs/weekly_ops/evidence/excel_refresh_results.md and, for the last period, Excel screenshots in
reports/figures/.

    python src/verify_excel_refresh.py            (Windows with Excel desktop only)

This is scripted Excel automation: the same Refresh All a user clicks, run through COM. A manual click in
the Excel UI is recorded separately in docs/weekly_ops/acceptance.md.
"""
import json
import re
import subprocess
import sys
import zipfile

import pandas as pd

from config import FIGURES_DIR, PROJECT_ROOT

AS_OF_DATES = ["2018-03-11", "2018-03-18"]
LATEST = PROJECT_ROOT / "output" / "weekly" / "latest"
PS1 = PROJECT_ROOT / "excel" / "refresh_and_read.ps1"
WORKBOOK = PROJECT_ROOT / "excel" / "olist_weekly_ops.xlsx"
RESULTS_PATH = PROJECT_ROOT / "docs" / "weekly_ops" / "evidence" / "excel_refresh_results.md"


def close(a, b, tol=0.005):
    return a is not None and b is not None and abs(float(a) - float(b)) < tol


def strip_local_paths(path):
    """Remove this machine's folder from the saved workbook: Excel stores the save location (absPath) and
    the last computed value of the OutputFolder formula. Both are rebuilt by Excel when the file is opened."""
    with zipfile.ZipFile(path) as z:
        parts = {info: z.read(info.filename) for info in z.infolist()}
    out = {}
    for info, data in parts.items():
        if info.filename == "xl/workbook.xml":
            data = re.sub(rb"<mc:AlternateContent[^>]*><mc:Choice Requires=\"x15\"><x15ac:absPath[^>]*/>"
                          rb"</mc:Choice></mc:AlternateContent>", b"", data)
        elif info.filename.startswith("xl/worksheets/"):
            data = re.sub(rb'(<c r="B6"[^>]*?)( t="str")?(><f[^>]*>[^<]*</f>)<v>[^<]*</v>', rb"\1\3", data)
        out[info] = data
    tmp = path.with_suffix(".tmp.xlsx")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in out.items():
            z.writestr(info, data)
    tmp.replace(path)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sections = []
    all_ok = True
    for i, as_of in enumerate(AS_OF_DATES):
        subprocess.run([sys.executable, str(PROJECT_ROOT / "src" / "weekly_report.py"), "--as-of", as_of],
                       check=True, capture_output=True)
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1)]
        if i == len(AS_OF_DATES) - 1:
            cmd += ["-ScreenshotDir", str(FIGURES_DIR)]
        out = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8").stdout
        xl = json.loads(out[out.index("{"):])

        summary = pd.read_csv(LATEST / "weekly_summary.csv")
        exc = pd.read_csv(LATEST / "exceptions.csv")
        route = pd.read_csv(LATEST / "route_diagnosis.csv")
        recon = pd.read_csv(LATEST / "reconciliation.csv")
        metric_mismatches = [m for m, v in zip(summary["metric"], summary["value"])
                             if not close(xl["summary"].get(m), v)]
        rows = [
            ("Loaded cut-off date (Read Me)", xl["loaded_cutoff"], as_of, xl["loaded_cutoff"] == as_of),
            ("Weekly Summary: all 22 metric values", f"{len(summary) - len(metric_mismatches)} match",
             f"{len(summary)} in CSV", not metric_mismatches),
            ("Orders placed", xl["summary"]["Orders placed"],
             summary.set_index("metric").loc["Orders placed", "value"],
             close(xl["summary"]["Orders placed"], summary.set_index("metric").loc["Orders placed", "value"])),
            ("Product value placed (BRL)", xl["summary"]["Product value"],
             summary.set_index("metric").loc["Product value", "value"],
             close(xl["summary"]["Product value"], summary.set_index("metric").loc["Product value", "value"])),
            ("Exceptions rows", xl["exceptions_rows"], len(exc), xl["exceptions_rows"] == len(exc)),
            ("Exceptions product value (BRL)", round(xl["exceptions_product_value"], 2),
             round(exc["product_value"].sum(), 2), close(xl["exceptions_product_value"], exc["product_value"].sum())),
            ("Exceptions first order_id", xl["exceptions_first_order"], exc["order_id"].iloc[0],
             xl["exceptions_first_order"] == exc["order_id"].iloc[0]),
            ("Pivot: total orders", xl["pivot_orders_total"], len(exc), xl["pivot_orders_total"] == len(exc)),
            ("Pivot: total product value (BRL)", round(xl["pivot_product_value_total"], 2),
             round(exc["product_value"].sum(), 2),
             close(xl["pivot_product_value_total"], exc["product_value"].sum())),
            ("Route rows", xl["route_rows"], len(route), xl["route_rows"] == len(route)),
            ("Route delivered total", xl["route_delivered_total"], route["delivered_orders"].sum(),
             xl["route_delivered_total"] == route["delivered_orders"].sum()),
            ("Routes ranked", xl["route_ranked"], route["late_rate_rank"].notna().sum(),
             xl["route_ranked"] == route["late_rate_rank"].notna().sum()),
            ("Reconciliation PASS rows", xl["reconciliation_pass"], (recon["status"] == "PASS").sum(),
             xl["reconciliation_pass"] == (recon["status"] == "PASS").sum() == len(recon)),
        ]
        ok = all(r[3] for r in rows)
        all_ok &= ok
        print(f"\n== {as_of}: Refresh All took {xl['refresh_seconds']}s, {'PASS' if ok else 'FAIL'}")
        for name, a, b, good in rows:
            print(f"  {'PASS' if good else 'FAIL'}  {name}: Excel {a} / CSV {b}")
        lines = [f"## Step {i + 1}: publish cut-off {as_of}, then Refresh All", "",
                 f"Refresh All took {xl['refresh_seconds']} s. Late rate shown as `{xl['summary_display_late_rate']}`.", "",
                 "| Item | Excel after refresh | SQL / CSV | Result |", "|---|---|---|---|"]
        lines += [f"| {n} | {a} | {b} | {'PASS' if g else 'FAIL'} |" for n, a, b, g in rows]
        sections.append("\n".join(lines))

    text = ["# Excel refresh verification", "",
            "Generated by `python src/verify_excel_refresh.py`: Excel desktop opened through COM automation, "
            "`Workbook.RefreshAll()` (the Data > Refresh All command), values read back from the sheets and "
            "the pivot table, compared with the CSV files of the same run. "
            "No macro is stored in the workbook. A manual click in the Excel window is recorded separately "
            "in [`../acceptance.md`](../acceptance.md).", "", "\n\n".join(sections), "",
            f"**Overall: {'PASS' if all_ok else 'FAIL'}.**", ""]
    RESULTS_PATH.write_text("\n".join(text), encoding="utf-8")
    strip_local_paths(WORKBOOK)
    print(f"\n-> {RESULTS_PATH.relative_to(PROJECT_ROOT).as_posix()}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
