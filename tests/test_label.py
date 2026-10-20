"""Acceptance tests for sql/03_label.sql (docs/label_spec.md v2).

Each scenario is a synthetic city: 100 background listings present at every
snapshot (so counts are stable), plus test listings with known presence patterns.

    .venv/bin/python -m pytest tests -q
"""
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Optional

import duckdb
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import label  # noqa: E402

D = date
T = D(2018, 7, 1)                       # prediction date used in most scenarios
C1, C2, C3 = D(2018, 10, 1), D(2019, 1, 1), D(2019, 4, 1)
MONTHS = list(pd.date_range("2018-01-01", periods=24, freq="MS").date)
FILL = 100
# synthetic rows are collected on their snapshot date, so no scrape lag is needed
TEST_PARAMS = {**label.PARAMS, "max_scrape_lag_days": 0}


@dataclass
class Listing:
    id: int
    present: Callable[[date], bool]
    host: Optional[Callable[[date], int]] = None
    reviewed: bool = True               # last review 10 days before each snapshot
    rating: Optional[float] = 4.8
    reviews: float = 10


def city(city_id, snaps, listings=(), partial=(), contraction=None):
    """Rows for one city. `partial`: snapshots missing 60 background listings that
    return next time. `contraction`: from this snapshot on, 60 are gone for good."""
    rows = []
    for s in snaps:
        for i in range(FILL):
            if i < 60 and (s in partial or (contraction and s >= contraction)):
                continue
            lid = city_id * 1_000_000 + i
            rows.append((city_id, s, lid, lid + 500_000, s - timedelta(days=10), 4.8, 10))
        for L in listings:
            if L.present(s):
                host = L.host(s) if L.host else L.id + 500_000
                rows.append((city_id, s, L.id, host, s - timedelta(days=10) if L.reviewed else None,
                             L.rating, L.reviews))
    return rows


def run(rows, as_of=None, params=None, scrape_lag=0):
    """Build labels from synthetic rows; every row is collected `scrape_lag` days after its snapshot."""
    con = duckdb.connect()
    df = pd.DataFrame(rows, columns=["city_id", "snap", "list_id", "host_id", "last_review_date",
                                     "overall_rating", "number_of_reviews"])
    df["last_scraped"] = df["snap"] + timedelta(days=scrape_lag)
    con.register("df", df)
    con.execute("""CREATE TABLE ls AS
                   SELECT city_id::INTEGER AS city_id, snap::DATE AS snap, list_id::BIGINT AS list_id,
                          host_id::BIGINT AS host_id, last_scraped::DATE AS last_scraped,
                          last_review_date::DATE AS last_review_date,
                          overall_rating::DOUBLE AS overall_rating, number_of_reviews::DOUBLE AS number_of_reviews
                   FROM df""")
    label.build(con, params or TEST_PARAMS, as_of=as_of)
    return con


def one(con, sql, *params):
    df = con.execute(sql, list(params)).df()
    assert len(df) == 1, f"expected one row, got {len(df)}"
    return df.iloc[0]


def lab(con, city_id, t, list_id):
    return one(con, "SELECT * FROM labels WHERE city_id = ? AND t = ? AND list_id = ?", city_id, t, list_id)


def cp(con, city_id, t):
    return one(con, "SELECT * FROM checkpoints WHERE city_id = ? AND t = ?", city_id, t)


def status(con, city_id, snap):
    return one(con, "SELECT * FROM schedule WHERE city_id = ? AND snap = ?", city_id, snap)["status"]


def as_date(x):
    return None if pd.isna(x) else pd.Timestamp(x).date()


# --- scenarios -------------------------------------------------------------------

