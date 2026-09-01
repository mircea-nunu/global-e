# Assignment — End-to-end Plan & Repo

This repository contains a modular, checkpointed plan to complete the assessment within 2–3 hours.

Decisions taken for implementation
- Database: SQLite 3 (`assignment.db`) — chosen for portability and local Power BI connectivity.
- Dashboard: Power BI (export CSVs from SQLite; load into Power BI desktop for visuals).
- Currency conversion: `1 EUR = 1.08 USD`. Shipping costs in EUR will be converted to USD.
- SCD strategy: recommended **SCD Type 2** for `dim_customer` (preserves history).

Quick start

1. Create a Python virtualenv and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Place your provided `orders_raw.json` in this folder (root-level) and run:

```bash
python scripts/create_schema.py
python scripts/etl.py orders_raw.json
```

3. Outputs:
- `assignment.db` — SQLite database with star-schema tables
- `exports/` — CSV exports of query results suitable for Power BI

AI usage declaration

- Tools used: Gemini/ChatGPT/Copilot (as drafting and code assistance). Specific prompts and exports are recorded in `ai_prompts/` (if any).
- What AI produced: starter ETL and schema drafts, SQL query templates, README drafts.
- Manual verification: all code and logic were reviewed and adjusted by the engineer (you). Any AI-suggested code must be reviewed before use.

SCD meaning (short)

SCD = Slowly Changing Dimension. Use SCD Type 2 to preserve historical values by adding new rows with `effective_date` / `expiration_date` and `is_current`.

Notes
- This scaffold provides minimal, runnable starter scripts. The ETL is conservative and logs data quality issues into `data_quality_log.md`.
