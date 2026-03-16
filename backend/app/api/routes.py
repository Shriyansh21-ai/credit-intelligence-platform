from fastapi import APIRouter
from app.schemas.company import CompanyInput
from app.services.risk_service import calculate_risk

router = APIRouter()

@router.post("/risk-score")
def get_risk_score(data: CompanyInput):
    score = calculate_risk(data)
    return {"risk_score": score}