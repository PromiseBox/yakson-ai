from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import Patient, Prescription, PrescriptionMedication
from app.models import AnalysisReport, AnalysisReportHistoryResponse, AnalyzeRequest, DrugSearchItem
from app.services.analysis_storage import (
    get_dashboard_report,
    get_latest_dashboard_report,
    list_dashboard_reports,
    save_dashboard_report,
)
from app.services.rule_preview import build_preview_report, fetch_drug_for_validation

router = APIRouter(prefix="/api", tags=["analysis-preview"])


@router.get("/drugs/validate", response_model=DrugSearchItem, response_model_by_alias=True)
def validate_drug(
    product_code: str | None = Query(default=None, alias="productCode"),
    item_seq: str | None = Query(default=None, alias="itemSeq"),
    db: Session = Depends(get_db),
) -> DrugSearchItem:
    drug = fetch_drug_for_validation(db, product_code, item_seq)
    if not drug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="식약처 기반 DB에서 확인되지 않은 약물입니다.",
        )
    return drug


@router.post("/analysis/preview", response_model=AnalysisReport, response_model_by_alias=True)
def preview_analysis(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
) -> AnalysisReport:
    return build_preview_report(payload, db)


def _analysis_request_from_patient(patient_id: int, db: Session) -> AnalyzeRequest:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="복용자를 찾을 수 없습니다.")

    medications = db.scalars(
        select(PrescriptionMedication)
        .join(Prescription)
        .where(Prescription.patient_id == patient_id)
        .where(PrescriptionMedication.status == "ACTIVE")
        .order_by(Prescription.created_at.desc(), PrescriptionMedication.prescription_medication_id.desc())
    ).all()

    if not medications:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="분석할 약물이 없습니다. 식약처 DB 자동완성에서 선택한 약물을 먼저 저장해주세요.",
        )

    return AnalyzeRequest(
        patient={
            "displayName": patient.display_name,
            "ageYears": patient.age_years,
            "sex": patient.sex,
        },
        medications=[
            {
                "enteredDrugName": medication.entered_drug_name,
                "categoryName": medication.prescription.category.category_name,
                "productCode": medication.product_code,
                "itemSeq": medication.item_seq,
                "durationDays": medication.duration_days,
                "dosesPerDay": float(medication.doses_per_day),
                "doseAmount": float(medication.dose_amount),
                "doseUnit": medication.dose_unit,
            }
            for medication in medications
        ],
    )


@router.post(
    "/patients/{patient_id}/analysis/latest",
    response_model=AnalysisReport,
    response_model_by_alias=True,
)
def run_and_save_latest_analysis(patient_id: int, db: Session = Depends(get_db)) -> AnalysisReport:
    payload = _analysis_request_from_patient(patient_id, db)
    report = build_preview_report(payload, db)
    return save_dashboard_report(db, patient_id, report)


@router.get(
    "/patients/{patient_id}/analysis/latest",
    response_model=AnalysisReport,
    response_model_by_alias=True,
)
def get_latest_analysis(patient_id: int, db: Session = Depends(get_db)) -> AnalysisReport:
    return get_latest_dashboard_report(db, patient_id)


@router.get(
    "/patients/{patient_id}/analysis/reports",
    response_model=AnalysisReportHistoryResponse,
    response_model_by_alias=True,
)
def list_analysis_reports(
    patient_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AnalysisReportHistoryResponse:
    return list_dashboard_reports(db, patient_id, limit)


@router.get(
    "/patients/{patient_id}/analysis/reports/{analysis_run_id}",
    response_model=AnalysisReport,
    response_model_by_alias=True,
)
def get_analysis_report(
    patient_id: int,
    analysis_run_id: int,
    db: Session = Depends(get_db),
) -> AnalysisReport:
    return get_dashboard_report(db, patient_id, analysis_run_id)
