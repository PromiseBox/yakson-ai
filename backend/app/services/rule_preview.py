from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import combinations
from typing import Mapping
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.models import (
    AlertEvidence,
    AlertSeverity,
    AnalysisAlert,
    AnalysisReport,
    AnalyzeRequest,
    DrugSearchItem,
    MatchStatus,
    MedicationInput,
    MedicationResult,
    ReportSummary,
    RuleType,
    Sex,
)

KST = timezone(timedelta(hours=9))
ALERT_LIMIT_PER_RULE = 30
SCHEMA = "yakson"


@dataclass(frozen=True)
class SelectedProduct:
    product_code: str
    item_seq: str
    product_name: str
    company_name: str
    input_name: str
    duration_days: int | None
    doses_per_day: float | None
    dose_amount: float | None
    dose_unit: str | None

    @property
    def daily_amount(self) -> float | None:
        if self.doses_per_day is None or self.dose_amount is None:
            return None
        return self.doses_per_day * self.dose_amount


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"


def _source(source_name: str, source_record_id: str, description: str) -> AlertEvidence:
    return AlertEvidence(
        sourceType="DUR",
        sourceName=source_name,
        sourceRecordId=source_record_id,
        description=description,
    )


def _clean_text(*values: object) -> str:
    for value in values:
        if value is None:
            continue
        text_value = str(value).strip()
        if text_value and text_value not in {"_", "-", "None"}:
            return text_value
    return ""


def _first_number(value: object) -> float | None:
    if value is None:
        return None
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    if not match:
        return None
    return float(match.group(0))


def _is_female_of_childbearing_age(payload: AnalyzeRequest) -> bool:
    if payload.patient.sex != Sex.FEMALE:
        return False
    if payload.patient.age_years is None:
        return True
    return 10 <= payload.patient.age_years <= 55


def _age_for_unit(age_years: int | None, unit_text: object) -> float | None:
    if age_years is None:
        return None
    unit = str(unit_text or "")
    if "개월" in unit or "월" in unit:
        return age_years * 12
    if "일" in unit:
        return age_years * 365
    return float(age_years)


def _age_rule_applies(
    age_years: int | None,
    age_value: object,
    condition_text: object = None,
    unit_text: object = None,
) -> bool:
    patient_age = _age_for_unit(age_years, unit_text or condition_text)
    threshold = _first_number(age_value)
    if patient_age is None or threshold is None:
        return False

    condition = str(condition_text or "")
    if "초과" in condition:
        return patient_age > threshold
    if "이상" in condition:
        return patient_age >= threshold
    if "이하" in condition:
        return patient_age <= threshold
    return patient_age < threshold


def fetch_drug_for_validation(
    db: Session,
    product_code: str | None,
    item_seq: str | None = None,
) -> DrugSearchItem | None:
    if not product_code and not item_seq:
        return None

    where_clause = "product_code = :lookup_value" if product_code else "item_seq = :lookup_value"
    lookup_value = product_code or item_seq
    row = db.execute(
        text(
            f"""
            select product_code, item_seq, product_name, company_name
            from {SCHEMA}.drug_product
            where {where_clause}
            order by product_name
            limit 1
            """
        ),
        {"lookup_value": lookup_value},
    ).mappings().first()

    if not row:
        return None

    return DrugSearchItem(
        productCode=row["product_code"] or "",
        itemSeq=row["item_seq"] or "",
        productName=row["product_name"] or "",
        companyName=row["company_name"] or "",
        ingredientNames=[],
        matchScore=1.0,
    )


