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
        currency = o.get('currency', 'USD')
        shipping = o.get('shipping_cost', 0.0)
        order_date = o.get('order_date') or o.get('created_at')

        # extract customer nested info if present
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

        # support multiple common keys for line items
        for li in o.get('lines', []) or o.get('order_lines', []) or o.get('line_items', []):
            product_id = li.get('product_id')
            qty = li.get('quantity', 1)
            unit_price = li.get('unit_price', li.get('unit_price_local', 0.0))

            # currency conversion to USD
            if currency == 'EUR':
                unit_price_usd = float(unit_price) * RATE_EUR_USD
                shipping_usd = float(shipping) * RATE_EUR_USD
            else:
                unit_price_usd = float(unit_price)
                shipping_usd = float(shipping)

            line_revenue_usd = qty * unit_price_usd

            lines_rows.append({
                'order_id': order_id,
                'product_id': product_id,
                'product_name': li.get('product_name'),
                'category': li.get('category'),
                'quantity': qty,
                'unit_price_local': unit_price,
                'unit_price_usd': unit_price_usd,
                'line_revenue_usd': line_revenue_usd,
                'shipping_cost_usd': shipping_usd
            })

            # basic quality checks
            if isinstance(li.get('category'), str) and li.get('category') != li.get('category').title():
                dq_issues.append(f"Category casing drift product {product_id} in order {order_id}")
            if li.get('product_id') and li.get('unit_price') is None:
                dq_issues.append(f"Missing price for product {product_id} in order {order_id}")

    orders_df = pd.DataFrame(orders_rows)
    lines_df = pd.DataFrame(lines_rows)
    return orders_df, lines_df, dq_issues


def write_sqlite(orders_df, lines_df):
    conn = sqlite3.connect(DB_PATH)
    orders_df.to_sql('orders_staging', conn, if_exists='replace', index=False)
    lines_df.to_sql('order_lines_staging', conn, if_exists='replace', index=False)

    # move into star schema fact_sales
    cur = conn.cursor()

    # delete existing fact_sales rows for orders present in staging to avoid duplicates
    cur.execute("SELECT order_id FROM orders_staging")
    staging_order_ids = [r[0] for r in cur.fetchall()]
    if staging_order_ids:
        # use a parameterized delete in chunks
        placeholders = ','.join('?' for _ in staging_order_ids)
        cur.execute(f"DELETE FROM fact_sales WHERE order_id IN ({placeholders})", staging_order_ids)

    # Insert/append into fact_sales mapping basic columns
    cur.executescript("""
    INSERT INTO fact_sales (order_id, customer_id, product_id, order_date_key, quantity, unit_price_local, line_revenue_usd, shipping_cost_usd, status, channel)
    SELECT
        o.order_id,
        o.customer_id,
        l.product_id,
        o.order_date,
        l.quantity,
        l.unit_price_local,
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
