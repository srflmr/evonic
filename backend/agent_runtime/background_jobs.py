"""
background_jobs — Track long-running processes detached from the agent loop.

When a build/download is launched via the long_running_guard wrapper (tmux/
screen/nohup) and the user issues ``/detach``, the agent stops polling and the
process is handed off to a persisted scheduler job (APScheduler + SQLite). The
scheduler polls the OS process on an interval; on completion it feeds the result
back into the agent (via handle_message) so the agent summarizes the outcome for
the user, then self-deletes so the interval stops.

Using the scheduler (not an in-process thread) means tracking survives a server
restart: the poll schedule is reloaded from the DB on boot and keeps going.

The in-memory registry here is intentionally lightweight and transient — it only
holds the identity of jobs that have NOT been detached yet (populated by the bash
tool when it runs a wrapper). Once ``/detach`` fires, all state needed to resume
lives in the schedule's action_config, so losing the registry on restart is fine.
"""
from __future__ import annotations

import logging
import threading
import time
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

_logger = logging.getLogger(__name__)

# Poll cadence and a hard lifetime cap (also enforced via schedule max_runs).
_POLL_SECONDS = 30
_MAX_WATCH_SECONDS = 6 * 60 * 60          # 6 hours
_MAX_RUNS = _MAX_WATCH_SECONDS // _POLL_SECONDS  # backstop if self-cancel fails
_POLL_TIMEOUT = 15
_TAIL_LINES = 30

# owner_type for internal poll schedules — distinct so they stay out of the
# user-facing routines UI (which lists by a specific owner_type).
SCHEDULE_OWNER_TYPE = "background_job"


@dataclass
class BackgroundJob:
    job_id: str
    session_id: str
    session_name: str
    log_file: str
    pid_file: str
    command: str
    started_at: float
    detached: bool = False
    schedule_id: Optional[str] = None


class BackgroundJobRegistry:
    """Thread-safe in-memory registry of not-yet-detached background jobs."""

    def __init__(self):
        self._jobs: Dict[str, BackgroundJob] = {}
        self._guard = threading.Lock()
        self._counter = 0

    def register(self, session_id: str, session_name: str, log_file: str,
                 pid_file: str, command: str) -> BackgroundJob:
        with self._guard:
            for j in self._jobs.values():
                if j.session_name == session_name:
                    return j  # dedup: wrapper re-run
            self._counter += 1
            job = BackgroundJob(
                job_id=f"job{self._counter}",
                session_id=session_id,
                session_name=session_name,
                log_file=log_file,
                pid_file=pid_file,
                command=command,
                started_at=time.time(),
            )
            self._jobs[job.job_id] = job
            _logger.info("[bgjob] registered %s session=%s sess=%s cmd=%r",
                         job.job_id, session_id, session_name, command)
            return job

    def active_for_session(self, session_id: str) -> List[BackgroundJob]:
        """Jobs in this session not yet detached (candidates for /detach)."""
        with self._guard:
            return [j for j in self._jobs.values()
                    if j.session_id == session_id and not j.detached]

    def list_for_session(self, session_id: str) -> List[BackgroundJob]:
        with self._guard:
            return [j for j in self._jobs.values() if j.session_id == session_id]

    def mark_detached(self, job_id: str, schedule_id: Optional[str]) -> None:
        with self._guard:
            j = self._jobs.get(job_id)
            if j:
                j.detached = True
                j.schedule_id = schedule_id


# Singleton
background_jobs = BackgroundJobRegistry()


def parse_wrapper_script(script: str) -> Optional[dict]:
    """Extract job identity from a long_running_guard wrapper script.

    Returns dict(session_name, log_file, pid_file, command) when the script is a
    generated wrapper (starts with the bypass marker), else None.
    """
    from backend.tools.lib.long_running_guard import BYPASS_MARKER

    if not script.lstrip().startswith(BYPASS_MARKER):
        return None

    def _grab(pattern: str) -> str:
        m = re.search(pattern, script)
        return m.group(1) if m else ""

    session_name = _grab(r'SESS="([^"]+)"')
    if not session_name:
        return None
    log_file = _grab(r'LOG_FILE="([^"]+)"')
    pid_file = _grab(r'PID_FILE="([^"]+)"')

    cmd_m = re.search(r"SCRIPT_CMD='\{ (.*?); \}; EC=\$\?", script, re.DOTALL)
    command = cmd_m.group(1).strip() if cmd_m else session_name
    command = command.replace("'\\''", "'")  # undo wrapper's quote escaping

    return {
        "session_name": session_name,
        "log_file": log_file,
        "pid_file": pid_file,
        "command": command,
    }


