# Smoke Test

## 실행 전 준비

1. Cloud SQL 프록시 또는 배포 DB 연결을 준비합니다.
2. `backend/.env`에 `DATABASE_URL`, `DATABASE_SCHEMA=yakson`, `DATABASE_AUTO_CREATE=false`를 설정합니다.
3. 백엔드와 프론트엔드를 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
powershell -ExecutionPolicy Bypass -File scripts/start-frontend.ps1
```

## 자동 스모크 테스트

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1
```

배포 환경처럼 shared secret이 설정된 백엔드를 직접 확인할 때:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1 `
  -FrontendBaseUrl https://YOUR-VERCEL-URL `
  -BackendBaseUrl https://YOUR-CLOUD-RUN-URL `
  -BackendSharedSecret "<secret>"
```

성공하면 `Smoke test passed.`가 출력됩니다.

자동 확인 범위:

- 백엔드/DB health
- 케토프로펜 DB 검색 자동완성
- 복용자 생성/수정/삭제
- 약물 생성/수정/삭제
- 최신 리포트 저장/조회
- 분석 이력 목록/상세 조회
- 약물 수정 후 `isStale=true` 전환
- 재분석 후 최신 리포트 `isStale=false` 복귀와 과거 이력 보존

룰 샘플 전체 검증:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/rule-sample-test.ps1
```

## 수동 확인

1. `http://127.0.0.1:3000/patients` 접속
2. 복용자 추가
3. 약 입력 화면에서 `케토프로펜` 검색
4. 자동완성 후보를 선택하지 않고 저장 시도
5. “식약처 DB 검색 결과에서 약물을 선택해야 DB에 저장할 수 있습니다.” 문구 확인
6. 자동완성 후보 선택 후 저장
7. 등록된 약 목록에서 공식명, 업체명, 제품코드 확인
8. 약물 수정 버튼으로 분류, 투약 일수, 하루 횟수, 1회 용량, 단위 수정
9. 약물 삭제 후 목록에서 사라지는지 확인
10. 리포트 화면에서 `분석하기` 클릭
11. “최신 분석 리포트를 저장했습니다.” 문구 확인
12. 페이지를 새로고침해도 저장된 최신 리포트가 다시 표시되는지 확인
13. 분석 이력 목록에 실행일시, 위험/주의 건수, 약물 수가 표시되는지 확인
14. 과거 이력의 `보기`를 눌러 특정 리포트 상세가 표시되는지 확인
15. 약물 수정/삭제 후 리포트 화면에 “다시 분석이 필요합니다” 문구가 표시되는지 확인
16. 분석 이력 목록에서 오래된 리포트에 `재분석 필요` 뱃지가 표시되는지 확인
17. 다시 분석 후 최신 리포트의 stale 경고가 사라지는지 확인
18. 룰별 근거 테이블과 약사 전달 요약 확인
19. 모바일 폭에서 자동완성 목록과 근거 테이블이 가로 스크롤로 깨지지 않는지 확인
