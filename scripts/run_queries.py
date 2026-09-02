"""Run analytical SQL queries and export results as CSVs for Power BI.

Outputs (in ../exports/):
- monthly_revenue.csv
- top_products.csv
- revenue_by_segment_channel.csv
- customer_rank.csv
"""
import os
import sqlite3

import pandas as pd

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
DB_PATH = os.path.join(BASE_DIR, 'assignment.db')
EXPORT_DIR = os.path.join(BASE_DIR, 'exports')

os.makedirs(EXPORT_DIR, exist_ok=True)

con = sqlite3.connect(DB_PATH)

queries = {
    'monthly_revenue.csv': '''
        SELECT
            strftime('%Y-%m', date(order_date_key)) AS sales_month,
            SUM(line_revenue_usd) AS total_revenue_usd
        FROM fact_sales
        WHERE status = 'Delivered'
        GROUP BY sales_month
        ORDER BY sales_month;
    ''',

    'top_products.csv': '''
        SELECT
            p.product_id,
            p.product_name,
            SUM(f.line_revenue_usd) AS revenue,
            ROUND(
                100.0 * SUM(f.line_revenue_usd) /
                NULLIF((SELECT SUM(line_revenue_usd) FROM fact_sales WHERE status = 'Delivered'), 0),
                2
            ) AS pct_share
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_id = p.product_id
        WHERE f.status = 'Delivered'
        GROUP BY p.product_id, p.product_name
        ORDER BY revenue DESC;
    ''',

    'revenue_by_segment_channel.csv': '''
        SELECT
            COALESCE(d.segment, 'Unknown') AS segment,
            COALESCE(f.channel, 'Unknown') AS channel,
            SUM(f.line_revenue_usd) AS revenue
        FROM fact_sales f
        LEFT JOIN dim_customer d
          ON f.customer_id = d.customer_id
         AND d.is_current = 1
        WHERE f.status = 'Delivered'
        GROUP BY segment, channel
        ORDER BY revenue DESC;
    ''',

    'customer_rank.csv': '''
        SELECT
            f.customer_id,
            d.full_name,
            COUNT(DISTINCT f.order_id) AS order_count,
            SUM(f.line_revenue_usd) AS total_revenue,
            DENSE_RANK() OVER (ORDER BY SUM(f.line_revenue_usd) DESC) AS revenue_rank
        FROM fact_sales f
        LEFT JOIN dim_customer d
          ON f.customer_id = d.customer_id
         AND d.is_current = 1
        WHERE f.status = 'Delivered'
        GROUP BY f.customer_id, d.full_name
        ORDER BY total_revenue DESC;
    ''',
}

for fname, q in queries.items():
    df = pd.read_sql_query(q, con)
    out_path = os.path.join(EXPORT_DIR, fname)
    df.to_csv(out_path, index=False)
    print(f'Wrote {out_path} ({len(df)} rows)')

con.close()
