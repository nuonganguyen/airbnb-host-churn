# Label Summary

Built 2026-10-20 by `src/label.py` from `listings_6city_clean.parquet` per `docs/label_spec.md` (v3). Rates are descriptive, not a validation target. Only `final` labels may be used for training or evaluation.

## Snapshot status (operational rule)

| city        |   anomaly_unresolved |   insufficient_history |   ok |   partial_scrape |   suspected_contraction |
|:------------|---------------------:|-----------------------:|-----:|-----------------:|------------------------:|
| Austin      |                    1 |                      3 |   89 |                0 |                       3 |
| Denver      |                    0 |                      3 |   80 |                1 |                       1 |
| Nashville   |                    0 |                      3 |   91 |                2 |                       0 |
| New Orleans |                    0 |                      3 |   96 |                0 |                       2 |
| San Diego   |                    0 |                      3 |   87 |                1 |                       2 |
| Seattle     |                    0 |                      3 |   86 |                1 |                       2 |

## Flagged snapshots

| city        | snap       |   n_listings |   trailing_ratio | reference_snap   | resolver_snap   |   n_missing |   return_rate | status                | status_known_at   |
|:------------|:-----------|-------------:|-----------------:|:-----------------|:----------------|------------:|--------------:|:----------------------|:------------------|
| Austin      | 2022-11-06 |        13587 |             0.75 | 2022-10-13       | 2022-12-15      |         757 |         0.089 | suspected_contraction | 2022-12-29        |
| Austin      | 2025-09-16 |        10533 |             0.68 | 2025-06-13       | nan             |        5957 |       nan     | anomaly_unresolved    | 2026-04-04        |
| Austin      | 2025-12-22 |        11251 |             0.74 | 2025-06-13       | 2026-06-22      |        6033 |         0.06  | suspected_contraction | 2026-07-02        |
| Austin      | 2026-03-25 |         8170 |             0.73 | 2025-06-13       | 2026-06-22      |        9002 |         0.258 | suspected_contraction | 2026-07-02        |
| Denver      | 2020-10-29 |         3153 |             0.74 | 2020-06-28       | 2020-11-30      |        1905 |         0.068 | suspected_contraction | 2020-12-04        |
| Denver      | 2026-03-31 |         2159 |             0.44 | 2025-12-30       | 2026-06-30      |        2380 |         0.787 | partial_scrape        | 2026-07-02        |
| Nashville   | 2025-12-27 |         6594 |             0.69 | 2025-09-23       | 2026-06-26      |        3585 |         0.664 | partial_scrape        | 2026-07-03        |
| Nashville   | 2026-03-28 |         6030 |             0.64 | 2025-09-23       | 2026-06-26      |        4526 |         0.636 | partial_scrape        | 2026-07-03        |
| New Orleans | 2017-07-03 |         3665 |             0.66 | 2017-06-02       | 2017-09-02      |        1846 |         0.063 | suspected_contraction | 2017-09-02        |
| New Orleans | 2017-08-02 |         3947 |             0.74 | 2017-06-02       | 2017-09-02      |        1877 |         0.011 | suspected_contraction | 2017-09-02        |
| San Diego   | 2017-07-11 |         3134 |             0.38 | 2017-06-08       | 2017-08-11      |        5681 |         0.857 | partial_scrape        | 2017-08-12        |
| San Diego   | 2020-10-25 |         8688 |             0.68 | 2020-07-27       | 2020-12-23      |        4885 |         0.072 | suspected_contraction | 2020-12-30        |
| San Diego   | 2020-11-12 |         8852 |             0.71 | 2020-07-27       | 2020-12-23      |        4834 |         0.039 | suspected_contraction | 2020-12-30        |
| Seattle     | 2020-10-25 |         4335 |             0.62 | 2020-06-17       | 2020-12-23      |        3194 |         0.049 | suspected_contraction | 2020-12-30        |
| Seattle     | 2020-11-12 |         4428 |             0.67 | 2020-06-17       | 2020-12-23      |        3153 |         0.02  | suspected_contraction | 2020-12-30        |
| Seattle     | 2026-03-29 |         4550 |             0.66 | 2025-12-28       | 2026-06-15      |        2555 |         0.735 | partial_scrape        | 2026-07-06        |

## Follow-up coverage by city and era

| city        | era     |   prediction_dates |   provisional |   final_with_followup |   final_no_c2 |   final_no_c3 |   final_no_c2_c3 | last_labeled_t   |
|:------------|:--------|-------------------:|--------------:|----------------------:|--------------:|--------------:|-----------------:|:-----------------|
| Austin      | 2015-22 |                 28 |             0 |                    26 |             1 |             1 |                0 | 2022-04-14       |
| Austin      | 2023+   |                 11 |             1 |                     8 |             1 |             1 |                0 | 2025-06-13       |
| Denver      | 2015-22 |                 25 |             0 |                    23 |             1 |             1 |                0 | 2022-04-28       |
| Denver      | 2023+   |                 12 |             3 |                     8 |             0 |             1 |                0 | 2025-03-26       |
| Nashville   | 2015-22 |                 28 |             0 |                    26 |             1 |             1 |                0 | 2022-04-23       |
| Nashville   | 2023+   |                 12 |             2 |                     8 |             0 |             1 |                1 | 2024-12-21       |
| New Orleans | 2015-22 |                 29 |             0 |                    27 |             1 |             1 |                0 | 2022-04-10       |
| New Orleans | 2023+   |                 14 |             4 |                    10 |             0 |             0 |                0 | 2025-06-09       |
| San Diego   | 2015-22 |                 27 |             0 |                    25 |             1 |             1 |                0 | 2022-04-25       |
| San Diego   | 2023+   |                 14 |             4 |                    10 |             0 |             0 |                0 | 2025-06-21       |
| Seattle     | 2015-22 |                 26 |             0 |                    24 |             1 |             1 |                0 | 2022-04-25       |
| Seattle     | 2023+   |                 13 |             3 |                     9 |             0 |             1 |                0 | 2025-03-16       |

