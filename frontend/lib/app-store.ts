import { buildMockReport } from "./mock";
import {
  AnalysisReport,
  AppData,
  DietGuide,
  DrugSearchItem,
  ExerciseGuide,
  MedicationRecord,
  PatientRecord,
  PrescriptionCategory,
  Sex
} from "./types";

const STORAGE_KEY = "yakson-ai-readonly-preview-v2";

export const prescriptionCategories: PrescriptionCategory[] = [
  "정형외과",
  "내과",
  "외과",
  "성인병약",
  "당뇨약",
  "수면/신경안정",
  "기타"
];

export function createId(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID().replaceAll("-", "").slice(0, 18)}`;
  }

  return `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

export function nowIso() {
  return new Date().toISOString();
}

export function sexLabel(sex: Sex) {
  if (sex === "FEMALE") {
    return "여성";
  }
  if (sex === "MALE") {
    return "남성";
  }
  return "미입력";
}

export function createSeedData(): AppData {
  const createdAt = nowIso();
  return {
    patients: [
      {
        id: "patient_hong",
        displayName: "홍길순 할머니",
        ageYears: 78,
        sex: "FEMALE",
        createdAt,
        updatedAt: createdAt
      },
      {
        id: "patient_kim",
        displayName: "김영수 아버지",
        ageYears: 72,
        sex: "MALE",
        createdAt,
        updatedAt: createdAt
      }
    ],
    medications: []
  };
}

export function loadAppData(): AppData {
  if (typeof window === "undefined") {
    return createSeedData();
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    const seed = createSeedData();
    saveAppData(seed);
    return seed;
  }

  try {
    const parsed = JSON.parse(raw) as AppData;
    if (Array.isArray(parsed.patients) && Array.isArray(parsed.medications)) {
      return parsed;
    }
  } catch {
    // Fall through to reset corrupt data.
  }

  const seed = createSeedData();
  saveAppData(seed);
  return seed;
}

export function saveAppData(data: AppData) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

export function createPatient(displayName: string, ageYears: number, sex: Sex): PatientRecord {
  const createdAt = nowIso();
  return {
    id: createId("patient"),
    displayName,
    ageYears,
    sex,
    createdAt,
    updatedAt: createdAt
  };
}

export function createMedication(
  patientId: string,
  category: PrescriptionCategory,
  enteredDrugName: string,
  durationDays: number,
  dosesPerDay: number,
  doseAmount: number,
  doseUnit: string,
  matchedDrug: DrugSearchItem
): MedicationRecord {
  return {
    id: createId("med"),
    patientId,
    category,
    enteredDrugName,
    matchedProductName: matchedDrug.productName,
    productCode: matchedDrug.productCode,
    itemSeq: matchedDrug.itemSeq,
    companyName: matchedDrug.companyName,
    durationDays,
    dosesPerDay,
    doseAmount,
    doseUnit,
    createdAt: nowIso()
  };
}

export function getPatient(data: AppData, patientId: string) {
  return data.patients.find((patient) => patient.id === patientId) ?? null;
}

export function getPatientMedications(data: AppData, patientId: string) {
  return data.medications.filter((medication) => medication.patientId === patientId);
}

export function buildPatientReport(
  patient: PatientRecord,
  medications: MedicationRecord[]
): AnalysisReport {
  return buildMockReport(
    {
      patient: {
        displayName: patient.displayName,
        ageYears: patient.ageYears,
        sex: patient.sex
      },
      medications: medications.map((medication) => ({
        enteredDrugName: medication.enteredDrugName,
        productCode: medication.productCode,
        itemSeq: medication.itemSeq,
        productName: medication.matchedProductName,
        companyName: medication.companyName,
        durationDays: medication.durationDays,
        dosesPerDay: medication.dosesPerDay,
        doseAmount: medication.doseAmount,
        doseUnit: medication.doseUnit
      }))
    },
    `report_${patient.id}`
  );
}

export function groupMedicationsByCategory(medications: MedicationRecord[]) {
  return prescriptionCategories
    .map((category) => ({
      category,
      medications: medications.filter((medication) => medication.category === category)
    }))
    .filter((group) => group.medications.length > 0);
}

export function buildDietGuides(medications: MedicationRecord[]): DietGuide[] {
  if (medications.length === 0) {
    return [
      {
        id: "diet_empty",
        severity: "safe",
        foodName: "복약 정보 없음",
        title: "분석할 약물이 아직 없습니다",
        reason: "식약처 DB에서 선택한 약물을 먼저 추가해야 식생활 안내를 만들 수 있습니다.",
        action: "약 정보 입력 화면에서 자동완성 결과를 선택해 약물을 추가하세요.",
        relatedMedications: [],
        source: "read-only preview"
      }
    ];
  }

  return [
    {
      id: "diet_general",
      severity: "safe",
      foodName: "규칙적인 식사",
      title: "복약 시간과 식사 시간을 일정하게 유지하세요",
      reason: "현재 단계에서는 약물별 식품 상호작용을 저장하지 않고, 선택 약물 기반 안전 분석만 미리보기로 제공합니다.",
      action: "위험 또는 주의 알림이 있는 약은 약사에게 음식 제한 여부를 함께 확인하세요.",
      relatedMedications: medications.map((medication) => medication.matchedProductName ?? medication.enteredDrugName),
      source: "read-only preview"
    }
  ];
}

export function buildExerciseGuides(medications: MedicationRecord[]): ExerciseGuide[] {
  if (medications.length === 0) {
    return [
      {
        id: "exercise_empty",
        severity: "safe",
        activityName: "복약 정보 없음",
        title: "분석할 약물이 아직 없습니다",
        reason: "식약처 DB에서 선택한 약물을 먼저 추가해야 활동 안내를 만들 수 있습니다.",
        action: "약 정보 입력 화면에서 자동완성 결과를 선택해 약물을 추가하세요.",
        relatedMedications: [],
        source: "read-only preview"
      }
    ];
  }

  return [
    {
      id: "exercise_general",
      severity: "safe",
      activityName: "가벼운 걷기",
      title: "어지러움이나 졸림이 있으면 활동 강도를 낮추세요",
      reason: "고령자 주의, 병용 주의 알림이 있는 경우 낙상이나 어지러움 여부를 함께 확인해야 합니다.",
      action: "리포트에 위험 또는 주의가 표시되면 운동 전 약사나 의사에게 상담하세요.",
      relatedMedications: medications.map((medication) => medication.matchedProductName ?? medication.enteredDrugName),
      source: "read-only preview"
    }
  ];
}
