from fastapi import Depends
from fastapi import HTTPException

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

from jose import jwt

from sqlalchemy.orm import Session

from app.db.database import get_db

from app.models.user import User

from app.core.security import (
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