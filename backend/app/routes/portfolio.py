from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.services.portfolio import analyze_portfolio

from app.db.database import get_db

from app.models.prediction import Prediction

from app.models.user import User

from app.core.dependencies import (
    get_current_user
)

router = APIRouter()


@router.post("/portfolio-analysis")
def portfolio_analysis(data: list):

    result = analyze_portfolio(data)

    return {
        "success": True,
        "data": result
    }


@router.get("/summary")
def portfolio_summary(

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    predictions = (

        db.query(Prediction)

        .filter(
            Prediction.user_id ==
            current_user.id
        )

        .all()
    )

    total_predictions = len(predictions)

    if total_predictions == 0:

        return {

            "success": True,

            "summary": {

                "total_predictions": 0,

                "approved": 0,

                "rejected": 0,

                "approval_rate": 0,

                "average_credit_score": 0,

                "low_risk": 0,

                "medium_risk": 0,

                "high_risk": 0
            }
        }

    approved = sum(
        1 for p in predictions
        if p.approval
    )

    rejected = total_predictions - approved

    avg_score = round(

        sum(
            p.credit_score
            for p in predictions
        ) / total_predictions,

        2
    )

    low_risk = sum(
        1 for p in predictions
        if p.risk_level == "Low"
    )

    medium_risk = sum(
        1 for p in predictions
        if p.risk_level == "Medium"
    )

    high_risk = sum(
        1 for p in predictions
        if p.risk_level == "High"
    )

    approval_rate = round(
        approved * 100 / total_predictions,
        2
    )

    return {

        "success": True,

        "summary": {

            "total_predictions":
                total_predictions,

            "approved":
                approved,

            "rejected":
                rejected,

            "approval_rate":
                approval_rate,

            "average_credit_score":
                avg_score,

            "low_risk":
                low_risk,

            "medium_risk":
                medium_risk,

            "high_risk":
                high_risk
        }
    }