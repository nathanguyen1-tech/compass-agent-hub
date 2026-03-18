#!/usr/bin/env python3
"""
Agent Hub — Bản chỉ huy
Server quản lý tất cả agents, live logs, approval queue, activity stream
"""
import asyncio, json, os, subprocess, time, uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE = Path(__file__).parent
REGISTRY_FILE = BASE / "registry.json"
LOGS_DIR = BASE / "logs"
APPROVALS_FILE = BASE / "approvals.json"
LOGS_DIR.mkdir(exist_ok=True)

# ── Startup / Lifespan ───────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        reg = load_registry()
        changed = 0
        for a in reg["agents"]:
            agent_id = a["id"]
            if agent_id not in agent_processes or agent_processes[agent_id].poll() is not None:
                if a.get("status") not in ("idle", "done", "rejected"):
                    a["status"] = "idle"
                    changed += 1
        if changed:
            save_registry(reg)
            print(f"[startup] Reset {changed} agent(s) về 'idle'")
    except Exception as e:
        print(f"[startup] Lỗi reset status: {e}")
    yield


app = FastAPI(title="Agent Hub — Bản chỉ huy", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In-memory state
agent_processes: Dict[str, subprocess.Popen] = {}
ws_clients: Dict[str, List[WebSocket]] = {}        # agent_id → websockets
global_ws_clients: List[WebSocket] = []             # command center clients
activity_log: deque = deque(maxlen=200)             # global activity feed

# ── Helpers ──────────────────────────────────────────────────

def load_registry():
    return json.loads(REGISTRY_FILE.read_text())

def save_registry(data):
    REGISTRY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def update_agent_status(agent_id: str, status: str, extra: dict = {}):
    reg = load_registry()
    for a in reg["agents"]:
        if a["id"] == agent_id:
            a["status"] = status
            a.update(extra)
            break
    save_registry(reg)

def load_approvals():
    if not APPROVALS_FILE.exists():
        return []
    return json.loads(APPROVALS_FILE.read_text())

def save_approvals(data):
    APPROVALS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

async def broadcast(agent_id: str, message: dict):
    clients = ws_clients.get(agent_id, [])
    dead = []
    for ws in clients:
        try:
            await ws.send_json(message)
        except:
            dead.append(ws)
    for d in dead:
        clients.remove(d)

async def push_activity(agent_id: str, message: str, level: str = "info"):
    """Push event vào global activity stream."""
    reg = load_registry()
    agent = next((a for a in reg["agents"] if a["id"] == agent_id), None)
    emoji = agent.get("emoji", "🤖") if agent else "🤖"
    name = agent.get("name", agent_id) if agent else agent_id

    event = {
        "id": str(uuid.uuid4())[:8],
        "agent_id": agent_id,
        "agent_name": name,
        "agent_emoji": emoji,
        "message": message,
        "level": level,   # info | success | error | warning | progress
        "ts": datetime.now().isoformat()
    }
    activity_log.append(event)

    dead = []
    for ws in global_ws_clients:
        try:
            await ws.send_json({"type": "activity", "event": event})
        except:
            dead.append(ws)
    for d in dead:
        global_ws_clients.remove(d)

# ── API Routes ───────────────────────────────────────────────

@app.get("/api/agents")
def get_agents():
    reg = load_registry()
    for a in reg["agents"]:
        pid = a["id"]
        if pid in agent_processes:
            proc = agent_processes[pid]
            if proc.poll() is None:
                a["status"] = "running"
            else:
                if a["status"] == "running":
                    a["status"] = "done" if proc.returncode == 0 else "error"
    return reg["agents"]

@app.get("/api/approvals")
def get_approvals():
    return load_approvals()

@app.get("/api/activity")
def get_activity(limit: int = 100):
    """Lấy lịch sử activity gần đây."""
    events = list(activity_log)[-limit:]
    return {"events": events}

# ── Agent tự báo cáo tiến trình ──────────────────────────────

class ActivityReport(BaseModel):
    message: str
    level: str = "info"   # info | success | error | warning | progress

@app.post("/api/agents/{agent_id}/activity")
async def post_activity(agent_id: str, report: ActivityReport):
    """Endpoint để agent báo cáo tiến trình về Hub."""
    reg = load_registry()
    agent = next((a for a in reg["agents"] if a["id"] == agent_id), None)
    if not agent:
        raise HTTPException(404, "Agent không tồn tại")
    await push_activity(agent_id, report.message, report.level)
    # Cũng broadcast vào agent-specific websocket
    await broadcast(agent_id, {
        "type": "log",
        "line": f"[{report.level.upper()}] {report.message}",
        "ts": datetime.now().isoformat()
    })
    return {"status": "ok"}

# ── Run / Stop ────────────────────────────────────────────────

class RunRequest(BaseModel):
    args: Optional[List[str]] = []

@app.post("/api/agents/{agent_id}/run")
async def run_agent(agent_id: str, req: RunRequest, background_tasks: BackgroundTasks):
    reg = load_registry()
    agent = next((a for a in reg["agents"] if a["id"] == agent_id), None)
    if not agent:
        raise HTTPException(404, "Agent không tồn tại")
    if agent_id in agent_processes and agent_processes[agent_id].poll() is None:
        raise HTTPException(409, "Agent đang chạy")

    script = agent.get("script", "")
    if not script:
        raise HTTPException(400, f"Agent '{agent_id}' chưa được cấu hình script.")
    if not Path(script).exists():
        raise HTTPException(400, f"Script không tồn tại: {script}")

    log_file = LOGS_DIR / f"{agent_id}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    update_agent_status(agent_id, "running", {"last_run": datetime.now().isoformat(), "last_log": str(log_file)})
    await push_activity(agent_id, "Bắt đầu chạy", "info")

    background_tasks.add_task(_run_agent_bg, agent_id, agent["script"], req.args or [], log_file)
    return {"status": "started", "log_file": str(log_file)}

async def _run_agent_bg(agent_id: str, script: str, args: List[str], log_file: Path):
    cmd = ["bash", script] + args
    await broadcast(agent_id, {"type": "started", "cmd": " ".join(cmd), "ts": datetime.now().isoformat()})

    with open(log_file, "w") as lf:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        agent_processes[agent_id] = proc

        for line in proc.stdout:
            line = line.rstrip()
            lf.write(line + "\n")
            lf.flush()
            await broadcast(agent_id, {"type": "log", "line": line, "ts": datetime.now().isoformat()})
            # Push dòng log vào global stream nếu quan trọng
            if any(k in line for k in ["✅", "❌", "⚠️", "🔧", "🚀", "⏳", "error", "Error"]):
                level = "success" if "✅" in line else "error" if "❌" in line else "warning"
                await push_activity(agent_id, line, level)

        proc.wait()

    rc = proc.returncode
    status = "pending_approval" if rc == 0 else "error"
    update_agent_status(agent_id, status)
    await broadcast(agent_id, {"type": "done", "rc": rc, "status": status, "ts": datetime.now().isoformat()})

    if rc == 0:
        await push_activity(agent_id, "Hoàn thành — chờ phê duyệt", "success")
        approvals = load_approvals()
        approvals.append({
            "id": str(uuid.uuid4())[:8],
            "agent_id": agent_id,
            "created_at": datetime.now().isoformat(),
            "log_file": str(log_file),
            "status": "pending"
        })
        save_approvals(approvals)
    else:
        await push_activity(agent_id, f"Lỗi (exit code {rc})", "error")

@app.post("/api/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    proc = agent_processes.get(agent_id)
    if proc and proc.poll() is None:
        proc.terminate()
        update_agent_status(agent_id, "stopped")
        await broadcast(agent_id, {"type": "stopped", "ts": datetime.now().isoformat()})
        await push_activity(agent_id, "Bị dừng thủ công", "warning")
        return {"status": "stopped"}
    return {"status": "not_running"}

# ── Approvals ─────────────────────────────────────────────────

class ApprovalAction(BaseModel):
    action: str  # "approve" or "reject"

@app.post("/api/approvals/{approval_id}")
async def handle_approval(approval_id: str, req: ApprovalAction):
    approvals = load_approvals()
    approval = next((a for a in approvals if a["id"] == approval_id), None)
    if not approval:
        raise HTTPException(404, "Approval không tồn tại")

    approval["status"] = req.action + "d"
    approval["resolved_at"] = datetime.now().isoformat()
    save_approvals(approvals)

    agent_id = approval["agent_id"]
    if req.action == "approve":
        Path("/tmp/fb_confirm").touch()
        update_agent_status(agent_id, "done")
        await broadcast(agent_id, {"type": "approved", "ts": datetime.now().isoformat()})
        await push_activity(agent_id, "✅ Đã được phê duyệt — commit + push", "success")
    else:
        Path("/tmp/fb_reject").touch()
        update_agent_status(agent_id, "rejected")
        await broadcast(agent_id, {"type": "rejected", "ts": datetime.now().isoformat()})
        await push_activity(agent_id, "❌ Bị từ chối", "error")

    return {"status": "ok"}

# ── Logs ─────────────────────────────────────────────────────

@app.get("/api/agents/{agent_id}/logs")
def get_logs(agent_id: str, lines: int = 100):
    reg = load_registry()
    agent = next((a for a in reg["agents"] if a["id"] == agent_id), None)
    if not agent or not agent.get("last_log"):
        return {"lines": []}
    log_file = Path(agent["last_log"])
    if not log_file.exists():
        return {"lines": []}
    all_lines = log_file.read_text().splitlines()
    return {"lines": all_lines[-lines:]}

@app.post("/api/agents")
async def register_agent(agent: dict):
    reg = load_registry()
    reg["agents"].append(agent)
    save_registry(reg)
    return {"status": "registered"}

# ── WebSockets ────────────────────────────────────────────────

@app.websocket("/ws/{agent_id}")
async def websocket_agent(websocket: WebSocket, agent_id: str):
    """WebSocket cho individual agent log."""
    await websocket.accept()
    if agent_id not in ws_clients:
        ws_clients[agent_id] = []
    ws_clients[agent_id].append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in ws_clients.get(agent_id, []):
            ws_clients[agent_id].remove(websocket)

@app.websocket("/ws/activity/stream")
async def websocket_activity(websocket: WebSocket):
    """WebSocket cho Command Center — global activity stream."""
    await websocket.accept()
    global_ws_clients.append(websocket)
    # Gửi lịch sử gần đây ngay khi kết nối
    recent = list(activity_log)[-50:]
    for event in recent:
        await websocket.send_json({"type": "activity", "event": event})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in global_ws_clients:
            global_ws_clients.remove(websocket)

# ── Serve UI ──────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7777, log_level="warning")
