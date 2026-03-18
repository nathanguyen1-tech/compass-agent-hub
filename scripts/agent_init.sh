#!/bin/bash
# ============================================================
# agent_init.sh — Auto hub reporting cho mọi agent
# ============================================================
# Cách dùng: thêm vào đầu script của agent:
#
#   export AGENT_ID="ten-agent"
#   source /home/nathan-ubutu/.openclaw/workspace/agent-hub/scripts/agent_init.sh
#
# Sau đó mọi thứ tự động:
#   - git commit/push/pull → tự báo cáo
#   - pytest               → tự báo cáo
#   - Dùng hlog "message"  → báo cáo thủ công nếu cần
# ============================================================

AGENT_ID="${AGENT_ID:?[agent_init] Cần set AGENT_ID trước khi source file này}"
HUB_LOG="/tmp/hub-${AGENT_ID}.log"
HUB_URL="${HUB_URL:-http://localhost:7777}"

# Tạo / reset log file
: > "$HUB_LOG"

# ── Core: ghi log ─────────────────────────────────────────────
hlog() {
  local msg="$1"
  local level="${2:-info}"
  # Ghi JSON line vào log file — server sẽ tự đọc và push lên stream
  python3 -c "import json,sys; print(json.dumps({'message':sys.argv[1],'level':sys.argv[2]}, ensure_ascii=False))" \
    "$msg" "$level" >> "$HUB_LOG"
}

# Báo bắt đầu
hlog "🚀 Agent khởi động" info

# ── Auto-hook: git ─────────────────────────────────────────────
git() {
  case "$1" in
    pull)   hlog "⬇️ Đang pull code mới nhất..." progress ;;
    commit) hlog "📦 Đang commit..." progress ;;
    push)   hlog "🚀 Đang push lên GitHub..." progress ;;
  esac

  command git "$@"
  local rc=$?

  case "$1" in
    pull)
      [[ $rc -eq 0 ]] && hlog "✅ Pull thành công" success \
                      || hlog "❌ Pull thất bại (exit $rc)" error ;;
    commit)
      if [[ $rc -eq 0 ]]; then
        local hash; hash=$(command git rev-parse --short HEAD 2>/dev/null)
        hlog "✅ Committed: $hash" success
      else
        hlog "❌ Commit thất bại (exit $rc)" error
      fi ;;
    push)
      [[ $rc -eq 0 ]] && hlog "✅ Pushed lên GitHub" success \
                      || hlog "❌ Push thất bại (exit $rc)" error ;;
  esac
  return $rc
}

# ── Auto-hook: pytest ──────────────────────────────────────────
pytest() {
  hlog "🧪 Đang chạy tests..." progress
  command python3 -m pytest "$@"
  local rc=$?
  if [[ $rc -eq 0 ]]; then
    # Đếm số tests pass
    local summary; summary=$(command python3 -m pytest "$@" --tb=no -q 2>&1 | tail -1)
    hlog "✅ Tests pass — $summary" success
  else
    local fail_info; fail_info=$(command python3 -m pytest "$@" --tb=line -q 2>&1 | tail -5 | tr '\n' ' ')
    hlog "❌ Tests FAIL — $fail_info" error
  fi
  return $rc
}

# ── Trap: exit ─────────────────────────────────────────────────
_hub_on_exit() {
  local rc=$?
  if [[ $rc -eq 0 ]]; then
    hlog "✅ Agent hoàn thành (exit 0)" success
  else
    hlog "❌ Agent kết thúc với lỗi (exit $rc)" error
  fi
}
trap _hub_on_exit EXIT

# ── Export để subshells dùng được ─────────────────────────────
export -f hlog git pytest 2>/dev/null || true
export HUB_LOG HUB_URL AGENT_ID
