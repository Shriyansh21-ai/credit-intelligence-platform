"""Platform-operations persistence (Phase 8, Milestones 6-9).

Additive, tenant-scoped tables for the background-job platform (M6), cloud
storage metadata (M7), the real-time activity stream + presence (M8) and
observability traces/metrics (M9). Ephemeral concerns (in-memory queue state,
live socket connections, cache) live in the service layer behind abstractions;
these tables are the durable record.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
)

from backend.app.db.database import Base


# ===========================================================================
# M6 — Background job platform
# ===========================================================================
class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    job_type = Column(String, nullable=False, index=True)
    queue = Column(String, nullable=False, default="default", index=True)
    status = Column(String, nullable=False, default="queued", index=True)
    # queued|running|succeeded|failed|retrying|dead|canceled
    priority = Column(Integer, nullable=False, default=5)  # lower = sooner
    payload = Column(JSON, nullable=False, default=dict)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    progress = Column(Float, nullable=False, default=0.0)  # 0..100
    progress_message = Column(String, nullable=True)
    available_at = Column(DateTime, nullable=True, index=True)  # for scheduling / backoff
    schedule_id = Column(Integer, ForeignKey("job_schedules.id"), nullable=True)
    idempotency_key = Column(String, nullable=True, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobSchedule(Base):
    """A recurring job definition (cron-like interval)."""

    __tablename__ = "job_schedules"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    job_type = Column(String, nullable=False)
    queue = Column(String, nullable=False, default="default")
    interval_seconds = Column(Integer, nullable=False, default=3600)
    payload = Column(JSON, nullable=False, default=dict)
    enabled = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M7 — Cloud storage metadata
# ===========================================================================
class StorageObject(Base):
    __tablename__ = "storage_objects"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    bucket = Column(String, nullable=False, default="default", index=True)
    key = Column(String, nullable=False, index=True)
    backend = Column(String, nullable=False, default="local")  # local|s3|azure|gcs|minio
    content_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=False, default=0)
    checksum = Column(String, nullable=True)
    current_version = Column(Integer, nullable=False, default=1)
    encrypted = Column(Boolean, nullable=False, default=False)
    # Lifecycle: policy name + computed expiry (deletion / archival).
    lifecycle_policy = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StorageObjectVersion(Base):
    __tablename__ = "storage_object_versions"

    id = Column(Integer, primary_key=True, index=True)
    object_id = Column(Integer, ForeignKey("storage_objects.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    checksum = Column(String, nullable=True)
    physical_uri = Column(String, nullable=False)  # backend-specific locator
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M8 — Real-time activity stream + presence
# ===========================================================================
class ActivityEvent(Base):
    """Durable feed backing live dashboards, notifications and the activity
    stream. Broadcast over WebSockets by the real-time hub when produced."""

    __tablename__ = "activity_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    channel = Column(String, nullable=False, default="global", index=True)
    event_type = Column(String, nullable=False, index=True)
    actor = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class PresenceRecord(Base):
    __tablename__ = "presence_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="online")  # online|away|offline
    last_seen_at = Column(DateTime, default=datetime.utcnow, index=True)
    context = Column(JSON, nullable=False, default=dict)  # current page / entity


# ===========================================================================
# M9 — Observability
# ===========================================================================
class TraceSpan(Base):
    """One span of a distributed trace, keyed by ``correlation_id``.

    OpenTelemetry-shaped (trace_id / span_id / parent_span_id) so the durable
    store can be swapped for an OTLP exporter without changing producers."""

    __tablename__ = "trace_spans"

    id = Column(Integer, primary_key=True, index=True)
    correlation_id = Column(String, nullable=False, index=True)
    trace_id = Column(String, nullable=False, index=True)
    span_id = Column(String, nullable=False)
    parent_span_id = Column(String, nullable=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False, default="internal")  # server|client|internal|db
    service = Column(String, nullable=False, default="api")
    status = Column(String, nullable=False, default="ok")  # ok|error
    duration_ms = Column(Float, nullable=True)
    attributes = Column(JSON, nullable=False, default=dict)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
