import json
from datetime import datetime

LOG_FILE = "data/audit_log.json"


def log_decision(data):

    entry = {
        "timestamp": str(datetime.now()),
        "input": data["input"],
        "risk_score": data["risk_score"],
        "decision": data["decision"]
    }

    try:
        with open(LOG_FILE, "r") as f:
            logs = json.load(f)
    except:
        logs = []

    logs.append(entry)

    with open(LOG_FILE, "w") as f:
        json.dump(logs, f)