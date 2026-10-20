"""Business evaluation of backtest rankings (docs/business_spec.md).

Three outputs per quality-policy variant and quarter:
  1. targeting value: host precision@K, lift over the rule, results by portfolio size
  2. value exposure: estimated value associated with correctly flagged disappearances
  3. intervention scenarios: net benefit by cost per contact, prevention rate and take rate

    python src/business.py             # development predictions -> reports/business_development.md
    python src/business.py --holdout   # holdout predictions (after the freeze)
"""
import json
import sys
from datetime import date

import duckdb
import numpy as np
import pandas as pd

from db import LOCAL, PROJECT
from label import md

FREEZE = PROJECT / "config" / "analysis_freeze.json"
OUT = LOCAL / "backtest"

# --- value proxy -----------------------------------------------------------------------
# V_i: 12-month gross booking value proxy at the listing's asking price, host side.
# bookings/yr = reviews per 30 days x (365/30) / review_share; nights = bookings x stay,
# stay = max(min nights capped at 30, 3); nights capped at 70% of the year.
# Not realized revenue: asking prices and review-based bookings are both proxies.
REVIEW_SHARES = {"high_value": 0.30, "central": 0.50, "low_value": 0.72}
AVG_STAY = 3
MAX_OCCUPANCY = 0.70
STAY_CAP = 30


def value_proxy(df, review_share):
    """V_i per listing row. Expects price, review_rate_365, review_rate_90, min_night,
    city_id, room_type, neighbourhood, quarter. Missing prices are filled with the median
    of the same city, room type and neighbourhood at that quarter's prediction dates
    (then city and room type), and flagged; prices are capped at that quarter's p99."""
    out = df.copy()
    price = out["price"].where(out["price"] > 0)
    for keys in (["quarter", "city_id", "room_type", "neighbourhood"], ["quarter", "city_id", "room_type"]):
        price = price.fillna(out.assign(_p=price).groupby(keys)["_p"].transform("median"))
    out["price_imputed"] = out["price"].isna() | (out["price"] <= 0)
    cap = price.groupby(out["quarter"]).transform(lambda p: p.quantile(0.99))
    price = price.clip(upper=cap)
    rate = out["review_rate_365"].fillna(out["review_rate_90"]).fillna(0.0).clip(lower=0.0)
    stay = np.maximum(out["min_night"].fillna(AVG_STAY).clip(upper=STAY_CAP), AVG_STAY)
    nights = np.minimum(rate * (365 / 30) / review_share * stay, MAX_OCCUPANCY * 365)
    out["value"] = (price * nights).fillna(0.0)
    out["value_missing_price"] = price.isna()
    return out


# --- host ranking strategies -----------------------------------------------------------

def host_table(listings, risk_col, rule_col):
    """One row per (quarter, host). Contact timing: the earliest decision date among the
    host's eligible listings in that quarter."""
    g = listings.assign(exposure=listings[risk_col] * listings["value"],
                        lost_value=listings["value"] * listings["target"])
    return (g.groupby(["quarter", "host_id_at_t"])
             .agg(risk_max=(risk_col, "max"), exposure=("exposure", "sum"), value_total=("value", "sum"),
                  rule=(rule_col, "max"), hit=("target", "max"), lost_value=("lost_value", "sum"),
                  n_listings=("target", "size"), contact_date=("decision_date", "min"))
             .reset_index())


STRATEGIES = {
    "risk (max p)": "risk_max",           # ranking heuristic; not a portfolio probability
    "risk × value (Σ p·V)": "exposure",
    "value only (Σ V)": "value_total",
    "best rule": "rule",
}


def top_k(hosts, score, k):
    return (hosts.sort_values(["quarter", score, "host_id_at_t"], ascending=[True, False, True])
                 .groupby("quarter").head(k))


def portfolio_bucket(n):
    return pd.cut(n, [0, 1, 5, 20, np.inf], labels=["1", "2–5", "6–20", "21+"])


