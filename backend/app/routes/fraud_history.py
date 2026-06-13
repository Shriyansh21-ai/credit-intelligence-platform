from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.db.database import get_db

from app.models.fraud import FraudCheck

from app.models.user import User

from app.core.dependencies import (
    get_current_user
)

router = APIRouter()


@router.get("/fraud-history")
def get_fraud_history(

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    records = (

        db.query(FraudCheck)

        .filter(
            FraudCheck.user_id ==
            current_user.id
        )

        .order_by(
            FraudCheck.id.desc()
        )

        .all()
    )

    return {

        "success": True,

        "total_records":
            len(records),

        "data": [

            {

                "id": item.id,

                "fraud_detected":
                    item.fraud_detected,

                "fraud_risk":
                    item.fraud_risk,

                "anomaly_score":
                    item.anomaly_score,

                "ai_analysis":
                    item.ai_analysis,

                "created_at":
                    item.created_at

            }

            for item in records
        ]
    }