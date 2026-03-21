def analyze_portfolio(companies):

    total_risk = 0
    high_risk_count = 0

    results = []

    for company in companies:

        risk = company.get("risk_score", 0)

        total_risk += risk

        if risk > 70:
            high_risk_count += 1

        results.append({
            "name": company.get("name", "Unknown"),
            "risk": risk
        })

    avg_risk = total_risk / len(companies) if companies else 0

    return {
        "average_risk": avg_risk,
        "high_risk_companies": high_risk_count,
        "total_companies": len(companies),
        "distribution": results
    }