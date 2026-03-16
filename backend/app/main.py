from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(
    title="Credit Intelligence Platform",
    description="AI powered credit risk analysis system",
    version="1.0"
)

app.include_router(router)

@app.get("/")
def root():
    return {"message": "Credit Intelligence Platform API"}