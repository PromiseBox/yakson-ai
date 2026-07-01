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
from dataclasses import dataclass, field
from typing import Any

from app.services.langsmith_masking import maybe_wrap_openai_client

PIM_SOURCE_NAME = "노인 부적절약물(PIM) 잠정 기준 — 약사 감수 필요"
ELDERLY_AGE = 65
PROMPT_VERSION = "yakson-ai-report-v2"
DEFAULT_OPENAI_MODEL = "gpt-5.5"
logger = logging.getLogger("uvicorn.error")

_CAREGIVER_RULE_LABELS: dict[str, str] = {
    "PRODUCT_INTERACTION": "병용 주의",
    "INGREDIENT_INTERACTION": "성분 병용 주의",
    "DUPLICATE_INGREDIENT": "성분 중복",
    "DUPLICATE_EFFICACY": "효능 중복",
    "DOSAGE_CAUTION": "용량 주의",
    "DURATION_CAUTION": "복용기간 주의",
    "ELDERLY_CAUTION": "고령자 주의",
    "PREGNANCY_CAUTION": "임부 주의",
    "LACTATION_CAUTION": "수유 주의",
    "AGE_CONTRAINDICATION": "연령 주의",
    "MATCHING_REVIEW": "약 정보 확인",
}


@dataclass(frozen=True)
class ReportTextBundle:
    caregiver_summary: str
    pharmacist_summary: str
    caregiver_detail: str
    pharmacist_detail: str
    source: str
    model: str | None
    recommended_questions: list[str] = field(default_factory=list)
    alert_explanations: list[dict[str, Any]] = field(default_factory=list)
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
    alert_explanations = [_template_alert_explanation(alert) for alert in alerts]
    recommended_questions = _template_recommended_questions(alert_explanations)
    caregiver_detail = _template_caregiver_detail(
        patient,
        risk_count,
        caution_count,
        normal_count,
        alert_explanations,
        recommended_questions,
    )
    pharmacist_summary = _template_pharmacist_summary(
        patient,
        alerts,
        risk_count,
        caution_count,
        normal_count,
        analysis_source=analysis_source,
    )
    pharmacist_detail = _template_pharmacist_detail(
        patient,
        risk_count,
        caution_count,
        normal_count,
        alert_explanations,
        analysis_source=analysis_source,
    )
    model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    provider = os.getenv("LLM_SUMMARY_PROVIDER", "template").lower()
    if provider != "openai" or not os.getenv("OPENAI_API_KEY"):
        return ReportTextBundle(
            caregiver_summary=caregiver_summary,
            pharmacist_summary=pharmacist_summary,
            caregiver_detail=caregiver_detail,
            pharmacist_detail=pharmacist_detail,
            source="TEMPLATE",
            model=None,
            recommended_questions=recommended_questions,
            alert_explanations=alert_explanations,
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
            caregiver_detail=caregiver_detail,
            pharmacist_detail=pharmacist_detail,
            recommended_questions=recommended_questions,
            alert_explanations=alert_explanations,
            model=model,
            analysis_source=analysis_source,
        )
        elapsed_ms = round((time.perf_counter() - started_at) * 1000)
        logger.info("ai_summary_source=OPENAI prompt_version=%s model=%s duration_ms=%s", PROMPT_VERSION, model, elapsed_ms)
        return ReportTextBundle(
            caregiver_summary=polished["caregiverSummaryText"],
            pharmacist_summary=polished["pharmacistSummaryText"],
            caregiver_detail=polished["caregiverDetailText"],
            pharmacist_detail=polished["pharmacistDetailText"],
            source="OPENAI",
            model=model,
            recommended_questions=polished["recommendedQuestions"],
            alert_explanations=polished["alertExplanations"],
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
            caregiver_detail=caregiver_detail,
            pharmacist_detail=pharmacist_detail,
            source="TEMPLATE",
            model=None,
            recommended_questions=recommended_questions,
            alert_explanations=alert_explanations,
        )


