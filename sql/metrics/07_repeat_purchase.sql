-- Analysis 7: repeat purchase — how many people come back, and how much value repeat buyers bring.
--
-- Person = customer_unique_id (customer_id is one per order and would show zero repeat buyers).
-- Visit  = a calendar day with at least one valid order. Several orders on the same day are one visit
--          (869 people only "repeated" on their first day — a split basket, not a return).
-- Population: valid orders, all months (a return may fall outside the complete window).
-- Grain: one row per purchase-days bucket; days_first_to_second_visit is a summary repeated per row.

WITH visit_gaps AS (                   -- days from first to second purchase day, per person
    SELECT
        customer_unique_id,
        date_diff('day', MIN(purchase_date),
                  MIN(purchase_date) FILTER (WHERE is_return_order)) AS days_to_second_visit
    FROM fct_orders
    WHERE is_valid
    GROUP BY customer_unique_id
),

summary AS (
    SELECT
        MEDIAN(days_to_second_visit)                                  AS median_days,
        ROUND(100.0 * AVG(CASE WHEN days_to_second_visit <= 90 THEN 1 ELSE 0 END)
              FILTER (WHERE days_to_second_visit IS NOT NULL), 1)     AS pct_within_90d
    FROM visit_gaps
)

SELECT
    CASE WHEN n_purchase_days >= 3 THEN '3+' ELSE CAST(n_purchase_days AS VARCHAR) END AS purchase_days,
    COUNT(*)                                                                    AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)                          AS customer_share_pct,
    CAST(SUM(n_orders) AS INTEGER)                                              AS orders,
    ROUND(SUM(total_product_value), 2)                                          AS product_value,
    ROUND(100.0 * SUM(total_product_value) / SUM(SUM(total_product_value)) OVER (), 2) AS value_share_pct,
    (SELECT median_days FROM summary)                                           AS median_days_to_second_visit,
    (SELECT pct_within_90d FROM summary)                                        AS second_visit_within_90d_pct
FROM dim_customer
GROUP BY 1
ORDER BY 1;
