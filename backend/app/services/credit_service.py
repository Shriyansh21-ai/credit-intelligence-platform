from app.ml.predict import predict_credit
from app.services.explainability import generate_reason
from app.services.transaction_service import analyze_transactions

def evaluate_credit(data, transactions=None):
    score, risk, approval = predict_credit(data)

    txn_analysis = None

    if transactions:
        txn_analysis = analyze_transactions(transactions)
        score += txn_analysis["score_adjustment"]

    reason = generate_reason(data, score)

    return {
        "credit_score": max(0, min(100, score)),
        "risk": risk,
        "approval": score > 50,
        "reason": reason,
        "transaction_analysis": txn_analysis
    }