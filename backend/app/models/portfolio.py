from sqlalchemy import Column, Integer, Float, String

from app.db.database import Base

class PortfolioAnalysis(Base):

    __tablename__ = "portfolio_analysis"

    id = Column(Integer, primary_key=True, index=True)

    total_customers = Column(Integer)

    approved = Column(Integer)

    rejected = Column(Integer)

    approval_rate = Column(Float)

    average_credit_score = Column(Float)

    ai_analysis = Column(String)