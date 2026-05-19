"""
filter_schema.py — TOML schema parser and CompiledFilter for RTK.

Parses TOML filter definitions and produces CompiledFilter instances
with pre-compiled regexes for all matching and transformation stages.

Three priority levels, merged in order:
    built-in -> agent-specific -> project-specific

Later levels replace earlier ones when a filter's command regex matches
an already-loaded filter. Otherwise, filters from higher-priority levels
are added to the set.

Usage:
    from token_compressor.filter_schema import load_filter, load_filters, CompiledFilter

    # Single file
    f = load_filter("builtins/git_status.toml")

    # Merged from three directories
    filters = load_filters("builtins/", "agents/linus/", "projects/myproject/")
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FilterParseError(Exception):
    """Raised when a TOML filter definition is malformed or missing required fields."""

    def __init__(self, message: str, path: Optional[Path] = None) -> None:
        loc = f" in {path}" if path else ""
        super().__init__(f"{message}{loc}")
        self.path = path


# ---------------------------------------------------------------------------
# CompiledFilter
# ---------------------------------------------------------------------------

@dataclass
class CompiledFilter:
    """A fully-compiled filter ready for runtime matching and transformation.

    All regex patterns are pre-compiled at parse time.  No lazy compilation.
    """

    # The compiled regex used to match a command string (e.g. "git status").
    command_re: re.Pattern

    # Human-readable label for this filter (optional).
    description: str = ""

    # If True, ANSI escape sequences will be stripped from output before
    # any other processing.
    strip_ansi: bool = False

    # Ordered list of (compiled_pattern, replacement) pairs for regex-based
    # find-and-replace on output lines.
    replace: list[tuple[re.Pattern, str]] = field(default_factory=list)

    # Ordered list of (compiled_pattern, message) pairs.  When a pattern
    # matches the output, the message is emitted instead of the raw line(s).
    match_output: list[tuple[re.Pattern, str]] = field(default_factory=list)

    # Regex patterns — lines matching any of these are removed entirely.
    strip_lines: list[re.Pattern] = field(default_factory=list)

    # Regex patterns — only lines matching at least one of these are kept.
    # If empty, all lines pass (subject to strip_lines).
    keep_lines: list[re.Pattern] = field(default_factory=list)

    # If set, lines longer than this are truncated to this length.
    truncate_lines_at: Optional[int] = None

    # Keep only the first N lines (after all other filtering).
    head_lines: Optional[int] = None

    # Keep only the last N lines (after all other filtering).
    tail_lines: Optional[int] = None

    # Hard cap on total lines after all processing.
    max_lines: Optional[int] = None

    # Replacement text when the output is empty after filtering.
    on_empty: Optional[str] = None

    # Where this filter was loaded from (for debugging / diagnostics).
    source: str = ""

    def matches_command(self, command: str) -> bool:
        """Return True if this filter's command regex matches *command*."""
        return bool(self.command_re.search(command))


# ---------------------------------------------------------------------------
# Known / allowed TOML keys
# ---------------------------------------------------------------------------

# Valid top-level keys under [filter]
_VALID_KEYS: frozenset[str] = frozenset({
    "command", "description", "strip_ansi",
    "replace", "match_output",
    "strip_lines", "keep_lines",
    "truncate_lines_at", "head_lines", "tail_lines", "max_lines",
    "on_empty",
})


# ---------------------------------------------------------------------------
# Internal: compile a single TOML dict into a CompiledFilter
# ---------------------------------------------------------------------------

