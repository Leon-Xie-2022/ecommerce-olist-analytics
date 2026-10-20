-- Analysis 5: delivery performance and reviews by customer state.
--
-- Grain: one row per customer state (27 states).
-- Population: delivered orders (valid, with a delivery date) in complete months.
-- avg_review uses only delivered orders that have a review.
-- States with fewer than 300 delivered orders are flagged: their rates move a lot with a few orders.

SELECT
    customer_state,
    COUNT(*)                                                     AS delivered_orders,
    ROUND(AVG(delivery_days), 1)                                 AS avg_delivery_days,
    ROUND(AVG(promised_days), 1)                                 AS avg_promised_days,
    ROUND(100.0 * AVG(CASE WHEN is_late THEN 1 ELSE 0 END), 1)   AS late_rate_pct,
    ROUND(AVG(review_score), 2)                                  AS avg_review,
    COUNT(*) < 300                                               AS small_sample,
    RANK() OVER (ORDER BY AVG(CASE WHEN is_late THEN 1 ELSE 0 END) DESC) AS late_rate_rank
FROM fct_orders
WHERE is_delivered AND is_complete_month
GROUP BY customer_state
ORDER BY late_rate_pct DESC;