def _template_caregiver_summary(patient, alerts, risk_count: int, caution_count: int, normal_count: int) -> str:
    alias = _patient_name(patient)
    total = risk_count + caution_count
    if total == 0:
        return (
            f"{alias}님의 복용 약에서는 현재 등재된 위험·주의 알림이 확인되지 않았습니다. "
            f"특별한 문제로 표시되지 않은 약은 {normal_count}개입니다. 새 약이 추가되거나 증상이 달라지면 "
            "현재 약 목록을 약사·의사에게 보여주고 다시 확인하세요."
        )

    priority_alert_groups = _priority_alert_groups(alerts, limit=3)
    parts = [
        f"{alias}님의 복용 약에서 위험 {risk_count}건, 주의 {caution_count}건이 확인되었습니다.",
    ]
    if normal_count:
        parts.append(f"특별한 문제로 표시되지 않은 약은 {normal_count}개입니다.")

    if priority_alert_groups:
        alert_summaries = [_caregiver_alert_summary(alert, count=count) for alert, count in priority_alert_groups]
        covered_count = sum(count for _, count in priority_alert_groups)
        remaining = max(0, total - covered_count)
        focus_text = " ".join(summary for summary in alert_summaries if summary)
        if remaining:
            focus_text += f" 그 외 확인 항목 {remaining}건은 알림 목록에서 함께 확인해주세요."
        parts.append(focus_text)

    pim_alert = next(
        (a for a in alerts if _rule_type_value(a) == "ELDERLY_CAUTION" and getattr(a, "related_medications", None)),
        None,
    )
    if pim_alert:
        parts.append(
            "'고령자 주의'는 어르신에게 특히 조심할 약이라는 뜻입니다. "
            "졸림, 어지럼, 비틀거림, 혼동, 낙상 여부를 관찰해 상담 때 전달하세요."
        )

    parts.append("복용을 임의로 중단하거나 조절하지 말고, 현재 약 목록과 이 결과를 약사·의사에게 보여주고 상담하세요.")
    return " ".join(part for part in parts if part).strip()


def _template_caregiver_detail(
    patient,
    risk_count: int,
    caution_count: int,
    normal_count: int,
    alert_explanations: list[dict[str, Any]],
    recommended_questions: list[str],
) -> str:
    alias = _patient_name(patient)
    total = risk_count + caution_count
    if total == 0:
        return (
            f"{alias}님의 현재 복용 목록에서는 등재된 위험·주의 알림이 확인되지 않았습니다.\n"
            f"다만 새 약이 추가되거나 복용량·복용 기간이 바뀌면 결과가 달라질 수 있습니다.\n"
            "새로운 증상이나 복용 변경이 있으면 약사·의사에게 현재 약 목록을 보여주고 다시 확인하세요."
        )

    lines = [
        f"{alias}님의 복용 목록에서 위험 {risk_count}건, 주의 {caution_count}건이 확인되었습니다.",
        f"별도 알림이 없는 약은 {normal_count}개입니다.",
        "아래 내용은 복용을 임의로 바꾸기 위한 지시가 아니라, 상담 때 확인할 항목을 정리한 것입니다.",
        "",
    ]
    for index, explanation in enumerate(alert_explanations, start=1):
        related = ", ".join(explanation["relatedMedications"]) or "관련 약물"
        lines.extend(
            [
                f"{index}. {explanation['title']} - {related}",
                f"   이유: {explanation['plainLanguageReason']}",
                f"   보호자 확인: {explanation['caregiverAction']}",
                f"   상담 질문: {explanation['professionalQuestion']}",
            ]
        )
    if recommended_questions:
        lines.extend(["", "상담 전에 메모하면 좋은 질문:"])
        lines.extend(f"- {question}" for question in recommended_questions[:5])
    return "\n".join(lines)


