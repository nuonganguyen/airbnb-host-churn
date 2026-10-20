# Backtest Summary: development

Built 2026-10-20 by `src/backtest.py`. 23 quarterly folds, 2017Q3–2023Q3. The shared holdout block (2023-Q4–2024-Q3) was **not** used.

Each fold trains on final, usable, eligible labels with `label_final_at` before the quarter starts, early-stops and calibrates on the latest 2 training quarters, and evaluates on eligible rows at that quarter's prediction dates. Host precision@K ranks unique hosts (host at *t*) by their riskiest listing; a hit is a host with ≥ 1 listing `absent_confirmed`. Scores are predictive associations, not causes.

Best simple rule (highest mean AP on the development folds): `rule:low_presence_365`.

## Mean over folds

| model                       |    ap |   auc |   host_p@100 |   host_p@500 |   host_p@1000 |
|:----------------------------|------:|------:|-------------:|-------------:|--------------:|
| lgbm                        | 0.377 | 0.699 |        0.697 |        0.608 |         0.55  |
| lr                          | 0.347 | 0.673 |        0.575 |        0.523 |         0.49  |
| rule:low_presence_365       | 0.313 | 0.644 |        0.42  |        0.426 |         0.436 |
| rule:low_review_rate_90     | 0.275 | 0.611 |        0.272 |        0.273 |         0.271 |
| rule:calendar_blocked       | 0.241 | 0.539 |        0.261 |        0.272 |         0.274 |
| rule:days_since_last_review | 0.233 | 0.53  |        0.371 |        0.322 |         0.307 |

## Sensitivity: excluding suspect folds

`2023Q1`: Jan→Jun 2023 source coverage break.

| model                 |    ap |   auc |   host_p@100 |   host_p@500 |   host_p@1000 |
|:----------------------|------:|------:|-------------:|-------------:|--------------:|
| lgbm                  | 0.361 | 0.695 |        0.686 |        0.593 |         0.533 |
| lr                    | 0.332 | 0.671 |        0.563 |        0.508 |         0.472 |
| rule:low_presence_365 | 0.288 | 0.632 |        0.402 |        0.404 |         0.413 |

## Lift over the best rule

CI from a bootstrap over folds. Outcomes overlap across folds (~9-month follow-up), so treat the intervals as approximate.

| comparison                                         | metric     |   mean_diff | 95% CI (folds)   | folds_better   |
|:---------------------------------------------------|:-----------|------------:|:-----------------|:---------------|
| lr − rule:low_presence_365                         | ap         |       0.033 | [0.005, 0.057]   | 19/23          |
| lr − rule:low_presence_365                         | host_p@500 |       0.096 | [0.059, 0.135]   | 18/23          |
| lgbm − rule:low_presence_365                       | ap         |       0.064 | [0.036, 0.089]   | 20/23          |
| lgbm − rule:low_presence_365                       | host_p@500 |       0.182 | [0.150, 0.215]   | 23/23          |
| lr − rule:low_presence_365 (excl. suspect folds)   | host_p@500 |       0.104 | [0.068, 0.138]   | 18/22          |
| lgbm − rule:low_presence_365 (excl. suspect folds) | host_p@500 |       0.189 | [0.159, 0.221]   | 22/22          |

## Average precision by era

| era     |   lgbm |    lr |   rule:low_presence_365 |
|:--------|-------:|------:|------------------------:|
| 2017–19 |  0.351 | 0.325 |                   0.275 |
| 2020–21 |  0.374 | 0.34  |                   0.33  |
| 2022–23 |  0.435 | 0.401 |                   0.363 |

## Calibration (Platt on the validation quarters)

`gap` = mean predicted probability − observed rate in the evaluation quarter.

| model   |   brier |   mean_abs_gap |   worst_gap |
|:--------|--------:|---------------:|------------:|
| lgbm    |  0.1588 |         0.0563 |     -0.2813 |
| lr      |  0.1613 |         0.0538 |     -0.3048 |

## Per fold

