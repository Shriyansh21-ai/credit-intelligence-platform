from typing import List, Optional

from pydantic import BaseModel


class SignupRequest(BaseModel):

    email: str

    password: str

    # Optional profile fields captured on the sign-up form so a new account is
    # personalised from the first login. All optional — the backend derives
    # sensible values from the email when they are omitted.
    full_name: Optional[str] = None

    job_title: Optional[str] = None

    department: Optional[str] = None

    organization: Optional[str] = None


class LoginRequest(BaseModel):

    email: str

    password: str


class ProfileOut(BaseModel):
    """The authenticated user's profile, rendered across the app."""

    user_id: int
    email: Optional[str] = None
    full_name: str
    first_name: str
    job_title: str
    department: Optional[str] = None
    organization: str
    avatar_url: Optional[str] = None
    initials: str
    role: Optional[str] = None
    roles: List[str] = []


class ProfileUpdate(BaseModel):
    """Editable profile fields (Profile Settings page). All optional."""

    full_name: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    organization: Optional[str] = None
    avatar_url: Optional[str] = None
