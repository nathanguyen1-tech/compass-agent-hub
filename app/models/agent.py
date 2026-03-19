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
    # v3 fields
    model: str = ""
    workspace_path: str = ""
    agent_dir: str = ""
    source: str = "manual"        # "manual" | "openclaw"
    a2a_enabled: bool = False
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
    status: str = "pending"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class Binding(SQLModel, table=True):
    """Routing bindings: (channel + peer) → agentId"""
    id: Optional[int] = Field(default=None, primary_key=True)
    agent_id: str = Field(index=True)
    channel: str = ""         # "discord", "telegram", "whatsapp", "webchat" ...
    account_id: str = ""
    peer_kind: str = ""       # "direct" | "group" | ""
    peer_id: str = ""
    source: str = "manual"    # "manual" | "openclaw"


class SessionInfo(SQLModel, table=True):
    """Snapshot của active sessions mỗi agent"""
    id: Optional[int] = Field(default=None, primary_key=True)
    agent_id: str = Field(index=True)
    session_key: str = ""
    channel: str = ""
    updated_at_ms: int = 0
    msg_count: int = 0
    is_active: bool = False
    session_file: str = ""
    refreshed_at: datetime = Field(default_factory=datetime.utcnow)


class AgentMessage(SQLModel, table=True):
    """Agent-to-agent messages intercepted từ transcript"""
    id: Optional[int] = Field(default=None, primary_key=True)
    from_agent: str = Field(index=True)
    to_agent: str = Field(index=True)
    preview: str = ""
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)
