#!/usr/bin/env python3
"""Analyze local Claude Code session history for workload, breaks and friction.

Reads ~/.claude/projects/**/*.jsonl (stdlib only, nothing leaves the machine)
and writes a self-contained HTML report. Prompt text is read only to compute
counts (length, frustration-word hits) and is never written to the output.

Daily history: --save-daily stores one numbers-only line per finished day in
~/.claude/mindful-work/daily.jsonl, so trends survive after Claude Code prunes
old transcripts (cleanupPeriodDays). Reports for longer --days windows fill
days without raw logs from that file; days in neither show as "no data".

Recovery and check-ins (SPEC-v3.md): the output also has a `recovery` block
(rest, late and long days per week against a 4-week personal baseline, work
streak, drift flags, recovery debt), `monthly_checks` parsed from
checkins.md, and `validation` (Spearman correlation between self-reports
and the recovery week before, after 8+ paired weeks). Counts only; no
composite score. --json writes all of it, also with --no-report.

Usage:
  python3 -I scripts/analyze_sessions.py [--days 30] [--out report.html]
        [--projects-dir ~/.claude/projects] [--json data.json]
        [--save-daily] [--no-report] [--history PATH]
"""
import os
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---- Thresholds: mirror instructions/mindful-work.md --------------------------
BREAK_GAP_MIN = 10        # gap between prompts that counts as a break
NUDGE_LIGHT_MIN = 90      # stretch length for a light nudge
NUDGE_FIRM_MIN = 150      # stretch length for a firm nudge
COOLDOWN_MIN = 45         # minimum time between nudges
PARALLEL_WINDOW_MIN = 15  # sessions active within this window count as parallel
WORK_START, WORK_END = 9, 18  # weekday working hours (local); weekends are always late
SHORT_PROMPT_CHARS = 40   # short follow-up prompt, proxy for corrections
RETRY_WINDOW_MIN = 15     # window for counting retry-loop evidence
RETRY_MIN_EVENTS = 3      # interrupts + short follow-ups in window => retry loop

FRUSTRATION = re.compile(
    r"\b(still (not|doesn'?t|broken|failing|wrong)|doesn'?t work|not working|"
    r"nothing works|why (is|does|isn'?t|doesn'?t)|again\?|wtf|ugh|argh|ffs|"
    r"broken again|come on|seriously|i give up|stuck)\b",
    re.IGNORECASE,
)
INTERRUPT_MARK = "Request interrupted by user"


def parse_ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone()
    except (AttributeError, ValueError):
        return None


def prompt_text(rec):
    """Return typed prompt text, or None if the record isn't a typed prompt."""
    if rec.get("isMeta"):
        return None
    c = rec.get("message", {}).get("content")
    if isinstance(c, str):
        if c.startswith("<") or c.startswith(f"[{INTERRUPT_MARK}"):
            return None
        return c
    if isinstance(c, list):
        types = {b.get("type") for b in c if isinstance(b, dict)}
        if "tool_result" in types:
            return None
        text = " ".join(b.get("text", "") for b in c
                        if isinstance(b, dict) and b.get("type") == "text")
        if not text or text.startswith(f"[{INTERRUPT_MARK}") or text.startswith("<"):
            return None
        return text
    return None


def is_interrupt(rec):
    c = rec.get("message", {}).get("content")
    if isinstance(c, str):
        return c.startswith(f"[{INTERRUPT_MARK}")
    if isinstance(c, list):
        return any(isinstance(b, dict) and b.get("type") == "text"
                   and b.get("text", "").startswith(f"[{INTERRUPT_MARK}") for b in c)
    return False


def project_name(path, cwd):
    if cwd:
        return Path(cwd).name or cwd
    return path.parent.name.rsplit("-", 1)[-1]


