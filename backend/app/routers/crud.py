from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.db_models import (
    DrugItemMfds,
    DrugProduct,
    Patient,
    Prescription,
    PrescriptionCategory,
    PrescriptionMedication,
)
from app.models import DrugSearchItem, DrugSearchResponse
from app.schemas import (
    MedicationCreate,
    MedicationListOut,
    MedicationOut,
    MedicationUpdate,
    PatientCreate,
    PatientListOut,
    PatientOut,
    PatientUpdate,
    PrescriptionCategoryCreate,
    PrescriptionCategoryListOut,
    PrescriptionCategoryOut,
    PrescriptionCategoryUpdate,
)

router = APIRouter(prefix="/api", tags=["crud"])

DEFAULT_CATEGORIES = ["정형외과", "내과", "외과", "성인병약", "당뇨약", "수면/신경안정", "기타"]


def _patient_out(patient: Patient) -> PatientOut:
    return PatientOut(
        id=str(patient.patient_id),
        patientId=patient.patient_id,
        displayName=patient.display_name,
        ageYears=patient.age_years,
        sex=patient.sex,
        createdAt=patient.created_at,
        updatedAt=patient.updated_at,
    )


def _category_out(category: PrescriptionCategory) -> PrescriptionCategoryOut:
    return PrescriptionCategoryOut(
        id=str(category.prescription_category_id),
        prescriptionCategoryId=category.prescription_category_id,
        categoryName=category.category_name,
        displayOrder=category.display_order,
        isActive=category.is_active,
    )


def _get_drug_product_or_422(
    db: Session,
    product_code: str | None,
    item_seq: str | None = None,
) -> DrugProduct:
    if not product_code and not item_seq:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="식약처 DB 자동완성에서 선택된 약물만 저장할 수 있습니다.",
        )

    conditions = []
    if product_code:
        conditions.append(DrugProduct.product_code == product_code)
    if item_seq:
        conditions.append(DrugProduct.item_seq == item_seq)

    drug = db.scalar(select(DrugProduct).where(or_(*conditions)).order_by(DrugProduct.product_name).limit(1))
    if not drug:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="서비스 대상 아님: 식약처 기반 DB에서 확인되지 않은 약물입니다.",
        )
    return drug


def _drug_snapshot(db: Session, medication: PrescriptionMedication) -> DrugProduct | None:
    if not medication.product_code and not medication.item_seq:
        return None

    conditions = []
    if medication.product_code:
        conditions.append(DrugProduct.product_code == medication.product_code)
    if medication.item_seq:
        conditions.append(DrugProduct.item_seq == medication.item_seq)
    return db.scalar(select(DrugProduct).where(or_(*conditions)).order_by(DrugProduct.product_name).limit(1))


def _medication_out(db: Session, medication: PrescriptionMedication) -> MedicationOut:
    prescription = medication.prescription
    drug = _drug_snapshot(db, medication)
    return MedicationOut(
        id=str(medication.prescription_medication_id),
        medicationId=medication.prescription_medication_id,
        prescriptionId=medication.prescription_id,
        patientId=prescription.patient_id,
        categoryName=prescription.category.category_name,
        enteredDrugName=medication.entered_drug_name,
        matchedProductName=drug.product_name if drug else None,
        companyName=drug.company_name if drug else None,
        durationDays=medication.duration_days,
        dosesPerDay=medication.doses_per_day,
        doseAmount=medication.dose_amount,
        doseUnit=medication.dose_unit,
        prescribedOn=prescription.prescribed_on,
        memo=prescription.memo,
        productCode=medication.product_code,
        itemSeq=medication.item_seq,
        matchStatus=medication.match_status,
        status=medication.status,
        createdAt=prescription.created_at,
    )


def _get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


def _get_medication_or_404(db: Session, medication_id: int) -> PrescriptionMedication:
    medication = db.scalar(
        select(PrescriptionMedication)
        .options(joinedload(PrescriptionMedication.prescription).joinedload(Prescription.category))
        .where(PrescriptionMedication.prescription_medication_id == medication_id)
    )
    if not medication:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")
    return medication


def _get_or_create_category(db: Session, category_name: str) -> PrescriptionCategory:
    name = category_name.strip()
    category = db.scalar(
        select(PrescriptionCategory).where(func.lower(PrescriptionCategory.category_name) == name.lower())
    )
    if category:
        return category

    next_order = db.scalar(select(func.coalesce(func.max(PrescriptionCategory.display_order), 0))) or 0
    category = PrescriptionCategory(category_name=name, display_order=int(next_order) + 1, is_active=True)
    db.add(category)
    db.flush()
    return category


