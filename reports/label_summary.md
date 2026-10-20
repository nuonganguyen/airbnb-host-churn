# Label Summary

Built 2026-10-20 by `src/label.py` from `listings_6city_clean.parquet` per `docs/label_spec.md` (v2). Rates are descriptive, not a validation target.

## Snapshot status (operational rule)

| city        |   anomaly_genuine |   insufficient_history |   ok |   partial_scrape |
|:------------|------------------:|-----------------------:|-----:|-----------------:|
| Austin      |                 3 |                      3 |   89 |                1 |
| Denver      |                 1 |                      3 |   80 |                1 |
| Nashville   |                 1 |                      3 |   91 |                1 |
| New Orleans |                 2 |                      3 |   96 |                0 |
| San Diego   |                 2 |                      3 |   87 |                1 |
| Seattle     |                 2 |                      3 |   86 |                1 |

## Flagged snapshots

| city        | snap       |   n_listings |   trailing_ratio |   n_missing |   return_rate | status          | status_known_at   |
|:------------|:-----------|-------------:|-----------------:|------------:|--------------:|:----------------|:------------------|
| Austin      | 2022-11-06 |        13591 |             0.75 |         758 |         0.088 | anomaly_genuine | 2022-12-15        |
| Austin      | 2025-09-16 |        10533 |             0.68 |        5957 |         0.126 | anomaly_genuine | 2025-12-22        |
| Austin      | 2025-12-22 |        11251 |             0.74 |        1146 |         0.066 | anomaly_genuine | 2026-03-25        |
| Austin      | 2026-03-25 |         8170 |             0.73 |        4051 |         0.625 | partial_scrape  | nan               |
| Denver      | 2020-10-29 |         3153 |             0.74 |        1905 |         0.068 | anomaly_genuine | 2020-11-30        |
| Denver      | 2026-03-31 |         2159 |             0.44 |        2380 |         0.787 | partial_scrape  | nan               |
| Nashville   | 2025-12-27 |         6594 |             0.69 |        3585 |         0.269 | anomaly_genuine | 2026-03-28        |
| Nashville   | 2026-03-28 |         6030 |             0.64 |        2225 |         0.715 | partial_scrape  | nan               |
| New Orleans | 2017-07-03 |         3665 |             0.66 |        1846 |         0.073 | anomaly_genuine | 2017-08-02        |
| New Orleans | 2017-08-02 |         3947 |             0.74 |         207 |         0.126 | anomaly_genuine | 2017-09-02        |
| San Diego   | 2017-07-11 |         3134 |             0.38 |        5681 |         0.857 | partial_scrape  | nan               |
| San Diego   | 2020-10-25 |         8688 |             0.68 |        4885 |         0.04  | anomaly_genuine | 2020-11-12        |
| San Diego   | 2020-11-12 |         8852 |             0.71 |         317 |         0.079 | anomaly_genuine | 2020-12-23        |
| Seattle     | 2020-10-25 |         4335 |             0.62 |        3194 |         0.036 | anomaly_genuine | 2020-11-12        |
| Seattle     | 2020-11-12 |         4428 |             0.67 |         213 |         0.042 | anomaly_genuine | 2020-12-23        |
| Seattle     | 2026-03-29 |         4550 |             0.66 |        2555 |         0.735 | partial_scrape  | nan               |

## Follow-up coverage by city and era

| city        | era     |   prediction_dates |   with_followup |   no_c2 |   no_c3 |   no_c2_c3 | last_labeled_t   |
|:------------|:--------|-------------------:|----------------:|--------:|--------:|-----------:|:-----------------|
| Austin      | 2015-22 |                 28 |              26 |       1 |       1 |          0 | 2022-04-14       |
| Austin      | 2023+   |                 11 |               9 |       0 |       1 |          1 | 2025-03-06       |
| Denver      | 2015-22 |                 25 |              23 |       1 |       1 |          0 | 2022-04-28       |
| Denver      | 2023+   |                 12 |               8 |       1 |       2 |          1 | 2025-03-26       |
| Nashville   | 2015-22 |                 28 |              26 |       1 |       1 |          0 | 2022-04-23       |
| Nashville   | 2023+   |                 12 |               9 |       1 |       1 |          1 | 2025-03-15       |
| New Orleans | 2015-22 |                 29 |              27 |       1 |       1 |          0 | 2022-04-10       |
| New Orleans | 2023+   |                 14 |              11 |       0 |       1 |          2 | 2025-09-11       |
| San Diego   | 2015-22 |                 27 |              25 |       1 |       1 |          0 | 2022-04-25       |
| San Diego   | 2023+   |                 14 |              11 |       0 |       1 |          2 | 2025-09-25       |
| Seattle     | 2015-22 |                 26 |              24 |       1 |       1 |          0 | 2022-04-25       |
| Seattle     | 2023+   |                 13 |               9 |       1 |       2 |          1 | 2025-03-16       |

