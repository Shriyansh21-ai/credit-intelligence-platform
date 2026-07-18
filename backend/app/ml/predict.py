import logging
from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.ml.artifact_store import load_artifact
from backend.app.ml.explain import generate_explanation
from backend.app.services.ai_analyst import generate_ai_analysis

model = load_artifact("model.pkl")
scaler = load_artifact("scaler.pkl")
encoders = load_artifact("label_encoders.pkl")
feature_columns = load_artifact("feature_columns.pkl")

logger = logging.getLogger(__name__)

def predict_credit(data):

    # Convert input to dataframe
    df = pd.DataFrame([data])

    # Encode categorical columns, handling unseen values
    for col, encoder in encoders.items():
        if col in df.columns:
            try:
                df[col] = encoder.transform(df[col])
            except Exception:
                # Map unseen categories to 'Unknown' if available, otherwise NaN
                classes = getattr(encoder, "classes_", [])
                if "Unknown" in classes:
                    df[col] = df[col].apply(lambda x: x if x in classes else "Unknown")
                    df[col] = encoder.transform(df[col])
                else:
                    df[col] = df[col].apply(lambda x: x if x in classes else np.nan)
                    try:
                        df[col] = encoder.transform(df[col].fillna("Unknown"))
                    except Exception:
                        # fallback: set unknowns to -1
                        df[col] = df[col].apply(lambda x: -1)

    # Ensure all expected features exist and maintain feature order
    for c in feature_columns:
        if c not in df.columns:
            df[c] = np.nan

    df = df[feature_columns]

    # Convert numeric columns to numeric types
    numeric_cols = [c for c in df.columns if c in ["Age", "Job", "Credit amount", "Duration"]]
    for nc in numeric_cols:
        df[nc] = pd.to_numeric(df[nc], errors="coerce")

    # Fill missing numeric values with median (if available) or 0
    try:
        medians = df[numeric_cols].median()
        df[numeric_cols] = df[numeric_cols].fillna(medians)
    except Exception:
        df[numeric_cols] = df[numeric_cols].fillna(0)

    # Fill remaining NaNs with 0
    df = df.fillna(0)

    # Scale
    scaled_data = scaler.transform(df)

    # Guard against non-finite scaled data
    if not np.isfinite(scaled_data).all():
        logger.warning("Non-finite values encountered after scaling; replacing with zeros")
        scaled_data = np.nan_to_num(scaled_data, nan=0.0, posinf=0.0, neginf=0.0)

    # Predict
    prediction = model.predict(scaled_data)[0]

    # Predict probability; guard against missing method
    try:
        proba = model.predict_proba(scaled_data)[0]
        # if binary, take class 1 probability; otherwise attempt to find positive class
        if len(proba) > 1:
            probability = float(proba[1])
        else:
            probability = float(proba[0])
    except Exception:
        logger.exception("predict_proba failed; defaulting probability to 0.0")
        probability = 0.0

    # Ensure finite probability
    if not np.isfinite(probability):
        probability = 0.0

    credit_score = int(round(probability * 100))

    # Risk category
    if credit_score > 75:
        risk = "Low"
    elif credit_score > 45:
        risk = "Medium"
    else:
        risk = "High"

    approval = probability > 0.5

    # SHAP Explanation
    explanation = generate_explanation(data)

    # ------------------------------------
    # CREATE RESULT OBJECT FIRST
    # ------------------------------------

    result = {
        "credit_score": credit_score,
        "risk_level": risk,
        "approval": bool(approval),
        "probability": round(float(probability), 2),
        "prediction": int(prediction),
        "explanation": explanation
    }

    # ------------------------------------
    # NOW GENERATE AI ANALYSIS
    # ------------------------------------

    result["ai_analysis"] = generate_ai_analysis(result)

    return result