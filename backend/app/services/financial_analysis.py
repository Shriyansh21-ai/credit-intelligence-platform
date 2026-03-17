class FinancialAnalyzer:

    def __init__(self, revenue, expenses, total_assets, total_liabilities, equity, current_assets, current_liabilities):
        self.revenue = revenue
        self.expenses = expenses
        self.total_assets = total_assets
        self.total_liabilities = total_liabilities
        self.equity = equity
        self.current_assets = current_assets
        self.current_liabilities = current_liabilities

    def profit_margin(self):
        return (self.revenue - self.expenses) / self.revenue

    def debt_ratio(self):
        return self.total_liabilities / self.total_assets

    def current_ratio(self):
        return self.current_assets / self.current_liabilities

    def return_on_equity(self):
        net_income = self.revenue - self.expenses
        return net_income / self.equity

    def analyze(self):
        return {
            "profit_margin": round(self.profit_margin(), 3),
            "debt_ratio": round(self.debt_ratio(), 3),
            "current_ratio": round(self.current_ratio(), 3),
            "roe": round(self.return_on_equity(), 3)
        }