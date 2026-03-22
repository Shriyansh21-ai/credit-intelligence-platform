from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def generate_pdf(data, filename="report.pdf"):

    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()

    elements = []

    # Title
    elements.append(Paragraph("Credit Risk Report", styles["Title"]))
    elements.append(Spacer(1, 12))

    # Basic Info
    elements.append(Paragraph(f"Risk Score: {data['risk_score']}", styles["Normal"]))
    elements.append(Paragraph(f"Fraud Score: {data['fraud_score']}", styles["Normal"]))
    elements.append(Paragraph(f"Decision: {data['decision']}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    # Ratios
    elements.append(Paragraph("Financial Ratios:", styles["Heading2"]))
    for key, value in data.get("ratios", {}).items():
        elements.append(Paragraph(f"{key}: {value}", styles["Normal"]))

    elements.append(Spacer(1, 12))

    # AI Analysis
    analysis = data.get("analysis", {})

    elements.append(Paragraph("AI Analysis:", styles["Heading2"]))

    elements.append(Paragraph(analysis.get("risk_summary", ""), styles["Normal"]))
    elements.append(Spacer(1, 6))

    elements.append(Paragraph("Strengths:", styles["Heading3"]))
    for s in analysis.get("strengths", []):
        elements.append(Paragraph(f"- {s}", styles["Normal"]))

    elements.append(Spacer(1, 6))

    elements.append(Paragraph("Weaknesses:", styles["Heading3"]))
    for w in analysis.get("weaknesses", []):
        elements.append(Paragraph(f"- {w}", styles["Normal"]))

    elements.append(Spacer(1, 6))

    elements.append(Paragraph(f"Confidence: {analysis.get('confidence', 0)}%", styles["Normal"]))

    doc.build(elements)

    return filename