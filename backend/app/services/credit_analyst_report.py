from typing import Any, Dict, List

from backend.app.ml.predict import predict_credit
from backend.app.services.enterprise_assessment import evaluate_enterprise_assessment


def build_credit_analyst_report(payload: Dict[str, Any], report_type: str = "personal") -> Dict[str, Any]:
    if report_type == "enterprise":
        assessment = evaluate_enterprise_assessment(payload)
        return {
            "report_type": "enterprise",
            "summary": {
                "score": assessment["enterprise_credit_score"],
                "risk_rating": assessment["risk_rating"],
                "default_probability": assessment["probability_of_default"],
                "expected_loss": assessment["expected_loss"],
            },
            "recommendations": {
                "loan": assessment["loan_recommendation"],
                "interest_rate": assessment["interest_rate_recommendation"],
                "tenure": assessment["loan_tenure_recommendation"],
                "collateral": assessment["collateral_recommendation"],
            },
            "explanations": assessment.get("explanations", {}),
            "ai_analysis": assessment.get("ai_analysis", ""),
            "status": "ready",
        }

    prediction = predict_credit(payload)
    explanation = prediction.get("explanation", {}) or {}
    ordered_factors = sorted(explanation.items(), key=lambda item: abs(float(item[1])), reverse=True)[:5]
    top_factors = [name for name, _ in ordered_factors]

    risk = prediction.get("risk_level", "Medium")
    if risk == "High":
        narrative = "High risk profile detected. Review affordability, repayment stability, and supporting financial evidence before approval."
    elif risk == "Medium":
        narrative = "Moderate risk profile detected. Consider enhanced monitoring and additional documentation for approval."
    else:
        narrative = "Strong applicant profile detected. The credit decision is supported by positive repayment indicators."

    return {
        "report_type": "personal",
        "summary": {
            "score": prediction.get("credit_score"),
            "risk_level": risk,
            "approval": prediction.get("approval"),
            "probability": prediction.get("probability"),
        },
        "recommendations": {
            "decision": "Approve" if prediction.get("approval") else "Reject",
            "monitoring": "Enhanced monitoring" if risk != "Low" else "Standard monitoring",
            "next_steps": "Gather supplemental documents and verify repayment capacity." if risk != "Low" else "Proceed with standard underwriting.",
        },
        "top_factors": top_factors,
        "explanations": explanation,
        "ai_analysis": prediction.get("ai_analysis", narrative),
        "status": "ready",
    }
