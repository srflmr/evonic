"""
LocalBackend — runs bash and Python directly on the host via subprocess.

Used when sandbox_enabled=0 in agent_context. No container, no isolation.
"""

import os
import subprocess
import time

from backend.tools.lib.exec_backend import ExecutionBackend, truncate
from backend.tools.lib.process_tracker import process_tracker

try:
    from config import SANDBOX_WORKSPACE
except ImportError:
    SANDBOX_WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

_MAX_OUTPUT_BYTES = 64 * 1024  # 64 KB

# Directory containing the evonic -> runpy_helpers symlink, so that
# `from evonic import tree` works in non-sandbox (local) mode.
_HELPERS_PARENT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
_EVONIC_SYMLINK = os.path.join(_HELPERS_PARENT_DIR, 'evonic')


def _ensure_evonic_symlink():
    """Create evonic -> runpy_helpers symlink if it doesn't exist.

    In sandbox mode the runpy_helpers directory is mounted into the Docker
    container at /usr/local/lib/python3.11/site-packages/evonic/.  In local
    (non-sandbox) mode we create a symlink so the same ``from evonic import
    tree`` idiom works on the host.
    """
    if not os.path.exists(_EVONIC_SYMLINK):
        try:
            os.symlink('runpy_helpers', _EVONIC_SYMLINK)
        except OSError:
            pass  # best-effort; run_python will still set PYTHONPATH


_ensure_evonic_symlink()


