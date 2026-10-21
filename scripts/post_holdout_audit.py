"""Post-holdout audit (2026-10-20). Recomputes checks raised in review AFTER the one-time
holdout run, from saved results only. It changes nothing in the frozen analysis and its
numbers are not holdout results of a prespecified analysis.

    .venv/bin/python scripts/post_holdout_audit.py   # -> reports/post_holdout_audit.md
"""
import sys
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
import business  # noqa: E402
from label import md  # noqa: E402

BT = PROJECT / "data_local" / "backtest"


def main():
    preds = business.load("holdout")
    lst = business.value_proxy(preds[preds.variant == "retain"], business.REVIEW_SHARES["central"])
    hosts = business.host_table(lst, "lgbm", "rule:low_presence_365")

    # 1. contact timing: hosts whose ranking used listings observed after their contact date
    last = lst.groupby(["quarter", "host_id_at_t"]).decision_date.max().rename("latest_decision")
    hosts = hosts.join(last, on=["quarter", "host_id_at_t"])
    late = []
    for name, col in [("risk (max p)", "risk_max"), ("risk × value (Σ p·V)", "exposure")]:
        top = business.top_k(hosts, col, 500)
        g = top.assign(uses_later=top.latest_decision > top.contact_date).groupby("quarter")
        late.append(g.agg(contacted=("hit", "size"), using_later_listings=("uses_later", "sum")).assign(ranking=name))
    late = pd.concat(late).reset_index()
    spread = (lst.groupby("quarter").decision_date.agg(["min", "max"])
                 .assign(days=lambda d: (pd.to_datetime(d["max"]) - pd.to_datetime(d["min"])).dt.days).reset_index())

    # 3. experiment sizing on the proposed recruitment population
    top1000 = business.top_k(hosts, "exposure", 1000)
    rates = top1000.groupby("quarter").hit.mean()
    p = float(top1000.hit.mean())
    sizing = pd.DataFrame([{"relative reduction": f"{r:.0%}", "event rate (top 1,000 by Σ p·V, holdout)": round(p, 3),
                            "independent hosts per arm": business.hosts_per_arm(p, r),
                            "recruitment quarters at 500 new hosts per arm":
                                -(-business.hosts_per_arm(p, r) // 500)} for r in (0.05, 0.10, 0.20)])

    # 2. calibration, from the frozen holdout outputs
    m = pd.read_csv(BT / "holdout_metrics.csv").query("variant == 'retain' and model in ['lgbm', 'lr']")
    f = pd.read_csv(BT / "holdout_folds.csv").query("variant == 'retain'")[["quarter", "base_rate"]]
    cal = m.merge(f, on="quarter").assign(gap_pp=lambda d: 100 * (d.mean_pred - d.base_rate))
    cal = cal.pivot(index="quarter", columns="model", values="gap_pp").round(1).reset_index()

    lines = [
        "# Post-Holdout Audit", "",
        "Run after the one-time holdout, from saved results, in response to review. **Nothing here changes the frozen "
        "analysis or its reported holdout results**; these numbers are audits, not prespecified holdout results.", "",
        "## 1. Contact timing vs information used", "",
        "The frozen host aggregation pools a host's eligible listings across markets for the whole quarter, and assigns "
        "the earliest decision date as the contact date. Contacted hosts whose ranking used listings observed **after** "
        "that date:", "", md(late), "",
        "Spread of decision dates within each quarter (markets are scraped on different days):", "", md(spread), "",
        "So the frozen results are a **pooled quarterly ranking benchmark**. A deployable contact policy needs a shared "
        "information cutoff (e.g. contact on the quarter's last decision date) or a sequential selection as each market "
        "arrives. Neither has been evaluated.", "",
        "## 2. Calibration on the holdout", "",
        "Mean predicted probability minus observed rate, in percentage points, per holdout quarter:", "", md(cal), "",
        f"LightGBM mean absolute gap: **{cal['lgbm'].abs().mean():.1f} pp**, worst **{cal['lgbm'].abs().max():.1f} pp**. "
        "Probability-weighted value (Σ p·V) is affected; the rank-based precision metrics are not.", "",
        "## 3. Experiment sizing on the proposed recruitment population", "",
        "The frozen business report sized the experiment from the top 500 hosts by risk (event rate 0.512). The proposal "
        "recruits the top 1,000 by Σ p·V, whose holdout event rate is lower:", "",
        md(rates.round(3).rename("event rate").reset_index()), "", md(sizing), "",
        "Hosts recur across quarters; each host can be randomized once, so only new hosts count toward the totals. "
        "Outcomes need ~9–10 months of follow-up after the last recruitment quarter.", "",
    ]
    (PROJECT / "reports" / "post_holdout_audit.md").write_text("\n".join(lines))
    print(late.to_string(index=False)); print(cal.to_string(index=False)); print(sizing.to_string(index=False))


if __name__ == "__main__":
    main()
