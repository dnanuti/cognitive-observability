---
name: battery
description: >
  Quick self-reported energy check (Samn-Perelli fatigue scale) with an optional
  NASA-TLX follow-up, plus a monthly exhaustion-and-causes check. Use when the
  user runs `/battery` (optionally `/battery 4`), answers a "battery check" from
  a break nudge with a number 1–7, runs `/battery month`, or when `/observe`
  offers the monthly check.
disable-model-invocation: false
---

# Battery check

A self-report beats anything you can infer. Use the published wording below exactly. Never fill in a rating for the user, and never state one as fact.

## 1. Get the rating

If the user already gave a number 1–7 (as an argument or in reply to a nudge), use it. Otherwise ask, word for word:

> **Battery check:** which best describes how you feel right now?
> 1. Fully alert, wide awake
> 2. Very lively, responsive, but not at peak
> 3. Okay, somewhat fresh
> 4. A little tired, less than fresh
> 5. Moderately tired, let down
> 6. Extremely tired, very difficult to concentrate
> 7. Completely exhausted, unable to function effectively
>
> (or skip)

Source: Samn & Perelli (1982), USAF School of Aerospace Medicine. Lower is more alert.

If the user skips, say "Skipped." and continue the work. A skip is not a low score.

## 2. Respond to the rating

Keep it short. The scale's authors associate 5–6 with moderate-to-severe fatigue, where performance may start to suffer.

| Rating | Response |
|---|---|
| 1–3 | Acknowledge in a few words and carry on. Reset the nudge cool-down. |
| 4 | Carry on. The next break nudge may come a little earlier. |
| 5 | Suggest a break or a natural stopping point. Offer a "where we are" note. |
| 6–7 | Suggest stopping for now. Write the "where we are" note so the work can be picked up later. Never argue for continuing because "we're almost done." |

A **"where we are" note** has three short parts: what we tried, the current state, and the first step on return.

## 3. Optional follow-up (only for a rating of 5 or higher)

Offer once, skippable, as two NASA-TLX items (Hart & Staveland, 1988) answered on 0–10:

> What's draining it? (0–10 each, or skip)
> - **Mental demand:** How mentally demanding was the task?
> - **Frustration:** How insecure, discouraged, irritated, stressed, and annoyed were you?

Use the answer to fit the suggestion: high mental demand points to a break or splitting the task; high frustration points to stepping back from a retry loop or changing approach. These 0–10 answers are only comparable with the user's own earlier answers, not with published TLX scores.

## 4. Record it

Append one line per answer to `checkins.md` in the project memory directory, the same directory that holds `MEMORY.md`. Record no prompt text.

If the file doesn't exist, create it:

```markdown
---
name: mindful-work-checkins
description: Self-reported check-ins (Samn-Perelli battery, NASA-TLX, weekly burnout item, monthly check), one line each
metadata:
  type: user
---

Format: `YYYY-MM-DD HH:MM · instrument · answer · source`
instrument: samn-perelli (1–7) | tlx-mental (0–10) | tlx-frustration (0–10) | burnout (1–5)
            | bo1–bo4, qd2, in3, re1, sc1, ju4, mw1, wf2 (0–100, monthly check)
source: manual | nudge | observe

```

Then add one pointer line to `MEMORY.md`, unless one is already there:

```text
- [Mindful-work check-ins](checkins.md) — self-reported battery/TLX/burnout ratings, one line each
```

Example lines:

```text
2026-11-05 14:32 · samn-perelli · 5 · nudge
2026-11-05 14:33 · tlx-mental · 8 · nudge
2026-11-05 14:33 · tlx-frustration · 3 · nudge
```

Take the time from the latest `mindful-work: local time` line if present, otherwise from `date`. Record skips as `skip`. If an existing `checkins.md` has an older format note, add the monthly keys to it.

## 5. Monthly check (`/battery month`, or when `/observe` offers it)

A longer-term check: four exhaustion items and one optional item per cause area. Items are from COPSOQ III (COPSOQ International Network, CC BY-NC-ND 4.0), used **word for word** with their published answer options. Don't reword them, don't call this check "COPSOQ", and don't compare scores with COPSOQ norms.

