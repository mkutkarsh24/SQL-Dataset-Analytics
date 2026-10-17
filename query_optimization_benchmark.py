"""
Query optimization benchmark for SQL-Dataset-Analytics.

Builds a relational dataset (customers, products, orders), then times the
same join + aggregation queries in three stages:
  1. baseline        - no indexes, correlated-subquery style query
  2. indexed         - indexes on join/filter columns
  3. indexed + CTE   - pre-aggregate before joining

It prints the timings, the % reduction vs. baseline, and the SQLite query
plans so the improvement can be explained, not just claimed.

Usage:
    python query_optimization_benchmark.py
    python query_optimization_benchmark.py --orders 300000 --repeat 5
"""

import argparse
import random
import sqlite3
import statistics
import time
from datetime import date, timedelta


def build_database(n_customers: int, n_products: int, n_orders: int) -> sqlite3.Connection:
    random.seed(7)
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT, region TEXT);
        CREATE TABLE products  (product_id  INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL);
        CREATE TABLE orders (
            order_id    INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product_id  INTEGER,
            order_date  TEXT,
            quantity    INTEGER
        );
        """
    )
    regions = ["North", "South", "East", "West"]
    categories = ["Electronics", "Home", "Books", "Toys", "Sports"]
    conn.executemany(
        "INSERT INTO customers VALUES (?,?,?)",
        [(i, f"Customer {i}", random.choice(regions)) for i in range(1, n_customers + 1)],
    )
    conn.executemany(
        "INSERT INTO products VALUES (?,?,?,?)",
        [
            (i, f"Product {i}", random.choice(categories), round(random.uniform(5, 900), 2))
            for i in range(1, n_products + 1)
        ],
    )
    start = date(2025, 1, 1)
    conn.executemany(
        "INSERT INTO orders VALUES (?,?,?,?,?)",
        [
            (
                i,
                random.randint(1, n_customers),
                random.randint(1, n_products),
                (start + timedelta(days=random.randint(0, 600))).isoformat(),
                random.randint(1, 5),
            )
            for i in range(1, n_orders + 1)
        ],
    )
    conn.commit()
    return conn


# Revenue per region/category for a date window, via joins + aggregation.
BASELINE_SQL = """
    SELECT c.region, p.category,
           SUM(o.quantity * p.price) AS revenue,
           COUNT(*)                  AS orders
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    JOIN products  p ON p.product_id  = o.product_id
    WHERE o.order_date BETWEEN '2025-06-01' AND '2025-08-31'
    GROUP BY c.region, p.category
    ORDER BY revenue DESC
"""

# Same result, but filter and pre-aggregate orders before joining dimensions.
OPTIMIZED_SQL = """
    WITH filtered AS (
        SELECT customer_id, product_id, SUM(quantity) AS qty, COUNT(*) AS n
        FROM orders
        WHERE order_date BETWEEN '2025-06-01' AND '2025-08-31'
        GROUP BY customer_id, product_id
    )
    SELECT c.region, p.category,
           SUM(f.qty * p.price) AS revenue,
           SUM(f.n)             AS orders
    FROM filtered f
    JOIN customers c ON c.customer_id = f.customer_id
    JOIN products  p ON p.product_id  = f.product_id
    GROUP BY c.region, p.category
    ORDER BY revenue DESC
"""

INDEXES = [
    "CREATE INDEX idx_orders_date     ON orders(order_date, customer_id, product_id, quantity)",
    "CREATE INDEX idx_orders_customer ON orders(customer_id)",
    "CREATE INDEX idx_orders_product  ON orders(product_id)",
]


def time_query(conn, sql: str, repeat: int) -> float:
    runs = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        conn.execute(sql).fetchall()
        runs.append(time.perf_counter() - t0)
    return statistics.median(runs)


def show_plan(conn, sql: str) -> None:
    for row in conn.execute("EXPLAIN QUERY PLAN " + sql):
        print("   ", row[-1])


def results(conn, sql):
    return [(r, c, round(rev, 2), n) for r, c, rev, n in conn.execute(sql).fetchall()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--customers", type=int, default=5_000)
    ap.add_argument("--products", type=int, default=500)
    ap.add_argument("--orders", type=int, default=200_000)
    ap.add_argument("--repeat", type=int, default=5)
    args = ap.parse_args()

    conn = build_database(args.customers, args.products, args.orders)
    print(f"Dataset: {args.customers:,} customers, {args.products:,} products, {args.orders:,} orders\n")

    expected = results(conn, BASELINE_SQL)
    assert results(conn, OPTIMIZED_SQL) == expected, "Optimized query changed the result!"

    base = time_query(conn, BASELINE_SQL, args.repeat)
    print(f"1) Baseline (no indexes):            {base * 1000:8.1f} ms")
    show_plan(conn, BASELINE_SQL)

    cte_only = time_query(conn, OPTIMIZED_SQL, args.repeat)
    print(f"\n2) Rewritten query (CTE), no index:  {cte_only * 1000:8.1f} ms")

    for stmt in INDEXES:
        conn.execute(stmt)
    conn.execute("ANALYZE")

    indexed = time_query(conn, BASELINE_SQL, args.repeat)
    print(f"\n3) Baseline query + indexes:         {indexed * 1000:8.1f} ms")
    show_plan(conn, BASELINE_SQL)

    both = time_query(conn, OPTIMIZED_SQL, args.repeat)
    print(f"\n4) Rewritten query + indexes:        {both * 1000:8.1f} ms")
    show_plan(conn, OPTIMIZED_SQL)

    assert results(conn, BASELINE_SQL) == expected
    print("\nResults identical across all variants: OK")
    print(f"Reduction vs baseline: indexes {100 * (1 - indexed / base):.1f}%, "
          f"rewrite {100 * (1 - cte_only / base):.1f}%, "
          f"both {100 * (1 - both / base):.1f}%")


if __name__ == "__main__":
    main()