# ---- Load ----------------------------------------------------------------------
def load(projects_dir, since):
    """Return (events, subagent_counts). Events are dicts sorted by time."""
    events = []
    subagent_calls = Counter()  # session_id -> subagent assistant turns
    for path in Path(projects_dir).expanduser().rglob("*.jsonl"):
        is_sub = "subagents" in path.parts
        try:
            fh = path.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = rec.get("type")
                if t not in ("user", "assistant", "system"):
                    continue
                ts = parse_ts(rec.get("timestamp", ""))
                if ts is None or ts < since:
                    continue
                sid = rec.get("sessionId") or path.stem
                if is_sub or rec.get("isSidechain"):
                    if t == "assistant":
                        subagent_calls[sid] += 1
                    continue
                proj = project_name(path, rec.get("cwd"))
                base = {"ts": ts, "session": sid, "project": proj}
                if t == "system":
                    if rec.get("subtype") == "compact_boundary":
                        events.append({**base, "kind": "compact"})
                    continue
                if t == "user":
                    if is_interrupt(rec):
                        events.append({**base, "kind": "interrupt"})
                        continue
                    c = rec.get("message", {}).get("content")
                    if isinstance(c, list):
                        for b in c:
                            if (isinstance(b, dict) and b.get("type") == "tool_result"
                                    and b.get("is_error")):
                                events.append({**base, "kind": "tool_error"})
                    text = prompt_text(rec)
                    if text is not None:
                        events.append({**base, "kind": "prompt",
                                       "chars": len(text),
                                       "frustration": len(FRUSTRATION.findall(text))})
                    continue
                # assistant
                events.append({**base, "kind": "agent"})
                for b in rec.get("message", {}).get("content") or []:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    name, inp = b.get("name"), b.get("input") or {}
                    lines = 0
                    if name == "Edit":
                        lines = (inp.get("new_string") or "").count("\n") + 1
                    elif name == "Write":
                        lines = (inp.get("content") or "").count("\n") + 1
                    elif name == "MultiEdit":
                        lines = sum((e.get("new_string") or "").count("\n") + 1
                                    for e in inp.get("edits") or [])
                    if lines:
                        events.append({**base, "kind": "edit", "lines": lines})
                    elif name in ("Agent", "Task"):
                        events.append({**base, "kind": "subagent"})
    events.sort(key=lambda e: e["ts"])
    return events, subagent_calls


# ---- Analysis ------------------------------------------------------------------
def minutes(a, b):
    return (b - a).total_seconds() / 60


def is_late(ts):
    return ts.weekday() >= 5 or not (WORK_START <= ts.hour < WORK_END)


def build_stretches(acts):
    """Group user activity (prompts + interrupts) into stretches split by breaks."""
    stretches, cur = [], []
    for e in acts:
        if cur and minutes(cur[-1]["ts"], e["ts"]) >= BREAK_GAP_MIN:
            stretches.append(cur)
            cur = []
        cur.append(e)
    if cur:
        stretches.append(cur)
    return stretches


def active_minutes(acts):
    """Sum of gaps under BREAK_GAP_MIN, plus 2 min for the last action of a stretch."""
    total = 0.0
    for a, b in zip(acts, acts[1:]):
        g = minutes(a["ts"], b["ts"])
        total += g if g < BREAK_GAP_MIN else 2
    return total + (2 if acts else 0)


def mark_short_followups(events):
    """Flag short prompts sent soon after the previous event in the same session."""
    last_in_session = {}
    for e in events:
        if e["kind"] == "prompt":
            prev = last_in_session.get(e["session"])
            e["short_followup"] = bool(prev and e["chars"] <= SHORT_PROMPT_CHARS
                                       and minutes(prev, e["ts"]) <= 3)
        last_in_session[e["session"]] = e["ts"]


ENGAGED = ("prompt", "interrupt", "agent")  # activity from either side counts


