# Business Evaluation: development

Built 2026-10-20 by `src/business.py` from `dev_predictions.parquet` under the frozen analysis (`config/analysis_freeze.json`). Model scores are LightGBM; the rule is `rule:low_presence_365`. K = 500 unique hosts per quarter unless noted. See `docs/business_spec.md` for definitions.

**Value proxy V_i:** 12-month gross booking value at the asking price, estimated from reviews (scenarios for the share of stays that leave a review: 0.30 / 0.50 / 0.72). Host-side value, not realized revenue and not Airbnb revenue. Missing prices are filled from neighbourhood × room medians (1.4% of rows, primary variant).

## 1. Targeting value

Host precision@500 per quarter (share of contacted hosts with ≥ 1 eligible listing `absent_confirmed`).

| variant   | quarter   |   best rule |   random (expected) |   risk (max p) |   risk × value (Σ p·V) |   value only (Σ V) |
|:----------|:----------|------------:|--------------------:|---------------:|-----------------------:|-------------------:|
| exclude   | 2017Q3    |       0.374 |               0.222 |          0.556 |                  0.396 |              0.336 |
| exclude   | 2017Q4    |       0.336 |               0.235 |          0.576 |                  0.424 |              0.336 |
| exclude   | 2018Q1    |       0.48  |               0.23  |          0.656 |                  0.428 |              0.334 |
| exclude   | 2018Q2    |       0.388 |               0.222 |          0.602 |                  0.478 |              0.392 |
| exclude   | 2018Q3    |       0.42  |               0.231 |          0.506 |                  0.462 |              0.4   |
| exclude   | 2018Q4    |       0.434 |               0.224 |          0.534 |                  0.474 |              0.4   |
| exclude   | 2019Q1    |       0.402 |               0.204 |          0.596 |                  0.486 |              0.364 |
| exclude   | 2019Q2    |       0.42  |               0.22  |          0.602 |                  0.548 |              0.418 |
| exclude   | 2019Q3    |       0.416 |               0.245 |          0.622 |                  0.568 |              0.496 |
| exclude   | 2019Q4    |       0.47  |               0.238 |          0.62  |                  0.606 |              0.514 |
| exclude   | 2020Q1    |       0.482 |               0.248 |          0.52  |                  0.58  |              0.524 |
| exclude   | 2020Q2    |       0.61  |               0.344 |          0.746 |                  0.65  |              0.584 |
| exclude   | 2020Q3    |       0.506 |               0.248 |          0.57  |                  0.52  |              0.404 |
| exclude   | 2020Q4    |       0.472 |               0.219 |          0.628 |                  0.53  |              0.444 |
| exclude   | 2021Q1    |       0.488 |               0.204 |          0.648 |                  0.506 |              0.442 |
| exclude   | 2021Q2    |       0.372 |               0.178 |          0.614 |                  0.458 |              0.42  |
| exclude   | 2021Q3    |       0.292 |               0.164 |          0.516 |                  0.482 |              0.43  |
| exclude   | 2021Q4    |       0.338 |               0.161 |          0.602 |                  0.52  |              0.424 |
| exclude   | 2022Q1    |       0.324 |               0.147 |          0.522 |                  0.476 |              0.424 |
| exclude   | 2022Q2    |       0.298 |               0.171 |          0.638 |                  0.562 |              0.452 |
| exclude   | 2023Q2    |       0.23  |               0.18  |          0.518 |                  0.546 |              0.42  |
| exclude   | 2023Q3    |       0.172 |               0.204 |          0.48  |                  0.61  |              0.546 |
| retain    | 2017Q3    |       0.374 |               0.222 |          0.556 |                  0.396 |              0.336 |
| retain    | 2017Q4    |       0.336 |               0.235 |          0.576 |                  0.424 |              0.336 |
| retain    | 2018Q1    |       0.48  |               0.23  |          0.656 |                  0.428 |              0.334 |
| retain    | 2018Q2    |       0.388 |               0.222 |          0.602 |                  0.478 |              0.392 |
| retain    | 2018Q3    |       0.42  |               0.231 |          0.506 |                  0.462 |              0.4   |
| retain    | 2018Q4    |       0.434 |               0.224 |          0.534 |                  0.474 |              0.4   |
| retain    | 2019Q1    |       0.402 |               0.204 |          0.596 |                  0.486 |              0.364 |
| retain    | 2019Q2    |       0.42  |               0.22  |          0.602 |                  0.548 |              0.418 |
| retain    | 2019Q3    |       0.416 |               0.245 |          0.622 |                  0.568 |              0.496 |
| retain    | 2019Q4    |       0.47  |               0.238 |          0.62  |                  0.606 |              0.514 |
| retain    | 2020Q1    |       0.482 |               0.248 |          0.52  |                  0.58  |              0.524 |
| retain    | 2020Q2    |       0.61  |               0.344 |          0.746 |                  0.65  |              0.584 |
| retain    | 2020Q3    |       0.506 |               0.248 |          0.57  |                  0.52  |              0.404 |
| retain    | 2020Q4    |       0.472 |               0.219 |          0.628 |                  0.53  |              0.444 |
| retain    | 2021Q1    |       0.488 |               0.204 |          0.648 |                  0.506 |              0.442 |
| retain    | 2021Q2    |       0.372 |               0.178 |          0.614 |                  0.458 |              0.42  |
| retain    | 2021Q3    |       0.292 |               0.164 |          0.516 |                  0.482 |              0.43  |
| retain    | 2021Q4    |       0.338 |               0.161 |          0.602 |                  0.52  |              0.424 |
| retain    | 2022Q1    |       0.324 |               0.147 |          0.522 |                  0.476 |              0.424 |
| retain    | 2022Q2    |       0.298 |               0.171 |          0.638 |                  0.562 |              0.452 |
| retain    | 2023Q1    |       0.918 |               0.447 |          0.938 |                  0.824 |              0.76  |
| retain    | 2023Q2    |       0.23  |               0.18  |          0.518 |                  0.546 |              0.42  |
| retain    | 2023Q3    |       0.338 |               0.204 |          0.602 |                  0.676 |              0.546 |