**Cadence.** At most once per 28 days. If `checkins.md` already has a `bo1` line from the last 28 days, say when the last one was and don't ask again unless the user insists. Never at session start, never mid-task.

### Part A: exhaustion (always ask all four together)

Show the answer options once, then the items:

> These questions are about how you have been during the last 4 weeks.
> Answer each with 1–5 (or skip):
> 1. All the time · 2. A large part of the time · 3. Part of the time · 4. A small part of the time · 5. Not at all
>
> - a. How often have you felt worn out?
> - b. How often have you been physically exhausted?
> - c. How often have you been emotionally exhausted?
> - d. How often have you felt tired?

Accept "a3 b2 c3 d1", "3 2 3 1", or the words. Store the published values: All the time = 100, A large part of the time = 75, Part of the time = 50, A small part of the time = 25, Not at all = 0.

**Exhaustion score** = mean of the answered items, only if at least 3 of 4 were answered. Otherwise there is no score this month; say so plainly.

### Part B: causes (optional; offer once, skippable as a block)

> Seven quick ones about what's around the work (1–5 each, or skip all):
>
> Frequency: 1. Always · 2. Often · 3. Sometimes · 4. Seldom · 5. Never/hardly ever
> - e. How often do you not have time to complete all your work tasks?
> - f. Can you influence the amount of work assigned to you?
> - g. How often do you get help and support from your colleagues, if needed? (or "I do not have colleagues")
>
> Extent: 1. To a very large extent · 2. To a large extent · 3. Somewhat · 4. To a small extent · 5. To a very small extent
> - h. Is your work recognized and appreciated by the management?
> - i. Is the work distributed fairly?
> - j. Is your work meaningful?
> - k. Do you feel that your work drains so much of your energy that it has a negative effect on your private life?

Stored values: option 1 = 100, 2 = 75, 3 = 50, 4 = 25, 5 = 0. "I do not have colleagues" is stored as `na`.

| Letter | Key | Area | Reading |
|---|---|---|---|
| e | `qd2` | Workload | demand: high is worse |
| f | `in3` | Control | resource: low is worse |
| g | `sc1` | Community | resource: low is worse |
| h | `re1` | Reward | resource: low is worse |
| i | `ju4` | Fairness | resource: low is worse |
| j | `mw1` | Values (closest proxy for detachment) | resource: low is worse |
| k | `wf2` | Work–life | demand: high is worse |

Never invert stored values; apply the reading only when you talk about them.

### Responding

Compare with the previous monthly check, if there is one.

| Result | Response |
|---|---|
| Score < 50, or ≥ 10 points lower than last month | Record. One factual line, e.g. "Exhaustion 31, down from 50 last month." |
| Score ≥ 50 (on average "part of the time" or more), or ≥ 15 points higher than last month | Record. Name the 1–2 cause areas that look worst (highest demand, lowest resource) and offer the Workload Summary from `/observe` |
| Score ≥ 75 | As above, and say once, plainly, that this is worth raising with someone they trust (a manager, colleague or professional support). No diagnosis, no self-care list, no repeating it later |

These cut-offs only decide when to offer something. They are not validated clinical cut-offs; say so if asked. Never combine the exhaustion score with other numbers into one score.

### Recording

One line per item, same format as above, keys `bo1`–`bo4` and the Part B keys, source `manual` (for `/battery month`) or `observe`. Example:

```text
2026-11-30 17:30 · bo1 · 75 · observe
2026-11-30 17:30 · bo2 · 50 · observe
2026-11-30 17:30 · bo3 · 75 · observe
2026-11-30 17:30 · bo4 · 75 · observe
2026-11-30 17:31 · qd2 · 75 · observe
2026-11-30 17:31 · sc1 · na · observe
2026-11-30 17:31 · mw1 · skip · observe
```

## Rules

- Always optional. Never ask at session start, and never ask twice in a row.
- Don't comment on trends here; that belongs in `/observe`.
- No diagnosis, no generic wellness advice.
