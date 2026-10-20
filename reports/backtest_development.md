# Backtest Summary: development

Built 2026-10-20 by `src/backtest.py` under quality policy `QP-2026-10-20.1`. 23 quarterly folds, 2017Q3–2023Q3. The shared holdout block (2023-Q4–2024-Q3) was **not** used.

Each fold trains on final, usable, eligible labels with `label_final_at` before the quarter starts, early-stops and calibrates on the latest 2 training quarters, and evaluates on eligible rows at that quarter's prediction dates. Host precision@K ranks unique hosts (host at *t*) by their riskiest listing; a hit is a host with ≥ 1 listing `absent_confirmed`. Scores are predictive associations, not causes.

**Variants** (`config/quality_policy.json`): `retain` is the primary analysis and keeps every outcome. `exclude` is the prespecified sensitivity analysis: it drops comparisons whose follow-up crosses a suspected source break and masks history features that cross it, only for decisions on/after the policy's effective date (2023-07-01). Both are reported regardless of which scores higher.

Best simple rule (highest mean AP, primary development folds): `rule:low_presence_365`.

## Mean over folds

| variant   | model                 |    ap |   auc |   host_p@100 |   host_p@500 |   host_p@1000 |
|:----------|:----------------------|------:|------:|-------------:|-------------:|--------------:|
| retain    | lgbm                  | 0.375 | 0.7   |        0.711 |        0.606 |         0.549 |
| retain    | lr                    | 0.346 | 0.675 |        0.572 |        0.521 |         0.488 |
| retain    | rule:low_presence_365 | 0.313 | 0.644 |        0.42  |        0.426 |         0.436 |
| exclude   | lgbm                  | 0.356 | 0.693 |        0.696 |        0.585 |         0.525 |
| exclude   | lr                    | 0.329 | 0.669 |        0.56  |        0.505 |         0.47  |
| exclude   | rule:low_presence_365 | 0.286 | 0.627 |        0.391 |        0.397 |         0.406 |

## Lift over the best rule

Fold metrics are serially dependent (outcomes follow up for ~9 months, so neighbouring folds overlap). Intervals use a moving-block bootstrap over consecutive folds (blocks of 4 quarters) and a Newey–West HAC standard error (lag 3). Both are approximate with this few folds.

| variant   | comparison                   | metric     |   mean_diff | folds_better   | block bootstrap (b=4)   | Newey–West (lag 3)   |
|:----------|:-----------------------------|:-----------|------------:|:---------------|:------------------------|:---------------------|
| retain    | lr − rule:low_presence_365   | ap         |       0.033 | 19/23          | [0.007, 0.050]          | [0.012, 0.054]       |
| retain    | lr − rule:low_presence_365   | host_p@500 |       0.094 | 18/23          | [0.033, 0.135]          | [0.043, 0.146]       |
| retain    | lgbm − rule:low_presence_365 | ap         |       0.062 | 19/23          | [0.035, 0.084]          | [0.038, 0.086]       |
| retain    | lgbm − rule:low_presence_365 | host_p@500 |       0.179 | 23/23          | [0.139, 0.208]          | [0.144, 0.214]       |
| exclude   | lr − rule:low_presence_365   | ap         |       0.043 | 19/22          | [0.008, 0.062]          | [0.014, 0.072]       |
| exclude   | lr − rule:low_presence_365   | host_p@500 |       0.109 | 18/22          | [0.031, 0.155]          | [0.040, 0.177]       |
| exclude   | lgbm − rule:low_presence_365 | ap         |       0.07  | 19/22          | [0.037, 0.095]          | [0.042, 0.099]       |
| exclude   | lgbm − rule:low_presence_365 | host_p@500 |       0.189 | 22/22          | [0.137, 0.223]          | [0.142, 0.235]       |

## Folds where the variants differ (LightGBM host P@500)

