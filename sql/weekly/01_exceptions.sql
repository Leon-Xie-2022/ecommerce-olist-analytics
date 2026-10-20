-- Follow-up list at the cut-off: one row per order, ranked by a written priority rule.
--
-- Status note: the data keep only the order status at extraction (Oct 2018) and no cancellation date, so
-- whether a listed order had been cancelled by the cut-off cannot be known. Inclusion therefore uses only
-- dated events (approval, carrier hand-over, delivery). This is a historical diagnostic list, not a
-- reconstruction of a live alert queue.
--
-- Rules (first match wins, checked in this order):
--   Overdue = no delivery known and estimated date passed 1..max_overdue_days ago (open_state = 'overdue')
--     R1 IN_TRANSIT_OVERDUE      handed to carrier by the cut-off           -> chase carrier tracking
--     R2 NOT_SHIPPED_OVERDUE     payment approved, not handed to carrier    -> chase seller dispatch
--     R3 NOT_APPROVED_OVERDUE    payment not approved by the cut-off        -> check payment / cancellation
--   Early warning = not yet due, payment approved, not handed to carrier, and every item's seller ship-by
--   date has passed (looking back at most max_overdue_days)
--     R4 SHIP_BY_MISSED          -> remind seller(s) before the customer date is missed
-- Priority: overdue P1 if days_overdue >= p1_min_days_overdue, P2 if >= p2_min_days_overdue, else P3;
--           early warnings P4. Within a priority: more days overdue first, then higher product value.
-- Seller attribution: an order with several sellers has one order-level carrier date, so a dispatch delay
-- cannot be pinned on one seller; those rows say so instead of naming a seller.

CREATE OR REPLACE TEMP TABLE exceptions AS
WITH flagged AS (
    SELECT
        o.*,
        p.as_of_date,
        p.window_start,
        date_diff('day', CAST(o.ship_by_ts AS DATE), p.as_of_date) + 1 AS days_past_ship_by,
        CASE
            WHEN o.open_state = 'overdue' AND o.carrier_ts IS NOT NULL  THEN 'R1'
            WHEN o.open_state = 'overdue' AND o.approved_ts IS NOT NULL THEN 'R2'
            WHEN o.open_state = 'overdue'                               THEN 'R3'
            WHEN o.open_state = 'not yet due'
                 AND o.approved_ts IS NOT NULL
                 AND o.carrier_ts IS NULL
                 AND o.ship_by_ts < p.cutoff_ts
                 AND date_diff('day', CAST(o.ship_by_ts AS DATE), p.as_of_date) + 1
                     <= p.max_overdue_days                              THEN 'R4'
        END AS rule_id,
        p.p1_min_days_overdue,
        p.p2_min_days_overdue
    FROM pit_orders  AS o
    CROSS JOIN params AS p
),

described AS (
    SELECT
        *,
        CASE rule_id
            WHEN 'R1' THEN 'Overdue, handed to carrier, no delivery recorded'
            WHEN 'R2' THEN 'Overdue, payment approved, not handed to carrier'
            WHEN 'R3' THEN 'Overdue, payment not approved by cut-off'
            WHEN 'R4' THEN 'Not yet due, seller ship-by date passed, not handed to carrier'
        END AS rule_reason,
        CASE rule_id
            WHEN 'R1' THEN 'Ask carrier for tracking status; consider proactive message to customer'
            WHEN 'R2' THEN 'Ask seller(s) for dispatch date; consider proactive message to customer'
            WHEN 'R3' THEN 'Check payment status and whether the order was cancelled; close or notify customer'
            WHEN 'R4' THEN 'Remind seller(s) to dispatch before the estimated delivery date'
        END AS suggested_action,
        CASE
            WHEN rule_id = 'R4'                          THEN 'P4'
            WHEN days_overdue >= p1_min_days_overdue     THEN 'P1'
            WHEN days_overdue >= p2_min_days_overdue     THEN 'P2'
            ELSE                                              'P3'
        END AS priority
    FROM flagged
    WHERE rule_id IS NOT NULL
)

SELECT
    ROW_NUMBER() OVER (ORDER BY priority, days_overdue DESC NULLS LAST, days_past_ship_by DESC,
                                product_value DESC, order_id)                    AS priority_rank,
    priority,
    CASE WHEN rule_id = 'R4' THEN 'Early warning' ELSE 'Overdue' END             AS exception_type,
    rule_id,
    rule_reason,
    order_id,
    purchase_date,
    estimated_delivery_date,
    days_overdue,
    CAST(ship_by_ts AS DATE)                                                     AS ship_by_date,
    approved_ts IS NOT NULL                                                      AS approved_by_cutoff,
    CAST(carrier_ts AS DATE)                                                     AS carrier_handover_date,
    estimated_delivery_date BETWEEN window_start AND as_of_date                  AS became_overdue_this_window,
    n_items,
    n_sellers,
    CASE WHEN n_sellers = 1 THEN seller_ids END                                  AS seller_id,
    CASE WHEN n_sellers = 1 THEN 'single seller'
         WHEN n_sellers > 1 THEN 'several sellers - not attributed to one seller'
         ELSE 'no items recorded' END                                            AS seller_attribution,
    origin_states,
    customer_state,
    ROUND(product_value, 2)                                                      AS product_value,
    ROUND(freight_value, 2)                                                      AS freight_value,
    ROUND(payment_value, 2)                                                      AS payment_value,
    CASE rule_id
        WHEN 'R1' THEN printf('Estimated %s; handed to carrier %s; no delivery recorded by end of %s',
                              estimated_delivery_date, CAST(carrier_ts AS DATE), as_of_date)
        WHEN 'R2' THEN printf('Estimated %s; approved %s; ship-by %s; not handed to carrier by end of %s',
                              estimated_delivery_date, CAST(approved_ts AS DATE), CAST(ship_by_ts AS DATE),
                              as_of_date)
        WHEN 'R3' THEN printf('Estimated %s; purchased %s; payment not approved by end of %s',
                              estimated_delivery_date, purchase_date, as_of_date)
        WHEN 'R4' THEN printf('Ship-by %s (%d day(s) ago); not handed to carrier; estimated delivery %s',
                              CAST(ship_by_ts AS DATE), days_past_ship_by, estimated_delivery_date)
    END                                                                          AS evidence,
    suggested_action,
    as_of_date,
    window_start,
    as_of_date                                                                   AS window_end
FROM described
ORDER BY priority_rank;
