"""
Tieout backend — FastAPI application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as ingest_router
from backend.cash_position.routes import router as cash_position_router
from backend.exceptions.routes import audit_router, exceptions_router

app = FastAPI(
    title="Tieout",
    description="Payment reconciliation engine for self-funded health plans",
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*|http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router)
app.include_router(exceptions_router)
app.include_router(audit_router)
app.include_router(cash_position_router)


@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    return {"status": "ok"}
