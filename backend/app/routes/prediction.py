from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.schemas import CreditPredictionRequest

from app.ml.predict import predict_credit

from app.db.database import get_db

from app.models.prediction import Prediction
from app.core.dependencies import get_current_user

from app.models.user import User

router = APIRouter()

@router.post("/predict")

def predict(

    request: CreditPredictionRequest,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    # ----------------------------------------
    # Convert Request → Dict
    # ----------------------------------------

    data = request.dict()

    # ----------------------------------------
    # Match Dataset Column Names
    # ----------------------------------------

    formatted_data = {

        "Age": data["Age"],

        "Sex": data["Sex"],

        "Job": data["Job"],

        "Housing": data["Housing"],

        "Saving accounts": data["Saving_accounts"],

        "Checking account": data["Checking_account"],

        "Credit amount": data["Credit_amount"],

        "Duration": data["Duration"],

        "Purpose": data["Purpose"]
    }

    # ----------------------------------------
    # ML Prediction
    # ----------------------------------------

    result = predict_credit(formatted_data)

    # ----------------------------------------
    # Save To Database
    # ----------------------------------------

    db_prediction = Prediction(

    user_id=current_user.id,

    credit_score=result["credit_score"],

    risk_level=result["risk_level"],

    approval=result["approval"],

    probability=result["probability"],

    ai_analysis=result["ai_analysis"]
)
    db.add(db_prediction)

    db.commit()

    db.refresh(db_prediction)

    # ----------------------------------------
    # API Response
    # ----------------------------------------

    return {
        "success": True,
        "data": result
    }