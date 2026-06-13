from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db

from app.models.user import User

from app.schemas.auth_schema import (
    SignupRequest,
    LoginRequest
)

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token
)

router = APIRouter()

# ----------------------------------------
# Signup
# ----------------------------------------

@router.post("/signup")

def signup(
    request: SignupRequest,
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
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.email == request.email
    ).first()

    if not user:

        return {
            "success": False,
            "message": "Invalid credentials"
        }

    if not verify_password(
        request.password,
        user.password
    ):

        return {
            "success": False,
            "message": "Invalid credentials"
        }

    token = create_access_token({

        "sub": user.email
    })

    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer"
    }