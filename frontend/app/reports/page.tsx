"use client";

import { FileText, User } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell, EmptyState, LoadingState } from "@/components/AppShell";
import { YkCard, YkErrorState, YkStatusPill } from "@/components/ui/design-system";
import { sexLabel } from "@/lib/app-store";
import { fetchAnalysisHistory, listPatientMedications, listPatients } from "@/lib/api";
import { toUserErrorMessage } from "@/lib/error-messages";
import { PatientRecord } from "@/lib/types";

type PatientRow = {
  patient: PatientRecord;
  medicationCount: number;
  latestAnalysisAt: string | null;
};

export default function ReportsPage() {
  const [rows, setRows] = useState<PatientRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadRows() {
      setIsLoading(true);
      setError("");
      try {
        const patients = await listPatients();
        const nextRows = await Promise.all(
          patients.map(async (patient) => {
            const [medications, history] = await Promise.all([
              listPatientMedications(patient.id),
              fetchAnalysisHistory(patient.id, 1)
            ]);
            return { patient, medicationCount: medications.length, latestAnalysisAt: history[0]?.createdAt ?? null };
          })
        );
        setRows(nextRows);
      } catch (caught) {
        setError(toUserErrorMessage(caught, "분석 조회 목록을 불러오지 못했습니다."));
      } finally {
        setIsLoading(false);
      }
    }

    void loadRows();
  }, []);

  return (
    <AppShell title="분석 조회" subtitle="조회 - 복용자 선택">
      {isLoading && <LoadingState />}
      {error && <YkErrorState title="분석 조회 목록을 불러오지 못했습니다" description={error} />}

      {!isLoading && rows.length === 0 && (
        <EmptyState
          title="등록된 복용자가 없습니다"
          description="복용자를 먼저 등록한 뒤 식약처 DB에서 약물을 선택해주세요."
          action={
            <Link className="button primary" href="/patients">
              복용자 등록
            </Link>
          }
        />
      )}

      {!isLoading && rows.length > 0 && (
        <div className="yk-styleguide-grid">
          {rows.map(({ patient, medicationCount, latestAnalysisAt }) => {
            const canAnalyze = medicationCount > 0;

            return (
              <YkCard className="yk-product-patient-card" key={patient.id}>
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
                  <YkStatusPill tone={canAnalyze ? "safe" : "caution"}>
                    {canAnalyze ? "분석 가능" : "약물 선택 필요"}
                  </YkStatusPill>
                </div>

                <p className="yk-product-card-copy">
                  {canAnalyze
                    ? "등록된 약을 바탕으로 함께 복용할 때 주의할 점을 확인할 수 있습니다."
                    : "약 정보 입력 화면에서 자동완성 결과를 선택해 분석 목록을 채워주세요."}
                </p>
                <p className="yk-product-card-copy">마지막 분석 {formatDateTime(latestAnalysisAt)}</p>

                <div className="yk-card-meta yk-report-list-actions">
                  <Link className="yk-button yk-button-primary yk-button-compact" href={`/reports/${patient.id}`}>
                    <FileText size={15} />
                    분석 화면
                  </Link>
                </div>
              </YkCard>
            );
          })}
        </div>
      )}
    </AppShell>
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
