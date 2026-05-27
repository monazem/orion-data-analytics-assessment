"""extract.py — Stream-read source JSON files into pandas DataFrames.

We use streaming JSON parsing (ijson) for Sales.json because it's 186 MB.
Loading it eagerly via json.load() would briefly consume ~1.5 GB of RAM
(JSON-to-Python overhead is roughly 8x file size). Streaming reads in
constant memory regardless of file size, which is the correct production
pattern even when local memory is sufficient.

forecast.json is small (~4 KB) — standard json.load is fine there.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import ijson
import pandas as pd

from src.utils import get_logger

logger = get_logger(__name__)


def extract_sales(
    path: str | Path,
    batch_size: int = 50_000,
) -> pd.DataFrame:
    """Stream-parse the sales JSON file and return it as a DataFrame.

    Records are read one at a time via ijson, accumulated in batches,
    and each batch is converted into a small DataFrame. The batches are
    then concatenated into one final DataFrame.

    Args:
        path: location of the sales JSON file.
        batch_size: how many records to accumulate before converting to a
                    DataFrame chunk. Larger = fewer concat operations but
                    higher peak memory. 50,000 is a balanced default.

    Returns:
        A pandas DataFrame containing all sales records.

    Raises:
        FileNotFoundError: if the path doesn't exist.
        ValueError: if the file contains zero records.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Sales file not found: {path.resolve()}")

    size_mb = path.stat().st_size / 1024 / 1024
    logger.info(f"Streaming sales records from {path} ({size_mb:.1f} MB)")

    batch: list[dict[str, Any]] = []
    chunks: list[pd.DataFrame] = []
    total_records = 0

    with open(path, "rb") as f:
        for record in ijson.items(f, "item"):
            batch.append(record)
            if len(batch) >= batch_size:
                chunks.append(pd.DataFrame(batch))
                total_records += len(batch)
                batch = []
                logger.info(f"  ...processed {total_records:,} records")

        # Flush any remaining records in the final partial batch
        if batch:
            chunks.append(pd.DataFrame(batch))
            total_records += len(batch)

    if not chunks:
        raise ValueError(f"No records found in {path}")

    df = pd.concat(chunks, ignore_index=True)
    logger.info(f"Extracted {len(df):,} sales records with {len(df.columns)} columns")
    return df


def extract_forecast(path: str | Path) -> pd.DataFrame:
    """Read the forecast JSON file. Small file — eager load is fine.

    Args:
        path: location of the forecast JSON file.

    Returns:
        A pandas DataFrame of forecast records.

    Raises:
        FileNotFoundError: if the path doesn't exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Forecast file not found: {path.resolve()}")

    logger.info(f"Loading forecast from {path}")
    with open(path, "r") as f:
        data = json.load(f)

    df = pd.DataFrame(data)
    logger.info(f"Extracted {len(df):,} forecast records with {len(df.columns)} columns")
    return df


def extract_all(config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extract both source datasets using paths from the config.

    Args:
        config: parsed pipeline.yaml dictionary.

    Returns:
        A tuple of (sales_df, forecast_df).
    """
    sales_df = extract_sales(config["input"]["sales_json"])
    forecast_df = extract_forecast(config["input"]["forecast_json"])
    return sales_df, forecast_df


if __name__ == "__main__":
    # Standalone test: run from project root with `python -m src.extract`
    # This block runs ONLY when this file is executed directly,
    # NOT when it's imported by other modules.
    from src.utils import load_config, setup_logging

    setup_logging()
    cfg = load_config()
    sales_df, forecast_df = extract_all(cfg)

    print()
    print("=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"\nSales:    {len(sales_df):,} rows x {len(sales_df.columns)} columns")
    print(f"Forecast: {len(forecast_df):,} rows x {len(forecast_df.columns)} columns")
    print(f"\nSales columns: {list(sales_df.columns)}")
    print(f"\nForecast columns: {list(forecast_df.columns)}")
    print(f"\nSales head:")
    print(sales_df.head(3))
    print(f"\nForecast head:")
    print(forecast_df.head(3))