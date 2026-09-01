"""Create star-schema tables in a local SQLite database.

Run before ETL to ensure tables exist.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'assignment.db')

DDL = [
    # Dimension: date
    """
    CREATE TABLE IF NOT EXISTS dim_date (
        date_key TEXT PRIMARY KEY,
        full_date TEXT,
        month INTEGER,
        quarter INTEGER,
        year INTEGER
    );
    """,

    # Dimension: product
    """
    CREATE TABLE IF NOT EXISTS dim_product (
        product_id TEXT PRIMARY KEY,
        product_name TEXT,
        category TEXT
    );
    """,

    # Dimension: customer (SCD Type 2 basic columns)
    """
    CREATE TABLE IF NOT EXISTS dim_customer (
        customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id TEXT,
        full_name TEXT,
        segment TEXT,
        region TEXT,
        city TEXT,
        country TEXT,
        is_current INTEGER DEFAULT 1,
        effective_date TEXT,
        expiration_date TEXT
    );
    """,

    # Fact table: sales at line-item grain
    """
    CREATE TABLE IF NOT EXISTS fact_sales (
        fact_sales_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        customer_id TEXT,
        product_id TEXT,
        order_date_key TEXT,
        quantity INTEGER,
        unit_price_local REAL,
        line_revenue_usd REAL,
        shipping_cost_usd REAL,
        status TEXT,
        channel TEXT
    );
    """,
]


def main():
    db_path = os.path.abspath(DB_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for stmt in DDL:
        cur.executescript(stmt)
    conn.commit()
    conn.close()
    print(f"Created schema at {db_path}")


if __name__ == '__main__':
    main()
