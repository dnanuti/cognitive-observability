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
# ~/.claude/mindful-work). No prompt text is read or stored.
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

stamp=$(date -r "$now" '+%Y-%m-%d %H:%M %Z (%a)' 2>/dev/null \
     || date -d "@$now" '+%Y-%m-%d %H:%M %Z (%a)' 2>/dev/null \
     || date '+%Y-%m-%d %H:%M %Z (%a)')

if [ -n "$note" ] && [ "$start" = "$now" ]; then
  echo "mindful-work: local time $stamp$note"
else
  echo "mindful-work: local time $stamp · stretch $(( (now - start) / 60 )) min · idle $(( idle / 60 )) min"
fi
exit 0
