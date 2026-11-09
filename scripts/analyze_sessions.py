#!/usr/bin/env python3
"""Analyze local Claude Code session history for workload, breaks and friction.

Reads ~/.claude/projects/**/*.jsonl (stdlib only, nothing leaves the machine)
and writes a self-contained HTML report. Prompt text is read only to compute
counts (length, frustration-word hits) and is never written to the output.

Usage:
  python3 -I scripts/analyze_sessions.py [--days 30] [--out report.html]
        [--projects-dir ~/.claude/projects] [--json data.json]
"""
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
WORK_START, WORK_END = 9, 19  # working hours (local), late = outside
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


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0


def summarize(events, subagent_calls, checkins, days, since):
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
    by_day = {d: [] for d in day_list}
    for e in events:
        if e["ts"].date() in by_day:
            by_day[e["ts"].date()].append(e)
    daily = []
    for d in day_list:
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
        })

    # Heatmap weekday x hour (prompts)
    heat = [[0] * 24 for _ in range(7)]
    for e in prompts:
        heat[e["ts"].weekday()][e["ts"].hour] += 1

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
    lengths = sorted(r["minutes"] for r in stretch_rows)

    return {
        "generated": datetime.now().astimezone().isoformat(timespec="minutes"),
        "since": since.date().isoformat(),
        "days": days,
        "thresholds": {"break_gap": BREAK_GAP_MIN, "light": NUDGE_LIGHT_MIN,
                       "firm": NUDGE_FIRM_MIN, "cooldown": COOLDOWN_MIN,
                       "work_start": WORK_START, "work_end": WORK_END},
        "totals": {
            "prompts": len(prompts),
            "sessions": len({e["session"] for e in acts}),
            "active_days": sum(1 for d in daily if d["prompts"]),
            "zero_days": sum(1 for d in daily if not d["prompts"]),
            "active_h": round(sum(d["active_h"] for d in daily), 1),
            "late_share": round(sum(d["late_prompts"] for d in daily) / max(len(prompts), 1), 3),
            "interrupts": sum(d["interrupts"] for d in daily),
            "tool_errors": sum(d["tool_errors"] for d in daily),
            "lines_edited": sum(d["lines_edited"] for d in daily),
            "subagent_turns": sum(subagent_calls.values()),
            "compactions": sum(1 for e in events if e["kind"] == "compact"),
            "nudges": len(nudges),
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
        "stretches": stretch_rows,
        "prompt_len_by_pos": prompt_len_by_pos,
        "segments": segments,
        "nudges": [{**n, "ts": n["ts"].isoformat()} for n in nudges],
        "sensitivity": sensitivity,
        "parallel_dist": sorted(parallel_dist.items()),
        "projects": projects.most_common(),
        "checkins": [{**c, "ts": c["ts"].isoformat()} for c in checkins],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--projects-dir", default="~/.claude/projects")
    ap.add_argument("--out", default="session-report.html")
    ap.add_argument("--json", help="also write the aggregated data as JSON")
    args = ap.parse_args()
    since = datetime.now().astimezone().replace(hour=0, minute=0, second=0,
                                                microsecond=0) - timedelta(days=args.days - 1)
    events, subs = load(args.projects_dir, since)
    if not events:
        sys.exit(f"No session activity found in {args.projects_dir} since {since.date()}")
    data = summarize(events, subs, load_checkins(args.projects_dir, since), args.days, since)
    if args.json:
        Path(args.json).write_text(json.dumps(data, indent=1))
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
