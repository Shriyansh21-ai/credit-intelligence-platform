from fastapi import APIRouter
from app.schemas.company import CompanyInput
from app.services.risk_service import calculate_risk
from app.schemas.financials import FinancialInput
from app.services.financial_analysis import FinancialAnalyzer
from fastapi import UploadFile, File
from app.services.document_ai import DocumentProcessor
from app.services.financial_extractor import FinancialExtractor

router = APIRouter()

@router.post("/risk-score")
def get_risk_score(data: CompanyInput):
    score = calculate_risk(data)
    return {"risk_score": score}

@router.post("/financial-analysis")
def financial_analysis(data: FinancialInput):

    analyzer = FinancialAnalyzer(
        revenue=data.revenue,
        expenses=data.expenses,
        total_assets=data.total_assets,
        total_liabilities=data.total_liabilities,
        equity=data.equity,
        current_assets=data.current_assets,
        current_liabilities=data.current_liabilities
    )

    result = analyzer.analyze()

    return result

@router.post("/upload-financial-document")
async def upload_document(file: UploadFile = File(...)):

    file_location = f"data/uploads/{file.filename}"

    with open(file_location, "wb") as f:
        f.write(await file.read())

    processor = DocumentProcessor(file_location)

    text = processor.process_document()

    extractor = FinancialExtractor(text)

    financial_data = extractor.extract_financials()

    return {
        "extracted_text": text[:500],
        "financial_data": financial_data
    }