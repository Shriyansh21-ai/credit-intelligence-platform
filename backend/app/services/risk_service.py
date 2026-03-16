import numpy as np
import joblib
import os

MODEL_PATH = "ml/models/risk_model.pkl"

def load_model():
    if os.path.exists(MODEL_PATH):
        return joblib.load(MODEL_PATH)
    return None

model = load_model()

def calculate_risk(data):

    if model is None:
        return "Model not trained yet"

    features = np.array([[
        data.revenue_growth,
        data.debt_ratio,
        data.current_ratio,
        data.roe
    ]])

    prediction = model.predict_proba(features)[0][1]

    risk_score = int(prediction * 100)

    return risk_score