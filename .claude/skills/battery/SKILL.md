---
name: battery
description: >
  Quick self-reported energy check (Samn-Perelli fatigue scale) with an optional
  NASA-TLX follow-up. Use when the user runs `/battery` (optionally `/battery 4`)
  or answers a "battery check" from a break nudge with a number 1–7.
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
description: Self-reported check-ins (Samn-Perelli battery, NASA-TLX, weekly burnout item), one line each
metadata:
  type: user
---

Format: `YYYY-MM-DD HH:MM · instrument · answer · source`
instrument: samn-perelli (1–7) | tlx-mental (0–10) | tlx-frustration (0–10) | burnout (1–5)
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

Take the time from the latest `mindful-work: local time` line if present, otherwise from `date`. Record skips as `skip`.

## Rules

- Always optional. Never ask at session start, and never ask twice in a row.
- Don't comment on trends here; that belongs in `/observe`.
- No diagnosis, no generic wellness advice.
