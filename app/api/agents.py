from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.core.registry import get_agents, get_agent, upsert_agent, update_status
from app.core.events import push_activity
from app.models.agent import Agent

router = APIRouter(prefix="/api/agents", tags=["agents"])


class NewAgentRequest(BaseModel):
    id: str
    name: str
    emoji: str = "🤖"
    description: str = ""
    script: str = ""
    requires_approval: bool = False
    openclaw_agent_id: str = ""


def _agent_dict(a: Agent) -> dict:
    return {
        "id": a.id, "name": a.name, "emoji": a.emoji,
        "description": a.description, "script": a.script,
        "requires_approval": a.requires_approval, "status": a.status,
        "last_run": a.last_run.isoformat() if a.last_run else None,
        "last_log": a.last_log, "openclaw_agent_id": a.openclaw_agent_id,
    }


@router.get("")
def list_agents():
    return [_agent_dict(a) for a in get_agents()]


@router.get("/{agent_id}")
def get_agent_detail(agent_id: str):
    a = get_agent(agent_id)
    if not a:
        raise HTTPException(404, "Agent không tồn tại")
    return _agent_dict(a)


@router.post("")
async def create_agent(req: NewAgentRequest):
    if get_agent(req.id):
        raise HTTPException(400, f"Agent '{req.id}' đã tồn tại")
    agent = Agent(**req.model_dump())
    upsert_agent(agent)
    await push_activity(req.id, f"✨ Agent mới: {req.name}", "success")
    return {"status": "created", "agent": _agent_dict(agent)}


@router.post("/{agent_id}/status")
async def set_status(agent_id: str, payload: dict):
    status = payload.get("status", "idle")
    a = update_status(agent_id, status)
    if not a:
        raise HTTPException(404, "Agent không tồn tại")
    return {"status": "ok", "agent_status": a.status}


@router.post("/{agent_id}/activity")
async def agent_activity(agent_id: str, payload: dict):
    msg = payload.get("message", "")
    level = payload.get("level", "info")
    if not msg:
        raise HTTPException(400, "message required")
    event = await push_activity(agent_id, msg, level)
    return {"status": "ok", "event": event}
