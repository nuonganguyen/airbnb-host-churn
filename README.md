# Supply at Risk: Predicting Airbnb Host Churn

_Headline chart and numbers go here once results are in._

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

python -m pytest tests -q                 # label acceptance tests (docs/label_spec.md)
python src/label.py                       # labels -> data_local/labels/, reports/label_summary.md
```

The outcome definition, population rules and evaluation timing are in
[docs/label_spec.md](docs/label_spec.md).

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
