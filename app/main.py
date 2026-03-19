"""
Agent Hub v3 — Multi-Agent Edition
FastAPI backend: modular, SQLite, 4-phase upgrade.
"""
import asyncio, json, os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.database import init_db
from app.core.events import push_activity, ws_clients
from app.core.registry import get_agents, update_status, seed_from_json
from app.core.discovery import sync_agents_from_config
from app.core.sessions import sync_session_snapshots
from app.core.message_bus import handle_tool_call
from app.api import agents, approvals, activity, general, topology

BASE             = Path(__file__).parent.parent
OPENCLAW_AGENTS  = Path.home() / ".openclaw" / "agents"

# ── Constants ─────────────────────────────────────────────────
SESSION_ACTIVE_SEC = 180
TOOL_LABELS = {
    "exec":           "🖥️ Chạy lệnh",
    "Edit":           "✏️ Sửa file",
    "Write":          "📝 Viết file",
    "Read":           "📖 Đọc file",
    "web_search":     "🔍 Tìm kiếm",
    "web_fetch":      "🌐 Fetch URL",
    "memory_search":  "🧠 Tìm memory",
    "memory_get":     "🧠 Đọc memory",
    "browser":        "🌐 Browser",
    "sessions_list":  "📋 Xem sessions",
    "sessions_send":  "📨 Gửi session",
    "sessions_spawn": "🚀 Spawn agent",
    "image":          "🖼️ Phân tích ảnh",
    "pdf":            "📄 Đọc PDF",
}

_log_positions:    dict = {}
_transcript_pos:   dict = {}
_session_cache:    dict = {}

# ── Watcher: Log files ────────────────────────────────────────

async def _watch_all_logs():
    while True:
        for agent in get_agents():
            log_path = Path(f"/tmp/hub-{agent.id}.log")
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
                            await push_activity(agent.id, evt.get("message", ""), evt.get("level", "info"))
                        except Exception:
                            await push_activity(agent.id, line[:200], "info")
                _log_positions[agent.id] = log_path.stat().st_size
            except Exception:
                pass
        await asyncio.sleep(0.5)


# ── Watcher: Session intelligence (Phase 3) ───────────────────

async def _watch_sessions():
    """Poll session store → detect active sessions + sync snapshots."""
    import time
    while True:
        for agent in get_agents():
            oc_id = agent.openclaw_agent_id or agent.id
            sess_file = OPENCLAW_AGENTS / oc_id / "sessions" / "sessions.json"
            if not sess_file.exists():
                continue
            try:
                data     = json.loads(sess_file.read_text())
                sessions = data if isinstance(data, list) else data.get("sessions", [])
                latest   = max((s.get("updatedAt", 0) for s in sessions), default=0)
                age_sec  = time.time() - (latest / 1000) if latest else 9999

                was_running = _session_cache.get(oc_id) == "running"
                is_running  = age_sec < SESSION_ACTIVE_SEC

                if is_running and not was_running:
                    update_status(agent.id, "running")
                    await push_activity(agent.id, "🟢 Session active", "info")
                elif not is_running and was_running:
                    cur = next((a for a in get_agents() if a.id == agent.id), None)
                    if cur and cur.status == "running":
                        update_status(agent.id, "idle")

                _session_cache[oc_id] = "running" if is_running else "idle"

                # Sync session snapshots vào DB (không await — sync operation)
                sync_session_snapshots(oc_id)

            except Exception:
                pass
        await asyncio.sleep(5)


# ── Watcher: Transcript + A2A Bus (Phase 3 + 4) ──────────────

