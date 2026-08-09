"""Centralized, profile-aware application configuration.

This module is the single source of truth for every runtime configuration value
in the platform. It replaces the scattered ``os.getenv`` calls and hardcoded
constants that previously lived in ``config.py``, ``core/security.py``
``db/database.py`` and the individual service modules.

Design
------
* **Typed & validated** — built on ``pydantic-settings`` (Pydantic v2). Every
  value is parsed and validated once, at process start, with clear errors.
* **Profile aware** — ``APP_ENV`` selects one of ``development`` / ``testing`` /
  ``staging`` / ``production``. Validation rules tighten for staging/production
  (no insecure secrets, no SQLite, explicit CORS, …).
* **12-Factor** — configuration comes from the environment (optionally seeded
  from a ``.env`` file for local development). Nothing secret is hardcoded.
* **Backward compatible** — the historical zero-config defaults (SQLite +
  in-process cache/storage/broker, the legacy dev secret) are preserved, so
  existing development and test flows keep working with no environment set.

Access the settings through :func:`get_settings` (cached). Tests and hot-reload
flows can call :func:`reload_settings` to re-read the environment.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Any, List, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# ---------------------------------------------------------------------------
# Profiles & sentinels
# ---------------------------------------------------------------------------

Environment = Literal["development", "testing", "staging", "production"]

# Secret values that ship as defaults and must never be used outside of local
# development / test. Startup validation rejects these in staging/production.
INSECURE_SECRETS = frozenset(
    {
        "",
        "dev-insecure-change-me",
        "SUPER_SECRET_KEY",
        "change-me-in-production",
        "changeme",
        "secret",
    }
)
INSECURE_CONNECTOR_KEYS = frozenset({"", "dev-master-key-change-me"})

# Content types accepted by the document-upload endpoints. This is a fixed part
# of the API contract, not an operator-tunable value, so it lives in code.
ALLOWED_UPLOAD_TYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
}


class ValidationIssue:
    """A single startup-validation finding.

    ``level`` is ``"error"`` (fatal in staging/production) or ``"warning"``
    (advisory everywhere). ``code`` is a stable machine-readable identifier.
    """

    __slots__ = ("level", "code", "message")

    def __init__(self, level: str, code: str, message: str) -> None:
        self.level = level
        self.code = code
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.level.upper()}] {self.code}: {self.message}"

    def as_dict(self) -> dict[str, str]:
        return {"level": self.level, "code": self.code, "message": self.message}


class AppSettings(BaseSettings):
    """Strongly-typed application settings, populated from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # ``ml_*`` / ``model_*`` field names would otherwise trip Pydantic's
        # protected-namespace guard; we manage that surface ourselves.
        protected_namespaces=(),
    )

    # ------------------------------------------------------------------ core
    app_env: Environment = Field(default="development", alias="APP_ENV")
    app_name: str = Field(default="AI Credit Intelligence Platform", alias="APP_NAME")
    app_version: str = Field(default="1.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    secret_key: str = Field(default="dev-insecure-change-me", alias="SECRET_KEY")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    # "json" for structured production logs, "console" for human-readable dev.
    log_format: Literal["json", "console"] = Field(default="console", alias="LOG_FORMAT")

    cors_origins: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:4173",
            "http://localhost:5173",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:4173",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8080",
        ],
        alias="CORS_ORIGINS",
    )
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")

    # -------------------------------------------------------------- database
    database_url: str = Field(default="sqlite:///./credit_ai.db", alias="DATABASE_URL")
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=1800, alias="DB_POOL_RECYCLE")
    db_pool_pre_ping: bool = Field(default=True, alias="DB_POOL_PRE_PING")
    db_echo: bool = Field(default=False, alias="DB_ECHO")
    run_migrations: bool = Field(default=True, alias="RUN_MIGRATIONS")

    # ----------------------------------------------------------------- cache
    cache_backend: Literal["memory", "redis"] = Field(default="memory", alias="CACHE_BACKEND")
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")
    cache_default_ttl: int = Field(default=300, alias="CACHE_DEFAULT_TTL")

    # ------------------------------------------------------------ messaging
    job_broker: Literal["in_process", "redis", "celery", "rabbitmq", "kafka"] = Field(
        default="in_process", alias="JOB_BROKER"
    )
    kafka_bootstrap_servers: Optional[str] = Field(default=None, alias="KAFKA_BOOTSTRAP_SERVERS")
    kafka_client_id: str = Field(default="ai-credit-platform", alias="KAFKA_CLIENT_ID")
    rabbitmq_url: Optional[str] = Field(default=None, alias="RABBITMQ_URL")

    # --------------------------------------------------------------- storage
    storage_backend: Literal["local", "memory", "s3", "azure", "gcs", "minio"] = Field(
        default="local", alias="STORAGE_BACKEND"
    )
    storage_root: str = Field(default="backend/storage", alias="STORAGE_ROOT")
    # S3 / MinIO (S3-compatible)
    s3_bucket: Optional[str] = Field(default=None, alias="S3_BUCKET")
    s3_region: Optional[str] = Field(default=None, alias="S3_REGION")
    s3_endpoint_url: Optional[str] = Field(default=None, alias="S3_ENDPOINT_URL")
    s3_access_key_id: Optional[str] = Field(default=None, alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: Optional[str] = Field(default=None, alias="S3_SECRET_ACCESS_KEY")
    # Azure Blob
    azure_storage_connection_string: Optional[str] = Field(
        default=None, alias="AZURE_STORAGE_CONNECTION_STRING"
    )
    azure_storage_container: Optional[str] = Field(default=None, alias="AZURE_STORAGE_CONTAINER")
    # Google Cloud Storage
    gcs_bucket: Optional[str] = Field(default=None, alias="GCS_BUCKET")
    gcs_credentials_json: Optional[str] = Field(default=None, alias="GCS_CREDENTIALS_JSON")
    # MinIO-specific
    minio_endpoint: Optional[str] = Field(default=None, alias="MINIO_ENDPOINT")
    minio_access_key: Optional[str] = Field(default=None, alias="MINIO_ACCESS_KEY")
    minio_secret_key: Optional[str] = Field(default=None, alias="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="ai-credit", alias="MINIO_BUCKET")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")

    # ------------------------------------------------------------------- JWT
    jwt_secret_key: Optional[str] = Field(default=None, alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # ------------------------------------------------------------------- LLM
    llm_provider: str = Field(default="local", alias="COPILOT_LLM_PROVIDER")
    llm_model: str = Field(default="claude-sonnet-5", alias="COPILOT_CLAUDE_MODEL")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")

    # --------------------------------------------------------- observability
    otel_exporter_otlp_endpoint: Optional[str] = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_service_name: str = Field(default="ai-credit-platform", alias="OTEL_SERVICE_NAME")
    tracing_enabled: bool = Field(default=False, alias="TRACING_ENABLED")
    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")

    # -------------------------------------------------------- security (M8)
    security_headers_enabled: bool = Field(default=True, alias="SECURITY_HEADERS_ENABLED")
    hsts_max_age: int = Field(default=63072000, alias="HSTS_MAX_AGE")  # 2 years
    hsts_preload: bool = Field(default=True, alias="HSTS_PRELOAD")
    content_security_policy: str = Field(
        default=(
            "default-src 'self'; frame-ancestors 'none'; object-src 'none'; "
            "base-uri 'self'; form-action 'self'"
        ),
        alias="CONTENT_SECURITY_POLICY",
    )
    permissions_policy: str = Field(
        default="geolocation=(), microphone=(), camera=(), payment=()",
        alias="PERMISSIONS_POLICY",
    )
    # Field-level encryption + secrets provider.
    encryption_key: Optional[str] = Field(default=None, alias="ENCRYPTION_KEY")
    encryption_key_version: int = Field(default=1, alias="ENCRYPTION_KEY_VERSION")
    secrets_provider: Literal["env", "file", "aws", "vault"] = Field(
        default="env", alias="SECRETS_PROVIDER"
    )
    secrets_file_path: Optional[str] = Field(default=None, alias="SECRETS_FILE_PATH")
    signed_url_ttl_seconds: int = Field(default=300, alias="SIGNED_URL_TTL_SECONDS")
    # Password policy.
    password_min_length: int = Field(default=12, alias="PASSWORD_MIN_LENGTH")
    password_require_complexity: bool = Field(default=True, alias="PASSWORD_REQUIRE_COMPLEXITY")
    # Account lockout.
    account_lockout_threshold: int = Field(default=5, alias="ACCOUNT_LOCKOUT_THRESHOLD")
    account_lockout_window_seconds: int = Field(default=900, alias="ACCOUNT_LOCKOUT_WINDOW_SECONDS")
    account_lockout_duration_seconds: int = Field(
        default=900, alias="ACCOUNT_LOCKOUT_DURATION_SECONDS"
    )
    # MFA / refresh tokens.
    mfa_issuer: str = Field(default="AI Credit Platform", alias="MFA_ISSUER")
    refresh_token_expire_days: int = Field(default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # ------------------------------------------ disaster recovery (M11)
    backup_dir: str = Field(default="backend/storage/backups", alias="BACKUP_DIR")
    backup_retention_days: int = Field(default=35, alias="BACKUP_RETENTION_DAYS")
    pitr_window_days: int = Field(default=7, alias="PITR_WINDOW_DAYS")

    # ----------------------------------------------------- performance (M9)
    compression_enabled: bool = Field(default=True, alias="COMPRESSION_ENABLED")
    compression_min_size: int = Field(default=1024, alias="COMPRESSION_MIN_SIZE")
    query_profiling_enabled: bool = Field(default=False, alias="QUERY_PROFILING_ENABLED")

    # ------------------------------------------------------------------ mail
    mail_backend: Literal["console", "smtp"] = Field(default="console", alias="MAIL_BACKEND")
    smtp_host: Optional[str] = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: Optional[str] = Field(default=None, alias="SMTP_USER")
    smtp_password: Optional[str] = Field(default=None, alias="SMTP_PASSWORD")
    smtp_tls: bool = Field(default=True, alias="SMTP_TLS")
    mail_from: str = Field(default="no-reply@ai-credit.local", alias="MAIL_FROM")

    # ------------------------------------------------------------------- OCR
    ocr_engine: str = Field(default="auto", alias="OCR_ENGINE")
    tesseract_cmd: Optional[str] = Field(default=None, alias="TESSERACT_CMD")

    # ------------------------------------------------------------ connectors
    connector_master_key: str = Field(
        default="dev-master-key-change-me", alias="CONNECTOR_MASTER_KEY"
    )

    # ---------------------------------------------------------- data provider
    # Selects the source of company / financial / credit / portfolio data used
    # by the seed system and the "Load Demo Portfolio" feature. ``demo`` yields
    # synthetic, clearly-labelled sample data; ``production`` / ``public`` are
    # reserved for real financial-data providers wired later. The core credit /
    # risk engine reads persisted rows and is agnostic to the origin.
    data_provider: str = Field(default="demo", alias="DATA_PROVIDER")

    # ------------------------------------------------------ workers/scheduler
    worker_queue: Optional[str] = Field(default=None, alias="WORKER_QUEUE")
    worker_poll_interval: float = Field(default=2.0, alias="WORKER_POLL_INTERVAL")
    worker_batch_size: int = Field(default=100, alias="WORKER_BATCH_SIZE")
    scheduler_interval: float = Field(default=15.0, alias="SCHEDULER_INTERVAL")

    # --------------------------------------------------------------- billing
    payment_gateway: Literal["internal", "stripe", "razorpay"] = Field(
        default="internal", alias="PAYMENT_GATEWAY"
    )
    stripe_api_key: Optional[str] = Field(default=None, alias="STRIPE_API_KEY")
    razorpay_api_key: Optional[str] = Field(default=None, alias="RAZORPAY_API_KEY")

    # --------------------------------------------------------- uploads / ML
    max_upload_mb: int = Field(default=20, alias="MAX_UPLOAD_MB")
    ml_model_path: str = Field(default="app/ml/model.pkl", alias="MODEL_PATH")
    ml_default_model: str = Field(default="scorecard", alias="ML_DEFAULT_MODEL")
    ml_explainer: str = Field(default="auto", alias="ML_EXPLAINER")

    # ------------------------------------------------------------ validators
    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: Any) -> Any:
        """Accept a comma-separated string or JSON array for ``CORS_ORIGINS``."""
        if value is None or isinstance(value, (list, tuple)):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: Any) -> Any:
        """Pin PostgreSQL DSNs to the installed psycopg (v3) driver.

        Managed Postgres providers (Render, Heroku, Railway, …) hand out a
        ``DATABASE_URL`` with no explicit driver — ``postgres://…`` or
        ``postgresql://…``. SQLAlchemy then defaults to ``psycopg2``, which is
        *not* a dependency here (we ship ``psycopg[binary]``, i.e. psycopg 3),
        so the engine would fail at boot with ``ModuleNotFoundError: psycopg2``.
        Rewriting the scheme to ``postgresql+psycopg://`` makes the provider's
        default DSN work out of the box while leaving any explicit driver
        (``+psycopg``/``+psycopg2``/``+asyncpg``) and non-Postgres URLs (SQLite)
        untouched.
        """
        if not isinstance(value, str):
            return value
        raw = value.strip()
        if raw.startswith("postgresql+") or raw.startswith("postgres+"):
            # An explicit driver was chosen — respect it.
            return raw
        if raw.startswith("postgresql://"):
            return "postgresql+psycopg://" + raw[len("postgresql://"):]
        if raw.startswith("postgres://"):
            return "postgresql+psycopg://" + raw[len("postgres://"):]
        return raw

    # ------------------------------------------------------------ properties
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_staging(self) -> bool:
        return self.app_env == "staging"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_testing(self) -> bool:
        return self.app_env == "testing"

    @property
    def is_production_like(self) -> bool:
        """Staging and production share the strict validation rules."""
        return self.app_env in ("staging", "production")

    @property
    def effective_jwt_secret(self) -> str:
        """JWT signing key — a dedicated ``JWT_SECRET_KEY`` or the app secret."""
        return self.jwt_secret_key or self.secret_key

    @property
    def effective_encryption_key(self) -> str:
        """Field-encryption key — a dedicated ``ENCRYPTION_KEY`` or the app secret."""
        return self.encryption_key or self.secret_key

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def sqlalchemy_connect_args(self) -> dict[str, Any]:
        """Engine ``connect_args`` — the SQLite thread guard, else empty."""
        if self.is_sqlite:
            return {"check_same_thread": False}
        return {}

    @property
    def sqlalchemy_engine_kwargs(self) -> dict[str, Any]:
        """Engine keyword args. Pooling knobs apply only to real DB servers
        SQLite (esp. in-memory) does not use a sized connection pool."""
        kwargs: dict[str, Any] = {
            "connect_args": self.sqlalchemy_connect_args,
            "echo": self.db_echo,
        }
        if not self.is_sqlite:
            kwargs.update(
                pool_size=self.db_pool_size,
                max_overflow=self.db_max_overflow,
                pool_timeout=self.db_pool_timeout,
                pool_recycle=self.db_pool_recycle,
                pool_pre_ping=self.db_pool_pre_ping,
            )
        return kwargs

    # ------------------------------------------------------------ validation
    def validate_runtime(self) -> List[ValidationIssue]:
        """Return startup-validation findings for the active profile.

        Errors are fatal in staging/production; warnings are advisory. This is
        pure (no side effects) so it is safe to call from tests and health
        endpoints as well as from the startup hook.
        """
        issues: List[ValidationIssue] = []
        strict = self.is_production_like

        # --- Secrets --------------------------------------------------------
        if self.secret_key in INSECURE_SECRETS:
            issues.append(
                ValidationIssue(
                    "error" if strict else "warning",
                    "insecure_secret_key",
                    "SECRET_KEY is unset or uses a well-known default; set a "
                    "strong random value (e.g. `openssl rand -hex 32`).",
                )
            )
        elif len(self.secret_key) < 32 and strict:
            issues.append(
                ValidationIssue(
                    "warning",
                    "weak_secret_key",
                    "SECRET_KEY is shorter than 32 characters; prefer >= 32 bytes of entropy.",
                )
            )

        if self.jwt_secret_key is not None and self.jwt_secret_key in INSECURE_SECRETS:
            issues.append(
                ValidationIssue(
                    "error" if strict else "warning",
                    "insecure_jwt_secret",
                    "JWT_SECRET_KEY uses a well-known default value.",
                )
            )

        if self.connector_master_key in INSECURE_CONNECTOR_KEYS:
            issues.append(
                ValidationIssue(
                    "error" if strict else "warning",
                    "insecure_connector_master_key",
                    "CONNECTOR_MASTER_KEY is unset or default; connector "
                    "credentials would be encrypted with a known key.",
                )
            )

        # --- Database -------------------------------------------------------
        if strict and self.is_sqlite:
            issues.append(
                ValidationIssue(
                    "error",
                    "sqlite_in_production",
                    "SQLite is not supported in staging/production; set "
                    "DATABASE_URL to a PostgreSQL DSN.",
                )
            )

        # --- CORS -----------------------------------------------------------
        if "*" in self.cors_origins:
            issues.append(
                ValidationIssue(
                    "error" if strict else "warning",
                    "wildcard_cors_with_credentials"
                    if self.cors_allow_credentials
                    else "wildcard_cors",
                    "CORS is configured with a wildcard origin"
                    + (
                        " together with allow_credentials=True, which browsers reject."
                        if self.cors_allow_credentials
                        else "."
                    ),
                )
            )
        if strict and not self.cors_origins:
            issues.append(
                ValidationIssue(
                    "warning",
                    "empty_cors",
                    "CORS_ORIGINS is empty; browser clients on other origins "
                    "will be blocked.",
                )
            )

        # --- Backend wiring completeness ------------------------------------
        if self.cache_backend == "redis" and not self.redis_url:
            issues.append(
                ValidationIssue(
                    "error", "redis_cache_without_url",
                    "CACHE_BACKEND=redis but REDIS_URL is not set.",
                )
            )
        if self.job_broker == "redis" and not self.redis_url:
            issues.append(
                ValidationIssue(
                    "error", "redis_broker_without_url",
                    "JOB_BROKER=redis but REDIS_URL is not set.",
                )
            )
        if self.job_broker == "rabbitmq" and not self.rabbitmq_url:
            issues.append(
                ValidationIssue(
                    "error", "rabbitmq_broker_without_url",
                    "JOB_BROKER=rabbitmq but RABBITMQ_URL is not set.",
                )
            )
        if self.job_broker == "kafka" and not self.kafka_bootstrap_servers:
            issues.append(
                ValidationIssue(
                    "error", "kafka_broker_without_servers",
                    "JOB_BROKER=kafka but KAFKA_BOOTSTRAP_SERVERS is not set.",
                )
            )

        # --- Storage credentials --------------------------------------------
        if self.storage_backend in ("s3", "minio") and not (
            self.s3_bucket or self.minio_bucket
        ):
            issues.append(
                ValidationIssue(
                    "warning", "object_storage_without_bucket",
                    f"STORAGE_BACKEND={self.storage_backend} but no bucket is configured.",
                )
            )
        if self.storage_backend == "azure" and not self.azure_storage_connection_string:
            issues.append(
                ValidationIssue(
                    "error", "azure_storage_without_connection_string",
                    "STORAGE_BACKEND=azure but AZURE_STORAGE_CONNECTION_STRING is not set.",
                )
            )
        if self.storage_backend == "gcs" and not self.gcs_bucket:
            issues.append(
                ValidationIssue(
                    "error", "gcs_storage_without_bucket",
                    "STORAGE_BACKEND=gcs but GCS_BUCKET is not set.",
                )
            )

        # --- Billing --------------------------------------------------------
        if self.payment_gateway == "stripe" and not self.stripe_api_key:
            issues.append(
                ValidationIssue(
                    "error", "stripe_without_key",
                    "PAYMENT_GATEWAY=stripe but STRIPE_API_KEY is not set.",
                )
            )
        if self.payment_gateway == "razorpay" and not self.razorpay_api_key:
            issues.append(
                ValidationIssue(
                    "error", "razorpay_without_key",
                    "PAYMENT_GATEWAY=razorpay but RAZORPAY_API_KEY is not set.",
                )
            )

        # --- Mail -----------------------------------------------------------
        if self.mail_backend == "smtp" and not self.smtp_host:
            issues.append(
                ValidationIssue(
                    "error", "smtp_without_host",
                    "MAIL_BACKEND=smtp but SMTP_HOST is not set.",
                )
            )

        # --- Debug in prod --------------------------------------------------
        if self.is_production and self.debug:
            issues.append(
                ValidationIssue(
                    "warning", "debug_in_production",
                    "DEBUG is enabled in production.",
                )
            )

        return issues

    def has_fatal_issues(self) -> bool:
        """True if any error-level issue exists in a staging/production profile."""
        if not self.is_production_like:
            return False
        return any(i.level == "error" for i in self.validate_runtime())

    def summary(self) -> dict[str, Any]:
        """Non-secret snapshot for logs / the readiness endpoint."""
        return {
            "app_env": self.app_env,
            "app_version": self.app_version,
            "debug": self.debug,
            "database": "sqlite" if self.is_sqlite else self.database_url.split("://", 1)[0],
            "cache_backend": self.cache_backend,
            "job_broker": self.job_broker,
            "storage_backend": self.storage_backend,
            "payment_gateway": self.payment_gateway,
            "mail_backend": self.mail_backend,
            "data_provider": self.data_provider,
            "llm_provider": self.llm_provider,
            "tracing_enabled": self.tracing_enabled,
            "metrics_enabled": self.metrics_enabled,
        }


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return the process-wide settings singleton (cached)."""
    return AppSettings()


def reload_settings() -> AppSettings:
    """Clear the cache and re-read settings from the environment.

    Intended for tests and hot-reload flows; production reads once at startup.
    """
    get_settings.cache_clear()
    return get_settings()
