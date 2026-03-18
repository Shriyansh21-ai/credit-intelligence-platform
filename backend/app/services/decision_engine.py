def make_decision(risk_score, fraud_score):

    if fraud_score > 60:
        return {
            "decision": "REJECTED",
            "reason": "High fraud risk detected"
        }

    if risk_score > 75:
        return {
            "decision": "REJECTED",
            "reason": "High credit risk"
        }

    if 50 < risk_score <= 75:
        return {
            "decision": "CONDITIONAL_APPROVAL",
            "reason": "Moderate risk - requires collateral"
        }

    return {
        "decision": "APPROVED",
        "reason": "Low risk profile"
    }

def generate_loan_terms(risk_score):

    if risk_score < 40:
        return {"interest_rate": 8, "tenure": 10}

    if risk_score < 70:
        return {"interest_rate": 12, "tenure": 7}

    return {"interest_rate": 16, "tenure": 3}