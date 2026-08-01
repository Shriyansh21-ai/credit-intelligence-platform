"""Background job worker process.

Drains the platform's background job queue by repeatedly calling
``services.saas.jobs.run_pending``. Run as

    python -m backend.app.workers.worker

Configuration (see ``core.settings``)
    WORKER_QUEUE restrict to a single queue (default: all queues)
    WORKER_POLL_INTERVAL idle poll interval in seconds (default: 2.0)
    WORKER_BATCH_SIZE max jobs drained per pass (default: 100)
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from backend.app.core.settings import get_settings
from backend.app.core.startup import validate_configuration
from backend.app.services.saas import jobs
from backend.app.workers.runtime import run_loop

logger = logging.getLogger("app.worker")


def _tick(db: Session) -> int:
    settings = get_settings()
    processed = jobs.run_pending(
        db,
        queue=settings.worker_queue,
        max_jobs=settings.worker_batch_size,
    )
    return len(processed)


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    validate_configuration()
    settings = get_settings()
    run_loop("job-worker", _tick, interval=settings.worker_poll_interval)


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    main()
