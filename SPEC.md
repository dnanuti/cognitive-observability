# Spec: Cognitive Observability v2: Claude that notices when the work is wearing you down

> Status: draft v2 · 2026-11-05
> Constraint: **no extra apps or tools.** Only what Claude Code already provides: instructions (CLAUDE.md or a skill), its built-in hooks, and its memory folder.

## Goal

While you work, Claude keeps a light watch on the session. When the work looks like it's grinding you down (long unbroken stretches, going in circles, rising frustration, late hours), it says so in **one short line** and suggests a break. Otherwise it stays quiet.

Nothing can measure "you've used your brain too much." Claude can only notice rough stand-ins: time without a break, retry loops, drift away from the goal, frustrated wording, and how much AI output you've had to review. The spec builds on those and does not claim to measure fatigue.

---

## 1. Why this matters (evidence)

| Finding | Source | What it means for the design |
|---|---|---|
| AI tends to make work more intense: people take on more and spread work into more hours, often unprompted | [HBR, Feb 2026][hbr-intensify] | Session length and time of day are worth watching |
| About 1 in 7 AI users report "brain fry." Heavy oversight of AI output predicted 12% more mental fatigue | [HBR/BCG, Mar 2026][hbr-brainfry] | Reviewing a lot of AI output is a real source of load |
| Developers' work is shifting from writing code to supervising AI output, which is demanding and hard to see | [arXiv 2510.07435][arxiv-strains] | Count the effort of reviewing, not only of writing |
| Developers believed AI made them 20% faster while measuring 19% slower | [METR 2025][metr-2025] (called outdated in [2026][metr-2026]) | People misjudge their own state mid-session, so an outside observer helps |
| Breaks of 10 minutes or less modestly reduce fatigue (d≈.35). Their effect on performance was not significant; demanding work may need longer breaks | [Albulescu et al. 2022][microbreaks] | Frame breaks as recovery, not a productivity hack |
| Stress built up over back-to-back meetings and stayed flat with 10-min breaks (EEG, n=14) | [Microsoft Human Factors Lab][ms-eeg] | Supports gap-based nudges; the evidence is weak, so don't overclaim |

Burnout builds over weeks of poor recovery, while breaks fix short-term fatigue. So the design has an **in-session loop** (nudge now) and a **weekly loop** (reflect with `/observe`).

Existing tools ([Stretchly][stretchly], [ActivityWatch][activitywatch], [Viva Insights][viva], [Uplevel / Haystack / Swarmia][cortex]) are either timers that can't see what the work is like, or team dashboards. None of them watch the AI conversation itself, which is the one thing Claude can see directly. That is this project's niche.

---

## 2. What Claude can and can't see on its own

| Claude can see | Claude can't see without help |
|---|---|
| Every prompt and reply in the session | **What time it is**, or how long the session has run |
| Rephrased requests and retry loops | Breaks you took away from the keyboard |
| Drift from the original goal | Other Claude sessions running in parallel |
| Frustrated or urgent wording | Anything you do outside Claude |
| How much code it produced for you to review | Earlier parts of the session once they've been summarized (compacted) |

Time is the most important gap: without it there's no "you've been at it for 2 hours." Claude Code's built-in **`UserPromptSubmit` hook** fills it. Its plain output is added to each prompt as context ([hooks docs][cc-hooks]), so a hook that prints the current time gives Claude a timestamp on every message. It's a one-line shell command in `settings.json` using the system clock: nothing to install.

Everything else stays within the session. Parallel sessions, outside-Claude work and true idle detection are **out of scope**: we accept these blind spots to keep it lightweight.

---

## 3. Components

Three pieces, all native to Claude Code:

