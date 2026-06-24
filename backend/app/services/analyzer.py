from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models import (
    AlertEvidence,
    AlertSeverity,
    AnalysisAlert,
    AnalysisReport,
    AnalyzeRequest,
    DrugSearchItem,
    DrugSearchResponse,
    MatchStatus,
    MedicationResult,
    ReportSummary,
    RuleType,
)


KST = timezone(timedelta(hours=9))

DRUG_CATALOG = [
    {
        "productCode": "DEMO-ASPIRIN-100",
        "itemSeq": "DEMO-ITEM-ASPIRIN",
        "productName": "아스피린 100mg",
        "companyName": "Demo Pharma",
        "ingredientNames": ["Aspirin"],
        "aliases": ["아스피린", "aspirin"],
    },
    {
        "productCode": "DEMO-CLOPIDOGREL-75",
        "itemSeq": "DEMO-ITEM-CLOPIDOGREL",
        "productName": "클로피도그렐 75mg",
        "companyName": "Demo Pharma",
        "ingredientNames": ["Clopidogrel"],
        "aliases": ["클로피도그렐", "clopidogrel", "플라빅스"],
    },
    {
        "productCode": "DEMO-ZOLPIDEM-10",
        "itemSeq": "DEMO-ITEM-ZOLPIDEM",
        "productName": "졸피뎀 10mg",
        "companyName": "Demo Pharma",
        "ingredientNames": ["Zolpidem"],
        "aliases": ["졸피뎀", "zolpidem"],
    },
    {
        "productCode": "DEMO-METFORMIN-500",
        "itemSeq": "DEMO-ITEM-METFORMIN",
        "productName": "메트포르민 500mg",
        "companyName": "Demo Pharma",
        "ingredientNames": ["Metformin"],
        "aliases": ["메트포르민", "metformin"],
    },
    {
        "productCode": "DEMO-GLIMEPIRIDE-2",
        "itemSeq": "DEMO-ITEM-GLIMEPIRIDE",
        "productName": "글리메피리드 2mg",
        "companyName": "Demo Pharma",
        "ingredientNames": ["Glimepiride"],
        "aliases": ["글리메피리드", "glimepiride"],
    },
]


REPORT_STORE: dict[str, AnalysisReport] = {}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"


def _normalize(text: str) -> str:
    return text.strip().lower().replace(" ", "")


def _match_drug(entered_name: str) -> dict | None:
    normalized = _normalize(entered_name)
    for drug in DRUG_CATALOG:
        for alias in drug["aliases"]:
            if _normalize(alias) in normalized or normalized in _normalize(alias):
                return drug
    return None


def search_drugs(query: str) -> DrugSearchResponse:
    normalized = _normalize(query)
    matches: list[DrugSearchItem] = []

    if not normalized:
        return DrugSearchResponse(items=[])

    for drug in DRUG_CATALOG:
        aliases = [_normalize(alias) for alias in drug["aliases"]]
        product_name = _normalize(drug["productName"])
        if any(normalized in alias or alias in normalized for alias in aliases) or normalized in product_name:
            matches.append(
                DrugSearchItem(
                    productCode=drug["productCode"],
                    itemSeq=drug["itemSeq"],
                    productName=drug["productName"],
                    companyName=drug["companyName"],
                    ingredientNames=drug["ingredientNames"],
                    matchScore=0.98,
                )
            )

    return DrugSearchResponse(items=matches[:8])


def analyze_medications(payload: AnalyzeRequest) -> AnalysisReport:
    medication_results: list[MedicationResult] = []
    matched_names: list[str] = []
    normalized_matches: set[str] = set()

    for medication in payload.medications:
        drug = _match_drug(medication.entered_drug_name)
        if drug:
            matched_name = drug["productName"]
            matched_names.append(matched_name)
            normalized_matches.add(_normalize(matched_name))
            medication_results.append(
                MedicationResult(
                    enteredDrugName=medication.entered_drug_name,
                    matchedProductName=matched_name,
                    matchStatus=MatchStatus.MATCHED,
                )
            )
        else:
            medication_results.append(
                MedicationResult(
                    enteredDrugName=medication.entered_drug_name,
                    matchedProductName=None,
                    matchStatus=MatchStatus.UNMATCHED,
                )
            )

    alerts = _build_mock_alerts(payload, matched_names, normalized_matches, medication_results)
    alerted_medications = {
        _normalize(name)
        for alert in alerts
        for name in alert.related_medications
    }
    unmatched_count = sum(1 for item in medication_results if item.match_status == MatchStatus.UNMATCHED)
    normal_count = sum(
        1
        for item in medication_results
        if item.match_status == MatchStatus.MATCHED
        and item.matched_product_name
        and _normalize(item.matched_product_name) not in alerted_medications
    )

    report = AnalysisReport(
        reportId=_new_id("rep"),
        generatedAt=datetime.now(KST).isoformat(),
        patient=payload.patient,
        summary=ReportSummary(
            riskCount=sum(1 for alert in alerts if alert.severity == AlertSeverity.RISK),
            cautionCount=sum(1 for alert in alerts if alert.severity == AlertSeverity.CAUTION),
            normalCount=normal_count,
            unmatchedMedicationCount=unmatched_count,
        ),
        medications=medication_results,
        alerts=alerts,
        caregiverGuidance=(
            "이 리포트는 진단이나 처방이 아닌 복약 안전 참고자료입니다. "
            "위험 항목은 약사 또는 의사에게 상담해 주세요."
        ),
        pharmacistHandoffText=_build_handoff_text(payload, medication_results, alerts),
    )
    REPORT_STORE[report.report_id] = report
    return report


