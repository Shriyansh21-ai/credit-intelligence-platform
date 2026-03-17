from pydantic import BaseModel

class FinancialInput(BaseModel):

    revenue: float
    expenses: float
    total_assets: float
    total_liabilities: float
    equity: float
    current_assets: float
    current_liabilities: float