from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.db_models import Patient, Prescription, PrescriptionMedication
from app.models import (
    AlertSeverity,
    AnalysisReport,
    AnalysisSource,
    AnalyzeRequest,
    MedicationInput,
    PatientInput,
    RuleType,
    Sex,
)
from app.services.graph_analyzer import analyze_medications_with_graph
from app.services.rule_preview import build_preview_report


def patient_payload(db: Session, patient_id: int) -> AnalyzeRequest:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise RuntimeError(f"Patient not found: {patient_id}")

    medications = db.scalars(
        select(PrescriptionMedication)
        .join(Prescription)
        .options(joinedload(PrescriptionMedication.prescription).joinedload(Prescription.category))
        .where(Prescription.patient_id == patient_id)
        .where(PrescriptionMedication.status == "ACTIVE")
        .order_by(Prescription.created_at.desc(), PrescriptionMedication.prescription_medication_id.desc())
    ).all()

    if not medications:
        raise RuntimeError(f"Patient {patient_id} has no active medications.")

    return AnalyzeRequest(
        patient=PatientInput(displayName=patient.display_name, ageYears=patient.age_years, sex=Sex(patient.sex)),
        medications=[
            MedicationInput(
                enteredDrugName=medication.entered_drug_name,
                categoryName=medication.prescription.category.category_name,
                productCode=medication.product_code,
                itemSeq=medication.item_seq,
                durationDays=medication.duration_days,
                dosesPerDay=float(medication.doses_per_day),
                doseAmount=float(medication.dose_amount),
                doseUnit=medication.dose_unit,
            )
            for medication in medications
        ],
    )


def summary_dict(report: AnalysisReport) -> dict[str, Any]:
    return {
        "analysisSource": report.analysis_source.value,
        "riskCount": report.summary.risk_count,
        "cautionCount": report.summary.caution_count,
        "normalCount": report.summary.normal_count,
        "unmatchedMedicationCount": report.summary.unmatched_medication_count,
        "hasSummaryDescription": bool(report.summary.description),
        "hasCaregiverDetail": bool(report.caregiver_detail_text),
        "hasPharmacistDetail": bool(report.pharmacist_detail_text),
        "recommendedQuestionCount": len(report.recommended_questions),
        "alertExplanationCount": len(report.alert_explanations),
        "aiSummarySource": report.ai_summary_source,
    }


def assert_summary(
    label: str,
    report: AnalysisReport,
    *,
    source: AnalysisSource,
    risk: int,
    caution: int,
    normal: int,
) -> None:
    actual = {
        "analysisSource": report.analysis_source.value,
        "riskCount": report.summary.risk_count,
        "cautionCount": report.summary.caution_count,
        "normalCount": report.summary.normal_count,
        "unmatchedMedicationCount": report.summary.unmatched_medication_count,
    }
    expected = {
        "analysisSource": source.value,
        "riskCount": risk,
        "cautionCount": caution,
        "normalCount": normal,
        "unmatchedMedicationCount": 0,
    }
    if actual != expected:
        raise AssertionError(f"{label} summary mismatch. expected={expected} actual={actual}")


def assert_itra_simvastatin_graph_alerts(report: AnalysisReport, expected_count: int) -> None:
    alerts = [
        alert
        for alert in report.alerts
        if alert.severity == AlertSeverity.RISK
        and alert.rule_type == RuleType.INGREDIENT_INTERACTION
        and "이트라코나졸" in " ".join(alert.related_medications)
        and "심바스타틴" in " ".join(alert.related_medications)
    ]
    if len(alerts) != expected_count:
        raise AssertionError(
            "Itraconazole + simvastatin graph alert count mismatch. "
            f"expected={expected_count} actual={len(alerts)}"
        )


def assert_ai_report_texts(label: str, report: AnalysisReport) -> None:
    if not report.summary.description:
        raise AssertionError(f"{label} missing summary.description.")
    if not report.caregiver_summary_text:
        raise AssertionError(f"{label} missing caregiverSummaryText.")
    if not report.pharmacist_summary_text:
        raise AssertionError(f"{label} missing pharmacistSummaryText.")
    if not report.caregiver_detail_text:
        raise AssertionError(f"{label} missing caregiverDetailText.")
    if not report.pharmacist_detail_text:
        raise AssertionError(f"{label} missing pharmacistDetailText.")
    if len(report.recommended_questions) < 2:
        raise AssertionError(f"{label} recommendedQuestions too short: {report.recommended_questions}")
    if len(report.alert_explanations) != len(report.alerts):
        raise AssertionError(
            f"{label} alertExplanations count mismatch. "
            f"alerts={len(report.alerts)} explanations={len(report.alert_explanations)}"
        )
    if report.summary.description != report.caregiver_summary_text:
        raise AssertionError(f"{label} summary.description does not match caregiverSummaryText.")
    if report.ai_summary_source not in {"TEMPLATE", "OPENAI"}:
        raise AssertionError(f"{label} invalid aiSummarySource: {report.ai_summary_source}")
    if report.ai_prompt_version != "yakson-ai-report-v2":
        raise AssertionError(f"{label} invalid aiPromptVersion: {report.ai_prompt_version}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Yakson graph-first analysis regression cases.")
    parser.add_argument("--patient-id", type=int, default=22)
    parser.add_argument("--expect-graph-risk", type=int, default=2)
    parser.add_argument("--expect-graph-caution", type=int, default=1)
    parser.add_argument("--expect-graph-normal", type=int, default=3)
    parser.add_argument("--expect-rule-risk", type=int, default=1)
    parser.add_argument("--expect-rule-caution", type=int, default=1)
    parser.add_argument("--expect-rule-normal", type=int, default=3)
    parser.add_argument("--expect-itra-simvastatin-risk", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal() as db:
        payload = patient_payload(db, args.patient_id)
        graph_report = analyze_medications_with_graph(payload, db)
        rule_report = build_preview_report(payload, db)

    assert_summary(
        "Graph",
        graph_report,
        source=AnalysisSource.GRAPH,
        risk=args.expect_graph_risk,
        caution=args.expect_graph_caution,
        normal=args.expect_graph_normal,
    )
    assert_summary(
        "Rule preview",
        rule_report,
        source=AnalysisSource.RULE_PREVIEW,
        risk=args.expect_rule_risk,
        caution=args.expect_rule_caution,
        normal=args.expect_rule_normal,
    )
    assert_itra_simvastatin_graph_alerts(graph_report, args.expect_itra_simvastatin_risk)
    assert_ai_report_texts("Graph", graph_report)
    assert_ai_report_texts("Rule preview", rule_report)

    print(
        json.dumps(
            {
                "patientId": args.patient_id,
                "graph": summary_dict(graph_report),
                "rulePreview": summary_dict(rule_report),
                "status": "ok",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
