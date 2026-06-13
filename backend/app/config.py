import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MODEL_PATH = os.getenv("MODEL_PATH", "app/ml/model.pkl")

settings = Settings()