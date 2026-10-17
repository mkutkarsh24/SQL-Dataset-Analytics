"""
SQL-Dataset-Analytics
---------------------
A small, self-contained example of analysing a dataset with SQL.

It builds a sample sales dataset in an in-memory SQLite database and runs
common analytics queries: aggregations, GROUP BY, window functions, CTEs,
and ranking. No external packages are needed (pandas is optional).

Usage:
    python sql_dataset_analytics.py
    python sql_dataset_analytics.py --csv your_data.csv --table sales
"""

import argparse
import csv
import random
import sqlite3
from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Data setup
# ---------------------------------------------------------------------------
def create_sample_data(conn: sqlite3.Connection, rows: int = 500) -> None:
    """Create a synthetic `sales` table."""
    random.seed(42)
    conn.execute(
        """
        CREATE TABLE sales (
            order_id   INTEGER PRIMARY KEY,
            order_date TEXT,
            region     TEXT,
            category   TEXT,
            product    TEXT,
            quantity   INTEGER,
            unit_price REAL
        )
        """
    )
    regions = ["North", "South", "East", "West"]
    catalog = {
        "Electronics": [("Phone", 300), ("Laptop", 800), ("Earbuds", 60)],
        "Home": [("Lamp", 25), ("Chair", 90), ("Desk", 220)],
        "Books": [("Novel", 12), ("Textbook", 55), ("Comic", 8)],
    }
    start = date(2026, 1, 1)
    data = []
    for i in range(1, rows + 1):
        category = random.choice(list(catalog))
        product, price = random.choice(catalog[category])
        data.append(
            (
                i,
                (start + timedelta(days=random.randint(0, 270))).isoformat(),
                random.choice(regions),
                category,
                product,
                random.randint(1, 5),
                price,
            )
        )
    conn.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?,?)", data)
    conn.commit()


def load_csv(conn: sqlite3.Connection, path: str, table: str) -> None:
    """Load any CSV file into a SQLite table (all columns stored as TEXT/auto)."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        cols = ", ".join(f'"{h}"' for h in header)
        conn.execute(f'CREATE TABLE "{table}" ({cols})')
        placeholders = ",".join("?" * len(header))
        conn.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', reader)
    conn.commit()


# ---------------------------------------------------------------------------
# Analytics queries
# ---------------------------------------------------------------------------
QUERIES = {
    "1. Overall summary": """
        SELECT COUNT(*)                            AS total_orders,
               SUM(quantity)                       AS units_sold,
               ROUND(SUM(quantity * unit_price), 2) AS total_revenue,
               ROUND(AVG(quantity * unit_price), 2) AS avg_order_value
        FROM sales
    """,
    "2. Revenue by region": """
        SELECT region,
               ROUND(SUM(quantity * unit_price), 2) AS revenue,
               ROUND(100.0 * SUM(quantity * unit_price)
                     / (SELECT SUM(quantity * unit_price) FROM sales), 1) AS pct_of_total
        FROM sales
        GROUP BY region
        ORDER BY revenue DESC
    """,
    "3. Top 3 products per category (window function)": """
        SELECT category, product, revenue, rank_in_category
        FROM (
            SELECT category, product,
                   ROUND(SUM(quantity * unit_price), 2) AS revenue,
                   RANK() OVER (PARTITION BY category
                                ORDER BY SUM(quantity * unit_price) DESC) AS rank_in_category
            FROM sales
            GROUP BY category, product
        )
        WHERE rank_in_category <= 3
        ORDER BY category, rank_in_category
    """,
    "4. Monthly revenue with running total (CTE + window)": """
        WITH monthly AS (
            SELECT strftime('%Y-%m', order_date) AS month,
                   SUM(quantity * unit_price)    AS revenue
            FROM sales
            GROUP BY month
        )
        SELECT month,
               ROUND(revenue, 2) AS revenue,
               ROUND(SUM(revenue) OVER (ORDER BY month), 2) AS running_total
        FROM monthly
        ORDER BY month
    """,
    "5. Month-over-month growth (LAG)": """
        WITH monthly AS (
            SELECT strftime('%Y-%m', order_date) AS month,
                   SUM(quantity * unit_price)    AS revenue
            FROM sales
            GROUP BY month
        )
        SELECT month,
               ROUND(revenue, 2) AS revenue,
               ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
                     / LAG(revenue) OVER (ORDER BY month), 1) AS mom_growth_pct
        FROM monthly
        ORDER BY month
    """,
}


def print_table(cursor: sqlite3.Cursor) -> None:
    """Pretty-print query results without external dependencies."""
    headers = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    widths = [
        max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h))
        for i, h in enumerate(headers)
    ]
    line = " | ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("-" * len(line))
    for r in rows:
        print(" | ".join(str(v).ljust(w) for v, w in zip(r, widths)))


def main() -> None:
    parser = argparse.ArgumentParser(description="SQL dataset analytics demo")
    parser.add_argument("--csv", help="Optional CSV file to load instead of sample data")
    parser.add_argument("--table", default="data", help="Table name for the CSV")
    args = parser.parse_args()

    conn = sqlite3.connect(":memory:")

    if args.csv:
        load_csv(conn, args.csv, args.table)
        print(f"Loaded {args.csv} into table '{args.table}'.")
        print("Write your own SQL against it with conn.execute(...).")
        return

    create_sample_data(conn)
    for title, sql in QUERIES.items():
        print(f"\n=== {title} ===")
        print_table(conn.execute(sql))

    conn.close()


if __name__ == "__main__":
    main()
