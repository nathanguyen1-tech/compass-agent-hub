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
ACTIVITY_FILE = BASE / "activity.jsonl"   # Persistent activity log
LOGS_DIR.mkdir(exist_ok=True)

# ── Startup / Lifespan ───────────────────────────────────────

OPENCLAW_AGENTS_DIR = Path.home() / ".openclaw" / "agents"
# agent_id → last known updatedAt (ms)
_session_last_updated: Dict[str, int] = {}
# agent_id → whether session was "active" last check
_session_was_active: Dict[str, bool] = {}
# Ngưỡng: < N giây → coi là đang hoạt động
SESSION_ACTIVE_THRESHOLD_SEC = 180   # 3 phút — vừa phản hồi xong


async def _watch_agent_sessions():
    """Tự động detect khi chat-based agent đang hoạt động.
    Dùng 2 tín hiệu:
      1. File .lock tồn tại  → đang xử lý ngay lúc này (real-time)
      2. updatedAt < 3 phút  → vừa hoạt động gần đây
    """
    while True:
        await asyncio.sleep(5)
        try:
            reg = load_registry()
            now_ms = int(time.time() * 1000)
            for a in reg["agents"]:
                oc_id = a.get("openclaw_agent_id")
                if not oc_id:
                    continue
                agent_id = a["id"]
                sessions_dir = OPENCLAW_AGENTS_DIR / oc_id / "sessions"
                sessions_file = sessions_dir / "sessions.json"
                if not sessions_file.exists():
                    continue
                try:
                    sessions_data = json.loads(sessions_file.read_text())
                    latest_updated = max(
                        (v.get("updatedAt", 0) for v in sessions_data.values() if isinstance(v, dict)),
                        default=0
                    )
                    age_sec = (now_ms - latest_updated) / 1000

                    # Kiểm tra file .lock — đang xử lý ngay lúc này
                    lock_files = list(sessions_dir.glob("*.lock"))
                    is_processing = len(lock_files) > 0

                    # Đang chạy nếu: có lock file HOẶC vừa cập nhật < 3 phút
                    is_active = is_processing or (age_sec < SESSION_ACTIVE_THRESHOLD_SEC)

                    last_updated = _session_last_updated.get(agent_id, 0)
                    was_active   = _session_was_active.get(agent_id, False)

                    if is_active:
                        if not was_active:
                            # Vừa bắt đầu hoạt động
                            _session_was_active[agent_id] = True
                            _session_last_updated[agent_id] = latest_updated
                            current = next((x for x in reg["agents"] if x["id"] == agent_id), {})
                            if current.get("status") not in ("pending_approval", "done"):
                                update_agent_status(agent_id, "running")
                            status_msg = "🔄 Đang xử lý..." if is_processing else "💬 Vừa hoạt động"
                            await push_activity(agent_id, status_msg, "progress" if is_processing else "info")
                        elif is_processing and latest_updated > last_updated:
                            # Có response mới trong khi đang chạy
                            _session_last_updated[agent_id] = latest_updated
                            await push_activity(agent_id, "🔄 Đang xử lý...", "progress")
                    else:
                        if was_active:
                            # Vừa ngừng hoạt động
                            _session_was_active[agent_id] = False
                            current = next((x for x in reg["agents"] if x["id"] == agent_id), {})
                            if current.get("status") == "running":
                                update_agent_status(agent_id, "idle")
                                await push_activity(agent_id, "⚪ Agent đã nghỉ", "info")

                except Exception:
                    pass
        except Exception:
            pass


