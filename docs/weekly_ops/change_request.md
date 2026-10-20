# Change request CR-001 (simulated): raise the route minimum sample from 30 to 50

> Simulated requirement change for practice; no real requester.

| Step | Record |
|---|---|
| Request | "Routes with 30–49 deliveries in a week still swing a lot from week to week. Only rank routes with at least 50 deliveries." |
| Where it changes | One parameter: `min_route_sample` in [`config/weekly_report.toml`](../../config/weekly_report.toml), read by [`sql/weekly/02_route_diagnosis.sql`](../../sql/weekly/02_route_diagnosis.sql) via `getvariable('min_route_sample')`. No SQL or Python edit. |
| How it was tested | What-if run, kept apart from the official outputs: `python src/weekly_report.py --as-of 2018-03-18 --set min_route_sample=50 --label CR-001` → `output/weekly/what_if/CR-001/as_of=2018-03-18/` (does not touch `latest/`). |
| Expected change | Only the route table's `meets_min_sample`, `sample_note` and `late_rate_rank` columns change. Fewer routes ranked. Every count and amount stays the same. |
| Actual result | Ranked routes 11 → 6; orders on ranked routes 1,027 → 843 of 1,483 delivered (69% → 57%). The five routes no longer ranked (SP→SC, SP→GO, SP→BA, MG→SP, SP→DF; 33–41 orders each) are still shown, now labelled "Small sample (< 50) - not ranked". SP→RJ stays rank 1 (44.1% late on 93 orders). |
| Reconciliation | `weekly_summary.csv`, `exceptions.csv` and `reconciliation.csv` are byte-identical to the official 2018-03-18 run (SHA-256 compared). Route table: same 117 rows, 1,483 delivered, 182 late, BRL 195,454.33 product value in both versions. 17/17 reconciliation checks pass (re-run after the 2026-10-20 fixes). |
| Trade-off | Higher threshold = fewer, more stable rankings but less coverage. Three of the dropped routes had above-average late rates (SP→SC 23%, SP→GO 22%, SP→BA 20%), so they would no longer be flagged by rank; a reviewer would still see them in the table. 50 is not an optimised value either. |
| Status | Evaluated, not adopted: the official configuration stays at 30. To adopt, change the one line in the config and re-run both periods. |

Run evidence: `output/weekly/what_if/CR-001/as_of=2018-03-18/run_manifest.json` (parameters, input and output
checksums) and the `CR-001` line in `output/weekly/run_log.csv`.
