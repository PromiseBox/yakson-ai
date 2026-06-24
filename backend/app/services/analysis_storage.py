from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import DATABASE_SCHEMA
from app.models import (
    AlertEvidence,
    AlertSeverity,
    AnalysisAlert,
    AnalysisReport,
    AnalysisReportHistoryItem,
    AnalysisReportHistoryResponse,
    RuleType,
)


API_RULE_TYPE_TO_DB_RULE_TYPE = {
    RuleType.PRODUCT_INTERACTION: "CONTRAINDICATION_PAIR",
    RuleType.INGREDIENT_INTERACTION: "CONTRAINDICATION_PAIR",
    RuleType.DUPLICATE_INGREDIENT: "DUPLICATE_EFFICACY",
    RuleType.DUPLICATE_EFFICACY: "DUPLICATE_EFFICACY",
    RuleType.ELDERLY_CAUTION: "ELDERLY_CAUTION",
    RuleType.PREGNANCY_CAUTION: "PREGNANCY_CONTRAINDICATION",
    RuleType.LACTATION_CAUTION: "LACTATION_CAUTION",
    RuleType.AGE_CONTRAINDICATION: "AGE_CONTRAINDICATION",
    RuleType.DURATION_CAUTION: "DURATION_CAUTION",
    RuleType.DOSAGE_CAUTION: "DOSAGE_CAUTION",
    RuleType.MATCHING_REVIEW: "UNMATCHED_MEDICATION",
}


def _table(name: str) -> str:
    return f"{DATABASE_SCHEMA}.{name}" if DATABASE_SCHEMA else name


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _db_severity(severity: AlertSeverity) -> str:
    if severity == AlertSeverity.RISK:
        return "CRITICAL"
    if severity == AlertSeverity.CAUTION:
        return "WARNING"
    return "INFO"


def _db_rule_type(rule_type: RuleType) -> str:
    return API_RULE_TYPE_TO_DB_RULE_TYPE[rule_type]


def _snapshot_value(item: Any, alias: str, field_name: str) -> Any:
    if isinstance(item, dict):
        return item.get(alias, item.get(field_name))
    return getattr(item, field_name, None)


def _normalized_number(value: Any) -> str:
    if value is None:
        return ""
    try:
        text = format(Decimal(str(value)).normalize(), "f")
    except Exception:
        return str(value).strip()
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _snapshot_key(item: Any, include_category: bool) -> str:
    values = [
        str(_snapshot_value(item, "productCode", "product_code") or "").strip(),
        str(_snapshot_value(item, "itemSeq", "item_seq") or "").strip(),
    ]
    if include_category:
        values.append(str(_snapshot_value(item, "categoryName", "category_name") or "").strip())
    values.extend(
        [
            _normalized_number(_snapshot_value(item, "durationDays", "duration_days")),
            _normalized_number(_snapshot_value(item, "dosesPerDay", "doses_per_day")),
            _normalized_number(_snapshot_value(item, "doseAmount", "dose_amount")),
            str(_snapshot_value(item, "doseUnit", "dose_unit") or "").strip(),
        ]
    )
    return "|".join(values)


def _snapshot_has_category(snapshot: list[Any]) -> bool:
    return any(_snapshot_value(item, "categoryName", "category_name") for item in snapshot)


def _snapshot_keys(snapshot: list[Any], include_category: bool) -> list[str]:
    return sorted(_snapshot_key(item, include_category) for item in snapshot)


def _current_medication_snapshot(db: Session, patient_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            f"""
            select pm.entered_drug_name,
                   pc.category_name,
                   pm.product_code,
                   pm.item_seq,
                   pm.duration_days,
                   pm.doses_per_day,
                   pm.dose_amount,
                   pm.dose_unit
            from {_table("prescription_medication")} pm
            join {_table("prescription")} p on p.prescription_id = pm.prescription_id
            join {_table("prescription_category")} pc on pc.prescription_category_id = p.prescription_category_id
            where p.patient_id = :patient_id
              and pm.status = 'ACTIVE'
            """
        ),
        {"patient_id": patient_id},
    ).mappings().all()

    return [
        {
            "enteredDrugName": row["entered_drug_name"],
            "categoryName": row["category_name"],
            "productCode": row["product_code"],
            "itemSeq": row["item_seq"],
            "durationDays": row["duration_days"],
            "dosesPerDay": row["doses_per_day"],
            "doseAmount": row["dose_amount"],
            "doseUnit": row["dose_unit"],
        }
        for row in rows
    ]


