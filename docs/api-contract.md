# Yakson AI API Contract

현재 프론트엔드는 같은 출처 `/api/*`를 호출하고, Next.js API route가 FastAPI로 프록시합니다. 브라우저가 외부 백엔드를 직접 호출해야 하는 배포 구조가 아니라면 `NEXT_PUBLIC_API_BASE_URL`은 비워둡니다.

## Base URLs

- Frontend proxy: `http://127.0.0.1:3000/api`
- FastAPI backend: `http://127.0.0.1:8000/api`
- Next proxy target: `BACKEND_API_BASE_URL`

## Principles

- 약물 저장은 식약처 기반 DB 자동완성에서 선택된 약물만 허용합니다.
- 미등록 약물은 “서비스 대상 아님”으로 처리합니다.
- AI/LLM 기능은 현재 범위에서 제외합니다.
- 분석 결과는 `분석하기` 실행 시 최신 DASHBOARD 리포트로 저장됩니다.
- 모든 경고는 룰 근거 테이블과 source record id를 포함해야 합니다.

## Health

### `GET /health`

```json
{
  "status": "ok",
  "service": "yakson-api"
}
```

### `GET /api/db/health`

```json
{
  "status": "ok",
  "database": "reachable",
  "driver": "postgresql+psycopg",
  "databaseName": "yakson",
  "schema": "yakson",
  "autoCreate": false,
  "usingDefaultSqlite": false
}
```

## Patients

### `GET /api/patients`

```json
{
  "items": [
    {
      "id": "1",
      "patientId": 1,
      "displayName": "홍길순 할머니",
      "ageYears": 78,
      "sex": "FEMALE",
      "createdAt": "2026-06-24T10:00:00Z",
      "updatedAt": "2026-06-24T10:00:00Z"
    }
  ]
}
```

### `POST /api/patients`

```json
{
  "displayName": "홍길순 할머니",
  "ageYears": 78,
  "sex": "FEMALE"
}
```

### `PATCH /api/patients/{patientId}`

복용자 이름, 나이, 성별을 수정할 수 있습니다.

```json
{
  "displayName": "홍길순",
  "ageYears": 79,
  "sex": "FEMALE"
}
```

### `DELETE /api/patients/{patientId}`

복용자와 연결된 처방/약물 데이터를 삭제합니다.

## Medications

### `GET /api/patients/{patientId}/medications`

`status=ACTIVE` 약물만 반환합니다.

### `POST /api/patients/{patientId}/medications`

`productCode` 또는 `itemSeq`가 실제 `drug_product`에서 확인되어야 저장됩니다.

```json
{
  "categoryName": "내과",
  "enteredDrugName": "아스피린프로텍트정100밀리그람",
  "productCode": "641100270",
  "itemSeq": "200008968",
  "durationDays": 30,
  "dosesPerDay": 1,
  "doseAmount": 1,
  "doseUnit": "정"
}
```

### `PATCH /api/medications/{medicationId}`

분류, 투약 일수, 하루 횟수, 1회 용량, 단위, 처방일, 메모를 수정할 수 있습니다.

```json
{
  "categoryName": "외과",
  "durationDays": 14,
  "dosesPerDay": 2,
  "doseAmount": 0.5,
  "doseUnit": "정"
}
```

### `DELETE /api/medications/{medicationId}`

실제 삭제가 아니라 `prescription_medication.status="DELETED"`로 변경합니다. 일반 목록에서는 보이지 않습니다.

## Drug Search

### `GET /api/drugs/search?q={query}&limit={limit}`

Cloud SQL의 식약처 기반 약물 DB를 검색합니다.

정렬 기준:

1. 정확히 일치
2. 제품명 포함
3. 성분명 포함
4. 업체명/제품코드/품목기준코드/EDI 포함

```json
{
  "items": [
    {
      "productCode": "645401820",
      "itemSeq": "199800686",
      "productName": "케펜텍-엘플라스타(케토프로펜)",
      "companyName": "제일헬스사이언스(주)",
      "ingredientNames": [],
      "matchScore": 0.7
    }
  ]
}
```

### `GET /api/drugs/validate?productCode={code}&itemSeq={seq}`