def build_preview_report(payload: AnalyzeRequest, db: Session) -> AnalysisReport:
    products = _resolve_products(payload.medications, db)
    ingredients = _ingredients_by_product(products, db)

    alerts = _dedupe_alerts(
        [
            *_build_duplicate_ingredient_alerts(products, ingredients),
            *_build_duplicate_efficacy_alerts(products, ingredients, db),
            *_build_product_interaction_alerts(products, db),
            *_build_ingredient_interaction_alerts(products, ingredients, db),
            *_build_product_safety_alerts(payload, products, db),
            *_build_ingredient_safety_alerts(payload, products, ingredients, db),
        ]
    )

    alerted_names = {
        related_name
        for alert in alerts
        for related_name in alert.related_medications
    }
    normal_count = sum(1 for product in products if product.product_name not in alerted_names)
    risk_count = sum(1 for alert in alerts if alert.severity == AlertSeverity.RISK)
    caution_count = sum(1 for alert in alerts if alert.severity == AlertSeverity.CAUTION)

    return AnalysisReport(
        reportId=_new_id("preview"),
        generatedAt=datetime.now(KST).isoformat(),
        patient=payload.patient,
        summary=ReportSummary(
            riskCount=risk_count,
            cautionCount=caution_count,
            normalCount=normal_count,
            unmatchedMedicationCount=0,
        ),
        medications=[
            MedicationResult(
                enteredDrugName=product.input_name,
                matchedProductName=product.product_name,
                matchStatus=MatchStatus.MATCHED,
            )
            for product in products
        ],
        sourceMedicationSnapshot=payload.medications,
        alerts=alerts,
        caregiverGuidance=(
            "식약처 기반 DB에 등록된 약물만 대상으로 하는 저장 없는 미리보기입니다. "
            "위험 또는 주의 항목은 임의로 중단하지 말고 약사나 의사에게 확인하세요."
        ),
        pharmacistHandoffText=_build_handoff_text(payload, products, risk_count, caution_count),
    )


def _resolve_products(medications: list[MedicationInput], db: Session) -> list[SelectedProduct]:
    product_codes = [item.product_code for item in medications if item.product_code]
    if len(product_codes) != len(medications):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="식약처 DB 자동완성에서 선택된 약물만 분석할 수 있습니다.",
        )

    rows = db.execute(
        text(
            f"""
            select product_code, item_seq, product_name, company_name
            from {SCHEMA}.drug_product
            where product_code in :codes
            """
        ).bindparams(bindparam("codes", expanding=True)),
        {"codes": product_codes},
    ).mappings().all()
    product_by_code = {row["product_code"]: row for row in rows}

    missing = [code for code in product_codes if code not in product_by_code]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"서비스 대상 아님: 식약처 기반 DB에서 확인되지 않은 약물 코드가 있습니다. ({', '.join(missing)})",
        )

    return [
        SelectedProduct(
            product_code=item.product_code or "",
            item_seq=product_by_code[item.product_code]["item_seq"] or "",
            product_name=product_by_code[item.product_code]["product_name"] or item.entered_drug_name,
            company_name=product_by_code[item.product_code]["company_name"] or "",
            input_name=item.entered_drug_name,
            duration_days=item.duration_days,
            doses_per_day=item.doses_per_day,
            dose_amount=item.dose_amount,
            dose_unit=item.dose_unit,
        )
        for item in medications
    ]


def _ingredients_by_product(products: list[SelectedProduct], db: Session) -> dict[str, list[Mapping[str, object]]]:
    if not products:
        return {}

    rows = db.execute(
        text(
            f"""
            select dpi.product_code,
                   dpi.ingredient_id,
                   coalesce(i.ingredient_name_ko, i.canonical_name, dpi.ingredient_name_at_source) as ingredient_name
            from {SCHEMA}.drug_product_ingredient dpi
            left join {SCHEMA}.ingredient i on i.ingredient_id = dpi.ingredient_id
            where dpi.product_code in :codes
            order by dpi.product_code, ingredient_name
            """
        ).bindparams(bindparam("codes", expanding=True)),
        {"codes": [product.product_code for product in products]},
    ).mappings().all()

    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["product_code"])].append(row)
    return grouped


