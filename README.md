# Supply at Risk: Predicting Airbnb Host Churn

*An end-to-end churn project on a decade of public Airbnb data, built the way a real team would: a read-only source,
labels you can defend, a holdout opened once, and a number a retention team can act on.*

Every marketplace pays to win new supply. Very few can tell you which of their current hosts are about to pull their
listings, until the listings are already gone.

That is the gap this project fills. Each quarter it answers one question: **which 500 hosts should a retention team
contact first?** It finishes where most churn tutorials stop short: a contact list that beats the best simple rule by
**about 90 hosts per 500** on a holdout opened exactly once, the cost per call at which outreach pays for itself, and
the experiment that would prove it works.

## The dataset

Public snapshots from [Inside Airbnb](https://insideairbnb.com/get-the-data/) (CC BY 4.0) for six US markets: Austin,
Denver, Nashville, New Orleans, San Diego and Seattle. **563 snapshots, May 2015 to June 2026, 4.2M listing-snapshot
rows.** Monthly until 2022, quarterly after.

It is messy the way real data is messy. Files arrive days after their date, some scrapes are partial, and one quarter
breaks in a way nobody has explained. That is what makes it worth building on.

## First, the one rule that shapes everything

**A prediction made on date *t* may use only what was known on date *t*.**

It sounds obvious. It gets broken all the time. Here it reaches into everything: a snapshot counts only once it has
finished collecting, a suspicious snapshot counts only once a later one has resolved it, and a label becomes training
data only once nothing still to arrive could change it.

Hold that rule. Every step below is a way of enforcing it.

## Step 1 — Keep the source where nothing can touch it

The source database (35 US markets) lives on an external drive. It is attached read-only, so a stray write fails
instead of quietly damaging a decade of data ([src/db.py](src/db.py)):

```python
con.execute(f"ATTACH IF NOT EXISTS '{SOURCE_DB}' AS ia (TYPE sqlite, READ_ONLY)")
```

Everything the pipeline writes goes to `data_local/`, which is git-ignored. A fingerprint records the size and
modification time of every source file before the first run.

```bash
python src/fingerprint.py           # baseline of the source files
python src/fingerprint.py --check   # confirm nothing changed
```

***Check:*** *the fingerprint check is the last line of [scripts/reproduce.sh](scripts/reproduce.sh), so every full
rebuild ends by proving the source is untouched.*

## Step 2 — Find the data quality traps

Before trusting a single number, check the curated table against the raw CSVs. That turned up six traps, and any one of
them would have quietly bent the model:

| Trap | Effect | Fix |
|---|---|---|
| Prices ≥ $1,000 parsed only up to the thousands comma | 95,984 prices became 1–15 | re-read from raw |
| Missing values stored as 0 (price, response and acceptance rates) | 2.2M false zeros | NULL |
| Amenity codes `AC1`–`AC82` are positions of hand labels built from all years at once | "waterslide" at 96% in 2016 | dropped |
| `zip` actually holds neighbourhood names, mixed with other fields | geography not comparable across years | raw `neighbourhood_cleansed` |
| Snapshot rows collected days after the file date | features could see past the decision | all timing uses actual collection dates |
| 166 ids written in scientific notation | listings can't be followed over time | excluded |

Each fix lands in a corrected copy with every changed value flagged, so nothing is silently overwritten. (From December
2025 the source also stops publishing host response and acceptance rates. Those stay NULL; no fix exists.)

```bash
python src/run_sql.py sql/01_extract.sql             # 6-market extract
python src/rebuild_from_raw.py                       # re-read price, host and collection-date fields
python src/run_sql.py sql/02_clean.sql               # corrected copy, every change flagged
python src/validate.py listings_6city_clean.parquet
```

***Check:*** *[reports/data_validation_clean.md](reports/data_validation_clean.md) is the same validation re-run on the
corrected copy.*

## Step 3 — Decide what "gone" means before you predict it

This is the step most churn projects skip, and it decides everything after it. There is no "churned" column. A listing
simply stops appearing.

The obvious definition, "not seen again within 180 days", fails twice. It mislabels listings that show up once more and
then leave. And it gives monthly-era listings more chances to reappear, so apparent churn nearly doubles after 2022
(5% to 10%) only because snapshots became less frequent.

The label here uses two checkpoints. A listing present at a quarterly prediction date *t* is **`absent_confirmed`** if
it is missing from the snapshot nearest *t* + 180 days **and** from the one nearest *t* + 270 days (±45 days each).

Two more pieces keep it honest:

- **Unreliable snapshots.** A snapshot whose listing count drops below 75% of its trailing median is flagged. It is a
  **partial scrape** if most of the missing listings return at the next unflagged snapshot, and a suspected contraction
  if not. Until that later snapshot exists, the flagged one is unusable.
- **Finality.** A label is final only once every snapshot that could still change it has arrived and been classified.
  Models train on final labels only.

The population is active listings (a review in the last 365 days, or newly observed with enough prior coverage),
excluding poorly rated ones (below 4.0 with ≥ 5 reviews). The rules were fixed before any results.

```bash
python src/label.py   # -> data_local/labels/, reports/label_summary.md
```

***Check:*** *a forward-in-time test feeds data in 15 days at a time and confirms a final label never changes. Full
definition in [docs/label_spec.md](docs/label_spec.md).*

## Step 4 — Build features only from what you knew that day

61 predictors, built in SQL: the listing's state at *t*, tenure and recency, change over ~90 and ~365 days (with the
elapsed days included, since snapshot gaps vary), presence over the past year, the host's portfolio, and city and
neighbourhood supply.