def _is_stale_against_current(saved_snapshot: list[Any], current_snapshot: list[dict[str, Any]]) -> bool:
    include_category = _snapshot_has_category(saved_snapshot)
    return _snapshot_keys(saved_snapshot, include_category) != _snapshot_keys(current_snapshot, include_category)


def _report_with_stale_status(db: Session, patient_id: int, report: AnalysisReport) -> AnalysisReport:
    is_stale = _is_stale_against_current(report.source_medication_snapshot, _current_medication_snapshot(db, patient_id))
    return report.model_copy(update={"is_stale": is_stale})


def _reference_from_evidence(evidence: AlertEvidence) -> dict[str, object]:
    source_record_id = evidence.source_record_id
    prefix, _, raw_id = source_record_id.partition(":")
    reference_id = int(raw_id) if raw_id.isdigit() else None

    result: dict[str, object] = {
        "evidence_type": "OTHER",
        "product_safety_rule_id": None,
        "product_interaction_rule_id": None,
        "ingredient_safety_rule_id": None,
        "ingredient_interaction_rule_id": None,
        "external_trace_id": source_record_id,
    }

    if reference_id is None:
        return result

    if prefix == "product_safety_rule":
        result.update(
            {
                "evidence_type": "PRODUCT_SAFETY_RULE",
                "product_safety_rule_id": reference_id,
                "external_trace_id": None,
            }
        )
    elif prefix == "product_interaction_rule":
        result.update(
            {
                "evidence_type": "PRODUCT_INTERACTION_RULE",
                "product_interaction_rule_id": reference_id,
                "external_trace_id": None,
            }
        )
    elif prefix == "ingredient_safety_rule":
        result.update(
            {
                "evidence_type": "INGREDIENT_SAFETY_RULE",
                "ingredient_safety_rule_id": reference_id,
                "external_trace_id": None,
            }
        )
    elif prefix == "ingredient_interaction_rule":
        result.update(
            {
                "evidence_type": "INGREDIENT_INTERACTION_RULE",
                "ingredient_interaction_rule_id": reference_id,
                "external_trace_id": None,
            }
        )

    return result


def _first_rule_reference(alert: AnalysisAlert) -> dict[str, object]:
    for evidence in alert.evidence:
        reference = _reference_from_evidence(evidence)
        if reference["evidence_type"] != "OTHER":
            return reference
    return _reference_from_evidence(alert.evidence[0]) if alert.evidence else {
        "product_safety_rule_id": None,
        "product_interaction_rule_id": None,
        "ingredient_safety_rule_id": None,
        "ingredient_interaction_rule_id": None,
    }


