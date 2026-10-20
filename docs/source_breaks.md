# Source Breaks

Discontinuities in how the source collected listings that the snapshot rules in `docs/label_spec.md` §2
cannot detect, because listing counts stay normal. Status: **finding documented; handling not yet approved.**

## SB-1: Jan → Jun 2023 coverage change (all 6 markets)

**What happens.** The last monthly scrape (Dec 2022 / Jan 2023) is followed by the first quarterly scrape
(Jun 2023), a gap of 145–182 days. Listing counts are flat (ratio 0.96–1.09), but:

| Evidence | Jan 2023 cohort | Typical |
|---|---|---|
| Listings at Jun 2023 never seen before | 35–45% per market | ~5% per month, ~10% per quarter |
| `absent_confirmed` among eligible listings at the Jan 2023 prediction dates | **37–50%** in every market | 13–22% (2022-Q1/Q2, 2023-Q2/Q3) |
| Absence by availability (0 / 1–89 / 90+ days) | 51% / 44% / 43%, nearly flat | 2021-Q1: 24% / 23% / 21%; Jun 2023: 32% / 21% / 14% |
| Absence among listings reviewed in the last 180 days | 38% | 15% (2021-Q1) |
| New Jun 2023 IDs with reviews older than a year (re-keyed listings) | ~1% | ~0% |

**Interpretation.** Absence that is nearly the same whatever the listing's activity, at flat counts, points
to a change in *which* listings the source captured, not to hosts leaving. Turnover per 30 days at Jun 2023
(0.07–0.09) is within the normal range (median 0.055, p90 0.085), so no snapshot-level rule flags it. The evidence
appears in the Jan 2023 cohort's outcomes, which become final around Oct 2023 (C3 ≈ Sep 2023).
A real platform event can't be ruled out, but it would have to remove listings regardless of activity.

**Impact.**
- **Development backtest fold 2023-Q1:** base rate 0.44; the presence rule reaches AP 0.86. The report shows a sensitivity view without it.
- **Holdout training data:** Jan 2023 labels are final from ~Oct 2023, so they would enter training for every holdout fold (2023-Q4 to 2024-Q3).
- **Features after the break:** `presence_rate_365`, `days_since_first_observed` and the lag-365 changes for 2023-Q2 to 2024-Q1 compare against pre-break snapshots, where ~40% of current listings "didn't exist".

## Proposed handling (for decision)

A **source-break registry**: a dated table of known breaks, each with a `known_from` date (when the evidence
became available, ~2023-10-01 for SB-1). It is applied like this:

1. **Labels:** a prediction date whose follow-up window (*t*, C3] crosses a registered break gets
   `insufficient_followup` with `followup_reason = 'source_break'`. This is excluded from training and
   evaluation like any other unusable follow-up.
2. **Features:** history features that compare across a break (presence over 365 days, lag-365 changes,
   first-observed tenure) are set to NULL, with a `history_crosses_break` flag. The fold pipeline's imputation and missing-value indicators then handle them.
3. **Information timing:** the registry entry only takes effect for decisions after `known_from`. Since the affected labels
   aren't final before then, excluding them uses no information a real deployment wouldn't have.

Alternatives: (a) keep the labels and report the break only as a sensitivity analysis. That's simpler, but the
holdout would train on labels that are probably artifacts. (b) Drop all prediction dates before Jun 2023 for
2023+ models. That loses most of the training data.