Every one of them obeys the rule. History counts only if its status was known by *t*, partial scrapes never count as
history, and label outputs and IDs are banned outright (`features.FORBIDDEN`).

One feature worth stealing: **presence rate over the past year**, the share of usable snapshots that contained the
listing. It's a rate, so it means the same thing in the monthly and the quarterly eras.

```bash
python src/features.py   # -> data_local/features.parquet (1,865,331 rows)
```

***Check:*** *the tests rebuild every prediction date from data truncated at t, and from data whose later rows were
changed, dropped and added to. Each must match the full build exactly. A mutation runner
([tests/mutation_check.py](tests/mutation_check.py)) plants 24 deliberate bugs in the SQL and confirms the 91 tests
catch every one. Full spec in [docs/feature_spec.md](docs/feature_spec.md).*

## Step 5 — Beat a simple rule first, then train two models

Start with what a retention analyst could build in a spreadsheet. Four rules: days since the last review, low presence
over the past year, a low recent review rate, and a fully blocked calendar ([src/model.py](src/model.py)). The best of
them, **low presence over the past year**, is the bar every model has to clear.

Then two models. **Logistic regression** is simple and explainable. **LightGBM** is heavier and has to earn its place.
Preprocessing is fit on each fold's training rows only, and both models are calibrated on the latest two training
quarters.

What LightGBM leans on most: listing type, overall rating, days available over the next year, presence rate and
superhost status. Those are predictive associations, not reasons hosts leave.

## Step 6 — Evaluate the way it will be used

Accuracy is meaningless here. The team calls 500 hosts a quarter, so the metric is **host precision@500**: of the 500
highest-ranked hosts, the share with at least one listing that later disappears. Listings are scored; hosts are ranked
by their riskiest listing.

The test is a **rolling-origin backtest**: one fold per quarter, trained only on labels final before that quarter
starts, scored on the next. 23 development quarters, 2017 to 2023.

```bash
python src/backtest.py   # -> reports/backtest_development.md
```

![Share of 500 contacted hosts with a listing that later disappears, by quarter](reports/figures/host_precision_by_quarter.png)

The blue line sits above the orange one in every quarter. In development, LightGBM reaches **0.61** against **0.43** for
the best rule and 0.22 for random contact: **+17.9 pp**, better in **23 of 23** quarters (block-bootstrap 95% CI
13.9–20.8 pp). The spike in 2023 comes back later.

## Step 7 — Freeze everything, then open the holdout once

A holdout you can peek at is just another development fold. So before touching 2023-Q4 to 2024-Q3, every setting and
the hash of every analysis file went into [config/analysis_freeze.json](config/analysis_freeze.json). The code refuses
to run the holdout a second time, or with any frozen file changed.

```bash
python src/freeze.py                # settings + file hashes
python src/backtest.py --holdout    # refuses if already run, or if a frozen file changed
```

| Contact 500 hosts per quarter, ranked by | Development (23 quarters) | **Holdout (4 quarters, run once)** |
|---|---|---|
| Random | 0.22 | 0.17 |
| Best simple rule (low presence over the past year) | 0.43 | 0.33 |
| Logistic regression | 0.52 | 0.51 |
| **LightGBM** | **0.61** | **0.51** |

