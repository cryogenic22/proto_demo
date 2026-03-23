#!/bin/bash
# Feedback sync script — pulls feedback from Railway API
# Currently a placeholder — will be wired when feedback API is added

cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || cd "$(dirname "$0")/.." 2>/dev/null

API_BASE="${PROTOEXTRACT_API_URL:-https://protoextract-production.up.railway.app}"
BACKLOG="feedback/backlog.jsonl"

# Ensure backlog file exists
touch "$BACKLOG"

# TODO: When feedback API is added to the backend:
# 1. Authenticate to the API
# 2. Fetch entries: curl -s "$API_BASE/api/feedback/backlog?status=new"
# 3. Append new entries to $BACKLOG (skip duplicates by ID)

echo "Feedback sync: backlog has $(wc -l < "$BACKLOG" | tr -d ' ') entries"
