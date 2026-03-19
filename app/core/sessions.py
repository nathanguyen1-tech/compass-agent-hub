"""
Phase 3 — Real-time Session Intelligence
Parse session store sâu hơn: biết agent đang trong session nào,
channel nào, user nào, bao nhiêu messages.
"""
import json, re, time
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from app.core.database import engine
from app.models.agent import SessionInfo

OPENCLAW_AGENTS_DIR = Path.home() / ".openclaw" / "agents"
SESSION_ACTIVE_MS   = 180_000   # 3 phút

# Pattern: "agent:<agentId>:<channelKey>"
_SESSION_KEY_RE = re.compile(r'^agent:([^:]+):(.+)$')

# Map channel keys → tên đẹp
_CHANNEL_MAP = {
    "main": "webchat",
    "telegram": "telegram",
    "discord": "discord",
    "whatsapp": "whatsapp",
    "signal": "signal",
    "imessage": "iMessage",
    "slack": "Slack",
    "irc": "IRC",
}


def _parse_channel(session_key: str, agent_id: str) -> str:
    """Từ session key → tên channel."""
    # Remove "agent:<agentId>:" prefix
    m = _SESSION_KEY_RE.match(session_key)
    if not m:
        return "unknown"
    rest = m.group(2)   # phần sau agent_id

    for k, v in _CHANNEL_MAP.items():
        if rest.startswith(k) or k in rest:
            return v
    # Fallback: lấy phần đầu
    return rest.split(":")[0] or "unknown"


def get_agent_sessions(agent_id: str) -> list[dict]:
    """
    Đọc sessions.json của agent → parse thành danh sách sessions với metadata.
    """
    sess_dir  = OPENCLAW_AGENTS_DIR / agent_id / "sessions"
    sess_file = sess_dir / "sessions.json"
    if not sess_file.exists():
        return []

    try:
        raw  = sess_file.read_text()
        data = json.loads(raw)
        sessions = data if isinstance(data, list) else data.get("sessions", [])
    except Exception:
        return []

    now_ms = time.time() * 1000
    result = []
    for s in sessions:
        key        = s.get("key", "")
        updated_ms = s.get("updatedAt", 0)
        age_sec    = (now_ms - updated_ms) / 1000 if updated_ms else 9999
        is_active  = age_sec < (SESSION_ACTIVE_MS / 1000)
        sf         = s.get("sessionFile") or s.get("file", "")

        # Tìm số messages từ JSONL nếu có
        msg_count = 0
        sf_path   = None
        if sf:
            sf_path = Path(sf) if Path(sf).is_absolute() else sess_dir / sf
            if sf_path.exists():
                try:
                    msg_count = sum(1 for line in sf_path.open()
                                    if '"role"' in line and '"user"' in line)
                except Exception:
                    pass

        result.append({
            "key":          key,
            "channel":      _parse_channel(key, agent_id),
            "updated_at_ms": updated_ms,
            "updated_ago":  _format_age(age_sec),
            "is_active":    is_active,
            "msg_count":    msg_count,
            "session_file": str(sf_path) if sf_path else "",
            "age_sec":      int(age_sec),
        })

    # Sort: active first, then by recency
    result.sort(key=lambda x: (-x["is_active"], x["age_sec"]))
    return result


def _format_age(age_sec: float) -> str:
    if age_sec < 60:        return f"{int(age_sec)}s ago"
    if age_sec < 3600:      return f"{int(age_sec/60)}m ago"
    if age_sec < 86400:     return f"{int(age_sec/3600)}h ago"
    return f"{int(age_sec/86400)}d ago"


def sync_session_snapshots(agent_id: str):
    """Lưu snapshot session vào DB để query nhanh."""
    sessions = get_agent_sessions(agent_id)
    now      = datetime.utcnow()

    with Session(engine) as db:
        # Xoá snapshots cũ của agent này
        old = db.exec(select(SessionInfo).where(SessionInfo.agent_id == agent_id)).all()
        for o in old:
            db.delete(o)

        for s in sessions:
            snap = SessionInfo(
                agent_id       = agent_id,
                session_key    = s["key"],
                channel        = s["channel"],
                updated_at_ms  = s["updated_at_ms"],
                msg_count      = s["msg_count"],
                is_active      = s["is_active"],
                session_file   = s["session_file"],
                refreshed_at   = now,
            )
            db.add(snap)
        db.commit()


def get_all_active_sessions() -> list[dict]:
    """Trả về tất cả sessions đang active (< 3 phút) của mọi agent."""
    with Session(engine) as db:
        rows = db.exec(
            select(SessionInfo).where(SessionInfo.is_active == True)  # noqa
        ).all()
        return [
            {"agent_id": r.agent_id, "channel": r.channel,
             "session_key": r.session_key, "msg_count": r.msg_count,
             "updated_at_ms": r.updated_at_ms}
            for r in rows
        ]
