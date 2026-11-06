# cognitive-observability

Bringing observability to human cognition: detect patterns in prompting behavior to surface overload, friction, and early burnout signals.

A lightweight way for Claude Code to notice when AI-assisted work is wearing you down and suggest a break: no extra apps, no background processes, nothing leaves your machine. See [SPEC.md](SPEC.md) for the design and research behind it.

## What's included

| Piece | File | What it does |
|---|---|---|
| Mindful-work instructions | `instructions/mindful-work.md` | Always-on guidance: watch for long stretches, retry loops, yak shaving, late hours; nudge in one line at most every ~45 min |
| Timing hook | `hooks/mindful-time.sh`, wired in `.claude/settings.json` | Records activity from you (prompts) and Claude (tool use, finished replies), and adds the local time, current stretch and idle time to each prompt. Claude working for a long time doesn't count as a break |
| `/battery` | `.claude/skills/battery/` | Optional self-reported energy check (Samn-Perelli fatigue scale, NASA-TLX follow-up) |
| `/observe` | `.claude/skills/observe/` | On-demand reflection; `/observe 7d` gives a weekly view from git history and your check-ins, plus an optional weekly burnout question |

## Use it in this repo

Open Claude Code in this repo. `CLAUDE.md`, the hook and both skills load automatically. You may be asked to approve the project hook the first time.

## Use it everywhere

Install user-level so it applies to every project (the recommended setup). To turn the watcher off in one repo, add a line `mindful-work: off` to that repo's `CLAUDE.md`; `/battery` still works there.

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
3. **Hooks:** copy the script, then merge the `hooks` block from `.claude/settings.json` into `~/.claude/settings.json`, replacing `$CLAUDE_PROJECT_DIR/hooks/` with `$HOME/.claude/hooks/`. If you already have hooks, add the three entries (`UserPromptSubmit`, `PostToolUse`, `Stop`) rather than replacing the file.
   ```bash
   mkdir -p ~/.claude/hooks && cp hooks/mindful-time.sh ~/.claude/hooks/
   ```
   The hook keeps two timestamps in `~/.claude/mindful-work/` (no prompt text). Set `MINDFUL_BREAK_MIN` to change the 10-minute break threshold.

To change working hours or thresholds, edit `mindful-work.md`.

## Session history report

`scripts/analyze_sessions.py` reads your local Claude Code history (`~/.claude/projects/`) and writes a self-contained HTML report with charts: workload, breaks and stretches, friction, AI review load, a replay of the nudge rules over past sessions, and your check-ins. Python standard library only, nothing to install, nothing leaves your machine. Prompt text is read only to count things and is never written to the report.

```bash
python3 -I scripts/analyze_sessions.py --days 30 --out session-report.html
open session-report.html
```

Claude Code deletes transcripts after `cleanupPeriodDays` (30 by default). To keep long-range trends without keeping transcripts, the prompt hook runs `analyze_sessions.py --save-daily` once a day in the background. It saves one line per finished day to `~/.claude/mindful-work/daily.jsonl`, holding only counts: active hours, prompts, late prompts, stretch lengths, friction counts, replayed nudges, and prompts per hour. No text is saved. Reports with a longer `--days` window fill in older days from that file and show days in neither source as "no data", not "no activity". Set `MINDFUL_DAILY=0` to turn this off, or run it by hand:

```bash
python3 -I scripts/analyze_sessions.py --days 30 --save-daily --no-report   # backfill from current logs
python3 -I scripts/analyze_sessions.py --days 180 --out session-report.html # long view
```

The day timeline, friction-by-hour, prompt-length and threshold-sensitivity charts need raw logs, so they only cover the days still on disk. Each saved day records the thresholds that were in force. Stretch minutes are stored raw so stretch counts can be recomputed if thresholds change, but saved nudge counts can't be.

The thresholds at the top of the script mirror `instructions/mindful-work.md`; change both together.

## Demo report (synthetic data)

[`examples/report-synthetic.html`](examples/report-synthetic.html) is a full report built from **invented** data, for presentations. You don't need a session history to see it. It covers 30 days across four generic projects (Project A–D), with no real prompts, names or paths:

- **Low-effort week** (Mon 12 Oct): short mornings, Friday off, no nudges, battery ratings around 2.
- **High-effort week** (Mon 26 Oct): 8–10 h days into the late evening, a Saturday catch-up, two or three parallel sessions, retry loops and frustrated wording, heavy AI edit volume, Claude running alone for long stretches. Nudges cluster here, battery ratings climb to 6 and the weekly burnout item reaches 3.
- Normal weeks before and after, so the contrast is visible.

To rebuild it (`--end` sets the last day; the seed keeps it reproducible):

```bash
python3 -I scripts/make_synthetic.py --end 2026-11-06
python3 -I scripts/analyze_sessions.py --projects-dir examples/synthetic/projects \
  --history examples/synthetic/no-history.jsonl --out examples/report-synthetic.html
```

The raw synthetic transcripts are in `examples/synthetic/projects/`, in the same JSONL shape Claude Code writes. The analyzer reads them like real logs.

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
