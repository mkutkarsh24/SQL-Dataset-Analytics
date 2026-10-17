"""Unit tests for SQL-Dataset-Analytics."""

import sqlite3
import unittest

import query_optimization_benchmark as bench
import sql_dataset_analytics as analytics


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        analytics.create_sample_data(self.conn, rows=200)

    def tearDown(self):
        self.conn.close()

    def test_row_count(self):
        n = self.conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        self.assertEqual(n, 200)

    def test_all_queries_run(self):
        for title, sql in analytics.QUERIES.items():
            rows = self.conn.execute(sql).fetchall()
            self.assertTrue(rows, f"{title} returned no rows")

    def test_region_percentages_sum_to_100(self):
        rows = self.conn.execute(analytics.QUERIES["2. Revenue by region"]).fetchall()
        self.assertAlmostEqual(sum(r[2] for r in rows), 100.0, delta=0.5)

    def test_running_total_matches_total_revenue(self):
        total = self.conn.execute("SELECT SUM(quantity * unit_price) FROM sales").fetchone()[0]
        rows = self.conn.execute(
            analytics.QUERIES["4. Monthly revenue with running total (CTE + window)"]
        ).fetchall()
        self.assertAlmostEqual(rows[-1][2], total, places=1)

    def test_first_month_has_no_growth(self):
        rows = self.conn.execute(analytics.QUERIES["5. Month-over-month growth (LAG)"]).fetchall()
        self.assertIsNone(rows[0][2])


class BenchmarkTests(unittest.TestCase):
    def test_optimized_query_returns_same_results(self):
        conn = bench.build_database(200, 50, 5000)
        self.assertEqual(
            bench.results(conn, bench.BASELINE_SQL),
            bench.results(conn, bench.OPTIMIZED_SQL),
        )

    def test_indexes_do_not_change_results(self):
        conn = bench.build_database(200, 50, 5000)
        before = bench.results(conn, bench.BASELINE_SQL)
        for stmt in bench.INDEXES:
            conn.execute(stmt)
        self.assertEqual(before, bench.results(conn, bench.BASELINE_SQL))


if __name__ == "__main__":
    unittest.main()
