# Metric definitions

All amounts are in Brazilian reais (BRL), nominal. None of the money metrics is company revenue:
Olist is a marketplace and the data has no commission, cost or margin fields.

## Common rules

| Term | Definition | Why |
|---|---|---|
| Month | Calendar month of `order_purchase_timestamp` | Every order has a purchase time; delivery dates are missing for undelivered orders |
| Complete months | 2017-01 to 2018-08 | 2016-09 to 2016-12 have 1–324 orders per month (2016-11 has none); 2018-09 and 2018-10 have 16 and 4. These are partial data-collection periods, not real demand |
| Valid order | `order_status NOT IN ('canceled', 'unavailable')` | Canceled and unavailable orders never became sales; 603 of the 609 unavailable orders have no items at all |
| Delivered order | `order_status = 'delivered'` and `order_delivered_customer_date IS NOT NULL` | 8 delivered orders have no delivery date and cannot be timed |

## Metrics in stage 1

| # | Metric | Formula | Population | SQL |
|---|---|---|---|---|
| 1 | Valid orders | `COUNT(*)` of orders | Valid orders | `sql/metrics/01_monthly_orders_and_value.sql` |
| 1 | Product value | `SUM(order_items.price)` | Items of valid orders | same |
| 1 | Freight value | `SUM(order_items.freight_value)` | Items of valid orders | same |
| 1 | Product value MoM % | this month / previous calendar month − 1 | Complete months only | same |
| 2 | AOV (product) | product value / orders with items | Valid orders, complete months | `sql/metrics/02_average_order_value.sql` |
| 2 | AOV (payment) | `SUM(payment_value)` / orders with payments | same | same |
| 2 | Items per order | item rows / orders with items | same | same |
| 3 | Delivery days | days from purchase to `order_delivered_customer_date` | Delivered orders, complete months | `sql/metrics/03_delivery_time_and_late_rate.sql` |
| 3 | Late rate | delivered orders with delivery **date** > estimated **date**, ÷ delivered orders | same | same |

### Notes

- **Product value vs payment value.** Payment value includes freight and can include instalment interest and
  voucher use, so AOV (payment) is higher than AOV (product). For 303 orders the payment total differs from
  price + freight by more than 0.01 (see `reports/data_quality_report.md`). The two are never mixed in one metric.
- **Late by calendar date.** The estimated delivery date has no time of day (stored as 00:00). Comparing timestamps
  would mark an order delivered at 15:00 on the promised day as late, so both sides are cast to `DATE`.
- **Undelivered orders and recent months.** Delivery metrics only see delivered orders. The share of valid
  orders not yet delivered is 0.8–4.7% in every complete month, with no rise at the end of the data,
  so the shorter delivery times in mid-2018 are not just missing slow orders.
- **Average vs median.** Order value and delivery days are right-skewed, so medians are reported next to averages.
