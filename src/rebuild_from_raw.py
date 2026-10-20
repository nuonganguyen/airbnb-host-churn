"""Re-read price and host fields from the raw listings CSVs (read-only).

One small Parquet per snapshot file goes to data_local/raw_fields/, so the run
can be interrupted and resumed. Values are parsed the way
iadb_engineer/09_formCuratedViews.R intended, minus its bugs: commas are
stripped from prices, and '' / 'NA' / 'N/A' become NULL instead of 0.
Only host_since, host_response_time and the two rates are rebuilt: those are
the host fields lost in the Dec 2025+ batch; the rest are intact.

    python src/rebuild_from_raw.py
"""
import sqlite3
import time

import duckdb
import pandas as pd

from db import CITIES, LOCAL, SOURCE_DB, SOURCE_DIR

OUT = LOCAL / "raw_fields"
EXTRACT = LOCAL / "listings_6city.parquet"

# curated column <- raw column (NULL when a raw file lacks it)
# only the columns the curated table gets wrong; other host fields are intact
RAW_COLS = ["id", "price", "host_id", "host_since", "host_response_time", "host_response_rate",
            "host_acceptance_rate"]


def snapshot_files(con):
    ro = sqlite3.connect(f"file:{SOURCE_DB}?mode=ro", uri=True)
    meta = pd.read_sql(f"""SELECT FILE_ID, FILE_NAME, LOC, EXT FROM [META.V_FILE_INFO]
                           WHERE TYPE = 'listings' AND LOC IN ({",".join("?" * len(CITIES))})""",
                       ro, params=list(CITIES.values()))
    ro.close()
    meta["FILE_ID"] = meta["FILE_ID"].astype(str)
    loaded = set(con.execute(f"SELECT DISTINCT KEY_FILE FROM '{EXTRACT}'").df()["KEY_FILE"])
    return meta[meta["FILE_ID"].isin(loaded)].sort_values("FILE_ID")


def text(col):
    # raw files written by R spell missing as 'NA'
    return f"NULLIF(NULLIF(TRIM({col}), ''), 'NA')"


def pct(col):
    return f"TRY_CAST(REPLACE(NULLIF({text(col)}, 'N/A'), '%', '') AS DOUBLE) / 100.0"


def rebuild_file(con, f):
    path = SOURCE_DIR / "raw" / f.LOC / f.FILE_NAME
    delim = "\\t" if f.EXT == "tsv" else ","
    con.execute(f"""CREATE OR REPLACE TEMP TABLE r AS
                    SELECT *, row_number() OVER () AS rn
                    FROM read_csv('{path}', all_varchar = true, header = true,
                                  delim = '{delim}', quote = '"', escape = '"',
                                  strict_mode = false, ignore_errors = true)""")
    have = set(con.execute("SELECT * FROM r LIMIT 0").df().columns)
    col = {c: (c if c in have else "NULL::VARCHAR") for c in RAW_COLS}
    con.execute(f"""
        COPY (
            WITH listing AS (
                SELECT DISTINCT ON (TRY_CAST({col['id']} AS BIGINT))
                       TRY_CAST({col['id']} AS BIGINT) AS list_id,
                       TRY_CAST({col['host_id']} AS BIGINT) AS host_id,
                       TRY_CAST(regexp_replace({text(col['price'])}, '[$,]', '', 'g') AS DOUBLE) AS price,
                       rn
                FROM r WHERE TRY_CAST({col['id']} AS BIGINT) IS NOT NULL
                ORDER BY TRY_CAST({col['id']} AS BIGINT), rn
            ),
            host AS (  -- pipeline keeps the first row per host per file
                SELECT DISTINCT ON (TRY_CAST({col['host_id']} AS BIGINT))
                       TRY_CAST({col['host_id']} AS BIGINT) AS host_id,
                       {text(col['host_since'])} AS host_since,
                       {text(col['host_response_time'])} AS host_response_time,
                       {pct(col['host_response_rate'])} AS host_response_rate,
                       {pct(col['host_acceptance_rate'])} AS host_accept_rate
                FROM r WHERE TRY_CAST({col['host_id']} AS BIGINT) IS NOT NULL
                ORDER BY TRY_CAST({col['host_id']} AS BIGINT), rn
            )
            SELECT '{f.FILE_ID}' AS KEY_FILE, l.list_id, l.price, h.* EXCLUDE (host_id)
            FROM listing l LEFT JOIN host h USING (host_id)
        ) TO '{OUT / (f.FILE_ID + ".parquet")}' (FORMAT parquet)
    """)
    dups = con.execute(f"SELECT COUNT(*) - COUNT(DISTINCT TRY_CAST({col['id']} AS BIGINT)) FROM r "
                       f"WHERE TRY_CAST({col['id']} AS BIGINT) IS NOT NULL").fetchone()[0]
    return dups, sorted(set(RAW_COLS) - have)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    files = snapshot_files(con)
    log = []
    start = time.time()
    for i, f in enumerate(files.itertuples(), 1):
        if (OUT / f"{f.FILE_ID}.parquet").exists():
            continue
        dups, absent = rebuild_file(con, f)
        log.append({"KEY_FILE": f.FILE_ID, "file": f.FILE_NAME, "duplicate_ids": dups,
                    "absent_cols": ",".join(absent)})
        print(f"[{i}/{len(files)}] {f.FILE_NAME}  dup_ids={dups}  absent={absent or '-'}  "
              f"{time.time() - start:.0f}s", flush=True)
    if log:
        pd.DataFrame(log).to_csv(LOCAL / "validation" / "rebuild_log.csv", index=False,
                                 mode="a", header=not (LOCAL / "validation" / "rebuild_log.csv").exists())
    print(f"done: {len(list(OUT.glob('*.parquet')))} of {len(files)} files rebuilt")


if __name__ == "__main__":
    main()
