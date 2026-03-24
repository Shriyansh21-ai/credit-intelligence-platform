from sqlalchemy.orm import Session
from datetime import datetime
from app.models.risk_history import RiskHistory

def save_risk_db(user_email, risk_score, db: Session):

    record = RiskHistory(
        user_email=user_email,
        risk_score=risk_score,
        timestamp=str(datetime.utcnow())
    )

    db.add(record)
    db.commit()