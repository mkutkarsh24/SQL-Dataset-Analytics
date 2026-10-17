# SQL-Dataset-Analytics

A Python project for querying and analysing relational datasets with SQL (SQLite). It has two parts: an analytics script that runs common business queries, and a benchmark that measures how indexing and query rewriting affect performance. No external dependencies.

## Features
- **Analytics queries**: aggregations, `GROUP BY`, percentage-of-total, window functions (`RANK`, running totals, `LAG`) and CTEs
- **Multi-table joins**: customers, products and orders
- **Query optimization benchmark**: compares a baseline query with indexed and rewritten versions, checks the results are identical, and prints `EXPLAIN QUERY PLAN` output so you can see why a query got faster
- **Bring your own data**: load any CSV into SQLite from the command line

## Project structure
```
SQL-Dataset-Analytics/
├── sql_dataset_analytics.py          # sample sales data + analytics queries
├── query_optimization_benchmark.py   # indexing / query-rewrite benchmark
├── test_analytics.py                 # unit tests
├── requirements.txt
├── LICENSE
└── README.md
```

## Getting started
Requires Python 3.8+ (SQLite 3.25+ for window functions, included with modern Python).

```bash
git clone https://github.com/<your-username>/SQL-Dataset-Analytics.git
cd SQL-Dataset-Analytics
```

### Run the analytics
```bash
python sql_dataset_analytics.py
```

Load your own CSV:
```bash
python sql_dataset_analytics.py --csv your_data.csv --table sales
```

### Run the optimization benchmark
```bash
python query_optimization_benchmark.py
python query_optimization_benchmark.py --orders 500000 --repeat 5
```

Sample output (200,000 orders; timings vary by machine):

| Variant | Time |
|---|---|
| Baseline (no indexes) | ~57 ms |
| Baseline + covering index | ~32 ms (~44% faster) |
| CTE rewrite, no index | ~71 ms (slower) |

The index replaces a full table scan on `orders` with a date-range index search. The CTE rewrite was slower on this dataset, which is worth knowing: not every rewrite helps, so measure.

### Run the tests
```bash
python -m unittest -v
```

## Example queries
- Revenue by region with percent of total
- Top 3 products per category using `RANK() OVER (PARTITION BY ...)`
- Monthly revenue with a running total
- Month-over-month growth using `LAG`

## License
MIT
