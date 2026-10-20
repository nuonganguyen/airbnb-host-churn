"""Versioned data-quality policy (config/quality_policy.json) and its application.

The label and feature tables are never edited. A policy variant decides, for a given
decision date, which training/evaluation rows to drop and which history features to
mask. Nothing is applied to decisions made before the policy's effective date.

    python src/quality.py   # re-keying detector over all snapshot pairs -> reports/rekey_detection.md
"""
import json
from datetime import date

import duckdb
import numpy as np
import pandas as pd

from db import CITIES, LOCAL, PROJECT

POLICY = PROJECT / "config" / "quality_policy.json"

# history features that compare across a break, by the anchor that would cross it
MASK_LAG365 = ["lag365_days", "present_lag365", "price_change_365", "reviews_added_365", "review_rate_365",
               "city_supply_growth_365", "neighbourhood_supply_growth_365"]
MASK_LAG90 = ["lag90_days", "present_lag90", "price_change_90", "avail365_change_90", "rating_change_90",
              "reviews_added_90", "review_rate_90", "reviews_decreased_90", "host_listings_change_90"]
MASK_PRESENCE = ["hist_snapshots_365", "hist_present_365", "presence_rate_365"]


def load_policy(path=POLICY):
    return json.loads(path.read_text())


def detect_rekeying(con):
    """For each pair of consecutive snapshots in a city: of the listings that vanish, the
    share with at least one candidate replacement, a new id sharing host, neighbourhood,
    room type and capacity with at least the vanished listing's review count. Candidates
    are not one-to-one (several vanished ids may share one), so this is a screening
    signal, not a crosswalk. Uses only the two snapshots, so it is known once the later
    one is available."""
    return con.execute("""
        WITH snaps AS (
            SELECT city_id, snap, LAG(snap) OVER (PARTITION BY city_id ORDER BY snap) AS prev,
                   MAX(last_scraped) AS available_at
            FROM lf GROUP BY city_id, snap
        ),
        gone AS (
            SELECT s.city_id, s.snap, a.*  EXCLUDE (city_id, snap)
            FROM snaps s JOIN lf a ON a.city_id = s.city_id AND a.snap = s.prev
            WHERE NOT EXISTS (SELECT 1 FROM lf b WHERE b.city_id = s.city_id AND b.snap = s.snap
                              AND b.list_id = a.list_id)
        ),
        fresh AS (
            SELECT s.city_id, s.snap, b.* EXCLUDE (city_id, snap)
            FROM snaps s JOIN lf b ON b.city_id = s.city_id AND b.snap = s.snap
            WHERE NOT EXISTS (SELECT 1 FROM lf a WHERE a.city_id = s.city_id AND a.snap = s.prev
                              AND a.list_id = b.list_id)
        ),
        matched AS (
            SELECT DISTINCT g.city_id, g.snap, g.list_id
            FROM gone g JOIN fresh f
              ON f.city_id = g.city_id AND f.snap = g.snap AND f.host_id = g.host_id
             AND f.neighbourhood = g.neighbourhood AND f.room_type = g.room_type
             AND f.capacity = g.capacity
             AND g.number_of_reviews > 0 AND f.number_of_reviews >= g.number_of_reviews
        )
        SELECT s.city_id, s.prev, s.snap, s.available_at,
               (SELECT COUNT(*) FROM gone g WHERE g.city_id = s.city_id AND g.snap = s.snap) AS n_gone,
               (SELECT COUNT(*) FROM matched m WHERE m.city_id = s.city_id AND m.snap = s.snap) AS n_rekeyed
        FROM snaps s WHERE s.prev IS NOT NULL ORDER BY s.city_id, s.snap
    """).df().assign(rekey_share=lambda d: d.n_rekeyed / d.n_gone.where(d.n_gone > 0))


def _crosses(lo, hi, pre, post):
    """Interval [lo, hi] spans the break gap (pre, post): starts on/before pre, ends on/after post."""
    return (lo <= pre) & (hi >= post)


