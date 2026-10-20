"""Tests for the quality-policy layer (src/quality.py, config/quality_policy.json).

    .venv/bin/python -m pytest tests -q
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import quality  # noqa: E402
from test_features import enrich, run  # noqa: E402
from test_label import Listing, city  # noqa: E402

D = date
PRE, POST = D(2023, 1, 16), D(2023, 6, 10)            # break gap in market 11
POLICY = {
    "policy_version": "test.1",
    "breaks": [{"break_id": "SB-T", "status": "suspected", "markets": {"11": [str(PRE), str(POST)]}}],
    "variants": {"retain": {"apply_breaks": False},
                 "exclude": {"apply_breaks": True, "effective_date": "2023-07-15"}},
}


def rows(**cols):
    base = dict(city_id=11, t=D(2023, 9, 10), decision_date=D(2023, 9, 12), c2=D(2024, 3, 1), c3=D(2024, 6, 1),
                lag365_snap=D(2022, 9, 12), lag90_snap=D(2023, 6, 10), days_since_first_observed=1000,
                first_observed_censored=False, presence_rate_365=0.9, hist_snapshots_365=8.0,
                hist_present_365=7.0, review_rate_365=1.0, review_rate_90=1.0, target=True)
    n = max((len(v) for v in cols.values() if isinstance(v, list)), default=1)
    df = pd.DataFrame([base] * n)
    for k, v in cols.items():
        df[k] = v
    for c in quality.MASK_LAG365 + quality.MASK_LAG90:
        if c not in df:
            df[c] = 1.0
    return df


def test_retain_changes_nothing():
    df = rows()
    out = quality.apply_policy(df, POLICY, "retain", "score")
    assert not out.history_crosses_break.any()
    pd.testing.assert_frame_equal(out.drop(columns="history_crosses_break"), df)
    assert len(quality.apply_policy(rows(t=D(2023, 1, 16), c3=D(2023, 9, 1)), POLICY, "retain", "train",
                                    D(2024, 1, 1))) == 1


def test_no_flags_or_masks_before_effective_date():
    # decided 2023-07-01, before the policy's effective date: history crosses the break,
    # but the row must come out exactly as it went in
    df = rows(t=D(2023, 6, 28), decision_date=D(2023, 7, 1), lag365_snap=D(2022, 6, 28))
    out = quality.apply_policy(df, POLICY, "exclude", "score")
    assert not out.history_crosses_break.any()
    pd.testing.assert_frame_equal(out.drop(columns="history_crosses_break"), df)


def test_masks_only_features_that_cross_the_break():
    df = rows()                                    # decided after the effective date
    out = quality.apply_policy(df, POLICY, "exclude", "score").iloc[0]
    assert out.history_crosses_break
    assert np.isnan(out.review_rate_365) and np.isnan(out.presence_rate_365)    # windows reach before PRE
    assert out.review_rate_90 == 1.0                                            # lag90 anchor is POST itself


def test_tenure_restarting_at_the_break_is_censored():
    first_seen_at_post = (D(2023, 9, 12) - POST).days
    out = quality.apply_policy(rows(days_since_first_observed=first_seen_at_post), POLICY, "exclude", "score")
    assert out.iloc[0].first_observed_censored


def test_other_markets_untouched():
    df = rows(city_id=24)
    out = quality.apply_policy(df, POLICY, "exclude", "score")
    assert not out.history_crosses_break.any()
    pd.testing.assert_frame_equal(out.drop(columns="history_crosses_break"), df)


def test_training_exclusion_only_from_effective_date():
    crossing = rows(t=[D(2023, 1, 16), D(2023, 6, 10)], c3=[D(2023, 9, 10), D(2024, 3, 1)])
    before = quality.apply_policy(crossing, POLICY, "exclude", "train", D(2023, 7, 1))
    after = quality.apply_policy(crossing, POLICY, "exclude", "train", D(2024, 1, 1))
    assert len(before) == 2                        # deployment before the effective date
    assert list(after.t) == [D(2023, 6, 10)]       # only the cohort whose follow-up spans the gap is dropped


def test_evaluation_drops_crossing_comparisons():
    ev = rows(t=[D(2023, 1, 16), D(2023, 6, 10)], c3=[D(2023, 9, 10), D(2024, 3, 1)])
    assert list(quality.apply_policy(ev, POLICY, "exclude", "evaluate").t) == [D(2023, 6, 10)]


def test_config_policy_is_complete():
    p = quality.load_policy()
    assert p["policy_version"] and p["variants"]["retain"]["apply_breaks"] is False
    ex = p["variants"]["exclude"]
    assert ex["apply_breaks"] and ex["effective_date"]
    for b in p["breaks"]:
        assert b["status"] == "suspected" and b["cause"] == "unresolved"
        for key in ["break_id", "markets", "evidence", "evidence_available_at", "detectable_at", "identified_at"]:
            assert key in b
        assert all(pre < post for pre, post in b["markets"].values())
        assert ex["effective_date"] >= max(b["detectable_at"].values())   # never earlier than detectable


# --- re-keying detector -------------------------------------------------------------------

def rekey_world():
    """City 11: listings 1-20 vanish at the 2018-07-01 snapshot and reappear as 101-120 with
    the same host, neighbourhood, room type, capacity and review count."""
    months = list(pd.date_range("2018-01-01", periods=12, freq="MS").date)
    cut = D(2018, 7, 1)
    ls = [Listing(i, (lambda s: s < cut), host=lambda s, i=i: 900 + i) for i in range(1, 21)]
    ls += [Listing(100 + i, (lambda s: s >= cut), host=lambda s, i=i: 900 + i) for i in range(1, 21)]
    out = enrich(city(11, months, ls))
    for r in out:                                  # same neighbourhood for the old/new pair
        if r["list_id"] <= 120:
            r["neighbourhood"] = f"N{r['list_id'] % 100}"
    return out


def test_rekey_detector_flags_the_swap_only():
    con = run(rekey_world())
    det = quality.detect_rekeying(con).set_index("snap")
    assert det.loc[pd.Timestamp(D(2018, 7, 1)), "rekey_share"] == pytest.approx(1.0)
    others = det.drop(index=pd.Timestamp(D(2018, 7, 1)))
    assert (others.rekey_share.fillna(0) == 0).all()


def test_rekey_detector_uses_only_the_two_snapshots():
    full = rekey_world()
    det_full = quality.detect_rekeying(run(full)).set_index("snap")
    cut = [r for r in full if r["snap"] <= D(2018, 7, 1)]
    det_cut = quality.detect_rekeying(run(cut)).set_index("snap")
    pd.testing.assert_frame_equal(det_cut, det_full.loc[det_cut.index], check_dtype=False)
