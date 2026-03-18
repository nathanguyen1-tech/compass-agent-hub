"""Agent registry — CRUD operations via SQLModel."""
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select

from app.core.database import engine
from app.models.agent import Agent


def get_agents() -> list[Agent]:
    with Session(engine) as s:
        return s.exec(select(Agent)).all()


def get_agent(agent_id: str) -> Optional[Agent]:
    with Session(engine) as s:
        return s.get(Agent, agent_id)


def upsert_agent(agent: Agent) -> Agent:
    with Session(engine) as s:
        existing = s.get(Agent, agent.id)
        if existing:
            for k, v in agent.model_dump(exclude_unset=True).items():
                setattr(existing, k, v)
            existing.updated_at = datetime.utcnow()
            s.add(existing)
            s.commit()
            s.refresh(existing)
            return existing
        s.add(agent)
        s.commit()
        s.refresh(agent)
        return agent


def update_status(agent_id: str, status: str, extra: dict | None = None) -> Optional[Agent]:
    with Session(engine) as s:
        agent = s.get(Agent, agent_id)
        if not agent:
            return None
        agent.status = status
        agent.updated_at = datetime.utcnow()
        if extra:
            for k, v in extra.items():
                if hasattr(agent, k):
                    setattr(agent, k, v)
        s.add(agent)
        s.commit()
        s.refresh(agent)
        return agent


def seed_from_json(json_path):
    """Migrate dữ liệu từ registry.json cũ sang SQLite."""
    import json
    from pathlib import Path
    data = json.loads(Path(json_path).read_text())
    AGENT_FIELDS = {f for f in Agent.model_fields}
    with Session(engine) as s:
        for a in data.get("agents", []):
            if s.get(Agent, a["id"]):
                continue
            # Chỉ lấy fields tồn tại, bỏ None dates
            filtered = {k: v for k, v in a.items() if k in AGENT_FIELDS and v is not None}
            filtered.pop("last_run", None)   # ignore string dates từ JSON cũ
            filtered.pop("created_at", None)
            filtered.pop("updated_at", None)
            agent = Agent(**filtered)
            s.add(agent)
        s.commit()
    print(f"[seed] Migrated {len(data.get('agents', []))} agents from {json_path}")
