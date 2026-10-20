-- Listing features at each prediction date, per docs/feature_spec.md.
-- Input: lf (typed listing snapshots, all columns), plus schedule and prediction_dates
--        from sql/03_label.sql. Parameters: lag_tol_days, new_min_coverage_days.
-- Output: features, one row per (city_id, list_id, t) for every listing present at t.
-- t keys the snapshot (its file date); decision_date is when that snapshot was fully
-- collected. Every row uses the snapshot at t plus history snapshots dated before t
-- whose usable status was known by decision_date, so data arriving later cannot change it.
-- Durations ("days since") are measured from decision_date.
-- Raw values only: caps, imputation, scaling and encoding are fitted per training fold.

-- 1. Snapshots usable as history at t
CREATE OR REPLACE TABLE history AS
SELECT p.city_id, p.t, s.snap
FROM prediction_dates p
JOIN schedule s ON s.city_id = p.city_id AND s.snap < p.t
WHERE s.status IN ('ok', 'insufficient_history', 'suspected_contraction')
  AND s.status_known_at <= p.decision_date;

-- 2. Lag anchors: the history snapshot nearest t-90 and t-365 days (ties -> earlier)
CREATE OR REPLACE TABLE anchors AS
WITH candidates AS (
    SELECT h.city_id, h.t, k.lag, h.snap,
           abs(datediff('day', h.t - k.days, h.snap)) AS distance
    FROM history h
    CROSS JOIN (VALUES ('lag90', 90), ('lag365', 365)) AS k(lag, days)
)
SELECT city_id, t, lag, snap
FROM candidates
WHERE distance <= getvariable('lag_tol_days')
QUALIFY row_number() OVER (PARTITION BY city_id, t, lag ORDER BY distance, snap) = 1;

-- 3. Per-snapshot aggregates; each uses only its own snapshot's rows
CREATE OR REPLACE TABLE snap_market AS
SELECT city_id, snap, COUNT(*) AS n_listings FROM lf GROUP BY ALL;

CREATE OR REPLACE TABLE snap_room AS
SELECT city_id, snap, room_type, median(price) AS median_price FROM lf GROUP BY ALL;

CREATE OR REPLACE TABLE snap_neighbourhood AS
SELECT city_id, snap, neighbourhood, COUNT(*) AS n_listings, median(price) AS median_price FROM lf GROUP BY ALL;

CREATE OR REPLACE TABLE snap_host AS
SELECT city_id, snap, host_id, COUNT(*) AS n_listings FROM lf GROUP BY ALL;

-- 4. Presence over the past year: share of usable history snapshots with the listing
CREATE OR REPLACE TABLE presence AS
SELECT c.city_id, c.t, c.list_id,
       COUNT(h.snap) AS hist_snapshots_365,
       COUNT(x.list_id) AS hist_present_365
FROM (SELECT p.city_id, p.t, l.list_id
      FROM prediction_dates p JOIN lf l ON l.city_id = p.city_id AND l.snap = p.t) c
LEFT JOIN history h ON h.city_id = c.city_id AND h.t = c.t AND h.snap >= c.t - 365
LEFT JOIN lf x ON x.city_id = c.city_id AND x.snap = h.snap AND x.list_id = c.list_id
GROUP BY ALL;

-- 5. One row per listing present at a prediction date
CREATE OR REPLACE TABLE features AS
WITH cur AS (
    SELECT l.*, p.decision_date,
           percent_rank() OVER (PARTITION BY l.city_id, l.snap ORDER BY l.amenity_count) AS amenity_count_pct
    FROM prediction_dates p JOIN lf l ON l.city_id = p.city_id AND l.snap = p.t
),
-- the listing is present at t, so its earliest snapshot is on or before t
first_seen AS (SELECT city_id, list_id, MIN(snap) AS first_observed FROM lf GROUP BY ALL),
coverage AS (SELECT city_id, MIN(snap) AS coverage_start FROM lf GROUP BY ALL),
a90 AS (SELECT city_id, t, snap FROM anchors WHERE lag = 'lag90'),
a365 AS (SELECT city_id, t, snap FROM anchors WHERE lag = 'lag365'),
lagged AS (SELECT city_id, snap, list_id, price, available_365, overall_rating, number_of_reviews FROM lf)
SELECT
    -- keys and metadata, not predictors
    c.city_id, c.list_id, c.snap AS t, c.decision_date, c.host_id AS host_id_at_t,
    a90.snap AS lag90_snap, a365.snap AS lag365_snap,

    -- state at t
    c.price, c.price IS NULL AS price_missing,
    c.capacity, c.bathrooms, c.bedrooms, c.beds, c.room_type, c.listing_type,
    c.min_night, c.max_night,
    c.available_030, c.available_060, c.available_090, c.available_365,
    c.number_of_reviews,
    c.overall_rating, c.accom_rating, c.clean_rating, c.checkin_rating,
    c.com_rating, c.loc_rating, c.value_rating,
    c.amenity_count, c.amenity_count_pct, c.descrip_word_count, c.host_about_word_count,
    c.host_is_superhost, c.host_listing_count, c.host_has_pic, c.host_verified,

    -- tenure and recency, in days before the decision date
    datediff('day', fs.first_observed, c.decision_date) AS days_since_first_observed,
    datediff('day', cv.coverage_start, fs.first_observed) < getvariable('new_min_coverage_days')
        AS first_observed_censored,
    datediff('day', c.host_since, c.decision_date) AS host_tenure_days,
    datediff('day', c.last_review_date, c.decision_date) AS days_since_last_review,
    datediff('day', c.first_review_date, c.decision_date) AS days_since_first_review,

    -- change since the ~90-day anchor; elapsed time explicit, rates per 30 days
    datediff('day', a90.snap, c.snap) AS lag90_days,
    CASE WHEN a90.snap IS NOT NULL THEN x90.list_id IS NOT NULL END AS present_lag90,
    c.price / NULLIF(x90.price, 0) - 1 AS price_change_90,
    c.available_365 - x90.available_365 AS avail365_change_90,
    c.overall_rating - x90.overall_rating AS rating_change_90,
    c.number_of_reviews - x90.number_of_reviews AS reviews_added_90,
    30.0 * (c.number_of_reviews - x90.number_of_reviews) / datediff('day', a90.snap, c.snap) AS review_rate_90,
    c.number_of_reviews < x90.number_of_reviews AS reviews_decreased_90,

    -- change since the ~365-day anchor
    datediff('day', a365.snap, c.snap) AS lag365_days,
    CASE WHEN a365.snap IS NOT NULL THEN x365.list_id IS NOT NULL END AS present_lag365,
    c.price / NULLIF(x365.price, 0) - 1 AS price_change_365,
    c.number_of_reviews - x365.number_of_reviews AS reviews_added_365,
    30.0 * (c.number_of_reviews - x365.number_of_reviews) / datediff('day', a365.snap, c.snap) AS review_rate_365,

    -- presence over the past year
    pr.hist_snapshots_365,
    pr.hist_present_365,
    pr.hist_present_365 / NULLIF(pr.hist_snapshots_365, 0) AS presence_rate_365,

    -- the host's portfolio in this city
    hc.n_listings AS host_n_listings,
    CASE WHEN a90.snap IS NOT NULL THEN hc.n_listings - COALESCE(h90.n_listings, 0) END AS host_listings_change_90,

    -- market at t, and growth since the ~365-day anchor (usable snapshots only)
    m.n_listings AS city_n_listings,
    m.n_listings / m365.n_listings - 1 AS city_supply_growth_365,
    c.price / NULLIF(rm.median_price, 0) AS price_rel_room_median,
    nb.n_listings AS neighbourhood_n_listings,
    nb.n_listings / nb365.n_listings - 1 AS neighbourhood_supply_growth_365,
    c.price / NULLIF(nb.median_price, 0) AS price_rel_neighbourhood_median,
    quarter(c.snap) AS quarter_of_year
FROM cur c
JOIN first_seen fs ON fs.city_id = c.city_id AND fs.list_id = c.list_id
JOIN coverage cv ON cv.city_id = c.city_id
LEFT JOIN a90 ON a90.city_id = c.city_id AND a90.t = c.snap
LEFT JOIN lagged x90 ON x90.city_id = c.city_id AND x90.snap = a90.snap AND x90.list_id = c.list_id
LEFT JOIN a365 ON a365.city_id = c.city_id AND a365.t = c.snap
LEFT JOIN lagged x365 ON x365.city_id = c.city_id AND x365.snap = a365.snap AND x365.list_id = c.list_id
LEFT JOIN presence pr ON pr.city_id = c.city_id AND pr.t = c.snap AND pr.list_id = c.list_id
LEFT JOIN snap_host hc ON hc.city_id = c.city_id AND hc.snap = c.snap AND hc.host_id = c.host_id
LEFT JOIN snap_host h90 ON h90.city_id = c.city_id AND h90.snap = a90.snap AND h90.host_id = c.host_id
JOIN snap_market m ON m.city_id = c.city_id AND m.snap = c.snap
LEFT JOIN snap_market m365 ON m365.city_id = c.city_id AND m365.snap = a365.snap
LEFT JOIN snap_room rm ON rm.city_id = c.city_id AND rm.snap = c.snap AND rm.room_type = c.room_type
LEFT JOIN snap_neighbourhood nb ON nb.city_id = c.city_id AND nb.snap = c.snap
                                AND nb.neighbourhood = c.neighbourhood
LEFT JOIN snap_neighbourhood nb365 ON nb365.city_id = c.city_id AND nb365.snap = a365.snap
                                   AND nb365.neighbourhood = c.neighbourhood;
