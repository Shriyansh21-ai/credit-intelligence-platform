from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def credit_chat(messages, context):

    system_prompt = f"""
You are a senior credit analyst AI.

You are analyzing a company with:

Financials:
{context.get("financials")}

Risk Score:
{context.get("risk_score")}

Fraud Score:
{context.get("fraud_score")}

SHAP Factors:
{context.get("shap_values")}

Your job:
- Answer user questions clearly
- Be financial and risk aware
- Give actionable insights
- Be concise but expert-level
"""

    chat_messages = [{"role": "system", "content": system_prompt}]

    chat_messages.extend(messages)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=chat_messages,
        temperature=0.3
    )

    return response.choices[0].message.content