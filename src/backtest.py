"""Rolling-origin backtest (docs/label_spec.md §7).

One fold per deployment quarter Q: train on features.training_frame(Q), validate on
the latest 2 training quarters (early stopping + Platt calibration), then score the
eligible prediction-date rows in Q. Preprocessing is fitted inside each fold. Every run
covers both quality-policy variants (config/quality_policy.json): `retain` (primary)
and `exclude` (prespecified sensitivity).

    python src/backtest.py             # development folds, before the holdout block
    python src/backtest.py --holdout   # the shared holdout block, once, at the very end
    python src/backtest.py --report-only   # rebuild the report from saved fold results
"""
import sys
import time
from datetime import date

import duckdb
import numpy as np
import pandas as pd

import features
from db import CITIES, LOCAL, PROJECT
from label import md
from model import RULES, Prep, fit_lightgbm, fit_logistic, host_precision_at_k, listing_metrics
from quality import apply_policy, load_policy

HOLDOUT = (date(2023, 10, 1), date(2024, 10, 1))     # docs/label_spec.md §7
FIRST_DEPLOYMENT = date(2017, 1, 1)
MIN_TRAIN_ROWS = 50_000
VAL_QUARTERS = 2
OUT = LOCAL / "backtest"
MODELS = ["lr", "lgbm"]
VARIANTS = ["retain", "exclude"]
BLOCK = 4          # quarters per bootstrap block: longer than the ~3-quarter outcome overlap
HAC_LAGS = 3


def connect():
    con = duckdb.connect()
    con.execute(f"CREATE TABLE features AS SELECT * FROM '{LOCAL / 'features.parquet'}'")
    con.execute(f"CREATE TABLE labels AS SELECT * FROM '{LOCAL / 'labels' / 'labels.parquet'}'")
    return con


def quarter_starts(start, end):
    q = pd.Period(start, freq="Q")
    while q.start_time.date() < end:
        yield q.start_time.date(), (q + 1).start_time.date()
        q += 1


def evaluation_frame(con, start, end):
    """Eligible rows at prediction dates in [start, end) whose outcome is known."""
    return con.execute("""
        SELECT f.*, l.outcome = 'absent_confirmed' AS target, l.c2, l.c3
        FROM features f
        JOIN labels l ON l.city_id = f.city_id AND l.list_id = f.list_id AND l.t = f.t
        WHERE l.eligible_main AND l.label_status = 'final'
          AND l.outcome IN ('absent_confirmed', 'observed')
          AND f.t >= ? AND f.t < ?
    """, [start, end]).df()


def split_validation(train):
    quarter = pd.PeriodIndex(pd.to_datetime(train["t"]), freq="Q")
    val_q = sorted(quarter.unique())[-VAL_QUARTERS:]
    is_val = quarter.isin(val_q)
    return train[~is_val], train[is_val]


def run_fold(con, start, end, policy, variant):
    train = features.training_frame(con, start)
    train = apply_policy(apply_policy(train, policy, variant, "train", start), policy, variant, "score")
    ev = evaluation_frame(con, start, end)
    ev = apply_policy(apply_policy(ev, policy, variant, "evaluate"), policy, variant, "score")
    if len(train) < MIN_TRAIN_ROWS or ev.empty:
        return None
    assert (pd.to_datetime(train["label_final_at"]) < pd.Timestamp(start)).all()
    assert (pd.to_datetime(ev["t"]) >= pd.Timestamp(start)).all()
    fit_df, val_df = split_validation(train)
    prep = Prep().fit(fit_df)
    lr = fit_logistic(prep, fit_df, val_df)
    lgbm, booster = fit_lightgbm(prep, fit_df, val_df)

    scores = {"lr": lr(ev), "lgbm": lgbm(ev)}
    scores.update({f"rule:{name}": rule(ev).to_numpy() for name, rule in RULES.items()})
    preds = ev[["city_id", "list_id", "t", "host_id_at_t", "target"]].copy()
    rows = []
    for name, s in scores.items():
        preds[name] = s
        m = listing_metrics(ev["target"], s, calibrated=name in MODELS)
        hp, n_hosts, host_base = host_precision_at_k(preds, name)
        rows.append({"quarter": f"{pd.Period(start, freq='Q')}", "model": name, **m, **hp})
    meta = {"quarter": f"{pd.Period(start, freq='Q')}", "n_train": len(fit_df), "n_val": len(val_df),
            "n_masked_eval": int(ev["history_crosses_break"].sum()),
            "n_eval": len(ev), "base_rate": float(ev["target"].mean()), "n_hosts": n_hosts,
            "host_base_rate": host_base, "lgbm_trees": booster.best_iteration_}
    gain = pd.Series(booster.booster_.feature_importance("gain"), index=booster.booster_.feature_name())
    return preds, rows, meta, gain / gain.sum()


