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

import anthropic as _anthropic

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
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

def _parse_tool_calls_from_lines(lines: list) -> list:
    """Parse tool calls từ danh sách JSONL lines, trả về list (ts, tool_name, description)."""
    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            msg = entry.get("message", {})
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue
            ts = entry.get("timestamp") or datetime.now().isoformat()
            for c in msg.get("content", []):
                if not isinstance(c, dict) or c.get("type") != "toolCall":
                    continue
                tool_name = c.get("name", "")
                args = c.get("arguments", {})
                label_fn = TOOL_LABELS.get(tool_name)
                try:
                    description = label_fn(args) if label_fn else f"🔧 {tool_name}"
                except Exception:
                    description = f"🔧 {tool_name}"
                results.append((ts, tool_name, description))
        except Exception:
            pass
    return results


async def _watch_session_transcript(agent_id: str, oc_id: str):
    """Watch session JSONL file — tự parse tool calls và push lên activity stream.
    Khi khởi động: load 30 tool calls gần nhất để có lịch sử ngay."""
    sessions_dir = OPENCLAW_AGENTS_DIR / oc_id / "sessions"
    last_session_file = None
    last_pos = 0
    bootstrapped = False

    while True:
        await asyncio.sleep(2)
        try:
            sessions_json = sessions_dir / "sessions.json"
            if not sessions_json.exists():
                continue

            sessions_data = json.loads(sessions_json.read_text())
            session_file = None
            for v in sessions_data.values():
                if isinstance(v, dict) and v.get("sessionFile"):
                    session_file = Path(v["sessionFile"])
                    break
            if not session_file or not session_file.exists():
                continue

            if session_file != last_session_file:
                last_session_file = session_file
                bootstrapped = False

            if not bootstrapped:
                bootstrapped = True
                # Load 30 tool calls gần nhất từ lịch sử
                try:
                    all_lines = session_file.read_text().splitlines()
                    recent_calls = _parse_tool_calls_from_lines(all_lines)[-30:]
                    for (ts, tool_name, description) in recent_calls:
                        # Thêm trực tiếp vào activity_log (không broadcast WebSocket — tránh spam)
                        reg = load_registry()
                        agent = next((a for a in reg["agents"] if a["id"] == agent_id), None)
                        emoji = agent.get("emoji", "🤖") if agent else "🤖"
                        name  = agent.get("name", agent_id) if agent else agent_id
                        event = {
                            "id": str(uuid.uuid4())[:8],
                            "agent_id": agent_id,
                            "agent_name": name,
                            "agent_emoji": emoji,
                            "message": description,
                            "level": "progress",
                            "ts": ts if isinstance(ts, str) else datetime.fromtimestamp(ts/1000).isoformat()
                        }
                        # Chỉ thêm nếu chưa có trong activity_log (tránh duplicate)
                        existing_msgs = {e["message"] for e in activity_log}
                        if description not in existing_msgs:
                            activity_log.append(event)
                            _save_activity_to_disk(event)  # Persist → không mất khi navigate
                    last_pos = session_file.stat().st_size
                    print(f"[transcript] {agent_id}: loaded {len(recent_calls)} recent tool calls")
                except Exception as e:
                    last_pos = session_file.stat().st_size
                continue

            size = session_file.stat().st_size
            if size <= last_pos:
                continue

            with open(session_file) as f:
                f.seek(last_pos)
                new_lines = f.readlines()
                last_pos = f.tell()

            for (ts, tool_name, description) in _parse_tool_calls_from_lines(new_lines):
                await push_activity(agent_id, description, "progress")

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
def get_agent_activity(agent_id: str, limit: int = 150):
    """Lấy activity stream của một agent — đọc từ disk để không bao giờ mất."""
    if not ACTIVITY_FILE.exists():
        return {"events": []}
    events = []
    try:
        for line in ACTIVITY_FILE.read_text().splitlines():
            try:
                event = json.loads(line)
                if event.get("agent_id") == agent_id:
                    events.append(event)
            except Exception:
                pass
    except Exception:
        pass
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

