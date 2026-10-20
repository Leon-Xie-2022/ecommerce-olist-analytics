# Weekly delivery operations report (phase 2)

A repeatable weekly report on top of the existing Olist mart: **historical cut-off → only data known then →
SQL weekly summary and follow-up list → Excel / Power Query refresh → reconciliation and run record.**
Independent practice with simulated requirements; historical replay, not a live system.

| Document | Content |
|---|---|
| [requirements.md](requirements.md) | Simulated users, weekly decisions, inputs, outputs, acceptance criteria |
| [point_in_time.md](point_in_time.md) | Cut-off and window rules, field-by-field audit, what cannot be rebuilt |
| [change_request.md](change_request.md) | CR-001: minimum route sample 30 → 50, traced end to end |
| [acceptance.md](acceptance.md) | Acceptance table: script and Excel steps, Pass / Not executed |
| [evidence/](evidence) | Scripted check results and Excel refresh comparison |

## Run

```powershell
python src/weekly_report.py --as-of 2018-03-11     # one period -> output/weekly/as_of=2018-03-11/ + latest/
python src/weekly_report.py --as-of 2018-03-18     # next period
python src/check_weekly.py                          # 8 scripted checks (temporary folders)
python src/verify_excel_refresh.py                  # Excel desktop: Refresh All per period, compare with CSV
```

Prerequisite: the main pipeline (`clean.py`, `build_db.py`) has been run. Parameters are in
`config/weekly_report.toml`; `--set key=value --label NAME` makes a what-if run under `what_if/NAME/`.
Exit codes: 0 published, 2 input problem, 3 reconciliation failed, 4 output folder in use.

Excel: open `excel/olist_weekly_ops.xlsx` from inside the project folder and click **Data → Refresh All**.
The yellow cell `OutputFolder` on the Read Me sheet points to `..\output\weekly\latest\` relative to the
workbook; type another path over it to read elsewhere. The M code is in [`excel/power_query/`](../../excel/power_query).
If the workbook ever has to be rebuilt: `powershell -ExecutionPolicy Bypass -File excel/build_workbook.ps1`.

Manual setup without the build script (any Excel 2016+): on a new sheet name a cell `OutputFolder` holding the
full path of `output\weekly\latest\`; for each `.pq` file use **Data → Get Data → From Other Sources → Blank
Query → Advanced Editor**, paste the code, name the query after the file, then **Close & Load** to a table;
insert a PivotTable from the `Exceptions` table (rows: priority, rule_id; values: count of order_id, sum of
product_value).

## 3-minute demo

1. **(30 s) The question.** "Each Monday operations needs to know which open orders to chase and which routes
   are slipping, using only what was known that day." Show `requirements.md`, mention it is simulated.
2. **(40 s) Time rules.** Show `00_point_in_time.sql`: future events set to NULL, `order_status` never read
   because it is the October 2018 status. Mention the snapshot test that gives identical results.
3. **(40 s) Run two weeks.** Run the command for 2018-03-11 and 2018-03-18; point at "15/15 reconciliation
   checks" and the two output folders. Re-run one: same files, no duplicates.
4. **(40 s) Excel.** Open the workbook, Refresh All, show the cut-off date change on Read Me, the Weekly Summary
   (late rate 7.8% → 12.3%, overdue orders 356 → 529), the Exceptions filters and the pivot.
5. **(30 s) Trust and change.** Reconciliation sheet (report vs mart, order vs item grain), then CR-001: one
   config value, only the route ranking changed, all amounts identical.

## Results for the two demo weeks

| Cut-off (window) | Orders placed | Delivered | Late rate | Open, overdue (listed) | Exceptions (P1) |
|---|---|---|---|---|---|
| 2018-03-11 (03-05 to 03-11) | 1,643 | 1,567 | 7.8% | 356 | 466 (154) |
| 2018-03-18 (03-12 to 03-18) | 1,595 | 1,483 | 12.3% | 529 | 602 (234) |

Highest-ranked route in both weeks: SP → RJ (23.7% then 44.1% late, 93 deliveries each week).
