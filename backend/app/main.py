import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import DATABASE_AUTO_CREATE, SessionLocal, database_info, get_db, initialize_database
from app.routers.analysis import router as analysis_router
from app.routers.crud import router as crud_router
from app.routers.crud import seed_default_categories


def _cors_origins() -> list[str]:
    raw = os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(
    title="Yakson AI API",
    version="0.1.0",
    description="Medication safety report API for caregiver-facing Yakson AI.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crud_router)
app.include_router(analysis_router)


@app.exception_handler(OperationalError)
async def database_connection_error_handler(_request: Request, _exc: OperationalError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": "DB에 연결할 수 없습니다. Cloud SQL 프록시와 DATABASE_URL 계정 정보를 확인해주세요."
        },
    )


@app.on_event("startup")
def startup() -> None:
    initialize_database()
    if DATABASE_AUTO_CREATE:
        db = SessionLocal()
        try:
            seed_default_categories(db)
        finally:
            db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "yakson-api"}


@app.get("/api/db/health")
def db_health(db: Session = Depends(get_db)) -> dict[str, object]:
    db.execute(text("select 1"))
    return {"status": "ok", "database": "reachable", **database_info()}


@app.post("/api/prescriptions", status_code=501)
def create_prescription_disabled() -> None:
    raise HTTPException(
        status_code=501,
        detail="Prescription bundle API is not implemented in this CRUD phase. Use /api/patients/{patient_id}/medications.",
    )


@app.post("/api/analyze", status_code=501)
def analyze_disabled() -> None:
    raise HTTPException(
        status_code=501,
        detail="AI/rule analysis is intentionally excluded from this backend CRUD phase.",
    )


@app.get("/api/reports/{report_id}", status_code=501)
def report_disabled(report_id: str) -> None:
    raise HTTPException(
        status_code=501,
        detail="Report generation is intentionally excluded from this backend CRUD phase.",
    )