### Mean over quarters, central value scenario

| variant   |    k | strategy             |   precision |   captured $M |   captured_share |   listings_covered |
|:----------|-----:|:---------------------|------------:|--------------:|-----------------:|-------------------:|
| exclude   |  100 | best rule            |       0.391 |          1.36 |            0.012 |            479.591 |
| exclude   |  100 | random (expected)    |       0.215 |          0.5  |            0.005 |            nan     |
| exclude   |  100 | risk (max p)         |       0.696 |         13.99 |            0.08  |           1883.36  |
| exclude   |  100 | risk × value (Σ p·V) |       0.733 |         31.06 |            0.242 |           4014.23  |
| exclude   |  100 | value only (Σ V)     |       0.67  |         29.65 |            0.225 |           3959.05  |
| exclude   |  500 | best rule            |       0.397 |         15.8  |            0.102 |           2481.23  |
| exclude   |  500 | random (expected)    |       0.215 |          2.49 |            0.025 |            nan     |
| exclude   |  500 | risk (max p)         |       0.585 |         22.42 |            0.162 |           3807.64  |
| exclude   |  500 | risk × value (Σ p·V) |       0.514 |         47.33 |            0.413 |           7414.82  |
| exclude   |  500 | value only (Σ V)     |       0.432 |         44.88 |            0.384 |           7358.09  |
| exclude   | 1000 | best rule            |       0.406 |         22.82 |            0.166 |           4828.45  |
| exclude   | 1000 | random (expected)    |       0.215 |          4.99 |            0.05  |            nan     |
| exclude   | 1000 | risk (max p)         |       0.525 |         27.93 |            0.212 |           5535.64  |
| exclude   | 1000 | risk × value (Σ p·V) |       0.421 |         56.2  |            0.508 |           9306.14  |
| exclude   | 1000 | value only (Σ V)     |       0.342 |         53.09 |            0.471 |           9344.64  |
| retain    |  100 | best rule            |       0.42  |          1.41 |            0.012 |            493.87  |
| retain    |  100 | random (expected)    |       0.225 |          0.53 |            0.005 |            nan     |
| retain    |  100 | risk (max p)         |       0.711 |         13.57 |            0.077 |           1884.39  |
| retain    |  100 | risk × value (Σ p·V) |       0.746 |         31.62 |            0.24  |           4045.7   |
| retain    |  100 | value only (Σ V)     |       0.679 |         30.1  |            0.223 |           3998.17  |
| retain    |  500 | best rule            |       0.426 |         16.22 |            0.103 |           2586.57  |
| retain    |  500 | random (expected)    |       0.225 |          2.64 |            0.025 |            nan     |
| retain    |  500 | risk (max p)         |       0.606 |         22.01 |            0.157 |           3812.52  |
| retain    |  500 | risk × value (Σ p·V) |       0.53  |         48.97 |            0.411 |           7500.52  |
| retain    |  500 | value only (Σ V)     |       0.446 |         46.46 |            0.382 |           7455.35  |
| retain    | 1000 | best rule            |       0.436 |         23.82 |            0.168 |           5024     |
| retain    | 1000 | random (expected)    |       0.225 |          5.28 |            0.05  |            nan     |
| retain    | 1000 | risk (max p)         |       0.549 |         28.03 |            0.209 |           5568.35  |
| retain    | 1000 | risk × value (Σ p·V) |       0.439 |         58.5  |            0.507 |           9399.78  |
| retain    | 1000 | value only (Σ V)     |       0.355 |         55.28 |            0.47  |           9467.61  |

