"""load.py — Persist transformed frames as CSV files.

Brief permits "CSV files OR a relational database." CSV chosen because:
    - Native Power BI ingestion format (minimal friction)
    - No meaningful advantage from a relational engine at this data volume
    - Modular structure means switching to a relational store is a small
      change in this file if requirements evolve
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils import get_logger

logger = get_logger(__name__)


def write_csvs(tables: dict[str, pd.DataFrame], output_dir: str | Path) -> None:
    """Write each table in the dict to a CSV file in output_dir.

    Files are named after the dictionary key (e.g., 'dim_product' -> 'dim_product.csv').
    The output directory is created if it doesn't exist.

    Args:
        tables: dict mapping table name -> DataFrame (output of transform_all)
        output_dir: directory path where CSVs will be written

    Notes:
        - We use index=False because the row index is not meaningful for Power BI
        - We use encoding='utf-8' explicitly to avoid platform-dependent defaults
        - Existing files are overwritten silently (idempotent: re-running produces
          identical output)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Writing {len(tables)} CSV files to {output_dir}")

    for name, df in tables.items():
        path = output_dir / f"{name}.csv"
        df.to_csv(path, index=False, encoding="utf-8")
        size_kb = path.stat().st_size / 1024
        logger.info(f"  {name:20s} -> {path.name:24s} ({len(df):>8,} rows, {size_kb:>8.1f} KB)")

    logger.info(f"All {len(tables)} CSV files written successfully")


if __name__ == "__main__":
    # Standalone test: runs the full extract -> transform -> load pipeline
    from src.utils import load_config, setup_logging
    from src.extract import extract_all
    from src.transform import transform_all

    setup_logging()
    cfg = load_config()

    sales_df, forecast_df = extract_all(cfg)
    tables = transform_all(sales_df, forecast_df, cfg)
    write_csvs(tables, cfg["output"]["csv_dir"])

    print()
    print("=" * 60)
    print("LOAD COMPLETE")
    print("=" * 60)
    print(f"Output directory: {cfg['output']['csv_dir']}")
    print(f"Files written: {len(tables)}")