| # | Component | Where it lives | Job |
|---|---|---|---|
| 1 | **Mindful-work instructions** | A short block in user-level `~/.claude/CLAUDE.md` (always loaded); a repo opts out with `mindful-work: off` in its own `CLAUDE.md` | Tells Claude what to watch for, when to speak up and how |
| 2 | **Timing hook** | `hooks/mindful-time.sh` on `UserPromptSubmit`, `PostToolUse` and `Stop` | Records activity from both sides and adds local time, current stretch and idle time to each prompt. A break means 10+ min with no activity from you *or* Claude, across sessions; prompt gaps alone would count Claude's long-running work as a break (found by the history replay: longest stretch 68 min by prompt gaps vs 139 min counting both sides) |
| 3 | **`/observe` skill** (exists; evolved) | `.claude/skills/observe/` | On-demand deeper reflection, weekly trends from git history plus saved snapshots |
| 4 | **`/battery` skill** (new, tiny) | `.claude/skills/battery/` | Asks the in-session self-report questions in section 6 and saves the answer |

**Why CLAUDE.md and not only a skill:** a skill loads only when invoked or when Claude decides it's relevant, so it can't be relied on to watch continuously. CLAUDE.md is always in context. The block must stay **short (about 15–25 lines)** so it doesn't crowd the context or distract from real work. The detailed reasoning stays in `/observe`.

---

## 4. Behavior spec for the in-session watch

### 4.1 Signals

| Signal | How Claude detects it | Default threshold |
|---|---|---|
| **Unbroken stretch** | Time since the last gap of ≥10 min between your prompts (from timestamps) | Mention at ~90 min; firmer at ~150 min |
| **Retry loop** | Same request rephrased 3+ times, or the same fix attempted repeatedly without progress | Suggest stepping back, not necessarily a break |
| **Yak shaving** | Work has drifted 2+ steps away from the original goal | Name the original goal and offer to park the side quest |
| **Frustration** | Wording like "nothing works", "why is this still broken", self-blame | Only counts alongside another signal |
| **Review load** | Claude has produced a lot of code or diff for you to check this stretch | Raises urgency of a time nudge; never a trigger on its own |
| **Late hours** | Timestamp outside working hours: weekdays 09:00–18:00 by default (configurable in the CLAUDE.md block); weekends count as outside hours all day | One quiet mention per day |

**Corroboration:** one signal alone (other than time) never triggers a nudge. Time, or two signals together, does.

### 4.2 How Claude speaks up