### Lift over the rule, host precision@500 (risk ranking vs `rule:low_presence_365`)

| variant   |   mean difference | mean relative   | quarters better   | block bootstrap 95%   |
|:----------|------------------:|:----------------|:------------------|:----------------------|
| exclude   |             0.189 | +56.2%          | 22/22             | [0.137, 0.223]        |
| retain    |             0.179 | +49.5%          | 23/23             | [0.139, 0.208]        |

### By host portfolio size (eligible listings in the quarter), primary variant

`contacted_share`: share of the contacted hosts in each size group. `captured_value_share`: share of the captured disappearing value coming from that group.

| bucket   |   hosts |   base_rate |   contacted |   precision |   contacted_share |   lift |   captured_value_share | ranking              |
|:---------|--------:|------------:|------------:|------------:|------------------:|-------:|-----------------------:|:---------------------|
| 1        |  370381 |       0.2   |        6568 |       0.548 |             0.571 |  2.745 |                  0.016 | risk (max p)         |
| 2–5      |   91571 |       0.29  |        2712 |       0.594 |             0.236 |  2.051 |                  0.044 | risk (max p)         |
| 6–20     |   11855 |       0.501 |        1286 |       0.728 |             0.112 |  1.454 |                  0.11  | risk (max p)         |
| 21+      |    2540 |       0.806 |         934 |       0.878 |             0.081 |  1.09  |                  0.83  | risk (max p)         |
| 1        |  370381 |       0.2   |        1319 |       0.301 |             0.115 |  1.508 |                  0.049 | risk × value (Σ p·V) |
| 2–5      |   91571 |       0.29  |        3476 |       0.409 |             0.302 |  1.411 |                  0.132 | risk × value (Σ p·V) |
| 6–20     |   11855 |       0.501 |        4594 |       0.554 |             0.399 |  1.107 |                  0.229 | risk × value (Σ p·V) |
| 21+      |    2540 |       0.806 |        2111 |       0.823 |             0.184 |  1.022 |                  0.59  | risk × value (Σ p·V) |

## 2. Value exposure

Estimated value associated with correctly flagged disappearances: the summed V_i of `absent_confirmed` listings held by the 500 contacted hosts, per quarter (mean over quarters). `captured_share` is that value as a share of all disappearing value among eligible listings that quarter. Host exposure for ranking is Σ p_i·V_i over the host's listings, never max p × portfolio value.

