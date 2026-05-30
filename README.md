# Orion Sales Analytics Pipeline

Built for the Orion Digital Solutions Data & Analytics Engineer technical assessment.

A Python ETL pipeline that turns 298K raw sales records into a clean star schema, plus a Power BI dashboard on top.

## What it does

1. Reads Sales.json (186 MB) and forecast.json
2. Runs 9 data quality checks and writes a markdown report
3. Builds 6 dimensions + 2 facts, ready for Power BI
4. Saves 8 CSV files

Total runtime: under 10 seconds.

## Three things I found in the data

**The Color column is broken.** Every row has the Subcategory in it instead of an actual color. Fixed by parsing the last word of the product name. Recovered colors for 95% of products.

**73% of sales rows look like duplicates.** I initially deduplicated them — but then I noticed the forecast file matches the *raw* totals at 104%, while deduplicated totals would be 50% of forecast. So I kept the raw rows and documented why. Full reasoning in `docs/decisions_log.md`.

## How to run it

```bash
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Put Sales.json and forecast.json in data/raw/

python -m src.pipeline
```

Each step can also run on its own: `python -m src.extract`, `python -m src.validate`, etc.

## Project layout

src/                  ETL code
config/               YAML config
data/raw/             Source JSON (gitignored)
data/output/csv/      8 CSVs after running
docs/                 Documentation
powerbi/              The .pbix dashboard
logs/                 Per-run logs

## The dashboard

`powerbi/Orion_Sales_Dashboard.pbix` — one page with:
- KPI cards (Total Sales, YoY, Forecast Achievement %, Top Customer)
- Monthly sales trend (2008 vs 2009)
- Sales by country
- Top 10 products
- Forecast vs Actual by brand
- Slicers for year, country, state, brand