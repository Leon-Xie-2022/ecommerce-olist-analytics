-- Analysis 11: monthly orders and product value from new vs returning customers.
--
-- Returning order = valid order on a later calendar day than the person's first purchase (is_return_order).
-- First-visit order = every other valid order (the first order plus any extra orders that same day).
-- Population: valid orders in complete months. Note: the data start in 2016-09, so a few "new"
-- orders in early 2017 may belong to people who bought before the data begin (left censoring).
-- Grain: one row per month (conditional aggregation, one column per segment).

SELECT
    strftime(purchase_month, '%Y-%m')                                              AS month,
    COUNT(*)                                                                       AS valid_orders,
    COUNT(*) FILTER (WHERE NOT is_return_order)                                    AS first_visit_orders,
    COUNT(*) FILTER (WHERE is_return_order)                                        AS returning_orders,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_return_order) / COUNT(*), 2)    AS returning_order_pct,
    ROUND(SUM(product_value) FILTER (WHERE is_return_order), 2)             AS returning_product_value,
    ROUND(100.0 * SUM(product_value) FILTER (WHERE is_return_order)
                / SUM(product_value), 2)                                           AS returning_value_pct
FROM fct_orders
WHERE is_valid AND is_complete_month
GROUP BY purchase_month
ORDER BY purchase_month;
