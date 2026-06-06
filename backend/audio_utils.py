"""
Audio conversion utilities for Evonic platform.

Provides shared audio format conversion (OGG -> WAV) used by Telegram
and WhatsApp channels to prepare voice messages for multimodal LLM APIs.
"""

import logging
import os
import subprocess
import uuid

_logger = logging.getLogger(__name__)

# How long ffmpeg may run before we consider it stalled (guards against
# pathological input).  30 seconds is generous -- typical OGG->WAV
# conversion of a <10 MB file finishes in under 1 second.
_FFMPEG_TIMEOUT_SECONDS = 30

# Maximum size in bytes we will attempt to convert (10 MB).
# Files larger than this are rejected upstream before reaching us,
# but this guard provides defence-in-depth against edge cases.
_MAX_CONVERT_BYTES = 10 * 1024 * 1024  # 10 MB


def convert_ogg_to_wav(ogg_bytes: bytes) -> bytes:
    """Convert OGG (Opus) audio to WAV using ffmpeg subprocess.

    Uses stdin/stdout pipes to avoid writing temporary files to the
    project directory.  Falls back to named temp files in ``/tmp``
    only when pipe mode fails (some ffmpeg builds / input types
    require seekable input).

    Args:
        ogg_bytes: Raw OGG audio bytes.

    Returns:
        WAV audio bytes (16-bit PCM, mono or stereo, original sample rate).

    Raises:
        RuntimeError: If ffmpeg is not available or conversion fails.
        ValueError: If input is empty or exceeds size limit.
    """
    if not ogg_bytes:
        raise ValueError("Cannot convert empty OGG data")

    if len(ogg_bytes) > _MAX_CONVERT_BYTES:
        raise ValueError(
            f"OGG data too large: {len(ogg_bytes)} bytes "
            f"(max {_MAX_CONVERT_BYTES})"
        )

    # Try pipe mode first (no temp files).
    try:
        return _convert_via_pipe(ogg_bytes)
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"ffmpeg OGG->WAV conversion timed out after "
            f"{_FFMPEG_TIMEOUT_SECONDS}s"
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg is not installed -- cannot convert OGG to WAV. "
            "Install ffmpeg on the server to enable voice message processing."
        )
    except Exception:
        # Pipe mode failed -- fall back to temp files.
        _logger.debug(
            "OGG->WAV pipe conversion failed, falling back to temp files",
            exc_info=True,
        )

    # Temp-file fallback.  NEVER write temp files into the project
    # directory -- use /tmp exclusively.
    return _convert_via_tempfiles(ogg_bytes)


def _convert_via_pipe(ogg_bytes: bytes) -> bytes:
    """Convert OGG->WAV using stdin/stdout pipes (no temp files)."""
    result = subprocess.run(
        [
            "ffmpeg",
            "-i", "pipe:0",       # read from stdin
            "-f", "wav",           # output format
            "-acodec", "pcm_s16le",  # 16-bit PCM little-endian
            "pipe:1",                # write to stdout
            "-loglevel", "error",   # suppress verbose ffmpeg output
            "-y",                     # overwrite output (N/A for pipes but safe)
        ],
        input=ogg_bytes,
        capture_output=True,
        timeout=_FFMPEG_TIMEOUT_SECONDS,
        check=True,
    )
    return result.stdout


def _convert_via_tempfiles(ogg_bytes: bytes) -> bytes:
    """Convert OGG->WAV using named temp files in /tmp.

    This is the fallback for ffmpeg builds or OGG inputs that cannot
    be read from a pipe (seekable requirement).

    CRITICAL: Temp files are written ONLY to /tmp -- NEVER inside the
    Evonic project directory.
    """
    uid = uuid.uuid4().hex[:12]
    ogg_path = os.path.join("/tmp", f"evonic_audio_{uid}.ogg")
    wav_path = os.path.join("/tmp", f"evonic_audio_{uid}.wav")

    try:
        # Write OGG bytes to temp file.
        with open(ogg_path, "wb") as f:
            f.write(ogg_bytes)

        # Convert via ffmpeg.
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-i", ogg_path,
                    "-f", "wav",
                    "-acodec", "pcm_s16le",
                    wav_path,
                    "-loglevel", "error",
                    "-y",
                ],
                capture_output=True,
                timeout=_FFMPEG_TIMEOUT_SECONDS,
                check=True,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"ffmpeg OGG->WAV conversion timed out after "
                f"{_FFMPEG_TIMEOUT_SECONDS}s"
            )
        except FileNotFoundError:
            raise RuntimeError(
                "ffmpeg is not installed -- cannot convert OGG to WAV. "
                "Install ffmpeg on the server to enable voice message processing."
            )

        # Read back the WAV output.
        with open(wav_path, "rb") as f:
            wav_bytes = f.read()

        return wav_bytes

    finally:
        # Best-effort cleanup of temp files.
        for path in (ogg_path, wav_path):
            try:
                if os.path.isfile(path):
                    os.unlink(path)
            except OSError:
                pass
