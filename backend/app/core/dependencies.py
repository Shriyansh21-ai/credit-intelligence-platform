from fastapi import Depends
from fastapi import HTTPException

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

from jose import jwt

from sqlalchemy.orm import Session

from backend.app.db.database import get_db

from backend.app.models.user import User

from backend.app.core.security import (
    SECRET_KEY,
    ALGORITHM
)

# ----------------------------------------
# Bearer Token Security
# ----------------------------------------

security = HTTPBearer()

# ----------------------------------------
# Get Current User
# ----------------------------------------

def get_current_user(

    credentials: HTTPAuthorizationCredentials = Depends(security),

    db: Session = Depends(get_db)
):

    # ----------------------------------------
    # Extract Token
    # ----------------------------------------

    token = credentials.credentials

    # ----------------------------------------
    # Exception
    # ----------------------------------------

    credentials_exception = HTTPException(

        status_code=401,

        detail="Invalid or expired token"
    )

    try:

        # ----------------------------------------
        # Decode JWT
        # ----------------------------------------

        payload = jwt.decode(

            token,

            SECRET_KEY,

            algorithms=[ALGORITHM]
        )

        # ----------------------------------------
        # Extract Email
        # ----------------------------------------

        email = payload.get("sub")

        if email is None:

            raise credentials_exception

    except Exception:

        raise credentials_exception

    # ----------------------------------------
    # Fetch User From Database
    # ----------------------------------------

    user = db.query(User).filter(
        User.email == email
    ).first()

    if user is None:

        raise credentials_exception

    return user


# ----------------------------------------
# Get Current Tenant
# ----------------------------------------


def get_current_tenant_id(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> int:
    """Resolve the authenticated user's owning tenant id (isolation key).

    Provisions an organization + default tenant + membership on first use via
    :func:`resolve_user_tenant`, so this is the single source of the tenant a
    request may read/write. Every tenant-scoped feature depends on this rather
    than trusting a client-supplied ``X-Tenant-ID`` header.
    """
    from backend.app.services.saas.provisioning import resolve_user_tenant

    tenant = resolve_user_tenant(db, user)
    if tenant is None:
        raise HTTPException(status_code=409, detail="Could not resolve tenant for user")
    return tenant.id