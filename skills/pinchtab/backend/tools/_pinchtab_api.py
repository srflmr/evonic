"""
Shared PinchTab HTTP API wrapper.

Handles all communication with the PinchTab server. Uses environment
variables PINCHTAB_HOST and PINCHTAB_PORT (with sensible defaults) so
configuration can be injected at deployment time without code changes.
"""

import json
import os
import urllib.request
import urllib.error

PINCHTAB_HOST = os.environ.get("PINCHTAB_HOST", "localhost")
PINCHTAB_PORT = os.environ.get("PINCHTAB_PORT", "9867")
PINCHTAB_BASE_URL = f"http://{PINCHTAB_HOST}:{PINCHTAB_PORT}"


def _api(method: str, path: str, body: dict = None, timeout: int = 30) -> dict:
    """Call PinchTab HTTP API and return the parsed JSON response.

    Args:
        method: HTTP method (GET, POST, DELETE, etc.)
        path: API path starting with / (e.g. /api/health)
        body: Optional JSON-serializable dict for the request body
        timeout: Request timeout in seconds (default 30)

    Returns:
        Parsed JSON response dict. On any error, returns {"error": "..."}.
    """
    url = f"{PINCHTAB_BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body else None

    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        # Try to parse the error body for a better message
        try:
            err_body = json.loads(e.read())
        except Exception:
            err_body = None
        detail = ""
        if isinstance(err_body, dict):
            detail = err_body.get("error", err_body.get("message", ""))
        elif isinstance(err_body, str):
            detail = err_body
        return {
            "error": (
                f"PinchTab HTTP {e.code} on {method} {path}"
                + (f": {detail}" if detail else "")
            )
        }
    except urllib.error.URLError as e:
        return {
            "error": f"PinchTab unreachable at {PINCHTAB_BASE_URL}: {e.reason}",
            "hint": "Is PinchTab running? Start it with: pinchtab serve",
        }
    except json.JSONDecodeError:
        return {"error": f"PinchTab returned non-JSON response from {method} {path}"}
    except Exception as e:
        return {"error": f"PinchTab request failed: {type(e).__name__}: {e}"}
