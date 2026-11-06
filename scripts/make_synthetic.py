#!/usr/bin/env python3
"""Generate 30 days of synthetic Claude Code session logs for demos.

Writes transcripts in the same JSONL shape Claude Code uses, so the real
analyzer can turn them into a report. Everything is invented: project names
are generic ("Project A".."Project D") and prompt text is placeholder wording.

The month has a shape worth presenting:
  first days  normal
  week 1      low effort (short days, Friday off)
  week 2      normal
  week 3      high effort (long stretches, late evenings, Saturday work,
              parallel sessions, retry loops, heavy AI review load)
  rest        recovery / normal

Usage:
  python3 -I scripts/make_synthetic.py [--out examples/synthetic] [--end 2026-11-06] [--seed 7]
  python3 -I scripts/analyze_sessions.py --projects-dir examples/synthetic/projects \\
      --history examples/synthetic/no-history.jsonl --out examples/report.html
"""
import argparse
import json
import random
import shutil
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECTS = ["Project A", "Project B", "Project C", "Project D"]

PROMPTS = [
    "Add input validation to the request handler and cover it with tests",
    "Refactor the service layer so the repository is injected instead of created",
    "Explain why this test is flaky and suggest a fix",
    "Write a migration that adds the new status column with a default",
    "Review the diff for edge cases before I open the pull request",
    "Rename the config option and update every place that reads it",
    "Split this module into smaller files without changing behaviour",
    "Add structured logging around the retry logic",
    "Draft the README section for the new command",
    "Find where the timeout is set and make it configurable",
    "Summarise what changed on this branch since main",
    "Add a unit test for the empty-list case",
]
FOLLOWUPS = ["yes, go ahead", "looks good", "run the tests", "commit that",
             "now the other file", "ok, next step", "use the existing helper"]
RETRIES = ["no, try again", "still not working", "that broke the build",
           "revert that", "not that file", "why is this still failing?"]
FRUSTRATED = ["ugh, still broken. why does this keep failing?",
              "seriously, nothing works after that change",
              "this is broken again, I'm stuck"]


