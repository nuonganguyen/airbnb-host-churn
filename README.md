# Supply at Risk: Predicting Airbnb Host Churn

**Which 500 Airbnb hosts should a retention team contact each quarter?** This project compares simple rules,
logistic regression and LightGBM using public [Inside Airbnb](https://insideairbnb.com/get-the-data/) snapshots from
six US markets. On a four-quarter holdout, LightGBM selects **about 90 more hosts per 500 whose listings later
disappear** than the best rule (51% vs 33% host precision).

This is a historical targeting benchmark. Listing disappearance is a proxy for churn; outreach effectiveness is
untested, and contact timing must be corrected and evaluated before a live pilot.

Full write-up: [reports/writeup.md](reports/writeup.md) · Step-by-step notebook:
[notebooks/walkthrough.ipynb](notebooks/walkthrough.ipynb)

## 1. Key findings

The holdout covers **2023-Q4 to 2024-Q3** and was evaluated once after the analysis settings were frozen.

1. **LightGBM beats the best rule by 18.4 percentage points (pp)** in host precision@500, with gains in all four
   holdout quarters (+15.6 to +20.8 pp).
2. **Logistic regression nearly ties LightGBM at 500 contacts** (0.508 vs 0.511). At 100 contacts, LightGBM leads
   0.64 to 0.49.
3. **Risk × value beats estimated booking value alone**: 0.61 vs 0.52 host precision@500 and 11% more estimated
   booking value associated with confirmed absences. Both metrics improve in all four quarters in the central value
   scenario.

Break-even outreach costs are scenario estimates, covered in [section 5](#5-evaluation-and-results).

![Share of 500 contacted hosts with a listing that later disappears, by quarter](reports/figures/host_precision_by_quarter.png)

*LightGBM (blue) sits above the best rule (orange) in every quarter. The 2023-Q1 spike is a suspected source break
(see [Data](#3-data)).*

## 2. Business problem and decision

The assumed capacity is **500 unique hosts per quarter across all six markets**. The primary metric is
**host precision@500**: the share of selected hosts with at least one eligible listing later classified as
`absent_confirmed`. For targeting by value, the metric is the estimated booking value of those absent listings.
These measure which hosts the list reaches; retained listings require an outreach experiment.

## 3. Data

| Attribute | Definition |
|---|---|
| **Source** | [Inside Airbnb](https://insideairbnb.com/get-the-data/) listing snapshots |
| **Markets** | Austin, Denver, Nashville, New Orleans, San Diego, Seattle |
| **Period** | May 2015 – June 2026; monthly snapshots until 2022, quarterly after |
| **Size** | 563 snapshots, 4.2M listing-snapshot rows; 1,865,274 listing × prediction-date rows in the feature table |
| **Unit of observation** | a listing present at a quarterly prediction snapshot *t*; hosts are the contact unit |
| **Target** | `absent_confirmed`: missing from the usable snapshot nearest *t* + 180 days **and** from the one nearest *t* + 270 days (±45 days each); both checkpoints must be available and final |
| **Population** | listings with a review in the last 365 days, or first observed within 180 days of *t* with city coverage starting ≥ 180 days before first observation; excludes ratings below 4.0 with ≥ 5 reviews |

**Why two checkpoints.** A "never seen again within 180 days" label misses listings that reappear briefly and then
leave, and gives monthly snapshots more chances to record a return. Fixed checkpoints reduce this dependence on
snapshot frequency. Full definition: [docs/label_spec.md](docs/label_spec.md).

**Limitations:**

- **The curated source had six data-quality issues**, corrected or excluded in a derived copy with changes flagged.
  Examples: prices ≥ $1,000 parsed as 1–15 (95,984 rows), 2.2M missing values stored as zero, and snapshot rows collected
  days after the file date. Full table in [the write-up](reports/writeup.md#2-data).
- **A missing listing ID does not establish host departure.** Listings can reappear or receive new IDs.
- **Some snapshots are partial scrapes.** A count below 75% of the preceding three-snapshot median triggers a flag.
  The snapshot cannot be used as a checkpoint until a later reliable snapshot resolves the flag; partial scrapes and
  unresolved flags are excluded.
- **January 2023 is a suspected source break.** 37–50% of listings were labelled absent, against 13–22% in neighbouring
  quarters, and 35–49% of the vanished IDs have a possible replacement ID (same host, neighbourhood, room type and capacity)
  against ≤ 8% in all 473 earlier snapshot pairs. The cause is unresolved
  ([docs/source_breaks.md](docs/source_breaks.md)).

## 4. Approach

The pipeline uses DuckDB SQL for labels and features, then trains models in a rolling-origin backtest. Listing
features use information available at their snapshot's collection date. Host aggregation has a separate timing
limitation described in [section 5](#5-evaluation-and-results).

1. **Wait for final labels.** Training uses a label only after its checkpoint windows and any relevant snapshot flags
   are resolved, so later observations cannot change it under the specified arrival rules.
2. **Build point-in-time features.** 61 predictors in SQL: the listing's state at *t*, tenure and recency, change over
   ~90 and ~365 days, presence over the past year, the host's portfolio, and city and neighbourhood supply. Timing uses
   actual collection dates; label outputs and listing/host IDs are excluded ([docs/feature_spec.md](docs/feature_spec.md)).
3. **Compare with simple rules.** Test days since the last review, low presence over the past year, a low recent review
   rate, and a fully blocked calendar. **Low presence over the past year** wins on mean listing-level average precision
   in development and becomes the fixed rule baseline.
4. **Train logistic regression and LightGBM.** Fit preprocessing within each fold and calibrate both models on the
   latest two available training quarters, held out for validation.
5. **Rank hosts, and optionally weight by value.** Listings are scored and hosts are ranked by their riskiest listing.
   For the value-weighted list, each listing gets a proxy *V*: twelve months of gross booking value at its asking price,
   with bookings estimated from reviews. Hosts are ranked by **Σ p·V**, summed over eligible listings, where *p* is the
   model's predicted absence probability.
6. **Split by time and freeze the holdout.** A rolling-origin backtest trains each quarter's fold only on labels final
   before that quarter starts: 23 development folds between 2017-Q3 and 2023-Q3. Settings and file hashes were saved in
   [config/analysis_freeze.json](config/analysis_freeze.json) before the holdout. The backtest refuses to rerun the
   holdout when its saved metrics exist.

**Leakage checks.** On synthetic scenarios, tests compare features built from full data with builds that truncate or
alter future rows, and verify that final labels stay unchanged as observations arrive. The suite has 91 tests; the
mutation runner checks its ability to catch 24 deliberate SQL bugs.

## 5. Evaluation and results

Values are means across evaluated quarters for the primary (`retain`) analysis. Random contact is the expected
host event rate. Full results: [development](reports/backtest_development.md) and [holdout](reports/backtest_holdout.md).

| Ranked by | Development precision@500 (23 quarters) | **Holdout precision@500 (4 quarters)** | Holdout precision@100 |
|---|---|---|---|
| Random contact (expected) | 0.22 | 0.17 | 0.17 |
| Best simple rule | 0.43 | 0.33 | 0.36 |
| Logistic regression | 0.52 | 0.51 | 0.49 |
| **LightGBM** | **0.61** | **0.51** | **0.64** |

LightGBM also beats the rule in all 23 development folds: +17.9 pp, with an approximate block-bootstrap 95% confidence
interval of 13.9–20.8 pp. Holdout precision is lower alongside a lower host event rate (17% vs 22%); this does not
establish why precision fell. The prespecified sensitivity analysis, which excludes affected comparisons and masks
history across the suspected source break, gives a mean holdout gain of 23.2 pp, positive in all four quarters.

The [post-holdout audit](reports/post_holdout_audit.md) identifies two limits:

- **Probability calibration:** LightGBM overpredicts listing absence in every holdout quarter, by 10.5 pp on average
  and 13.9 pp at worst. Recalibration could change the risk × value ranking.
- **Contact timing:** markets are scraped on different days. Up to 24 of 500 selected hosts per quarter were ranked
  using listings observed after their assigned contact date. A shared information cutoff or sequential selection
  across markets must be evaluated before deployment.

**Business scenarios.** Under risk × value targeting, the estimated booking value of confirmed-absent listings held
by selected hosts averages **$37.1M per quarter** in the central scenario. This is a proxy for exposure, not observed
revenue lost or saved. The [business evaluation](reports/business_holdout.md) calculates:

> Net benefit per quarter = prevention rate × platform take rate × captured value − cost per contact × 500.

Here, prevention rate is the assumed share of otherwise-occurring disappearances prevented by outreach; platform
take rate is the share of booking value earned as platform revenue. Break-even cost ranges from **about $370 per
contact** (5% prevention, 10% platform take rate) to **$2,200** (20%, 15%). Outreach effectiveness remains unknown.

## 6. Recommendations and limitations

The results support evaluating a model-ranked pilot after resolving contact timing and calibration. At 500 contacts,
logistic regression offers a simpler candidate with nearly the same holdout precision; LightGBM performs better at
100 contacts. Risk × value targets more estimated exposure but concentrates outreach on large portfolios: hosts with
21+ eligible listings make up about 32% of that list, compared with 7% of the risk-only list.

1. **Evaluate selection under a shared information cutoff or sequential market arrivals.** Recalibrate probabilities
   and check how the resulting lists change before using them in a pilot or forecast.
2. **Test outreach with a host-randomized experiment.** The proposal recruits the top 1,000 hosts per quarter by
   Σ p·V and randomizes them equally to outreach or business as usual, stratified by market and portfolio size.
   At the observed 47.5% event rate, a 10% relative reduction requires about **1,722 independent hosts per arm**
   (80% power, two-sided 5% significance). Four recruitment quarters assumes 500 new hosts per arm each quarter;
   each host is randomized once, with follow-up until labels are final. Reassess sizing if selection changes.
   See the [design](docs/business_spec.md) and
   [corrected sizing](reports/post_holdout_audit.md#3-experiment-sizing-on-the-proposed-recruitment-population).
3. **Validate links between re-created listing IDs.** Reviewed one-to-one matches could help distinguish listing
   replacement from actual loss of supply.

The analysis does not establish why hosts leave, whether outreach prevents departure, or realized financial impact.

## 7. Repository structure

```
airbnb-host-churn/
├── sql/       01_extract → 02_clean → 03_label → 04_features
├── src/       data preparation, validation, labels, features, models and evaluation
├── scripts/   reproduction, figures, post-holdout audit and Power BI export
├── notebooks/ walkthrough.ipynb: executed walkthrough from labels onward
├── powerbi/   optional semantic model and setup instructions
├── tests/     automated tests and SQL mutation checks
├── docs/      label, feature and business specifications; source-break analysis
├── config/    frozen analysis settings and data-quality policy
└── reports/   write-up, validation, evaluation, audit and figures
```

## 8. How to reproduce

**Data required.** Listing-level data is not included. The pipeline expects a prepared SQLite database (`ia.db`) and
`raw/<City>/*_listings.csv` files from a separate ingestion pipeline. The database must contain the curated and metadata
tables referenced in [sql/01_extract.sql](sql/01_extract.sql) and [src/rebuild_from_raw.py](src/rebuild_from_raw.py);
downloading CSVs alone is insufficient. Set `SOURCE_DIR` in [src/db.py](src/db.py) to that source folder. Changing this
file causes the final freeze check to fail because its original hash is part of the frozen analysis.

**Environment.** Use Python 3.12. Run from the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
scripts/reproduce.sh                      # rebuild pipeline; requirements below
.venv/bin/python tests/mutation_check.py   # optional SQL mutation checks
```

The [reproduction script](scripts/reproduce.sh) extracts and cleans data, builds labels and features, runs tests,
rebuilds development evaluations, generates the chart and checks the freeze and source-file manifest. Pipeline outputs
go to `data_local/` (git-ignored) and `reports/`; runtime depends on data access and hardware.

**Saved holdout artifacts are also required for the chart.** `scripts/make_figures.py` reads
`data_local/backtest/holdout_metrics.csv` and `holdout_folds.csv`, which are not committed. Without them, the script
stops at figure generation. It does not regenerate the holdout. Published results are in
[reports/backtest_holdout.md](reports/backtest_holdout.md) and [reports/business_holdout.md](reports/business_holdout.md).

**Power BI (optional).** `scripts/export_powerbi.py` exports the results for a Power BI report; setup steps are in
[powerbi/README.md](powerbi/README.md).

## 9. References and credits

- **Data:** [Inside Airbnb](https://insideairbnb.com/), licensed CC BY 4.0.
- **Methods:**
  - Ke, G., et al. (2017). LightGBM: A highly efficient gradient boosting decision tree. *Advances in Neural Information
    Processing Systems 30*.
  - Tashman, L. J. (2000). Out-of-sample tests of forecasting accuracy: An analysis and review. *International Journal of
    Forecasting*, 16(4), 437–450. (rolling-origin evaluation)
  - Künsch, H. R. (1989). The jackknife and the bootstrap for general stationary observations. *The Annals of
    Statistics*, 17(3), 1217–1241. (moving-block bootstrap)
- **Author:** Nuong Nguyen.
- **License:** code is MIT (see [LICENSE](LICENSE)).