def _build_duplicate_ingredient_alerts(
    products: list[SelectedProduct],
    ingredients: dict[str, list[Mapping[str, object]]],
) -> list[AnalysisAlert]:
    by_ingredient: dict[int, list[SelectedProduct]] = defaultdict(list)
    ingredient_names: dict[int, str] = {}

    for product in products:
        seen_for_product: set[int] = set()
        for ingredient in ingredients.get(product.product_code, []):
            ingredient_id = ingredient["ingredient_id"]
            if ingredient_id is None:
                continue
            ingredient_id_int = int(ingredient_id)
            if ingredient_id_int in seen_for_product:
                continue
            seen_for_product.add(ingredient_id_int)
            by_ingredient[ingredient_id_int].append(product)
            ingredient_names[ingredient_id_int] = str(ingredient["ingredient_name"] or ingredient_id_int)

    alerts: list[AnalysisAlert] = []
    for ingredient_id, matched_products in by_ingredient.items():
        if len(matched_products) < 2:
            continue
        ingredient_name = ingredient_names.get(ingredient_id, str(ingredient_id))
        alerts.append(
            AnalysisAlert(
                alertId=_new_id("alt"),
                severity=AlertSeverity.CAUTION,
                ruleType=RuleType.DUPLICATE_INGREDIENT,
                title="동일 성분 중복",
                message=f"{ingredient_name} 성분이 여러 약에 포함되어 있습니다. 중복 복용 여부를 확인하세요.",
                relatedMedications=[product.product_name for product in matched_products],
                evidence=[
                    _source(
                        "drug_product_ingredient",
                        f"ingredient:{ingredient_id}",
                        "선택된 약물 간 동일 성분이 확인되었습니다.",
                    )
                ],
                routeToProfessional=True,
            )
        )
    return alerts[:ALERT_LIMIT_PER_RULE]


def _build_duplicate_efficacy_alerts(
    products: list[SelectedProduct],
    ingredients: dict[str, list[Mapping[str, object]]],
    db: Session,
) -> list[AnalysisAlert]:
    if len(products) < 2:
        return []

    rows = db.execute(
        text(
            f"""
            select egm.efficacy_group_id,
                   eg.efficacy_group_name,
                   egm.product_code
            from {SCHEMA}.efficacy_group_member egm
            join {SCHEMA}.efficacy_group eg on eg.efficacy_group_id = egm.efficacy_group_id
            where egm.product_code in :codes
            order by eg.efficacy_group_name
            """
        ).bindparams(bindparam("codes", expanding=True)),
        {"codes": [product.product_code for product in products]},
    ).mappings().all()

    products_by_code: dict[str, list[SelectedProduct]] = defaultdict(list)
    for product in products:
        products_by_code[product.product_code].append(product)

    group_map: dict[int, list[SelectedProduct]] = defaultdict(list)
    group_names: dict[int, str] = {}
    for row in rows:
        group_id = int(row["efficacy_group_id"])
        for product in products_by_code.get(str(row["product_code"]), []):
            group_map[group_id].append(product)
        group_names[group_id] = str(row["efficacy_group_name"] or "동일 효능군")

    alerts: list[AnalysisAlert] = []
    for group_id, matched_products in group_map.items():
        unique_products = list({(product.product_code, product.input_name): product for product in matched_products}.values())
        if len(unique_products) < 2:
            continue
        non_ingredient_duplicate_products = _products_without_shared_ingredients(unique_products, ingredients)
        if len(non_ingredient_duplicate_products) < 2:
            continue
        group_name = group_names.get(group_id, "동일 효능군")
        alerts.append(
            AnalysisAlert(
                alertId=_new_id("alt"),
                severity=AlertSeverity.CAUTION,
                ruleType=RuleType.DUPLICATE_EFFICACY,
                title="동일 효능군 중복",
                message=f"{group_name} 효능군 약물이 여러 개 선택되었습니다. 치료 목적상 필요한 조합인지 확인하세요.",
                relatedMedications=[product.product_name for product in non_ingredient_duplicate_products],
                evidence=[
                    _source(
                        "efficacy_group_member",
                        f"efficacy_group:{group_id}",
                        "선택된 약물 간 동일 효능군 중복이 확인되었습니다.",
                    )
                ],
                routeToProfessional=False,
            )
        )
    return alerts[:ALERT_LIMIT_PER_RULE]


