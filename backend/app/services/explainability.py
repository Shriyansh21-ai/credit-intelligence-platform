import shap
import numpy as np
import joblib
import os

MODEL_PATH = "ml/models/risk_model.pkl"

model = None
explainer = None

# Load model if it exists, otherwise it will be loaded later or mocked
if os.path.exists(MODEL_PATH):
    try:
        model = joblib.load(MODEL_PATH)
        explainer = shap.Explainer(model)
    except Exception as e:
        print(f"Warning: Failed to load model from {MODEL_PATH}: {e}")
else:
    print(f"Warning: Model file not found at {MODEL_PATH}. Please train the model first.")


def explain_prediction(data):
    if model is None or explainer is None:
        return [{
            "feature": "Revenue Growth",
            "impact": 0.0
        }, {
            "feature": "Debt Ratio",
            "impact": 0.0
        }, {
            "feature": "Current Ratio",
            "impact": 0.0
        }, {
            "feature": "ROE",
            "impact": 0.0
        }]

    features = np.array([[
        data.revenue_growth,
        data.debt_ratio,
        data.current_ratio,
        data.roe
    ]])

    shap_values = explainer(features)

    feature_names = [
        "Revenue Growth",
        "Debt Ratio",
        "Current Ratio",
        "ROE"
    ]

    explanation = []

    for i, value in enumerate(shap_values.values[0]):

        impact = round(float(value * 100), 2)

        explanation.append({
            "feature": feature_names[i],
            "impact": impact
        })

    return explanation