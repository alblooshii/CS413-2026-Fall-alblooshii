"""Hard-deadline execution: one worker process per call, terminated on expiry.

A thread or a timer cannot stop a running recursive computation; a process can
be killed. The deadline clock starts when the worker reports it has finished
importing LAMBDA3, so process start-up does not eat the budget.
"""

import multiprocessing
import sys
import traceback

DEADLINE_SECONDS = 5
STARTUP_SECONDS = 30.0
MEMORY_LIMIT_BYTES = 1 << 30  # best effort, Linux only

_ctx = multiprocessing.get_context("spawn")  # fork is unsafe once Flask has threads


class DeadlineExceeded(Exception):
    """The worker did not finish within the deadline and was terminated."""


class WorkerFailed(Exception):
    """The worker died or never started, without a result."""


def _child(conn, op, source, target):
    try:
        if sys.platform.startswith("linux"):
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
        from . import lambda_service
        conn.send(("ready", None))
        outcome = lambda_service.execute(op, source, target)
    except BaseException:  # noqa: BLE001 - report as data; the parent logs it
        outcome = {"ok": False, "failure": {"kind": "internal", "log": traceback.format_exc()}}
    conn.send(("done", outcome))
    conn.close()


def _recv(conn, timeout):
    """Return ('msg', message), ('timeout', None) or ('eof', None)."""
    if not conn.poll(timeout):
        return "timeout", None
    try:
        return "msg", conn.recv()
    except EOFError:
        return "eof", None


def run_with_deadline(op, source, target=None, *, timeout=DEADLINE_SECONDS):
    """Run lambda_service.execute in a worker process; kill it after `timeout` seconds."""
    parent, child = _ctx.Pipe(duplex=False)
    proc = _ctx.Process(target=_child, args=(child, op, source, target), daemon=True)
    proc.start()
    child.close()
    try:
        state, msg = _recv(parent, STARTUP_SECONDS)
        if state != "msg":
            raise WorkerFailed(f"worker did not start ({state})")
        if msg[0] == "ready":
            state, msg = _recv(parent, timeout)
            if state == "timeout":
                raise DeadlineExceeded()
            if state == "eof":
                raise WorkerFailed(f"worker died (exit code {proc.exitcode})")
        return msg[1]
    finally:
        if proc.is_alive():
            proc.terminate()
            proc.join(1)
            if proc.is_alive():
                proc.kill()
        proc.join()
        parent.close()
