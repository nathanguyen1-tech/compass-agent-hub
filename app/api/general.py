"""Đại Tướng API — chat, delegate, fire-and-monitor."""
import asyncio, json, re
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.delegator import detect_target, is_exit_request, call_agent, run_delegate_background
from app.core.events import push_activity, get_recent_activity, broadcast
from app.core.registry import get_agents
from app.core.approvals import get_approvals

router = APIRouter(prefix="/api/general", tags=["general"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    active_agent_id: str = ""


def _empire_context() -> dict:
    agents    = get_agents()
    approvals = get_approvals("pending")
    events    = get_recent_activity(limit=50)
    return {"agents": agents, "approvals": approvals, "events": events}


def _build_prompt(user_msg: str) -> str:
    ctx    = _empire_context()
    agents = ctx["agents"]
    now    = datetime.now().strftime("%H:%M %d/%m/%Y")
    army   = "\n".join(f"  {a.emoji} {a.name} (id={a.id} oc={a.openclaw_agent_id} status={a.status})" for a in agents)
    recent = "\n".join(f"  [{e['ts'][11:16]}] {e['agent_id']}: {e['message'][:60]}" for e in ctx["events"][-10:])
    appr_count = len(ctx["approvals"])

    return (
        f"Mày là Đại Tướng Nathan-Ubu, tổng chỉ huy đội quân AI.\n"
        f"Xưng 'thần', gọi user là 'Chủ tướng'. Ngắn gọn, súc tích.\n\n"
        f"[Thời gian: {now}]\n"
        f"[Quân đội]\n{army}\n"
        f"[Chờ duyệt: {appr_count}]\n"
        f"[Hoạt động gần đây]\n{recent}\n\n"
        f"Chủ tướng: {user_msg}"
    )


async def _stream_text(text: str):
    for i in range(0, len(text), 10):
        yield "data: " + json.dumps({"type": "delta", "text": text[i:i+10]}) + "\n\n"
        await asyncio.sleep(0.008)


@router.post("/chat")
async def general_chat(req: ChatRequest, background_tasks: BackgroundTasks):
    user_msg = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    if not user_msg:
        async def _err():
            yield "data: " + json.dumps({"type": "error", "text": "Không có tin nhắn"}) + "\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream")

    active_oc_id = req.active_agent_id.strip()

    # ── Active agent direct routing ───────────────────────────
    if active_oc_id:
        agents = get_agents()
        active_obj = next((a for a in agents if a.openclaw_agent_id == active_oc_id), None)
        if active_obj:
            if is_exit_request(user_msg):
                async def _exit():
                    yield "data: " + json.dumps({"type": "delta",
                        "text": f"✅ Kết thúc phiên với {active_obj.emoji} **{active_obj.name}**. Quay lại Đại Tướng."}) + "\n\n"
                    yield "data: " + json.dumps({"type": "done", "executed": [], "delegates": [], "exit_agent": True}) + "\n\n"
                return StreamingResponse(_exit(), media_type="text/event-stream",
                                         headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

            async def _direct():
                proc_response = await call_agent(active_oc_id, user_msg)
                if not proc_response:
                    proc_response = "⚠️ Không có phản hồi."
                async for chunk in _stream_text(proc_response):
                    yield chunk
                await push_activity(active_obj.id, f"💬 {proc_response[:80]}", "info")
                yield "data: " + json.dumps({"type": "done", "executed": [], "delegates": [],
                                             "keep_agent": active_oc_id}) + "\n\n"

            return StreamingResponse(_direct(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ── Detect target agent ───────────────────────────────────
    target_dict, is_cmd = detect_target(user_msg)

    async def _stream():
        if is_cmd and target_dict:
            oc_id  = target_dict.get("openclaw_agent_id", "")
            emoji  = target_dict.get("emoji", "")
            name   = target_dict.get("name", oc_id)
            hub_id = target_dict.get("id", oc_id)
            label  = f"{emoji} **{name}**"

            ack = (f"⚔️ Tuân lệnh! Đã giao nhiệm vụ cho {label}.\n\n"
                   f"📡 Theo dõi tiến trình tại **Activity Stream**.\n"
                   f"🔔 Thần sẽ báo cáo ngay khi {name} hoàn thành.")
            async for chunk in _stream_text(ack):
                yield chunk

            asyncio.create_task(run_delegate_background(hub_id, oc_id, emoji, name, user_msg))

            yield "data: " + json.dumps({
                "type": "done", "executed": [], "delegates": [oc_id],
                "fire_and_monitor": True,
                "activate_agent": {"oc_id": oc_id, "name": name, "emoji": emoji, "hub_id": hub_id}
            }) + "\n\n"

        else:
            prompt       = _build_prompt(user_msg)
            general_text = await call_agent("main", prompt)
            if not general_text:
                general_text = "❌ Đại Tướng không phản hồi."
            visible = re.sub(r'\[ACTION:[^\]]+\]', '', general_text).strip()
            async for chunk in _stream_text(visible):
                yield chunk
            yield "data: " + json.dumps({"type": "done", "executed": [], "delegates": []}) + "\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
