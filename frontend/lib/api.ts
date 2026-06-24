import {
  AnalysisReport,
  AnalysisReportHistoryItem,
  AnalyzeRequest,
  DrugSearchItem,
  MedicationCreateInput,
  MedicationRecord,
  MedicationUpdateInput,
  PatientCreateInput,
  PatientRecord,
  PatientUpdateInput,
  PrescriptionCategory
} from "./types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type ApiPatient = {
  id: string;
  patientId: number;
  displayName: string;
  ageYears: number;
  sex: PatientRecord["sex"];
  createdAt: string;
  updatedAt: string;
};

type ApiMedication = {
  id: string;
  medicationId: number;
  prescriptionId: number;
  patientId: number;
  categoryName: PrescriptionCategory;
  enteredDrugName: string;
  matchedProductName?: string | null;
  companyName?: string | null;
  durationDays: number;
  dosesPerDay: number | string;
  doseAmount: number | string;
  doseUnit: string;
  prescribedOn?: string | null;
  memo?: string | null;
  productCode?: string | null;
  itemSeq?: string | null;
  matchStatus: string;
  status: string;
  createdAt: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    const contentType = response.headers.get("content-type") ?? "";

    if (contentType.includes("application/json")) {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        message = body.detail;
      }
    } else {
      const detail = await response.text();
      if (detail) {
        message = detail;
      }
    }

    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function analyzeMedication(payload: AnalyzeRequest) {
  return request<AnalysisReport>("/api/analyze", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function previewAnalysis(payload: AnalyzeRequest) {
  return request<AnalysisReport>("/api/analysis/preview", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function runAndSaveLatestAnalysis(patientId: string) {
  return request<AnalysisReport>(`/api/patients/${patientId}/analysis/latest`, {
    method: "POST"
  });
}

export async function fetchLatestAnalysis(patientId: string) {
  try {
    return await request<AnalysisReport>(`/api/patients/${patientId}/analysis/latest`);
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 404) {
      return null;
    }
    throw caught;
  }
}

export async function fetchAnalysisHistory(patientId: string, limit = 20) {
  const result = await request<{ items: AnalysisReportHistoryItem[] }>(
    `/api/patients/${patientId}/analysis/reports?limit=${limit}`
  );
  return result.items;
}

export function fetchAnalysisReport(patientId: string, analysisRunId: number) {
  return request<AnalysisReport>(`/api/patients/${patientId}/analysis/reports/${analysisRunId}`);
}

export function fetchReport(reportId: string) {
  return request<AnalysisReport>(`/api/reports/${reportId}`);
}

export async function searchDrugs(query: string, limit = 15) {
  if (query.trim().length < 2) {
    return [];
  }

  const result = await request<{ items: DrugSearchItem[] }>(
    `/api/drugs/search?q=${encodeURIComponent(query)}&limit=${limit}`
  );
  return result.items;
}

export function validateDrug(productCode: string, itemSeq?: string | null) {
  const params = new URLSearchParams();
  params.set("productCode", productCode);
  if (itemSeq) {
    params.set("itemSeq", itemSeq);
  }
  return request<DrugSearchItem>(`/api/drugs/validate?${params.toString()}`);
}

function toPatientRecord(patient: ApiPatient): PatientRecord {
  return {
    id: patient.id,
    displayName: patient.displayName,
    ageYears: patient.ageYears,
    sex: patient.sex,
    createdAt: patient.createdAt,
    updatedAt: patient.updatedAt
  };
}

function toMedicationRecord(medication: ApiMedication): MedicationRecord {
  return {
    id: medication.id,
    patientId: String(medication.patientId),
    category: medication.categoryName,
    enteredDrugName: medication.enteredDrugName,
    matchedProductName: medication.matchedProductName ?? medication.enteredDrugName,
    productCode: medication.productCode,
    itemSeq: medication.itemSeq,
    companyName: medication.companyName,
    durationDays: medication.durationDays,
    dosesPerDay: Number(medication.dosesPerDay),
    doseAmount: Number(medication.doseAmount),
    doseUnit: medication.doseUnit,
    status: medication.status,
    createdAt: medication.createdAt
  };
}

export async function listPatients() {
  const result = await request<{ items: ApiPatient[] }>("/api/patients");
  return result.items.map(toPatientRecord);
}

export async function getPatientById(patientId: string) {
  const patient = await request<ApiPatient>(`/api/patients/${patientId}`);
  return toPatientRecord(patient);
}

export async function createPatientOnServer(payload: PatientCreateInput) {
  const patient = await request<ApiPatient>("/api/patients", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return toPatientRecord(patient);
}

export async function updatePatientOnServer(patientId: string, payload: PatientUpdateInput) {
  const patient = await request<ApiPatient>(`/api/patients/${patientId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
  return toPatientRecord(patient);
}

export async function deletePatientOnServer(patientId: string) {
  await request<void>(`/api/patients/${patientId}`, {
    method: "DELETE"
  });
}

export async function listPatientMedications(patientId: string) {
  const result = await request<{ items: ApiMedication[] }>(`/api/patients/${patientId}/medications`);
  return result.items.map(toMedicationRecord);
}

export async function createMedicationOnServer(patientId: string, payload: MedicationCreateInput) {
  const medication = await request<ApiMedication>(`/api/patients/${patientId}/medications`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return toMedicationRecord(medication);
}

export async function updateMedicationOnServer(medicationId: string, payload: MedicationUpdateInput) {
  const medication = await request<ApiMedication>(`/api/medications/${medicationId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
  return toMedicationRecord(medication);
}

export async function deleteMedicationOnServer(medicationId: string) {
  await request<void>(`/api/medications/${medicationId}`, {
    method: "DELETE"
  });
}
