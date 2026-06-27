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
NEO4J_ANALYSIS_ENABLED=true
NEO4J_URI=bolt+s://YOUR_AURA_INSTANCE.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_DATABASE=neo4j
LLM_SUMMARY_PROVIDER=openai
OPENAI_MODEL=gpt-5.5
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=yakson-ai-dev
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_HIDE_INPUTS=false
LANGSMITH_HIDE_OUTPUTS=false
```

Secret Manager에서 주입할 값:

```text
DATABASE_URL              -> yakson-database-url
BACKEND_SHARED_SECRET     -> yakson-backend-shared-secret
NEO4J_PASSWORD            -> yakson-neo4j-password
OPENAI_API_KEY            -> yakson-openai-api-key (선택)
LANGSMITH_API_KEY         -> yakson-langsmith-api-key (선택)
```

`yakson-openai-api-key` Secret이 없으면 배포 workflow는 해당 secret 주입을 건너뛰고
백엔드는 템플릿 기반 AI 리포트 문구를 사용한다. Secret을 생성한 뒤 다음 배포부터
OpenAI 문장 다듬기가 활성화된다.

`yakson-langsmith-api-key` Secret이 있으면 OpenAI 리포트 문장 다듬기 호출이
LangSmith 프로젝트 `yakson-ai-dev`로 전송된다. 트레이스 전송 전 사람 식별 값은
백엔드 마스킹 함수에서 가리고, 약 이름과 알림 근거 문장은 평가를 위해 보존한다.

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
- Secret Manager에 `yakson-neo4j-password` 생성 및 값 등록
- 운영 DB 계정 생성 및 `yakson` schema/table 권한 부여

Neo4j password secret 생성 예시:

```bash
printf '%s' 'YOUR_NEO4J_PASSWORD' | gcloud secrets create yakson-neo4j-password \
  --project promisebox-yakson \
  --replication-policy=automatic \
  --data-file=-
```

Cloud Run runtime service account에 secret 접근 권한 부여:

```bash
gcloud secrets add-iam-policy-binding yakson-neo4j-password \
  --project promisebox-yakson \
  --member serviceAccount:yakson-runner@promisebox-yakson.iam.gserviceaccount.com \
  --role roles/secretmanager.secretAccessor
```

Neo4j AuraDB는 `bolt+s://...` URI를 사용한다. `neo4j+s://...` 라우팅이 막히는
Aura 환경에서도 `bolt+s://...`는 Cloud Run에서 직접 연결할 수 있다.

## AI 리포팅 설정

Graph-first 분석 결과의 위험/주의/정상 판정은 Neo4j와 PostgreSQL 룰이 담당하고,
AI는 보호자 요약과 약사 전달 요약의 문장 다듬기에만 사용한다. OpenAI 사용을 켜려면
다음 Secret을 만든다.

```bash
printf '%s' 'YOUR_OPENAI_API_KEY' | gcloud secrets create yakson-openai-api-key \
  --project promisebox-yakson \
  --replication-policy=automatic \
  --data-file=-
```

Cloud Run runtime service account에 secret 접근 권한 부여:

```bash
gcloud secrets add-iam-policy-binding yakson-openai-api-key \
  --project promisebox-yakson \
  --member serviceAccount:yakson-runner@promisebox-yakson.iam.gserviceaccount.com \
  --role roles/secretmanager.secretAccessor
```

LangSmith tracing을 켜려면 다음 Secret을 만든다.

```bash
printf '%s' 'YOUR_LANGSMITH_API_KEY' | gcloud secrets create yakson-langsmith-api-key \
  --project promisebox-yakson \
  --replication-policy=automatic \
  --data-file=-
```

Cloud Run runtime service account에 secret 접근 권한 부여:

```bash
gcloud secrets add-iam-policy-binding yakson-langsmith-api-key \
  --project promisebox-yakson \
  --member serviceAccount:yakson-runner@promisebox-yakson.iam.gserviceaccount.com \
  --role roles/secretmanager.secretAccessor
```

OpenAI 호출이 실패하거나 응답 형식이 맞지 않으면 리포트 생성은 실패하지 않고
템플릿 요약으로 fallback된다.

## Neo4j Graph 재적재

Cloud SQL의 DUR 데이터가 갱신되면 GitHub Actions의 `Load Neo4j Graph` workflow를
수동 실행한다. 이 workflow는 백엔드 이미지를 빌드한 뒤 `yakson-neo4j-loader`
Cloud Run Job을 배포하고 실행한다.

기본 입력값:

```text
resetGraph=true
includePatients=true
patientIdScope=
```

특정 환자 검증용으로만 좁혀 적재할 때는 `patientIdScope`에 `22` 또는 `22,23`처럼
쉼표로 구분한 환자 ID를 입력한다. 운영 전체 재적재는 `patientIdScope`를 비워둔다.

재적재 후 대표 회귀 케이스는 다음 스크립트로 확인한다.

```bash
cd backend
python scripts/verify_analysis_regression.py --patient-id 22
```
