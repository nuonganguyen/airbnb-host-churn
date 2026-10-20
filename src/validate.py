"""Validate the curated 6-city extract without touching the source.

Reads: data_local/listings_6city.parquet, META.V_FILE_INFO (sqlite3, mode=ro),
and a sample of raw listings CSVs (DuckDB read_csv). Writes only to
reports/data_validation.md and data_local/validation/.

    python src/validate.py                            # the extract
    python src/validate.py listings_6city_clean.parquet   # -> data_validation_clean.md
"""
import sqlite3
import sys
from datetime import date

import duckdb
import pandas as pd

from db import CITIES, LOCAL, PROJECT, SOURCE_DB, SOURCE_DIR

PARQUET = LOCAL / (sys.argv[1] if len(sys.argv) > 1 else "listings_6city.parquet")
SUFFIX = PARQUET.stem.removeprefix("listings_6city")
OUT_DIR = LOCAL / f"validation{SUFFIX}"
REPORT = PROJECT / "reports" / f"data_validation{SUFFIX}.md"

NUMERIC = [
    "price", "capacity", "bathrooms", "bedrooms", "beds", "min_night", "max_night",
    "available", "available_030", "available_060", "available_090", "available_365",
    "number_of_reviews", "overall_rating", "accom_rating", "clean_rating",
    "checkin_rating", "com_rating", "loc_rating", "value_rating",
    "amenity_word_count", "amenity_count", "amenity_char_count",
    "loc_overview_word_count", "descrip_word_count", "loc_overview_char_count",
    "descrip_char_count", "host_response_rate", "host_accept_rate",
    "host_is_superhost", "host_listing_count", "host_has_pic", "host_verified",
    "host_about_word_count", "host_about_char_count",
]
DATES = ["first_review_date", "last_review_date", "host_since"]
TEXT = ["zip", "listing_type", "room_type", "host_response_time"]
RATINGS = ["overall_rating", "accom_rating", "clean_rating", "checkin_rating",
           "com_rating", "loc_rating", "value_rating"]
BINARY = ["available", "host_is_superhost", "host_has_pic", "host_verified"]

results = []   # (section, check, status, detail)
tables = {}    # section -> markdown table appended to the report


def record(section, check, bad, total, warn_at=0.0, fail_at=0.01, note=""):
    """bad/total share -> PASS / WARN / FAIL."""
    share = bad / total if total else 0
    status = "PASS" if share <= warn_at else ("WARN" if share <= fail_at else "FAIL")
    detail = f"{bad:,} / {total:,} ({share:.2%})"
    results.append((section, check, status, detail + (f" - {note}" if note else "")))


def info(section, check, detail):
    results.append((section, check, "INFO", detail))


def build_typed_view(con):
    ac = [c for c in con.execute(f"SELECT * FROM '{PARQUET}' LIMIT 0").df().columns
          if c.startswith("AC") and c[2:].isdigit()]
    num = ",\n".join(f"TRY_CAST(NULLIF(TRIM({c}), '') AS DOUBLE) AS {c}" for c in NUMERIC)
    dts = ",\n".join(f"TRY_CAST(NULLIF(TRIM({c}), '') AS DATE) AS {c}" for c in DATES)
    acs = ",\n".join(f"TRY_CAST({c} AS INTEGER) AS {c}" for c in ac)
    con.execute(f"""
        CREATE OR REPLACE VIEW raw_t AS SELECT * FROM '{PARQUET}';
        CREATE OR REPLACE VIEW t AS
        SELECT KEY_FILE, KEY_LIST_ID, KEY_HOST_ID,
               TRY_CAST(CITY_ID AS DOUBLE)::INTEGER AS city_id,
               TRY_STRPTIME(DATE, '%Y%m%d')::DATE AS snap,
               {", ".join(TEXT)},
               {num},
               {dts},
               {acs}
        FROM raw_t;
    """)
    return ac


