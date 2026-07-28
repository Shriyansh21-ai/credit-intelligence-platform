"""Phase 11, Milestone 1 — tests for the production configuration system.

Covers the typed settings, profile-aware validation, backward-compatible
facades, and the fail-fast startup hook. Tests build ``AppSettings`` with
``_env_file=None`` so a developer's local ``.env`` never affects results.
"""

import os
import unittest
from contextlib import contextmanager

from backend.app.core import settings as settings_mod
from backend.app.core.settings import AppSettings, get_settings, reload_settings
from backend.app.core.startup import ConfigurationError, validate_configuration


def make(**env):
    """Build settings from an explicit env mapping, ignoring any .env file."""
    return AppSettings(_env_file=None, **env)


@contextmanager
def environ(**values):
    """Temporarily set process environment variables, then restore."""
    old = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class DefaultsTest(unittest.TestCase):
    def test_zero_config_defaults(self):
        s = make()
        self.assertEqual(s.app_env, "development")
        self.assertTrue(s.is_development)
        self.assertTrue(s.is_sqlite)
        self.assertEqual(s.database_url, "sqlite:///./credit_ai.db")
        self.assertEqual(s.cache_backend, "memory")
        self.assertEqual(s.job_broker, "in_process")
        self.assertEqual(s.storage_backend, "local")
        self.assertEqual(s.max_upload_bytes, 20 * 1024 * 1024)

    def test_effective_jwt_secret_falls_back_to_secret_key(self):
        s = make(SECRET_KEY="abc123")
        self.assertEqual(s.effective_jwt_secret, "abc123")
        s2 = make(SECRET_KEY="abc123", JWT_SECRET_KEY="jwt-specific")
        self.assertEqual(s2.effective_jwt_secret, "jwt-specific")

    def test_summary_contains_no_secrets(self):
        s = make(SECRET_KEY="topsecret", CONNECTOR_MASTER_KEY="alsosecret")
        blob = str(s.summary())
        self.assertNotIn("topsecret", blob)
        self.assertNotIn("alsosecret", blob)


class EnvOverrideTest(unittest.TestCase):
    def test_scalar_overrides(self):
        s = make(APP_ENV="staging", MAX_UPLOAD_MB="50", ACCESS_TOKEN_EXPIRE_MINUTES="15")
        self.assertEqual(s.app_env, "staging")
        self.assertTrue(s.is_staging)
        self.assertTrue(s.is_production_like)
        self.assertEqual(s.max_upload_mb, 50)
        self.assertEqual(s.access_token_expire_minutes, 15)

    def test_bool_parsing(self):
        self.assertTrue(make(DEBUG="true").debug)
        self.assertTrue(make(DEBUG="1").debug)
        self.assertFalse(make(DEBUG="false").debug)

    def test_cors_comma_separated(self):
        s = make(CORS_ORIGINS="https://a.com, https://b.com ,https://c.com")
        self.assertEqual(s.cors_origins, ["https://a.com", "https://b.com", "https://c.com"])

    def test_cors_json_array(self):
        s = make(CORS_ORIGINS='["https://a.com","https://b.com"]')
        self.assertEqual(s.cors_origins, ["https://a.com", "https://b.com"])

    def test_cors_empty(self):
        self.assertEqual(make(CORS_ORIGINS="").cors_origins, [])

    def test_log_level_uppercased(self):
        self.assertEqual(make(LOG_LEVEL="debug").log_level, "DEBUG")


class EngineKwargsTest(unittest.TestCase):
    def test_sqlite_kwargs(self):
        s = make()  # sqlite default
        kwargs = s.sqlalchemy_engine_kwargs
        self.assertEqual(kwargs["connect_args"], {"check_same_thread": False})
        self.assertNotIn("pool_size", kwargs)

    def test_postgres_pooling_kwargs(self):
        s = make(
            DATABASE_URL="postgresql+psycopg://u:p@db:5432/credit",
            DB_POOL_SIZE="7",
            DB_MAX_OVERFLOW="3",
        )
        kwargs = s.sqlalchemy_engine_kwargs
        self.assertEqual(kwargs["connect_args"], {})
        self.assertEqual(kwargs["pool_size"], 7)
        self.assertEqual(kwargs["max_overflow"], 3)
        self.assertTrue(kwargs["pool_pre_ping"])