| quarter   |   n_train |   n_val |   n_eval |   base_rate |   n_hosts |   host_base_rate |   lgbm_trees |   AP lr |   AP lgbm |   AP rule:low_presence_365 |   host P@500 lr |   host P@500 lgbm |   host P@500 rule:low_presence_365 |
|:----------|----------:|--------:|---------:|------------:|----------:|-----------------:|-------------:|--------:|----------:|---------------------------:|----------------:|------------------:|-----------------------------------:|
| 2017Q3    |     11999 |   40613 |    29072 |       0.203 |     19765 |            0.222 |          103 |   0.316 |     0.337 |                      0.269 |           0.44  |             0.548 |                              0.374 |
| 2017Q4    |     30066 |   49989 |    34154 |       0.207 |     22536 |            0.235 |          108 |   0.319 |     0.367 |                      0.273 |           0.432 |             0.584 |                              0.336 |
| 2018Q1    |     54962 |   56318 |    35820 |       0.194 |     22948 |            0.23  |           85 |   0.315 |     0.374 |                      0.276 |           0.506 |             0.632 |                              0.48  |
| 2018Q2    |     83124 |   57365 |    36720 |       0.191 |     23205 |            0.222 |          297 |   0.309 |     0.354 |                      0.27  |           0.47  |             0.602 |                              0.388 |
| 2018Q3    |    111280 |   54645 |    38939 |       0.206 |     23994 |            0.231 |          191 |   0.343 |     0.329 |                      0.287 |           0.546 |             0.586 |                              0.42  |
| 2018Q4    |    140489 |   63226 |    40183 |       0.201 |     24479 |            0.224 |           33 |   0.354 |     0.331 |                      0.3   |           0.57  |             0.49  |                              0.434 |
| 2019Q1    |    169561 |   69974 |    39926 |       0.182 |     23814 |            0.204 |          586 |   0.303 |     0.312 |                      0.274 |           0.524 |             0.626 |                              0.402 |
| 2019Q2    |    203715 |   72540 |    41125 |       0.193 |     24242 |            0.22  |          559 |   0.323 |     0.34  |                      0.258 |           0.528 |             0.584 |                              0.42  |
| 2019Q3    |    239535 |   75659 |    42771 |       0.215 |     24926 |            0.245 |          117 |   0.343 |     0.382 |                      0.277 |           0.564 |             0.624 |                              0.416 |
| 2019Q4    |    276255 |   79122 |    42708 |       0.212 |     24352 |            0.238 |          137 |   0.323 |     0.383 |                      0.27  |           0.522 |             0.662 |                              0.47  |
| 2020Q1    |    315194 |   80109 |    42059 |       0.246 |     23450 |            0.248 |          132 |   0.32  |     0.354 |                      0.304 |           0.47  |             0.552 |                              0.482 |
| 2020Q2    |    355377 |   81051 |    40559 |       0.337 |     22380 |            0.344 |          207 |   0.423 |     0.481 |                      0.383 |           0.556 |             0.718 |                              0.61  |
| 2020Q3    |    395303 |   83896 |    26791 |       0.232 |     14509 |            0.248 |          407 |   0.338 |     0.353 |                      0.276 |           0.504 |             0.588 |                              0.506 |
| 2020Q4    |    436428 |   85479 |    30708 |       0.227 |     16429 |            0.219 |          692 |   0.306 |     0.332 |                      0.394 |           0.47  |             0.61  |                              0.472 |
| 2021Q1    |    479199 |   84767 |    30141 |       0.216 |     15794 |            0.204 |           57 |   0.325 |     0.378 |                      0.371 |           0.504 |             0.638 |                              0.488 |
| 2021Q2    |    521907 |   82618 |    28132 |       0.199 |     14378 |            0.178 |           37 |   0.334 |     0.34  |                      0.352 |           0.492 |             0.59  |                              0.372 |
| 2021Q3    |    563966 |   67350 |    29810 |       0.179 |     15319 |            0.164 |           70 |   0.35  |     0.387 |                      0.289 |           0.492 |             0.54  |                              0.292 |
| 2021Q4    |    604525 |   43606 |    32205 |       0.162 |     16812 |            0.161 |           50 |   0.326 |     0.372 |                      0.27  |           0.518 |             0.59  |                              0.338 |
| 2022Q1    |    631316 |   60849 |    33743 |       0.142 |     17607 |            0.147 |          367 |   0.323 |     0.383 |                      0.246 |           0.482 |             0.546 |                              0.324 |
| 2022Q2    |    662024 |   58273 |    37595 |       0.153 |     19317 |            0.171 |         1996 |   0.391 |     0.451 |                      0.273 |           0.518 |             0.694 |                              0.298 |
| 2023Q1    |    750107 |   65948 |    38903 |       0.438 |     19237 |            0.448 |          741 |   0.681 |     0.739 |                      0.863 |           0.844 |             0.94  |                              0.918 |
| 2023Q2    |    782312 |   71338 |    46747 |       0.162 |     23314 |            0.18  |         1213 |   0.295 |     0.281 |                      0.201 |           0.52  |             0.498 |                              0.23  |
| 2023Q3    |    782312 |   71338 |    46997 |       0.177 |     23543 |            0.204 |         1213 |   0.317 |     0.321 |                      0.234 |           0.546 |             0.548 |                              0.338 |

## LightGBM: top 20 features by gain share (mean over folds)

| feature                |   mean_gain_share |
|:-----------------------|------------------:|
| available_365          |            0.0814 |
| presence_rate_365      |            0.0772 |
| listing_type           |            0.0527 |
| avail365_change_90     |            0.0453 |
| host_listing_count     |            0.0444 |
| host_n_listings        |            0.0373 |
| days_since_last_review |            0.0364 |
| city_id                |            0.0345 |
| rating_change_90       |            0.031  |
| available_090          |            0.0298 |
| host_is_superhost      |            0.0286 |
| city_n_listings        |            0.0282 |
| overall_rating         |            0.0257 |
| descrip_word_count     |            0.0233 |
| host_about_word_count  |            0.0227 |
| zip_n_listings         |            0.0218 |
| host_tenure_days       |            0.0209 |
| clean_rating           |            0.0204 |
| city_supply_growth_365 |            0.0197 |
| number_of_reviews      |            0.0189 |
