"""Banking Ecosystem Integration Platform persistence (Phase 7).

All tables are **additive** — nothing from Phases 1–6 is touched. Schema is
created by the Alembic migration ``b8c9d0e1f2a3_integration_platform_phase7``
(never ``create_all`` in the app). Grouped by milestone:

Framework / observability / security (M1, M13, M14)
    * :class:`ConnectorConfig`  — per-connector provider mode + (encrypted) config.
    * :class:`ConnectorCallLog` — one durable row per connector call.

Imported external data, versioned snapshots (M2, M3, M6, M7, M8)
    * :class:`IntegrationSnapshot` — versioned, hashed snapshot of any provider
      payload (GST profile/returns, MCA master, bureau report, ERP financials,
      payment analytics), keyed by (connector, entity_ref, version).

Account Aggregator + statement analytics (M4, M5)
    * :class:`ConsentArtifact`   — AA consent lifecycle.
    * :class:`BankStatement` / :class:`BankTransaction` — imported statements.
    * :class:`StatementAnalytics`— derived analytics per statement/entity.

Collateral (M9)
    * :class:`CollateralItem` / :class:`CollateralValuation` / :class:`CollateralInspection`.

Open API platform (M12)
    * :class:`ApiKey` / :class:`ApiUsageLog` / :class:`WebhookSubscription` /
      :class:`WebhookDelivery`.

Synchronisation engine (M11)
    * :class:`PortfolioSyncJob` / :class:`SyncDeadLetter`.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
)

from backend.app.db.database import Base


# ===========================================================================
# M1 / M14 — Connector configuration
# ===========================================================================
class ConnectorConfig(Base):
    """Active provider selection + config for one connector key.

    ``credentials_encrypted`` holds an at-rest envelope (see
    ``services/integrations/base/security.encrypt_secret``); raw secrets are
    never stored. ``config`` holds non-secret settings (base URLs, timeouts).
    """

    __tablename__ = "connector_configs"

    id = Column(Integer, primary_key=True, index=True)
    connector_key = Column(String, nullable=False, unique=True, index=True)
    category = Column(String, nullable=False, index=True)
    provider_mode = Column(String, nullable=False, default="mock")  # mock|sandbox|production
    enabled = Column(Boolean, nullable=False, default=True)
    config = Column(JSON, nullable=False, default=dict)
    credentials_encrypted = Column(Text, nullable=True)
    rate_limit_per_sec = Column(Float, nullable=True)
    timeout_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ===========================================================================
# M1 / M13 — Durable connector call log
# ===========================================================================
class ConnectorCallLog(Base):
    __tablename__ = "connector_call_logs"

    id = Column(Integer, primary_key=True, index=True)
    connector_key = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)
    mode = Column(String, nullable=False)
    operation = Column(String, nullable=False, index=True)
    success = Column(Boolean, nullable=False, default=True, index=True)
    from_cache = Column(Boolean, nullable=False, default=False)
    latency_ms = Column(Float, nullable=True)
    attempts = Column(Integer, nullable=False, default=1)
    circuit_state = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    request_summary = Column(JSON, nullable=True)   # PII-masked
    entity_ref = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M2/M3/M6/M7/M8 — Versioned imported-data snapshots
# ===========================================================================
class IntegrationSnapshot(Base):
    """A versioned, content-hashed snapshot of one provider payload.

    Generic on purpose: GST profiles, GST returns, MCA company masters, bureau
    reports, ERP financials and payment analytics all persist here, discriminated
    by ``connector_key`` + ``dataset`` (e.g. ``gst`` / ``returns``). New versions
    are appended; only one row per (connector, entity_ref, dataset) is current.
    """

    __tablename__ = "integration_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    connector_key = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    mode = Column(String, nullable=False, default="mock")
    dataset = Column(String, nullable=False, default="default", index=True)
    entity_ref = Column(String, nullable=False, index=True)  # GSTIN / CIN / PAN / entity id
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    status = Column(String, nullable=False, default="active")
    payload = Column(JSON, nullable=False, default=dict)
    content_hash = Column(String, nullable=False, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    refresh_due_at = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M4 — Account Aggregator consent
# ===========================================================================
class ConsentArtifact(Base):
    __tablename__ = "aa_consents"

    id = Column(Integer, primary_key=True, index=True)
    handle = Column(String, nullable=False, unique=True, index=True)
    entity_ref = Column(String, nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True, index=True)
    status = Column(String, nullable=False, default="pending", index=True)  # pending|active|revoked|expired|rejected
    purpose = Column(String, nullable=True)
    scope = Column(JSON, nullable=False, default=dict)     # fi_types, fetch window, frequency
    accounts = Column(JSON, nullable=False, default=list)  # discovered/linked accounts
    provider = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    activated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    revoked_at = Column(DateTime, nullable=True)


# ===========================================================================
# M4 / M5 — Bank statements + transactions + analytics
# ===========================================================================
class BankStatement(Base):
    __tablename__ = "bank_statements"

    id = Column(Integer, primary_key=True, index=True)
    entity_ref = Column(String, nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True, index=True)
    consent_id = Column(Integer, ForeignKey("aa_consents.id"), nullable=True, index=True)
    account_ref = Column(String, nullable=False, index=True)
    account_type = Column(String, nullable=True)  # savings|current|od|cc
    bank_name = Column(String, nullable=True)
    ifsc = Column(String, nullable=True)
    currency = Column(String, nullable=False, default="INR")
    from_date = Column(DateTime, nullable=True)
    to_date = Column(DateTime, nullable=True)
    opening_balance = Column(Float, nullable=True)
    closing_balance = Column(Float, nullable=True)
    source = Column(String, nullable=False, default="account_aggregator")
    provider = Column(String, nullable=True)
    txn_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("bank_statements.id"), nullable=False, index=True)
    txn_date = Column(DateTime, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    direction = Column(String, nullable=False)  # credit|debit
    balance = Column(Float, nullable=True)
    narration = Column(Text, nullable=True)
    category = Column(String, nullable=True, index=True)  # salary|vendor|emi|tax|collection|...
    counterparty = Column(String, nullable=True)
    mode = Column(String, nullable=True)  # upi|neft|imps|rtgs|cash|cheque|card
    reference = Column(String, nullable=True)
    is_recurring = Column(Boolean, nullable=False, default=False)


class StatementAnalytics(Base):
    __tablename__ = "statement_analytics"

    id = Column(Integer, primary_key=True, index=True)
    entity_ref = Column(String, nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True, index=True)
    statement_id = Column(Integer, ForeignKey("bank_statements.id"), nullable=True, index=True)
    scope = Column(String, nullable=False, default="statement")  # statement|entity
    version = Column(Integer, nullable=False, default=1)
    bank_health_score = Column(Float, nullable=True)
    metrics = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M9 — Collateral management
# ===========================================================================
class CollateralItem(Base):
    __tablename__ = "collateral_items"

    id = Column(Integer, primary_key=True, index=True)
    entity_ref = Column(String, nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True, index=True)
    collateral_type = Column(String, nullable=False, index=True)  # real_estate|machinery|vehicle|inventory|receivables|fixed_deposit|guarantee|insurance
    description = Column(String, nullable=False)
    owner = Column(String, nullable=True)
    currency = Column(String, nullable=False, default="INR")
    market_value = Column(Float, nullable=False, default=0.0)
    haircut_pct = Column(Float, nullable=False, default=0.0)
    realizable_value = Column(Float, nullable=False, default=0.0)
    loan_amount = Column(Float, nullable=True)   # exposure secured by this collateral
    ltv = Column(Float, nullable=True)
    coverage_ratio = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="active", index=True)  # active|released|expired|impaired
    charge_type = Column(String, nullable=True)  # first|second|pari_passu
    expiry_date = Column(DateTime, nullable=True, index=True)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CollateralValuation(Base):
    __tablename__ = "collateral_valuations"

    id = Column(Integer, primary_key=True, index=True)
    collateral_id = Column(Integer, ForeignKey("collateral_items.id"), nullable=False, index=True)
    market_value = Column(Float, nullable=False)
    haircut_pct = Column(Float, nullable=False, default=0.0)
    realizable_value = Column(Float, nullable=False, default=0.0)
    method = Column(String, nullable=True)  # market|book|income|expert
    valuer = Column(String, nullable=True)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    valued_at = Column(DateTime, default=datetime.utcnow, index=True)
    notes = Column(Text, nullable=True)


class CollateralInspection(Base):
    __tablename__ = "collateral_inspections"

    id = Column(Integer, primary_key=True, index=True)
    collateral_id = Column(Integer, ForeignKey("collateral_items.id"), nullable=False, index=True)
    inspected_at = Column(DateTime, default=datetime.utcnow, index=True)
    inspector = Column(String, nullable=True)
    outcome = Column(String, nullable=True)  # satisfactory|deficient|not_found
    condition = Column(String, nullable=True)
    notes = Column(Text, nullable=True)


# ===========================================================================
# M12 — Open API platform
# ===========================================================================
class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    key_prefix = Column(String, nullable=False, index=True)  # public, shown once + on list
    key_hash = Column(String, nullable=False, index=True)    # sha256 of the full key
    scopes = Column(JSON, nullable=False, default=list)
    owner = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    rate_limit_per_min = Column(Integer, nullable=False, default=600)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)


class ApiUsageLog(Base):
    __tablename__ = "api_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True, index=True)
    endpoint = Column(String, nullable=False, index=True)
    method = Column(String, nullable=False)
    status_code = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False)
    events = Column(JSON, nullable=False, default=list)
    secret = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("webhook_subscriptions.id"), nullable=False, index=True)
    event = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    status = Column(String, nullable=False, default="pending", index=True)  # pending|delivered|failed
    attempts = Column(Integer, nullable=False, default=0)
    response_code = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    delivered_at = Column(DateTime, nullable=True)


# ===========================================================================
# M11 — Synchronisation engine
# ===========================================================================
class PortfolioSyncJob(Base):
    __tablename__ = "portfolio_sync_jobs"

    id = Column(Integer, primary_key=True, index=True)
    sync_type = Column(String, nullable=False, default="incremental")  # full|incremental
    connectors = Column(JSON, nullable=False, default=list)
    status = Column(String, nullable=False, default="pending", index=True)  # pending|running|completed|failed|partial
    scope = Column(JSON, nullable=False, default=dict)
    cursor = Column(String, nullable=True)  # incremental watermark
    stats = Column(JSON, nullable=False, default=dict)
    conflicts = Column(JSON, nullable=False, default=list)
    total = Column(Integer, nullable=False, default=0)
    processed = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SyncDeadLetter(Base):
    __tablename__ = "sync_dead_letters"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("portfolio_sync_jobs.id"), nullable=True, index=True)
    connector_key = Column(String, nullable=True, index=True)
    entity_ref = Column(String, nullable=True, index=True)
    operation = Column(String, nullable=True)
    payload = Column(JSON, nullable=False, default=dict)
    error = Column(Text, nullable=True)
    retries = Column(Integer, nullable=False, default=0)
    resolved = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
