"""Tests for the backtest machinery: fold isolation, per-fold preprocessing,
host-level metrics and the holdout guard.

    .venv/bin/python -m pytest tests -q
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import backtest  # noqa: E402
import model  # noqa: E402
from features import ALLOWLIST  # noqa: E402
from test_features import enrich, run  # noqa: E402
from test_label import Listing, city  # noqa: E402


def frame(n, seed=0, price_scale=1.0):
    """Synthetic feature rows containing every allowlisted predictor."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({c: rng.normal(size=n) for c, k in ALLOWLIST.items() if k in ("numeric", "binary")})
    df["price"] = rng.lognormal(5, 1, n) * price_scale
    df["city_id"] = rng.choice([11, 19], n)
    df["room_type"] = rng.choice(["Entire home/apt", "Private room"], n)
    df["listing_type"] = rng.choice(["House"] * 99 + ["Castle"], n)
    df["quarter_of_year"] = rng.choice([1, 2, 3, 4], n)
    df.loc[: n // 10, "bedrooms"] = np.nan
    df["target"] = rng.random(n) < 0.2
    return df


def test_prep_learns_only_from_training_rows():
    train, later = frame(5000, seed=1), frame(5000, seed=2, price_scale=10)
    prep = model.Prep().fit(train)
    assert prep.upper["price"] == pytest.approx(train["price"].quantile(0.99))
    assert prep.median["bedrooms"] == pytest.approx(train["bedrooms"].clip(
        prep.lower["bedrooms"], prep.upper["bedrooms"]).median())
    # later rows are capped at the training p99 and use the training columns
    tree = prep.tree(later)
    assert tree["price"].max() == pytest.approx(train["price"].quantile(0.99))
    assert prep.linear(later).shape[1] == len(prep.linear_columns)


def test_prep_maps_rare_and_unseen_categories_to_other():
    train = frame(5000, seed=3)
    train["listing_type"] = ["House"] * 4996 + ["Castle"] * 4           # Castle < 0.1%
    prep = model.Prep().fit(train)
    later = frame(10, seed=4)
    later["listing_type"] = ["Castle"] * 5 + ["Igloo"] * 5             # rare + unseen
    assert set(prep.tree(later)["listing_type"].astype(str)) == {"other"}


def test_host_precision_counts_unique_hosts():
    df = pd.DataFrame({"host_id_at_t": [1, 1, 2, 3, 4],
                       "s": [0.9, 0.1, 0.8, 0.7, 0.6],
                       "target": [False, True, False, True, False]})
    hp, n_hosts, base = model.host_precision_at_k(df, "s", ks=(1, 2, 3))
    assert n_hosts == 4 and base == pytest.approx(0.5)
    # host 1 ranks first (max 0.9) and is a hit through its other listing
    assert hp == {"host_p@1": 1.0, "host_p@2": 0.5, "host_p@3": pytest.approx(2 / 3)}


def test_validation_split_is_latest_quarters():
    t = [date(2018, 1, 1) + timedelta(days=30 * i) for i in range(24)]
    df = pd.DataFrame({"t": t})
    fit, val = backtest.split_validation(df)
    assert pd.to_datetime(fit.t).max() < pd.to_datetime(val.t).min()
    assert pd.PeriodIndex(pd.to_datetime(val.t), freq="Q").nunique() == backtest.VAL_QUARTERS


def test_fold_rows_respect_deployment_date():
    # four years of monthly snapshots; listing i leaves after 60*i days
    months = list(pd.date_range("2018-01-01", periods=48, freq="MS").date)
    leavers = [Listing(i, lambda s, i=i: s <= date(2018, 1, 1) + timedelta(days=60 * i)) for i in range(1, 25)]
    con = run(enrich(city(31, months, leavers)))
    start, end = date(2020, 7, 1), date(2020, 10, 1)
    from features import training_frame
    train = training_frame(con, start)
    ev = backtest.evaluation_frame(con, start, end)
    assert len(train) > 0 and len(ev) > 0
    assert (pd.to_datetime(train.label_final_at) < pd.Timestamp(start)).all()
    assert (pd.to_datetime(train.t) < pd.Timestamp(start)).all()
    assert pd.to_datetime(ev.t).between(pd.Timestamp(start), pd.Timestamp(end), inclusive="left").all()


def test_development_run_stops_before_holdout():
    quarters = [s for s, e in backtest.quarter_starts(backtest.FIRST_DEPLOYMENT, backtest.HOLDOUT[0])]
    assert max(quarters) < backtest.HOLDOUT[0]
    assert all(e <= backtest.HOLDOUT[0] for s, e in backtest.quarter_starts(backtest.FIRST_DEPLOYMENT,
                                                                             backtest.HOLDOUT[0]))


def test_policy_variants_run_on_real_fold_frames():
    """The exclude variant's training, evaluation and scoring paths must work on the frames
    the backtest actually builds (training_frame / evaluation_frame)."""
    import quality
    months = list(pd.date_range("2018-01-01", periods=48, freq="MS").date)
    leavers = [Listing(i, lambda s, i=i: s <= date(2018, 1, 1) + timedelta(days=60 * i)) for i in range(1, 25)]
    con = run(enrich(city(31, months, leavers)))
    from features import training_frame
    policy = {"policy_version": "t", "breaks": [{"markets": {"31": ["2019-01-01", "2019-06-01"]}}],
              "variants": {"exclude": {"apply_breaks": True, "effective_date": "2020-01-01"}}}
    start, end = date(2020, 7, 1), date(2020, 10, 1)
    train = training_frame(con, start)
    kept = quality.apply_policy(quality.apply_policy(train, policy, "exclude", "train", start), policy, "exclude", "score")
    ev = backtest.evaluation_frame(con, start, end)
    scored = quality.apply_policy(quality.apply_policy(ev, policy, "exclude", "evaluate"), policy, "exclude", "score")
    assert 0 < len(kept) < len(train)               # follow-ups spanning the gap are dropped
    assert "history_crosses_break" in kept and "history_crosses_break" in scored
