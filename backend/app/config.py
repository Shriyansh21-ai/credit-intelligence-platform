"""Backward-compatible configuration facade.

The authoritative configuration now lives in :mod:`backend.app.core.settings`
(Phase 11, M1). This module preserves the historical ``settings`` object and
its uppercase attribute surface so existing imports
(``from backend.app.config import settings``) keep working unchanged, while
delegating every value to the centralized, validated settings.

Prefer importing :func:`backend.app.core.settings.get_settings` in new code.
"""

from __future__ import annotations

from backend.app.core.settings import ALLOWED_UPLOAD_TYPES, AppSettings, get_settings


class _LegacySettings:
    """Adapter exposing the legacy uppercase attribute names.

    Reads through to the live :class:`AppSettings` singleton so a
    :func:`backend.app.core.settings.reload_settings` in tests is reflected
    here too.
    """

    @property
    def _s(self) -> AppSettings:
        return get_settings()

    # --- Document Intelligence (Phase 2) ---
    @property
    def STORAGE_ROOT(self) -> str:
        return self._s.storage_root

    @property
    def MAX_UPLOAD_MB(self) -> int:
        return self._s.max_upload_mb

    @property
    def OCR_ENGINE(self) -> str:
        return self._s.ocr_engine

    # --- ML (Phase 4) ---
    @property
    def MODEL_PATH(self) -> str:
        return self._s.ml_model_path

    @property
    def ML_DEFAULT_MODEL(self) -> str:
        return self._s.ml_default_model

    @property
    def ML_EXPLAINER(self) -> str:
        return self._s.ml_explainer

    # Accepted upload content types -> canonical extension.
    ALLOWED_UPLOAD_TYPES = ALLOWED_UPLOAD_TYPES

    @property
    def max_upload_bytes(self) -> int:
        return self._s.max_upload_bytes


settings = _LegacySettings()