| quarter   |   exclude |   retain |   difference |
|:----------|----------:|---------:|-------------:|
| 2023Q3    |      0.48 |    0.602 |       -0.122 |

## Average precision by era

| variant   | era     |   lgbm |    lr |   rule:low_presence_365 |
|:----------|:--------|-------:|------:|------------------------:|
| exclude   | 2017–19 |  0.35  | 0.324 |                   0.275 |
| exclude   | 2020–21 |  0.371 | 0.335 |                   0.33  |
| exclude   | 2022–23 |  0.342 | 0.328 |                   0.224 |
| retain    | 2017–19 |  0.35  | 0.324 |                   0.275 |
| retain    | 2020–21 |  0.371 | 0.335 |                   0.33  |
| retain    | 2022–23 |  0.433 | 0.409 |                   0.363 |

## Calibration, primary variant (Platt on the validation quarters)

`gap` = mean predicted probability − observed rate in the evaluation quarter.

| model   |   brier |   mean_abs_gap |   worst_gap |
|:--------|--------:|---------------:|------------:|
| lgbm    |  0.1578 |         0.053  |     -0.2768 |
| lr      |  0.1609 |         0.0519 |     -0.295  |

## Per fold, primary variant

| quarter   |   n_train |   n_val |   n_masked_eval |   n_eval |   base_rate |   n_hosts |   host_base_rate |   lgbm_trees |   AP lr |   AP lgbm |   AP rule:low_presence_365 |   host P@500 lr |   host P@500 lgbm |   host P@500 rule:low_presence_365 |
|:----------|----------:|--------:|----------------:|---------:|------------:|----------:|-----------------:|-------------:|--------:|----------:|---------------------------:|----------------:|------------------:|-----------------------------------:|
| 2017Q3    |     11999 |   40613 |               0 |    29072 |       0.203 |     19765 |            0.222 |          103 |   0.318 |     0.336 |                      0.269 |           0.452 |             0.556 |                              0.374 |
| 2017Q4    |     30066 |   28997 |               0 |    34154 |       0.207 |     22536 |            0.235 |          134 |   0.32  |     0.371 |                      0.273 |           0.45  |             0.576 |                              0.336 |
| 2018Q1    |     54962 |   56318 |               0 |    35820 |       0.194 |     22948 |            0.23  |          103 |   0.315 |     0.373 |                      0.276 |           0.506 |             0.656 |                              0.48  |
| 2018Q2    |     83124 |   57365 |               0 |    36720 |       0.191 |     23205 |            0.222 |          297 |   0.31  |     0.347 |                      0.27  |           0.482 |             0.602 |                              0.388 |
| 2018Q3    |    111280 |   46945 |               0 |    38939 |       0.206 |     23994 |            0.231 |          310 |   0.341 |     0.325 |                      0.287 |           0.568 |             0.506 |                              0.42  |
| 2018Q4    |    140489 |   63226 |               0 |    40183 |       0.201 |     24479 |            0.224 |           51 |   0.35  |     0.35  |                      0.3   |           0.6   |             0.534 |                              0.434 |
| 2019Q1    |    169561 |   66202 |               0 |    39926 |       0.182 |     23814 |            0.204 |          701 |   0.302 |     0.306 |                      0.274 |           0.516 |             0.596 |                              0.402 |
| 2019Q2    |    203715 |   72540 |               0 |    41125 |       0.193 |     24242 |            0.22  |          571 |   0.323 |     0.345 |                      0.258 |           0.524 |             0.602 |                              0.42  |
| 2019Q3    |    239535 |   71306 |               0 |    42771 |       0.215 |     24926 |            0.245 |          142 |   0.342 |     0.373 |                      0.277 |           0.552 |             0.622 |                              0.416 |
| 2019Q4    |    276255 |   79122 |               0 |    42708 |       0.212 |     24352 |            0.238 |           77 |   0.323 |     0.377 |                      0.27  |           0.518 |             0.62  |                              0.47  |
| 2020Q1    |    315194 |   80109 |               0 |    42059 |       0.246 |     23450 |            0.248 |           71 |   0.318 |     0.353 |                      0.304 |           0.47  |             0.52  |                              0.482 |
| 2020Q2    |    355377 |   81051 |               0 |    40559 |       0.337 |     22380 |            0.344 |          240 |   0.415 |     0.488 |                      0.383 |           0.548 |             0.746 |                              0.61  |
| 2020Q3    |    395303 |   83896 |               0 |    26791 |       0.232 |     14509 |            0.248 |          499 |   0.317 |     0.342 |                      0.276 |           0.448 |             0.57  |                              0.506 |
| 2020Q4    |    436428 |   85479 |               0 |    30708 |       0.227 |     16429 |            0.219 |          590 |   0.305 |     0.32  |                      0.394 |           0.448 |             0.628 |                              0.472 |
| 2021Q1    |    479199 |   84767 |               0 |    30141 |       0.216 |     15794 |            0.204 |           97 |   0.328 |     0.368 |                      0.371 |           0.52  |             0.648 |                              0.488 |
| 2021Q2    |    521907 |   78753 |               0 |    28132 |       0.199 |     14378 |            0.178 |           34 |   0.33  |     0.336 |                      0.352 |           0.486 |             0.614 |                              0.372 |
| 2021Q3    |    563966 |   67350 |               0 |    29810 |       0.179 |     15319 |            0.164 |           48 |   0.345 |     0.384 |                      0.289 |           0.484 |             0.516 |                              0.292 |
| 2021Q4    |    604525 |   43606 |               0 |    32205 |       0.162 |     16812 |            0.161 |           54 |   0.318 |     0.377 |                      0.27  |           0.506 |             0.602 |                              0.338 |
| 2022Q1    |    631316 |   57740 |               0 |    33743 |       0.142 |     17607 |            0.147 |           48 |   0.313 |     0.352 |                      0.246 |           0.476 |             0.522 |                              0.324 |
| 2022Q2    |    662024 |   58273 |               0 |    37587 |       0.153 |     19317 |            0.171 |         2000 |   0.389 |     0.446 |                      0.273 |           0.51  |             0.638 |                              0.298 |
| 2023Q1    |    750107 |   65948 |               0 |    38887 |       0.438 |     19234 |            0.447 |          580 |   0.731 |     0.738 |                      0.862 |           0.848 |             0.938 |                              0.918 |
| 2023Q2    |    782312 |   71330 |               0 |    46747 |       0.162 |     23314 |            0.18  |         1296 |   0.296 |     0.289 |                      0.201 |           0.512 |             0.518 |                              0.23  |
| 2023Q3    |    782312 |   71330 |               0 |    46997 |       0.177 |     23543 |            0.204 |         1296 |   0.318 |     0.337 |                      0.234 |           0.554 |             0.602 |                              0.338 |

## LightGBM: top 20 features by gain share (primary, mean over folds)

| feature                  |   mean_gain_share |
|:-------------------------|------------------:|
| available_365            |            0.0802 |
| presence_rate_365        |            0.0791 |
| listing_type             |            0.0529 |
| avail365_change_90       |            0.0484 |
| host_listing_count       |            0.0433 |
| host_n_listings          |            0.0379 |
| days_since_last_review   |            0.0365 |
| city_id                  |            0.0351 |
| available_090            |            0.0342 |
| rating_change_90         |            0.0306 |
| host_is_superhost        |            0.0296 |
| city_n_listings          |            0.0283 |
| overall_rating           |            0.0269 |
| descrip_word_count       |            0.0229 |
| host_about_word_count    |            0.0217 |
| neighbourhood_n_listings |            0.0216 |
| clean_rating             |            0.0211 |
| host_tenure_days         |            0.0204 |
| number_of_reviews        |            0.0183 |
| days_since_first_review  |            0.0181 |
