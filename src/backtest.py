"""Rolling-origin backtest (docs/label_spec.md §7).

One fold per deployment quarter Q: train on features.training_frame(Q), validate on
the latest 2 training quarters (early stopping + Platt calibration), then score the
eligible prediction-date rows in Q. Preprocessing is fitted inside each fold.

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

HOLDOUT = (date(2023, 10, 1), date(2024, 10, 1))     # docs/label_spec.md §7
FIRST_DEPLOYMENT = date(2017, 1, 1)
MIN_TRAIN_ROWS = 50_000
VAL_QUARTERS = 2
OUT = LOCAL / "backtest"
MODELS = ["lr", "lgbm"]
# folds whose labels cross a known source discontinuity (reported, and excluded in the
# sensitivity view): ~40% of listings swap between the Jan 2023 and Jun 2023 scrapes
# at flat counts, and Jan 2023 absence is ~43% regardless of listing characteristics
SUSPECT_FOLDS = {"2023Q1": "Jan→Jun 2023 source coverage break"}


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
        SELECT f.*, l.outcome = 'absent_confirmed' AS target
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


def run_fold(con, start, end):
    train = features.training_frame(con, start)
    ev = evaluation_frame(con, start, end)
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
            "n_eval": len(ev), "base_rate": float(ev["target"].mean()), "n_hosts": n_hosts,
            "host_base_rate": host_base, "lgbm_trees": booster.best_iteration_}
    gain = pd.Series(booster.booster_.feature_importance("gain"), index=booster.booster_.feature_name())
    return preds, rows, meta, gain / gain.sum()


def bootstrap_mean_ci(x, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    x = np.asarray(x)
    means = rng.choice(x, size=(n, len(x)), replace=True).mean(axis=1)
    return float(x.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def report(metrics, meta, gains, holdout):
    rule_names = [m for m in metrics.model.unique() if m.startswith("rule:")]
    if holdout:
        best_rule = (pd.read_csv(OUT / "dev_metrics.csv").query("model.str.startswith('rule:')", engine="python")
                     .groupby("model").ap.mean().idxmax())
    else:
        best_rule = metrics[metrics.model.isin(rule_names)].groupby("model").ap.mean().idxmax()
    shown = MODELS + [best_rule]
    wide = metrics[metrics.model.isin(shown)].pivot(index="quarter", columns="model")
    per_fold = meta.set_index("quarter").join(pd.DataFrame({
        **{f"AP {m}": wide["ap"][m] for m in shown},
        **{f"host P@500 {m}": wide["host_p@500"][m] for m in shown},
    })).reset_index()

    summary = (metrics[metrics.model.isin(shown + rule_names)].groupby("model")
               [["ap", "auc", "host_p@100", "host_p@500", "host_p@1000"]].mean().round(3)
               .sort_values("ap", ascending=False).reset_index())
    lifts = []
    for m in MODELS:
        for col in ["ap", "host_p@500"]:
            d = wide[col][m] - wide[col][best_rule]
            mean, lo, hi = bootstrap_mean_ci(d)
            lifts.append({"comparison": f"{m} − {best_rule}", "metric": col, "mean_diff": round(mean, 3),
                          "95% CI (folds)": f"[{lo:.3f}, {hi:.3f}]", "folds_better": f"{(d > 0).sum()}/{len(d)}"})
    clean = metrics[~metrics.quarter.isin(SUSPECT_FOLDS)]
    sensitivity = (clean[clean.model.isin(shown)].groupby("model")
                   [["ap", "auc", "host_p@100", "host_p@500", "host_p@1000"]].mean().round(3)
                   .sort_values("ap", ascending=False).reset_index())
    clean_wide = wide[~wide.index.isin(SUSPECT_FOLDS)]
    for m in MODELS:
        d = clean_wide["host_p@500"][m] - clean_wide["host_p@500"][best_rule]
        mean, lo, hi = bootstrap_mean_ci(d)
        lifts.append({"comparison": f"{m} − {best_rule} (excl. suspect folds)", "metric": "host_p@500",
                      "mean_diff": round(mean, 3), "95% CI (folds)": f"[{lo:.3f}, {hi:.3f}]",
                      "folds_better": f"{(d > 0).sum()}/{len(d)}"})
    era = lambda q: "2017–19" if q < "2020" else ("2020–21" if q < "2022" else "2022–23")
    by_era = (metrics[metrics.model.isin(shown)].assign(era=lambda d: d.quarter.map(era))
              .groupby(["era", "model"]).ap.mean().unstack().round(3).reset_index())
    calib = metrics[metrics.model.isin(MODELS)].merge(meta[["quarter", "base_rate"]], on="quarter")
    calib = (calib.assign(gap=lambda d: d.mean_pred - d.base_rate).groupby("model")
             .agg(brier=("brier", "mean"), mean_abs_gap=("gap", lambda g: g.abs().mean()),
                  worst_gap=("gap", lambda g: g.loc[g.abs().idxmax()])).round(4).reset_index())
    top = gains.mean(axis=1).sort_values(ascending=False).head(20).round(4).rename("mean_gain_share").reset_index()
    top.columns = ["feature", "mean_gain_share"]

    name = "holdout" if holdout else "development"
    lines = [
        f"# Backtest Summary: {name}", "",
        f"Built {date.today():%Y-%m-%d} by `src/backtest.py`. {len(meta)} quarterly folds, "
        f"{meta.quarter.iloc[0]}–{meta.quarter.iloc[-1]}. "
        + ("The shared holdout block (2023-Q4–2024-Q3) was **not** used." if not holdout else
           "Shared holdout block; the rule baseline was fixed from the development folds."), "",
        "Each fold trains on final, usable, eligible labels with `label_final_at` before the quarter starts, "
        "early-stops and calibrates on the latest 2 training quarters, and evaluates on eligible rows at that "
        "quarter's prediction dates. Host precision@K ranks unique hosts (host at *t*) by their riskiest "
        "listing; a hit is a host with ≥ 1 listing `absent_confirmed`. Scores are predictive associations, "
        "not causes.", "",
        f"Best simple rule (highest mean AP on the development folds): `{best_rule}`.", "",
        "## Mean over folds", "", md(summary), "",
        "## Sensitivity: excluding suspect folds", "",
        "; ".join(f"`{q}`: {why}" for q, why in SUSPECT_FOLDS.items()) + ".", "", md(sensitivity), "",
        "## Lift over the best rule", "",
        "CI from a bootstrap over folds. Outcomes overlap across folds (~9-month follow-up), so treat "
        "the intervals as approximate.", "", md(pd.DataFrame(lifts)), "",
        "## Average precision by era", "", md(by_era), "",
        "## Calibration (Platt on the validation quarters)", "",
        "`gap` = mean predicted probability − observed rate in the evaluation quarter.", "", md(calib), "",
        "## Per fold", "", md(per_fold.round(3)), "",
        "## LightGBM: top 20 features by gain share (mean over folds)", "", md(top), "",
    ]
    (PROJECT / "reports" / f"backtest_{name}.md").write_text("\n".join(lines))


def main(holdout=False):
    OUT.mkdir(parents=True, exist_ok=True)
    con = connect()
    if holdout:
        if not (OUT / "dev_metrics.csv").exists():
            sys.exit("run the development backtest first; the holdout is evaluated once, at the end")
        span = HOLDOUT
    else:
        span = (FIRST_DEPLOYMENT, HOLDOUT[0])
    all_preds, all_rows, metas, gains = [], [], [], {}
    t0 = time.time()
    for start, end in quarter_starts(*span):
        if not holdout and end > HOLDOUT[0]:
            break
        out = run_fold(con, start, end)
        if out is None:
            print(f"{pd.Period(start, freq='Q')}: skipped (too little training data or no outcomes)", flush=True)
            continue
        preds, rows, meta, gain = out
        all_preds.append(preds.assign(quarter=meta["quarter"]))
        all_rows += rows
        metas.append(meta)
        gains[meta["quarter"]] = gain
        lg = next(r for r in rows if r["model"] == "lgbm")
        print(f"{meta['quarter']}: train {meta['n_train']:,} eval {meta['n_eval']:,} base {meta['base_rate']:.3f} "
              f"lgbm AP {lg['ap']:.3f} P@500 {lg['host_p@500']:.3f}  [{time.time() - t0:.0f}s]", flush=True)
    name = "holdout" if holdout else "dev"
    metrics, meta = pd.DataFrame(all_rows), pd.DataFrame(metas)
    pd.concat(all_preds).to_parquet(OUT / f"{name}_predictions.parquet", index=False)
    metrics.to_csv(OUT / f"{name}_metrics.csv", index=False)
    meta.to_csv(OUT / f"{name}_folds.csv", index=False)
    pd.DataFrame(gains).fillna(0.0).to_csv(OUT / f"{name}_gains.csv")
    report(metrics, meta, pd.DataFrame(gains).fillna(0.0), holdout)
    print(f"report -> reports/backtest_{'holdout' if holdout else 'development'}.md")


def report_only(holdout=False):
    """Rebuild the report from saved fold results, without refitting."""
    name = "holdout" if holdout else "dev"
    report(pd.read_csv(OUT / f"{name}_metrics.csv"), pd.read_csv(OUT / f"{name}_folds.csv"),
           pd.read_csv(OUT / f"{name}_gains.csv", index_col=0), holdout)


if __name__ == "__main__":
    if "--report-only" in sys.argv:
        report_only(holdout="--holdout" in sys.argv)
    else:
        main(holdout="--holdout" in sys.argv)
