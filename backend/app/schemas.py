from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import Sex


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class PatientCreate(ApiModel):
    display_name: str = Field(alias="displayName", min_length=1)
    age_years: int = Field(alias="ageYears", ge=0, le=130)
    sex: Sex = Sex.UNKNOWN


class PatientUpdate(ApiModel):
    display_name: str | None = Field(default=None, alias="displayName", min_length=1)
    age_years: int | None = Field(default=None, alias="ageYears", ge=0, le=130)
    sex: Sex | None = None


class PatientOut(ApiModel):
    id: str
    patient_id: int = Field(alias="patientId")
    display_name: str = Field(alias="displayName")
    age_years: int = Field(alias="ageYears")
    sex: Sex
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class PatientListOut(ApiModel):
    items: list[PatientOut]


class PrescriptionCategoryCreate(ApiModel):
    category_name: str = Field(alias="categoryName", min_length=1)
    display_order: int = Field(default=0, alias="displayOrder", ge=0)
    is_active: bool = Field(default=True, alias="isActive")


class PrescriptionCategoryUpdate(ApiModel):
    category_name: str | None = Field(default=None, alias="categoryName", min_length=1)
    display_order: int | None = Field(default=None, alias="displayOrder", ge=0)
    is_active: bool | None = Field(default=None, alias="isActive")


class PrescriptionCategoryOut(ApiModel):
    id: str
    prescription_category_id: int = Field(alias="prescriptionCategoryId")
    category_name: str = Field(alias="categoryName")
    display_order: int = Field(alias="displayOrder")
    is_active: bool = Field(alias="isActive")


class PrescriptionCategoryListOut(ApiModel):
    items: list[PrescriptionCategoryOut]


class MedicationCreate(ApiModel):
    category_name: str = Field(alias="categoryName", min_length=1)
    entered_drug_name: str = Field(alias="enteredDrugName", min_length=1)
    duration_days: int = Field(alias="durationDays", ge=1)
    doses_per_day: Decimal = Field(alias="dosesPerDay", gt=0)
    dose_amount: Decimal = Field(alias="doseAmount", gt=0)
    dose_unit: str = Field(default="정", alias="doseUnit", min_length=1)
    prescribed_on: date | None = Field(default=None, alias="prescribedOn")
    memo: str | None = None
    product_code: str | None = Field(default=None, alias="productCode")
    item_seq: str | None = Field(default=None, alias="itemSeq")


class MedicationUpdate(ApiModel):
    category_name: str | None = Field(default=None, alias="categoryName", min_length=1)
    entered_drug_name: str | None = Field(default=None, alias="enteredDrugName", min_length=1)
    duration_days: int | None = Field(default=None, alias="durationDays", ge=1)
    doses_per_day: Decimal | None = Field(default=None, alias="dosesPerDay", gt=0)
    dose_amount: Decimal | None = Field(default=None, alias="doseAmount", gt=0)
    dose_unit: str | None = Field(default=None, alias="doseUnit", min_length=1)
    prescribed_on: date | None = Field(default=None, alias="prescribedOn")
    memo: str | None = None
    product_code: str | None = Field(default=None, alias="productCode")
    item_seq: str | None = Field(default=None, alias="itemSeq")
    status: Literal["ACTIVE", "STOPPED", "DELETED"] | None = None


class MedicationOut(ApiModel):
    id: str
    medication_id: int = Field(alias="medicationId")
    prescription_id: int = Field(alias="prescriptionId")
    patient_id: int = Field(alias="patientId")
    category_name: str = Field(alias="categoryName")
    entered_drug_name: str = Field(alias="enteredDrugName")
    matched_product_name: str | None = Field(default=None, alias="matchedProductName")
    company_name: str | None = Field(default=None, alias="companyName")
    duration_days: int = Field(alias="durationDays")
    doses_per_day: Decimal = Field(alias="dosesPerDay")
    dose_amount: Decimal = Field(alias="doseAmount")
    dose_unit: str = Field(alias="doseUnit")
    prescribed_on: date | None = Field(alias="prescribedOn")
    memo: str | None
    product_code: str | None = Field(alias="productCode")
    item_seq: str | None = Field(alias="itemSeq")
    match_status: str = Field(alias="matchStatus")
    status: str
    created_at: datetime = Field(alias="createdAt")


class MedicationListOut(ApiModel):
    items: list[MedicationOut]


class MedicationOcrCandidate(ApiModel):
    candidate_id: str = Field(alias="candidateId")
    entered_drug_name: str = Field(alias="enteredDrugName")
    category_name: str | None = Field(default=None, alias="categoryName")
    duration_days: int | None = Field(default=None, alias="durationDays")
    doses_per_day: float | None = Field(default=None, alias="dosesPerDay")
    dose_amount: float | None = Field(default=None, alias="doseAmount")
    dose_unit: str | None = Field(default=None, alias="doseUnit")
    source_line: str = Field(alias="sourceLine")
    confidence: float
    needs_review: bool = Field(alias="needsReview")


class MedicationOcrResponse(ApiModel):
    provider: str
    raw_text: str = Field(alias="rawText")
    candidates: list[MedicationOcrCandidate]
    warnings: list[str] = Field(default_factory=list)
