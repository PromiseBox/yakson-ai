"""
노인 PIM 보강 + 보호자 요약 생성 (rule_preview에서 호출).

[왜] 식약처 노인주의 DUR이 졸피뎀/알프라졸람 등 PIM을 미수록(목록 커버리지 한계). 국제 PIM
기준 계열(벤조·Z-drug·1세대 항히스타민)을 '잠정 노인주의'로 보강하고, 보호자용 요약
(summary.description)을 생성한다.

[안전]
- PIM 출처를 식약처(DUR)와 구분: AlertEvidence.sourceType="PIM_CURATED_DRAFT", sourceName=아래.
- 심각도 보수적: CAUTION(주의). 약사 감수 후 RISK 상향 가능.
- 요약은 기본 '템플릿'(외부 호출 없음, 결정론적). 진단·처방 단정어 미사용, 약사·의사 상의로 라우팅.
- GPT 다듬기는 opt-in: LLM_SUMMARY_PROVIDER=openai + OPENAI_API_KEY 설정 시에만. 실패 시 템플릿 폴백.
- ⚠️ PIM 목록·임상 문구는 DRAFT — 약사 감수 전제. 운영 전 검수 필요.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

PIM_SOURCE_NAME = "노인 부적절약물(PIM) 잠정 기준 — 약사 감수 필요"
ELDERLY_AGE = 65
PROMPT_VERSION = "yakson-ai-report-v1"
DEFAULT_OPENAI_MODEL = "gpt-5.5"
logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class ReportTextBundle:
    caregiver_summary: str
    pharmacist_summary: str
    source: str
    model: str | None
    prompt_version: str = PROMPT_VERSION

# 분류 → (성분 키워드[약명에 포함 시 매칭], 보호자용 임상 맥락[DRAFT])
_PIM: dict[str, tuple[list[str], str]] = {
    "벤조디아제핀계": (
        ["트리아졸람", "알프라졸람", "디아제팜", "로라제팜", "클로나제팜",
         "에틸로플라제페이트", "플루라제팜", "브로마제팜", "클로르디아제폭시드"],
        "벤조디아제핀계는 고령자에서 졸림·어지럼으로 낙상·골절·인지저하·의존 위험이 커질 수 있습니다.",
    ),
    "Z-drug": (
        ["졸피뎀", "조피클론", "잘레플론", "에스조피클론"],
        "Z-drug(수면유도제)는 고령자에서 낙상·인지저하·의존 위험이 보고됩니다.",
    ),
    "1세대 항히스타민": (
        ["클로르페니라민", "디펜히드라민", "하이드록시진", "트리프롤리딘", "사이프로헵타딘"],
        "1세대 항히스타민은 고령자에서 졸림·입마름·배뇨곤란·혼동 위험을 높일 수 있습니다.",
    ),
}


def match_pim(drug_name: str) -> tuple[str, str] | None:
    """약명에 PIM 성분 키워드가 있으면 (분류, 임상 맥락)을 반환."""
    name = drug_name or ""
    for category, (keywords, context) in _PIM.items():
        if any(kw in name for kw in keywords):
            return category, context
    return None


def build_summary_description(
    patient, alerts, risk_count: int, caution_count: int, normal_count: int
) -> str:
    """보호자용 분석 요약(summary.description). 사실(약명·맥락)은 alerts에서 오고 말투만 입힘."""
    return build_report_texts(patient, alerts, risk_count, caution_count, normal_count).caregiver_summary


def build_report_texts(
    patient,
    alerts,
    risk_count: int,
    caution_count: int,
    normal_count: int,
    *,
    analysis_source: str | None = None,
) -> ReportTextBundle:
    """Graph/rule 결과를 사람이 읽을 보호자·약사용 문장으로 변환한다."""
    caregiver_summary = _template_caregiver_summary(patient, alerts, risk_count, caution_count, normal_count)
    pharmacist_summary = _template_pharmacist_summary(
        patient,
        alerts,
        risk_count,
        caution_count,
        normal_count,
        analysis_source=analysis_source,
    )
    model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    provider = os.getenv("LLM_SUMMARY_PROVIDER", "template").lower()
    if provider != "openai" or not os.getenv("OPENAI_API_KEY"):
        return ReportTextBundle(
            caregiver_summary=caregiver_summary,
            pharmacist_summary=pharmacist_summary,
            source="TEMPLATE",
            model=None,
        )

    started_at = time.perf_counter()
    try:
        polished = _polish_with_openai(
            patient=patient,
            alerts=alerts,
            risk_count=risk_count,
            caution_count=caution_count,
            normal_count=normal_count,
            caregiver_summary=caregiver_summary,
            pharmacist_summary=pharmacist_summary,
            model=model,
            analysis_source=analysis_source,
        )
        elapsed_ms = round((time.perf_counter() - started_at) * 1000)
        logger.info("ai_summary_source=OPENAI prompt_version=%s model=%s duration_ms=%s", PROMPT_VERSION, model, elapsed_ms)
        return ReportTextBundle(
            caregiver_summary=polished["caregiverSummaryText"],
            pharmacist_summary=polished["pharmacistSummaryText"],
            source="OPENAI",
            model=model,
        )
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000)
        logger.warning(
            "ai_summary_source=TEMPLATE ai_summary_failed=true prompt_version=%s model=%s duration_ms=%s error=%s",
            PROMPT_VERSION,
            model,
            elapsed_ms,
            exc,
        )
        return ReportTextBundle(
            caregiver_summary=caregiver_summary,
            pharmacist_summary=pharmacist_summary,
            source="TEMPLATE",
            model=None,
        )


# 룰 종류 → 보호자용 짧은 라벨. 출처=rule_type(사실)의 '풀이'일 뿐, LLM이 지어내는 새 의학 주장이 아니다.
_RULE_LABEL: dict[str, str] = {
    "DOSAGE_CAUTION": "용량 주의",
    "DURATION_CAUTION": "복용기간 주의",
    "ELDERLY_CAUTION": "노인주의(낙상·졸림)",
    "PRODUCT_INTERACTION": "병용 주의",
    "INGREDIENT_INTERACTION": "성분 병용 주의",
    "DUPLICATE_INGREDIENT": "성분 중복",
    "DUPLICATE_EFFICACY": "효능 중복",
    "PREGNANCY_CAUTION": "임부 주의",
    "LACTATION_CAUTION": "수유 주의",
    "AGE_CONTRAINDICATION": "연령 주의",
    "MATCHING_REVIEW": "약 정보 확인",
}
_RULE_LABEL_DEFAULT = "확인 필요"


def _caregiver_item_lines(alerts, limit: int = 3) -> list[str]:
    """약별로 묶어 '약 — 라벨1, 라벨2' 한 줄(약·라벨 중복 제거). 최대 limit개 약 + '외 N개'."""
    by_drug: dict[str, list[str]] = {}
    order: list[str] = []
    for alert in alerts:
        drugs = getattr(alert, "related_medications", None) or [""]
        drug = drugs[0]
        label = _RULE_LABEL.get(_rule_type_value(alert), _RULE_LABEL_DEFAULT)
        if drug not in by_drug:
            by_drug[drug] = []
            order.append(drug)
        if label not in by_drug[drug]:
            by_drug[drug].append(label)
    lines: list[str] = []
    for drug in order[:limit]:
        labels = ", ".join(by_drug[drug])
        lines.append(f"{drug} — {labels}" if drug else labels)
    if len(order) > limit:
        lines.append(f"외 약 {len(order) - limit}개는 아래 카드에서 확인하세요")
    return lines


def _template_caregiver_summary(patient, alerts, risk_count: int, caution_count: int, normal_count: int) -> str:
    """보호자용 요약(쉽고 상세하게). 사실은 alerts/counts에서 오고, 말투·풀이만 입힌다.
    줄바꿈 없는 한 단락(프론트가 <p>로 렌더). 진단·중단/감량 단정 없이 약사·의사 상의로 마무리.
    """
    alias = _patient_name(patient)
    age = getattr(patient, "age_years", None)
    who = f"{alias}({age}세)" if age is not None else alias
    alerted = {drug for alert in alerts for drug in (getattr(alert, "related_medications", None) or [])}
    drug_count = normal_count + len(alerted)
    med_phrase = f"복용 약 {drug_count}개를" if drug_count else "복용 약을"
    total = risk_count + caution_count

    if total == 0:
        return (f"{who} {med_phrase} 점검한 결과, 지금 등재된 위험·주의는 발견되지 않았습니다. "
                f"나머지도 함께 복용에 특별한 문제는 보이지 않았어요. "
                f"새로운 증상이 있으면 약사·의사와 상의하세요.")

    head = f"{who} {med_phrase} 점검했어요. 확인이 필요한 항목 {total}건"
    if risk_count:
        head += f"(이 중 {risk_count}건은 지금 약사·의사 확인 필요)"
    if normal_count:
        head += f", 특별한 문제 없는 약 {normal_count}개"
    head += "입니다."
    parts = [head]

    item_lines = _caregiver_item_lines(alerts)
    if item_lines:
        parts.append(" · ".join(item_lines) + ".")

    if any(_rule_type_value(alert) == "ELDERLY_CAUTION" for alert in alerts):
        parts.append(
            "어르신은 밤에 일어나실 때 불을 켜고 천천히 부축해 주시고, 졸림·어지럼이 심하면 메모해 "
            "두었다가 다음 약국 방문 때 약을 함께 보여주세요. "
            "('노인주의'는 어르신께 특히 조심해야 하는 약이라는 뜻이에요.)"
        )
    else:
        parts.append("이상 증상이 있으면 메모해 두었다가 다음 약국 방문 때 약을 함께 보여주세요.")

    parts.append("약을 임의로 끊거나 줄이지 말고, 변경은 약사·의사와 상의하세요.")
    return " ".join(parts)


def _template_pharmacist_summary(
    patient,
    alerts,
    risk_count: int,
    caution_count: int,
    normal_count: int,
    *,
    analysis_source: str | None = None,
) -> str:
    alias = _patient_name(patient)
    age = getattr(patient, "age_years", None)
    age_text = f"{age}세" if age is not None else "나이 미입력"
    source_text = "Graph DB" if analysis_source == "GRAPH" else "룰 기반"
    alert_lines = [_alert_fact(alert) for alert in alerts[:5]]
    alert_text = " / ".join(line for line in alert_lines if line)
    if not alert_text:
        alert_text = "위험·주의 알림 없음"
    suffix = "" if alert_text.endswith((".", "!", "?")) else "."
    return (
        f"{alias} / {age_text} / {source_text} 분석 기준 위험 {risk_count}건, "
        f"주의 {caution_count}건, 정상 {normal_count}건. 주요 확인 항목: {alert_text}{suffix}"
    )


def _polish_with_openai(
    *,
    patient,
    alerts,
    risk_count: int,
    caution_count: int,
    normal_count: int,
    caregiver_summary: str,
    pharmacist_summary: str,
    model: str,
    analysis_source: str | None,
) -> dict[str, str]:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "8")))
    fact_payload = {
        "patient": {
            "displayName": _patient_name(patient),
            "ageYears": getattr(patient, "age_years", None),
            "sex": _enum_value(getattr(patient, "sex", None)),
        },
        "analysisSource": analysis_source,
        "summary": {
            "riskCount": risk_count,
            "cautionCount": caution_count,
            "normalCount": normal_count,
        },
        "alerts": [_alert_payload(alert) for alert in alerts[:8]],
        "template": {
            "caregiverSummaryText": caregiver_summary,
            "pharmacistSummaryText": pharmacist_summary,
        },
    }
    resp = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "너는 약물 안전 리포트 문장 편집자다. 입력된 사실만 사용해 한국어 JSON을 반환한다. "
                    "새 약물명, 새 위험, 새 수치, 진단, 처방 변경 지시를 추가하지 않는다. "
                    "복용 중단·감량·대체 처방을 지시하지 말고 약사·의사 상담으로 안내한다. "
                    "반환 키는 caregiverSummaryText, pharmacistSummaryText 두 개만 사용한다."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(fact_payload, ensure_ascii=False),
            },
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    data = json.loads(raw)
    caregiver = str(data.get("caregiverSummaryText") or "").strip()
    pharmacist = str(data.get("pharmacistSummaryText") or "").strip()
    if not caregiver or not pharmacist:
        raise ValueError("OpenAI response missing required summary fields.")
    return {
        "caregiverSummaryText": caregiver,
        "pharmacistSummaryText": pharmacist,
    }


def _patient_name(patient) -> str:
    return getattr(patient, "display_name", None) or getattr(patient, "displayName", None) or "어르신"


def _enum_value(value: Any) -> str:
    return getattr(value, "value", None) or str(value or "")


def _rule_type_value(alert) -> str:
    return _enum_value(getattr(alert, "rule_type", None))


def _severity_value(alert) -> str:
    return _enum_value(getattr(alert, "severity", None))


def _alert_payload(alert) -> dict[str, Any]:
    return {
        "severity": _severity_value(alert),
        "ruleType": _rule_type_value(alert),
        "title": getattr(alert, "title", ""),
        "message": getattr(alert, "message", ""),
        "relatedMedications": list(getattr(alert, "related_medications", []) or []),
        "evidence": [
            {
                "sourceType": getattr(evidence, "source_type", ""),
                "sourceName": getattr(evidence, "source_name", ""),
                "description": getattr(evidence, "description", ""),
            }
            for evidence in list(getattr(alert, "evidence", []) or [])[:2]
        ],
    }


def _alert_fact(alert) -> str:
    related = ", ".join(getattr(alert, "related_medications", []) or [])
    message = getattr(alert, "message", "")
    return f"{_severity_value(alert)} {getattr(alert, 'title', '')}({related}): {message}".strip()
