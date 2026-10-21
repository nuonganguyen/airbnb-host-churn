# Supply at Risk: Predicting Airbnb Host Churn

**Question:** each quarter, which 500 hosts should a retention team contact to protect listings that are likely to
disappear? Built on public Inside Airbnb snapshots (6 US markets, 2015–2026) with read-only access to the source.

**Holdout results** (shared block 2023-Q4 to 2024-Q3, run once after the analysis was frozen; primary `retain` variant):

| Contact 500 hosts per quarter, ranked by | Hosts with ≥ 1 listing that disappears | Quarters better than the rule |
|---|---|---|
| Best simple rule (low presence over the past year) | 0.33 | — |
| LightGBM risk (riskiest listing) | **0.51** (+18.4 pp) | 4/4 |
| Logistic regression | 0.51 | 4/4 |
| LightGBM risk × value (Σ p·V) | **0.61** | 4/4 vs value only |
| Value only (Σ V) | 0.52 | — |
| Random | 0.17 | — |

- **Value:** ranking by risk × value captures **+11%** more estimated disappearing booking value than ranking by value alone (4/4 quarters).
- **Where the value is:** hosts with 21+ listings hold 56–66% of the captured value.
- **Model complexity:** both trained models beat the rules; LightGBM adds little host precision@500 over logistic regression on the holdout
  (it stays ahead at precision@100: 0.64 vs 0.49).
- **Sensitivity variant:** the `exclude` variant gives the same conclusions (risk vs rule +0.23, 4/4 quarters).
- **Scope:** a pooled quarterly ranking benchmark, not a deployable contact policy; probabilities overpredict on the holdout by 10.5 pp
  on average ([post-holdout audit](reports/post_holdout_audit.md)).
- **What it doesn't show:** the scores are predictive associations. Whether outreach prevents disappearances needs the
  host-randomized experiment in [docs/business_spec.md](docs/business_spec.md); about 1,722 independent hosts per arm detect a 10% reduction.

Write-up: [reports/writeup.md](reports/writeup.md). Reports: `reports/backtest_development.md`, `reports/backtest_holdout.md`, `reports/business_development.md`, `reports/business_holdout.md`.

## Data (not included)

This repository holds code, specifications and aggregate reports only. No listing-level data is committed.
The source is [Inside Airbnb](https://insideairbnb.com/get-the-data/) (CC BY 4.0): listings snapshots for Austin, Denver,
Nashville, New Orleans, San Diego and Seattle, 2015–2026, loaded into a SQLite database (`ia.db`) by a separate R pipeline.
To run the code, point `SOURCE_DIR` in `src/db.py` at a folder containing `ia.db` and `raw/<City>/*_listings.csv`.
(`src/db.py` is part of the frozen analysis, so `src/freeze.py --check` will report the change.) Everything the pipeline
writes goes to `data_local/`, which is git-ignored.

## License

Code: MIT (see `LICENSE`). Data: not redistributed; Inside Airbnb data is CC BY 4.0.

## Project layout

```
host-churn/
├── sql/          01_extract.sql … 05_features.sql
├── src/          db.py, run_sql.py, fingerprint.py, features.py, train.py, evaluate.py
├── notebooks/    eda.ipynb, results.ipynb
├── app/          Streamlit: city picker → ranked at-risk list + $ at risk
├── reports/      4-page write-up
├── data/         symlink → /Volumes/UKYECON/AirBnB Data (read-only source, not in git)
└── data_local/   extracts, features, models (not in git)
```

## Data safety

The source data (Inside Airbnb snapshots, 35 US markets, 2014–2026) lives on an
external drive and is never modified:

- `src/db.py` attaches `ia.db` with DuckDB in `READ_ONLY` mode. Write statements against it fail.
- All outputs are written to `data_local/` on the local disk.
- `src/fingerprint.py` records the size and modification time of every source file, and `--check` confirms nothing changed.

## Setup

```bash
# Python 3.12+ (scipy wheels for 3.10 fail to load on recent macOS)
/opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python src/fingerprint.py                 # baseline of the source files
python src/run_sql.py sql/01_extract.sql  # one-time extract of 6 markets
python src/rebuild_from_raw.py            # re-read price + host fields from raw CSVs
python src/run_sql.py sql/02_clean.sql    # corrected copy -> listings_6city_clean.parquet
python src/validate.py                    # reports/data_validation.md (extract)
python src/validate.py listings_6city_clean.parquet   # reports/data_validation_clean.md
python src/fingerprint.py --check         # confirm source untouched

python -m pytest tests -q                 # label + feature acceptance tests
python tests/mutation_check.py            # optional: suite must catch 21 deliberate SQL breaks (~4 min)
python src/label.py                       # labels -> data_local/labels/, reports/label_summary.md
python src/features.py                    # features -> data_local/features.parquet, reports/feature_summary.md
```

The outcome definition, population rules and evaluation timing are in
[docs/label_spec.md](docs/label_spec.md); predictors and the information rule are in
[docs/feature_spec.md](docs/feature_spec.md).

## Data quality fixes

`CURATED.TAB_LISTING_ANALYTICS` has three problems, corrected in `listings_6city_clean.parquet`
(each changed value is flagged):

| Problem | Rows | Fix | Flag |
|---|---|---|---|
| Prices ≥ $1,000 truncated to 1, 2, … (`CAST` stops at the thousands comma) | 95,984 | re-read from raw | `price_fixed` |
| Missing price stored as 0 | 76,503 | NULL | `price_fixed` |
| Response / acceptance rate 'N/A' stored as 0 | 2.16M | NULL | `rate_fixed` |
| `host_since` missing from Dec 2025 (source writes 'NA') | 134,397 | carried forward from the host's earlier snapshots | `host_since_filled` |

Not fixable: from Dec 2025 the source has no host response time, response rate or
acceptance rate, so those stay NULL. Leave them out of features, or add a missing indicator.

## Backtest

```bash
python src/backtest.py                 # development folds 2017-Q3..2023-Q3 -> reports/backtest_development.md
python src/backtest.py --report-only   # rebuild the report from saved fold results
python src/backtest.py --holdout       # shared holdout block 2023-Q4..2024-Q3, run once at the end
```

Known source discontinuities and their proposed handling: [docs/source_breaks.md](docs/source_breaks.md).

## Business evaluation and holdout

```bash
python src/business.py                 # targeting, value exposure, intervention scenarios -> reports/business_development.md
python src/freeze.py                   # freeze settings + file hashes (config/analysis_freeze.json)
python src/backtest.py --holdout       # refuses to run if any frozen file changed, or if already run
python src/business.py --holdout       # -> reports/business_holdout.md
```

Definitions, value proxy and the experiment proposal: [docs/business_spec.md](docs/business_spec.md).
