import numpy as np
from sklearn.ensemble import IsolationForest
from app.services.fraud_ai import generate_fraud_analysis

# ------------------------------------------------
# Train Simple Fraud Detection Model
# ------------------------------------------------

# Dummy transaction patterns
# [amount, frequency, account_age]

training_data = np.array([
    [100, 5, 24],
    [200, 8, 36],
    [150, 6, 30],
    [5000, 40, 1],
    [120, 4, 48],
    [7000, 50, 2],
    [90, 3, 60],
    [10000, 80, 1]
])

# Train model
fraud_model = IsolationForest(
    contamination=0.2,
    random_state=42
)

fraud_model.fit(training_data)

# ------------------------------------------------
# Fraud Prediction Function
# ------------------------------------------------

def detect_fraud(transaction):

    features = np.array([[
        transaction["amount"],
        transaction["frequency"],
        transaction["account_age"]
    ]])

    prediction = fraud_model.predict(features)[0]

    anomaly_score = fraud_model.decision_function(features)[0]

    is_fraud = prediction == -1

    fraud_risk = (
        "High"
        if is_fraud
        else "Low"
    )

    # Create result first
    result = {
        "fraud_detected": bool(is_fraud),
        "fraud_risk": fraud_risk,
        "anomaly_score": round(float(anomaly_score), 4)
    }

    # Add AI explanation
    result["ai_analysis"] = generate_fraud_analysis(result)

    return result