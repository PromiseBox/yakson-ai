"use client";

import { Database, FileText, Pencil, Pill, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { AppShell, EmptyState, LoadingState } from "@/components/AppShell";
import {
  YkButton,
  YkCard,
  YkDrugSearchResultItem,
  YkErrorState,
  YkIconButton,
  YkInlineAlert,
  YkNoResultState,
  YkNoticeBox,
  YkSectionHeader,
  YkStatusPill
} from "@/components/ui/design-system";
import { groupMedicationsByCategory, prescriptionCategories, sexLabel } from "@/lib/app-store";
import {
  createMedicationOnServer,
  deleteMedicationOnServer,
  getPatientById,
  listPatientMedications,
  searchDrugs,
  updateMedicationOnServer,
  validateDrug
} from "@/lib/api";
import { toUserErrorMessage } from "@/lib/error-messages";
import { DrugSearchItem, MedicationRecord, PatientRecord, PrescriptionCategory } from "@/lib/types";

export default function MedicationInputPage() {
  const params = useParams<{ id: string }>();
  const patientId = Array.isArray(params.id) ? params.id[0] : params.id;
  const [patient, setPatient] = useState<PatientRecord | null>(null);
  const [medications, setMedications] = useState<MedicationRecord[]>([]);
  const [category, setCategory] = useState<PrescriptionCategory>("내과");
  const [drugName, setDrugName] = useState("");
  const [selectedDrug, setSelectedDrug] = useState<DrugSearchItem | null>(null);
  const [searchResults, setSearchResults] = useState<DrugSearchItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [durationDays, setDurationDays] = useState("30");
  const [dosesPerDay, setDosesPerDay] = useState("1");
  const [doseAmount, setDoseAmount] = useState("1");
  const [doseUnit, setDoseUnit] = useState("정");
  const [error, setError] = useState("");
  const [pageError, setPageError] = useState("");
  const [notice, setNotice] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isAdding, setIsAdding] = useState(false);
  const [editTarget, setEditTarget] = useState<MedicationRecord | null>(null);
  const [editCategory, setEditCategory] = useState<PrescriptionCategory>("내과");
  const [editDurationDays, setEditDurationDays] = useState("");
  const [editDosesPerDay, setEditDosesPerDay] = useState("");
  const [editDoseAmount, setEditDoseAmount] = useState("");
  const [editDoseUnit, setEditDoseUnit] = useState("");
  const [editError, setEditError] = useState("");
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    void refreshPage();
  }, [patientId]);

  useEffect(() => {
    if (!notice) {
      return;
    }

    const timer = window.setTimeout(() => setNotice(""), 3500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    const query = drugName.trim();
    if (query.length < 2 || selectedDrug?.productName === query) {
      setSearchResults([]);
      setSearchError("");
      setIsSearching(false);
      return;
    }

    let ignore = false;
    setIsSearching(true);
    setSearchError("");

    const timer = window.setTimeout(async () => {
      try {
        const results = await searchDrugs(query, 15);
        if (!ignore) {
          setSearchResults(results);
        }
      } catch (caught) {
        if (!ignore) {
          setSearchResults([]);
          setSearchError(toUserErrorMessage(caught, "약품 데이터베이스 조회 중 문제가 발생했습니다."));
        }
      } finally {
        if (!ignore) {
          setIsSearching(false);
        }
      }
    }, 280);

    return () => {
      ignore = true;
      window.clearTimeout(timer);
    };
  }, [drugName, selectedDrug]);

  const grouped = useMemo(() => groupMedicationsByCategory(medications), [medications]);

  async function refreshPage() {
    setIsLoading(true);
    setPageError("");
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
      setPageError(toUserErrorMessage(caught, "약 정보 화면을 불러오지 못했습니다."));
    } finally {
      setIsLoading(false);
    }
  }

  function selectDrug(drug: DrugSearchItem) {
    setSelectedDrug(drug);
    setDrugName(drug.productName);
    setSearchResults([]);
    setSearchError("");
    setError("");
    setNotice("");
  }

  function handleDrugNameChange(value: string) {
    setDrugName(value);
    setSelectedDrug(null);
    setError("");
    setNotice("");
  }

  async function submitMedication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!patient) {
      return;
    }

    const parsedDuration = Number(durationDays);
    const parsedDoses = Number(dosesPerDay);
    const parsedAmount = Number(doseAmount);

    if (
      !durationDays ||
      !dosesPerDay ||
      !doseAmount ||
      Number.isNaN(parsedDuration) ||
      Number.isNaN(parsedDoses) ||
      Number.isNaN(parsedAmount) ||
      parsedDuration <= 0 ||
      parsedDoses <= 0 ||
      parsedAmount <= 0
    ) {
      setError("투약 일수, 하루 횟수, 1회 용량을 올바르게 입력해주세요.");
      return;
    }

    if (!selectedDrug?.productCode) {
      setError("서비스 대상 아님: 식약처 DB 자동완성 결과에서 약물을 선택해야 저장할 수 있습니다.");
      return;
    }

    setIsAdding(true);
    setError("");
    setNotice("");

    try {
      const validatedDrug = await validateDrug(selectedDrug.productCode, selectedDrug.itemSeq);
      await createMedicationOnServer(patient.id, {
        categoryName: category,
        enteredDrugName: validatedDrug.productName,
        productCode: validatedDrug.productCode,
        itemSeq: validatedDrug.itemSeq,
        durationDays: parsedDuration,
        dosesPerDay: parsedDoses,
        doseAmount: parsedAmount,
        doseUnit: doseUnit.trim() || "정"
      });

      setDrugName("");
      setSelectedDrug(null);
      setSearchResults([]);
      setDurationDays("30");
      setDosesPerDay("1");
      setDoseAmount("1");
      setDoseUnit("정");
      setNotice("약 정보를 저장했습니다.");
      await refreshPage();
    } catch (caught) {
      setError(toUserErrorMessage(caught, "선택한 약 정보를 저장하지 못했습니다."));
    } finally {
      setIsAdding(false);
    }
  }

  async function deleteMedication(medicationId: string) {
    setPageError("");
    setNotice("");
    try {
      await deleteMedicationOnServer(medicationId);
      setNotice("약 정보를 삭제했습니다.");
      await refreshPage();
    } catch (caught) {
      setPageError(toUserErrorMessage(caught, "약물 정보를 삭제하지 못했습니다."));
    }
  }

  function openEditMedication(medication: MedicationRecord) {
    setEditTarget(medication);
    setEditCategory(medication.category);
    setEditDurationDays(String(medication.durationDays));
    setEditDosesPerDay(String(medication.dosesPerDay));
    setEditDoseAmount(String(medication.doseAmount));
    setEditDoseUnit(medication.doseUnit);
    setEditError("");
    setNotice("");
  }

  function closeEditMedication() {
    if (isEditing) {
      return;
    }
    setEditTarget(null);
    setEditError("");
  }

  async function submitMedicationEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editTarget) {
      return;
    }

    const parsedDuration = Number(editDurationDays);
    const parsedDoses = Number(editDosesPerDay);
    const parsedAmount = Number(editDoseAmount);

    if (
      !editDurationDays ||
      !editDosesPerDay ||
      !editDoseAmount ||
      Number.isNaN(parsedDuration) ||
      Number.isNaN(parsedDoses) ||
      Number.isNaN(parsedAmount) ||
      parsedDuration <= 0 ||
      parsedDoses <= 0 ||
      parsedAmount <= 0
    ) {
      setEditError("투약 일수, 하루 횟수, 1회 용량을 올바르게 입력해주세요.");
      return;
    }

    setIsEditing(true);
    setEditError("");

    try {
      await updateMedicationOnServer(editTarget.id, {
        categoryName: editCategory,
        durationDays: parsedDuration,
        dosesPerDay: parsedDoses,
        doseAmount: parsedAmount,
        doseUnit: editDoseUnit.trim() || "정"
      });
      setEditTarget(null);
      setNotice("약 정보를 수정했습니다.");
      await refreshPage();
    } catch (caught) {
      setEditError(toUserErrorMessage(caught, "약물 정보를 수정하지 못했습니다."));
    } finally {
      setIsEditing(false);
    }
  }

  return (
    <AppShell
      title="약 정보 입력"
      subtitle="입력 - 상세 약 정보"
      action={
        <Link className="yk-button yk-button-secondary" href="/patients">
          복용자 목록
        </Link>
      }
    >
      {isLoading && <LoadingState />}
      {pageError && <YkErrorState title="복용자 또는 약물 목록을 불러오지 못했습니다" description={pageError} />}
      {notice && (
        <YkInlineAlert title="저장 완료" tone="safe">
          {notice}
        </YkInlineAlert>
      )}

      {!isLoading && !patient && (
        <EmptyState
          title="복용자를 찾을 수 없습니다"
          description="목록에서 복용자를 다시 선택해주세요."
          action={
            <Link className="button primary" href="/patients">
              복용자 목록으로 이동
            </Link>
          }
        />
      )}

      {!isLoading && patient && (
        <div className="twoColumn">
          <YkCard>
            <YkSectionHeader
              title={patient.displayName}
              subtitle={`${patient.ageYears}세 · ${sexLabel(patient.sex)} · 분석 목록 ${medications.length}개`}
              icon={Pill}
              action={
                <Link className="yk-button yk-button-secondary yk-button-compact" href={`/reports/${patient.id}`}>
                  <FileText size={15} />
                  리포트 보기
                </Link>
              }
            />

            <YkNoticeBox title="등록 원칙" tone="brand" icon={Database}>
              약품은 식약처 기반 데이터베이스에서 확인된 품목을 검색해 선택할 수 있습니다.
            </YkNoticeBox>

            <form className="stack yk-product-form" onSubmit={submitMedication}>
              <div className="fieldLabel">
                처방 대분류
                <div className="chipGroup">
                  {prescriptionCategories.map((item) => (
                    <button
                      className={`chip ${category === item ? "selected" : ""}`}
                      key={item}
                      type="button"
                      onClick={() => setCategory(item)}
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </div>

              <label className="fieldLabel">
                약명 입력
                <input
                  className="input"
                  value={drugName}
                  onChange={(event) => handleDrugNameChange(event.target.value)}
                  placeholder="약 봉투나 처방전에 적힌 약명을 입력하세요"
                  autoComplete="off"
                />
              </label>

              <DrugAutocomplete
                drugName={drugName}
                isSearching={isSearching}
                results={searchResults}
                searchError={searchError}
                selectedDrug={selectedDrug}
                onSelect={selectDrug}
              />

              <div className="formGrid">
                <label className="fieldLabel">
                  투약 일수
                  <input
                    className="input"
                    value={durationDays}
                    onChange={(event) => setDurationDays(event.target.value.replace(/[^0-9]/g, ""))}
                    inputMode="numeric"
                    placeholder="30"
                  />
                </label>
                <label className="fieldLabel">
                  하루 횟수
                  <input
                    className="input"
                    value={dosesPerDay}
                    onChange={(event) => setDosesPerDay(event.target.value.replace(/[^0-9.]/g, ""))}
                    inputMode="decimal"
                    placeholder="1"
                  />
                </label>
                <label className="fieldLabel">
                  1회 용량
                  <input
                    className="input"
                    value={doseAmount}
                    onChange={(event) => setDoseAmount(event.target.value.replace(/[^0-9.]/g, ""))}
                    inputMode="decimal"
                    placeholder="1"
                  />
                </label>
                <label className="fieldLabel">
                  단위
                  <input
                    className="input"
                    value={doseUnit}
                    onChange={(event) => setDoseUnit(event.target.value)}
                    placeholder="정"
                  />
                </label>
              </div>

              {error && (
                <YkInlineAlert title="최소 입력이 필요합니다" tone="caution">
                  {error}
                </YkInlineAlert>
              )}

              <YkButton icon={Plus} type="submit" disabled={isAdding || !selectedDrug}>
                {isAdding ? "저장 중" : "약 정보 저장"}
              </YkButton>
            </form>
          </YkCard>

          <YkCard>
              <YkSectionHeader
              title="분석 목록"
              subtitle="선택한 약품을 기준으로 분석 대상 목록을 구성합니다."
              icon={Database}
              action={
                medications.length > 0 && (
                  <Link className="yk-button yk-button-primary yk-button-compact" href={`/reports/${patient.id}`}>
                    분석하기
                  </Link>
                )
              }
            />

            {medications.length === 0 ? (
              <YkNoResultState
                title="분석 목록이 비어 있습니다"
                description="왼쪽 입력 영역에서 약명을 검색하고 자동완성 결과를 선택해주세요."
              />
            ) : (
              <div className="categoryList">
                {grouped.map((group) => (
                  <article className="categoryCard" key={group.category}>
                    <div className="sectionHeader">
                      <h3>{group.category}</h3>
                      <YkStatusPill tone="brand" count={group.medications.length}>
                        등록
                      </YkStatusPill>
                    </div>
                    <div className="drugList">
                      {group.medications.map((medication) => (
                        <MedicationRow
                          key={medication.id}
                          medication={medication}
                          onEdit={() => openEditMedication(medication)}
                          onDelete={() => deleteMedication(medication.id)}
                        />
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </YkCard>
        </div>
      )}
      {editTarget && (
        <div className="modalBackdrop" role="dialog" aria-modal="true">
          <form className="sheet" onSubmit={submitMedicationEdit}>
            <div className="sheetHeader">
              <div>
                <h2>약 정보 수정</h2>
                <p className="subtext">
                  {editTarget.matchedProductName || editTarget.enteredDrugName}
                  <br />
                  식약처 등록 약물은 유지하고 분류와 복용 정보만 수정합니다.
                </p>
              </div>
              <button className="closeButton" type="button" onClick={closeEditMedication} aria-label="닫기">
                x
              </button>
            </div>

            <div className="stack">
              <div className="fieldLabel">
                처방 대분류
                <div className="chipGroup">
                  {prescriptionCategories.map((item) => (
                    <button
                      className={`chip ${editCategory === item ? "selected" : ""}`}
                      key={item}
                      type="button"
                      onClick={() => setEditCategory(item)}
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </div>

              <div className="formGrid">
                <label className="fieldLabel">
                  투약 일수
                  <input
                    className="input"
                    value={editDurationDays}
                    onChange={(event) => setEditDurationDays(event.target.value.replace(/[^0-9]/g, ""))}
                    inputMode="numeric"
                  />
                </label>
                <label className="fieldLabel">
                  하루 횟수
                  <input
                    className="input"
                    value={editDosesPerDay}
                    onChange={(event) => setEditDosesPerDay(event.target.value.replace(/[^0-9.]/g, ""))}
                    inputMode="decimal"
                  />
                </label>
                <label className="fieldLabel">
                  1회 용량
                  <input
                    className="input"
                    value={editDoseAmount}
                    onChange={(event) => setEditDoseAmount(event.target.value.replace(/[^0-9.]/g, ""))}
                    inputMode="decimal"
                  />
                </label>
                <label className="fieldLabel">
                  단위
                  <input
                    className="input"
                    value={editDoseUnit}
                    onChange={(event) => setEditDoseUnit(event.target.value)}
                  />
                </label>
              </div>
            </div>

            {editError && <p className="error">{editError}</p>}

            <div className="sheetActions">
              <button className="button secondary" type="button" onClick={closeEditMedication} disabled={isEditing}>
                취소
              </button>
              <button className="button primary" type="submit" disabled={isEditing}>
                {isEditing ? "수정 중" : "수정 저장"}
              </button>
            </div>
          </form>
        </div>
      )}
    </AppShell>
  );
}

function DrugAutocomplete({
  drugName,
  isSearching,
  results,
  searchError,
  selectedDrug,
  onSelect
}: {
  drugName: string;
  isSearching: boolean;
  results: DrugSearchItem[];
  searchError: string;
  selectedDrug: DrugSearchItem | null;
  onSelect: (drug: DrugSearchItem) => void;
}) {
  const trimmed = drugName.trim();

  if (selectedDrug) {
    return (
      <div className="selectedDrugBox">
        <div>
          <strong>{selectedDrug.productName}</strong>
          <p className="subtext">
            {selectedDrug.companyName || "업체명 없음"} · 제품코드 {selectedDrug.productCode || "-"} · 품목코드{" "}
            {selectedDrug.itemSeq || "-"}
          </p>
          {selectedDrug.ingredientNames.length > 0 && (
            <p className="subtext">성분 {selectedDrug.ingredientNames.slice(0, 3).join(", ")}</p>
          )}
        </div>
        <YkStatusPill tone="safe">선택 완료</YkStatusPill>
      </div>
    );
  }

  if (trimmed.length < 2) {
    return (
      <YkInlineAlert title="최소 입력이 필요합니다" tone="caution">
        두 글자 이상 입력하면 식약처 기반 약품 데이터베이스에서 검색합니다.
      </YkInlineAlert>
    );
  }

  if (isSearching) {
    return (
      <YkInlineAlert title="검색 중" tone="brand">
        식약처 DB에서 약명을 검색하고 있습니다.
      </YkInlineAlert>
    );
  }

  if (searchError) {
    return <YkErrorState title="약명 검색 서버에 연결하지 못했습니다" description={searchError} />;
  }

  if (results.length === 0) {
    return (
      <YkNoResultState
        title="서비스 대상 아님"
        description="식약처 기반 DB에서 일치하는 약물을 찾지 못했습니다. 공식 제품명, 성분명, 다른 표기명으로 다시 검색해주세요."
      />
    );
  }

  return (
    <div className="autocompleteList" aria-label="식약처 DB 약물 자동완성 결과">
      {results.map((drug) => (
        <YkDrugSearchResultItem
          key={`${drug.productCode}-${drug.itemSeq}-${drug.productName}`}
          onClick={() => onSelect(drug)}
          productName={drug.productName}
          companyName={`${drug.companyName || "업체명 없음"} · 품목코드 ${drug.itemSeq || "-"}`}
          code={drug.productCode || "-"}
        />
      ))}
    </div>
  );
}

function MedicationRow({
  medication,
  onEdit,
  onDelete
}: {
  medication: MedicationRecord;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="drugRow">
      <div>
        <strong>{medication.matchedProductName || medication.enteredDrugName}</strong>
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
      <div className="rowActions">
        <YkButton className="yk-button-compact" icon={Pencil} variant="secondary" type="button" onClick={onEdit}>
          수정
        </YkButton>
        <YkIconButton icon={Trash2} label="약물 삭제" tone="danger" onClick={onDelete} />
      </div>
    </div>
  );
}
