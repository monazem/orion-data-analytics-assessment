"""Orion sales analytics ETL pipeline.

Modules:
    extract   — Stream large JSON sources into in-memory frames
    validate  — Data quality checks; generates the DQ report
    transform — Build star-schema dimensions and facts
    load      — Write outputs to CSV files
    pipeline  — Orchestrator: ties extract → validate → transform → load together
    utils     — Logging, config loading, shared helpers
"""
__version__ = "1.0.0"
