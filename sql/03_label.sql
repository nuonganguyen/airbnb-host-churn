-- Listing absence labels, per docs/label_spec.md (v3).
-- Input: table ls(city_id, snap, list_id, host_id, last_review_date, overall_rating,
--        number_of_reviews), one row per listing per snapshot.
-- Parameters: DuckDB variables set by src/label.py (tol_days, anomaly_ratio, ...).
--   as_of: the date the data is current to (NULL -> each city's latest snapshot).
-- Output tables: schedule, prediction_dates, checkpoints, labels.

-- 1. Operational observation schedule. Every status records when it became known
--    (status_known_at); nothing uses data from after that date.
CREATE OR REPLACE TABLE schedule AS
WITH counts AS (
    SELECT city_id, snap, COUNT(*) AS n_listings FROM ls GROUP BY ALL
),
ordered AS (
    SELECT *,
           COUNT(*) OVER (PARTITION BY city_id ORDER BY snap
                          ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS n_prior,
           median(n_listings) OVER (PARTITION BY city_id ORDER BY snap
                                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS trailing_median,
           COALESCE(getvariable('as_of'), MAX(snap) OVER (PARTITION BY city_id)) AS as_of
    FROM counts
),
flags AS (
    SELECT *,
           n_prior >= 3 AND n_listings < getvariable('anomaly_ratio') * trailing_median AS anomaly
    FROM ordered
),
-- reference: the latest unflagged snapshot before a flagged one
reference AS (
    SELECT f.city_id, f.snap, MAX(r.snap) AS reference_snap
    FROM flags f JOIN flags r ON r.city_id = f.city_id AND r.snap < f.snap AND NOT r.anomaly
    WHERE f.anomaly
    GROUP BY ALL
),
-- resolver: the earliest later snapshot that is itself unflagged, within the wait limit
resolver AS (
    SELECT f.city_id, f.snap, MIN(r.snap) AS resolver_snap
    FROM flags f JOIN flags r ON r.city_id = f.city_id AND r.snap > f.snap AND NOT r.anomaly
                             AND r.n_prior >= 3 AND r.snap <= f.snap + getvariable('resolve_max_days')
    WHERE f.anomaly
    GROUP BY ALL
),
-- listings in the reference snapshot but missing from the flagged one, and how many
-- are back at the resolver
gone AS (
    SELECT rf.city_id, rf.snap, COUNT(*) AS n_missing, COUNT(bk.list_id) AS n_returned
    FROM reference rf
    LEFT JOIN resolver rv ON rv.city_id = rf.city_id AND rv.snap = rf.snap
    JOIN ls a ON a.city_id = rf.city_id AND a.snap = rf.reference_snap
    LEFT JOIN ls cur ON cur.city_id = rf.city_id AND cur.snap = rf.snap AND cur.list_id = a.list_id
    LEFT JOIN ls bk ON bk.city_id = rf.city_id AND bk.snap = rv.resolver_snap AND bk.list_id = a.list_id
    WHERE cur.list_id IS NULL
    GROUP BY ALL
),
resolved AS (
    SELECT f.*,
           f.n_listings / f.trailing_median AS trailing_ratio,
           rf.reference_snap, rv.resolver_snap,
           COALESCE(g.n_missing, 0) AS n_missing,
           CASE WHEN rv.resolver_snap IS NOT NULL THEN g.n_returned / NULLIF(g.n_missing, 0) END AS return_rate
    FROM flags f
    LEFT JOIN reference rf USING (city_id, snap)
    LEFT JOIN resolver rv USING (city_id, snap)
    LEFT JOIN gone g USING (city_id, snap)
)
SELECT *,
       CASE WHEN n_prior < 3 THEN 'insufficient_history'
            WHEN NOT anomaly THEN 'ok'
            WHEN resolver_snap IS NOT NULL
                 AND COALESCE(return_rate, 0) >= getvariable('return_threshold') THEN 'partial_scrape'
            WHEN resolver_snap IS NOT NULL THEN 'suspected_contraction'
            WHEN as_of >= snap + getvariable('resolve_max_days') THEN 'anomaly_unresolved'
            ELSE 'anomaly_pending' END AS status,
       status IN ('ok', 'suspected_contraction') AS usable_checkpoint,
       CASE WHEN status IN ('ok', 'insufficient_history') THEN snap
            WHEN status IN ('partial_scrape', 'suspected_contraction') THEN resolver_snap
            WHEN status = 'anomaly_unresolved' THEN snap + getvariable('resolve_max_days')
       END AS status_known_at
FROM resolved;

-- 2. Prediction dates: earliest 'ok' snapshot per city and calendar quarter. Flagged
--    snapshots are excluded because their status is unknown at decision time.
CREATE OR REPLACE TABLE prediction_dates AS
SELECT city_id, snap AS t
FROM schedule
WHERE status = 'ok'
QUALIFY row_number() OVER (PARTITION BY city_id, date_trunc('quarter', snap) ORDER BY snap) = 1;

-- 3. Checkpoints, once per city and prediction date: nearest usable snapshot within
--    tolerance (ties -> earlier date); C3 strictly after C2; C1 independent.
--    A checkpoint is final once its window has closed and every snapshot that would
--    outrank the pick, were it usable, has a known status.
CREATE OR REPLACE TABLE checkpoints AS
WITH targets AS (
    SELECT p.city_id, p.t, k.checkpoint, p.t + k.days AS target,
           p.t + k.days + getvariable('tol_days') AS window_closes
    FROM prediction_dates p
    CROSS JOIN (VALUES ('c1', 90), ('c2', 180), ('c3', 270)) AS k(checkpoint, days)
),
win AS (
    SELECT tg.city_id, tg.t, tg.checkpoint, s.snap, s.usable_checkpoint, s.status_known_at,
           abs(datediff('day', tg.target, s.snap)) AS distance
    FROM targets tg
    JOIN schedule s ON s.city_id = tg.city_id AND s.snap > tg.t
    WHERE abs(datediff('day', tg.target, s.snap)) <= getvariable('tol_days')
),
pick12 AS (
    SELECT * FROM win
    WHERE checkpoint IN ('c1', 'c2') AND usable_checkpoint
    QUALIFY row_number() OVER (PARTITION BY city_id, t, checkpoint ORDER BY distance, snap) = 1
),
win3 AS (
    SELECT w.*
    FROM win w
    LEFT JOIN pick12 c2 ON c2.city_id = w.city_id AND c2.t = w.t AND c2.checkpoint = 'c2'
    WHERE w.checkpoint = 'c3' AND (c2.snap IS NULL OR w.snap > c2.snap)
),
pick3 AS (
    SELECT * FROM win3
    WHERE usable_checkpoint
    QUALIFY row_number() OVER (PARTITION BY city_id, t ORDER BY distance, snap) = 1
),
picks AS (SELECT * FROM pick12 UNION ALL SELECT * FROM pick3),
-- unusable snapshots that would beat the pick if they turned out usable
blockers AS (
    SELECT w.city_id, w.t, w.checkpoint, w.status_known_at
    FROM (SELECT * FROM win WHERE checkpoint IN ('c1', 'c2') UNION ALL SELECT * FROM win3) w
    LEFT JOIN picks pk ON pk.city_id = w.city_id AND pk.t = w.t AND pk.checkpoint = w.checkpoint
    WHERE NOT w.usable_checkpoint
      AND (pk.snap IS NULL OR w.distance < pk.distance OR (w.distance = pk.distance AND w.snap < pk.snap))
),
final AS (
    SELECT tg.city_id, tg.t, tg.checkpoint, pk.snap,
           CASE WHEN COUNT(b.city_id) FILTER (WHERE b.status_known_at IS NULL) > 0 THEN NULL
                ELSE greatest(tg.window_closes,
                              COALESCE(pk.status_known_at, tg.window_closes),
                              COALESCE(MAX(b.status_known_at), tg.window_closes)) END AS final_at
    FROM targets tg
    LEFT JOIN picks pk ON pk.city_id = tg.city_id AND pk.t = tg.t AND pk.checkpoint = tg.checkpoint
    LEFT JOIN blockers b ON b.city_id = tg.city_id AND b.t = tg.t AND b.checkpoint = tg.checkpoint
    GROUP BY tg.city_id, tg.t, tg.checkpoint, tg.window_closes, pk.snap, pk.status_known_at
),
as_of AS (SELECT city_id, ANY_VALUE(as_of) AS as_of FROM schedule GROUP BY 1)
SELECT p.city_id, p.t,
       f1.snap AS c1, f2.snap AS c2, f3.snap AS c3,
       datediff('day', p.t, f1.snap) AS c1_offset,
       datediff('day', p.t, f2.snap) AS c2_offset,
       datediff('day', p.t, f3.snap) AS c3_offset,
       CASE WHEN f2.snap IS NULL AND f3.snap IS NULL THEN 'no_c2_c3'
            WHEN f2.snap IS NULL THEN 'no_c2'
            WHEN f3.snap IS NULL THEN 'no_c3'
            ELSE 'ok' END AS followup_reason,
       f2.final_at AS c2_final_at,
       f3.final_at AS c3_final_at,
       -- C3's candidates depend on C2, so C3 is final no earlier than C2
       CASE WHEN f2.final_at IS NOT NULL AND f3.final_at IS NOT NULL
            THEN greatest(f2.final_at, f3.final_at) END AS label_final_at,
       a.as_of,
       COALESCE(label_final_at <= a.as_of, false) AS label_final
FROM prediction_dates p
JOIN as_of a ON a.city_id = p.city_id
LEFT JOIN final f1 ON f1.city_id = p.city_id AND f1.t = p.t AND f1.checkpoint = 'c1'
LEFT JOIN final f2 ON f2.city_id = p.city_id AND f2.t = p.t AND f2.checkpoint = 'c2'
LEFT JOIN final f3 ON f3.city_id = p.city_id AND f3.t = p.t AND f3.checkpoint = 'c3';

-- 4. Listing labels and population flags. Everything except the outcome uses only
--    information available at t. Provisional labels must not be used for training.
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
       CASE WHEN label_final THEN 'final' ELSE 'provisional' END AS label_status,
       COALESCE(last_review_date >= t - getvariable('active_review_days'), false) AS active_review,
       first_observed >= t - getvariable('new_window_days') AS recently_first_observed,
       datediff('day', coverage_start, first_observed) >= getvariable('new_min_coverage_days') AS newness_known,
       COALESCE(overall_rating < getvariable('low_rating')
                AND number_of_reviews >= getvariable('low_rating_min_reviews'), false) AS low_quality,
       (active_review OR (recently_first_observed AND newness_known)) AND NOT low_quality AS eligible_main
FROM base;
