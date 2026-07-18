import json
import os
from pathlib import Path
from typing import Any, Dict

import joblib

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def save_artifact(name: str, payload: Any) -> Path:
    path = ARTIFACTS_DIR / name
    joblib.dump(payload, path)
    return path


def load_artifact(name: str, default: Any = None) -> Any:
    path = ARTIFACTS_DIR / name
    if not path.exists():
        return default
    return joblib.load(path)


def save_metadata(metadata: Dict[str, Any]) -> Path:
    path = ARTIFACTS_DIR / "training_metadata.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2, default=str)
    return path


def load_metadata() -> Dict[str, Any]:
    path = ARTIFACTS_DIR / "training_metadata.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)
