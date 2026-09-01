"""Generate Matplotlib dashboard images from exports CSVs.

Produces PNG files in ../exports/
"""
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import FuncFormatter

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
EXPORT_DIR = os.path.join(BASE_DIR, 'exports')
os.makedirs(EXPORT_DIR, exist_ok=True)

sns.set(style='darkgrid')


def plot_monthly_revenue():
    path = os.path.join(EXPORT_DIR, 'monthly_revenue.csv')
    df = pd.read_csv(path)
    df['sales_month'] = pd.to_datetime(df['sales_month'])
    df = df.sort_values('sales_month')

    plt.figure(figsize=(8,4))
    plt.plot(df['sales_month'], df['total_revenue_usd'], marker='o')
    plt.title('Monthly Revenue (Delivered)')
    plt.xlabel('Month')
    plt.ylabel('Revenue (USD)')
    plt.gca().yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    plt.tight_layout()
    out = os.path.join(EXPORT_DIR, 'monthly_revenue.png')
    plt.savefig(out)
    plt.close()
    print('Wrote', out)


def plot_top_products():
    path = os.path.join(EXPORT_DIR, 'top_products.csv')
    df = pd.read_csv(path)
    df = df.sort_values('revenue', ascending=False).head(10)

    plt.figure(figsize=(8,5))
    sns.barplot(x='revenue', y='product_name', data=df, palette='muted')
    plt.title('Top 10 Products by Revenue')
    plt.xlabel('Revenue (USD)')
    plt.gca().xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    plt.tight_layout()
    out = os.path.join(EXPORT_DIR, 'top_products.png')
    plt.savefig(out)
    plt.close()
    print('Wrote', out)


def plot_revenue_by_segment_channel():
    path = os.path.join(EXPORT_DIR, 'revenue_by_segment_channel.csv')
    df = pd.read_csv(path)
    # support multiple column name variants
    seg_col = 'segment' if 'segment' in df.columns else ('customer_segment' if 'customer_segment' in df.columns else None)
    rev_col = 'revenue' if 'revenue' in df.columns else ('revenue_usd' if 'revenue_usd' in df.columns else None)
    if seg_col is None or rev_col is None:
        print('Unexpected columns in', path, 'columns=', df.columns.tolist())
        return
    pivot = df.pivot_table(index=seg_col, columns='channel', values=rev_col, aggfunc='sum').fillna(0)
    pivot.plot(kind='bar', stacked=False, figsize=(10,5))
    plt.title('Revenue by Segment and Channel')
    plt.ylabel('Revenue (USD)')
    plt.gca().yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    plt.tight_layout()
    out = os.path.join(EXPORT_DIR, 'revenue_by_segment_channel.png')
    plt.savefig(out)
    plt.close()
    print('Wrote', out)


def plot_customer_rank():
    path = os.path.join(EXPORT_DIR, 'customer_rank.csv')
    df = pd.read_csv(path)
    # support different revenue column names
    rev_col = 'total_revenue' if 'total_revenue' in df.columns else ('total_revenue_usd' if 'total_revenue_usd' in df.columns else None)
    if rev_col is None:
        print('Unexpected columns in', path, 'columns=', df.columns.tolist())
        return
    df = df.sort_values(rev_col, ascending=False).head(10)
    plt.figure(figsize=(8,5))
    sns.barplot(x=rev_col, y='full_name', data=df, palette='deep')
    plt.title('Top 10 Customers by Revenue')
    plt.xlabel('Total Revenue (USD)')
    plt.gca().xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    plt.tight_layout()
    out = os.path.join(EXPORT_DIR, 'customer_rank.png')
    plt.savefig(out)
    plt.close()
    print('Wrote', out)


def main():
    plot_monthly_revenue()
    plot_top_products()
    plot_revenue_by_segment_channel()
    plot_customer_rank()


if __name__ == '__main__':
    main()