def evaluate(listings, risk_col, rule_col, ks=(100, 500, 1000)):
    hosts = host_table(listings, risk_col, rule_col)
    totals = hosts.groupby("quarter").agg(n_hosts=("hit", "size"), host_base=("hit", "mean"),
                                          lost_total=("lost_value", "sum"))
    rows = []
    for k in ks:
        for name, col in STRATEGIES.items():
            sel = top_k(hosts, col, k)
            q = sel.groupby("quarter").agg(precision=("hit", "mean"), captured=("lost_value", "sum"),
                                           listings_covered=("n_listings", "sum")).join(totals)
            q["captured_share"] = q.captured / q.lost_total
            rows.append(q.assign(strategy=name, k=k).reset_index())
        # random contact: expected values
        rnd = totals.assign(precision=totals.host_base, captured=totals.lost_total * np.minimum(k / totals.n_hosts, 1),
                            listings_covered=np.nan, captured_share=np.minimum(k / totals.n_hosts, 1))
        rows.append(rnd.assign(strategy="random (expected)", k=k).reset_index())
    return hosts, pd.concat(rows, ignore_index=True)


def by_portfolio(hosts, k=500, score="risk_max"):
    sel = top_k(hosts, score, k).assign(bucket=lambda d: portfolio_bucket(d.n_listings))
    allh = hosts.assign(bucket=lambda d: portfolio_bucket(d.n_listings))
    contacted = sel.groupby("bucket", observed=True).agg(contacted=("hit", "size"), precision=("hit", "mean"),
                                                         captured_value=("lost_value", "sum"))
    base = allh.groupby("bucket", observed=True).agg(hosts=("hit", "size"), base_rate=("hit", "mean"))
    out = base.join(contacted)
    out["contacted_share"] = out.contacted / out.contacted.sum()
    out["lift"] = out.precision / out.base_rate
    out["captured_value_share"] = out.captured_value / out.captured_value.sum()
    return out.drop(columns="captured_value").reset_index()


def paired_comparison(results, a, b, k, intervals=True):
    """Quarter-by-quarter difference between two strategies, with a moving-block bootstrap
    over consecutive quarters (quarters overlap through the ~9-month follow-up). With
    intervals=False (the four-quarter holdout), each quarter's difference is listed instead."""
    from backtest import block_bootstrap_ci
    rows = []
    for (variant, scen), g in results[results.k == k].groupby(["variant", "value_scenario"]):
        w = g.pivot(index="quarter", columns="strategy").sort_index()
        for metric in ["precision", "captured"]:
            d = w[metric][a] - w[metric][b]
            rel = (w[metric][a] / w[metric][b] - 1)
            unit = 1e6 if metric == "captured" else 1
            row = {"variant": variant, "value_scenario": scen, "metric": metric,
                   "mean difference": round(float(d.mean()) / unit, 3),
                   "mean relative": f"{rel.mean():+.1%}", "quarters better": f"{(d > 0).sum()}/{len(d)}"}
            if intervals:
                _, lo, hi = block_bootstrap_ci(d)
                row["block bootstrap 95%"] = f"[{lo / unit:.3f}, {hi / unit:.3f}]"
            else:
                row.update({q: round(float(x) / unit, 3) for q, x in d.items()})
            rows.append(row)
    return pd.DataFrame(rows)


def net_benefit(captured, k, prevent, take_rate, cost):
    """Platform net benefit of contacting k hosts in a quarter: the prevented share of the
    platform's cut of value that would otherwise disappear, minus contact costs."""
    return prevent * take_rate * captured - cost * k


def breakeven_cost(captured, k, prevent, take_rate):
    return prevent * take_rate * captured / k


# --- experiment sizing -------------------------------------------------------------------

def hosts_per_arm(p_control, relative_reduction, alpha=0.05, power=0.8):
    """Two-proportion sample size per arm for host-level hit rates (normal approximation)."""
    from scipy.stats import norm
    p1, p2 = p_control, p_control * (1 - relative_reduction)
    za, zb = norm.ppf(1 - alpha / 2), norm.ppf(power)
    pbar = (p1 + p2) / 2
    n = (za * np.sqrt(2 * pbar * (1 - pbar)) + zb * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p1 - p2) ** 2
    return int(np.ceil(n))


