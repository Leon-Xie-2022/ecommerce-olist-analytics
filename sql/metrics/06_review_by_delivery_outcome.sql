-- Analysis 6: review score by delivery outcome (association, not causation).
--
-- Grain: one row per delivery bucket.
-- Population: delivered orders with a review, complete months.
-- Bucket by days_late = delivered date - estimated date (negative = early).
-- low_score_pct = share of 1-2 star reviews.
-- Late orders differ from on-time ones in other ways too (region, product, season), so this table
-- shows that low scores and lateness go together; it does not show how much fixing lateness would help.

WITH bucketed AS (                     -- delivery_bucket is defined once, in sql/mart/01_fct_orders.sql
    SELECT review_score, delivery_bucket
    FROM fct_orders
    WHERE is_delivered AND is_complete_month AND review_score IS NOT NULL
)

SELECT
    delivery_bucket,
    COUNT(*)                                                           AS orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)                 AS share_of_orders_pct,
    ROUND(AVG(review_score), 2)                                        AS avg_review,
    ROUND(100.0 * AVG(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END), 1) AS low_score_pct,
    ROUND(100.0 * AVG(CASE WHEN review_score = 5 THEN 1 ELSE 0 END), 1)  AS five_star_pct
FROM bucketed
GROUP BY delivery_bucket
ORDER BY delivery_bucket;
