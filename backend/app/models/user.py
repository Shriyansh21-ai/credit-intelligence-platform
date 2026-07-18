from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String

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