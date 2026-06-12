"""
downloader — Auto-download PROMPTPurify L5e ONNX model on startup.

Spawns a background daemon thread only when the model file is missing.
Once downloaded, no thread is spawned on subsequent starts.
"""
import logging
import threading
from pathlib import Path

_logger = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).resolve().parent
_MODEL_FILE = "model.int8.onnx"
_MODEL_PATH = _MODEL_DIR / _MODEL_FILE
_MODEL_URL = (
    "https://raw.githubusercontent.com/securelayer7/"
    "PROMPTPurify/main/models/l5e/model.int8.onnx"
)


def _get_size_mb(path: Path) -> str:
    size_bytes = path.stat().st_size
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _download() -> None:
    import urllib.request
    import urllib.error

    _logger.info(
        "[promptpurify] Downloading L5e ONNX model (~14 MB) from GitHub..."
    )
    try:
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        size = _get_size_mb(_MODEL_PATH)
        _logger.info(
            "[promptpurify] L5e model downloaded successfully: %s (%s)",
            _MODEL_FILE, size,
        )
    except (urllib.error.URLError, OSError, ConnectionError) as e:
        _logger.error(
            "[promptpurify] Failed to download L5e model: %s", e
        )
        if _MODEL_PATH.exists():
            try:
                _MODEL_PATH.unlink()
            except OSError:
                pass


def ensure_l5e_model() -> None:
    """Check if the L5e model exists; if not, spawn a background download.

    The thread is daemon so it won't block server shutdown.
    Once the model file is present on disk, no thread is created.
    """
    if _MODEL_PATH.exists():
        size = _get_size_mb(_MODEL_PATH)
        _logger.info(
            "[promptpurify] L5e model already present: %s (%s)",
            _MODEL_FILE, size,
        )
        return

    _logger.info(
        "[promptpurify] L5e model not found — spawning background download thread"
    )
    t = threading.Thread(target=_download, daemon=True, name="l5e-download")
    t.start()
