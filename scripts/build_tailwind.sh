#!/usr/bin/env bash
# Build Tailwind CSS from input sources.
# Requires tailwindcss CLI (v4) installed at /workspace/.local/bin/tailwindcss
# or available in PATH.
#
# Usage:
#     ./scripts/build_tailwind.sh          # development build
#     ./scripts/build_tailwind.sh --minify # production build (minified)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INPUT="$ROOT/static/css/tailwind-input.css"
OUTPUT="$ROOT/static/css/tailwind.css"

TW="tailwindcss"
if command -v tailwindcss &>/dev/null; then
    TW="tailwindcss"
elif [ -x "$ROOT/.local/bin/tailwindcss" ]; then
    TW="$ROOT/.local/bin/tailwindcss"
else
    echo "ERROR: tailwindcss CLI not found."
    echo "Install it from https://github.com/tailwindlabs/tailwindcss/releases"
    echo "Place the binary at /workspace/.local/bin/tailwindcss"
    exit 1
fi

MINIFY=""
if [ "${1:-}" = "--minify" ]; then
    MINIFY="-m"
fi

echo "Building Tailwind CSS..."
$TW -i "$INPUT" -o "$OUTPUT" $MINIFY

SIZE=$(wc -c < "$OUTPUT")
echo "Done. Output: $OUTPUT (${SIZE} bytes)"
