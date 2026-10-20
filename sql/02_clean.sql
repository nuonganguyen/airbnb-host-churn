-- Corrected copy of the 6-city extract. Replaces the columns the curated table
-- gets wrong with values re-read from the raw CSVs (src/rebuild_from_raw.py):
--   price               commas stripped, so $1,000+ no longer truncates to 1, 2, ...
--   host_response_rate  raw 'N/A' / empty -> NULL instead of 0
--   host_accept_rate    same
--   last_scraped, scrape_source, neighbourhood, id_imprecise: raw fields the curated
--                       table never extracted (actual collection date; 'city scrape' /
--                       'previous scrape'; neighbourhood_cleansed; scientific-notation id)
--   host_since          carried forward from the host's earlier snapshots where the
--                       source has 'NA' (every snapshot from Dec 2025 on); backward
--                       only, so no future information leaks into a row
-- Keeps the extract's schema (all VARCHAR) and adds price_fixed, rate_fixed and
-- host_since_filled flags. Neither the extract nor the source is modified.
COPY (
    WITH joined AS (
        SELECT e.*,
               r.price AS raw_price,
               r.host_response_rate AS raw_resp,
               r.host_accept_rate AS raw_acc,
               r.last_scraped,
               r.source AS scrape_source,
               r.neighbourhood,
               COALESCE(r.id_imprecise, false) AS id_imprecise,
               r.KEY_FILE IS NOT NULL AS has_raw
        FROM 'data_local/listings_6city.parquet' e
        LEFT JOIN 'data_local/raw_fields/*.parquet' r
               ON r.KEY_FILE = e.KEY_FILE AND r.list_id = TRY_CAST(e.KEY_LIST_ID AS BIGINT)
    ),
    filled AS (
        SELECT *,
               LAST_VALUE(NULLIF(host_since, '') IGNORE NULLS) OVER (
                   PARTITION BY KEY_HOST_ID ORDER BY DATE
                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS host_since_ff
        FROM joined
    )
    SELECT * EXCLUDE (raw_price, raw_resp, raw_acc, has_raw, host_since_ff) REPLACE (
               CASE WHEN has_raw THEN CAST(raw_price AS VARCHAR) ELSE price END AS price,
               CASE WHEN has_raw THEN CAST(raw_resp AS VARCHAR) ELSE host_response_rate END AS host_response_rate,
               CASE WHEN has_raw THEN CAST(raw_acc AS VARCHAR) ELSE host_accept_rate END AS host_accept_rate,
               COALESCE(NULLIF(host_since, ''), host_since_ff) AS host_since
           ),
           has_raw AND TRY_CAST(price AS DOUBLE) IS DISTINCT FROM raw_price AS price_fixed,
           has_raw AND COALESCE(
               (TRY_CAST(host_response_rate AS DOUBLE) IS NULL) <> (raw_resp IS NULL)
               OR abs(TRY_CAST(host_response_rate AS DOUBLE) - raw_resp) > 1e-9
               OR (TRY_CAST(host_accept_rate AS DOUBLE) IS NULL) <> (raw_acc IS NULL)
               OR abs(TRY_CAST(host_accept_rate AS DOUBLE) - raw_acc) > 1e-9, false) AS rate_fixed,
           NULLIF(host_since, '') IS NULL AND host_since_ff IS NOT NULL AS host_since_filled
    FROM filled
) TO 'data_local/listings_6city_clean.parquet' (FORMAT parquet, COMPRESSION zstd);