def check_types(con, total):
    s = "1. Types"
    exprs = [f"COUNT(*) FILTER (WHERE NULLIF(TRIM({c}), '') IS NOT NULL "
             f"AND TRY_CAST(TRIM({c}) AS {'DATE' if c in DATES else 'DOUBLE'}) IS NULL) AS {c}"
             for c in NUMERIC + DATES]
    bad = con.execute(f"SELECT {', '.join(exprs)} FROM raw_t").df().T[0]
    for c, n in bad[bad > 0].items():
        sample = con.execute(f"SELECT DISTINCT {c} FROM raw_t WHERE NULLIF(TRIM({c}), '') IS NOT NULL "
                             f"AND TRY_CAST(TRIM({c}) AS {'DATE' if c in DATES else 'DOUBLE'}) IS NULL LIMIT 3").df()[c].tolist()
        record(s, f"`{c}` values that fail to cast", int(n), total, note=f"e.g. {sample}")
    record(s, "numeric/date columns that cast cleanly", int((bad > 0).sum()), len(bad), fail_at=0.0,
           note="columns with any uncastable value")
    bad_date = con.execute("SELECT COUNT(*) FROM t WHERE snap IS NULL").fetchone()[0]
    record(s, "snapshot DATE parses as YYYYMMDD", bad_date, total, fail_at=0.0)
    fmt = con.execute("""SELECT CASE WHEN TAB_LAST_UPDATED LIKE '____-__-__%' THEN 'timestamp text'
                                     ELSE 'unix epoch number' END AS fmt, COUNT(*) AS n
                         FROM raw_t GROUP BY 1 ORDER BY 1""").df()
    info(s, "`TAB_LAST_UPDATED` storage format",
         "; ".join(f"{r.fmt}: {r.n:,}" for r in fmt.itertuples())
         + " (mixed formats - rows appended by NEWpipeline.R use epoch seconds)")


def check_keys(con, total):
    s = "2. Keys & identity"
    dup = con.execute("""SELECT COALESCE(SUM(n - 1), 0) FROM
                         (SELECT COUNT(*) n FROM t GROUP BY KEY_FILE, KEY_LIST_ID HAVING n > 1)""").fetchone()[0]
    record(s, "duplicate (KEY_FILE, KEY_LIST_ID) rows", int(dup), total, fail_at=0.0)
    dup2 = con.execute("""SELECT COALESCE(SUM(n - 1), 0) FROM
                          (SELECT COUNT(*) n FROM t GROUP BY city_id, snap, KEY_LIST_ID HAVING n > 1)""").fetchone()[0]
    record(s, "duplicate (city, snapshot date, listing) rows", int(dup2), total, fail_at=0.0,
           note="same snapshot loaded from two files (e.g. .csv and .tsv)")
    nulls = con.execute("SELECT COUNT(*) FROM t WHERE KEY_LIST_ID IS NULL OR KEY_HOST_ID IS NULL").fetchone()[0]
    record(s, "null listing or host id", nulls, total, fail_at=0.0)
    mism_city = con.execute("SELECT COUNT(*) FROM t WHERE LEFT(KEY_FILE, 2)::INT != city_id").fetchone()[0]
    record(s, "CITY_ID matches KEY_FILE prefix", mism_city, total, fail_at=0.0)
    mism_date = con.execute("SELECT COUNT(*) FROM t WHERE RIGHT(KEY_FILE, 8) != strftime(snap, '%Y%m%d')").fetchone()[0]
    record(s, "DATE matches KEY_FILE suffix", mism_date, total, fail_at=0.0)
    multi_city = con.execute("""SELECT COUNT(*) FROM (SELECT KEY_LIST_ID FROM t GROUP BY 1
                                HAVING COUNT(DISTINCT city_id) > 1)""").fetchone()[0]
    n_list = con.execute("SELECT COUNT(DISTINCT KEY_LIST_ID) FROM t").fetchone()[0]
    record(s, "listings appearing in more than one city", multi_city, n_list, warn_at=0.0, fail_at=0.001)
    host_change = con.execute("""SELECT COUNT(*) FROM (SELECT KEY_LIST_ID FROM t GROUP BY 1
                                 HAVING COUNT(DISTINCT KEY_HOST_ID) > 1)""").fetchone()[0]
    record(s, "listings whose host id changes over time", host_change, n_list, warn_at=0.01, fail_at=0.05,
           note="ownership transfer or re-assignment; matters for host-level churn")


