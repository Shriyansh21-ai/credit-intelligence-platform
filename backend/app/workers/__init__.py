"""Standalone worker & scheduler processes (Phase 11, M2).

These modules turn the platform's existing in-process job primitives
(``services.saas.jobs``) and due-task scanner (``services.tasks``) into
long-running, containerizable processes:

* ``python -m backend.app.workers.worker``     — drains the background job queue
* ``python -m backend.app.workers.scheduler``  — ticks recurring schedules and
  notifies due tasks

Both share :mod:`backend.app.workers.runtime`, which provides a signal-aware
poll loop with per-tick DB sessions and structured logging.
"""
