from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.db.database import get_db

from backend.app.core.dependencies import get_current_user

from backend.app.models.user import User

from backend.app.schemas.auth_schema import (
    SignupRequest,
    LoginRequest,
    ProfileOut,
    ProfileUpdate,
)

from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_token
)

from backend.app.services import audit
from backend.app.services import profile as profile_service
from backend.app.services.rbac import catalog, user_role_names
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

    # Normalise optional profile fields; fall back to email-derived values so
    # the account is personalised even when the form left them blank.
    full_name = (request.full_name or "").strip() or profile_service.derive_name_from_email(request.email)
    organization = (request.organization or "").strip() or profile_service.derive_organization_from_email(request.email)

    user = User(

        email=request.email,

        password=hash_password(
            request.password
        ),

        full_name=full_name or None,

        job_title=(request.job_title or "").strip() or None,

        department=(request.department or "").strip() or None,

        organization_name=organization or None,
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

    # Provision the user's organization + default tenant + owner membership so
    # every account has an isolated home tenant (best-effort; never blocks
    # signup if the tenancy schema is unavailable).
    try:
        from backend.app.services.saas.provisioning import resolve_user_tenant

        resolve_user_tenant(db, user)
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

# ----------------------------------------
# Current user's profile
# ----------------------------------------

@router.get("/api/auth/me", response_model=ProfileOut)
def get_my_profile(
    user: User = Depends(get_current_user),
):
    """Return the authenticated user's full profile (name, title, org, role).

    Values come from the stored ``users`` row; empty columns are derived from
    the email. The current user is identified purely from the JWT via
    ``get_current_user``, so each request resolves to its own account.
    """
    return ProfileOut(**profile_service.compute_profile(user, user_role_names(user)))


@router.patch("/api/auth/me", response_model=ProfileOut)
def update_my_profile(
    request: ProfileUpdate,
    http_request: Request = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the signed-in user's editable profile fields and persist to the
    database so the change reflects everywhere on the next load."""
    before = {
        "full_name": user.full_name,
        "job_title": user.job_title,
        "department": user.department,
        "organization_name": user.organization_name,
        "avatar_url": user.avatar_url,
    }

    data = request.model_dump(exclude_unset=True)

    def _clean(value):
        if value is None:
            return None
        value = value.strip()
        return value or None

    if "full_name" in data:
        user.full_name = _clean(data["full_name"])
    if "job_title" in data:
        user.job_title = _clean(data["job_title"])
    if "department" in data:
        user.department = _clean(data["department"])
    if "organization" in data:
        user.organization_name = _clean(data["organization"])
    if "avatar_url" in data:
        user.avatar_url = _clean(data["avatar_url"])

    db.add(user)
    db.commit()
    db.refresh(user)

    audit.record_safe(
        db,
        action="profile.update",
        actor=user,
        entity_type="user",
        entity_id=user.id,
        previous_value=before,
        new_value={
            "full_name": user.full_name,
            "job_title": user.job_title,
            "department": user.department,
            "organization_name": user.organization_name,
            "avatar_url": user.avatar_url,
        },
        request=http_request,
    )

    return ProfileOut(**profile_service.compute_profile(user, user_role_names(user)))