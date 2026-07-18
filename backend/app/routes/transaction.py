from fastapi import APIRouter
from backend.app.services.transaction_service import analyze_transactions

router = APIRouter()

@router.post("/analyze")
async def analyze(data: dict):
    transactions = data.get("transactions", [])

    result = analyze_transactions(transactions)

    return {
        "analysis": result
    }