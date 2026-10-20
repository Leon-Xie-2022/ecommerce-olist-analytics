-- Analysis 4: category mix — which categories carry product value, and how concentrated it is.
--
-- Grain: one row per product category (English name; 'unknown' = no category in source).
-- Population: items of valid orders in complete months (2017-01 .. 2018-08).
-- share_pct / cumulative_share_pct use window functions over the whole result.
-- An order with items from two categories is counted once in each, so `orders` does not sum to total orders.

WITH category AS (
    SELECT
        category,
        COUNT(DISTINCT order_id)   AS orders,
        COUNT(*)                   AS items,
        SUM(price)                 AS product_value,
        AVG(price)                 AS avg_item_price
    FROM fct_order_items
    WHERE is_valid AND is_complete_month
    GROUP BY category
)

SELECT
    RANK() OVER (ORDER BY product_value DESC)                               AS value_rank,
    category,
    orders,
    items,
    ROUND(product_value, 2)                                                 AS product_value,
    ROUND(avg_item_price, 2)                                                AS avg_item_price,
    ROUND(100.0 * product_value / SUM(product_value) OVER (), 2)            AS share_pct,
    ROUND(100.0 * SUM(product_value) OVER (ORDER BY product_value DESC
                                           ROWS UNBOUNDED PRECEDING)
                / SUM(product_value) OVER (), 1)                            AS cumulative_share_pct
FROM category
ORDER BY value_rank;
