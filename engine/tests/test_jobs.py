"""Pure-Python tests for the in-process job registry.

No browser. Verifies registry storage, the spawn wrapper's event/state
transitions for normal return / cancel / error, the cancel-flag check,
and the trailing queue sentinel that lets SSE consumers stop polling.
"""

from __future__ import annotations

import queue
import threading

import pytest

from fuzzmark.jobs import (
    QUEUE_SENTINEL,
    STATE_CANCELLED,
    STATE_ERROR,
    STATE_FINISHED,
    STATE_RUNNING,
    Job,
    JobCancelled,
    check_cancel,
    create_job,
    get_job,
    spawn,
)


def _drain(job: Job, timeout: float = 1.0) -> list:
    """Pop events from the job queue, stopping at the sentinel."""
    events = []
    while True:
        evt = job.queue.get(timeout=timeout)
        if evt is QUEUE_SENTINEL:
            return events
        events.append(evt)


class TestRegistry:
    def test_create_assigns_uuid_and_registers(self) -> None:
        job = create_job("run")
        assert job.kind == "run"
        assert isinstance(job.id, str) and len(job.id) >= 8
        assert get_job(job.id) is job

    def test_unique_ids(self) -> None:
        ids = {create_job("run").id for _ in range(20)}
        assert len(ids) == 20

    def test_unknown_id_returns_none(self) -> None:
        assert get_job("nope") is None


class TestCheckCancel:
    def test_no_op_when_flag_unset(self) -> None:
        job = create_job("run")
        check_cancel(job)  # does not raise

    def test_raises_when_flag_set(self) -> None:
        job = create_job("run")
        job.cancel_event.set()
        with pytest.raises(JobCancelled):
            check_cancel(job)


class TestSpawnHappyPath:
    def test_emits_started_finished_sentinel_in_order(self) -> None:
        job = create_job("run")

        def target(j, on_event, cancel):
            on_event({"event": "step_finished", "index": 0})
            return {"ok": True}

        thread = spawn(job, target)
        thread.join(timeout=1.0)
        assert not thread.is_alive()

        events = _drain(job)
        assert [e["event"] for e in events] == ["job_started", "step_finished", "finished"]
        assert events[0]["job_id"] == job.id
        assert events[0]["kind"] == "run"
        assert events[-1]["result"] == {"ok": True}

        assert job.state == STATE_FINISHED
        assert job.result == {"ok": True}
        assert job.error is None

    def test_running_state_is_observable_mid_flight(self) -> None:
        job = create_job("run")
        proceed = threading.Event()
        saw_running = threading.Event()

        def target(j, on_event, cancel):
            if j.state == STATE_RUNNING:
                saw_running.set()
            proceed.wait(timeout=1.0)
            return None

        spawn(job, target)
        assert saw_running.wait(timeout=1.0)
        proceed.set()
        _drain(job)

    def test_non_dict_return_becomes_none_result(self) -> None:
        job = create_job("run")

        def target(j, on_event, cancel):
            return "not-a-dict"

        spawn(job, target)
        events = _drain(job)
        assert events[-1] == {"event": "finished", "result": None}
        assert job.result is None


class TestSpawnCancel:
    def test_cancelled_event_and_state(self) -> None:
        job = create_job("run")
        released = threading.Event()

        def target(j, on_event, cancel):
            released.wait(timeout=1.0)
            check_cancel(j)
            return {"unreachable": True}

        spawn(job, target)
        job.cancel_event.set()
        released.set()

        events = _drain(job)
        assert events[-1] == {"event": "cancelled"}
        assert job.state == STATE_CANCELLED
        assert job.result is None

    def test_cancel_before_target_runs_still_handled(self) -> None:
        job = create_job("run")
        job.cancel_event.set()

        def target(j, on_event, cancel):
            check_cancel(j)
            return {"unreachable": True}

        spawn(job, target)
        events = _drain(job)
        assert events[-1] == {"event": "cancelled"}
        assert job.state == STATE_CANCELLED


class TestSpawnError:
    def test_exception_becomes_error_event(self) -> None:
        job = create_job("run")

        def target(j, on_event, cancel):
            raise RuntimeError("kaboom")

        spawn(job, target)
        events = _drain(job)
        assert events[-1] == {"event": "error", "message": "kaboom"}
        assert job.state == STATE_ERROR
        assert job.error == "kaboom"


class TestSnapshot:
    def test_snapshot_finished(self) -> None:
        job = create_job("run")
        spawn(job, lambda j, on_event, cancel: {"answer": 42})
        _drain(job)

        snap = job.snapshot()
        assert snap["job_id"] == job.id
        assert snap["kind"] == "run"
        assert snap["state"] == STATE_FINISHED
        assert snap["result"] == {"answer": 42}
        assert "error" not in snap

    def test_snapshot_error_includes_message(self) -> None:
        job = create_job("run")

        def boom(j, on_event, cancel):
            raise ValueError("nope")

        spawn(job, boom)
        _drain(job)

        snap = job.snapshot()
        assert snap["state"] == STATE_ERROR
        assert snap["error"] == "nope"
        assert "result" not in snap


class TestArgsForwarding:
    def test_positional_and_kwargs_reach_target(self) -> None:
        job = create_job("run")

        def target(j, on_event, cancel, a, b, *, c):
            return {"sum": a + b + c}

        spawn(job, target, 1, 2, c=3)
        events = _drain(job)
        assert events[-1]["result"] == {"sum": 6}


class TestQueueDrainSemantics:
    def test_sentinel_is_last_item(self) -> None:
        job = create_job("run")

        def target(j, on_event, cancel):
            for i in range(3):
                on_event({"event": "tick", "i": i})
            return {"done": True}

        spawn(job, target)
        events: list = []
        while True:
            evt = job.queue.get(timeout=1.0)
            if evt is QUEUE_SENTINEL:
                break
            events.append(evt)
        with pytest.raises(queue.Empty):
            job.queue.get_nowait()
        kinds = [e["event"] for e in events]
        assert kinds == ["job_started", "tick", "tick", "tick", "finished"]
