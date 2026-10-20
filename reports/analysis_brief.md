# Analysis brief: orders, delivery and customers (Olist, 2017-01 to 2018-08)

**Scope.** Public Olist marketplace data (Brazil). 97,910 valid orders across 20 complete months, with BRL 13.45 m in
product value (item prices; not company revenue, since commission and costs are not in the data). Every figure
below comes from the SQL in `sql/` or `src/review_drivers.py`, and the base tables are reconciled to the source
(`src/validate.py`).

## Findings

**1. Late delivery is rare, but it goes with very poor reviews, and region, product or season do not explain it.**
92% of delivered, reviewed orders arrived before the estimated date. For orders 8+ days late, **79%** got a 1–2 star
review, against **9%** for orders 10+ days early. A logistic regression on 95,560 orders controls for customer state,
product category, purchase month, basket size, seller count, price and freight. With those held constant, the
adjusted rates barely move (**78%** vs **8%**): 8+ days late carries 33× the odds of a low review relative to
1–9 days early. Lateness is concentrated by time and place. It reached 12.4% in 2017-11 (Black Friday month) and
19.0% in 2018-03, against 1–8% in most months. Among states with 300+ orders it ranges from 4.1% (Paraná) to 21.5%
(Alagoas).
*(sql/metrics/03, 05, 06 · sql/models/review_model_data.sql · src/review_drivers.py)*

**2. Split orders are the second big source of bad reviews, and the problem is missing items, not lateness.**
Orders from several sellers are almost never late (1.0%), yet **47%** get a 1–2 star review, against 11% for
single-item orders (odds ratio 3.6 after controls). Among their low reviews that have a comment, **56%** mention a
missing or undelivered item ("only received one", "did not arrive"), against 21% for single-item orders. The
order is marked delivered although part of it has not arrived. Multi-item orders from one seller show the same
pattern at a smaller scale (24% low reviews; 45% of those comments mention missing items).
*(sql/metrics/13_split_order_complaints.sql)*

**3. Almost every customer buys only once.**
Only **2.2%** of customers bought on two or more different days. Same-day extra orders are excluded, because they are
split baskets, not returns. Since mid-2017, returning customers have accounted for 1.7–3.4% of monthly orders. The
12-month repeat rate per cohort is 2.7–3.8%. For those who do return, the median gap is **74 days**, and 55% return
within 90 days.
*(sql/metrics/07, 08, 11)*

Also relevant for planning: the top 10% of sellers generate 67% of product value (09), and credit-card orders paid
in 7+ instalments are 12.2% of orders but 25.5% of payment value (10).

## Recommendations (to test, not proven)

1. **Fix the fulfilment experience where reviews break: split orders first, then late routes.**
   - Track delivery per parcel, mark an order delivered only when every item has arrived, and tell customers up
     front when an order ships in parts.
   - Monitor the late rate weekly by route (seller state → customer state) and add carrier capacity before November.
   - Test each change against a control group and judge it on the share of 1–2 star reviews.
2. **A second-purchase programme in the 30–90 day window.** With 97.8% one-time buyers and a median of 74 days to a
   second purchase, a post-delivery re-engagement offer is the obvious experiment. Use a holdout group and judge it
   on the cohort 3-month repeat rate.

## Limitations

- Historical (2016–2018) public data from one Brazilian marketplace. These are not Hong Kong or current results.
- No costs, commission, margin, marketing or web-traffic data, so there are no profit, ROI or conversion metrics.
- The regression adjusts for observed factors only (McFadden pseudo R² 0.19). Unobserved factors such as product
  quality or seller behaviour may still play a part, so the results are adjusted associations, not causal effects.
- The missing-item share uses a Portuguese keyword pattern. It is a heuristic for comparing groups, not an exact count.
- How the estimated delivery date is set is unknown. Very early deliveries suggest conservative promises.
- Customers who bought before 2016-09 cannot be identified, so some early-2017 "first" orders may be returns.
  Recent cohorts have short observation windows and are left blank, not counted as lost.