def save_dashboard_report(db: Session, patient_id: int, report: AnalysisReport) -> AnalysisReport:
    try:
        analysis_run_id = db.execute(
            text(
                f"""
                insert into {_table("analysis_run")} (
                  patient_id,
                  status,
                  model_name,
                  prompt_version,
                  completed_at,
                  medication_count,
                  unmatched_medication_count,
                  summary
                )
                values (
                  :patient_id,
                  :status,
                  :model_name,
                  :prompt_version,
                  now(),
                  :medication_count,
                  :unmatched_medication_count,
                  :summary
                )
                returning analysis_run_id
                """
            ),
            {
                "patient_id": patient_id,
                "status": "COMPLETED",
                "model_name": "rule-preview",
                "prompt_version": "rule-preview-v1",
                "medication_count": len(report.medications),
                "unmatched_medication_count": report.summary.unmatched_medication_count,
                "summary": report.pharmacist_handoff_text,
            },
        ).scalar_one()

        saved_at = datetime.now(timezone.utc).isoformat()
        saved_report = report.model_copy(
            update={
                "report_id": f"analysis_{analysis_run_id}",
                "saved_at": saved_at,
                "is_stale": False,
            }
        )

        for alert in saved_report.alerts:
            reference = _first_rule_reference(alert)
            analysis_alert_id = db.execute(
                text(
                    f"""
                    insert into {_table("analysis_alert")} (
                      analysis_run_id,
                      patient_id,
                      rule_type,
                      severity,
                      title,
                      message,
                      product_safety_rule_id,
                      product_interaction_rule_id,
                      ingredient_safety_rule_id,
                      ingredient_interaction_rule_id,
                      evidence
                    )
                    values (
                      :analysis_run_id,
                      :patient_id,
                      :rule_type,
                      :severity,
                      :title,
                      :message,
                      :product_safety_rule_id,
                      :product_interaction_rule_id,
                      :ingredient_safety_rule_id,
                      :ingredient_interaction_rule_id,
                      cast(:evidence as jsonb)
                    )
                    returning analysis_alert_id
                    """
                ),
                {
                    "analysis_run_id": analysis_run_id,
                    "patient_id": patient_id,
                    "rule_type": _db_rule_type(alert.rule_type),
                    "severity": _db_severity(alert.severity),
                    "title": alert.title,
                    "message": alert.message,
                    "product_safety_rule_id": reference.get("product_safety_rule_id"),
                    "product_interaction_rule_id": reference.get("product_interaction_rule_id"),
                    "ingredient_safety_rule_id": reference.get("ingredient_safety_rule_id"),
                    "ingredient_interaction_rule_id": reference.get("ingredient_interaction_rule_id"),
                    "evidence": _json(
                        {
                            "apiRuleType": alert.rule_type.value,
                            "routeToProfessional": alert.route_to_professional,
                            "relatedMedications": alert.related_medications,
                            "evidence": [
                                item.model_dump(by_alias=True, mode="json")
                                for item in alert.evidence
                            ],
                        }
                    ),
                },
            ).scalar_one()

            for evidence in alert.evidence:
                evidence_reference = _reference_from_evidence(evidence)
                db.execute(
                    text(
                        f"""
                        insert into {_table("analysis_alert_evidence")} (
                          analysis_alert_id,
                          evidence_type,
                          product_safety_rule_id,
                          product_interaction_rule_id,
                          ingredient_safety_rule_id,
                          ingredient_interaction_rule_id,
                          external_trace_id,
                          evidence_payload
                        )
                        values (
                          :analysis_alert_id,
                          :evidence_type,
                          :product_safety_rule_id,
                          :product_interaction_rule_id,
                          :ingredient_safety_rule_id,
                          :ingredient_interaction_rule_id,
                          :external_trace_id,
                          cast(:evidence_payload as jsonb)
                        )
                        """
                    ),
                    {
                        "analysis_alert_id": analysis_alert_id,
                        "evidence_type": evidence_reference["evidence_type"],
                        "product_safety_rule_id": evidence_reference["product_safety_rule_id"],
                        "product_interaction_rule_id": evidence_reference["product_interaction_rule_id"],
                        "ingredient_safety_rule_id": evidence_reference["ingredient_safety_rule_id"],
                        "ingredient_interaction_rule_id": evidence_reference["ingredient_interaction_rule_id"],
                        "external_trace_id": evidence_reference["external_trace_id"],
                        "evidence_payload": _json(
                            {
                                "apiRuleType": alert.rule_type.value,
                                **evidence.model_dump(by_alias=True, mode="json"),
                            }
                        ),
                    },
                )

        db.execute(
            text(
                f"""
                insert into {_table("patient_report")} (
                  analysis_run_id,
                  patient_id,
                  report_type,
                  title,
                  recommendation_text,
                  content
                )
                values (
                  :analysis_run_id,
                  :patient_id,
                  :report_type,
                  :title,
                  :recommendation_text,
                  cast(:content as jsonb)
                )
                """
            ),
            {
                "analysis_run_id": analysis_run_id,
                "patient_id": patient_id,
                "report_type": "DASHBOARD",
                "title": "복약 분석 리포트",
                "recommendation_text": saved_report.caregiver_guidance,
                "content": _json(saved_report.model_dump(by_alias=True, mode="json")),
            },
        )
        db.commit()
        return saved_report
    except Exception:
        db.rollback()
        raise


