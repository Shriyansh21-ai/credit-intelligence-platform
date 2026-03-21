import os
from dotenv import load_dotenv
from openai import OpenAI
import json

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_credit_analysis(financials, risk_score, shap_values):

    prompt = f"""
You are a senior credit risk analyst.

Analyze the following company data.

Financials:
{financials}

Risk Score:
{risk_score}

SHAP Factors:
{shap_values}

Return ONLY a valid JSON (no text outside JSON):

{{
  "risk_summary": "...",
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "fraud_flags": ["...", "..."],
  "decision": "Approve / Conditional / Reject",
  "confidence": 0-100
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a financial risk expert. Always return JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    raw_output = response.choices[0].message.content

    try:
        return json.loads(raw_output)
    except:
        return {
            "risk_summary": raw_output,
            "strengths": [],
            "weaknesses": [],
            "fraud_flags": [],
            "decision": "Unknown",
            "confidence": 0
        }