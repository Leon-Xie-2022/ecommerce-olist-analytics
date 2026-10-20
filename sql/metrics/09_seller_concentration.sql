-- Analysis 9: seller concentration — how much product value comes from the top sellers.
--
-- Population: items of valid orders in complete months.
-- Sellers are ranked by product value; NTILE(10) splits them into deciles (1 = top 10%).
-- Grain: one row per seller decile.

WITH seller AS (
    SELECT
        seller_id,
        SUM(price)                 AS product_value,
        COUNT(DISTINCT order_id)   AS orders
    FROM fct_order_items
    WHERE is_valid AND is_complete_month
    GROUP BY seller_id
),

ranked AS (
    SELECT *, NTILE(10) OVER (ORDER BY product_value DESC) AS seller_decile
    FROM seller
)

SELECT
    seller_decile,
    COUNT(*)                                                               AS sellers,
    ROUND(SUM(product_value), 2)                                           AS product_value,
    ROUND(100.0 * SUM(product_value) / SUM(SUM(product_value)) OVER (), 1) AS value_share_pct,
    ROUND(100.0 * SUM(SUM(product_value)) OVER (ORDER BY seller_decile)
                / SUM(SUM(product_value)) OVER (), 1)                      AS cumulative_share_pct,
    ROUND(MEDIAN(product_value), 2)                                        AS median_seller_value,
    ROUND(AVG(orders), 1)                                                  AS avg_orders_per_seller
FROM ranked
GROUP BY seller_decile
ORDER BY seller_decile;
