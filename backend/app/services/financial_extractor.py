import re


class FinancialExtractor:

    def __init__(self, text):
        self.text = text

    def extract_value(self, keyword):

        pattern = rf"{keyword}[\s:₹$]*([\d,]+)"
        match = re.search(pattern, self.text, re.IGNORECASE)

        if match:
            return float(match.group(1).replace(",", ""))

        return None

    def extract_financials(self):

        revenue = self.extract_value("Revenue")
        expenses = self.extract_value("Expenses")
        assets = self.extract_value("Total Assets")
        liabilities = self.extract_value("Total Liabilities")
        equity = self.extract_value("Equity")

        return {
            "revenue": revenue,
            "expenses": expenses,
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity
        }