| variant   | value_scenario   | strategy             |   captured_share |   captured ($M / quarter) |
|:----------|:-----------------|:---------------------|-----------------:|--------------------------:|
| exclude   | central          | best rule            |            0.102 |                     15.8  |
| exclude   | central          | random (expected)    |            0.025 |                      2.49 |
| exclude   | central          | risk (max p)         |            0.162 |                     22.42 |
| exclude   | central          | risk × value (Σ p·V) |            0.413 |                     47.33 |
| exclude   | central          | value only (Σ V)     |            0.384 |                     44.88 |
| exclude   | high_value       | best rule            |            0.103 |                     21.04 |
| exclude   | high_value       | random (expected)    |            0.025 |                      3.26 |
| exclude   | high_value       | risk (max p)         |            0.168 |                     30.34 |
| exclude   | high_value       | risk × value (Σ p·V) |            0.415 |                     62.08 |
| exclude   | high_value       | value only (Σ V)     |            0.382 |                     58.26 |
| exclude   | low_value        | best rule            |            0.1   |                     11.78 |
| exclude   | low_value        | random (expected)    |            0.025 |                      1.92 |
| exclude   | low_value        | risk (max p)         |            0.158 |                     16.76 |
| exclude   | low_value        | risk × value (Σ p·V) |            0.415 |                     36.58 |
| exclude   | low_value        | value only (Σ V)     |            0.385 |                     34.65 |
| retain    | central          | best rule            |            0.103 |                     16.22 |
| retain    | central          | random (expected)    |            0.025 |                      2.64 |
| retain    | central          | risk (max p)         |            0.157 |                     22.01 |
| retain    | central          | risk × value (Σ p·V) |            0.411 |                     48.97 |
| retain    | central          | value only (Σ V)     |            0.382 |                     46.46 |
| retain    | high_value       | best rule            |            0.104 |                     21.58 |
| retain    | high_value       | random (expected)    |            0.025 |                      3.46 |
| retain    | high_value       | risk (max p)         |            0.163 |                     29.8  |
| retain    | high_value       | risk × value (Σ p·V) |            0.414 |                     64.31 |
| retain    | high_value       | value only (Σ V)     |            0.381 |                     60.43 |
| retain    | low_value        | best rule            |            0.101 |                     12.09 |
| retain    | low_value        | random (expected)    |            0.025 |                      2.03 |
| retain    | low_value        | risk (max p)         |            0.153 |                     16.45 |
| retain    | low_value        | risk × value (Σ p·V) |            0.414 |                     37.79 |
| retain    | low_value        | value only (Σ V)     |            0.384 |                     35.82 |

### Does risk add anything over value alone?

Quarter-by-quarter difference, risk × value minus value only, at K = 500 (captured in $M per quarter). Value per host is heavy-tailed, so both rankings favour large portfolios; the comparison shows how much the risk score adds on top.

| variant   | value_scenario   | metric    |   mean difference | mean relative   | quarters better   | block bootstrap 95%   |
|:----------|:-----------------|:----------|------------------:|:----------------|:------------------|:----------------------|
| exclude   | central          | precision |             0.082 | +19.6%          | 22/22             | [0.071, 0.091]        |
| exclude   | central          | captured  |             2.447 | +8.4%           | 22/22             | [1.793, 2.966]        |
| exclude   | high_value       | precision |             0.087 | +20.9%          | 22/22             | [0.074, 0.100]        |
| exclude   | high_value       | captured  |             3.822 | +9.7%           | 22/22             | [2.801, 4.813]        |
| exclude   | low_value        | precision |             0.083 | +19.9%          | 22/22             | [0.072, 0.091]        |
| exclude   | low_value        | captured  |             1.929 | +8.7%           | 22/22             | [1.486, 2.285]        |
| retain    | central          | precision |             0.084 | +19.7%          | 23/23             | [0.072, 0.093]        |
| retain    | central          | captured  |             2.512 | +8.4%           | 23/23             | [1.834, 3.031]        |
| retain    | high_value       | precision |             0.09  | +21.1%          | 23/23             | [0.076, 0.102]        |
| retain    | high_value       | captured  |             3.874 | +9.6%           | 23/23             | [2.875, 4.802]        |
| retain    | low_value        | precision |             0.085 | +20.0%          | 23/23             | [0.073, 0.092]        |
| retain    | low_value        | captured  |             1.975 | +8.6%           | 23/23             | [1.513, 2.307]        |

## 3. Intervention scenarios (central value scenario)

Net benefit per quarter ($ thousands) = prevention rate × take rate × captured value − cost per contact × K. The prevention rate is the share of **otherwise-occurring** disappearances that contact prevents, and is unknown until tested. The take rate converts host booking value into platform revenue. Break-even is the cost per contact at which net benefit is zero.

