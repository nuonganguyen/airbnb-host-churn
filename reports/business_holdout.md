# Business Evaluation: holdout

Built 2026-10-20 by `src/business.py` from `holdout_predictions.parquet` under the frozen analysis (`config/analysis_freeze.json`). Model scores are LightGBM; the rule is `rule:low_presence_365`. K = 500 unique hosts per quarter unless noted. See `docs/business_spec.md` for definitions.

**Value proxy V_i:** 12-month gross booking value at the asking price, estimated from reviews (scenarios for the share of stays that leave a review: 0.30 / 0.50 / 0.72). Host-side value, not realized revenue and not Airbnb revenue. Missing prices are filled from neighbourhood × room medians (7.3% of rows, primary variant).

## 1. Targeting value

Host precision@500 per quarter (share of contacted hosts with ≥ 1 eligible listing `absent_confirmed`).

| variant   | quarter   |   best rule |   random (expected) |   risk (max p) |   risk × value (Σ p·V) |   value only (Σ V) |
|:----------|:----------|------------:|--------------------:|---------------:|-----------------------:|-------------------:|
| exclude   | 2023Q4    |       0.198 |               0.204 |          0.414 |                  0.546 |              0.524 |
| exclude   | 2024Q1    |       0.324 |               0.167 |          0.54  |                  0.622 |              0.492 |
| exclude   | 2024Q2    |       0.308 |               0.157 |          0.584 |                  0.644 |              0.536 |
| exclude   | 2024Q3    |       0.304 |               0.157 |          0.526 |                  0.662 |              0.53  |
| retain    | 2023Q4    |       0.374 |               0.204 |          0.582 |                  0.57  |              0.524 |
| retain    | 2024Q1    |       0.324 |               0.167 |          0.502 |                  0.602 |              0.492 |
| retain    | 2024Q2    |       0.308 |               0.157 |          0.502 |                  0.654 |              0.536 |
| retain    | 2024Q3    |       0.304 |               0.157 |          0.46  |                  0.624 |              0.53  |

### Mean over quarters, central value scenario

| variant   |    k | strategy             |   precision |   captured $M |   captured_share |   listings_covered |
|:----------|-----:|:---------------------|------------:|--------------:|-----------------:|-------------------:|
| exclude   |  100 | best rule            |       0.312 |          0.46 |            0.005 |             332.25 |
| exclude   |  100 | random (expected)    |       0.171 |          0.43 |            0.004 |             nan    |
| exclude   |  100 | risk (max p)         |       0.65  |          4.23 |            0.042 |            1565.5  |
| exclude   |  100 | risk × value (Σ p·V) |       0.852 |         19.34 |            0.2   |            5222.75 |
| exclude   |  100 | value only (Σ V)     |       0.81  |         17.64 |            0.183 |            5197.75 |
| exclude   |  500 | best rule            |       0.284 |          4.39 |            0.044 |            1933.25 |
| exclude   |  500 | random (expected)    |       0.171 |          2.13 |            0.022 |             nan    |
| exclude   |  500 | risk (max p)         |       0.516 |         10.28 |            0.105 |            3655.25 |
| exclude   |  500 | risk × value (Σ p·V) |       0.618 |         36.77 |            0.382 |           10346.5  |
| exclude   |  500 | value only (Σ V)     |       0.52  |         33.4  |            0.346 |           10747    |
| exclude   | 1000 | best rule            |       0.28  |          7.19 |            0.074 |            3533.5  |
| exclude   | 1000 | random (expected)    |       0.171 |          4.26 |            0.044 |             nan    |
| exclude   | 1000 | risk (max p)         |       0.461 |         15.64 |            0.157 |            5433.25 |
| exclude   | 1000 | risk × value (Σ p·V) |       0.482 |         46.05 |            0.479 |           12786.8  |
| exclude   | 1000 | value only (Σ V)     |       0.38  |         41.15 |            0.427 |           13402.8  |
| retain    |  100 | best rule            |       0.36  |          0.41 |            0.004 |             361.5  |
| retain    |  100 | random (expected)    |       0.171 |          0.43 |            0.004 |             nan    |
| retain    |  100 | risk (max p)         |       0.635 |          3.1  |            0.031 |            1518.25 |
| retain    |  100 | risk × value (Σ p·V) |       0.838 |         18.83 |            0.194 |            5402.75 |
| retain    |  100 | value only (Σ V)     |       0.81  |         17.64 |            0.183 |            5197.75 |
| retain    |  500 | best rule            |       0.328 |          4.73 |            0.048 |            2282    |
| retain    |  500 | random (expected)    |       0.171 |          2.13 |            0.022 |             nan    |
| retain    |  500 | risk (max p)         |       0.511 |          8.14 |            0.083 |            3713    |
| retain    |  500 | risk × value (Σ p·V) |       0.612 |         37.06 |            0.385 |           10680.5  |
| retain    |  500 | value only (Σ V)     |       0.52  |         33.4  |            0.346 |           10747    |
| retain    | 1000 | best rule            |       0.326 |          7.98 |            0.082 |            4106.25 |
| retain    | 1000 | random (expected)    |       0.171 |          4.26 |            0.044 |             nan    |
| retain    | 1000 | risk (max p)         |       0.476 |         13.05 |            0.136 |            5742.75 |
| retain    | 1000 | risk × value (Σ p·V) |       0.475 |         46.11 |            0.478 |           13284.2  |
| retain    | 1000 | value only (Σ V)     |       0.38  |         41.15 |            0.427 |           13402.8  |

