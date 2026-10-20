-- Analysis 13: split orders and "missing item" complaints.
--
-- Orders with several items or several sellers get far more 1-2 star reviews even though they are
-- rarely late (sql/models + src/review_drivers.py). This checks the review text for why.
--
-- Population: delivered orders in complete months with a review.
-- missing_item_pct = share of low reviews WITH a comment whose text matches a Portuguese keyword
--   pattern for "did not receive / only received / missing / one of the products". A keyword match is
--   a heuristic: it misses some complaints and catches a few unrelated ones, so read it as a
--   comparison between groups, not as an exact count.

WITH orders AS (
    SELECT
        order_id,
        review_score,
        is_late,
        CASE
            WHEN n_sellers > 1 THEN '3. several sellers'
            WHEN n_items > 1   THEN '2. several items, one seller'
            ELSE                    '1. one item'
        END AS order_type
    FROM fct_orders
    WHERE is_delivered AND is_complete_month AND review_score IS NOT NULL
),

review_text AS (                       -- one comment per order (an order can have up to 3 reviews)
    SELECT order_id, ANY_VALUE(lower(review_comment_message)) AS msg
    FROM reviews
    WHERE review_comment_message IS NOT NULL
    GROUP BY order_id
)

SELECT
    o.order_type,
    COUNT(*)                                                                   AS orders,
    ROUND(100.0 * AVG(CASE WHEN o.is_late THEN 1 ELSE 0 END), 1)               AS late_pct,
    ROUND(100.0 * AVG(CASE WHEN o.review_score <= 2 THEN 1 ELSE 0 END), 1)     AS low_review_pct,
    COUNT(*) FILTER (WHERE o.review_score <= 2 AND t.msg IS NOT NULL)          AS low_reviews_with_text,
    ROUND(100.0 * AVG(CASE WHEN regexp_matches(t.msg,
              '(n[aã]o receb|s[oó] receb|receb[ie] (s[oó]|apenas)|falt(ou|ando|a um|a o)'
              || '|apenas um|um dos produtos|veio s[oó]|n[aã]o (veio|chegou) (o|um|a))')
              THEN 1 ELSE 0 END)
          FILTER (WHERE o.review_score <= 2 AND t.msg IS NOT NULL), 1)        AS missing_item_pct
FROM orders AS o
LEFT JOIN review_text AS t USING (order_id)
GROUP BY o.order_type
ORDER BY o.order_type;
