-- Model data for the low-review driver analysis (src/review_drivers.py).
--
-- Grain: one row per delivered, reviewed order with items, complete months (2017-01 .. 2018-08).
-- Target: low_review = 1 if the review score is 1 or 2.
-- Question: is late delivery still associated with low reviews after accounting for where the customer
-- lives, what was bought, how the order was split and when it was placed?
--
-- main_category = category of the order's most expensive item; categories with fewer than 500 orders
-- are grouped as 'other' so every model coefficient rests on enough data.

WITH main_item AS (
    SELECT order_id, category
    FROM fct_order_items
    QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY price DESC, order_item_id) = 1
),

orders AS (
    SELECT
        o.order_id,
        CASE WHEN o.review_score <= 2 THEN 1 ELSE 0 END          AS low_review,
        o.delivery_bucket,
        o.promised_days,
        o.customer_state,
        m.category,
        CASE WHEN o.n_items >= 3 THEN '3+' ELSE CAST(o.n_items AS VARCHAR) END AS items_band,
        CASE WHEN o.n_sellers > 1 THEN 1 ELSE 0 END               AS multi_seller,
        LN(o.product_value)                                       AS log_product_value,
        o.freight_value / o.product_value                         AS freight_ratio,
        strftime(o.purchase_month, '%Y-%m')                       AS purchase_month
    FROM fct_orders AS o
    JOIN main_item  AS m USING (order_id)
    WHERE o.is_delivered
      AND o.is_complete_month
      AND o.review_score IS NOT NULL
      AND o.n_items > 0
)

SELECT
    * EXCLUDE (category),
    CASE WHEN COUNT(*) OVER (PARTITION BY category) >= 500 THEN category ELSE 'other' END AS main_category
FROM orders;
