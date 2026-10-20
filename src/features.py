"""Listing features per docs/feature_spec.md (sql/04_features.sql).

    python src/features.py   # -> data_local/features.parquet, reports/feature_summary.md

Model code gets predictors only through model_matrix(), which returns exactly the
approved ALLOWLIST. Training rows come only from training_frame().
"""
import os
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

import label
from db import CITIES, LOCAL, PROJECT

SQL = Path(os.environ.get("FEATURES_SQL", PROJECT / "sql" / "04_features.sql"))
OUT = LOCAL / "features.parquet"
REPORT = PROJECT / "reports" / "feature_summary.md"

PARAMS = {"lag_tol_days": 45, "new_min_coverage_days": 180}

NUMERIC_COLS = [
    "price", "capacity", "bathrooms", "bedrooms", "beds", "min_night", "max_night",
    "available_030", "available_060", "available_090", "available_365", "number_of_reviews",
    "overall_rating", "accom_rating", "clean_rating", "checkin_rating", "com_rating",
    "loc_rating", "value_rating", "amenity_count", "descrip_word_count", "host_about_word_count",
    "host_is_superhost", "host_listing_count", "host_has_pic", "host_verified",
]
# Curated amenity flags AC1-AC82 are not used: codes are factor positions of hand
# labels built from all years at once (one is the discard label "remove"), and their
# prevalence is implausible and unstable (e.g. "waterslide" 96% in 2016).
AMENITIES = [f"AC{i}" for i in range(1, 83)]

# Approved predictors: name -> kind. Kinds tell the per-fold preprocessing what to fit.
ALLOWLIST = {
    **{c: "numeric" for c in ["price", "capacity", "bathrooms", "bedrooms", "beds", "min_night", "max_night",
                              "available_030", "available_060", "available_090", "available_365",
                              "number_of_reviews", "overall_rating", "accom_rating", "clean_rating",
                              "checkin_rating", "com_rating", "loc_rating", "value_rating",
                              "amenity_count", "amenity_count_pct", "descrip_word_count",
                              "host_about_word_count", "host_listing_count"]},
    **{c: "binary" for c in ["price_missing", "host_is_superhost", "host_has_pic", "host_verified"]},
    **{c: "categorical" for c in ["city_id", "room_type", "listing_type", "quarter_of_year"]},
    **{c: "numeric" for c in ["days_since_first_observed", "host_tenure_days", "days_since_last_review",
                              "days_since_first_review"]},
    "first_observed_censored": "binary",
    **{c: "numeric" for c in ["lag90_days", "price_change_90", "avail365_change_90", "rating_change_90",
                              "reviews_added_90", "review_rate_90"]},
    **{c: "binary" for c in ["present_lag90", "reviews_decreased_90"]},
    **{c: "numeric" for c in ["lag365_days", "price_change_365", "reviews_added_365", "review_rate_365"]},
    "present_lag365": "binary",
    **{c: "numeric" for c in ["hist_snapshots_365", "hist_present_365", "presence_rate_365",
                              "host_n_listings", "host_listings_change_90",
                              "city_n_listings", "city_supply_growth_365", "price_rel_room_median",
                              "neighbourhood_n_listings", "neighbourhood_supply_growth_365",
                              "price_rel_neighbourhood_median"]},
}

# Never predictors: label outputs (derived from the future), population filters,
# identifiers, and fields that vanish in deployment-era data.
FORBIDDEN = {
    "outcome", "label_status", "label_final", "label_final_at", "c1_final_at", "c2_final_at", "c3_final_at",
    "c1", "c2", "c3", "c1_offset", "c2_offset", "c3_offset", "in_c1", "in_c2", "in_c3",
    "followup_reason", "host_changed", "as_of",
    "eligible_main", "active_review", "recently_first_observed", "newness_known", "low_quality",
    "list_id", "host_id", "host_id_at_t", "t", "decision_date", "lag90_snap", "lag365_snap",
    "zip", "neighbourhood", "scrape_source", *AMENITIES,
    "host_response_time", "host_response_rate", "host_accept_rate",
    "loc_overview_word_count", "loc_overview_char_count",
}
KEYS = ["city_id", "list_id", "t"]


