"""Phase 2 — Topology API: bindings, channels, session stats, A2A bus."""
from fastapi import APIRouter
from app.core.discovery import get_topology
from app.core.sessions import get_agent_sessions, get_all_active_sessions
from app.core.message_bus import get_message_bus, get_agent_message_count

router = APIRouter(prefix="/api/topology", tags=["topology"])


@router.get("")
def topology():
    return get_topology()


@router.get("/sessions")
def all_active_sessions():
    return get_all_active_sessions()


@router.get("/sessions/{agent_id}")
def agent_sessions(agent_id: str):
    return get_agent_sessions(agent_id)


@router.get("/messages")
def message_bus(limit: int = 50):
    return get_message_bus(limit)


@router.get("/messages/{agent_id}")
def agent_messages(agent_id: str):
    return get_agent_message_count(agent_id)
