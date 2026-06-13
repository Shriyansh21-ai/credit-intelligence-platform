from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.services.fraud_detection import (
    detect_fraud
)

from app.db.database import get_db

from app.models.fraud import FraudCheck

from app.models.user import User

from app.core.dependencies import (
    get_current_user
)

router = APIRouter()


@router.post("/detect-fraud")
def fraud_check(

    data: dict,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    result = detect_fraud(data)

    fraud_record = FraudCheck(

        user_id=current_user.id,

        fraud_detected=result[
            "fraud_detected"
        ],

        fraud_risk=result[
            "fraud_risk"
        ],

        anomaly_score=result[
            "anomaly_score"
        ],

        ai_analysis=result[
            "ai_analysis"
        ]
    )

    db.add(fraud_record)

    db.commit()

    db.refresh(fraud_record)

    return {

        "success": True,

        "data": result
    }