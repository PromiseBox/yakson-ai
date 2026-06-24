# Yakson AI

Yakson AI는 보호자용 약물 안전 확인 프로토타입입니다. 현재 구현은 Next.js 프론트엔드, FastAPI 백엔드, Cloud SQL PostgreSQL 기반 CRUD와 룰 기반 최신 리포트 저장으로 구성되어 있습니다.

## Current Status

- Cloud SQL schema/data migration: completed
- Frontend: responsive Next.js UI
- Backend: DB-backed CRUD, drug autocomplete, rule analysis save/read
- AI/LLM features: excluded for now
- Analysis persistence: latest dashboard report is saved to `analysis_*` and `patient_report`
- Report history: all runs are retained; the UI shows the latest by default and allows past report lookup

## Local URLs

- Frontend: `http://127.0.0.1:3000`
- Backend health: `http://127.0.0.1:8000/health`
- DB health: `http://127.0.0.1:8000/api/db/health`

## Run

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
powershell -ExecutionPolicy Bypass -File scripts/start-frontend.ps1
```

## Smoke Test

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1
```

배포 환경처럼 백엔드 shared secret을 켠 경우:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1 -BackendSharedSecret "<secret>"
```

## Important Behavior

- 약물 저장은 식약처 DB 자동완성 후보 선택이 필수입니다.
- 미등록 약물은 서비스 대상이 아닙니다.
- 약물 삭제는 실제 삭제가 아니라 `status=DELETED` 처리입니다.
- 분석은 사용자가 `분석하기`를 눌렀을 때 실행되고 최신 리포트로 저장됩니다.
- 약물 목록이 저장 시점과 달라지면 백엔드가 `isStale=true`를 내려주고, 리포트 화면에서 다시 분석 필요 문구를 표시합니다.
- 룰 근거는 리포트 화면의 근거 테이블에 표시됩니다.
- 운영 환경에서는 `BACKEND_SHARED_SECRET`으로 FastAPI `/api/*`를 보호하고, Next.js 서버 프록시만 이 값을 전달합니다.

## Docs

- API contract: `docs/api-contract.md`
- Rule validation: `docs/rule-validation.md`
- Smoke test: `docs/smoke-test.md`
- Deployment notes: `docs/deployment-notes.md`
