# Label Specification: Listing Absence at Follow-up Checkpoints

Status: **v3, 2026-10-20**: v2 (approved) plus fixes for label finality and anomaly resolution. Implemented in `sql/03_label.sql`; acceptance gate is
`tests/test_label.py`, not the resulting rates.
Data: `data_local/listings_6city_clean.parquet` (6 markets, 563 snapshots, 2015–2026).

## 1. Outcome

> **Absent at the approximately 180-day checkpoint, confirmed absent at the approximately 270-day checkpoint**
> (`absent_confirmed`).

A proxy for "the host stopped offering this listing on Airbnb". It does **not** establish uninterrupted
absence between checkpoints, permanent departure, the reason for leaving, or a move to another platform.
With ±45-day tolerance, "180 days" means somewhere between 135 and 225 days.

Status, applied in this order to every listing:

```text
if C2 or C3 is unavailable:        insufficient_followup   (whatever the listing's presence)
elif absent at C2 and absent at C3: absent_confirmed
else:                               observed
```

Checking for missing follow-up first stops recent cohorts from admitting known negatives while excluding
the potential positives that haven't resolved yet.

## 2. Observation schedule

One row per city and snapshot. Two versions are kept apart:

| | Uses | Purpose |
|---|---|---|
| **Operational** (used for labels) | only snapshots up to the date the status becomes known | backtests reproducible at historical decision dates |
| **Retrospective audit** | snapshots on both sides | quality reporting only; never used for labels |

### Operational usability rule
1. **History:** a snapshot needs ≥ 3 earlier snapshots in its city. A city's first 3 snapshots are `insufficient_history`:
   never prediction dates or checkpoints.
2. **Anomaly flag:** listing count < 75% of the median of the **3 preceding** snapshots. This is a flag, not proof
   that the scrape was incomplete.
3. **Resolution, using only reliable snapshots:**
   - **Reference:** the latest *unflagged* snapshot before the flagged one.
   - **Resolver:** the earliest later snapshot that is itself unflagged (with history), within **200 days**.
     A damaged snapshot never resolves another one.
   - **Return rate:** of the listings in the reference but missing from the flagged snapshot, the share present at the resolver.
     - ≥ 50% → `partial_scrape`: unusable.
     - < 50% → `suspected_contraction`: usable. This is a classification under the rule, not proof the market really shrank.
     - No resolver yet, with < 200 days elapsed → `anomaly_pending`: unusable for now, so anything it could affect stays provisional.
     - No resolver within 200 days → `anomaly_unresolved`: permanently unusable.
4. **Status known at:** the snapshot date for `ok` and `insufficient_history`; the resolver date for `partial_scrape`
   and `suspected_contraction`, which is also recorded for rejected snapshots; snapshot + 200 days for `anomaly_unresolved`;
   unknown for `anomaly_pending`.

Edges: the trailing window uses the up to 3 preceding snapshots, including flagged ones. A real contraction keeps
later snapshots flagged until the trailing median catches up (2 more snapshots), so a contraction is resolved by
the first snapshot after that. **Limitation:** the rule tolerates at most 2 damaged snapshots in a row; a 3rd would fall below a
trailing median that has already dropped, and so not be flagged. Also, when several flags come in a row, the reference
can be far back. Its missing set then includes listings that left earlier, which can dilute a partial scrape's return
rate. Austin 2026-03 is a likely case: 26% return against a Jun 2025 reference, versus 63% against Dec 2025.

On current data: 16 flagged snapshots. 5 are `partial_scrape` (64–86% return): San Diego 2017-07, Nashville 2025-12,
and Mar 2026 in Denver, Nashville and Seattle. 10 are `suspected_contraction` (1–26%): Oct–Nov 2020 in Denver, San Diego and
Seattle; New Orleans Jul–Aug 2017; Austin 2022-11, 2025-12 and 2026-03. 1 is `anomaly_unresolved`: Austin 2025-09.
Details: `reports/label_summary.md`. Not handled, but audited: snapshots with normal counts but high return rates,
i.e. unusual turnover in which listings appear (e.g. Nashville 2017-06, New Orleans 2022-03).

