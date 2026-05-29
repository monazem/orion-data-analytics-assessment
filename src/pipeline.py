"""pipeline.py — Master orchestrator for the full ETL flow.

Run from project root: `python -m src.pipeline`

Pipeline stages (idempotent — safe to rerun):
    1. Load config + initialize logging
    2. Extract raw frames from JSON sources
    3. Validate raw data; write DQ report to disk
    4. Transform into star schema (with color recovery, no dedup)
    5. Load to CSV files

Each stage can also be run independently via `python -m src.<module>`.
"""
from __future__ import annotations

import sys
import time

from src.utils import load_config, setup_logging, get_logger
from src.extract import extract_all
from src.validate import validate_all
from src.transform import transform_all
from src.load import write_csvs

logger = get_logger(__name__)


def run_pipeline() -> dict:
    """Run the full ETL pipeline end-to-end.

    Returns:
        Summary dict with row counts and timing per stage.
    """
    start = time.time()
    logger.info("=" * 60)
    logger.info("ORION SALES ANALYTICS PIPELINE — START")
    logger.info("=" * 60)

    cfg = load_config()

    # Stage 1: Extract
    t0 = time.time()
    sales_df, forecast_df = extract_all(cfg)
    t_extract = time.time() - t0

    # Stage 2: Validate (report-then-proceed; does not halt pipeline)
    t0 = time.time()
    dq_report = validate_all(sales_df, forecast_df, cfg)
    dq_report.write(cfg["output"]["dq_report"])
    t_validate = time.time() - t0

    # Stage 3: Transform
    t0 = time.time()
    tables = transform_all(sales_df, forecast_df, cfg)
    t_transform = time.time() - t0

    # Stage 4: Load
    t0 = time.time()
    write_csvs(tables, cfg["output"]["csv_dir"])
    t_load = time.time() - t0

    total = time.time() - start

    # Summary
    logger.info("=" * 60)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Extract  : {t_extract:>6.2f}s")
    logger.info(f"  Validate : {t_validate:>6.2f}s  ({len(dq_report.findings)} findings, "
                f"{dq_report.critical_count()} critical, {dq_report.high_count()} high)")
    logger.info(f"  Transform: {t_transform:>6.2f}s  ({len(tables)} tables built)")
    logger.info(f"  Load     : {t_load:>6.2f}s  ({len(tables)} files written)")
    logger.info(f"  TOTAL    : {total:>6.2f}s")
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)

    return {
        "tables": tables,
        "dq_report": dq_report,
        "timings": {
            "extract": t_extract,
            "validate": t_validate,
            "transform": t_transform,
            "load": t_load,
            "total": total,
        },
    }


if __name__ == "__main__":
    setup_logging()
    try:
        run_pipeline()
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        sys.exit(1)