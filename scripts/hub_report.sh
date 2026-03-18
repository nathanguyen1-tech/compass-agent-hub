#!/bin/bash
# ============================================================
# hub_report.sh — Báo cáo tiến trình về Agent Hub
# ============================================================
# Usage:
#   hub_report.sh <agent_id> <message> [level]
#
# Levels: info | success | error | warning | progress
#
# Ví dụ:
#   hub_report.sh feedback-bot "Đang đọc feedback.md..." progress
#   hub_report.sh feedback-bot "Tests pass (12/12)" success
#   hub_report.sh feedback-bot "Lỗi: không tìm thấy file" error
# ============================================================

AGENT_ID="${1:?Thiếu agent_id}"
MESSAGE="${2:?Thiếu message}"
LEVEL="${3:-info}"
HUB_URL="${HUB_URL:-http://localhost:7777}"

curl -s -X POST "${HUB_URL}/api/agents/${AGENT_ID}/activity" \
  -H "Content-Type: application/json" \
  -d "{\"message\": $(echo -n "$MESSAGE" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'), \"level\": \"${LEVEL}\"}" \
  > /dev/null 2>&1 || true  # Không fail nếu hub offline
