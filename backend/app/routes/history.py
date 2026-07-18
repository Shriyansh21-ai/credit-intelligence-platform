from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from backend.app.db.database import get_db

from backend.app.models.prediction import Prediction

from backend.app.models.user import User

from backend.app.core.dependencies import (
    get_current_user
)

router = APIRouter(
    tags=["History"]
)


@router.get("/risk-history")
def get_risk_history(

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

        .order_by(
            Prediction.id.desc()
        )

        .all()
    )

    results = []

    for item in predictions:

        results.append({

            "id": item.id,

            "credit_score":
                item.credit_score,

            "risk_level":
                item.risk_level,

            "approval":
                item.approval,

            "probability":
                item.probability,

            "ai_analysis":
                item.ai_analysis,

            "created_at":
                item.created_at
        })

    return {

        "success": True,

        "user":
            current_user.email,

        "total_records":
            len(results),

        "data":
            results
    }