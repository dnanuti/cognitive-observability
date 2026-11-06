#!/bin/sh
# mindful-work timing hook for Claude Code. POSIX sh + date only.
#
#   mindful-time.sh prompt    (UserPromptSubmit) print time, stretch and idle
#                             time; start a new stretch after a break
#   mindful-time.sh activity  (PostToolUse, Stop) record that Claude is working
#
# A stretch is continuous activity from you OR Claude, across all sessions.
# It resets when nothing happened for BREAK_MIN minutes (default 10), so
# Claude working for a long time no longer looks like a break.
#
# State: two epoch-second files in $MINDFUL_STATE_DIR (default
# ~/.claude/mindful-work), plus daily.jsonl written once a day by
# scripts/analyze_sessions.py --save-daily (counts only). No prompt text is
# stored.
# MINDFUL_NOW overrides the clock for testing.

[ -t 0 ] || cat >/dev/null   # drain the hook's JSON input; we don't need it

mode=${1:-prompt}
dir=${MINDFUL_STATE_DIR:-$HOME/.claude/mindful-work}
break_s=$(( ${MINDFUL_BREAK_MIN:-10} * 60 ))
now=${MINDFUL_NOW:-$(date +%s)}

mkdir -p "$dir" 2>/dev/null || exit 0

read_num() { v=$(cat "$1" 2>/dev/null); case $v in ''|*[!0-9]*) echo "";; *) echo "$v";; esac; }
write_num() { printf '%s\n' "$2" > "$1.$$" 2>/dev/null && mv "$1.$$" "$1" 2>/dev/null; }

last=$(read_num "$dir/last_activity")
start=$(read_num "$dir/stretch_start")

if [ "$mode" = "activity" ]; then
  # Claude is working: extend the stretch, never start a new one here.
  [ -n "$start" ] || write_num "$dir/stretch_start" "$now"
  write_num "$dir/last_activity" "$now"
  exit 0
fi

note=""
if [ -z "$last" ] || [ -z "$start" ]; then
  start=$now; idle=0; note=" · new stretch"
else
  idle=$(( now - last ))
  [ "$idle" -lt 0 ] && idle=0
  if [ "$idle" -ge "$break_s" ]; then
    note=" · new stretch after $(( idle / 60 )) min break"
    start=$now
  fi
fi
write_num "$dir/stretch_start" "$start"
write_num "$dir/last_activity" "$now"

# Once a day, save yesterday's numbers-only summary in the background so
# trends outlive transcript cleanup. Set MINDFUL_DAILY=0 to turn off.
today=$(date '+%Y-%m-%d')
if [ "${MINDFUL_DAILY:-1}" != 0 ] && [ "$(cat "$dir/daily_saved" 2>/dev/null)" != "$today" ]; then
  script="$(dirname "$0")/../scripts/analyze_sessions.py"
  if [ -f "$script" ] && command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "$today" > "$dir/daily_saved"
    ( python3 -I "$script" --days 3 --save-daily --no-report >/dev/null 2>"$dir/daily.err" & ) 2>/dev/null
  fi
fi

stamp=$(date -r "$now" '+%Y-%m-%d %H:%M %Z (%a)' 2>/dev/null \
     || date -d "@$now" '+%Y-%m-%d %H:%M %Z (%a)' 2>/dev/null \
     || date '+%Y-%m-%d %H:%M %Z (%a)')

if [ -n "$note" ] && [ "$start" = "$now" ]; then
  echo "mindful-work: local time $stamp$note"
else
  echo "mindful-work: local time $stamp · stretch $(( (now - start) / 60 )) min · idle $(( idle / 60 )) min"
fi
exit 0
