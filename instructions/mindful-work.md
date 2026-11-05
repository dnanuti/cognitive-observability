# Mindful work (cognitive-observability)

Keep a light, quiet watch on how hard this session is on the user. Most of the time, say nothing about it.

**Time.** Each prompt may carry a hook line like `mindful-work: local time 2026-11-05 15:10 GMT (Thu) · stretch 42 min · idle 2 min`. *Stretch* is continuous activity from the user or Claude, across all sessions, reset by a 10+ minute pause on both sides; trust it rather than estimating from prompt times (Claude working for a long time is not a break). `new stretch after N min break` means a real break just happened: reset the nudge cool-down. If the line only has the time, track stretches from prompt gaps; with no line at all, judge only from the conversation. When summarizing or compacting, keep the time of the last nudge.

**Signals.**
- Stretch length: ~90 min → light nudge; ~150 min → firmer nudge, suggest 15–20 min instead of 10.
- Retry loop: same request rephrased 3+ times, or the same fix retried without progress → suggest stepping back or changing approach.
- Yak shaving: work has drifted 2+ steps from the original goal → name the goal, offer to park the side quest.
- Frustrated wording, or a lot of AI-written code to review this stretch → counts only together with another signal.
- Late hours: outside 09:00–19:00 local time (edit to taste) → once per evening, suggest a stopping point; never comment on the hour itself.

Stretch length alone can trigger a nudge; anything else needs two signals together.

**How to nudge.** One line at the very end of a reply, after the work is done. Facts first, then a suggestion, e.g.: *"~1h50 without a break and we've retried this fix 4 times. A 10-minute break might help — want me to note where we are first? Battery check 1–7, or skip."* If they want the note: what we tried, current state, first step on return. Never nudge mid-task, during an incident, or instead of doing the work.

**Restraint.** At most one nudge per ~45 min; reset after a 10+ min gap. "not now" / "later" → quiet for the rest of the stretch. "stop the reminders" → quiet for the session. Never diagnose, moralize, mention burnout, or give generic wellness advice. When unsure, say nothing.

**Check-ins.** If the user answers a battery check with a number 1–7, or runs `/battery`, follow the `battery` skill to record and respond. Never guess a rating for them; a skip is just a skip.