| strategy             |   prevention_rate |   take_rate |   breakeven_cost_per_contact |   net @ $25 |   net @ $100 |   net @ $250 |
|:---------------------|------------------:|------------:|-----------------------------:|------------:|-------------:|-------------:|
| risk × value (Σ p·V) |              0.05 |        0.1  |                       489.73 |       232.4 |        194.9 |        119.9 |
| risk × value (Σ p·V) |              0.05 |        0.15 |                       734.59 |       354.8 |        317.3 |        242.3 |
| risk × value (Σ p·V) |              0.1  |        0.1  |                       979.45 |       477.2 |        439.7 |        364.7 |
| risk × value (Σ p·V) |              0.1  |        0.15 |                      1469.18 |       722.1 |        684.6 |        609.6 |
| risk × value (Σ p·V) |              0.2  |        0.1  |                      1958.9  |       967   |        929.5 |        854.5 |
| risk × value (Σ p·V) |              0.2  |        0.15 |                      2938.35 |      1456.7 |       1419.2 |       1344.2 |
| risk (max p)         |              0.05 |        0.1  |                       220.06 |        97.5 |         60   |        -15   |
| risk (max p)         |              0.05 |        0.15 |                       330.08 |       152.5 |        115   |         40   |
| risk (max p)         |              0.1  |        0.1  |                       440.11 |       207.6 |        170.1 |         95.1 |
| risk (max p)         |              0.1  |        0.15 |                       660.17 |       317.6 |        280.1 |        205.1 |
| risk (max p)         |              0.2  |        0.1  |                       880.22 |       427.6 |        390.1 |        315.1 |
| risk (max p)         |              0.2  |        0.15 |                      1320.34 |       647.7 |        610.2 |        535.2 |
| value only (Σ V)     |              0.05 |        0.1  |                       464.61 |       219.8 |        182.3 |        107.3 |
| value only (Σ V)     |              0.05 |        0.15 |                       696.92 |       336   |        298.5 |        223.5 |
| value only (Σ V)     |              0.1  |        0.1  |                       929.22 |       452.1 |        414.6 |        339.6 |
| value only (Σ V)     |              0.1  |        0.15 |                      1393.83 |       684.4 |        646.9 |        571.9 |
| value only (Σ V)     |              0.2  |        0.1  |                      1858.44 |       916.7 |        879.2 |        804.2 |
| value only (Σ V)     |              0.2  |        0.15 |                      2787.66 |      1381.3 |       1343.8 |       1268.8 |
| best rule            |              0.05 |        0.1  |                       162.16 |        68.6 |         31.1 |        -43.9 |
| best rule            |              0.05 |        0.15 |                       243.24 |       109.1 |         71.6 |         -3.4 |
| best rule            |              0.1  |        0.1  |                       324.31 |       149.7 |        112.2 |         37.2 |
| best rule            |              0.1  |        0.15 |                       486.47 |       230.7 |        193.2 |        118.2 |
| best rule            |              0.2  |        0.1  |                       648.63 |       311.8 |        274.3 |        199.3 |
| best rule            |              0.2  |        0.15 |                       972.94 |       474   |        436.5 |        361.5 |
| random (expected)    |              0.05 |        0.1  |                        26.42 |         0.7 |        -36.8 |       -111.8 |
| random (expected)    |              0.05 |        0.15 |                        39.63 |         7.3 |        -30.2 |       -105.2 |
| random (expected)    |              0.1  |        0.1  |                        52.84 |        13.9 |        -23.6 |        -98.6 |
| random (expected)    |              0.1  |        0.15 |                        79.27 |        27.1 |        -10.4 |        -85.4 |
| random (expected)    |              0.2  |        0.1  |                       105.69 |        40.3 |          2.8 |        -72.2 |
| random (expected)    |              0.2  |        0.15 |                       158.53 |        66.8 |         29.3 |        -45.7 |

Sensitivity variant (`exclude`):

