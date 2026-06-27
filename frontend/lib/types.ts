export type Sex = "FEMALE" | "MALE" | "UNKNOWN";
export type AlertSeverity = "RISK" | "CAUTION" | "NORMAL";
export type AnalysisSource = "GRAPH" | "RULE_PREVIEW";
export type MatchStatus = "MATCHED" | "UNMATCHED" | "NEEDS_REVIEW";

export type PatientInput = {
  displayName: string;
  ageYears?: number | null;
  sex: Sex;
};

export type MedicationInput = {
  enteredDrugName: string;
  categoryName?: string | null;
  productCode?: string | null;
  itemSeq?: string | null;
  productName?: string | null;
  companyName?: string | null;
  durationDays?: number | null;
  dosesPerDay?: number | null;
  doseAmount?: number | null;
  doseUnit?: string | null;
};

export type AnalyzeRequest = {
  patient: PatientInput;
  medications: MedicationInput[];
};

export type MedicationResult = {
  enteredDrugName: string;
  matchedProductName?: string | null;
  matchStatus: MatchStatus;
};

export type AlertEvidence = {
  sourceType: string;
  sourceName: string;
  sourceRecordId: string;
  description: string;
};

export type RuleType =
  | "PRODUCT_INTERACTION"
  | "INGREDIENT_INTERACTION"
  | "DUPLICATE_INGREDIENT"
  | "DUPLICATE_EFFICACY"
  | "ELDERLY_CAUTION"
  | "PREGNANCY_CAUTION"
  | "LACTATION_CAUTION"
  | "AGE_CONTRAINDICATION"
  | "DURATION_CAUTION"
  | "DOSAGE_CAUTION"
  | "MATCHING_REVIEW";

export type AnalysisAlert = {
  alertId: string;
  severity: AlertSeverity;
  ruleType: RuleType;
  title: string;
  message: string;
  relatedMedications: string[];
  evidence: AlertEvidence[];
  routeToProfessional: boolean;
};

export type AlertExplanation = {
  alertId: string;
  severity: AlertSeverity;
  ruleType: RuleType;
  title: string;
  relatedMedications: string[];
  plainLanguageReason: string;
  caregiverAction: string;
  professionalQuestion: string;
  evidenceSummary: string;
};

export type AnalysisReport = {
  reportId: string;
  generatedAt: string;
  savedAt?: string | null;
  isStale?: boolean;
  analysisSource?: AnalysisSource;
  patient: PatientInput;
  summary: {
    riskCount: number;
    cautionCount: number;
    normalCount: number;
    unmatchedMedicationCount: number;
    description?: string | null;
  };
  medications: MedicationResult[];
  sourceMedicationSnapshot?: MedicationInput[];
  alerts: AnalysisAlert[];
  caregiverGuidance: string;
  pharmacistHandoffText: string;
  reportSummaryText?: string | null;
  llmSummaryText?: string | null;
  caregiverSummaryText?: string | null;
  pharmacistSummaryText?: string | null;
  caregiverDetailText?: string | null;
  pharmacistDetailText?: string | null;
  recommendedQuestions?: string[];
  alertExplanations?: AlertExplanation[];
  aiSummarySource?: "OPENAI" | "TEMPLATE" | string | null;
  aiModel?: string | null;
  aiPromptVersion?: string | null;
};

export type AnalysisReportHistoryItem = {
  analysisRunId: number;
  patientReportId: number;
  reportId: string;
  createdAt: string;
  isStale: boolean;
  riskCount: number;
  cautionCount: number;
  normalCount: number;
  medicationCount: number;
  alertCount: number;
  isLatest: boolean;
};

export type DrugSearchItem = {
  productCode: string;
  itemSeq: string;
  productName: string;
  companyName: string;
  ingredientNames: string[];
  matchScore: number;
};

export type PrescriptionCategory = string;

export type PatientRecord = {
  id: string;
  displayName: string;
  ageYears: number;
  sex: Sex;
  createdAt: string;
  updatedAt: string;
};

export type MedicationRecord = {
  id: string;
  patientId: string;
  category: PrescriptionCategory;
  enteredDrugName: string;
  matchedProductName?: string | null;
  productCode?: string | null;
  itemSeq?: string | null;
  companyName?: string | null;
  durationDays: number;
  dosesPerDay: number;
  doseAmount: number;
  doseUnit: string;
  status?: string;
  createdAt: string;
};

export type AppData = {
  patients: PatientRecord[];
  medications: MedicationRecord[];
};

export type PatientCreateInput = {
  displayName: string;
  ageYears: number;
  sex: Sex;
};

export type PatientUpdateInput = {
  displayName?: string;
  ageYears?: number;
  sex?: Sex;
};

export type MedicationCreateInput = {
  categoryName: PrescriptionCategory;
  enteredDrugName: string;
  productCode: string;
  itemSeq?: string | null;
  durationDays: number;
  dosesPerDay: number;
  doseAmount: number;
  doseUnit: string;
};

export type MedicationUpdateInput = Partial<MedicationCreateInput> & {
  status?: string;
};

export type GuideSeverity = "avoid" | "caution" | "safe";

export type DietGuide = {
  id: string;
  severity: GuideSeverity;
  foodName: string;
  title: string;
  reason: string;
  action: string;
  relatedMedications: string[];
  source: string;
};

export type ExerciseGuide = {
  id: string;
  severity: GuideSeverity;
  activityName: string;
  title: string;
  reason: string;
  action: string;
  relatedMedications: string[];
  source: string;
};
