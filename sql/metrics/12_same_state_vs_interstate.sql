-- Analysis 12: delivery for same-state vs interstate orders.
--
-- Population: delivered orders in complete months whose items all come from sellers in ONE state
-- (multi-seller-state orders, ~1%, are excluded so each order has a single route).
-- route = 'same state' if seller state = customer state, else 'interstate'.
-- Also split by whether the customer is in SP (São Paulo), where most sellers are located.

WITH order_seller_state AS (
    SELECT order_id, MIN(seller_state) AS seller_state
    FROM fct_order_items
    GROUP BY order_id
    HAVING COUNT(DISTINCT seller_state) = 1
),

routed AS (
    SELECT
        o.*,
        s.seller_state,
        CASE WHEN s.seller_state = o.customer_state THEN 'same state' ELSE 'interstate' END AS route,
        CASE WHEN o.customer_state = 'SP' THEN 'customer in SP' ELSE 'customer outside SP' END AS customer_region
    FROM fct_orders AS o
    JOIN order_seller_state AS s USING (order_id)
    WHERE o.is_delivered AND o.is_complete_month
)

SELECT
    customer_region,
    route,
    COUNT(*)                                                     AS delivered_orders,
    ROUND(AVG(delivery_days), 1)                                 AS avg_delivery_days,
    ROUND(AVG(promised_days), 1)                                 AS avg_promised_days,
    ROUND(100.0 * AVG(CASE WHEN is_late THEN 1 ELSE 0 END), 1)   AS late_rate_pct,
    ROUND(AVG(review_score), 2)                                  AS avg_review,
    ROUND(AVG(freight_value), 2)                                 AS avg_freight
FROM routed
GROUP BY customer_region, route
ORDER BY customer_region, route;
