def analyze_transactions(transactions):
    total_spent = sum(t["amount"] for t in transactions if t["type"] == "debit")
    total_income = sum(t["amount"] for t in transactions if t["type"] == "credit")

    savings = total_income - total_spent

    spending_ratio = total_spent / total_income if total_income > 0 else 1

    # Risk logic
    if spending_ratio > 0.9:
        behavior = "High Risk Spender"
        score_adjustment = -20
    elif spending_ratio > 0.7:
        behavior = "Moderate Spender"
        score_adjustment = -10
    else:
        behavior = "Financially Stable"
        score_adjustment = +10

    return {
        "total_income": total_income,
        "total_spent": total_spent,
        "savings": savings,
        "behavior": behavior,
        "score_adjustment": score_adjustment
    }