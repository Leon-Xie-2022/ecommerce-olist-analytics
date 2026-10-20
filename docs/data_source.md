# Data source record

| Item | Value |
|---|---|
| Dataset | Brazilian E-Commerce Public Dataset by Olist |
| URL | https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce |
| Publisher | Olist (Kaggle user `olistbr`) |
| Version | Kaggle API does not report a version number; all files carry creation date 2021-10-01 |
| Download date | 2026-10-20, via `kaggle datasets download` (Kaggle CLI 2.2.4) |
| Licence | CC BY-NC-SA 4.0 (from Kaggle dataset metadata) |
| Attribution | Credit "Olist, Brazilian E-Commerce Public Dataset, Kaggle" with a link to the URL above |

## What the licence means for this repo

- **BY** — attribution is required (README credits Olist with a link).
- **NC** — non-commercial use only; this is a personal learning/portfolio project.
- **SA** — adapted material (e.g. cleaned extracts, aggregated tables shipped with the Power BI file)
  must be shared under the same licence. Raw data is not redistributed here.

## File checksums (SHA-256)

Output of `python src/check_raw.py` on 2026-10-20. Data rows = line count minus header; review text
contains embedded newlines, so the true row count of `olist_order_reviews_dataset.csv` may be lower.

| File | Size (bytes) | Data rows | SHA-256 |
|---|---|---|---|
| olist_customers_dataset.csv | 9033957 | 99441 | 983a422239e1712ded753b3bf9ecf47dc73f144d306029dcfa99e70a226883d2 |
| olist_geolocation_dataset.csv | 61273883 | 1000163 | b514f6fc991b9566aeba02aa5d67e2c3630f034b60a0e05aa0d082a3b66d88d6 |
| olist_order_items_dataset.csv | 15438671 | 112650 | 0bc4d068c4fe38cbb01bd90e8746e3c613fe7b4baef75fab7b0e329701c3e279 |
| olist_order_payments_dataset.csv | 5777138 | 103886 | 4f713964f2815dbbaa40b9488268c55aac3627bfce5aa96cf58d1f3616de3cc0 |
| olist_order_reviews_dataset.csv | 14451670 | 104719 | 012b61c7593e34f51fa614efdf802b9c7056ce6aae5307ddb93236e7cfc797d7 |
| olist_orders_dataset.csv | 17654914 | 99441 | 8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf |
| olist_products_dataset.csv | 2379446 | 32951 | 3e6569628a17fbc75fd206ee357b59e20364b9afa90f5b6cd5b4d624c58aa9cc |
| olist_sellers_dataset.csv | 174703 | 3095 | 1f643d2b950373b85735e7794b20986f528d7a000432e7c6f9bcbb44d0846a0e |
| product_category_name_translation.csv | 2613 | 71 | a81f0d1f27b27e7293f761bc79e3ce8f348ee39c4b3ed3e49bde38f478586278 |
