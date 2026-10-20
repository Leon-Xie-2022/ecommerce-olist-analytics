-- Point-in-time order facts: what was known about each order at the end of the cut-off day.
--
-- Parameters (set by src/weekly_report.py with SET VARIABLE): as_of_date, window_days,
-- min_route_sample, max_overdue_days, p1_min_days_overdue, p2_min_days_overdue.
-- Inputs are the src_* views over the clean Parquet files.
--
-- Rules (docs/weekly_ops/point_in_time.md):
--   * cut-off instant = (as_of_date + 1 day) 00:00; an event is known only if its timestamp is earlier.
--   * orders purchased after the cut-off do not exist yet.
--   * approval, carrier hand-over and customer delivery timestamps after the cut-off are set to NULL.
--   * order_status is NOT read: it is the status at data extraction (Oct 2018), not at the cut-off.
--   * items, prices, freight, payments, sellers, the estimated delivery date and the seller ship-by date
--     are taken as known from purchase/approval (the data keep no change history for them).
-- Grain: one row per order known at the cut-off. Child tables are aggregated before the join.

CREATE OR REPLACE TEMP TABLE params AS
SELECT
    CAST(getvariable('as_of_date') AS DATE)                                        AS as_of_date,
    CAST(getvariable('as_of_date') AS DATE) - (getvariable('window_days') - 1)     AS window_start,
    CAST(CAST(getvariable('as_of_date') AS DATE) + 1 AS TIMESTAMP)                 AS cutoff_ts,
    getvariable('window_days')                                                     AS window_days,
    getvariable('min_route_sample')                                                AS min_route_sample,
    getvariable('max_overdue_days')                                                AS max_overdue_days,
    getvariable('p1_min_days_overdue')                                             AS p1_min_days_overdue,
    getvariable('p2_min_days_overdue')                                             AS p2_min_days_overdue;

CREATE OR REPLACE TEMP TABLE pit_items AS
SELECT
    i.order_id,
    i.order_item_id,
    i.seller_id,
    s.seller_state,
    i.shipping_limit_date,
    i.price,
    i.freight_value
FROM src_order_items AS i
JOIN src_sellers     AS s USING (seller_id)
JOIN src_orders      AS o USING (order_id)
CROSS JOIN params    AS p
WHERE o.order_purchase_timestamp < p.cutoff_ts;

CREATE OR REPLACE TEMP TABLE pit_order_facts AS
WITH item_agg AS (
    SELECT
        order_id,
        COUNT(*)                                           AS n_items,
        COUNT(DISTINCT seller_id)                          AS n_sellers,
        COUNT(DISTINCT seller_state)                       AS n_origin_states,
        string_agg(DISTINCT seller_id, ' | ' ORDER BY seller_id)       AS seller_ids,
        string_agg(DISTINCT seller_state, ' | ' ORDER BY seller_state) AS origin_states,
        MAX(shipping_limit_date)                           AS ship_by_ts,
        SUM(price)                                         AS product_value,
        SUM(freight_value)                                 AS freight_value
    FROM pit_items
    GROUP BY order_id
),

payment_agg AS (
    SELECT order_id, SUM(payment_value) AS payment_value
    FROM src_payments
    GROUP BY order_id
)

SELECT
    o.order_id,
    c.customer_state,
    CAST(o.order_purchase_timestamp AS DATE)                                   AS purchase_date,
    CAST(o.order_estimated_delivery_date AS DATE)                              AS estimated_delivery_date,
    CASE WHEN o.order_approved_at < p.cutoff_ts THEN o.order_approved_at END   AS approved_ts,
    CASE WHEN o.order_delivered_carrier_date < p.cutoff_ts
         THEN o.order_delivered_carrier_date END                               AS carrier_ts,
    CASE WHEN o.order_delivered_customer_date < p.cutoff_ts
         THEN o.order_delivered_customer_date END                              AS delivered_ts,
    COALESCE(i.n_items, 0)                                                     AS n_items,
    COALESCE(i.n_sellers, 0)                                                   AS n_sellers,
    COALESCE(i.n_origin_states, 0)                                             AS n_origin_states,
    i.seller_ids,
    i.origin_states,
    i.ship_by_ts,
    COALESCE(i.product_value, 0)                                               AS product_value,
    COALESCE(i.freight_value, 0)                                               AS freight_value,
    pa.payment_value
FROM src_orders          AS o
CROSS JOIN params        AS p
JOIN src_customers       AS c  USING (customer_id)
LEFT JOIN item_agg       AS i  USING (order_id)
LEFT JOIN payment_agg    AS pa USING (order_id)
WHERE o.order_purchase_timestamp < p.cutoff_ts;

-- Order state at the cut-off, defined once and used by every weekly output.
--   open_state:  'delivered'        delivery known by the cut-off
--                'not yet due'      no delivery, estimated date after the cut-off day (right-censored:
--                                   outcome unknown, never counted as on time)
--                'overdue'          no delivery, estimated date passed 1..max_overdue_days ago
--                'stale overdue'    no delivery, estimated date passed longer ago; most such orders were
--                                   probably cancelled or lost, but the status at the cut-off is unknown
--   days_overdue: lower bound of lateness. An order due on the cut-off day and still undelivered at the
--                 end of it is at least 1 day late (late = delivered on a later calendar day than estimated).
CREATE OR REPLACE TEMP TABLE pit_orders AS
SELECT
    f.*,
    CAST(f.delivered_ts AS DATE)                                                AS delivered_date,
    f.purchase_date BETWEEN p.window_start AND p.as_of_date                     AS is_placed_in_window,
    COALESCE(CAST(f.delivered_ts AS DATE)
             BETWEEN p.window_start AND p.as_of_date, FALSE)                    AS is_delivered_in_window,
    CASE WHEN f.delivered_ts IS NOT NULL
         THEN CAST(f.delivered_ts AS DATE) > f.estimated_delivery_date END      AS is_late,
    date_diff('day', f.purchase_date, CAST(f.delivered_ts AS DATE))             AS delivery_days,
    date_diff('day', f.estimated_delivery_date, CAST(f.delivered_ts AS DATE))   AS days_late,
    CASE WHEN f.delivered_ts IS NULL AND f.estimated_delivery_date <= p.as_of_date
         THEN date_diff('day', f.estimated_delivery_date, p.as_of_date) + 1 END AS days_overdue,
    CASE
        WHEN f.delivered_ts IS NOT NULL                                  THEN 'delivered'
        WHEN f.estimated_delivery_date > p.as_of_date                    THEN 'not yet due'
        WHEN date_diff('day', f.estimated_delivery_date, p.as_of_date) + 1
             <= p.max_overdue_days                                       THEN 'overdue'
        ELSE                                                                  'stale overdue'
    END                                                                         AS open_state
FROM pit_order_facts AS f
CROSS JOIN params    AS p;
