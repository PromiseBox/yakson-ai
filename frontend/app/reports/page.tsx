"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell, EmptyState, LoadingState } from "@/components/AppShell";
import { sexLabel } from "@/lib/app-store";
import { fetchAnalysisHistory, listPatientMedications, listPatients } from "@/lib/api";
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
        setError(caught instanceof Error ? caught.message : "분석 조회 목록을 불러오지 못했습니다.");
      } finally {
        setIsLoading(false);
      }
    }

    void loadRows();
  }, []);

  return (
    <AppShell title="분석 조회" subtitle="조회 - 복용자 선택">
      {isLoading && <LoadingState />}
      {error && <p className="error">{error}</p>}

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
        <div className="cardGrid">
          {rows.map(({ patient, medicationCount, latestAnalysisAt }) => {
            const canAnalyze = medicationCount > 0;

            return (
              <article className="reportPatientCard" key={patient.id}>
                <div className="patientCardTop">
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span className="avatar">{patient.displayName.slice(0, 1)}</span>
                    <div>
                      <h3>{patient.displayName}</h3>
                      <div className="meta">
                        <span>{patient.ageYears}세</span>
                        <span>{sexLabel(patient.sex)}</span>
                        <span>분석 목록 {medicationCount}개</span>
                      </div>
                    </div>
                  </div>
                  <span className={`pill ${canAnalyze ? "normal" : "caution"}`}>
                    {canAnalyze ? "분석 가능" : "약물 선택 필요"}
                  </span>
                </div>

                <p className="subtext">
                  {canAnalyze
                    ? "DB에 저장된 식약처 등록 약물을 기준으로 룰 기반 분석 미리보기를 실행할 수 있습니다."
                    : "약 정보 입력 화면에서 자동완성 결과를 선택해 분석 목록을 채워주세요."}
                </p>
                <p className="subtext">마지막 분석 {formatDateTime(latestAnalysisAt)}</p>

                <div className="quickLinks">
                  <Link className="button primary" href={`/reports/${patient.id}`}>
                    분석 화면
                  </Link>
                  <Link className="button secondary" href={`/patients/${patient.id}/medications`}>
                    약 정보 입력
                  </Link>
                </div>
              </article>
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
