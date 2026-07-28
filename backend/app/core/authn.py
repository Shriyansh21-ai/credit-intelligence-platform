"""Authentication hardening (Phase 11, M8).

Additive, stdlib + python-jose only. Complements the existing
``core/security.py`` (password hashing, access-token creation) and the Phase-8
session/device store without changing any existing signature:

* :class:`JwtKeyRing` — versioned JWT signing keys (``kid``) enabling zero-
  downtime signing-key rotation: sign with the active key, verify against all.
* :class:`RefreshTokenService` — opaque, rotating refresh tokens with reuse
  detection (stolen-token families are revoked on replay).
* :class:`PasswordPolicy` — configurable strength policy + scoring.
* :class:`AccountLockout` — failed-attempt throttling with lockout window.
* :class:`Totp` — RFC 6238 time-based OTP for MFA (no third-party dependency).
* :class:`RiskEngine` — risk-based authentication scoring / step-up decisions.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from backend.app.core.settings import get_settings


# ===========================================================================
# JWT signing-key rotation
# ===========================================================================
class JwtKeyRing:
    """Multiple JWT signing keys addressed by ``kid`` for seamless rotation."""

    def __init__(self, algorithm: str = "HS256") -> None:
        self.algorithm = algorithm
        self._keys: dict[str, str] = {}
        self._active: str | None = None

    def add_key(self, kid: str, secret: str, *, activate: bool = True) -> None:
        self._keys[kid] = secret
        if activate or self._active is None:
            self._active = kid

    def rotate(self, kid: str, secret: str) -> None:
        self.add_key(kid, secret, activate=True)

    def retire(self, kid: str) -> None:
        self._keys.pop(kid, None)
        if self._active == kid:
            self._active = next(iter(self._keys), None)

    @property
    def active_kid(self) -> str | None:
        return self._active

    def sign(self, claims: dict, *, expires_in: int | None = None) -> str:
        if self._active is None:
            raise RuntimeError("JwtKeyRing has no active key")
        payload = dict(claims)
        if expires_in is not None:
            payload["exp"] = datetime.now(UTC) + timedelta(seconds=expires_in)
        return jwt.encode(
            payload,
            self._keys[self._active],
            algorithm=self.algorithm,
            headers={"kid": self._active},
        )

    def verify(self, token: str) -> dict:
        """Verify against the token's ``kid`` (or try all keys if absent)."""
        try:
            header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise JWTError("malformed token header") from exc
        kid = header.get("kid")
        candidates = [self._keys[kid]] if kid in self._keys else list(self._keys.values())
        last_err: Exception | None = None
        for secret in candidates:
            try:
                return jwt.decode(token, secret, algorithms=[self.algorithm])
            except JWTError as exc:
                last_err = exc
        raise JWTError("token verification failed") from last_err


_default_keyring: JwtKeyRing | None = None


def get_jwt_keyring() -> JwtKeyRing:
    global _default_keyring  # noqa: PLW0603 - process-wide singleton
    if _default_keyring is None:
        settings = get_settings()
        ring = JwtKeyRing(algorithm=settings.jwt_algorithm)
        ring.add_key("v1", settings.effective_jwt_secret)
        _default_keyring = ring
    return _default_keyring


# ===========================================================================
# Refresh-token rotation with reuse detection
# ===========================================================================
@dataclass
class _RefreshRecord:
    jti: str
    family: str
    user_id: int
    expires_at: float
    used: bool = False
    revoked: bool = False


class RefreshTokenStore:
    """In-memory refresh-token store. Swap for Redis/DB in production."""

    def __init__(self) -> None:
        self._by_jti: dict[str, _RefreshRecord] = {}

    def put(self, rec: _RefreshRecord) -> None:
        self._by_jti[rec.jti] = rec

    def get(self, jti: str) -> _RefreshRecord | None:
        return self._by_jti.get(jti)

    def revoke_family(self, family: str) -> None:
        for rec in self._by_jti.values():
            if rec.family == family:
                rec.revoked = True


class RefreshReuseError(Exception):
    """Raised when a previously-used/revoked refresh token is replayed."""


