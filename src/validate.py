"""Reconcile the mart against the clean source tables. Any failed assertion stops with exit code 1.

Checks: row counts (no rows lost or duplicated by joins), money totals, key uniqueness and
metric denominators.

Run after src/build_db.py:  python src/validate.py
"""
import sys

import duckdb

from config import DB_PATH

# (description, SQL returning the actual value, SQL returning the expected value)
CHECKS = [
    ("fct_orders: one row per source order",
     "SELECT COUNT(*) FROM fct_orders", "SELECT COUNT(*) FROM orders"),
    ("fct_orders: order_id unique",
     "SELECT COUNT(DISTINCT order_id) FROM fct_orders", "SELECT COUNT(*) FROM fct_orders"),
    ("fct_orders: product value = sum of item prices",
     "SELECT ROUND(SUM(product_value), 2) FROM fct_orders",
     "SELECT ROUND(SUM(price), 2) FROM order_items"),
    ("fct_orders: freight value = sum of item freight",
     "SELECT ROUND(SUM(freight_value), 2) FROM fct_orders",
     "SELECT ROUND(SUM(freight_value), 2) FROM order_items"),
    ("fct_orders: payment value = sum of payments",
     "SELECT ROUND(SUM(payment_value), 2) FROM fct_orders",
     "SELECT ROUND(SUM(payment_value), 2) FROM payments"),
    ("fct_orders: item count = item rows",
     "SELECT SUM(n_items) FROM fct_orders", "SELECT COUNT(*) FROM order_items"),
    ("fct_orders: reviewed orders = distinct reviewed order_ids",
     "SELECT COUNT(review_score) FROM fct_orders",
     "SELECT COUNT(DISTINCT order_id) FROM reviews"),
    ("fct_orders: every valid order has a customer_order_seq",
     "SELECT COUNT(customer_order_seq) FROM fct_orders",
     "SELECT COUNT(*) FROM fct_orders WHERE is_valid"),
    ("fct_orders: is_late defined exactly for delivered orders",
     "SELECT COUNT(is_late) FROM fct_orders",
     "SELECT COUNT(*) FROM orders WHERE order_status = 'delivered' "
     "AND order_delivered_customer_date IS NOT NULL"),
    ("dim_customer: repeat customers = people with a return order",
     "SELECT COUNT(*) FROM dim_customer WHERE is_repeat_customer",
     "SELECT COUNT(DISTINCT customer_unique_id) FROM fct_orders WHERE is_return_order"),
    ("fct_order_items: one row per source item",
     "SELECT COUNT(*) FROM fct_order_items", "SELECT COUNT(*) FROM order_items"),
    ("fct_order_items: price total unchanged",
     "SELECT ROUND(SUM(price), 2) FROM fct_order_items",
     "SELECT ROUND(SUM(price), 2) FROM order_items"),
    ("dim_customer: one row per person with a valid order",
     "SELECT COUNT(*) FROM dim_customer",
     "SELECT COUNT(DISTINCT customer_unique_id) FROM fct_orders WHERE is_valid"),
    ("dim_customer: order count = valid orders",
     "SELECT SUM(n_orders) FROM dim_customer", "SELECT COUNT(*) FROM fct_orders WHERE is_valid"),
    ("dim_customer: exactly one first order per person",
     "SELECT COUNT(*) FROM fct_orders WHERE customer_order_seq = 1",
     "SELECT COUNT(*) FROM dim_customer"),
    ("dim_date: covers every purchase date",
     "SELECT COUNT(*) FROM fct_orders o LEFT JOIN dim_date d ON o.purchase_date = d.date "
     "WHERE d.date IS NULL", "SELECT 0"),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    failed = 0
    for description, actual_sql, expected_sql in CHECKS:
        actual = con.execute(actual_sql).fetchone()[0]
        expected = con.execute(expected_sql).fetchone()[0]
        ok = actual == expected
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {description}: {actual:,} (expected {expected:,})")
    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} checks passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
