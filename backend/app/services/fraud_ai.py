def generate_fraud_analysis(result):

    if result["fraud_detected"]:

        return (
            "Suspicious transaction pattern detected. "
            "Transaction shows anomalous behavior "
            "compared to normal customer activity."
        )

    return (
        "Transaction appears consistent with "
        "normal behavioral patterns."
    )