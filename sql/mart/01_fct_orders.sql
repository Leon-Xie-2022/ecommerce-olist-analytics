-- Order mart: exactly one row per order (99,441 rows), the main table for analysis and Power BI.
--
-- Each child table is reduced to the order grain in its own CTE BEFORE joining, so no join can
-- multiply rows (see sql/checks/fanout_demo.sql). src/validate.py reconciles counts and totals.
--
-- Child-table rules
--   items     : summed (product value, freight, item count, seller count)
--   payments  : summed; main payment type = type of the largest payment row
--   reviews   : one review per order = the most recently answered one (547 orders have 2-3)
--   customers : 1:1 on customer_id, adds the person-level customer_unique_id
-- customer_order_seq numbers each person's VALID orders by purchase time (1 = first purchase).

CREATE OR REPLACE TABLE fct_orders AS
WITH item_agg AS (
    SELECT
        order_id,
        COUNT(*)                  AS n_items,
        COUNT(DISTINCT seller_id) AS n_sellers,
        SUM(price)                AS product_value,
        SUM(freight_value)        AS freight_value
    FROM order_items
    GROUP BY order_id
),

payment_ranked AS (
    SELECT
        order_id,
        payment_type,
        payment_installments,
        payment_value,
        ROW_NUMBER() OVER (PARTITION BY order_id
                           ORDER BY payment_value DESC, payment_sequential) AS rn
    FROM payments
),

payment_agg AS (
    SELECT
        order_id,
        COUNT(*)                                    AS n_payments,
        SUM(payment_value)                          AS payment_value,
        MAX(payment_installments)                   AS max_installments,
        MAX(CASE WHEN rn = 1 THEN payment_type END) AS main_payment_type
    FROM payment_ranked
    GROUP BY order_id
),

review_latest AS (
    SELECT order_id, review_score
    FROM reviews
    QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id
                               ORDER BY review_answer_timestamp DESC, review_creation_date DESC,
                                        review_id) = 1
),

base AS (
    SELECT
        o.order_id,
        o.customer_id,
        c.customer_unique_id,
        c.customer_state,
        c.customer_city,
        o.order_status,
        o.order_status NOT IN ('canceled', 'unavailable')                    AS is_valid,
        o.order_purchase_timestamp                                           AS purchase_ts,
        CAST(o.order_purchase_timestamp AS DATE)                             AS purchase_date,
        CAST(o.purchase_month AS DATE)                                       AS purchase_month,
        o.purchase_month BETWEEN DATE '2017-01-01' AND DATE '2018-08-01'     AS is_complete_month,

        COALESCE(i.n_items, 0)                                               AS n_items,
        COALESCE(i.n_sellers, 0)                                             AS n_sellers,
        COALESCE(i.product_value, 0)                                         AS product_value,
        COALESCE(i.freight_value, 0)                                         AS freight_value,

        COALESCE(p.n_payments, 0)                                            AS n_payments,
        p.payment_value,
        p.main_payment_type,
        p.max_installments,

        o.order_status = 'delivered'
            AND o.order_delivered_customer_date IS NOT NULL                  AS is_delivered,
        CAST(o.order_estimated_delivery_date AS DATE)                        AS estimated_delivery_date,
        CAST(o.order_delivered_customer_date AS DATE)                        AS delivered_date,
        date_diff('day', o.order_purchase_timestamp,
                         o.order_delivered_customer_date)                    AS delivery_days,
        date_diff('day', CAST(o.order_purchase_timestamp AS DATE),
                         CAST(o.order_estimated_delivery_date AS DATE))      AS promised_days,
        date_diff('day', CAST(o.order_estimated_delivery_date AS DATE),
                         CAST(o.order_delivered_customer_date AS DATE))      AS days_late,

        r.review_score,
        o.flag_carrier_before_approval
    FROM orders AS o
    JOIN customers          AS c USING (customer_id)
    LEFT JOIN item_agg      AS i USING (order_id)
    LEFT JOIN payment_agg   AS p USING (order_id)
    LEFT JOIN review_latest AS r USING (order_id)
)

SELECT
    *,
    CASE WHEN is_delivered THEN days_late > 0 END                            AS is_late,
    CASE WHEN is_valid THEN
        ROW_NUMBER() OVER (PARTITION BY customer_unique_id, is_valid
                           ORDER BY purchase_ts, order_id)
    END                                                                      AS customer_order_seq
FROM base;
