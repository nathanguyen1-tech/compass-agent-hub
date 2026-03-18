from fastapi import APIRouter
from app.core.events import get_recent_activity

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("")
def list_activity(agent_id: str | None = None, limit: int = 100):
    return get_recent_activity(agent_id, limit)


@router.get("/agents/{agent_id}")
def agent_activity(agent_id: str, limit: int = 100):
    return get_recent_activity(agent_id, limit)
