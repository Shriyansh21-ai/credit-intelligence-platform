from openai import OpenAI

client = OpenAI(api_key="YOUR_API_KEY")


def generate_credit_analysis(financials, risk_score, explanation):

    prompt = f"""
Act as a senior credit risk analyst at a top investment bank.

Analyze the company:

Financials:
{financials}

Risk Score:
{risk_score}

SHAP Factors:
{explanation}

Give:
• Risk Summary
• Strengths
• Weaknesses
• Lending Decision
• Confidence Level (%)

Be precise and professional.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content