def _products_without_shared_ingredients(
    products: list[SelectedProduct],
    ingredients: dict[str, list[Mapping[str, object]]],
) -> list[SelectedProduct]:
    ingredient_ids_by_code = {
        product.product_code: {
            int(ingredient["ingredient_id"])
            for ingredient in ingredients.get(product.product_code, [])
            if ingredient["ingredient_id"] is not None
        }
        for product in products
    }
    kept_codes: set[str] = set()
    for product_a, product_b in combinations(products, 2):
        if ingredient_ids_by_code.get(product_a.product_code, set()) & ingredient_ids_by_code.get(
            product_b.product_code,
            set(),
        ):
            continue
        kept_codes.add(product_a.product_code)
        kept_codes.add(product_b.product_code)
    return [product for product in products if product.product_code in kept_codes]


def _build_product_interaction_alerts(products: list[SelectedProduct], db: Session) -> list[AnalysisAlert]:
    if len(products) < 2:
        return []

    rows = db.execute(
        text(
            f"""
            select product_interaction_rule_id,
                   product_code_a,
                   product_code_b,
                   contraindication_reason,
                   remark
            from {SCHEMA}.product_interaction_rule
            where product_code_a in :codes_a
              and product_code_b in :codes_b
            limit 120
            """
        )
        .bindparams(bindparam("codes_a", expanding=True))
        .bindparams(bindparam("codes_b", expanding=True)),
        {
            "codes_a": [product.product_code for product in products],
            "codes_b": [product.product_code for product in products],
        },
    ).mappings().all()

    product_by_code = {product.product_code: product for product in products}
    alerts: list[AnalysisAlert] = []
    seen_pairs: set[tuple[str, str]] = set()
    for row in rows:
        product_a = product_by_code.get(str(row["product_code_a"]))
        product_b = product_by_code.get(str(row["product_code_b"]))
        if not product_a or not product_b or product_a.product_code == product_b.product_code:
            continue
        pair_key = tuple(sorted([product_a.product_code, product_b.product_code]))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        reason = _clean_text(row["contraindication_reason"], row["remark"])
        alerts.append(
            AnalysisAlert(
                alertId=_new_id("alt"),
                severity=AlertSeverity.RISK,
                ruleType=RuleType.PRODUCT_INTERACTION,
                title="제품 병용금기/주의",
                message=reason or "식약처 병용금기/주의 데이터에 해당 조합이 있습니다.",
                relatedMedications=[product_a.product_name, product_b.product_name],
                evidence=[
                    _source(
                        "product_interaction_rule",
                        f"product_interaction_rule:{row['product_interaction_rule_id']}",
                        "제품 코드 기준 병용금기/주의 룰입니다.",
                    )
                ],
                routeToProfessional=True,
            )
        )
    return alerts[:ALERT_LIMIT_PER_RULE]


