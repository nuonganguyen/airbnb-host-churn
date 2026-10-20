# Feature Summary

Built 2026-10-20 by `src/features.py` per `docs/feature_spec.md`.

## Row integrity

|    rows |   distinct_keys |   listings_at_prediction_dates |
|--------:|----------------:|-------------------------------:|
| 1865274 |         1865274 |                        1865274 |

## Allowlist: 61 predictors (49 numeric, 8 binary, 4 categorical)

## Null share by era

| feature                         |   2015-22 |   2023+ |
|:--------------------------------|----------:|--------:|
| price                           |     0.011 |   0.171 |
| capacity                        |     0     |   0     |
| bathrooms                       |     0.001 |   0     |
| bedrooms                        |     0.037 |   0.139 |
| beds                            |     0.016 |   0.121 |
| min_night                       |     0.011 |   0     |
| max_night                       |     0.011 |   0     |
| available_030                   |     0     |   0     |
| available_060                   |     0     |   0     |
| available_090                   |     0     |   0     |
| available_365                   |     0     |   0     |
| number_of_reviews               |     0     |   0     |
| overall_rating                  |     0.178 |   0.157 |
| accom_rating                    |     0.18  |   0.158 |
| clean_rating                    |     0.18  |   0.158 |
| checkin_rating                  |     0.18  |   0.158 |
| com_rating                      |     0.18  |   0.158 |
| loc_rating                      |     0.181 |   0.158 |
| value_rating                    |     0.181 |   0.158 |
| amenity_count                   |     0     |   0     |
| amenity_count_pct               |     0     |   0     |
| descrip_word_count              |     0     |   0     |
| host_about_word_count           |     0     |   0     |
| host_listing_count              |     0.002 |   0.003 |
| price_missing                   |     0     |   0     |
| host_is_superhost               |     0.002 |   0.027 |
| host_has_pic                    |     0.002 |   0.003 |
| host_verified                   |     0.002 |   0.003 |
| city_id                         |     0     |   0     |
| room_type                       |     0     |   0     |
| listing_type                    |     0     |   0     |
| quarter_of_year                 |     0     |   0     |
| days_since_first_observed       |     0     |   0     |
| host_tenure_days                |     0     |   0.008 |
| days_since_last_review          |     0.172 |   0.157 |
| days_since_first_review         |     0.172 |   0.157 |
| first_observed_censored         |     0     |   0     |
| lag90_days                      |     0.003 |   0.112 |
| price_change_90                 |     0.191 |   0.408 |
| avail365_change_90              |     0.171 |   0.211 |
| rating_change_90                |     0.309 |   0.328 |
| reviews_added_90                |     0.171 |   0.211 |
| review_rate_90                  |     0.171 |   0.211 |
| present_lag90                   |     0.003 |   0.112 |
| reviews_decreased_90            |     0.171 |   0.211 |
| lag365_days                     |     0.055 |   0.078 |
| price_change_365                |     0.469 |   0.528 |
| reviews_added_365               |     0.454 |   0.393 |
| review_rate_365                 |     0.454 |   0.393 |
| present_lag365                  |     0.055 |   0.078 |
| hist_snapshots_365              |     0     |   0     |
| hist_present_365                |     0     |   0     |
| presence_rate_365               |     0     |   0     |
| host_n_listings                 |     0     |   0     |
| host_listings_change_90         |     0.003 |   0.112 |
| city_n_listings                 |     0     |   0     |
| city_supply_growth_365          |     0.055 |   0.078 |
| price_rel_room_median           |     0.011 |   0.171 |
| neighbourhood_n_listings        |     0     |   0     |
| neighbourhood_supply_growth_365 |     0.06  |   0.078 |
| price_rel_neighbourhood_median  |     0.011 |   0.171 |
