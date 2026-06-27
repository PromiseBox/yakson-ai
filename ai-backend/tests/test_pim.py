"""노인 PIM 보강(C) + PR#4 요약 포맷(B) 회귀 테스트.

식약처가 놓친 PIM(벤조/Z-drug/1세대 항히스타민)을 고령 환자에게 '노인주의'로 보강하고,
출처를 식약처와 구분하며, 비고령엔 적용 안 함. build_report→PR#4 summary 변환까지 확인.
"""
from __future__ import annotations

from agents import pim
from agents.assemble import build_report
from domain.models import Conflict, Drug, FlagType, PatientProfile, Severity, Source
from domain.report import to_analysis_summary


def _profile(age: int, names: list[str]) -> PatientProfile:
    p = PatientProfile(profile_id="t", alias="아버지", age=age)
    for i, n in enumerate(names):
        p.drugs.append(Drug(item_seq=str(1000 + i), name=n))
    return p


def test_pim_elderly_benzo_flagged():
    p = _profile(72, ["트리람정0.125밀리그램(트리아졸람)", "가나텍정(이토프리드염산염)"])
    cs = pim.elderly_pim_conflicts(p)
    assert len(cs) == 1  # 벤조계 1건만(이토프리드는 PIM 아님)
    c = cs[0]
    assert c.flag_type == FlagType.ODSN_ATENT
    assert "트리람정" in c.drugs[0]
    assert "치매·낙상 위험" in c.tags
    assert "PIM" in c.source.provider          # 출처가 식약처와 구분됨(약사감수 표기)
    assert c.severity == Severity.MEDIUM        # 미검수 기본은 보수적 '주의'


def test_pim_zdrug_and_first_gen_antihistamine():
    p = _profile(76, ["졸피움정(졸피뎀타르타르산염)", "페니라민정(클로르페니라민)"])
    cats = {pim._match_category(d.name) for d in p.drugs}
    assert cats == {"Z-drug", "1세대 항히스타민"}
    assert len(pim.elderly_pim_conflicts(p)) == 2


def test_pim_not_elderly_skip():
    p = _profile(40, ["트리람정0.125밀리그램(트리아졸람)"])
    assert pim.elderly_pim_conflicts(p) == []


def test_pim_dedup_with_existing_elderly():
    p = _profile(72, ["트리람정0.125밀리그램(트리아졸람)"])
    existing = [Conflict(
        flag_type=FlagType.ODSN_ATENT, severity=Severity.HIGH,
        drugs=["트리람정0.125밀리그램(트리아졸람)"], reason="식약처 노인주의",
        recommendation="확인", source=Source(operation="product_safety_rule"),
    )]
    assert pim.elderly_pim_conflicts(p, existing) == []  # 식약처가 이미 잡음 → 중복 안 함


def test_build_report_includes_pim_and_pr4_summary():
    p = _profile(72, ["트리람정0.125밀리그램(트리아졸람)", "가나텍정(이토프리드염산염)"])
    rep = build_report({"profile": p, "conflicts": [], "needs_pharmacist": False})
    # PIM 노인주의가 리포트에 반영됨 + audit 통과(서술이 출처 reason 기반)
    assert any(it.flag_type == FlagType.ODSN_ATENT for it in rep.items)
    assert rep.counts["주의"] >= 1
    assert rep.eval_report["report_audit"]["passed"] is True
    # PR#4 포맷 변환
    out = to_analysis_summary(rep, unmatched_count=0)
    assert set(out["summary"]) == {
        "riskCount", "cautionCount", "normalCount", "unmatchedMedicationCount", "description"
    }
    assert out["summary"]["description"] == rep.overall_message
    assert out["summary"]["cautionCount"] == rep.counts["주의"]
