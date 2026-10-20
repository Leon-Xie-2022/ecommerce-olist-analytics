-- Date dimension covering every purchase date, for Power BI time intelligence.

CREATE OR REPLACE TABLE dim_date AS
SELECT
    CAST(d AS DATE)                                              AS date,
    CAST(date_trunc('month', d) AS DATE)                         AS month_start,
    strftime(d, '%Y-%m')                                         AS year_month,
    year(d)                                                      AS year,
    month(d)                                                     AS month,
    quarter(d)                                                   AS quarter,
    isodow(d)                                                    AS iso_weekday,
    strftime(d, '%a')                                            AS weekday_name,
    date_trunc('month', d) BETWEEN DATE '2017-01-01' AND DATE '2018-08-01' AS is_complete_month
FROM range(DATE '2016-09-01', DATE '2018-11-01', INTERVAL 1 DAY) AS t(d);
