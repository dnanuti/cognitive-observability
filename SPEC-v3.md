# Spec v3: from session fatigue to burnout risk

> Status: approved v3 · 2026-11-08 · builds on [SPEC.md](SPEC.md) (v2), which stays valid unless a section here replaces it.
> Constraint kept from v2: **no extra apps, daemons or services.** Claude Code instructions, hooks, skills, its memory folder, and the stdlib-only Python analyzer already in `scripts/`.

## 0. How to read this spec

This spec drives the implementation. Each requirement has an ID (`R-…`) and each requirement has at least one acceptance check (`AC-…`). Checks marked **[test]** are automated in `tests/`; checks marked **[replay]** are verified by running the analyzer on synthetic data; checks marked **[review]** are verified by reading the skill text. A phase is done when all its checks pass.

---

## 1. Why v3

v2 watches **acute load**: how hard this session or this day is. That is fatigue, not burnout. Burnout is a chronic state built over weeks to months, with three parts (Maslach): **exhaustion**, **cynicism / detachment**, and **reduced efficacy**. Its causes are mostly structural, in six areas of work life (Leiter & Maslach): **workload, control, reward, community, fairness, values**.

The working model for v3 is **effort–recovery** (Meijman & Mulder) plus **job demands–resources**: high load causes harm when recovery is too short for too long and resources are too few. So the most useful quantity to add is **recovery**, not more load signals.

Gaps in v2 this spec closes:

| Gap in v2 | v3 answer |
|---|---|
| Recovery is implicit (idle gaps only) | Explicit recovery layer: rest days, late days, days since rest, compared to your own baseline (section 3) |
| Single-item burnout measure only covers exhaustion roughly | Monthly check with validated exhaustion items, plus one item per cause area (section 4) |
| Cynicism, efficacy and causes not captured | Cause items from COPSOQ III; cynicism proxied by *meaning of work* (known limit, section 4.4) |
| No way to tell whether the signals match how you feel | Personal validation view after 8+ paired weeks (section 5) |
| No team view | Design for an opt-in, aggregate-only team layer; **not implemented until decided** (section 6) |

## 2. Three layers, never one score

| Layer | Timescale | Source | Where it shows |
|---|---|---|---|
| **Acute load** | minutes–hours | hook stretch time, in-session signals, Samn-Perelli | in-session nudges (v2, unchanged) |
| **Recovery** | days–weeks | `daily.jsonl` and raw session logs (numbers only) | `/observe 7d`+, report section 7 |
| **Chronic state and causes** | weeks–months | weekly single-item burnout, monthly check | `/observe 7d`+, report section 6 |

- **R-1** The layers are reported separately, each with its own facts. No composite "burnout score" is computed, stored or shown.
  - AC-1a [review] `/observe` output and the report have no field or sentence combining layers into one number.
  - AC-1b [test] the analyzer's JSON has `recovery` and `checkins` as separate keys and no `burnout_score`-like key.
- **R-2** Predictions are framed as "this pattern is drifting, here's what changed", never as a risk number attached to a person.
  - AC-2 [review] skill text contains no risk percentage, grade or label for the person.

---

## 3. Recovery layer

Computed by `scripts/analyze_sessions.py` from the per-day records it already builds (raw logs plus `daily.jsonl`). Numbers only; no new data store.

### 3.1 Definitions

| Term | Definition |
|---|---|
| **Known day** | A day with data (raw or history). Days with no data are *unknown*, never counted as rest |
| **Rest day** | Known day with `active_h < 0.5` |
| **Late day** | Known day with `late_prompts ≥ 3` (late = outside weekday 09:00–18:00, or any time on a weekend, as in v2) |
| **Long day** | Known day with `active_h ≥ 8` |
| **Work streak** | Consecutive known non-rest days ending on the last finished day. An unknown day ends the streak |
| **Week** | The 7 finished days ending yesterday (rolling), so `/observe 7d` and the report agree |
| **Baseline** | Median of the same weekly metric over the 4 rolling weeks *before* the current week. Needs ≥ 14 known days in those 28; otherwise "no baseline yet" |

Today is never included: it isn't finished.