# ── Đại Tướng Command Interface ──────────────────────────────

class GeneralCommand(BaseModel):
    message: str

def _get_empire_context() -> dict:
    """Lấy toàn bộ context của đế chế để Đại Tướng nắm tình hình."""
    reg = load_registry()
    agents = reg["agents"]
    approvals = [a for a in load_approvals() if a["status"] == "pending"]

    # Activity 24h gần nhất
    recent_events = []
    if ACTIVITY_FILE.exists():
        cutoff = datetime.now().timestamp() - 86400
        for line in ACTIVITY_FILE.read_text().splitlines()[-200:]:
            try:
                e = json.loads(line)
                ts = datetime.fromisoformat(e["ts"]).timestamp()
                if ts > cutoff:
                    recent_events.append(e)
            except:
                pass

    return {
        "agents": agents,
        "pending_approvals": approvals,
        "recent_events": recent_events[-50:],
        "now": datetime.now().isoformat()
    }

def _general_response(msg: str, ctx: dict) -> dict:
    """Đại Tướng xử lý lệnh và trả lời."""
    msg_lower = msg.lower().strip()
    agents = ctx["agents"]
    approvals = ctx["pending_approvals"]
    events = ctx["recent_events"]
    actions = []
    response_lines = []

    # ── Intent: Báo cáo tổng quan ──────────────────────────────
    report_keywords = ["tình hình", "toàn cảnh", "báo cáo", "status", "tổng quan",
                       "đang gì", "thế nào", "ra sao", "hôm nay", "today", "overview"]
    if any(k in msg_lower for k in report_keywords):
        running  = [a for a in agents if a["status"] == "running"]
        pending  = [a for a in agents if a["status"] == "pending_approval"]
        errors   = [a for a in agents if a["status"] == "error"]
        idle     = [a for a in agents if a["status"] == "idle"]

        response_lines.append(f"**Báo cáo tình hình đế chế — {datetime.now().strftime('%H:%M %d/%m')}**\n")

        if running:
            response_lines.append(f"🔵 **Đang hoạt động ({len(running)}):**")
            for a in running:
                last = next((e["message"] for e in reversed(events) if e["agent_id"] == a["id"]), "...")
                response_lines.append(f"   {a['emoji']} {a['name']}: {last}")

        if pending:
            response_lines.append(f"\n⏳ **Chờ Chủ tướng duyệt ({len(pending)}):**")
            for a in pending:
                response_lines.append(f"   {a['emoji']} {a['name']} — cần phê duyệt")

        if errors:
            response_lines.append(f"\n🔴 **Có vấn đề ({len(errors)}):**")
            for a in errors:
                response_lines.append(f"   {a['emoji']} {a['name']} — lỗi lần chạy cuối")

        response_lines.append(f"\n⚪ **Nghỉ ngơi:** {len(idle)} tướng")

        # Tóm tắt 24h
        today_success = len([e for e in events if e["level"] == "success"])
        today_error   = len([e for e in events if e["level"] == "error"])
        response_lines.append(f"\n📊 **24h qua:** {today_success} thành công · {today_error} lỗi · {len(events)} hoạt động")

        if not running and not pending and not errors:
            response_lines.append("\n✅ **Toàn bộ đế chế đang ổn định.**")

    # ── Intent: Chạy agent ─────────────────────────────────────
    elif any(k in msg_lower for k in ["chạy", "run", "kích hoạt", "trigger", "thực thi"]):
        target = None
        for a in agents:
            if a["name"].lower() in msg_lower or a["id"].lower() in msg_lower:
                target = a
                break
        # Nhận diện theo từ khoá
        if not target:
            if any(k in msg_lower for k in ["health", "kiểm tra", "check"]):
                target = next((a for a in agents if "health" in a["id"]), None)
            elif any(k in msg_lower for k in ["feedback", "bác sĩ", "góp ý"]):
                target = next((a for a in agents if "feedback" in a["id"] and a.get("script")), None)

        if target:
            if not target.get("script"):
                response_lines.append(f"⚠️ **{target['name']}** là chat-based agent — không thể trigger qua nút Run.")
                response_lines.append(f"💬 Hãy nhắn tin trực tiếp với {target['name']} để giao nhiệm vụ.")
            elif target["status"] == "running":
                response_lines.append(f"🔵 **{target['name']}** đang chạy rồi, Chủ tướng.")
            else:
                actions.append({"type": "run", "agent_id": target["id"]})
                response_lines.append(f"✅ Đã kích hoạt **{target['emoji']} {target['name']}**.")
                response_lines.append(f"📡 Theo dõi tiến trình trên Activity Stream.")
        else:
            response_lines.append("❓ Chủ tướng muốn kích hoạt tướng nào? Các tướng hiện có:")
            for a in agents:
                response_lines.append(f"   {a['emoji']} {a['name']}")

    # ── Intent: Duyệt ──────────────────────────────────────────
    elif any(k in msg_lower for k in ["duyệt", "approve", "ok", "đồng ý", "cho phép", "xác nhận"]):
        if not approvals:
            response_lines.append("✅ Không có gì cần duyệt lúc này, Chủ tướng.")
        else:
            for appr in approvals:
                actions.append({"type": "approve", "approval_id": appr["id"]})
                agent = next((a for a in agents if a["id"] == appr["agent_id"]), {})
                response_lines.append(f"✅ Đã duyệt: **{agent.get('emoji','')} {agent.get('name', appr['agent_id'])}**")
            response_lines.append("📦 Đang commit & push...")

    # ── Intent: Từ chối ────────────────────────────────────────
    elif any(k in msg_lower for k in ["từ chối", "reject", "không duyệt", "cancel", "huỷ"]):
        if not approvals:
            response_lines.append("✅ Không có gì để từ chối.")
        else:
            for appr in approvals:
                actions.append({"type": "reject", "approval_id": appr["id"]})
                agent = next((a for a in agents if a["id"] == appr["agent_id"]), {})
                response_lines.append(f"❌ Đã từ chối: **{agent.get('emoji','')} {agent.get('name', appr['agent_id'])}**")

    # ── Intent: Dừng agent ─────────────────────────────────────
    elif any(k in msg_lower for k in ["dừng", "stop", "tạm dừng", "halt"]):
        running_agents = [a for a in agents if a["status"] == "running"]
        if not running_agents:
            response_lines.append("⚪ Không có tướng nào đang chạy để dừng.")
        else:
            for a in running_agents:
                if a["name"].lower() in msg_lower or a["id"] in msg_lower or "tất cả" in msg_lower or "all" in msg_lower:
                    actions.append({"type": "stop", "agent_id": a["id"]})
                    response_lines.append(f"⏹ Đã dừng: **{a['emoji']} {a['name']}**")
            if not actions:
                response_lines.append("❓ Dừng tướng nào, Chủ tướng? Đang chạy:")
                for a in running_agents:
                    response_lines.append(f"   {a['emoji']} {a['name']}")

    # ── Intent: Danh sách tướng ────────────────────────────────
    elif any(k in msg_lower for k in ["danh sách", "list", "tướng", "agent", "có những ai", "có ai"]):
        response_lines.append(f"**Quân đội hiện có ({len(agents)} tướng):**\n")
        status_labels = {
            "running": "🔵 đang chạy", "idle": "⚪ nghỉ",
            "pending_approval": "⏳ chờ duyệt", "error": "🔴 lỗi",
            "done": "✅ xong", "rejected": "❌ bị từ chối"
        }
        for a in agents:
            status = status_labels.get(a["status"], a["status"])
            last_run = f" · lần cuối {a['last_run'][:10]}" if a.get("last_run") else ""
            response_lines.append(f"{a['emoji']} **{a['name']}** — {status}{last_run}")
            response_lines.append(f"   _{a['description']}_")

    # ── Default: Không hiểu ────────────────────────────────────
    else:
        response_lines.append("**Đại Tướng nghe, Chủ tướng.**")
        response_lines.append("\nTôi có thể:")
        response_lines.append("• **Báo cáo tình hình** — \"Tình hình thế nào?\" / \"Báo cáo hôm nay\"")
        response_lines.append("• **Kích hoạt tướng** — \"Chạy Health Check\" / \"Kích hoạt FeedbackBot\"")
        response_lines.append("• **Phê duyệt** — \"Duyệt\" / \"Approve tất cả\"")
        response_lines.append("• **Từ chối** — \"Từ chối\" / \"Reject\"")
        response_lines.append("• **Dừng** — \"Dừng Health Check\"")
        response_lines.append("• **Xem quân đội** — \"Danh sách tướng\"")

    return {
        "response": "\n".join(response_lines),
        "actions": actions
    }

