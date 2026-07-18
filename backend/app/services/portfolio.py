from backend.app.services.portfolio_ai import generate_portfolio_analysis

def analyze_portfolio(customers):

    total_customers = len(customers)

    approved = 0
    rejected = 0

    high_risk = 0
    medium_risk = 0
    low_risk = 0

    total_credit_score = 0

    for customer in customers:

        score = customer["credit_score"]

        total_credit_score += score

        if customer["approval"]:
            approved += 1
        else:
            rejected += 1

        risk = customer["risk_level"]

        if risk == "High":
            high_risk += 1

        elif risk == "Medium":
            medium_risk += 1

        else:
            low_risk += 1

    average_score = (
        total_credit_score / total_customers
        if total_customers > 0
        else 0
    )

    # -----------------------------------
    # CREATE RESULT OBJECT
    # -----------------------------------

    result = {
        "total_customers": total_customers,

        "approved": approved,

        "rejected": rejected,

        "approval_rate": round(
            approved / total_customers * 100,
            2
        ) if total_customers > 0 else 0,

        "average_credit_score": round(
            average_score,
            2
        ),

        "risk_distribution": {
            "high_risk": high_risk,
            "medium_risk": medium_risk,
            "low_risk": low_risk
        }
    }

    # -----------------------------------
    # ADD AI ANALYSIS
    # -----------------------------------

    result["ai_analysis"] = generate_portfolio_analysis(result)

    return result