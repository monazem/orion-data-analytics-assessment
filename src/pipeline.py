"""pipeline.py — Orchestrator for the full ETL flow.

Run as: `python -m src.pipeline`

Pipeline stages (idempotent — safe to rerun):
    1. Load config + initialize logging
    2. Extract raw frames from JSON sources
    3. Validate raw data; emit DQ report
    4. Transform into star schema (with dedup + color recovery)
    5. Validate transformed outputs (row count sanity, FK integrity)
    6. Load to CSV + SQLite
    7. Summary report
"""
# Implementation later in the build.