def _template_alert_explanation(alert) -> dict[str, Any]:
    severity = _severity_value(alert)
    rule_type = _rule_type_value(alert)
    related = list(getattr(alert, "related_medications", []) or [])
    related_text = ", ".join(related) or "관련 약물"
    message = str(getattr(alert, "message", "") or "").strip()
    title = str(getattr(alert, "title", "") or rule_type).strip()
    reason = _plain_language_reason(rule_type, severity, related_text, message)
    action = _caregiver_action(rule_type, severity, related_text)
    question = _professional_question(rule_type, severity, related_text, message)
    return {
        "alertId": str(getattr(alert, "alert_id", "") or ""),
        "severity": severity,
        "ruleType": rule_type,
        "title": title,
        "relatedMedications": related,
        "plainLanguageReason": reason,
        "caregiverAction": action,
        "professionalQuestion": question,
        "evidenceSummary": _evidence_summary(alert),
    }


def _template_recommended_questions(alert_explanations: list[dict[str, Any]]) -> list[str]:
    questions: list[str] = []
    for explanation in alert_explanations:
        question = str(explanation.get("professionalQuestion") or "").strip()
        if question and question not in questions:
            questions.append(question)
    general = "현재 복용 중인 모든 약과 복용량, 복용 기간을 함께 보여드리면 추가 확인이 필요한가요?"
    if general not in questions:
        questions.append(general)
    return questions[:6]


def _plain_language_reason(rule_type: str, severity: str, related_text: str, message: str) -> str:
    severity_label = "위험" if severity == "RISK" else "주의"
    if rule_type in {"PRODUCT_INTERACTION", "INGREDIENT_INTERACTION"}:
        return (
            f"{related_text} 조합에서 {severity_label} 알림이 확인되었습니다. "
            f"DUR 근거 메시지는 '{message or '상호작용 가능성'}'입니다. "
            "두 약을 같은 기간에 복용할 때 전문가 확인이 필요합니다."
        )
    if rule_type == "DOSAGE_CAUTION":
        return (
            f"{related_text}의 입력된 복용량이 기준을 초과할 수 있다는 주의 알림입니다. "
            f"근거 메시지는 '{message or '용량 확인 필요'}'입니다."
        )
    if rule_type == "DURATION_CAUTION":
        return (
            f"{related_text}의 복용 기간이 기준보다 길 수 있다는 주의 알림입니다. "
            f"근거 메시지는 '{message or '투여 기간 확인 필요'}'입니다."
        )
    if rule_type == "DUPLICATE_INGREDIENT":
        return f"{related_text}에 같은 성분이 겹칠 수 있어 중복 복용 여부를 확인해야 합니다."
    if rule_type == "DUPLICATE_EFFICACY":
        return f"{related_text}가 비슷한 효능군으로 함께 쓰이고 있어 중복 복용 가능성을 확인해야 합니다."
    if rule_type == "ELDERLY_CAUTION":
        return (
            f"{related_text}는 고령자에게 더 주의가 필요한 항목으로 표시되었습니다. "
            f"{message or '어지럼, 졸림, 낙상 등과 관련된 주의가 필요할 수 있습니다.'}"
        )
    if rule_type in {"PREGNANCY_CAUTION", "LACTATION_CAUTION", "AGE_CONTRAINDICATION"}:
        return f"{related_text}는 환자 상태나 연령 조건에 따라 전문가 확인이 필요한 항목입니다. {message}"
    return f"{related_text}에 대해 {severity_label} 알림이 확인되었습니다. {message}"


def _caregiver_action(rule_type: str, severity: str, related_text: str) -> str:
    if severity == "RISK":
        return (
            "복용을 임의로 중단하지 말고, 가능한 한 빨리 처방 병원이나 약국에 현재 약 목록과 이 알림을 보여주세요. "
            "근육통, 심한 어지럼, 호흡 불편, 의식 변화처럼 평소와 다른 증상이 있으면 즉시 상담하세요."
        )
    if rule_type in {"DOSAGE_CAUTION", "DURATION_CAUTION"}:
        return "실제 복용량과 복용 기간이 입력값과 같은지 확인하고, 약 봉투나 처방전을 함께 가져가 상담하세요."
    if rule_type == "ELDERLY_CAUTION":
        return "졸림, 어지럼, 비틀거림, 혼동, 낙상 같은 변화가 있는지 관찰하고 상담 때 전달하세요."
    return f"{related_text}를 복용하는 동안 평소와 다른 증상이 있는지 기록하고 다음 상담 때 보여주세요."


