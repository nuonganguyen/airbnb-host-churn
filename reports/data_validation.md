# Data Validation: Curated Listings Extract

Run 2026-10-20 on `data_local/listings_6city.parquet` (4,191,985 listing-snapshot rows; Austin, Denver, Nashville, New Orleans, San Diego, Seattle).
The source drive was read only: `ia.db` via read-only connections and raw CSVs via `read_csv`.

**Summary:** 8 FAIL · 15 WARN · 26 PASS · 19 INFO

## 1. Types

| Status | Check | Result |
|---|---|---|
| PASS | numeric/date columns that cast cleanly | 0 / 38 (0.00%) - columns with any uncastable value |
| PASS | snapshot DATE parses as YYYYMMDD | 0 / 4,191,985 (0.00%) |
| INFO | `TAB_LAST_UPDATED` storage format | timestamp text: 3,701,300; unix epoch number: 490,685 (mixed formats - rows appended by NEWpipeline.R use epoch seconds) |

## 2. Keys & identity

| Status | Check | Result |
|---|---|---|
| PASS | duplicate (KEY_FILE, KEY_LIST_ID) rows | 0 / 4,191,985 (0.00%) |
| PASS | duplicate (city, snapshot date, listing) rows | 0 / 4,191,985 (0.00%) - same snapshot loaded from two files (e.g. .csv and .tsv) |
| PASS | null listing or host id | 0 / 4,191,985 (0.00%) |
| PASS | CITY_ID matches KEY_FILE prefix | 0 / 4,191,985 (0.00%) |
| PASS | DATE matches KEY_FILE suffix | 0 / 4,191,985 (0.00%) |
| WARN | listings appearing in more than one city | 2 / 294,622 (0.00%) |
| WARN | listings whose host id changes over time | 7,221 / 294,622 (2.45%) - ownership transfer or re-assignment; matters for host-level churn |

## 3. Reconciliation with source files

| Status | Check | Result |
|---|---|---|
| WARN | registered listings files with no curated rows | 27 / 590 (4.58%) - by type: {'csv': 1, 'tsv': 26} |
| INFO | unloaded files whose date is covered by another file | 26 of 27 (likely .tsv duplicates of a .csv snapshot) |
| PASS | curated KEY_FILEs not registered in META | 0 / 563 (0.00%) |
| PASS | curated listings = META unique listings, per file | 0 / 552 (0.00%) |
| INFO | files with no ROWS / UNIQUE_LISTINGS recorded in META | 11 (2024-06, 2024-09) - metadata gap only; the rows are in the curated table |
| INFO | unloaded files that are empty at the source | San Diego_2017-11-16_listings.csv |
| INFO | META ROWS vs UNIQUE_LISTINGS in raw listings files | 552 of 563 files have ROWS > UNIQUE_LISTINGS (median gap 5,348) - META ROWS likely counts text lines, since descriptions contain embedded newlines; UNIQUE_LISTINGS is the reliable count |
| PASS | raw listings files on disk not registered in META | 0 / 590 (0.00%) |

## 4. Field-level check against raw CSVs

| Status | Check | Result |
|---|---|---|
| FAIL | `price` matches raw value | 9,956 / 127,399 (7.81%) - worst file San Diego_2026-06-27_listings.csv (81.2%) |
| PASS | `reviews` matches raw value | 0 / 127,399 (0.00%) - worst file Austin_2015-05-23_listings.csv (100.0%) |
| PASS | `avail_365` matches raw value | 0 / 127,399 (0.00%) - worst file Austin_2015-05-23_listings.csv (100.0%) |
| PASS | `capacity` matches raw value | 0 / 127,399 (0.00%) - worst file Austin_2015-05-23_listings.csv (100.0%) |
| PASS | `room_type` matches raw value | 0 / 127,399 (0.00%) - worst file Austin_2015-05-23_listings.csv (100.0%) |
| PASS | `host_id` matches raw value | 0 / 127,399 (0.00%) - worst file Austin_2015-05-23_listings.csv (100.0%) |
| FAIL | raw prices >= $1,000 truncated at the thousands comma | 4,603 / 4,603 (100.00%) - e.g. raw "$1,067.50" -> curated 1.0; every price >= $1,000 is affected |
| FAIL | raw empty price stored as 0 (should be NULL) | 5,353 / 127,399 (4.20%) |
| PASS | raw listings found in curated table | 0 / 127,399 (0.00%) |

