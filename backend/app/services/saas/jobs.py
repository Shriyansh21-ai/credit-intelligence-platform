"""Background job platform (Phase 8, Milestone 6).

A durable, tenant-scoped job engine with queues, priorities, retries with
exponential backoff, a dead-letter queue, scheduling / recurring jobs,
cancellation and progress tracking. Jobs persist to ``background_jobs`` so state
survives restarts and is visible in the admin console.

Execution is broker-agnostic: :class:`JobBroker` is the abstraction and the
built-in :class:`InProcessBroker` runs handlers synchronously in-process (ideal
for single-node deploys and tests). Redis/Celery/RabbitMQ/Kafka brokers can be
dropped in by implementing the same interface — producers (``enqueue``) and the
worker loop (``run_pending``) are unchanged.

Handlers are registered by ``job_type`` via :func:`register_handler`. A handler
receives ``(db, job, ctx)`` and may call ``ctx.progress(pct, msg)``; returning a
value stores it as the job result, raising triggers retry/DLQ.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Protocol

from sqlalchemy import asc
from sqlalchemy.orm import Session

from backend.app.models.platform_ops import BackgroundJob, JobSchedule

# Registry of job_type -> handler.
_HANDLERS: Dict[str, Callable[..., Any]] = {}


def register_handler(job_type: str):
    def _wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        _HANDLERS[job_type] = fn
        return fn
    return _wrap


def registered_types() -> List[str]:
    return sorted(_HANDLERS)


@dataclass
class JobContext:
    """Passed to handlers; lets them report progress + read tenant scope."""
    db: Session
    job: BackgroundJob

    def progress(self, pct: float, message: Optional[str] = None) -> None:
        self.job.progress = max(0.0, min(100.0, pct))
        if message:
            self.job.progress_message = message
        self.db.commit()


# ===========================================================================
# Broker abstraction
# ===========================================================================
class JobBroker(Protocol):
    name: str

    def enqueue(self, db: Session, job: BackgroundJob) -> None: ...


class InProcessBroker:
    """Default broker: jobs live in the DB and are executed by ``run_pending``.

    No external dependency; the "queue" is the ``background_jobs`` table ordered
    by (priority, available_at, id)."""

    name = "in_process"

    def enqueue(self, db: Session, job: BackgroundJob) -> None:
        # Nothing to push — the table *is* the queue. Present for interface parity.
        return None


class RedisBroker:  # pragma: no cover - abstraction placeholder
    name = "redis"

    def __init__(self, url: Optional[str] = None):
        self.url = url

    def enqueue(self, db: Session, job: BackgroundJob) -> None:
        raise NotImplementedError("Redis broker not configured")


_broker: JobBroker = InProcessBroker()


def set_broker(broker: JobBroker) -> None:
    global _broker
    _broker = broker


def get_broker() -> JobBroker:
    return _broker


# ===========================================================================
# Enqueue / query
# ===========================================================================
def enqueue(db: Session, job_type: str, payload: Optional[Dict] = None, *,
            tenant_id: Optional[int] = None, queue: str = "default",
            priority: int = 5, max_attempts: int = 3,
            available_at: Optional[datetime] = None,
            idempotency_key: Optional[str] = None,
            schedule_id: Optional[int] = None) -> BackgroundJob:
    if idempotency_key:
        existing = (
            db.query(BackgroundJob)
            .filter(BackgroundJob.idempotency_key == idempotency_key,
                    BackgroundJob.status.in_(["queued", "running", "retrying", "succeeded"]))
            .first()
        )
        if existing:
            return existing
    job = BackgroundJob(
        tenant_id=tenant_id, job_type=job_type, queue=queue, priority=priority,
        payload=payload or {}, max_attempts=max_attempts,
        available_at=available_at or datetime.utcnow(),
        idempotency_key=idempotency_key, schedule_id=schedule_id,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_broker().enqueue(db, job)
    return job


def get_job(db: Session, job_id: int) -> Optional[BackgroundJob]:
    return db.query(BackgroundJob).get(job_id)


def list_jobs(db: Session, *, tenant_id: Optional[int] = None,
              status: Optional[str] = None, queue: Optional[str] = None,
              limit: int = 100) -> List[BackgroundJob]:
    q = db.query(BackgroundJob)
    if tenant_id is not None:
        q = q.filter(BackgroundJob.tenant_id == tenant_id)
    if status:
        q = q.filter(BackgroundJob.status == status)
    if queue:
        q = q.filter(BackgroundJob.queue == queue)
    return q.order_by(BackgroundJob.id.desc()).limit(limit).all()


def cancel_job(db: Session, job_id: int) -> BackgroundJob:
    job = db.query(BackgroundJob).get(job_id)
    if job is None:
        raise ValueError("job not found")
    if job.status in ("queued", "retrying"):
        job.status = "canceled"
        job.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
    return job


# ===========================================================================
# Execution (worker loop)
# ===========================================================================
def _claim_next(db: Session, queue: Optional[str] = None) -> Optional[BackgroundJob]:
    now = datetime.utcnow()
    q = db.query(BackgroundJob).filter(
        BackgroundJob.status.in_(["queued", "retrying"]),
        BackgroundJob.available_at <= now,
    )
    if queue:
        q = q.filter(BackgroundJob.queue == queue)
    return q.order_by(asc(BackgroundJob.priority),
                      asc(BackgroundJob.available_at),
                      asc(BackgroundJob.id)).first()


def _run_job(db: Session, job: BackgroundJob) -> BackgroundJob:
    handler = _HANDLERS.get(job.job_type)
    job.status = "running"
    job.attempts += 1
    job.started_at = datetime.utcnow()
    db.commit()

    if handler is None:
        return _fail(db, job, f"no handler registered for '{job.job_type}'")

    try:
        result = handler(db, job, JobContext(db, job))
        job.status = "succeeded"
        job.result = result if isinstance(result, (dict, list, str, int, float, bool)) else {"ok": True}
        job.progress = 100.0
        job.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        _notify(db, job, "job.succeeded")
        return job
    except Exception as exc:  # noqa: BLE001 - handler failures are expected
        db.rollback()
        return _fail(db, job, str(exc))


def _fail(db: Session, job: BackgroundJob, error: str) -> BackgroundJob:
    job.error = error
    if job.attempts < job.max_attempts:
        # Exponential backoff: 2**attempts seconds.
        delay = 2 ** job.attempts
        job.status = "retrying"
        job.available_at = datetime.utcnow() + timedelta(seconds=delay)
        _notify(db, job, "job.retrying")
    else:
        job.status = "dead"
        job.finished_at = datetime.utcnow()
        _notify(db, job, "job.dead")
    db.commit()
    db.refresh(job)
    return job


def run_next(db: Session, queue: Optional[str] = None) -> Optional[BackgroundJob]:
    job = _claim_next(db, queue)
    if job is None:
        return None
    return _run_job(db, job)


def run_pending(db: Session, *, queue: Optional[str] = None, max_jobs: int = 100) -> List[BackgroundJob]:
    """Drain the ready queue (respecting backoff availability). Returns the jobs
    processed this pass. Retrying jobs whose backoff has not elapsed are skipped."""
    processed: List[BackgroundJob] = []
    for _ in range(max_jobs):
        job = run_next(db, queue)
        if job is None:
            break
        processed.append(job)
    return processed


def requeue_dead(db: Session, job_id: int) -> BackgroundJob:
    """Manually replay a dead-letter job (admin action)."""
    job = db.query(BackgroundJob).get(job_id)
    if job is None:
        raise ValueError("job not found")
    if job.status != "dead":
        raise ValueError("job is not dead")
    job.status = "queued"
    job.attempts = 0
    job.error = None
    job.available_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def dead_letters(db: Session, *, tenant_id: Optional[int] = None) -> List[BackgroundJob]:
    return list_jobs(db, tenant_id=tenant_id, status="dead")


def _notify(db: Session, job: BackgroundJob, event_type: str) -> None:
    """Emit an activity event so live monitors and notifications update."""
    try:
        from backend.app.services.saas import realtime
        realtime.publish(db, channel="jobs", event_type=event_type,
                         tenant_id=job.tenant_id, subject=str(job.id),
                         payload={"job_type": job.job_type, "status": job.status})
    except Exception:
        db.rollback()


# ===========================================================================
# Scheduling / recurring jobs
# ===========================================================================
def create_schedule(db: Session, name: str, job_type: str, interval_seconds: int, *,
                    tenant_id: Optional[int] = None, queue: str = "default",
                    payload: Optional[Dict] = None) -> JobSchedule:
    sched = JobSchedule(
        name=name, job_type=job_type, interval_seconds=interval_seconds,
        tenant_id=tenant_id, queue=queue, payload=payload or {},
        next_run_at=datetime.utcnow(),
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched


def due_schedules(db: Session) -> List[JobSchedule]:
    now = datetime.utcnow()
    return (
        db.query(JobSchedule)
        .filter(JobSchedule.enabled.is_(True), JobSchedule.next_run_at <= now)
        .all()
    )


def tick_schedules(db: Session) -> List[BackgroundJob]:
    """Enqueue a job for every schedule that is due, then advance its next run.
    Called by the platform scheduler tick (or the /jobs run endpoint)."""
    enqueued: List[BackgroundJob] = []
    now = datetime.utcnow()
    for sched in due_schedules(db):
        job = enqueue(db, sched.job_type, sched.payload, tenant_id=sched.tenant_id,
                      queue=sched.queue, schedule_id=sched.id)
        sched.last_run_at = now
        sched.next_run_at = now + timedelta(seconds=sched.interval_seconds)
        enqueued.append(job)
    db.commit()
    return enqueued


# A couple of built-in handlers so the platform is useful out of the box.
@register_handler("noop")
def _noop_handler(db: Session, job: BackgroundJob, ctx: JobContext) -> Dict[str, Any]:
    ctx.progress(100.0, "done")
    return {"echo": job.payload}


@register_handler("storage.lifecycle_sweep")
def _lifecycle_handler(db: Session, job: BackgroundJob, ctx: JobContext) -> Dict[str, Any]:
    from backend.app.services.saas import storage
    removed = storage.run_lifecycle_sweep(db, tenant_id=job.tenant_id)
    return {"expired_objects": removed}