def replay_nudges(events, light_min=NUDGE_LIGHT_MIN, engaged=True):
    """Replay the mindful-work rules over history. Returns a list of nudges.

    engaged=True: a break is 10+ min with no activity from you *or* Claude.
    engaged=False: only gaps between your prompts count (the watcher's view
    before the activity hooks existed; kept for comparison).
    """
    act_kinds = ENGAGED if engaged else ("prompt", "interrupt")
    nudges = []
    stretch_start = last_act = last_nudge = None
    window = []  # recent (ts, kind, weight) for retry/frustration evidence
    stretch_lines = 0
    late_nudged_day = None
    for e in events:
        ts = e["ts"]
        if e["kind"] == "edit":
            stretch_lines += e["lines"]
            continue
        if e["kind"] not in act_kinds:
            continue
        if last_act is None or minutes(last_act, ts) >= BREAK_GAP_MIN:
            stretch_start, last_nudge, stretch_lines, window = ts, None, 0, []
        last_act = ts
        if e["kind"] == "agent":
            continue
        if e["kind"] == "interrupt" or e.get("short_followup"):
            window.append((ts, "retry"))
        if e.get("frustration"):
            window.append((ts, "frustration"))
        window = [w for w in window if minutes(w[0], ts) <= RETRY_WINDOW_MIN]
        if e["kind"] != "prompt":
            continue
        if last_nudge and minutes(last_nudge, ts) < COOLDOWN_MIN:
            continue
        length = minutes(stretch_start, ts)
        retry = sum(1 for w in window if w[1] == "retry") >= RETRY_MIN_EVENTS
        signals = {
            "retry loop": retry,
            "frustration": any(w[1] == "frustration" for w in window),
            "review load": stretch_lines >= 300,
            "late hours": is_late(ts) and late_nudged_day != ts.date(),
        }
        active = [k for k, v in signals.items() if v]
        kind = None
        if length >= NUDGE_FIRM_MIN:
            kind = "firm"
        elif length >= light_min:
            kind = "light"
        elif len(active) >= 2:
            kind = "step back" if retry else "light"
        if kind:
            nudges.append({"ts": ts, "kind": kind, "stretch_min": round(length),
                           "signals": active, "session": e["session"]})
            last_nudge = ts
            if "late hours" in active or is_late(ts):
                late_nudged_day = ts.date()
    return nudges


def load_checkins(projects_dir, since):
    out = []
    pat = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d)\s*·\s*([\w-]+)\s*·\s*(\w+)")
    for p in Path(projects_dir).expanduser().glob("*/memory/checkins.md"):
        for line in p.read_text(errors="replace").splitlines():
            m = pat.match(line.strip())
            if not m or not m.group(3).isdigit():
                continue
            ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").astimezone()
            if ts >= since:
                out.append({"ts": ts, "instrument": m.group(2), "value": int(m.group(3))})
    return sorted(out, key=lambda c: c["ts"])


# ---- Daily history (numbers only, survives transcript cleanup) ---------------
HISTORY_VERSION = 1
NUDGE_KINDS = ("light", "firm", "step back")


def default_history_path():
    base = os.environ.get("MINDFUL_STATE_DIR") or "~/.claude/mindful-work"
    return Path(base).expanduser() / "daily.jsonl"


def load_history(path):
    """Return {date_iso: record}. Bad lines are skipped."""
    out = {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and isinstance(rec.get("date"), str):
            out[rec["date"]] = rec
    return out


def save_history(path, daily, raw_start):
    """Upsert finished days into the history file. Returns days written.

    Today is skipped (unfinished), as are days before the oldest raw log.
    A stored day is never replaced by one with fewer prompts, so a day whose
    transcripts were partly pruned can't overwrite a complete record.
    """
    today = datetime.now().astimezone().date().isoformat()
    hist = load_history(path)
    written = 0
    for d in daily:
        if d["source"] != "raw" or d["date"] >= today or d["date"] < raw_start:
            continue
        old = hist.get(d["date"])
        if old and old.get("prompts", 0) > d["prompts"]:
            continue
        rec = {k: v for k, v in d.items() if k not in ("source", "no_data")}
        rec["v"] = HISTORY_VERSION
        rec["thresholds"] = {"break_gap": BREAK_GAP_MIN, "light": NUDGE_LIGHT_MIN,
                             "firm": NUDGE_FIRM_MIN, "cooldown": COOLDOWN_MIN,
                             "work_start": WORK_START, "work_end": WORK_END}
        if rec != old:
            hist[d["date"]] = rec
            written += 1
    if written:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(hist[k], separators=(",", ":")) + "\n"
                               for k in sorted(hist)), encoding="utf-8")
        tmp.replace(path)
    return written


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0


