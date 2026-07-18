from typing import Dict, List

import numpy as np
from sklearn.ensemble import IsolationForest

from backend.app.services.fraud_ai import generate_fraud_analysis

training_data = np.array([
    [100, 5, 24],
    [200, 8, 36],
    [150, 6, 30],
    [5000, 40, 1],
    [120, 4, 48],
    [7000, 50, 2],
    [90, 3, 60],
    [10000, 80, 1],
    [3500, 28, 3],
    [80, 2, 72],
    [5400, 33, 2],
    [130, 4, 96],
])

fraud_model = IsolationForest(contamination=0.2, random_state=42)
fraud_model.fit(training_data)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _score_amount(amount: float) -> float:
    if amount <= 100:
        return 0.0
    if amount <= 1000:
        return 0.15
    if amount <= 5000:
        return 0.35
    if amount <= 10000:
        return 0.6
    return 0.8


def _score_frequency(frequency: float) -> float:
    if frequency <= 3:
        return 0.0
    if frequency <= 8:
        return 0.2
    if frequency <= 20:
        return 0.45
    if frequency <= 40:
        return 0.65
    return 0.85


def _score_account_age(account_age: float) -> float:
    if account_age >= 36:
        return 0.0
    if account_age >= 12:
        return 0.15
    if account_age >= 6:
        return 0.35
    return 0.7


def detect_fraud(transaction: Dict[str, float]) -> Dict[str, object]:
    amount = float(transaction.get("amount", 0) or 0)
    frequency = float(transaction.get("frequency", 0) or 0)
    account_age = float(transaction.get("account_age", 0) or 0)

    features = np.array([[amount, frequency, account_age]])
    prediction = fraud_model.predict(features)[0]
    anomaly_score = fraud_model.decision_function(features)[0]

    base_score = 0.25 * _score_amount(amount) + 0.4 * _score_frequency(frequency) + 0.35 * _score_account_age(account_age)
    anomaly_component = _clamp(float(abs(anomaly_score)) / 0.5, 0.0, 1.0)
    initial_score = base_score * 0.55 + anomaly_component * 0.45

    suspicious_flags = sum(
        [
            amount >= 5000,
            frequency >= 20,
            account_age <= 12,
        ]
    )
    fraud_score = _clamp(initial_score + suspicious_flags * 0.08, 0.0, 1.0)
    is_fraud = bool(prediction == -1 or fraud_score >= 0.7 or suspicious_flags >= 2)
    if fraud_score >= 0.75 or suspicious_flags >= 2:
        fraud_risk = "High"
    elif fraud_score >= 0.45:
        fraud_risk = "Medium"
    else:
        fraud_risk = "Low"

    risk_reasons: List[str] = []
    if amount >= 5000:
        risk_reasons.append("High transaction amount")
    if frequency >= 20:
        risk_reasons.append("Unusually high transaction frequency")
    if account_age <= 6:
        risk_reasons.append("Very new account")
    elif account_age <= 12:
        risk_reasons.append("Recently opened account")
    if not risk_reasons:
        risk_reasons.append("Transaction profile is within normal bounds")

    result = {
        "fraud_detected": is_fraud,
        "fraud_risk": fraud_risk,
        "fraud_score": round(fraud_score, 4),
        "anomaly_score": round(float(anomaly_component), 4),
        "risk_reasons": risk_reasons,
    }
    result["ai_analysis"] = generate_fraud_analysis(result)
    return result