# Map tool name → mô tả human-readable
TOOL_LABELS = {
    "exec":          lambda a: f"🖥️ Chạy: {a.get('command','')[:80]}",
    "Edit":          lambda a: f"✏️ Sửa file: {Path(a.get('file_path') or a.get('path','')).name}",
    "Write":         lambda a: f"📝 Ghi file: {Path(a.get('file_path') or a.get('path','')).name}",
    "Read":          lambda a: f"📖 Đọc file: {Path(a.get('file_path') or a.get('path','')).name}",
    "web_search":    lambda a: f"🔍 Tìm kiếm: {a.get('query','')}",
    "web_fetch":     lambda a: f"🌐 Fetch: {a.get('url','')}",
    "memory_search": lambda a: f"🧠 Tìm memory: {a.get('query','')}",
    "memory_get":    lambda a: f"🧠 Đọc memory: {a.get('path','')}",
    "browser":       lambda a: f"🌐 Browser: {a.get('action','')} {a.get('url','')}",
    "sessions_list": lambda a: "📋 Kiểm tra sessions",
    "sessions_send": lambda a: f"📨 Gửi message",
}

async def _watch_session_transcript(agent_id: str, oc_id: str):
    """Watch session JSONL file — tự parse tool calls và push lên activity stream."""
    sessions_dir = OPENCLAW_AGENTS_DIR / oc_id / "sessions"
    last_session_file = None
    last_pos = 0

    while True:
        await asyncio.sleep(2)
        try:
            sessions_json = sessions_dir / "sessions.json"
            if not sessions_json.exists():
                continue

            # Lấy session file hiện tại
            sessions_data = json.loads(sessions_json.read_text())
            session_file = None
            for v in sessions_data.values():
                if isinstance(v, dict) and v.get("sessionFile"):
                    session_file = Path(v["sessionFile"])
                    break
            if not session_file or not session_file.exists():
                continue

            # Reset nếu session file thay đổi
            if session_file != last_session_file:
                last_session_file = session_file
                last_pos = session_file.stat().st_size  # Chỉ đọc từ đây trở đi (bỏ qua lịch sử)

            size = session_file.stat().st_size
            if size <= last_pos:
                continue

            with open(session_file) as f:
                f.seek(last_pos)
                new_lines = f.readlines()
                last_pos = f.tell()

            for line in new_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    msg = entry.get("message", {})
                    if not isinstance(msg, dict):
                        continue
                    if msg.get("role") != "assistant":
                        continue
                    for c in msg.get("content", []):
                        if not isinstance(c, dict) or c.get("type") != "toolCall":
                            continue
                        tool_name = c.get("name", "")
                        args = c.get("arguments", {})
                        label_fn = TOOL_LABELS.get(tool_name)
                        if label_fn:
                            try:
                                description = label_fn(args)
                            except Exception:
                                description = f"🔧 {tool_name}"
                        else:
                            description = f"🔧 {tool_name}"
                        await push_activity(agent_id, description, "progress")
                except Exception:
                    pass
        except Exception:
            pass


