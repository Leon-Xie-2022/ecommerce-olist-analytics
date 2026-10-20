# Weekly delivery operations report — simulated business requirement

> **Independent practice / simulated requirements.** There is no real client, user or go-live. The "users" and
> "decisions" below are assumptions written to give the build clear acceptance criteria. Olist data are
> historical (2016–2018); each run replays a past week as if the report had been produced at that time.

## Users and the weekly decision

| User (assumed) | Decision each Monday | What they need |
|---|---|---|
| Marketplace operations analyst | Which open orders to chase this week, and with whom (seller, carrier, payments) | A ranked follow-up list with the evidence and the rule behind each row |
| Logistics / seller-performance lead | Which delivery routes to raise with carriers or sellers | Last week's completed deliveries by route, with late rate **and sample size** |
| Team lead | Is the operation getting better or worse; can the numbers be trusted | A one-page weekly summary that reconciles to the existing data mart |

## Inputs

- Clean Olist tables from the existing pipeline (`data/processed/*.parquet`): orders, order items, payments,
  customers, sellers. SHA-256 of each input is recorded in every run manifest.
- The existing order mart (`data/processed/olist.duckdb`, table `fct_orders`) — used **only for reconciliation**.
- Configuration (`config/weekly_report.toml`): cut-off date, window length, minimum route sample,
  overdue look-back and priority thresholds. The cut-off is never taken from the computer clock.

## Outputs (one folder per cut-off date, plus `latest/` for Excel)

| File | Grain | Content |
|---|---|---|
| `weekly_summary.csv` | one row per metric | orders placed, deliveries completed, open orders at cut-off, exception counts |
| `route_diagnosis.csv` | one row per seller-state → customer-state route | delivered orders, late orders, late rate, sample flag |
| `exceptions.csv` | one row per order | follow-up list: rule, evidence, suggested action, priority |
| `reconciliation.csv` | one row per check | weekly figures vs mart, order vs item grain, table-to-table totals |
| `run_info.csv`, `run_manifest.json` | one per run | parameters, input/output checksums, checks, timing |

An Excel workbook (`excel/olist_weekly_ops.xlsx`) loads the `latest/` CSVs with Power Query.

## Acceptance criteria

1. One command produces all outputs for a given cut-off date; two consecutive weeks can be produced and kept.
2. No figure or list row uses information dated after the cut-off (delivery, carrier hand-over, approval).
   Fields that cannot be reconstructed at the cut-off (order status, cancellation) are not used and are listed.
3. Completed-delivery metrics and open-order follow-up are separate, with their own populations; orders not
   yet due are reported as "outcome unknown", never as on time.
4. Routes below the minimum sample (default 30, a demonstration setting) are shown but flagged and not ranked.
5. Every exception row has an order ID, evidence, the rule that fired, a suggested (not assigned) action and a
   priority computed by a written rule.
6. Order-grain and item-grain money totals agree; weekly totals agree with the existing mart under the same filter.
7. Re-running the same cut-off and configuration gives identical data files and does not duplicate rows.
   A missing input file or column stops the run and leaves the last successful output untouched.
8. In Excel, **Data → Refresh All** loads the newest published run; the summary, exceptions, pivot and
   reconciliation sheets match the CSV files.

## Out of scope

Real-time ingestion, scheduling, web apps, cloud deployment, forecasting models, named owners or case
outcomes, and any claim of business impact.
