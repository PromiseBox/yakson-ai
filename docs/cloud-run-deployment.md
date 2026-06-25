# Cloud Run 배포 가이드

이 문서는 Yakson AI를 Vercel 없이 GCP Cloud Run에 배포하는 기준을 정리한다.

## 배포 구조

```text
Browser
  -> yakson-web Cloud Run service
  -> Next.js /api/* server route
  -> yakson-api Cloud Run service
  -> Cloud SQL PostgreSQL
```

브라우저는 FastAPI를 직접 호출하지 않는다. Next.js 서버 라우트가 `BACKEND_API_BASE_URL`로 FastAPI에 프록시한다.

## 서비스

| 구분 | 값 |
|---|---|
| Frontend service | `yakson-web` |
| Backend service | `yakson-api` |
| Region | `asia-northeast3` |
| Backend port | `8080` |
| Frontend port | `8080` |
| Cloud SQL | `promisebox-yakson:asia-northeast3:yakson-postgres` |

## Backend 환경변수

```env
DATABASE_SCHEMA=yakson
DATABASE_AUTO_CREATE=false
DATABASE_CONNECT_TIMEOUT_SECONDS=5
BACKEND_CORS_ORIGINS=https://YAKSON_WEB_URL
```

Secret Manager에서 주입할 값:

```text
DATABASE_URL              -> yakson-database-url
BACKEND_SHARED_SECRET     -> yakson-backend-shared-secret
```

## Frontend 환경변수

```env
NEXT_PUBLIC_API_BASE_URL=
BACKEND_API_BASE_URL=https://YAKSON_API_URL
```

Secret Manager에서 주입할 값:

```text
BACKEND_SHARED_SECRET     -> yakson-backend-shared-secret
```

`BACKEND_SHARED_SECRET`은 Next.js 서버 라우트에서만 사용한다. `NEXT_PUBLIC_*` 변수로 만들지 않는다.

## 로컬 Docker 빌드 확인

Backend:

```bash
cd backend
docker build -t yakson-backend:local .
```

Frontend:

```bash
cd frontend
docker build -t yakson-frontend:local .
```

## 헬스체크

Backend:

```bash
curl https://YAKSON_API_URL/health
```

기대 응답:

```json
{
  "status": "ok",
  "service": "yakson-api"
}
```

DB 연결 확인:

```bash
curl -H "x-yakson-backend-secret: SHARED_SECRET" \
  https://YAKSON_API_URL/api/db/health
```

## 배포 전 필수 준비

- Artifact Registry 저장소 생성
- Cloud Run runtime service account 생성
- runtime service account에 `roles/cloudsql.client` 부여
- runtime service account에 Secret Manager accessor 권한 부여
- Secret Manager에 `yakson-database-url` 생성 및 값 등록
- Secret Manager에 `yakson-backend-shared-secret` 생성 및 값 등록
- 운영 DB 계정 생성 및 `yakson` schema/table 권한 부여
