# Codex Handoff

이 문서는 다른 컴퓨터나 다른 기기의 Codex가 Yakson AI 프로젝트를 바로 이어받기 위한 시작 문서입니다.

Last updated: 2026-06-25

## 저장소

- GitHub: https://github.com/PromiseBox/yakson-ai
- Branch: `main`
- Latest known deployment-prep commit: `035d5ba chore: prepare secure deployment`
- Clone path: any local workspace path is fine.

## 프로젝트 요약

Yakson AI는 보호자용 약물 안전 확인 프로토타입입니다.

- Frontend: `frontend`, Next.js
- Backend: `backend`, FastAPI
- DB: Cloud SQL PostgreSQL
- DB schema: `yakson`
- 약물 검색/저장 기준: 식약처 기반 DB 자동완성 선택 필수
- 분석 방식: 현재는 AI 제외, DB/룰 기반 분석
- 리포트 저장: `분석하기` 실행 시 최신 DASHBOARD 리포트 저장
- 이력 정책: 전체 분석 이력은 보관, 화면은 최신 리포트를 기본 표시

## 현재 구현 상태

완료된 주요 기능:

- 반응형 프론트엔드 화면
- 복용자 CRUD
- 약물 CRUD
- DB 조회 기반 약명 자동완성
- 자동완성 선택 필수 UX
- 미등록 약물 “서비스 대상 아님” 처리
- 룰 기반 분석 preview
- 최신 분석 리포트 저장/조회
- 분석 이력 목록/과거 상세 조회
- 약물 변경 후 stale 리포트 표시
- shared secret 기반 백엔드 보호
- smoke test, rule sample test 스크립트

현재 제외된 기능:

- AI/LLM 설명 보조 기능
- 로그인/권한 관리
- PDF 출력
- 운영 관리자 화면

## 중요한 정책

- 약물 저장은 식약처 DB 자동완성 후보에서 선택한 약물만 허용합니다.
- 식약처 DB에서 확인되지 않는 약물은 서비스 대상이 아닙니다.
- 약물 삭제는 실제 삭제가 아니라 `prescription_medication.status='DELETED'` 처리입니다.
- 복용자 삭제는 연결된 처방/약물/분석 이력까지 cascade 삭제합니다.
- 분석 결과는 자동 실행하지 않고 사용자가 `분석하기`를 눌렀을 때 저장합니다.
- 저장 당시 약물 snapshot과 현재 ACTIVE 약물 목록이 다르면 `isStale=true`를 내려줍니다.
- 운영 환경에서는 `BACKEND_SHARED_SECRET`을 설정하고 FastAPI `/api/*`를 보호합니다.
- 브라우저는 FastAPI를 직접 호출하지 않고 Vercel/Next.js `/api/*` route를 호출합니다.

## 주요 문서

먼저 아래 순서로 읽으면 됩니다.

1. `README.md`
2. `docs/deployment-notes.md`
3. `docs/api-contract.md`
4. `docs/rule-validation.md`
5. `docs/smoke-test.md`
6. `yakson_erd.md`

## 주요 소스 위치

Frontend:

- `frontend/app/patients/page.tsx`: 복용자 목록/생성/수정/삭제
- `frontend/app/patients/[id]/medications/page.tsx`: 약물 입력/자동완성/수정/삭제
- `frontend/app/reports/page.tsx`: 분석 대상 복용자 목록
- `frontend/app/reports/[id]/page.tsx`: 분석 실행/리포트/이력/근거 테이블
- `frontend/app/api/[...path]/route.ts`: 일반 FastAPI 프록시
- `frontend/app/api/_backend.ts`: 백엔드 URL/shared secret header 공통 처리
- `frontend/lib/api.ts`: 프론트 API client
- `frontend/lib/types.ts`: 프론트 타입

Backend:

- `backend/app/main.py`: FastAPI app, CORS, shared secret middleware, health
- `backend/app/database.py`: DB 연결 설정
- `backend/app/routers/crud.py`: 복용자/약물/약명 검색 CRUD
- `backend/app/routers/analysis.py`: 분석 preview/latest/history API
- `backend/app/services/rule_preview.py`: 룰 분석
- `backend/app/services/analysis_storage.py`: 분석 결과 저장/조회/stale 계산
- `backend/app/models.py`: API model
- `backend/app/db_models.py`: ORM model

Scripts:

- `scripts/start-backend.ps1`
- `scripts/start-frontend.ps1`
- `scripts/smoke-test.ps1`
- `scripts/rule-sample-test.ps1`

## 로컬 실행

Cloud SQL Proxy 예시:

```powershell
.\cloud-sql-proxy.x64.exe promisebox-yakson:asia-northeast3:yakson-postgres --port 55432
```

Backend:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
```

Frontend:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-frontend.ps1
```

Local URLs:

- Frontend: `http://127.0.0.1:3000`
- Backend health: `http://127.0.0.1:8000/health`
- DB health: `http://127.0.0.1:8000/api/db/health`

## 환경 변수

실제 `.env` 파일은 커밋하지 않습니다. 예시는 아래 파일을 봅니다.

- `backend/.env.example`
- `frontend/.env.example`

Backend local example:

```env
DATABASE_URL=postgresql+psycopg://DB_USER:DB_PASSWORD@127.0.0.1:55432/yakson
DATABASE_SCHEMA=yakson
DATABASE_AUTO_CREATE=false
DATABASE_CONNECT_TIMEOUT_SECONDS=5
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
BACKEND_SHARED_SECRET=
```

Frontend local example:

