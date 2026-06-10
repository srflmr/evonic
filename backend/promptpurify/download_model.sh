#!/usr/bin/env bash
# Download the PROMPTPurify L5e ONNX model from GitHub.
# The model is ~14 MB (ELECTRA-small, int8-quantized).
# Required by L5eRunner for ML-based prompt injection detection.
#
# Usage:
#   cd backend/promptpurify && bash download_model.sh
#
# Source: https://github.com/securelayer7/PROMPTPurify

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODEL_URL="https://raw.githubusercontent.com/securelayer7/PROMPTPurify/main/models/l5e/model.int8.onnx"

if [ -f "model.int8.onnx" ]; then
    echo "[promptpurify] Model already downloaded: model.int8.onnx ($(du -h model.int8.onnx | cut -f1))"
    exit 0
fi

echo "[promptpurify] Downloading L5e ONNX model (~14 MB)..."
curl -sL "$MODEL_URL" -o model.int8.onnx
echo "[promptpurify] Done: model.int8.onnx ($(du -h model.int8.onnx | cut -f1))"