### Lift over the rule, host precision@500 (risk ranking vs `rule:low_presence_365`)

| variant   |   mean difference | mean relative   | quarters better   |   2023Q4 |   2024Q1 |   2024Q2 |   2024Q3 |
|:----------|------------------:|:----------------|:------------------|---------:|---------:|---------:|---------:|
| exclude   |             0.232 | +84.6%          | 4/4               |    0.216 |    0.216 |    0.276 |    0.222 |
| retain    |             0.184 | +56.2%          | 4/4               |    0.208 |    0.178 |    0.194 |    0.156 |

### By host portfolio size (eligible listings in the quarter), primary variant

`contacted_share`: share of the contacted hosts in each size group. `captured_value_share`: share of the captured disappearing value coming from that group.

| bucket   |   hosts |   base_rate |   contacted |   precision |   contacted_share |   lift |   captured_value_share | ranking              |
|:---------|--------:|------------:|------------:|------------:|------------------:|-------:|-----------------------:|:---------------------|
| 1        |   68831 |       0.136 |        1045 |       0.411 |             0.522 |  3.027 |                  0.012 | risk (max p)         |
| 2–5      |   17932 |       0.234 |         582 |       0.509 |             0.291 |  2.176 |                  0.093 | risk (max p)         |
| 6–20     |    3009 |       0.461 |         231 |       0.727 |             0.116 |  1.579 |                  0.232 | risk (max p)         |
| 21+      |     729 |       0.807 |         142 |       0.908 |             0.071 |  1.126 |                  0.663 | risk (max p)         |
| 1        |   68831 |       0.136 |         110 |       0.255 |             0.055 |  1.872 |                  0.025 | risk × value (Σ p·V) |
| 2–5      |   17932 |       0.234 |         356 |       0.368 |             0.178 |  1.574 |                  0.09  | risk × value (Σ p·V) |
| 6–20     |    3009 |       0.461 |         904 |       0.597 |             0.452 |  1.297 |                  0.323 | risk × value (Σ p·V) |
| 21+      |     729 |       0.807 |         630 |       0.835 |             0.315 |  1.035 |                  0.562 | risk × value (Σ p·V) |

## 2. Value exposure

Estimated value associated with correctly flagged disappearances: the summed V_i of `absent_confirmed` listings held by the 500 contacted hosts, per quarter (mean over quarters). `captured_share` is that value as a share of all disappearing value among eligible listings that quarter. Host exposure for ranking is Σ p_i·V_i over the host's listings, never max p × portfolio value.

