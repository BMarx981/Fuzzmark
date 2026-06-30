"""Pure-Python tests for the in-process job registry.

No browser. Verifies registry storage, the spawn wrapper's event/state
transitions for normal return / cancel / error, the cancel-flag check,
and that `Job.stream()` is replayable from any starting point so an SSE
client that connects mid-run sees the full history.
"""

from __future__ import annotations

import threading
import time

import pytest

from fuzzmark.jobs import (
    STATE_CANCELLED,
    STATE_ERROR,
    STATE_FINISHED,
    STATE_RUNNING,
    TERMINAL_STATES,
    Job,
    JobCancelled,
    check_cancel,
    create_job,
    get_job,
    spawn,
)


def _wait_terminal(job: Job, timeout: float = 1.0) -> None:
    """Block until the worker thread sets a terminal state."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if job.state in TERMINAL_STATES:
            return
        time.sleep(0.005)
    raise AssertionError(f"job did not reach a terminal state within {timeout}s")


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
    def test_emits_job_started_and_finished_in_order(self) -> None:
        job = create_job("run")

        def target(j, on_event, cancel):
            on_event({"event": "step_finished", "index": 0})
            return {"ok": True}

        thread = spawn(job, target)
        thread.join(timeout=1.0)
        assert not thread.is_alive()

        kinds = [e["event"] for e in job.events]
        assert kinds == ["job_started", "step_finished", "finished"]
        assert job.events[0]["job_id"] == job.id
        assert job.events[0]["kind"] == "run"
        assert job.events[-1]["result"] == {"ok": True}

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
        _wait_terminal(job)

    def test_non_dict_return_becomes_none_result(self) -> None:
        job = create_job("run")

        def target(j, on_event, cancel):
            return "not-a-dict"

        spawn(job, target)
        _wait_terminal(job)
        assert job.events[-1] == {"event": "finished", "result": None}
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

        _wait_terminal(job)
        assert job.events[-1] == {"event": "cancelled"}
        assert job.state == STATE_CANCELLED
        assert job.result is None

    def test_cancel_before_target_runs_still_handled(self) -> None:
        job = create_job("run")
        job.cancel_event.set()

        def target(j, on_event, cancel):
            check_cancel(j)
            return {"unreachable": True}

        spawn(job, target)
        _wait_terminal(job)
        assert job.events[-1] == {"event": "cancelled"}
        assert job.state == STATE_CANCELLED


class TestSpawnError:
    def test_exception_becomes_error_event(self) -> None:
        job = create_job("run")

        def target(j, on_event, cancel):
            raise RuntimeError("kaboom")

        spawn(job, target)
        _wait_terminal(job)
        assert job.events[-1] == {"event": "error", "message": "kaboom"}
        assert job.state == STATE_ERROR
        assert job.error == "kaboom"


class TestSnapshot:
    def test_snapshot_finished(self) -> None:
        job = create_job("run")
        spawn(job, lambda j, on_event, cancel: {"answer": 42})
        _wait_terminal(job)

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
        _wait_terminal(job)

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
        _wait_terminal(job)
        assert job.events[-1]["result"] == {"sum": 6}


class TestStreamReplay:
    def test_stream_after_terminal_yields_full_history(self) -> None:
        job = create_job("run")

        def target(j, on_event, cancel):
            for i in range(3):
                on_event({"event": "tick", "i": i})
            return {"done": True}

        spawn(job, target)
        _wait_terminal(job)

        # Subscriber starts AFTER the job is done. Should still see everything.
        events: list = []
        for evt in job.stream(keepalive_interval=0.05):
            if evt is None:
                continue
            events.append(evt)
        kinds = [e["event"] for e in events]
        assert kinds == ["job_started", "tick", "tick", "tick", "finished"]

    def test_stream_blocks_until_event_arrives(self) -> None:
        job = create_job("run")
        proceed = threading.Event()

        def target(j, on_event, cancel):
            proceed.wait(timeout=1.0)
            on_event({"event": "mid"})
            return {"done": True}

        spawn(job, target)
        stream_iter = job.stream(keepalive_interval=0.05)

        # First event: job_started, available almost immediately.
        first = next(e for e in stream_iter if e is not None)
        assert first["event"] == "job_started"

        # Next consumer call would block until proceed is set.
        # Use a thread to verify blocking semantics without deadlocking.
        got: list = []

        def consume() -> None:
            for evt in stream_iter:
                if evt is None:
                    continue
                got.append(evt)
                if evt["event"] == "finished":
                    return

        reader = threading.Thread(target=consume, daemon=True)
        reader.start()
        time.sleep(0.05)
        assert got == []  # blocked

        proceed.set()
        reader.join(timeout=1.0)
        assert [e["event"] for e in got] == ["mid", "finished"]

    def test_stream_keepalive_yields_none_while_idle(self) -> None:
        job = create_job("run")
        proceed = threading.Event()

        def target(j, on_event, cancel):
            proceed.wait(timeout=2.0)
            return {"done": True}

        spawn(job, target)
        # Drain job_started so the stream is idle.
        stream_iter = job.stream(keepalive_interval=0.05)
        first = next(stream_iter)
        assert first["event"] == "job_started"

        # Now stream should yield None (keepalive) while waiting.
        ticks = 0

        def consume() -> None:
            nonlocal ticks
            for evt in stream_iter:
                if evt is None:
                    ticks += 1
                    if ticks >= 2:
                        proceed.set()
                else:
                    if evt["event"] == "finished":
                        return

        reader = threading.Thread(target=consume, daemon=True)
        reader.start()
        reader.join(timeout=2.0)
        assert ticks >= 2

    def test_two_concurrent_subscribers_see_same_terminal_state(self) -> None:
        job = create_job("run")

        def target(j, on_event, cancel):
            on_event({"event": "mid"})
            return {"done": True}

        spawn(job, target)

        a: list = []
        b: list = []

        def consume(out: list) -> None:
            for evt in job.stream(keepalive_interval=0.05):
                if evt is None:
                    continue
                out.append(evt["event"])
                if evt["event"] == "finished":
                    return

        ta = threading.Thread(target=consume, args=(a,), daemon=True)
        tb = threading.Thread(target=consume, args=(b,), daemon=True)
        ta.start()
        tb.start()
        ta.join(timeout=1.0)
        tb.join(timeout=1.0)

        assert a == b == ["job_started", "mid", "finished"]