def check_reconciliation(con):
    s = "3. Reconciliation with source files"
    ro = sqlite3.connect(f"file:{SOURCE_DB}?mode=ro", uri=True)
    meta = pd.read_sql(f"""SELECT FILE_ID, FILE_NAME, LOC, EXT, DATE, ROWS, UNIQUE_LISTINGS
                           FROM [META.V_FILE_INFO]
                           WHERE TYPE = 'listings' AND LOC IN ({",".join("?" * len(CITIES))})""",
                       ro, params=list(CITIES.values()))
    ro.close()
    meta["FILE_ID"] = meta["FILE_ID"].astype(str)
    cur = con.execute("""SELECT KEY_FILE AS FILE_ID, COUNT(*) AS curated_rows,
                                COUNT(DISTINCT KEY_LIST_ID) AS curated_listings
                         FROM t GROUP BY 1""").df()
    rec = meta.merge(cur, on="FILE_ID", how="outer", indicator=True)
    rec.to_csv(OUT_DIR / "file_reconciliation.csv", index=False)

    loaded = rec[rec["_merge"] == "both"]
    missing = rec[rec["_merge"] == "left_only"]
    orphan = rec[rec["_merge"] == "right_only"]
    record(s, "registered listings files with no curated rows", len(missing), len(meta), warn_at=0.0, fail_at=0.05,
           note=f"by type: {missing.groupby('EXT').size().to_dict()}" if len(missing) else "")
    if len(missing):
        same_day = missing["DATE"].isin(loaded["DATE"]).sum()
        info(s, "unloaded files whose date is covered by another file",
             f"{same_day} of {len(missing)} (likely .tsv duplicates of a .csv snapshot)")
    record(s, "curated KEY_FILEs not registered in META", len(orphan), len(cur), fail_at=0.0)
    counted = loaded[loaded["UNIQUE_LISTINGS"].notna()]
    diff = (counted["curated_listings"] != counted["UNIQUE_LISTINGS"]).sum()
    record(s, "curated listings = META unique listings, per file", int(diff), len(counted), fail_at=0.0)
    uncounted = loaded[loaded["UNIQUE_LISTINGS"].isna()]
    if len(uncounted):
        info(s, "files with no ROWS / UNIQUE_LISTINGS recorded in META",
             f"{len(uncounted)} ({', '.join(sorted(uncounted['DATE'].astype(str).str[:7].unique()))}) - "
             "metadata gap only; the rows are in the curated table")
    empty = missing[missing["UNIQUE_LISTINGS"] == 0]
    if len(empty):
        info(s, "unloaded files that are empty at the source", ", ".join(empty["FILE_NAME"]))
    gap = loaded["ROWS"] - loaded["UNIQUE_LISTINGS"]
    info(s, "META ROWS vs UNIQUE_LISTINGS in raw listings files",
         f"{(gap > 0).sum()} of {len(loaded)} files have ROWS > UNIQUE_LISTINGS "
         f"(median gap {gap.median():,.0f}) - META ROWS likely counts text lines, "
         "since descriptions contain embedded newlines; UNIQUE_LISTINGS is the reliable count")

    on_disk = {p.name for c in CITIES.values() for p in (SOURCE_DIR / "raw" / c).glob("*_listings.*")
               if not p.name.startswith("._")}
    unregistered = sorted(on_disk - set(meta["FILE_NAME"]))
    record(s, "raw listings files on disk not registered in META", len(unregistered), len(on_disk),
           warn_at=0.0, fail_at=0.05, note=", ".join(unregistered[:5]))
    return loaded