| variant   | value_scenario   | strategy             |   captured_share |   captured ($M / quarter) |
|:----------|:-----------------|:---------------------|-----------------:|--------------------------:|
| exclude   | central          | best rule            |            0.044 |                      4.39 |
| exclude   | central          | random (expected)    |            0.022 |                      2.13 |
| exclude   | central          | risk (max p)         |            0.105 |                     10.28 |
| exclude   | central          | risk × value (Σ p·V) |            0.382 |                     36.77 |
| exclude   | central          | value only (Σ V)     |            0.346 |                     33.4  |
| exclude   | high_value       | best rule            |            0.045 |                      5.94 |
| exclude   | high_value       | random (expected)    |            0.022 |                      2.81 |
| exclude   | high_value       | risk (max p)         |            0.107 |                     13.81 |
| exclude   | high_value       | risk × value (Σ p·V) |            0.385 |                     48.88 |
| exclude   | high_value       | value only (Σ V)     |            0.353 |                     44.76 |
| exclude   | low_value        | best rule            |            0.044 |                      3.35 |
| exclude   | low_value        | random (expected)    |            0.022 |                      1.63 |
| exclude   | low_value        | risk (max p)         |            0.104 |                      7.83 |
| exclude   | low_value        | risk × value (Σ p·V) |            0.382 |                     28.2  |
| exclude   | low_value        | value only (Σ V)     |            0.347 |                     25.7  |
| retain    | central          | best rule            |            0.048 |                      4.73 |
| retain    | central          | random (expected)    |            0.022 |                      2.13 |
| retain    | central          | risk (max p)         |            0.083 |                      8.14 |
| retain    | central          | risk × value (Σ p·V) |            0.385 |                     37.06 |
| retain    | central          | value only (Σ V)     |            0.346 |                     33.4  |
| retain    | high_value       | best rule            |            0.049 |                      6.39 |
| retain    | high_value       | random (expected)    |            0.022 |                      2.81 |
| retain    | high_value       | risk (max p)         |            0.086 |                     11.03 |
| retain    | high_value       | risk × value (Σ p·V) |            0.388 |                     49.19 |
| retain    | high_value       | value only (Σ V)     |            0.353 |                     44.76 |
| retain    | low_value        | best rule            |            0.047 |                      3.6  |
| retain    | low_value        | random (expected)    |            0.022 |                      1.63 |
| retain    | low_value        | risk (max p)         |            0.082 |                      6.17 |
| retain    | low_value        | risk × value (Σ p·V) |            0.386 |                     28.51 |
| retain    | low_value        | value only (Σ V)     |            0.347 |                     25.7  |

### Does risk add anything over value alone?

Quarter-by-quarter difference, risk × value minus value only, at K = 500 (captured in $M per quarter). Value per host is heavy-tailed, so both rankings favour large portfolios; the comparison shows how much the risk score adds on top.

| variant   | value_scenario   | metric    |   mean difference | mean relative   | quarters better   |   2023Q4 |   2024Q1 |   2024Q2 |   2024Q3 |
|:----------|:-----------------|:----------|------------------:|:----------------|:------------------|---------:|---------:|---------:|---------:|
| exclude   | central          | precision |             0.098 | +18.9%          | 4/4               |    0.022 |    0.13  |    0.108 |    0.132 |
| exclude   | central          | captured  |             3.374 | +10.3%          | 4/4               |    1.351 |    3.637 |    3.679 |    4.829 |
| exclude   | high_value       | precision |             0.089 | +16.9%          | 3/4               |    0     |    0.118 |    0.118 |    0.12  |
| exclude   | high_value       | captured  |             4.12  | +9.0%           | 4/4               |    0.767 |    3.543 |    6.095 |    6.076 |
| exclude   | low_value        | precision |             0.089 | +17.3%          | 4/4               |    0.026 |    0.106 |    0.102 |    0.122 |
| exclude   | low_value        | captured  |             2.503 | +10.1%          | 4/4               |    1.128 |    2.614 |    2.433 |    3.836 |
| retain    | central          | precision |             0.092 | +17.7%          | 4/4               |    0.046 |    0.11  |    0.118 |    0.094 |
| retain    | central          | captured  |             3.669 | +11.1%          | 4/4               |    2.642 |    3.373 |    4.617 |    4.042 |
| retain    | high_value       | precision |             0.083 | +15.7%          | 4/4               |    0.036 |    0.1   |    0.104 |    0.092 |
| retain    | high_value       | captured  |             4.428 | +9.9%           | 4/4               |    3.264 |    3.676 |    5.663 |    5.108 |
| retain    | low_value        | precision |             0.085 | +16.5%          | 4/4               |    0.054 |    0.094 |    0.104 |    0.088 |
| retain    | low_value        | captured  |             2.816 | +11.3%          | 4/4               |    2.329 |    2.632 |    3.074 |    3.231 |

## 3. Intervention scenarios (central value scenario)

