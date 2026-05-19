"""
Command detection helper for RTK token compressor.

Maps tool invocations to filter-friendly command strings
so the compressor registry can pick the right TOML pipeline.
"""

from __future__ import annotations

import re
from typing import Any


_META_PREFIXES = ("cd ", "export ", "set ", "trap ", "exec ", "echo ")


def extract_command(tool_name: str, params: dict[str, Any]) -> str:
    """Derive a command string for compressor filter matching.

    Args:
        tool_name: The tool being invoked (e.g. "bash", "runpy").
        params:    Tool arguments dict.

    Returns:
        A string like "git status", "pytest", "read_file foo.py", or tool_name.
    """
    if not isinstance(params, dict):
        return tool_name

    if tool_name == "bash":
        script = params.get("script", "")
        if not isinstance(script, str):
            return "bash"
        return _bash_cmd(script)

    if tool_name == "runpy":
        code = params.get("code", "")
        if not isinstance(code, str):
            return "python"
        return _py_cmd(code)

    if tool_name in ("read_file", "write_file"):
        fp = params.get("file_path", "")
        return f"{tool_name} {fp}" if fp else tool_name

    return tool_name


def _bash_cmd(script: str) -> str:
    """Extract the last substantive command from a bash script."""
    if not script:
        return "bash"

    lines = [l.strip() for l in script.split("\n")]
    candidates: list[str] = []

    for line in reversed(lines):
        if not line:
            continue
        if line.startswith("#") or line.startswith("#!/"):
            continue
        if line.startswith(_META_PREFIXES):
            continue
        candidates.insert(0, line)

    if not candidates:
        return "bash"

    cmd = candidates[-1]
    cmd = re.sub(r"^\s*(?:\w+=[^\s]+\s+)+", "", cmd)
    base = re.split(r"[|;&<>]", cmd)[0].strip()
    tokens = base.split()
    if len(tokens) >= 2:
        return " ".join(tokens[:2])
    return tokens[0] if tokens else "bash"


def _py_cmd(code: str) -> str:
    """Heuristically detect the Python command from code content."""
    if not code:
        return "python"

    for line in code.strip().split("\n")[:10]:
        s = line.strip()
        if re.match(r"^(?:import\s+pytest|from\s+pytest\s)", s):
            return "pytest"
        if re.match(r"^(?:import\s+unittest|from\s+unittest\s)", s):
            return "python -m unittest"
        if "subprocess.run" in s or "subprocess.call" in s:
            return "python subprocess"
        if "os.system" in s:
            return "python"

    return "python"
