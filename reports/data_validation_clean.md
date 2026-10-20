# Data Validation: Curated Listings Extract

Run 2026-10-20 on `data_local/listings_6city.parquet` (4,191,985 listing-snapshot rows; Austin, Denver, Nashville, New Orleans, San Diego, Seattle).
The source drive was read only: `ia.db` via read-only connections and raw CSVs via `read_csv`.

**Summary:** 0 FAIL · 17 WARN · 32 PASS · 19 INFO

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
| PASS | `price` matches raw value | 0 / 127,399 (0.00%) - worst file Austin_2015-05-23_listings.csv (100.0%) |
| PASS | `reviews` matches raw value | 0 / 127,399 (0.00%) - worst file Austin_2015-05-23_listings.csv (100.0%) |
| PASS | `avail_365` matches raw value | 0 / 127,399 (0.00%) - worst file Austin_2015-05-23_listings.csv (100.0%) |
| PASS | `capacity` matches raw value | 0 / 127,399 (0.00%) - worst file Austin_2015-05-23_listings.csv (100.0%) |
| PASS | `room_type` matches raw value | 0 / 127,399 (0.00%) - worst file Austin_2015-05-23_listings.csv (100.0%) |
| PASS | `host_id` matches raw value | 0 / 127,399 (0.00%) - worst file Austin_2015-05-23_listings.csv (100.0%) |
| PASS | raw prices >= $1,000 truncated at the thousands comma | 0 / 4,603 (0.00%) - e.g. raw "$1,067.50" -> curated 1.0; every price >= $1,000 is affected |
| PASS | raw empty price stored as 0 (should be NULL) | 0 / 127,399 (0.00%) |
| PASS | raw listings found in curated table | 0 / 127,399 (0.00%) |

| file                                |   raw_listings |   matched | price   | reviews   | avail_365   | capacity   | room_type   | host_id   |   raw_price_ge_1000 |   price_thousands_bug |   price_null_as_zero |
|:------------------------------------|---------------:|----------:|:--------|:----------|:------------|:-----------|:------------|:----------|--------------------:|----------------------:|---------------------:|
| Austin_2015-05-23_listings.csv      |           5192 |      5192 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 211 |                     0 |                    0 |
| Austin_2020-02-19_listings.csv      |          11520 |     11520 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 740 |                     0 |                    0 |
| Austin_2026-06-22_listings.csv      |          11295 |     11295 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 486 |                     0 |                    0 |
| Denver_2016-06-07_listings.csv      |           2239 |      2239 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                   2 |                     0 |                    0 |
| Denver_2020-03-23_listings.csv      |           4868 |      4868 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 111 |                     0 |                    0 |
| Denver_2026-06-30_listings.csv      |           4939 |      4939 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                  62 |                     0 |                    0 |
| Nashville_2015-10-03_listings.csv   |           2110 |      2110 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                   7 |                     0 |                    0 |
| Nashville_2020-01-14_listings.csv   |           7506 |      7506 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 365 |                     0 |                    0 |
| Nashville_2026-06-26_listings.csv   |          10242 |     10242 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 410 |                     0 |                    0 |
| New Orleans_2015-06-05_listings.csv |           2614 |      2614 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                  43 |                     0 |                    0 |
| New Orleans_2019-11-03_listings.csv |           7195 |      7195 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 211 |                     0 |                    0 |
| New Orleans_2026-06-16_listings.csv |           7189 |      7189 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 162 |                     0 |                    0 |
| San Diego_2015-11-07_listings.csv   |           4279 |      4279 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                  66 |                     0 |                    0 |
| San Diego_2020-01-15_listings.csv   |          13731 |     13731 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 329 |                     0 |                    0 |
| San Diego_2026-06-27_listings.csv   |          13225 |     13225 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                1112 |                     0 |                    0 |
| Seattle_2015-11-08_listings.csv     |           3617 |      3617 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                   1 |                     0 |                    0 |
| Seattle_2020-01-15_listings.csv     |           7869 |      7869 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                  85 |                     0 |                    0 |
| Seattle_2026-06-15_listings.csv     |           7769 |      7769 | 100.0%  | 100.0%    | 100.0%      | 100.0%     | 100.0%      | 100.0%    |                 200 |                     0 |                    0 |

## 5. Missingness over time

