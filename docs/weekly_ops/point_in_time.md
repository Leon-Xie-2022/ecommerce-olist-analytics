# Weekly report: time definitions and what was knowable at the cut-off

The weekly report replays history: for a cut-off date `as_of_date` it should show only what an analyst
could have known **at the end of that day**. This page states the time rules and audits every field used.

## Time rules

| Item | Rule |
|---|---|
| Cut-off date | `as_of_date` from `config/weekly_report.toml` or `--as-of`. Never the computer's date. |
| Cut-off instant | `as_of_date + 1 day` at 00:00. An event is known only if its timestamp is **strictly earlier**. |
| Window | The `window_days` (default 7) calendar days ending on `as_of_date`, **both ends inclusive**. Example: cut-off 2018-03-11 → window 2018-03-05 to 2018-03-11 (Mon–Sun). |
| Calendar / time zone | Dataset-local calendar dates. Timestamps carry no time zone (they appear to be Brazilian local time); no conversion is applied. |
| Late | Delivered on a later **calendar day** than the estimated date (the estimate has no time of day). Same rule as the existing mart. |
| Days overdue | For an open order: `as_of_date − estimated date + 1`. An order due on the cut-off day and still undelivered at the end of it will be at least 1 day late. |

The SQL enforces this in one place, [`sql/weekly/00_point_in_time.sql`](../../sql/weekly/00_point_in_time.sql):
orders purchased after the cut-off are dropped and every later event timestamp is set to NULL before any
metric is computed. [`src/check_weekly.py`](../../src/check_weekly.py) tests it independently: it builds a
physical snapshot of the inputs that contains nothing dated after the cut-off and no `order_status`, runs the
report on it and gets byte-identical outputs (check 7 in
[`evidence/check_weekly_results.md`](evidence/check_weekly_results.md)).

## Field audit

| Field | Known at cut-off? | How it is used |
|---|---|---|
| `order_purchase_timestamp` | Yes, if before the cut-off | Order exists; "placed in window" |
| `order_approved_at` | Yes, if before the cut-off; else NULL | Rule R3 (payment not approved), R4 |
| `order_delivered_carrier_date` | Yes, if before the cut-off; else NULL | Rules R1/R2 (in transit vs not shipped) |
| `order_delivered_customer_date` | Yes, if before the cut-off; else NULL | Delivered vs open; late; delivery days |
| `order_estimated_delivery_date` | **Assumed** known from purchase | Due date, overdue. The data keep one value; if the estimate was ever revised, the revision history is lost |
| `shipping_limit_date` (items) | **Assumed** known from approval | Rule R4 (seller ship-by date missed) |
| Items, prices, freight, sellers | Assumed fixed from purchase | Product/freight value, route, seller attribution |
| Payments | Assumed fixed from purchase (no timestamp) | Payment value |
| `order_status` | **No** — status at extraction (Oct 2018) | **Not used** by the report; used only in reconciliation to explain the gap to the mart |
| Cancellation | **No** — no cancellation date exists | Cannot be reconstructed (see below) |
| Reviews | Answer timestamp exists | Not used: reviews arrive after delivery and would be immature for the latest week |

## States that cannot be rebuilt

- **Cancelled before the cut-off?** Unknown. An order cancelled in, say, February looks exactly like a stuck
  order on 11 March. The follow-up list is therefore a **historical diagnostic list**, not a reconstruction of a
  live alert queue: some listed orders were probably already cancelled. Rule R3 (payment never approved) is the
  group most likely to be cancellations, and its suggested action is to check that first.
- **Stale overdue orders.** Orders overdue for more than `max_overdue_days` (default 30) accumulate across
  the whole history (mostly old cancellations). They are counted in the summary as "stale overdue (status
  unknown)" and not listed.
- **Revised delivery estimates and status changes after delivery** are not visible; the single stored value is
  used.

This is not an exact production snapshot; it is the closest reconstruction the public data allow.

## Two populations, two denominators

| | Deliveries completed in window (retrospective) | Open orders at cut-off (follow-up) |
|---|---|---|
| Who | Orders whose delivery date is in the window | Orders purchased by the cut-off with no known delivery |
| Denominator | Orders delivered in the window | Open orders, split into not yet due / overdue / stale |
| Outcome | Final: on time or late | Not final. "Not yet due" = right-censored, outcome unknown, never counted as on time |
| Information time | Fully known at the cut-off | Partial; may change after the cut-off |

The completed-delivery late rate is "late among deliveries that **arrived** this week". It is not a
purchase-cohort late rate: a slow order bought weeks ago is counted in the week it arrives.

## Change to an existing definition and its impact

The mart's `is_delivered` requires `order_status = 'delivered'`. Status is only known at extraction, so the
weekly report defines "delivered" by the delivery timestamp alone. Orders that have a delivery date but a later
status of `canceled` (6 in the whole dataset) are therefore counted as delivered by the report and not by the
mart. The reconciliation sheet computes this gap from the mart as the *expected difference*; in both demo
weeks it is 0. The existing mart and dashboard are unchanged.
