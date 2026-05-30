# Decisions Log

The choices I made while building this, and why.

## 1. Streaming the JSON

Sales.json is 186 MB. Loading it normally with `json.load` or `pd.read_json` uses ~1.5 GB of RAM. I used `ijson` instead, which reads records one at a time and stays under 10 MB no matter how big the file gets. The forecast file is 4 KB so I loaded it normally.

## 2. Keys

Where the source has stable integer keys (product_key, customer_key), I used them directly. Where it didn't (geography, country, brand), I generated surrogate integer keys.

## 3. No SCD

The data is a one-time snapshot. There's no change-tracking info in the source. If the data team gave us regular updates later, I'd add SCD-2 to dim_customer for exampel since things like education and occupation can legitimately change.

## 4. Conformed dimensions

The brief asks for filtering by country and brand across both Sales and Forecast. For that to work cleanly in Power BI, those dimensions need to filter both fact tables. I made dim_country and dim_brand the parents of their snowflake chains (geography → country, product → brand) and connected them to fact_forecast directly too. One slicer click filters both facts correctly.

## 5. Why state and city filters don't filter the forecast

The forecast only exists at country level. There's no California forecast, no Beijing forecast. If I let the state filter cascade to fact_forecast, the dashboard would either go blank or show a country number labeled as a state number.

Instead: state and city filters apply to sales only. When the user does filter by state, a warning text appears explaining this, and the Forecast Achievement % card goes blank (instead of showing a wrong ratio).

## 6. Why I didn't deduplicate sales

This was the biggest decision and I changed my mind on it.

Initially I deduplicated on (product_key, customer_key, order_date, quantity, unit_price). 298K rows became 80K. 73% reduction.

Then I checked the totals:
- Forecast 2009: $39.0M
- Raw 2009 actuals: $40.6M (104% — matches forecast)
- Deduplicated 2009 actuals: $19.5M (50% — clearly wrong)

A 4% match between raw and forecast is too clean to be coincidence. Whoever set the forecast file calibrated it to the raw, duplicated data. So I kept the raw rows and documented the duplication as an open data quality issue.

If the source had a transaction ID (SalesKey, OrderID), I could tell whether the duplicates are real repeats or artifacts of an extract bug. It doesn't, so I can't be sure. I picked the option that matched the only ground-truth signal I had (the forecast file).

## 7. Recovering the Color column

Every row had Color equal to Subcategory ("Cell phones Accessories", "Audio") — clearly broken. But product names follow a pattern: "Proseware Chandelier M0615 Silver" — the color is the last word.

I extract the last word and validate it's 3-15 letters only (regex), which filters out words like M0615 or E120. Then capitalize first letter so "blue" and "Blue" be the same value.


## 8. PII

Customer name, education, and occupation are personally identifiable or close to it. Even on a fictional dataset, the engineering practice should be the same as production.

The dashboard shows customer code instead of name. The PII columns are loaded into the model but hidden from the report view so nobody accidentally drags them onto a visual.