-- Route diagnosis: deliveries completed in the window, by seller state -> customer state.
--
-- Why routes and not sellers: in a 7-day window only 1-3 of ~530 sellers have 30+ delivered orders, so a
-- seller ranking would be almost all small samples. Routes group enough orders to compare.
-- Population: orders whose delivery is known and falls in the window (open_state = 'delivered'), so every
-- order has a final on-time/late outcome. This is not a purchase-cohort late rate: slow orders bought in
-- earlier weeks are counted in the week they arrive.
-- An order whose items ship from several seller states has no single route; it is kept as 'MULTI-ORIGIN'
-- so totals still reconcile with the weekly summary. Routes below min_route_sample are shown, flagged
-- and not ranked.

CREATE OR REPLACE TEMP TABLE route_diagnosis AS
WITH delivered AS (
    SELECT
        *,
        CASE
            WHEN n_origin_states = 1 THEN origin_states || ' -> ' || customer_state
            WHEN n_origin_states > 1 THEN 'MULTI-ORIGIN'
            ELSE 'NO ITEMS'
        END AS route
    FROM pit_orders
    WHERE is_delivered_in_window
),

overall AS (
    SELECT AVG(CAST(is_late AS INT)) AS overall_late_rate FROM delivered
),

by_route AS (
    SELECT
        route,
        CASE WHEN n_origin_states = 1 THEN origin_states END        AS origin_state,
        CASE WHEN n_origin_states = 1 THEN customer_state END       AS destination_state,
        COUNT(*)                                                    AS delivered_orders,
        COUNT(*) FILTER (WHERE is_late)                             AS late_orders,
        AVG(CAST(is_late AS INT))                                   AS late_rate,
        MEDIAN(delivery_days)                                       AS median_delivery_days,
        SUM(product_value)                                          AS product_value
    FROM delivered
    GROUP BY ALL
)

SELECT
    r.route,
    r.origin_state,
    r.destination_state,
    CASE WHEN r.origin_state IS NULL THEN NULL
         ELSE r.origin_state <> r.destination_state END                         AS is_interstate,
    r.delivered_orders,
    r.late_orders,
    ROUND(r.late_rate, 4)                                                       AS late_rate,
    ROUND(r.late_rate - o.overall_late_rate, 4)                                 AS late_rate_vs_overall,
    r.median_delivery_days,
    ROUND(r.product_value, 2)                                                   AS product_value,
    r.delivered_orders >= p.min_route_sample AND r.origin_state IS NOT NULL     AS meets_min_sample,
    CASE
        WHEN r.origin_state IS NULL THEN 'Not a single route - totals only'
        WHEN r.delivered_orders >= p.min_route_sample THEN 'OK'
        ELSE printf('Small sample (< %d) - not ranked', p.min_route_sample)
    END                                                                         AS sample_note,
    CASE WHEN r.delivered_orders >= p.min_route_sample AND r.origin_state IS NOT NULL
         THEN RANK() OVER (PARTITION BY r.delivered_orders >= p.min_route_sample
                                        AND r.origin_state IS NOT NULL
                           ORDER BY r.late_rate DESC) END                       AS late_rate_rank,
    p.min_route_sample,
    p.as_of_date,
    p.window_start,
    p.as_of_date                                                                AS window_end
FROM by_route     AS r
CROSS JOIN overall AS o
CROSS JOIN params  AS p
ORDER BY meets_min_sample DESC, late_rate_rank NULLS LAST, delivered_orders DESC, route;
