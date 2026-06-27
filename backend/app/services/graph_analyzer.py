from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from uuid import uuid4

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from sqlalchemy.orm import Session

from app.models import (
    AlertSeverity,
    AnalysisAlert,
    AnalysisReport,
    AnalyzeRequest,
    MatchStatus,
    MedicationResult,
    ReportSummary,
    RuleType,
)
from app.services.rule_preview import (
    KST,
    SelectedProduct,
    _dedupe_alerts,
    _ingredient_safety_alert_for_row,
    _product_safety_alert_for_row,
    _resolve_products,
    _source,
)


class GraphAnalysisUnavailable(RuntimeError):
    pass


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _neo4j_uri() -> str | None:
    return os.getenv("NEO4J_URI")


def _neo4j_user() -> str | None:
    return os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")


def _neo4j_password() -> str | None:
    return os.getenv("NEO4J_PASSWORD")


def _neo4j_database() -> str | None:
    return os.getenv("NEO4J_DATABASE") or "neo4j"


def is_graph_analysis_enabled() -> bool:
    return (
        _bool_env("NEO4J_ANALYSIS_ENABLED", True)
        and bool(_neo4j_uri())
        and bool(_neo4j_user())
        and bool(_neo4j_password())
    )


def _bolt_fallback_uri(uri: str) -> str | None:
    if uri.startswith("neo4j+s://"):
        return "bolt+s://" + uri.removeprefix("neo4j+s://")
    return None


def _new_graph_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"


def _make_driver(uri: str | None = None) -> Driver:
    neo4j_uri = uri or _neo4j_uri()
    user = _neo4j_user()
    password = _neo4j_password()
    if not neo4j_uri or not user or not password:
        raise GraphAnalysisUnavailable("Neo4j environment variables are not configured.")
    return GraphDatabase.driver(
        neo4j_uri,
        auth=(user, password),
        connection_timeout=5,
        max_connection_lifetime=300,
    )


def _make_verified_driver() -> Driver:
    uri = _neo4j_uri()
    driver = _make_driver(uri)
    try:
        driver.verify_connectivity()
        return driver
    except ServiceUnavailable as first_error:
        driver.close()
        fallback_uri = _bolt_fallback_uri(uri or "")
        if not fallback_uri:
            raise GraphAnalysisUnavailable("Neo4j is unavailable.") from first_error
        fallback_driver = _make_driver(fallback_uri)
        try:
            fallback_driver.verify_connectivity()
            return fallback_driver
        except Exception as fallback_error:
            fallback_driver.close()
            raise GraphAnalysisUnavailable("Neo4j is unavailable.") from fallback_error


def _neo4j_session(driver: Driver):
    database = _neo4j_database()
    return driver.session(database=database) if database else driver.session()


def _assert_products_loaded(driver: Driver, codes: list[str]) -> None:
    with _neo4j_session(driver) as session:
        row = session.run(
            """
            UNWIND $codes AS code
            OPTIONAL MATCH (p:Product {productCode: code})
            WITH code, p
            WHERE p IS NULL
            RETURN collect(code) AS missing
            """,
            codes=codes,
        ).single()
    missing = row["missing"] if row else []
    if missing:
        raise GraphAnalysisUnavailable(f"Neo4j graph is missing product codes: {', '.join(missing)}")


def _product_interaction_alerts(driver: Driver, products: dict[str, SelectedProduct]) -> list[AnalysisAlert]:
    codes = list(products)
    with _neo4j_session(driver) as session:
        rows = session.run(
            """
            MATCH (a:Product)-[rel:PRODUCT_INTERACTS_WITH]->(b:Product)
            WHERE a.productCode IN $codes
              AND b.productCode IN $codes
              AND a.productCode <> b.productCode
            RETURN a.productCode AS codeA,
                   b.productCode AS codeB,
                   rel.ruleKey AS ruleKey,
                   rel.message AS message
            ORDER BY rel.ruleId
            """,
            codes=codes,
        ).data()

    alerts: list[AnalysisAlert] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        code_a = row["codeA"]
        code_b = row["codeB"]
        key = (*sorted([code_a, code_b]), row["ruleKey"])
        if key in seen:
            continue
        seen.add(key)
        alerts.append(
            AnalysisAlert(
                alertId=_new_graph_id("alt"),
                severity=AlertSeverity.RISK,
                ruleType=RuleType.PRODUCT_INTERACTION,
                title="제품 병용금기/주의",
                message=row["message"] or "식약처 병용금기/주의 데이터에 해당 조합이 있습니다.",
                relatedMedications=[products[code_a].product_name, products[code_b].product_name],
                evidence=[_source("neo4j_product_interaction_rule", row["ruleKey"], "Neo4j 제품 병용금기 경로입니다.")],
                routeToProfessional=True,
            )
        )
    return alerts


