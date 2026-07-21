import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MODEL_PATH = os.getenv("MODEL_PATH", "app/ml/model.pkl")

    # --- Document Intelligence (Phase 2) ---
    # Root directory for the local storage backend (files are NOT stored in the DB).
    STORAGE_ROOT = os.getenv("STORAGE_ROOT", "backend/storage")
    # Maximum accepted upload size, in megabytes.
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
    # OCR engine selection: "auto" picks the best path per document.
    OCR_ENGINE = os.getenv("OCR_ENGINE", "auto")

    # --- Enterprise AI Risk Intelligence (Phase 4) ---
    # Default risk model used by the ML engine when a caller does not specify
    # one. Must match a registered model_type (see services/ml/models/catalog).
    # No model is trained yet, so all types run the deterministic estimator.
    ML_DEFAULT_MODEL = os.getenv("ML_DEFAULT_MODEL", "scorecard")
    # Default explanation method: "auto" | "contribution" | "shap" | "lime".
    # "auto" uses SHAP when the active model is trained, else exact contributions.
    ML_EXPLAINER = os.getenv("ML_EXPLAINER", "auto")

    # Accepted upload content types -> canonical extension.
    ALLOWED_UPLOAD_TYPES = {
        "application/pdf": "pdf",
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
    }

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

settings = Settings()