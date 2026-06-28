"""
노인 부적절약물(PIM) 큐레이션 보강 레이어.

[왜 필요한가 — 면밀 검토 결과]
식약처 노인주의 DUR(product_safety_rule.ELDERLY_CAUTION)은 일부 약만 잡는다.
실측: 졸피뎀(졸피움정)·알프라졸람(한림)은 product·ingredient 둘 다 ELDERLY_CAUTION 미수록
(빅손정만 product에 수록). 즉 '노인주의 누락'은 쿼리 갭이 아니라 **식약처 목록 커버리지 한계**다.
→ 국제 PIM 기준(Beers 등)에서 고령 부적절로 보는 계열을 '잠정 노인주의'로 보강한다.

[안전 설계]
- 출처를 식약처와 **명확히 구분**: provider="노인 부적절약물(PIM) 잠정 기준 — 약사 감수 필요".
- 심각도는 **보수적으로 '주의'(중)** 기본. 약사 감수 후 '위험'(상) 상향 가능(_PIM_SEVERITY).
- 임상 문구는 LLM이 생성하지 않고 **여기(출처 있는 사실)에서 reason으로 공급** → LLM은 재서술만.

⚠️ 아래 목록·문구는 **DRAFT**이며 약사·약학 **감수가 전제**입니다. 운영 전 검수 필요.
"""
from __future__ import annotations

from domain.models import Conflict, FlagType, PatientProfile, Severity, Source

_EXPERT = "최종 판단이 아닙니다. 약사·의사에게 이 약을 확인하세요."
_SOURCE = Source(
    provider="노인 부적절약물(PIM) 잠정 기준 — 약사 감수 필요",
    operation="pim_curated_draft",
)
# 약사 감수 후 Severity.HIGH 로 상향 가능. 미검수 상태의 기본은 보수적 '주의'.
_PIM_SEVERITY = Severity.MEDIUM

# 카테고리 → {성분 키워드(약명에 포함되면 매칭), 보호자용 임상 맥락[DRAFT]}
_PIM: dict[str, dict] = {
    "벤조디아제핀계": {
        "keywords": ["트리아졸람", "알프라졸람", "디아제팜", "로라제팜", "클로나제팜",
                     "에틸로플라제페이트", "플루라제팜", "브로마제팜", "클로르디아제폭시드"],
        "context": "벤조디아제핀계는 고령자에서 졸림·어지럼으로 낙상·골절·인지저하·의존 위험이 커질 수 있습니다.",
    },
    "Z-drug": {
        "keywords": ["졸피뎀", "조피클론", "잘레플론", "에스조피클론"],
        "context": "Z-drug(수면유도제)는 고령자에서 낙상·인지저하·의존 위험이 보고됩니다.",
    },
    "1세대 항히스타민": {
        "keywords": ["클로르페니라민", "디펜히드라민", "하이드록시진", "트리프롤리딘", "사이프로헵타딘"],
        "context": "1세대 항히스타민은 고령자에서 졸림·입마름·배뇨곤란·혼동 위험을 높일 수 있습니다.",
    },
}


def _match_category(drug_name: str) -> str | None:
    n = drug_name or ""
    for cat, spec in _PIM.items():
        if any(kw in n for kw in spec["keywords"]):
            return cat
    return None


def elderly_pim_conflicts(
    profile: PatientProfile, existing: list[Conflict] | None = None
) -> list[Conflict]:
    """고령(>=65) 환자의 약 중 PIM 해당분을 '노인주의'로 보강(식약처 중복분 제외).

    임상 맥락을 출처 있는 reason 으로 담는다 → 기존 narration/audit 가 그대로 처리.
    """
    if not profile.is_elderly:
        return []
    # 이미 노인주의가 잡힌 약(식약처)과 중복 방지
    already = {
        d for c in (existing or []) if c.flag_type == FlagType.ODSN_ATENT for d in c.drugs
    }
    out: list[Conflict] = []
    for d in profile.drugs:
        if d.name in already:
            continue
        cat = _match_category(d.name)
        if not cat:
            continue
        out.append(Conflict(
            flag_type=FlagType.ODSN_ATENT,
            severity=_PIM_SEVERITY,
            drugs=[d.name],
            reason=f"{_PIM[cat]['context']} (분류: {cat})",
            recommendation=_EXPERT,
            source=_SOURCE,
            tags=["치매·낙상 위험"],
        ))
        already.add(d.name)
    return out
