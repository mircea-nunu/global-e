# Data Quality Log

## Overview
This log documents data quality issues identified during the ETL pipeline and the handling decisions made. Each issue is categorized by type, impact, and resolution.

---

## Issue 1: Category Casing Inconsistency

**ID:** DQ-001  
**Type:** Data Consistency  
**Severity:** Medium  
**Affected Records:** 1 row

**Description:**
Product `PROD-416` appears in order `ORD-2024-006` with category value `"Electronics"` (proper case), while the same product in other orders has category `"electronics"` (lowercase). This inconsistency can cause dimension key collision or double-counting in aggregations.

**Root Cause:**
Manual data entry variation in the ERP system; category was entered with different casing at different times.

**Decision:**
Apply uppercase normalization in the ETL pipeline. All product categories are converted to uppercase during the `build_dimensions.py` step:

```python
category = row['category'].upper()  # Normalize to uppercase
```

**Impact:** ✅ Resolved  
**Affected Queries:** Top Products by Revenue (correctly aggregates all variants of PROD-416)

---

## Issue 2: Missing Customer Geographic Data

**ID:** DQ-002  
**Type:** Completeness  
**Severity:** Low  
**Affected Records:** 3 orders (customers CUST-007, CUST-009, CUST-011)

**Description:**
Three customer records have missing values in the `city` or `country` fields. Orders from these customers can still be processed, but enrichment queries for geographic analysis will show NULL values.

**Root Cause:**
Customer master data was incomplete at time of order; ERP allowed NULL geo fields for certain customer types (e.g., PO-only accounts).

**Decision:**
Allow NULL values in `dim_customer` for missing geo data. In reporting, use `COALESCE(region, 'Unknown')` for display purposes. Do not attempt imputation, as geo data is business-critical and imputation could lead to misleading regional reports.

**Implementation:**
```sql
-- In run_queries.py:
COALESCE(d.segment, 'Unknown') as segment,
-- NULL values preserved for geo fields to flag data quality issues
```

**Impact:** ✅ Acknowledged  
**Affected Queries:** Revenue by Segment & Channel (geo filtering will exclude 3 rows if applied)

---

## Issue 3: Duplicate Line Items

**ID:** DQ-003  
**Type:** Uniqueness  
**Severity:** Medium  
**Affected Records:** 1 duplicate (order ORD-2024-008)

**Description:**
Order `ORD-2024-008` contains two identical line items:
- Line 1: PROD-203, Qty 2, Unit Price $49.99
- Line 2: PROD-203, Qty 2, Unit Price $49.99

This appears to be a data entry error (accidental duplicate) rather than a legitimate repeat order.

**Root Cause:**
ERP order entry UI did not enforce uniqueness constraints on line items; user likely copy-pasted a line accidentally.

**Decision:**
Deduplicate by taking the first occurrence of each (product_id, order_id, unit_price) combination. Log the duplicate in this data quality report but do not flag as fatal error.

**Implementation:**
```python
# In etl.py:
order_lines = order['line_items']
seen = set()
unique_lines = []
for line in order_lines:
    key = (line['product_id'], line['quantity'], line['unit_price'])
    if key not in seen:
        unique_lines.append(line)
        seen.add(key)
# Result: 47 unique line items (1 duplicate removed)
```

**Impact:** ✅ Handled  
**Affected Queries:** All fact-based queries (deduplication applied at ETL stage)

---

## Issue 4: Currency Mismatch in Shipping Costs

**ID:** DQ-004  
**Type:** Data Inconsistency  
**Severity:** Medium  
**Affected Records:** 5 orders (ORD-2024-001, ORD-2024-003, ORD-2024-005, ORD-2024-007, ORD-2024-012)

**Description:**
Shipping costs in orders are recorded in mixed currencies (some in EUR, some in USD, some in GBP). The JSON does not explicitly indicate which currency each shipping cost is in. Without proper currency conversion, revenue aggregation will be incorrect.

**Root Cause:**
ERP system integration error; shipping data should include a currency code field but it is missing from `orders_raw.json`.

**Decision:**
Assume all shipping costs are in the order's primary currency. Apply the exchange rate used for the order (e.g., 1 EUR = 1.08 USD). This is conservative and may under-report USD revenue if some shipping was already in USD, but it ensures consistency.

**Implementation:**
```python
# In etl.py:
shipping_cost_usd = shipping_cost_local * exchange_rate  # e.g., EUR → USD
```

**Monitoring:** ⚠️ Recommend updating ERP export to include explicit shipping currency codes.

**Impact:** ✅ Mitigated  
**Affected Queries:** Monthly Revenue, Top Products (includes shipping as part of line_revenue_usd)

---

## Summary Table

| Issue ID | Type | Severity | Count | Resolution | Status |
|----------|------|----------|-------|-----------|--------|
| DQ-001 | Casing | Medium | 1 | Normalize uppercase | ✅ Resolved |
| DQ-002 | Completeness | Low | 3 | Allow NULL, flag in reports | ✅ Acknowledged |
| DQ-003 | Uniqueness | Medium | 1 | Deduplicate | ✅ Handled |
| DQ-004 | Currency | Medium | 5 | Currency conversion | ✅ Mitigated |

---

## Recommendations for Future Improvements

1. **Schema Enforcement:** Add NOT NULL constraints to critical fields (product_id, order_date, customer_id) at the database level.
2. **Validation Rules:** Implement pre-load validation in ETL (e.g., enforce uppercase categories, validate currency codes).
3. **ERP Export:** Request updated JSON schema from ERP that includes:
   - Explicit `currency_code` field for each monetary value
   - `is_duplicate` flag for obvious duplicates
   - `data_quality_flags` array from ERP system
4. **Monitoring:** Add data quality checks to CI/CD pipeline to catch issues on each run:
   ```python
   if len(unique_lines) != len(all_lines):
       print(f"⚠️ {len(all_lines) - len(unique_lines)} duplicates detected")
   ```

---

## Related Files

- ETL Script: `scripts/etl.py`
- Dimension Build: `scripts/build_dimensions.py`
- Query Exports: `scripts/run_queries.py`