class Day:
    def __init__(self, rng, d):
        self.rng, self.d = rng, d
        self.sessions = {}  # (project) -> (session_id, records)

    def at(self, hh, mm=0):
        return datetime(self.d.year, self.d.month, self.d.day, hh, mm).astimezone()

    def session(self, project):
        if project not in self.sessions:
            self.sessions[project] = (str(uuid.UUID(int=self.rng.getrandbits(128))), [])
        return self.sessions[project]

    def rec(self, project, t, kind, **extra):
        sid, recs = self.session(project)
        r = {"type": kind, "timestamp": t.isoformat(timespec="seconds"),
             "sessionId": sid, "cwd": f"/work/{project}"}
        r.update(extra)
        recs.append(r)

    def stretch(self, project, start, minutes, mode="normal"):
        """One continuous stretch: prompts, Claude working in between, edits."""
        rng = self.rng
        t, end = start, start + timedelta(minutes=minutes)
        gap = {"low": (3, 9), "normal": (2, 7), "high": (2, 6)}[mode]
        edit = {"low": (2, 12), "normal": (3, 20), "high": (10, 70)}[mode]
        p_edit = {"low": 0.25, "normal": 0.3, "high": 0.55}[mode]
        p_retry = {"low": 0.0, "normal": 0.012, "high": 0.1}[mode]
        p_err = {"low": 0.03, "normal": 0.06, "high": 0.15}[mode]
        first = True
        while t < end:
            if not first and rng.random() < p_retry:
                self.retry_burst(project, t, mode)
                t += timedelta(minutes=rng.randint(8, 14))
                continue
            text = rng.choice(PROMPTS) if first or rng.random() < 0.55 else rng.choice(FOLLOWUPS)
            first = False
            self.rec(project, t, "user", message={"role": "user", "content": text})
            # Claude works for a while: several assistant turns, maybe edits/errors
            work = rng.randint(1, gap[1])
            for k in range(work):
                ta = t + timedelta(seconds=40 + k * rng.randint(40, 70))
                content = [{"type": "text", "text": "Working on it."}]
                if rng.random() < p_edit:
                    n = rng.randint(*edit)
                    content.append({"type": "tool_use", "name": "Edit",
                                    "input": {"new_string": "\n" * (n - 1)}})
                elif mode != "low" and rng.random() < 0.05:
                    content.append({"type": "tool_use", "name": "Agent", "input": {}})
                self.rec(project, ta, "assistant", message={"role": "assistant", "content": content})
                if rng.random() < p_err:
                    self.rec(project, ta + timedelta(seconds=5), "user", message={
                        "role": "user", "content": [{"type": "tool_result", "is_error": True,
                                                     "content": "command failed"}]})
            t += timedelta(minutes=rng.randint(*gap), seconds=rng.randint(0, 59))
            if mode == "high" and rng.random() < 0.04:
                # Claude runs alone for 12-20 min: no prompts, but not a break
                for k in range(rng.randint(12, 20)):
                    t += timedelta(minutes=1)
                    self.rec(project, t, "assistant", message={"role": "assistant",
                             "content": [{"type": "text", "text": "Still running the suite."}]})
        if mode == "high" and minutes > 150 and rng.random() < 0.6:
            self.rec(project, end, "system", subtype="compact_boundary")

    def retry_burst(self, project, t, mode):
        """Interrupts and short corrections close together: a retry loop."""
        rng = self.rng
        for i in range(rng.randint(3, 5)):
            t += timedelta(seconds=rng.randint(50, 150))
            self.rec(project, t, "assistant", message={"role": "assistant",
                     "content": [{"type": "text", "text": "Trying another fix."}]})
            if rng.random() < 0.4:
                self.rec(project, t + timedelta(seconds=20), "user", message={
                    "role": "user", "content": "[Request interrupted by user]"})
            text = (rng.choice(FRUSTRATED) if mode == "high" and i == 2 and rng.random() < 0.7
                    else rng.choice(RETRIES))
            self.rec(project, t + timedelta(seconds=35), "user",
                     message={"role": "user", "content": text})

    def write(self, root):
        for project, (sid, recs) in self.sessions.items():
            d = root / "projects" / ("-work-" + project.replace(" ", "-"))
            d.mkdir(parents=True, exist_ok=True)
            recs.sort(key=lambda r: r["timestamp"])
            with (d / f"{sid}.jsonl").open("w", encoding="utf-8") as fh:
                for r in recs:
                    fh.write(json.dumps(r, separators=(",", ":")) + "\n")


def plan_day(day, phase):
    """Lay out the stretches for one day according to the week's phase."""
    rng, wd = day.rng, day.d.weekday()
    j = lambda a, b: rng.randint(a, b)  # noqa: E731
    if phase == "low":
        if wd >= 4:
            return  # Friday and weekend off
        day.stretch("Project A", day.at(9, j(40, 59)), j(30, 55), "low")
        if rng.random() < 0.7:
            day.stretch("Project B", day.at(14, j(0, 40)), j(25, 50), "low")
        return
    if phase == "high":
        if wd == 6:
            return  # Sunday off, finally
        if wd == 5:  # Saturday catch-up
            day.stretch("Project C", day.at(10, j(0, 30)), j(110, 150), "high")
            day.stretch("Project C", day.at(15, j(0, 30)), j(90, 130), "high")
            return
        day.stretch("Project C", day.at(8, j(10, 30)), j(150, 200), "high")
        # a second session running in parallel on another project
        day.stretch("Project D", day.at(9, j(30, 50)), j(60, 100), "high")
        day.stretch("Project C", day.at(12, j(30, 50)), j(160, 210), "high")
        if wd in (1, 3):
            day.stretch("Project A", day.at(14, j(0, 30)), j(45, 70), "high")
        if wd == 3:  # three sessions at once
            day.stretch("Project D", day.at(14, j(10, 30)), j(40, 60), "high")
        day.stretch("Project C", day.at(18, j(40, 59)), j(110, 160), "high")
        if wd in (2, 3):  # past 22:00 on the worst two days
            day.stretch("Project C", day.at(21, j(55, 59)), j(40, 70), "high")
        return
    # normal and recovery weeks
    if wd >= 5:
        if wd == 6 and rng.random() < 0.3:
            day.stretch("Project D", day.at(11, j(0, 30)), j(25, 45), "low")
        return
    lead = "Project B" if phase == "recovery" else rng.choice(["Project A", "Project B"])
    day.stretch(lead, day.at(9, j(15, 40)), j(70, 100), "normal")
    day.stretch(rng.choice(PROJECTS[:3]), day.at(11, j(30, 55)), j(45, 75), "normal")
    day.stretch(lead, day.at(14, j(0, 25)), j(80, 115), "normal")
    if rng.random() < 0.5:
        day.stretch(rng.choice(PROJECTS), day.at(16, j(30, 50)), j(30, 55), "normal")


