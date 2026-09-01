# Assignment — End-to-end Plan & Repo

This repository contains a modular, checkpointed plan to complete the assessment within 2–3 hours.

## Decisions taken for implementation
- Database: SQLite 3 (`assignment.db`) — chosen for portability and local Power BI connectivity.
- Dashboard: Interactive static site (`site/index.html`) with Plotly.js charts rendering from CSV exports — published to GitHub Pages via Actions.
- Currency conversion: `1 EUR = 1.08 USD`. Shipping costs in EUR will be converted to USD.
- SCD strategy: **SCD Type 2** for `dim_customer` (preserves history).

---

## Data Model

📊 **Star Schema Architecture**

See [Data Model Documentation](docs/DATA_MODEL.md) for the complete schema specification.

**Visual Diagram:**
![Star Schema](docs/star_schema_diagram.svg)

**Key Tables:**
- **FACT_SALES** (central fact table, line-item grain)
  - Links to dim_date, dim_product, dim_customer, and implicitly channel
  - 47 line items across 12 orders
  
- **DIM_DATE** (SCD Type 1)
  - Temporal dimensions for analysis (month, quarter, year)
  
- **DIM_PRODUCT** (SCD Type 1)
  - Product details and category
  
- **DIM_CUSTOMER** (SCD Type 2)
  - Tracks customer segment, region, and contact changes over time
  - Enables historical "as-of" queries and accurate revenue attribution

---

## Question A: Slowly Changing Dimension Strategy

### Q-A: How would you handle slowly changing dimensions in this model?

**Answer:**

We implemented **SCD Type 2** for the `dim_customer` table to preserve the full history of customer attributes while enabling accurate historical analysis.

**Why SCD Type 2?**

1. **Business Requirement:** Customers transition between segments (e.g., SMB → Enterprise) as their business grows. Understanding historical segment affiliation is critical for trend analysis.

2. **Accurate Reporting:** When analyzing "Q2 revenue by customer segment," we need to use the segment value that was *active during Q2*, not the current segment. Without SCD Type 2, past reports would be retroactively rewritten.

3. **Auditability:** Every change is timestamped with `effective_date` and `expiration_date`, providing a complete audit trail.

**Implementation:**

```sql
-- DIM_CUSTOMER structure with SCD Type 2
CREATE TABLE dim_customer (
    customer_key INTEGER PRIMARY KEY,      -- Surrogate key (tracks versions)
    customer_id TEXT,                      -- Business key (customer ID)
    full_name TEXT,
    segment TEXT,                          -- Dimension attribute
    region TEXT,
    city TEXT,
    country TEXT,
    is_current INTEGER DEFAULT 1,          -- 1 = active, 0 = historical
    effective_date TEXT,                   -- Start date of this version
    expiration_date TEXT                   -- End date (NULL = current)
);
```

**Example:** Customer segment upgrade
```
customer_key | customer_id | segment      | is_current | effective_date | expiration_date
1            | CUST-001    | SMB          | 0          | 2023-01-15     | 2024-06-30
2            | CUST-001    | Enterprise   | 1          | 2024-07-01     | NULL
```

**Query Impact:**

```sql
-- Current segment (standard report)
SELECT customer_id, segment
FROM dim_customer
WHERE is_current = 1;

-- Historical as-of Q2 2024
SELECT customer_id, segment
FROM dim_customer
WHERE effective_date <= '2024-06-30' AND (expiration_date IS NULL OR expiration_date > '2024-06-30');
```

**When Would We Use SCD Type 1 or Type 3?**
- **SCD Type 1:** For attributes that don't need history (e.g., product category corrections, data corrections). Simpler, but loses history.
- **SCD Type 3:** If we only need to compare current vs. previous value (e.g., "previous_segment"). Less storage than Type 2, but limited history depth.

---

## Question B: Incremental Load Strategy

### Q-B: How would you design an incremental load for this pipeline?

**Answer:**

An incremental load strategy would replace the current full-reload approach with a **change-data-capture (CDC) and delta-merge pattern** to handle recurring data syncs efficiently.

**Current State (Full Load):**
- Every run: Delete all tables → Re-extract JSON → Re-load into SQLite
- Pros: Simplicity, consistency, full re-validation
- Cons: Inefficient for large datasets; loses performance advantage of incremental updates

**Proposed Incremental Strategy:**

**1. Extract Phase: Change Detection**

```python
# Pseudo-code: incremental extract
def extract_new_orders(last_sync_timestamp):
    """Only fetch orders modified since last run."""
    new_orders = [o for o in orders if o['updated_at'] > last_sync_timestamp]
    updated_orders = [o for o in orders if o['updated_at'] > last_sync_timestamp and o['id'] in existing_ids]
    return new_orders, updated_orders
```

**Implementation:**
- Add a `last_sync_timestamp` checkpoint file (`checkpoints/last_sync.txt`)
- Call ERP API with `?updated_since=<timestamp>` filter (if available)
- Parse only new/modified orders from `orders_raw.json`

**2. Load Phase: Upsert Logic**

```sql
-- Upsert fact_sales (replace if exists, insert if new)
INSERT INTO fact_sales (order_id, customer_id, ..., line_revenue_usd)
SELECT order_id, customer_id, ..., line_revenue_usd
FROM staged_orders
ON CONFLICT(order_id) DO UPDATE SET
    status = excluded.status,
    line_revenue_usd = excluded.line_revenue_usd,
    updated_at = datetime('now');
```

**Key Points:**
- Use `ON CONFLICT` (SQLite) or `MERGE` (SQL Server) to idempotently handle retries
- Only update fields that may have changed (status, shipping cost)
- Preserve historical fact records for audit

**3. Dimension Phase: SCD Type 2 for Customers**