def get_report(report_id: str) -> AnalysisReport | None:
    if report_id == "demo-latest":
        return analyze_medications(
            AnalyzeRequest(
                patient={"displayName": "홍길순 할머니", "ageYears": 78, "sex": "FEMALE"},
                medications=[
                    {"enteredDrugName": "아스피린 100mg"},
                    {"enteredDrugName": "클로피도그렐"},
                    {"enteredDrugName": "졸피뎀 10mg"},
                    {"enteredDrugName": "메트포르민 500mg"},
                    {"enteredDrugName": "글리메피리드"},
                ],
            )
        )
    return REPORT_STORE.get(report_id)


def _build_mock_alerts(
    payload: AnalyzeRequest,
    matched_names: list[str],
    normalized_matches: set[str],
    medication_results: list[MedicationResult],
) -> list[AnalysisAlert]:
    alerts: list[AnalysisAlert] = []

    has_aspirin = any("아스피린" in name or "aspirin" in name.lower() for name in matched_names)
    has_clopidogrel = any("클로피도그렐" in name or "clopidogrel" in name.lower() for name in matched_names)
    has_zolpidem = any("졸피뎀" in name or "zolpidem" in name.lower() for name in matched_names)
    has_metformin = any("메트포르민" in name or "metformin" in name.lower() for name in matched_names)
    has_glimepiride = any("글리메피리드" in name or "glimepiride" in name.lower() for name in matched_names)

    if has_zolpidem and (payload.patient.age_years or 0) >= 65:
        alerts.append(
            AnalysisAlert(
                alertId=_new_id("alt"),
                severity=AlertSeverity.RISK,
                ruleType=RuleType.ELDERLY_CAUTION,
                title="노인 부적절 약물(PIM)",
                message="졸피뎀은 어르신에게 낙상과 섬망 위험을 높일 수 있어 약사 상담을 권장해요.",
                relatedMedications=["졸피뎀 10mg"],
                evidence=[
                    _evidence(
                        "식약처 DUR 노인주의",
                        "product_safety_rule:demo-zolpidem-elderly",
                        "노인주의 제품 안전성 규칙",
                    )
                ],
                routeToProfessional=True,
            )
        )

    if has_aspirin and has_clopidogrel:
        alerts.append(
            AnalysisAlert(
                alertId=_new_id("alt"),
                severity=AlertSeverity.RISK,
                ruleType=RuleType.PRODUCT_INTERACTION,
                title="병용금기/주의",
                message="두 약을 함께 복용하면 출혈 위험이 높아질 수 있어 복용 목적과 기간을 확인해야 해요.",
                relatedMedications=["아스피린 100mg", "클로피도그렐 75mg"],
                evidence=[
                    _evidence(
                        "식약처 DUR 병용금기",
                        "product_interaction_rule:demo-aspirin-clopidogrel",
                        "제품 병용 주의 규칙",
                    )
                ],
                routeToProfessional=True,
            )
        )

    if has_metformin and has_glimepiride:
        alerts.append(
            AnalysisAlert(
                alertId=_new_id("alt"),
                severity=AlertSeverity.CAUTION,
                ruleType=RuleType.DUPLICATE_EFFICACY,
                title="동일 효능 중복",
                message="비슷한 혈당 조절 목적의 약이 함께 있어 저혈당 증상 여부를 확인하면 좋아요.",
                relatedMedications=["메트포르민 500mg", "글리메피리드 2mg"],
                evidence=[
                    _evidence(
                        "효능군 중복 점검",
                        "efficacy_group_member:demo-diabetes",
                        "효능군 기반 중복 규칙",
                    )
                ],
                routeToProfessional=False,
            )
        )

    for item in medication_results:
        if item.match_status == MatchStatus.UNMATCHED:
            alerts.append(
                AnalysisAlert(
                    alertId=_new_id("alt"),
                    severity=AlertSeverity.CAUTION,
                    ruleType=RuleType.MATCHING_REVIEW,
                    title="약물명 확인 필요",
                    message="입력한 약을 공식 약물 마스터와 매칭하지 못했어요. 약봉투나 처방전의 정확한 이름을 확인해 주세요.",
                    relatedMedications=[item.entered_drug_name],
                    evidence=[
                        _evidence(
                            "약물 마스터 매칭",
                            "drug_match:unmatched",
                            "제품코드 매칭 실패",
                        )
                    ],
                    routeToProfessional=False,
                )
            )

    return alerts


def _evidence(source_name: str, source_record_id: str, description: str) -> AlertEvidence:
    return AlertEvidence(
        sourceType="DUR",
        sourceName=source_name,
        sourceRecordId=source_record_id,
        description=description,
    )


def _build_handoff_text(
    payload: AnalyzeRequest,
    medication_results: list[MedicationResult],
    alerts: list[AnalysisAlert],
) -> str:
    risk_count = sum(1 for alert in alerts if alert.severity == AlertSeverity.RISK)
    caution_count = sum(1 for alert in alerts if alert.severity == AlertSeverity.CAUTION)
    medication_names = ", ".join(item.entered_drug_name for item in medication_results)
    return (
        f"{payload.patient.display_name} / "
        f"{payload.patient.age_years or '나이 미입력'}세 / "
        f"입력 약물 {len(medication_results)}개({medication_names}) / "
        f"위험 {risk_count}건, 주의 {caution_count}건"
    )
