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
from app.services.simulation import apply_scenario
from app.services.fraud_detection import detect_fraud
from app.services.decision_engine import make_decision
from app.services.decision_engine import generate_loan_terms
from app.services.risk_history import save_risk
from app.services.drift_detection import detect_drift
from app.services.audit_logger import log_decision
from app.services.ai_chat import credit_chat
from app.services.portfolio import analyze_portfolio
from app.services.alert_engine import generate_alerts


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
    # Convert explanation to better format for AI
    if isinstance(explanation, list):
        shap_values = {item["feature"]: item["value"] for item in explanation}
    else:
        shap_values = explanation

    analysis = generate_credit_analysis(
    financials=financials,
    risk_score=risk_score,
    shap_values=shap_values
)

    # Create ratios
    ratios = {
    "debt_ratio": data["debt_ratio"],
    "current_ratio": data["current_ratio"],
    "roe": data["roe"]
}

    # Fraud detection
    fraud_flags = detect_fraud(financials, ratios)

    #fraud score
    fraud_score = min(len(fraud_flags) * 20, 100)

    #decision making
    decision = make_decision(risk_score, fraud_score)
    
    #loan terms
    loan_terms = generate_loan_terms(risk_score)

    save_risk("company_x", risk_score)

    drift_status = detect_drift(data)

    log_decision({
    "input": data,
    "risk_score": risk_score,
    "decision": decision
    })
    
    alerts = generate_alerts(risk_score, fraud_score, drift_status)

    return {
    "risk_score": risk_score,
    "fraud_score": fraud_score,
    "alerts": alerts,
    "decision": decision,
    "loan_terms": loan_terms,
    "drift_status": drift_status,

    "analysis": analysis,  # AI output

    # 🔥 NEW (for frontend power)
    "financials": financials,
    "shap_values": shap_values,
    "fraud_flags": fraud_flags
}

@router.post("/simulate-risk")
def simulate_risk(input_data: dict):

    base_data = input_data["base_data"]
    scenario = input_data["scenario"]

    # Apply scenario
    new_data = apply_scenario(base_data, scenario)

    # Recalculate
    risk_score = calculate_risk(new_data)
    explanation = explain_prediction(type("obj", (object,), new_data))

    return {
        "new_data": new_data,
        "risk_score": risk_score,
        "explanation": explanation
    }

@router.post("/chat")
def chat_endpoint(payload: dict):

    messages = payload["messages"]
    context = payload["context"]

    reply = credit_chat(messages, context)

    return {
        "reply": reply
    }

@router.post("/portfolio-analysis")
def portfolio_analysis(data: dict):

    companies = data["companies"]

    result = analyze_portfolio(companies)

    return result