def _ingredient_interaction_alerts(driver: Driver, products: dict[str, SelectedProduct]) -> list[AnalysisAlert]:
    codes = list(products)
    with _neo4j_session(driver) as session:
        rows = session.run(
            """
            MATCH (p1:Product)-[:HAS_INGREDIENT|INFERRED_INGREDIENT]->(i1:Ingredient)
                  -[rel:INGREDIENT_INTERACTS_WITH]-
                  (i2:Ingredient)<-[:HAS_INGREDIENT|INFERRED_INGREDIENT]-(p2:Product)
            WHERE p1.productCode IN $codes
              AND p2.productCode IN $codes
              AND p1.productCode < p2.productCode
            RETURN p1.productCode AS codeA,
                   p2.productCode AS codeB,
                   rel.ruleKey AS ruleKey,
                   rel.message AS message
            ORDER BY rel.ruleId
            """,
            codes=codes,
        ).data()

    alerts: list[AnalysisAlert] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        code_a = row["codeA"]
        code_b = row["codeB"]
        key = (*sorted([code_a, code_b]), row["ruleKey"])
        if key in seen:
            continue
        seen.add(key)
        alerts.append(
            AnalysisAlert(
                alertId=_new_graph_id("alt"),
                severity=AlertSeverity.RISK,
                ruleType=RuleType.INGREDIENT_INTERACTION,
                title="성분 병용금기/주의",
                message=row["message"] or "성분 기준 병용금기/주의 룰이 확인되었습니다.",
                relatedMedications=[products[code_a].product_name, products[code_b].product_name],
                evidence=[_source("neo4j_ingredient_interaction_rule", row["ruleKey"], "Neo4j 성분 병용금기 경로입니다.")],
                routeToProfessional=True,
            )
        )
    return alerts


def _duplicate_ingredient_alerts(driver: Driver, products: dict[str, SelectedProduct]) -> list[AnalysisAlert]:
    codes = list(products)
    with _neo4j_session(driver) as session:
        rows = session.run(
            """
            MATCH (p:Product)-[:HAS_INGREDIENT|INFERRED_INGREDIENT]->(i:Ingredient)
            WHERE p.productCode IN $codes
            WITH i, collect(DISTINCT p.productCode) AS productCodes
            WHERE size(productCodes) > 1
            RETURN i.ingredientKey AS ingredientKey,
                   coalesce(i.displayName, i.canonicalName, i.ingredientNameKo, i.ingredientKey) AS ingredientName,
                   productCodes
            ORDER BY ingredientName
            """,
            codes=codes,
        ).data()

    alerts: list[AnalysisAlert] = []
    for row in rows:
        related = [products[code].product_name for code in row["productCodes"] if code in products]
        alerts.append(
            AnalysisAlert(
                alertId=_new_graph_id("alt"),
                severity=AlertSeverity.CAUTION,
                ruleType=RuleType.DUPLICATE_INGREDIENT,
                title="동일 성분 중복",
                message=f"{row['ingredientName']} 성분이 여러 약에 포함되어 있습니다. 중복 복용 여부를 확인하세요.",
                relatedMedications=related,
                evidence=[_source("neo4j_ingredient", f"ingredient:{row['ingredientKey']}", "Neo4j 성분 중복 경로입니다.")],
                routeToProfessional=True,
            )
        )
    return alerts


def _product_safety_alerts(
    driver: Driver,
    payload: AnalyzeRequest,
    products: dict[str, SelectedProduct],
) -> list[AnalysisAlert]:
    codes = list(products)
    with _neo4j_session(driver) as session:
        rows = session.run(
            """
            MATCH (p:Product)-[:HAS_SAFETY_RULE]->(rule:SafetyRule {scope: 'PRODUCT'})
            WHERE p.productCode IN $codes
            RETURN p.productCode AS productCode, properties(rule) AS rule
            ORDER BY rule.ruleId
            """,
            codes=codes,
        ).data()

    alerts: list[AnalysisAlert] = []
    for row in rows:
        rule = row["rule"]
        safety_row = {
            "product_safety_rule_id": rule.get("ruleId"),
            "rule_type": rule.get("ruleType"),
            "pregnancy_grade": rule.get("pregnancyGrade"),
            "age_value": rule.get("ageValue"),
            "age_unit": rule.get("ageUnit"),
            "age_condition": rule.get("ageCondition"),
            "max_daily_dose_text": rule.get("maxDailyDoseText"),
            "max_daily_dose_value": rule.get("maxDailyDoseValue"),
            "max_duration_days": rule.get("maxDurationDays"),
            "detail_info": rule.get("detailInfo"),
            "remark": rule.get("remark"),
        }
        alert = _product_safety_alert_for_row(payload, products[row["productCode"]], safety_row)
        if alert:
            alerts.append(alert)
    return alerts


