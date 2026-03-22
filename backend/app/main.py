from fastapi import FastAPI
from app.api.routes import router
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth





app = FastAPI(
    title="Credit Intelligence Platform",
    description="AI powered credit risk analysis system",
    version="1.0"
)

app.include_router(router)
app.include_router(auth.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Credit Intelligence Platform API"}