@app.post("/api/general/command")
async def general_command(cmd: GeneralCommand, background_tasks: BackgroundTasks):
    """Đại Tướng nhận lệnh từ Chủ tướng và thực thi."""
    ctx = _get_empire_context()
    result = _general_response(cmd.message, ctx)

    # Thực thi actions
    executed = []
    for action in result["actions"]:
        try:
            if action["type"] == "run":
                agent_id = action["agent_id"]
                reg = load_registry()
                agent = next((a for a in reg["agents"] if a["id"] == agent_id), None)
                if agent and agent.get("script"):
                    log_file = LOGS_DIR / f"{agent_id}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                    update_agent_status(agent_id, "running", {
                        "last_run": datetime.now().isoformat(), "last_log": str(log_file)
                    })
                    await push_activity(agent_id, f"🚀 Lệnh từ Chủ tướng: bắt đầu chạy", "info")
                    background_tasks.add_task(_run_agent_bg, agent_id, agent["script"], [], log_file)
                    executed.append(f"run:{agent_id}")

            elif action["type"] == "approve":
                appr_id = action["approval_id"]
                approvals = load_approvals()
                appr = next((a for a in approvals if a["id"] == appr_id), None)
                if appr:
                    appr["status"] = "approved"
                    appr["resolved_at"] = datetime.now().isoformat()
                    save_approvals(approvals)
                    Path("/tmp/fb_confirm").touch()
                    update_agent_status(appr["agent_id"], "done")
                    await push_activity(appr["agent_id"], "✅ Chủ tướng đã phê duyệt", "success")
                    executed.append(f"approve:{appr_id}")

            elif action["type"] == "reject":
                appr_id = action["approval_id"]
                approvals = load_approvals()
                appr = next((a for a in approvals if a["id"] == appr_id), None)
                if appr:
                    appr["status"] = "rejected"
                    appr["resolved_at"] = datetime.now().isoformat()
                    save_approvals(approvals)
                    Path("/tmp/fb_reject").touch()
                    update_agent_status(appr["agent_id"], "rejected")
                    await push_activity(appr["agent_id"], "❌ Chủ tướng từ chối", "error")
                    executed.append(f"reject:{appr_id}")

            elif action["type"] == "stop":
                agent_id = action["agent_id"]
                proc = agent_processes.get(agent_id)
                if proc and proc.poll() is None:
                    proc.terminate()
                    update_agent_status(agent_id, "stopped")
                    await push_activity(agent_id, "⏹ Bị Chủ tướng dừng", "warning")
                    executed.append(f"stop:{agent_id}")

        except Exception as e:
            pass

    return {"response": result["response"], "executed": executed}


