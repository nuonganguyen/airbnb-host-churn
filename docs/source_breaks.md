# Source Breaks

Suspected discontinuities in what the source captured, which the count-based snapshot rules in
`docs/label_spec.md` §2 cannot detect. Each one is recorded in the versioned policy
`config/quality_policy.json` and applied only through its variants (`src/quality.py`).

**Decision (2026-10-20):** the primary analysis **retains** all outcomes. Exclusion runs as a
prespecified sensitivity variant. Both variants are reported and frozen before the holdout.

## SB-1: Jan → Jun 2023, all 6 markets (suspected comparability break, cause unresolved)

The last monthly scrape (Dec 2022 / Jan 2023) is followed by the first quarterly scrape (Jun 2023), 145–183 days later.

### What was checked

| Check | Result | What it does and doesn't show |
|---|---|---|
| Jan 2023 cohort outcomes | 37–50% `absent_confirmed` in every market vs 13–22% in neighbouring cohorts | Unusual, but an unusual outcome distribution alone is not grounds to remove outcomes |
| Absence by availability (0 / 1–89 / 90+ nights) | 51% / 44% / 43% | A weak gradient doesn't show a collection problem: 2021-Q1 is also fairly flat (24% / 23% / 21%) |
| **1. Matched-duration turnover** (share of listings missing ~5–6 months later, 487 matched intervals) | 35–45% at the break, the 93rd–97th percentile | **Comparable** to the 2020 COVID intervals (Seattle 0.55, Denver 0.51) and New Orleans 2017 (0.47–0.49); not unprecedented on its own |
| **2. ID reconciliation** (raw vs extracted, Jan and Jun 2023, all markets) | Every raw id is present in the extract, and 18–19-digit ids above 2^53 survive intact. 166 rows (Feb 2022 – Jan 2023) have ids written in scientific notation (`6.2610005361e+17`), which lost precision. | The rounded ids can't be followed across snapshots; those rows are now excluded at load. They're far too few to explain the break. |
| **2b. Re-keying** (vanished listings reappearing under a new id with the same host, neighbourhood, room type, capacity, and ≥ the same review count) | **35–49%** at the break; all 473 earlier pairs ≤ 8.4% (p99 4.5%); all later pairs ≤ 13.2% | The strongest signal, and specific to this transition. Consistent with listings being re-created or re-identified under new ids, but it doesn't establish *why* (a platform change, host behaviour, or source processing) |
| **3. Source metadata and documentation** | A `source` column appears in every market's files from **Aug 2022**. Schemas are otherwise the same across the break. Inside Airbnb's data dictionary (v4.3, "Date Introduced August, 2022") defines it as "neighbourhood search" or "previous scrape", the latter meaning the listing "was seen in another scrape performed in the last 65 days" and confirmed still available. The files use "city scrape" instead of "neighbourhood search". The data-assumptions and get-the-data pages describe no 2022–2023 change to frequency, inclusion rules or identifiers. | A documented change in collection scope, but it **doesn't explain** the break: Jan 2023 `city scrape` listings are as absent (43–50%) as carry-overs. The 65-day carry-over window can't bridge a 145–183-day gap between published snapshots, but Jun 2023 files still contain carry-overs (presumably from unpublished scrapes), and the rule doesn't account for re-keying. |

Earlier statements removed from this document: "real churn always shows a gradient"; "few old reviews among
new ids rules out id changes" (the re-keying check contradicts it); "a coverage change, not hosts leaving".

### Dates

| Date | Value | Basis |
|---|---|---|
| Evidence available: re-keying | 2023-06-06 to 2023-06-30 by market | when each market's first post-break snapshot finished collecting |
| Evidence available: finalized outcomes | 2023-11-20 (New Orleans) to 2023-12-04 (San Diego, Seattle) | `label_final_at` of the Jan 2023 cohort. These labels enter training only from the **2024-01-01** deployment. |
| Detectable by a procedure | same as re-keying evidence | `src/quality.py:detect_rekeying`, flag when the share > 0.25 (3× the pre-2023 maximum). It uses only the two snapshots in each pair. **The threshold was set retrospectively.** |
| Identified by this investigation | 2026-10-20 | |

### Variants (`config/quality_policy.json`, version `QP-2026-10-20.1`)
- **`retain` (primary):** every outcome and feature value as built.
- **`exclude` (sensitivity), effective 2023-07-01**, the first deployment after every market was detectable:
  - **Training:** for deployments on/after that date, drop labels whose follow-up (*t*, C3] spans the gap.
  - **Scoring:** for decisions on/after that date, mask lag-365, lag-90 and 365-day presence features whose windows span the gap, and mark tenure that restarts at the post-break snapshot as censored.
  - **Evaluation:** drop comparisons whose follow-up spans the gap.
  - **No retroactivity:** decisions dated before 2023-07-01 are never flagged or changed (tested).

### Not yet done
- **ID crosswalk:** linking old to new ids for the matched pairs would treat re-keyed listings as continuing, instead of
  counting them as exits. It's a candidate third variant, but needs its own review: one-to-one matching rules, and
  false links for multi-unit hosts.
- **External documentation:** read on 2026-10-20: insideairbnb.com/data-assumptions, insideairbnb.com/get-the-data
  (partly; the page is long), and the data dictionary's v4.3 tab. The dictionary's other version tabs (v4.7, v4, v3) and
  Airbnb's own announcements were not read.

### Development results under each variant (2026-10-20, frozen before the holdout)

See `reports/backtest_development.md`. The variants differ in two folds:
- **2023-Q1:** dropped under `exclude`, because every evaluation comparison's follow-up spans the gap.
- **2023-Q3:** every evaluation row is masked under `exclude`, because its 365-day windows span the gap. LightGBM
  host precision@500 is 0.602 under `retain` and 0.480 under `exclude`.

**Limitation of the masking rule:** the model scoring 2023-Q3 was trained on rows decided before the effective date,
which are correctly left unchanged, so it never saw those features missing. The drop therefore mostly reflects
features missing only at scoring time, not a judgement on which variant handles the data better. Training with
missingness (e.g. random masking of history features) would be needed before reading the gap as evidence either way.
