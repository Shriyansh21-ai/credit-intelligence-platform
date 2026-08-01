"""Scheduler process.

Ticks recurring job schedules (``services.saas.jobs.tick_schedules``) and
notifies owners of due/overdue tasks (``services.tasks.scan_due_tasks``) on a
fixed interval. Run as

    python -m backend.app.workers.scheduler

Run exactly one scheduler replica (it is the single writer of schedule
next-run timestamps); scale the worker independently to add job throughput.

Configuration (see ``core.settings``)
    SCHEDULER_INTERVAL seconds between ticks (default: 15.0)
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from backend.app.core.settings import get_settings
from backend.app.core.startup import validate_configuration
from backend.app.services.saas import jobs
from backend.app.workers.runtime import run_loop

logger = logging.getLogger("app.scheduler")


def _tick(db: Session) -> int:
    """Enqueue due scheduled jobs and notify due tasks. Returns actions taken."""
    actions = 0

    enqueued = jobs.tick_schedules(db)
    actions += len(enqueued)

    # Task due-scan is best-effort and isolated: a failure here must not stop
    # schedule ticking (each is committed independently).
    try:
        from backend.app.services.tasks import service as task_service

        actions += task_service.scan_due_tasks(db)
    except Exception:
        logger.exception("scheduler: due-task scan failed")
        db.rollback()

    return actions


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    validate_configuration()
    settings = get_settings()
    run_loop("scheduler", _tick, interval=settings.scheduler_interval)


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    main()
