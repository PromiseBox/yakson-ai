from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from neo4j import Driver
from sqlalchemy import select
from sqlalchemy.orm import joinedload

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.database import SessionLocal
from app.db_models import Patient, Prescription, PrescriptionMedication
from app.models import (
    AlertSeverity,
    AnalysisAlert,
    AnalyzeRequest,
    MedicationInput,
    PatientInput,
    ReportSummary,
    RuleType,
    Sex,
)
from app.services.analysis_storage import get_latest_dashboard_report
from app.services.rule_preview import (
    SelectedProduct,
    _dedupe_alerts,
    _ingredient_safety_alert_for_row,
    _new_id,
    _product_safety_alert_for_row,
    _resolve_products,
    _source,
    build_preview_report,
)
from load_neo4j_graph import make_verified_driver, neo4j_config


def patient_payload(patient_id: int) -> AnalyzeRequest:
    with SessionLocal() as db:
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


def selected_products(payload: AnalyzeRequest) -> list[SelectedProduct]:
    with SessionLocal() as db:
        return _resolve_products(payload.medications, db)


def saved_latest_summary(patient_id: int) -> dict[str, Any] | None:
    with SessionLocal() as db:
        try:
            report = get_latest_dashboard_report(db, patient_id)
        except Exception:
            return None
    return {
        "reportId": report.report_id,
        "summary": report.summary.model_dump(by_alias=True),
        "alerts": [alert.model_dump(by_alias=True, mode="json") for alert in report.alerts],
    }


def neo4j_session(driver: Driver):
    return driver.session(database=neo4j_config()["database"])


def assert_products_loaded(driver: Driver, codes: list[str]) -> None:
    with neo4j_session(driver) as session:
        rows = session.run(
            """
            UNWIND $codes AS code
            OPTIONAL MATCH (p:Product {productCode: code})
            WITH code, p
            WHERE p IS NULL
            RETURN collect(code) AS missing
            """,
            codes=codes,
        ).single()
    missing = rows["missing"] if rows else []
    if missing:
        raise RuntimeError(
            "Neo4j graph is missing selected products. "
            f"Run scripts/load_neo4j_graph.py first. Missing: {', '.join(missing)}"
        )


def product_interaction_alerts(driver: Driver, products: dict[str, SelectedProduct]) -> list[AnalysisAlert]:
    codes = list(products)
    with neo4j_session(driver) as session:
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
                alertId=_new_id("alt"),
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


def ingredient_interaction_alerts(driver: Driver, products: dict[str, SelectedProduct]) -> list[AnalysisAlert]:
    codes = list(products)
    with neo4j_session(driver) as session:
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
                   i1.ingredientKey AS ingredientA,
                   i2.ingredientKey AS ingredientB,
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
                alertId=_new_id("alt"),
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


def duplicate_ingredient_alerts(driver: Driver, products: dict[str, SelectedProduct]) -> list[AnalysisAlert]:
    codes = list(products)
    with neo4j_session(driver) as session:
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
                alertId=_new_id("alt"),
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


def product_safety_alerts(
    driver: Driver,
    payload: AnalyzeRequest,
    products: dict[str, SelectedProduct],
) -> list[AnalysisAlert]:
    codes = list(products)
    with neo4j_session(driver) as session:
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


def ingredient_safety_alerts(
    driver: Driver,
    payload: AnalyzeRequest,
    products: dict[str, SelectedProduct],
) -> list[AnalysisAlert]:
    codes = list(products)
    with neo4j_session(driver) as session:
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


def analyze_with_graph(driver: Driver, payload: AnalyzeRequest) -> dict[str, Any]:
    products = {product.product_code: product for product in selected_products(payload)}
    assert_products_loaded(driver, list(products))

    alerts = _dedupe_alerts(
        [
            *duplicate_ingredient_alerts(driver, products),
            *product_interaction_alerts(driver, products),
            *ingredient_interaction_alerts(driver, products),
            *product_safety_alerts(driver, payload, products),
            *ingredient_safety_alerts(driver, payload, products),
        ]
    )
    alerted_names = {
        related_name
        for alert in alerts
        for related_name in alert.related_medications
    }
    summary = ReportSummary(
        riskCount=sum(1 for alert in alerts if alert.severity == AlertSeverity.RISK),
        cautionCount=sum(1 for alert in alerts if alert.severity == AlertSeverity.CAUTION),
        normalCount=sum(1 for product in products.values() if product.product_name not in alerted_names),
        unmatchedMedicationCount=0,
    )
    return {
        "summary": summary.model_dump(by_alias=True),
        "alerts": [alert.model_dump(by_alias=True, mode="json") for alert in alerts],
    }


def live_sql_analysis(payload: AnalyzeRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        report = build_preview_report(payload, db)
    return {
        "reportId": report.report_id,
        "summary": report.summary.model_dump(by_alias=True),
        "alerts": [alert.model_dump(by_alias=True, mode="json") for alert in report.alerts],
    }


def alert_key(alert: dict[str, Any]) -> tuple[str, str, str, tuple[str, ...]]:
    return (
        alert["severity"],
        alert["ruleType"],
        alert["message"],
        tuple(sorted(alert["relatedMedications"])),
    )


def comparison(saved: dict[str, Any] | None, sql: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    sql_keys = {alert_key(alert): alert for alert in sql["alerts"]}
    graph_keys = {alert_key(alert): alert for alert in graph["alerts"]}
    return {
        "savedLatest": saved,
        "livePostgres": sql,
        "neo4jGraph": graph,
        "onlyInPostgres": [sql_keys[key] for key in sorted(sql_keys.keys() - graph_keys.keys())],
        "onlyInNeo4j": [graph_keys[key] for key in sorted(graph_keys.keys() - sql_keys.keys())],
    }


def print_report(result: dict[str, Any]) -> None:
    saved = result["savedLatest"]
    if saved:
        print(f"Saved latest: {saved['reportId']} {saved['summary']}")
    else:
        print("Saved latest: none")
    print(f"Live PostgreSQL: {result['livePostgres']['summary']}")
    print(f"Neo4j graph:     {result['neo4jGraph']['summary']}")
    print()

    print("Neo4j graph alerts")
    for alert in result["neo4jGraph"]["alerts"]:
        related = " | ".join(alert["relatedMedications"])
        print(f"- {alert['severity']} {alert['ruleType']} {alert['message']} :: {related}")
        evidence = ", ".join(item["sourceRecordId"] for item in alert["evidence"])
        print(f"  evidence: {evidence}")

    print()
    print(f"Only in PostgreSQL: {len(result['onlyInPostgres'])}")
    for alert in result["onlyInPostgres"]:
        print(f"- {alert['severity']} {alert['ruleType']} {alert['message']}")

    print(f"Only in Neo4j: {len(result['onlyInNeo4j'])}")
    for alert in result["onlyInNeo4j"]:
        print(f"- {alert['severity']} {alert['ruleType']} {alert['message']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare PostgreSQL rule preview and Neo4j graph analysis for a patient.")
    parser.add_argument("--patient-id", type=int, default=22)
    parser.add_argument("--json", action="store_true", help="Print full comparison as JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = patient_payload(args.patient_id)
    driver = make_verified_driver()
    try:
        saved = saved_latest_summary(args.patient_id)
        sql = live_sql_analysis(payload)
        graph = analyze_with_graph(driver, payload)
        result = comparison(saved, sql, graph)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_report(result)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
