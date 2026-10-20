# Resume bullets

Use only after you can explain each point without notes (see the learning notes in `notes/`).

**E-commerce Orders, Delivery & Customer Analytics** — Python, SQL, Power BI · [GitHub link]

- Built a reproducible Python + SQL pipeline on 100k e-commerce orders (9 tables) with 35 data-quality checks, an
  order-level data mart and 16 automated reconciliations; showed that a naive multi-table join would overstate
  payment value by 28%.
- Identified the two main drivers of 1–2 star reviews with 13 SQL analyses and a logistic regression: late delivery
  (79% low reviews when 8+ days late vs 9% when early, robust to region/category/season controls) and split orders
  (47% low reviews, 56% of complaints about missing items despite a 1% late rate).
- Designed a 3-page Power BI dashboard (star schema, 17 DAX measures incl. time intelligence) reconciled to SQL,
  which caught a DAX blank-handling bug, plus a one-page brief with test-based recommendations and limitations.

Shorter variant (one line):

- Analysed 100k marketplace orders with Python, SQL and Power BI; found that late and split deliveries drive most
  1–2 star reviews (79% and 47% vs 11% baseline) and built a reconciled dashboard to monitor them.