def _professional_question(rule_type: str, severity: str, related_text: str, message: str) -> str:
    if rule_type in {"PRODUCT_INTERACTION", "INGREDIENT_INTERACTION"}:
        return f"{related_text}를 같은 기간에 함께 복용해도 되는지, 대체 약이나 복용 일정 조정이 필요한지 확인해주세요."
    if rule_type == "DOSAGE_CAUTION":
        return f"{related_text}의 하루 총 복용량이 현재 처방 의도와 맞는지 확인해주세요."
    if rule_type == "DURATION_CAUTION":
        return f"{related_text}의 복용 기간이 기준을 넘는 이유가 있는지 확인해주세요."
    if rule_type in {"DUPLICATE_INGREDIENT", "DUPLICATE_EFFICACY"}:
        return f"{related_text}가 중복 처방인지, 함께 복용해야 하는 치료 계획인지 확인해주세요."
    if rule_type == "ELDERLY_CAUTION":
        return f"{related_text}가 고령자에게 필요한 약인지, 졸림·낙상 위험을 줄일 방법이 있는지 확인해주세요."
    return f"{related_text}의 '{message or '주의 알림'}'에 대해 현재 복용을 유지해도 되는지 확인해주세요."


def _evidence_summary(alert) -> str:
    evidence_items = list(getattr(alert, "evidence", []) or [])
    if not evidence_items:
        return "확인 근거 정보가 응답에 포함되지 않았습니다."
    summaries = []
    for evidence in evidence_items[:2]:
        source_name = getattr(evidence, "source_name", "")
        description = getattr(evidence, "description", "")
        summaries.append(f"{source_name}: {description}".strip(": "))
    return " / ".join(summaries)


def _priority_alerts(alerts, limit: int) -> list[Any]:
    return [alert for alert, _count in _priority_alert_groups(alerts, limit)]


def _priority_alert_groups(alerts, limit: int) -> list[tuple[Any, int]]:
    sorted_alerts = sorted(
        list(alerts),
        key=lambda alert: (
            0 if _severity_value(alert) == "RISK" else 1,
            _rule_priority(_rule_type_value(alert)),
            str(getattr(alert, "title", "")),
        ),
    )
    groups: list[tuple[Any, int]] = []
    key_index: dict[tuple[str, str, tuple[str, ...]], int] = {}
    for alert in sorted_alerts:
        key = _alert_group_key(alert)
        if key in key_index:
            index = key_index[key]
            representative, count = groups[index]
            groups[index] = (representative, count + 1)
            continue
        if len(groups) >= limit:
            continue
        key_index[key] = len(groups)
        groups.append((alert, 1))
    return groups


def _alert_group_key(alert) -> tuple[str, str, tuple[str, ...]]:
    related_key = tuple(
        sorted(
            _normalize_summary_text(name)
            for name in (getattr(alert, "related_medications", []) or [])
            if str(name).strip()
        )
    )
    return (_severity_value(alert), _rule_type_value(alert), related_key)


def _rule_priority(rule_type: str) -> int:
    priorities = {
        "PRODUCT_INTERACTION": 0,
        "INGREDIENT_INTERACTION": 0,
        "DUPLICATE_INGREDIENT": 1,
        "DUPLICATE_EFFICACY": 2,
        "DOSAGE_CAUTION": 3,
        "DURATION_CAUTION": 4,
        "ELDERLY_CAUTION": 5,
    }
    return priorities.get(rule_type, 9)


