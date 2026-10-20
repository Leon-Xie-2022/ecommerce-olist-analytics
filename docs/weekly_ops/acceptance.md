# Weekly report: acceptance record

Status values: **Pass** (executed, result matches), **Fail**, **Not executed** (not run yet, no claim made).
Scripted checks and Excel checks are listed separately. Evidence paths are relative to the project root.
Run on 2026-10-20 on Windows 10, Python 3.12, DuckDB 1.5.6, Excel desktop 16.0. Re-run the same day after
fixing four defects found in code review (section D).

## A. Script / SQL (automated)

| # | Step | Expected | Actual | Evidence | Status |
|---|---|---|---|---|---|
| A1 | Existing checks: `python src/validate.py` | 16/16 pass | 16/16 pass | console output | Pass |
| A2 | `python src/weekly_report.py --as-of 2018-03-11` | Publishes period folder + `latest/`, 17/17 reconciliations | Published in ~2 s, 17/17 | `output/weekly/as_of=2018-03-11/`, `run_log.csv` | Pass |
| A3 | Same for `--as-of 2018-03-18` | Second period kept next to the first | Both folders present, different results | `output/weekly/as_of=2018-03-18/` | Pass |
| A4 | Re-run the same cut-off | Identical data files, no added rows | Identical SHA-256, 602 exception rows before and after | `evidence/check_weekly_results.md` #2 | Pass |
| A5 | Missing input file | Exit 2, outputs unchanged | Exit 2, unchanged | same file, #3 | Pass |
| A6 | Missing required column | Exit 2, outputs unchanged | Exit 2, unchanged | #4 | Pass |
| A7 | Duplicate primary key (batch loaded twice) | Exit 2, outputs unchanged | Exit 2, unchanged | #5 | Pass |
| A8 | Output folder open in another program | Exit 4, outputs unchanged | Exit 4, unchanged (found during development, then fixed) | #6 | Pass |
| A9 | No future information: run on a snapshot with nothing after the cut-off and no `order_status` | Identical outputs | Identical for both cut-offs | #13, #14; `point_in_time.md` | Pass |
| A10 | Order grain vs item grain, report vs mart (incl. listed orders bought before the window), table-to-table totals | All 17 checks PASS | 17/17 both periods | `reconciliation.csv` | Pass |
| A11 | Change request CR-001 (sample 30 → 50) | Only route ranking changes | 11 → 6 ranked; all counts and amounts identical | `change_request.md` | Pass |
| A12 | `latest/` open in another program | Exit 4; period folder and `latest/` both keep the previous run | As expected, no staging/.old left | `evidence/check_weekly_results.md` #7 | Pass |
| A13 | Duplicate payment row (same order and sequence) | Exit 2 | Exit 2 | #8 | Pass |
| A14 | Extra payment row on a listed order bought before the window | Exit 3 (exceptions vs mart) | Exit 3 | #9 | Pass |
| A15 | Corrupt input file | Exit 2, FAILED line in run log, nothing left behind | As expected | #10 | Pass |
| A16 | Week with no deliveries (cut-off 2016-09-04) | Publishes; counts 0, rates blank, all checks PASS | As expected | #11 | Pass |
| A17 | Invalid parameters (p1 below p2, sample 0, negative threshold) | Exit 2 before running | Exit 2 ×3 | #12 | Pass |

## B. Excel / Power Query

| # | Step | Expected | Actual | Evidence | Status |
|---|---|---|---|---|---|
| B1 | Build workbook (`excel/build_workbook.ps1`) | .xlsx with 5 Power Query queries, 5 tables, 1 pivot, no macros | Built; file is .xlsx (macro-free format) | `excel/olist_weekly_ops.xlsx` | Pass |
| B2 | Publish 2018-03-11, Refresh All via Excel COM | Read Me shows 2018-03-11; all values = CSV | 13/13 comparisons match | `evidence/excel_refresh_results.md` step 1 | Pass |
| B3 | Publish 2018-03-18, Refresh All via Excel COM | New period appears; tables and pivot update; values = CSV | 13/13 match; pivot total 602 orders / BRL 83,189.63 | same file, step 2 | Pass |
| B4 | Formats readable (dates, BRL, %, filters) | Dates yyyy-mm-dd, money 2 dp, rates %, filter buttons | As expected | `reports/figures/excel_*.png` | Pass |
| B5 | User opens the workbook and clicks Data > Refresh All by hand (2026-10-21) | Publish 2018-03-11, refresh: Read Me shows 2018-03-11 and 17 of 17 PASS; publish 2018-03-18, refresh: date changes, late rate 7.8% -> 12.3% | As expected, reported by the user; both runs SUCCESS in run_log.csv | user report; `output/weekly/run_log.csv` (2026-10-21 lines) | Pass |
| B6 | Workbook opened from another folder (fresh git clone, 2026-10-21) | `OutputFolder` resolves to that copy's `output\weekly\latest\` | Resolved to the clone's folder; Refresh All loaded 2018-03-18, 602 exceptions, 17 of 17 PASS. Re-running both cut-offs in the clone reproduced every data file byte for byte | `excel/refresh_and_read.ps1` run in the clone | Pass |
| B7 | Security / privacy prompts on manual refresh | Refresh completes, at most a one-time prompt | Refresh completed in the user's Excel; no blocking prompt reported. Excel asks to save on close (expected: refresh changes the file) | user report | Pass |

B2–B3 use COM automation (`Workbook.RefreshAll()`, the command behind the Refresh All button) and read the
values back from the sheets. This is real Excel and real Power Query, but it is not the same as a person
clicking the button, so the user repeated it by hand on 2026-10-21 (B5, B7). After a manual save the workbook again caches the local folder path in the OutputFolder cell; it is stripped before committing (`strip_local_paths` in `src/verify_excel_refresh.py`).

## D. Defects found in code review (2026-10-20) and fixed

| # | Defect | Fix | Regression test |
|---|---|---|---|
| 1 | If `latest/` was locked, the period folder was already replaced while Excel kept reading the old week, and the message said nothing was published | Both staging folders are prepared first and swapped as one unit; any failed rename undoes the earlier swaps | A12 |
| 2 | A duplicated payment row doubled a listed order's payment value and all 15 checks still passed (they only covered orders placed in the window) | Payments key `(order_id, payment_sequential)` checked on input (not de-duplicated by order: split payments are legal); two new checks compare listed orders with the mart | A13, A14 |
| 3 | A week with no deliveries failed reconciliation (`0` vs `NULL` from an empty `SUM`) | Counts and amounts of empty sets are 0; rates and medians stay blank | A16 |
| 4 | A corrupt input raised a DuckDB traceback (exit 1) with no run-log line | Input read errors become exit 2; any other data/database/file error exit 5; connection closed, staging removed, attempt logged | A15 |
| — | Negative or inverted thresholds were accepted | Parameter rules checked before running | A17 |

Not covered by a test: corruption inside a data page that only appears during the SQL run (handled by the
exit 5 path, but not reproduced).

## C. Not built (by design or left open)

- A "hindsight" check of how listed orders were finally resolved (delivered later vs cancelled) was not built.
- Power BI was not changed. The weekly report reconciles to `mart.fct_orders`, the same table the dashboard
  loads, under the weekly filter; dashboard and weekly numbers are not expected to be equal because the
  dashboard groups by purchase month.
