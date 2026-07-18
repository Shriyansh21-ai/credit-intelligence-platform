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

class FraudCheck(Base):

    __tablename__ = "fraud_checks"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    fraud_detected = Column(Boolean)

    fraud_risk = Column(String)

    anomaly_score = Column(Float)

    ai_analysis = Column(String)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )