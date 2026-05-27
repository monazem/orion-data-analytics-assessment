"""validate.py — Data quality checks on raw extracted data.

Produces:
    1. A DataQualityReport object (in-memory findings)
    2. A markdown report file at docs/data_quality_report.md

Checks include:
    - Row-level duplication on the fact table (the 73% finding)
    - Color column corruption (Color == Subcategory in 100% of rows)
    - Null pattern analysis (Name/Education/Occupation legitimate nulls)
    - Schema integrity (expected columns present, types reasonable)
    - Brand count sanity (we expect 11)
"""
# Implementation later in the build.
