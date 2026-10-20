-- Pull the 6 study markets out of the curated table into one local Parquet file.
-- Source is attached READ_ONLY (src/db.py); the only write is to data_local/.
-- Full scan of the 141 GB table (it has no indexes), so this runs once.
-- Columns arrive as text; typing happens in 02_clean.sql.
COPY (
    SELECT *
    FROM ia."CURATED.TAB_LISTING_ANALYTICS"
    WHERE TRY_CAST(CITY_ID AS DOUBLE)::INTEGER IN (11, 19, 24, 25, 33, 38)
) TO 'data_local/listings_6city.parquet' (FORMAT parquet, COMPRESSION zstd);