def seed_default_categories(db: Session) -> None:
    existing_count = db.scalar(select(func.count(PrescriptionCategory.prescription_category_id))) or 0
    if existing_count:
        return

    for index, name in enumerate(DEFAULT_CATEGORIES, start=1):
        db.add(PrescriptionCategory(category_name=name, display_order=index, is_active=True))
    db.commit()


@router.get("/patients", response_model=PatientListOut, response_model_by_alias=True)
def list_patients(db: Session = Depends(get_db)) -> PatientListOut:
    patients = db.scalars(select(Patient).order_by(Patient.created_at.desc(), Patient.patient_id.desc())).all()
    return PatientListOut(items=[_patient_out(patient) for patient in patients])


@router.post(
    "/patients",
    response_model=PatientOut,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)) -> PatientOut:
    patient = Patient(
        display_name=payload.display_name.strip(),
        age_years=payload.age_years,
        sex=payload.sex.value,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return _patient_out(patient)


@router.get("/patients/{patient_id}", response_model=PatientOut, response_model_by_alias=True)
def get_patient(patient_id: int, db: Session = Depends(get_db)) -> PatientOut:
    return _patient_out(_get_patient_or_404(db, patient_id))


@router.patch("/patients/{patient_id}", response_model=PatientOut, response_model_by_alias=True)
def update_patient(patient_id: int, payload: PatientUpdate, db: Session = Depends(get_db)) -> PatientOut:
    patient = _get_patient_or_404(db, patient_id)
    if payload.display_name is not None:
        patient.display_name = payload.display_name.strip()
    if payload.age_years is not None:
        patient.age_years = payload.age_years
    if payload.sex is not None:
        patient.sex = payload.sex.value
    db.commit()
    db.refresh(patient)
    return _patient_out(patient)


@router.delete("/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(patient_id: int, db: Session = Depends(get_db)) -> None:
    patient = _get_patient_or_404(db, patient_id)
    db.delete(patient)
    db.commit()


@router.get(
    "/prescription-categories",
    response_model=PrescriptionCategoryListOut,
    response_model_by_alias=True,
)
def list_prescription_categories(
    include_inactive: bool = Query(default=False, alias="includeInactive"),
    db: Session = Depends(get_db),
) -> PrescriptionCategoryListOut:
    statement: Select[tuple[PrescriptionCategory]] = select(PrescriptionCategory)
    if not include_inactive:
        statement = statement.where(PrescriptionCategory.is_active.is_(True))
    statement = statement.order_by(PrescriptionCategory.display_order, PrescriptionCategory.category_name)
    categories = db.scalars(statement).all()
    return PrescriptionCategoryListOut(items=[_category_out(category) for category in categories])


@router.post(
    "/prescription-categories",
    response_model=PrescriptionCategoryOut,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
def create_prescription_category(
    payload: PrescriptionCategoryCreate,
    db: Session = Depends(get_db),
) -> PrescriptionCategoryOut:
    category = PrescriptionCategory(
        category_name=payload.category_name.strip(),
        display_order=payload.display_order,
        is_active=payload.is_active,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _category_out(category)


@router.patch(
    "/prescription-categories/{category_id}",
    response_model=PrescriptionCategoryOut,
    response_model_by_alias=True,
)
def update_prescription_category(
    category_id: int,
    payload: PrescriptionCategoryUpdate,
    db: Session = Depends(get_db),
) -> PrescriptionCategoryOut:
    category = db.get(PrescriptionCategory, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription category not found")

    if payload.category_name is not None:
        category.category_name = payload.category_name.strip()
    if payload.display_order is not None:
        category.display_order = payload.display_order
    if payload.is_active is not None:
        category.is_active = payload.is_active
    db.commit()
    db.refresh(category)
    return _category_out(category)


@router.delete(
    "/prescription-categories/{category_id}",
    response_model=PrescriptionCategoryOut,
    response_model_by_alias=True,
)
def delete_prescription_category(category_id: int, db: Session = Depends(get_db)) -> PrescriptionCategoryOut:
    category = db.get(PrescriptionCategory, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription category not found")

    category.is_active = False
    db.commit()
    db.refresh(category)
    return _category_out(category)


@router.get(
    "/patients/{patient_id}/medications",
    response_model=MedicationListOut,
    response_model_by_alias=True,
)
def list_patient_medications(patient_id: int, db: Session = Depends(get_db)) -> MedicationListOut:
    _get_patient_or_404(db, patient_id)
    medications = db.scalars(
        select(PrescriptionMedication)
        .join(Prescription)
        .options(joinedload(PrescriptionMedication.prescription).joinedload(Prescription.category))
        .where(Prescription.patient_id == patient_id)
        .where(PrescriptionMedication.status == "ACTIVE")
        .order_by(Prescription.created_at.desc(), PrescriptionMedication.prescription_medication_id.desc())
    ).all()
    return MedicationListOut(items=[_medication_out(db, medication) for medication in medications])


@router.post(
    "/patients/{patient_id}/medications",
    response_model=MedicationOut,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
def create_patient_medication(
    patient_id: int,
    payload: MedicationCreate,
    db: Session = Depends(get_db),
) -> MedicationOut:
    _get_patient_or_404(db, patient_id)
    drug = _get_drug_product_or_422(db, payload.product_code, payload.item_seq)
    category = _get_or_create_category(db, payload.category_name)
    prescription = Prescription(
        patient_id=patient_id,
        prescription_category_id=category.prescription_category_id,
        prescribed_on=payload.prescribed_on or date.today(),
        memo=payload.memo,
    )
    db.add(prescription)
    db.flush()

    medication = PrescriptionMedication(
        prescription_id=prescription.prescription_id,
        product_code=drug.product_code,
        item_seq=drug.item_seq,
        entered_drug_name=payload.entered_drug_name.strip(),
        match_status="PRODUCT_MATCHED",
        match_confidence=Decimal("1.0"),
        duration_days=payload.duration_days,
        doses_per_day=payload.doses_per_day,
        dose_amount=payload.dose_amount,
        dose_unit=payload.dose_unit.strip(),
        status="ACTIVE",
    )
    db.add(medication)
    db.commit()
    db.refresh(medication)
    return _medication_out(db, _get_medication_or_404(db, medication.prescription_medication_id))


@router.patch("/medications/{medication_id}", response_model=MedicationOut, response_model_by_alias=True)
def update_medication(
    medication_id: int,
    payload: MedicationUpdate,
    db: Session = Depends(get_db),
) -> MedicationOut:
    medication = _get_medication_or_404(db, medication_id)
    prescription = medication.prescription

    if payload.category_name is not None:
        category = _get_or_create_category(db, payload.category_name)
        prescription.prescription_category_id = category.prescription_category_id
        prescription.category = category
    if payload.prescribed_on is not None:
        prescription.prescribed_on = payload.prescribed_on
    if payload.memo is not None:
        prescription.memo = payload.memo
    if payload.entered_drug_name is not None:
        medication.entered_drug_name = payload.entered_drug_name.strip()
    if payload.duration_days is not None:
        medication.duration_days = payload.duration_days
    if payload.doses_per_day is not None:
        medication.doses_per_day = payload.doses_per_day
    if payload.dose_amount is not None:
        medication.dose_amount = payload.dose_amount
    if payload.dose_unit is not None:
        medication.dose_unit = payload.dose_unit.strip()
    if "product_code" in payload.model_fields_set or "item_seq" in payload.model_fields_set:
        drug = _get_drug_product_or_422(
            db,
            payload.product_code if payload.product_code is not None else medication.product_code,
            payload.item_seq if payload.item_seq is not None else medication.item_seq,
        )
        medication.product_code = drug.product_code
        medication.item_seq = drug.item_seq
    if payload.status is not None:
        medication.status = payload.status

    medication.match_status = "PRODUCT_MATCHED"
    db.commit()
    return _medication_out(db, _get_medication_or_404(db, medication_id))


@router.delete("/medications/{medication_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_medication(medication_id: int, db: Session = Depends(get_db)) -> None:
    medication = _get_medication_or_404(db, medication_id)
    medication.status = "DELETED"
    db.commit()


@router.get("/drugs/search", response_model=DrugSearchResponse, response_model_by_alias=True)
def search_drugs_from_db(
    q: str = Query(default="", min_length=0),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> DrugSearchResponse:
    query = q.strip()
    if not query:
        return DrugSearchResponse(items=[])

    normalized_query = "".join(query.split()).lower()
    pattern = f"%{query}%"
    prefix = f"{query}%"
    normalized_pattern = f"%{normalized_query}%"
    normalized_prefix = f"{normalized_query}%"

    rows = db.execute(
        text(
            """
            with product_matches as (
                select dp.product_code,
                       dp.item_seq,
                       coalesce(dp.product_name, dim.item_name) as product_name,
                       coalesce(dp.company_name, dim.company_name) as company_name,
                       case
                         when lower(coalesce(dp.product_name, dim.item_name)) = lower(:query) then 10
                         when coalesce(dp.product_name, dim.item_name) ilike :prefix then 20
                         when replace(lower(coalesce(dp.normalized_product_name, dp.product_name, dim.item_name)), ' ', '') = :normalized_query then 25
                         when coalesce(dp.product_name, dim.item_name) ilike :pattern then 30
                         when replace(lower(coalesce(dp.normalized_product_name, dp.product_name, dim.item_name)), ' ', '') like :normalized_prefix then 35
                         when replace(lower(coalesce(dp.normalized_product_name, dp.product_name, dim.item_name)), ' ', '') like :normalized_pattern then 40
                         when coalesce(dp.company_name, dim.company_name) ilike :pattern then 80
                         when dp.product_code ilike :pattern or coalesce(dp.item_seq, '') ilike :pattern or coalesce(dim.edi_code, '') ilike :pattern then 90
                         else 100
                       end as match_rank
                from yakson.drug_product dp
                left join yakson.drug_item_mfds dim on dim.item_seq = dp.item_seq
                where coalesce(dp.product_name, dim.item_name) ilike :pattern
                   or replace(lower(coalesce(dp.normalized_product_name, dp.product_name, dim.item_name)), ' ', '') like :normalized_pattern
                   or coalesce(dp.company_name, dim.company_name) ilike :pattern
                   or dp.product_code ilike :pattern
                   or coalesce(dp.item_seq, '') ilike :pattern
                   or coalesce(dim.edi_code, '') ilike :pattern
            ),
            ingredient_matches as (
                select dp.product_code,
                       dp.item_seq,
                       dp.product_name,
                       dp.company_name,
                       case
                         when lower(coalesce(i.ingredient_name_ko, i.canonical_name, dpi.ingredient_name_at_source, ia.alias_name)) = lower(:query) then 15
                         when replace(lower(coalesce(i.ingredient_name_ko, i.canonical_name, dpi.ingredient_name_at_source, ia.alias_name)), ' ', '') = :normalized_query then 16
                         when coalesce(i.ingredient_name_ko, i.canonical_name, dpi.ingredient_name_at_source, ia.alias_name) ilike :prefix then 45
                         when coalesce(i.ingredient_name_ko, i.canonical_name, dpi.ingredient_name_at_source, ia.alias_name) ilike :pattern then 50
                         when replace(lower(coalesce(i.ingredient_name_ko, i.canonical_name, dpi.ingredient_name_at_source, ia.alias_name)), ' ', '') like :normalized_pattern then 55
                         else 95
                       end as match_rank
                from yakson.drug_product dp
                join yakson.drug_product_ingredient dpi on dpi.product_code = dp.product_code
                join yakson.ingredient i on i.ingredient_id = dpi.ingredient_id
                left join yakson.ingredient_alias ia on ia.ingredient_id = i.ingredient_id
                where coalesce(i.ingredient_name_ko, i.canonical_name, dpi.ingredient_name_at_source, ia.alias_name) ilike :pattern
                   or replace(lower(coalesce(i.ingredient_name_ko, i.canonical_name, dpi.ingredient_name_at_source, ia.alias_name)), ' ', '') like :normalized_pattern
            ),
            ranked as (
                select product_code, item_seq, product_name, company_name, min(match_rank) as match_rank
                from (
                    select * from product_matches
                    union all
                    select * from ingredient_matches
                ) matched
                group by product_code, item_seq, product_name, company_name
            )
            select r.product_code,
                   r.item_seq,
                   r.product_name,
                   r.company_name,
                   r.match_rank,
                   coalesce(
                     array_remove(array_agg(distinct coalesce(i.ingredient_name_ko, i.canonical_name, dpi.ingredient_name_at_source)), null),
                     '{}'
                   ) as ingredient_names
            from ranked r
            left join yakson.drug_product_ingredient dpi on dpi.product_code = r.product_code
            left join yakson.ingredient i on i.ingredient_id = dpi.ingredient_id
            group by r.product_code, r.item_seq, r.product_name, r.company_name, r.match_rank
            order by r.match_rank, r.product_name, r.company_name, r.product_code
            limit :limit
            """
        ),
        {
            "query": query,
            "normalized_query": normalized_query,
            "pattern": pattern,
            "prefix": prefix,
            "normalized_pattern": normalized_pattern,
            "normalized_prefix": normalized_prefix,
            "limit": limit,
        },
    ).mappings().all()

    return DrugSearchResponse(
        items=[
            DrugSearchItem(
                productCode=row.product_code,
                itemSeq=row.item_seq or "",
                productName=row.product_name,
                companyName=row.company_name or "",
                ingredientNames=list(row.ingredient_names or []),
                matchScore=max(0.0, 1.0 - (float(row.match_rank) / 100.0)),
            )
            for row in rows
        ]
    )
