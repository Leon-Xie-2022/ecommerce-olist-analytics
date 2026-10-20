-- Weekly summary: one row per metric, three populations kept apart.
--   A. Orders placed in the window      purchase date in window; all orders known at the cut-off
--                                        (cancellations cannot be dated, so none are excluded)
--   B. Deliveries completed in window   delivery date in window; final on-time/late outcome known
--   C. Open orders at the cut-off       purchased by the cut-off, no delivery known; split by due state
--   D. Follow-up list                   counts of the exceptions table
-- Money names follow the mart: product_value = item prices, freight_value, payment_value. None is revenue.
-- Empty sets: counts and amounts are 0 (nothing happened); rates and medians stay NULL (undefined).

CREATE OR REPLACE TEMP TABLE weekly_summary AS
WITH placed AS (
    SELECT
        COUNT(*)                                AS orders,
        COUNT(*) FILTER (WHERE n_items > 0)     AS orders_with_items,
        COALESCE(SUM(n_items), 0)               AS item_units,
        COALESCE(SUM(product_value), 0)         AS product_value,
        COALESCE(SUM(freight_value), 0)         AS freight_value,
        COALESCE(SUM(payment_value), 0)         AS payment_value
    FROM pit_orders
    WHERE is_placed_in_window
),

delivered AS (
    SELECT
        COUNT(*)                                AS orders,
        COUNT(*) FILTER (WHERE is_late)         AS late_orders,
        AVG(CAST(is_late AS INT))               AS late_rate,
        MEDIAN(delivery_days)                   AS median_delivery_days,
        MEDIAN(days_late) FILTER (WHERE is_late) AS median_days_late_of_late
    FROM pit_orders
    WHERE is_delivered_in_window
),

open_orders AS (
    SELECT
        COUNT(*)                                                       AS orders,
        COUNT(*) FILTER (WHERE open_state = 'not yet due')             AS not_yet_due,
        COUNT(*) FILTER (WHERE open_state = 'overdue')                 AS overdue,
        COUNT(*) FILTER (WHERE open_state = 'overdue'
                         AND estimated_delivery_date >= (SELECT window_start FROM params)) AS overdue_new,
        COUNT(*) FILTER (WHERE open_state = 'stale overdue')           AS stale_overdue
    FROM pit_orders
    WHERE open_state <> 'delivered'
),

exc AS (
    SELECT
        COUNT(*)                                            AS total,
        COUNT(*) FILTER (WHERE exception_type = 'Overdue')  AS overdue,
        COUNT(*) FILTER (WHERE priority = 'P1')             AS p1,
        COUNT(*) FILTER (WHERE priority = 'P2')             AS p2,
        COUNT(*) FILTER (WHERE priority = 'P3')             AS p3,
        COUNT(*) FILTER (WHERE priority = 'P4')             AS p4,
        COALESCE(SUM(product_value), 0)                     AS product_value
    FROM exceptions
),

metrics (metric_order, section, metric, value, unit, definition) AS (
    SELECT 1,  'A. Orders placed in window', 'Orders placed', orders, 'orders',
           'Orders with purchase date in the window (any later status)' FROM placed
    UNION ALL SELECT 2,  'A. Orders placed in window', 'Orders with items', orders_with_items, 'orders',
           'Placed orders with at least one item row' FROM placed
    UNION ALL SELECT 3,  'A. Orders placed in window', 'Item units', item_units, 'items',
           'Item rows of placed orders' FROM placed
    UNION ALL SELECT 4,  'A. Orders placed in window', 'Product value', product_value, 'BRL',
           'Sum of item prices of placed orders' FROM placed
    UNION ALL SELECT 5,  'A. Orders placed in window', 'Freight value', freight_value, 'BRL',
           'Sum of item freight of placed orders' FROM placed
    UNION ALL SELECT 6,  'A. Orders placed in window', 'Payment value', payment_value, 'BRL',
           'Sum of payment rows of placed orders' FROM placed
    UNION ALL SELECT 7,  'B. Deliveries completed in window', 'Orders delivered', orders, 'orders',
           'Orders with customer delivery date in the window' FROM delivered
    UNION ALL SELECT 8,  'B. Deliveries completed in window', 'Late orders', late_orders, 'orders',
           'Delivered on a later calendar day than the estimated date' FROM delivered
    UNION ALL SELECT 9,  'B. Deliveries completed in window', 'Late rate', late_rate, 'rate',
           'Late orders / orders delivered' FROM delivered
    UNION ALL SELECT 10, 'B. Deliveries completed in window', 'Median delivery days', median_delivery_days, 'days',
           'Median days from purchase date to delivery date' FROM delivered
    UNION ALL SELECT 11, 'B. Deliveries completed in window', 'Median days late (late orders)',
           median_days_late_of_late, 'days', 'Median days after the estimated date, late orders only' FROM delivered
    UNION ALL SELECT 12, 'C. Open orders at cut-off', 'Open orders', orders, 'orders',
           'Purchased by the cut-off, no delivery recorded by the cut-off' FROM open_orders
    UNION ALL SELECT 13, 'C. Open orders at cut-off', 'Not yet due (outcome unknown)', not_yet_due, 'orders',
           'Estimated date after the cut-off day; right-censored, not counted as on time' FROM open_orders
    UNION ALL SELECT 14, 'C. Open orders at cut-off', 'Overdue (listed)', overdue, 'orders',
           'Estimated date passed 1..max_overdue_days ago' FROM open_orders
    UNION ALL SELECT 15, 'C. Open orders at cut-off', 'Overdue, became due this window', overdue_new, 'orders',
           'Overdue orders whose estimated date falls in the window' FROM open_orders
    UNION ALL SELECT 16, 'C. Open orders at cut-off', 'Stale overdue (status unknown)', stale_overdue, 'orders',
           'Estimated date passed more than max_overdue_days ago; not listed' FROM open_orders
    UNION ALL SELECT 17, 'D. Follow-up list', 'Exceptions listed', total, 'orders',
           'Rows in the exceptions table (overdue + early warnings)' FROM exc
    UNION ALL SELECT 18, 'D. Follow-up list', 'P1 overdue', p1, 'orders',
           'days_overdue >= p1_min_days_overdue' FROM exc
    UNION ALL SELECT 19, 'D. Follow-up list', 'P2 overdue', p2, 'orders',
           'days_overdue >= p2_min_days_overdue' FROM exc
    UNION ALL SELECT 20, 'D. Follow-up list', 'P3 overdue', p3, 'orders',
           'Other overdue orders' FROM exc
    UNION ALL SELECT 21, 'D. Follow-up list', 'P4 early warnings', p4, 'orders',
           'Not yet due, seller ship-by date passed, not handed to carrier' FROM exc
    UNION ALL SELECT 22, 'D. Follow-up list', 'Product value of listed orders', product_value, 'BRL',
           'Sum of item prices of exception orders' FROM exc
)

SELECT
    m.metric_order,
    m.section,
    m.metric,
    ROUND(CAST(m.value AS DOUBLE), CASE m.unit WHEN 'rate' THEN 4 ELSE 2 END) AS value,
    m.unit,
    m.definition,
    p.as_of_date,
    p.window_start,
    p.as_of_date AS window_end
FROM metrics      AS m
CROSS JOIN params AS p
ORDER BY m.metric_order;
