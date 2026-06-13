from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.db.database import get_db

from app.models.user import User
from app.models.prediction import Prediction
from app.models.fraud import FraudCheck

from app.core.dependencies import (
    get_current_user
)

router = APIRouter()


@router.get("/dashboard/overview")
def dashboard_overview(

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    # -----------------------------------
    # Predictions
    # -----------------------------------

    predictions = (

        db.query(Prediction)

        .filter(
            Prediction.user_id ==
            current_user.id
        )

        .all()
    )

    total_predictions = len(
        predictions
    )

    approved = sum(

        1 for p in predictions

        if p.approval
    )

    approval_rate = (

        round(
            approved * 100 /
            total_predictions,
            2
        )

        if total_predictions > 0

        else 0
    )

    average_credit_score = (

        round(

            sum(
                p.credit_score
                for p in predictions
            )

            / total_predictions

        )

        if total_predictions > 0

        else 0
    )

    # -----------------------------------
    # Fraud Checks
    # -----------------------------------

    fraud_checks = (

        db.query(FraudCheck)

        .filter(
            FraudCheck.user_id ==
            current_user.id
        )

        .all()
    )

    total_checks = len(
        fraud_checks
    )

    fraud_detected = sum(

        1 for f in fraud_checks

        if f.fraud_detected
    )

    fraud_rate = (

        round(
            fraud_detected * 100 /
            total_checks,
            2
        )

        if total_checks > 0

        else 0
    )

    # -----------------------------------
    # Recent Predictions
    # -----------------------------------

    recent_predictions = [

        {
            "id": item.id,
            "credit_score": item.credit_score,
            "risk_level": item.risk_level,
            "approval": item.approval
        }

        for item in

        sorted(
            predictions,
            key=lambda x: x.id,
            reverse=True
        )[:5]
    ]

    # -----------------------------------
    # Recent Fraud Checks
    # -----------------------------------

    recent_fraud_checks = [

        {
            "id": item.id,
            "fraud_detected":
                item.fraud_detected,

            "fraud_risk":
                item.fraud_risk,

            "anomaly_score":
                item.anomaly_score
        }

        for item in

        sorted(
            fraud_checks,
            key=lambda x: x.id,
            reverse=True
        )[:5]
    ]

    return {

        "success": True,

        "user": current_user.email,

        "portfolio_summary": {

            "total_predictions":
                total_predictions,

            "approved":
                approved,

            "approval_rate":
                approval_rate,

            "average_credit_score":
                average_credit_score
        },

        "fraud_summary": {

            "total_checks":
                total_checks,

            "fraud_detected":
                fraud_detected,

            "fraud_rate":
                fraud_rate
        },

        "recent_predictions":
            recent_predictions,

        "recent_fraud_checks":
            recent_fraud_checks
    }