def scenario_a():
    """Monthly city, all snapshots complete. Worked examples 1-7, 10, 12, 13, 17."""
    host_change = lambda s: 9010 if s < D(2018, 11, 1) else 9011
    return city(1, MONTHS, [
        Listing(1, lambda s: True),                                               # 1 stays
        Listing(2, lambda s: s <= T),                                             # 2 leaves early
        Listing(3, lambda s: s <= D(2018, 8, 1)),                                 # 3 seen at day 30
        Listing(4, lambda s: s <= D(2018, 12, 1)),                                # 4 late
        Listing(5, lambda s: not D(2018, 9, 1) <= s <= D(2018, 11, 1)),           # 5 temporary
        Listing(6, lambda s: s != C2),                                            # 6 absent C2 only
        Listing(7, lambda s: s <= D(2019, 3, 1)),                                 # 7 after horizon
        Listing(10, lambda s: True, host=host_change),                            # 10 host change
        Listing(12, lambda s: s >= T, reviewed=False, rating=None, reviews=0),    # 12 new
        Listing(13, lambda s: s <= T or s >= D(2019, 7, 1)),                      # 13 comes back
        Listing(17, lambda s: True, reviewed=False, rating=None, reviews=0),      # 17 since coverage start
        Listing(18, lambda s: True),                                              # 17 control
    ])


def scenario_b():
    """No usable snapshot near t+270 (Feb-May 2019 missing). Examples 9, 14."""
    snaps = [s for s in MONTHS if not D(2019, 2, 1) <= s <= D(2019, 5, 1)]
    return city(2, snaps, [Listing(9, lambda s: s <= T), Listing(14, lambda s: True)])


def scenario_c():
    """No usable snapshot near t+180 (Nov 2018 - Feb 2019 missing). Example 15."""
    snaps = [s for s in MONTHS if not D(2018, 11, 1) <= s <= D(2019, 2, 1)]
    return city(3, snaps, [Listing(15, lambda s: True)])


def scenario_d():
    """Partial scrape at 2019-01-01, extra complete snapshot 2019-01-20. Examples 8, 11."""
    snaps = sorted(MONTHS + [D(2019, 1, 20)])
    return city(4, snaps, [Listing(81, lambda s: True), Listing(82, lambda s: s <= D(2018, 12, 1))],
                partial={D(2019, 1, 1)})


def scenario_e():
    """Genuine contraction at C3 (2019-04-01). Example 16."""
    return city(5, MONTHS, [Listing(16, lambda s: s <= D(2018, 12, 1))], contraction=C3)


def scenario_f():
    """Anomaly at the city's last snapshot: no resolver yet."""
    return city(6, MONTHS, partial={MONTHS[-1]})


def scenario_g():
    """Equidistant C2 candidates (t+170, t+190); no snapshot near t+90."""
    snaps = [D(2018, 4, 1), D(2018, 5, 1), D(2018, 6, 1), T, T + timedelta(170), T + timedelta(190),
             T + timedelta(270), T + timedelta(330)]                  # last one: after C3 window closes
    return city(7, snaps, [Listing(1, lambda s: True)])


def scenario_h():
    """Only one snapshot (t+225) in range of both C2 and C3."""
    snaps = [D(2018, 4, 1), D(2018, 5, 1), D(2018, 6, 1), T, T + timedelta(225), D(2019, 8, 1)]
    return city(8, snaps, [Listing(1, lambda s: True)])


def scenario_i():
    """Reviewer's case: absent at t+250, back at t+270; both fall in C3's window."""
    snaps = [D(2018, 4, 1), D(2018, 5, 1), D(2018, 6, 1), T, T + timedelta(180), T + timedelta(250),
             T + timedelta(270), T + timedelta(330)]
    back = {T, T + timedelta(270), T + timedelta(330)}
    return city(9, snaps, [Listing(91, lambda s: s in back)])


def scenario_j():
    """Two damaged snapshots in a row (Jan, Feb 2019), recovery in Mar 2019."""
    return city(10, MONTHS, [Listing(1, lambda s: True)], partial={D(2019, 1, 1), D(2019, 2, 1)})


def scenario_k():
    """Anomaly at 2019-06-01, then nothing until 2020-03-01 (past the 200-day wait)."""
    return city(11, MONTHS[:18] + [D(2020, 3, 1)], partial={D(2019, 6, 1)})


def scenario_l():
    """Partial scrape at t+180 whose reliable resolver (t+330) arrives after C3's window closes."""
    snaps = [D(2018, 4, 1), D(2018, 5, 1), D(2018, 6, 1), T, T + timedelta(90), T + timedelta(180),
             T + timedelta(330), T + timedelta(360)]
    return city(12, snaps, [Listing(1, lambda s: True)], partial={T + timedelta(180)})


