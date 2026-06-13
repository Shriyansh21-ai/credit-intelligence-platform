import os
import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import accuracy_score, classification_report

# ------------------------------------------------
# Paths
# ------------------------------------------------

ARTIFACTS_DIR = "app/ml/artifacts"
DATA_PATH = "app/ml/data/german_credit_data.csv"

os.makedirs(ARTIFACTS_DIR, exist_ok=True)

# ------------------------------------------------
# Load Dataset
# ------------------------------------------------

df = pd.read_csv(DATA_PATH)


print("\nDataset Loaded Successfully\n")

# Remove unnecessary column if exists
if "Unnamed: 0" in df.columns:
    df.drop(columns=["Unnamed: 0"], inplace=True)

# ------------------------------------------------
# Handle Missing Values
# ------------------------------------------------

df.fillna("Unknown", inplace=True)

# ------------------------------------------------
# Encode Target
# good = 1
# bad = 0
# ------------------------------------------------

df["Risk"] = df["Risk"].map({
    "good": 1,
    "bad": 0
})

# ------------------------------------------------
# Encode Categorical Features
# ------------------------------------------------

label_encoders = {}

categorical_cols = df.select_dtypes(include=["object"]).columns

for col in categorical_cols:

    le = LabelEncoder()

    df[col] = le.fit_transform(df[col])

    label_encoders[col] = le

# Save encoders
joblib.dump(
    label_encoders,
    f"{ARTIFACTS_DIR}/label_encoders.pkl"
)

# ------------------------------------------------
# Features and Target
# ------------------------------------------------

X = df.drop("Risk", axis=1)
y = df["Risk"]

# Save feature columns
joblib.dump(
    X.columns.tolist(),
    f"{ARTIFACTS_DIR}/feature_columns.pkl"
)

# ------------------------------------------------
# Train Test Split
# ------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)

# ------------------------------------------------
# Scaling
# ------------------------------------------------

scaler = StandardScaler()

X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Save scaler
joblib.dump(
    scaler,
    f"{ARTIFACTS_DIR}/scaler.pkl"
)

# ------------------------------------------------
# Model Training
# ------------------------------------------------

model = RandomForestClassifier(
    n_estimators=200,
    max_depth=8,
    random_state=42
)

model.fit(X_train_scaled, y_train)

# ------------------------------------------------
# Evaluation
# ------------------------------------------------

predictions = model.predict(X_test_scaled)

accuracy = accuracy_score(y_test, predictions)

print(f"\n✅ Accuracy: {accuracy:.2f}\n")

print("Classification Report:\n")

print(classification_report(y_test, predictions))

# ------------------------------------------------
# Save Model
# ------------------------------------------------

joblib.dump(
    model,
    f"{ARTIFACTS_DIR}/model.pkl"
)

print("\n✅ Model Saved Successfully")