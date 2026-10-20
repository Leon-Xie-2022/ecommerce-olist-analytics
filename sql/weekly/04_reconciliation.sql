-- Reconciliation: each check compares two independently computed numbers. status = 'FAIL' stops the
-- run before anything is published (src/weekly_report.py).
--
-- Mart checks use mart.fct_orders (the existing order mart) under the same date filter. The mart's
-- is_delivered also requires order_status = 'delivered'; the weekly report does not read status (it is
-- known only at extraction), so orders with a delivery date but a later status of 'canceled' are counted
-- by the report and not by the mart. That gap is computed from the mart and shown as expected_difference.

CREATE OR REPLACE TEMP TABLE reconciliation AS
WITH p AS (SELECT * FROM params),

summary AS (
    SELECT metric, value FROM weekly_summary
),

s AS (
    SELECT
        MAX(value) FILTER (WHERE metric = 'Orders placed')                  AS orders_placed,
        MAX(value) FILTER (WHERE metric = 'Product value')                  AS product_value,
        MAX(value) FILTER (WHERE metric = 'Freight value')                  AS freight_value,
        MAX(value) FILTER (WHERE metric = 'Payment value')                  AS payment_value,
        MAX(value) FILTER (WHERE metric = 'Orders delivered')               AS delivered,
        MAX(value) FILTER (WHERE metric = 'Late orders')                    AS late,
        MAX(value) FILTER (WHERE metric = 'Open orders')                    AS open_orders,
        MAX(value) FILTER (WHERE metric = 'Not yet due (outcome unknown)')  AS not_yet_due,
        MAX(value) FILTER (WHERE metric = 'Overdue (listed)')               AS overdue,
        MAX(value) FILTER (WHERE metric = 'Stale overdue (status unknown)') AS stale,
        MAX(value) FILTER (WHERE metric = 'Exceptions listed')              AS exceptions,
        MAX(value) FILTER (WHERE metric = 'Product value of listed orders') AS exc_product_value
    FROM summary
),

mart_placed AS (
    SELECT COUNT(*) AS orders, SUM(product_value) AS product_value,
           SUM(freight_value) AS freight_value, SUM(payment_value) AS payment_value
    FROM mart.fct_orders, p
    WHERE purchase_date BETWEEN p.window_start AND p.as_of_date
),

mart_delivered AS (
    SELECT
        COUNT(*) FILTER (WHERE is_delivered)                                   AS delivered,
        COUNT(*) FILTER (WHERE is_delivered AND is_late)                       AS late,
        COUNT(*) FILTER (WHERE NOT is_delivered)                               AS status_gap,
        COUNT(*) FILTER (WHERE NOT is_delivered AND delivered_date > estimated_delivery_date) AS late_gap
    FROM mart.fct_orders, p
    WHERE delivered_date BETWEEN p.window_start AND p.as_of_date
),

item_placed AS (
    SELECT SUM(i.price) AS product_value, SUM(i.freight_value) AS freight_value
    FROM pit_items AS i
    JOIN pit_orders AS o USING (order_id)
    WHERE o.is_placed_in_window
),

item_exceptions AS (
    SELECT SUM(i.price) AS product_value
    FROM pit_items AS i
    WHERE i.order_id IN (SELECT order_id FROM exceptions)
),

route AS (
    SELECT SUM(delivered_orders) AS delivered, SUM(late_orders) AS late FROM route_diagnosis
),

exc AS (
    SELECT COUNT(*) AS n_rows, COUNT(DISTINCT order_id) AS n_orders,
           COUNT(*) FILTER (WHERE exception_type = 'Overdue') AS overdue
    FROM exceptions
),

