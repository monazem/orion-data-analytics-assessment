# Orion Digital Solutions — Data & Analytics Engineer Technical Assessment

**Author:** Mohamed Nazem Hendawy
**Submitted:** [Date]
**Repository:** [GitHub link]

---

## Project Overview

End-to-end data engineering solution that ingests unstructured sales data, applies data quality investigation, transforms it into a relational star schema, and powers an analytical Power BI dashboard for the sales team.

**Stack:** Python 3.10+, pandas, SQLite, Power BI Desktop.

---

## Quick Start

```bash
# Clone and set up
git clone <repo-url>
cd orion-data-analytics-assessment
python -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows PowerShell
pip install -r requirements.txt

# Place source data
cp /path/to/Sales.json     data/raw/
cp /path/to/forecast.json  data/raw/

# Run the pipeline
python -m src.pipeline

# Outputs land in data/output/csv/ and data/output/sales_dwh.db
```

---

## Repository Structure

```
.
├── config/           # Configuration (paths, parameters, color whitelist seed)
├── data/
│   ├── raw/          # Source files (gitignored — see data/raw/README.md)
│   └── output/       # Generated artifacts: CSVs + SQLite DB
├── docs/             # Data model diagram, data quality report, decisions log
├── logs/             # Pipeline run logs (gitignored)
├── powerbi/          # .pbix file + DAX measures documentation
├── src/              # ETL pipeline source
│   ├── extract.py
│   ├── validate.py
│   ├── transform.py
│   ├── load.py
│   ├── pipeline.py
│   └── utils.py
└── tests/            # Unit tests for transformations
```

---

## Documentation

- **[Data Model](docs/data_model.md)** — Star schema design, conformed dimensions, grain decisions
- **[Data Quality Report](docs/data_quality_report.md)** — Findings, evidence, handling
- **[Decisions Log](docs/decisions_log.md)** — Major engineering choices with alternatives and rationale
- **[DAX Measures](powerbi/dax_measures.md)** — All Power BI measures, organized by display folder

---

## Key Findings at a Glance

To be filled in after pipeline execution.

---

## What I Would Do Differently at Production Scale

To be filled in during final write-up.