def _caregiver_alert_summary(alert, *, count: int = 1) -> str:
    related = _compact_related_medications(getattr(alert, "related_medications", []) or [])
    severity_label = "위험" if _severity_value(alert) == "RISK" else "주의"
    rule_type = _rule_type_value(alert)
    label = _caregiver_rule_label(rule_type)
    if rule_type in {"PRODUCT_INTERACTION", "INGREDIENT_INTERACTION"}:
        basis_text = f" 관련 근거 {count}건으로 확인되었습니다." if count > 1 else " 확인되었습니다."
        return f"{label}({severity_label}): {related} 조합으로{basis_text} 같은 기간 복용 가능 여부를 먼저 확인하세요."
    if rule_type in {"DUPLICATE_INGREDIENT", "DUPLICATE_EFFICACY"}:
        return f"{label}({severity_label}): {related}는 중복 가능성이 있어 함께 복용해야 하는 처방인지 확인이 필요합니다."
    if rule_type in {"DOSAGE_CAUTION", "DURATION_CAUTION"}:
        return f"{label}({severity_label}): {related}는 입력된 용량이나 복용 기간이 기준과 맞는지 확인해야 합니다."
    if rule_type == "ELDERLY_CAUTION":
        return f"{label}({severity_label}): {related}는 어르신에게 특히 조심할 약으로 표시되었습니다."
    return f"{label}({severity_label}): {related}에 확인이 필요한 알림이 있습니다."


def _pharmacist_alert_summary(alert, *, count: int = 1) -> str:
    related = _compact_related_medications(getattr(alert, "related_medications", []) or [], limit=2)
    title = str(getattr(alert, "title", "") or _rule_type_value(alert)).strip()
    message = _truncate_text(str(getattr(alert, "message", "") or ""), limit=70)
    count_text = f" x{count}" if count > 1 else ""
    return f"{_severity_value(alert)}{count_text}/{_rule_type_value(alert)} {title}({related}) {message}".strip()


def _caregiver_rule_label(rule_type: str) -> str:
    return _CAREGIVER_RULE_LABELS.get(rule_type, "확인 필요")


def _compact_related_medications(medications: list[str], *, limit: int = 2) -> str:
    cleaned = [str(name).strip() for name in medications if str(name).strip()]
    if not cleaned:
        return "관련 약물"
    shown = cleaned[:limit]
    extra = len(cleaned) - len(shown)
    text = ", ".join(shown)
    return f"{text} 외 {extra}개" if extra > 0 else text


def _truncate_text(value: str, *, limit: int) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _normalize_summary_text(value: str) -> str:
    return " ".join(str(value).split()).lower()


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
    alert_groups = _priority_alert_groups(alerts, limit=3)
    alert_lines = [_pharmacist_alert_summary(alert, count=count) for alert, count in alert_groups]
    alert_text = " / ".join(line for line in alert_lines if line)
    if not alert_text:
        alert_text = "위험·주의 알림 없음"
    covered_count = sum(count for _, count in alert_groups)
    remaining = max(0, len(alerts) - covered_count)
    remaining_text = f" / 그 외 {remaining}건" if remaining else ""
    suffix = "" if alert_text.endswith((".", "!", "?")) else "."
    return (
        f"{alias} / {age_text} / {source_text}: RISK {risk_count}, CAUTION {caution_count}, "
        f"NORMAL {normal_count}. 확인 우선: {alert_text}{remaining_text}{suffix}"
    )


def _template_pharmacist_detail(
    patient,
    risk_count: int,
    caution_count: int,
    normal_count: int,
    alert_explanations: list[dict[str, Any]],
    *,
    analysis_source: str | None = None,
) -> str:
    alias = _patient_name(patient)
    age = getattr(patient, "age_years", None)
    age_text = f"{age}세" if age is not None else "나이 미입력"
    source_text = "Graph DB" if analysis_source == "GRAPH" else "룰 기반"
    lines = [
        f"{alias} / {age_text} / {source_text} 분석",
        f"요약: RISK {risk_count}건, CAUTION {caution_count}건, NORMAL {normal_count}건",
    ]
    if not alert_explanations:
        lines.append("현재 분석 기준에서 전문가 확인이 필요한 위험·주의 알림은 없습니다.")
        return "\n".join(lines)

    lines.append("알림별 확인 항목:")
    for index, explanation in enumerate(alert_explanations, start=1):
        related = ", ".join(explanation["relatedMedications"]) or "관련 약물"
        lines.extend(
            [
                f"{index}. [{explanation['severity']}/{explanation['ruleType']}] {explanation['title']}",
                f"   관련 약물: {related}",
                f"   메시지: {explanation['plainLanguageReason']}",
                f"   근거: {explanation['evidenceSummary']}",
                f"   확인 질문: {explanation['professionalQuestion']}",
            ]
        )
    return "\n".join(lines)


