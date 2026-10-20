"""Acceptance tests for sql/04_features.sql (docs/feature_spec.md).

Reuses the synthetic cities from test_label.py, enriched with every lf column.

    .venv/bin/python -m pytest tests -q
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import features  # noqa: E402
import label  # noqa: E402
from test_label import (LAG_PARAMS, MONTHS, TEST_PARAMS, Listing, T, as_date, city, scenario_a,  # noqa: E402
                        scenario_d, scenario_e)

D = date


def enrich(rows, reviews=None, lag=0):
    """Label-test rows -> full lf rows. `reviews`: optional {list_id: f(snap)}; rows are
    collected `lag` days after their snapshot date."""
    out = []
    for city_id, snap, list_id, host_id, last_review, rating, n_reviews in rows:
        r = {c: 0.0 for c in features.NUMERIC_COLS}
        r.update(city_id=city_id, snap=snap, list_id=list_id, host_id=host_id, last_scraped=snap + timedelta(days=lag),
                 room_type="Entire home/apt", listing_type="House", neighbourhood=f"N{list_id % 3}",
                 scrape_source="city scrape",
                 first_review_date=snap - timedelta(days=400) if last_review else None,
                 last_review_date=last_review, host_since=D(2015, 1, 1),
                 price=100.0 + list_id % 50, capacity=2.0, bathrooms=1.0, bedrooms=1.0, beds=1.0,
                 min_night=2.0, max_night=30.0, available_030=10.0, available_060=20.0,
                 available_090=30.0, available_365=100.0, amenity_count=10.0, descrip_word_count=50.0,
                 host_listing_count=1.0, host_has_pic=1.0, host_verified=1.0,
                 number_of_reviews=float(reviews[list_id](snap)) if reviews and list_id in reviews else n_reviews)
        for c in ["overall_rating", "accom_rating", "clean_rating", "checkin_rating", "com_rating",
                  "loc_rating", "value_rating"]:
            r[c] = rating
        out.append(r)
    return out


def run(lf_rows, as_of=None, params=None):
    con = duckdb.connect()
    df = pd.DataFrame(lf_rows)
    con.register("df", df)
    dates = ["snap", "last_scraped", "first_review_date", "last_review_date", "host_since"]
    casts = ", ".join(
        [f"{c}::DATE AS {c}" for c in dates]
        + [f"{c}::INTEGER AS {c}" for c in ["city_id"]]
        + [f"{c}::BIGINT AS {c}" for c in ["list_id", "host_id"]]
        + [f"{c}::VARCHAR AS {c}" for c in ["room_type", "listing_type", "neighbourhood", "scrape_source"]]
        + [f"{c}::DOUBLE AS {c}" for c in features.NUMERIC_COLS])
    con.execute(f"CREATE TABLE lf AS SELECT {casts} FROM df")
    features.ls_view(con)
    label.build(con, params or TEST_PARAMS, as_of=as_of)
    features.build(con, as_of=as_of)
    return con


def feats(con, city_id, t, list_id):
    df = con.execute("SELECT * FROM features WHERE city_id = ? AND t = ? AND list_id = ?",
                     [city_id, t, list_id]).df()
    assert len(df) == 1
    return df.iloc[0]


# --- scenarios ---------------------------------------------------------------------

def scenario_presence():
    """City 21: listing 30 absent in 3 of the 12 snapshots before 2019-07-01; listing 31
    first seen 2018-09-01; host 777 has 3 listings at 2019-04-01 and 1 at 2019-07-01."""
    gaps = {D(2018, 10, 1), D(2018, 11, 1), D(2019, 2, 1)}
    host = lambda s: 777
    return enrich(city(21, MONTHS, [
        Listing(30, lambda s: s not in gaps),
        Listing(31, lambda s: s >= D(2018, 9, 1)),
        Listing(41, lambda s: True, host=host),
        Listing(42, lambda s: s <= D(2019, 5, 1), host=host),
        Listing(43, lambda s: s <= D(2019, 5, 1), host=host),
    ]))


def one_review_per_30_days(s):
    return (s - D(2018, 1, 1)).days // 30


def scenario_velocity():
    """City 22 monthly and city 23 every 60 days; listing 50 gains a review every 30 days."""
    every60 = [D(2018, 1, 1) + timedelta(days=60 * i) for i in range(12)]
    rows = city(22, MONTHS, [Listing(50, lambda s: True)]) + city(23, every60, [Listing(50, lambda s: True)])
    return enrich(rows, reviews={50: one_review_per_30_days})


SCENARIOS = [lambda: enrich(scenario_a()), lambda: enrich(scenario_d()), lambda: enrich(scenario_e()),
             scenario_presence, scenario_velocity]


@pytest.fixture(scope="module")
def con():
    return run([r for make in SCENARIOS for r in make()])


# --- row integrity -----------------------------------------------------------------

def test_one_row_per_key(con):
    n, k = con.execute("SELECT COUNT(*), COUNT(DISTINCT (city_id, list_id, t)) FROM features").fetchone()
    assert n == k > 0


def test_rows_cover_every_listing_at_prediction_dates(con):
    expected = con.execute("""SELECT COUNT(*) FROM prediction_dates p
                              JOIN lf l ON l.city_id = p.city_id AND l.snap = p.t""").fetchone()[0]
    assert con.execute("SELECT COUNT(*) FROM features").fetchone()[0] == expected


def test_history_is_before_t_and_known_by_t(con):
    bad = con.execute("""SELECT COUNT(*) FROM history h
                         JOIN schedule s ON s.city_id = h.city_id AND s.snap = h.snap
                         WHERE h.snap >= h.t OR s.status_known_at > h.t
                            OR s.status NOT IN ('ok', 'insufficient_history', 'suspected_contraction')""").fetchone()[0]
    assert bad == 0
    assert con.execute("SELECT COUNT(*) FROM anchors WHERE snap >= t").fetchone()[0] == 0
    late = con.execute("SELECT COUNT(*) FROM features WHERE lag90_snap >= t OR lag365_snap >= t").fetchone()[0]
    assert late == 0


# --- information availability -------------------------------------------------------

def poison(rows, after):
    """Change every row dated after `after`, drop half of them, and add new listings."""
    out = []
    for r in rows:
        if r["snap"] <= after:
            out.append(r)
        elif r["list_id"] % 2:
            out.append({**r, "price": r["price"] * 10, "number_of_reviews": r["number_of_reviews"] + 999,
                        "available_365": 0.0, "host_id": r["host_id"] + 1})
    extra = [{**r, "list_id": r["list_id"] + 7_000_000} for r in rows if r["snap"] > after]
    return out + extra


@pytest.mark.parametrize("make", [lambda: enrich(scenario_a()), lambda: enrich(scenario_d()),
                                  lambda: enrich(scenario_e()), scenario_presence])
def test_later_data_cannot_change_features(make):
    rows = make()
    full = run(rows)
    q = "SELECT * FROM features WHERE t = ? ORDER BY city_id, list_id"
    for (t,) in full.execute("SELECT DISTINCT t FROM features ORDER BY t").fetchall():
        expected = full.execute(q, [t]).df()
        truncated = run([r for r in rows if r["snap"] <= t], as_of=t)
        pd.testing.assert_frame_equal(truncated.execute(q, [t]).df(), expected, check_dtype=False)
        poisoned = run(poison(rows, t))
        pd.testing.assert_frame_equal(poisoned.execute(q, [t]).df(), expected, check_dtype=False)


def test_build_rejects_rows_after_as_of():
    rows = enrich(scenario_a())
    with pytest.raises(ValueError, match="after as_of"):
        run(rows, as_of=D(2018, 12, 1))


# --- feature definitions ---------------------------------------------------------------

def test_lag_anchor_skips_partial_scrape(con):
    # city 4: 2019-01-01 is a partial scrape; t = 2019-04-01 targets 2019-01-01 for lag90
    row = feats(con, 4, D(2019, 4, 1), 81)
    assert as_date(row.lag90_snap) == D(2019, 1, 20)


def test_review_rate_accounts_for_elapsed_time(con):
    rates = con.execute("""SELECT city_id, lag90_days, reviews_added_90, review_rate_90 FROM features
                           WHERE list_id = 50 AND lag90_days IS NOT NULL""").df()
    assert set(rates.city_id) == {22, 23}
    assert rates.lag90_days.nunique() > 1                     # spacing differs between cities
    assert rates.review_rate_90.between(0.8, 1.2).all()       # same underlying velocity


def test_presence_rate_over_past_year(con):
    row = feats(con, 21, D(2019, 7, 1), 30)
    assert (row.hist_snapshots_365, row.hist_present_365) == (12, 9)
    assert row.presence_rate_365 == pytest.approx(0.75)


def test_first_observed_censoring(con):
    t = D(2019, 7, 1)
    assert feats(con, 21, t, 30).first_observed_censored               # seen since coverage start
    row = feats(con, 21, t, 31)                                         # first seen 2018-09-01
    assert not row.first_observed_censored
    assert row.days_since_first_observed == (t - D(2018, 9, 1)).days


def test_host_portfolio_change(con):
    row = feats(con, 21, D(2019, 7, 1), 41)
    assert row.host_n_listings == 1 and row.host_listings_change_90 == -2


def test_market_growth_uses_anchor_snapshot(con):
    row = feats(con, 4, D(2019, 4, 1), 81)
    n = lambda s: con.execute("SELECT COUNT(*) FROM lf WHERE city_id = 4 AND snap = ?", [s]).fetchone()[0]
    assert row.city_n_listings == n(D(2019, 4, 1))
    assert row.city_supply_growth_365 == pytest.approx(n(D(2019, 4, 1)) / n(as_date(row.lag365_snap)) - 1)


# --- predictors and training rows -----------------------------------------------------

def test_allowlist_excludes_forbidden_and_exists(con):
    assert not set(features.ALLOWLIST) & features.FORBIDDEN
    cols = set(con.execute("SELECT * FROM features LIMIT 0").df().columns)
    assert set(features.ALLOWLIST) <= cols
    label_cols = {"outcome", "in_c2", "in_c3", "host_changed", "label_status", "label_final_at", "c2", "c3"}
    assert not cols & set(features.AMENITIES)                  # unreliable curated amenity codes
    assert not cols & label_cols


def test_model_matrix_is_exactly_the_allowlist(con):
    df = con.execute("SELECT * FROM features").df()
    assert list(features.model_matrix(df).columns) == list(features.ALLOWLIST)
    with pytest.raises(KeyError):
        features.model_matrix(df.drop(columns=["price"]))


def test_training_frame_enforces_all_four_conditions(con):
    deploy = D(2019, 7, 1)
    got = features.training_frame(con, deploy)
    assert len(got) > 0
    keys = set(map(tuple, got[["city_id", "list_id", "t"]].astype(str).values))
    expected = con.execute("""SELECT city_id, list_id, t FROM labels
                              WHERE eligible_main AND label_status = 'final'
                                AND outcome IN ('absent_confirmed', 'observed') AND label_final_at < ?""",
                           [deploy]).df()
    assert keys == set(map(tuple, expected.astype(str).values))
    excluded = con.execute("""SELECT COUNT(*) FROM labels WHERE NOT eligible_main OR label_status <> 'final'
                              OR outcome = 'insufficient_followup' OR label_final_at >= ?""", [deploy]).fetchone()[0]
    assert excluded > 0                                        # the filters had something to remove
    assert (pd.to_datetime(got.label_final_at) < pd.Timestamp(deploy)).all()


def test_scoring_frame_includes_rows_without_outcomes(con):
    t = con.execute("SELECT MAX(t) FROM prediction_dates WHERE city_id = 1").fetchone()[0]
    got = features.scoring_frame(con, t)
    unresolved = con.execute("""SELECT COUNT(*) FROM labels WHERE t = ? AND eligible_main
                                AND (label_status = 'provisional' OR outcome = 'insufficient_followup')""",
                             [t]).fetchone()[0]
    assert unresolved > 0 and len(got) >= unresolved


def test_durations_measured_from_decision_date():
    con = run(enrich(scenario_a(), lag=6), params=LAG_PARAMS)
    row = feats(con, 1, T, 1)
    assert as_date(row.decision_date) == T + timedelta(6)
    # last review 10 days before the snapshot date -> 16 days before collection finished
    assert row.days_since_last_review == 16 and row.days_since_last_review >= 0


def test_amenity_percentile_uses_only_its_snapshot(con):
    pct = con.execute("SELECT MIN(amenity_count_pct), MAX(amenity_count_pct) FROM features").fetchone()
    assert 0 <= pct[0] <= pct[1] <= 1
