from datetime import datetime, timedelta

from jose import jwt
import bcrypt

from backend.app.core.settings import get_settings

# ----------------------------------------
# Config
# ----------------------------------------
# Sourced from the centralized settings (Phase 11, M1) instead of hardcoded
# constants. The module-level names are preserved for backward compatibility —
# many modules do ``from backend.app.core.security import SECRET_KEY``.
_settings = get_settings()

SECRET_KEY = _settings.effective_jwt_secret

ALGORITHM = _settings.jwt_algorithm

ACCESS_TOKEN_EXPIRE_MINUTES = _settings.access_token_expire_minutes

# ----------------------------------------
# Normalize Password for bcrypt
# ----------------------------------------

def _normalize_password(password: str) -> bytes:
    if not isinstance(password, str):
        password = str(password)

    # bcrypt supports up to 72 bytes. Truncate safely in utf-8.
    encoded = password.encode("utf-8")[:72]
    return encoded

# ----------------------------------------
# Hash Password
# ----------------------------------------

def hash_password(password: str) -> str:
    normalized = _normalize_password(password)
    hashed = bcrypt.hashpw(normalized, bcrypt.gensalt())
    return hashed.decode("utf-8")

# ----------------------------------------
# Verify Password
# ----------------------------------------

def verify_password(
    plain_password,
    hashed_password
):

    normalized = _normalize_password(plain_password)
    return bcrypt.checkpw(
        normalized,
        hashed_password.encode("utf-8")
    )

# ----------------------------------------
# Create JWT Token
# ----------------------------------------

def create_access_token(data: dict):

    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({
        "exp": expire
    })

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return encoded_jwt