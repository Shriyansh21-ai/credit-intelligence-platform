from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Boolean,
    ForeignKey,
    DateTime
)

from datetime import datetime

from backend.app.db.database import Base


class Prediction(Base):

    __tablename__ = "predictions"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    credit_score = Column(
        Integer,
        nullable=False
    )

    risk_level = Column(
        String,
        nullable=False
    )

    approval = Column(
        Boolean,
        nullable=False
    )

    probability = Column(
        Float,
        nullable=False
    )

    ai_analysis = Column(
        String,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )