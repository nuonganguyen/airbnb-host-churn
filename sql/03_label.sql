-- Listing absence labels, per docs/label_spec.md (v2).
-- Input: table ls(city_id, snap, list_id, host_id, last_review_date, overall_rating,
--        number_of_reviews), one row per listing per snapshot.
-- Parameters: DuckDB variables set by src/label.py (tol_days, anomaly_ratio, ...).
-- Output tables: schedule, prediction_dates, checkpoints, labels.

-- 1. Operational observation schedule. A snapshot's status uses only snapshots up to
--    the date that status becomes known (status_known_at).
CREATE OR REPLACE TABLE schedule AS
WITH counts AS (
    SELECT city_id, snap, COUNT(*) AS n_listings FROM ls GROUP BY ALL
),
ordered AS (
    SELECT *,
           LAG(snap) OVER (PARTITION BY city_id ORDER BY snap) AS prev_snap,
           LEAD(snap) OVER (PARTITION BY city_id ORDER BY snap) AS next_snap,
           COUNT(*) OVER (PARTITION BY city_id ORDER BY snap
                          ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS n_prior,
           median(n_listings) OVER (PARTITION BY city_id ORDER BY snap
                                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS trailing_median
    FROM counts
),
-- listings present at the previous snapshot but missing from this one, and how many
-- are back at the next snapshot (known only once the next snapshot exists)
gone AS (
    SELECT o.city_id, o.snap, COUNT(*) AS n_missing, COUNT(nx.list_id) AS n_returned
    FROM ordered o
    JOIN ls pv ON pv.city_id = o.city_id AND pv.snap = o.prev_snap
    LEFT JOIN ls cur ON cur.city_id = o.city_id AND cur.snap = o.snap AND cur.list_id = pv.list_id
    LEFT JOIN ls nx ON nx.city_id = o.city_id AND nx.snap = o.next_snap AND nx.list_id = pv.list_id
    WHERE cur.list_id IS NULL
    GROUP BY ALL
),
flagged AS (
    SELECT o.*,
           o.n_listings / o.trailing_median AS trailing_ratio,
           COALESCE(g.n_missing, 0) AS n_missing,
           g.n_returned / NULLIF(g.n_missing, 0) AS return_rate,
           o.n_prior >= 3
               AND o.n_listings < getvariable('anomaly_ratio') * o.trailing_median AS anomaly
    FROM ordered o
    LEFT JOIN gone g USING (city_id, snap)
)
SELECT *,
       CASE WHEN n_prior < 3 THEN 'insufficient_history'
            WHEN NOT anomaly THEN 'ok'
            WHEN next_snap IS NULL THEN 'anomaly_unresolved'
            WHEN COALESCE(return_rate, 0) >= getvariable('return_threshold') THEN 'partial_scrape'
            ELSE 'anomaly_genuine' END AS status,
       status IN ('ok', 'anomaly_genuine') AS usable_checkpoint,
       CASE status WHEN 'ok' THEN snap WHEN 'anomaly_genuine' THEN next_snap END AS status_known_at
FROM flagged;

-- 2. Prediction dates: earliest 'ok' snapshot per city and calendar quarter. Flagged
--    snapshots are excluded because their status is unknown at decision time.
CREATE OR REPLACE TABLE prediction_dates AS
SELECT city_id, snap AS t
FROM schedule
WHERE status = 'ok'
QUALIFY row_number() OVER (PARTITION BY city_id, date_trunc('quarter', snap) ORDER BY snap) = 1;

-- 3. Checkpoints, once per city and prediction date: nearest usable snapshot within
--    tolerance (ties -> earlier date); C3 strictly after C2; C1 independent.
CREATE OR REPLACE TABLE checkpoints AS
WITH targets AS (
    SELECT p.city_id, p.t, k.checkpoint, p.t + k.days AS target
    FROM prediction_dates p
    CROSS JOIN (VALUES ('c1', 90), ('c2', 180), ('c3', 270)) AS k(checkpoint, days)
),
candidates AS (
    SELECT tg.*, s.snap, s.status_known_at, abs(datediff('day', tg.target, s.snap)) AS distance
    FROM targets tg
    JOIN schedule s ON s.city_id = tg.city_id AND s.usable_checkpoint AND s.snap > tg.t
    WHERE abs(datediff('day', tg.target, s.snap)) <= getvariable('tol_days')
),
nearest AS (
    SELECT * FROM candidates
    WHERE checkpoint IN ('c1', 'c2')
    QUALIFY row_number() OVER (PARTITION BY city_id, t, checkpoint ORDER BY distance, snap) = 1
),
c3 AS (
    SELECT cd.*
    FROM candidates cd
    LEFT JOIN nearest c2 ON c2.city_id = cd.city_id AND c2.t = cd.t AND c2.checkpoint = 'c2'
    WHERE cd.checkpoint = 'c3' AND (c2.snap IS NULL OR cd.snap > c2.snap)
    QUALIFY row_number() OVER (PARTITION BY cd.city_id, cd.t ORDER BY cd.distance, cd.snap) = 1
)
SELECT p.city_id, p.t,
       c1.snap AS c1, c2.snap AS c2, c3.snap AS c3,
       datediff('day', p.t, c1.snap) AS c1_offset,
       datediff('day', p.t, c2.snap) AS c2_offset,
       datediff('day', p.t, c3.snap) AS c3_offset,
       CASE WHEN c2.snap IS NULL AND c3.snap IS NULL THEN 'no_c2_c3'
            WHEN c2.snap IS NULL THEN 'no_c2'
            WHEN c3.snap IS NULL THEN 'no_c3'
            ELSE 'ok' END AS followup_reason,
       CASE WHEN c2.snap IS NOT NULL AND c3.snap IS NOT NULL
            THEN greatest(c2.status_known_at, c3.status_known_at) END AS label_available_at
FROM prediction_dates p
LEFT JOIN nearest c1 ON c1.city_id = p.city_id AND c1.t = p.t AND c1.checkpoint = 'c1'
LEFT JOIN nearest c2 ON c2.city_id = p.city_id AND c2.t = p.t AND c2.checkpoint = 'c2'
LEFT JOIN c3 ON c3.city_id = p.city_id AND c3.t = p.t;

-- 4. Listing labels and population flags. Everything except the outcome uses only
--    information available at t.
CREATE OR REPLACE TABLE labels AS
WITH first_seen AS (
    SELECT city_id, list_id, MIN(snap) AS first_observed FROM ls GROUP BY ALL
),
coverage AS (
    SELECT city_id, MIN(snap) AS coverage_start FROM ls GROUP BY ALL
),
base AS (
    SELECT cp.*, l.list_id, l.host_id AS host_at_t,
           l.last_review_date, l.overall_rating, l.number_of_reviews,
           f.first_observed, cv.coverage_start,
           CASE WHEN cp.c1 IS NOT NULL THEN x1.list_id IS NOT NULL END AS in_c1,
           CASE WHEN cp.c2 IS NOT NULL THEN x2.list_id IS NOT NULL END AS in_c2,
           CASE WHEN cp.c3 IS NOT NULL THEN x3.list_id IS NOT NULL END AS in_c3,
           COALESCE(x2.host_id <> l.host_id, false) OR COALESCE(x3.host_id <> l.host_id, false) AS host_changed
    FROM checkpoints cp
    JOIN ls l ON l.city_id = cp.city_id AND l.snap = cp.t
    JOIN first_seen f ON f.city_id = l.city_id AND f.list_id = l.list_id
    JOIN coverage cv ON cv.city_id = l.city_id
    LEFT JOIN ls x1 ON x1.city_id = cp.city_id AND x1.snap = cp.c1 AND x1.list_id = l.list_id
    LEFT JOIN ls x2 ON x2.city_id = cp.city_id AND x2.snap = cp.c2 AND x2.list_id = l.list_id
    LEFT JOIN ls x3 ON x3.city_id = cp.city_id AND x3.snap = cp.c3 AND x3.list_id = l.list_id
)
SELECT *,
       CASE WHEN c2 IS NULL OR c3 IS NULL THEN 'insufficient_followup'
            WHEN NOT in_c2 AND NOT in_c3 THEN 'absent_confirmed'
            ELSE 'observed' END AS outcome,
       COALESCE(last_review_date >= t - getvariable('active_review_days'), false) AS active_review,
       first_observed >= t - getvariable('new_window_days') AS recently_first_observed,
       datediff('day', coverage_start, first_observed) >= getvariable('new_min_coverage_days') AS newness_known,
       COALESCE(overall_rating < getvariable('low_rating')
                AND number_of_reviews >= getvariable('low_rating_min_reviews'), false) AS low_quality,
       (active_review OR (recently_first_observed AND newness_known)) AND NOT low_quality AS eligible_main
FROM base;
