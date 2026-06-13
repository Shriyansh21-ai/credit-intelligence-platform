import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
import joblib
import os

ARTIFACTS_DIR = "app/ml/artifacts"

os.makedirs(ARTIFACTS_DIR, exist_ok=True)

def preprocess_data(filepath):
    df = pd.read_csv(filepath)

    # Convert target
    df["Risk"] = df["Risk"].map({"good": 1, "bad": 0})

    # Encode categorical columns
    categorical_cols = df.select_dtypes(include=["object"]).columns

    encoders = {}

    for col in categorical_cols:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col])
        encoders[col] = le

    X = df.drop("Risk", axis=1)
    y = df["Risk"]

    # Save columns
    joblib.dump(X.columns.tolist(), f"{ARTIFACTS_DIR}/columns.pkl")

    scaler = StandardScaler()

    X_scaled = scaler.fit_transform(X)

    # Save scaler
    joblib.dump(scaler, f"{ARTIFACTS_DIR}/scaler.pkl")

    return train_test_split(
        X_scaled,
        y,
        test_size=0.2,
        random_state=42
    )