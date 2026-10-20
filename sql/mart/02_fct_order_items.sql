-- Item fact: one row per item unit (112,650 rows). Used for category and seller analysis.
-- Order-level attributes (validity, month, customer state) are copied from fct_orders, which is
-- one row per order, so this join cannot multiply item rows.

CREATE OR REPLACE TABLE fct_order_items AS
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    p.product_category_name_english  AS category,
    s.seller_state,
    o.customer_state,
    o.purchase_month,
    o.is_valid,
    o.is_complete_month,
    i.price,
    i.freight_value
FROM order_items      AS i
JOIN fct_orders       AS o USING (order_id)
JOIN products         AS p USING (product_id)
JOIN sellers          AS s USING (seller_id);