def _compile_filter(raw: dict, source: str) -> CompiledFilter:
    """Validate and compile a raw TOML [filter] dict.

    Args:
        raw: The parsed dict from TOML, expected to be the [filter] table.
        source: Human-readable origin of this data (e.g. a file path).

    Returns:
        A fully-compiled CompiledFilter.

    Raises:
        FilterParseError: On missing fields, bad types, invalid regex, etc.
    """
    path_ref = Path(source) if source else None

    # --- command (required) ---
    raw_cmd = raw.get("command")
    if not raw_cmd:
        raise FilterParseError(
            "Missing required field 'command' (the regex to match command strings)",
            path=path_ref,
        )
    if not isinstance(raw_cmd, str):
        raise FilterParseError(
            f"'command' must be a string, got {type(raw_cmd).__name__}",
            path=path_ref,
        )
    try:
        command_re = re.compile(raw_cmd)
    except re.error as exc:
        raise FilterParseError(
            f"Invalid regex in 'command' = {raw_cmd!r}: {exc}",
            path=path_ref,
        ) from exc

    # --- description ---
    description = raw.get("description", "")
    if not isinstance(description, str):
        raise FilterParseError(
            f"'description' must be a string, got {type(description).__name__}",
            path=path_ref,
        )

    # --- strip_ansi ---
    strip_ansi = raw.get("strip_ansi", False)
    if not isinstance(strip_ansi, bool):
        raise FilterParseError(
            f"'strip_ansi' must be a boolean, got {type(strip_ansi).__name__}",
            path=path_ref,
        )

    # --- replace ---
    replace_list: list[tuple[re.Pattern, str]] = []
    for i, entry in enumerate(raw.get("replace") or []):
        if not isinstance(entry, dict):
            raise FilterParseError(
                f"'replace[{i}]' must be a table, got {type(entry).__name__}",
                path=path_ref,
            )
        pat = entry.get("pattern")
        repl = entry.get("replacement", "")
        if not pat:
            raise FilterParseError(
                f"'replace[{i}]' missing required 'pattern' key",
                path=path_ref,
            )
        try:
            replace_list.append((re.compile(pat), repl))
        except re.error as exc:
            raise FilterParseError(
                f"Invalid regex in 'replace[{i}].pattern' = {pat!r}: {exc}",
                path=path_ref,
            ) from exc

    # --- match_output ---
    match_list: list[tuple[re.Pattern, str]] = []
    for i, entry in enumerate(raw.get("match_output") or []):
        if not isinstance(entry, dict):
            raise FilterParseError(
                f"'match_output[{i}]' must be a table, got {type(entry).__name__}",
                path=path_ref,
            )
        pat = entry.get("pattern")
        msg = entry.get("message", "")
        if not pat:
            raise FilterParseError(
                f"'match_output[{i}]' missing required 'pattern' key",
                path=path_ref,
            )
        try:
            match_list.append((re.compile(pat), msg))
        except re.error as exc:
            raise FilterParseError(
                f"Invalid regex in 'match_output[{i}].pattern' = {pat!r}: {exc}",
                path=path_ref,
            ) from exc

    # --- strip_lines ---
    strip_lines: list[re.Pattern] = []
    for i, pat in enumerate(raw.get("strip_lines") or []):
        if not isinstance(pat, str):
            raise FilterParseError(
                f"'strip_lines[{i}]' must be a string, got {type(pat).__name__}",
                path=path_ref,
            )
        try:
            strip_lines.append(re.compile(pat))
        except re.error as exc:
            raise FilterParseError(
                f"Invalid regex in 'strip_lines[{i}]' = {pat!r}: {exc}",
                path=path_ref,
            ) from exc

    # --- keep_lines ---
    keep_lines: list[re.Pattern] = []
    for i, pat in enumerate(raw.get("keep_lines") or []):
        if not isinstance(pat, str):
            raise FilterParseError(
                f"'keep_lines[{i}]' must be a string, got {type(pat).__name__}",
                path=path_ref,
            )
        try:
            keep_lines.append(re.compile(pat))
        except re.error as exc:
            raise FilterParseError(
                f"Invalid regex in 'keep_lines[{i}]' = {pat!r}: {exc}",
                path=path_ref,
            ) from exc

    # --- numeric helpers ---
    def _get_positive_int(key: str) -> Optional[int]:
        val = raw.get(key)
        if val is None:
            return None
        if isinstance(val, bool):
            raise FilterParseError(
                f"'{key}' must be an integer, got bool",
                path=path_ref,
            )
        if not isinstance(val, int):
            raise FilterParseError(
                f"'{key}' must be an integer, got {type(val).__name__}",
                path=path_ref,
            )
        if val < 1:
            raise FilterParseError(
                f"'{key}' must be >= 1, got {val}",
                path=path_ref,
            )
        return val

    truncate_lines_at = _get_positive_int("truncate_lines_at")
    head_lines = _get_positive_int("head_lines")
    tail_lines = _get_positive_int("tail_lines")
    max_lines = _get_positive_int("max_lines")

    # --- on_empty ---
    on_empty = raw.get("on_empty")
    if on_empty is not None and not isinstance(on_empty, str):
        raise FilterParseError(
            f"'on_empty' must be a string, got {type(on_empty).__name__}",
            path=path_ref,
        )

    # --- warn about unknown keys ---
    unknown = set(raw.keys()) - _VALID_KEYS
    if unknown:
        import sys
        print(
            f"[filter_schema] Warning: unknown key(s) {sorted(unknown)}"
            f" in {source or '<dict>'} — they will be ignored.",
            file=sys.stderr,
        )

    return CompiledFilter(
        command_re=command_re,
        description=description,
        strip_ansi=strip_ansi,
        replace=replace_list,
        match_output=match_list,
        strip_lines=strip_lines,
        keep_lines=keep_lines,
        truncate_lines_at=truncate_lines_at,
        head_lines=head_lines,
        tail_lines=tail_lines,
        max_lines=max_lines,
        on_empty=on_empty,
        source=source,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_filter(path: str | Path) -> CompiledFilter:
    """Parse a single TOML file into a CompiledFilter.

    The TOML file must contain a [filter] table.

    Args:
        path: Path to the .toml file.

    Returns:
        A fully-compiled CompiledFilter.

    Raises:
        FilterParseError: On any validation or parsing failure.
        FileNotFoundError: If the file does not exist.
        tomllib.TOMLDecodeError: If the file is not valid TOML.
    """
    path = Path(path)
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise FilterParseError(
            f"Invalid TOML: {exc}",
            path=path,
        ) from exc

    table = data.get("filter")
    if table is None:
        raise FilterParseError(
            "TOML file missing required [filter] table",
            path=path,
        )
    if not isinstance(table, dict):
        raise FilterParseError(
            f"[filter] must be a table, got {type(table).__name__}",
            path=path,
        )

    return _compile_filter(table, source=str(path))


def load_filters(
    builtin_dir: str | Path | None = None,
    agent_dir: str | Path | None = None,
    project_dir: str | Path | None = None,
) -> dict[str, CompiledFilter]:
    """Load filters from three priority levels, merging them together.

    Load order:
        1. builtin_dir  (lowest priority)
        2. agent_dir
        3. project_dir  (highest priority)

    When a filter from a higher-priority level has a command regex whose
    pattern string is identical to an already-loaded filter, the later one
    replaces the earlier one.  Otherwise, filters are additive.

    Args:
        builtin_dir: Directory of built-in filter TOML files.
        agent_dir: Directory of agent-specific filter TOML files.
        project_dir: Directory of project-specific filter TOML files.

    Returns:
        Dict mapping command regex pattern strings to CompiledFilter instances.
    """
    merged: dict[str, CompiledFilter] = {}

    for label, dir_path in [
        ("builtin", builtin_dir),
        ("agent", agent_dir),
        ("project", project_dir),
    ]:
        if dir_path is None:
            continue
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            continue

        for toml_file in sorted(dir_path.glob("*.toml")):
            try:
                f = load_filter(toml_file)
            except FilterParseError:
                raise
            except Exception as exc:
                raise FilterParseError(
                    f"Failed to load filter: {exc}",
                    path=toml_file,
                ) from exc

            key = f.command_re.pattern
            if key in merged:
                # Higher-priority level replaces the earlier one.
                pass  # fall through to assignment below
            merged[key] = f

    return merged
