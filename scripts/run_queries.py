"""Run analytical SQL queries and export results as CSVs for Power BI.

Outputs (in `../exports/`):
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
            strftime('%Y-%m', date(order_date_key)) as sales_month,
            SUM(line_revenue_usd) as total_revenue_usd
        FROM fact_sales
        WHERE status = 'Delivered'
        GROUP BY sales_month
        ORDER BY sales_month;
    ''',

    'top_products.csv': '''
        SELECT
            COALESCE(p.product_id, f.product_id) as product_id,
            p.product_name,
            SUM(f.line_revenue_usd) as revenue,
            100.0 * SUM(f.line_revenue_usd) / SUM(SUM(f.line_revenue_usd)) OVER () as pct_share
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_id = p.product_id
        GROUP BY COALESCE(p.product_id, f.product_id), p.product_name
        ORDER BY revenue DESC;
    ''',

    'revenue_by_segment_channel.csv': '''
        SELECT
            COALESCE(d.segment, 'Unknown') as segment,
            COALESCE(f.channel, 'Unknown') as channel,
            SUM(f.line_revenue_usd) as revenue
        FROM fact_sales f
        LEFT JOIN dim_customer d ON f.customer_id = d.customer_id AND d.is_current = 1
        GROUP BY segment, channel
        ORDER BY revenue DESC;
    ''',

    'customer_rank.csv': '''
        SELECT
            f.customer_id,
            d.full_name,
            COUNT(DISTINCT f.order_id) as order_count,
            SUM(f.line_revenue_usd) as total_revenue,
            DENSE_RANK() OVER (ORDER BY SUM(f.line_revenue_usd) DESC) as revenue_rank
        FROM fact_sales f
        LEFT JOIN dim_customer d ON f.customer_id = d.customer_id AND d.is_current = 1
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
"""Run analytical SQL queries against assignment.db and export CSVs for Power BI."""
import os
import sqlite3
import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), '..')
DB = os.path.join(BASE, 'assignment.db')
OUT = os.path.join(BASE, 'exports')
os.makedirs(OUT, exist_ok=True)

con = sqlite3.connect(DB)

queries = {
    'monthly_revenue_delivered': (
        """
        SELECT
            strftime('%Y-%m', order_date_key) as sales_month,
            SUM(line_revenue_usd) as total_revenue_usd
        FROM fact_sales
        WHERE status = 'Delivered'
        GROUP BY sales_month
        ORDER BY sales_month
        """
    ),

    'top_products_share': (
        """
        WITH product_totals AS (
            SELECT product_id, SUM(line_revenue_usd) AS product_revenue
            FROM fact_sales
            GROUP BY product_id
        ), total AS (
            SELECT SUM(product_revenue) AS total_revenue FROM product_totals
        )
        SELECT
            p.product_id,
            p.product_revenue,
            ROUND(100.0 * p.product_revenue / t.total_revenue, 2) AS pct_share
        FROM product_totals p CROSS JOIN total t
        ORDER BY p.product_revenue DESC
        """
    ),

    'revenue_by_segment_channel': (
        """
        SELECT
            dc.segment as customer_segment,
            f.channel,
            SUM(f.line_revenue_usd) as revenue_usd
        FROM fact_sales f
        LEFT JOIN dim_customer dc ON f.customer_id = dc.customer_id
        GROUP BY dc.segment, f.channel
        ORDER BY dc.segment, f.channel
        """
    ),

    'customer_rank': (
        """
        SELECT
            f.customer_id,
            dc.full_name,
            COUNT(DISTINCT f.order_id) AS order_count,
            SUM(f.line_revenue_usd) AS total_revenue_usd,
            RANK() OVER (ORDER BY SUM(f.line_revenue_usd) DESC) AS revenue_rank
        FROM fact_sales f
        LEFT JOIN dim_customer dc ON f.customer_id = dc.customer_id
        GROUP BY f.customer_id
        ORDER BY total_revenue_usd DESC
        """
    ),
}

for name, q in queries.items():
    try:
        df = pd.read_sql_query(q, con)
    except Exception as e:
        # Some SQLite versions may not support window functions; emulate ranking if needed
        if 'no such function: RANK' in str(e) or 'syntax error' in str(e):
            if name == 'customer_rank':
                df = pd.read_sql_query(
                    """
                    SELECT customer_id, SUM(line_revenue_usd) as total_revenue_usd
                    FROM fact_sales
                    GROUP BY customer_id
                    ORDER BY total_revenue_usd DESC
                    """, con)
                df['order_count'] = df.apply(lambda r: 0, axis=1)
                df['revenue_rank'] = df['total_revenue_usd'].rank(method='dense', ascending=False).astype(int)
            else:
                raise
        else:
            raise

    out_path = os.path.join(OUT, f"{name}.csv")
    df.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")

con.close()
