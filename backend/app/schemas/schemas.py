from pydantic import BaseModel

# ------------------------------------------------
# Credit Prediction Input
# ------------------------------------------------

class CreditPredictionRequest(BaseModel):

    Age: int

    Sex: str

    Job: int

    Housing: str

    Saving_accounts: str

    Checking_account: str

    Credit_amount: int

    Duration: int

    Purpose: str

# ------------------------------------------------
# Prediction Output
# ------------------------------------------------

class CreditPredictionResponse(BaseModel):

    credit_score: int

    risk_level: str

    approval: bool

    probability: float

    prediction: int

    ai_analysis: str