#!/usr/bin/env bash
# pre-commit-check.sh — Safety gate to prevent accidental commits of
# forbidden files, sensitive data, and large binaries.
#
# Usage:
#   ./scripts/pre-commit-check.sh          # manual run
#   SKIP_PRECOMMIT=1 git commit ...        # bypass check
#
# Install as a git hook:
#   ./scripts/install-pre-commit.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_FILE_SIZE="${MAX_FILE_SIZE:-5242880}"  # 5 MB default

# ---------------------------------------------------------------------------
# Colours (auto-detects whether stdout is a terminal)
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    NC='\033[0m'  # No Colour
else
    RED='' GREEN='' YELLOW='' NC=''
fi

# ---------------------------------------------------------------------------
# Override / skip
# ---------------------------------------------------------------------------
if [ "${SKIP_PRECOMMIT:-0}" = "1" ] || [ "${SKIP_PRECOMMIT:-0}" = "true" ]; then
    echo -e "${YELLOW}[pre-commit] SKIP_PRECOMMIT set — bypassing all checks${NC}"
    exit 0
fi

# ---------------------------------------------------------------------------
# Helper: report a violation block and exit 1
# ---------------------------------------------------------------------------
violation_found=false

fail() {
    local title="$1"
    shift
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  PRECOMMIT BLOCKED: ${title}$(printf '%*s' $((54 - ${#title})) '')║${NC}"
    echo -e "${RED}╠══════════════════════════════════════════════════════════════╣${NC}"
    for line in "$@"; do
        printf "${RED}║${NC}  %s\n" "$line"
    done
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Tip: use SKIP_PRECOMMIT=1 git commit ... to bypass (not recommended)${NC}"
    violation_found=true
}

# ---------------------------------------------------------------------------
# Gather staged files (excluding deletions so we can inspect content)
# ---------------------------------------------------------------------------
STAGED_FILES=$(git diff --cached --name-only --diff-filter=d 2>/dev/null || true)

if [ -z "$STAGED_FILES" ]; then
    echo -e "${GREEN}[pre-commit] No staged files — nothing to check${NC}"
    exit 0
fi

# ---------------------------------------------------------------------------
# 1. FORBIDDEN PATH DETECTION
# ---------------------------------------------------------------------------
# Patterns that must never be committed.  Each is matched as:
#   - line starts with <pattern>       (top-level directory or file)
#   - line contains /<pattern>         (nested directory)
#   - line contains /<pattern>/        (nested directory with trailing slash)
#
# IMPORTANT: 'VERSION' is intentionally *not* in this list — it is allowed.
# ---------------------------------------------------------------------------

FORBIDDEN_DIRS=(
    "agents/"
    "keys/"
    "data/"
    "plan/"
    "run/"
    "docs-site/"
    "releases/"
    "shared/"
    "artifacts/"
    "logs/"
)

FORBIDDEN_NAMES=(
    "current"
    "current.slot"
    "rollback.slot"
)

FORBIDDEN_PATTERNS=(
    "*.db"
    "*.db-journal"
    "*.db-wal"
    "*.db-shm"
    "__pycache__/"
    ".venv/"
    ".pytest_cache/"
    "node_modules/"
)

blocked_paths=()

# -- Sensitive directories
for dir in "${FORBIDDEN_DIRS[@]}"; do
    while IFS= read -r file; do
        # Match either as top-level prefix or as a path component
        if [[ "$file" == "$dir"* ]] || [[ "$file" == *"/$dir"* ]]; then
            blocked_paths+=("$file")
        fi
    done <<< "$STAGED_FILES"
done

# -- Exact forbidden names (current, current.slot, rollback.slot)
for name in "${FORBIDDEN_NAMES[@]}"; do
    while IFS= read -r file; do
        if [ "$file" = "$name" ] || [[ "$file" == *"/$name" ]]; then
            blocked_paths+=("$file")
        fi
    done <<< "$STAGED_FILES"
done

# -- Forbidden patterns (globs)
for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    while IFS= read -r file; do
        # Simple glob match against the full path
        case "$file" in
            $pattern|*/$pattern|*/$pattern/*) blocked_paths+=("$file") ;;
        esac
    done <<< "$STAGED_FILES"
done

# -- .env files (except .env.example)
while IFS= read -r file; do
    if [ "$file" = ".env" ] || [[ "$file" == *"/.env" ]]; then
        if [ "$file" != ".env.example" ] && [[ "$file" != *"/.env.example" ]]; then
            blocked_paths+=("$file")
        fi
    fi
done <<< "$STAGED_FILES"

# Deduplicate and report
if [ ${#blocked_paths[@]} -gt 0 ]; then
    # deduplicate while preserving order
    declare -A seen
    unique_blocked=()
    for f in "${blocked_paths[@]}"; do
        if [ -z "${seen[$f]:-}" ]; then
            unique_blocked+=("$f")
            seen[$f]=1
        fi
    done

    fail "FORBIDDEN PATH" "${unique_blocked[@]}"
else
    echo -e "${GREEN}[pre-commit] Path check passed${NC}"
fi

# ---------------------------------------------------------------------------
# 2. SENSITIVE DATA SCAN
# ---------------------------------------------------------------------------
# Scan the staged *diff* for common credential patterns so we catch secrets
# even inside files whose paths are innocent.
# ---------------------------------------------------------------------------

SENSITIVE_PATTERNS=(
    # GitHub tokens (classic & fine-grained)
    'ghp_[A-Za-z0-9_]{36,}'
    'gho_[A-Za-z0-9_]{36,}'
    'ghu_[A-Za-z0-9_]{36,}'
    'ghs_[A-Za-z0-9_]{36,}'
    'ghr_[A-Za-z0-9_]{36,}'

    # AWS access keys
    'AKIA[0-9A-Z]{16}'
    'ASIA[0-9A-Z]{16}'

    # Generic assignment patterns (heuristic — catches things like
    # pass=<VAL>, secret_key=<VAL>, apikey=<VAL>, token=<TOKEN>)
    '[a-zA-Z_]*password[a-zA-Z_]*\s*=\s*.+'
    'secret_key\s*=\s*.+'
    'api_key\s*=\s*.+'
    'token\s*=\s*[A-Za-z0-9_\-\.]{8,}'

    # Private SSH keys
    '-----BEGIN [A-Z]+ PRIVATE KEY-----'
)

# Get the full staged diff (binary diffs appear as "Binary files differ"
# which won't match any secret pattern, so they're harmless)
STAGED_DIFF=$(git diff --cached 2>/dev/null || true)

sensitive_hits=()

if [ -n "$STAGED_DIFF" ]; then
    for pat in "${SENSITIVE_PATTERNS[@]}"; do
        while IFS= read -r line; do
            # Strip the leading '+' from diff lines and skip header lines
            content="${line#+}"
            if [ "$content" != "$line" ] && [ -n "$content" ]; then
                sensitive_hits+=("$content")
            fi
        done < <(echo "$STAGED_DIFF" | grep -E -e "$pat" || true)
    done
fi

if [ ${#sensitive_hits[@]} -gt 0 ]; then
    # Show first few hits (avoid flooding the terminal)
    display=("${sensitive_hits[@]:0:10}")
    if [ ${#sensitive_hits[@]} -gt 10 ]; then
        display+=("... and $((${#sensitive_hits[@]} - 10)) more match(es)")
    fi
    fail "SENSITIVE DATA DETECTED" "${display[@]}"
else
    echo -e "${GREEN}[pre-commit] Sensitive data scan passed${NC}"
fi

# ---------------------------------------------------------------------------
# 3. LARGE FILE DETECTION
# ---------------------------------------------------------------------------
# Check each staged file's size in the working tree (not the blob) so we
# catch large binaries *before* they enter the repo.
# ---------------------------------------------------------------------------

large_files=()

while IFS= read -r file; do
    if [ -f "$file" ]; then
        size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo 0)
        if [ "$size" -gt "$MAX_FILE_SIZE" ] 2>/dev/null; then
            human=$(numfmt --to=iec "$size" 2>/dev/null || echo "${size} bytes")
            large_files+=("$file  (${human})")
        fi
    fi
done <<< "$STAGED_FILES"

if [ ${#large_files[@]} -gt 0 ]; then
    max_human=$(numfmt --to=iec "$MAX_FILE_SIZE" 2>/dev/null || echo "${MAX_FILE_SIZE} bytes")
    fail "LARGE FILE (max: ${max_human})" "${large_files[@]}"
else
    echo -e "${GREEN}[pre-commit] File size check passed${NC}"
fi

# ---------------------------------------------------------------------------
# Final verdict
# ---------------------------------------------------------------------------
if [ "$violation_found" = true ]; then
    exit 1
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  All pre-commit checks passed. Proceeding with commit.       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
exit 0
