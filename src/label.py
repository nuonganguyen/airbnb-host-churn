"""Build listing labels per docs/label_spec.md (sql/03_label.sql).

    python src/label.py    # -> data_local/labels/*.parquet, reports/label_summary.md
"""
from datetime import date

import duckdb
import pandas as pd

from db import CITIES, LOCAL, PROJECT

CLEAN = LOCAL / "listings_6city_clean.parquet"
OUT = LOCAL / "labels"
REPORT = PROJECT / "reports" / "label_summary.md"

# approved in docs/label_spec.md section 8
PARAMS = {
    "tol_days": 45,
    "anomaly_ratio": 0.75,
    "return_threshold": 0.5,
    "resolve_max_days": 200,
    "active_review_days": 365,
    "new_window_days": 180,
    "new_min_coverage_days": 180,
    "low_rating": 4.0,
    "low_rating_min_reviews": 5,
}
TABLES = ["schedule", "prediction_dates", "checkpoints", "labels"]


def build(con, params=PARAMS, as_of=None):
    """Run sql/03_label.sql against an existing `ls` table. `as_of` is the date the
    data is current to; None means each city's latest snapshot."""
    for name, value in params.items():
        con.execute(f"SET VARIABLE {name} = {value}")
    con.execute(f"SET VARIABLE as_of = DATE '{as_of}'" if as_of else "SET VARIABLE as_of = NULL::DATE")
    con.execute((PROJECT / "sql" / "03_label.sql").read_text())


def load_clean(con):
    con.execute(f"""
        CREATE OR REPLACE TABLE ls AS
        SELECT TRY_CAST(CITY_ID AS DOUBLE)::INTEGER AS city_id,
               strptime(DATE, '%Y%m%d')::DATE AS snap,
               TRY_CAST(KEY_LIST_ID AS BIGINT) AS list_id,
               TRY_CAST(KEY_HOST_ID AS BIGINT) AS host_id,
               TRY_CAST(NULLIF(last_review_date, '') AS DATE) AS last_review_date,
               TRY_CAST(overall_rating AS DOUBLE) AS overall_rating,
               TRY_CAST(number_of_reviews AS DOUBLE) AS number_of_reviews
        FROM '{CLEAN}'
    """)


def md(df):
    df = df.copy()
    for c in df.select_dtypes("datetime").columns:
        df[c] = df[c].dt.strftime("%Y-%m-%d")
    return df.to_markdown(index=False)