async def _watch_all_logs():
    """Single loop watch /tmp/hub-<agent_id>.log cho MỌI agent trong registry.
    Tự động pick up agent mới mà không cần restart server."""
    positions: Dict[str, int] = {}   # agent_id → file position

    while True:
        await asyncio.sleep(0.5)
        try:
            reg = load_registry()
            for a in reg["agents"]:
                agent_id = a["id"]
                log_path = Path(f"/tmp/hub-{agent_id}.log")
                if not log_path.exists():
                    positions[agent_id] = 0
                    continue
                size = log_path.stat().st_size
                last_pos = positions.get(agent_id, 0)
                # File bị reset (agent chạy lại)
                if size < last_pos:
                    last_pos = 0
                if size == last_pos:
                    continue
                with open(log_path) as f:
                    f.seek(last_pos)
                    new_lines = f.readlines()
                    positions[agent_id] = f.tell()
                for line in new_lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data  = json.loads(line)
                        msg   = data.get("message", line)
                        level = data.get("level", "info")
                    except json.JSONDecodeError:
                        msg, level = line, "info"
                    await push_activity(agent_id, msg, level)
                    # Cũng broadcast vào per-agent WebSocket để Live Log tab nhận được
                    await broadcast(agent_id, {
                        "type": "log",
                        "line": f"[{level.upper()}] {msg}",
                        "ts": datetime.now().isoformat()
                    })
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Reset status stale
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

    # Load activity log từ disk (tồn tại qua restart)
    _load_activity_from_disk()

    # Một loop duy nhất watch log files của TẤT CẢ agent (kể cả agent mới thêm sau)
    asyncio.create_task(_watch_all_logs())
    print("[watcher] Log watcher khởi động (dynamic — tự pick up agent mới)")

    # Session watcher — detect chat-based agents đang hoạt động
    asyncio.create_task(_watch_agent_sessions())
    print("[watcher] Session watcher khởi động (dynamic)")

    # Transcript watcher — parse tool calls từ session file → hiện lên log
    try:
        reg = load_registry()
        for a in reg["agents"]:
            oc_id = a.get("openclaw_agent_id")
            if oc_id:
                asyncio.create_task(_watch_session_transcript(a["id"], oc_id))
                print(f"[watcher] Transcript watcher: {a['id']} → {oc_id}")
    except Exception as e:
        print(f"[startup] Lỗi transcript watcher: {e}")

    yield


app = FastAPI(title="Agent Hub — Bản chỉ huy", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In-memory state
agent_processes: Dict[str, subprocess.Popen] = {}
ws_clients: Dict[str, List[WebSocket]] = {}        # agent_id → websockets
global_ws_clients: List[WebSocket] = []             # command center clients
activity_log: deque = deque(maxlen=500)             # global activity feed (in-memory)

def _load_activity_from_disk():
    """Load activity log từ file khi server khởi động."""
    if not ACTIVITY_FILE.exists():
        return
    try:
        lines = ACTIVITY_FILE.read_text().strip().splitlines()
        for line in lines[-500:]:   # chỉ load 500 dòng gần nhất
            try:
                activity_log.append(json.loads(line))
            except Exception:
                pass
        print(f"[startup] Loaded {len(activity_log)} activity events từ disk")
    except Exception as e:
        print(f"[startup] Lỗi load activity: {e}")

def _save_activity_to_disk(event: dict):
    """Append một event mới vào file."""
    try:
        with open(ACTIVITY_FILE, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        # Giới hạn file 2000 dòng
        lines = ACTIVITY_FILE.read_text().splitlines()
        if len(lines) > 2000:
            ACTIVITY_FILE.write_text("\n".join(lines[-2000:]) + "\n")
    except Exception:
        pass

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
    _save_activity_to_disk(event)   # Persist xuống disk

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

@app.get("/api/agents/{agent_id}/activity")
def get_agent_activity(agent_id: str, limit: int = 100):
    """Lấy activity stream của một agent cụ thể."""
    events = [e for e in activity_log if e["agent_id"] == agent_id]
    return {"events": events[-limit:]}

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

class NewAgent(BaseModel):
    id: str
    name: str
    emoji: str = "🤖"
    rank: str = "Tướng lĩnh"
    description: str = ""
    workspace: str = ""
    script: str = ""
    trigger: str = "manual"
    requires_approval: bool = True
    openclaw_agent_id: str = ""
    tags: List[str] = []

@app.post("/api/agents")
async def register_agent(agent: NewAgent):
    reg = load_registry()
    # Kiểm tra trùng ID
    if any(a["id"] == agent.id for a in reg["agents"]):
        raise HTTPException(400, f"Agent ID '{agent.id}' đã tồn tại")
    new_entry = {**agent.dict(), "status": "idle", "last_run": None, "last_log": None}
    reg["agents"].append(new_entry)
    save_registry(reg)
    # Push activity để thông báo lên stream
    await push_activity(agent.id, f"✨ Agent mới được đăng ký: {agent.name}", "success")
    return {"status": "registered", "agent": new_entry}

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
