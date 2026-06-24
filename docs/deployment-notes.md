# Deployment Notes

## 현재 결정

- 프론트엔드: Next.js
- 백엔드: FastAPI
- DB: Cloud SQL PostgreSQL, schema `yakson`
- 약물 저장: 식약처 DB 자동완성 선택 필수
- 약물 삭제: 실제 삭제가 아니라 `DELETED` 상태 처리
- 분석 결과: `분석하기` 실행 시 최신 DASHBOARD 리포트 저장

## 분석 결과 저장/조회 정책

`POST /api/patients/{patient_id}/analysis/latest`는 현재 DB에 저장된 ACTIVE 약물 목록으로 룰 분석을 실행하고 결과를 저장합니다.

정책:

- 전체 이력은 계속 저장합니다.
- 화면은 기본적으로 최신 리포트 1건을 표시합니다.
- 복용자별 분석 이력 목록에서 과거 리포트를 선택해 상세 조회할 수 있습니다.
- 백엔드는 저장 시점 약물 snapshot과 현재 ACTIVE 약물 목록을 비교해 `isStale`을 내려줍니다.
- 약물 추가/수정/삭제로 `isStale=true`가 되면 화면은 “다시 분석이 필요합니다” 경고를 표시합니다.

저장 테이블:

- `analysis_run`: 분석 실행 단위
- `analysis_alert`: 경고 카드 단위
- `analysis_alert_evidence`: 룰 근거 단위
- `patient_report`: 화면 표시용 DASHBOARD JSON과 저장 시점 약물 snapshot

삭제 정책:

- 복용자 삭제는 연결된 처방/약물/분석 이력까지 cascade 삭제합니다.
- 약물 삭제는 실제 삭제가 아니라 `prescription_medication.status='DELETED'`로 처리합니다.
- 리포트 이력은 약물 변경 후에도 삭제하지 않고, stale 상태로 표시합니다.

API 룰 타입과 DB enum이 완전히 같지 않은 항목은 DB enum에 맞춰 대표 타입으로 매핑하고, 원본 API 룰 타입은 JSON payload에 보존합니다.

- `PRODUCT_INTERACTION`, `INGREDIENT_INTERACTION` -> `CONTRAINDICATION_PAIR`
- `DUPLICATE_INGREDIENT`, `DUPLICATE_EFFICACY` -> `DUPLICATE_EFFICACY`
- `PREGNANCY_CAUTION` -> `PREGNANCY_CONTRAINDICATION`
- 나머지 안전 룰은 같은 의미의 DB enum으로 저장

## 환경 변수

Backend:

```env
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
BACKEND_SHARED_SECRET=
DATABASE_URL=postgresql+psycopg://DB_USER:DB_PASSWORD@127.0.0.1:55432/yakson
DATABASE_SCHEMA=yakson
DATABASE_AUTO_CREATE=false
DATABASE_CONNECT_TIMEOUT_SECONDS=5
```

Frontend:

```env
NEXT_PUBLIC_API_BASE_URL=
BACKEND_API_BASE_URL=http://127.0.0.1:8000
BACKEND_SHARED_SECRET=
```

`BACKEND_SHARED_SECRET`은 운영 환경에서 필수로 설정합니다. 값이 설정되면 FastAPI는 `/api/*` 요청에 `x-yakson-backend-secret` 헤더를 요구합니다. 브라우저에는 노출하지 않고 Next.js API route에서만 백엔드로 전달합니다.

## 로컬 실행

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
powershell -ExecutionPolicy Bypass -File scripts/start-frontend.ps1
```

## CORS / Proxy

- 로컬 브라우저는 `http://127.0.0.1:3000/api/*`를 호출합니다.
- Next.js API route가 `BACKEND_API_BASE_URL`로 FastAPI를 호출합니다.
- 이 구조에서는 브라우저가 FastAPI를 직접 호출하지 않으므로 CORS 노출을 줄일 수 있습니다.
- 외부 백엔드를 브라우저에서 직접 호출할 때만 `NEXT_PUBLIC_API_BASE_URL`을 설정합니다.

## Cloud SQL 프록시 없는 배포

로컬 개발은 Cloud SQL Auth Proxy를 사용할 수 있습니다. 배포 환경에서는 플랫폼에 따라 아래 중 하나를 선택합니다.

- Cloud Run: Cloud SQL 연결을 서비스에 직접 연결하고 Unix socket 또는 private IP 사용
- GCE/GKE: private IP 또는 Cloud SQL connector 사용
- 공통: DB 계정 권한은 최소 권한 원칙으로 분리하고, 비밀번호는 Secret Manager 등 런타임 secret으로 주입

현재 Cloud SQL 연결명:

```text
promisebox-yakson:asia-northeast3:yakson-postgres
```

Cloud Run 배포 시에는 로컬 proxy 명령 대신 서비스에 Cloud SQL 인스턴스를 연결합니다.

```powershell
gcloud run deploy yakson-api `
  --source backend `
  --region asia-northeast3 `
  --allow-unauthenticated `
  --add-cloudsql-instances promisebox-yakson:asia-northeast3:yakson-postgres
```

Cloud Run용 DB URL 예시:

```env
DATABASE_URL=postgresql+psycopg://DB_USER:DB_PASSWORD@/yakson?host=/cloudsql/promisebox-yakson:asia-northeast3:yakson-postgres
```

Vercel은 GitHub repo를 연결하고 Root Directory를 `frontend`로 지정합니다. 환경변수는 `BACKEND_API_BASE_URL`에 Cloud Run URL, `BACKEND_SHARED_SECRET`에 백엔드와 같은 값을 설정합니다. `NEXT_PUBLIC_API_BASE_URL`은 비워둡니다.

## 최소 배포 전 체크

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1 `
  -FrontendBaseUrl https://YOUR-VERCEL-URL `
  -BackendBaseUrl https://YOUR-CLOUD-RUN-URL `
  -BackendSharedSecret "<secret>"
```

확인 항목:

- FastAPI health
- DB health
- 케토프로펜 자동완성
- 복용자 생성/수정/삭제
- 약물 생성/수정/삭제
- 삭제 약물 목록 제외
- 병용금기 최신 리포트 저장/조회