- **R-3** The analyzer outputs, for the current week: `rest_days`, `late_days`, `long_days`, `active_h`, `known_days`, the current `work_streak`, and the baseline for each weekly metric (or `null`).
  - AC-3a [test] a week with 5 workdays of 4 h and 2 empty days gives `rest_days = 2`, `late_days = 0`, `work_streak = 0` if yesterday was empty.
  - AC-3b [test] a day with `no_data` is neither rest nor work, and breaks the streak.
  - AC-3c [test] fewer than 14 known baseline days gives `baseline = null` for every metric.

### 3.2 Drift flags

A flag is a factual statement about change from *your own* baseline. Thresholds are deliberately simple and live at the top of the script with the others.

| Flag | Fires when |
|---|---|
| `fewer_rest_days` | `rest_days ≤ 1` and `rest_days ≤ baseline − 1` |
| `more_late_days` | `late_days ≥ baseline + 2` |
| `more_long_days` | `long_days ≥ baseline + 2` |
| `long_streak` | `work_streak ≥ 12` (absolute: no baseline needed) |

- **R-4** Flags other than `long_streak` need a baseline; with no baseline they don't fire. No flag fires for a week with fewer than 5 known days (a week of missing data is not a week without rest). Baselines are medians of the 4 weekly values (mean of the two middle values).
  - AC-4a [test] each flag fires on the boundary value and not one step before it; the rest, late and long day definitions are tested at their boundaries too.
  - AC-4b [test] no baseline → only `long_streak` can fire.
  - AC-4c [test] a week with 4 known days raises no flag, even with a baseline.
- **R-5** **Recovery debt** = the number of consecutive rolling weeks (stepping back 7 days at a time, up to 8) with at least one flag. Reported as "N weeks in a row". "Sustained" needs N ≥ 2, matching v2's rule.
  - AC-5 [test] three flagged weeks then one clean week, counted from the latest, gives 0; one clean week then three flagged gives 3.

### 3.3 Known limits

- A "rest day" only means no Claude Code activity. Work in an editor, meetings or on-call are invisible. `/observe` says "days without Claude sessions", never "days off".
- The baseline is your recent normal, which may already be overloaded. That's why the check-ins in section 4 matter: they're the anchor.

---

## 4. Chronic state and causes: monthly check

v2's weekly single-item burnout question stays. v3 adds a **monthly** check with two parts, using COPSOQ III items **word for word** with their published response options.

### 4.1 Part A: exhaustion (4 items, always asked together)

Intro, verbatim: *"These questions are about how you have been during the last 4 weeks."*

| Key | Item |
|---|---|
| `bo1` | How often have you felt worn out? |
| `bo2` | How often have you been physically exhausted? |
| `bo3` | How often have you been emotionally exhausted? |
| `bo4` | How often have you felt tired? |

Response options: **All the time (100) · A large part of the time (75) · Part of the time (50) · A small part of the time (25) · Not at all (0)**.

**Scale score** = mean of answered items, if at least 3 of 4 were answered; otherwise no score.

### 4.2 Part B: causes (one item per area, optional, skippable as a block)

| Area | Key | Item | Options |
|---|---|---|---|
| Workload | `qd2` | How often do you not have time to complete all your work tasks? | F |
| Control | `in3` | Can you influence the amount of work assigned to you? | F |
| Reward | `re1` | Is your work recognized and appreciated by the management? | E |
| Community | `sc1` | How often do you get help and support from your colleagues, if needed? | F |
| Fairness | `ju4` | Is the work distributed fairly? | E |
| Values | `mw1` | Is your work meaningful? | E |
| Work–life | `wf2` | Do you feel that your work drains so much of your energy that it has a negative effect on your private life? | E |

- **F** (frequency): Always (100) · Often (75) · Sometimes (50) · Seldom (25) · Never/hardly ever (0)
- **E** (extent): To a very large extent (100) · To a large extent (75) · Somewhat (50) · To a small extent (25) · To a very small extent (0)

Values are stored as published (0–100). For **reading**, `qd2` and `wf2` are demands (high = worse); the other five are resources (high = better). The skill states which direction is which; it never inverts stored values.

`sc1` may be answered "I do not have colleagues", stored as `na`.

### 4.3 Cadence and responses