def _build_ingredient_interaction_alerts(
    products: list[SelectedProduct],
    ingredients: dict[str, list[Mapping[str, object]]],
    db: Session,
) -> list[AnalysisAlert]:
    if len(products) < 2:
        return []

    pairs: list[tuple[SelectedProduct, SelectedProduct, int, int]] = []
    for product_a, product_b in combinations(products, 2):
        for ingredient_a in ingredients.get(product_a.product_code, []):
            for ingredient_b in ingredients.get(product_b.product_code, []):
                ingredient_a_id = ingredient_a["ingredient_id"]
                ingredient_b_id = ingredient_b["ingredient_id"]
                if ingredient_a_id is None or ingredient_b_id is None or ingredient_a_id == ingredient_b_id:
                    continue
                pairs.append((product_a, product_b, int(ingredient_a_id), int(ingredient_b_id)))

    if not pairs:
        return []

    ingredient_ids = sorted(
        {ingredient_a_id for _, _, ingredient_a_id, _ in pairs}
        | {ingredient_b_id for _, _, _, ingredient_b_id in pairs}
    )
    rows = db.execute(
        text(
            f"""
            select ingredient_interaction_rule_id,
                   ingredient_a_id,
                   ingredient_b_id,
                   prohibited_content,
                   remark
            from {SCHEMA}.ingredient_interaction_rule
            where ingredient_a_id in :ids_a
              and ingredient_b_id in :ids_b
            limit 120
            """
        )
        .bindparams(bindparam("ids_a", expanding=True))
        .bindparams(bindparam("ids_b", expanding=True)),
        {"ids_a": ingredient_ids, "ids_b": ingredient_ids},
    ).mappings().all()

    rule_by_pair = {
        (int(row["ingredient_a_id"]), int(row["ingredient_b_id"])): row
        for row in rows
    }
    alerts: list[AnalysisAlert] = []
    seen_rules: set[int] = set()
    for product_a, product_b, ingredient_a_id, ingredient_b_id in pairs:
        row = rule_by_pair.get((ingredient_a_id, ingredient_b_id)) or rule_by_pair.get(
            (ingredient_b_id, ingredient_a_id)
        )
        if not row:
            continue
        rule_id = int(row["ingredient_interaction_rule_id"])
        if rule_id in seen_rules:
            continue
        seen_rules.add(rule_id)
        message = _clean_text(row["prohibited_content"], row["remark"])
        alerts.append(
            AnalysisAlert(
                alertId=_new_id("alt"),
                severity=AlertSeverity.RISK,
                ruleType=RuleType.INGREDIENT_INTERACTION,
                title="성분 병용금기/주의",
                message=message or "성분 기준 병용금기/주의 룰이 확인되었습니다.",
                relatedMedications=[product_a.product_name, product_b.product_name],
                evidence=[
                    _source(
                        "ingredient_interaction_rule",
                        f"ingredient_interaction_rule:{rule_id}",
                        "성분 기준 병용금기/주의 룰입니다.",
                    )
                ],
                routeToProfessional=True,
            )
        )
    return alerts[:ALERT_LIMIT_PER_RULE]


def _build_product_safety_alerts(
    payload: AnalyzeRequest,
    products: list[SelectedProduct],
    db: Session,
) -> list[AnalysisAlert]:
    if not products:
        return []

    rows = db.execute(
        text(
            f"""
            select product_safety_rule_id,
                   product_code,
                   rule_type::text as rule_type,
                   pregnancy_grade,
                   age_value,
                   age_unit,
                   age_condition,
                   max_daily_dose_text,
                   max_daily_dose_value,
                   max_duration_days,
                   detail_info,
                   remark
            from {SCHEMA}.product_safety_rule
            where product_code in :codes
              and rule_type::text in (
                'AGE_CONTRAINDICATION',
                'DOSAGE_CAUTION',
                'DURATION_CAUTION',
                'ELDERLY_CAUTION',
                'ELDERLY_NSAID_CAUTION',
                'LACTATION_CAUTION',
                'PREGNANCY_CONTRAINDICATION'
              )
            limit 200
            """
        ).bindparams(bindparam("codes", expanding=True)),
        {"codes": [product.product_code for product in products]},
    ).mappings().all()

    products_by_code: dict[str, list[SelectedProduct]] = defaultdict(list)
    for product in products:
        products_by_code[product.product_code].append(product)

    alerts: list[AnalysisAlert] = []
    for row in rows:
        for product in products_by_code.get(str(row["product_code"]), []):
            alert = _product_safety_alert_for_row(payload, product, row)
            if alert:
                alerts.append(alert)
    return alerts[:ALERT_LIMIT_PER_RULE]


