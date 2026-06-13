from pydantic import BaseModel

# ------------------------------------------------
# User Data
# ------------------------------------------------

class UserData(BaseModel):

    name: str

    age: int

    income: float

    employment_type: str

# ------------------------------------------------
# Loan Request
# ------------------------------------------------

class LoanRequest(BaseModel):

    user_id: str

    amount: float

    tenure: int

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
# Credit Prediction Output
# ------------------------------------------------

class CreditPredictionResponse(BaseModel):

    credit_score: int

    risk_level: str

    approval: bool

    probability: float

    prediction: int

    ai_analysis: str