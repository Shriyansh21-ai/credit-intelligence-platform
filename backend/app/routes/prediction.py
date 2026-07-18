from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from backend.app.schemas.schemas import CreditPredictionRequest
from backend.app.schemas.enterprise import (
    EnterpriseAssessmentRequest,
    EnterpriseAssessmentResult,
)

from backend.app.ml.predict import predict_credit
from backend.app.services.enterprise_assessment import evaluate_enterprise_assessment

from backend.app.db.database import get_db

from backend.app.models.prediction import Prediction
from backend.app.models.enterprise_assessment import EnterpriseAssessment
from backend.app.core.dependencies import get_current_user

from backend.app.models.user import User
import asyncio
from backend.app.core.realtime import manager
from backend.app.services.statement_extraction import extract_financial_statement_from_bytes
from backend.app.ml.train import train_and_persist_model
from backend.app.services.credit_analyst_report import build_credit_analyst_report

router = APIRouter()


@router.post("/predict")

async def predict(

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

    # Broadcast new prediction to connected websocket clients
    try:
        await manager.broadcast({"type": "prediction", "data": {
            "id": db_prediction.id,
            "credit_score": db_prediction.credit_score,
            "risk_level": db_prediction.risk_level,
            "approval": db_prediction.approval,
            "probability": db_prediction.probability,
            "ai_analysis": db_prediction.ai_analysis,
            "created_at": str(db_prediction.created_at)
        }})
    except Exception:
        # best-effort broadcast; ignore failures
        pass

    return {
        "success": True,
        "data": result
    }


@router.post("/extract-statement")
async def extract_statement(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    result = extract_financial_statement_from_bytes(content, file.filename or "statement")

    return {
        "success": True,
        "data": {
            "metrics": result["metrics"],
            "message": result["message"],
            "source": result["source"],
            "extracted_text": result["extracted_text"],
            "ocr_used": result["ocr_used"],
        },
    }


@router.post("/retrain-model")
async def retrain_model(current_user: User = Depends(get_current_user)):
    result = train_and_persist_model()
    return {
        "success": True,
        "data": result,
    }


@router.post("/analyst-report")
async def analyst_report(request: dict, current_user: User = Depends(get_current_user)):
    payload = request or {}
    report_type = str(payload.get("report_type", "personal")).lower()
    report = build_credit_analyst_report(payload.get("data", payload), report_type=report_type)
    return {
        "success": True,
        "data": report,
    }


@router.post("/enterprise-assessment", response_model=EnterpriseAssessmentResult)
async def enterprise_assessment(
    request: EnterpriseAssessmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    )
):
    engine_input = request.to_engine_input()
    result = evaluate_enterprise_assessment(engine_input)

    bp = request.business_profile
    health = result["health_metrics"]

    db_record = EnterpriseAssessment(
        user_id=current_user.id,
        company_name=bp.company_name,
        industry=bp.industry,
        business_type=bp.business_type,
        years_in_business=bp.years_in_business,
        employee_count=bp.employee_count,
        country=bp.country,
        website=bp.website,
        business_expansion_stage=engine_input["business_expansion_stage"],
        enterprise_credit_score=result["enterprise_credit_score"],
        probability_of_default=result["probability_of_default"],
        loss_given_default=result["loss_given_default"],
        expected_loss=result["expected_loss"],
        risk_rating=result["risk_rating"],
        recommended_loan_amount=result["summary"]["recommended_loan_amount"],
        recommended_interest_rate=result["summary"]["recommended_interest_rate"],
        working_capital=engine_input["working_capital"],
        loan_recommendation=result["loan_recommendation"],
        interest_rate_recommendation=result["interest_rate_recommendation"],
        loan_tenure_recommendation=result["loan_tenure_recommendation"],
        collateral_recommendation=result["collateral_recommendation"],
        liquidity_health=health["liquidity_health"]["score"],
        debt_health=health["debt_health"]["score"],
        working_capital_health=health["working_capital_health"]["score"],
        business_stability=health["business_stability"]["score"],
        ai_analysis=result["ai_analysis"],
    )

    db.add(db_record)
    db.commit()
    db.refresh(db_record)

    return result