LightGBM beats the rule by **+18.4 pp** on the holdout, in all 4 quarters (15.6 to 20.8 pp). That is **about 90 more of
every 500 contacted hosts** going on to lose a listing. Precision is lower than in development, which coincides with a
lower base rate (17% vs 22%). That hasn't been shown to explain all of the drop.

And one result worth saying out loud: **logistic regression nearly ties LightGBM at 500 contacts** (0.508 vs 0.511).
The heavier model keeps a clear lead only on a tighter budget: 0.64 vs 0.49 at 100 contacts.

## Step 8 — Turn probabilities into a contact list

A risk score tells you who is likely to leave, not who is worth a call. So each listing gets a value proxy, ***V***:
twelve months of booking value at its asking price, with bookings estimated from reviews. (It's a proxy, run under three
scenarios for the share of stays that leave a review. It isn't realized revenue.)

Then rank hosts by expected exposure, **Σ p·V**: probability times value, summed over their listings. Compare that with
the obvious alternative, "call the biggest accounts" (Σ V).

Risk × value reaches **0.61** holdout precision against **0.52** for value alone, better in 4 of 4 quarters, and captures
**+11%** more of the estimated booking value that actually disappears. Risk adds a real but modest gain on top of size.

```bash
python src/business.py              # development -> reports/business_development.md
python src/business.py --holdout    # -> reports/business_holdout.md
```

## Step 9 — Translate it for the retention lead

Nobody on a retention team needs a precision-recall curve. They need four lines:

- **About half** of the hosts on the list go on to lose a listing, against **a third** with the best rule: **about 90
  more hosts per 500 calls**.
- Ranking by risk × value captures **+11%** more of the booking value that disappears than ranking by size alone.
- The value is concentrated: hosts with **21+ listings** hold **56–66%** of it.
- Outreach breaks even at **$370 to $2,200 per contact**, depending on how many disappearances it prevents (5% to 20%)
  and how many hosts take up the offer (10% to 15%).

And one sentence for the meeting:

*"This list finds about 90 more hosts a quarter who are about to lose a listing than our current rule does. We don't
know yet whether a call keeps the listing, and here is the test that will tell us."*

(The value and break-even figures are scenario estimates built on the proxy *V*, and the prevention rate is unknown.)

## Step 10 — Design the test that proves it works

Everything so far measures **targeting**: whether the list picks the right hosts. None of it shows that a call keeps a
single listing. Only an experiment can.

The proposal is a **host-randomized experiment**. Take the top 1,000 hosts per quarter by Σ p·V, split them 1:1,
stratified by market and portfolio size, and keep the same outcome label. In that population the holdout event rate is
47.5%, so detecting a 10% relative reduction needs about **1,722 independent hosts per arm**. That is about **four
recruitment quarters**, plus 9–10 months of follow-up. Hosts recur across quarters, so each one can be randomized only
once.

***Check:*** *design in [docs/business_spec.md](docs/business_spec.md); the sizing above is the corrected figure from
the [post-holdout audit](reports/post_holdout_audit.md).*

## Step 11 — Audit it before anyone ships it

After the holdout, a review raised two hard questions. The audit answers them from saved results, without touching the
frozen analysis:

- **Are the probabilities usable as probabilities?** Not yet. LightGBM overpredicts in every holdout quarter, by
  **10.5 pp** on average and **13.9 pp** at worst. The ranking holds up; dollar forecasts built on raw *p* would not,
  and recalibrating could reshuffle the risk × value list.
- **Could this list have been built on the day?** Not exactly. A quarter's ranking pools markets that are scraped on
  different days, so up to **24 of 500** contacted hosts were ranked partly on listings observed after their contact
  date. A live system needs a shared information cutoff or a sequential selection, and neither has been evaluated.

So the honest name for the result is a **pooled quarterly ranking benchmark**, not a deployable contact policy.

```bash
python scripts/post_holdout_audit.py   # -> reports/post_holdout_audit.md
```

## The quarter that broke the labels

At every January 2023 prediction date (five markets; Denver's quarterly schedule skips that quarter), **37–50%** of
listings came out absent, against 13–22% in neighbouring quarters. It's the spike in the chart above.

Four checks followed. Turnover was high (93rd–97th percentile) but comparable to COVID. Raw and extracted ids
reconciled. The source's data dictionary describes a collection change in August 2022 that doesn't explain it. The
strongest signal: **35–49%** of the vanished ids have a new id with the same host, neighbourhood, room type and capacity,
against at most 8% in all 473 earlier snapshot pairs. Even that doesn't establish they are the same accommodations, or
why it happened.

So the cause stays **unresolved**. Dropping outcomes because they look strange is itself a modelling choice, so the
primary analysis keeps them and a **prespecified sensitivity variant** excludes them. Both were frozen and both are
reported. They agree: the sensitivity variant beats the rule by +0.23 on the holdout, in 4 of 4 quarters.

***Check:*** *[docs/source_breaks.md](docs/source_breaks.md) and [reports/rekey_detection.md](reports/rekey_detection.md).*

## Trade-offs worth knowing

- **Logistic regression vs LightGBM:** a near tie at 500 contacts on the holdout, while LightGBM wins at 100 (0.64 vs
  0.49). Logistic regression is easier to explain; LightGBM is better when the budget is tight.
- **Risk vs risk × value:** risk finds the most hosts about to lose a listing; risk × value finds the most value at
  stake and shifts the list toward big operators (hosts with 21+ listings are 31% of that list, against 7% of the
  risk list).
- **Strict label vs quick label:** the two-checkpoint label waits ~270 days and needs finality rules, but it means the
  same thing in every era.
- **Keep vs drop the 2023 break:** keeping it is the primary analysis, dropping it is the sensitivity check. Same
  conclusion either way.
- **Ranking vs probabilities:** good enough to order hosts, not yet to forecast dollars.
- **Pooled benchmark vs live policy:** pooling a quarter is clean to evaluate, but a real contact process can't see
  listings from markets it hasn't scraped yet.

## The project in four lines

- **Overview:** rank 500 Airbnb hosts per quarter by the risk that their listings disappear, on a decade of public
  snapshots from six US markets.
- **Approach:** DuckDB SQL for a two-checkpoint label and 61 point-in-time features; simple rules, logistic regression
  and LightGBM in a rolling-origin backtest; a frozen holdout, run once.
- **Findings:** host precision@500 of 0.51 against 0.33 for the best rule on the holdout (4/4 quarters); risk × value
  captures 11% more estimated disappearing value than ranking by size.
- **Limitations:** the target is a listing id, not an accommodation; value is a proxy; probabilities overpredict by
  10.5 pp; scores are associations, and whether outreach helps needs the experiment.

None of the hard parts were the model. They were deciding what "gone" means, keeping the future out of every feature,
and opening the holdout once. Every step has a reason you can say out loud, and a test or a report that checks it.

Steps 3 to 11 on the corrected data, with the code and its output: [notebooks/walkthrough.ipynb](notebooks/walkthrough.ipynb).
The formal write-up, with the method in full: [reports/writeup.md](reports/writeup.md).

---

## Run it yourself

### Data (not included)

This repository holds code, specifications and aggregate reports only. No listing-level data is committed. The source
is Inside Airbnb listings snapshots, loaded into a SQLite database (`ia.db`) by a separate R pipeline. To run the code,
point `SOURCE_DIR` in [src/db.py](src/db.py) at a folder containing `ia.db` and `raw/<City>/*_listings.csv`.
(`src/db.py` is part of the frozen analysis, so `src/freeze.py --check` will report the change.)

### Setup

```bash
# Python 3.12+ (scipy wheels for 3.10 fail to load on recent macOS)
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt

scripts/reproduce.sh               # extract -> clean -> validate -> labels -> features -> tests -> backtest -> business
python tests/mutation_check.py     # optional: the suite must catch 24 deliberate SQL bugs (~4 min)
```

A full rebuild takes about 1.5 hours. The holdout is not rerun: it runs once, and `src/backtest.py` refuses a second
run. The holdout results come from commit `c09092f` (hashes as rewritten on 2026-10-21, when commit emails were changed
to the GitHub noreply address).

### Repo map

```
host-churn/
├── sql/       01_extract → 02_clean → 03_label → 04_features
├── src/       db, fingerprint, run_sql, rebuild_from_raw, validate, quality, label, features,
│              model, backtest, business, freeze
├── scripts/   reproduce.sh, make_figures.py, post_holdout_audit.py
├── notebooks/ walkthrough.ipynb: from the label onward, with code and output
├── tests/     91 tests + mutation_check.py
├── docs/      label, feature and business specs; source breaks
├── config/    analysis_freeze.json, quality_policy.json
└── reports/   write-up, backtest and business reports, figures
```

## License

Code: MIT (see [LICENSE](LICENSE)). Data: not redistributed; Inside Airbnb data is CC BY 4.0.
