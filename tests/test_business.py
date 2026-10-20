"""Tests for the business evaluation (src/business.py).

    .venv/bin/python -m pytest tests -q
"""
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import business  # noqa: E402

D = date


def listings(**cols):
    base = dict(quarter="2020Q1", city_id=11, room_type="Entire home/apt", neighbourhood="A",
                price=100.0, review_rate_365=1.0, review_rate_90=1.0, min_night=2.0,
                host_id_at_t=1, target=False, lgbm=0.1, rule=0.0, decision_date=D(2020, 1, 5))
    n = max((len(v) for v in cols.values() if isinstance(v, list)), default=1)
    df = pd.DataFrame([base] * n)
    for k, v in cols.items():
        df[k] = v
    return df


def test_value_proxy_formula():
    v = business.value_proxy(listings(), review_share=0.5).value.iloc[0]
    # 1 review / 30 d -> 12.17 reviews/yr -> 24.3 bookings at 50% -> x 3 nights = 73 nights x $100
    assert v == pytest.approx(100 * (365 / 30) / 0.5 * 3)


def test_value_proxy_caps_occupancy_and_handles_missing():
    df = business.value_proxy(listings(review_rate_365=[100.0, np.nan, -2.0], review_rate_90=[1.0, 2.0, 1.0],
                                       price=[100.0, 100.0, 100.0]), 0.5)
    assert df.value.iloc[0] == pytest.approx(100 * 0.70 * 365)            # 70% occupancy cap
    assert df.value.iloc[1] == pytest.approx(100 * 2 * (365 / 30) / 0.5 * 3)   # falls back to the 90-day rate
    assert df.value.iloc[2] == 0                                          # reviews decreased -> no bookings


def test_missing_price_filled_from_same_quarter_neighbourhood():
    df = business.value_proxy(listings(price=[np.nan, 80.0, 120.0], host_id_at_t=[1, 2, 3]), 0.5)
    assert df.price_imputed.tolist() == [True, False, False]
    assert df.value.iloc[0] == pytest.approx(100 * (365 / 30) / 0.5 * 3)    # median of 80 and 120 = 100


def test_host_exposure_is_sum_of_p_times_v_not_max_p_times_portfolio():
    # host 1: one risky small listing + one safe large listing; host 2: one moderately risky large listing
    df = listings(host_id_at_t=[1, 1, 2], lgbm=[0.9, 0.05, 0.5], target=[True, False, True])
    df["value"] = [100.0, 10_000.0, 2_000.0]
    hosts = business.host_table(df, "lgbm", "rule").set_index("host_id_at_t")
    assert hosts.loc[1, "exposure"] == pytest.approx(0.9 * 100 + 0.05 * 10_000)   # 590, not 0.9 x 10,100
    assert hosts.loc[2, "exposure"] == pytest.approx(1000)
    assert hosts.loc[1, "risk_max"] == 0.9 and hosts.loc[1, "value_total"] == 10_100
    assert hosts.loc[1, "lost_value"] == 100                                       # only the absent listing


def test_contact_date_is_earliest_decision_date_across_markets():
    df = listings(host_id_at_t=[7, 7], city_id=[11, 24], decision_date=[D(2020, 1, 9), D(2020, 1, 3)])
    df["value"] = 1.0
    assert business.host_table(df, "lgbm", "rule").contact_date.iloc[0] == D(2020, 1, 3)


def test_strategies_rank_differently_and_capture_only_contacted_losses():
    df = listings(host_id_at_t=[1, 1, 2, 3], lgbm=[0.9, 0.05, 0.5, 0.2], target=[True, False, True, False])
    df["value"] = [100.0, 10_000.0, 2_000.0, 50.0]
    hosts, res = business.evaluate(df, "lgbm", "rule", ks=(1,))
    top = res.set_index("strategy")
    assert top.loc["risk (max p)", "captured"] == 100        # host 1 (max p 0.9), its absent listing only
    assert top.loc["risk × value (Σ p·V)", "captured"] == 2000   # host 2 (exposure 1000 > 590)
    assert top.loc["value only (Σ V)", "captured"] == 100    # host 1 (portfolio 10,100)
    assert top.loc["random (expected)", "captured"] == pytest.approx(2100 / 3)


def test_net_benefit_and_breakeven():
    assert business.net_benefit(1_000_000, 500, 0.1, 0.15, 100) == pytest.approx(15_000 - 50_000)
    assert business.breakeven_cost(1_000_000, 500, 0.1, 0.15) == pytest.approx(30.0)
    assert business.net_benefit(1_000_000, 500, 0.1, 0.15, business.breakeven_cost(1_000_000, 500, 0.1, 0.15)) \
        == pytest.approx(0)


def test_sample_size_grows_as_effect_shrinks():
    assert business.hosts_per_arm(0.6, 0.05) > business.hosts_per_arm(0.6, 0.10) > business.hosts_per_arm(0.6, 0.20)


def test_portfolio_buckets():
    assert business.portfolio_bucket(pd.Series([1, 2, 5, 6, 20, 21])).astype(str).tolist() == \
        ["1", "2–5", "2–5", "6–20", "6–20", "21+"]


def test_freeze_detects_changed_files(tmp_path, monkeypatch):
    import json
    import freeze
    a = tmp_path / "a.py"
    a.write_text("x = 1\n")
    spec = tmp_path / "freeze.json"
    spec.write_text(json.dumps({"purpose": "test"}))
    monkeypatch.setattr(freeze, "FREEZE", spec)
    monkeypatch.setattr(freeze, "FROZEN_FILES", [a])
    monkeypatch.setattr(freeze, "PROJECT", tmp_path)
    with pytest.raises(SystemExit, match="not frozen"):
        freeze.verify()
    freeze.write()
    assert freeze.verify()["file_sha256"]
    a.write_text("x = 2\n")
    with pytest.raises(SystemExit, match="changed since the freeze"):
        freeze.verify()