| file                                |   raw_listings |   matched | price   | reviews   | avail_365   | capacity   | room_type   | host_id   |   raw_price_ge_1000 |   price_thousands_bug |   price_null_as_zero |
|:------------------------------------|---------------:|----------:|:--------|:----------|:------------|:-----------|:------------|:----------|--------------------:|----------------------:|---------------------:|
| Austin_2015-05-23_listings.csv      |           5192 |      5192 | 95.9%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 211 |                   211 |                    0 |
| Austin_2020-02-19_listings.csv      |          11520 |     11520 | 93.6%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 740 |                   740 |                    0 |
| Austin_2026-06-22_listings.csv      |          11295 |     11295 | 87.1%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 486 |                   486 |                  974 |
| Denver_2016-06-07_listings.csv      |           2239 |      2239 | 99.9%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                   2 |                     2 |                    0 |
| Denver_2020-03-23_listings.csv      |           4868 |      4868 | 97.7%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 111 |                   111 |                    0 |
| Denver_2026-06-30_listings.csv      |           4939 |      4939 | 84.8%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                  62 |                    62 |                  688 |
| Nashville_2015-10-03_listings.csv   |           2110 |      2110 | 99.7%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                   7 |                     7 |                    0 |
| Nashville_2020-01-14_listings.csv   |           7506 |      7506 | 95.1%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 365 |                   365 |                    0 |
| Nashville_2026-06-26_listings.csv   |          10242 |     10242 | 88.9%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 410 |                   410 |                  727 |
| New Orleans_2015-06-05_listings.csv |           2614 |      2614 | 98.4%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                  43 |                    43 |                    0 |
| New Orleans_2019-11-03_listings.csv |           7195 |      7195 | 97.1%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 211 |                   211 |                    0 |
| New Orleans_2026-06-16_listings.csv |           7189 |      7189 | 87.0%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 162 |                   162 |                  769 |
| San Diego_2015-11-07_listings.csv   |           4279 |      4279 | 98.5%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                  66 |                    66 |                    0 |
| San Diego_2020-01-15_listings.csv   |          13731 |     13731 | 97.6%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 329 |                   329 |                    0 |
| San Diego_2026-06-27_listings.csv   |          13225 |     13225 | 81.2%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                1112 |                  1112 |                 1369 |
| Seattle_2015-11-08_listings.csv     |           3617 |      3617 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                   1 |                     1 |                    0 |
| Seattle_2020-01-15_listings.csv     |           7869 |      7869 | 98.9%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                  85 |                    85 |                    0 |
| Seattle_2026-06-15_listings.csv     |           7769 |      7769 | 86.8%   | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 200 |                   200 |                  826 |

## 5. Missingness over time

| Status | Check | Result |
|---|---|---|
| INFO | `price` null rate shifts across years | 0% (2015) to 27% (2025) - overall 2.3% |
| INFO | `bedrooms` null rate shifts across years | 0% (2018) to 37% (2023) - overall 4.7% |
| INFO | `available` null rate shifts across years | 0% (2018) to 76% (2016) - overall 12.0% |
| INFO | `loc_overview_word_count` null rate shifts across years | 0% (2015) to 100% (2026) - overall 3.7% |
| INFO | `loc_overview_char_count` null rate shifts across years | 0% (2016) to 100% (2026) - overall 3.9% |
| INFO | `descrip_char_count` null rate shifts across years | 0% (2015) to 26% (2023) - overall 1.3% |
| INFO | `host_response_rate` null rate shifts across years | 0% (2015) to 100% (2026) - overall 3.2% |
| INFO | `host_accept_rate` null rate shifts across years | 0% (2015) to 100% (2026) - overall 3.2% |
| INFO | `host_since` null rate shifts across years | 0% (2024) to 100% (2026) - overall 3.4% |
| INFO | `host_response_time` null rate shifts across years | 0% (2015) to 100% (2026) - overall 3.2% |

|   year | price   | capacity   | bedrooms   | overall_rating   | host_response_rate   | host_accept_rate   | available_365   | first_review_date   |
|-------:|:--------|:-----------|:-----------|:-----------------|:---------------------|:-------------------|:----------------|:--------------------|
|   2015 | 0%      | 0%         | 0%         | 26%              | 0%                   | 0%                 | 0%              | 25%                 |
|   2016 | 0%      | 0%         | 0%         | 24%              | 0%                   | 0%                 | 0%              | 23%                 |
|   2017 | 0%      | 0%         | 0%         | 20%              | 0%                   | 0%                 | 0%              | 19%                 |
|   2018 | 0%      | 0%         | 0%         | 19%              | 0%                   | 0%                 | 0%              | 18%                 |
|   2019 | 0%      | 0%         | 0%         | 16%              | 0%                   | 0%                 | 0%              | 15%                 |
|   2020 | 3%      | 0%         | 5%         | 17%              | 0%                   | 0%                 | 0%              | 16%                 |
|   2021 | 0%      | 0%         | 8%         | 17%              | 0%                   | 0%                 | 0%              | 17%                 |
|   2022 | 0%      | 0%         | 7%         | 15%              | 0%                   | 0%                 | 0%              | 15%                 |
|   2023 | 0%      | 0%         | 37%        | 16%              | 0%                   | 0%                 | 0%              | 16%                 |
|   2024 | 0%      | 0%         | 3%         | 16%              | 0%                   | 0%                 | 0%              | 16%                 |
|   2025 | 27%     | 0%         | 2%         | 15%              | 18%                  | 18%                | 0%              | 15%                 |
|   2026 | 24%     | 0%         | 8%         | 14%              | 100%                 | 100%               | 0%              | 14%                 |