def _product_safety_alert_for_row(
    payload: AnalyzeRequest,
    product: SelectedProduct,
    row: Mapping[str, object],
) -> AnalysisAlert | None:
    rule_type = str(row["rule_type"])
    message_detail = _clean_text(row["detail_info"], row["remark"])
    evidence_id = f"product_safety_rule:{row['product_safety_rule_id']}"

    if rule_type == "AGE_CONTRAINDICATION":
        if not _age_rule_applies(payload.patient.age_years, row["age_value"], row["age_condition"], row["age_unit"]):
            return None
        return _safety_alert(
            product,
            AlertSeverity.RISK,
            RuleType.AGE_CONTRAINDICATION,
            "연령 금기",
            message_detail or "환자 연령에 적용되는 제품 연령 제한이 있습니다.",
            "product_safety_rule",
            evidence_id,
            "제품 기준 연령 금기 룰입니다.",
        )

    if rule_type in {"ELDERLY_CAUTION", "ELDERLY_NSAID_CAUTION"}:
        if (payload.patient.age_years or 0) < 65:
            return None
        return _safety_alert(
            product,
            AlertSeverity.CAUTION,
            RuleType.ELDERLY_CAUTION,
            "고령자 주의 약물",
            message_detail or "65세 이상 고령자에게 주의가 필요한 약물입니다.",
            "product_safety_rule",
            evidence_id,
            "제품 기준 고령자 주의 룰입니다.",
        )

    if rule_type == "PREGNANCY_CONTRAINDICATION":
        if not _is_female_of_childbearing_age(payload):
            return None
        grade = _clean_text(row["pregnancy_grade"])
        grade_text = f" 임부금기 {grade}등급" if grade else " 임부금기"
        return _safety_alert(
            product,
            AlertSeverity.RISK,
            RuleType.PREGNANCY_CAUTION,
            "임부 금기/주의",
            message_detail or f"{grade_text} 대상 약물입니다. 임신 가능성이 있으면 반드시 전문가에게 확인하세요.",
            "product_safety_rule",
            evidence_id,
            "제품 기준 임부 금기/주의 룰입니다.",
        )

    if rule_type == "LACTATION_CAUTION":
        if not _is_female_of_childbearing_age(payload):
            return None
        return _safety_alert(
            product,
            AlertSeverity.CAUTION,
            RuleType.LACTATION_CAUTION,
            "수유부 주의",
            message_detail or "수유 중 복용 주의가 필요한 약물입니다.",
            "product_safety_rule",
            evidence_id,
            "제품 기준 수유부 주의 룰입니다.",
        )

    if rule_type == "DURATION_CAUTION":
        max_duration = _first_number(row["max_duration_days"])
        if not product.duration_days or not max_duration or product.duration_days <= max_duration:
            return None
        return _safety_alert(
            product,
            AlertSeverity.CAUTION,
            RuleType.DURATION_CAUTION,
            "투여기간 주의",
            message_detail or f"입력된 투여기간 {product.duration_days}일이 기준 {int(max_duration)}일을 초과합니다.",
            "product_safety_rule",
            evidence_id,
            "제품 기준 투여기간 주의 룰입니다.",
        )

    if rule_type == "DOSAGE_CAUTION":
        max_dose = _first_number(row["max_daily_dose_value"])
        if product.daily_amount is None or max_dose is None or product.daily_amount <= max_dose:
            return None
        dose_text = _clean_text(row["max_daily_dose_text"]) or f"기준값 {max_dose:g}"
        return _safety_alert(
            product,
            AlertSeverity.CAUTION,
            RuleType.DOSAGE_CAUTION,
            "용량 주의",
            message_detail or f"입력된 하루 총량이 용량 주의 기준({dose_text})을 초과할 수 있습니다.",
            "product_safety_rule",
            evidence_id,
            "제품 기준 용량 주의 룰입니다.",
        )

    return None