| strategy             |   prevention_rate |   take_rate |   breakeven_cost_per_contact |   net @ $25 |   net @ $100 |   net @ $250 |
|:---------------------|------------------:|------------:|-----------------------------:|------------:|-------------:|-------------:|
| risk × value (Σ p·V) |              0.05 |        0.1  |                       473.28 |       224.1 |        186.6 |        111.6 |
| risk × value (Σ p·V) |              0.05 |        0.15 |                       709.92 |       342.5 |        305   |        230   |
| risk × value (Σ p·V) |              0.1  |        0.1  |                       946.56 |       460.8 |        423.3 |        348.3 |
| risk × value (Σ p·V) |              0.1  |        0.15 |                      1419.84 |       697.4 |        659.9 |        584.9 |
| risk × value (Σ p·V) |              0.2  |        0.1  |                      1893.12 |       934.1 |        896.6 |        821.6 |
| risk × value (Σ p·V) |              0.2  |        0.15 |                      2839.68 |      1407.3 |       1369.8 |       1294.8 |
| risk (max p)         |              0.05 |        0.1  |                       224.19 |        99.6 |         62.1 |        -12.9 |
| risk (max p)         |              0.05 |        0.15 |                       336.29 |       155.6 |        118.1 |         43.1 |
| risk (max p)         |              0.1  |        0.1  |                       448.38 |       211.7 |        174.2 |         99.2 |
| risk (max p)         |              0.1  |        0.15 |                       672.57 |       323.8 |        286.3 |        211.3 |
| risk (max p)         |              0.2  |        0.1  |                       896.76 |       435.9 |        398.4 |        323.4 |
| risk (max p)         |              0.2  |        0.15 |                      1345.15 |       660.1 |        622.6 |        547.6 |
| value only (Σ V)     |              0.05 |        0.1  |                       448.81 |       211.9 |        174.4 |         99.4 |
| value only (Σ V)     |              0.05 |        0.15 |                       673.21 |       324.1 |        286.6 |        211.6 |
| value only (Σ V)     |              0.1  |        0.1  |                       897.61 |       436.3 |        398.8 |        323.8 |
| value only (Σ V)     |              0.1  |        0.15 |                      1346.42 |       660.7 |        623.2 |        548.2 |
| value only (Σ V)     |              0.2  |        0.1  |                      1795.23 |       885.1 |        847.6 |        772.6 |
| value only (Σ V)     |              0.2  |        0.15 |                      2692.84 |      1333.9 |       1296.4 |       1221.4 |
| best rule            |              0.05 |        0.1  |                       157.98 |        66.5 |         29   |        -46   |
| best rule            |              0.05 |        0.15 |                       236.96 |       106   |         68.5 |         -6.5 |
| best rule            |              0.1  |        0.1  |                       315.95 |       145.5 |        108   |         33   |
| best rule            |              0.1  |        0.15 |                       473.93 |       224.5 |        187   |        112   |
| best rule            |              0.2  |        0.1  |                       631.9  |       303.5 |        266   |        191   |
| best rule            |              0.2  |        0.15 |                       947.85 |       461.4 |        423.9 |        348.9 |
| random (expected)    |              0.05 |        0.1  |                        24.93 |        -0   |        -37.5 |       -112.5 |
| random (expected)    |              0.05 |        0.15 |                        37.4  |         6.2 |        -31.3 |       -106.3 |
| random (expected)    |              0.1  |        0.1  |                        49.86 |        12.4 |        -25.1 |       -100.1 |
| random (expected)    |              0.1  |        0.15 |                        74.79 |        24.9 |        -12.6 |        -87.6 |
| random (expected)    |              0.2  |        0.1  |                        99.72 |        37.4 |         -0.1 |        -75.1 |
| random (expected)    |              0.2  |        0.15 |                       149.58 |        62.3 |         24.8 |        -50.2 |

## Experiment sizing (host-randomized)

Hosts needed per arm to detect a relative reduction in the share of contacted hosts with a disappearance (two-sided α = 0.05, power 0.8, normal approximation, ignoring clustering across quarters).

| relative reduction in hosts with a disappearance   |   control hit rate (top-ranked hosts) |   hosts per arm |   quarters at 500 treated + 500 control |
|:---------------------------------------------------|--------------------------------------:|----------------:|----------------------------------------:|
| 5%                                                 |                                 0.606 |            4137 |                                       9 |
| 10%                                                |                                 0.606 |            1045 |                                       3 |
| 20%                                                |                                 0.606 |             265 |                                       1 |