def _break_dates(df, brk):
    pre = df["city_id"].astype(str).map(lambda c: brk["markets"].get(c, [None, None])[0])
    post = df["city_id"].astype(str).map(lambda c: brk["markets"].get(c, [None, None])[1])
    return pd.to_datetime(pre), pd.to_datetime(post)


def apply_policy(df, policy, variant, role, decision_date=None):
    """Return df under a policy variant.

    role="train": drop labels whose follow-up (t, c3] crosses a break, for training runs
                  on/after the variant's effective date (`decision_date` = deployment).
    role="evaluate": drop rows whose follow-up crosses a break (retrospective evaluation).
    role="score": mask history features that compare across a break, only for rows whose
                  own decision_date is on/after the effective date; adds `history_crosses_break`.
    """
    spec = policy["variants"][variant]
    if not spec.get("apply_breaks"):
        return df.assign(history_crosses_break=False) if role == "score" else df
    out = df.copy()
    effective = pd.Timestamp(spec["effective_date"])
    t = pd.to_datetime(out["t"])
    if role in ("train", "evaluate"):
        if role == "train" and pd.Timestamp(decision_date) < effective:
            return out
        drop = pd.Series(False, index=out.index)
        for brk in policy["breaks"]:
            pre, post = _break_dates(out, brk)
            drop |= _crosses(t, pd.to_datetime(out["c3"]), pre, post).fillna(False)
        return out[~drop]
    assert role == "score"
    active = pd.to_datetime(out["decision_date"]) >= effective
    crossing = pd.Series(False, index=out.index)
    for brk in policy["breaks"]:
        pre, post = _break_dates(out, brk)
        lag365 = active & _crosses(pd.to_datetime(out["lag365_snap"]), t, pre, post).fillna(False)
        lag90 = active & _crosses(pd.to_datetime(out["lag90_snap"]), t, pre, post).fillna(False)
        presence = active & _crosses(t - pd.Timedelta(days=365), t, pre, post).fillna(False)
        first_seen = pd.to_datetime(out["decision_date"]) - pd.to_timedelta(out["days_since_first_observed"], unit="D")
        reset = active & (first_seen.dt.normalize() >= pre) & (first_seen.dt.normalize() <= post) & (t >= post)
        out.loc[lag365, MASK_LAG365] = np.nan
        out.loc[lag90, MASK_LAG90] = np.nan
        out.loc[presence, MASK_PRESENCE] = np.nan
        out.loc[reset, "first_observed_censored"] = True     # tenure may restart at the break
        crossing |= lag365 | lag90 | presence | reset
    return out.assign(history_crosses_break=crossing)


def main():
    import features
    con = duckdb.connect()
    features.load_clean(con)
    det = detect_rekeying(con)
    det.to_csv(LOCAL / "validation_clean" / "rekey_detection.csv", index=False)
    det["year"] = pd.to_datetime(det.snap).dt.year
    by_year = det.groupby("year").rekey_share.describe(percentiles=[.5, .95]).round(3).reset_index()
    top = det.sort_values("rekey_share", ascending=False).head(12).copy()
    top["city"] = top.city_id.map(CITIES)
    from label import md
    lines = ["# Re-keying Detection", "",
             f"Built {date.today():%Y-%m-%d} by `src/quality.py`. For each pair of consecutive snapshots: of the "
             "listings that vanish, the share with at least one candidate replacement: a new id sharing host, "
             "neighbourhood, room type and capacity with at least the vanished review count. Candidates are not "
             "one-to-one, so this screens for a break; it is not a crosswalk. Known once the later snapshot is available.", "",
             "## By year of the later snapshot", "", md(by_year), "",
             "## Highest pairs", "",
             md(top[["city", "prev", "snap", "available_at", "n_gone", "n_rekeyed", "rekey_share"]].round(3)), ""]
    (PROJECT / "reports" / "rekey_detection.md").write_text("\n".join(lines))
    print(top[["city", "prev", "snap", "n_gone", "n_rekeyed", "rekey_share"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