- **R-6** Asked at most once per 28 days, only in `/observe` with a timeframe ≥ 7 days, or on demand with `/battery month`. In a week the monthly check runs, the weekly single item is not asked as well.
  - AC-6a [review] `observe` skill checks `checkins.md` for a `bo1` line in the last 28 days before offering.
  - AC-6b [review] `observe` skips the weekly burnout item in a run that asks the monthly check.
- **R-7** Wording and response options are copied exactly from section 4.1–4.2; the user can answer with the number 1–5 of the option or its words.
  - AC-7 [review] text in `battery` skill matches this section character for character (checked by a test that greps the skill for each item string) **[test]**.
- **R-8** Responses after scoring:

| Result | Response |
|---|---|
| Score < 50, or ≥ 10 points lower than last month | Record. One-line factual summary only |
| Score ≥ 50 (on average "part of the time" or more), or ≥ 15 points higher than last month | Record. Name the 1–2 Part B areas that look worst (highest demand, lowest resource) and offer the factual Workload Summary from v2 |
| Score ≥ 75 | As above, plus v2's "4–5" response: say once, plainly, that this is worth raising with someone they trust |

These cut-offs are heuristics for *when to offer something*, not validated clinical cut-offs, and the skill must say so if asked.

  - AC-8 [review] the table above is in the skill; no other thresholds are introduced.

### 4.4 Known limits

