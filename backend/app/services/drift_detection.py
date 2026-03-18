import numpy as np

baseline = np.array([0.1, 0.5, 1.2, 0.12])  # initial avg


def detect_drift(new_data):

    new = np.array([
        new_data["revenue_growth"],
        new_data["debt_ratio"],
        new_data["current_ratio"],
        new_data["roe"]
    ])

    diff = np.abs(new - baseline)

    if np.mean(diff) > 0.3:
        return "Data drift detected"

    return "No drift"