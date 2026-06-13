def generate_reason(data, score):
    # Handle both dict and object
    income = data["income"] if isinstance(data, dict) else data.income
    transactions = data["transactions"] if isinstance(data, dict) else data.transactions
    credit_history = data["credit_history"] if isinstance(data, dict) else data.credit_history

    reasons = []

    if income < 30000:
        reasons.append("Low income")

    if transactions < 5000:
        reasons.append("Low transaction activity")

    if credit_history < 2:
        reasons.append("Poor credit history")

    if score > 70:
        return "Strong financial profile"

    return ", ".join(reasons) if reasons else "Moderate profile"