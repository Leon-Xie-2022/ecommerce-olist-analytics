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

## Core metrics

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

## Customer and mix metrics

| Metric | Definition | SQL |
|---|---|---|
| Person | `customer_unique_id` (`customer_id` is one per order) | — |
| Return order | Valid order on a later calendar day than the person's first valid order (`fct_orders.is_return_order`) | `sql/mart/01_fct_orders.sql` |
| Repeat customer | Person with valid orders on 2+ different calendar days | `sql/mart/03_dim_customer.sql` |
| Cohort | Month of a person's first valid order | `sql/metrics/08_cohort_retention.sql` |
| Cohort repeat rate (N months) | Share of the cohort with a return order by the end of month N after the cohort month; blank if month N is after 2018-08 | same |
| Main payment type | Type of the order's largest payment row | `sql/mart/01_fct_orders.sql` |
| Delivery bucket | Days between delivery date and estimated date, in 6 bands (10+ early … 8+ late) | same |
| Category share | Category product value / all categories, items of valid orders | `sql/metrics/04_category_mix.sql` |
| Seller decile | Sellers ranked by product value, split into 10 equal-count groups (`NTILE`) | `sql/metrics/09_seller_concentration.sql` |

### Why same-day orders are not repeat purchases

823 of the 2,888 people with two or more valid orders placed all of them on the same day: one shopping session
split into several orders, for example by seller. Counting those people as repeat customers would raise the repeat
rate from 2.2% to 3.0% of customers (+40%).
