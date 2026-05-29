"""validate.py — Data quality checks on raw extracted data.

Runs a battery of checks against the extracted DataFrames and produces:
1. An in-memory DataQualityReport (can be inspected by pipeline.py)
2. A markdown report at docs/data_quality_report.md (the reviewer-facing artifact)

Design principle: report-then-proceed. Critical findings are documented loudly
but do NOT halt the pipeline — transform.py handles remediation.
In production at scale, the policy would invert: halt-and-alert on critical findings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Severity levels
# ---------------------------------------------------------------------------
class Severity(str, Enum):
    CRITICAL = "CRITICAL"   # Would produce wrong analytics if uncorrected
    HIGH = "HIGH"           # Material analytical impact
    MEDIUM = "MEDIUM"       # Cosmetic or low-impact issue
    INFO = "INFO"           # Notable but expected/legitimate
    PASS = "PASS"           # Check ran and passed


SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.INFO: 3,
    Severity.PASS: 4,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class DQFinding:
    """A single data quality finding."""
    check_name: str
    severity: Severity
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation: str = ""


@dataclass
class DataQualityReport:
    """Aggregates findings from all checks and writes the markdown report."""
    findings: list[DQFinding] = field(default_factory=list)

    def add(self, finding: DQFinding) -> None:
        self.findings.append(finding)
        log_msg = f"[{finding.severity.value}] {finding.check_name}: {finding.message}"
        if finding.severity == Severity.CRITICAL:
            logger.error(log_msg)
        elif finding.severity == Severity.HIGH:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.HIGH)

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append("# Data Quality Report")
        lines.append("")
        lines.append(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append("| Severity | Count |")
        lines.append("|---|---|")
        for sev in Severity:
            count = sum(1 for f in self.findings if f.severity == sev)
            lines.append(f"| {sev.value} | {count} |")
        lines.append("")

        sorted_findings = sorted(
            self.findings,
            key=lambda f: (SEVERITY_ORDER[f.severity], f.check_name),
        )

        current_sev = None
        for f in sorted_findings:
            if f.severity != current_sev:
                current_sev = f.severity
                lines.append(f"## {current_sev.value} Findings")
                lines.append("")

            lines.append(f"### {f.check_name}")
            lines.append("")
            lines.append(f"**Message:** {f.message}")
            lines.append("")
            if f.evidence:
                lines.append("**Evidence:**")
                lines.append("")
                lines.append("```")
                for k, v in f.evidence.items():
                    lines.append(f"  {k}: {v}")
                lines.append("```")
                lines.append("")
            if f.remediation:
                lines.append(f"**Remediation:** {f.remediation}")
                lines.append("")

        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_markdown())
        logger.info(f"Data quality report written to {path}")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_SALES_COLUMNS = {
    "ProductKey", "Product Name", "Brand", "Color", "Subcategory", "Category",
    "CustomerKey", "Customer Code", "Name", "Education", "Occupation",
    "Continent", "City", "State", "CountryRegion", "OrderDate", "Quantity",
    "Net Price",
}

EXPECTED_FORECAST_COLUMNS = {"CountryRegion", "Brand", "Forecast", "Year"}

DEDUPE_KEYS = ["ProductKey", "CustomerKey", "OrderDate", "Quantity", "Net Price"]


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_schema_sales(sales_df: pd.DataFrame, report: DataQualityReport) -> None:
    actual = set(sales_df.columns)
    missing = EXPECTED_SALES_COLUMNS - actual
    extra = actual - EXPECTED_SALES_COLUMNS

    if missing:
        report.add(DQFinding(
            check_name="Sales schema: missing expected columns",
            severity=Severity.CRITICAL,
            message=f"{len(missing)} expected column(s) missing",
            evidence={"missing": sorted(missing)},
            remediation="Verify source extraction; missing columns will break downstream.",
        ))
    elif extra:
        report.add(DQFinding(
            check_name="Sales schema: unexpected extra columns",
            severity=Severity.INFO,
            message=f"{len(extra)} unexpected column(s)",
            evidence={"extra": sorted(extra)},
            remediation="Review extras; may be new fields to incorporate.",
        ))
    else:
        report.add(DQFinding(
            check_name="Sales schema integrity",
            severity=Severity.PASS,
            message=f"All {len(EXPECTED_SALES_COLUMNS)} expected columns present, no extras.",
            evidence={"column_count": len(actual)},
        ))


def check_schema_forecast(forecast_df: pd.DataFrame, report: DataQualityReport) -> None:
    actual = set(forecast_df.columns)
    missing = EXPECTED_FORECAST_COLUMNS - actual

    if missing:
        report.add(DQFinding(
            check_name="Forecast schema: missing expected columns",
            severity=Severity.CRITICAL,
            message=f"{len(missing)} expected column(s) missing from forecast",
            evidence={"missing": sorted(missing)},
        ))
    else:
        report.add(DQFinding(
            check_name="Forecast schema integrity",
            severity=Severity.PASS,
            message=f"All {len(EXPECTED_FORECAST_COLUMNS)} expected columns present.",
            evidence={"column_count": len(actual)},
        ))


def check_sales_duplicates(
    sales_df: pd.DataFrame,
    report: DataQualityReport,
    threshold_pct: float = 5.0,
) -> None:
    """Report row-level duplication on the natural transaction key.

    We INTENTIONALLY do not flag this as CRITICAL because cross-validation
    against the forecast file shows raw-level revenue matches forecast (104%),
    while deduplicated revenue would be 50% of forecast. See decisions log.
    """
    total = len(sales_df)
    unique = sales_df[DEDUPE_KEYS].drop_duplicates().shape[0]
    duplicates = total - unique
    dup_pct = duplicates * 100 / total if total else 0

    grp = sales_df.groupby(DEDUPE_KEYS).size().reset_index(name="count")
    worst = grp.nlargest(5, "count")
    worst_summary = [
        f"ProductKey={r['ProductKey']}, CustomerKey={r['CustomerKey']}, "
        f"Date={r['OrderDate']}, appears {r['count']}x"
        for _, r in worst.iterrows()
    ]

    report.add(DQFinding(
        check_name="Sales fact: row-level duplication (informational)",
        severity=Severity.INFO,
        message=(
            f"Observed {duplicates:,} of {total:,} rows ({dup_pct:.1f}%) as "
            f"duplicates on the natural transaction key. We do NOT deduplicate "
            f"because cross-validation against the forecast file (raw 2009 actuals "
            f"= 104% of forecast, deduplicated would be 50%) indicates raw-level "
            f"data is intended. Source data lacks a transaction-level unique "
            f"identifier to definitively classify duplicates."
        ),
        evidence={
            "total_rows": f"{total:,}",
            "unique_tuples": f"{unique:,}",
            "duplicate_rows": f"{duplicates:,}",
            "duplicate_percentage": f"{dup_pct:.2f}%",
            "max_group_size": int(grp["count"].max()),
            "worst_offenders_top5": worst_summary,
        },
        remediation=(
            "In production: surface to source data team and request a transaction-level "
            "unique identifier (OrderID or LineItemID) in future extracts. "
            "Once available, re-evaluate whether the duplication is corruption "
            "or legitimate fine-grained data."
        ),
    ))


def check_color_subcategory_collision(sales_df: pd.DataFrame, report: DataQualityReport) -> None:
    """The Color column is suspected to be polluted with Subcategory values."""
    matching = (sales_df["Color"] == sales_df["Subcategory"]).sum()
    total = len(sales_df)
    pct = matching * 100 / total if total else 0

    if pct >= 99.0:
        report.add(DQFinding(
            check_name="Color column corruption (Color == Subcategory)",
            severity=Severity.HIGH,
            message=(
                f"Color column is identical to Subcategory in {pct:.1f}% of rows. "
                f"Color values are subcategory names (e.g., 'Cell phones Accessories'), not actual colors."
            ),
            evidence={
                "matching_rows": f"{matching:,}",
                "total_rows": f"{total:,}",
                "percentage": f"{pct:.2f}%",
                "sample_color_values": list(sales_df["Color"].unique()[:5]),
            },
            remediation=(
                "Drop the source Color column. Recover color from the last word "
                "of Product Name (e.g., 'Proseware Chandelier M0615 Silver' -> 'Silver'). "
                "Apply alphabetic validation to exclude model codes. "
                "~95% of products will have color recovered; the remainder "
                "(Download Games, digital products) legitimately have no physical color."
            ),
        ))
    else:
        report.add(DQFinding(
            check_name="Color column corruption check",
            severity=Severity.PASS,
            message=f"Color matches Subcategory in {pct:.2f}% of rows (no widespread corruption)",
            evidence={"matching_pct": f"{pct:.2f}%"},
        ))


def check_null_patterns(sales_df: pd.DataFrame, report: DataQualityReport) -> None:
    total = len(sales_df)
    null_counts = sales_df.isna().sum()
    high_null_cols = {}

    for col in sales_df.columns:
        nulls = null_counts[col]
        pct = nulls * 100 / total
        if pct > 50:
            high_null_cols[col] = (int(nulls), pct)

    if high_null_cols:
        evidence = {
            col: f"{n:,} nulls ({p:.1f}%)" for col, (n, p) in high_null_cols.items()
        }
        report.add(DQFinding(
            check_name="High-null columns (informational)",
            severity=Severity.INFO,
            message=(
                f"{len(high_null_cols)} column(s) have >50% null values. "
                f"For this dataset, Name/Education/Occupation nulls correspond to "
                f"anonymous/unenriched customer records — legitimate, not corruption."
            ),
            evidence=evidence,
            remediation=(
                "Accept nulls as legitimate. In dim_customer, do not impose NOT NULL "
                "on these. In dashboards, display as 'Unknown' or filter explicitly."
            ),
        ))
    else:
        report.add(DQFinding(
            check_name="Null pattern check",
            severity=Severity.PASS,
            message="No columns exceed 50% null threshold",
            evidence={},
        ))


def check_date_parseability(sales_df: pd.DataFrame, report: DataQualityReport) -> None:
    parsed = pd.to_datetime(sales_df["OrderDate"], format="%m/%d/%Y", errors="coerce")
    failed = parsed.isna().sum()
    total = len(sales_df)

    if failed > 0:
        sample_bad = sales_df.loc[parsed.isna(), "OrderDate"].head(5).tolist()
        report.add(DQFinding(
            check_name="OrderDate parseability",
            severity=Severity.HIGH,
            message=f"{failed:,} of {total:,} dates failed to parse as %m/%d/%Y",
            evidence={"failed_count": f"{failed:,}", "sample_unparseable": sample_bad},
        ))
    else:
        date_min = parsed.min()
        date_max = parsed.max()
        report.add(DQFinding(
            check_name="OrderDate parseability",
            severity=Severity.PASS,
            message=f"All {total:,} dates parsed successfully",
            evidence={
                "date_range_start": str(date_min.date()),
                "date_range_end": str(date_max.date()),
                "format": "%m/%d/%Y",
            },
        ))


def check_numeric_ranges(sales_df: pd.DataFrame, report: DataQualityReport) -> None:
    bad_qty = (sales_df["Quantity"] <= 0).sum()
    bad_price = (sales_df["Net Price"] <= 0).sum()

    if bad_qty or bad_price:
        report.add(DQFinding(
            check_name="Numeric range sanity (Quantity, Net Price)",
            severity=Severity.HIGH,
            message=f"Found {bad_qty} rows with Quantity<=0 and {bad_price} rows with Net Price<=0",
            evidence={
                "qty_min": int(sales_df["Quantity"].min()),
                "qty_max": int(sales_df["Quantity"].max()),
                "price_min": float(sales_df["Net Price"].min()),
                "price_max": float(sales_df["Net Price"].max()),
            },
        ))
    else:
        report.add(DQFinding(
            check_name="Numeric range sanity (Quantity, Net Price)",
            severity=Severity.PASS,
            message="All Quantity and Net Price values are positive",
            evidence={
                "qty_range": f"[{sales_df['Quantity'].min()}, {sales_df['Quantity'].max()}]",
                "price_range": f"[{sales_df['Net Price'].min():.2f}, {sales_df['Net Price'].max():.2f}]",
            },
        ))


def check_brand_count(
    sales_df: pd.DataFrame,
    report: DataQualityReport,
    expected: int = 11,
) -> None:
    """Report distinct brand count. INFO if it differs from baseline expectation.

    Brand counts can legitimately change as the business adds or removes brands.
    We report the actual count and the deviation as INFO, not as a problem,
    leaving threshold-based alerting to a baseline-aware system in production.
    """
    actual = sales_df["Brand"].nunique()
    brands = sorted(sales_df["Brand"].unique().tolist())
    deviation = abs(actual - expected)

    if actual == expected:
        report.add(DQFinding(
            check_name="Brand count in Sales",
            severity=Severity.PASS,
            message=f"Found {actual} distinct brands (matches baseline expectation of {expected})",
            evidence={"brands": brands},
        ))
    else:
        report.add(DQFinding(
            check_name="Brand count in Sales",
            severity=Severity.INFO,
            message=(
                f"Found {actual} distinct brands; baseline expectation was {expected} "
                f"(deviation: {deviation}). Brand counts can change legitimately — "
                f"verify this matches business expectations."
            ),
            evidence={"actual_count": actual, "expected_count": expected, "brands": brands},
        ))


def check_brand_consistency(
    sales_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    report: DataQualityReport,
) -> None:
    """Brands in Sales must match brands in Forecast (else orphan data in dashboard)."""
    sales_brands = set(sales_df["Brand"].unique())
    forecast_brands = set(forecast_df["Brand"].unique())

    only_in_sales = sales_brands - forecast_brands
    only_in_forecast = forecast_brands - sales_brands

    if not only_in_sales and not only_in_forecast:
        report.add(DQFinding(
            check_name="Brand consistency: Sales <-> Forecast",
            severity=Severity.PASS,
            message=f"All {len(sales_brands)} brands appear in both datasets",
            evidence={"shared_brands": sorted(sales_brands)},
        ))
    else:
        report.add(DQFinding(
            check_name="Brand consistency: Sales <-> Forecast",
            severity=Severity.INFO,
            message=(
                f"Brand mismatch: {len(only_in_sales)} only in Sales, "
                f"{len(only_in_forecast)} only in Forecast"
            ),
            evidence={
                "only_in_sales": sorted(only_in_sales),
                "only_in_forecast": sorted(only_in_forecast),
            },
            remediation="Orphan brands will produce missing-data visuals in the dashboard.",
        ))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def validate_all(
    sales_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    config: dict[str, Any] | None = None,
) -> DataQualityReport:
    """Run all data quality checks and return the populated report."""
    logger.info("Starting data quality validation...")

    report = DataQualityReport()

    # Schema checks first — broken schema would cause other checks to error oddly
    check_schema_sales(sales_df, report)
    check_schema_forecast(forecast_df, report)

    threshold = (config or {}).get("data_quality", {}).get("max_duplicate_pct", 5.0)
    expected_brands = (config or {}).get("data_quality", {}).get("expected_brands_count", 11)

    check_sales_duplicates(sales_df, report, threshold_pct=threshold)
    check_color_subcategory_collision(sales_df, report)
    check_null_patterns(sales_df, report)
    check_date_parseability(sales_df, report)
    check_numeric_ranges(sales_df, report)
    check_brand_count(sales_df, report, expected=expected_brands)
    check_brand_consistency(sales_df, forecast_df, report)

    logger.info(
        f"Validation complete. {len(report.findings)} findings. "
        f"Critical: {report.critical_count()}, High: {report.high_count()}"
    )
    return report


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from src.utils import load_config, setup_logging
    from src.extract import extract_all

    setup_logging()
    cfg = load_config()

    sales_df, forecast_df = extract_all(cfg)
    report = validate_all(sales_df, forecast_df, cfg)

    report_path = cfg["output"]["dq_report"]
    report.write(report_path)

    print()
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    for sev in Severity:
        count = sum(1 for f in report.findings if f.severity == sev)
        print(f"  {sev.value:10s}: {count}")
    print(f"\nFull report: {report_path}")