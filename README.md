# cognitive-observability

Bringing observability to human cognition: detect patterns in prompting behavior to surface overload, friction, and early burnout signals.

A lightweight way for Claude Code to notice when AI-assisted work is wearing you down and suggest a break: no extra apps, no background processes, nothing leaves your machine. See [SPEC.md](SPEC.md) for the design and research behind it.

## What's included

| Piece | File | What it does |
|---|---|---|
| Mindful-work instructions | `instructions/mindful-work.md` | Always-on guidance: watch for long stretches, retry loops, yak shaving, late hours; nudge in one line at most every ~45 min |
| Timestamp hook | `.claude/settings.json` | Adds the local time to each prompt, so Claude can tell how long you've been going |
| `/battery` | `.claude/skills/battery/` | Optional self-reported energy check (Samn-Perelli fatigue scale, NASA-TLX follow-up) |
| `/observe` | `.claude/skills/observe/` | On-demand reflection; `/observe 7d` gives a weekly view from git history and your check-ins, plus an optional weekly burnout question |

## Use it in this repo

Open Claude Code in this repo. `CLAUDE.md`, the hook and both skills load automatically. You may be asked to approve the project hook the first time.

## Use it everywhere

Install user-level so it applies to every project:

1. **Skills:** copy both skill folders.
   ```bash
   mkdir -p ~/.claude/skills
   cp -R .claude/skills/observe .claude/skills/battery ~/.claude/skills/
   ```
2. **Instructions:** copy the instructions file and import it from your user `CLAUDE.md`.
   ```bash
   cp instructions/mindful-work.md ~/.claude/mindful-work.md
   echo '@mindful-work.md' >> ~/.claude/CLAUDE.md
   ```
3. **Hook:** merge the `hooks` block from `.claude/settings.json` into `~/.claude/settings.json`. If you already have hooks, add the `UserPromptSubmit` entry rather than replacing the file.

To change working hours or thresholds, edit `mindful-work.md`.

## Commands

| Command | What happens |
|---|---|
| `/battery` or `/battery 4` | Log how you feel (1 fully alert … 7 completely exhausted); Claude adjusts |
| `/observe` | Reflect on the current session |
| `/observe 7d` | Weekly view: git patterns, your check-ins, optional burnout question |
| "not now" / "stop the reminders" | Quiet for this stretch / this session |

## Privacy

Everything stays local. Check-ins and snapshots are stored in Claude's per-project memory folder (`~/.claude/projects/<project>/memory/`) with no prompt text. There's no team or manager view.

## Limits

It only sees the current Claude session: not parallel sessions, not work outside Claude, not breaks away from the keyboard. Detection is Claude's judgment, not a measurement, and nothing here diagnoses burnout.
