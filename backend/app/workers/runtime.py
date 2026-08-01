"""Shared runtime for standalone worker/scheduler processes.

Provides a resilient, signal-aware poll loop

* graceful shutdown on SIGTERM/SIGINT (drains the in-flight tick, then exits)
  the contract Kubernetes and Docker use when stopping a pod/container
* a fresh DB session per tick, always closed, so a poisoned session never
  wedges the loop
* per-tick exception isolation with backoff so one bad tick cannot crash the
  process
* structured logging of throughput.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import time
from typing import Callable

from sqlalchemy.orm import Session

from backend.app.db.database import SessionLocal
from backend.app.db import registry as _registry  # noqa: F401 — register all ORM mappers

logger = logging.getLogger("app.worker")

# Liveness heartbeat: the loop rewrites this file's mtime every pass so a
# container HEALTHCHECK / k8s exec probe can detect a wedged process. Override
# with WORKER_HEARTBEAT_FILE.
HEARTBEAT_FILE = os.getenv("WORKER_HEARTBEAT_FILE", "/tmp/worker-heartbeat")


def _beat(path: str) -> None:
    try:
        with open(path, "w") as fh:
            fh.write(str(time.time()))
    except OSError:  # pragma: no cover - heartbeat is best-effort
        pass

# A tick returns the number of units of work it processed this pass. The loop
# uses that to decide whether to idle (nothing to do) or immediately poll again
# (queue still draining).
TickFn = Callable[[Session], int]


class GracefulShutdown:
    """Flips to ``True`` on the first SIGTERM/SIGINT so loops can exit cleanly."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def install(self) -> "GracefulShutdown":
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, self._handle)
            except (ValueError, OSError):  # pragma: no cover
                # Not on the main thread (e.g. under a test runner) — skip.
                pass
        return self

    def _handle(self, signum, _frame) -> None:  # pragma: no cover - signal path
        logger.info("received signal %s; shutting down gracefully", signum)
        self._event.set()

    @property
    def requested(self) -> bool:
        return self._event.is_set()

    def wait(self, seconds: float) -> None:
        """Sleep up to ``seconds``, waking early if shutdown is requested."""
        self._event.wait(timeout=seconds)


def run_loop(
    name: str,
    tick: TickFn,
    *,
    interval: float,
    shutdown: GracefulShutdown | None = None,
    max_iterations: int | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
    heartbeat_file: str = HEARTBEAT_FILE,
) -> int:
    """Run ``tick`` on a poll loop until shutdown is requested.

    Returns the total number of work units processed — handy for tests, which
    pass ``max_iterations`` to run a bounded number of passes and inject a
    ``session_factory`` bound to a throwaway database.
    """
    shutdown = shutdown or GracefulShutdown().install()
    logger.info("%s starting (interval=%.1fs)", name, interval)

    total = 0
    iterations = 0
    idle_backoff = min(interval, 1.0)

    while not shutdown.requested:
        if max_iterations is not None and iterations >= max_iterations:
            break
        iterations += 1
        _beat(heartbeat_file)

        db = session_factory()
        try:
            processed = tick(db)
            total += processed
            if processed:
                logger.info("%s processed %d unit(s)", name, processed)
        except Exception:  # never let one bad tick kill the process
            logger.exception("%s tick failed; backing off", name)
            try:
                db.rollback()
            except Exception:  # pragma: no cover - defensive
                pass
            processed = 0
        finally:
            db.close()

        # Busy queue → poll again immediately; otherwise idle for the interval.
        if processed:
            continue
        shutdown.wait(interval if max_iterations is None else idle_backoff)

    logger.info("%s stopped (processed %d unit(s) total)", name, total)
    return total
