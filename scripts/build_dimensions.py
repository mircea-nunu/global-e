"""Build dimension tables and implement SCD Type 2 for dim_customer.

Outputs:
- dim_date, dim_product, dim_customer (SCD Type 2)
- fact_sales will get an updated `customer_key` foreign key via a new table `fact_sales_enriched`
"""
import sqlite3
import os
import pandas as pd
from datetime import datetime, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
DB_PATH = os.path.join(BASE_DIR, 'assignment.db')


def create_dim_date(conn):
    df = pd.read_sql("SELECT DISTINCT order_date_key FROM fact_sales", conn)
    df['full_date'] = pd.to_datetime(df['order_date_key']).dt.date
    df['date_key'] = df['full_date'].astype(str)
    df['month'] = pd.to_datetime(df['full_date']).dt.month
    df['quarter'] = pd.to_datetime(df['full_date']).dt.quarter
    df['year'] = pd.to_datetime(df['full_date']).dt.year

    dim = df[['date_key', 'full_date', 'month', 'quarter', 'year']].drop_duplicates()
    dim.to_sql('dim_date', conn, if_exists='replace', index=False)


def create_dim_product(conn):
    # gather product attributes from order_lines_staging
    try:
        df = pd.read_sql('SELECT DISTINCT product_id, product_name, category FROM order_lines_staging', conn)
    except Exception:
        df = pd.read_sql('SELECT DISTINCT product_id FROM fact_sales', conn)
        df['product_name'] = None
        df['category'] = None

    # Normalize product category values so case-only drift doesn't create duplicate rows.
    df['category'] = df['category'].fillna('Unknown').astype(str).str.strip().str.title()
    df['product_name'] = df['product_name'].fillna(df['product_id'])

    # Detect products with conflicting category values and log them as data quality issues.
    dup_categories = (
        df.groupby('product_id', as_index=False)
          .agg(category_variants=('category', lambda s: sorted(s.unique().tolist())))
    )
    dup_categories = dup_categories[dup_categories['category_variants'].map(len) > 1]
    if not dup_categories.empty:
        for _, row in dup_categories.iterrows():
            print(f"Data quality issue: product {row['product_id']} has multiple categories -> {row['category_variants']}")

    # Choose a canonical category per product_id so dim_product stays unique by business key.
    canonical = (
        df.groupby('product_id', as_index=False)
          .agg(
              product_name=('product_name', lambda s: s.dropna().iloc[0] if s.notna().any() else None),
              category=('category', lambda s: s.mode().iloc[0] if len(s.mode()) else 'Unknown')
          )
    )

    canonical.to_sql('dim_product', conn, if_exists='replace', index=False)


def build_scd_customers(conn):
    # load customer-level rows from orders_staging
    orders = pd.read_sql('SELECT order_id, customer_id, customer_full_name, customer_segment, order_date FROM orders_staging', conn)
    if orders.empty:
        return

    # normalize dates
    orders['order_date'] = pd.to_datetime(orders['order_date'])

    # for each customer and segment, take earliest order_date as effective_date
    grouped = orders.groupby(['customer_id', 'customer_full_name', 'customer_segment']).agg({'order_date': 'min'}).reset_index()
    grouped = grouped.sort_values(['customer_id', 'order_date'])

    scd_rows = []
    for cid, g in grouped.groupby('customer_id'):
        g = g.sort_values('order_date')
        for i, row in g.iterrows():
            eff = row['order_date'].date()
            scd_rows.append({
                'customer_id': row['customer_id'],
                'full_name': row['customer_full_name'],
                'segment': row['customer_segment'],
                'effective_date': str(eff),
                'expiration_date': None,
                'is_current': 1
            })
    scd_df = pd.DataFrame(scd_rows)

    # set expiration_date as next effective_date - 1 day per customer
    if not scd_df.empty:
        new_rows = []
        for cid, g in scd_df.groupby('customer_id'):
            g = g.sort_values('effective_date')
            dates = list(g['effective_date'])
            for i, r in g.iterrows():
                row = r.to_dict()
                idx = list(g.index).index(i)
                if idx < len(dates) - 1:
                    next_eff = pd.to_datetime(dates[idx+1])
                    row['expiration_date'] = str((next_eff - pd.Timedelta(days=1)).date())
                    row['is_current'] = 0
                new_rows.append(row)
        scd_df = pd.DataFrame(new_rows)

    scd_df.to_sql('dim_customer', conn, if_exists='replace', index_label='customer_key')


def enrich_fact_sales(conn):
    # join fact_sales to dim_customer using customer_id and order_date in the logic
    fact = pd.read_sql('SELECT * FROM fact_sales', conn)
    dims = pd.read_sql('SELECT rowid as scd_key, customer_id, full_name, segment, effective_date, expiration_date, is_current FROM dim_customer', conn)
    if fact.empty or dims.empty:
        return

    fact['order_date'] = pd.to_datetime(fact['order_date_key']).dt.date
    dims['effective_date'] = pd.to_datetime(dims['effective_date']).dt.date
    dims['expiration_date'] = pd.to_datetime(dims['expiration_date'], errors='coerce').dt.date

    # for each fact row, find matching dim row where customer_id matches and order_date between effective and expiration (or is_current)
    merged_keys = []
    for _, fr in fact.iterrows():
        cust_id = fr['customer_id']
        od = fr['order_date']
        candidate = dims[(dims['customer_id'] == cust_id) & (dims['effective_date'] <= od) & ((dims['expiration_date'].isna()) | (dims['expiration_date'] >= od))]
        if not candidate.empty:
            merged_keys.append(int(candidate.iloc[0]['scd_key']))
        else:
            merged_keys.append(None)
    fact['customer_key'] = merged_keys

    fact.to_sql('fact_sales_enriched', conn, if_exists='replace', index=False)


def main():
    conn = sqlite3.connect(DB_PATH)
    create_dim_date(conn)
    create_dim_product(conn)
    build_scd_customers(conn)
    enrich_fact_sales(conn)
    conn.close()
    print('Dimensions created and fact_sales_enriched written to DB')


if __name__ == '__main__':
    main()