def load_clean(con, source=label.CLEAN):
    """Typed listing snapshots (lf), plus the narrower ls view the label SQL reads.
    Rows whose raw id was written in scientific notation are dropped: their ids are
    rounded, so the listing cannot be followed across snapshots."""
    num = ",\n".join(f"TRY_CAST(NULLIF(TRIM({c}), '') AS DOUBLE) AS {c}" for c in NUMERIC_COLS)
    con.execute(f"""
        CREATE OR REPLACE TABLE lf AS
        SELECT TRY_CAST(CITY_ID AS DOUBLE)::INTEGER AS city_id,
               strptime(DATE, '%Y%m%d')::DATE AS snap,
               TRY_CAST(KEY_LIST_ID AS BIGINT) AS list_id,
               TRY_CAST(KEY_HOST_ID AS BIGINT) AS host_id,
               NULLIF(TRIM(room_type), '') AS room_type,
               NULLIF(TRIM(listing_type), '') AS listing_type,
               NULLIF(TRIM(neighbourhood), '') AS neighbourhood,
               scrape_source,
               -- 28 rows in 4 files carry scrape dates 22-59 days after their file date (after the
               -- next snapshot); treat those dates as unknown rather than delay the whole snapshot
               CASE WHEN TRY_CAST(last_scraped AS DATE) <= strptime(DATE, '%Y%m%d')::DATE
                         + {label.PARAMS["max_scrape_lag_days"]} THEN TRY_CAST(last_scraped AS DATE) END AS last_scraped,
               TRY_CAST(NULLIF(first_review_date, '') AS DATE) AS first_review_date,
               TRY_CAST(NULLIF(last_review_date, '') AS DATE) AS last_review_date,
               TRY_CAST(NULLIF(host_since, '') AS DATE) AS host_since,
               {num}
        FROM '{source}'
        WHERE NOT id_imprecise
    """)
    ls_view(con)


def ls_view(con):
    con.execute("""CREATE OR REPLACE VIEW ls AS
                   SELECT city_id, snap, list_id, host_id, last_scraped, last_review_date,
                          overall_rating, number_of_reviews
                   FROM lf""")


def build(con, params=PARAMS, as_of=None):
    """Run sql/04_features.sql; needs lf, schedule and prediction_dates (label.build)."""
    label.check_inputs(con, "lf", as_of)
    for name, value in params.items():
        con.execute(f"SET VARIABLE {name} = {value}")
    con.execute(SQL.read_text())


def model_matrix(df):
    """Exactly the approved predictors, in a fixed order."""
    missing = [c for c in ALLOWLIST if c not in df.columns]
    if missing:
        raise KeyError(f"allowlisted predictors missing from input: {missing[:5]}")
    return df[list(ALLOWLIST)]


def training_frame(con, deployment_date):
    """Rows a model deployed at `deployment_date` may train on (docs/label_spec.md §7)."""
    return con.execute("""
        SELECT f.*, l.outcome = 'absent_confirmed' AS target, l.label_final_at, l.c2, l.c3
        FROM features f
        JOIN labels l ON l.city_id = f.city_id AND l.list_id = f.list_id AND l.t = f.t
        WHERE l.eligible_main
          AND l.label_status = 'final'
          AND l.outcome IN ('absent_confirmed', 'observed')
          AND l.label_final_at < ?
        ORDER BY f.t, f.city_id, f.list_id
    """, [deployment_date]).df()


def scoring_frame(con, t):
    """Eligible rows at prediction date t, whether or not an outcome is known."""
    return con.execute("""
        SELECT f.*
        FROM features f
        JOIN labels l ON l.city_id = f.city_id AND l.list_id = f.list_id AND l.t = f.t
        WHERE l.eligible_main AND f.t = ?
        ORDER BY f.city_id, f.list_id
    """, [t]).df()


def summarize(con):
    era = "CASE WHEN year(t) <= 2022 THEN '2015-22' ELSE '2023+' END"
    keys = con.execute(f"""SELECT COUNT(*) AS rows, COUNT(DISTINCT (city_id, list_id, t)) AS distinct_keys,
                                  (SELECT COUNT(*) FROM prediction_dates p JOIN lf l
                                     ON l.city_id = p.city_id AND l.snap = p.t) AS listings_at_prediction_dates
                           FROM features""").df()
    cols = list(ALLOWLIST)
    nulls = con.execute(f"""SELECT {era} AS era, {', '.join(f'round(AVG(({c} IS NULL)::INT), 3) AS "{c}"' for c in cols)}
                            FROM features GROUP BY 1 ORDER BY 1""").df().set_index("era").T
    nulls.index.name = "feature"
    lines = [
        "# Feature Summary", "",
        f"Built {date.today():%Y-%m-%d} by `src/features.py` per `docs/feature_spec.md`.", "",
        "## Row integrity", "", label.md(keys), "",
        f"## Allowlist: {len(ALLOWLIST)} predictors "
        f"({sum(k == 'numeric' for k in ALLOWLIST.values())} numeric, "
        f"{sum(k == 'binary' for k in ALLOWLIST.values())} binary, "
        f"{sum(k == 'categorical' for k in ALLOWLIST.values())} categorical)", "",
        "## Null share by era", "",
        nulls.reset_index().to_markdown(index=False), "",
    ]
    REPORT.write_text("\n".join(lines))


def main():
    con = duckdb.connect()
    load_clean(con)
    label.build(con)
    build(con)
    con.execute(f"COPY features TO '{OUT}' (FORMAT parquet)")
    summarize(con)
    n, k = con.execute("SELECT COUNT(*), COUNT(DISTINCT (city_id, list_id, t)) FROM features").fetchone()
    print(f"{n:,} rows, {k:,} distinct keys -> {OUT}\nreport -> {REPORT}")


if __name__ == "__main__":
    main()