def summarize(con):
    city = "CASE city_id " + " ".join(f"WHEN {k} THEN '{v}'" for k, v in CITIES.items()) + " END"
    era = "CASE WHEN year(t) <= 2022 THEN '2015-22' ELSE '2023+' END"
    q = lambda sql: con.execute(sql).df()

    status = q(f"""SELECT {city} AS city, status, COUNT(*) AS snapshots FROM schedule GROUP BY ALL
                   ORDER BY 1, 2""").pivot(index="city", columns="status", values="snapshots").fillna(0).astype(int).reset_index()
    flagged = q(f"""SELECT {city} AS city, snap, n_listings, round(trailing_ratio, 2) AS trailing_ratio,
                           reference_snap, resolver_snap, n_missing, round(return_rate, 3) AS return_rate,
                           status, status_known_at
                    FROM schedule WHERE anomaly ORDER BY city_id, snap""")
    coverage = q(f"""SELECT {city} AS city, {era} AS era, COUNT(*) AS prediction_dates,
                            COUNT(*) FILTER (WHERE NOT label_final) AS provisional,
                            COUNT(*) FILTER (WHERE label_final AND followup_reason = 'ok') AS final_with_followup,
                            COUNT(*) FILTER (WHERE label_final AND followup_reason = 'no_c2') AS final_no_c2,
                            COUNT(*) FILTER (WHERE label_final AND followup_reason = 'no_c3') AS final_no_c3,
                            COUNT(*) FILTER (WHERE label_final AND followup_reason = 'no_c2_c3') AS final_no_c2_c3,
                            MAX(t) FILTER (WHERE label_final AND followup_reason = 'ok') AS last_labeled_t
                     FROM checkpoints GROUP BY ALL ORDER BY 1, 2""")
    offsets = q(f"""SELECT {city} AS city, {era} AS era,
                           median(c2_offset) AS c2_median, MIN(c2_offset) AS c2_min, MAX(c2_offset) AS c2_max,
                           median(c3_offset) AS c3_median, MIN(c3_offset) AS c3_min, MAX(c3_offset) AS c3_max
                    FROM checkpoints WHERE label_final AND followup_reason = 'ok' GROUP BY ALL ORDER BY 1, 2""")
    population = q(f"""SELECT {era} AS era, COUNT(*) AS listings_at_t,
                              COUNT(*) FILTER (WHERE active_review) AS active_review,
                              COUNT(*) FILTER (WHERE NOT active_review AND recently_first_observed AND newness_known) AS via_recent_first_obs,
                              COUNT(*) FILTER (WHERE NOT active_review AND recently_first_observed AND NOT newness_known) AS excl_newness_unknown,
                              COUNT(*) FILTER (WHERE NOT active_review AND NOT recently_first_observed) AS excl_inactive,
                              COUNT(*) FILTER (WHERE (active_review OR (recently_first_observed AND newness_known)) AND low_quality) AS excl_low_quality,
                              COUNT(*) FILTER (WHERE eligible_main) AS eligible_main
                       FROM labels GROUP BY ALL ORDER BY 1""")
    outcomes = q(f"""SELECT {era} AS era, label_status, CASE WHEN eligible_main THEN 'main' ELSE 'excluded' END AS population,
                            COUNT(*) AS listings,
                            round(AVG((outcome = 'insufficient_followup')::INT), 3) AS insufficient_followup,
                            round(AVG((outcome = 'absent_confirmed')::INT) FILTER (WHERE outcome <> 'insufficient_followup'), 3)
                                AS absent_confirmed_rate
                     FROM labels GROUP BY ALL ORDER BY 1, 2, 3""")
    quarters = q(f"""SELECT strftime(date_trunc('quarter', t), '%Y-Q') || quarter(t) AS quarter,
                            COUNT(*) FILTER (WHERE label_final AND followup_reason = 'ok') AS markets_with_final_outcomes,
                            string_agg({city}, ', ') FILTER (WHERE NOT (label_final AND followup_reason = 'ok'))
                                AS markets_without
                     FROM checkpoints WHERE t >= DATE '2023-01-01' GROUP BY ALL ORDER BY 1""")
    reactivation = q(f"""SELECT {era} AS era, COUNT(*) AS absent_confirmed,
                                round(AVG((EXISTS (SELECT 1 FROM ls WHERE ls.city_id = l.city_id
                                    AND ls.list_id = l.list_id AND ls.snap > l.c3))::INT), 3) AS seen_again_after_c3
                         FROM labels l WHERE outcome = 'absent_confirmed' AND label_status = 'final'
                         GROUP BY ALL ORDER BY 1""")

    lines = [
        "# Label Summary",
        "",
        f"Built {date.today():%Y-%m-%d} by `src/label.py` from `listings_6city_clean.parquet` per "
        "`docs/label_spec.md` (v3). Rates are descriptive, not a validation target. Only `final` "
        "labels may be used for training or evaluation.",
        "",
        "## Snapshot status (operational rule)", "", md(status), "",
        "## Flagged snapshots", "", md(flagged), "",
        "## Follow-up coverage by city and era", "", md(coverage), "",
        "## Actual checkpoint offsets (days after t)", "", md(offsets), "",
        "## Population rules (counts of listing-dates)", "", md(population), "",
        "## Outcomes", "",
        "`absent_confirmed_rate` is among listing-dates with usable follow-up. Provisional labels can still "
        "change as data arrives.", "", md(outcomes), "",
        "## Markets with final outcomes per quarter (2023+, for the shared holdout block)", "",
        "A market without a prediction date in a quarter is not listed.", "",
        md(quarters), "",
        "## Reactivation after confirmed absence", "",
        "Right-censored: later prediction dates have less time after C3 in which to be seen again.", "",
        md(reactivation), "",
    ]
    REPORT.write_text("\n".join(lines))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    load_clean(con)
    build(con)
    for table in TABLES:
        con.execute(f"COPY {table} TO '{OUT / (table + '.parquet')}' (FORMAT parquet)")
    summarize(con)
    n = con.execute("SELECT outcome, COUNT(*) FROM labels GROUP BY 1 ORDER BY 1").fetchall()
    print(dict(n))
    print(f"tables -> {OUT}\nreport -> {REPORT}")


if __name__ == "__main__":
    main()