SCENARIOS = [scenario_a, scenario_b, scenario_c, scenario_d, scenario_e, scenario_f, scenario_g, scenario_h,
             scenario_i, scenario_j, scenario_k, scenario_l]


@pytest.fixture(scope="module")
def con():
    return run([r for make in SCENARIOS for r in make()])


# --- worked examples ---------------------------------------------------------------

@pytest.mark.parametrize("list_id, expected", [
    (1, "observed"), (2, "absent_confirmed"), (3, "absent_confirmed"), (4, "absent_confirmed"),
    (5, "observed"), (6, "observed"), (7, "observed"), (13, "absent_confirmed"),
])
def test_presence_patterns(con, list_id, expected):
    row = lab(con, 1, T, list_id)
    assert (as_date(row.c1), as_date(row.c2), as_date(row.c3)) == (C1, C2, C3)
    assert row.outcome == expected


def test_day30_sighting_does_not_count_as_retained(con):
    # example 3: present in the 2018-08-01 snapshot, which is not a checkpoint
    row = lab(con, 1, T, 3)
    assert not row.in_c1 and not row.in_c2 and not row.in_c3
    assert row.outcome == "absent_confirmed"


def test_host_change_keeps_listing_outcome_and_host_at_t(con):
    row = lab(con, 1, T, 10)
    assert row.outcome == "observed" and row.host_at_t == 9010 and row.host_changed


def test_missing_c3_overrides_presence(con):
    for list_id in (9, 14):                          # absent / present at C2
        row = lab(con, 2, T, list_id)
        assert row.outcome == "insufficient_followup"
        assert row.followup_reason == "no_c3" and pd.isna(row.c3)


def test_missing_c2_overrides_presence(con):
    row = lab(con, 3, T, 15)                         # present at C3
    assert row.outcome == "insufficient_followup"
    assert row.followup_reason == "no_c2" and as_date(row.c3) == C3


def test_partial_scrape_skipped_for_next_usable_snapshot(con):
    assert status(con, 4, D(2019, 1, 1)) == "partial_scrape"
    assert as_date(cp(con, 4, T).c2) == D(2019, 1, 20)
    assert lab(con, 4, T, 81).outcome == "observed"
    assert lab(con, 4, T, 82).outcome == "absent_confirmed"


def test_flagged_snapshot_is_not_a_prediction_date(con):
    dates = con.execute("SELECT t FROM prediction_dates WHERE city_id = 4 AND t >= '2019-01-01' "
                        "AND t < '2019-04-01'").df().t.map(as_date).tolist()
    assert dates == [D(2019, 1, 20)]


def test_suspected_contraction_is_used_and_delays_label(con):
    s = one(con, "SELECT * FROM schedule WHERE city_id = 5 AND snap = ?", C3)
    # May 2019 is still flagged (its trailing median includes pre-drop counts), so the
    # first reliable resolver is June 2019
    assert s.status == "suspected_contraction" and as_date(s.resolver_snap) == D(2019, 6, 1)
    row = lab(con, 5, T, 16)
    assert as_date(row.c3) == C3 and row.outcome == "absent_confirmed"
    assert as_date(row.label_final_at) == D(2019, 6, 1) and row.label_status == "final"


def test_anomaly_without_resolver_is_pending(con):
    s = one(con, "SELECT * FROM schedule WHERE city_id = 6 AND snap = ?", MONTHS[-1])
    assert s.status == "anomaly_pending" and not s.usable_checkpoint and pd.isna(s.status_known_at)


def test_anomaly_unresolved_after_wait_limit(con):
    s = one(con, "SELECT * FROM schedule WHERE city_id = 11 AND snap = ?", D(2019, 6, 1))
    assert s.status == "anomaly_unresolved" and not s.usable_checkpoint
    assert as_date(s.status_known_at) == D(2019, 6, 1) + timedelta(200)


