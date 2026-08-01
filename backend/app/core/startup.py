"""Startup configuration validation.

Runs once when the application boots. It logs a non-secret configuration
summary, surfaces every validation finding, and — in staging/production
fails fast if any fatal misconfiguration is present (insecure secrets, SQLite
half-configured backends, …). In development/testing it only warns, so the
zero-config local experience is preserved.
"""

from __future__ import annotations

import logging

from backend.app.core.settings import AppSettings, get_settings

logger = logging.getLogger("app.startup")


class ConfigurationError(RuntimeError):
    """Raised when a staging/production process is misconfigured."""


def validate_configuration(settings: AppSettings | None = None) -> None:
    """Validate the active configuration; log findings and fail fast in prod.

    Raises :class:`ConfigurationError` when running under a
    staging/production profile and one or more error-level issues are present.
    """
    settings = settings or get_settings()

    logger.info(
        "configuration loaded: %s",
        ", ".join(f"{k}={v}" for k, v in settings.summary().items()),
    )

    issues = settings.validate_runtime()
    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]

    for issue in warnings:
        logger.warning("config warning [%s]: %s", issue.code, issue.message)

    if not errors:
        logger.info("configuration validation passed (%d warning(s))", len(warnings))
        return

    for issue in errors:
        logger.error("config error [%s]: %s", issue.code, issue.message)

    if settings.is_production_like:
        detail = "; ".join(f"{i.code}: {i.message}" for i in errors)
        raise ConfigurationError(
            f"refusing to start in '{settings.app_env}' profile with "
            f"{len(errors)} fatal configuration error(s): {detail}"
        )

    # Non-prod: errors are downgraded to loud warnings so local dev still runs.
    logger.warning(
        "%d configuration error(s) detected but tolerated in '%s' profile",
        len(errors),
        settings.app_env,
    )
