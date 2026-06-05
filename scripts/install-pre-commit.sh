#!/usr/bin/env bash
# ==============================================================================
# install-pre-commit.sh — Install the pre-commit safety check hook
# ==============================================================================
# Creates a symlink from scripts/pre-commit-check.sh to .git/hooks/pre-commit
# so it runs automatically before every commit. Idempotent — safe to run
# multiple times; overwrites an existing hook if it was installed by this
# script, otherwise prompts for confirmation.
# ==============================================================================

set -euo pipefail

# --- Color helpers -----------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# --- Paths -------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SOURCE="${SCRIPT_DIR}/pre-commit-check.sh"
HOOK_TARGET=".git/hooks/pre-commit"

# --- Pre-flight checks -------------------------------------------------------
echo -e "${YELLOW}==> Installing pre-commit safety check hook...${NC}"

if [[ ! -f "$HOOK_SOURCE" ]]; then
    echo -e "${RED}ERROR: Cannot find ${HOOK_SOURCE}${NC}"
    echo "Make sure scripts/pre-commit-check.sh exists."
    exit 1
fi

if [[ ! -d ".git/hooks" ]]; then
    echo -e "${RED}ERROR: .git/hooks directory not found. Are you in the repository root?${NC}"
    exit 1
fi

# --- Handle existing hook ----------------------------------------------------
if [[ -e "$HOOK_TARGET" ]]; then
    if [[ -L "$HOOK_TARGET" ]]; then
        # It's a symlink — check if it points to our script
        CURRENT_TARGET="$(readlink "$HOOK_TARGET")"
        if [[ "$CURRENT_TARGET" == "$HOOK_SOURCE" ]]; then
            echo -e "${GREEN}==> Pre-commit hook is already installed (symlink to ${HOOK_SOURCE}).${NC}"
            exit 0
        else
            echo -e "${YELLOW}==> Existing pre-commit symlink points to ${CURRENT_TARGET} — replacing...${NC}"
            rm "$HOOK_TARGET"
        fi
    else
        echo -e "${YELLOW}==> An existing pre-commit hook file (not a symlink) was found.${NC}"
        echo -n "    Overwrite it? [y/N] "
        read -r REPLY
        if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
            echo "    Aborted by user."
            exit 0
        fi
        rm "$HOOK_TARGET"
    fi
fi

# --- Create symlink ----------------------------------------------------------
ln -s "$HOOK_SOURCE" "$HOOK_TARGET"
chmod +x "$HOOK_TARGET"

echo -e "${GREEN}==> Pre-commit hook installed successfully!${NC}"
echo "    Source : ${HOOK_SOURCE}"
echo "    Target : ${HOOK_TARGET}"
echo ""
echo "    To skip the hook for a single commit:"
echo "      SKIP_PRECOMMIT=1 git commit -m \"...\""