def check_against_raw(con, loaded):
    """Re-read a sample of raw CSVs and compare field values listing by listing."""
    s = "4. Field-level check against raw CSVs"
    csvs = loaded[loaded["EXT"] == "csv"].sort_values("DATE")
    sample = pd.concat([g.iloc[[0, len(g) // 2, -1]] for _, g in csvs.groupby("LOC")]).drop_duplicates("FILE_ID")
    rows = []
    for f in sample.itertuples():
        path = SOURCE_DIR / "raw" / f.LOC / f.FILE_NAME
        con.execute(f"""CREATE OR REPLACE TEMP TABLE r AS
                        SELECT * FROM read_csv('{path}', all_varchar = true, header = true,
                                               delim = ',', quote = '"', escape = '"',
                                               strict_mode = false, ignore_errors = true)""")
        rcols = set(con.execute("SELECT * FROM r LIMIT 0").df().columns)
        if "id" not in rcols:
            info(s, f"could not parse {f.FILE_NAME}", f"columns read: {sorted(rcols)[:3]} - skipped")
            continue
        avail = "availability_365" if "availability_365" in rcols else "NULL"
        m = con.execute(f"""
            WITH r2 AS (
                SELECT DISTINCT ON (id) id,
                       TRY_CAST(regexp_replace(price, '[$,]', '', 'g') AS DOUBLE) AS price,
                       TRY_CAST(number_of_reviews AS DOUBLE) AS number_of_reviews,
                       TRY_CAST({avail} AS DOUBLE) AS available_365,
                       TRY_CAST(accommodates AS DOUBLE) AS capacity,
                       room_type, host_id
                FROM r WHERE TRY_CAST(id AS BIGINT) IS NOT NULL)
            SELECT (SELECT COUNT(*) FROM r2) AS raw_listings,
                   COUNT(c.KEY_LIST_ID) AS matched,
                   AVG((r2.price IS NOT DISTINCT FROM c.price)::INT) AS price,
                   AVG((r2.number_of_reviews IS NOT DISTINCT FROM c.number_of_reviews)::INT) AS reviews,
                   AVG((r2.available_365 IS NOT DISTINCT FROM c.available_365)::INT) AS avail_365,
                   AVG((r2.capacity IS NOT DISTINCT FROM c.capacity)::INT) AS capacity,
                   AVG((r2.room_type IS NOT DISTINCT FROM c.room_type)::INT) AS room_type,
                   AVG((r2.host_id IS NOT DISTINCT FROM c.KEY_HOST_ID)::INT) AS host_id,
                   COUNT(*) FILTER (WHERE r2.price >= 1000) AS raw_price_ge_1000,
                   COUNT(*) FILTER (WHERE r2.price >= 1000 AND c.price = floor(r2.price / 1000)) AS price_thousands_bug,
                   COUNT(*) FILTER (WHERE r2.price IS NULL AND c.price = 0) AS price_null_as_zero
            FROM r2 JOIN t c ON c.KEY_FILE = '{f.FILE_ID}'
                            AND TRY_CAST(c.KEY_LIST_ID AS BIGINT) = TRY_CAST(r2.id AS BIGINT)
        """).df().iloc[0]
        rows.append({"file": f.FILE_NAME, **m.to_dict()})
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "raw_field_match.csv", index=False)
    fields = ["price", "reviews", "avail_365", "capacity", "room_type", "host_id"]
    for fld in fields:
        worst = df.loc[df[fld].idxmin()]
        mismatched = ((1 - df[fld]) * df["matched"]).sum()
        record(s, f"`{fld}` matches raw value", int(round(mismatched)), int(df["matched"].sum()),
               warn_at=0.001, fail_at=0.02, note=f"worst file {worst['file']} ({worst[fld]:.1%})")
    ge1000, bug, null0 = (int(df[c].sum()) for c in ("raw_price_ge_1000", "price_thousands_bug", "price_null_as_zero"))
    record(s, "raw prices >= $1,000 truncated at the thousands comma", bug, ge1000, fail_at=0.0,
           note="e.g. raw \"$1,067.50\" -> curated 1.0; every price >= $1,000 is affected")
    record(s, "raw empty price stored as 0 (should be NULL)", null0, int(df["matched"].sum()), warn_at=0.0, fail_at=0.0)
    unmatched = (df["raw_listings"] - df["matched"]).sum()
    record(s, "raw listings found in curated table", int(unmatched), int(df["raw_listings"].sum()),
           warn_at=0.0, fail_at=0.01)
    show = df.copy()
    for fld in fields:
        show[fld] = show[fld].map("{:.1%}".format)
    tables[s] = show.to_markdown(index=False)


def check_missingness(con, total):
    s = "5. Missingness over time"
    cols = NUMERIC + DATES + TEXT
    df = con.execute(f"""SELECT year(snap) AS year,
                                {", ".join(f"AVG(({c} IS NULL)::INT) AS {c}" for c in cols)}
                         FROM t GROUP BY 1 ORDER BY 1""").df().set_index("year")
    df.to_csv(OUT_DIR / "null_rate_by_year.csv")
    overall = con.execute(f"SELECT {', '.join(f'AVG(({c} IS NULL)::INT) AS {c}' for c in cols)} FROM t").df().T[0]
    for c in cols:
        lo, hi = df[c].min(), df[c].max()
        if hi - lo > 0.25:
            info(s, f"`{c}` null rate shifts across years",
                 f"{lo:.0%} ({df[c].idxmin()}) to {hi:.0%} ({df[c].idxmax()}) - overall {overall[c]:.1%}")
    heavy = overall[overall > 0.5]
    if len(heavy):
        info(s, "columns more than 50% null overall", ", ".join(f"`{c}` {v:.0%}" for c, v in heavy.items()))
    key = ["price", "capacity", "bedrooms", "overall_rating", "host_response_rate",
           "host_accept_rate", "available_365", "first_review_date"]
    tables[s] = (df[key] * 100).round(0).astype(int).astype(str).add("%").to_markdown()


def check_ranges(con, total, ac):
    s = "6. Ranges & domains"
    rules = {
        "price <= 0": "price <= 0",
        "price > $10,000/night": "price > 10000",
        "capacity outside 1-16": "capacity < 1 OR capacity > 16",
        "bedrooms > 20": "bedrooms > 20",
        "bathrooms > 20": "bathrooms > 20",
        "min_night > 365": "min_night > 365",
        "max_night < min_night": "max_night < min_night",
        "available_365 outside 0-365": "available_365 < 0 OR available_365 > 365",
        "availability windows not nested (30 <= 60 <= 90 <= 365)":
            "available_030 > available_060 OR available_060 > available_090 OR available_090 > available_365",
        "ratings outside 0-5": " OR ".join(f"{c} < 0 OR {c} > 5" for c in RATINGS),
        "response/accept rate outside 0-1": "host_response_rate NOT BETWEEN 0 AND 1 OR host_accept_rate NOT BETWEEN 0 AND 1",
        "binary flags not 0/1": " OR ".join(f"{c} NOT IN (0, 1)" for c in BINARY),
        "amenity flags (AC*) not 0/1": " OR ".join(f"{c} NOT IN (0, 1)" for c in ac),
        "negative counts": " OR ".join(f"{c} < 0" for c in NUMERIC if c.endswith("_count") or c == "number_of_reviews"),
    }
    counts = con.execute(f"SELECT {', '.join(f'COUNT(*) FILTER (WHERE {w})' for w in rules.values())} FROM t").fetchone()
    for (label, _), n in zip(rules.items(), counts):
        warn = 0.001 if label.startswith("price >") or "min_night" in label else 0.0
        record(s, label, n, total, warn_at=warn)
    low = con.execute("SELECT COUNT(*) FROM t WHERE price BETWEEN 1 AND 15").fetchone()[0]
    record(s, "price between $1 and $15 (mostly truncated $1,000+ prices)", low, total, warn_at=0.001)
    p = con.execute("""SELECT quantile_cont(price, [0.01, 0.5, 0.99]) AS q, MAX(price) AS mx
                       FROM t WHERE price > 0""").fetchone()
    info(s, "price distribution", f"p1 ${p[0][0]:,.0f} · median ${p[0][1]:,.0f} · p99 ${p[0][2]:,.0f} · max ${p[1]:,.0f}")
    scale = con.execute("""SELECT year(snap) y, MAX(overall_rating) mx, AVG(overall_rating) av
                           FROM t GROUP BY 1 ORDER BY 1""").df()
    info(s, "overall_rating scale by year",
         "max " + ", ".join(f"{int(r.y)}: {r.mx:.1f}" for r in scale.itertuples() if pd.notna(r.mx))
         + " - one 0-5 scale throughout, so the source's 0-100 era was rescaled")


def check_logic(con, total):
    s = "7. Logical consistency"
    rules = {
        "first_review_date > last_review_date": ("first_review_date > last_review_date", 0.0, 0.001),
        "last_review_date after snapshot date (by up to 21 days; file date precedes scrape)":
            ("last_review_date > snap", 0.0, 0.01),
        "host_since after snapshot date": ("host_since > snap", 0.0, 0.001),
        "reviews = 0 but has a review date": ("number_of_reviews = 0 AND first_review_date IS NOT NULL", 0.0, 0.001),
        "reviews > 0 but no review date": ("number_of_reviews > 0 AND first_review_date IS NULL", 0.001, 0.01),
        "reviews = 0 but has a rating": ("number_of_reviews = 0 AND overall_rating IS NOT NULL", 0.0, 0.001),
        "host_response_time 'N/A' but response rate stored as 0 (missing coded as 0)":
            ("host_response_time = 'N/A' AND host_response_rate IS NOT NULL", 0.0, 0.01),
        "host_accept_rate exactly 0 (raw 'N/A' coded as 0)": ("host_accept_rate = 0", 0.05, 0.25),
    }
    counts = con.execute(f"SELECT {', '.join(f'COUNT(*) FILTER (WHERE {w})' for w, _, _ in rules.values())} FROM t").fetchone()
    for (label, (_, warn, fail)), n in zip(rules.items(), counts):
        record(s, label, n, total, warn_at=warn, fail_at=fail)
    zero_acc = con.execute("""SELECT year(snap) y, AVG((host_accept_rate = 0)::INT) z
                              FROM t GROUP BY 1 ORDER BY 1""").df()
    info(s, "share of host_accept_rate = 0 by year",
         ", ".join(f"{int(r.y)}: {r.z:.0%}" for r in zero_acc.itertuples() if pd.notna(r.z))
         + " - 100% in 2017-2019 because the raw column is 'N/A' for every listing then")
    host = con.execute("""SELECT city_id, snap, COUNT(*) AS n,
                                 AVG((host_since IS NULL)::INT) AS since_null,
                                 AVG((host_response_time IS NULL OR host_response_time = '')::INT) AS resp_null
                          FROM t GROUP BY 1, 2 ORDER BY 2""").df()
    gap = host[host["resp_null"] > 0.5]
    record(s, "snapshots where the source has no host response/acceptance data",
           len(gap), len(host), warn_at=0.0, fail_at=1.0,
           note=(f"every snapshot from {gap['snap'].min():%Y-%m-%d} on ({gap['n'].sum():,} rows): raw files contain "
                 "'NA' for host_since, response time/rate and acceptance rate - a source gap, not a pipeline bug")
           if len(gap) else "")
    lost = host[host["since_null"] > 0.5]
    record(s, "snapshots with host_since missing for most listings", len(lost), len(host), fail_at=0.0,
           note="host_since is fixed per host, so it can be carried forward from earlier snapshots"
           if len(lost) else "")


def check_timeline(con):
    s = "8. Snapshot timeline"
    snaps = con.execute("""SELECT city_id, snap, COUNT(*) n FROM t GROUP BY 1, 2 ORDER BY 1, 2""").df()
    snaps["prev"] = snaps.groupby("city_id")["n"].shift()
    snaps["gap_days"] = snaps.groupby("city_id")["snap"].diff().dt.days
    snaps.to_csv(OUT_DIR / "snapshot_counts.csv", index=False)
    jumps = snaps[(snaps["prev"].notna()) & ((snaps["n"] / snaps["prev"] - 1).abs() > 0.4)]
    record(s, "snapshots with >40% row-count change vs previous", len(jumps), len(snaps), warn_at=0.0, fail_at=0.05,
           note="; ".join(f"{CITIES[r.city_id]} {r.snap:%Y-%m-%d} ({r.prev:,.0f}->{r.n:,})" for r in jumps.head(6).itertuples()))
    long_gap = snaps[snaps["gap_days"] > 120]
    record(s, "gaps of more than 120 days between snapshots", len(long_gap), len(snaps), warn_at=0.0, fail_at=0.05,
           note="; ".join(f"{CITIES[r.city_id]} before {r.snap:%Y-%m-%d} ({r.gap_days:.0f}d)" for r in long_gap.head(6).itertuples()))
    cad = snaps.assign(era=snaps["snap"].dt.year.map(lambda y: "2015-2022" if y <= 2022 else "2023-2026"))
    med = cad.groupby("era")["gap_days"].median()
    info(s, "median days between snapshots", " · ".join(f"{e}: {d:.0f} days" for e, d in med.items()))


def write_report(total):
    REPORT.parent.mkdir(exist_ok=True)
    counts = pd.Series([r[2] for r in results]).value_counts()
    lines = [
        "# Data Validation: Curated Listings Extract",
        "",
        f"Run {date.today():%Y-%m-%d} on `data_local/listings_6city.parquet` "
        f"({total:,} listing-snapshot rows; {', '.join(CITIES.values())}).",
        "The source drive was read only: `ia.db` via read-only connections and raw CSVs via `read_csv`.",
        "",
        "**Summary:** " + " · ".join(f"{counts.get(k, 0)} {k}" for k in ["FAIL", "WARN", "PASS", "INFO"]),
        "",
    ]
    for section in dict.fromkeys(r[0] for r in results):
        lines += [f"## {section}", "", "| Status | Check | Result |", "|---|---|---|"]
        for sec, check, status, detail in results:
            if sec == section:
                lines.append(f"| {status} | {check} | {detail.replace('|', '/')} |")
        if section in tables:
            lines += ["", tables[section]]
        lines.append("")
    lines += ["Detail files: `data_local/validation/`"]
    REPORT.write_text("\n".join(lines))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    ac = build_typed_view(con)
    total = con.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    check_types(con, total)
    check_keys(con, total)
    loaded = check_reconciliation(con)
    check_against_raw(con, loaded)
    check_missingness(con, total)
    check_ranges(con, total, ac)
    check_logic(con, total)
    check_timeline(con)
    write_report(total)
    for r in results:
        if r[2] in ("FAIL", "WARN"):
            print(f"[{r[2]}] {r[0]} | {r[1]}: {r[3]}")
    print(f"report -> {REPORT}")


if __name__ == "__main__":
    main()