Net benefit per quarter ($ thousands) = prevention rate × take rate × captured value − cost per contact × K. The prevention rate is the share of **otherwise-occurring** disappearances that contact prevents, and is unknown until tested. The take rate converts host booking value into platform revenue. Break-even is the cost per contact at which net benefit is zero.

| strategy             |   prevention_rate |   take_rate |   breakeven_cost_per_contact |   net @ $25 |   net @ $100 |   net @ $250 |
|:---------------------|------------------:|------------:|-----------------------------:|------------:|-------------:|-------------:|
| risk × value (Σ p·V) |              0.05 |        0.1  |                       370.64 |       172.8 |        135.3 |         60.3 |
| risk × value (Σ p·V) |              0.05 |        0.15 |                       555.96 |       265.5 |        228   |        153   |
| risk × value (Σ p·V) |              0.1  |        0.1  |                       741.29 |       358.1 |        320.6 |        245.6 |
| risk × value (Σ p·V) |              0.1  |        0.15 |                      1111.93 |       543.5 |        506   |        431   |
| risk × value (Σ p·V) |              0.2  |        0.1  |                      1482.57 |       728.8 |        691.3 |        616.3 |
| risk × value (Σ p·V) |              0.2  |        0.15 |                      2223.86 |      1099.4 |       1061.9 |        986.9 |
| risk (max p)         |              0.05 |        0.1  |                        81.45 |        28.2 |         -9.3 |        -84.3 |
| risk (max p)         |              0.05 |        0.15 |                       122.17 |        48.6 |         11.1 |        -63.9 |
| risk (max p)         |              0.1  |        0.1  |                       162.9  |        68.9 |         31.4 |        -43.6 |
| risk (max p)         |              0.1  |        0.15 |                       244.34 |       109.7 |         72.2 |         -2.8 |
| risk (max p)         |              0.2  |        0.1  |                       325.79 |       150.4 |        112.9 |         37.9 |
| risk (max p)         |              0.2  |        0.15 |                       488.69 |       231.8 |        194.3 |        119.3 |
| value only (Σ V)     |              0.05 |        0.1  |                       333.96 |       154.5 |        117   |         42   |
| value only (Σ V)     |              0.05 |        0.15 |                       500.93 |       238   |        200.5 |        125.5 |
| value only (Σ V)     |              0.1  |        0.1  |                       667.91 |       321.5 |        284   |        209   |
| value only (Σ V)     |              0.1  |        0.15 |                      1001.87 |       488.4 |        450.9 |        375.9 |
| value only (Σ V)     |              0.2  |        0.1  |                      1335.82 |       655.4 |        617.9 |        542.9 |
| value only (Σ V)     |              0.2  |        0.15 |                      2003.74 |       989.4 |        951.9 |        876.9 |
| best rule            |              0.05 |        0.1  |                        47.34 |        11.2 |        -26.3 |       -101.3 |
| best rule            |              0.05 |        0.15 |                        71.01 |        23   |        -14.5 |        -89.5 |
| best rule            |              0.1  |        0.1  |                        94.68 |        34.8 |         -2.7 |        -77.7 |
| best rule            |              0.1  |        0.15 |                       142.02 |        58.5 |         21   |        -54   |
| best rule            |              0.2  |        0.1  |                       189.36 |        82.2 |         44.7 |        -30.3 |
| best rule            |              0.2  |        0.15 |                       284.05 |       129.5 |         92   |         17   |
| random (expected)    |              0.05 |        0.1  |                        21.29 |        -1.9 |        -39.4 |       -114.4 |
| random (expected)    |              0.05 |        0.15 |                        31.93 |         3.5 |        -34   |       -109   |
| random (expected)    |              0.1  |        0.1  |                        42.58 |         8.8 |        -28.7 |       -103.7 |
| random (expected)    |              0.1  |        0.15 |                        63.86 |        19.4 |        -18.1 |        -93.1 |
| random (expected)    |              0.2  |        0.1  |                        85.15 |        30.1 |         -7.4 |        -82.4 |
| random (expected)    |              0.2  |        0.15 |                       127.73 |        51.4 |         13.9 |        -61.1 |

Sensitivity variant (`exclude`):

