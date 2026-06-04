"""
_workspace.py — shared workspace path resolution for file tools.
"""
from typing import Optional

import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_AGENTS_DIR = os.path.join(_BASE_DIR, 'agents')
_SHARED_AGENTS_DIR = os.path.join(_BASE_DIR, 'shared', 'agents')
_SELF_PREFIX = '/_self/'


def effective_agent_id(agent: dict) -> str:
    """Return the effective agent ID for /_self/ path resolution.

    Sub-agents don't have their own directory under agents/ — they inherit
    their parent's SYSTEM.md, KB files, tool assignments, and skill
    assignments.  This mirrors context.py:_effective_id().
    """
    agent_id = (agent or {}).get('id', '')
    if (agent or {}).get('is_subagent'):
        return (agent or {}).get('parent_id', agent_id)
    return agent_id


def is_self_path(file_path: str) -> bool:
    """Return True if file_path uses the /_self/ virtual prefix."""
    return bool(file_path) and (file_path.startswith(_SELF_PREFIX) or file_path == '/_self')


def resolve_self_path(agent_id: str, file_path: str) -> Optional[str]:
    """Resolve /_self/... to the agent's local directory on the evonic server.

    Returns the absolute local path, or None if the resolved path escapes
    the agent's directory (path traversal / symlink attack prevention).
    """
    rel = file_path[len(_SELF_PREFIX):] if file_path.startswith(_SELF_PREFIX) else ''

    # /_self/artifacts/ resolves to shared/agents/<id>/artifacts/ (not agents/<id>/artifacts/)
    if rel == 'artifacts' or rel.startswith('artifacts/'):
        base_dir = _SHARED_AGENTS_DIR
        safe_root = os.path.realpath(os.path.join(_SHARED_AGENTS_DIR, agent_id, 'artifacts'))
    else:
        base_dir = _AGENTS_DIR
        safe_root = os.path.realpath(os.path.join(_AGENTS_DIR, agent_id))

    abs_path = os.path.normpath(os.path.join(base_dir, agent_id, rel))
    resolved = os.path.realpath(abs_path)
    if not resolved.startswith(safe_root + os.sep) and resolved != safe_root:
        return None
    return resolved


def resolve_workspace_path(agent, file_path: str, fallback_workspace: str) -> str:
    """Resolve a file path to an absolute path, honoring the agent's workspace.

    Rules (in priority order):
    1. If path starts with '/workspace', strip that prefix and join with the
       agent's workspace (or fallback_workspace).  This is the runpy-sandbox
       convention for paths inside a Docker container.
    2. If path is relative (not absolute) and the agent has a workspace set,
       resolve it relative to that workspace.
    3. Otherwise return the path unchanged.
    """
    if not file_path:
        return file_path

    if file_path.startswith('/workspace'):
        workspace_root = (agent or {}).get('workspace') or fallback_workspace
        rel = file_path[len('/workspace'):].lstrip('/')
        return os.path.join(os.path.abspath(workspace_root), rel)

    if not os.path.isabs(file_path):
        workspace = (agent or {}).get('workspace')
        if workspace:
            return os.path.join(os.path.abspath(workspace), file_path)

    return file_path