# ── Đại Tướng AI Chat (Streaming) ────────────────────────────

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

GENERAL_SYSTEM_PROMPT = """Mày là Đại Tướng Nathan-Ubu — Tổng chỉ huy đội quân AI của Chủ tướng.

Tính cách:
- Trung thành, mạnh mẽ, nói chuyện ngắn gọn nhưng đủ ý
- Xưng "thần", gọi người dùng là "Chủ tướng"
- Dùng tiếng Việt tự nhiên, không cứng nhắc
- Khi báo cáo: ngắn gọn, bullet points, emoji phù hợp
- Khi nhận lệnh: xác nhận rõ ràng rồi báo mày sẽ làm gì

Khả năng thực thi (khi Chủ tướng ra lệnh, thêm tag vào cuối response):
- Kích hoạt agent: [ACTION:run:<agent_id>]
- Duyệt approval: [ACTION:approve:all] hoặc [ACTION:approve:<id>]
- Từ chối: [ACTION:reject:all]
- Dừng agent: [ACTION:stop:<agent_id>]

Ví dụ: "Thần đã kích hoạt Health Check. [ACTION:run:health-check]"
Tags này sẽ được hệ thống xử lý, Chủ tướng sẽ không nhìn thấy.

THÔNG TIN ĐẾ CHẾ HIỆN TẠI:
{empire_context}
"""

