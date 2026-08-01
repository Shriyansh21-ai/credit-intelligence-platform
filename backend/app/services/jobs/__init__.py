"""Background jobs.

A small registry of idempotent maintenance jobs that a scheduler (cron, APScheduler
Celery beat) can drive, exposed via an admin API for manual runs. Each job takes a
DB session and returns a small result dict.
"""

from backend.app.services.jobs.runner import JOBS, list_jobs, run_all_jobs, run_job

__all__ = ["JOBS", "list_jobs", "run_all_jobs", "run_job"]