## Actual checkpoint offsets (days after t)

| city        | era     |   c2_median |   c2_min |   c2_max |   c3_median |   c3_min |   c3_max |
|:------------|:--------|------------:|---------:|---------:|------------:|---------:|---------:|
| Austin      | 2015-22 |       182   |      153 |      193 |       275.5 |      262 |      284 |
| Austin      | 2023+   |       181   |      145 |      195 |       273   |      237 |      291 |
| Denver      | 2015-22 |       182   |      150 |      197 |       274   |      242 |      288 |
| Denver      | 2023+   |       182.5 |      179 |      189 |       274   |      269 |      280 |
| Nashville   | 2015-22 |       184   |      153 |      193 |       275   |      258 |      285 |
| Nashville   | 2023+   |       180   |      153 |      192 |       275   |      239 |      287 |
| New Orleans | 2015-22 |       182   |      175 |      192 |       274   |      267 |      284 |
| New Orleans | 2023+   |       183   |      148 |      193 |       277   |      237 |      285 |
| San Diego   | 2015-22 |       184   |      151 |      203 |       276   |      259 |      290 |
| San Diego   | 2023+   |       182   |      152 |      203 |       275   |      238 |      292 |
| Seattle     | 2015-22 |       184   |      154 |      197 |       275.5 |      243 |      290 |
| Seattle     | 2023+   |       180   |      152 |      193 |       276   |      238 |      287 |

## Population rules (counts of listing-dates)

| era     |   listings_at_t |   active_review |   via_recent_first_obs |   excl_newness_unknown |   excl_inactive |   excl_low_quality |   eligible_main |
|:--------|----------------:|----------------:|-----------------------:|-----------------------:|----------------:|-------------------:|----------------:|
| 2015-22 |         1168808 |          847611 |                 101413 |                   5738 |          214046 |               4871 |          944153 |
| 2023+   |          696523 |          505093 |                  57950 |                      0 |          133480 |               1983 |          561060 |

## Outcomes

`absent_confirmed_rate` is among listing-dates with usable follow-up.

| era     | population   |   listings |   insufficient_followup |   absent_confirmed_rate |
|:--------|:-------------|-----------:|------------------------:|------------------------:|
| 2015-22 | excluded     |     224655 |                   0.079 |                   0.219 |
| 2015-22 | main         |     944153 |                   0.096 |                   0.211 |
| 2023+   | excluded     |     135463 |                   0.25  |                   0.19  |
| 2023+   | main         |     561060 |                   0.228 |                   0.182 |

## Markets with usable outcomes per quarter (2023+, for the shared holdout block)

| quarter   |   markets_with_outcomes | markets_without                                            |
|:----------|------------------------:|:-----------------------------------------------------------|
| 2023-Q1   |                       5 |                                                            |
| 2023-Q2   |                       6 |                                                            |
| 2023-Q3   |                       6 |                                                            |
| 2023-Q4   |                       6 |                                                            |
| 2024-Q1   |                       6 |                                                            |
| 2024-Q2   |                       6 |                                                            |
| 2024-Q3   |                       6 |                                                            |
| 2024-Q4   |                       6 |                                                            |
| 2025-Q1   |                       6 |                                                            |
| 2025-Q2   |                       2 | Seattle, Austin, Denver, Nashville                         |
| 2025-Q3   |                       2 | Denver, Nashville, Seattle                                 |
| 2025-Q4   |                       0 | San Diego, New Orleans, Seattle, Denver                    |
| 2026-Q1   |                       0 | New Orleans, San Diego                                     |
| 2026-Q2   |                       0 | Austin, Seattle, San Diego, Denver, Nashville, New Orleans |

## Reactivation after confirmed absence

Right-censored: later prediction dates have less time after C3 in which to be seen again.

| era     |   absent_confirmed |   seen_again_after_c3 |
|:--------|-------------------:|----------------------:|
| 2015-22 |             225214 |                 0.118 |
| 2023+   |              98190 |                 0.063 |
