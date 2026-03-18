"""Approval queue — CRUD via SQLModel."""
import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select

from app.core.database import engine
from app.models.agent import Approval


def get_approvals(status: str | None = "pending") -> list[Approval]:
    with Session(engine) as s:
        stmt = select(Approval).order_by(Approval.created_at.desc())
        if status:
            stmt = stmt.where(Approval.status == status)
        return s.exec(stmt).all()


def create_approval(agent_id: str, metadata: dict | None = None) -> Approval:
    import json
    appr = Approval(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        metadata_json=json.dumps(metadata or {}),
    )
    with Session(engine) as s:
        s.add(appr)
        s.commit()
        s.refresh(appr)
    return appr


def resolve_approval(approval_id: str, status: str) -> Optional[Approval]:
    with Session(engine) as s:
        appr = s.get(Approval, approval_id)
        if not appr:
            return None
        appr.status = status
        appr.resolved_at = datetime.utcnow()
        s.add(appr)
        s.commit()
        s.refresh(appr)
    return appr