class RefreshTokenService:
    """Issues and rotates refresh tokens; detects and neutralises reuse."""

    def __init__(
        self, store: RefreshTokenStore | None = None, *, clock: Callable[[], float] = time.time
    ) -> None:
        self._store = store or RefreshTokenStore()
        self._clock = clock

    def issue(self, user_id: int, *, family: str | None = None, ttl_days: int | None = None) -> str:
        settings = get_settings()
        days = ttl_days if ttl_days is not None else settings.refresh_token_expire_days
        jti = secrets.token_urlsafe(24)
        rec = _RefreshRecord(
            jti=jti,
            family=family or secrets.token_urlsafe(12),
            user_id=user_id,
            expires_at=self._clock() + days * 86400,
        )
        self._store.put(rec)
        return self._encode(rec)

    def rotate(self, token: str) -> str:
        """Exchange a refresh token for a new one; the old one is consumed.

        Replaying an already-used or revoked token revokes the whole family
        (the classic refresh-token-rotation theft mitigation).
        """
        jti, family, user_id = self._decode(token)
        rec = self._store.get(jti)
        if rec is None or rec.revoked or rec.family != family or rec.user_id != user_id:
            self._store.revoke_family(family)
            raise RefreshReuseError("unknown or revoked refresh token")
        if rec.used:
            self._store.revoke_family(rec.family)
            raise RefreshReuseError("refresh token reuse detected; family revoked")
        if self._clock() > rec.expires_at:
            raise RefreshReuseError("refresh token expired")
        rec.used = True
        return self.issue(rec.user_id, family=rec.family)

    def revoke(self, token: str) -> None:
        try:
            _jti, family, _uid = self._decode(token)
        except RefreshReuseError:
            return
        self._store.revoke_family(family)

    # -- token codec (HMAC-signed, opaque) -------------------------------
    def _encode(self, rec: _RefreshRecord) -> str:
        body = f"{rec.jti}:{rec.family}:{rec.user_id}"
        sig = hmac.new(get_settings().secret_key.encode(), body.encode(), hashlib.sha256).digest()
        signed = f"{body}:{base64.urlsafe_b64encode(sig).decode()}"
        return base64.urlsafe_b64encode(signed.encode()).decode()

    def _decode(self, token: str) -> tuple[str, str, int]:
        try:
            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            jti, family, user_id, sig_b = decoded.split(":")
            body = f"{jti}:{family}:{user_id}"
            expected = hmac.new(
                get_settings().secret_key.encode(), body.encode(), hashlib.sha256
            ).digest()
            if not hmac.compare_digest(base64.urlsafe_b64encode(expected).decode(), sig_b):
                raise RefreshReuseError("bad refresh token signature")
            return jti, family, int(user_id)
        except RefreshReuseError:
            raise
        except Exception as exc:
            raise RefreshReuseError("malformed refresh token") from exc


# ===========================================================================
# Password policy
# ===========================================================================
_COMMON_PASSWORDS = frozenset(
    {
        "password",
        "123456",
        "123456789",
        "qwerty",
        "abc123",
        "password1",
        "111111",
        "12345678",
        "iloveyou",
        "admin",
        "welcome",
        "monkey",
        "letmein",
        "dragon",
        "passw0rd",
        "master",
        "hello",
        "login",
        "changeme",
    }
)


@dataclass
class PasswordCheck:
    ok: bool
    score: int  # 0-100
    violations: list[str] = field(default_factory=list)


class PasswordPolicy:
    """Configurable password strength policy."""

    def __init__(
        self, *, min_length: int | None = None, require_complexity: bool | None = None
    ) -> None:
        settings = get_settings()
        self.min_length = min_length if min_length is not None else settings.password_min_length
        self.require_complexity = (
            require_complexity
            if require_complexity is not None
            else settings.password_require_complexity
        )

    def check(self, password: str, *, username: str | None = None) -> PasswordCheck:
        violations: list[str] = []
        if len(password) < self.min_length:
            violations.append(f"must be at least {self.min_length} characters")
        classes = [
            bool(re.search(r"[a-z]", password)),
            bool(re.search(r"[A-Z]", password)),
            bool(re.search(r"\d", password)),
            bool(re.search(r"[^A-Za-z0-9]", password)),
        ]
        if self.require_complexity and sum(classes) < 3:
            violations.append("must mix upper, lower, digits, and symbols (>=3 classes)")
        if password.lower() in _COMMON_PASSWORDS:
            violations.append("is a commonly-used password")
        if username and username.lower() in password.lower():
            violations.append("must not contain the username")
        if re.search(r"(.)\1{3,}", password):
            violations.append("must not contain long character runs")

        # Simple entropy-ish score.
        score = min(100, len(password) * 4 + sum(classes) * 10)
        if password.lower() in _COMMON_PASSWORDS:
            score = min(score, 10)
        return PasswordCheck(ok=not violations, score=score, violations=violations)

    def is_valid(self, password: str, *, username: str | None = None) -> bool:
        return self.check(password, username=username).ok


# ===========================================================================
# Account lockout
# ===========================================================================
@dataclass
class _LockState:
    failures: list[float] = field(default_factory=list)
    locked_until: float = 0.0