# --- driver --------------------------------------------------------------------------------

def load(name):
    """Backtest predictions joined to the at-t inputs of the value proxy."""
    con = duckdb.connect()
    return con.execute(f"""
        SELECT p.*, f.decision_date, f.price, f.review_rate_365, f.review_rate_90, f.min_night, f.room_type,
               n.neighbourhood
        FROM '{OUT / f"{name}_predictions.parquet"}' p
        JOIN '{LOCAL / "features.parquet"}' f USING (city_id, list_id, t)
        LEFT JOIN (SELECT TRY_CAST(CITY_ID AS DOUBLE)::INTEGER AS city_id, TRY_CAST(KEY_LIST_ID AS BIGINT) AS list_id,
                          strptime(DATE, '%Y%m%d')::DATE AS t, neighbourhood
                   FROM '{LOCAL / "listings_6city_clean.parquet"}' WHERE NOT id_imprecise) n
          USING (city_id, list_id, t)
    """).df()


def main(holdout=False):
    freeze = json.loads(FREEZE.read_text())
    if holdout:
        import freeze as fz
        fz.verify()
    name = "holdout" if holdout else "dev"
    preds = load(name)
    rule_col = freeze["best_rule"]
    k_main = freeze["business"]["contacts_per_quarter"]
    sections, summary_rows, nb_rows = [], [], []
    for variant in freeze["quality_variants"]:
        lv = preds[preds.variant == variant]
        for scen, share in REVIEW_SHARES.items():
            lst = value_proxy(lv, share)
            hosts, res = evaluate(lst, "lgbm", rule_col)
            res = res.assign(variant=variant, value_scenario=scen)
            summary_rows.append(res)
            if scen == "central":
                port = pd.concat([by_portfolio(hosts, k_main, "risk_max").assign(ranking="risk (max p)"),
                                  by_portfolio(hosts, k_main, "exposure").assign(ranking="risk × value (Σ p·V)")])
                sections.append((variant, port.assign(variant=variant), lst))
    res = pd.concat(summary_rows, ignore_index=True)
    res.to_csv(OUT / f"{name}_business.csv", index=False)

    central = res[res.value_scenario == "central"]
    mean = (central.groupby(["variant", "k", "strategy"])
                   [["precision", "captured", "captured_share", "listings_covered"]].mean().reset_index())
    targeting = (central[central.k == k_main].pivot_table(index=["variant", "quarter"], columns="strategy",
                                                           values="precision").round(3).reset_index())
    exposure = (res[res.k == k_main].groupby(["variant", "value_scenario", "strategy"])
                [["captured", "captured_share"]].mean().reset_index())
    exposure["captured ($M / quarter)"] = (exposure.captured / 1e6).round(2)
    exposure = exposure.drop(columns="captured").round(3)

    grid = freeze["business"]
    for variant in freeze["quality_variants"]:
        cap = central[(central.variant == variant) & (central.k == k_main)].groupby("strategy").captured.mean()
        for strat in ["risk × value (Σ p·V)", "risk (max p)", "value only (Σ V)", "best rule", "random (expected)"]:
            for prevent in grid["prevention_rates"]:
                for take in grid["take_rates"]:
                    row = {"variant": variant, "strategy": strat, "prevention_rate": prevent, "take_rate": take,
                           "breakeven_cost_per_contact": round(breakeven_cost(cap[strat], k_main, prevent, take), 2)}
                    for cost in grid["costs_per_contact"]:
                        row[f"net @ ${cost}"] = round(net_benefit(cap[strat], k_main, prevent, take, cost) / 1e3, 1)
                    nb_rows.append(row)
    nb = pd.DataFrame(nb_rows)
    prim = central[(central.variant == "retain") & (central.k == k_main)]
    p_ctrl = prim[prim.strategy == "risk (max p)"].precision.mean()
    sizing = pd.DataFrame([{"relative reduction in hosts with a disappearance": f"{r:.0%}",
                            "control hit rate (top-ranked hosts)": round(p_ctrl, 3),
                            "hosts per arm": hosts_per_arm(p_ctrl, r),
                            "quarters at 500 treated + 500 control": int(np.ceil(hosts_per_arm(p_ctrl, r) / k_main))}
                           for r in (0.05, 0.10, 0.20)])
    imputed = sections[0][2].price_imputed.mean()
    vs_value = paired_comparison(res, "risk × value (Σ p·V)", "value only (Σ V)", k_main, intervals=not holdout)
    vs_rule = paired_comparison(res[res.value_scenario == "central"], "risk (max p)", "best rule", k_main,
                                intervals=not holdout)

    title = "holdout" if holdout else "development"
    lines = [
        f"# Business Evaluation: {title}", "",
        f"Built {date.today():%Y-%m-%d} by `src/business.py` from `{name}_predictions.parquet` under the frozen "
        f"analysis (`config/analysis_freeze.json`). Model scores are LightGBM; the rule is `{rule_col}`. "
        f"K = {k_main} unique hosts per quarter unless noted. See `docs/business_spec.md` for definitions.", "",
        "**Value proxy V_i:** 12-month gross booking value at the asking price, estimated from reviews (scenarios for the "
        "share of stays that leave a review: 0.30 / 0.50 / 0.72). Host-side value, not realized revenue and not Airbnb "
        f"revenue. Missing prices are filled from neighbourhood × room medians ({imputed:.1%} of rows, primary variant).", "",
        "## 1. Targeting value", "",
        f"Host precision@{k_main} per quarter (share of contacted hosts with ≥ 1 eligible listing `absent_confirmed`).", "",
        md(targeting), "",
        "### Mean over quarters, central value scenario", "",
        md(mean.round(3).assign(captured=lambda d: (d.captured / 1e6).round(2)).rename(columns={"captured": "captured $M"})),
        "",
        f"### Lift over the rule, host precision@{k_main} (risk ranking vs `{rule_col}`)", "",
        md(vs_rule[vs_rule.metric == "precision"].drop(columns=["value_scenario", "metric"])), "",
        "### By host portfolio size (eligible listings in the quarter), primary variant", "",
        "`contacted_share`: share of the contacted hosts in each size group. `captured_value_share`: share of the "
        "captured disappearing value coming from that group.", "",
        md(sections[0][1].drop(columns="variant").round(3)), "",
        "## 2. Value exposure", "",
        f"Estimated value associated with correctly flagged disappearances: the summed V_i of `absent_confirmed` listings "
        f"held by the {k_main} contacted hosts, per quarter (mean over quarters). `captured_share` is that value as a share "
        "of all disappearing value among eligible listings that quarter. Host exposure for ranking is Σ p_i·V_i over the "
        "host's listings, never max p × portfolio value.", "",
        md(exposure), "",
        "### Does risk add anything over value alone?", "",
        f"Quarter-by-quarter difference, risk × value minus value only, at K = {k_main} (captured in $M per quarter). "
        "Value per host is heavy-tailed, so both rankings favour large portfolios; the comparison shows how much the "
        "risk score adds on top.", "", md(vs_value), "",
        "## 3. Intervention scenarios (central value scenario)", "",
        "Net benefit per quarter ($ thousands) = prevention rate × take rate × captured value − cost per contact × K. "
        "The prevention rate is the share of **otherwise-occurring** disappearances that contact prevents, and is unknown "
        "until tested. The take rate converts host booking value into platform revenue. Break-even is the cost per contact "
        "at which net benefit is zero.", "",
        md(nb[nb.variant == "retain"].drop(columns="variant")), "",
        "Sensitivity variant (`exclude`):", "", md(nb[nb.variant == "exclude"].drop(columns="variant")), "",
        "## Experiment sizing (host-randomized)", "",
        "Hosts needed per arm to detect a relative reduction in the share of contacted hosts with a disappearance "
        "(two-sided α = 0.05, power 0.8, normal approximation, ignoring clustering across quarters).", "",
        md(sizing), "",
    ]
    (PROJECT / "reports" / f"business_{title}.md").write_text("\n".join(lines))
    print(f"report -> reports/business_{title}.md")


if __name__ == "__main__":
    main(holdout="--holdout" in sys.argv)
