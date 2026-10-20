-- Metric 3: delivery time and late-delivery rate per month.
--
-- Grain of the result: one row per complete purchase month (2017-01 .. 2018-08).
-- Population: delivered orders = status 'delivered' AND a recorded delivery date
--             (8 'delivered' orders without a date are excluded; see data quality report).
-- delivery_days = days from purchase to delivery to the customer
-- late          = delivered on a calendar day after the estimated delivery date
--                 (the estimate has no time of day, so delivery on the estimated date counts as on time)
-- late_rate     = late orders / delivered orders
-- Month = purchase month, so each order is judged against the promise made when it was bought.

WITH delivered AS (
    SELECT
        purchase_month,
        date_diff('day', order_purchase_timestamp, order_delivered_customer_date) AS delivery_days,
        CAST(order_delivered_customer_date AS DATE)
            > CAST(order_estimated_delivery_date AS DATE)                        AS is_late,
        date_diff('day', CAST(order_delivered_customer_date AS DATE),
                         CAST(order_estimated_delivery_date AS DATE))            AS days_before_estimate
    FROM orders
    WHERE order_status = 'delivered'
      AND order_delivered_customer_date IS NOT NULL
      AND purchase_month BETWEEN DATE '2017-01-01' AND DATE '2018-08-01'
)

SELECT
    strftime(purchase_month, '%Y-%m')                           AS month,
    COUNT(*)                                                    AS delivered_orders,
    ROUND(AVG(delivery_days), 1)                                AS avg_delivery_days,
    MEDIAN(delivery_days)                                       AS median_delivery_days,
    CAST(SUM(CASE WHEN is_late THEN 1 ELSE 0 END) AS INTEGER)   AS late_orders,
    ROUND(100.0 * AVG(CASE WHEN is_late THEN 1 ELSE 0 END), 1)  AS late_rate_pct,
    ROUND(AVG(days_before_estimate), 1)                         AS avg_days_before_estimate
FROM delivered
GROUP BY purchase_month
ORDER BY purchase_month;