- Cynicism/detachment has no item; `mw1` (meaning) is the closest proxy. Efficacy is not measured (COPSOQ's self-efficacy items describe a personality trait, not work). Both are stated in the report.
- Licence: COPSOQ III is CC BY-NC-ND 4.0, free for non-commercial use, with attribution, and modified material may not be distributed *as "COPSOQ"*. We use individual items verbatim, attribute them, and never call the check "COPSOQ" or compare scores with COPSOQ norms. See decision D-2.

### 4.5 Storage

Same `checkins.md`, same format: `YYYY-MM-DD HH:MM · <key> · <0–100|na|skip> · <source>`, with keys from 4.1–4.2 and source `observe` or `manual`.

- **R-9** The analyzer reads the new keys without changes to the line format and groups lines within 1 hour into one monthly check.
  - AC-9 [test] a block of 4 `bo` lines and 7 cause lines is parsed into one check with `exhaustion = mean(bo*)` and a `causes` dict; `na` and `skip` don't count towards the mean.

---

## 5. Personal validation (does this match how I feel?)

After at least **8 weeks with both** a weekly recovery record and a self-report (weekly burnout item or monthly exhaustion score), the report and `/observe 30d`+ show which recovery metrics move with your self-reports.

- **R-10** The analyzer pairs each self-report with the recovery metrics of the week before it and reports, per metric, the Spearman rank correlation and `n`. With `n < 8` it reports "not enough paired weeks yet" and nothing else.
  - AC-10a [test] perfectly monotonic synthetic pairs give ρ = 1.0; `n = 7` gives no correlation.
  - AC-10b [review] output wording is "moved together in your data (ρ = 0.6, 10 weeks)", never "predicts" or "causes".
- **R-11** No model is fitted and nothing is forecast in v3. Forecasting is out of scope until a year of paired data shows which metrics lead self-reports (decision D-4).

---

## 6. Team layer (design only, not built in v3)

Most effective interventions are structural, so the team view matters, but it is also how such tools turn into surveillance. v3 records the design; building it is a separate decision (D-3).

| Rule | Why |
|---|---|
| Individual data stays local and owned by the individual | No server holds personal records, so they can't be subpoenaed, leaked or misused |
| Contribution is opt-in per person, per period, and revocable | Consent is ongoing, not a one-off |
| A person contributes only **weekly aggregates**: recovery metrics, flags, monthly check scores (rounded to 25) | No timestamps, no project names, no text |
| A team view needs **k ≥ 5** contributors for that week; otherwise it shows nothing | Small groups re-identify people |
| The view shows distributions and trends, never a ranked list or a named person | Points at structure, not individuals |
| Structural signals come from team tools (on-call load and its spread, review concentration, unplanned work), not from Claude sessions | That's where the causes live |
| Never used for performance evaluation, stated in writing to the team before rollout | Goodhart: once measured for evaluation, people game it (batch commits, hide late work) |

---

## 7. Changes by component

| Component | Change | Requirements |
|---|---|---|
| `scripts/analyze_sessions.py` | `recovery` block (3.1–3.2), recovery-debt count, parse monthly-check keys, paired correlation | R-1, R-3–R-5, R-9, R-10 |
| `scripts/report_template.html`, `report.js` | New section "7. Recovery"; section 6 shows monthly checks and validation | R-1, R-10 |
| `.claude/skills/battery/SKILL.md` | `/battery month` asks the monthly check (4.1–4.2) | R-6–R-8 |
| `.claude/skills/observe/SKILL.md` | Cross-session mode runs the analyzer with `--json` for the recovery block; reports recovery facts; offers the monthly check per R-6; Workload Summary uses recovery and Part B | R-1, R-2, R-6, R-8 |
| `scripts/make_synthetic.py` | 8+ weeks, monthly checks, a slow drift (shrinking rest days, rising exhaustion) so the validation view has something to show | AC-10, demo |
| `tests/` (new) | stdlib `unittest` for every **[test]** check | all [test] ACs |
| `instructions/mindful-work.md` | No change. The in-session watch stays acute-only | — |

The in-session nudge must not start talking about weekly recovery: chronic topics belong in `/observe`, where the user asked for reflection.

---

## 8. Delivery phases (spec-driven)

Each phase starts by writing the failing tests for its [test] checks.

| Phase | Scope | Done when |
|---|---|---|
| **5** | Recovery layer in the analyzer + tests | AC-1b, AC-3*, AC-4*, AC-5 pass |
| **6** | Monthly check in `battery`, parser in analyzer, cadence in `observe` | AC-6*, AC-7, AC-8, AC-9 pass |
| **7** | `observe` reports recovery; report section 7 | AC-1a, AC-2 reviewed; synthetic report shows a recovery-debt streak in the high-effort weeks |
| **8** | Paired validation + synthetic data extended to 10 weeks | AC-10* pass; demo report shows ρ for each metric |
| **9 (not scheduled)** | Team layer | Only after D-3 |

---

## 9. Decisions

| # | Decision | Status |
|---|---|---|
| D-1 | Keep layers separate; no composite score (R-1) | accepted 2026-11-08 |
| D-2 | Use COPSOQ III items verbatim under CC BY-NC-ND 4.0 with attribution; not branded as COPSOQ; no norm comparison | accepted 2026-11-08 |
| D-3 | Build the team layer (section 6)? | deferred 2026-11-08: design only for now |
| D-4 | No forecasting in v3 (R-11) | accepted 2026-11-08 |
| D-5 | Rest/late/long thresholds (0.5 h, 3 late prompts, 8 h, 12-day streak) | accepted 2026-11-08 as starting values; tune after replay |

---

## Sources (new in v3; v2's list still applies)

- Maslach, C. & Leiter, M.P. (2016). Understanding the burnout experience: recent research and its implications for psychiatry. *World Psychiatry* 15(2), 103–111. doi:10.1002/wps.20311
- Leiter, M.P. & Maslach, C. (2003). Areas of worklife: a structured approach to organizational predictors of job burnout. *Research in Occupational Stress and Well-being* 3, 91–134. doi:10.1016/S1479-3555(03)03003-8
- Meijman, T.F. & Mulder, G. (1998). Psychological aspects of workload. In *Handbook of Work and Organizational Psychology* vol. 2, 5–33.
- Demerouti, E., Bakker, A.B., Nachreiner, F. & Schaufeli, W.B. (2001). The job demands–resources model of burnout. *J Appl Psychol* 86(3), 499–512. doi:10.1037/0021-9010.86.3.499
- Kristensen, T.S., Borritz, M., Villadsen, E. & Christensen, K.B. (2005). The Copenhagen Burnout Inventory: a new tool for the assessment of burnout. *Work & Stress* 19(3), 192–207. doi:10.1080/02678370500297720
- Llorens-Serrano, C., Pérez-Franco, J., Oudyk, J. et al. (2020). [COPSOQ III. Guidelines and questionnaire][copsoq]. COPSOQ International Network. Item wording, response options and licence (CC BY-NC-ND 4.0) taken from this document.

[copsoq]: https://www.copsoq-network.org/licence-guidelines-and-questionnaire
