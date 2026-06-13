def generate_portfolio_analysis(result):

    avg_score = result["average_credit_score"]

    approval_rate = result["approval_rate"]

    high_risk = result["risk_distribution"]["high_risk"]

    if avg_score > 75 and high_risk < 3:

        return (
            "Portfolio appears financially healthy "
            "with strong approval metrics and "
            "low high-risk exposure."
        )

    elif avg_score > 50:

        return (
            "Portfolio shows moderate stability "
            "but contains some elevated risk segments."
        )

    return (
        "Portfolio risk exposure is high. "
        "Significant concentration of risky applicants detected."
    )