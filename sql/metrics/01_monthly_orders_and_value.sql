-- Metric 1: monthly orders, product value and freight, with month-over-month growth.
--
-- Grain of the result: one row per purchase month.
-- Definitions (docs/metric_definitions.md):
--   valid order    = order_status NOT IN ('canceled', 'unavailable')
--   product value  = SUM(order_items.price)          -- item sales value, BRL; not company revenue
--   freight value  = SUM(order_items.freight_value)  -- reported separately, never added to product value
--   month_status   = 'complete' for 2017-01 .. 2018-08; months outside this window have too few orders
--
-- order_items has many rows per order, so it is aggregated to one row per order (CTE order_value)
-- before joining to orders. That keeps COUNT(*) equal to the number of orders and keeps any
-- later join (payments, reviews) from multiplying rows.

WITH order_value AS (
    SELECT
        order_id,
        SUM(price)         AS product_value,
        SUM(freight_value) AS freight_value
    FROM order_items
    GROUP BY order_id
),

monthly AS (
    SELECT
        o.purchase_month,
        COUNT(*)                         AS valid_orders,
        COUNT(v.order_id)                AS orders_with_items,
        ROUND(SUM(v.product_value), 2)   AS product_value,
        ROUND(SUM(v.freight_value), 2)   AS freight_value
    FROM orders AS o
    LEFT JOIN order_value AS v USING (order_id)
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY o.purchase_month
),

with_previous AS (
    SELECT
        *,
        purchase_month BETWEEN DATE '2017-01-01' AND DATE '2018-08-01' AS is_complete,
        LAG(purchase_month) OVER (ORDER BY purchase_month) AS prev_month,
        LAG(product_value)  OVER (ORDER BY purchase_month) AS prev_product_value
    FROM monthly
)

-- Growth is shown only when the previous row really is the previous calendar month
-- (2016-11 has no orders, so LAG alone would compare 2016-12 with 2016-10) and both months are complete.
SELECT
    strftime(purchase_month, '%Y-%m') AS month,
    CASE WHEN is_complete THEN 'complete' ELSE 'incomplete' END AS month_status,
    valid_orders,
    orders_with_items,
    product_value,
    freight_value,
    CASE WHEN is_complete
          AND prev_month = purchase_month - INTERVAL 1 MONTH
          AND prev_month >= DATE '2017-01-01'
         THEN ROUND(100.0 * (product_value / prev_product_value - 1), 1)
    END AS product_value_mom_pct
FROM with_previous
ORDER BY purchase_month;