def block_bootstrap_ci(x, block=BLOCK, n=4000, seed=0):
    """Moving-block bootstrap over consecutive folds, for serially dependent fold metrics."""
    x = np.asarray(x, dtype=float)
    k = len(x)
    block = min(block, k)
    starts = np.arange(k - block + 1)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(k / block))
    means = np.array([np.concatenate([x[s:s + block] for s in rng.choice(starts, n_blocks)])[:k].mean()
                      for _ in range(n)])
    return float(x.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def newey_west_ci(x, lags=HAC_LAGS):
    """Mean with a HAC (Bartlett-kernel) standard error; normal 95% interval."""
    x = np.asarray(x, dtype=float)
    e = x - x.mean()
    k = len(x)
    var = e @ e / k + 2 * sum((1 - j / (lags + 1)) * (e[j:] @ e[:-j]) / k for j in range(1, min(lags, k - 1) + 1))
    se = np.sqrt(max(var, 0) / k)
    return float(x.mean()), float(x.mean() - 1.96 * se), float(x.mean() + 1.96 * se)


def best_rule_from(metrics):
    rules = metrics[metrics.model.str.startswith("rule:") & (metrics.variant == "retain")]
    return rules.groupby("model").ap.mean().idxmax()


def report(metrics, meta, gains, holdout, policy):
    # the rule baseline is always chosen on the primary (retain) development folds
    best_rule = best_rule_from(pd.read_csv(OUT / "dev_metrics.csv") if holdout else metrics)
    shown = MODELS + [best_rule]
    cols = ["ap", "auc", "host_p@100", "host_p@500", "host_p@1000"]
    summary = (metrics[metrics.model.isin(shown)].groupby(["variant", "model"])[cols].mean().round(3)
               .reset_index().sort_values(["variant", "ap"], ascending=[False, False]))
    lifts = []
    for v in VARIANTS:
        wide = metrics[(metrics.variant == v) & metrics.model.isin(shown)].pivot(index="quarter", columns="model")
        for m in MODELS:
            for col in ["ap", "host_p@500"]:
                d = (wide[col][m] - wide[col][best_rule]).sort_index()
                row = {"variant": v, "comparison": f"{m} − {best_rule}", "metric": col,
                       "mean_diff": round(float(d.mean()), 3), "folds_better": f"{(d > 0).sum()}/{len(d)}"}
                if holdout:              # four quarters: report each one, no intervals
                    row.update({q: round(float(x), 3) for q, x in d.items()})
                else:
                    _, blo, bhi = block_bootstrap_ci(d)
                    _, hlo, hhi = newey_west_ci(d)
                    row.update({f"block bootstrap (b={BLOCK})": f"[{blo:.3f}, {bhi:.3f}]",
                                f"Newey–West (lag {HAC_LAGS})": f"[{hlo:.3f}, {hhi:.3f}]"})
                lifts.append(row)
    prim = metrics[metrics.variant == "retain"]
    pm = meta[meta.variant == "retain"]
    era = lambda q: "2017–19" if q < "2020" else ("2020–21" if q < "2022" else "2022–23")
    by_era = (metrics[metrics.model.isin(shown)].assign(era=lambda d: d.quarter.map(era))
              .groupby(["variant", "era", "model"]).ap.mean().unstack().round(3).reset_index())
    calib = prim[prim.model.isin(MODELS)].merge(pm[["quarter", "base_rate"]], on="quarter")
    calib = (calib.assign(gap=lambda d: d.mean_pred - d.base_rate).groupby("model")
             .agg(brier=("brier", "mean"), mean_abs_gap=("gap", lambda g: g.abs().mean()),
                  worst_gap=("gap", lambda g: g.loc[g.abs().idxmax()])).round(4).reset_index())
    wide = prim[prim.model.isin(shown)].pivot(index="quarter", columns="model")
    per_fold = pm.drop(columns="variant").set_index("quarter").join(pd.DataFrame({
        **{f"AP {m}": wide["ap"][m] for m in shown},
        **{f"host P@500 {m}": wide["host_p@500"][m] for m in shown}})).reset_index()
    diff = (metrics[metrics.model == "lgbm"].pivot(index="quarter", columns="variant", values="host_p@500")
            .assign(difference=lambda d: d["exclude"] - d["retain"]).round(3).reset_index())
    diff = diff[diff.difference.abs() > 0]
    top = gains.mean(axis=1).sort_values(ascending=False).head(20).round(4).rename("mean_gain_share").reset_index()
    top.columns = ["feature", "mean_gain_share"]

    name = "holdout" if holdout else "development"
    lines = [
        f"# Backtest Summary: {name}", "",
        f"Built {date.today():%Y-%m-%d} by `src/backtest.py` under quality policy `{policy['policy_version']}`. "
        f"{pm.quarter.nunique()} quarterly folds, {pm.quarter.iloc[0]}–{pm.quarter.iloc[-1]}. "
        + ("The shared holdout block (2023-Q4–2024-Q3) was **not** used." if not holdout else
           "Shared holdout block; the rule baseline was fixed from the development folds."), "",
        "Each fold trains on final, usable, eligible labels with `label_final_at` before the quarter starts, "
        "early-stops and calibrates on the latest 2 training quarters, and evaluates on eligible rows at that "
        "quarter's prediction dates. Host precision@K ranks unique hosts (host at *t*) by their riskiest "
        "listing; a hit is a host with ≥ 1 listing `absent_confirmed`. Scores are predictive associations, "
        "not causes.", "",
        "**Variants** (`config/quality_policy.json`): `retain` is the primary analysis and keeps every outcome. "
        "`exclude` is the prespecified sensitivity analysis: it drops comparisons whose follow-up crosses a suspected "
        "source break and masks history features that cross it, only for decisions on/after the policy's effective "
        f"date ({policy['variants']['exclude']['effective_date']}). Both are reported regardless of which scores higher.", "",
        f"Best simple rule (highest mean AP, primary development folds): `{best_rule}`.", "",
        "## Mean over folds", "", md(summary), "",
        "## Lift over the best rule", "",
        ("Four holdout quarters: each quarter's difference is shown, and no intervals are computed." if holdout else
         "Fold metrics are serially dependent (outcomes follow up for ~9 months, so neighbouring folds overlap). "
         f"Intervals use a moving-block bootstrap over consecutive folds (blocks of {BLOCK} quarters) and a "
         f"Newey–West HAC standard error (lag {HAC_LAGS}). Both are approximate with this few folds."), "",
        md(pd.DataFrame(lifts)), "",
        "## Folds where the variants differ (LightGBM host P@500)", "",
        md(diff) if len(diff) else "None.", "",
        "## Average precision by era", "", md(by_era), "",
        "## Calibration, primary variant (Platt on the validation quarters)", "",
        "`gap` = mean predicted probability − observed rate in the evaluation quarter.", "", md(calib), "",
        "## Per fold, primary variant", "", md(per_fold.round(3)), "",
        "## LightGBM: top 20 features by gain share (primary, mean over folds)", "", md(top), "",
    ]
    (PROJECT / "reports" / f"backtest_{name}.md").write_text("\n".join(lines))


def main(holdout=False):
    OUT.mkdir(parents=True, exist_ok=True)
    con = connect()
    policy = load_policy()
    if holdout:
        if not (OUT / "dev_metrics.csv").exists():
            sys.exit("run the development backtest first; the holdout is evaluated once, at the end")
        import freeze
        freeze.verify()                  # refuses to run if any frozen file changed
        if (OUT / "holdout_metrics.csv").exists():
            sys.exit("the holdout has already been run; it is evaluated once")
        span = HOLDOUT
    else:
        span = (FIRST_DEPLOYMENT, HOLDOUT[0])
    all_preds, all_rows, metas, gains = [], [], [], {}
    t0 = time.time()
    for start, end in quarter_starts(*span):
        if not holdout and end > HOLDOUT[0]:
            break
        for variant in VARIANTS:
            out = run_fold(con, start, end, policy, variant)
            if out is None:
                print(f"{pd.Period(start, freq='Q')} {variant}: skipped (too little training data or no outcomes)",
                      flush=True)
                continue
            preds, rows, meta, gain = out
            q = meta["quarter"]
            all_preds.append(preds.assign(quarter=q, variant=variant))
            all_rows += [{**r, "variant": variant} for r in rows]
            metas.append({**meta, "variant": variant})
            if variant == "retain":
                gains[q] = gain
            lg = next(r for r in rows if r["model"] == "lgbm")
            print(f"{q} {variant}: train {meta['n_train']:,} eval {meta['n_eval']:,} masked {meta['n_masked_eval']:,} "
                  f"base {meta['base_rate']:.3f} lgbm AP {lg['ap']:.3f} P@500 {lg['host_p@500']:.3f}  "
                  f"[{time.time() - t0:.0f}s]", flush=True)
    name = "holdout" if holdout else "dev"
    metrics, meta = pd.DataFrame(all_rows), pd.DataFrame(metas)
    pd.concat(all_preds).to_parquet(OUT / f"{name}_predictions.parquet", index=False)
    metrics.to_csv(OUT / f"{name}_metrics.csv", index=False)
    meta.to_csv(OUT / f"{name}_folds.csv", index=False)
    pd.DataFrame(gains).fillna(0.0).to_csv(OUT / f"{name}_gains.csv")
    report(metrics, meta, pd.DataFrame(gains).fillna(0.0), holdout, policy)
    print(f"report -> reports/backtest_{'holdout' if holdout else 'development'}.md")


def report_only(holdout=False):
    """Rebuild the report from saved fold results, without refitting."""
    name = "holdout" if holdout else "dev"
    report(pd.read_csv(OUT / f"{name}_metrics.csv"), pd.read_csv(OUT / f"{name}_folds.csv"),
           pd.read_csv(OUT / f"{name}_gains.csv", index_col=0), holdout, load_policy())


if __name__ == "__main__":
    if "--report-only" in sys.argv:
        report_only(holdout="--holdout" in sys.argv)
    else:
        main(holdout="--holdout" in sys.argv)
