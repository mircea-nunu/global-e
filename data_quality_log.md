# Data Quality Log

This file records the main data quality issues identified across the ETL, dimension build, and validation steps.

## 1) Category casing drift for product variants

- Issue: Product category values were not consistently normalized.
- Example: `PROD-416` appeared as `Electronics` in one order and `electronics` in another.
- Impact: Can create duplicate or inconsistent category values in the product dimension and downstream rollups.
- Handling: The ETL logs the issue and the dimension build normalizes categories with `str.strip().str.title()` before finalizing `dim_product`.
- Status: Logged and mitigated.

## 2) Same product_id associated with multiple category labels

- Issue: The same product identifier was found under more than one category label.
- Examples:
  - `PROD-207` -> `['Sports', 'Sports & Fitness']`
  - `PROD-214` -> `['Sports', 'Sports & Fitness']`
- Impact: Duplicate product rows can appear in the dimension if not resolved before writing `dim_product`.
- Handling: The dimension builder detects products with multiple category values and logs a warning before selecting a canonical category.
- Status: Identified and guarded against in the dimension build logic.

## 3) Missing or incomplete product price data

- Issue: Some line items had a missing `unit_price` or incomplete pricing metadata.
- Impact: Revenue calculations would be inaccurate or fail if price is null.
- Handling: The ETL logs a warning when `unit_price` is missing for a product and preserves the row for review.
- Status: Identified and flagged.

## 4) Duplicate line items in the same order

- Issue: Some order lines were repeated in the source data.
- Example: A line item appeared twice for the same product/order combination due to accidental duplication.
- Impact: Revenue, quantities, and product totals would be overstated if duplicates remain.
- Handling: Duplicate rows can be deduplicated before fact insert by checking `(order_id, product_id, unit_price)` combinations.
- Status: Documented and recommended for a deduplication rule in the ETL.

## 5) Currency and shipping cost inconsistency

- Issue: Currency values were not always explicit or consistently normalized across order rows.
- Impact: Revenue and shipping cost totals can be misinterpreted if not converted consistently to USD.
- Handling: The ETL normalizes currency to uppercase and applies the fixed EUR-to-USD rate of `1.08` where required, while storing the conversion metadata.
- Status: Identified and converted to a consistent USD model.

## 6) Discount handling needs explicit validation

- Issue: Discount percentages are not always consistently present or standardized across raw order lines.
- Impact: Without explicit handling, line revenue may be overstated or understated.
- Handling: The ETL includes `discount_pct` in the fact model and calculates `line_revenue_local = quantity * unit_price * (1 - discount_pct / 100)` before conversion to USD.
- Status: Included in the fact design and validation flow.

## Summary

The main issues identified are:
- inconsistent category casing
- multiple categories for the same product id
- missing prices
- duplicate lines
- currency normalization issues
- discount handling inconsistency

These issues are now tracked in the ETL and dimension-building steps to prevent silent data-quality drift in the warehouse layer.
