-- Customer dimension: one row per person (customer_unique_id) with at least one valid order.
-- cohort_month = month of the first valid purchase. State is taken from the first valid order.
-- is_repeat_customer = bought on 2+ different calendar days (same-day extra orders are one visit).

CREATE OR REPLACE TABLE dim_customer AS
SELECT
    customer_unique_id,
    MIN(purchase_month)                                           AS cohort_month,
    MIN(purchase_ts)                                              AS first_purchase_ts,
    MAX(purchase_ts)                                              AS last_purchase_ts,
    COUNT(*)                                                      AS n_orders,
    COUNT(DISTINCT purchase_date)                                 AS n_purchase_days,
    SUM(product_value)                                            AS total_product_value,
    MAX(CASE WHEN customer_order_seq = 1 THEN customer_state END) AS first_order_state,
    COUNT(DISTINCT purchase_date) > 1                             AS is_repeat_customer
FROM fct_orders
WHERE is_valid
GROUP BY customer_unique_id;
