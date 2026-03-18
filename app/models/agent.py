from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class Agent(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    emoji: str = "🤖"
    description: str = ""
    script: str = ""
    requires_approval: bool = False
    status: str = "idle"
    last_run: Optional[datetime] = None
    last_log: Optional[str] = None
    openclaw_agent_id: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ActivityEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    agent_id: str = Field(index=True)
    message: str
    level: str = "info"
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)


class Approval(SQLModel, table=True):
    id: str = Field(primary_key=True)
    agent_id: str = Field(index=True)
    status: str = "pending"   # pending | approved | rejected
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
