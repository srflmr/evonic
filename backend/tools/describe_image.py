"""
describe_image.py — dedicated image description tool using a separate vision model.

Agents use this tool to analyze images rather than having images auto-fed to the
main LLM. The vision model is selected via a configurable priority chain:
  1. agent-level `vision_model_id` column
  2. system config `vision_model_id` (app_settings)
  3. first enabled model with `vision_supported = 1` in `llm_models`

The `vision_enabled` flag on the agent gates access to this tool entirely:
when `vision_enabled = 0`, the tool returns an error.
"""

from __future__ import annotations

import base64
import mimetypes
import os
from typing import Any, Dict, Optional

from backend.llm_client import LLMClient

# Image MIME types the tool supports
_SUPPORTED_IMAGE_TYPES = frozenset({
    "image/jpeg", "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
})


def _resolve_vision_model(agent: dict) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Resolve the vision model to use for image description.

    Priority:
      1. Agent-level vision_model_id (from agent_context)
      2. System config vision_model_id (app_settings)
      3. First enabled model with vision_supported = 1

    Returns:
        (model_dict, error_string).  Exactly one will be non-None.
    """
    from models.db import db

    vision_model_id = None

    # Priority 1: agent-level config (from context dict)
    vision_model_id = agent.get("vision_model_id")

    # Priority 2: system config
    if not vision_model_id:
        vision_model_id = db.get_setting("vision_model_id")

    # Look up the model
    if vision_model_id:
        model = db.get_model_by_id(vision_model_id)
        if model and model.get("enabled"):
            return model, None
        # model_id was set but invalid — fall through to auto-detect

    # Priority 3: agent's current model (natural fallback before global auto-detect).
    # Uses _db_agent_id for sub-agents so they resolve to the parent agent's model.
    _agent_db_id = agent.get("_db_agent_id") or agent.get("id")
    agent_model = db.get_agent_model(_agent_db_id)
    if agent_model and agent_model.get("vision_supported"):
        return agent_model, None

    # Priority 4: first enabled vision-capable model
    all_models = db.get_enabled_llm_models()
    for model in all_models:
        if model.get("vision_supported"):
            return model, None

    return None, (
        "No vision-capable model is available. "
        "Please configure a vision model in System Settings (requires vision_supported=1)."
    )


def execute(agent: dict, args: dict) -> Any:
    """Analyze an image file and return a text description.

    Args:
        agent: Agent context dict (must contain at least 'id').
        args:
            path (str, required): Absolute or relative path to the image file.
            query (str, optional): Specific question about the image.
                If omitted, a general description is returned.

    Returns:
        str: Plain-text description of the image, or an error message.
    """
    path = (args.get("path") or "").strip()
    query = (args.get("query") or "").strip()

    # --- Gate: vision_enabled ---
    # The agent_context dict includes vision_enabled when the runtime builds it.
    vision_enabled = agent.get("vision_enabled", 1)
    if not vision_enabled:
        return (
            "Error: Image analysis is not enabled for this agent "
            "(vision_enabled=0). Enable it in the agent's settings to use "
            "the describe_image tool."
        )

    # --- Validate path ---
    if not path:
        return "Error: 'path' parameter is required. Provide the file path to the image."

    if not os.path.isfile(path):
        return f"Error: File not found: {path}"

    file_size = os.path.getsize(path)
    if file_size > 10 * 1024 * 1024:  # 10 MB
        return f"Error: Image file is {file_size / (1024*1024):.1f} MB, which exceeds the 10 MB limit."

    # --- Detect MIME type ---
    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type or mime_type not in _SUPPORTED_IMAGE_TYPES:
        detected = mime_type or "unknown"
        return (
            f"Error: Unsupported image type '{detected}'. "
            f"Supported formats: JPEG, PNG, GIF, WebP, BMP."
        )

    # --- Read image and encode as base64 ---
    try:
        with open(path, "rb") as f:
            image_data = f.read()
    except PermissionError:
        return f"Error: Permission denied — cannot read: {path}"
    except Exception as e:
        return f"Error: Failed to read image: {e}"

    image_b64 = base64.b64encode(image_data).decode("utf-8")

    # --- Resolve vision model ---
    vision_model, error = _resolve_vision_model(agent)
    if error:
        return f"Error: {error}"

    # --- Build the vision request ---
    # Use base64 JPEG encoding for the data URL regardless of source format;
    # most vision models handle the standard image/jpeg MIME fine.
    data_url = f"data:image/jpeg;base64,{image_b64}"

    system_prompt = (
        "You are a helpful image analysis assistant. "
        "Describe the image clearly and concisely. "
        "If asked a specific question, answer it directly based on what you see."
    )

    if query:
        user_text = (
            f"Please analyze this image and answer the following question: {query}"
        )
    else:
        user_text = "Please describe this image in detail. What do you see?"

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    # --- Call the vision model ---
    try:
        client = LLMClient(model_config=vision_model)
        result = client.chat_completion(
            messages=messages,
            enable_thinking=False,  # No need for reasoning on vision task
        )
    except Exception as e:
        return f"Error: Vision model call failed: {e}"

    response_text = result.get("response", "")
    if not response_text and result.get("error"):
        return f"Error: Vision model returned an error: {result['error']}"

    if not response_text:
        return "Error: Vision model returned an empty response."

    return response_text.strip()
