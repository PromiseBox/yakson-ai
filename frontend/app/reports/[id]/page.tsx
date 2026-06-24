"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell, EmptyState, LoadingState } from "@/components/AppShell";
import { buildDietGuides, buildExerciseGuides, groupMedicationsByCategory, sexLabel } from "@/lib/app-store";
import {
  fetchAnalysisHistory,
  fetchAnalysisReport,
  fetchLatestAnalysis,
  getPatientById,
  listPatientMedications,
  runAndSaveLatestAnalysis
} from "@/lib/api";
import {
  AlertEvidence,
  AnalysisAlert,
  AnalysisReport,
  AnalysisReportHistoryItem,
  MedicationInput,
  MedicationRecord,
  PatientRecord,
  RuleType
} from "@/lib/types";

const ruleLabels: Record<RuleType, string> = {
  PRODUCT_INTERACTION: "제품 병용 주의",
  INGREDIENT_INTERACTION: "성분 병용 주의",
  DUPLICATE_INGREDIENT: "동일 성분 중복",
  DUPLICATE_EFFICACY: "동일 효능군 중복",
  ELDERLY_CAUTION: "고령자 주의",
  PREGNANCY_CAUTION: "임부 금기/주의",
  LACTATION_CAUTION: "수유부 주의",
  AGE_CONTRAINDICATION: "연령 금기",
  DURATION_CAUTION: "투여기간 주의",
  DOSAGE_CAUTION: "용량 주의",
  MATCHING_REVIEW: "약물 매칭 확인"
};

