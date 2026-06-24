import {
  AnalysisAlert,
  AnalysisReport,
  AnalyzeRequest,
  DrugSearchItem,
  MedicationResult
} from "./types";

const catalog = [
  {
    productCode: "DEMO-ASPIRIN-100",
    itemSeq: "DEMO-ITEM-ASPIRIN",
    productName: "아스피린 100mg",
    companyName: "Demo Pharma",
    ingredientNames: ["Aspirin"],
    aliases: ["아스피린", "aspirin"]
  },
  {
    productCode: "DEMO-CLOPIDOGREL-75",
    itemSeq: "DEMO-ITEM-CLOPIDOGREL",
    productName: "클로피도그렐 75mg",
    companyName: "Demo Pharma",
    ingredientNames: ["Clopidogrel"],
    aliases: ["클로피도그렐", "clopidogrel", "플라빅스"]
  },
  {
    productCode: "DEMO-ZOLPIDEM-10",
    itemSeq: "DEMO-ITEM-ZOLPIDEM",
    productName: "졸피뎀 10mg",
    companyName: "Demo Pharma",
    ingredientNames: ["Zolpidem"],
    aliases: ["졸피뎀", "zolpidem"]
  },
  {
    productCode: "DEMO-METFORMIN-500",
    itemSeq: "DEMO-ITEM-METFORMIN",
    productName: "메트포르민 500mg",
    companyName: "Demo Pharma",
    ingredientNames: ["Metformin"],
    aliases: ["메트포르민", "metformin"]
  },
  {
    productCode: "DEMO-GLIMEPIRIDE-2",
    itemSeq: "DEMO-ITEM-GLIMEPIRIDE",
    productName: "글리메피리드 2mg",
    companyName: "Demo Pharma",
    ingredientNames: ["Glimepiride"],
    aliases: ["글리메피리드", "glimepiride"]
  }
];

function id(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID().replaceAll("-", "").slice(0, 24)}`;
  }
  return `${prefix}_${Math.random().toString(16).slice(2, 26)}`;
}

function normalize(value: string) {
  return value.trim().toLowerCase().replaceAll(" ", "");
}

function matchDrug(enteredDrugName: string) {
  const normalized = normalize(enteredDrugName);
  return catalog.find((drug) => {
    const aliases = drug.aliases.map(normalize);
    const productName = normalize(drug.productName);
    return (
      productName.includes(normalized) ||
      aliases.some((alias) => normalized.includes(alias) || alias.includes(normalized))
    );
  });
}

export function searchMockDrugs(query: string): DrugSearchItem[] {
  const normalized = normalize(query);
  if (!normalized) {
    return [];
  }

  return catalog
    .filter((drug) => {
      const aliases = drug.aliases.map(normalize);
      return (
        normalize(drug.productName).includes(normalized) ||
        aliases.some((alias) => normalized.includes(alias) || alias.includes(normalized))
      );
    })
    .slice(0, 8)
    .map((drug) => ({
      productCode: drug.productCode,
      itemSeq: drug.itemSeq,
      productName: drug.productName,
      companyName: drug.companyName,
      ingredientNames: drug.ingredientNames,
      matchScore: 0.98
    }));
}

export function buildMockReport(payload: AnalyzeRequest, reportId = id("rep")): AnalysisReport {
  const medications: MedicationResult[] = payload.medications.map((medication) => {
    const matched = matchDrug(medication.enteredDrugName);
    return {
      enteredDrugName: medication.enteredDrugName,
      matchedProductName: matched?.productName ?? null,
      matchStatus: matched ? "MATCHED" : "UNMATCHED"
    };
  });

  const matchedNames = medications
    .map((medication) => medication.matchedProductName)
    .filter((value): value is string => Boolean(value));

  const alerts = buildAlerts(payload, medications, matchedNames);
  const alerted = new Set(alerts.flatMap((alert) => alert.relatedMedications.map(normalize)));
  const normalCount = medications.filter(
    (medication) =>
      medication.matchStatus === "MATCHED" &&
      medication.matchedProductName &&
      !alerted.has(normalize(medication.matchedProductName))
  ).length;

  const riskCount = alerts.filter((alert) => alert.severity === "RISK").length;
  const cautionCount = alerts.filter((alert) => alert.severity === "CAUTION").length;
  const unmatchedMedicationCount = medications.filter(
    (medication) => medication.matchStatus === "UNMATCHED"
  ).length;

  return {
    reportId,
    generatedAt: new Date().toISOString(),
    patient: payload.patient,
    summary: {
      riskCount,
      cautionCount,
      normalCount,
      unmatchedMedicationCount
    },
    medications,
    alerts,
    caregiverGuidance:
      "이 리포트는 진단이나 처방이 아닌 복약 안전 참고자료입니다. 위험 항목은 약사 또는 의사에게 상담해 주세요.",
    pharmacistHandoffText: `${payload.patient.displayName} / ${
      payload.patient.ageYears ?? "나이 미입력"
    }세 / 입력 약물 ${medications.length}개 / 위험 ${riskCount}건, 주의 ${cautionCount}건`
  };
}

export function buildDemoReport() {
  return buildMockReport(
    {
      patient: {
        displayName: "홍길순 할머니",
        ageYears: 78,
        sex: "FEMALE"
      },
      medications: [
        { enteredDrugName: "아스피린 100mg" },
        { enteredDrugName: "클로피도그렐" },
        { enteredDrugName: "졸피뎀 10mg" },
        { enteredDrugName: "메트포르민 500mg" },
        { enteredDrugName: "글리메피리드" }
      ]
    },
    "demo-latest"
  );
}

function buildAlerts(
  payload: AnalyzeRequest,
  medications: MedicationResult[],
  matchedNames: string[]
): AnalysisAlert[] {
  const alerts: AnalysisAlert[] = [];
  const hasAspirin = matchedNames.some((name) => /아스피린|aspirin/i.test(name));
  const hasClopidogrel = matchedNames.some((name) => /클로피도그렐|clopidogrel/i.test(name));
  const hasZolpidem = matchedNames.some((name) => /졸피뎀|zolpidem/i.test(name));
  const hasMetformin = matchedNames.some((name) => /메트포르민|metformin/i.test(name));
  const hasGlimepiride = matchedNames.some((name) => /글리메피리드|glimepiride/i.test(name));

  if (hasZolpidem && (payload.patient.ageYears ?? 0) >= 65) {
    alerts.push({
      alertId: id("alt"),
      severity: "RISK",
      ruleType: "ELDERLY_CAUTION",
      title: "노인 부적절 약물(PIM)",
      message: "졸피뎀은 어르신에게 낙상과 섬망 위험을 높일 수 있어 약사 상담을 권장해요.",
      relatedMedications: ["졸피뎀 10mg"],
      evidence: [
        {
          sourceType: "DUR",
          sourceName: "식약처 DUR 노인주의",
          sourceRecordId: "product_safety_rule:demo-zolpidem-elderly",
          description: "노인주의 제품 안전성 규칙"
        }
      ],
      routeToProfessional: true
    });
  }

  if (hasAspirin && hasClopidogrel) {
    alerts.push({
      alertId: id("alt"),
      severity: "RISK",
      ruleType: "PRODUCT_INTERACTION",
      title: "병용금기/주의",
      message: "두 약을 함께 복용하면 출혈 위험이 높아질 수 있어 복용 목적과 기간을 확인해야 해요.",
      relatedMedications: ["아스피린 100mg", "클로피도그렐 75mg"],
      evidence: [
        {
          sourceType: "DUR",
          sourceName: "식약처 DUR 병용금기",
          sourceRecordId: "product_interaction_rule:demo-aspirin-clopidogrel",
          description: "제품 병용 주의 규칙"
        }
      ],
      routeToProfessional: true
    });
  }

  if (hasMetformin && hasGlimepiride) {
    alerts.push({
      alertId: id("alt"),
      severity: "CAUTION",
      ruleType: "DUPLICATE_EFFICACY",
      title: "동일 효능 중복",
      message: "비슷한 혈당 조절 목적의 약이 함께 있어 저혈당 증상 여부를 확인하면 좋아요.",
      relatedMedications: ["메트포르민 500mg", "글리메피리드 2mg"],
      evidence: [
        {
          sourceType: "DUR",
          sourceName: "효능군 중복 점검",
          sourceRecordId: "efficacy_group_member:demo-diabetes",
          description: "효능군 기반 중복 규칙"
        }
      ],
      routeToProfessional: false
    });
  }

  for (const medication of medications) {
    if (medication.matchStatus !== "UNMATCHED") {
      continue;
    }

    alerts.push({
      alertId: id("alt"),
      severity: "CAUTION",
      ruleType: "MATCHING_REVIEW",
      title: "약물명 확인 필요",
      message: "공식 약물 마스터와 매칭하지 못했어요. 약봉투나 처방전의 정확한 이름을 확인해 주세요.",
      relatedMedications: [medication.enteredDrugName],
      evidence: [
        {
          sourceType: "DUR",
          sourceName: "약물 마스터 매칭",
          sourceRecordId: "drug_match:unmatched",
          description: "제품코드 매칭 실패"
        }
      ],
      routeToProfessional: false
    });
  }

  return alerts;
}
