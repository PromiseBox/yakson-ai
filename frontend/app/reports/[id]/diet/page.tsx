"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell, EmptyState, LoadingState } from "@/components/AppShell";
import { buildDietGuides } from "@/lib/app-store";
import { getPatientById, listPatientMedications } from "@/lib/api";
import { toUserErrorMessage } from "@/lib/error-messages";
import { DietGuide, MedicationRecord, PatientRecord } from "@/lib/types";

export default function DietReportPage() {
  const params = useParams<{ id: string }>();
  const patientId = Array.isArray(params.id) ? params.id[0] : params.id;
  const [patient, setPatient] = useState<PatientRecord | null>(null);
  const [medications, setMedications] = useState<MedicationRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadPage() {
      setIsLoading(true);
      setError("");
      try {
        const [nextPatient, nextMedications] = await Promise.all([
          getPatientById(patientId),
          listPatientMedications(patientId)
        ]);
        setPatient(nextPatient);
        setMedications(nextMedications);
      } catch (caught) {
        setPatient(null);
        setMedications([]);
        setError(toUserErrorMessage(caught, "식습관 리포트를 불러오지 못했습니다."));
      } finally {
        setIsLoading(false);
      }
    }

    void loadPage();
  }, [patientId]);

  const guides = useMemo(() => buildDietGuides(medications), [medications]);

  return (
    <AppShell
      title="식습관 리포트"
      subtitle="조회 - 복약 기반 생활 안내"
      action={
        <Link className="button secondary" href={`/reports/${patientId}`}>
          분석 화면
        </Link>
      }
    >
      {isLoading && <LoadingState />}
      {error && <p className="error">{error}</p>}

      {!isLoading && !patient && (
        <EmptyState
          title="복용자를 찾을 수 없습니다"
          description="조회 목록에서 복용자를 다시 선택해주세요."
          action={
            <Link className="button primary" href="/reports">
              조회 목록으로 이동
            </Link>
          }
        />
      )}

      {!isLoading && patient && (
        <div className="dashboardGrid">
          <section className="panel">
            <div className="sectionHeader">
              <div>
                <h2>{patient.displayName} 식습관 안내</h2>
                <p className="subtext">
                  DB에 저장된 약물 목록을 기준으로 기본 식습관 안내를 제공합니다.
                </p>
              </div>
            </div>

            <div className="guideList">
              {guides.map((guide) => (
                <DietGuideCard guide={guide} key={guide.id} />
              ))}
            </div>
          </section>

          <aside className="stack">
            <section className="panel">
              <h2>분석 대상 약물</h2>
              {medications.length === 0 ? (
                <p className="subtext">아직 선택된 약물이 없습니다.</p>
              ) : (
                <div className="drugList">
                  {medications.map((medication) => (
                    <div className="drugRow" key={medication.id}>
                      <div>
                        <strong>{medication.matchedProductName ?? medication.enteredDrugName}</strong>
                        <p className="subtext">{medication.category}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="guidance">
              <strong>안내</strong>
              <br />
              이 화면은 상담 참고자료입니다. 실제 식단 제한은 약사 또는 의사에게 확인해주세요.
            </section>
          </aside>
        </div>
      )}
    </AppShell>
  );
}

function DietGuideCard({ guide }: { guide: DietGuide }) {
  const className = guide.severity === "avoid" ? "avoid" : guide.severity === "caution" ? "caution" : "safe";
  const label = guide.severity === "avoid" ? "피하기" : guide.severity === "caution" ? "주의" : "안전";

  return (
    <article className="guideCard">
      <div className="guideTitle">
        <span className={`dot ${className}`} aria-hidden="true" />
        <div>
          <h3>{guide.title}</h3>
          <span className={`pill ${guide.severity === "avoid" ? "risk" : guide.severity === "caution" ? "caution" : "normal"}`}>
            {label}
          </span>
        </div>
      </div>
      <p className="subtext">
        <strong>{guide.foodName}</strong> · {guide.reason}
      </p>
      <div className="guidance" style={{ marginTop: 12 }}>
        {guide.action}
      </div>
      <div className="tagList">
        {guide.relatedMedications.map((medication) => (
          <span className="tag" key={medication}>
            {medication}
          </span>
        ))}
      </div>
      <p className="source">근거: {guide.source}</p>
    </article>
  );
}
