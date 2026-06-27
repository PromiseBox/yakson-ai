from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Sex(str, Enum):
    FEMALE = "FEMALE"
    MALE = "MALE"
    UNKNOWN = "UNKNOWN"


class MatchStatus(str, Enum):
    MATCHED = "MATCHED"
    UNMATCHED = "UNMATCHED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class AlertSeverity(str, Enum):
    RISK = "RISK"
    CAUTION = "CAUTION"
    NORMAL = "NORMAL"


class AnalysisSource(str, Enum):
    GRAPH = "GRAPH"
    RULE_PREVIEW = "RULE_PREVIEW"


class RuleType(str, Enum):
    PRODUCT_INTERACTION = "PRODUCT_INTERACTION"
    INGREDIENT_INTERACTION = "INGREDIENT_INTERACTION"
    DUPLICATE_INGREDIENT = "DUPLICATE_INGREDIENT"
    ELDERLY_CAUTION = "ELDERLY_CAUTION"
    PREGNANCY_CAUTION = "PREGNANCY_CAUTION"
    LACTATION_CAUTION = "LACTATION_CAUTION"
    AGE_CONTRAINDICATION = "AGE_CONTRAINDICATION"
    DURATION_CAUTION = "DURATION_CAUTION"
    DOSAGE_CAUTION = "DOSAGE_CAUTION"
    DUPLICATE_EFFICACY = "DUPLICATE_EFFICACY"
    MATCHING_REVIEW = "MATCHING_REVIEW"


class PatientInput(BaseModel):
    display_name: str = Field(alias="displayName", min_length=1)
    age_years: int | None = Field(default=None, alias="ageYears", ge=0, le=130)
    sex: Sex = Sex.UNKNOWN


class MedicationInput(BaseModel):
    entered_drug_name: str = Field(alias="enteredDrugName", min_length=1)
    category_name: str | None = Field(default=None, alias="categoryName")
    product_code: str | None = Field(default=None, alias="productCode")
    item_seq: str | None = Field(default=None, alias="itemSeq")
    product_name: str | None = Field(default=None, alias="productName")
    company_name: str | None = Field(default=None, alias="companyName")
    duration_days: int | None = Field(default=None, alias="durationDays", ge=1)
    doses_per_day: float | None = Field(default=None, alias="dosesPerDay", ge=0)
    dose_amount: float | None = Field(default=None, alias="doseAmount", ge=0)
    dose_unit: str | None = Field(default=None, alias="doseUnit")


class AnalyzeRequest(BaseModel):
    patient: PatientInput
    medications: list[MedicationInput] = Field(min_length=1)


class PrescriptionRequest(AnalyzeRequest):
    memo: str | None = None


class PrescriptionResponse(BaseModel):
    prescription_id: str = Field(alias="prescriptionId")
    status: Literal["created"]


class DrugSearchItem(BaseModel):
    product_code: str = Field(alias="productCode")
    item_seq: str = Field(alias="itemSeq")
    product_name: str = Field(alias="productName")
    company_name: str = Field(alias="companyName")
    ingredient_names: list[str] = Field(alias="ingredientNames")
    match_score: float = Field(alias="matchScore")


class DrugSearchResponse(BaseModel):
    items: list[DrugSearchItem]


class MedicationResult(BaseModel):
    entered_drug_name: str = Field(alias="enteredDrugName")
    matched_product_name: str | None = Field(default=None, alias="matchedProductName")
    match_status: MatchStatus = Field(alias="matchStatus")


class AlertEvidence(BaseModel):
    source_type: str = Field(alias="sourceType")
    source_name: str = Field(alias="sourceName")
    source_record_id: str = Field(alias="sourceRecordId")
    description: str


class AnalysisAlert(BaseModel):
    alert_id: str = Field(alias="alertId")
    severity: AlertSeverity
    rule_type: RuleType = Field(alias="ruleType")
    title: str
    message: str
    related_medications: list[str] = Field(alias="relatedMedications")
    evidence: list[AlertEvidence]
    route_to_professional: bool = Field(alias="routeToProfessional")


class ReportSummary(BaseModel):
    risk_count: int = Field(alias="riskCount")
    caution_count: int = Field(alias="cautionCount")
    normal_count: int = Field(alias="normalCount")
    unmatched_medication_count: int = Field(alias="unmatchedMedicationCount")
    # LLM 보호자 요약(있으면 프론트가 분석 요약 설명문으로 표시 — PR #4). 없으면 프론트 기존 폴백.
    description: str | None = Field(default=None)


class AnalysisReport(BaseModel):
    report_id: str = Field(alias="reportId")
    generated_at: str = Field(alias="generatedAt")
    saved_at: str | None = Field(default=None, alias="savedAt")
    is_stale: bool = Field(default=False, alias="isStale")
    analysis_source: AnalysisSource = Field(default=AnalysisSource.RULE_PREVIEW, alias="analysisSource")
    patient: PatientInput
    summary: ReportSummary
    medications: list[MedicationResult]
    source_medication_snapshot: list[MedicationInput] = Field(default_factory=list, alias="sourceMedicationSnapshot")
    alerts: list[AnalysisAlert]
    caregiver_guidance: str = Field(alias="caregiverGuidance")
    pharmacist_handoff_text: str = Field(alias="pharmacistHandoffText")

    class Config:
        populate_by_name = True


class AnalysisReportHistoryItem(BaseModel):
    analysis_run_id: int = Field(alias="analysisRunId")
    patient_report_id: int = Field(alias="patientReportId")
    report_id: str = Field(alias="reportId")
    created_at: str = Field(alias="createdAt")
    is_stale: bool = Field(alias="isStale")
    risk_count: int = Field(alias="riskCount")
    caution_count: int = Field(alias="cautionCount")
    normal_count: int = Field(alias="normalCount")
    medication_count: int = Field(alias="medicationCount")
    alert_count: int = Field(alias="alertCount")
    is_latest: bool = Field(alias="isLatest")


class AnalysisReportHistoryResponse(BaseModel):
    items: list[AnalysisReportHistoryItem]