def create_detach_schedule(job: BackgroundJob, agent_id: str,
                           external_user_id: Optional[str],
                           channel_id: Optional[str]) -> Optional[str]:
    """Create a persisted scheduler job that polls `job` to completion.

    Returns the schedule_id, or None on failure.
    """
    from backend.scheduler import scheduler

    action_config = {
        "session_name": job.session_name,
        "log_file": job.log_file,
        "pid_file": job.pid_file,
        "command": job.command,
        "session_id": job.session_id,
        "agent_id": agent_id,
        "external_user_id": external_user_id,
        "channel_id": channel_id,
        "deadline_ts": job.started_at + _MAX_WATCH_SECONDS,
    }
    try:
        sched = scheduler.create_schedule(
            name=f"bgjob:{job.command[:40]}",
            owner_type=SCHEDULE_OWNER_TYPE,
            owner_id=agent_id,
            trigger_type="interval",
            trigger_config={"seconds": _POLL_SECONDS},
            action_type="poll_background_job",
            action_config=action_config,
            max_runs=_MAX_RUNS,
            metadata={"session_id": job.session_id},
        )
        return sched.get("id") if sched else None
    except Exception as e:
        _logger.warning("[bgjob] failed to create poll schedule: %s", e)
        return None


def run_poll_action(action_config: dict) -> dict:
    """Poll one background job (called by the scheduler each interval tick).

    Returns {'done': bool, 'state': str}. When done, the agent has been notified
    and the caller (scheduler) self-cancels the schedule.
    """
    from backend.tools.lib.exec_backend import registry
    from backend.tools.lib.long_running_guard import build_status_scripts
    from models.db import db

    session_id = action_config["session_id"]
    session_name = action_config["session_name"]
    log_file = action_config["log_file"]
    pid_file = action_config["pid_file"]
    deadline_ts = action_config.get("deadline_ts") or 0

    scripts = build_status_scripts(session_name, log_file, pid_file)
    agent = db.get_agent(action_config["agent_id"]) or {}

    try:
        backend = registry.get_backend(session_id, agent)
    except Exception as e:
        _logger.warning("[bgjob] backend resolve failed: %s", e)
        return {"done": False, "state": "backend_error"}

    timed_out = deadline_ts and time.time() > deadline_ts

    if not timed_out:
        try:
            res = backend.run_bash(scripts["check_status_script"], _POLL_TIMEOUT, {})
            out = (res.get("stdout") or "")
        except Exception as e:
            _logger.warning("[bgjob] status poll failed: %s", e)
            return {"done": False, "state": "poll_error"}
        if "DONE" not in out:
            return {"done": False, "state": "running"}

    # Completed (or timed out) — gather exit code + log tail, then notify.
    exit_code: Optional[int] = None
    tail = ""
    if not timed_out:
        try:
            ec = backend.run_bash(scripts["check_exit_code_script"], _POLL_TIMEOUT, {})
            ec_out = (ec.get("stdout") or "").strip()
            if ec_out.isdigit():
                exit_code = int(ec_out)
        except Exception:
            pass
    try:
        tr = backend.run_bash(f"tail -n {_TAIL_LINES} {log_file}", _POLL_TIMEOUT, {})
        tail = (tr.get("stdout") or "")
    except Exception:
        pass

    status = "timeout" if timed_out else "done"
    _trigger_agent_summary(action_config, status=status,
                           exit_code=exit_code, tail=tail)
    return {"done": True, "state": status}


def _trigger_agent_summary(action_config: dict, status: str,
                           exit_code: Optional[int], tail: str) -> None:
    """Feed the finished job back into the agent so it summarizes for the user.

    Routes through handle_message (same path scheduled prompts use) so the
    agent's reply is delivered via the normal pipeline (web SSE + channel).
    """
    command = action_config.get("command", "the background job")
    log_file = action_config.get("log_file", "")
    tail = (tail or "").strip()

    if status == "done":
        outcome = ("finished successfully (exit code 0)"
                   if exit_code in (0, None)
                   else f"finished with FAILURE (exit code {exit_code})")
    else:
        outcome = "is still running past the watch limit; monitoring was stopped"

    trigger = (
        "[SYSTEM] A background job you detached has finished — there is no user "
        "message to answer; proactively report the outcome. The background "
        "tracking schedule has already been removed automatically, so no cleanup "
        "is needed on your part.\n\n"
        f"Command: `{command}`\n"
        f"Outcome: {outcome}\n"
        f"Log file: {log_file}\n"
    )
    if tail:
        trigger += f"\nLast output:\n```\n{tail[-1500:]}\n```\n"
    trigger += (
        "\nSummarize the result for the user concisely and naturally. If it "
        "failed, note the likely cause from the output and suggest a next step."
    )

    try:
        from backend.agent_runtime import agent_runtime
        agent_runtime.handle_message(
            agent_id=action_config["agent_id"],
            external_user_id=action_config.get("external_user_id") or "__system__",
            message=trigger,
            channel_id=action_config.get("channel_id"),
            metadata={"background_job_trigger": True},
        )
    except Exception as e:
        _logger.warning("[bgjob] summary trigger failed: %s", e)
