from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from backend.app.db.database import get_db

from backend.app.models.fraud import FraudCheck

from backend.app.models.user import User

from backend.app.core.dependencies import (
    get_current_user
)

router = APIRouter()


@router.get("/fraud-summary")
def get_fraud_summary(

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

        .all()
    )

    total_checks = len(records)

    if total_checks == 0:

        return {

            "success": True,

            "summary": {

                "total_checks": 0,

                "fraud_detected": 0,

                "normal_transactions": 0,

                "fraud_rate": 0,

                "average_anomaly_score": 0
            }
        }

    fraud_count = sum(

        1 for record in records

        if record.fraud_detected
    )

    normal_count = (
        total_checks - fraud_count
    )

    fraud_rate = round(

        fraud_count * 100 /
        total_checks,

        2
    )

    average_anomaly_score = round(

        sum(
            record.anomaly_score
            for record in records
        ) / total_checks,

        4
    )

    return {

        "success": True,

        "user": current_user.email,

        "summary": {

            "total_checks":
                total_checks,

            "fraud_detected":
                fraud_count,

            "normal_transactions":
                normal_count,

            "fraud_rate":
                fraud_rate,

            "average_anomaly_score":
                average_anomaly_score
        }
    }