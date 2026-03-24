import json
import os

FILE_PATH = "data/risk_history.json"


def save_risk(company_name, risk_score):

    if not os.path.exists(FILE_PATH):
        data = {}
    else:
        with open(FILE_PATH, "r") as f:
            data = json.load(f)

    if company_name not in data:
        data[company_name] = []

    data[company_name].append(risk_score)

    with open(FILE_PATH, "w") as f:
        json.dump(data, f)


def get_risk_history(company_name):

    if not os.path.exists(FILE_PATH):
        return []

    with open(FILE_PATH, "r") as f:
        data = json.load(f)

    return data.get(company_name, [])