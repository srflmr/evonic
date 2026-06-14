"""
Tool: agent_info — return comprehensive information about an agent.

Supports sections:
  - info: agent DB settings
  - tools: assigned tool IDs
  - skills: assigned skill IDs
  - channels: connected channels (without sensitive config keys)
  - portals: portal configurations
  - kb: knowledge base files
  - artifacts: artifact file statistics
  - variables: environment variables
  - models: primary and fallback model info
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _redact_channel_config(config: dict) -> dict:
    """Strip sensitive keys from channel config before returning."""
    if not isinstance(config, dict):
        return {}
    allowed = {"mode", "allowed_users", "user_names"}
    safe = {}
    for key in allowed:
        if key in config:
            safe[key] = config[key]
    return safe


def _get_kb_files(agent_id: str) -> list:
    kb_dir = os.path.join(BASE_DIR, "agents", agent_id, "kb")
    if not os.path.isdir(kb_dir):
        return []
    files = []
    for fname in sorted(os.listdir(kb_dir)):
        fpath = os.path.join(kb_dir, fname)
        if os.path.isfile(fpath):
            stat = os.stat(fpath)
            files.append({
                "filename": fname,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
    return files


def _get_artifacts_stats(agent_id: str) -> dict:
    arts_dir = os.path.join(BASE_DIR, "shared", "agents", agent_id, "artifacts")
    if not os.path.isdir(arts_dir):
        return {"count": 0, "total_size": 0, "by_category": {}}
    total = 0
    size = 0
    by_category = {}
    for fname in os.listdir(arts_dir):
        fpath = os.path.join(arts_dir, fname)
        if os.path.isfile(fpath):
            stat = os.stat(fpath)
            total += 1
            size += stat.st_size
            cat = _file_category(fname)
            by_category[cat] = by_category.get(cat, 0) + 1
    return {"count": total, "total_size": size, "by_category": by_category}


def _file_category(fname: str) -> str:
    ext = os.path.splitext(fname)[1].lower()
    if ext in ('.md', '.pdf'):
        return "document"
    if ext in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.ico'):
        return "image"
    if ext in ('.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma'):
        return "sound"
    if ext in ('.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v'):
        return "video"
    if ext in ('.txt', '.csv', '.json', '.yaml', '.yml', '.xml', '.log',
               '.py', '.c', '.rs', '.js', '.ts', '.jsx', '.tsx',
               '.html', '.css', '.toml', '.ini', '.cfg', '.conf',
               '.sh', '.bash', '.sql', '.lua', '.rb', '.go', '.java',
               '.swift', '.kt', '.r', '.m', '.pl', '.pm', '.vue', '.svelte'):
        return "text"
    return "data"


def execute(agent: dict, args: dict) -> dict:
    from models.db import db

    target_id = (args.get("agent_id") or "").strip()
    if not target_id:
        return {"error": "agent_id is required"}

    target = db.get_agent(target_id)
    if not target:
        return {"error": f"Agent '{target_id}' not found"}

    section_arg = (args.get("section") or "").strip().lower()
    if section_arg:
        sections = [s.strip() for s in section_arg.split(",") if s.strip()]
    else:
        sections = ["info", "tools", "skills", "channels", "portals",
                    "kb", "artifacts", "variables", "models"]

    result = {"agent_id": target_id}

    # --- info ---
    if "info" in sections:
        exclude = {"system_prompt", "workspace"}
        info = {}
        for k, v in target.items():
            if k not in exclude:
                info[k] = v
        result["info"] = info

    # --- tools ---
    if "tools" in sections:
        result["tools"] = db.get_agent_tools(target_id)

    # --- skills ---
    if "skills" in sections:
        result["skills"] = db.get_agent_skills(target_id)

    # --- channels ---
    if "channels" in sections:
        raw = db.get_channels(target_id)
        safe = []
        for ch in raw:
            safe.append({
                "id": ch.get("id"),
                "type": ch.get("type"),
                "name": ch.get("name"),
                "enabled": ch.get("enabled"),
                "config": _redact_channel_config(ch.get("config", {})),
                "created_at": ch.get("created_at"),
            })
        result["channels"] = safe

    # --- portals ---
    if "portals" in sections:
        portals = db.get_agent_portals(target_id)
        result["portals"] = portals

    # --- kb ---
    if "kb" in sections:
        result["kb"] = _get_kb_files(target_id)

    # --- artifacts ---
    if "artifacts" in sections:
        result["artifacts"] = _get_artifacts_stats(target_id)

    # --- variables ---
    if "variables" in sections:
        vars_raw = db.get_agent_variables(target_id)
        result["variables"] = vars_raw

    # --- models ---
    if "models" in sections:
        model_info = {}
        try:
            primary = db.get_agent_model(target_id)
            if primary:
                model_info["primary"] = {
                    "id": primary.get("id"),
                    "name": primary.get("name"),
                    "provider": primary.get("provider"),
                    "model_name": primary.get("model_name"),
                }
        except Exception:
            pass
        try:
            fallback = db.get_agent_fallback_model(target_id)
            if fallback:
                model_info["fallback"] = {
                    "id": fallback.get("id"),
                    "name": fallback.get("name"),
                    "provider": fallback.get("provider"),
                    "model_name": fallback.get("model_name"),
                }
        except Exception:
            pass
        result["models"] = model_info

    return result