### Prediction dates
The earliest `ok` snapshot in each city and calendar quarter. Flagged snapshots are never prediction dates, because
their status is unknown at decision time.

### Checkpoint selection (deterministic)
- Selected once per **city and prediction date**, and shared by every listing.
- Targets: C1 = *t*+90 (diagnostic), C2 = *t*+180, C3 = *t*+270.
- Candidates: usable snapshots after *t* within ±45 days of the target. Pick the nearest; break equal-distance ties by taking the earlier date.
- C3 must come after C2; when C2 exists, only snapshots after C2 are C3 candidates.
- C1 is selected on its own, and its absence doesn't affect C2 or C3.
- Stored: checkpoint dates, offsets in days, and `followup_reason` (`ok`, `no_c2`, `no_c3`, `no_c2_c3`).

### Finality
A later snapshot can replace a provisional pick: one that arrives inside the window and is nearer the target, or a
flagged one that resolves as usable. So a checkpoint is **final** only once:
1. its window has closed (target + 45 days), and
2. every unusable snapshot in the window that would outrank the pick, if it were usable, has a known status.

`cN_final_at` is the later of those dates and the pick's own status-known date. C3 is final no earlier than C2,
because C3's candidates depend on C2. `label_final_at` = the later of the C2 and C3 final dates. A label is `final`
when `label_final_at` ≤ the data's as-of date, and `provisional` otherwise. **Provisional labels are never used for
training or evaluation.** This assumes snapshots arrive in date order, with no backfill of earlier dates.

## 3. Population (prespecified business segment)

Uses only information available at *t*. Exclusion counts are reported, and an all-listings comparison is kept.

| Rule | Main | Sensitivity |
|---|---|---|
| Present in the prediction-date snapshot | required | required |
| **Active review:** `last_review_date` within 365 days of *t* | qualifies | — |
| **Recently first observed:** first seen within 180 days of *t*, **and** the city's coverage started ≥ 180 days before that first sighting | qualifies | — |
| First seen soon after coverage began | newness **unknown**; can qualify only through active review | — |
| Quality: exclude `overall_rating` < 4.0 with ≥ 5 reviews | applied | not applied |
| Missing rating | kept | kept |

"Recently first observed" isn't "newly listed": at a city's first scrape, every listing is first observed.

## 4. Prediction unit vs. action unit
- **Model:** scores listings.
- **Outreach:** listings are grouped by the `KEY_HOST_ID` they have **at *t***, so each host appears once.
- **Capacity assumption:** 500 unique hosts per quarter across the 6 markets, with 100 and 1,000 as sensitivity checks.
- **Host-level precision:** the share of contacted hosts with ≥ 1 eligible listing that is `absent_confirmed`.
  Listing-level metrics are reported separately.
- **Host change after *t*:** the outcome is listing-level. The outreach target stays the host at *t*; changes are flagged (`host_changed`).

## 5. Worked examples (tested)

P = present, A = absent, – = not relevant, ∅ = no usable checkpoint.

