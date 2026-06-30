"""In-process background-job registry for long-running engine operations.

Long-running endpoints (test runs, scans, extracts) execute on a worker
thread spawned through `spawn`. Each `Job` owns an event `queue.Queue`
that the worker pushes progress events into; an HTTP SSE handler pulls
from the same queue and writes events to the client. A `threading.Event`
cancel flag is checked by the worker between steps via `check_cancel`.

The registry is a module-level `dict` guarded by a lock for read-modify-
write. The engine is a single process — completed jobs stay in memory
for the process lifetime, which is fine at desktop scale.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


log = logging.getLogger(__name__)


STATE_PENDING = "pending"
STATE_RUNNING = "running"
STATE_FINISHED = "finished"
STATE_ERROR = "error"
STATE_CANCELLED = "cancelled"

TERMINAL_STATES = frozenset({STATE_FINISHED, STATE_ERROR, STATE_CANCELLED})

# Pushed to the queue after the final event so SSE consumers can break
# out of their `queue.get()` loop without polling.
QUEUE_SENTINEL: None = None


class JobCancelled(Exception):
    """Raised inside a worker when `check_cancel` sees the cancel flag set."""


@dataclass
class Job:
    id: str
    kind: str
    state: str = STATE_PENDING
    queue: "queue.Queue[Optional[dict]]" = field(default_factory=queue.Queue)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    started_at: float = field(default_factory=time.time)
    result: Optional[dict] = None
    error: Optional[str] = None

    def snapshot(self) -> dict:
        """Return a JSON-safe view of the job's terminal state."""
        out: dict[str, Any] = {
            "job_id": self.id,
            "kind": self.kind,
            "state": self.state,
            "started_at": self.started_at,
        }
        if self.result is not None:
            out["result"] = self.result
        if self.error is not None:
            out["error"] = self.error
        return out


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def create_job(kind: str) -> Job:
    """Allocate a new `Job` and register it under a fresh uuid4."""
    job = Job(id=uuid.uuid4().hex, kind=kind)
    with _lock:
        _jobs[job.id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    """Return the registered job, or `None` if no such id."""
    with _lock:
        return _jobs.get(job_id)


def check_cancel(job: Job) -> None:
    """Raise `JobCancelled` if the job's cancel flag has been set."""
    if job.cancel_event.is_set():
        raise JobCancelled()


# A worker target receives the job, an `on_event(dict)` callback, the cancel
# event, and any args supplied at spawn time. It returns the dict that should
# be attached to the terminal `finished` event (or `None`).
WorkerTarget = Callable[..., Optional[dict]]


def spawn(job: Job, target: WorkerTarget, *args: Any, **kwargs: Any) -> threading.Thread:
    """Run `target` in a daemon thread, translating return / raise into events.

    The wrapper:
    - flips `state` to RUNNING and pushes an `event=job_started` marker
      (so SSE consumers see the queue is alive even before the worker
      emits its first domain event);
    - calls `target(job, on_event, cancel_event, *args, **kwargs)`;
    - on normal return: stores `result`, sets state FINISHED, pushes
      `{"event":"finished","result":result}`;
    - on `JobCancelled`: sets state CANCELLED, pushes `{"event":"cancelled"}`;
    - on any other exception: stores `error=str(exc)`, sets state ERROR,
      pushes `{"event":"error","message":str(exc)}` and logs the traceback;
    - always pushes `QUEUE_SENTINEL` so the SSE loop can exit cleanly.
    """

    def _on_event(evt: dict) -> None:
        job.queue.put(evt)

    def _run() -> None:
        job.state = STATE_RUNNING
        _on_event({"event": "job_started", "job_id": job.id, "kind": job.kind})
        try:
            result = target(job, _on_event, job.cancel_event, *args, **kwargs)
        except JobCancelled:
            job.state = STATE_CANCELLED
            _on_event({"event": "cancelled"})
        except Exception as exc:  # noqa: BLE001 — surfaced to client via event
            log.exception("job %s (%s) failed", job.id, job.kind)
            job.state = STATE_ERROR
            job.error = str(exc)
            _on_event({"event": "error", "message": str(exc)})
        else:
            job.result = result if isinstance(result, dict) else None
            job.state = STATE_FINISHED
            _on_event({"event": "finished", "result": job.result})
        finally:
            job.queue.put(QUEUE_SENTINEL)

    thread = threading.Thread(target=_run, name=f"job-{job.kind}-{job.id[:8]}", daemon=True)
    thread.start()
    return thread
