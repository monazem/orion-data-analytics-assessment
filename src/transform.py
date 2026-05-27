"""transform.py — Convert raw frames into star-schema dimensions and facts.

Builds:
    dim_date       — Daily grain, 2008-01-01 to 2009-12-31
    dim_country    — 3-row mini-dim used as conformed dim for Forecast
    dim_geography  — Country/State/City, with surrogate GeographyKey
    dim_brand      — 11 brands, conformed dim used by Forecast directly
    dim_product    — With recovered Color column (from product name)
    dim_customer   — Stable customer attributes
    fact_sales     — Transaction grain, deduplicated
    fact_forecast  — Country × Brand × Year grain (as-is from source)

All names are snake_case. Schema decisions documented in docs/decisions_log.md.
"""
# Implementation later in the build.
