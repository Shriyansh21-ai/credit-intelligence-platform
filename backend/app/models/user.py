from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import relationship

from backend.app.db.database import Base

class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    email = Column(
        String,
        unique=True,
        index=True
    )

    password = Column(String)

    # ------------------------------------------------------------------
    # Profile fields. Nullable so every pre-existing account keeps working;
    # the ``/api/auth/me`` endpoint derives sensible values from the email
    # when a column is empty. Populated at signup and editable from the
    # Profile Settings page so each user sees their own identity/org.
    # ------------------------------------------------------------------
    full_name = Column(String, nullable=True)

    job_title = Column(String, nullable=True)

    department = Column(String, nullable=True)

    organization_name = Column(String, nullable=True)

    avatar_url = Column(String, nullable=True)

    # (RBAC): many-to-many link to roles. Defined via the
    # ``user_roles`` association table in ``models/rbac.py``. Optional so all
    # pre-Phase-5 code paths that build a User keep working unchanged.
    roles = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
    )