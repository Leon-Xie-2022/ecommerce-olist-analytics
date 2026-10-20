-- Analysis 8: monthly cohort repeat-purchase rates.
--
-- Cohort       = month of a person's first valid purchase (cohorts 2017-01 .. 2018-08).
-- Denominator  = all people in the cohort.
-- repeat_Nm    = share of the cohort who came back (a valid order on a later calendar day than their
--                first purchase) by the end of month N after the cohort month. Cumulative; month 0 =
--                a return later in the cohort month itself, which is included.
-- Observation  = data are complete through 2018-08. A cohort can only report repeat_Nm if
--                cohort_month + N <= 2018-08; otherwise the cell is NULL ("not yet observable"),
--                NOT 0. Showing 0 would wrongly count unobserved customers as lost.

WITH people AS (
    SELECT customer_unique_id, cohort_month
    FROM dim_customer
    WHERE cohort_month BETWEEN DATE '2017-01-01' AND DATE '2018-08-01'
),

later_orders AS (                      -- months after the cohort month in which the person bought again
    SELECT
        p.customer_unique_id,
        p.cohort_month,
        date_diff('month', p.cohort_month, o.purchase_month) AS month_number
    FROM people AS p
    JOIN fct_orders AS o
      ON o.customer_unique_id = p.customer_unique_id
     AND o.is_valid
     AND o.is_return_order
     AND o.purchase_month <= DATE '2018-08-01'
),

first_return AS (                      -- earliest return month per person (0 = later day in the cohort month)
    SELECT customer_unique_id, cohort_month, MIN(month_number) AS first_return_month
    FROM later_orders
    GROUP BY customer_unique_id, cohort_month
),

cohort AS (
    SELECT
        p.cohort_month,
        COUNT(*)                                               AS cohort_size,
        COUNT(*) FILTER (WHERE f.first_return_month <= 1)      AS returned_1m,
        COUNT(*) FILTER (WHERE f.first_return_month <= 3)      AS returned_3m,
        COUNT(*) FILTER (WHERE f.first_return_month <= 6)      AS returned_6m,
        COUNT(*) FILTER (WHERE f.first_return_month <= 12)     AS returned_12m,
        date_diff('month', p.cohort_month, DATE '2018-08-01')  AS months_observed
    FROM people AS p
    LEFT JOIN first_return AS f USING (customer_unique_id, cohort_month)
    GROUP BY p.cohort_month
)

SELECT
    strftime(cohort_month, '%Y-%m')                                                  AS cohort,
    cohort_size,
    months_observed,
    CASE WHEN months_observed >= 1  THEN ROUND(100.0 * returned_1m  / cohort_size, 2) END AS repeat_1m_pct,
    CASE WHEN months_observed >= 3  THEN ROUND(100.0 * returned_3m  / cohort_size, 2) END AS repeat_3m_pct,
    CASE WHEN months_observed >= 6  THEN ROUND(100.0 * returned_6m  / cohort_size, 2) END AS repeat_6m_pct,
    CASE WHEN months_observed >= 12 THEN ROUND(100.0 * returned_12m / cohort_size, 2) END AS repeat_12m_pct
FROM cohort
ORDER BY cohort_month;