def _build_system_prompt() -> str:
    ctx = _get_empire_context()
    agents = ctx["agents"]
    approvals = ctx["pending_approvals"]
    events = ctx["recent_events"]

    lines = []
    lines.append(f"Thời gian: {datetime.now().strftime('%H:%M %d/%m/%Y')}\n")

    lines.append("=== QUÂN ĐỘI ===")
    for a in agents:
        lines.append(f"- {a['emoji']} {a['name']} (id: {a['id']}) — status: {a['status']} — {a['description']}")

    lines.append(f"\n=== CHỜ DUYỆT ({len(approvals)}) ===")
    for ap in approvals:
        lines.append(f"- id:{ap['id']} agent:{ap['agent_id']} created:{ap.get('created_at','?')[:16]}")

    lines.append(f"\n=== HOẠT ĐỘNG GẦN ĐÂY (24h, {len(events)} sự kiện) ===")
    for e in events[-20:]:
        ts = e['ts'][11:16] if len(e['ts']) > 16 else e['ts']
        lines.append(f"- [{ts}] {e['agent_id']}: {e['message']}")

    empire_str = "\n".join(lines)
    return GENERAL_SYSTEM_PROMPT.replace("{empire_context}", empire_str)


async def _execute_action_tags(raw_response: str, background_tasks: BackgroundTasks) -> list:
    """Parse [ACTION:...] tags từ response và thực thi."""
    import re
    executed = []
    tags = re.findall(r'\[ACTION:(\w+):([^\]]+)\]', raw_response)

    for action_type, action_arg in tags:
        try:
            if action_type == "run":
                agent_id = action_arg
                reg = load_registry()
                agent = next((a for a in reg["agents"] if a["id"] == agent_id), None)
                if agent and agent.get("script"):
                    log_file = LOGS_DIR / f"{agent_id}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                    update_agent_status(agent_id, "running", {
                        "last_run": datetime.now().isoformat(), "last_log": str(log_file)
                    })
                    await push_activity(agent_id, "🚀 Lệnh từ Đại Tướng: bắt đầu chạy", "info")
                    background_tasks.add_task(_run_agent_bg, agent_id, agent["script"], [], log_file)
                    executed.append(f"run:{agent_id}")

            elif action_type == "approve":
                approvals = load_approvals()
                targets = [a for a in approvals if a["status"] == "pending"] if action_arg == "all" \
                          else [a for a in approvals if a["id"] == action_arg]
                for appr in targets:
                    appr["status"] = "approved"
                    appr["resolved_at"] = datetime.now().isoformat()
                    Path("/tmp/fb_confirm").touch()
                    update_agent_status(appr["agent_id"], "done")
                    await push_activity(appr["agent_id"], "✅ Đại Tướng phê duyệt theo lệnh Chủ tướng", "success")
                    executed.append(f"approve:{appr['id']}")
                save_approvals(approvals)

            elif action_type == "reject":
                approvals = load_approvals()
                targets = [a for a in approvals if a["status"] == "pending"] if action_arg == "all" \
                          else [a for a in approvals if a["id"] == action_arg]
                for appr in targets:
                    appr["status"] = "rejected"
                    appr["resolved_at"] = datetime.now().isoformat()
                    Path("/tmp/fb_reject").touch()
                    update_agent_status(appr["agent_id"], "rejected")
                    await push_activity(appr["agent_id"], "❌ Bị từ chối theo lệnh Chủ tướng", "error")
                    executed.append(f"reject:{appr['id']}")
                save_approvals(approvals)

            elif action_type == "stop":
                agent_id = action_arg
                proc = agent_processes.get(agent_id)
                if proc and proc.poll() is None:
                    proc.terminate()
                    update_agent_status(agent_id, "stopped")
                    await push_activity(agent_id, "⏹ Dừng theo lệnh Chủ tướng", "warning")
                    executed.append(f"stop:{agent_id}")
        except Exception as e:
            print(f"[general] Action error {action_type}:{action_arg}: {e}")

    return executed


