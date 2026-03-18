from fastapi import APIRouter
from app.schemas.company import CompanyInput
from app.services.risk_service import calculate_risk
from app.schemas.financials import FinancialInput
from app.services.financial_analysis import FinancialAnalyzer
from fastapi import UploadFile, File
from app.services.document_ai import DocumentProcessor
from app.services.financial_extractor import FinancialExtractor
from app.services.explainability import explain_prediction
from app.services.ai_analyst import generate_credit_analysis

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

@router.post("/explain-risk")
def explain_risk(data: CompanyInput):

    explanation = explain_prediction(data)

    return {
        "explanation": explanation
    }

@router.post("/ai-credit-analysis")
async def ai_credit_analysis(file: UploadFile = File(...)):

    # Step 1: Save file
    file_path = f"data/uploads/{file.filename}"

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Step 2: OCR
    processor = DocumentProcessor(file_path)
    text = processor.process_document()

    # Step 3: Extract financials
    extractor = FinancialExtractor(text)
    financials = extractor.extract_financials()

    # Step 4: Prepare data
    data = {
        "revenue_growth": 0.1,
        "debt_ratio": (financials["liabilities"] or 1) / (financials["assets"] or 1),
        "current_ratio": 1.2,
        "roe": 0.15
    }

    # Step 5: Risk score
    risk_score = calculate_risk(data)

    # Step 6: SHAP explanation
    explanation = explain_prediction(type("obj", (object,), data))

    # Step 7: AI Analysis
    analysis = generate_credit_analysis(financials, risk_score, explanation)

    return {
        "risk_score": risk_score,
        "analysis": analysis
    }