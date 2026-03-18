#!/bin/bash
# ============================================================
# health_check.sh — Compass Vitals Health Check Agent
# Kiểm tra toàn bộ hệ thống mỗi sáng
# ============================================================

export AGENT_ID="health-check"
source /home/nathan-ubutu/.openclaw/workspace/agent-hub/scripts/agent_init.sh

PROJECT_DIR="/home/nathan-ubutu/2026/CVH-Agents/2026-Compass-Vitals-Agent/services/ai-agent-service"
NGROK_URL="https://sleepless-unaffiliated-regena.ngrok-free.dev"
RESULTS=()
PASS=0
FAIL=0

# ── Helper ────────────────────────────────────────────────────
check() {
  local name="$1"
  local result="$2"  # "ok" hoặc "fail"
  local detail="$3"

  if [[ "$result" == "ok" ]]; then
    RESULTS+=("✅ $name — $detail")
    hlog "✅ $name — $detail" success
    ((PASS++))
  else
    RESULTS+=("❌ $name — $detail")
    hlog "❌ $name — $detail" error
    ((FAIL++))
  fi
}

# ── 1. Kiểm tra Python environment ───────────────────────────
hlog "🔍 Kiểm tra Python environment..." progress
if [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
  check "Python venv" "ok" "$(${PROJECT_DIR}/.venv/bin/python --version 2>&1)"
else
  check "Python venv" "fail" "Không tìm thấy .venv"
fi

# ── 2. Kiểm tra server local ──────────────────────────────────
hlog "🌐 Kiểm tra server local..." progress
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://localhost:8001/health" 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" == "200" ]]; then
  check "Server local" "ok" "HTTP $HTTP_CODE — đang chạy"
else
  check "Server local" "fail" "HTTP $HTTP_CODE — không respond"
fi

# ── 3. Kiểm tra ngrok URL ─────────────────────────────────────
hlog "🌐 Kiểm tra ngrok URL..." progress
NGROK_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$NGROK_URL" 2>/dev/null || echo "000")
if [[ "$NGROK_CODE" =~ ^(200|301|302|404)$ ]]; then
  check "Ngrok URL" "ok" "HTTP $NGROK_CODE — tunnel sống"
else
  check "Ngrok URL" "fail" "HTTP $NGROK_CODE — tunnel chết hoặc timeout"
fi

# ── 4. Chạy unit tests ────────────────────────────────────────
hlog "🧪 Đang chạy unit tests..." progress
if [ -d "$PROJECT_DIR" ]; then
  cd "$PROJECT_DIR"
  TEST_OUTPUT=$(.venv/bin/python -m pytest tests/unit/ -x -q 2>&1)
  TEST_RC=$?
  TEST_SUMMARY=$(echo "$TEST_OUTPUT" | tail -1)

  if [[ $TEST_RC -eq 0 ]]; then
    check "Unit tests" "ok" "$TEST_SUMMARY"
  else
    FAIL_LINE=$(echo "$TEST_OUTPUT" | grep "FAILED" | head -1)
    check "Unit tests" "fail" "$FAIL_LINE"
  fi
else
  check "Unit tests" "fail" "Không tìm thấy project directory"
fi

# ── 5. Kiểm tra disk space ────────────────────────────────────
hlog "💾 Kiểm tra disk space..." progress
DISK_USE=$(df -h / | awk 'NR==2{print $5}' | tr -d '%')
if [[ $DISK_USE -lt 85 ]]; then
  check "Disk space" "ok" "Còn $(df -h / | awk 'NR==2{print $4}') — dùng ${DISK_USE}%"
else
  check "Disk space" "fail" "Cảnh báo: dùng ${DISK_USE}% — sắp đầy"
fi

# ── Tổng kết ──────────────────────────────────────────────────
TOTAL=$((PASS + FAIL))
hlog "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" info
hlog "📊 Kết quả: $PASS/$TOTAL pass" "$([ $FAIL -eq 0 ] && echo success || echo warning)"

for r in "${RESULTS[@]}"; do
  hlog "  $r" info
done

if [[ $FAIL -eq 0 ]]; then
  hlog "🏥 Compass Vitals: Tất cả hệ thống bình thường ✅" success
  exit 0
else
  hlog "⚠️ Compass Vitals: $FAIL vấn đề cần chú ý" warning
  exit 1
fi