checks (check_order, check_name, source_a, value_a, source_b, value_b, expected_difference, note) AS (
    SELECT 1, 'Orders placed: report vs mart', 'weekly_summary', s.orders_placed,
           'mart.fct_orders (same purchase dates)', m.orders, 0, '' FROM s, mart_placed m
    UNION ALL SELECT 2, 'Product value placed: report vs mart', 'weekly_summary', s.product_value,
           'mart.fct_orders', m.product_value, 0, 'BRL' FROM s, mart_placed m
    UNION ALL SELECT 3, 'Freight value placed: report vs mart', 'weekly_summary', s.freight_value,
           'mart.fct_orders', m.freight_value, 0, 'BRL' FROM s, mart_placed m
    UNION ALL SELECT 4, 'Payment value placed: report vs mart', 'weekly_summary', s.payment_value,
           'mart.fct_orders', m.payment_value, 0, 'BRL' FROM s, mart_placed m
    UNION ALL SELECT 5, 'Product value placed: order grain vs item grain', 'weekly_summary', s.product_value,
           'pit_items (item rows)', i.product_value, 0, 'No join fan-out' FROM s, item_placed i
    UNION ALL SELECT 6, 'Freight value placed: order grain vs item grain', 'weekly_summary', s.freight_value,
           'pit_items (item rows)', i.freight_value, 0, 'No join fan-out' FROM s, item_placed i
    UNION ALL SELECT 7, 'Orders delivered: report vs mart', 'weekly_summary', s.delivered,
           'mart.fct_orders is_delivered (same delivery dates)', m.delivered, m.status_gap,
           'Expected gap = orders with a delivery date whose extract status is not delivered'
           FROM s, mart_delivered m
    UNION ALL SELECT 8, 'Late orders: report vs mart', 'weekly_summary', s.late,
           'mart.fct_orders is_late', m.late, m.late_gap, 'Same status gap, late orders only'
           FROM s, mart_delivered m
    UNION ALL SELECT 9, 'Orders delivered: summary vs route table', 'weekly_summary', s.delivered,
           'route_diagnosis (all rows)', r.delivered, 0, 'Includes MULTI-ORIGIN row' FROM s, route r
    UNION ALL SELECT 10, 'Late orders: summary vs route table', 'weekly_summary', s.late,
           'route_diagnosis (all rows)', r.late, 0, '' FROM s, route r
    UNION ALL SELECT 11, 'Open orders = not yet due + overdue + stale', 'weekly_summary', s.open_orders,
           'sum of the three open states', s.not_yet_due + s.overdue + s.stale, 0, '' FROM s
    UNION ALL SELECT 12, 'Overdue orders: summary vs exceptions', 'weekly_summary', s.overdue,
           'exceptions (Overdue rows)', e.overdue, 0, 'Every listed overdue order matches one rule' FROM s, exc e
    UNION ALL SELECT 13, 'Exceptions: one row per order', 'exceptions rows', e.n_rows,
           'distinct order_id', e.n_orders, 0, '' FROM exc e
    UNION ALL SELECT 14, 'Exceptions listed: summary vs table', 'weekly_summary', s.exceptions,
           'exceptions rows', e.n_rows, 0, '' FROM s, exc e
    UNION ALL SELECT 15, 'Product value of exceptions: order grain vs item grain', 'weekly_summary',
           s.exc_product_value, 'pit_items (item rows)', i.product_value, 0, 'No join fan-out'
           FROM s, item_exceptions i
)

SELECT
    c.check_order,
    c.check_name,
    c.source_a,
    ROUND(CAST(c.value_a AS DOUBLE), 2)                                AS value_a,
    c.source_b,
    ROUND(CAST(c.value_b AS DOUBLE), 2)                                AS value_b,
    -- + 0.0 turns a rounded -0.0 into 0.0
    ROUND(CAST(c.value_a AS DOUBLE) - CAST(c.value_b AS DOUBLE), 2) + 0.0 AS difference,
    CAST(c.expected_difference AS DOUBLE)                              AS expected_difference,
    CASE WHEN ABS(COALESCE(CAST(c.value_a AS DOUBLE), 0) - COALESCE(CAST(c.value_b AS DOUBLE), 0)
                  - c.expected_difference) < 0.005
              AND (c.value_a IS NULL) = (c.value_b IS NULL)
         THEN 'PASS' ELSE 'FAIL' END                                   AS status,
    c.note,
    p.as_of_date,
    p.window_start,
    p.as_of_date                                                       AS window_end
FROM checks AS c
CROSS JOIN params AS p
ORDER BY c.check_order;