자동완성에서 선택한 약물이 현재 DB에 존재하는지 저장 직전에 다시 확인합니다.

## Analysis Preview

### `POST /api/analysis/preview`

룰 기반 분석 미리보기입니다. 디버그와 저장 전 확인용이며 결과를 DB에 저장하지 않습니다.

```json
{
  "patient": {
    "displayName": "홍길순",
    "ageYears": 78,
    "sex": "FEMALE"
  },
  "medications": [
    {
      "enteredDrugName": "중외5-에프유주",
      "categoryName": "내과",
      "productCode": "644902311",
      "durationDays": 30,
      "dosesPerDay": 1,
      "doseAmount": 1,
      "doseUnit": "정"
    },
    {
      "enteredDrugName": "티에스원캡슐25",
      "categoryName": "내과",
      "productCode": "645401940",
      "durationDays": 30,
      "dosesPerDay": 1,
      "doseAmount": 1,
      "doseUnit": "정"
    }
  ]
}
```

주요 응답 필드:

- `savedAt`: DB에 저장된 시각, 저장되지 않은 preview에서는 `null`
- `isStale`: 저장 시점 약물 snapshot과 현재 ACTIVE 약물 목록이 다르면 `true`
- `summary.riskCount`, `summary.cautionCount`, `summary.normalCount`
- `alerts[].severity`: `RISK`, `CAUTION`, `NORMAL`
- `alerts[].ruleType`: `PRODUCT_INTERACTION`, `INGREDIENT_INTERACTION`, `DUPLICATE_INGREDIENT`, `DUPLICATE_EFFICACY`, `ELDERLY_CAUTION`, `PREGNANCY_CAUTION`, `LACTATION_CAUTION`, `AGE_CONTRAINDICATION`, `DURATION_CAUTION`, `DOSAGE_CAUTION`
- `alerts[].evidence[]`: 근거 source와 source record id
- `sourceMedicationSnapshot`: 리포트 저장 시점의 약물 snapshot. `productCode`, `itemSeq`, `categoryName`, 복용일수/횟수/용량/단위를 현재 ACTIVE 약물 목록과 비교해 stale 여부를 판단
- `caregiverGuidance`: 보호자 안내 문구
- `pharmacistHandoffText`: 약사 전달 요약

## Latest Analysis Report

### `POST /api/patients/{patientId}/analysis/latest`

현재 DB에 저장된 ACTIVE 약물 목록으로 룰 분석을 실행하고 최신 DASHBOARD 리포트로 저장합니다. 요청 body는 없습니다.

저장 대상:

- `analysis_run`
- `analysis_alert`
- `analysis_alert_evidence`
- `patient_report`

응답은 `POST /api/analysis/preview`와 같은 `AnalysisReport` shape입니다.

### `GET /api/patients/{patientId}/analysis/latest`

저장된 최신 DASHBOARD 리포트를 조회합니다. 저장된 리포트가 없으면 `404`를 반환합니다. 약물 추가/수정/삭제 이후 다시 분석하지 않았다면 `isStale=true`로 내려옵니다.

### `GET /api/patients/{patientId}/analysis/reports?limit=20`

복용자별 분석 이력 목록을 최신순으로 조회합니다. 전체 이력은 DB에 계속 보관하고, 화면은 기본적으로 최신 1건을 표시합니다.

```json
{
  "items": [
    {
      "analysisRunId": 10,
      "patientReportId": 10,
      "reportId": "analysis_10",
      "createdAt": "2026-06-24T10:00:00+00:00",
      "isStale": false,
      "riskCount": 1,
      "cautionCount": 2,
      "normalCount": 3,
      "medicationCount": 6,
      "alertCount": 3,
      "isLatest": true
    }
  ]
}
```

### `GET /api/patients/{patientId}/analysis/reports/{analysisRunId}`

특정 과거 분석 리포트를 조회합니다. 응답은 `AnalysisReport` shape입니다.

## Disabled Legacy Endpoints

- `POST /api/prescriptions`: 현재 사용하지 않음
- `POST /api/analyze`: 현재 `501`, 최신 저장 분석은 `/api/patients/{patientId}/analysis/latest` 사용
- `GET /api/reports/{reportId}`: 현재 화면에서는 환자 기준 최신 리포트 조회를 사용