def _build_ingredient_safety_alerts(
    payload: AnalyzeRequest,
    products: list[SelectedProduct],
    ingredients: dict[str, list[Mapping[str, object]]],
    db: Session,
) -> list[AnalysisAlert]:
    ingredient_to_products: dict[int, list[SelectedProduct]] = defaultdict(list)
    for product in products:
        seen_for_product: set[int] = set()
        for ingredient in ingredients.get(product.product_code, []):
            ingredient_id = ingredient["ingredient_id"]
            if ingredient_id is None:
                continue
            ingredient_id_int = int(ingredient_id)
            if ingredient_id_int in seen_for_product:
                continue
            seen_for_product.add(ingredient_id_int)
            ingredient_to_products[ingredient_id_int].append(product)

    if not ingredient_to_products:
        return []

    rows = db.execute(
        text(
            f"""
            select ingredient_safety_rule_id,
                   rule_type::text as rule_type,
                   ingredient_id,
                   age_base_text,
                   max_quantity_text,
                   max_duration_text,
                   prohibited_content,
                   remark
            from {SCHEMA}.ingredient_safety_rule
            where ingredient_id in :ingredient_ids
              and rule_type::text in (
                'AGE_CONTRAINDICATION',
                'DOSAGE_CAUTION',
                'DURATION_CAUTION',
                'ELDERLY_CAUTION',
                'LACTATION_CAUTION',
                'PREGNANCY_CONTRAINDICATION'
              )
            limit 200
            """
        ).bindparams(bindparam("ingredient_ids", expanding=True)),
        {"ingredient_ids": sorted(ingredient_to_products.keys())},
    ).mappings().all()

    alerts: list[AnalysisAlert] = []
    for row in rows:
        for product in ingredient_to_products.get(int(row["ingredient_id"]), []):
            alert = _ingredient_safety_alert_for_row(payload, product, row)
            if alert:
                alerts.append(alert)
    return alerts[:ALERT_LIMIT_PER_RULE]


def _ingredient_safety_alert_for_row(
    payload: AnalyzeRequest,
    product: SelectedProduct,
    row: Mapping[str, object],
) -> AnalysisAlert | None:
    rule_type = str(row["rule_type"])
    evidence_id = f"ingredient_safety_rule:{row['ingredient_safety_rule_id']}"
    message_detail = _clean_text(row["prohibited_content"], row["remark"])

    if rule_type == "AGE_CONTRAINDICATION":
        if not _age_rule_applies(payload.patient.age_years, row["age_base_text"], row["age_base_text"]):
            return None
        return _safety_alert(
            product,
            AlertSeverity.RISK,
            RuleType.AGE_CONTRAINDICATION,
            "성분 연령 금기",
            message_detail or f"{row['age_base_text']} 연령 제한이 있는 성분입니다.",
            "ingredient_safety_rule",
            evidence_id,
            "성분 기준 연령 금기 룰입니다.",
        )

    if rule_type == "ELDERLY_CAUTION":
        if (payload.patient.age_years or 0) < 65:
            return None
        return _safety_alert(
            product,
            AlertSeverity.CAUTION,
            RuleType.ELDERLY_CAUTION,
            "성분 고령자 주의",
            message_detail or "65세 이상 고령자에게 주의가 필요한 성분입니다.",
            "ingredient_safety_rule",
            evidence_id,
            "성분 기준 고령자 주의 룰입니다.",
        )

    if rule_type == "PREGNANCY_CONTRAINDICATION":
        if not _is_female_of_childbearing_age(payload):
            return None
        return _safety_alert(
            product,
            AlertSeverity.RISK,
            RuleType.PREGNANCY_CAUTION,
            "성분 임부 금기/주의",
            message_detail or "임신 가능성이 있으면 전문가 확인이 필요한 성분입니다.",
            "ingredient_safety_rule",
            evidence_id,
            "성분 기준 임부 금기/주의 룰입니다.",
        )

    if rule_type == "LACTATION_CAUTION":
        if not _is_female_of_childbearing_age(payload):
            return None
        return _safety_alert(
            product,
            AlertSeverity.CAUTION,
            RuleType.LACTATION_CAUTION,
            "성분 수유부 주의",
            message_detail or "수유 중 복용 주의가 필요한 성분입니다.",
            "ingredient_safety_rule",
            evidence_id,
            "성분 기준 수유부 주의 룰입니다.",
        )

    if rule_type == "DURATION_CAUTION":
        threshold = _first_number(row["max_duration_text"])
        if not product.duration_days or not threshold or product.duration_days <= threshold:
            return None
        return _safety_alert(
            product,
            AlertSeverity.CAUTION,
            RuleType.DURATION_CAUTION,
            "성분 투여기간 주의",
            message_detail or f"입력된 투여기간 {product.duration_days}일이 성분 기준({row['max_duration_text']})을 초과합니다.",
            "ingredient_safety_rule",
            evidence_id,
            "성분 기준 투여기간 주의 룰입니다.",
        )

    if rule_type == "DOSAGE_CAUTION":
        threshold = _first_number(row["max_quantity_text"])
        if product.daily_amount is None or not threshold or product.daily_amount <= threshold:
            return None
        return _safety_alert(
            product,
            AlertSeverity.CAUTION,
            RuleType.DOSAGE_CAUTION,
            "성분 용량 주의",
            message_detail or f"입력된 하루 총량이 성분 기준({row['max_quantity_text']})을 초과할 수 있습니다.",
            "ingredient_safety_rule",
            evidence_id,
            "성분 기준 용량 주의 룰입니다. 단위 해석은 약사 확인이 필요합니다.",
        )

    return None


