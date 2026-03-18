"""
Agent Hub v2 — Professional Edition
FastAPI backend: modular, SQLite, extensible.
"""
import asyncio, json, os, subprocess
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.database import init_db
from app.core.events import push_activity, ws_clients
from app.core.registry import get_agents, update_status, seed_from_json
from app.api import agents, approvals, activity, general

BASE = Path(__file__).parent.parent

# ── Watchers ──────────────────────────────────────────────────

LOGS_DIR = BASE / "logs"
TMP_LOG_PATTERN = "/tmp/hub-{agent_id}.log"
OPENCLAW_AGENTS_DIR = Path.home() / ".openclaw" / "agents"
SESSION_ACTIVE_THRESHOLD_SEC = 180
TOOL_LABELS = {
    "exec": "🖥️ Chạy", "Edit": "✏️ Sửa", "Write": "📝 Viết",
    "Read": "📖 Đọc", "web_search": "🔍 Tìm kiếm", "web_fetch": "🌐 Fetch",
    "memory_search": "🧠 Memory", "browser": "🌐 Browser",
    "sessions_send": "📨 Gửi session", "sessions_spawn": "🚀 Spawn",
}

_log_positions: dict  = {}
_session_cache: dict  = {}
_transcript_pos: dict = {}


async def _watch_all_logs():
    """Poll /tmp/hub-<id>.log cho tất cả agents."""
    while True:
        for agent in get_agents():
            log_path = Path(TMP_LOG_PATTERN.format(agent_id=agent.id))
            if not log_path.exists():
                continue
            pos = _log_positions.get(agent.id, 0)
            try:
                size = log_path.stat().st_size
                if size <= pos:
                    continue
                with open(log_path, "r", errors="replace") as f:
                    f.seek(pos)
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            evt = json.loads(line)
                            await push_activity(agent.id, evt.get("message",""), evt.get("level","info"))
                        except:
                            await push_activity(agent.id, line[:200], "info")
                _log_positions[agent.id] = log_path.stat().st_size
            except:
                pass
        await asyncio.sleep(0.5)


async def _watch_agent_sessions():
    """Detect chat-based agent activity qua sessions.json updatedAt."""
    import time
    while True:
        for agent in get_agents():
            oc_id = agent.openclaw_agent_id
            if not oc_id:
                continue
            sess_file = OPENCLAW_AGENTS_DIR / oc_id / "sessions" / "sessions.json"
            if not sess_file.exists():
                continue
            try:
                data = json.loads(sess_file.read_text())
                sessions = data if isinstance(data, list) else data.get("sessions", [])
                latest = max((s.get("updatedAt", 0) for s in sessions), default=0)
                age = time.time() - (latest / 1000)
                was_running = _session_cache.get(oc_id) == "running"
                is_running = age < SESSION_ACTIVE_THRESHOLD_SEC

                if is_running and not was_running:
                    update_status(agent.id, "running")
                    await push_activity(agent.id, "🟢 Agent đang hoạt động", "info")
                elif not is_running and was_running:
                    cur = get_agents()
                    cur_agent = next((a for a in cur if a.id == agent.id), None)
                    if cur_agent and cur_agent.status == "running":
                        update_status(agent.id, "idle")

                _session_cache[oc_id] = "running" if is_running else "idle"
            except:
                pass
        await asyncio.sleep(5)


async def _watch_transcripts():
    """Parse tool calls từ session JSONL → push lên activity stream."""
    while True:
        for agent in get_agents():
            oc_id = agent.openclaw_agent_id
            if not oc_id:
                continue
            sess_file = OPENCLAW_AGENTS_DIR / oc_id / "sessions" / "sessions.json"
            if not sess_file.exists():
                continue
            try:
                data = json.loads(sess_file.read_text())
                sessions = data if isinstance(data, list) else data.get("sessions", [])
                if not sessions:
                    continue
                sess = max(sessions, key=lambda s: s.get("updatedAt", 0))
                sf = sess.get("sessionFile") or sess.get("file")
                if not sf:
                    continue
                sf_path = Path(sf) if Path(sf).is_absolute() else OPENCLAW_AGENTS_DIR / oc_id / "sessions" / sf
                if not sf_path.exists():
                    continue
                pos = _transcript_pos.get(sf, 0)
                size = sf_path.stat().st_size
                if size <= pos:
                    _transcript_pos[sf] = size
                    continue
                with open(sf_path, "r", errors="replace") as f:
                    f.seek(pos)
                    for line in f:
                        try:
                            entry = json.loads(line)
                            msg = entry.get("message", {})
                            if msg.get("role") == "assistant":
                                for block in msg.get("content", []):
                                    if block.get("type") == "toolCall":
                                        tool_name = block.get("name", "")
                                        label = TOOL_LABELS.get(tool_name, f"🔧 {tool_name}")
                                        args = block.get("arguments", {})
                                        detail = args.get("command") or args.get("file_path") or args.get("query", "")
                                        msg_text = f"{label}: {str(detail)[:80]}" if detail else label
                                        await push_activity(agent.id, msg_text, "progress")
                        except:
                            pass
                _transcript_pos[sf] = sf_path.stat().st_size
            except:
                pass
        await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    init_db()

    # Migrate từ JSON nếu SQLite còn rỗng
    registry_json = BASE / "registry.json"
    if registry_json.exists():
        seed_from_json(registry_json)

    # Reset running agents về idle
    for a in get_agents():
        if a.status == "running":
            update_status(a.id, "idle")

    # Start watchers
    asyncio.create_task(_watch_all_logs())
    asyncio.create_task(_watch_agent_sessions())
    asyncio.create_task(_watch_transcripts())
    print("[v2] Agent Hub v2 started ✅")
    yield
    print("[v2] Shutting down...")


# ── App ───────────────────────────────────────────────────────

app = FastAPI(title="Agent Hub v2", lifespan=lifespan)

# API routers
app.include_router(agents.router)
app.include_router(approvals.router)
app.include_router(activity.router)
app.include_router(general.router)


# ── WebSocket ─────────────────────────────────────────────────

@app.websocket("/ws/activity/stream")
async def ws_activity(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        try: ws_clients.remove(websocket)
        except: pass


# ── Static files / SPA ───────────────────────────────────────

STATIC_DIR = BASE / "frontend" / "dist"
LEGACY_STATIC = BASE / "static"

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    async def root():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        f = STATIC_DIR / path
        return FileResponse(f) if f.exists() else FileResponse(STATIC_DIR / "index.html")

elif LEGACY_STATIC.exists():
    # Fallback sang static cũ trong lúc React chưa build xong
    app.mount("/static", StaticFiles(directory=LEGACY_STATIC), name="static")

    @app.get("/")
    async def root_legacy():
        return FileResponse(LEGACY_STATIC / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=7777, reload=True)
