"""Simple ETL starter:
- Reads `orders_raw.json` (array of orders)
- Flattens into `orders` and `order_lines` DataFrames
- Converts EUR amounts to USD (1 EUR = 1.08 USD)
- Writes results into `assignment.db` SQLite database

Usage: python etl.py orders_raw.json
"""
import sys
import os
import json
from datetime import datetime
import pandas as pd
import sqlite3

RATE_EUR_USD = 1.08

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
DB_PATH = os.path.join(BASE_DIR, 'assignment.db')


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_orders(raw_orders):
    orders_rows = []
    lines_rows = []
    dq_issues = []

    for o in raw_orders:
        order_id = o.get('order_id') or o.get('id')
        currency = str(o.get('currency', 'USD') or 'USD').upper()
        shipping = float(o.get('shipping_cost', 0.0) or 0.0)
        order_date = o.get('order_date') or o.get('created_at')

        cust = o.get('customer') or {}
        orders_rows.append({
            'order_id': order_id,
            'customer_id': cust.get('customer_id') or o.get('customer_id'),
            'customer_full_name': cust.get('full_name'),
            'customer_segment': cust.get('segment'),
            'customer_region': cust.get('region'),
            'customer_city': cust.get('city'),
            'customer_country': cust.get('country'),
            'order_date': order_date,
            'currency': currency,
            'shipping_cost': shipping,
            'status': o.get('status'),
            'channel': o.get('channel')
        })

        for li in o.get('lines', []) or o.get('order_lines', []) or o.get('line_items', []):
            product_id = li.get('product_id')
            qty = float(li.get('quantity', 1) or 1)
            unit_price = float(li.get('unit_price', li.get('unit_price_local', 0.0)) or 0.0)
            discount_pct = float(li.get('discount_pct', 0.0) or 0.0)

            line_revenue_local = qty * unit_price * (1 - (discount_pct / 100.0))
            if currency == 'EUR':
                exchange_rate_usd = RATE_EUR_USD
                line_revenue_usd = line_revenue_local * exchange_rate_usd
            else:
                exchange_rate_usd = 1.0
                line_revenue_usd = line_revenue_local

            shipping_usd = float(shipping) * exchange_rate_usd if currency == 'EUR' else float(shipping)

            lines_rows.append({
                'order_id': order_id,
                'product_id': product_id,
                'product_name': li.get('product_name'),
                'category': li.get('category'),
                'quantity': qty,
                'unit_price_local': unit_price,
                'discount_pct': discount_pct,
                'line_revenue_local': line_revenue_local,
                'currency': currency,
                'exchange_rate_usd': exchange_rate_usd,
                'line_revenue_usd': line_revenue_usd,
                'shipping_cost_usd': shipping_usd
            })

            if isinstance(li.get('category'), str) and li.get('category') != li.get('category').title():
                dq_issues.append(f"Category casing drift product {product_id} in order {order_id}")
            if li.get('product_id') and li.get('unit_price') is None:
                dq_issues.append(f"Missing price for product {product_id} in order {order_id}")

    orders_df = pd.DataFrame(orders_rows)
    lines_df = pd.DataFrame(lines_rows)
    return orders_df, lines_df, dq_issues


def ensure_schema(conn):
    cur = conn.cursor()

    cur.execute("CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, customer_id TEXT, customer_full_name TEXT, customer_segment TEXT, customer_region TEXT, customer_city TEXT, customer_country TEXT, order_date TEXT, currency TEXT, shipping_cost REAL, status TEXT, channel TEXT)")

    columns = {row[1]: row[2] for row in cur.execute("PRAGMA table_info(fact_sales)").fetchall()}
    required_columns = {
        'discount_pct': 'REAL',
        'line_revenue_local': 'REAL',
        'currency': 'TEXT',
        'exchange_rate_usd': 'REAL',
    }
    for col_name, col_type in required_columns.items():
        if col_name not in columns:
            cur.execute(f"ALTER TABLE fact_sales ADD COLUMN {col_name} {col_type}")


def write_sqlite(orders_df, lines_df):
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    orders_df.to_sql('orders_staging', conn, if_exists='replace', index=False)
    lines_df.to_sql('order_lines_staging', conn, if_exists='replace', index=False)

    cur = conn.cursor()

    cur.execute("SELECT order_id FROM orders_staging")
    staging_order_ids = [r[0] for r in cur.fetchall()]
    if staging_order_ids:
        placeholders = ','.join('?' for _ in staging_order_ids)
        cur.execute(f"DELETE FROM fact_sales WHERE order_id IN ({placeholders})", staging_order_ids)

    cur.execute("""
    INSERT OR REPLACE INTO orders (
        order_id, customer_id, customer_full_name, customer_segment, customer_region,
        customer_city, customer_country, order_date, currency, shipping_cost, status, channel
    )
    SELECT
        order_id, customer_id, customer_full_name, customer_segment, customer_region,
        customer_city, customer_country, order_date, currency, shipping_cost, status, channel
    FROM orders_staging
    """)

    cur.executescript("""
    INSERT INTO fact_sales (
        order_id, customer_id, product_id, order_date_key, quantity, unit_price_local,
        discount_pct, line_revenue_local, currency, exchange_rate_usd, line_revenue_usd,
        shipping_cost_usd, status, channel
    )
    SELECT
        o.order_id,
        o.customer_id,
        l.product_id,
        o.order_date,
        l.quantity,
        l.unit_price_local,
        l.discount_pct,
        l.line_revenue_local,
        l.currency,
        l.exchange_rate_usd,
        l.line_revenue_usd,
        l.shipping_cost_usd,
        o.status,
        o.channel
    FROM orders_staging o
    JOIN order_lines_staging l USING(order_id);
    """)

    conn.commit()
    conn.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python etl.py orders_raw.json")
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"File not found: {path}")
        sys.exit(1)

    raw = load_json(path)
    # support file formats where orders are nested under a top-level key
    if isinstance(raw, dict) and 'orders' in raw:
        raw = raw['orders']
    orders_df, lines_df, dq_issues = normalize_orders(raw)

    # basic logging
    dq_path = os.path.join(os.path.dirname(__file__), '..', 'data_quality_log.md')
    with open(dq_path, 'w', encoding='utf-8') as f:
        f.write('# Data Quality Log\n')
        for i in dq_issues:
            f.write('- ' + i + '\n')

    write_sqlite(orders_df, lines_df)
    print('ETL complete. Check assignment.db and data_quality_log.md')


if __name__ == '__main__':
    main()
