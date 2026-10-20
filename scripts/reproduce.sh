#!/usr/bin/env bash
# Rebuild everything from the read-only source, in order (~1.5 hours, mostly reading raw CSVs
# and the development backtest). Needs the UKYECON drive mounted. Writes only to data_local/
# and reports/. The holdout is not rerun: it runs once, and backtest.py refuses a second run.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python

$PY src/fingerprint.py                      # baseline of the source files
$PY src/run_sql.py sql/01_extract.sql       # 6-market extract from ia.db (read-only)
$PY src/rebuild_from_raw.py                 # price, host, collection-date fields from raw CSVs
$PY src/run_sql.py sql/02_clean.sql         # corrected copy
$PY src/validate.py
$PY src/validate.py listings_6city_clean.parquet
$PY src/quality.py                          # candidate-replacement detector
$PY src/label.py
$PY src/features.py
$PY -m pytest tests -q
$PY src/backtest.py                         # development folds, both quality variants
$PY src/business.py
$PY scripts/make_figures.py
$PY src/freeze.py --check                   # confirms the analysis still matches the freeze
$PY src/fingerprint.py --check              # confirms the source is unchanged
