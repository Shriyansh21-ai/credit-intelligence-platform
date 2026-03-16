import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
import joblib

data = pd.read_csv("../../data/company_financials.csv")

X = data[[
    "revenue_growth",
    "debt_ratio",
    "current_ratio",
    "roe"
]]

y = data["default"]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2
)

model = XGBClassifier()

model.fit(X_train, y_train)

joblib.dump(model, "../models/risk_model.pkl")

print("Model trained and saved")