def _ingredient_safety_alerts(
    driver: Driver,
    payload: AnalyzeRequest,
    products: dict[str, SelectedProduct],
) -> list[AnalysisAlert]:
    codes = list(products)
    with _neo4j_session(driver) as session:
        rows = session.run(
            """
            MATCH (p:Product)-[:HAS_INGREDIENT|INFERRED_INGREDIENT]->(:Ingredient)-[:HAS_SAFETY_RULE]->(rule:SafetyRule {scope: 'INGREDIENT'})
            WHERE p.productCode IN $codes
            RETURN p.productCode AS productCode, properties(rule) AS rule
            ORDER BY rule.ruleId
            """,
            codes=codes,
        ).data()

    alerts: list[AnalysisAlert] = []
    for row in rows:
        rule = row["rule"]
        safety_row = {
            "ingredient_safety_rule_id": rule.get("ruleId"),
            "rule_type": rule.get("ruleType"),
            "age_base_text": rule.get("ageBaseText"),
            "max_quantity_text": rule.get("maxQuantityText"),
            "max_duration_text": rule.get("maxDurationText"),
            "prohibited_content": rule.get("prohibitedContent"),
            "remark": rule.get("remark"),
        }
        alert = _ingredient_safety_alert_for_row(payload, products[row["productCode"]], safety_row)
        if alert:
            alerts.append(alert)
    return alerts


def analyze_medications_with_graph(payload: AnalyzeRequest, db: Session) -> AnalysisReport:
    if not is_graph_analysis_enabled():
        raise GraphAnalysisUnavailable("Neo4j graph analysis is disabled or not configured.")

    products = {product.product_code: product for product in _resolve_products(payload.medications, db)}
    driver = _make_verified_driver()
    try:
        _assert_products_loaded(driver, list(products))
        alerts = _dedupe_alerts(
            [
                *_duplicate_ingredient_alerts(driver, products),
                *_product_interaction_alerts(driver, products),
                *_ingredient_interaction_alerts(driver, products),
                *_product_safety_alerts(driver, payload, products),
                *_ingredient_safety_alerts(driver, payload, products),
            ]
        )
    except (Neo4jError, ServiceUnavailable) as exc:
        raise GraphAnalysisUnavailable("Neo4j graph analysis failed.") from exc
    finally:
        driver.close()

    alerted_names = {
        related_name
        for alert in alerts
        for related_name in alert.related_medications
    }
    return AnalysisReport(
        reportId=_new_graph_id("graph"),
        generatedAt=datetime.now(KST).isoformat(),
        patient=payload.patient,
        summary=ReportSummary(
            riskCount=sum(1 for alert in alerts if alert.severity == AlertSeverity.RISK),
            cautionCount=sum(1 for alert in alerts if alert.severity == AlertSeverity.CAUTION),
            normalCount=sum(1 for product in products.values() if product.product_name not in alerted_names),
            unmatchedMedicationCount=0,
        ),
        medications=[
            MedicationResult(
                enteredDrugName=product.input_name,
                matchedProductName=product.product_name,
                matchStatus=MatchStatus.MATCHED,
            )
            for product in products.values()
        ],
        sourceMedicationSnapshot=payload.medications,
        alerts=alerts,
        caregiverGuidance=(
            "Neo4j DUR 지식 그래프를 우선 사용한 분석입니다. "
            "위험 또는 주의 항목은 임의로 중단하지 말고 약사나 의사에게 확인하세요."
        ),
        pharmacistHandoffText=_build_graph_handoff_text(payload, list(products.values()), alerts),
    )


def _build_graph_handoff_text(
    payload: AnalyzeRequest,
    products: list[SelectedProduct],
    alerts: list[AnalysisAlert],
) -> str:
    age_text = f"{payload.patient.age_years}세" if payload.patient.age_years is not None else "나이 미입력"
    sex_text = payload.patient.sex.value if hasattr(payload.patient.sex, "value") else str(payload.patient.sex)
    product_names = ", ".join(product.product_name for product in products)
    risk_count = sum(1 for alert in alerts if alert.severity == AlertSeverity.RISK)
    caution_count = sum(1 for alert in alerts if alert.severity == AlertSeverity.CAUTION)
    return (
        f"{payload.patient.display_name} / {age_text} / {sex_text} / "
        f"선택 약물 {len(products)}개: {product_names} / "
        f"Neo4j graph 분석 기준 위험 {risk_count}건, 주의 {caution_count}건."
    )
