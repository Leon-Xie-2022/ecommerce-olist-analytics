# Weekly report: acceptance record

Status values: **Pass** (executed, result matches), **Fail**, **Not executed** (not run yet, no claim made).
Scripted checks and Excel checks are listed separately. Evidence paths are relative to the project root.
Run on 2026-10-20 on Windows 10, Python 3.12, DuckDB 1.5.6, Excel desktop 16.0.

## A. Script / SQL (automated)

| # | Step | Expected | Actual | Evidence | Status |
|---|---|---|---|---|---|
| A1 | Existing checks: `python src/validate.py` | 16/16 pass | 16/16 pass | console output | Pass |
| A2 | `python src/weekly_report.py --as-of 2018-03-11` | Publishes period folder + `latest/`, 15/15 reconciliations | Published in ~1.7 s, 15/15 | `output/weekly/as_of=2018-03-11/`, `run_log.csv` | Pass |
| A3 | Same for `--as-of 2018-03-18` | Second period kept next to the first | Both folders present, different results | `output/weekly/as_of=2018-03-18/` | Pass |
| A4 | Re-run the same cut-off | Identical data files, no added rows | Identical SHA-256, 602 exception rows before and after | `evidence/check_weekly_results.md` #2 | Pass |
| A5 | Missing input file | Exit 2, outputs unchanged | Exit 2, unchanged | same file, #3 | Pass |
| A6 | Missing required column | Exit 2, outputs unchanged | Exit 2, unchanged | #4 | Pass |
| A7 | Duplicate primary key (batch loaded twice) | Exit 2, outputs unchanged | Exit 2, unchanged | #5 | Pass |
| A8 | Output folder open in another program | Exit 4, outputs unchanged | Exit 4, unchanged (found during development, then fixed) | #6 | Pass |
| A9 | No future information: run on a snapshot with nothing after the cut-off and no `order_status` | Identical outputs | Identical for both cut-offs | #7, #8; `point_in_time.md` | Pass |
| A10 | Order grain vs item grain, report vs mart, table-to-table totals | All 15 checks PASS | 15/15 both periods | `reconciliation.csv` | Pass |
| A11 | Change request CR-001 (sample 30 → 50) | Only route ranking changes | 11 → 6 ranked; all counts and amounts identical | `change_request.md` | Pass |

## B. Excel / Power Query

| # | Step | Expected | Actual | Evidence | Status |
|---|---|---|---|---|---|
| B1 | Build workbook (`excel/build_workbook.ps1`) | .xlsx with 5 Power Query queries, 5 tables, 1 pivot, no macros | Built; file is .xlsx (macro-free format) | `excel/olist_weekly_ops.xlsx` | Pass |
| B2 | Publish 2018-03-11, Refresh All via Excel COM | Read Me shows 2018-03-11; all values = CSV | 13/13 comparisons match | `evidence/excel_refresh_results.md` step 1 | Pass |
| B3 | Publish 2018-03-18, Refresh All via Excel COM | New period appears; tables and pivot update; values = CSV | 13/13 match; pivot total 602 orders / BRL 83,189.63 | same file, step 2 | Pass |
| B4 | Formats readable (dates, BRL, %, filters) | Dates yyyy-mm-dd, money 2 dp, rates %, filter buttons | As expected | `reports/figures/excel_*.png` | Pass |
| B5 | **User opens the workbook and clicks Data > Refresh All by hand** | Same as B3 | — | to be recorded by the user | **Not executed** |
| B6 | **Workbook opened from another folder / another PC** | `OutputFolder` formula resolves to that copy's `output\weekly\latest\` | — | — | **Not executed** |
| B7 | **Privacy-level prompt on first manual refresh** | No prompt, or prompt answered once | Not seen under COM automation; may appear in the UI | — | **Not executed** |

B2–B3 use COM automation (`Workbook.RefreshAll()`, the command behind the Refresh All button) and read the
values back from the sheets. This is real Excel and real Power Query, but it is not the same as a person
clicking the button, so B5 stays open until the user does it.

## C. Not built (by design or left open)

- A "hindsight" check of how listed orders were finally resolved (delivered later vs cancelled) was not built.
- Power BI was not changed. The weekly report reconciles to `mart.fct_orders`, the same table the dashboard
  loads, under the weekly filter; dashboard and weekly numbers are not expected to be equal because the
  dashboard groups by purchase month.
