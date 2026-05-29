"""transform.py — Convert raw frames into star-schema dimensions and facts.

Builds:
    dim_date       — Daily grain, 2008-01-01 to 2009-12-31
    dim_country    — 3-row mini-dim used as conformed dim for Forecast
    dim_geography  — Country/State/City, with surrogate GeographyKey
    dim_brand      — 11 brands, conformed dim used by Forecast directly
    dim_product    — With recovered Color column (from product name)
    dim_customer   — Stable customer attributes
    fact_sales     — Transaction grain, deduplicated
    fact_forecast  — Country x Brand x Year grain (as-is from source)

All column names are snake_case in the output.
Schema decisions documented in docs/decisions_log.md.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from src.utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Snake-case rename map for sales columns
SALES_COLUMN_MAP = {
    "ProductKey":      "product_key",
    "Product Name":    "product_name",
    "Brand":           "brand",
    "Color":           "color_raw",       # renamed, will be dropped (corrupted)
    "Subcategory":     "subcategory",
    "Category":        "category",
    "CustomerKey":     "customer_key",
    "Customer Code":   "customer_code",
    "Name":            "customer_name",
    "Education":       "education",
    "Occupation":      "occupation",
    "Continent":       "continent",
    "City":            "city",
    "State":           "state",
    "CountryRegion":   "country",
    "OrderDate":       "order_date",
    "Quantity":        "quantity",
    "Net Price":       "unit_price",
}

FORECAST_COLUMN_MAP = {
    "CountryRegion":   "country",
    "Brand":           "brand",
    "Forecast":        "forecast_amount",
    "Year":            "year",
}

# Natural transaction key for deduplication
DEDUPE_KEYS = ["product_key", "customer_key", "order_date", "quantity", "unit_price"]


# ---------------------------------------------------------------------------
# Cleaning functions
# ---------------------------------------------------------------------------

def clean_sales(sales_df: pd.DataFrame) -> pd.DataFrame:
    """Produce a cleaned single-table sales DataFrame ready for dim/fact splitting.

    Steps:
        1. Rename columns to snake_case
        2. Parse order_date to datetime
        3. Drop the corrupted color_raw column (recovered separately from product_name)

    NOTE on deduplication: we do NOT deduplicate the sales data despite observing
    73% row-level duplication on the natural transaction key. Rationale:
        - The forecast file (an independent expected-value source) totals $39.0M for 2009
        - Raw 2009 actuals total $40.6M (104% of forecast — strong validation match)
        - Deduplicated 2009 actuals would total $19.5M (50% of forecast — clearly wrong)
        - Without a transaction-level unique identifier, we cannot definitively
          distinguish duplicates-from-corruption from legitimate-fine-grained-records
        - The forecast match is our strongest signal that raw-level data is intended
    See docs/decisions_log.md for full analysis.
    """
    logger.info(f"Cleaning sales: input shape {sales_df.shape}")

    df = sales_df.rename(columns=SALES_COLUMN_MAP)
    df["order_date"] = pd.to_datetime(df["order_date"], format="%m/%d/%Y")
    df = df.drop(columns=["color_raw"])
    df = df.reset_index(drop=True)

    logger.info(f"Cleaned sales: {len(df):,} rows (no deduplication applied — see decisions log)")
    return df


def clean_forecast(forecast_df: pd.DataFrame) -> pd.DataFrame:
    """Rename forecast columns to snake_case. No other cleaning needed."""
    df = forecast_df.rename(columns=FORECAST_COLUMN_MAP)
    logger.info(f"Cleaned forecast: {len(df)} rows")
    return df

# ---------------------------------------------------------------------------
# Color recovery
# ---------------------------------------------------------------------------

# Validation regex: a candidate color must be 3-15 alphabetic characters only.
# This filters out model codes (M410, E120, X200) which all contain digits.
COLOR_CANDIDATE_PATTERN = re.compile(r"^[A-Za-z]{3,15}$")


def recover_color(product_name: str | None) -> str | None:
    """Extract the color from the last word of a product name.

    Convention observed in source data: physical products end their names
    with the color (e.g., 'Proseware Chandelier M0615 Silver' -> 'Silver').
    Digital products (Download Games) do NOT follow this convention; for
    those, this function correctly returns None.

    Validation: the last word must be 3-15 alphabetic characters.
    This filters out model codes like 'M410' or 'E120'.

    Examples:
        'Proseware Chandelier M0615 Silver'   -> 'Silver'
        'Litware 120mm Blue LED Case Fan E901 blue' -> 'Blue'  (case normalized)
        'MGS Flight Simulator 2000 M410'     -> None  (model code, not a color)
        'MGS Halo 2 for Windows Vista M220'  -> None  (digital product)
    """
    if not product_name:
        return None

    last_word = product_name.strip().split()[-1]
    if not COLOR_CANDIDATE_PATTERN.match(last_word):
        return None

    return last_word.capitalize()

# ---------------------------------------------------------------------------
# Dimension builders — DIM_DATE
# ---------------------------------------------------------------------------

def build_dim_date(start_date: str, end_date: str) -> pd.DataFrame:
    """Build a daily date dimension between two ISO dates (inclusive).

    Columns:
        date            - the date itself (PK, also the join key to fact_sales)
        year            - integer year, e.g. 2009
        quarter         - integer 1-4
        quarter_label   - 'Q1', 'Q2', 'Q3', 'Q4'
        month           - integer 1-12
        month_name      - 'January', 'February', ...
        month_short     - 'Jan', 'Feb', ...
        year_month      - 'YYYY-MM' for grouping
        day             - integer day of month (1-31)
        day_of_week     - integer 0-6 (Monday=0)
        day_name        - 'Monday', 'Tuesday', ...
        is_weekend      - boolean
        week_of_year    - ISO week number (1-53)

    The PK is the `date` column; fact_sales.order_date will join to it.
    """
    logger.info(f"Building dim_date from {start_date} to {end_date}")

    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    df = pd.DataFrame({"date": dates})

    df["year"]         = df["date"].dt.year
    df["quarter"]      = df["date"].dt.quarter
    df["quarter_label"] = "Q" + df["quarter"].astype(str)
    df["month"]        = df["date"].dt.month
    df["month_name"]   = df["date"].dt.month_name()
    df["month_short"]  = df["date"].dt.strftime("%b")
    df["year_month"]   = df["date"].dt.strftime("%Y-%m")
    df["day"]          = df["date"].dt.day
    df["day_of_week"]  = df["date"].dt.dayofweek
    df["day_name"]     = df["date"].dt.day_name()
    df["is_weekend"]   = df["day_of_week"].isin([5, 6])
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)

    logger.info(f"Built dim_date: {len(df)} rows ({len(df.columns)} columns)")
    return df

# ---------------------------------------------------------------------------
# Dimension builders — DIM_COUNTRY
# ---------------------------------------------------------------------------

def build_dim_country(sales_clean: pd.DataFrame) -> pd.DataFrame:
    """Build the country mini-dimension. Conformed: used by both Sales and Forecast.

    Columns:
        country_key  (PK, surrogate)
        country      (natural name: China, Germany, United States)
    """
    countries = sorted(sales_clean["country"].unique().tolist())
    df = pd.DataFrame({
        "country_key": range(1, len(countries) + 1),
        "country": countries,
    })
    logger.info(f"Built dim_country: {len(df)} rows -> {df['country'].tolist()}")
    return df


# ---------------------------------------------------------------------------
# Dimension builders — DIM_BRAND
# ---------------------------------------------------------------------------

def build_dim_brand(sales_clean: pd.DataFrame) -> pd.DataFrame:
    """Build the brand dimension. Conformed: used by both Sales (via Product) and Forecast.

    Brand is its own dimension (not just a column in dim_product) precisely so
    that fact_forecast — which lacks a product_key — can still filter by brand
    through a direct relationship.

    Columns:
        brand  (PK, natural — names are unique and stable)
    """
    brands = sorted(sales_clean["brand"].unique().tolist())
    df = pd.DataFrame({"brand": brands})
    logger.info(f"Built dim_brand: {len(df)} rows -> {brands}")
    return df


# ---------------------------------------------------------------------------
# Dimension builders — DIM_GEOGRAPHY
# ---------------------------------------------------------------------------

def build_dim_geography(
    sales_clean: pd.DataFrame,
    dim_country: pd.DataFrame,
) -> pd.DataFrame:
    """Build the geography dimension at City grain, with FK to dim_country.

    Geography has no natural key in the source (denormalized strings on every row).
    We generate a surrogate `geography_key` and link to dim_country.

    Columns:
        geography_key  (PK, surrogate, integer)
        country_key    (FK to dim_country)
        continent
        country
        state
        city
    """
    geo_cols = ["continent", "country", "state", "city"]
    df = (
        sales_clean[geo_cols]
        .drop_duplicates()
        .sort_values(geo_cols)
        .reset_index(drop=True)
    )

    df.insert(0, "geography_key", range(1, len(df) + 1))

    # Add country_key by joining to dim_country
    df = df.merge(dim_country, on="country", how="left")
    # Reorder for readability: keys first, then descriptive columns
    df = df[["geography_key", "country_key", "continent", "country", "state", "city"]]

    logger.info(f"Built dim_geography: {len(df)} rows")
    return df

# ---------------------------------------------------------------------------
# Dimension builders — DIM_PRODUCT
# ---------------------------------------------------------------------------

def build_dim_product(sales_clean: pd.DataFrame) -> pd.DataFrame:
    """Build the product dimension with recovered Color column.

    Uses the natural key (product_key) — verified stable across the dataset
    (every product_key has exactly one set of attributes; no SCD needed).

    The Color column from the source was 100% polluted with Subcategory values
    and has been dropped in clean_sales(). Here we RECOVER color by parsing
    the last word of product_name through recover_color().

    Columns:
        product_key  (PK, natural)
        product_name
        brand        (FK to dim_brand)
        category
        subcategory
        color        (recovered; NULL for Download Games / digital products)
    """
    cols = ["product_key", "product_name", "brand", "category", "subcategory"]
    df = (
        sales_clean[cols]
        .drop_duplicates(subset=["product_key"])
        .sort_values("product_key")
        .reset_index(drop=True)
    )

    df["color"] = df["product_name"].apply(recover_color)

    # Log color recovery summary
    total = len(df)
    recovered = df["color"].notna().sum()
    distinct_colors = sorted(df["color"].dropna().unique().tolist())
    logger.info(
        f"Built dim_product: {total} rows | "
        f"Color recovered for {recovered} ({recovered*100/total:.1f}%) | "
        f"Distinct colors found: {len(distinct_colors)}"
    )
    logger.info(f"Colors: {distinct_colors}")

    return df


# ---------------------------------------------------------------------------
# Dimension builders — DIM_CUSTOMER
# ---------------------------------------------------------------------------

def build_dim_customer(
    sales_clean: pd.DataFrame,
    dim_geography: pd.DataFrame,
) -> pd.DataFrame:
    """Build the customer dimension with FK to dim_geography.

    Uses the natural key (customer_key) — verified stable across the dataset.
    Name/Education/Occupation may be NULL (~90% of customers are anonymous;
    documented in the data quality report as legitimate).

    Columns:
        customer_key   (PK, natural)
        customer_code  (alternate business identifier)
        customer_name  (often NULL — anonymous customers)
        education      (often NULL)
        occupation     (often NULL)
        geography_key  (FK to dim_geography)
    """
    # Start with one row per customer
    customer_cols = [
        "customer_key", "customer_code", "customer_name",
        "education", "occupation",
        "continent", "country", "state", "city",
    ]
    df = (
        sales_clean[customer_cols]
        .drop_duplicates(subset=["customer_key"])
        .sort_values("customer_key")
        .reset_index(drop=True)
    )

    # Resolve geography_key by joining on the 4 geography columns
    geo_join_cols = ["continent", "country", "state", "city"]
    df = df.merge(
        dim_geography[["geography_key", *geo_join_cols]],
        on=geo_join_cols,
        how="left",
    )

    # Drop the denormalized geography text columns now that we have the FK
    df = df.drop(columns=geo_join_cols)

    # Reorder for readability: keys first, then attributes
    df = df[[
        "customer_key", "customer_code", "geography_key",
        "customer_name", "education", "occupation",
    ]]

    # Validate FK integrity
    null_fks = df["geography_key"].isna().sum()
    if null_fks:
        logger.warning(f"dim_customer has {null_fks} rows with no geography match!")
    else:
        logger.info(f"Built dim_customer: {len(df)} rows | All FKs resolved")

    return df

# ---------------------------------------------------------------------------
# Fact builders
# ---------------------------------------------------------------------------

def build_fact_sales(
    sales_clean: pd.DataFrame,
    dim_customer: pd.DataFrame,
) -> pd.DataFrame:
    """Build the sales fact table at transaction-line grain.

    Columns:
        order_date     (FK to dim_date)
        product_key    (FK to dim_product)
        customer_key   (FK to dim_customer)
        geography_key  (FK to dim_geography — derived via customer)
        quantity       (additive measure)
        unit_price     (semi-additive: per-unit, multiply by qty for total)
        sales_amount   (precomputed measure: quantity * unit_price)

    sales_amount is precomputed in the ETL rather than in DAX because:
        1. It is a fully additive measure — computing once in the ETL is correct
        2. It improves dashboard performance (no per-query multiplication)
        3. It encodes the business definition once, not in every DAX measure
    """
    df = sales_clean[[
        "order_date", "product_key", "customer_key",
        "quantity", "unit_price",
    ]].copy()

    # Derive geography_key by joining through customer
    df = df.merge(
        dim_customer[["customer_key", "geography_key"]],
        on="customer_key",
        how="left",
    )

    # Precompute additive sales measure
    df["sales_amount"] = (df["quantity"] * df["unit_price"]).round(2)

    # Reorder for readability: FKs first, then measures
    df = df[[
        "order_date", "product_key", "customer_key", "geography_key",
        "quantity", "unit_price", "sales_amount",
    ]]

    # Validate FK integrity
    null_geo = df["geography_key"].isna().sum()
    if null_geo:
        logger.warning(f"fact_sales has {null_geo} rows with no geography_key resolved!")

    total_revenue = df["sales_amount"].sum()
    logger.info(
        f"Built fact_sales: {len(df):,} rows | "
        f"Total revenue: ${total_revenue:,.0f}"
    )
    return df


def build_fact_forecast(
    forecast_clean: pd.DataFrame,
    dim_country: pd.DataFrame,
) -> pd.DataFrame:
    """Build the forecast fact at Country x Brand x Year grain.

    Columns:
        country_key      (FK to dim_country)
        brand            (FK to dim_brand)
        year             (FK to dim_date.year)
        forecast_amount  (additive measure)

    Note: this fact has a coarser grain than fact_sales. State and City-level
    filters do NOT apply here — by design. The model returns BLANK for those
    via DAX, communicating to the user that forecast data is available at
    Country grain only.
    """
    df = forecast_clean.merge(dim_country, on="country", how="left")
    df = df[["country_key", "brand", "year", "forecast_amount"]]

    null_fk = df["country_key"].isna().sum()
    if null_fk:
        logger.warning(f"fact_forecast has {null_fk} rows with no country_key resolved!")

    total_forecast = df["forecast_amount"].sum()
    logger.info(
        f"Built fact_forecast: {len(df)} rows | "
        f"Total forecast: ${total_forecast:,.0f}"
    )
    return df


# ---------------------------------------------------------------------------
# Master orchestrator
# ---------------------------------------------------------------------------

def transform_all(
    sales_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """Transform raw extracted data into the full star schema.

    Returns a dict keyed by table name, with each value a DataFrame.
    The order in which tables are built matters: dims must exist before
    facts can resolve their FKs.

    Returns:
        {
            'dim_date':       DataFrame,
            'dim_country':    DataFrame,
            'dim_geography':  DataFrame,
            'dim_brand':      DataFrame,
            'dim_product':    DataFrame,
            'dim_customer':   DataFrame,
            'fact_sales':     DataFrame,
            'fact_forecast':  DataFrame,
        }
    """
    logger.info("Starting transform stage...")

    # Stage 1: Clean
    sales_clean = clean_sales(sales_df)
    forecast_clean = clean_forecast(forecast_df)

    # Stage 2: Build lookup/conformed dimensions
    date_cfg = config["date_dimension"]
    dim_date = build_dim_date(date_cfg["start_date"], date_cfg["end_date"])
    dim_country = build_dim_country(sales_clean)
    dim_brand = build_dim_brand(sales_clean)
    dim_geography = build_dim_geography(sales_clean, dim_country)

    # Stage 3: Build the bigger dims (depend on geography)
    dim_product = build_dim_product(sales_clean)
    dim_customer = build_dim_customer(sales_clean, dim_geography)

    # Stage 4: Build facts (depend on customer for geography_key resolution)
    fact_sales = build_fact_sales(sales_clean, dim_customer)
    fact_forecast = build_fact_forecast(forecast_clean, dim_country)

    tables = {
        "dim_date": dim_date,
        "dim_country": dim_country,
        "dim_geography": dim_geography,
        "dim_brand": dim_brand,
        "dim_product": dim_product,
        "dim_customer": dim_customer,
        "fact_sales": fact_sales,
        "fact_forecast": fact_forecast,
    }

    logger.info(f"Transform complete. {len(tables)} tables built.")
    return tables


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from src.utils import load_config, setup_logging
    from src.extract import extract_all

    setup_logging()
    cfg = load_config()
    sales_df, forecast_df = extract_all(cfg)

    tables = transform_all(sales_df, forecast_df, cfg)

    print()
    print("=" * 60)
    print("TRANSFORM SUMMARY")
    print("=" * 60)
    for name, df in tables.items():
        print(f"  {name:20s}: {df.shape[0]:>8,} rows x {df.shape[1]:>2} cols")

    print()
    print("=" * 60)
    print("VALIDATION CHECKS")
    print("=" * 60)
    fs = tables["fact_sales"]
    ff = tables["fact_forecast"]

    print(f"\nfact_sales total revenue: ${fs['sales_amount'].sum():,.0f}")
    print(f"fact_forecast total 2009 forecast: ${ff['forecast_amount'].sum():,.0f}")

    revenue_2009 = fs[fs['order_date'].dt.year == 2009]['sales_amount'].sum()
    print(f"\nfact_sales 2009 revenue: ${revenue_2009:,.0f}")
    print(f"fact_forecast 2009 total: ${ff['forecast_amount'].sum():,.0f}")
    print(f"Ratio (actual / forecast): {revenue_2009/ff['forecast_amount'].sum():.2%}")