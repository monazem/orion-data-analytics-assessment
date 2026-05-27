# Decisions Log

This document records every significant engineering decision made during the assessment, including alternatives considered and the rationale for each choice. The goal is transparency — a reviewer should be able to challenge any decision and find a thoughtful answer here.

---

## Index

1. [ETL Architecture: Modular pipeline vs single script](#1-etl-architecture)
2. [Streaming JSON read vs in-memory load](#2-streaming-json-read)
3. [Natural keys for Product and Customer; surrogate for Geography](#3-key-strategy)
4. [No SCD implementation](#4-no-scd)
5. [No CDC implementation](#5-no-cdc)
6. [Star schema with conformed dimensions: Date, Brand, Country](#6-star-schema-with-conformed-dims)
7. [Country-level conformity for Geography (not State or City)](#7-country-level-conformity)
8. [Deduplication strategy on the fact table](#8-deduplication-strategy)
9. [Color column recovery via product name parsing](#9-color-column-recovery)
10. [Output as both CSV and SQLite](#10-dual-output-formats)
11. [Config-driven pipeline (YAML)](#11-config-driven-pipeline)

---

## 1. ETL Architecture
_To be expanded in the final write-up._

## 2. Streaming JSON Read
_To be expanded._

## 3. Key Strategy
_To be expanded._

## 4. No SCD
_To be expanded._

## 5. No CDC
_To be expanded._

## 6. Star Schema with Conformed Dims
_To be expanded._

## 7. Country-Level Conformity
_To be expanded._

## 8. Deduplication Strategy
_To be expanded._

## 9. Color Column Recovery
_To be expanded._

## 10. Dual Output Formats
_To be expanded._

## 11. Config-Driven Pipeline
_To be expanded._
