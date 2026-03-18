"""
Đại Tướng Delegator — routing logic và openclaw agent calls.
"""
import asyncio, json, os, re, shutil
from datetime import datetime
from pathlib import Path

from app.core.events import push_activity, broadcast
from app.core.registry import get_agents, update_status

_OC_BIN = shutil.which("openclaw") or "/home/nathan-ubutu/.npm-global/bin/openclaw"
_OC_ENV = {**os.environ, "PATH": os.environ.get("PATH", "") + ":/home/nathan-ubutu/.npm-global/bin:/usr/local/bin"}

STATUS_PHRASES = [
    "tình hình", "status", "đang thế nào", "ra sao", "như thế nào",
    "có khoẻ không", "đang làm gì", "hôm nay làm gì", "đang chạy không",
    "có vấn đề không", "bao nhiêu commit", "hôm nay commit",
]
ACTION_PHRASES = [
    "bảo", "gọi", "nhờ", "yêu cầu", "giao cho", "lệnh cho", "hãy làm",
    "kích hoạt", "thực hiện", "hãy thêm", "hãy sửa", "hãy viết",
    "deploy", "push", "build", "fix", "implement", "tạo", "xoá", "sửa",
]
EXIT_WORDS = ["xong", "thoát", "quay lại", "back", "đại tướng", "exit", "done"]


def detect_target(user_msg: str) -> tuple[dict | None, bool]:
    """Trả về (target_agent, is_command). target_agent = None nếu không tìm thấy."""
    agents = get_agents()
    msg_lower = user_msg.lower()

    def agent_keywords(a) -> list[str]:
        n = a.name.lower()
        return list({n, a.id.lower(), a.openclaw_agent_id.lower(),
                     n.replace("-", " "), n.replace(" ", "-"), n.replace(" ", "")})

    target = None
    for a in agents:
        if not a.openclaw_agent_id:
            continue
        if any(k and k in msg_lower for k in agent_keywords(a)):
            target = a
            break

    if target is None:
        return None, False

    has_status = any(w in msg_lower for w in STATUS_PHRASES)
    has_action = any(w in msg_lower for w in ACTION_PHRASES)
    is_cmd = not (has_status and not has_action)
    return target.__dict__ if hasattr(target, "__dict__") else vars(target), is_cmd


def is_exit_request(msg: str) -> bool:
    return any(w in msg.lower() for w in EXIT_WORDS)


async def call_agent(oc_agent_id: str, message: str, timeout: int = 120) -> str:
    """Gọi openclaw agent CLI, trả về text response."""
    try:
        proc = await asyncio.create_subprocess_exec(
            _OC_BIN, "agent", "--agent", oc_agent_id, "--message", message, "--json",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=_OC_ENV
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        raw = stdout.decode("utf-8", errors="replace").strip()
        data = json.loads(raw)
        payloads = data.get("result", {}).get("payloads", [])
        return "\n".join(p.get("text", "") for p in payloads if p.get("text"))
    except asyncio.TimeoutError:
        return "⚠️ Timeout — agent không phản hồi trong thời gian cho phép."
    except Exception as e:
        return f"⚠️ Lỗi: {str(e)[:100]}"


async def run_delegate_background(agent_id: str, oc_id: str, emoji: str, name: str, message: str):
    """Chạy nền: gọi agent, khi xong broadcast lên WebSocket."""
    try:
        await push_activity(agent_id, "🔄 Đang xử lý lệnh từ Chủ tướng...", "info")
        response = await call_agent(oc_id, message)
        short = response[:120] + ("..." if len(response) > 120 else "")
        await push_activity(agent_id, f"✅ Hoàn thành: {short}", "success")
        await broadcast({
            "type":     "agent_reply",
            "agent_id": agent_id,
            "emoji":    emoji,
            "name":     name,
            "message":  response,
            "ts":       datetime.now().isoformat(),
        })
    except Exception as e:
        await push_activity(agent_id, f"❌ Lỗi: {str(e)[:80]}", "error")
