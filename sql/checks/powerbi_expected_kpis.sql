-- Expected values for the Power BI cards (no slicer selected), computed independently in SQL.
-- Each row must match the card with the same name in powerbi/OlistDashboard.pbip.
-- Window: complete months 2017-01 .. 2018-08 (the model loads only these months).

WITH o AS (
    SELECT * FROM fct_orders WHERE is_complete_month
),
c AS (
    SELECT * FROM dim_customer WHERE cohort_month BETWEEN DATE '2017-01-01' AND DATE '2018-08-01'
)

SELECT 'Valid Orders' AS measure,
       CAST(COUNT(*) FILTER (WHERE is_valid) AS DOUBLE) AS expected_value FROM o
UNION ALL SELECT 'Product Value', ROUND(SUM(product_value) FILTER (WHERE is_valid), 2) FROM o
UNION ALL SELECT 'AOV', ROUND(SUM(product_value) FILTER (WHERE is_valid)
                              / COUNT(*) FILTER (WHERE is_valid AND n_items > 0), 2) FROM o
UNION ALL SELECT 'Delivered Orders', COUNT(*) FILTER (WHERE is_delivered) FROM o
UNION ALL SELECT 'Late Rate %', ROUND(100.0 * COUNT(*) FILTER (WHERE is_late)
                                      / COUNT(*) FILTER (WHERE is_delivered), 1) FROM o
UNION ALL SELECT 'Avg Delivery Days', ROUND(AVG(delivery_days) FILTER (WHERE is_delivered), 1) FROM o
UNION ALL SELECT 'Avg Review Score', ROUND(AVG(review_score) FILTER (WHERE is_valid), 2) FROM o
UNION ALL SELECT 'Low Review Share %',
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_valid AND review_score <= 2)
             / COUNT(review_score) FILTER (WHERE is_valid), 1) FROM o
UNION ALL SELECT 'Customers', COUNT(DISTINCT customer_unique_id) FILTER (WHERE is_valid) FROM o
UNION ALL SELECT 'Returning Order Share %',
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_return_order) / COUNT(*) FILTER (WHERE is_valid), 1) FROM o
UNION ALL SELECT 'Repeat Customer Share %',
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_repeat_customer) / COUNT(*), 1) FROM c;