| strategy             |   prevention_rate |   take_rate |   breakeven_cost_per_contact |   net @ $25 |   net @ $100 |   net @ $250 |
|:---------------------|------------------:|------------:|-----------------------------:|------------:|-------------:|-------------:|
| risk × value (Σ p·V) |              0.05 |        0.1  |                       367.7  |       171.3 |        133.8 |         58.8 |
| risk × value (Σ p·V) |              0.05 |        0.15 |                       551.54 |       263.3 |        225.8 |        150.8 |
| risk × value (Σ p·V) |              0.1  |        0.1  |                       735.39 |       355.2 |        317.7 |        242.7 |
| risk × value (Σ p·V) |              0.1  |        0.15 |                      1103.09 |       539   |        501.5 |        426.5 |
| risk × value (Σ p·V) |              0.2  |        0.1  |                      1470.79 |       722.9 |        685.4 |        610.4 |
| risk × value (Σ p·V) |              0.2  |        0.15 |                      2206.18 |      1090.6 |       1053.1 |        978.1 |
| risk (max p)         |              0.05 |        0.1  |                       102.83 |        38.9 |          1.4 |        -73.6 |
| risk (max p)         |              0.05 |        0.15 |                       154.25 |        64.6 |         27.1 |        -47.9 |
| risk (max p)         |              0.1  |        0.1  |                       205.66 |        90.3 |         52.8 |        -22.2 |
| risk (max p)         |              0.1  |        0.15 |                       308.5  |       141.7 |        104.2 |         29.2 |
| risk (max p)         |              0.2  |        0.1  |                       411.33 |       193.2 |        155.7 |         80.7 |
| risk (max p)         |              0.2  |        0.15 |                       616.99 |       296   |        258.5 |        183.5 |
| value only (Σ V)     |              0.05 |        0.1  |                       333.96 |       154.5 |        117   |         42   |
| value only (Σ V)     |              0.05 |        0.15 |                       500.93 |       238   |        200.5 |        125.5 |
| value only (Σ V)     |              0.1  |        0.1  |                       667.91 |       321.5 |        284   |        209   |
| value only (Σ V)     |              0.1  |        0.15 |                      1001.87 |       488.4 |        450.9 |        375.9 |
| value only (Σ V)     |              0.2  |        0.1  |                      1335.82 |       655.4 |        617.9 |        542.9 |
| value only (Σ V)     |              0.2  |        0.15 |                      2003.74 |       989.4 |        951.9 |        876.9 |
| best rule            |              0.05 |        0.1  |                        43.93 |         9.5 |        -28   |       -103   |
| best rule            |              0.05 |        0.15 |                        65.89 |        20.4 |        -17.1 |        -92.1 |
| best rule            |              0.1  |        0.1  |                        87.85 |        31.4 |         -6.1 |        -81.1 |
| best rule            |              0.1  |        0.15 |                       131.78 |        53.4 |         15.9 |        -59.1 |
| best rule            |              0.2  |        0.1  |                       175.71 |        75.4 |         37.9 |        -37.1 |
| best rule            |              0.2  |        0.15 |                       263.56 |       119.3 |         81.8 |          6.8 |
| random (expected)    |              0.05 |        0.1  |                        21.29 |        -1.9 |        -39.4 |       -114.4 |
| random (expected)    |              0.05 |        0.15 |                        31.93 |         3.5 |        -34   |       -109   |
| random (expected)    |              0.1  |        0.1  |                        42.58 |         8.8 |        -28.7 |       -103.7 |
| random (expected)    |              0.1  |        0.15 |                        63.86 |        19.4 |        -18.1 |        -93.1 |
| random (expected)    |              0.2  |        0.1  |                        85.15 |        30.1 |         -7.4 |        -82.4 |
| random (expected)    |              0.2  |        0.15 |                       127.73 |        51.4 |         13.9 |        -61.1 |

## Experiment sizing (host-randomized)

Hosts needed per arm to detect a relative reduction in the share of contacted hosts with a disappearance (two-sided α = 0.05, power 0.8, normal approximation, ignoring clustering across quarters).

| relative reduction in hosts with a disappearance   |   control hit rate (top-ranked hosts) |   hosts per arm |   quarters at 500 treated + 500 control |
|:---------------------------------------------------|--------------------------------------:|----------------:|----------------------------------------:|
| 5%                                                 |                                 0.512 |            5999 |                                      12 |
| 10%                                                |                                 0.512 |            1498 |                                       3 |
| 20%                                                |                                 0.512 |             372 |                                       1 |
