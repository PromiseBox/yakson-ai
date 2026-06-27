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

import os

PIM_SOURCE_NAME = "노인 부적절약물(PIM) 잠정 기준 — 약사 감수 필요"
ELDERLY_AGE = 65

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
    alias = getattr(patient, "display_name", None) or "어르신"
    total = risk_count + caution_count
    if total == 0:
        text = (f"{alias} 복용 약을 점검한 결과, 지금 등재된 위험·주의는 발견되지 않았습니다. "
                f"새로운 증상이 있으면 약사·의사와 상의하세요.")
    else:
        text = f"{alias} 복용 약을 점검한 결과, 확인이 필요한 항목 {total}건이 발견됐어요."
        if risk_count:
            text += f" 이 중 {risk_count}건은 지금 약사·의사 확인이 필요합니다."
        # 가치포인트: 노인주의(낙상) 맥락 한 마디 — alerts의 사실에 기반(새 주장 아님).
        pim_alert = next(
            (a for a in alerts
             if getattr(a, "rule_type", None) == "ELDERLY_CAUTION" and getattr(a, "related_medications", None)),
            None,
        )
        if pim_alert:
            text += f" 특히 {pim_alert.related_medications[0]} 등은 어르신에게 낙상·인지 주의가 필요합니다."
        text += " 처방·복용 변경은 직접 판단하지 말고 약사·의사와 상의하세요."
    return _maybe_polish(text)


def _maybe_polish(text: str) -> str:
    """opt-in: LLM_SUMMARY_PROVIDER=openai + 키 설정 시 GPT로 톤만 다듬기. 실패/미설정 시 원문(안전)."""
    if os.getenv("LLM_SUMMARY_PROVIDER", "template").lower() != "openai" or not os.getenv("OPENAI_API_KEY"):
        return text
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5.5"),
            messages=[
                {"role": "system", "content": (
                    "보호자용 약물안전 요약을 더 따뜻하고 쉽게 다듬어라. 새로운 약·위험·수치·진단을 "
                    "절대 추가하지 말고 사실은 그대로. 중단/감량/처방 같은 단정 대신 '약사·의사와 상의'로 "
                    "마무리. 한 단락.")},
                {"role": "user", "content": text},
            ],
        )
        out = (resp.choices[0].message.content or "").strip()
        return out or text
    except Exception:
        return text
