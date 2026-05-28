# Data Quality Report

_Generated: 2026-05-28 19:53:58_

## Summary

| Severity | Count |
|---|---|
| CRITICAL | 1 |
| HIGH | 1 |
| MEDIUM | 0 |
| INFO | 1 |
| PASS | 6 |

## CRITICAL Findings

### Sales fact: row-level duplication

**Message:** 218,008 of 298,246 rows (73.1%) are duplicates on the natural transaction key (ProductKey, CustomerKey, OrderDate, Quantity, Net Price).

**Evidence:**

```
  total_rows: 298,246
  unique_tuples: 80,238
  duplicate_rows: 218,008
  duplicate_percentage: 73.10%
  worst_offenders_top5: ['ProductKey=2490, CustomerKey=19126, Date=6/11/2009, appears 491x', 'ProductKey=2493, CustomerKey=19125, Date=6/5/2009, appears 491x', 'ProductKey=2508, CustomerKey=19000, Date=10/3/2009, appears 427x', 'ProductKey=2497, CustomerKey=19143, Date=12/8/2009, appears 416x', 'ProductKey=2503, CustomerKey=18894, Date=12/8/2008, appears 416x']
```

**Remediation:** Likely cause: a JOIN fanout in the source extraction. Deduplicate on the natural key during transform. In production: surface to source data team and request a transaction-level unique identifier (OrderID or LineItemID) in future extracts.

## HIGH Findings

### Color column corruption (Color == Subcategory)

**Message:** Color column is identical to Subcategory in 100.0% of rows. Color values are subcategory names (e.g., 'Cell phones Accessories'), not actual colors.

**Evidence:**

```
  matching_rows: 298,246
  total_rows: 298,246
  percentage: 100.00%
  sample_color_values: ['Cell phones Accessories', 'Download Games', 'Coffee Machines', 'Home Theater System', 'Boxed Games']
```

**Remediation:** Drop the source Color column. Recover color from the last word of Product Name (e.g., 'Proseware Chandelier M0615 Silver' -> 'Silver'). Apply alphabetic validation to exclude model codes. ~95% of products will have color recovered; the remainder (Download Games, digital products) legitimately have no physical color.

## INFO Findings

### High-null columns (informational)

**Message:** 3 column(s) have >50% null values. For this dataset, Name/Education/Occupation nulls correspond to anonymous/unenriched customer records — legitimate, not corruption.

**Evidence:**

```
  Name: 268,449 nulls (90.0%)
  Education: 268,449 nulls (90.0%)
  Occupation: 268,449 nulls (90.0%)
```

**Remediation:** Accept nulls as legitimate. In dim_customer, do not impose NOT NULL on these. In dashboards, display as 'Unknown' or filter explicitly.

## PASS Findings

### Brand consistency: Sales <-> Forecast

**Message:** All 11 brands appear in both datasets

**Evidence:**

```
  shared_brands: ['A. Datum', 'Adventure Works', 'Contoso', 'Fabrikam', 'Litware', 'Northwind Traders', 'Proseware', 'Southridge Video', 'Tailspin Toys', 'The Phone Company', 'Wide World Importers']
```

### Brand count in Sales

**Message:** Found exactly 11 distinct brands

**Evidence:**

```
  brands: ['A. Datum', 'Adventure Works', 'Contoso', 'Fabrikam', 'Litware', 'Northwind Traders', 'Proseware', 'Southridge Video', 'Tailspin Toys', 'The Phone Company', 'Wide World Importers']
```

### Forecast schema integrity

**Message:** All 4 expected columns present.

**Evidence:**

```
  column_count: 4
```

### Numeric range sanity (Quantity, Net Price)

**Message:** All Quantity and Net Price values are positive

**Evidence:**

```
  qty_range: [1, 4]
  price_range: [0.76, 3199.99]
```

### OrderDate parseability

**Message:** All 298,246 dates parsed successfully

**Evidence:**

```
  date_range_start: 2008-01-01
  date_range_end: 2009-12-31
  format: %m/%d/%Y
```

### Sales schema integrity

**Message:** All 18 expected columns present, no extras.

**Evidence:**

```
  column_count: 18
```