def get_latest_dashboard_report(db: Session, patient_id: int) -> AnalysisReport:
    row = db.execute(
        text(
            f"""
            select content
            from {_table("patient_report")}
            where patient_id = :patient_id
              and report_type = 'DASHBOARD'
            order by created_at desc, patient_report_id desc
            limit 1
            """
        ),
        {"patient_id": patient_id},
    ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="저장된 최신 분석 리포트가 없습니다.",
        )

    report = AnalysisReport.model_validate(row["content"])
    return _report_with_stale_status(db, patient_id, report)


def get_dashboard_report(db: Session, patient_id: int, analysis_run_id: int) -> AnalysisReport:
    row = db.execute(
        text(
            f"""
            select content
            from {_table("patient_report")}
            where patient_id = :patient_id
              and analysis_run_id = :analysis_run_id
              and report_type = 'DASHBOARD'
            order by created_at desc, patient_report_id desc
            limit 1
            """
        ),
        {"patient_id": patient_id, "analysis_run_id": analysis_run_id},
    ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 분석 리포트를 찾을 수 없습니다.",
        )

    report = AnalysisReport.model_validate(row["content"])
    return _report_with_stale_status(db, patient_id, report)


def list_dashboard_reports(db: Session, patient_id: int, limit: int = 20) -> AnalysisReportHistoryResponse:
    rows = db.execute(
        text(
            f"""
            with ranked as (
              select pr.patient_report_id,
                     pr.analysis_run_id,
                     pr.created_at,
                     ar.medication_count,
                     pr.content,
                     row_number() over(order by pr.created_at desc, pr.patient_report_id desc) as rn
              from {_table("patient_report")} pr
              join {_table("analysis_run")} ar on ar.analysis_run_id = pr.analysis_run_id
              where pr.patient_id = :patient_id
                and pr.report_type = 'DASHBOARD'
              order by pr.created_at desc, pr.patient_report_id desc
              limit :limit
            )
            select patient_report_id,
                   analysis_run_id,
                   created_at,
                   medication_count,
                   content,
                   rn
            from ranked
            order by rn
            """
        ),
        {"patient_id": patient_id, "limit": limit},
    ).mappings().all()

    current_snapshot = _current_medication_snapshot(db, patient_id)
    items: list[AnalysisReportHistoryItem] = []
    for row in rows:
        content = row["content"] or {}
        summary = content.get("summary", {})
        alerts = content.get("alerts", [])
        saved_snapshot = content.get("sourceMedicationSnapshot") or []
        analysis_run_id = int(row["analysis_run_id"])
        created_at = row["created_at"]
        items.append(
            AnalysisReportHistoryItem(
                analysisRunId=analysis_run_id,
                patientReportId=int(row["patient_report_id"]),
                reportId=str(content.get("reportId") or f"analysis_{analysis_run_id}"),
                createdAt=created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
                isStale=_is_stale_against_current(saved_snapshot, current_snapshot),
                riskCount=int(summary.get("riskCount") or 0),
                cautionCount=int(summary.get("cautionCount") or 0),
                normalCount=int(summary.get("normalCount") or 0),
                medicationCount=int(row["medication_count"] or 0),
                alertCount=len(alerts) if isinstance(alerts, list) else 0,
                isLatest=int(row["rn"]) == 1,
            )
        )

    return AnalysisReportHistoryResponse(items=items)
