from sqlalchemy import Column, String

from backend.app.db.database import Base

class User(Base):
    __tablename__ = "users"

    email = Column(String, primary_key=True)
    password = Column(String)
    role = Column(String, default="user")  # 🔥 NEW

    