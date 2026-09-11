#!/bin/zsh
# supervise.sh -- keeps the 14-hour run alive without anyone watching.
#
# Three failure modes it handles, because all three have already happened:
#   the runner dies          -> restart it (it resumes from its own log)
#   the runner stalls        -> heartbeat goes stale, kill and restart
#   the deadline passes      -> stop cleanly and build the deliverables
#
# Everything is idempotent: restarting never repeats or loses work.

SP=/private/tmp/claude-501/-Users-holocron-deep/9706c3ab-4482-41f0-8e16-f1c7269328ba/scratchpad
PY="$SP/rovenv/bin/python"
REPO="$HOME/chatguard"
STALL=420          # seconds without a logged probe before we assume it is wedged
cd "$SP"

echo "SUPERVISOR START $(date '+%F %H:%M')" >> "$SP/supervisor.log"

while true; do
  now=$(date +%s)
  deadline=$(cat "$SP/marathon.deadline" 2>/dev/null || echo 0)
  if [ "$now" -gt "$deadline" ]; then
    echo "DEADLINE $(date '+%H:%M')" >> "$SP/supervisor.log"
    break
  fi

  # queue exhausted?
  remaining=$($PY - <<'EOF' 2>/dev/null
import json,os
SP='/private/tmp/claude-501/-Users-holocron-deep/9706c3ab-4482-41f0-8e16-f1c7269328ba/scratchpad'
done=set()
p=f'{SP}/marathon-results.jsonl'
if os.path.exists(p):
    for l in open(p,encoding='utf-8'):
        try: done.add(json.loads(l)['text'])
        except Exception: pass
q=[l.split('\t')[0] for l in open(f'{SP}/marathon.txt',encoding='utf-8') if l.strip()]
print(sum(1 for w in q if w not in done))
EOF
)
  if [ "${remaining:-1}" = "0" ]; then
    echo "QUEUE EXHAUSTED $(date '+%H:%M')" >> "$SP/supervisor.log"
    break
  fi

  if ! pgrep -f "marathon.py" >/dev/null 2>&1; then
    echo "starting runner ($remaining left) $(date '+%H:%M')" >> "$SP/supervisor.log"
    nohup "$PY" "$SP/marathon.py" >> "$SP/marathon.log" 2>&1 &
    sleep 45
    continue
  fi

  # stall detection
  hb=$(cat "$SP/marathon.heartbeat" 2>/dev/null || echo 0)
  if [ $((now - hb)) -gt $STALL ]; then
    echo "STALLED ${$((now - hb))}s -- restarting $(date '+%H:%M')" >> "$SP/supervisor.log"
    pkill -f "marathon.py"
    sleep 10
    continue
  fi

  sleep 60
done

pkill -f "marathon.py" 2>/dev/null
sleep 3

# ---- build the deliverables from whatever was collected ----
echo "BUILDING DELIVERABLES $(date '+%H:%M')" >> "$SP/supervisor.log"
mkdir -p "$REPO/deploy/live"
"$PY" "$REPO/tools/build_findings.py" \
  --results "$SP/marathon-results.jsonl" \
  --results "$SP/results2.jsonl" \
  --results "$SP/probe-results.jsonl" \
  --out "$REPO/deploy/live" >> "$SP/supervisor.log" 2>&1
cp "$SP/marathon-results.jsonl" "$REPO/deploy/live/raw-marathon-log.jsonl" 2>/dev/null
echo "DONE $(date '+%F %H:%M')" >> "$SP/supervisor.log"