- **One line, at the end of a reply**, after the actual work is done. Never instead of the work, never mid-task, never while you're responding to an incident.
- **Facts, then a suggestion, in a warm voice.** Example: *"We've been at this ~1h50 and this fix is fighting back (4 tries). Good moment for a 10-minute break? I can note where we are first."* Warm, not cheerful: no exclamation marks, no praise, no wellness talk.
- **Offer a "where we are" note** before a break: what we tried, current state, first step on return (reusing `/observe`'s State Summary section). This removes the fear of losing context, a common reason to skip breaks.
- **Battery check attached to the nudge:** the nudge may end with an optional one-keystroke check (section 6.1), e.g. *"…A 10-minute break might help. Battery check, 1–7? (or skip)"*. It only appears when a nudge already fires, so it adds no extra interruptions.
- **Longer break after long stretches:** past ~150 min, suggest 15–20 minutes rather than 10, per the meta-analysis.
- **Late hours:** suggest a stopping point and offer the "where we are" note. Don't comment on the hour or the day itself.

### 4.3 Restraint rules (as important as the signals)

- At most **one nudge per ~45 minutes**; the timer resets after a detected break (≥10 min gap).
- If you say "not now", "later" or similar, stay quiet for the rest of that stretch.
- If you say "stop the break reminders", stay quiet for the session.
- Never diagnose, never moralize, never give generic wellness advice, never mention burnout. The only exception is the burnout question you choose to answer in `/observe` (section 6.3).
- When unsure, say nothing.

### 4.4 Known limits

- **Compaction:** once early messages are summarized, Claude may lose the session start time. Mitigation: the CLAUDE.md block asks Claude to keep the current stretch start time and nudge count in any summary. Accept that this is best effort.
- **Judgment varies:** detection is Claude's judgment, not a measurement. That's acceptable for a nudge; it's why `/observe` uses explicit scoring for anything stronger.
- **Single session only:** three parallel sessions each think you've been working for a short time.

---

## 5. Weekly loop: evolved `/observe`

No new data store. `/observe 7d` combines:

1. **Git history**, as today: commit times, churn, reverts and fixups, scope scatter.
2. **Snapshots** saved after each `/observe` run in Claude's memory folder.

Add to the output:
- Days with late-hour commits, and days with no commits at all (rough recovery days)
- Whether flagged patterns persist across snapshots ("sustained" requires 2+ weeks, never one bad day)
- A suggestion to run `/observe` at the end of a heavy day, so snapshots capture in-session signals git can't see

- **Factual workload summary (offered, never automatic):** when a pattern lasts 2+ weeks, or the burnout item (6.3) is 3 or higher twice in a row, offer a short neutral summary you could bring to a 1:1 or planning meeting, e.g. *"late-hour commits on 9 of the last 14 days, mostly in `billing/`; 3 revert clusters."* It stays private unless you share it, and it points at causes (workload, scope) rather than at you.
- Your own ratings from section 6 next to what Claude observed, e.g. *"Fatigue rated 5 or higher on 4 days; 3 of those had retry loops after 150+ min."* Over a few weeks this shows whether the signals match how you actually feel, which is the honest way to tune thresholds.

---

## 6. Self-report check-ins (battery level)

Your own rating beats anything Claude can infer. The questions below come from published, freely available instruments, used word for word wherever possible. Each one measures something different, so each has a different moment:

| When | Instrument | Measures |
|---|---|---|
| In session: `/battery`, or attached to a nudge | Samn-Perelli fatigue scale | How tired you are **right now** |
| Optional follow-up after a low rating | Two NASA-TLX items | **What** drained you: mental demand vs. frustration |
| Weekly, in `/observe 7d` | Single-item burnout measure (Dolan et al. 2015) | The **longer-term** trend, not today's energy |

### 6.1 In-session: Samn-Perelli fatigue scale

From USAF aircrew fatigue research (Samn & Perelli, 1982) and still standard in aviation fatigue risk management. 7 points; **lower is more alert**.

> **Battery check:** which best describes how you feel right now?
> 1. Fully alert, wide awake
> 2. Very lively, responsive, but not at peak
> 3. Okay, somewhat fresh
> 4. A little tired, less than fresh
> 5. Moderately tired, let down
> 6. Extremely tired, very difficult to concentrate
> 7. Completely exhausted, unable to function effectively

Item 7 is worded slightly differently across sources ("unable to function", "…effectively", "…ready to drop"). Use the version above throughout.

**What Claude does with the answer.** The scale's authors associate scores of 5–6 with moderate-to-severe fatigue, where performance may start to suffer:

| Rating | Claude's response |
|---|---|
| 1–3 | Acknowledge in a few words, carry on, reset the nudge cool-down |
| 4 | Carry on; the next break nudge may come a little earlier |
| 5 | Suggest a break or a natural stopping point; offer the "where we are" note |
| 6–7 | Suggest stopping for now; write the "where we are" note so the work can be picked up later |

Claude never suggests continuing past a 6–7 because "we're almost done."

### 6.2 Optional follow-up: what's draining it (NASA-TLX)

Asked only after a rating of 5 or higher, and always skippable. Two of the six NASA Task Load Index questions, worded as in the standard form:

> - **Mental demand:** How mentally demanding was the task? (very low → very high)
> - **Frustration:** How insecure, discouraged, irritated, stressed, and annoyed were you? (very low → very high)

The official form uses a 21-step scale; we use 0–10 for a one-keystroke answer. That modification means the numbers **can't be compared with published TLX scores**, only with your own earlier answers. The answer tells Claude what kind of help fits: high mental demand points to a break or splitting the task; high frustration points to stepping back from a retry loop or changing approach.

### 6.3 Weekly: single-item burnout measure

Asked at most once a week, and only during `/observe 7d` (or a longer timeframe), never mid-session. This is the non-proprietary version validated by Dolan et al. (2015) and recommended by the U.S. National Academy of Medicine. It is also used in the Mini-Z survey.

> **Overall, based on your definition of burnout, how would you rate your level of burnout?**
> 1. I enjoy my work. I have no symptoms of burnout.
> 2. Occasionally I am under stress, and I don't always have as much energy as I once did, but I don't feel burned out.
> 3. I am definitely burning out and have one or more symptoms of burnout, such as physical and emotional exhaustion.
> 4. The symptoms of burnout that I'm experiencing won't go away. I think about frustration at work a lot.
> 5. I feel completely burned out and often wonder if I can go on. I am at the point where I may need some changes or may need to seek some sort of help.

**Reading it.** Research usually splits it into ≤2 (no symptoms) and ≥3 (one or more symptoms). Validation was mainly against the emotional exhaustion part of the Maslach Burnout Inventory, so it is a screening signal, not a full measure.

| Answer | Claude's response |
|---|---|
| 1–2 | Record it; no comment beyond the normal `/observe` output |
| 3 | Record it; if it's 3 or higher in two consecutive check-ins, offer the factual workload summary in section 5 for you to bring to a 1:1 or planning meeting if you want |
| 4–5 | Acknowledge it plainly and without drama. Say once that this is worth raising with someone you trust (a manager, colleague or professional support), and offer the factual summary. No diagnosis, no list of self-care tips, no repeated reminders |

### 6.4 Rules for all check-ins

- **Always optional.** A skip is recorded as a skip, never treated as a low score.
- **Claude never fills in a rating for you** or states one as fact. Claude only reports what it observed.
- **No check-in at session start.** It adds friction before there's anything to rate.
- **Storage:** one line per answer in a single `checkins.md` in Claude's memory folder (date, time, instrument, answer). No prompt text. One pointer line in `MEMORY.md`, not one per check-in.

---

## 7. Fixes to the current skill (do first)

- Snapshot frontmatter: use `metadata.type` with an allowed type (`project`).
- Add Context Fragmentation to the scored categories.
- Use word boundaries in the revert/fixup grep ("retry" and "template" currently match).
- Scope the TODO count to the timeframe and author.
- Rebalance current-session scoring so it isn't capped low.
- Remove the leftover `system-prompt.md`.

---

## 8. Delivery phases

| Phase | Scope | Done when |
|---|---|---|
| **0** | Section 7 fixes; README with install steps | `/observe` runs cleanly and snapshots are well formed |
| **1** | CLAUDE.md block + timestamp hook; `/battery` skill with the Samn-Perelli check (6.1) and the check attached to nudges | In a real 2h session Claude nudges once at ~90 min, respects "not now", stays quiet otherwise; ratings land in `checkins.md` |
| **2** | Retry-loop / yak-shaving / frustration signals and the "where we are" note | Nudges name *why* they fired; no nudges in a smooth session |
| **3** | Weekly `/observe 7d` with snapshot trends, the NASA-TLX follow-up (6.2) and the weekly burnout item (6.3) | Two weeks of use produce a trend summary that sets your ratings next to the observed signals |
| **4 (optional)** | Package all three pieces as one Claude Code plugin for one-step install | Someone else can install it without editing files by hand |

**History replay (implemented):** `scripts/analyze_sessions.py` replays the nudge rules over local session logs and charts the results, so thresholds can be checked against real work before relying on them. A numbers-only daily history (`~/.claude/mindful-work/daily.jsonl`, written once a day) keeps trends beyond transcript retention.

**Testing approach:** replay or role-play sessions (smooth, grinding, late-night, frustrated) and check that Claude nudges in the right ones, stays quiet in the others and never nudges twice within the cool-down.

---

## 9. Non-goals

- No external apps, background daemons, wearables or OS idle detection.
- No event logs or new data stores beyond the existing snapshots, the single `checkins.md` file (section 6.4), the hook's two activity timestamps, and the numbers-only `daily.jsonl` summary (no text).
- No diagnosis or "fatigue score" presented as fact.
- No team or manager visibility. Personal and local only.
- No storing prompt text in snapshots; summaries only.

---

## 10. Decisions (resolved 2026-11-06)

1. **Scope of install:** user-level by default (stretch time already counts all sessions), with per-repo opt-out via `mindful-work: off` in the repo's `CLAUDE.md`.
2. **Working hours:** weekdays 09:00–18:00; weekends count as outside working hours all day. Still at most one stopping-point suggestion per day.
3. **Tone:** a bit warmer than purely factual, while keeping the restraint rules (no praise, no moralizing, no wellness advice).
4. **Timestamp hook:** acceptable. Claude Code hooks are a built-in feature, not an extra app or daemon; the hook is POSIX `sh` + `date`.
5. **Burnout item cadence:** weekly, in `/observe 7d`.

---

## Sources

- [AI Doesn't Reduce Work—It Intensifies It (HBR, Feb 2026)][hbr-intensify]
- [When Using AI Leads to "Brain Fry" (HBR, Mar 2026)][hbr-brainfry]
- [From Gains to Strains: Modeling Developer Burnout with GenAI Adoption (arXiv 2510.07435)][arxiv-strains]
- [Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity (METR)][metr-2025]
- [We are Changing our Developer Productivity Experiment Design (METR, Feb 2026)][metr-2026]
- ["Give me a break!" Micro-breaks meta-analysis (Albulescu et al., PLoS ONE 2022)][microbreaks]
- [Research Proves Your Brain Needs Breaks (Microsoft WorkLab)][ms-eeg]
- [Claude Code hooks reference][cc-hooks]
- Samn, S.W. & Perelli, L.P. (1982). *Estimating Aircrew Fatigue: A Technique with Application to Airlift Operations.* USAF School of Aerospace Medicine, SAM-TR-82-21. Wording via [FRMSc supported scales][samn-perelli] and [Emergency services fatigue study (PMC)][samn-perelli-pmc]
- Hart, S.G. & Staveland, L.E. (1988). NASA Task Load Index. Item wording via the [standard NASA-TLX form][nasa-tlx]
- [Dolan et al. (2015). Using a Single Item to Measure Burnout in Primary Care Staff. J Gen Intern Med 30, 582–587][dolan-2015]
- [NAM: Valid and reliable survey instruments to measure burnout][nam-burnout]
- [A Systematic Review of the Single-Item Burnout Question (JGIM, 2024)][sibo-review]
- Related tools, for context only: [Stretchly][stretchly], [ActivityWatch][activitywatch], [Viva Insights][viva], [Engineering intelligence platforms (Cortex)][cortex]

[hbr-intensify]: https://hbr.org/2026/02/ai-doesnt-reduce-work-it-intensifies-it
[hbr-brainfry]: https://hbr.org/2026/03/when-using-ai-leads-to-brain-fry
[arxiv-strains]: https://arxiv.org/html/2510.07435v2
[metr-2025]: https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/
[metr-2026]: https://metr.org/blog/2026-02-24-uplift-update/
[microbreaks]: https://pmc.ncbi.nlm.nih.gov/articles/PMC9432722/
[ms-eeg]: https://www.microsoft.com/en-us/worklab/work-trend-index/brain-research
[cc-hooks]: https://code.claude.com/docs/en/hooks
[samn-perelli]: https://help.frmsc.com/reference/results_breakdown/
[samn-perelli-pmc]: https://pmc.ncbi.nlm.nih.gov/articles/PMC4772191/
[nasa-tlx]: https://site.unibo.it/hfrs/en/traning-and-consultancy/human-factors-methods/nasa-tlx-scale-1.pdf/@@download/file/NASA-TLX%20Scale.pdf
[dolan-2015]: https://link.springer.com/article/10.1007/s11606-014-3112-6
[nam-burnout]: https://nam.edu/product/valid-and-reliable-survey-instruments-to-measure-burnout-well-being-and-other-work-related-dimensions/
[sibo-review]: https://pmc.ncbi.nlm.nih.gov/articles/PMC11043289/
[stretchly]: https://github.com/hovancik/stretchly
[activitywatch]: https://github.com/activitywatch/activitywatch
[viva]: https://support.microsoft.com/en-us/viva/insights/wellbeing-tab-in-viva-insights
[cortex]: https://www.cortex.io/post/engineering-intelligence-platforms-definition-benefits-tools
