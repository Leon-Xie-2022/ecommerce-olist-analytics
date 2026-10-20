-- Metric 2: average order value (AOV) per month, from items and from payments.
--
-- Grain of the result: one row per complete purchase month (2017-01 .. 2018-08).
-- AOV (product)  = product value / orders with items      -- what the basket is worth
-- AOV (payment)  = payment value / orders with payments   -- what the customer paid, incl. freight,
--                                                            instalment interest and vouchers
-- Both child tables (order_items, payments) are aggregated to one row per order BEFORE the join.
-- Joining them directly on order_id would multiply rows (items x payments) and inflate both sums.

WITH order_value AS (
    SELECT order_id,
           SUM(price) AS product_value,
           COUNT(*)   AS n_items
    FROM order_items
    GROUP BY order_id
),

order_payment AS (
    SELECT order_id,
           SUM(payment_value) AS payment_value
    FROM payments
    GROUP BY order_id
),

order_level AS (                       -- one row per valid order
    SELECT o.order_id,
           o.purchase_month,
           v.product_value,
           v.n_items,
           p.payment_value
    FROM orders AS o
    LEFT JOIN order_value   AS v USING (order_id)
    LEFT JOIN order_payment AS p USING (order_id)
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
      AND o.purchase_month BETWEEN DATE '2017-01-01' AND DATE '2018-08-01'
)

SELECT
    strftime(purchase_month, '%Y-%m')  AS month,
    COUNT(product_value)               AS orders_with_items,
    ROUND(AVG(product_value), 2)       AS aov_product,
    ROUND(MEDIAN(product_value), 2)    AS median_product_value,
    ROUND(AVG(n_items), 3)             AS avg_items_per_order,
    ROUND(AVG(payment_value), 2)       AS aov_payment
FROM order_level
GROUP BY purchase_month
ORDER BY purchase_month;
