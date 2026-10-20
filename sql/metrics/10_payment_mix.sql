-- Analysis 10: payment methods and credit-card instalments.
--
-- Population: valid orders in complete months that have a payment.
-- Each order is assigned its main payment type (type of its largest payment row, see fct_orders),
-- so order counts add up to the total. Instalment buckets apply to credit-card orders only.
-- Grain: one row per (payment type, instalment bucket).

WITH o AS (
    SELECT
        main_payment_type,
        CASE
            WHEN main_payment_type <> 'credit_card' THEN 'n/a'
            WHEN max_installments <= 1  THEN '1 (single payment)'
            WHEN max_installments <= 3  THEN '2-3'
            WHEN max_installments <= 6  THEN '4-6'
            ELSE                             '7+'
        END AS installments,
        payment_value
    FROM fct_orders
    WHERE is_valid AND is_complete_month AND payment_value IS NOT NULL
)

SELECT
    main_payment_type,
    installments,
    COUNT(*)                                                             AS orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)                   AS order_share_pct,
    ROUND(AVG(payment_value), 2)                                         AS avg_payment_value,
    ROUND(100.0 * SUM(payment_value) / SUM(SUM(payment_value)) OVER (), 1) AS value_share_pct
FROM o
GROUP BY main_payment_type, installments
ORDER BY main_payment_type, installments;
