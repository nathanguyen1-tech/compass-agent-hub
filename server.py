#!/usr/bin/env python3
"""
Agent Hub — Bản chỉ huy
Server quản lý tất cả agents, live logs, approval queue
"""
import asyncio, json, os, subprocess, time, uuid
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

app = FastAPI(title="Agent Hub — Bản chỉ huy")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In-memory state
agent_processes: Dict[str, subprocess.Popen] = {}
ws_clients: Dict[str, List[WebSocket]] = {}  # agent_id → list of websockets

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

# ── API Routes ───────────────────────────────────────────────

@app.get("/api/agents")
def get_agents():
    reg = load_registry()
    # Add process status
    for a in reg["agents"]:
        pid = agent_id = a["id"]
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

    log_file = LOGS_DIR / f"{agent_id}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    update_agent_status(agent_id, "running", {"last_run": datetime.now().isoformat(), "last_log": str(log_file)})

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

        proc.wait()

    rc = proc.returncode
    status = "pending_approval" if rc == 0 else "error"
    update_agent_status(agent_id, status)
    await broadcast(agent_id, {"type": "done", "rc": rc, "status": status, "ts": datetime.now().isoformat()})

    if rc == 0:
        # Tạo approval request
        approvals = load_approvals()
        approvals.append({
            "id": str(uuid.uuid4())[:8],
            "agent_id": agent_id,
            "created_at": datetime.now().isoformat(),
            "log_file": str(log_file),
            "status": "pending"
        })
        save_approvals(approvals)

@app.post("/api/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    proc = agent_processes.get(agent_id)
    if proc and proc.poll() is None:
        proc.terminate()
        update_agent_status(agent_id, "stopped")
        await broadcast(agent_id, {"type": "stopped", "ts": datetime.now().isoformat()})
        return {"status": "stopped"}
    return {"status": "not_running"}

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
        # Trigger commit+push
        confirm_file = Path("/tmp/fb_confirm")
        confirm_file.touch()
        update_agent_status(agent_id, "done")
        await broadcast(agent_id, {"type": "approved", "ts": datetime.now().isoformat()})
    else:
        reject_file = Path("/tmp/fb_reject")
        reject_file.touch()
        update_agent_status(agent_id, "rejected")
        await broadcast(agent_id, {"type": "rejected", "ts": datetime.now().isoformat()})

    return {"status": "ok"}

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

# ── WebSocket ─────────────────────────────────────────────────

@app.websocket("/ws/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: str):
    await websocket.accept()
    if agent_id not in ws_clients:
        ws_clients[agent_id] = []
    ws_clients[agent_id].append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_clients[agent_id].remove(websocket)

# ── Serve UI ──────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7777, log_level="warning")