| Status | Check | Result |
|---|---|---|
| INFO | `price` null rate shifts across years | 0% (2015) to 40% (2025) - overall 4.2% |
| INFO | `bedrooms` null rate shifts across years | 0% (2018) to 37% (2023) - overall 4.7% |
| INFO | `available` null rate shifts across years | 0% (2018) to 76% (2016) - overall 12.0% |
| INFO | `loc_overview_word_count` null rate shifts across years | 0% (2015) to 100% (2026) - overall 3.7% |
| INFO | `loc_overview_char_count` null rate shifts across years | 0% (2016) to 100% (2026) - overall 3.9% |
| INFO | `descrip_char_count` null rate shifts across years | 0% (2015) to 26% (2023) - overall 1.3% |
| INFO | `host_response_rate` null rate shifts across years | 15% (2022) to 100% (2026) - overall 21.9% |
| INFO | `host_accept_rate` null rate shifts across years | 11% (2022) to 100% (2026) - overall 51.8% |
| INFO | `host_response_time` null rate shifts across years | 0% (2015) to 100% (2026) - overall 3.2% |
| INFO | columns more than 50% null overall | `host_accept_rate` 52% |

|   year | price   | capacity   | bedrooms   | overall_rating   | host_response_rate   | host_accept_rate   | available_365   | first_review_date   |
|-------:|:--------|:-----------|:-----------|:-----------------|:---------------------|:-------------------|:----------------|:--------------------|
|   2015 | 0%      | 0%         | 0%         | 26%              | 16%                  | 20%                | 0%              | 25%                 |
|   2016 | 0%      | 0%         | 0%         | 24%              | 17%                  | 40%                | 0%              | 23%                 |
|   2017 | 0%      | 0%         | 0%         | 20%              | 19%                  | 100%               | 0%              | 19%                 |
|   2018 | 0%      | 0%         | 0%         | 19%              | 24%                  | 100%               | 0%              | 18%                 |
|   2019 | 0%      | 0%         | 0%         | 16%              | 20%                  | 100%               | 0%              | 15%                 |
|   2020 | 3%      | 0%         | 5%         | 17%              | 22%                  | 23%                | 0%              | 16%                 |
|   2021 | 0%      | 0%         | 8%         | 17%              | 22%                  | 19%                | 0%              | 17%                 |
|   2022 | 0%      | 0%         | 7%         | 15%              | 15%                  | 11%                | 0%              | 15%                 |
|   2023 | 2%      | 0%         | 37%        | 16%              | 17%                  | 13%                | 0%              | 16%                 |
|   2024 | 17%     | 0%         | 3%         | 16%              | 15%                  | 12%                | 0%              | 16%                 |
|   2025 | 40%     | 0%         | 2%         | 15%              | 31%                  | 28%                | 0%              | 15%                 |
|   2026 | 30%     | 0%         | 8%         | 14%              | 100%                 | 100%               | 0%              | 14%                 |

## 6. Ranges & domains

| Status | Check | Result |
|---|---|---|
| WARN | price <= 0 | 1,185 / 4,191,985 (0.03%) |
| PASS | price > $10,000/night | 878 / 4,191,985 (0.02%) |
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
| PASS | price between $1 and $15 (mostly truncated $1,000+ prices) | 4,050 / 4,191,985 (0.10%) |
| INFO | price distribution | p1 $30 · median $144 · p99 $1,500 · max $238,121 |
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
| WARN | host_response_time 'N/A' but response rate stored as 0 (missing coded as 0) | 12 / 4,191,985 (0.00%) |
| PASS | host_accept_rate exactly 0 (raw 'N/A' coded as 0) | 39,072 / 4,191,985 (0.93%) |
| INFO | share of host_accept_rate = 0 by year | 2015: 2%, 2016: 2%, 2017: 100%, 2018: 100%, 2019: 100%, 2020: 2%, 2021: 3%, 2022: 2%, 2023: 1%, 2024: 2%, 2025: 2% - 100% in 2017-2019 because the raw column is 'N/A' for every listing then |
| WARN | snapshots where the source has no host response/acceptance data | 17 / 563 (3.02%) - every snapshot from 2025-12-22 on (135,152 rows): raw files contain 'NA' for host_since, response time/rate and acceptance rate - a source gap, not a pipeline bug |
| PASS | snapshots with host_since missing for most listings | 0 / 563 (0.00%) |

## 8. Snapshot timeline

| Status | Check | Result |
|---|---|---|
| WARN | snapshots with >40% row-count change vs previous | 7 / 563 (1.24%) - Austin 2017-10-07 (7,062->10,437); Denver 2026-03-31 (4,260->2,159); Denver 2026-06-30 (2,159->4,939); Nashville 2026-06-26 (6,030->10,242); San Diego 2017-07-11 (8,421->3,134); San Diego 2017-08-11 (3,134->9,285) |
| WARN | gaps of more than 120 days between snapshots | 9 / 563 (1.60%) - Austin before 2015-11-07 (168d); Austin before 2023-06-10 (145d); Denver before 2020-10-29 (123d); Denver before 2023-06-30 (182d); Nashville before 2023-06-22 (153d); New Orleans before 2023-06-06 (148d) |
| INFO | median days between snapshots | 2015-2022: 31 days · 2023-2026: 92 days |

Detail files: `data_local/validation/`