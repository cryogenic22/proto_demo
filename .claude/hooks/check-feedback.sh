#!/bin/bash
# Hook: Check for new feedback entries on session start
# Runs feedback/sync.sh to pull from Railway, then reports new items

cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || cd "$(dirname "$0")/../.." 2>/dev/null

# Sync from Railway (silent, best-effort)
bash feedback/sync.sh > /dev/null 2>&1

# Count new entries
NEW_COUNT=$(grep -c '"status":"new"\|"status": "new"' feedback/backlog.jsonl 2>/dev/null || echo "0")

if [ "$NEW_COUNT" -gt 0 ]; then
  echo "=== FEEDBACK ALERT: $NEW_COUNT new entries found ==="
  python -c "
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
with open('feedback/backlog.jsonl', encoding='utf-8') as f:
    for line in f:
        e = json.loads(line)
        if e.get('status') == 'new':
            pri = e.get('priority','?')
            cat = e.get('category','?')
            title = e.get('title','')[:100]
            print(f'  [{pri}] [{cat}] {title}')
" 2>/dev/null
  echo ""
  echo "Run /process-feedback or /triage-feedback to address these items."
else
  echo "No new feedback entries."
fi

exit 0