# ---- Recovery layer (SPEC-v3.md section 3) ------------------------------------
REST_MAX_H = 0.5          # a known day under this many active hours is a rest day
LATE_DAY_PROMPTS = 3      # late prompts that make a late day
LONG_DAY_H = 8            # active hours that make a long day
LONG_STREAK_DAYS = 12     # work streak that raises a flag without a baseline
MIN_WEEK_DAYS = 5         # known days a week needs before it can raise a flag
MIN_BASELINE_DAYS = 14    # known days the 4 baseline weeks need
DEBT_WEEKS = 8            # weeks looked back for recovery debt
WEEK_METRICS = ("rest_days", "late_days", "long_days", "active_h")


def _true_median(xs):
    xs = sorted(xs)
    n = len(xs)
    return (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2) if xs else None


def _week_stats(by_date, end):
    """Stats for the 7 days ending on `end` (a date). Unknown days are skipped."""
    known = [by_date[d] for d in ((end - timedelta(days=i)).isoformat() for i in range(7))
             if d in by_date and not by_date[d].get("no_data")]
    return {"end": end.isoformat(), "known_days": len(known),
            "rest_days": sum(1 for d in known if d["active_h"] < REST_MAX_H),
            "late_days": sum(1 for d in known if d.get("late_prompts", 0) >= LATE_DAY_PROMPTS),
            "long_days": sum(1 for d in known if d["active_h"] >= LONG_DAY_H),
            "active_h": round(sum(d["active_h"] for d in known), 1)}


def _work_streak(by_date, end):
    n, d = 0, end
    while True:
        rec = by_date.get(d.isoformat())
        if not rec or rec.get("no_data") or rec["active_h"] < REST_MAX_H:
            return n
        n += 1
        d -= timedelta(days=1)


def _week_flags(by_date, end):
    week = _week_stats(by_date, end)
    base_weeks = [_week_stats(by_date, end - timedelta(days=7 * k)) for k in range(1, 5)]
    if sum(w["known_days"] for w in base_weeks) >= MIN_BASELINE_DAYS:
        baseline = {m: _true_median([w[m] for w in base_weeks]) for m in WEEK_METRICS}
    else:
        baseline = {m: None for m in WEEK_METRICS}
    streak = _work_streak(by_date, end)
    flags = []
    if week["known_days"] >= MIN_WEEK_DAYS and baseline["rest_days"] is not None:
        if week["rest_days"] <= 1 and week["rest_days"] <= baseline["rest_days"] - 1:
            flags.append("fewer_rest_days")
        if week["late_days"] >= baseline["late_days"] + 2:
            flags.append("more_late_days")
        if week["long_days"] >= baseline["long_days"] + 2:
            flags.append("more_long_days")
    if streak >= LONG_STREAK_DAYS:
        flags.append("long_streak")
    return week, baseline, streak, flags


def recovery_debt(flag_lists):
    """Consecutive flagged weeks, latest first, capped at DEBT_WEEKS."""
    n = 0
    for f in flag_lists[:DEBT_WEEKS]:
        if not f:
            break
        n += 1
    return n


