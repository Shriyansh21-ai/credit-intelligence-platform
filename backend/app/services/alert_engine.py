def generate_alerts(risk_score, fraud_score, drift_status):

    alerts = []

    # 🚨 High Risk
    if risk_score > 75:
        alerts.append({
            "type": "risk",
            "level": "high",
            "message": "High credit risk detected"
        })

    elif risk_score > 60:
        alerts.append({
            "type": "risk",
            "level": "medium",
            "message": "Moderate risk — monitor closely"
        })

    # 🚨 Fraud Alerts
    if fraud_score > 60:
        alerts.append({
            "type": "fraud",
            "level": "high",
            "message": "Potential fraud detected"
        })

    # 🚨 Drift Alert
    if drift_status == "drift_detected":
        alerts.append({
            "type": "model",
            "level": "warning",
            "message": "Model drift detected — retraining needed"
        })

    return alerts