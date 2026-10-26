"""Tables for a Power BI report, from saved backtest results (no refitting).

Writes CSVs (UTF-8 with BOM, so Power BI reads × and Σ correctly) and host_churn.xlsx (every
table on its own sheet, as an Excel table) to data_local/powerbi/, which is git-ignored. The
Power BI service makes one semantic model per uploaded CSV, so upload the workbook there to get
every table in one model. The default tables are quarterly aggregates: the same numbers the
reports already publish. --contact-list adds the top-500 hosts per quarter. That table holds
host ids, so keep it out of anything shared or published to the web.

    .venv/bin/python scripts/export_powerbi.py
    .venv/bin/python scripts/export_powerbi.py --contact-list   # needs features.parquet too

Every fact table except fact_feature_gain has both quality variants (retain = primary,
exclude = sensitivity): filter the report to one through dim_variant, or totals double. The
dim_ tables are the shared filters: relate each to the fact tables on the column of the same
name (quarter, variant, k). LightGBM probabilities
overpredict on the holdout (reports/post_holdout_audit.md), so use them to rank, not as
dollar forecasts.
"""
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

BT = PROJECT / "data_local" / "backtest"
OUT = PROJECT / "data_local" / "powerbi"
FREEZE = json.loads((PROJECT / "config" / "analysis_freeze.json").read_text())
SPLITS = {"dev": "development", "holdout": "holdout"}
MODELS = {"lgbm": "LightGBM", "lr": "Logistic regression",
          "rule:low_presence_365": "Rule: low presence over the past year",
          "rule:days_since_last_review": "Rule: days since last review",
          "rule:low_review_rate_90": "Rule: low recent review rate",
          "rule:calendar_blocked": "Rule: calendar fully blocked",
          "random": "Random contact (expected)"}
VARIANTS = {"retain": "Primary: every outcome as built",
            "exclude": "Sensitivity: 2023-Q1 source break removed"}


def read(kind):
    """Development and holdout versions of one backtest output, stacked, with a split column."""
    return pd.concat([pd.read_csv(BT / f"{name}_{kind}.csv").assign(split=label) for name, label in SPLITS.items()],
                     ignore_index=True)


def quarters(*frames):
    """Every quarter from the first evaluated to the last. Quarters with no usable follow-up
    stay in as 'not evaluated', so line charts break there instead of joining across them."""
    split = pd.concat(f[["quarter", "split"]] for f in frames).drop_duplicates().set_index("quarter").split
    q = pd.period_range(split.index.min(), split.index.max(), freq="Q")
    return pd.DataFrame({"quarter": q.astype(str), "quarter_start": q.start_time.date, "year": q.year,
                         "split": split.reindex(q.astype(str)).fillna("not evaluated").values})


def variants():
    return pd.DataFrame({"variant": list(VARIANTS), "variant_label": list(VARIANTS.values()),
                         "is_primary": [v == "retain" for v in VARIANTS]})


def contacts(*frames):
    """Contact budgets (K), shared by fact_precision and fact_business."""
    k = sorted(set().union(*(f.k for f in frames)))
    return pd.DataFrame({"k": k, "k_label": [f"{x:,} contacts" for x in k],
                         "is_main": [x == FREEZE["business"]["contacts_per_quarter"] for x in k]})


def precision(metrics, folds):
    """Host precision@K, one row per quarter x model x variant x K. Random contact is its
    expected value, the quarter's host base rate, at every K."""
    cols = [c for c in metrics if c.startswith("host_p@")]
    long = metrics.melt(["quarter", "model", "variant", "split"], cols, var_name="k", value_name="host_precision")
    rnd = pd.concat(folds[["quarter", "variant", "split", "host_base_rate"]].assign(k=c) for c in cols)
    long = pd.concat([long, rnd.rename(columns={"host_base_rate": "host_precision"}).assign(model="random")],
                     ignore_index=True)
    long["k"] = long.k.str.removeprefix("host_p@").astype(int)
    long["model_label"] = long.model.map(MODELS)
    long["is_best_rule"] = long.model == FREEZE["best_rule"]
    return long


def model_quality(metrics, folds):
    """Listing-level AP / AUC / Brier per quarter x model x variant, with the observed base
    rate beside mean_pred so the calibration gap is one subtraction. Rules have no Brier or
    mean_pred: their scores are not probabilities."""
    out = metrics.drop(columns=[c for c in metrics if c.startswith("host_p@")])
    out = out.merge(folds[["quarter", "variant", "base_rate"]], on=["quarter", "variant"], how="left")
    out["model_label"] = out.model.map(MODELS)
    return out


def feature_gain():
    """LightGBM gain share per feature and quarter (primary variant only, as saved)."""
    return pd.concat([pd.read_csv(BT / f"{name}_gains.csv", index_col=0).rename_axis("feature").reset_index()
                        .melt("feature", var_name="quarter", value_name="gain_share").assign(split=label)
                      for name, label in SPLITS.items()], ignore_index=True)


def contact_list():
    """Top hosts per quarter under the two host rankings in reports/business_*.md (primary
    variant, central value scenario), ranked exactly as src/business.py ranks them."""
    import business
    k = FREEZE["business"]["contacts_per_quarter"]
    frames = []
    for name, label in SPLITS.items():
        preds = business.load(name)
        lst = business.value_proxy(preds[preds.variant == "retain"], business.REVIEW_SHARES["central"])
        hosts = business.host_table(lst, "lgbm", FREEZE["best_rule"])
        for strategy in ("risk (max p)", "risk × value (Σ p·V)"):
            top = business.top_k(hosts, business.STRATEGIES[strategy], k)
            frames.append(top.assign(split=label, strategy=strategy, rank=top.groupby("quarter").cumcount() + 1))
    out = pd.concat(frames, ignore_index=True)
    out["portfolio_size"] = business.portfolio_bucket(out.n_listings).astype(str)
    return out[["quarter", "split", "strategy", "rank", "host_id_at_t", "n_listings", "portfolio_size",
                "contact_date", "risk_max", "exposure", "value_total", "rule", "hit", "lost_value"]]


def write_workbook(tables, path):
    """One sheet per table, each formatted as an Excel table named after it."""
    with pd.ExcelWriter(path, engine="xlsxwriter", date_format="yyyy-mm-dd", datetime_format="yyyy-mm-dd") as xl:
        for name, df in tables.items():
            df.to_excel(xl, sheet_name=name, index=False, startrow=1, header=False)
            xl.sheets[name].add_table(0, 0, len(df), len(df.columns) - 1,
                                      {"name": name, "columns": [{"header": c} for c in df.columns]})


def main(with_contacts=False):
    OUT.mkdir(parents=True, exist_ok=True)
    metrics, folds, biz = read("metrics"), read("folds"), read("business")
    prec = precision(metrics, folds)
    tables = {"dim_quarter": quarters(metrics, biz),
              "dim_variant": variants(),
              "dim_k": contacts(prec, biz),
              "fact_precision": prec,
              "fact_model_quality": model_quality(metrics, folds),
              "fact_business": biz,
              "fact_folds": folds,
              "fact_feature_gain": feature_gain()}
    if with_contacts:
        tables["contact_list"] = contact_list()
    for name, df in tables.items():
        path = OUT / f"{name}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"{path.relative_to(PROJECT)}  {len(df):,} rows")
    write_workbook(tables, OUT / "host_churn.xlsx")
    print((OUT / "host_churn.xlsx").relative_to(PROJECT))


if __name__ == "__main__":
    main(with_contacts="--contact-list" in sys.argv)
