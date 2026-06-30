"""In-process background-job registry for long-running engine operations.

Long-running endpoints (test runs, scans, extracts) execute on a worker
thread spawned through `spawn`. Each `Job` keeps an append-only event log
(`Job.events`) plus a `threading.Condition`; the SSE handler iterates
`Job.stream()` to replay history and block-wait for new events as they
arrive. Multiple SSE subscribers can read the same job concurrently —
each holds its own index into the list.

A `threading.Event` cancel flag is checked by the worker between steps
via `check_cancel`. The registry is a module-level `dict` guarded by a
lock for read-modify-write. The engine is a single process; completed
jobs stay in memory for the process lifetime, which is fine at desktop
scale.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional


log = logging.getLogger(__name__)


STATE_PENDING = "pending"
STATE_RUNNING = "running"
STATE_FINISHED = "finished"
STATE_ERROR = "error"
STATE_CANCELLED = "cancelled"

TERMINAL_STATES = frozenset({STATE_FINISHED, STATE_ERROR, STATE_CANCELLED})


class JobCancelled(Exception):
    """Raised inside a worker when `check_cancel` sees the cancel flag set."""


@dataclass
class Job:
    id: str
    kind: str
    state: str = STATE_PENDING
    events: list[dict] = field(default_factory=list)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    started_at: float = field(default_factory=time.time)
    result: Optional[dict] = None
    error: Optional[str] = None
    _cond: threading.Condition = field(default_factory=threading.Condition)

    def push(self, event: dict, *, final_state: Optional[str] = None) -> None:
        """Append `event` (and optionally flip `state`) atomically, wake waiters."""
        with self._cond:
            self.events.append(event)
            if final_state is not None:
                self.state = final_state
            self._cond.notify_all()

    def stream(self, *, keepalive_interval: float = 30.0) -> Iterator[Optional[dict]]:
        """Yield every event in order, blocking for new ones until terminal.

        Each subscriber maintains its own index, so multiple consumers see
        the same history and converge to the same terminal event. Yields
        `None` every `keepalive_interval` seconds while idle so SSE handlers
        can emit comment frames and keep the socket alive through proxies.
        """
        idx = 0
        while True:
            with self._cond:
                # Wait until there is a new event, the job has terminated,
                # or the keepalive window has elapsed.
                while idx >= len(self.events) and self.state not in TERMINAL_STATES:
                    if not self._cond.wait(timeout=keepalive_interval):
                        break  # timed out — leave the wait loop to keepalive
                if idx >= len(self.events):
                    if self.state in TERMINAL_STATES:
                        return
                    evt = None  # keepalive tick
                else:
                    evt = self.events[idx]
                    idx += 1
            yield evt

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
      pushes `{"event":"error","message":str(exc)}` and logs the traceback.

    The terminal event and the state flip are pushed atomically so SSE
    subscribers never see a terminal state with the final event still in
    flight.
    """

    def _on_event(evt: dict) -> None:
        job.push(evt)

    def _run() -> None:
        with job._cond:
            job.state = STATE_RUNNING
            job.events.append(
                {"event": "job_started", "job_id": job.id, "kind": job.kind}
            )
            job._cond.notify_all()
        try:
            result = target(job, _on_event, job.cancel_event, *args, **kwargs)
        except JobCancelled:
            job.push({"event": "cancelled"}, final_state=STATE_CANCELLED)
        except Exception as exc:  # noqa: BLE001 — surfaced to client via event
            log.exception("job %s (%s) failed", job.id, job.kind)
            job.error = str(exc)
            job.push(
                {"event": "error", "message": str(exc)}, final_state=STATE_ERROR
            )
        else:
            job.result = result if isinstance(result, dict) else None
            job.push(
                {"event": "finished", "result": job.result},
                final_state=STATE_FINISHED,
            )

    thread = threading.Thread(target=_run, name=f"job-{job.kind}-{job.id[:8]}", daemon=True)
    thread.start()
    return thread
