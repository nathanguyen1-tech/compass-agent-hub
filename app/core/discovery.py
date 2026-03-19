"""
Phase 1 — Auto-Discovery từ openclaw.json
Tự động sync agents + bindings từ config OpenClaw vào SQLite.
"""
import json, json5, os, time
from pathlib import Path
from typing import Any

from app.core.database import engine
from app.core.registry import get_agent, upsert_agent
from app.models.agent import Agent, Binding

OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
OPENCLAW_AGENTS_DIR = Path.home() / ".openclaw" / "agents"

# Default emoji map cho known agents
_EMOJI_DEFAULTS = {
    "main":               "🧠",
    "hub-keeper":         "🏗️",
    "compass-feedback":   "🩺",
    "feedback-bot":       "🩺",
    "health-check":       "🏥",
    "productivity-agent": "📋",
}

_NAME_OVERRIDES = {
    "main":               "Main Agent",
    "hub-keeper":         "HubKeeper",
    "compass-feedback":   "FeedbackBot",
    "health-check":       "Health Check",
    "productivity-agent": "Productivity Agent",
}

def _load_config() -> dict:
    if not OPENCLAW_CONFIG.exists():
        return {}
    try:
        return json5.loads(OPENCLAW_CONFIG.read_text())
    except Exception:
        try:
            return json.loads(OPENCLAW_CONFIG.read_text())
        except Exception:
            return {}


def sync_agents_from_config() -> list[str]:
    """
    Parse openclaw.json → upsert vào DB.
    Trả về list agent IDs vừa sync.
    """
    from sqlmodel import Session, select
    from app.models.agent import Binding as BindingModel

    cfg         = _load_config()
    agents_list = cfg.get("agents", {}).get("list", [])
    bindings    = cfg.get("bindings", [])
    tools_cfg   = cfg.get("tools", {})
    a2a_enabled = tools_cfg.get("agentToAgent", {}).get("enabled", False)

    synced = []
    for a in agents_list:
        agent_id = a.get("id", "")
        if not agent_id:
            continue

        identity = a.get("identity", {})
        # identity.name là persona AI (VD: "Nathan-Ubu") — KHÔNG dùng làm display name
        # Ưu tiên: existing custom name > openclaw 'name' field > slug từ id
        existing = get_agent(agent_id)
        if existing and existing.source == "manual":
            # Giữ nguyên name/emoji đã đặt thủ công
            name  = existing.name
            emoji = existing.emoji
        else:
            # Ưu tiên: override cứng > openclaw.json name > slug từ id
            if agent_id in _NAME_OVERRIDES:
                name = _NAME_OVERRIDES[agent_id]
            else:
                raw_name = a.get("name", "")
                if not raw_name or raw_name == agent_id:
                    name = agent_id.replace("-", " ").title()
                else:
                    # Bỏ các giá trị placeholder như "hub-keeper", "compass-feedback"
                    cleaned = raw_name.replace("-", " ").title()
                    name = cleaned
            emoji = _EMOJI_DEFAULTS.get(agent_id) or identity.get("emoji") or "🤖"
        model    = a.get("model", "")
        workspace = a.get("workspace", "")
        agent_dir = a.get("agentDir", str(OPENCLAW_AGENTS_DIR / agent_id / "agent"))

        agent = Agent(
            id                = agent_id,
            name              = name,
            emoji             = emoji,
            description       = identity.get("theme", f"OpenClaw agent — {agent_id}"),
            openclaw_agent_id = agent_id,
            model             = model,
            workspace_path    = workspace,
            agent_dir         = agent_dir,
            source            = "openclaw",
            a2a_enabled       = a2a_enabled,
            # Giữ status cũ nếu có
            status            = existing.status if existing else "idle",
            script            = existing.script if existing else "",
            requires_approval = existing.requires_approval if existing else False,
        )
        upsert_agent(agent)
        synced.append(agent_id)

    # Sync bindings
    with Session(engine) as s:
        # Xoá bindings cũ từ openclaw source
        old = s.exec(select(BindingModel).where(BindingModel.source == "openclaw")).all()
        for b in old:
            s.delete(b)
        s.commit()

        for b in bindings:
            bm = BindingModel(
                agent_id    = b.get("agentId", ""),
                channel     = b.get("match", {}).get("channel", ""),
                account_id  = b.get("match", {}).get("accountId", ""),
                peer_kind   = b.get("match", {}).get("peer", {}).get("kind", "") if b.get("match", {}).get("peer") else "",
                peer_id     = b.get("match", {}).get("peer", {}).get("id", "") if b.get("match", {}).get("peer") else "",
                source      = "openclaw",
            )
            s.add(bm)
        s.commit()

    return synced


def get_all_bindings() -> list[dict]:
    from sqlmodel import Session, select
    from app.models.agent import Binding as BindingModel
    with Session(engine) as s:
        rows = s.exec(select(BindingModel)).all()
        return [
            {"agent_id": r.agent_id, "channel": r.channel,
             "account_id": r.account_id, "peer_kind": r.peer_kind,
             "peer_id": r.peer_id, "source": r.source}
            for r in rows
        ]


def get_topology() -> dict:
    """Trả về full topology: agents + bindings + channel accounts."""
    from app.core.registry import get_agents
    cfg      = _load_config()
    channels = cfg.get("channels", {})
    bindings = get_all_bindings()
    agents   = get_agents()

    # Build channel accounts map
    accounts: dict[str, list[str]] = {}
    for ch_name, ch_cfg in channels.items():
        if isinstance(ch_cfg, dict):
            accs = ch_cfg.get("accounts", {})
            accounts[ch_name] = list(accs.keys()) if accs else ["default"]

    return {
        "agents":   [{"id": a.id, "name": a.name, "emoji": a.emoji,
                      "model": a.model, "status": a.status,
                      "source": a.source} for a in agents],
        "bindings": bindings,
        "accounts": accounts,
        "a2a_enabled": cfg.get("tools", {}).get("agentToAgent", {}).get("enabled", False),
    }
