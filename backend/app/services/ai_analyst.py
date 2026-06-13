def generate_ai_analysis(result):

    risk = result["risk_level"]

    explanation = result["explanation"]

    top_factors = list(explanation.keys())[:3]

    if risk == "High":

        message = (
            f"High credit risk detected. "
            f"Main contributing factors are "
            f"{', '.join(top_factors)}."
        )

    elif risk == "Medium":

        message = (
            f"Moderate credit risk observed. "
            f"Key influencing factors include "
            f"{', '.join(top_factors)}."
        )

    else:

        message = (
            f"Applicant shows strong credit profile. "
            f"Positive indicators include "
            f"{', '.join(top_factors)}."
        )

    return message