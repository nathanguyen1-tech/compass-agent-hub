"""
Phase 4 — Agent-to-Agent Message Bus
Intercept sessions_send tool calls từ transcript watcher.
Visualize inter-agent communication trong real-time.
"""
import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.core.database import engine
from app.core.events import push_activity, broadcast
from app.models.agent import AgentMessage

# sessions_send arguments: { sessionKey: "agent:<id>:main", message: "..." }
_SESSION_KEY_AGENT_PREFIX = "agent:"


def extract_target_agent(session_key: str) -> str | None:
    """Từ sessionKey → agent id. VD: 'agent:hub-keeper:main' → 'hub-keeper'"""
    if not session_key.startswith(_SESSION_KEY_AGENT_PREFIX):
        return None
    parts = session_key[len(_SESSION_KEY_AGENT_PREFIX):].split(":")
    return parts[0] if parts else None


async def handle_tool_call(agent_id: str, tool_name: str, arguments: dict):
    """
    Được gọi bởi transcript watcher cho mỗi tool call.
    Detect sessions_send → parse target → persist + broadcast.
    """
    if tool_name != "sessions_send":
        return

    target_key = arguments.get("sessionKey", "")
    message    = arguments.get("message", "")
    target_id  = extract_target_agent(target_key)

    if not target_id or target_id == agent_id:
        return

    preview = message[:120] + ("..." if len(message) > 120 else "")

    # Persist
    msg = AgentMessage(
        from_agent = agent_id,
        to_agent   = target_id,
        preview    = preview,
    )
    with Session(engine) as db:
        db.add(msg)
        db.commit()
        db.refresh(msg)

    # Push to activity stream của cả hai phía
    await push_activity(agent_id,  f"📨 → {target_id}: {preview[:60]}", "progress")
    await push_activity(target_id, f"📩 ← {agent_id}: {preview[:60]}", "info")

    # Broadcast event riêng cho UI bus
    await broadcast({
        "type":     "agent_message",
        "id":       msg.id,
        "from":     agent_id,
        "to":       target_id,
        "preview":  preview,
        "ts":       msg.ts.isoformat(),
    })


def get_message_bus(limit: int = 50) -> list[dict]:
    with Session(engine) as db:
        rows = db.exec(
            select(AgentMessage).order_by(AgentMessage.ts.desc()).limit(limit)
        ).all()
        return [
            {"id": r.id, "from": r.from_agent, "to": r.to_agent,
             "preview": r.preview, "ts": r.ts.isoformat()}
            for r in reversed(rows)
        ]


def get_agent_message_count(agent_id: str) -> dict:
    """Số messages sent + received hôm nay."""
    from datetime import date
    today = datetime.combine(date.today(), datetime.min.time())
    with Session(engine) as db:
        sent = len(db.exec(
            select(AgentMessage).where(
                AgentMessage.from_agent == agent_id,
                AgentMessage.ts >= today
            )
        ).all())
        received = len(db.exec(
            select(AgentMessage).where(
                AgentMessage.to_agent == agent_id,
                AgentMessage.ts >= today
            )
        ).all())
    return {"sent": sent, "received": received, "total": sent + received}