```env
NEXT_PUBLIC_API_BASE_URL=
BACKEND_API_BASE_URL=http://127.0.0.1:8000
BACKEND_SHARED_SECRET=
```

운영 환경에서는 backend와 frontend에 같은 `BACKEND_SHARED_SECRET`을 설정해야 합니다.

## 검증 명령

Frontend build:

```powershell
cd frontend
npm.cmd run build
```

Backend compile check:

```powershell
python -m compileall backend\app
```

시스템에 `python`이 없으면 Codex workspace dependency 또는 로컬 venv의 Python을 사용합니다.

Smoke test:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1
```

Shared secret이 켜진 환경:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1 -BackendSharedSecret "<secret>"
```

Rule sample test:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/rule-sample-test.ps1
```

## 배포 상태와 인프라 이관

배포는 인프라 담당자 계정으로 넘기기로 했습니다.

Cloud SQL connection name:

```text
promisebox-yakson:asia-northeast3:yakson-postgres
```

Backend 배포 추천:

- Platform: GCP Cloud Run
- Service name: `yakson-api`
- Region: `asia-northeast3`
- Source directory: `backend`
- Port: `8080`
- Cloud SQL instance: `promisebox-yakson:asia-northeast3:yakson-postgres`

Frontend 배포 추천:

- Platform: Vercel
- GitHub repo: `PromiseBox/yakson-ai`
- Root Directory: `frontend`
- Build Command: `npm run build`

운영 환경변수:

Backend Cloud Run:

```env
DATABASE_URL=postgresql+psycopg://DB_USER:DB_PASSWORD@/yakson?host=/cloudsql/promisebox-yakson:asia-northeast3:yakson-postgres
DATABASE_SCHEMA=yakson
DATABASE_AUTO_CREATE=false
DATABASE_CONNECT_TIMEOUT_SECONDS=5
BACKEND_SHARED_SECRET=<secret>
BACKEND_CORS_ORIGINS=https://YOUR-VERCEL-DOMAIN
```

Frontend Vercel:

```env
NEXT_PUBLIC_API_BASE_URL=
BACKEND_API_BASE_URL=https://YOUR-CLOUD-RUN-URL
BACKEND_SHARED_SECRET=<same-secret-as-backend>
```

주의:

- 운영 DB 계정은 현재 개발 계정 대신 인프라/DBA가 발급한 계정으로 교체 예정입니다.
- 기준 데이터는 가능하면 `SELECT`만, 환자/약물/분석 업무 테이블만 CRUD 권한을 권장합니다.
- `BACKEND_SHARED_SECRET`은 절대 `NEXT_PUBLIC_*` 변수로 만들지 않습니다.

## 최근 막혔던 배포 이슈

이전 시도에서는 개인 GCP 계정으로 배포를 진행하려 했으나 권한이 부족했습니다.

부족했던 권한/상태:

- Cloud Run Admin API 비활성
- Cloud Build API 비활성
- Artifact Registry API 비활성
- `serviceusage.services.enable` 권한 없음
- `secretmanager.secrets.create` 권한 없음
- Cloud Run 배포 권한 없음

인프라 담당자에게 필요한 권한:

- Service Usage Admin
- Cloud Run Admin
- Cloud Build Editor
- Artifact Registry Admin 또는 Writer
- Secret Manager Admin
- Service Account User

Vercel은 CLI가 설치되어 있지 않았고, `npx vercel`은 실행 가능했지만 로그인 인증 대기에서 중단했습니다. 인프라 담당자 계정으로 Vercel Dashboard에서 GitHub repo를 연결하는 방식을 추천합니다.

## 다음 작업 순서

현재 합의된 큰 순서:

1. 배포
2. 운영 보안/로그/백업/권한 점검
3. 운영 URL smoke test
4. 룰 검증 문서화 보강
5. AI 설명 보조 기능 추가
6. 화면 및 기능 QA
7. 개인정보/운영 정책 최종 정리

배포 이후 바로 확인할 것:

- Cloud Run `/health`
- Cloud Run `/api/db/health` with shared secret
- Vercel `/api/drugs/search?q=케토프로펜`
- 복용자 생성/수정/삭제
- 약물 자동완성/저장/수정/삭제
- 분석하기
- 리포트 이력 조회
- 약물 변경 후 stale 표시
- 모바일 화면

## AI 기능 추가 방향

AI는 금기/위험 판단 주체가 아니라 설명 보조로 둡니다.

추천 기능:

- 보호자용 쉬운 말 요약
- 약사에게 전달할 질문/요약문 생성
- 룰 기반 경고 결과를 쉬운 말로 풀어쓰기
- 생활습관 안내 문구 보강
- 현재 등록 약물 기준 Q&A

AI 기능 추가 전 결정할 것:

- AI 요청에 개인정보를 포함할지
- AI 응답을 DB에 저장할지
- AI 비용/로그/장애 처리 방식
- “AI 설명은 참고용이며 최종 판단은 룰/전문가 확인 기준” 문구

## Codex 작업 시 주의

- `.env`, DB 비밀번호, API key는 커밋하지 않습니다.
- 기존 사용자 변경사항이 있으면 되돌리지 말고 먼저 `git status`로 확인합니다.
- 수동 파일 수정은 `apply_patch`를 사용합니다.
- Windows PowerShell에서는 `npm` 대신 `npm.cmd`가 필요할 수 있습니다.
- `python`이 PATH에 없으면 Codex 번들 Python 경로를 사용합니다.
- Git 작업은 로컬 권한 문제로 escalation이 필요할 수 있습니다.
- 배포 URL이 생기면 `scripts/smoke-test.ps1`로 운영 smoke test를 먼저 실행합니다.