class LocalBackend(ExecutionBackend):
    """Executes bash/python directly on the host (no sandboxing)."""

    def __init__(self, session_id: str = '', workspace: str = None):
        self._session_id = session_id
        self._workspace = workspace

    def _cwd(self) -> str:
        return os.path.abspath(self._workspace or SANDBOX_WORKSPACE)

    @staticmethod
    def _poll_proc(proc, input_data: str, timeout: int, t0: float):
        """Poll a Popen process in 1s intervals, returning (stdout, stderr, reason).

        Returns (None, None, reason) if the process was killed externally or
        timed out.  *reason* is ``'timeout'`` when the deadline was exceeded,
        or ``'killed'`` when the process died from a signal during normal
        execution (e.g. killed by process_tracker or by sudo/TTY failure).
        On success, *reason* is ``None``.
        """
        deadline = t0 + timeout
        while True:
            try:
                stdout, stderr = proc.communicate(input=input_data, timeout=1)
                input_data = None
                if proc.returncode is not None and proc.returncode < 0:
                    return None, None, 'killed'
                return stdout, stderr, None
            except subprocess.TimeoutExpired:
                input_data = None
                if proc.poll() is not None:
                    if proc.returncode < 0:
                        return None, None, 'killed'
                    try:
                        stdout, stderr = proc.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        stdout, stderr = proc.communicate(timeout=2)
                    return stdout, stderr, None
                if time.time() > deadline:
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=2)
                    return None, None, 'timeout'

    def run_bash(self, script: str, timeout: int, env: dict) -> dict:
        run_env = dict(os.environ)
        run_env.update(env)
        t0 = time.time()
        proc = subprocess.Popen(
            ['bash', '-s'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=self._cwd(), env=run_env,
        )
        process_tracker.register(self._session_id, proc, proc.pid)
        try:
            stdout, stderr, reason = self._poll_proc(proc, script, timeout, t0)
            if stdout is None:
                elapsed = round(time.time() - t0, 3)
                if reason == 'timeout':
                    return {
                        'error': f'Execution timed out after {timeout}s',
                        'exit_code': -1,
                        'execution_time': elapsed,
                    }
                # Process killed by signal — check if user requested the stop
                # (process_tracker.kill() unregisters before we get here)
                was_user_stop = not process_tracker.is_registered(self._session_id)
                if was_user_stop:
                    return {
                        'error': 'Execution stopped by user',
                        'exit_code': -9,
                        'execution_time': elapsed,
                    }
                sig = -proc.returncode if proc.returncode else 'unknown'
                return {
                    'error': f'Process killed by signal {sig}. This may happen when a command requires interactive input (e.g. sudo password prompt) that cannot be provided in this environment.',
                    'exit_code': proc.returncode or -9,
                    'execution_time': elapsed,
                }
        finally:
            process_tracker.unregister(self._session_id)
        elapsed = round(time.time() - t0, 3)
        return {
            'stdout': truncate(stdout, _MAX_OUTPUT_BYTES),
            'stderr': truncate(stderr, _MAX_OUTPUT_BYTES),
            'exit_code': proc.returncode,
            'execution_time': elapsed,
        }

    def run_python(self, code: str, timeout: int, env: dict) -> dict:
        run_env = dict(os.environ)
        run_env.update(env)
        existing = run_env.get('PYTHONPATH', '')
        run_env['PYTHONPATH'] = f"{_HELPERS_PARENT_DIR}{os.pathsep}{existing}".rstrip(os.pathsep)
        t0 = time.time()
        proc = subprocess.Popen(
            ['python3', '-'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=self._cwd(), env=run_env,
        )
        process_tracker.register(self._session_id, proc, proc.pid)
        try:
            stdout, stderr, reason = self._poll_proc(proc, code, timeout, t0)
            if stdout is None:
                elapsed = round(time.time() - t0, 3)
                if reason == 'timeout':
                    return {
                        'error': f'Execution timed out after {timeout}s',
                        'exit_code': -1,
                        'execution_time': elapsed,
                    }
                was_user_stop = not process_tracker.is_registered(self._session_id)
                if was_user_stop:
                    return {
                        'error': 'Execution stopped by user',
                        'exit_code': -9,
                        'execution_time': elapsed,
                    }
                sig = -proc.returncode if proc.returncode else 'unknown'
                return {
                    'error': f'Process killed by signal {sig}. This may happen when a command requires interactive input (e.g. sudo password prompt) that cannot be provided in this environment.',
                    'exit_code': proc.returncode or -9,
                    'execution_time': elapsed,
                }
        finally:
            process_tracker.unregister(self._session_id)
        elapsed = round(time.time() - t0, 3)
        return {
            'stdout': truncate(stdout, _MAX_OUTPUT_BYTES),
            'stderr': truncate(stderr, _MAX_OUTPUT_BYTES),
            'exit_code': proc.returncode,
            'execution_time': elapsed,
        }

    def destroy(self) -> dict:
        return {'result': 'ok', 'detail': 'LocalBackend has no resources to destroy.'}

    def status(self) -> dict:
        return {'backend': 'local', 'workspace': self._cwd()}

    # ------------------------------------------------------------------
    # File I/O — direct host filesystem (same as original tool behavior)
    # ------------------------------------------------------------------

    def file_exists(self, path: str) -> bool:
        return os.path.exists(path)

    def file_stat(self, path: str) -> dict:
        if not os.path.exists(path):
            return {'exists': False}
        size = os.path.getsize(path)
        is_binary = False
        if size > 0:
            try:
                with open(path, 'rb') as f:
                    is_binary = b'\x00' in f.read(8192)
            except Exception:
                pass
        return {'exists': True, 'size': size, 'is_binary': is_binary}

    def read_file(self, path: str) -> dict:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                return {'content': f.read()}
        except PermissionError:
            return {'error': 'Permission denied — cannot read this file.'}
        except IsADirectoryError:
            return {'error': f'Path is a directory, not a file: {path}'}
        except UnicodeDecodeError:
            return {'error': 'File contains non-UTF-8 characters.'}
        except Exception as e:
            return {'error': str(e)}

    def write_file(self, path: str, content: str, create_dirs: bool = True) -> dict:
        try:
            if create_dirs:
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {'ok': True}
        except PermissionError:
            return {'error': f'Permission denied writing: {path}'}
        except IsADirectoryError:
            return {'error': f'Path is a directory, not a file: {path}'}
        except Exception as e:
            return {'error': str(e)}

    def cat_file_bytes(self, path: str) -> dict:
        """Read a file as raw bytes directly from the host filesystem."""
        try:
            with open(path, 'rb') as f:
                return {'bytes': f.read()}
        except PermissionError:
            return {'error': 'Permission denied — cannot read this file.'}
        except FileNotFoundError:
            return {'error': f'File not found: {path}'}
        except IsADirectoryError:
            return {'error': f'Path is a directory, not a file: {path}'}
        except Exception as e:
            return {'error': str(e)}

    def delete_file(self, path: str) -> dict:
        """Delete a file from the host filesystem."""
        try:
            os.remove(path)
            return {'ok': True}
        except FileNotFoundError:
            return {'error': f'File not found: {path}'}
        except PermissionError:
            return {'error': f'Permission denied: {path}'}
        except IsADirectoryError:
            return {'error': f'Path is a directory, not a file: {path}'}
        except Exception as e:
            return {'error': str(e)}

    def make_dirs(self, path: str) -> dict:
        try:
            os.makedirs(path, exist_ok=True)
            return {'ok': True}
        except Exception as e:
            return {'error': str(e)}
