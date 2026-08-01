from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.db.database import get_db

from backend.app.models.user import User

from backend.app.schemas.auth_schema import (
    SignupRequest,
    LoginRequest
)

from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_token
)

from backend.app.services import audit
from backend.app.services.rbac import catalog
from backend.app.services.rbac.seeding import ensure_user_role

router = APIRouter()

# ----------------------------------------
# Signup
# ----------------------------------------

@router.post("/signup")

def signup(
    request: SignupRequest,
    http_request: Request = None,
    db: Session = Depends(get_db)
):

    existing_user = db.query(User).filter(
        User.email == request.email
    ).first()

    if existing_user:

        return {
            "success": False,
            "message": "User already exists"
        }

    user = User(

        email=request.email,

        password=hash_password(
            request.password
        )
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    # grant the default role to a brand-new account (best-effort so a
    # missing RBAC catalog never blocks signup).
    try:
        ensure_user_role(db, user, catalog.DEFAULT_SIGNUP_ROLE)
    except Exception:
        db.rollback()

    audit.record_safe(
        db,
        action="auth.signup",
        actor=user,
        entity_type="user",
        entity_id=user.id,
        request=http_request,
    )

    token = create_access_token({
        "sub": user.email
    })

    return {
        "success": True,
        "message": "User created successfully",
        "access_token": token,
        "token_type": "bearer"
    }

# ----------------------------------------
# Login
# ----------------------------------------

@router.post("/login")

def login(
    request: LoginRequest,
    http_request: Request = None,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.email == request.email
    ).first()

    if not user:

        audit.record_safe(
            db,
            action="auth.login",
            user_email=request.email,
            status="failure",
            reason="Unknown user",
            request=http_request,
        )

        return {
            "success": False,
            "message": "Invalid credentials"
        }

    if not verify_password(
        request.password,
        user.password
    ):

        audit.record_safe(
            db,
            action="auth.login",
            actor=user,
            status="failure",
            reason="Bad password",
            request=http_request,
        )

        return {
            "success": False,
            "message": "Invalid credentials"
        }

    audit.record_safe(
        db,
        action="auth.login",
        actor=user,
        status="success",
        request=http_request,
    )

    token = create_access_token({

        "sub": user.email
    })

    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer"
    }