def _safety_alert(
    product: SelectedProduct,
    severity: AlertSeverity,
    rule_type: RuleType,
    title: str,
    message: str,
    source_name: str,
    source_record_id: str,
    description: str,
) -> AnalysisAlert:
    return AnalysisAlert(
        alertId=_new_id("alt"),
        severity=severity,
        ruleType=rule_type,
        title=title,
        message=message,
        relatedMedications=[product.product_name],
        evidence=[_source(source_name, source_record_id, description)],
        routeToProfessional=severity == AlertSeverity.RISK or rule_type in {
            RuleType.ELDERLY_CAUTION,
            RuleType.AGE_CONTRAINDICATION,
            RuleType.PREGNANCY_CAUTION,
            RuleType.LACTATION_CAUTION,
        },
    )


def _dedupe_alerts(alerts: list[AnalysisAlert]) -> list[AnalysisAlert]:
    seen: dict[tuple[str, str, str, tuple[str, ...]], AnalysisAlert] = {}
    deduped: list[AnalysisAlert] = []
    for alert in alerts:
        key = (
            alert.rule_type.value,
            alert.title,
            alert.message,
            tuple(sorted(alert.related_medications)),
        )
        existing = seen.get(key)
        if existing:
            existing_sources = {item.source_record_id for item in existing.evidence}
            existing.evidence.extend(
                item for item in alert.evidence if item.source_record_id not in existing_sources
            )
            existing.route_to_professional = existing.route_to_professional or alert.route_to_professional
            continue
        seen[key] = alert
        deduped.append(alert)
    return deduped


def _build_handoff_text(
    payload: AnalyzeRequest,
    products: list[SelectedProduct],
    risk_count: int,
    caution_count: int,
) -> str:
    age_text = f"{payload.patient.age_years}세" if payload.patient.age_years is not None else "나이 미입력"
    sex_text = {
        Sex.FEMALE: "여성",
        Sex.MALE: "남성",
        Sex.UNKNOWN: "성별 미입력",
    }.get(payload.patient.sex, "성별 미입력")
    product_names = ", ".join(product.product_name for product in products)
    return (
        f"{payload.patient.display_name} / {age_text} / {sex_text} / "
        f"선택 약물 {len(products)}개: {product_names} / "
        f"위험 {risk_count}건, 주의 {caution_count}건. "
        "식약처 DB 룰 근거를 기준으로 상담이 필요합니다."
    )