export default function PatientDashboardPage() {
  const params = useParams<{ id: string }>();
  const patientId = Array.isArray(params.id) ? params.id[0] : params.id;
  const [patient, setPatient] = useState<PatientRecord | null>(null);
  const [medications, setMedications] = useState<MedicationRecord[]>([]);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [reportHistory, setReportHistory] = useState<AnalysisReportHistoryItem[]>([]);
  const [reportError, setReportError] = useState("");
  const [reportNotice, setReportNotice] = useState("");
  const [pageError, setPageError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isReportLoading, setIsReportLoading] = useState(false);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);

  useEffect(() => {
    async function loadPage() {
      setIsLoading(true);
      setPageError("");
      try {
        const [nextPatient, nextMedications, latestReport, history] = await Promise.all([
          getPatientById(patientId),
          listPatientMedications(patientId),
          fetchLatestAnalysis(patientId),
          fetchAnalysisHistory(patientId)
        ]);
        setPatient(nextPatient);
        setMedications(nextMedications);
        setReport(latestReport);
        setReportHistory(history);
      } catch (caught) {
        setPatient(null);
        setMedications([]);
        setReport(null);
        setReportHistory([]);
        setPageError(caught instanceof Error ? caught.message : "분석 데이터를 불러오지 못했습니다.");
      } finally {
        setIsLoading(false);
      }
    }

    void loadPage();
  }, [patientId]);

  useEffect(() => {
    if (!reportNotice) {
      return;
    }

    const timer = window.setTimeout(() => setReportNotice(""), 3500);
    return () => window.clearTimeout(timer);
  }, [reportNotice]);

  const grouped = useMemo(() => groupMedicationsByCategory(medications), [medications]);
  const dietGuides = useMemo(() => buildDietGuides(medications), [medications]);
  const exerciseGuides = useMemo(() => buildExerciseGuides(medications), [medications]);
  const evidenceRows = useMemo(() => flattenEvidence(report), [report]);
  const canAnalyze = medications.length > 0 && medications.every((medication) => medication.productCode);
  const isReportStale = useMemo(
    () => (report?.isStale === undefined ? isMedicationSnapshotStale(report, medications) : report.isStale),
    [report, medications]
  );
  const latestReportId = reportHistory[0]?.reportId ?? null;
  const isViewingLatestReport = Boolean(report && latestReportId && report.reportId === latestReportId);
  const reportTimestamp = report?.savedAt ?? report?.generatedAt ?? "";

  async function runPreview() {
    if (!patient) {
      return;
    }

    if (medications.length === 0) {
      setReport(null);
      setReportError("분석할 약물이 없습니다. 약 정보 입력 화면에서 식약처 DB 자동완성 결과를 선택해주세요.");
      return;
    }

    if (!canAnalyze) {
      setReport(null);
      setReportError("식약처 DB 자동완성에서 선택된 약물만 분석할 수 있습니다. 미등록 약물은 서비스 대상 아님으로 처리됩니다.");
      return;
    }

    setIsReportLoading(true);
    setReportError("");
    setReportNotice("");

    try {
      const nextReport = await runAndSaveLatestAnalysis(patient.id);
      const history = await fetchAnalysisHistory(patient.id);
      setReport(nextReport);
      setReportHistory(history);
      setReportNotice("최신 분석 리포트를 저장했습니다.");
    } catch (caught) {
      setReport(null);
      setReportError(caught instanceof Error ? caught.message : "분석 리포트를 저장하지 못했습니다.");
    } finally {
      setIsReportLoading(false);
    }
  }

  async function openHistoryReport(item: AnalysisReportHistoryItem) {
    if (!patient) {
      return;
    }

    setIsHistoryLoading(true);
    setReportError("");
    setReportNotice("");

    try {
      const selectedReport = await fetchAnalysisReport(patient.id, item.analysisRunId);
      setReport(selectedReport);
      setReportNotice(item.isLatest ? "최신 리포트를 불러왔습니다." : "과거 리포트를 불러왔습니다.");
    } catch (caught) {
      setReportError(caught instanceof Error ? caught.message : "분석 이력을 불러오지 못했습니다.");
    } finally {
      setIsHistoryLoading(false);
    }
  }

  return (
    <AppShell
      title="복약 분석 미리보기"
      subtitle="조회 - 룰 기반 안전 분석"
      action={
        <Link className="button secondary" href="/reports">
          조회 목록
        </Link>
      }
    >
      {isLoading && <LoadingState />}
      {pageError && <p className="error">{pageError}</p>}

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

      {!isLoading && patient && medications.length === 0 && (
        <EmptyState
          title="분석할 약물이 없습니다"
          description="약 정보 입력 화면에서 식약처 DB 자동완성 결과를 선택해 분석 목록을 추가해주세요."
          action={
            <Link className="button primary" href={`/patients/${patient.id}/medications`}>
              약 정보 입력
            </Link>
          }
        />
      )}

      {!isLoading && patient && medications.length > 0 && (
        <div className="dashboardGrid">
          <div className="stack">
            <section className="panel">
              <div className="sectionHeader">
                <div>
                  <h2>{patient.displayName}</h2>
                  <p className="subtext">
                    {patient.ageYears}세 · {sexLabel(patient.sex)} · 분석 목록 {medications.length}개
                  </p>
                </div>
                <Link className="button small secondary" href={`/patients/${patient.id}/medications`}>
                  약 정보 수정
                </Link>
              </div>

              <div className="previewActions">
                <div>
                  <strong>DB 저장 약물 기준 분석</strong>
                  <p className="subtext">
                    Cloud SQL에 저장된 식약처 등록 약물을 룰 데이터로 조회하고 최신 리포트로 저장합니다.
                  </p>
                </div>
                <button className="button primary" type="button" onClick={runPreview} disabled={isReportLoading}>
                  {isReportLoading ? "분석 중" : report ? "다시 분석하기" : "분석하기"}
                </button>
              </div>

              {reportNotice && <p className="success">{reportNotice}</p>}
              {reportError && <p className="error">{reportError}</p>}
              {report && (
                <p className="subtext" style={{ marginTop: 10 }}>
                  저장일 {formatDateTime(reportTimestamp)}
                </p>
              )}
              {report && !isViewingLatestReport && (
                <div className="guidance caution" style={{ marginTop: 12 }}>
                  <strong>과거 리포트를 보고 있습니다</strong>
                  <br />
                  현재 화면은 최신 리포트가 아닙니다. 현재 약물 기준으로 다시 확인하려면 다시 분석하기를 눌러주세요.
                </div>
              )}
              {report && isReportStale && (
                <div className="guidance caution" style={{ marginTop: 12 }}>
                  <strong>다시 분석이 필요합니다</strong>
                  <br />
                  현재 약물 목록과 이 리포트의 저장 시점 약물 목록이 다릅니다. 최신 결과를 보려면 다시 분석해주세요.
                </div>
              )}
            </section>

            <section className="panel">
              <div className="sectionHeader">
                <div>
                  <h2>분석 대상 약물</h2>
                  <p className="subtext">공식명, 업체명, 제품코드 기준으로 분석합니다.</p>
                </div>
              </div>

              <div className="categoryList">
                {grouped.map((group) => (
                  <article className="categoryCard" key={group.category}>
                    <div className="sectionHeader">
                      <h3>{group.category}</h3>
                      <span className="pill normal">{group.medications.length}개</span>
                    </div>
                    <div className="drugList">
                      {group.medications.map((medication) => (
                        <div className="drugRow" key={medication.id}>
                          <div>
                            <strong>{medication.matchedProductName ?? medication.enteredDrugName}</strong>
                            <div className="meta">
                              <span>{medication.companyName || "업체명 없음"}</span>
                              <span>제품코드 {medication.productCode || "-"}</span>
                              <span>품목코드 {medication.itemSeq || "-"}</span>
                              <span>{medication.durationDays}일</span>
                              <span>하루 {medication.dosesPerDay}회</span>
                              <span>
                                1회 {medication.doseAmount}
                                {medication.doseUnit}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="panel">
              <div className="sectionHeader">
                <div>
                  <h2>룰 기반 알림</h2>
                  <p className="subtext">
                    동일 성분, 동일 효능군, 병용금기/주의, 고령자/임부/수유부/연령/기간/용량 주의 룰을 확인합니다.
                  </p>
                </div>
              </div>

              {isReportLoading && <LoadingState />}

              {!isReportLoading && !report && !reportError && (
                <div className="guidance">
                  <strong>분석 대기 중</strong>
                  <br />
                  위의 분석하기 버튼을 누르면 현재 DB 저장 목록 기준의 최신 리포트가 저장됩니다.
                </div>
              )}

              {!isReportLoading && report && report.alerts.length === 0 && (
                <div className="guidance">
                  <strong>확인된 경고 없음</strong>
                  <br />
                  현재 선택된 약물 조합에서는 적용된 룰 기준 위험/주의 알림이 확인되지 않았습니다.
                </div>
              )}

              {!isReportLoading && report && report.alerts.length > 0 && (
                <div className="alertList">
                  {report.alerts.map((alert) => (
                    <AlertCard alert={alert} key={alert.alertId} />
                  ))}
                </div>
              )}
            </section>

            {report && evidenceRows.length > 0 && (
              <section className="panel">
                <div className="sectionHeader">
                  <div>
                    <h2>룰별 근거</h2>
                    <p className="subtext">각 알림이 어떤 DB 룰에서 나왔는지 확인합니다.</p>
                  </div>
                </div>
                <EvidenceTable rows={evidenceRows} />
              </section>
            )}
          </div>

          <aside className="stack">
            <section className="panel">
              <div className="sectionHeader">
                <div>
                  <h2>분석 이력</h2>
                  <p className="subtext">전체 이력을 보관하고 화면은 최신 리포트를 기본으로 보여줍니다.</p>
                </div>
              </div>

              {reportHistory.length === 0 ? (
                <p className="subtext">저장된 분석 이력이 없습니다.</p>
              ) : (
                <div className="stack">
                  {reportHistory.map((item) => (
                    <div className="historyRow" key={item.patientReportId}>
                      <div>
                        <strong>{formatDateTime(item.createdAt)}</strong>
                        <div className="meta">
                          <span>위험 {item.riskCount}건</span>
                          <span>주의 {item.cautionCount}건</span>
                          <span>약물 {item.medicationCount}개</span>
                        </div>
                      </div>
                      <div className="rowActions">
                        {item.isLatest && <span className="pill normal">최신</span>}
                        {item.isStale && <span className="pill caution">재분석 필요</span>}
                        <button
                          className="button small secondary"
                          type="button"
                          onClick={() => openHistoryReport(item)}
                          disabled={isHistoryLoading}
                        >
                          보기
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="panel">
              <h2>분석 요약</h2>
              {report ? (
                <div className="summaryGrid">
                  <div className="summaryBox risk">
                    <div>
                      <strong>{report.summary.riskCount}</strong>
                      <span>위험</span>
                    </div>
                  </div>
                  <div className="summaryBox caution">
                    <div>
                      <strong>{report.summary.cautionCount}</strong>
                      <span>주의</span>
                    </div>
                  </div>
                  <div className="summaryBox normal">
                    <div>
                      <strong>{report.summary.normalCount}</strong>
                      <span>정상</span>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="subtext">분석하기를 누르면 최신 리포트 요약이 저장되고 표시됩니다.</p>
              )}
            </section>

            {report && (
              <section className="panel">
                <h2>약사 전달 요약</h2>
                <p className="subtext">{report.pharmacistHandoffText}</p>
              </section>
            )}

            {report && (
              <section className="guidance">
                <strong>보호자 안내</strong>
                <br />
                {report.caregiverGuidance}
              </section>
            )}

            <section className="panel">
              <h2>생활 리포트</h2>
              <div className="quickLinks">
                <Link className="quickLink" href={`/reports/${patient.id}/diet`}>
                  <strong>식습관</strong>
                  <p className="subtext">주의 항목 {dietGuides.filter((guide) => guide.severity !== "safe").length}건</p>
                </Link>
                <Link className="quickLink" href={`/reports/${patient.id}/exercise`}>
                  <strong>운동</strong>
                  <p className="subtext">
                    활동 주의 {exerciseGuides.filter((guide) => guide.severity !== "safe").length}건
                  </p>
                </Link>
              </div>
            </section>
          </aside>
        </div>
      )}
    </AppShell>
  );
}

function AlertCard({ alert }: { alert: AnalysisAlert }) {
  const className = alert.severity === "RISK" ? "risk" : alert.severity === "CAUTION" ? "caution" : "normal";
  const severityLabel = alert.severity === "RISK" ? "위험" : alert.severity === "CAUTION" ? "주의" : "정상";

  return (
    <article className={`alertCard ${className}`}>
      <div className="alertTitle">
        <span className={`dot ${className}`} aria-hidden="true" />
        <h3>{alert.title}</h3>
        <span className={`pill ${className}`}>{severityLabel}</span>
      </div>
      <p className="subtext" style={{ color: "#40504a" }}>
        {alert.message}
      </p>
      <div className="tagList">
        <span className="tag">{ruleLabels[alert.ruleType]}</span>
        {alert.relatedMedications.map((medication) => (
          <span className="tag" key={medication}>
            {medication}
          </span>
        ))}
        {alert.routeToProfessional && <span className="tag">전문가 확인 권장</span>}
      </div>
      <p className="source">
        근거: {alert.evidence.map((item) => `${item.sourceName} (${item.sourceRecordId})`).join(", ")}
      </p>
    </article>
  );
}

function EvidenceTable({ rows }: { rows: Array<AlertEvidence & { alertTitle: string; ruleType: RuleType }> }) {
  return (
    <div className="evidenceTableWrap">
      <table className="evidenceTable">
        <thead>
          <tr>
            <th>알림</th>
            <th>룰</th>
            <th>출처</th>
            <th>레코드</th>
            <th>설명</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.alertTitle}-${row.sourceRecordId}-${row.description}`}>
              <td>{row.alertTitle}</td>
              <td>{ruleLabels[row.ruleType]}</td>
              <td>{row.sourceName}</td>
              <td>{row.sourceRecordId}</td>
              <td>{row.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function flattenEvidence(report: AnalysisReport | null) {
  if (!report) {
    return [];
  }

  return report.alerts.flatMap((alert) =>
    alert.evidence.map((item) => ({
      ...item,
      alertTitle: alert.title,
      ruleType: alert.ruleType
    }))
  );
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
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

function isMedicationSnapshotStale(report: AnalysisReport | null, medications: MedicationRecord[]) {
  if (!report) {
    return false;
  }

  const savedSnapshot = report.sourceMedicationSnapshot ?? [];
  if (savedSnapshot.length !== medications.length) {
    return true;
  }

  const includeCategory = savedSnapshot.some((medication) => Boolean(medication.categoryName));
  const savedKeys = savedSnapshot.map((medication) => snapshotKey(medication, includeCategory)).sort();
  const currentKeys = medications.map((medication) => currentMedicationKey(medication, includeCategory)).sort();
  return savedKeys.some((key, index) => key !== currentKeys[index]);
}

function currentMedicationKey(medication: MedicationRecord, includeCategory: boolean) {
  return snapshotKey({
    enteredDrugName: medication.enteredDrugName,
    categoryName: medication.category,
    productCode: medication.productCode,
    itemSeq: medication.itemSeq,
    durationDays: medication.durationDays,
    dosesPerDay: medication.dosesPerDay,
    doseAmount: medication.doseAmount,
    doseUnit: medication.doseUnit
  }, includeCategory);
}

function snapshotKey(medication: MedicationInput, includeCategory: boolean) {
  const values = [
    medication.productCode ?? "",
    medication.itemSeq ?? ""
  ];
  if (includeCategory) {
    values.push(medication.categoryName ?? "");
  }
  values.push(
    normalizedNumber(medication.durationDays),
    normalizedNumber(medication.dosesPerDay),
    normalizedNumber(medication.doseAmount),
    medication.doseUnit ?? ""
  );
  return values.join("|");
}

function normalizedNumber(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(Number(value));
}
