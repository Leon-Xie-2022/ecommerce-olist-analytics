# Analysis brief: orders, delivery and customers (Olist, 2017-01 to 2018-08)

**Scope.** Public Olist marketplace data (Brazil). 97,910 valid orders across 20 complete months, with BRL 13.45 m in
product value (item prices; not company revenue, since commission and costs are not in the data). Every figure below
is produced by the SQL in `sql/metrics/` and reconciled to the source tables (`src/validate.py`).

## Findings

**1. Late deliveries are rare, but they go together with very poor reviews.**
93% of delivered, reviewed orders arrived on or before the estimated date, and 64% arrived 10 or more days early.
For the 6.6% that arrived late, review scores collapse. Orders 8+ days late average **1.70** stars and 79% of them
get 1–2 stars, against **4.32** stars and 9% low scores for orders 10+ days early.
*(sql/metrics/06_review_by_delivery_outcome.sql)*

**2. Lateness clusters in time and place.**
The late rate stays between 1% and 8% in most months, but **12.4% in 2017-11**, when product value rose 52% on the previous month
(Black Friday month), and **14.1% / 19.0% in 2018-02 / 2018-03**. Among states with 300+ delivered orders, it ranges from **4.1% in Paraná** (São Paulo 4.5%) to
**21.5% in Alagoas** and **17.5% in Maranhão**. Interstate orders to customers outside SP are late 8.9% of the time,
against 3.5% for same-state orders outside SP.
*(sql/metrics/03, 01, 05, 12)*

**3. Almost every customer buys only once.**
Only **2.2%** of customers bought on two or more different days. Same-day extra orders are excluded, because they are
split baskets, not returns. Since mid-2017, returning customers have accounted for 1.7–3.4% of monthly orders. The 12-month repeat
rate per cohort is 2.7–3.8%. For those who do return, the median gap is **74 days**, and 55% return within 90 days.
*(sql/metrics/07, 08, 11)*

Also relevant for planning: the top 10% of sellers generate 67% of product value (09), and credit-card orders paid
in 7+ instalments are 12.2% of orders but 25.5% of payment value (10).

## Recommendations (to test, not proven)

1. **Delivery reliability on long routes and in peak months.** Track the late rate weekly by route (seller state →
   customer state) and add carrier capacity before November. Test proactive delay notices on high-risk routes against
   a control group, and measure the effect on 1–2 star reviews. The data show an association between lateness and
   low scores, not how much reviews would improve if lateness fell.
2. **A second-purchase programme in the 30–90 day window.** With 97.8% one-time buyers and a median of 74 days to a
   second purchase, a post-delivery re-engagement offer is the obvious experiment. Use a holdout group and judge it
   on the cohort 3-month repeat rate.

## Limitations

- Historical (2016–2018) public data from one Brazilian marketplace. These are not Hong Kong or current results.
- No costs, commission, margin, marketing or web-traffic data, so there are no profit, ROI or conversion metrics.
- All relationships are associations. Late orders also differ in region, product and season.
- How the estimated delivery date is set is unknown. Very early deliveries suggest conservative promises.
- Customers who bought before 2016-09 cannot be identified, so some early-2017 "first" orders may be returns.
  Recent cohorts have short observation windows and are left blank, not counted as lost.