def test_consecutive_damage_resolved_by_reliable_snapshot(con):
    for snap in (D(2019, 1, 1), D(2019, 2, 1)):
        s = one(con, "SELECT * FROM schedule WHERE city_id = 10 AND snap = ?", snap)
        assert s.status == "partial_scrape"                       # not a "contraction"
        assert as_date(s.reference_snap) == D(2018, 12, 1)
        assert as_date(s.resolver_snap) == D(2019, 3, 1)


def test_rejected_snapshot_resolution_delays_finality(con):
    # Jan 2019 (partial) is nearer t+180 than the chosen Dec 2018, so C2 is final only
    # once Jan's status is known (Mar 2019), after the window closes (Feb 11)
    row = cp(con, 10, T)
    assert as_date(row.c2) == D(2018, 12, 1)
    assert as_date(row.c2_final_at) == D(2019, 3, 1)
    assert as_date(row.label_final_at) == T + timedelta(270 + 45)   # C3 window close
    at = D(2019, 2, 20)                                              # window closed, Jan unresolved
    early = cp(run([r for r in scenario_j() if r[1] <= at], as_of=at), 10, T)
    assert as_date(early.c2) == D(2018, 12, 1) and pd.isna(early.c2_final_at)


def test_c2_resolution_after_c3_window_delays_finality(con):
    # no usable C2 or C3, but the t+180 snapshot could still have turned out usable
    row = cp(con, 12, T)
    assert row.followup_reason == "no_c2_c3"
    assert as_date(row.c3_final_at) == T + timedelta(315)
    assert as_date(row.label_final_at) == T + timedelta(330)


def test_late_nearer_snapshot_keeps_label_provisional():
    rows = scenario_i()
    cut = T + timedelta(250)
    early = run([r for r in rows if r[1] <= cut], as_of=cut)
    row = lab(early, 9, T, 91)
    assert row.outcome == "absent_confirmed" and row.label_status == "provisional"
    full = lab(run(rows), 9, T, 91)
    assert as_date(full.c3) == T + timedelta(270) and full.outcome == "observed"
    assert full.label_status == "final" and as_date(full.label_final_at) == T + timedelta(315)


def test_insufficient_history(con):
    first3 = con.execute("SELECT status FROM schedule WHERE city_id = 1 ORDER BY snap LIMIT 4").df().status
    assert first3.tolist() == ["insufficient_history"] * 3 + ["ok"]
    assert con.execute("SELECT MIN(t) FROM prediction_dates WHERE city_id = 1").fetchone()[0] == D(2018, 4, 1)


# --- population ---------------------------------------------------------------------

def test_recently_first_observed_with_prior_coverage_is_eligible(con):
    row = lab(con, 1, T, 12)                         # first seen at t, 181 days after coverage start
    assert row.recently_first_observed and row.newness_known and not row.active_review
    assert row.eligible_main


def test_first_observed_at_coverage_start_is_newness_unknown(con):
    t = D(2018, 4, 1)
    row = lab(con, 1, t, 17)
    assert row.recently_first_observed and not row.newness_known and not row.eligible_main
    assert lab(con, 1, t, 18).eligible_main          # same timing, but has a recent review


# --- checkpoint selection --------------------------------------------------------------

def test_tie_breaks_to_earlier_and_c1_is_independent(con):
    row = cp(con, 7, T)
    assert as_date(row.c2) == T + timedelta(170)
    assert as_date(row.c3) == T + timedelta(270)
    assert pd.isna(row.c1) and row.followup_reason == "ok"
    assert lab(con, 7, T, 1).outcome == "observed"


def test_c3_must_be_after_c2(con):
    row = cp(con, 8, T)
    assert as_date(row.c2) == T + timedelta(225)
    assert pd.isna(row.c3) and row.followup_reason == "no_c3"


def test_checkpoints_only_use_usable_snapshots(con):
    bad = con.execute("""
        SELECT COUNT(*) FROM checkpoints c
        JOIN schedule s ON s.city_id = c.city_id AND s.snap IN (c.c1, c.c2, c.c3)
        WHERE NOT s.usable_checkpoint""").fetchone()[0]
    assert bad == 0
    bad_t = con.execute("""SELECT COUNT(*) FROM prediction_dates p JOIN schedule s
                           ON s.city_id = p.city_id AND s.snap = p.t WHERE s.status <> 'ok'""").fetchone()[0]
    assert bad_t == 0