class ValidationTest(unittest.TestCase):
    def _codes(self, s):
        return {i.code for i in s.validate_runtime()}

    def test_dev_defaults_are_warnings_not_fatal(self):
        s = make()  # insecure defaults, sqlite
        self.assertFalse(s.has_fatal_issues())
        levels = {i.level for i in s.validate_runtime()}
        self.assertEqual(levels, {"warning"})

    def test_production_insecure_defaults_are_fatal(self):
        s = make(APP_ENV="production")
        codes = self._codes(s)
        self.assertIn("insecure_secret_key", codes)
        self.assertIn("insecure_connector_master_key", codes)
        self.assertIn("sqlite_in_production", codes)
        self.assertTrue(s.has_fatal_issues())

    def test_production_clean_config_passes(self):
        s = make(
            APP_ENV="production",
            SECRET_KEY="x" * 40,
            CONNECTOR_MASTER_KEY="y" * 40,
            DATABASE_URL="postgresql+psycopg://u:p@db:5432/credit",
            CORS_ORIGINS="https://app.bank.com",
        )
        self.assertFalse(s.has_fatal_issues())
        self.assertEqual(s.validate_runtime(), [])

    def test_wildcard_cors_with_credentials_fatal_in_prod(self):
        s = make(
            APP_ENV="production",
            SECRET_KEY="x" * 40,
            CONNECTOR_MASTER_KEY="y" * 40,
            DATABASE_URL="postgresql+psycopg://u:p@db:5432/credit",
            CORS_ORIGINS="*",
            CORS_ALLOW_CREDENTIALS="true",
        )
        self.assertIn("wildcard_cors_with_credentials", self._codes(s))
        self.assertTrue(s.has_fatal_issues())

    def test_redis_cache_without_url_fatal_in_prod(self):
        s = make(
            APP_ENV="production",
            SECRET_KEY="x" * 40,
            CONNECTOR_MASTER_KEY="y" * 40,
            DATABASE_URL="postgresql+psycopg://u:p@db:5432/credit",
            CORS_ORIGINS="https://a.com",
            CACHE_BACKEND="redis",
        )
        self.assertIn("redis_cache_without_url", self._codes(s))

    def test_kafka_broker_without_servers(self):
        s = make(APP_ENV="production", JOB_BROKER="kafka")
        self.assertIn("kafka_broker_without_servers", self._codes(s))

    def test_stripe_without_key(self):
        s = make(APP_ENV="production", PAYMENT_GATEWAY="stripe")
        self.assertIn("stripe_without_key", self._codes(s))

    def test_smtp_without_host(self):
        s = make(APP_ENV="production", MAIL_BACKEND="smtp")
        self.assertIn("smtp_without_host", self._codes(s))

    def test_non_prod_never_fatal(self):
        for env in ("development", "testing"):
            s = make(APP_ENV=env, CACHE_BACKEND="redis")  # misconfigured
            self.assertFalse(s.has_fatal_issues())


class StartupHookTest(unittest.TestCase):
    def test_startup_raises_in_production_on_fatal(self):
        s = make(APP_ENV="production")
        with self.assertRaises(ConfigurationError):
            validate_configuration(s)

    def test_startup_tolerates_dev_defaults(self):
        s = make(APP_ENV="development")
        validate_configuration(s)  # must not raise

    def test_startup_passes_clean_production(self):
        s = make(
            APP_ENV="production",
            SECRET_KEY="x" * 40,
            CONNECTOR_MASTER_KEY="y" * 40,
            DATABASE_URL="postgresql+psycopg://u:p@db:5432/credit",
            CORS_ORIGINS="https://a.com",
        )
        validate_configuration(s)  # must not raise


class CachingTest(unittest.TestCase):
    def test_get_settings_is_cached(self):
        self.assertIs(get_settings(), get_settings())

    def test_reload_reads_environment(self):
        with environ(MAX_UPLOAD_MB="99"):
            s = reload_settings()
            self.assertEqual(s.max_upload_mb, 99)
        # restore the default singleton for the rest of the suite
        reload_settings()
        self.assertEqual(get_settings().max_upload_mb, 20)


class BackwardCompatTest(unittest.TestCase):
    def test_legacy_settings_facade(self):
        from backend.app.config import settings as legacy

        self.assertEqual(legacy.MAX_UPLOAD_MB, get_settings().max_upload_mb)
        self.assertEqual(legacy.max_upload_bytes, get_settings().max_upload_bytes)
        self.assertEqual(legacy.STORAGE_ROOT, get_settings().storage_root)
        self.assertEqual(legacy.ML_DEFAULT_MODEL, get_settings().ml_default_model)
        self.assertEqual(legacy.MODEL_PATH, get_settings().ml_model_path)
        self.assertIn("application/pdf", legacy.ALLOWED_UPLOAD_TYPES)

    def test_security_module_sources_from_settings(self):
        from backend.app.core import security

        self.assertEqual(security.SECRET_KEY, get_settings().effective_jwt_secret)
        self.assertEqual(security.ALGORITHM, get_settings().jwt_algorithm)
        self.assertEqual(
            security.ACCESS_TOKEN_EXPIRE_MINUTES,
            get_settings().access_token_expire_minutes,
        )

    def test_database_url_sourced_from_settings(self):
        from backend.app.db import database

        self.assertEqual(database.DATABASE_URL, get_settings().database_url)

    def test_insecure_sentinels_present(self):
        self.assertIn("SUPER_SECRET_KEY", settings_mod.INSECURE_SECRETS)
        self.assertIn("dev-master-key-change-me", settings_mod.INSECURE_CONNECTOR_KEYS)


if __name__ == "__main__":
    unittest.main()
