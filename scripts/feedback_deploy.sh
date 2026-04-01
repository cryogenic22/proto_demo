#!/bin/bash
# feedback_deploy.sh — Auto-deploy pipeline for feedback-driven changes
#
# Usage: ./scripts/feedback_deploy.sh [feedback_id]
#
# Flow:
#   1. Run full test suite
#   2. If all pass → commit + push to main
#   3. Railway auto-deploys from main branch
#   4. Update feedback status to "delivered" via API

set -e

FEEDBACK_ID="${1:-}"
API_BASE="${API_BASE:-http://localhost:8000}"

echo "========================================="
echo "  Feedback Deploy Pipeline"
echo "========================================="

# Step 1: Run tests
echo ""
echo "[1/4] Running test suite..."
cd "$(dirname "$0")/.."
python -m pytest tests/ --timeout=60 -q --ignore=tests/test_smb_integration.py 2>&1
TEST_EXIT=$?

if [ $TEST_EXIT -ne 0 ]; then
    echo ""
    echo "FAIL: Tests did not pass. Aborting deploy."
    if [ -n "$FEEDBACK_ID" ]; then
        curl -s -X PATCH "$API_BASE/api/feedback/$FEEDBACK_ID" \
            -H "Content-Type: application/json" \
            -d "{\"status\": \"testing\", \"resolution\": \"Tests failed — needs fix before deploy\"}" \
            > /dev/null 2>&1 || true
    fi
    exit 1
fi

echo ""
echo "[2/4] Tests passed. Checking for changes..."

# Step 2: Check if there are changes to commit
if git diff --quiet && git diff --cached --quiet; then
    echo "No changes to commit."
else
    echo "Staging and committing changes..."
    git add -A
    git commit -m "fix: feedback-driven auto-deploy [FB-${FEEDBACK_ID:-manual}]

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
fi

# Step 3: Push to main (Railway auto-deploys)
echo ""
echo "[3/4] Pushing to origin/main..."
git push origin main

echo ""
echo "[4/4] Deployed. Updating feedback status..."

# Step 4: Update feedback status
if [ -n "$FEEDBACK_ID" ]; then
    curl -s -X PATCH "$API_BASE/api/feedback/$FEEDBACK_ID" \
        -H "Content-Type: application/json" \
        -d "{\"status\": \"delivered\", \"resolution\": \"Auto-deployed to Railway via feedback pipeline\"}" \
        > /dev/null 2>&1 || echo "Warning: Could not update feedback status"
    echo "Feedback $FEEDBACK_ID marked as delivered."
fi

echo ""
echo "========================================="
echo "  Deploy complete"
echo "========================================="