def phase_for(d, start):
    week = (d - start).days // 7
    return {0: "low", 1: "normal", 2: "high"}.get(week, "recovery")


CHECKINS = {  # (days after start, HH:MM, instrument, value, source)
    "normal": [("samn-perelli", 3)], "low": [("samn-perelli", 2)],
    "high": [("samn-perelli", 5), ("tlx-mental", 8), ("tlx-frustration", 7)],
    "recovery": [("samn-perelli", 3)],
}


def write_checkins(root, days, start, rng):
    lines = ["# Mindful-work check-ins (synthetic)", "",
             "Format: `YYYY-MM-DD HH:MM · instrument · answer · source`", ""]
    burnout = {0: 1, 1: 2, 2: 3, 3: 2}
    for d in days:
        ph = phase_for(d, start)
        if d.weekday() >= 5 and ph != "high":
            continue
        if rng.random() < 0.6:
            for inst, v in CHECKINS[ph]:
                if inst != "samn-perelli" and rng.random() < 0.5:
                    continue
                v = max(1, min(7 if inst == "samn-perelli" else 10, v + rng.choice([-1, 0, 0, 1])))
                if ph == "high" and inst == "samn-perelli" and d.weekday() >= 2:
                    v = max(v, 6)
                hh = (rng.choice(["10:20", "14:40"]) if ph == "low"
                      else "15:10" if d.weekday() == 5
                      else rng.choice(["11:40", "15:10", "21:20"]) if ph == "high"
                      else rng.choice(["11:40", "15:10"]))
                lines.append(f"{d} {hh} · {inst} · {v} · nudge")
        if d.weekday() == 4:  # weekly, during /observe 7d
            w = (d - start).days // 7
            lines.append(f"{d} 17:30 · burnout · {burnout.get(w, 2)} · observe")
    mem = root / "projects" / "-work-Project-A" / "memory"
    mem.mkdir(parents=True, exist_ok=True)
    (mem / "checkins.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="examples/synthetic")
    ap.add_argument("--end", default=date.today().isoformat(), help="last day (YYYY-MM-DD)")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    end = date.fromisoformat(args.end)
    first = end - timedelta(days=args.days - 1)
    start = first + timedelta(days=(7 - first.weekday()) % 7)  # weeks begin on Monday
    root = Path(args.out)
    if (root / "projects").exists():
        shutil.rmtree(root / "projects")
    days = [first + timedelta(days=i) for i in range(args.days)]
    for d in days:
        day = Day(rng, d)
        plan_day(day, phase_for(d, start) if d >= start else "normal")
        day.write(root)
    write_checkins(root, [d for d in days if d >= start], start, rng)
    print(f"{root}: {args.days} days ({first} to {end}); "
          f"low week {start}, high week {start + timedelta(14)}")


if __name__ == "__main__":
    main()
