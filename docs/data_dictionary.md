# Data dictionary

Source: Olist Brazilian E-Commerce Public Dataset (see [`data_source.md`](data_source.md)).
Row counts and null shares are from the raw files downloaded on 2026-10-20.
Column meanings follow the dataset's Kaggle description and were checked against the data.

**Grain** = what one row represents. **PK** = column(s) that uniquely identify a row (verified, no duplicates).

## orders — `olist_orders_dataset.csv`

Grain: one row per order. PK: `order_id`. 99,441 rows. Purchases from 2016-09-04 to 2018-10-17.

| Column | Type | Meaning | Nulls | Notes |
|---|---|---|---|---|
| order_id | text | Order identifier | 0 | PK |
| customer_id | text | Customer key **for this order** | 0 | FK → customers. Each order gets its own `customer_id`; use `customer_unique_id` to follow a person across orders |
| order_status | text | Latest order status | 0 | delivered 96,478 · shipped 1,107 · canceled 625 · unavailable 609 · invoiced 314 · processing 301 · created 5 · approved 2 |
| order_purchase_timestamp | timestamp | Purchase time | 0 | Used to assign orders to months |
| order_approved_at | timestamp | Payment approval time | 0.16% | |
| order_delivered_carrier_date | timestamp | Hand-over to the logistics partner | 1.79% | 1,359 rows are earlier than approval (see quality report) |
| order_delivered_customer_date | timestamp | Actual delivery to customer | 2.98% | Null for undelivered orders; also null for 8 `delivered` orders |
| order_estimated_delivery_date | date (stored as timestamp 00:00) | Delivery date promised at purchase | 0 | Basis for the late-delivery metric |

## order_items — `olist_order_items_dataset.csv`

Grain: one row per item unit within an order (2 units of the same product = 2 rows). PK: (`order_id`, `order_item_id`). 112,650 rows covering 98,666 orders.

| Column | Type | Meaning | Nulls | Notes |
|---|---|---|---|---|
| order_id | text | Order | 0 | FK → orders |
| order_item_id | int | Sequence number of the item within the order (1, 2, …) | 0 | Max 21 |
| product_id | text | Product | 0 | FK → products |
| seller_id | text | Seller who fulfils this item | 0 | FK → sellers. One order can have several sellers |
| shipping_limit_date | timestamp | Deadline for the seller to hand the item to the carrier | 0 | |
| price | decimal | Item price (BRL) | 0 | 0.85 – 6,735.00 |
| freight_value | decimal | Freight charged for this item (BRL) | 0 | Order freight is split across items |

## order_payments — `olist_order_payments_dataset.csv`

Grain: one row per payment record of an order. PK: (`order_id`, `payment_sequential`). 103,886 rows covering 99,440 orders (1 order has no payment).

| Column | Type | Meaning | Nulls | Notes |
|---|---|---|---|---|
| order_id | text | Order | 0 | FK → orders. 2,961 orders have 2+ payment rows (e.g. card + voucher) |
| payment_sequential | int | Sequence of the payment within the order | 0 | |
| payment_type | text | credit_card · boleto · voucher · debit_card · not_defined | 0 | `boleto` = Brazilian bank slip. 3 `not_defined` rows, all value 0 |
| payment_installments | int | Number of instalments chosen | 0 | 2 credit-card rows have 0 |
| payment_value | decimal | Amount of this payment (BRL) | 0 | Order total = sum over rows |

## order_reviews — `olist_order_reviews_dataset.csv`

Grain: one row per (review, order) pair. PK: (`review_id`, `order_id`). 99,224 rows covering 98,673 orders.
Neither column is unique on its own: 547 orders have 2–3 reviews, and 789 `review_id`s are attached to more than one order.

| Column | Type | Meaning | Nulls | Notes |
|---|---|---|---|---|
| review_id | text | Review identifier | 0 | Not unique alone |
| order_id | text | Reviewed order | 0 | FK → orders |
| review_score | int | 1–5 stars | 0 | |
| review_comment_title | text | Comment title (Portuguese) | 88.3% | |
| review_comment_message | text | Comment text (Portuguese) | 58.7% | Contains line breaks and emoji |
| review_creation_date | date | Date the satisfaction survey was sent | 0 | Latest 2018-08-31 → orders after that have no review yet |
| review_answer_timestamp | timestamp | Time the customer answered | 0 | |

## customers — `olist_customers_dataset.csv`

Grain: one row per `customer_id`, i.e. effectively one per order. PK: `customer_id`. 99,441 rows, 96,096 distinct `customer_unique_id`.

| Column | Type | Meaning | Nulls | Notes |
|---|---|---|---|---|
| customer_id | text | Order-level customer key | 0 | PK; joins to orders 1:1 |
| customer_unique_id | text | Person-level customer identifier | 0 | Use for repeat purchase and cohorts. 2,997 people have more than one `customer_id` |
| customer_zip_code_prefix | text | First 5 digits of the postcode | 0 | Keep as text — leading zeros matter |
| customer_city | text | City | 0 | |
| customer_state | text | State (2-letter code, 27 states) | 0 | |

## products — `olist_products_dataset.csv`

Grain: one row per product. PK: `product_id`. 32,951 rows.

| Column | Type | Meaning | Nulls | Notes |
|---|---|---|---|---|
| product_id | text | Product | 0 | PK |
| product_category_name | text | Category (Portuguese) | 1.85% (610) | 73 categories; 2 have no English translation |
| product_name_lenght | int | Characters in the product name | 1.85% | Source spells "lenght"; renamed to `product_name_length` in clean data |
| product_description_lenght | int | Characters in the description | 1.85% | Renamed to `product_description_length` |
| product_photos_qty | int | Number of photos | 1.85% | |
| product_weight_g | int | Weight (g) | 2 rows | Min 0 |
| product_length_cm, product_height_cm, product_width_cm | int | Package dimensions (cm) | 2 rows | |

## sellers — `olist_sellers_dataset.csv`

Grain: one row per seller. PK: `seller_id`. 3,095 rows.

| Column | Type | Meaning | Nulls |
|---|---|---|---|
| seller_id | text | Seller | 0 |
| seller_zip_code_prefix | text | Postcode prefix | 0 |
| seller_city | text | City (free text, some messy values) | 0 |
| seller_state | text | State | 0 |

## product_category_name_translation

Grain: one row per Portuguese category name. PK: `product_category_name`. 71 rows. Columns: `product_category_name`, `product_category_name_english`.

## geolocation — not used

One row per (zip prefix, lat/lng sample); 1,000,163 rows with many duplicates per prefix and some coordinates outside Brazil. Not needed for the planned metrics, so it is left out of the clean layer.

## Fields this dataset does **not** have

No product cost, margin or seller commission → no profit metrics. No refund, return, inventory, marketing or web-session data → no refund rate, stock or conversion metrics.