def _polish_with_openai(
    *,
    patient,
    alerts,
    risk_count: int,
    caution_count: int,
    normal_count: int,
    caregiver_summary: str,
    pharmacist_summary: str,
    caregiver_detail: str,
    pharmacist_detail: str,
    recommended_questions: list[str],
    alert_explanations: list[dict[str, Any]],
    model: str,
    analysis_source: str | None,
) -> dict[str, Any]:
    from openai import OpenAI

    client = maybe_wrap_openai_client(
        OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "8")))
    )
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
            "caregiverDetailText": caregiver_detail,
            "pharmacistDetailText": pharmacist_detail,
            "recommendedQuestions": recommended_questions,
            "alertExplanations": alert_explanations,
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
                    "caregiverSummaryText는 500자 이내 압축 요약으로 작성하고, 위험·주의 개수, "
                    "우선 확인 항목 최대 3개, 보호자 행동만 포함한다. "
                    "pharmacistSummaryText는 450자 이내 전문 메모로 작성한다. "
                    "반환 키는 caregiverSummaryText, pharmacistSummaryText, caregiverDetailText, "
                    "pharmacistDetailText, recommendedQuestions, alertExplanations만 사용한다. "
                    "alertExplanations는 입력된 alertId 개수와 값을 그대로 유지하고 설명 문장만 다듬는다."
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
    caregiver_detail_out = str(data.get("caregiverDetailText") or "").strip()
    pharmacist_detail_out = str(data.get("pharmacistDetailText") or "").strip()
    questions = _coerce_questions(data.get("recommendedQuestions"), recommended_questions)
    explanations = _coerce_alert_explanations(data.get("alertExplanations"), alert_explanations)
    if not caregiver or not pharmacist or not caregiver_detail_out or not pharmacist_detail_out:
        raise ValueError("OpenAI response missing required summary fields.")
    return {
        "caregiverSummaryText": caregiver,
        "pharmacistSummaryText": pharmacist,
        "caregiverDetailText": caregiver_detail_out,
        "pharmacistDetailText": pharmacist_detail_out,
        "recommendedQuestions": questions,
        "alertExplanations": explanations,
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
        "alertId": getattr(alert, "alert_id", ""),
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


def _coerce_questions(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback

    questions: list[str] = []
    for item in value:
        question = str(item or "").strip()
        if question and question not in questions:
            questions.append(question)
    return questions[:6] or fallback


def _coerce_alert_explanations(
    value: Any,
    fallback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback

    candidate_by_id = {
        str(item.get("alertId") or ""): item
        for item in value
        if isinstance(item, dict)
    }
    result: list[dict[str, Any]] = []
    for template in fallback:
        alert_id = str(template.get("alertId") or "")
        candidate = candidate_by_id.get(alert_id)
        if not isinstance(candidate, dict):
            result.append(template)
            continue

        result.append(
            {
                "alertId": alert_id,
                "severity": template.get("severity"),
                "ruleType": template.get("ruleType"),
                "title": template.get("title"),
                "relatedMedications": list(template.get("relatedMedications") or []),
                "plainLanguageReason": _coerce_text(
                    candidate.get("plainLanguageReason"),
                    template.get("plainLanguageReason"),
                ),
                "caregiverAction": _coerce_text(
                    candidate.get("caregiverAction"),
                    template.get("caregiverAction"),
                ),
                "professionalQuestion": _coerce_text(
                    candidate.get("professionalQuestion"),
                    template.get("professionalQuestion"),
                ),
                "evidenceSummary": _coerce_text(
                    candidate.get("evidenceSummary"),
                    template.get("evidenceSummary"),
                ),
            }
        )

    return result or fallback


def _coerce_text(value: Any, fallback: Any) -> str:
    text = str(value or "").strip()
    return text or str(fallback or "").strip()