_CLAUDE_CREDS = Path.home() / ".claude" / ".credentials.json"
_ANTHROPIC_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
_OAUTH_REFRESH_URL   = "https://console.anthropic.com/v1/oauth/token"
_token_cache: dict = {}   # {"token": str, "expires_at": float}


def _refresh_oauth_token(refresh_token: str) -> str:
    """Refresh Claude OAuth access token, cập nhật credentials file."""
    import urllib.request, urllib.parse
    data = urllib.parse.urlencode({
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
        "client_id":     _ANTHROPIC_CLIENT_ID,
    }).encode()
    req = urllib.request.Request(_OAUTH_REFRESH_URL, data=data,
                                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
        new_token  = resp["access_token"]
        expires_in = int(resp.get("expires_in", 28800))
        # Lưu lại credentials
        if _CLAUDE_CREDS.exists():
            creds = json.loads(_CLAUDE_CREDS.read_text())
            creds.setdefault("claudeAiOauth", {})["accessToken"] = new_token
            if "refresh_token" in resp:
                creds["claudeAiOauth"]["refreshToken"] = resp["refresh_token"]
            _CLAUDE_CREDS.write_text(json.dumps(creds, indent=2))
        import time
        _token_cache["token"]      = new_token
        _token_cache["expires_at"] = time.time() + expires_in - 300  # 5-min buffer
        return new_token
    except Exception as e:
        print(f"[oauth] Refresh failed: {e}")
        return ""


def _get_anthropic_key() -> str:
    """Lấy Anthropic access token — tự refresh nếu hết hạn."""
    import time
    # 1. Env var (API key thật)
    if key := os.environ.get("ANTHROPIC_API_KEY", ""):
        return key
    # 2. Cache còn hạn
    if _token_cache.get("token") and time.time() < _token_cache.get("expires_at", 0):
        return _token_cache["token"]
    # 3. Đọc credentials file
    if not _CLAUDE_CREDS.exists():
        return ""
    try:
        creds  = json.loads(_CLAUDE_CREDS.read_text())
        oauth  = creds.get("claudeAiOauth", {})
        token  = oauth.get("accessToken", "")
        expiry = oauth.get("expiresAt", 0)  # milliseconds
        # Token còn hạn (> 5 phút)
        if token and time.time() < (expiry / 1000) - 300:
            _token_cache["token"]      = token
            _token_cache["expires_at"] = (expiry / 1000) - 300
            return token
        # Cần refresh
        if refresh := oauth.get("refreshToken", ""):
            return _refresh_oauth_token(refresh)
    except Exception as e:
        print(f"[oauth] Read creds failed: {e}")
    return ""


@app.post("/api/general/chat")
async def general_chat_stream(req: ChatRequest, background_tasks: BackgroundTasks):
    """Đại Tướng Nathan-Ubu — bridge tới OpenClaw main agent."""
    import re, asyncio

    # Lấy tin nhắn cuối từ user
    user_msg = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    if not user_msg:
        async def _empty():
            yield "data: " + json.dumps({"type": "error", "text": "❌ Không có tin nhắn."}) + "\n\n"
        return StreamingResponse(_empty(), media_type="text/event-stream")

    # Build prompt cho main agent — inject context đế chế
    ctx        = _get_empire_context()
    agents     = ctx["agents"]
    approvals  = ctx["pending_approvals"]
    events     = ctx["recent_events"]

    ctx_lines  = [f"[Thời gian: {datetime.now().strftime('%H:%M %d/%m/%Y')}]"]
    army_str = ', '.join(f"{a['emoji']}{a['name']}({a['status']})" for a in agents)
    ctx_lines += [f"[Quân đội: {army_str}]"]
    if approvals:
        ctx_lines += [f"[Chờ duyệt: {len(approvals)} mục]"]
    if events:
        recent = events[-5:]
        ctx_lines += ["[Gần đây: " + " | ".join(f"{e['agent_id']}:{e['message'][:40]}" for e in recent) + "]"]

    # Kết hợp context + lệnh Chủ tướng
    full_prompt = (
        "Mày là Đại Tướng Nathan-Ubu, tổng chỉ huy đội quân AI của Chủ tướng.\n"
        "Xưng 'thần', gọi người dùng là 'Chủ tướng'. Ngắn gọn, xúc tích.\n"
        "Nếu Chủ tướng ra lệnh chạy/duyệt/dừng agent, thêm tag [ACTION:run:<id>] / [ACTION:approve:all] / [ACTION:stop:<id>] vào cuối.\n\n"
        + "\n".join(ctx_lines) + "\n\n"
        f"Chủ tướng: {user_msg}"
    )

    async def _stream():
        import shutil
        openclaw_bin = shutil.which("openclaw") or "/home/nathan-ubutu/.npm-global/bin/openclaw"
        proc = await asyncio.create_subprocess_exec(
            openclaw_bin, "agent", "--agent", "main", "--message", full_prompt, "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PATH": os.environ.get("PATH","") + ":/home/nathan-ubutu/.npm-global/bin:/usr/local/bin"}
        )
        stdout, stderr = await proc.communicate()
        raw = stdout.decode("utf-8", errors="replace").strip()

        try:
            data = json.loads(raw)
            # Lấy text từ payloads
            payloads = data.get("result", {}).get("payloads", [])
            full_text = "\n".join(p.get("text", "") for p in payloads if p.get("text"))

            if not full_text:
                full_text = data.get("error") or "❌ Đại Tướng không phản hồi."

            # Stream từng chunk nhỏ (giả lập streaming)
            visible = re.sub(r'\[ACTION:[^\]]+\]', '', full_text)
            chunk_size = 8
            for i in range(0, len(visible), chunk_size):
                yield "data: " + json.dumps({"type": "delta", "text": visible[i:i+chunk_size]}) + "\n\n"
                await asyncio.sleep(0.01)

            # Thực thi actions
            executed = await _execute_action_tags(full_text, background_tasks)
            yield "data: " + json.dumps({"type": "done", "executed": executed}) + "\n\n"

        except json.JSONDecodeError:
            # Raw text nếu JSON fail
            err_text = stderr.decode("utf-8", errors="replace")[:200]
            yield "data: " + json.dumps({
                "type": "error",
                "text": f"❌ Lỗi gateway: {err_text or raw[:200]}"
            }) + "\n\n"
        except Exception as e:
            yield "data: " + json.dumps({"type": "error", "text": f"❌ {str(e)}"}) + "\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
