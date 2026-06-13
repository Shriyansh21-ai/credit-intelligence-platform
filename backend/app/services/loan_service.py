import uuid

def process_loan(user_id, amount, tenure, credit_data):
    loan_id = str(uuid.uuid4())

    return {
        "loan_id": loan_id,
        "user_id": user_id,
        "amount": amount,
        "tenure": tenure,
        "status": "Approved" if credit_data["approval"] else "Rejected",
        "credit_score": credit_data["credit_score"]
    }

def generate_recommendation(credit_data):
    score = credit_data["credit_score"]

    if score > 75:
        return "Eligible for premium loan offers"
    elif score > 50:
        return "Eligible for standard loan"
    else:
        return "Improve financial behavior for better loan options"