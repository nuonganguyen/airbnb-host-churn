# Feature Specification

Implemented in `sql/04_features.sql` and `src/features.py`. Acceptance gate: `tests/test_features.py`, plus
`tests/mutation_check.py`. Builds on the label tables from `docs/label_spec.md` (v3).

## 1. Rows

One row per **(city_id, list_id, t)** for **every listing present at a prediction date**, whether or not
an outcome is known yet. The same table therefore supports training (historical rows with final outcomes) and
scoring (current rows). It currently has 1,865,331 rows, one per key.

## 2. Information rule

A row uses only:
- **The snapshot at *t*,** whose rows finished collecting at `decision_date` (≥ *t*). History counts only if its status
  was known by `decision_date`.
- **History snapshots** dated **before *t*** whose status (`ok`, `insufficient_history`, `suspected_contraction`)
  was **known by *t***. Partial scrapes, unresolved anomalies and pending anomalies are never history.
- **Per-snapshot aggregates** (city, room type, neighbourhood, host) computed from that snapshot's rows alone.

So data arriving after *t* cannot change a row. Tests rebuild every prediction date from data truncated at *t*,
and from data whose later rows were changed, dropped and added to. Each must match the full build exactly.

## 3. Approved predictors (`features.ALLOWLIST`, 61)

| Group | Predictors | Notes |
|---|---|---|
| State at *t* | price, price_missing, capacity, bathrooms, bedrooms, beds, min/max nights, availability 30/60/90/365, number_of_reviews, 7 ratings, amenity_count, amenity_count_pct, descrip_word_count, host_about_word_count, superhost, host_listing_count, host_has_pic, host_verified | raw values; `amenity_count_pct` is the listing's percentile within its own snapshot, which survives changes in amenity formats |
| Categories | city_id, room_type, listing_type, quarter_of_year | encoded per fold |
| Tenure / recency | days_since_first_observed, first_observed_censored, host_tenure_days, days_since_last_review, days_since_first_review | measured from `decision_date`, when the snapshot finished collecting; "first observed", not "created": censored if first seen within 180 d of coverage start |
| ~90-day change | lag90_days, present_lag90, price_change_90, avail365_change_90, rating_change_90, reviews_added_90, review_rate_90, reviews_decreased_90 | anchor: the history snapshot nearest *t*−90 (±45 d); **elapsed days included**; rates per 30 days |
| ~365-day change | lag365_days, present_lag365, price_change_365, reviews_added_365, review_rate_365 | anchor nearest *t*−365 (±45 d) |
| Presence | hist_snapshots_365, hist_present_365, presence_rate_365 | share of usable snapshots in the past year with the listing; a rate, so it works for both monthly and quarterly snapshots |
| Host portfolio | host_n_listings, host_listings_change_90 | the host's listings in this city, counted from the data |
| Market | city_n_listings, city_supply_growth_365, price_rel_room_median, neighbourhood_n_listings, neighbourhood_supply_growth_365, price_rel_neighbourhood_median | growth uses usable anchor snapshots only; neighbourhood = raw `neighbourhood_cleansed` |

**Not predictors (`features.FORBIDDEN`):**
- **Label outputs:** checkpoints, presence at checkpoints, outcome, `host_changed`, finality fields. These are derived from the future.
- **Population filters:** `eligible_main` and its parts.
- **Identifiers:** listing and host IDs, `neighbourhood` itself.
- **Curated amenity flags `AC1`–`AC82`:** each code is a factor position of a hand label, built from all years at once. One is the
  discard label "remove", and prevalence is implausible and unstable (e.g. "waterslide" 96% in 2016, "alarm" 96% in
  2021–22; 16 of 82 flags move by more than 0.20 between years).
- **Curated `zip`:** despite the name, it mostly holds `neighbourhood_cleansed` (Seattle "Alki", New Orleans "Audubon";
  Austin's neighbourhoods are zip codes), with other values mixed in for Austin 2022 (80 values vs 44).
- **Fields missing at deployment:** host response time, response rate and acceptance rate (absent from Dec 2025), and location-overview counts (100% missing in 2026).

`model_matrix()` returns exactly the allowlist, in a fixed order, and fails if any predictor is missing.

## 4. Fitted inside each training fold (never in SQL)

The SQL produces raw values. In each backtest fold, the preprocessing pipeline is fitted on that fold's training rows only:
- **Price:** a cap at the training p99 for `price` and the price ratios.
- **Numeric predictors:** median imputation plus missing-value indicators. Price missingness rises to 17% in 2023+, bedrooms to 14% and beds to 12%.
- **Categoricals:** one-hot with a minimum frequency; rare `listing_type` values go to "other". Unseen categories are allowed at scoring.
- **Scaling:** for logistic regression only. Tree models are unscaled.

## 5. Training and scoring rows

```sql
-- features.training_frame(con, deployment_date)
WHERE eligible_main
  AND label_status = 'final'
  AND outcome IN ('absent_confirmed', 'observed')
  AND label_final_at < :deployment_date
```

`features.scoring_frame(con, t)` returns eligible rows at *t* regardless of outcome. Both `label.build` and
`features.build` refuse inputs that contain snapshots after `as_of`.

## 6. Known limitations
- **Lag anchors can be missing:** the 90-day anchor is absent for 11% of 2023+ rows (longer gaps between snapshots), and the 365-day anchor for 6–8%. Change features are then NULL, and imputation plus missing-value indicators handle it in each fold.
- **Small negative recency values:** `days_since_last_review` can be slightly negative (up to ~21 days), because the source file date comes before its scrape.
- **Price missingness shifts over time.** It's informative but changes across eras, so watch it in backtests by era.
- **Neighbourhood definitions:** neighbourhood features assume `neighbourhood_cleansed` boundaries are stable within a market.

## 7. Quality policy

`src/quality.py` applies the variants in `config/quality_policy.json` on top of these features without changing the
table. Under `exclude`, for decisions on/after the effective date, history features whose windows span a registered
break are set to NULL (`history_crosses_break` marks them, as metadata, not a predictor).
