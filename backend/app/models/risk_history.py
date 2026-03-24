from sqlalchemy import Column, Integer, Float, String
from app.db.database import Base

class RiskHistory(Base):
    __tablename__ = "risk_history"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String)
    risk_score = Column(Float)
    timestamp = Column(String)