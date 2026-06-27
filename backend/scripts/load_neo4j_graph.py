from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from sqlalchemy import bindparam, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import DATABASE_SCHEMA, SessionLocal


GRAPH_LABELS = [
    "Product",
    "Ingredient",
    "IngredientRecord",
    "ProductInteractionRule",
    "IngredientInteractionRule",
    "SafetyRule",
    "Patient",
    "Medication",
    "PrescriptionCategory",
]
MIN_KO_INGREDIENT_MATCH_LENGTH = 4
MIN_EN_INGREDIENT_MATCH_LENGTH = 5


def table(name: str) -> str:
    return f"{DATABASE_SCHEMA}.{name}" if DATABASE_SCHEMA else name


def chunks(items: list[dict[str, Any]], size: int = 1000) -> Iterator[list[dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def code_filter_sql(alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return f"and {prefix}product_code in :product_codes"


def clean_text(*values: object) -> str:
    for value in values:
        if value is None:
            continue
        text_value = str(value).strip()
        if text_value and text_value not in {"_", "-", "None"}:
            return text_value
    return ""


def normalize_key(value: object) -> str:
    text_value = clean_text(value).lower()
    text_value = re.sub(r"\s+", " ", text_value)
    return text_value.strip()


def ingredient_key(row: dict[str, Any]) -> str:
    base = clean_text(
        row.get("canonical_name"),
        row.get("ingredient_name_ko"),
        row.get("ingredient_name_at_source"),
        row.get("ingredient_id"),
    )
    return normalize_key(base)


def ingredient_display_name(row: dict[str, Any]) -> str:
    return clean_text(row.get("ingredient_name_ko"), row.get("canonical_name"), row.get("ingredient_name_at_source"))


def env_value(*names: str, required: bool = True) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    if required:
        raise RuntimeError(f"Missing required environment variable: {' or '.join(names)}")
    return None


def neo4j_config() -> dict[str, str]:
    load_dotenv(ROOT / ".env")
    return {
        "uri": env_value("NEO4J_URI"),
        "user": env_value("NEO4J_USERNAME", "NEO4J_USER"),
        "password": env_value("NEO4J_PASSWORD"),
        "database": env_value("NEO4J_DATABASE", required=False) or "neo4j",
    }


def make_driver(uri: str | None = None):
    config = neo4j_config()
    return GraphDatabase.driver(
        uri or config["uri"],
        auth=(config["user"], config["password"]),
        connection_timeout=30,
        max_connection_lifetime=300,
    )


def bolt_fallback_uri(uri: str) -> str | None:
    if uri.startswith("neo4j+s://"):
        return "bolt+s://" + uri.removeprefix("neo4j+s://")
    return None


def make_verified_driver():
    config = neo4j_config()
    driver = make_driver()
    try:
        driver.verify_connectivity()
        return driver
    except ServiceUnavailable:
        fallback_uri = bolt_fallback_uri(config["uri"])
        driver.close()
        if not fallback_uri:
            raise
        fallback_driver = make_driver(fallback_uri)
        fallback_driver.verify_connectivity()
        print(f"Connected with bolt+s fallback for {config['uri']}.")
        return fallback_driver


def run_write(driver, cypher: str, rows: list[dict[str, Any]], *, batch_size: int = 500) -> int:
    if not rows:
        return 0
    config = neo4j_config()
    total = 0
    for batch in chunks(rows, batch_size):
        for attempt in range(1, 4):
            try:
                with driver.session(database=config["database"]) as session:
                    session.run(cypher, rows=batch).consume()
                break
            except (ServiceUnavailable, SessionExpired, Neo4jError):
                if attempt == 3:
                    raise
                time.sleep(2 * attempt)
        total += len(batch)
    return total


def run_cypher(driver, cypher: str, **parameters: Any) -> None:
    config = neo4j_config()
    with driver.session(database=config["database"]) as session:
        session.run(cypher, **parameters).consume()


def create_constraints(driver) -> None:
    statements = [
        "CREATE CONSTRAINT yakson_product_code IF NOT EXISTS FOR (p:Product) REQUIRE p.productCode IS UNIQUE",
        "CREATE CONSTRAINT yakson_ingredient_key IF NOT EXISTS FOR (i:Ingredient) REQUIRE i.ingredientKey IS UNIQUE",
        "CREATE CONSTRAINT yakson_ingredient_record_id IF NOT EXISTS FOR (i:IngredientRecord) REQUIRE i.ingredientId IS UNIQUE",
        "CREATE CONSTRAINT yakson_product_interaction_rule_key IF NOT EXISTS FOR (r:ProductInteractionRule) REQUIRE r.ruleKey IS UNIQUE",
        "CREATE CONSTRAINT yakson_ingredient_interaction_rule_key IF NOT EXISTS FOR (r:IngredientInteractionRule) REQUIRE r.ruleKey IS UNIQUE",
        "CREATE CONSTRAINT yakson_safety_rule_key IF NOT EXISTS FOR (r:SafetyRule) REQUIRE r.ruleKey IS UNIQUE",
        "CREATE CONSTRAINT yakson_patient_id IF NOT EXISTS FOR (p:Patient) REQUIRE p.patientId IS UNIQUE",
        "CREATE CONSTRAINT yakson_medication_id IF NOT EXISTS FOR (m:Medication) REQUIRE m.medicationId IS UNIQUE",
        "CREATE CONSTRAINT yakson_category_name IF NOT EXISTS FOR (c:PrescriptionCategory) REQUIRE c.categoryName IS UNIQUE",
    ]
    for statement in statements:
        run_cypher(driver, statement)


def reset_graph(driver) -> None:
    run_cypher(
        driver,
        """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN $labels)
        DETACH DELETE n
        """,
        labels=GRAPH_LABELS,
    )


def fetch_products(product_codes: set[str] | None = None) -> list[dict[str, Any]]:
    parameters: dict[str, Any] = {}
    product_filter = ""
    bindparams = []
    if product_codes is not None:
        product_filter = code_filter_sql()
        parameters["product_codes"] = sorted(product_codes)
        bindparams.append(bindparam("product_codes", expanding=True))
    with SessionLocal() as db:
        rows = db.execute(
            text(
                f"""
                select product_code,
                       item_seq,
                       product_name,
                       normalized_product_name,
                       company_name,
                       benefit_status
                from {table("drug_product")}
                where product_code is not null
                  {product_filter}
                """
            ).bindparams(*bindparams),
            parameters,
        ).mappings().all()
    return [dict(row) for row in rows]


def fetch_ingredient_records() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                f"""
                with referenced_ingredients as (
                  select ingredient_id
                  from {table("drug_product_ingredient")}
                  where ingredient_id is not null
                  union
                  select ingredient_a_id from {table("ingredient_interaction_rule")}
                  union
                  select ingredient_b_id from {table("ingredient_interaction_rule")}
                  union
                  select ingredient_id from {table("ingredient_safety_rule")}
                )
                select i.ingredient_id,
                       i.ingredient_name_ko,
                       i.canonical_name
                from {table("ingredient")} i
                join referenced_ingredients ri on ri.ingredient_id = i.ingredient_id
                """
            )
        ).mappings().all()

    records: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        key = ingredient_key(item)
        if not key:
            continue
        records.append(
            {
                "ingredientId": int(item["ingredient_id"]),
                "ingredientKey": key,
                "displayName": ingredient_display_name(item),
                "ingredientNameKo": item.get("ingredient_name_ko"),
                "canonicalName": item.get("canonical_name"),
            }
        )
    return records


def fetch_direct_product_ingredients(product_codes: set[str] | None = None) -> list[dict[str, Any]]:
    parameters: dict[str, Any] = {}
    product_filter = ""
    bindparams = []
    if product_codes is not None:
        product_filter = code_filter_sql("dpi")
        parameters["product_codes"] = sorted(product_codes)
        bindparams.append(bindparam("product_codes", expanding=True))
    with SessionLocal() as db:
        rows = db.execute(
            text(
                f"""
                select dpi.product_code,
                       dpi.ingredient_id,
                       dpi.ingredient_name_at_source,
                       i.ingredient_name_ko,
                       i.canonical_name
                from {table("drug_product_ingredient")} dpi
                join {table("ingredient")} i on i.ingredient_id = dpi.ingredient_id
                where dpi.product_code is not null
                  and dpi.ingredient_id is not null
                  {product_filter}
                """
            ).bindparams(*bindparams),
            parameters,
        ).mappings().all()

    links: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        key = ingredient_key(item)
        if not key:
            continue
        links.append(
            {
                "productCode": item["product_code"],
                "ingredientId": int(item["ingredient_id"]),
                "ingredientKey": key,
                "ingredientName": ingredient_display_name(item),
                "source": "drug_product_ingredient",
            }
        )
    return links


def fetch_inferred_product_ingredients(product_codes: set[str] | None = None) -> list[dict[str, Any]]:
    parameters: dict[str, Any] = {}
    product_filter = ""
    bindparams = []
    if product_codes is not None:
        product_filter = code_filter_sql("dp")
        parameters["product_codes"] = sorted(product_codes)
        bindparams.append(bindparam("product_codes", expanding=True))
    with SessionLocal() as db:
        products = db.execute(
            text(
                f"""
                select dp.product_code,
                       lower(coalesce(dp.product_name, '') || ' ' || coalesce(dp.normalized_product_name, '')) as product_text
                from {table("drug_product")} dp
                where dp.product_code is not null
                  {product_filter}
                """
            ).bindparams(*bindparams),
            parameters,
        ).mappings().all()
        rule_ingredients = db.execute(
            text(
                f"""
                select distinct i.ingredient_id,
                       i.ingredient_name_ko,
                       i.canonical_name
                from {table("ingredient")} i
                join (
                  select ingredient_a_id as ingredient_id from {table("ingredient_interaction_rule")}
                  union
                  select ingredient_b_id as ingredient_id from {table("ingredient_interaction_rule")}
                  union
                  select ingredient_id from {table("ingredient_safety_rule")}
                ) ri on ri.ingredient_id = i.ingredient_id
                """
            )
        ).mappings().all()

    links: list[dict[str, Any]] = []
    terms: list[tuple[str, dict[str, Any]]] = []
    for row in rule_ingredients:
        item = dict(row)
        ko_name = clean_text(item.get("ingredient_name_ko"))
        canonical_name = clean_text(item.get("canonical_name"))
        if len(ko_name) >= MIN_KO_INGREDIENT_MATCH_LENGTH:
            terms.append((ko_name.lower(), item))
        if len(canonical_name) >= MIN_EN_INGREDIENT_MATCH_LENGTH:
            terms.append((canonical_name.lower(), item))

    seen: set[tuple[str, int]] = set()
    for product in products:
        product_code = str(product["product_code"])
        product_text = str(product["product_text"] or "")
        for term, item in terms:
            ingredient_id = int(item["ingredient_id"])
            key = (product_code, ingredient_id)
            if key in seen or term not in product_text:
                continue
            seen.add(key)
            ingredient_key_value = ingredient_key(item)
            if not ingredient_key_value:
                continue
            links.append(
                {
                    "productCode": product_code,
                    "ingredientId": ingredient_id,
                    "ingredientKey": ingredient_key_value,
                    "ingredientName": ingredient_display_name(item),
                    "source": "product_name_inference",
                }
            )
    return links


def fetch_product_interactions(product_codes: set[str] | None = None) -> list[dict[str, Any]]:
    parameters: dict[str, Any] = {}
    product_filter = ""
    bindparams = []
    if product_codes is not None:
        product_filter = """
                  and product_code_a in :product_codes
                  and product_code_b in :product_codes
        """
        parameters["product_codes"] = sorted(product_codes)
        bindparams.append(bindparam("product_codes", expanding=True))
    with SessionLocal() as db:
        rows = db.execute(
            text(
                f"""
                select product_interaction_rule_id,
                       product_code_a,
                       product_code_b,
                       contraindication_reason,
                       remark
                from {table("product_interaction_rule")}
                where product_code_a is not null
                  and product_code_b is not null
                  {product_filter}
                """
            ).bindparams(*bindparams),
            parameters,
        ).mappings().all()

    return [
        {
            "ruleId": int(row["product_interaction_rule_id"]),
            "ruleKey": f"product_interaction_rule:{row['product_interaction_rule_id']}",
            "productCodeA": row["product_code_a"],
            "productCodeB": row["product_code_b"],
            "message": clean_text(row["contraindication_reason"], row["remark"]),
        }
        for row in rows
    ]


def fetch_ingredient_interactions() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                f"""
                select iir.ingredient_interaction_rule_id,
                       iir.ingredient_a_id,
                       ia.ingredient_name_ko as ingredient_a_name_ko,
                       ia.canonical_name as ingredient_a_canonical_name,
                       iir.ingredient_b_id,
                       ib.ingredient_name_ko as ingredient_b_name_ko,
                       ib.canonical_name as ingredient_b_canonical_name,
                       iir.prohibited_content,
                       iir.remark
                from {table("ingredient_interaction_rule")} iir
                join {table("ingredient")} ia on ia.ingredient_id = iir.ingredient_a_id
                join {table("ingredient")} ib on ib.ingredient_id = iir.ingredient_b_id
                """
            )
        ).mappings().all()

    rules: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        ingredient_a = {
            "ingredient_id": item["ingredient_a_id"],
            "ingredient_name_ko": item["ingredient_a_name_ko"],
            "canonical_name": item["ingredient_a_canonical_name"],
        }
        ingredient_b = {
            "ingredient_id": item["ingredient_b_id"],
            "ingredient_name_ko": item["ingredient_b_name_ko"],
            "canonical_name": item["ingredient_b_canonical_name"],
        }
        key_a = ingredient_key(ingredient_a)
        key_b = ingredient_key(ingredient_b)
        if not key_a or not key_b:
            continue
        rules.append(
            {
                "ruleId": int(item["ingredient_interaction_rule_id"]),
                "ruleKey": f"ingredient_interaction_rule:{item['ingredient_interaction_rule_id']}",
                "ingredientKeyA": key_a,
                "ingredientKeyB": key_b,
                "ingredientNameA": ingredient_display_name(ingredient_a),
                "ingredientNameB": ingredient_display_name(ingredient_b),
                "message": clean_text(item["prohibited_content"], item["remark"]),
            }
        )
    return rules


def fetch_product_safety_rules(product_codes: set[str] | None = None) -> list[dict[str, Any]]:
    parameters: dict[str, Any] = {}
    product_filter = ""
    bindparams = []
    if product_codes is not None:
        product_filter = code_filter_sql()
        parameters["product_codes"] = sorted(product_codes)
        bindparams.append(bindparam("product_codes", expanding=True))
    with SessionLocal() as db:
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
                from {table("product_safety_rule")}
                where product_code is not null
                  {product_filter}
                """
            ).bindparams(*bindparams),
            parameters,
        ).mappings().all()

    return [
        {
            "ruleId": int(row["product_safety_rule_id"]),
            "ruleKey": f"product_safety_rule:{row['product_safety_rule_id']}",
            "scope": "PRODUCT",
            "productCode": row["product_code"],
            "ruleType": row["rule_type"],
            "pregnancyGrade": row["pregnancy_grade"],
            "ageValue": float(row["age_value"]) if row["age_value"] is not None else None,
            "ageUnit": row["age_unit"],
            "ageCondition": row["age_condition"],
            "maxDailyDoseText": row["max_daily_dose_text"],
            "maxDailyDoseValue": float(row["max_daily_dose_value"]) if row["max_daily_dose_value"] is not None else None,
            "maxDurationDays": int(row["max_duration_days"]) if row["max_duration_days"] is not None else None,
            "detailInfo": row["detail_info"],
            "remark": row["remark"],
        }
        for row in rows
    ]


def fetch_ingredient_safety_rules() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                f"""
                select isr.ingredient_safety_rule_id,
                       isr.rule_type::text as rule_type,
                       isr.ingredient_id,
                       i.ingredient_name_ko,
                       i.canonical_name,
                       isr.age_base_text,
                       isr.max_quantity_text,
                       isr.max_duration_text,
                       isr.prohibited_content,
                       isr.remark
                from {table("ingredient_safety_rule")} isr
                join {table("ingredient")} i on i.ingredient_id = isr.ingredient_id
                where isr.ingredient_id is not null
                """
            )
        ).mappings().all()

    rules: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        key = ingredient_key(item)
        if not key:
            continue
        rules.append(
            {
                "ruleId": int(item["ingredient_safety_rule_id"]),
                "ruleKey": f"ingredient_safety_rule:{item['ingredient_safety_rule_id']}",
                "scope": "INGREDIENT",
                "ingredientKey": key,
                "ruleType": item["rule_type"],
                "ageBaseText": item["age_base_text"],
                "maxQuantityText": item["max_quantity_text"],
                "maxDurationText": item["max_duration_text"],
                "prohibitedContent": item["prohibited_content"],
                "remark": item["remark"],
            }
        )
    return rules


def fetch_patients_and_medications(
    patient_ids: list[int] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    patient_parameters: dict[str, Any] = {}
    patient_filter = ""
    medication_patient_filter = ""
    patient_bindparams = []
    medication_bindparams = []
    if patient_ids:
        patient_filter = "where patient_id in :patient_ids"
        medication_patient_filter = "and p.patient_id in :patient_ids"
        patient_parameters["patient_ids"] = patient_ids
        patient_bindparams.append(bindparam("patient_ids", expanding=True))
        medication_bindparams.append(bindparam("patient_ids", expanding=True))

    with SessionLocal() as db:
        patients = [dict(row) for row in db.execute(
            text(
                f"""
                select patient_id, display_name, age_years, sex
                from {table("patient")}
                {patient_filter}
                """
            ).bindparams(*patient_bindparams),
            patient_parameters,
        ).mappings().all()]
        categories = [dict(row) for row in db.execute(
            text(
                f"""
                select prescription_category_id, category_name, display_order, is_active
                from {table("prescription_category")}
                """
            )
        ).mappings().all()]
        medications = [dict(row) for row in db.execute(
            text(
                f"""
                select pm.prescription_medication_id,
                       p.patient_id,
                       pc.category_name,
                       pm.product_code,
                       pm.item_seq,
                       pm.entered_drug_name,
                       pm.duration_days,
                       pm.doses_per_day,
                       pm.dose_amount,
                       pm.dose_unit,
                       pm.status
                from {table("prescription_medication")} pm
                join {table("prescription")} p on p.prescription_id = pm.prescription_id
                join {table("prescription_category")} pc on pc.prescription_category_id = p.prescription_category_id
                where pm.product_code is not null
                  {medication_patient_filter}
                """
            ).bindparams(*medication_bindparams),
            patient_parameters,
        ).mappings().all()]

    patient_rows = [
        {
            "patientId": int(row["patient_id"]),
            "displayName": row["display_name"],
            "ageYears": int(row["age_years"]) if row["age_years"] is not None else None,
            "sex": row["sex"],
        }
        for row in patients
    ]
    category_rows = [
        {
            "categoryId": int(row["prescription_category_id"]),
            "categoryName": row["category_name"],
            "displayOrder": int(row["display_order"] or 0),
            "isActive": bool(row["is_active"]),
        }
        for row in categories
    ]
    medication_rows = [
        {
            "medicationId": int(row["prescription_medication_id"]),
            "patientId": int(row["patient_id"]),
            "categoryName": row["category_name"],
            "productCode": row["product_code"],
            "itemSeq": row["item_seq"],
            "enteredDrugName": row["entered_drug_name"],
            "durationDays": int(row["duration_days"]) if row["duration_days"] is not None else None,
            "dosesPerDay": float(row["doses_per_day"]) if row["doses_per_day"] is not None else None,
            "doseAmount": float(row["dose_amount"]) if row["dose_amount"] is not None else None,
            "doseUnit": row["dose_unit"],
            "status": row["status"],
        }
        for row in medications
    ]
    return patient_rows, category_rows, medication_rows


def upsert_products(driver, rows: list[dict[str, Any]]) -> int:
    return run_write(
        driver,
        """
        UNWIND $rows AS row
        MERGE (p:Product {productCode: row.product_code})
        SET p.itemSeq = row.item_seq,
            p.productName = row.product_name,
            p.normalizedProductName = row.normalized_product_name,
            p.companyName = row.company_name,
            p.benefitStatus = row.benefit_status
        """,
        rows,
    )


def upsert_ingredient_records(driver, rows: list[dict[str, Any]]) -> int:
    return run_write(
        driver,
        """
        UNWIND $rows AS row
        MERGE (i:Ingredient {ingredientKey: row.ingredientKey})
        SET i.displayName = coalesce(i.displayName, row.displayName),
            i.canonicalName = coalesce(i.canonicalName, row.canonicalName),
            i.ingredientNameKo = coalesce(i.ingredientNameKo, row.ingredientNameKo)
        MERGE (record:IngredientRecord {ingredientId: row.ingredientId})
        SET record.canonicalName = row.canonicalName,
            record.ingredientNameKo = row.ingredientNameKo,
            record.displayName = row.displayName
        MERGE (record)-[:NORMALIZES_TO]->(i)
        """,
        rows,
    )


def upsert_product_ingredient_links(driver, rows: list[dict[str, Any]], relationship_type: str) -> int:
    cypher = f"""
        UNWIND $rows AS row
        MATCH (p:Product {{productCode: row.productCode}})
        MATCH (i:Ingredient {{ingredientKey: row.ingredientKey}})
        MERGE (p)-[r:{relationship_type}]->(i)
        SET r.source = row.source,
            r.ingredientId = row.ingredientId,
            r.ingredientName = row.ingredientName
        """
    return run_write(driver, cypher, rows)


def upsert_product_interactions(driver, rows: list[dict[str, Any]]) -> int:
    return run_write(
        driver,
        """
        UNWIND $rows AS row
        MATCH (a:Product {productCode: row.productCodeA})
        MATCH (b:Product {productCode: row.productCodeB})
        MERGE (rule:ProductInteractionRule {ruleKey: row.ruleKey})
        SET rule.ruleId = row.ruleId,
            rule.message = row.message,
            rule.severity = 'RISK'
        MERGE (a)-[rel:PRODUCT_INTERACTS_WITH {ruleKey: row.ruleKey}]->(b)
        SET rel.ruleId = row.ruleId,
            rel.message = row.message,
            rel.severity = 'RISK'
        MERGE (rule)-[:FROM_PRODUCT]->(a)
        MERGE (rule)-[:TO_PRODUCT]->(b)
        """,
        rows,
    )


def upsert_ingredient_interactions(driver, rows: list[dict[str, Any]]) -> int:
    return run_write(
        driver,
        """
        UNWIND $rows AS row
        MATCH (a:Ingredient {ingredientKey: row.ingredientKeyA})
        MATCH (b:Ingredient {ingredientKey: row.ingredientKeyB})
        MERGE (rule:IngredientInteractionRule {ruleKey: row.ruleKey})
        SET rule.ruleId = row.ruleId,
            rule.message = row.message,
            rule.severity = 'RISK',
            rule.ingredientNameA = row.ingredientNameA,
            rule.ingredientNameB = row.ingredientNameB
        MERGE (a)-[rel:INGREDIENT_INTERACTS_WITH {ruleKey: row.ruleKey}]->(b)
        SET rel.ruleId = row.ruleId,
            rel.message = row.message,
            rel.severity = 'RISK'
        MERGE (rule)-[:FROM_INGREDIENT]->(a)
        MERGE (rule)-[:TO_INGREDIENT]->(b)
        """,
        rows,
    )


def upsert_product_safety_rules(driver, rows: list[dict[str, Any]]) -> int:
    return run_write(
        driver,
        """
        UNWIND $rows AS row
        MATCH (p:Product {productCode: row.productCode})
        MERGE (rule:SafetyRule {ruleKey: row.ruleKey})
        SET rule.ruleId = row.ruleId,
            rule.scope = row.scope,
            rule.ruleType = row.ruleType,
            rule.pregnancyGrade = row.pregnancyGrade,
            rule.ageValue = row.ageValue,
            rule.ageUnit = row.ageUnit,
            rule.ageCondition = row.ageCondition,
            rule.maxDailyDoseText = row.maxDailyDoseText,
            rule.maxDailyDoseValue = row.maxDailyDoseValue,
            rule.maxDurationDays = row.maxDurationDays,
            rule.detailInfo = row.detailInfo,
            rule.remark = row.remark
        MERGE (p)-[:HAS_SAFETY_RULE]->(rule)
        """,
        rows,
    )


def upsert_ingredient_safety_rules(driver, rows: list[dict[str, Any]]) -> int:
    return run_write(
        driver,
        """
        UNWIND $rows AS row
        MATCH (i:Ingredient {ingredientKey: row.ingredientKey})
        MERGE (rule:SafetyRule {ruleKey: row.ruleKey})
        SET rule.ruleId = row.ruleId,
            rule.scope = row.scope,
            rule.ruleType = row.ruleType,
            rule.ageBaseText = row.ageBaseText,
            rule.maxQuantityText = row.maxQuantityText,
            rule.maxDurationText = row.maxDurationText,
            rule.prohibitedContent = row.prohibitedContent,
            rule.remark = row.remark
        MERGE (i)-[:HAS_SAFETY_RULE]->(rule)
        """,
        rows,
    )


def upsert_patients_and_medications(
    driver,
    patients: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    medications: list[dict[str, Any]],
) -> tuple[int, int, int]:
    patient_count = run_write(
        driver,
        """
        UNWIND $rows AS row
        MERGE (p:Patient {patientId: row.patientId})
        SET p.displayName = row.displayName,
            p.ageYears = row.ageYears,
            p.sex = row.sex
        """,
        patients,
    )
    category_count = run_write(
        driver,
        """
        UNWIND $rows AS row
        MERGE (c:PrescriptionCategory {categoryName: row.categoryName})
        SET c.categoryId = row.categoryId,
            c.displayOrder = row.displayOrder,
            c.isActive = row.isActive
        """,
        categories,
    )
    medication_count = run_write(
        driver,
        """
        UNWIND $rows AS row
        MATCH (patient:Patient {patientId: row.patientId})
        MATCH (product:Product {productCode: row.productCode})
        MERGE (med:Medication {medicationId: row.medicationId})
        SET med.enteredDrugName = row.enteredDrugName,
            med.categoryName = row.categoryName,
            med.itemSeq = row.itemSeq,
            med.durationDays = row.durationDays,
            med.dosesPerDay = row.dosesPerDay,
            med.doseAmount = row.doseAmount,
            med.doseUnit = row.doseUnit,
            med.status = row.status
        MERGE (patient)-[:TAKES]->(med)
        MERGE (med)-[:USES_PRODUCT]->(product)
        WITH med, row
        MATCH (category:PrescriptionCategory {categoryName: row.categoryName})
        MERGE (med)-[:IN_CATEGORY]->(category)
        """,
        medications,
    )
    return patient_count, category_count, medication_count


def graph_counts(driver) -> list[dict[str, Any]]:
    config = neo4j_config()
    with driver.session(database=config["database"]) as session:
        rows = session.run(
            """
            MATCH (n)
            WHERE any(label IN labels(n) WHERE label IN $labels)
            UNWIND labels(n) AS label
            WITH label, count(*) AS count
            WHERE label IN $labels
            RETURN label, count
            ORDER BY label
            """,
            labels=GRAPH_LABELS,
        ).data()
    return rows


def fetch_scoped_product_codes(patient_ids: list[int]) -> set[str]:
    if not patient_ids:
        return set()
    with SessionLocal() as db:
        rows = db.execute(
            text(
                f"""
                select distinct pm.product_code
                from {table("prescription_medication")} pm
                join {table("prescription")} p on p.prescription_id = pm.prescription_id
                where p.patient_id in :patient_ids
                  and pm.status = 'ACTIVE'
                  and pm.product_code is not null
                """
            ).bindparams(bindparam("patient_ids", expanding=True)),
            {"patient_ids": patient_ids},
        ).scalars().all()
    return {str(row) for row in rows}


def load_graph(
    driver,
    *,
    reset: bool = False,
    include_patients: bool = True,
    patient_scope_ids: list[int] | None = None,
) -> dict[str, int]:
    if reset:
        reset_graph(driver)

    create_constraints(driver)

    scoped_product_codes = fetch_scoped_product_codes(patient_scope_ids or []) if patient_scope_ids else None
    products = fetch_products(scoped_product_codes)
    ingredient_records = fetch_ingredient_records()
    direct_links = fetch_direct_product_ingredients(scoped_product_codes)
    inferred_links = fetch_inferred_product_ingredients(scoped_product_codes)
    product_interactions = fetch_product_interactions(scoped_product_codes)
    ingredient_interactions = fetch_ingredient_interactions()
    product_safety_rules = fetch_product_safety_rules(scoped_product_codes)
    ingredient_safety_rules = fetch_ingredient_safety_rules()

    stats: dict[str, int] = {}

    def run_stage(key: str, label: str, func, *args) -> None:
        print(f"Loading {label}...", flush=True)
        stats[key] = func(*args)
        print(f"Loaded {label}: {stats[key]}", flush=True)

    run_stage("products", "products", upsert_products, driver, products)
    run_stage("ingredient_records", "ingredient records", upsert_ingredient_records, driver, ingredient_records)
    run_stage(
        "direct_product_ingredients",
        "direct product ingredients",
        upsert_product_ingredient_links,
        driver,
        direct_links,
        "HAS_INGREDIENT",
    )
    run_stage(
        "inferred_product_ingredients",
        "inferred product ingredients",
        upsert_product_ingredient_links,
        driver,
        inferred_links,
        "INFERRED_INGREDIENT",
    )
    run_stage("product_interactions", "product interactions", upsert_product_interactions, driver, product_interactions)
    run_stage(
        "ingredient_interactions",
        "ingredient interactions",
        upsert_ingredient_interactions,
        driver,
        ingredient_interactions,
    )
    run_stage("product_safety_rules", "product safety rules", upsert_product_safety_rules, driver, product_safety_rules)
    run_stage(
        "ingredient_safety_rules",
        "ingredient safety rules",
        upsert_ingredient_safety_rules,
        driver,
        ingredient_safety_rules,
    )

    if include_patients:
        patients, categories, medications = fetch_patients_and_medications(patient_scope_ids)
        print("Loading patients, categories, and medications...", flush=True)
        patient_count, category_count, medication_count = upsert_patients_and_medications(
            driver,
            patients,
            categories,
            medications,
        )
        print(
            f"Loaded patients: {patient_count}, categories: {category_count}, medications: {medication_count}",
            flush=True,
        )
        stats.update(
            {
                "patients": patient_count,
                "categories": category_count,
                "medications": medication_count,
            }
        )

    return stats


def print_stats(title: str, rows: Iterable[dict[str, Any]]) -> None:
    print(title)
    for row in rows:
        print(f"  {row}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load Yakson PostgreSQL DUR data into Neo4j AuraDB.")
    parser.add_argument(
        "--reset-yakson-graph",
        action="store_true",
        help="Delete nodes with Yakson graph labels before loading. This is intentionally opt-in.",
    )
    parser.add_argument(
        "--skip-patients",
        action="store_true",
        help="Load product/ingredient/rule graph only, without patient medication nodes.",
    )
    parser.add_argument(
        "--patient-id-scope",
        type=int,
        action="append",
        default=None,
        help="Load only products and patient medication nodes needed for this patient. Repeat for multiple patients.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    driver = make_verified_driver()
    config = neo4j_config()
    try:
        print(f"Connected to Neo4j database '{config['database']}'.")
        stats = load_graph(
            driver,
            reset=args.reset_yakson_graph,
            include_patients=not args.skip_patients,
            patient_scope_ids=args.patient_id_scope,
        )
        print_stats("Loaded rows", [stats])
        print_stats("Graph node counts", graph_counts(driver))
    finally:
        driver.close()


if __name__ == "__main__":
    main()