## 6. Ranges & domains

| Status | Check | Result |
|---|---|---|
| FAIL | price <= 0 | 77,688 / 4,191,985 (1.85%) |
| PASS | price > $10,000/night | 0 / 4,191,985 (0.00%) |
| WARN | capacity outside 1-16 | 2,210 / 4,191,985 (0.05%) |
| WARN | bedrooms > 20 | 297 / 4,191,985 (0.01%) |
| WARN | bathrooms > 20 | 135 / 4,191,985 (0.00%) |
| PASS | min_night > 365 | 662 / 4,191,985 (0.02%) |
| PASS | max_night < min_night | 39 / 4,191,985 (0.00%) |
| WARN | available_365 outside 0-365 | 1 / 4,191,985 (0.00%) |
| PASS | availability windows not nested (30 <= 60 <= 90 <= 365) | 0 / 4,191,985 (0.00%) |
| WARN | ratings outside 0-5 | 1 / 4,191,985 (0.00%) |
| PASS | response/accept rate outside 0-1 | 0 / 4,191,985 (0.00%) |
| PASS | binary flags not 0/1 | 0 / 4,191,985 (0.00%) |
| PASS | amenity flags (AC*) not 0/1 | 0 / 4,191,985 (0.00%) |
| PASS | negative counts | 0 / 4,191,985 (0.00%) |
| FAIL | price between $1 and $15 (mostly truncated $1,000+ prices) | 99,301 / 4,191,985 (2.37%) |
| INFO | price distribution | p1 $1 · median $135 · p99 $871 · max $1,000 |
| INFO | overall_rating scale by year | max 2015: 5.0, 2016: 5.0, 2017: 5.0, 2018: 5.0, 2019: 5.0, 2020: 5.0, 2021: 5.0, 2022: 5.0, 2023: 5.0, 2024: 5.0, 2025: 5.0, 2026: 5.0 - one 0-5 scale throughout, so the source's 0-100 era was rescaled |

## 7. Logical consistency

| Status | Check | Result |
|---|---|---|
| WARN | first_review_date > last_review_date | 3,505 / 4,191,985 (0.08%) |
| WARN | last_review_date after snapshot date (by up to 21 days; file date precedes scrape) | 5,363 / 4,191,985 (0.13%) |
| PASS | host_since after snapshot date | 0 / 4,191,985 (0.00%) |
| WARN | reviews = 0 but has a review date | 14 / 4,191,985 (0.00%) |
| PASS | reviews > 0 but no review date | 923 / 4,191,985 (0.02%) |
| WARN | reviews = 0 but has a rating | 58 / 4,191,985 (0.00%) |
| FAIL | host_response_time 'N/A' but response rate stored as 0 (missing coded as 0) | 773,649 / 4,191,985 (18.46%) |
| FAIL | host_accept_rate exactly 0 (raw 'N/A' coded as 0) | 2,077,311 / 4,191,985 (49.55%) |
| INFO | share of host_accept_rate = 0 by year | 2015: 22%, 2016: 41%, 2017: 100%, 2018: 100%, 2019: 100%, 2020: 24%, 2021: 21%, 2022: 13%, 2023: 14%, 2024: 14%, 2025: 14% - 100% in 2017-2019 because the raw column is 'N/A' for every listing then |
| WARN | snapshots where the source has no host response/acceptance data | 17 / 563 (3.02%) - every snapshot from 2025-12-22 on (135,152 rows): raw files contain 'NA' for host_since, response time/rate and acceptance rate - a source gap, not a pipeline bug |
| FAIL | snapshots with host_since missing for most listings | 17 / 563 (3.02%) - host_since is fixed per host, so it can be carried forward from earlier snapshots |

## 8. Snapshot timeline

| Status | Check | Result |
|---|---|---|
| WARN | snapshots with >40% row-count change vs previous | 7 / 563 (1.24%) - Austin 2017-10-07 (7,062->10,437); Denver 2026-03-31 (4,260->2,159); Denver 2026-06-30 (2,159->4,939); Nashville 2026-06-26 (6,030->10,242); San Diego 2017-07-11 (8,421->3,134); San Diego 2017-08-11 (3,134->9,285) |
| WARN | gaps of more than 120 days between snapshots | 9 / 563 (1.60%) - Austin before 2015-11-07 (168d); Austin before 2023-06-10 (145d); Denver before 2020-10-29 (123d); Denver before 2023-06-30 (182d); Nashville before 2023-06-22 (153d); New Orleans before 2023-06-06 (148d) |
| INFO | median days between snapshots | 2015-2022: 31 days · 2023-2026: 92 days |

Detail files: `data_local/validation/`