def recovery(daily, last_day):
    """Recovery layer for the week ending on `last_day` (the last finished day).

    `daily` is a list of {"date", "no_data", "active_h", "late_prompts"}; days
    after `last_day` are ignored, missing days are unknown. Counts only: no
    composite score.
    """
    by_date = {d["date"]: d for d in daily if d["date"] <= last_day.isoformat()}
    week, baseline, streak, flags = _week_flags(by_date, last_day)
    weeks = []
    for k in range(DEBT_WEEKS):
        w, _, _, f = _week_flags(by_date, last_day - timedelta(days=7 * k))
        weeks.append({**w, "flags": f})
    return {"week": week, "baseline": baseline, "work_streak": streak, "flags": flags,
            "debt_weeks": recovery_debt([w["flags"] for w in weeks]), "weeks": weeks,
            "thresholds": {"rest_max_h": REST_MAX_H, "late_day_prompts": LATE_DAY_PROMPTS,
                           "long_day_h": LONG_DAY_H, "long_streak_days": LONG_STREAK_DAYS}}


# ---- Monthly check and personal validation (SPEC-v3.md sections 4-5) ---------
EXHAUSTION_KEYS = ("bo1", "bo2", "bo3", "bo4")
CAUSE_KEYS = ("qd2", "in3", "re1", "sc1", "ju4", "mw1", "wf2")
DEMAND_KEYS = ("qd2", "wf2")   # high = worse; the other cause items are resources
CHECK_BLOCK_MIN = 60           # lines within this many minutes form one check
MIN_PAIRED_WEEKS = 8


def monthly_checks(checkins):
    """Group monthly-check lines into checks with an exhaustion score (0-100)."""
    lines = sorted((c for c in checkins
                    if c["instrument"] in EXHAUSTION_KEYS + CAUSE_KEYS), key=lambda c: c["ts"])
    blocks = []
    for c in lines:
        if blocks and minutes(blocks[-1][-1]["ts"], c["ts"]) <= CHECK_BLOCK_MIN:
            blocks[-1].append(c)
        else:
            blocks.append([c])
    out = []
    for b in blocks:
        bo = [c["value"] for c in b if c["instrument"] in EXHAUSTION_KEYS]
        out.append({"ts": b[0]["ts"], "answered": len(bo),
                    "exhaustion": round(sum(bo) / len(bo), 1) if len(bo) >= 3 else None,
                    "causes": {c["instrument"]: c["value"] for c in b
                               if c["instrument"] in CAUSE_KEYS}})
    return out


def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(xs, ys):
    """Spearman rank correlation (Pearson on ranks, ties averaged); None if undefined."""
    if len(xs) < 2:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if not sxx or not syy:
        return None
    return round(sxy / (sxx * syy) ** 0.5, 3)


def validation(daily, checkins):
    """Pair each self-report with the recovery week before it (SPEC-v3 R-10).

    Self-reports: weekly burnout item (1-5) and monthly exhaustion score.
    The paired week is the 7 days ending the day before the report; weeks
    with fewer than MIN_WEEK_DAYS known days are not paired.
    """
    by_date = {d["date"]: d for d in daily}
    reports = {
        "burnout": [(c["ts"], c["value"]) for c in checkins if c["instrument"] == "burnout"],
        "exhaustion": [(m["ts"], m["exhaustion"]) for m in monthly_checks(checkins)
                       if m["exhaustion"] is not None],
    }
    out = {}
    for name, rs in reports.items():
        pairs = []
        for ts, v in rs:
            w = _week_stats(by_date, ts.date() - timedelta(days=1))
            if w["known_days"] >= MIN_WEEK_DAYS:
                pairs.append((w, v))
        n = len(pairs)
        rho = None
        if n >= MIN_PAIRED_WEEKS:
            ys = [v for _, v in pairs]
            rho = {m: spearman([w[m] for w, _ in pairs], ys) for m in WEEK_METRICS}
        out[name] = {"n": n, "rho": rho}
    out["min_pairs"] = MIN_PAIRED_WEEKS
    return out


