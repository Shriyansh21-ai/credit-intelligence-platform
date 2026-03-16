from pydantic import BaseModel

class CompanyInput(BaseModel):

    revenue_growth: float
    debt_ratio: float
    current_ratio: float
    roe: float