```sql
-- Handle customer segment changes
UPDATE dim_customer
SET is_current = 0, expiration_date = datetime('now')
WHERE customer_id = ? AND segment != ? AND is_current = 1;

INSERT INTO dim_customer (customer_id, segment, ..., is_current, effective_date)
VALUES (?, ?, ..., 1, datetime('now'));
```

**4. Checkpoint & Recovery**

```python
# After successful load, record sync checkpoint
def mark_sync_complete():
    with open('checkpoints/last_sync.txt', 'w') as f:
        f.write(datetime.utcnow().isoformat())
```

**5. Scheduling**

```yaml
# Example: Nightly incremental sync (cron or GitHub Actions)
schedule:
  - cron: "0 2 * * *"  # 2 AM daily
  run:
    - python scripts/incremental_etl.py
    - python scripts/run_queries.py
```

**Benefits:**
- ✅ **Speed:** Only process changed rows (minutes vs. full reload)
- ✅ **Volume:** Scales to millions of orders without full re-validation
- ✅ **Accuracy:** SCD Type 2 preserves change history
- ✅ **Resilience:** Idempotent upserts allow safe retries on failure
- ✅ **Cost:** Reduced compute; fewer redundant transformations

**Trade-offs:**
- ⚠️ More complex logic (must handle partial failures, state management)
- ⚠️ Requires API timestamp support or transaction logs from ERP
- ⚠️ Checkpoint state must be carefully managed (don't lose sync position)

---

---

## Quick Start

1. **Setup environment:**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. **Run the ETL pipeline:**
```bash
# Create schema
python scripts/create_schema.py

# Load data
python scripts/etl.py orders_raw.json

# Build dimensions and run analytics
python scripts/build_dimensions.py
python scripts/run_queries.py
```

3. **Outputs:**
- `assignment.db` — SQLite database with star-schema tables
- `exports/*.csv` — Query results (4 analytics queries)
- `site/index.html` — Interactive dashboard (served locally or via GitHub Pages)

4. **View Dashboard:**
```bash
python -m http.server 8000 --directory site
# Open http://localhost:8000 in browser
```

---

## Data Quality

See [Data Quality Log](data_quality_log.md) for detailed findings:
- **4 quality issues identified** during ETL
- All issues logged with root cause and resolution strategy
- Issues: category casing, missing geo data, duplicate lines, currency mismatches

---

## Submission Structure

```
assignment_submission/
├── orders_raw.json                # Raw ERP export (provided, unmodified)
├── assignment.db                  # SQLite database (created by ETL)
├── README.md                       # This file + Q-A & Q-B answers
├── data_quality_log.md            # 4+ data quality issues identified
├── DEPLOY.md                       # GitHub Pages deployment guide
├── CHAT_SESSION_FULL.md          # AI usage session transcript
│
├── docs/
│   ├── DATA_MODEL.md             # Full data model specification
│   └── star_schema_diagram.svg   # Visual ER diagram
│
├── scripts/
│   ├── create_schema.py          # Task 1: Create target tables
│   ├── etl.py                    # Task 1: Extract & load
│   ├── build_dimensions.py       # Build dim tables and enrich facts
│   ├── run_queries.py            # Task 3: Execute 4 SQL analytics queries
│   └── generate_dashboards.py    # Generate PNG mockups (optional)
│
├── exports/
│   ├── monthly_revenue_delivered.csv      # Query 1: Monthly revenue
│   ├── top_products.csv                   # Query 2: Top products
│   ├── revenue_by_segment_channel.csv     # Query 3: Segment × Channel
│   └── customer_rank.csv                  # Query 4: Customer ranking
│
├── site/
│   ├── index.html                # Dashboard (Plotly.js + CSV loading)
│   └── exports/                  # CSV files copied here by GitHub Actions
│
├── .github/workflows/
│   └── deploy.yml                # GitHub Actions: build & publish to Pages
│
└── requirements.txt              # Python dependencies
```

---

## AI Usage Declaration

**Tools Used:**
- GitHub Copilot — code drafting and completion
- Claude / ChatGPT — ETL design consultation, SQL query structure
- Gemini — initial project architecture planning

**What AI Produced:**
- Starter ETL skeleton (extraction logic, schema setup)
- SQL query templates (GROUP BY aggregations, window functions)
- README and documentation structure
- Dashboard HTML scaffold with Plotly integration

**Manual Verification:**
All AI-generated code was:
1. **Reviewed** for correctness and business logic
2. **Tested** against sample data (orders_raw.json)
3. **Refined** with manual adjustments for currency conversion, SCD Type 2 logic, data quality handling
4. **Validated** through export CSV inspection and dashboard rendering

**Key Decisions Made by Engineer:**
- Choice of SQLite over cloud database (portability)
- SCD Type 2 implementation pattern (preserves history)
- EUR→USD conversion rate (1:1.08)
- Deduplication strategy for duplicate line items
- GitHub Pages deployment architecture

---

## Notes & Known Limitations

- **Full Load Only:** Current pipeline reloads all data on each run. See Q-B for incremental load strategy.
- **Test Data:** Submission uses 12 sample orders (47 line items) from provided JSON.
- **Scaling:** Schema is designed to scale to millions of rows; tested locally with SQLite 3.
- **Dimensions:** Currently no time-based SCD Type 2 for products (could add if category changes). All dimensions use business keys for now.

---

## Questions?

Refer to:
- **Data Model:** [docs/DATA_MODEL.md](docs/DATA_MODEL.md)
- **Quality Issues:** [data_quality_log.md](data_quality_log.md)
- **Deployment:** [DEPLOY.md](DEPLOY.md)
- **Chat History:** [CHAT_SESSION_FULL.md](CHAT_SESSION_FULL.md)