## Actual checkpoint offsets (days after t)

| city        | era     |   c2_median |   c2_min |   c2_max |   c3_median |   c3_min |   c3_max |
|:------------|:--------|------------:|---------:|---------:|------------:|---------:|---------:|
| Austin      | 2015-22 |       182   |      153 |      193 |       275.5 |      262 |      284 |
| Austin      | 2023+   |       182.5 |      145 |      195 |       273   |      237 |      287 |
| Denver      | 2015-22 |       182   |      150 |      197 |       274   |      242 |      288 |
| Denver      | 2023+   |       182.5 |      179 |      189 |       274   |      269 |      280 |
| Nashville   | 2015-22 |       184   |      153 |      193 |       275   |      258 |      285 |
| Nashville   | 2023+   |       179.5 |      153 |      190 |       274.5 |      239 |      280 |
| New Orleans | 2015-22 |       182   |      175 |      192 |       274   |      267 |      284 |
| New Orleans | 2023+   |       182   |      148 |      193 |       277   |      237 |      285 |
| San Diego   | 2015-22 |       184   |      151 |      203 |       276   |      259 |      290 |
| San Diego   | 2023+   |       181   |      152 |      203 |       274   |      238 |      292 |
| Seattle     | 2015-22 |       184   |      154 |      197 |       275.5 |      243 |      290 |
| Seattle     | 2023+   |       180   |      152 |      193 |       276   |      238 |      287 |

## Population rules (counts of listing-dates)

| era     |   listings_at_t |   active_review |   via_recent_first_obs |   excl_newness_unknown |   excl_inactive |   excl_low_quality |   eligible_main |
|:--------|----------------:|----------------:|-----------------------:|-----------------------:|----------------:|-------------------:|----------------:|
| 2015-22 |         1168767 |          847586 |                 101397 |                   5738 |          214046 |               4871 |          944112 |
| 2023+   |          696507 |          505080 |                  57947 |                      0 |          133480 |               1983 |          561044 |

## Outcomes

`absent_confirmed_rate` = absent_confirmed / usable, where usable excludes insufficient_followup. Training rows are final, usable and eligible_main (see `src/features.py:training_frame`). Provisional labels can still change as data arrives.

| era     | label_status   | population   |   listings |   absent_confirmed |   observed |   insufficient_followup |   usable |   absent_confirmed_rate |
|:--------|:---------------|:-------------|-----------:|-------------------:|-----------:|------------------------:|---------:|------------------------:|
| 2015-22 | final          | excluded     |     224655 |              45260 |     161650 |                   17745 |   206910 |                   0.219 |
| 2015-22 | final          | main         |     944112 |             179952 |     673690 |                   90470 |   853642 |                   0.211 |
| 2023+   | final          | excluded     |     105315 |              17828 |      73270 |                   14217 |    91098 |                   0.196 |
| 2023+   | final          | main         |     445473 |              72881 |     324845 |                   47747 |   397726 |                   0.183 |
| 2023+   | provisional    | excluded     |      30148 |                945 |       3873 |                   25330 |     4818 |                   0.196 |
| 2023+   | provisional    | main         |     115571 |               2237 |      13551 |                   99783 |    15788 |                   0.142 |

## Markets with final outcomes per quarter (2023+, for the shared holdout block)

A market without a prediction date in a quarter is not listed.

| quarter   |   markets_with_final_outcomes | markets_without                                            |
|:----------|------------------------------:|:-----------------------------------------------------------|
| 2023-Q1   |                             5 |                                                            |
| 2023-Q2   |                             6 |                                                            |
| 2023-Q3   |                             6 |                                                            |
| 2023-Q4   |                             6 |                                                            |
| 2024-Q1   |                             6 |                                                            |
| 2024-Q2   |                             6 |                                                            |
| 2024-Q3   |                             6 |                                                            |
| 2024-Q4   |                             5 | Austin                                                     |
| 2025-Q1   |                             4 | Nashville, Austin                                          |
| 2025-Q2   |                             3 | Nashville, Denver, Seattle                                 |
| 2025-Q3   |                             0 | San Diego, New Orleans, Nashville, Denver, Seattle         |
| 2025-Q4   |                             0 | Denver, New Orleans, San Diego, Seattle                    |
| 2026-Q1   |                             0 | New Orleans, San Diego                                     |
| 2026-Q2   |                             0 | New Orleans, Denver, Seattle, Austin, San Diego, Nashville |

## Reactivation after confirmed absence

Right-censored: later prediction dates have less time after C3 in which to be seen again.

| era     |   absent_confirmed |   seen_again_after_c3 |
|:--------|-------------------:|----------------------:|
| 2015-22 |             225212 |                 0.118 |
| 2023+   |              90709 |                 0.066 |
