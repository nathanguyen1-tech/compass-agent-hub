"""
Event bus — WebSocket clients + activity stream.
Centralised broadcast cho toàn bộ app.
"""
import json
from datetime import datetime
from typing import List
from fastapi import WebSocket
from sqlmodel import Session, select

from app.core.database import engine
from app.models.agent import ActivityEvent

ACTIVITY_MAX = 2000
ws_clients: List[WebSocket] = []


async def broadcast(event: dict):
    """Gửi event JSON tới tất cả WebSocket clients đang kết nối."""
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_text(json.dumps(event, ensure_ascii=False))
        except Exception:
            dead.append(ws)
    for ws in dead:
        try: ws_clients.remove(ws)
        except: pass


async def push_activity(agent_id: str, message: str, level: str = "info"):
    """Lưu activity vào DB và broadcast lên WebSocket."""
    event = ActivityEvent(agent_id=agent_id, message=message, level=level)
    with Session(engine) as session:
        session.add(event)
        session.commit()
        session.refresh(event)

    payload = {
        "type": "activity",
        "event": {
            "id":       event.id,
            "agent_id": agent_id,
            "message":  message,
            "level":    level,
            "ts":       event.ts.isoformat(),
        }
    }
    await broadcast(payload)
    return payload["event"]


def get_recent_activity(agent_id: str | None = None, limit: int = 100) -> list:
    with Session(engine) as session:
        stmt = select(ActivityEvent).order_by(ActivityEvent.ts.desc()).limit(limit)
        if agent_id:
            stmt = stmt.where(ActivityEvent.agent_id == agent_id)
        rows = session.exec(stmt).all()
        return [
            {"id": r.id, "agent_id": r.agent_id, "message": r.message,
             "level": r.level, "ts": r.ts.isoformat()}
            for r in reversed(rows)
        ]
