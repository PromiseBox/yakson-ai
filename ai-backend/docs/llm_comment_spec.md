# 약손 AI — LLM 코멘트 + 노인 PIM 보강 통합 스펙 (v2)

> 배포 앱(yakson-ai.vercel.app) 리포트 화면 + 팀 PR #4 프론트 계약 기준.
> 구현 위치: 이 `ai-backend`(LangGraph/LLM). 프론트는 이미 준비됨 — 백엔드가 값만 채우면 됨.

## 0. 한눈에
```
[룰 분석(사실) + 노인 PIM 보강]
   → ReportPayload(사실/서술 분리)
   → LLM 서술(GPT-5.5, 키없으면 템플릿) + audit(환각/금지어/출처) + 폴백
   → to_analysis_summary() → PR#4 포맷 { summary: { …, description } }
   → 프론트가 description(=LLM 요약)을 분석 요약 설명문으로 렌더(+복사버튼)
```

## 1. 면밀 검토 결과 — 왜 "노인 PIM 보강"이 필요한가 (C)
- 실측: 졸피뎀(졸피움정)·알프라졸람(한림)은 `product_safety_rule`·`ingredient_safety_rule` 둘 다 `ELDERLY_CAUTION` **미수록**(빅손정만 product에 수록).
- 결론: 노인주의 누락은 **쿼리 갭이 아니라 식약처 노인주의 DUR 목록의 커버리지 한계**. → 쿼리로는 못 고침.
- 해법: 국제 PIM(Beers 등) 기준 계열(벤조·Z-drug·1세대 항히스타민)을 **큐레이션 목록**으로 '잠정 노인주의' 보강. (`agents/pim.py`)
- **출처 구분**: provider `노인 부적절약물(PIM) 잠정 기준 — 약사 감수 필요`. 식약처와 명확히 분리.
- **심각도 보수적**: 기본 `주의`(중). 약사 감수 후 `위험`(상) 상향 가능(`pim._PIM_SEVERITY`).
- ⚠️ 목록·임상 문구는 **DRAFT → 약사 감수 전제**.

## 2. 사실 vs 서술 (절대 원칙)
| 구분 | 항목 | 변경 주체 |
|---|---|---|
| **사실(불변)** | counts, flag_type, severity, drugs, reason, source, 기준 수치 | 룰/큐레이션(LLM 불가) |
| **서술(가변)** | overall_message, (향후) easy_explanation/question | **LLM**(재서술만) |

임상 맥락은 LLM이 생성하지 않는다. **출처 있는 `reason`으로 공급**되고 LLM은 보호자 말투로 **재서술만** 한다. audit이 환각/금지어/출처를 검증하고 실패 시 안전 템플릿으로 폴백한다.

## 3. 프론트 계약 (PR #4) — "갖다 붙이기"의 실체
프론트는 `AnalysisReport.summary`에서 아래 우선순위로 **첫 번째 비어있지 않은 문자열**을 분석 요약 설명문으로 표시한다(있으면 복사버튼):
`summary.description` → `reportSummaryText` → `llmSummaryText` → `caregiverSummaryText`.

**백엔드가 채울 형태** (`domain.report.to_analysis_summary(payload)`):
```json
{
  "summary": {
    "riskCount": 0,
    "cautionCount": 3,
    "normalCount": 2,
    "unmatchedMedicationCount": 0,
    "description": "<LLM 보호자 요약 = overall_message>"
  }
}
```
- 카운터(위험/주의/정상)는 **항상 룰값**.
- `description`은 LLM 요약(가치포인트=노인 PIM 맥락 포함). 키 없으면 안전 템플릿이 같은 자리를 채움(앱 항상 동작).

## 4. 조현우(72세) worked example — 실DB 검증됨
입력 약: 트리람정(트리아졸람)·가나텍·베포탄.
- 룰: 용량주의·투여기간주의(식약처) 2건. **노인주의는 룰이 못 잡음.**
- **PIM 보강**: 트리아졸람=벤조계 → 노인주의(주의) 추가, 출처=PIM 잠정기준, 태그=치매·낙상.
- 결과 counts: 위험0 / **주의3**(룰2+PIM1) / 정상2. audit 통과.
- `summary.description`:
  > "아버지 복용 약을 점검한 결과, 확인이 필요한 항목 3건이 발견됐어요. **특히 트리람정0.125밀리그램(트리아졸람) 등은 어르신에게 낙상·인지 주의가 필요합니다.** 처방·복용 변경은 직접 판단하지 말고 약사·의사와 상의하세요."

→ 프론트는 이 문자열을 그대로 렌더. (GPT-5.5 키가 있으면 더 자연스러운 요약, 없으면 위 템플릿)

## 5. 통합 방법 (프론트/백엔드 역할)
- **프론트**: 추가 작업 거의 없음 — PR #4가 `summary.description` 렌더를 이미 머지함.
- **백엔드**: 분석 결과로 `build_report()` → `to_analysis_summary()` 호출해 응답의 `summary`에 넣기. (이 `ai-backend` 로직을 팀 백엔드에 연동하거나, 이 백엔드가 분석 응답을 생성)
- **운영**: 풍부한 요약을 원하면 `OPENAI_API_KEY`(GPT-5.5) 설정. 없으면 템플릿 폴백(동작·안전 동일).

## 6. 두 트랙 (잊지 말 것)
- 단기(이 PR): 큐레이션 PIM 보강 + LLM 요약.
- 정석: 식약처 노인주의 커버리지 자체를 약사 감수로 확장/검증. **LLM·PIM 보강은 보완이지 식약처 룰의 대체가 아님.**

## 7. 구현 파일
`agents/pim.py`(PIM 큐레이션·DRAFT) · `agents/assemble.py`(보강 연결+audit) · `agents/comm.py`(요약에 맥락 surface) · `domain/report.py`(`to_analysis_summary`) · `tests/test_pim.py`(30 통과).
