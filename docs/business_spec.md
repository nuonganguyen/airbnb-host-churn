# Business Evaluation Specification

Implemented in `src/business.py`; settings frozen in `config/analysis_freeze.json` before the holdout.
Inputs are backtest predictions (calibrated LightGBM probabilities *p<sub>i</sub>*, the best rule) and at-*t*
features. Both quality variants are reported.

## 1. Decision being evaluated

Each quarter, a retention team contacts **K = 500 unique hosts** (100 and 1,000 as sensitivity). It picks
them by one of four rankings, compared with random contact:

| Strategy | Host score | Notes |
|---|---|---|
| risk | max<sub>i∈h</sub> *p<sub>i</sub>* | a ranking heuristic, not a probability that the host's portfolio disappears |
| **risk × value** | **Σ<sub>i∈h</sub> *p<sub>i</sub>·V<sub>i</sub>*** | expected exposure; never max *p* × portfolio value |
| value only | Σ<sub>i∈h</sub> *V<sub>i</sub>* | the "prioritise valuable accounts" baseline |
| best rule | max<sub>i∈h</sub> rule score | `rule:low_presence_365`, chosen on the primary development folds |

Hosts are identified by the host at *t* and deduplicated across markets within a quarter. **Contact timing:** the earliest
`decision_date` among the host's eligible listings that quarter.

## 2. Value proxy *V<sub>i</sub>*

**Meaning:** an approximate **12-month gross booking value at the listing's asking price**, host side. It is not
realized revenue (asking prices and review-based bookings are both proxies), and not platform revenue.

- **Bookings per year** = reviews per 30 days (365-day rate; 90-day rate if missing; negative → 0) × 365/30 ÷ *review share*.
- **Nights** = bookings × max(min nights capped at 30, 3), capped at 70% of the year.
- ***V<sub>i</sub>*** = price × nights. A missing or zero price is filled with the median price of the same city, room type and
  neighbourhood at that quarter's prediction dates (then city × room type), and flagged; prices are capped at the quarter's p99.
- **Scenario range:** review share **0.30 / 0.50 / 0.72** (higher / central / lower value). Results are reported for all three.
  Listings without reviews get *V* = 0, so new listings are undervalued.

## 3. Outputs

1. **Targeting value:** host precision@K (share of contacted hosts with ≥ 1 eligible listing `absent_confirmed`), lift over the
   rule, and results by eligible portfolio size (1, 2–5, 6–20, 21+).
2. **Value exposure:** *estimated value associated with correctly flagged disappearances*, the summed *V<sub>i</sub>* of `absent_confirmed`
   listings held by contacted hosts, plus its share of all disappearing value that quarter.
3. **Intervention scenarios:** net benefit per quarter = *prevention rate × take rate × captured value − cost per contact × K*,
   and the break-even cost per contact.
   - **Prevention rate** (5% / 10% / 20%): the share of **otherwise-occurring** disappearances that contact prevents. Unknown until tested.
   - **Take rate** (10% / 15%): converts host booking value into platform revenue.
   - **Cost per contact** ($25 / $100 / $250).

Quarter-by-quarter comparisons use the moving-block bootstrap from the backtest.

## 4. Experiment proposal

The backtest shows **who is likely to disappear**, not whether contact changes it. A prevention rate needs an experiment.

- **Unit:** the host, randomized once across all markets, so multi-market hosts can't be in both arms.
- **Population:** each quarter, the top **1,000** hosts by the frozen risk × value ranking. Randomize 1:1, stratified by market × portfolio size
  (1 / 2–5 / 6–20 / 21+). Hosts with 21+ listings supply most captured value, so they need their own stratum.
- **Treatment:** retention outreach within 14 days of the host's contact date. **Control:** business as usual.
- **Primary outcome:** the host has ≥ 1 eligible listing `absent_confirmed`, the same label as the model, known ~9–10 months
  later (`label_final_at`). **Prevention rate** = 1 − (treatment rate ÷ control rate).
- **Secondary outcomes:** value-weighted retained *V*, listings retained, and contact cost. **Guardrails:** host complaints and opt-outs.
- **Analysis:** intention to treat. Pre-register the outcome, strata and minimum detectable effect.
- **Size (post-holdout audit, `reports/post_holdout_audit.md`):** in the proposed recruitment population (top 1,000 by Σ p·V), the holdout
  event rate is 0.475. A 10% relative reduction then needs about **1,722 independent hosts per arm** (two-sided α = 0.05, power 0.8),
  about 4 recruitment quarters of 500 new hosts per arm, plus ~9–10 months of follow-up. A 5% reduction needs ~6,900 per arm. Hosts recur
  across quarters and are randomized once. The frozen business reports size it on the top 500 by risk instead (0.61 development / 0.51 holdout),
  which is the wrong population.

## 5. Limitations
- **Calibration:** in development the mean absolute gap between average predicted probability and observed frequency is ~5 pp per quarter; on the
  holdout it is **10.5 pp** (worst 13.9 pp, always overpredicting). This inflates Σ*p*·*V* exposure and affects Σ*p*·*V* rankings more than max-*p* rankings.
- **Contact timing:** host aggregation pools the whole quarter across markets but contacts on the earliest decision date, so a small share of contacted
  hosts (12–24 of 500 per holdout quarter) were ranked partly on later observations. Results are a pooled quarterly ranking benchmark.
- **Portfolio share:** captured value is dominated by hosts with many listings (59–83% from 21+ listings in development). Their responsiveness to outreach may differ.
- **What "disappearance" means:** the listing id is gone from the source (see `docs/label_spec.md` and `docs/source_breaks.md`), not necessarily the accommodation.
