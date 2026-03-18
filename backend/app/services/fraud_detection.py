def detect_fraud(financials, ratios):

    issues = []

    # 1️⃣ Negative or impossible values
    if financials.get("revenue") and financials["revenue"] < 0:
        issues.append("Negative revenue detected")

    if financials.get("assets") and financials["assets"] < 0:
        issues.append("Negative assets detected")

    # 2️⃣ Debt > Assets (red flag)
    if financials.get("liabilities") and financials.get("assets"):
        if financials["liabilities"] > financials["assets"]:
            issues.append("Liabilities exceed assets")

    # 3️⃣ Unrealistic ratios
    if ratios["debt_ratio"] > 1:
        issues.append("Debt ratio above 1 (very high risk)")

    if ratios["current_ratio"] < 0.5:
        issues.append("Very low liquidity")

    if ratios["roe"] > 0.5:
        issues.append("Unusually high ROE (possible manipulation)")

    # 4️⃣ Missing critical data
    for key, value in financials.items():
        if value is None:
            issues.append(f"Missing value: {key}")

    return issues