import joblib
import pandas as pd
import shap
from pathlib import Path

# ----------------------------------------
# Load Artifacts
# ----------------------------------------

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"

model = joblib.load(ARTIFACTS_DIR / "model.pkl")

label_encoders = joblib.load(ARTIFACTS_DIR / "label_encoders.pkl")

feature_columns = joblib.load(ARTIFACTS_DIR / "feature_columns.pkl")

# ----------------------------------------
# SHAP Explainer
# ----------------------------------------

explainer = shap.TreeExplainer(model)

# ----------------------------------------
# Generate Explanation
# ----------------------------------------

def generate_explanation(data):

    # Convert to dataframe
    df = pd.DataFrame([data])

    # ----------------------------------------
    # Encode categorical columns
    # ----------------------------------------

    categorical_columns = [

        "Sex",
        "Housing",
        "Saving accounts",
        "Checking account",
        "Purpose"
    ]

    for column in categorical_columns:

        encoder = label_encoders[column]

        df[column] = encoder.transform(
            df[column]
        )

    # ----------------------------------------
    # Match training columns
    # ----------------------------------------

    df = df[feature_columns]

    # ----------------------------------------
    # SHAP values
    # ----------------------------------------

    shap_values = explainer.shap_values(df)

    # Handle SHAP output safely

    if isinstance(shap_values, list):

        values = shap_values[1][0]

    else:

        values = shap_values

        # Sometimes SHAP returns 2D arrays
        if len(values.shape) > 1:

            values = values[0]

    # ----------------------------------------
    # Feature Importance
    # ----------------------------------------

    explanation = {}

    for feature, value in zip(
        feature_columns,
        values
    ):

        # Handle nested numpy arrays safely
        if hasattr(value, "__len__"):

            value = value[0]

        explanation[feature] = round(
            float(value),
            4
        )

    return explanation