| # | Case | C1 | C2 | C3 | Expected |
|---|---|---|---|---|---|
| 1 | Stays | P | P | P | observed |
| 2 | Leaves early | A | A | A | absent_confirmed |
| 3 | Seen in a day-30 snapshot, then gone | A | A | A | absent_confirmed |
| 4 | Late disappearance | P | A | A | absent_confirmed |
| 5 | Temporary absence | A | P | P | observed |
| 6 | Absent at C2, back at C3 | P | A | P | observed |
| 7 | Leaves after the horizon | P | P | A | observed |
| 8 | Partial scrape at the nearest C2 snapshot; another usable snapshot within ±45 d | – | that snapshot | P/A | decided by that snapshot |
| 9 | No usable snapshot near *t*+270 | – | A | ∅ | insufficient_followup |
| 10 | Host changes, listing stays | – | P (host Y) | P | observed; outreach to host X; host_changed |
| 11 | *t* would be a flagged snapshot | – | – | – | not a prediction date |
| 12 | Recently first observed, no rating, coverage ≥ 180 d earlier | – | – | – | eligible |
| 13 | Gone at C2 and C3, back later | – | A | A | absent_confirmed (reactivation reported) |
| 14 | Present at C2, C3 unavailable | – | P | ∅ | insufficient_followup |
| 15 | C2 unavailable, present at C3 | – | ∅ | P | insufficient_followup |
| 16 | Absent at a suspected-contraction snapshot used as C3 | – | A | A (suspected contraction) | absent_confirmed; final at C3's resolver (first unflagged snapshot after it) |
| 17 | First observed at the city's first scrape, no recent review | – | – | – | not eligible (newness unknown) |
| 18 | Absent at *t*+250, back at *t*+270 (both within C3's window) | – | A | P at *t*+270 | provisional until *t*+315, then observed |
| 19 | Two damaged snapshots in a row, then recovery | – | – | – | both `partial_scrape`, resolved by the recovery snapshot |
| 20 | Flagged snapshot nearer *t*+180 than the pick, resolved later | – | pick | – | C2 final at the flagged snapshot's resolution date |
| 21 | Flagged snapshot with no reliable snapshot within 200 days | – | – | – | `anomaly_unresolved`, known at snapshot + 200 days |
| 22 | No usable C2/C3, but a C2-window blocker resolves after C3's window closes | – | ∅ | ∅ | insufficient_followup, final at the blocker's resolution |

Also tested: tie-breaking, C3 strictly after C2, C1 independence, unusable snapshots never used as checkpoints,
`insufficient_history` and `anomaly_pending` dates, and two information-availability properties:
(a) every final label can be reproduced from only the data available at its `label_final_at`, and
(b) with data appended 15 days at a time, a label that's final never changes.

## 6. Exploratory evidence (pre-specification)

From a quick analysis using every monthly snapshot as *t*, requiring C1, and the earlier two-sided completeness rule.
Recomputed under this spec in `reports/label_summary.md`.

| | 2015–22 | 2023+ |
|---|---|---|
| Checkpoint rule | 21.5% | 16.3% |
| "Any snapshot in 180 d" rule | 5.3% | 9.7% |
| Absent at C2, back at C3 | 1.6% | 1.7% |

## 7. Evaluation timing
- **When a label can be used:** at `label_final_at`. A model deployed at quarter *Q* trains only on labels with `label_final_at` < *Q*.
- **Predictor allowlist:** the label tables contain fields derived from the future (`c1`–`c3`, `in_c1`–`in_c3`, `outcome`,
  `host_changed`, the `*_final_at` dates, `label_status`). Features come only from an explicit allowlist of
  fields known at *t*. Nothing from the label output is a predictor.
- **Overlap:** quarterly prediction dates reduce repetition but outcomes still overlap, since follow-up lasts ~9 months. Account for this in uncertainty estimates (e.g. block bootstrap by host).
- **Main evaluation:** rolling-origin backtest, one deployment per quarter, with tuning and calibration on earlier, separate periods.
- **Final holdout:** a **shared calendar block**, **2023-Q4 to 2024-Q3**, the last 4 quarters in which all 6 markets have
  final outcomes (`reports/label_summary.md`). 2024-Q4 (5 markets; not Austin), 2025-Q1 (4) and 2025-Q2 (3) are reported, not used
  as market-specific test periods. Later quarters have no final outcomes yet.
- **Secondary:** a historical stress test (train 2016–2019, test 2023+), plus sensitivity at ±31 / ±60-day tolerance, the any-snapshot rule, and the all-listings population.

## 8. Parameters (approved)

| Parameter | Value |
|---|---|
| Checkpoint tolerance | ±45 days; coverage and actual offsets reported by city and era |
| Anomaly flag | < 75% of the trailing 3-snapshot median |
| Partial-scrape resolution | ≥ 50% of the reference's missing listings return at the first reliable later snapshot |
| Resolution wait limit | 200 days, then `anomaly_unresolved` |
| Minimum history | 3 earlier snapshots |
| Active review window | 365 days |
| Recently first observed | within 180 days, with ≥ 180 days of prior city coverage |
| Quality exclusion | rating < 4.0 with ≥ 5 reviews |
| Decision size | 500 unique hosts per quarter (100 / 1,000 sensitivity) |