# --- information availability ------------------------------------------------------------

COLS = ("list_id, c2, c3, label_final_at, outcome, in_c2, in_c3, active_review, "
        "recently_first_observed, newness_known, eligible_main")
TIMED = [scenario_a, scenario_d, scenario_e, scenario_g, scenario_i, scenario_j, scenario_l]


@pytest.mark.parametrize("make", TIMED)
def test_final_label_reproducible_at_its_final_date(make):
    rows = make()
    full = run(rows)
    decided = full.execute("SELECT city_id, t, label_final_at FROM checkpoints WHERE label_final").df()
    assert len(decided) > 0
    for d in decided.itertuples():
        at = as_date(d.label_final_at)
        cut = run([r for r in rows if r[1] <= at], as_of=at)
        assert cp(cut, d.city_id, as_date(d.t)).label_final
        q = f"SELECT {COLS} FROM labels WHERE city_id = ? AND t = ? ORDER BY list_id"
        pd.testing.assert_frame_equal(full.execute(q, [d.city_id, d.t]).df(),
                                      cut.execute(q, [d.city_id, d.t]).df(), check_dtype=False)


@pytest.mark.parametrize("make", TIMED)
def test_final_labels_never_change_as_data_arrives(make):
    """Append data 15 days at a time; once a label is final it must equal the
    full-data label, and never move."""
    rows = make()
    q = f"SELECT city_id, t, {COLS} FROM labels WHERE label_status = 'final' ORDER BY city_id, t, list_id"
    truth = run(rows).execute(q).df().set_index(["city_id", "t", "list_id"])
    start, end = min(r[1] for r in rows), max(r[1] for r in rows) + timedelta(30)
    seen = 0
    cutoff = start + timedelta(120)
    while cutoff <= end:
        got = run([r for r in rows if r[1] <= cutoff], as_of=cutoff).execute(q).df()
        got = got.set_index(["city_id", "t", "list_id"])
        assert (got["label_final_at"] <= pd.Timestamp(cutoff)).all()
        missing = got.index.difference(truth.index)
        assert len(missing) == 0, f"final at {cutoff} but not final in full data: {list(missing)[:3]}"
        pd.testing.assert_frame_equal(got, truth.loc[got.index], check_like=True, check_dtype=False)
        seen = max(seen, len(got))
        cutoff += timedelta(15)
    assert seen > 0


# --- scrape lag: snapshots are known when collected, not on their file date -------------

LAG_PARAMS = {**label.PARAMS, "max_scrape_lag_days": 7}


def test_known_dates_follow_collection_not_file_date():
    con = run(scenario_a(), params=LAG_PARAMS, scrape_lag=6)
    s = one(con, "SELECT * FROM schedule WHERE city_id = 1 AND snap = ?", T)
    assert as_date(s.available_at) == T + timedelta(6) and as_date(s.status_known_at) == T + timedelta(6)
    p = one(con, "SELECT * FROM prediction_dates WHERE city_id = 1 AND t = ?", T)
    assert as_date(p.decision_date) == T + timedelta(6)
    # C3 window ends t+315; rows dated in it can arrive up to 7 days later
    assert as_date(cp(con, 1, T).label_final_at) == T + timedelta(315 + 7)


def test_rows_scraped_later_than_assumed_are_rejected():
    with pytest.raises(ValueError, match="max_scrape_lag_days"):
        run(scenario_a(), params=LAG_PARAMS, scrape_lag=10)


def test_as_of_compares_collection_dates():
    rows = [r for r in scenario_a() if r[1] <= T]
    with pytest.raises(ValueError, match="after as_of"):
        run(rows, as_of=T + timedelta(3), params=LAG_PARAMS, scrape_lag=6)   # T collected on T+6
    assert run(rows, as_of=T + timedelta(6), params=LAG_PARAMS, scrape_lag=6) is not None
