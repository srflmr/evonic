"""
process_tracker — Global registry of running subprocesses per session.

Allows request_stop() to kill a long-running tool immediately by session_id,
regardless of which backend (Docker, Local, SSH) is executing it.

Supports backend-specific killing strategies:
- **Docker**: Use ``container_id`` to kill orphan processes inside the
  container after the exec process is terminated.
- **Local**: Use ``kill_method='killpg'`` to kill the entire process group
  (parent + all children) in one shot.
- **SSH**: No special handling needed; the existing SSH backend's ``.kill()``
  method already handles remote cleanup.

Usage:
    from backend.tools.lib.process_tracker import process_tracker

    # Docker backend — pass container_id for orphan cleanup
    process_tracker.register(session_id, proc, pid, container_id=cid)

    # Local backend — pass kill_method='killpg' for process-group killing
    process_tracker.register(session_id, proc, pid, kill_method='killpg')

    try:
        ...  # polling loop
    finally:
        process_tracker.unregister(session_id)

    # From request_stop():
    process_tracker.kill(session_id)
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class ProcessTracker:
    """Thread-safe registry of running subprocesses, keyed by session_id.

    Supports optional ``container_id`` (for Docker orphan cleanup) and
    ``kill_method`` (e.g. ``'killpg'`` for local process-group killing).
    """

    def __init__(self):
        self._processes: dict = {}
        self._lock = threading.Lock()

    def register(self, session_id: str, proc, pid: int,
                 container_id: str = None, kill_method: str = None) -> None:
        """Store a running subprocess for a session.

        Args:
            session_id: The chat session ID.
            proc: A subprocess.Popen object (for Docker/Local) or any object
                  with a .kill() method (for SSH).
            pid: The process PID (or remote PID for SSH).
            container_id: Optional Docker container ID; used during kill() to
                clean up orphan processes inside the container.
            kill_method: Optional killing strategy. Use ``'killpg'`` for local
                backends to kill the entire process group.
        """
        with self._lock:
            self._processes[session_id] = {
                'proc': proc,
                'pid': pid,
                'started_at': __import__('time').time(),
                'container_id': container_id,
                'kill_method': kill_method,
            }

    def is_registered(self, session_id: str) -> bool:
        """Return True if a process is currently registered for *session_id*."""
        with self._lock:
            return session_id in self._processes

    def unregister(self, session_id: str) -> None:
        """Remove the process entry after execution completes naturally."""
        with self._lock:
            self._processes.pop(session_id, None)

    def kill(self, session_id: str) -> None:
        """Terminate and kill the running process for a session.

        Safe to call even if the process has already finished or was never
        registered (no-op for missing entries).

        After the primary process is killed, applies backend-specific cleanup:

        - If ``container_id`` was provided at registration, runs
          ``docker exec <id> sh -c 'kill -9 -1'`` to kill any orphan
          processes still running inside the Docker container.
        - If ``kill_method='killpg'`` was provided, sends SIGKILL to the
          entire process group via ``os.killpg()``.
        """
        with self._lock:
            info = self._processes.pop(session_id, None)
        if info is None:
            return
        proc = info['proc']
        pid = info['pid']
        try:
            logger.info(
                '[process_tracker] Killing pid=%s for session %s',
                pid, session_id[:12],
            )
            # If the object has its own .kill() method (e.g. SSH backend),
            # delegate to it.
            if hasattr(proc, 'kill') and not isinstance(proc, __import__('subprocess').Popen):
                proc.kill()
            else:
                # Standard subprocess.Popen: terminate, wait, then kill
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except __import__('subprocess').TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
        except Exception as e:
            logger.warning(
                '[process_tracker] Error killing pid=%s for session %s: %s',
                pid, session_id[:12], e,
            )

        # --- Backend-specific orphan / process-group cleanup ---

        # If container_id is known, kill orphan processes inside the
        # Docker container.  ``kill -9 -1`` sends SIGKILL to every process
        # in the container *except* PID 1 (the sleep-infinity sentinel)
        # and the killing process itself — the container stays alive.
        container_id = info.get('container_id')
        if container_id:
            try:
                __import__('subprocess').run(
                    ['docker', 'exec', container_id, 'sh', '-c',
                     'kill -9 -1 2>/dev/null || true'],
                    timeout=5,
                )
            except Exception:
                pass  # Best-effort cleanup

        # If kill_method is 'killpg', kill the entire process group.
        # This ensures that for local backends the parent bash process
        # and all its children (e.g. sleep, background jobs) are
        # terminated together.
        kill_method = info.get('kill_method')
        if kill_method == 'killpg':
            try:
                __import__('os').killpg(info['pid'], __import__('signal').SIGKILL)
            except (ProcessLookupError, OSError):
                pass  # Process already gone


# Module-level singleton
process_tracker = ProcessTracker()
