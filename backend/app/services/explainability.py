import shap
import numpy as np
import joblib

MODEL_PATH = "ml/models/risk_model.pkl"

model = joblib.load(MODEL_PATH)

explainer = shap.Explainer(model)


def explain_prediction(data):

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