def summarize(events, subagent_calls, checkins, days, since, history=None):
    mark_short_followups(events)
    acts = [e for e in events if e["kind"] in ("prompt", "interrupt")]
    prompts = [e for e in acts if e["kind"] == "prompt"]
    engaged = [e for e in events if e["kind"] in ENGAGED]
    stretches = build_stretches(engaged)
    prompt_only_lengths = sorted(round(minutes(s[0]["ts"], s[-1]["ts"]))
                                 for s in build_stretches(acts))
    nudges = replay_nudges(events)

    # Parallel sessions at each prompt
    recent = []  # (ts, session)
    for e in acts:
        recent = [r for r in recent if minutes(r[0], e["ts"]) <= PARALLEL_WINDOW_MIN]
        recent.append((e["ts"], e["session"]))
        e["parallel"] = len({s for _, s in recent})

    # Per-day aggregates
    today = datetime.now().astimezone().date()
    day_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    raw_start = events[0]["ts"].date() if events else today
    history = history or {}
    stretch_by_day = defaultdict(list)
    for st in stretches:
        stretch_by_day[st[0]["ts"].date()].append(round(minutes(st[0]["ts"], st[-1]["ts"])))
    by_day = {d: [] for d in day_list}
    for e in events:
        if e["ts"].date() in by_day:
            by_day[e["ts"].date()].append(e)
    daily = []
    for d in day_list:
        if d < raw_start:
            rec = history.get(d.isoformat())
            if rec:
                daily.append({**{k: v for k, v in rec.items() if k not in ("v", "thresholds")},
                              "source": "history", "no_data": False})
            else:
                daily.append({"date": d.isoformat(), "weekday": d.strftime("%a"),
                              "source": "none", "no_data": True, "active_h": 0,
                              "span_start": None, "span_end": None, "prompts": 0,
                              "late_prompts": 0, "interrupts": 0, "tool_errors": 0,
                              "short_followups": 0, "frustration": 0, "lines_edited": 0,
                              "subagents": 0, "sessions": 0, "max_parallel": 0,
                              "nudges": 0, "nudges_firm": 0,
                              "nudges_kind": {k: 0 for k in NUDGE_KINDS},
                              "stretch_min": [], "prompts_by_hour": [0] * 24})
            continue
        ev = by_day[d]
        da = [e for e in ev if e["kind"] in ENGAGED]
        dp = [e for e in da if e["kind"] == "prompt"]
        dn = [n for n in nudges if n["ts"].date() == d]
        daily.append({
            "date": d.isoformat(),
            "weekday": d.strftime("%a"),
            "active_h": round(active_minutes(da) / 60, 2) if da else 0,
            "span_start": da[0]["ts"].strftime("%H:%M") if da else None,
            "span_end": da[-1]["ts"].strftime("%H:%M") if da else None,
            "prompts": len(dp),
            "late_prompts": sum(1 for e in dp if is_late(e["ts"])),
            "interrupts": sum(1 for e in ev if e["kind"] == "interrupt"),
            "tool_errors": sum(1 for e in ev if e["kind"] == "tool_error"),
            "short_followups": sum(1 for e in dp if e.get("short_followup")),
            "frustration": sum(e.get("frustration", 0) for e in dp),
            "lines_edited": sum(e["lines"] for e in ev if e["kind"] == "edit"),
            "subagents": sum(1 for e in ev if e["kind"] == "subagent"),
            "sessions": len({e["session"] for e in dp}),
            "max_parallel": max((e.get("parallel", 0) for e in dp), default=0),
            "nudges": len(dn),
            "nudges_firm": sum(1 for n in dn if n["kind"] == "firm"),
            "nudges_kind": {k: sum(1 for n in dn if n["kind"] == k) for k in NUDGE_KINDS},
            "stretch_min": stretch_by_day.get(d, []),
            "prompts_by_hour": [sum(1 for e in dp if e["ts"].hour == h) for h in range(24)],
            "source": "raw", "no_data": False,
        })

    # Heatmap weekday x hour (prompts)
    heat = [[0] * 24 for _ in range(7)]
    for e in prompts:
        heat[e["ts"].weekday()][e["ts"].hour] += 1
    for d in daily:
        if d["source"] == "history":
            wd = datetime.fromisoformat(d["date"]).weekday()
            for h, c in enumerate(d.get("prompts_by_hour") or []):
                heat[wd][h] += c

    # Friction by hour of day
    by_hour = defaultdict(lambda: {"prompts": 0, "interrupts": 0, "tool_errors": 0,
                                   "short_followups": 0})
    for e in events:
        h = by_hour[e["ts"].hour]
        if e["kind"] == "prompt":
            h["prompts"] += 1
            h["short_followups"] += int(e.get("short_followup", False))
        elif e["kind"] == "interrupt":
            h["interrupts"] += 1
        elif e["kind"] == "tool_error":
            h["tool_errors"] += 1
    friction_hour = [{"hour": h, **by_hour[h]} for h in range(24) if by_hour[h]["prompts"]]

    # Stretch list (+ prompt length by minutes into stretch)
    stretch_rows = []
    pos_buckets = [(0, 30), (30, 60), (60, 90), (90, 150), (150, 10**6)]
    pos_chars = defaultdict(list)
    for s in stretches:
        start, end = s[0]["ts"], s[-1]["ts"]
        stretch_rows.append({
            "start": start.isoformat(), "end": end.isoformat(),
            "minutes": round(minutes(start, end)),
            "prompts": sum(1 for e in s if e["kind"] == "prompt"),
            "sessions": len({e["session"] for e in s}),
            "projects": sorted({e["project"] for e in s}),
        })
        for e in s:
            if e["kind"] == "prompt":
                m = minutes(start, e["ts"])
                for lo, hi in pos_buckets:
                    if lo <= m < hi:
                        pos_chars[f"{lo}-{hi if hi < 10**6 else ''}"].append(e["chars"])

    prompt_len_by_pos = [{"bucket": (k[:-1] + "+" if k.endswith("-") else k) + " min",
                          "median_chars": median(v), "n": len(v)}
                         for k, v in pos_chars.items()]

    # Session segments per day for the timeline
    seg = defaultdict(list)
    for e in engaged:
        seg[e["session"]].append(e)
    segments = []
    for sid, sacts in seg.items():
        for s in build_stretches(sacts):
            segments.append({"session": sid[:8], "project": s[0]["project"],
                             "start": s[0]["ts"].isoformat(),
                             "end": (s[-1]["ts"] + timedelta(minutes=2)).isoformat()})

    # Threshold sensitivity
    active_days = sum(1 for d in daily if d["prompts"]) or 1
    sensitivity = []
    for thr in (45, 60, 75, 90, 120, 150):
        n = replay_nudges(events, light_min=thr)
        p = replay_nudges(events, light_min=thr, engaged=False)
        sensitivity.append({"light_min": thr, "nudges": len(n),
                            "per_active_day": round(len(n) / active_days, 2),
                            "nudges_prompt_only": len(p)})

    parallel_dist = Counter(e["parallel"] for e in prompts)
    projects = Counter(e["project"] for e in prompts)
    hist_stretches = [{"minutes": m} for d in daily if d["source"] == "history"
                      for m in d.get("stretch_min") or []]
    lengths = sorted(r["minutes"] for r in stretch_rows + hist_stretches)
    with_data = [d for d in daily if not d["no_data"]]
    total_prompts = sum(d["prompts"] for d in with_data)

    return {
        "generated": datetime.now().astimezone().isoformat(timespec="minutes"),
        "since": since.date().isoformat(),
        "days": days,
        "coverage": {"raw_from": raw_start.isoformat(),
                     "raw_days": sum(1 for d in daily if d["source"] == "raw"),
                     "history_days": sum(1 for d in daily if d["source"] == "history"),
                     "no_data_days": sum(1 for d in daily if d["no_data"])},
        "thresholds": {"break_gap": BREAK_GAP_MIN, "light": NUDGE_LIGHT_MIN,
                       "firm": NUDGE_FIRM_MIN, "cooldown": COOLDOWN_MIN,
                       "work_start": WORK_START, "work_end": WORK_END},
        "totals": {
            "prompts": total_prompts,
            "sessions": len({e["session"] for e in acts}),
            "active_days": sum(1 for d in with_data if d["prompts"]),
            "zero_days": sum(1 for d in with_data if not d["prompts"]),
            "active_h": round(sum(d["active_h"] for d in daily), 1),
            "late_share": round(sum(d["late_prompts"] for d in daily) / max(total_prompts, 1), 3),
            "interrupts": sum(d["interrupts"] for d in daily),
            "tool_errors": sum(d["tool_errors"] for d in daily),
            "lines_edited": sum(d["lines_edited"] for d in daily),
            "subagent_turns": sum(subagent_calls.values()),
            "compactions": sum(1 for e in events if e["kind"] == "compact"),
            "nudges": sum(d["nudges"] for d in daily),
            "stretches_over_light": sum(1 for x in lengths if x >= NUDGE_LIGHT_MIN),
            "stretches_over_firm": sum(1 for x in lengths if x >= NUDGE_FIRM_MIN),
            "longest_stretch": lengths[-1] if lengths else 0,
            "median_stretch": median(lengths),
            "prompt_only_longest": prompt_only_lengths[-1] if prompt_only_lengths else 0,
            "prompt_only_median": median(prompt_only_lengths),
        },
        "daily": daily,
        "heatmap": heat,
        "friction_hour": friction_hour,
        "stretches": stretch_rows + hist_stretches,
        "prompt_len_by_pos": prompt_len_by_pos,
        "segments": segments,
        "nudges": [{**n, "ts": n["ts"].isoformat()} for n in nudges],
        "sensitivity": sensitivity,
        "parallel_dist": sorted(parallel_dist.items()),
        "projects": projects.most_common(),
        "checkins": [{**c, "ts": c["ts"].isoformat()} for c in checkins],
        "recovery": recovery(daily, today - timedelta(days=1)),
        "monthly_checks": [{**m, "ts": m["ts"].isoformat()} for m in monthly_checks(checkins)],
        "validation": validation(daily, checkins),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--projects-dir", default="~/.claude/projects")
    ap.add_argument("--out", default="session-report.html")
    ap.add_argument("--json", help="also write the aggregated data as JSON")
    ap.add_argument("--history", default=str(default_history_path()),
                    help="daily history file (default ~/.claude/mindful-work/daily.jsonl)")
    ap.add_argument("--save-daily", action="store_true",
                    help="store finished days from raw logs in the history file")
    ap.add_argument("--no-report", action="store_true", help="skip writing the HTML report")
    args = ap.parse_args()
    since = datetime.now().astimezone().replace(hour=0, minute=0, second=0,
                                                microsecond=0) - timedelta(days=args.days - 1)
    events, subs = load(args.projects_dir, since)
    history = load_history(args.history)
    if not events and not any(k >= since.date().isoformat() for k in history):
        sys.exit(f"No session activity found in {args.projects_dir} since {since.date()}")
    data = summarize(events, subs, load_checkins(args.projects_dir, since), args.days, since,
                     history)
    if args.save_daily:
        # If the oldest raw day isn't the window start, its transcripts may be
        # partly pruned already, so don't store it.
        raw_from = data["coverage"]["raw_from"]
        if raw_from > since.date().isoformat():
            raw_from = (datetime.fromisoformat(raw_from) + timedelta(days=1)).date().isoformat()
        n = save_history(args.history, data["daily"], raw_from)
        print(f"{args.history}: {n} day(s) saved")
    if args.json:
        Path(args.json).write_text(json.dumps(data, indent=1))
    if args.no_report:
        return
    here = Path(__file__).parent
    template = (here / "report_template.html").read_text()
    js = (here / "report.js").read_text()
    html = (template
            .replace('<script src="report.js"></script>', "<script>\n" + js + "\n</script>")
            .replace("/*__DATA__*/null", json.dumps(data).replace("</", "<\\/")))
    Path(args.out).write_text(html)
    t = data["totals"]
    print(f"{args.out}: {t['prompts']} prompts, {t['sessions']} sessions, "
          f"{t['active_h']}h active, {t['nudges']} replayed nudges")


if __name__ == "__main__":
    main()
