# Backtest Summary: holdout

Built 2026-10-20 by `src/backtest.py` under quality policy `QP-2026-10-20.1`. 4 quarterly folds, 2023Q4–2024Q3. Shared holdout block; the rule baseline was fixed from the development folds.

Each fold trains on final, usable, eligible labels with `label_final_at` before the quarter starts, early-stops and calibrates on the latest 2 training quarters, and evaluates on eligible rows at that quarter's prediction dates. Host precision@K ranks unique hosts (host at *t*) by their riskiest listing; a hit is a host with ≥ 1 listing `absent_confirmed`. Scores are predictive associations, not causes.

**Variants** (`config/quality_policy.json`): `retain` is the primary analysis and keeps every outcome. `exclude` is the prespecified sensitivity analysis: it drops comparisons whose follow-up crosses a suspected source break and masks history features that cross it, only for decisions on/after the policy's effective date (2023-07-01). Both are reported regardless of which scores higher.

Best simple rule (highest mean AP, primary development folds): `rule:low_presence_365`.

## Mean over folds

| variant   | model                 |    ap |   auc |   host_p@100 |   host_p@500 |   host_p@1000 |
|:----------|:----------------------|------:|------:|-------------:|-------------:|--------------:|
| retain    | lgbm                  | 0.29  | 0.711 |        0.635 |        0.511 |         0.476 |
| retain    | lr                    | 0.276 | 0.7   |        0.49  |        0.508 |         0.465 |
| retain    | rule:low_presence_365 | 0.212 | 0.626 |        0.36  |        0.328 |         0.326 |
| exclude   | lgbm                  | 0.282 | 0.693 |        0.65  |        0.516 |         0.461 |
| exclude   | lr                    | 0.27  | 0.695 |        0.505 |        0.5   |         0.462 |
| exclude   | rule:low_presence_365 | 0.193 | 0.591 |        0.312 |        0.284 |         0.28  |

## Lift over the best rule

Four holdout quarters: each quarter's difference is shown, and no intervals are computed.

| variant   | comparison                   | metric     |   mean_diff | folds_better   |   2023Q4 |   2024Q1 |   2024Q2 |   2024Q3 |
|:----------|:-----------------------------|:-----------|------------:|:---------------|---------:|---------:|---------:|---------:|
| retain    | lr − rule:low_presence_365   | ap         |       0.064 | 4/4            |    0.059 |    0.065 |    0.069 |    0.061 |
| retain    | lr − rule:low_presence_365   | host_p@500 |       0.181 | 4/4            |    0.162 |    0.18  |    0.18  |    0.202 |
| retain    | lgbm − rule:low_presence_365 | ap         |       0.077 | 4/4            |    0.075 |    0.077 |    0.087 |    0.07  |
| retain    | lgbm − rule:low_presence_365 | host_p@500 |       0.184 | 4/4            |    0.208 |    0.178 |    0.194 |    0.156 |
| exclude   | lr − rule:low_presence_365   | ap         |       0.077 | 4/4            |    0.112 |    0.065 |    0.07  |    0.062 |
| exclude   | lr − rule:low_presence_365   | host_p@500 |       0.216 | 4/4            |    0.32  |    0.174 |    0.184 |    0.186 |
| exclude   | lgbm − rule:low_presence_365 | ap         |       0.088 | 4/4            |    0.062 |    0.098 |    0.099 |    0.095 |
| exclude   | lgbm − rule:low_presence_365 | host_p@500 |       0.232 | 4/4            |    0.216 |    0.216 |    0.276 |    0.222 |

## Folds where the variants differ (LightGBM host P@500)

| quarter   |   exclude |   retain |   difference |
|:----------|----------:|---------:|-------------:|
| 2023Q4    |     0.414 |    0.582 |       -0.168 |
| 2024Q1    |     0.54  |    0.502 |        0.038 |
| 2024Q2    |     0.584 |    0.502 |        0.082 |
| 2024Q3    |     0.526 |    0.46  |        0.066 |

## Average precision by era

| variant   | era     |   lgbm |    lr |   rule:low_presence_365 |
|:----------|:--------|-------:|------:|------------------------:|
| exclude   | 2022–23 |  0.282 | 0.27  |                   0.193 |
| retain    | 2022–23 |  0.29  | 0.276 |                   0.212 |

## Calibration, primary variant (Platt on the validation quarters)

`gap` = mean predicted probability − observed rate in the evaluation quarter.

| model   |   brier |   mean_abs_gap |   worst_gap |
|:--------|--------:|---------------:|------------:|
| lgbm    |  0.1375 |         0.1053 |      0.1392 |
| lr      |  0.1527 |         0.1497 |      0.2273 |

## Per fold, primary variant

| quarter   |   n_train |   n_val |   n_masked_eval |   n_eval |   base_rate |   n_hosts |   host_base_rate |   lgbm_trees |   AP lr |   AP lgbm |   AP rule:low_presence_365 |   host P@500 lr |   host P@500 lgbm |   host P@500 rule:low_presence_365 |
|:----------|----------:|--------:|----------------:|---------:|------------:|----------:|-----------------:|-------------:|--------:|----------:|---------------------------:|----------------:|------------------:|-----------------------------------:|
| 2023Q4    |    782312 |   71330 |               0 |    46795 |       0.179 |     23426 |            0.204 |         1296 |   0.314 |     0.33  |                      0.255 |           0.536 |             0.582 |                              0.374 |
| 2024Q1    |    816055 |   76474 |               0 |    43587 |       0.147 |     22207 |            0.167 |           57 |   0.278 |     0.29  |                      0.213 |           0.504 |             0.502 |                              0.324 |
| 2024Q2    |    816055 |   76474 |               0 |    43718 |       0.138 |     22273 |            0.157 |           57 |   0.259 |     0.277 |                      0.189 |           0.488 |             0.502 |                              0.308 |
| 2024Q3    |    853642 |   85634 |               0 |    44433 |       0.136 |     22595 |            0.157 |           31 |   0.252 |     0.261 |                      0.191 |           0.506 |             0.46  |                              0.304 |

## LightGBM: top 20 features by gain share (primary, mean over folds)

| feature                 |   mean_gain_share |
|:------------------------|------------------:|
| listing_type            |            0.1214 |
| overall_rating          |            0.1004 |
| available_365           |            0.091  |
| presence_rate_365       |            0.0725 |
| host_is_superhost       |            0.0499 |
| rating_change_90        |            0.0482 |
| host_listing_count      |            0.0475 |
| days_since_last_review  |            0.0376 |
| avail365_change_90      |            0.0328 |
| host_n_listings         |            0.0328 |
| city_id                 |            0.0301 |
| available_090           |            0.0285 |
| city_n_listings         |            0.0265 |
| clean_rating            |            0.0252 |
| city_supply_growth_365  |            0.0211 |
| min_night               |            0.0182 |
| host_tenure_days        |            0.0179 |
| host_listings_change_90 |            0.0147 |
| lag365_days             |            0.0141 |
| room_type               |            0.0127 |
