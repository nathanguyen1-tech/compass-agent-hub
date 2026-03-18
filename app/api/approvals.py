from fastapi import APIRouter, HTTPException
from app.core.approvals import get_approvals, resolve_approval
from app.core.events import push_activity
from app.core.registry import update_status

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


def _appr_dict(a) -> dict:
    return {
        "id": a.id, "agent_id": a.agent_id, "status": a.status,
        "created_at": a.created_at.isoformat(),
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
    }


@router.get("")
def list_approvals(status: str = "pending"):
    return [_appr_dict(a) for a in get_approvals(status)]


@router.post("/{approval_id}/approve")
async def approve(approval_id: str):
    appr = resolve_approval(approval_id, "approved")
    if not appr:
        raise HTTPException(404)
    update_status(appr.agent_id, "done")
    from pathlib import Path
    Path("/tmp/fb_confirm").touch()
    await push_activity(appr.agent_id, "✅ Chủ tướng đã phê duyệt", "success")
    return {"status": "approved"}


@router.post("/{approval_id}/reject")
async def reject(approval_id: str):
    appr = resolve_approval(approval_id, "rejected")
    if not appr:
        raise HTTPException(404)
    update_status(appr.agent_id, "rejected")
    from pathlib import Path
    Path("/tmp/fb_reject").touch()
    await push_activity(appr.agent_id, "❌ Chủ tướng từ chối", "error")
    return {"status": "rejected"}
