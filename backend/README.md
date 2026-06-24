# Yakson AI Backend

FastAPI backend for Yakson AI. The current implementation provides DB-backed
CRUD APIs for patients, prescription categories, and medications. AI/LLM
features are intentionally not implemented here.

## Local Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

If `DATABASE_URL` is omitted, the app uses local SQLite at
`backend/yakson_local.db` and auto-creates the CRUD tables. For Cloud SQL,
set:

```powershell
$env:DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME"
$env:DATABASE_SCHEMA="yakson"
$env:DATABASE_AUTO_CREATE="false"
```

## Key Endpoints

- `GET /health`
- `GET /api/db/health`
- `GET /api/patients`
- `POST /api/patients`
- `PATCH /api/patients/{patient_id}`
- `DELETE /api/patients/{patient_id}`
- `GET /api/patients/{patient_id}/medications`
- `POST /api/patients/{patient_id}/medications`
- `PATCH /api/medications/{medication_id}`
- `DELETE /api/medications/{medication_id}`
- `GET /api/prescription-categories`
- `GET /api/drugs/search?q=...`

## Drug Search Troubleshooting

If a drug appears in Cloud SQL but does not appear in the app autocomplete,
check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/db/health
```

When `usingDefaultSqlite` is `true`, the backend is using
`backend/yakson_local.db` instead of Cloud SQL. Set `DATABASE_URL`,
`DATABASE_SCHEMA`, and `DATABASE_AUTO_CREATE=false`, then restart FastAPI.

## Current Implementation Notes

- Frontend is wired to the DB-backed CRUD endpoints through the Next.js `/api/*` proxy.
- Drug autocomplete reads Cloud SQL-backed 식약처 product data.
- Medication creation requires a validated `productCode` or `itemSeq`.
- Medication delete is soft delete: `prescription_medication.status="DELETED"`.
- Rule preview is still available at `POST /api/analysis/preview`.
- Latest report save/read is implemented at `POST/GET /api/patients/{patient_id}/analysis/latest`.
- Analysis storage writes `analysis_run`, `analysis_alert`, `analysis_alert_evidence`, and `patient_report`.
