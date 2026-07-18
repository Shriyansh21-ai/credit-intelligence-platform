import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from backend.app.ml.artifact_store import load_metadata, save_artifact, save_metadata

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
DATA_PATH = Path(__file__).resolve().parent / "data" / "german_credit_data.csv"


def train_and_persist_model(data_path: str | None = None, artifacts_dir: str | None = None) -> Dict[str, object]:
    resolved_data_path = Path(data_path or DATA_PATH)
    resolved_artifacts_dir = Path(artifacts_dir or ARTIFACTS_DIR)
    resolved_artifacts_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(resolved_data_path)
    print("\nDataset Loaded Successfully\n")

    if "Unnamed: 0" in df.columns:
        df.drop(columns=["Unnamed: 0"], inplace=True)

    df.fillna("Unknown", inplace=True)

    df["Risk"] = df["Risk"].map({"good": 1, "bad": 0})

    label_encoders = {}
    categorical_cols = df.select_dtypes(include=["object"]).columns
    for col in categorical_cols:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col])
        label_encoders[col] = le

    X = df.drop("Risk", axis=1)
    y = df["Risk"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
    model.fit(X_train_scaled, y_train)

    predictions = model.predict(X_test_scaled)
    accuracy = accuracy_score(y_test, predictions)

    save_artifact("label_encoders.pkl", label_encoders)
    save_artifact("feature_columns.pkl", X.columns.tolist())
    save_artifact("scaler.pkl", scaler)
    save_artifact("model.pkl", model)

    metadata = load_metadata()
    metadata.update({
        "last_trained_at": datetime.utcnow().isoformat(),
        "accuracy": round(float(accuracy), 4),
        "dataset_path": str(resolved_data_path),
        "artifacts_dir": str(resolved_artifacts_dir),
        "model_type": "RandomForestClassifier",
    })
    save_metadata(metadata)

    print(f"\n✅ Accuracy: {accuracy:.2f}\n")
    print("Classification Report:\n")
    print(classification_report(y_test, predictions))
    print("\n✅ Model and artifacts saved successfully")

    return {
        "accuracy": round(float(accuracy), 4),
        "artifacts_dir": str(resolved_artifacts_dir),
        "metadata": metadata,
    }


if __name__ == "__main__":
    train_and_persist_model()