class AccountLockout:
    """Throttle repeated auth failures per identifier (user/email/IP)."""

    def __init__(
        self,
        *,
        threshold: int | None = None,
        window_seconds: int | None = None,
        duration_seconds: int | None = None,
        clock: Callable[[], float] = time.time,
    ):
        settings = get_settings()
        self.threshold = threshold or settings.account_lockout_threshold
        self.window = window_seconds or settings.account_lockout_window_seconds
        self.duration = duration_seconds or settings.account_lockout_duration_seconds
        self._clock = clock
        self._state: dict[str, _LockState] = {}

    def is_locked(self, key: str) -> bool:
        st = self._state.get(key)
        return bool(st and self._clock() < st.locked_until)

    def record_failure(self, key: str) -> bool:
        """Register a failed attempt; return True if the account is now locked."""
        now = self._clock()
        st = self._state.setdefault(key, _LockState())
        st.failures = [t for t in st.failures if now - t <= self.window]
        st.failures.append(now)
        if len(st.failures) >= self.threshold:
            st.locked_until = now + self.duration
            st.failures.clear()
            return True
        return False

    def record_success(self, key: str) -> None:
        self._state.pop(key, None)

    def seconds_remaining(self, key: str) -> int:
        st = self._state.get(key)
        return int(max(0, st.locked_until - self._clock())) if st else 0


# ===========================================================================
# TOTP (RFC 6238) MFA
# ===========================================================================
class Totp:
    """Time-based one-time passwords for MFA. Pure stdlib."""

    def __init__(self, *, digits: int = 6, period: int = 30, algorithm: str = "sha1") -> None:
        self.digits = digits
        self.period = period
        self.algorithm = algorithm

    @staticmethod
    def generate_secret(length: int = 20) -> str:
        return base64.b32encode(secrets.token_bytes(length)).decode().rstrip("=")

    def _hotp(self, secret: str, counter: int) -> str:
        key = base64.b32decode(secret + "=" * (-len(secret) % 8))
        digest = hmac.new(key, struct.pack(">Q", counter), self.algorithm).digest()
        offset = digest[-1] & 0x0F
        truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
        code = truncated % (10**self.digits)
        return str(code).zfill(self.digits)

    def now_code(self, secret: str, *, at: float | None = None) -> str:
        t = int((at if at is not None else time.time()) // self.period)
        return self._hotp(secret, t)

    def verify(self, secret: str, code: str, *, at: float | None = None, window: int = 1) -> bool:
        t = int((at if at is not None else time.time()) // self.period)
        return any(
            hmac.compare_digest(self._hotp(secret, t + drift), str(code).zfill(self.digits))
            for drift in range(-window, window + 1)
        )

    def provisioning_uri(self, secret: str, account: str, *, issuer: str | None = None) -> str:
        issuer = issuer or get_settings().mfa_issuer
        label = f"{issuer}:{account}"
        return (
            f"otpauth://totp/{label}?secret={secret}&issuer={issuer}"
            f"&algorithm={self.algorithm.upper()}&digits={self.digits}&period={self.period}"
        )


# ===========================================================================
# Risk-based authentication
# ===========================================================================
@dataclass
class RiskSignals:
    known_device: bool = True
    known_ip: bool = True
    new_country: bool = False
    impossible_travel: bool = False
    recent_failures: int = 0
    tor_or_proxy: bool = False


@dataclass
class RiskAssessment:
    score: int  # 0-100 (higher = riskier)
    level: str  # low | medium | high
    require_mfa: bool
    deny: bool
    reasons: list[str] = field(default_factory=list)


class RiskEngine:
    """Scores a login attempt and recommends allow / step-up / deny."""

    def assess(self, signals: RiskSignals) -> RiskAssessment:
        score = 0
        reasons: list[str] = []
        if not signals.known_device:
            score += 25
            reasons.append("unrecognised device")
        if not signals.known_ip:
            score += 15
            reasons.append("new IP address")
        if signals.new_country:
            score += 25
            reasons.append("new country")
        if signals.impossible_travel:
            score += 40
            reasons.append("impossible travel")
        if signals.tor_or_proxy:
            score += 30
            reasons.append("anonymising network")
        score += min(30, signals.recent_failures * 10)
        if signals.recent_failures:
            reasons.append(f"{signals.recent_failures} recent failed attempts")

        score = min(100, score)
        if score >= 70:
            level, require_mfa, deny = "high", True, signals.impossible_travel
        elif score >= 30:
            level, require_mfa, deny = "medium", True, False
        else:
            level, require_mfa, deny = "low", False, False
        return RiskAssessment(
            score=score, level=level, require_mfa=require_mfa, deny=deny, reasons=reasons
        )


__all__ = [
    "AccountLockout",
    "JwtKeyRing",
    "PasswordCheck",
    "PasswordPolicy",
    "RefreshReuseError",
    "RefreshTokenService",
    "RefreshTokenStore",
    "RiskAssessment",
    "RiskEngine",
    "RiskSignals",
    "Totp",
    "get_jwt_keyring",
]
