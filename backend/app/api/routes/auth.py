from fastapi import APIRouter, HTTPException
from app.services.auth_service import *

router = APIRouter()

@router.post("/signup")
def signup(data: dict):

    email = data["email"]
    password = data["password"]

    if email in fake_users_db:
        raise HTTPException(status_code=400, detail="User already exists")

    fake_users_db[email] = {
        "email": email,
        "password": hash_password(password)
    }

    return {"message": "User created"}


@router.post("/login")
def login(data: dict):

    email = data["email"]
    password = data["password"]

    user = fake_users_db.get(email)

    if not user or not verify_password(password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": email})

    return {
        "access_token": token,
        "token_type": "bearer"
    }