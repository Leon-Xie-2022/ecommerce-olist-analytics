-- Demonstration and check: what happens when two "many rows per order" tables are joined directly.
--
-- Source totals are compared with
--   (a) a naive join  orders -> order_items -> payments  (items x payments rows per order)
--   (b) the correct way: aggregate each child table to one row per order, then join.
-- Expected: (b) equals the source totals; (a) inflates both money columns.

WITH source_totals AS (
    SELECT
        'source tables'                                     AS method,
        (SELECT COUNT(*) FROM orders)                       AS rows_after_join,
        (SELECT COUNT(*) FROM orders)                       AS distinct_orders,
        (SELECT ROUND(SUM(price), 2) FROM order_items)      AS product_value,
        (SELECT ROUND(SUM(payment_value), 2) FROM payments) AS payment_value
),

naive AS (
    SELECT
        'naive join'                     AS method,
        COUNT(*)                         AS rows_after_join,
        COUNT(DISTINCT o.order_id)       AS distinct_orders,
        ROUND(SUM(i.price), 2)           AS product_value,
        ROUND(SUM(p.payment_value), 2)   AS payment_value
    FROM orders AS o
    LEFT JOIN order_items AS i USING (order_id)
    LEFT JOIN payments    AS p USING (order_id)
),

pre_aggregated AS (
    SELECT
        'aggregate first, then join'     AS method,
        COUNT(*)                         AS rows_after_join,
        COUNT(DISTINCT o.order_id)       AS distinct_orders,
        ROUND(SUM(v.product_value), 2)   AS product_value,
        ROUND(SUM(p.payment_value), 2)   AS payment_value
    FROM orders AS o
    LEFT JOIN (SELECT order_id, SUM(price) AS product_value
               FROM order_items GROUP BY order_id) AS v USING (order_id)
    LEFT JOIN (SELECT order_id, SUM(payment_value) AS payment_value
               FROM payments GROUP BY order_id) AS p USING (order_id)
)

SELECT * FROM source_totals
UNION ALL SELECT * FROM naive
UNION ALL SELECT * FROM pre_aggregated;
