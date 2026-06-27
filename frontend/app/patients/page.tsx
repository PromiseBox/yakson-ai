"use client";

import { AlertCircle, Database, Pencil, Plus, Trash2, User } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { AppShell, EmptyState, LoadingState } from "@/components/AppShell";
import {
  YkButton,
  YkCard,
  YkErrorState,
  YkInlineAlert,
  YkNoticeBox,
  YkStatusPill
} from "@/components/ui/design-system";
import { sexLabel } from "@/lib/app-store";
import {
  createPatientOnServer,
  deletePatientOnServer,
  fetchAnalysisHistory,
  listPatientMedications,
  listPatients,
  updatePatientOnServer
} from "@/lib/api";
import { toUserErrorMessage } from "@/lib/error-messages";
import { PatientRecord, Sex } from "@/lib/types";

type SheetMode = "add" | "edit" | null;

export default function PatientsPage() {
  const [patients, setPatients] = useState<PatientRecord[]>([]);
  const [medicationCounts, setMedicationCounts] = useState<Record<string, number>>({});
  const [latestAnalysisDates, setLatestAnalysisDates] = useState<Record<string, string | null>>({});
  const [mode, setMode] = useState<SheetMode>(null);
  const [selectedPatient, setSelectedPatient] = useState<PatientRecord | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PatientRecord | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [ageYears, setAgeYears] = useState("");
  const [sex, setSex] = useState<Sex>("FEMALE");
  const [error, setError] = useState("");
  const [pageError, setPageError] = useState("");
  const [notice, setNotice] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    void refreshPatients();
  }, []);

  useEffect(() => {
    if (!notice) {
      return;
    }

    const timer = window.setTimeout(() => setNotice(""), 3500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  async function refreshPatients() {
    setIsLoading(true);
    setPageError("");
    try {
      const nextPatients = await listPatients();
      setPatients(nextPatients);
      const rows = await Promise.all(
        nextPatients.map(async (patient) => {
          const [medications, history] = await Promise.all([
            listPatientMedications(patient.id),
            fetchAnalysisHistory(patient.id, 1)
          ]);
          return {
            id: patient.id,
            medicationCount: medications.length,
            latestAnalysisAt: history[0]?.createdAt ?? null
          };
        })
      );
      setMedicationCounts(Object.fromEntries(rows.map((row) => [row.id, row.medicationCount])));
      setLatestAnalysisDates(Object.fromEntries(rows.map((row) => [row.id, row.latestAnalysisAt])));
    } catch (caught) {
      setPageError(toUserErrorMessage(caught, "복용자 목록을 불러오지 못했습니다."));
    } finally {
      setIsLoading(false);
    }
  }

  function openAddSheet() {
    setSelectedPatient(null);
    setDisplayName("");
    setAgeYears("");
    setSex("FEMALE");
    setError("");
    setNotice("");
    setMode("add");
  }

  function openEditSheet(patient: PatientRecord) {
    setSelectedPatient(patient);
    setDisplayName(patient.displayName);
    setAgeYears(String(patient.ageYears));
    setSex(patient.sex);
    setError("");
    setNotice("");
    setMode("edit");
  }

  function closeSheet() {
    if (isSaving) {
      return;
    }
    setMode(null);
    setSelectedPatient(null);
    setError("");
  }

  async function submitPatient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!mode) {
      return;
    }

    const trimmedName = displayName.trim();
    const parsedAge = Number(ageYears);
    if (!trimmedName || !ageYears || Number.isNaN(parsedAge) || parsedAge <= 0) {
      setError("성명, 나이, 성별을 모두 입력해주세요.");
      return;
    }

    setIsSaving(true);
    setError("");
    setNotice("");
    try {
      if (mode === "add") {
        await createPatientOnServer({ displayName: trimmedName, ageYears: parsedAge, sex });
        setNotice("복용자를 저장했습니다.");
      } else if (selectedPatient) {
        await updatePatientOnServer(selectedPatient.id, { displayName: trimmedName, ageYears: parsedAge, sex });
        setNotice("복용자 정보를 수정했습니다.");
      }
      setMode(null);
      setSelectedPatient(null);
      await refreshPatients();
    } catch (caught) {
      setError(toUserErrorMessage(caught, "복용자 정보를 저장하지 못했습니다."));
    } finally {
      setIsSaving(false);
    }
  }

  async function deletePatient() {
    if (!deleteTarget) {
      return;
    }

    setIsSaving(true);
    setPageError("");
    setNotice("");
    try {
      await deletePatientOnServer(deleteTarget.id);
      setNotice("복용자를 삭제했습니다.");
      setDeleteTarget(null);
      await refreshPatients();
    } catch (caught) {
      setPageError(toUserErrorMessage(caught, "복용자를 삭제하지 못했습니다."));
    } finally {
      setIsSaving(false);
    }
  }

  const action = (
    <YkButton icon={Plus} type="button" onClick={openAddSheet}>
      복용자 추가
    </YkButton>
  );

  return (
    <AppShell title="복용자 관리" subtitle="입력 - DB 저장 목록" action={action}>
      {isLoading && <LoadingState />}
      {pageError && <YkErrorState title="복용자 목록을 불러오지 못했습니다" description={pageError} />}
      {notice && (
        <YkInlineAlert title="저장 완료" tone="safe">
          {notice}
        </YkInlineAlert>
      )}

      {!isLoading && (
        <YkNoticeBox title="약품 데이터베이스 안내" tone="brand" icon={Database}>
          약품은 식약처 기반 데이터베이스에서 확인된 품목을 검색해 선택할 수 있습니다.
        </YkNoticeBox>
      )}

      {!isLoading && patients.length === 0 && (
        <EmptyState
          title="등록된 복용자가 없습니다"
          description="복용자를 추가한 뒤 약 정보 입력 화면에서 식약처 DB 검색 결과를 선택해주세요."
          action={
            <YkButton icon={Plus} type="button" onClick={openAddSheet}>
              복용자 추가
            </YkButton>
          }
        />
      )}

      {!isLoading && patients.length > 0 && (
        <div className="cardGrid">
          {patients.map((patient) => (
            <PatientCard
              key={patient.id}
              latestAnalysisAt={latestAnalysisDates[patient.id] ?? null}
              medicationCount={medicationCounts[patient.id] ?? 0}
              patient={patient}
              onEdit={() => openEditSheet(patient)}
              onDelete={() => setDeleteTarget(patient)}
            />
          ))}
        </div>
      )}

      {mode && (
        <div className="modalBackdrop" role="dialog" aria-modal="true">
          <form className="sheet" onSubmit={submitPatient}>
            <div className="sheetHeader">
              <div>
                <h2>{mode === "add" ? "복용자 추가" : "복용자 수정"}</h2>
                <p className="subtext">
                  {mode === "add"
                    ? "성명, 나이, 성별을 입력하면 DB에 저장됩니다."
                    : "성명, 나이, 성별을 수정하면 DB에 반영됩니다."}
                </p>
              </div>
              <button className="closeButton" type="button" onClick={closeSheet} aria-label="닫기">
                x
              </button>
            </div>

            <div className="stack">
              <label className="fieldLabel">
                성명
                <input
                  className="input"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="예: 홍길순 할머니"
                />
              </label>

              <label className="fieldLabel">
                나이
                <input
                  className="input"
                  value={ageYears}
                  onChange={(event) => setAgeYears(event.target.value.replace(/[^0-9]/g, ""))}
                  inputMode="numeric"
                  placeholder="예: 78"
                />
              </label>

              <div className="fieldLabel">
                성별
                <div className="segmented">
                  {[
                    ["FEMALE", "여성"],
                    ["MALE", "남성"],
                    ["UNKNOWN", "미입력"]
                  ].map(([value, label]) => (
                    <button
                      className={`segment ${sex === value ? "selected" : ""}`}
                      key={value}
                      type="button"
                      onClick={() => setSex(value as Sex)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {error && <p className="error">{error}</p>}

            <div className="sheetActions">
              <button className="button secondary" type="button" onClick={closeSheet} disabled={isSaving}>
                취소
              </button>
              <button className="button primary" type="submit" disabled={isSaving}>
                {isSaving ? "저장 중" : "저장"}
              </button>
            </div>
          </form>
        </div>
      )}

      {deleteTarget && (
        <div className="modalBackdrop" role="alertdialog" aria-modal="true">
          <div className="sheet">
            <div className="sheetHeader">
              <div>
                <h2>복용자 삭제</h2>
                <p className="subtext">
                  이 복용자와 연결된 약물, 분석 이력이 함께 삭제됩니다. 삭제 후에는 되돌릴 수 없습니다.
                </p>
              </div>
              <button
                className="closeButton"
                type="button"
                onClick={() => setDeleteTarget(null)}
                aria-label="닫기"
                disabled={isSaving}
              >
                x
              </button>
            </div>
            <div className="sheetActions">
              <button
                className="button secondary"
                type="button"
                onClick={() => setDeleteTarget(null)}
                disabled={isSaving}
              >
                취소
              </button>
              <button className="button danger" type="button" onClick={deletePatient} disabled={isSaving}>
                {isSaving ? "삭제 중" : "삭제 확인"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}

function PatientCard({
  patient,
  latestAnalysisAt,
  medicationCount,
  onEdit,
  onDelete
}: {
  patient: PatientRecord;
  latestAnalysisAt: string | null;
  medicationCount: number;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const canAnalyze = medicationCount > 0;

  return (
    <YkCard className="yk-product-patient-card">
      <div className="yk-card-head-row">
        <div className="yk-avatar-row">
          <span className="yk-avatar">
            <User size={18} />
          </span>
          <div>
            <strong>{patient.displayName}</strong>
            <div className="yk-product-meta">
              <span>{patient.ageYears}세</span>
              <span>{sexLabel(patient.sex)}</span>
              <span>분석 목록 {medicationCount}개</span>
            </div>
          </div>
        </div>
        <YkStatusPill tone={canAnalyze ? "safe" : "caution"}>{canAnalyze ? "분석 가능" : "약물 선택 필요"}</YkStatusPill>
      </div>

      <div className="yk-product-meta">
        <span>최근 수정 {new Date(patient.updatedAt).toLocaleDateString("ko-KR")}</span>
        <span>마지막 분석 {formatDateTime(latestAnalysisAt)}</span>
      </div>

      <div className="yk-card-meta">
        <div className="yk-component-row">
          <YkButton className="yk-button-compact" icon={Pencil} variant="secondary" type="button" onClick={onEdit}>
            수정
          </YkButton>
          <YkButton className="yk-button-compact" icon={Trash2} variant="danger" type="button" onClick={onDelete}>
            삭제
          </YkButton>
        </div>
        <Link className="yk-button yk-button-primary yk-button-compact" href={`/patients/${patient.id}/medications`}>
          약 입력
        </Link>
      </div>
    </YkCard>
  );
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "없음";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}
