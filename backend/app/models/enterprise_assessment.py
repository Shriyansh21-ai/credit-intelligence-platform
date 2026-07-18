from sqlalchemy import Column, Integer, Float, String, Boolean, ForeignKey, DateTime
from datetime import datetime
from backend.app.db.database import Base


class EnterpriseAssessment(Base):

    __tablename__ = "enterprise_assessments"

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

    # --- Business profile ---
    company_name = Column(String, nullable=False)
    industry = Column(String, nullable=False)
    business_type = Column(String, nullable=False)
    years_in_business = Column(Integer, nullable=False)
    employee_count = Column(Integer, nullable=False)
    country = Column(String, nullable=True)
    website = Column(String, nullable=True)
    business_expansion_stage = Column(String, nullable=True)

    # --- Core result ---
    enterprise_credit_score = Column(Integer, nullable=False)
    probability_of_default = Column(Float, nullable=False)
    loss_given_default = Column(Float, nullable=False)
    expected_loss = Column(Float, nullable=False)
    risk_rating = Column(String, nullable=False)

    # --- Sizing & pricing ---
    recommended_loan_amount = Column(Float, nullable=True)
    recommended_interest_rate = Column(Float, nullable=True)
    working_capital = Column(Float, nullable=True)

    # --- Recommendation ---
    loan_recommendation = Column(String, nullable=False)
    interest_rate_recommendation = Column(String, nullable=False)
    loan_tenure_recommendation = Column(String, nullable=False)
    collateral_recommendation = Column(String, nullable=False)

    # --- Health dimensions (0-100) ---
    liquidity_health = Column(Integer, nullable=True)
    debt_health = Column(Integer, nullable=True)
    working_capital_health = Column(Integer, nullable=True)
    business_stability = Column(Integer, nullable=True)

    ai_analysis = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
