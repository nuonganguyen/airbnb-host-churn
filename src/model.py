"""Per-fold preprocessing, models, calibration and metrics for the backtest.

Everything here is fitted on one fold's training rows only (docs/feature_spec.md §4).
"""
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from features import ALLOWLIST, model_matrix

NUMERIC = [c for c, k in ALLOWLIST.items() if k in ("numeric", "binary")]
CATEGORICAL = [c for c, k in ALLOWLIST.items() if k == "categorical"]
PRICE_LIKE = ["price", "price_rel_room_median", "price_rel_neighbourhood_median", "price_change_90", "price_change_365"]
MIN_CATEGORY_SHARE = 0.001
SEED = 7


class Prep:
    """Learns caps, medians, missing indicators, category levels and scaling from
    the rows passed to fit(); applies them unchanged to any later rows."""

    def fit(self, df):
        X = model_matrix(df)
        num = X[NUMERIC].astype("float64")
        self.lower = num.quantile(0.01)
        self.upper = num.quantile(0.99)                  # includes the price p99 cap
        capped = num.clip(self.lower, self.upper, axis=1)
        self.median = capped.median().fillna(0.0)
        self.indicators = [c for c in NUMERIC if num[c].isna().any()]
        self.levels = {}
        for c in CATEGORICAL:
            share = X[c].astype(str).value_counts(normalize=True)
            self.levels[c] = sorted(share[share >= MIN_CATEGORY_SHARE].index)
        lr = self._linear(X)
        self.mean = lr.mean()
        self.std = lr.std().replace(0, 1.0).fillna(1.0)
        self.linear_columns = list(lr.columns)
        return self

    def _categories(self, X, c):
        v = X[c].astype(str)
        return v.where(v.isin(self.levels[c]), "other")

    def _linear(self, X):
        num = X[NUMERIC].astype("float64").clip(self.lower, self.upper, axis=1)
        parts = [num.fillna(self.median)]
        parts.append(num[self.indicators].isna().astype("float64").add_suffix("__missing"))
        for c in CATEGORICAL:
            parts.append(pd.get_dummies(self._categories(X, c), prefix=c, dtype="float64"))
        return pd.concat(parts, axis=1)

    def linear(self, df):
        """Imputed, capped, one-hot, standardized matrix for logistic regression."""
        lr = self._linear(model_matrix(df)).reindex(columns=self.linear_columns, fill_value=0.0)
        return ((lr - self.mean) / self.std).to_numpy("float32")

    def tree(self, df):
        """Raw numerics (NaN kept, price-like values capped) plus fold-level categories."""
        X = model_matrix(df)
        out = X[NUMERIC].astype("float32").copy()
        out[PRICE_LIKE] = out[PRICE_LIKE].clip(self.lower[PRICE_LIKE], self.upper[PRICE_LIKE], axis=1)
        for c in CATEGORICAL:
            out[c] = pd.Categorical(self._categories(X, c), categories=self.levels[c] + ["other"])
        return out


def platt(raw_val, y_val):
    """Sigmoid calibration on log-odds, fitted on the validation period."""
    z = np.log(np.clip(raw_val, 1e-6, 1 - 1e-6) / (1 - np.clip(raw_val, 1e-6, 1 - 1e-6)))
    cal = LogisticRegression(C=1e6).fit(z.reshape(-1, 1), y_val)
    def apply(raw):
        r = np.clip(raw, 1e-6, 1 - 1e-6)
        return cal.predict_proba(np.log(r / (1 - r)).reshape(-1, 1))[:, 1]
    return apply


def fit_logistic(prep, fit_df, val_df, max_rows=300_000):
    if len(fit_df) > max_rows:
        fit_df = fit_df.sample(max_rows, random_state=SEED)
    model = LogisticRegression(C=1.0, max_iter=300).fit(prep.linear(fit_df), fit_df["target"])
    calibrate = platt(model.predict_proba(prep.linear(val_df))[:, 1], val_df["target"])
    return lambda df: calibrate(model.predict_proba(prep.linear(df))[:, 1])


LGB_PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=63, min_child_samples=200,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
                  n_estimators=2000, random_state=SEED, verbose=-1)


def fit_lightgbm(prep, fit_df, val_df):
    model = lgb.LGBMClassifier(**LGB_PARAMS)
    model.fit(prep.tree(fit_df), fit_df["target"], eval_set=[(prep.tree(val_df), val_df["target"])],
              callbacks=[lgb.early_stopping(100, verbose=False)])
    calibrate = platt(model.predict_proba(prep.tree(val_df))[:, 1], val_df["target"])
    predict = lambda df: calibrate(model.predict_proba(prep.tree(df))[:, 1])
    return predict, model


# Simple rules: a higher score means more likely to be absent_confirmed. Never-reviewed
# listings count as stale for the review rules.
RULES = {
    "days_since_last_review": lambda df: df["days_since_last_review"].fillna(df["days_since_first_observed"]),
    "low_presence_365": lambda df: 1 - df["presence_rate_365"].fillna(1.0),
    "low_review_rate_90": lambda df: -df["review_rate_90"].fillna(0.0),
    "calendar_blocked": lambda df: (df["available_365"] == 0).astype(float) * 1e6
                                   + df["days_since_last_review"].fillna(df["days_since_first_observed"]),
}


def listing_metrics(y, score, calibrated=False):
    out = {"ap": average_precision_score(y, score), "auc": roc_auc_score(y, score)}
    if calibrated:
        out.update(brier=brier_score_loss(y, score), mean_pred=float(np.mean(score)))
    return out


def host_precision_at_k(df, score_col, ks=(100, 500, 1000)):
    """Hosts ranked by their riskiest eligible listing; a host is a hit when at least
    one of its eligible listings is absent_confirmed. Ties broken by host id."""
    hosts = (df.groupby("host_id_at_t")
               .agg(score=(score_col, "max"), hit=("target", "max"))
               .reset_index()
               .sort_values(["score", "host_id_at_t"], ascending=[False, True]))
    return {f"host_p@{k}": float(hosts["hit"].head(k).mean()) for k in ks}, len(hosts), float(hosts["hit"].mean())
