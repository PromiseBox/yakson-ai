"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell, EmptyState, LoadingState } from "@/components/AppShell";
import { buildExerciseGuides } from "@/lib/app-store";
import { getPatientById, listPatientMedications } from "@/lib/api";
import { toUserErrorMessage } from "@/lib/error-messages";
import { ExerciseGuide, MedicationRecord, PatientRecord } from "@/lib/types";

export default function ExerciseReportPage() {
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
        setError(toUserErrorMessage(caught, "운동 리포트를 불러오지 못했습니다."));
      } finally {
        setIsLoading(false);
      }
    }

    void loadPage();
  }, [patientId]);

  const guides = useMemo(() => buildExerciseGuides(medications), [medications]);

  return (
    <AppShell
      title="운동 리포트"
      subtitle="조회 - 복약 기반 활동 안내"
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
                <h2>{patient.displayName} 운동 안내</h2>
                <p className="subtext">
                  복약 안전 알림을 참고해 어지러움, 졸림, 낙상 위험을 함께 확인합니다.
                </p>
              </div>
            </div>

            <div className="guideList">
              {guides.map((guide) => (
                <ExerciseGuideCard guide={guide} key={guide.id} />
              ))}
            </div>
          </section>

          <aside className="stack">
            <section className="panel">
              <h2>활동 전 확인</h2>
              <div className="stack">
                <div className="listRow">
                  <span>어지러움</span>
                  <span className="pill caution">확인</span>
                </div>
                <div className="listRow">
                  <span>졸림/낙상 위험</span>
                  <span className="pill caution">주의</span>
                </div>
                <div className="listRow">
                  <span>수분 섭취</span>
                  <span className="pill normal">권장</span>
                </div>
              </div>
            </section>

            <section className="guidance">
              <strong>안내</strong>
              <br />
              이 화면은 운동 처방이 아닌 안전 참고자료입니다. 통증, 어지러움, 호흡곤란이 있으면 운동을 멈추고 상담하세요.
            </section>
          </aside>
        </div>
      )}
    </AppShell>
  );
}

function ExerciseGuideCard({ guide }: { guide: ExerciseGuide }) {
  const className = guide.severity === "avoid" ? "avoid" : guide.severity === "caution" ? "caution" : "safe";
  const label = guide.severity === "avoid" ? "제한" : guide.severity === "caution" ? "주의" : "가능";

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
        <strong>{guide.activityName}</strong> · {guide.reason}
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