async def _watch_transcripts():
    """
    Parse tool calls từ session JSONL:
    - Push activity cho mọi tool call (Phase 3)
    - Detect sessions_send → A2A message bus (Phase 4)
    """
    while True:
        for agent in get_agents():
            oc_id     = agent.openclaw_agent_id or agent.id
            sess_file = OPENCLAW_AGENTS / oc_id / "sessions" / "sessions.json"
            if not sess_file.exists():
                continue
            try:
                data     = json.loads(sess_file.read_text())
                sessions = data if isinstance(data, list) else data.get("sessions", [])
                if not sessions:
                    continue

                sess = max(sessions, key=lambda s: s.get("updatedAt", 0))
                sf   = sess.get("sessionFile") or sess.get("file", "")
                if not sf:
                    continue
                sf_path = Path(sf) if Path(sf).is_absolute() else OPENCLAW_AGENTS / oc_id / "sessions" / sf
                if not sf_path.exists():
                    continue

                pos  = _transcript_pos.get(str(sf_path), 0)
                size = sf_path.stat().st_size
                if size <= pos:
                    _transcript_pos[str(sf_path)] = size
                    continue

                with open(sf_path, "r", errors="replace") as f:
                    f.seek(pos)
                    for line in f:
                        try:
                            entry = json.loads(line)
                            msg   = entry.get("message", {})
                            if msg.get("role") == "assistant":
                                for block in msg.get("content", []):
                                    if block.get("type") == "toolCall":
                                        name  = block.get("name", "")
                                        args  = block.get("arguments", {})
                                        label = TOOL_LABELS.get(name, f"🔧 {name}")
                                        detail = (args.get("command") or args.get("file_path")
                                                  or args.get("query") or args.get("url") or "")
                                        msg_text = f"{label}: {str(detail)[:80]}" if detail else label
                                        await push_activity(agent.id, msg_text, "progress")
                                        # Phase 4: A2A
                                        await handle_tool_call(agent.id, name, args)
                        except Exception:
                            pass
                _transcript_pos[str(sf_path)] = sf_path.stat().st_size
            except Exception:
                pass
        await asyncio.sleep(2)


# ── Watcher: Auto-discovery sync (Phase 1) ───────────────────

async def _watch_config():
    """Tự động re-sync khi openclaw.json thay đổi."""
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    last_mtime  = 0.0
    while True:
        try:
            mtime = config_path.stat().st_mtime if config_path.exists() else 0.0
            if mtime != last_mtime:
                synced = sync_agents_from_config()
                if mtime != 0.0:
                    await push_activity("hub-keeper",
                        f"🔄 Auto-sync: {len(synced)} agents từ openclaw.json", "info")
                last_mtime = mtime
        except Exception:
            pass
        await asyncio.sleep(10)


# ── Lifespan ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    # Migrate JSON cũ nếu DB rỗng
    registry_json = BASE / "registry.json"
    if registry_json.exists():
        seed_from_json(registry_json)

    # Phase 1: Sync từ openclaw.json ngay lúc boot
    synced = sync_agents_from_config()
    print(f"[v3] Auto-synced {len(synced)} agents from openclaw.json")

    # Reset running → idle
    for a in get_agents():
        if a.status == "running":
            update_status(a.id, "idle")

    # Start all watchers
    asyncio.create_task(_watch_all_logs())
    asyncio.create_task(_watch_sessions())
    asyncio.create_task(_watch_transcripts())
    asyncio.create_task(_watch_config())

    print("[v3] Agent Hub v3 started ✅")
    yield
    print("[v3] Shutting down...")


# ── App ───────────────────────────────────────────────────────

app = FastAPI(title="Agent Hub v3", lifespan=lifespan)

app.include_router(agents.router)
app.include_router(approvals.router)
app.include_router(activity.router)
app.include_router(general.router)
app.include_router(topology.router)


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


# ── Static / SPA ──────────────────────────────────────────────

STATIC_DIR = BASE / "frontend" / "dist"
LEGACY     = BASE / "static"

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    async def root():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{path:path}")
    async def spa(path: str):
        f = STATIC_DIR / path
        return FileResponse(f) if f.exists() else FileResponse(STATIC_DIR / "index.html")

elif LEGACY.exists():
    app.mount("/static", StaticFiles(directory=LEGACY), name="static")

    @app.get("/")
    async def root_legacy():
        return FileResponse(LEGACY / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=7777, reload=True)
