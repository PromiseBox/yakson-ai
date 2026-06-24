from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum as SqlEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, DATABASE_SCHEMA, IS_SQLITE, qualified_table


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def db_enum(name: str, *values: str) -> SqlEnum:
    return SqlEnum(
        *values,
        name=name,
        schema=DATABASE_SCHEMA,
        native_enum=not IS_SQLITE,
        create_constraint=IS_SQLITE,
        validate_strings=True,
    )


class Patient(Base):
    __tablename__ = "patient"

    patient_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    age_years: Mapped[int] = mapped_column(Integer, nullable=False)
    sex: Mapped[str] = mapped_column(
        db_enum("sex_code", "FEMALE", "MALE", "UNKNOWN"),
        nullable=False,
        default="UNKNOWN",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    prescriptions: Mapped[list[Prescription]] = relationship(
        "Prescription",
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PrescriptionCategory(Base):
    __tablename__ = "prescription_category"

    prescription_category_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    prescriptions: Mapped[list[Prescription]] = relationship("Prescription", back_populates="category")


class Prescription(Base):
    __tablename__ = "prescription"

    prescription_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey(f"{qualified_table('patient')}.patient_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prescription_category_id: Mapped[int] = mapped_column(
        ForeignKey(f"{qualified_table('prescription_category')}.prescription_category_id"),
        nullable=False,
        index=True,
    )
    prescribed_on: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    patient: Mapped[Patient] = relationship("Patient", back_populates="prescriptions")
    category: Mapped[PrescriptionCategory] = relationship("PrescriptionCategory", back_populates="prescriptions")
    medications: Mapped[list[PrescriptionMedication]] = relationship(
        "PrescriptionMedication",
        back_populates="prescription",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PrescriptionMedication(Base):
    __tablename__ = "prescription_medication"

    prescription_medication_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prescription_id: Mapped[int] = mapped_column(
        ForeignKey(f"{qualified_table('prescription')}.prescription_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_seq: Mapped[str | None] = mapped_column(Text, nullable=True)
    entered_drug_name: Mapped[str] = mapped_column(Text, nullable=False)
    match_status: Mapped[str] = mapped_column(
        db_enum(
            "medication_match_status",
            "UNMATCHED",
            "PRODUCT_MATCHED",
            "ITEM_MATCHED",
            "MANUAL_CONFIRMED",
        ),
        nullable=False,
        default="UNMATCHED",
    )
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    doses_per_day: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    dose_amount: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    dose_unit: Mapped[str] = mapped_column(Text, nullable=False, default="정")
    status: Mapped[str] = mapped_column(
        db_enum("prescription_status", "ACTIVE", "STOPPED", "DELETED"),
        nullable=False,
        default="ACTIVE",
    )

    prescription: Mapped[Prescription] = relationship("Prescription", back_populates="medications")


class DrugProduct(Base):
    __tablename__ = "drug_product"

    product_code: Mapped[str] = mapped_column(Text, primary_key=True)
    item_seq: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_product_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    benefit_status: Mapped[str | None] = mapped_column(Text, nullable=True)


class DrugItemMfds(Base):
    __tablename__ = "drug_item_mfds"

    item_seq: Mapped[str] = mapped_column(Text, primary_key=True)
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_name_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    edi_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
