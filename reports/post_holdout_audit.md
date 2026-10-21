# Post-Holdout Audit

Run after the one-time holdout, from saved results, in response to review. **Nothing here changes the frozen analysis or its reported holdout results**; these numbers are audits, not prespecified holdout results.

## 1. Contact timing vs information used

The frozen host aggregation pools a host's eligible listings across markets for the whole quarter, and assigns the earliest decision date as the contact date. Contacted hosts whose ranking used listings observed **after** that date:

| quarter   |   contacted |   using_later_listings | ranking              |
|:----------|------------:|-----------------------:|:---------------------|
| 2023Q4    |         500 |                     24 | risk (max p)         |
| 2024Q1    |         500 |                     16 | risk (max p)         |
| 2024Q2    |         500 |                     12 | risk (max p)         |
| 2024Q3    |         500 |                     12 | risk (max p)         |
| 2023Q4    |         500 |                     23 | risk × value (Σ p·V) |
| 2024Q1    |         500 |                     24 | risk × value (Σ p·V) |
| 2024Q2    |         500 |                     24 | risk × value (Σ p·V) |
| 2024Q3    |         500 |                     19 | risk × value (Σ p·V) |

Spread of decision dates within each quarter (markets are scraped on different days):

| quarter   | min        | max        |   days |
|:----------|:-----------|:-----------|-------:|
| 2023Q4    | 2023-12-04 | 2024-01-03 |     30 |
| 2024Q1    | 2024-03-12 | 2024-03-31 |     19 |
| 2024Q2    | 2024-06-14 | 2024-06-30 |     16 |
| 2024Q3    | 2024-09-05 | 2024-09-29 |     24 |

So the frozen results are a **pooled quarterly ranking benchmark**. A deployable contact policy needs a shared information cutoff (e.g. contact on the quarter's last decision date) or a sequential selection as each market arrives. Neither has been evaluated.

## 2. Calibration on the holdout

Mean predicted probability minus observed rate, in percentage points, per holdout quarter:

| quarter   |   lgbm |   lr |
|:----------|-------:|-----:|
| 2023Q4    |    6.1 |  4.3 |
| 2024Q1    |   13.2 | 13.7 |
| 2024Q2    |   13.9 | 22.7 |
| 2024Q3    |    8.9 | 19.2 |

LightGBM mean absolute gap: **10.5 pp**, worst **13.9 pp**. Probability-weighted value (Σ p·V) is affected; the rank-based precision metrics are not.

## 3. Experiment sizing on the proposed recruitment population

The frozen business report sized the experiment from the top 500 hosts by risk (event rate 0.512). The proposal recruits the top 1,000 by Σ p·V, whose holdout event rate is lower:

| quarter   |   event rate |
|:----------|-------------:|
| 2023Q4    |        0.479 |
| 2024Q1    |        0.446 |
| 2024Q2    |        0.492 |
| 2024Q3    |        0.483 |

| relative reduction   |   event rate (top 1,000 by Σ p·V, holdout) |   independent hosts per arm |   recruitment quarters at 500 new hosts per arm |
|:---------------------|-------------------------------------------:|----------------------------:|------------------------------------------------:|
| 5%                   |                                      0.475 |                        6919 |                                              14 |
| 10%                  |                                      0.475 |                        1722 |                                               4 |
| 20%                  |                                      0.475 |                         425 |                                               1 |

Hosts recur across quarters; each host can be randomized once, so only new hosts count toward the totals. Outcomes need ~9–10 months of follow-up after the last recruitment quarter.
