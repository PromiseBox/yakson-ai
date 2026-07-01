"use client";

import { Database, FileText, Pencil, Pill, Plus, Trash2, Upload } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

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
import {
  groupMedicationsByCategory,
  mergePrescriptionCategories,
  prescriptionCategories,
  sexLabel
} from "@/lib/app-store";
import {
  createMedicationOnServer,
  deleteMedicationOnServer,
  extractMedicationCandidatesFromImage,
  getPatientById,
  listPrescriptionCategories,
  listPatientMedications,
  searchDrugs,
  updateMedicationOnServer,
  validateDrug
} from "@/lib/api";
import { toUserErrorMessage } from "@/lib/error-messages";
import {
  DrugSearchItem,
  MedicationOcrCandidate,
  MedicationRecord,
  PatientRecord,
  PrescriptionCategory
} from "@/lib/types";

const DEFAULT_CATEGORY = "내과";
const CUSTOM_CATEGORY = "기타";

type OcrCandidateView = MedicationOcrCandidate & {
  matches: DrugSearchItem[];
  matchError?: string;
};

function resolveCategoryName(category: PrescriptionCategory, customCategory: string) {
  if (category === CUSTOM_CATEGORY) {
    return customCategory.trim();
  }
  return category.trim();
}

export default function MedicationInputPage() {
  const params = useParams<{ id: string }>();
  const patientId = Array.isArray(params.id) ? params.id[0] : params.id;
  const [patient, setPatient] = useState<PatientRecord | null>(null);
  const [medications, setMedications] = useState<MedicationRecord[]>([]);
  const [savedCategories, setSavedCategories] = useState<PrescriptionCategory[]>(prescriptionCategories);
  const [category, setCategory] = useState<PrescriptionCategory>(DEFAULT_CATEGORY);
  const [customCategory, setCustomCategory] = useState("");
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
  const [editCategory, setEditCategory] = useState<PrescriptionCategory>(DEFAULT_CATEGORY);
  const [editCustomCategory, setEditCustomCategory] = useState("");
  const [editDurationDays, setEditDurationDays] = useState("");
  const [editDosesPerDay, setEditDosesPerDay] = useState("");
  const [editDoseAmount, setEditDoseAmount] = useState("");
  const [editDoseUnit, setEditDoseUnit] = useState("");
  const [editError, setEditError] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [isOcrProcessing, setIsOcrProcessing] = useState(false);
  const [ocrFileName, setOcrFileName] = useState("");
  const [ocrCandidates, setOcrCandidates] = useState<OcrCandidateView[]>([]);
  const [ocrWarnings, setOcrWarnings] = useState<string[]>([]);
  const [ocrError, setOcrError] = useState("");

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
  const categoryOptions = useMemo(
    () =>
      mergePrescriptionCategories(
        prescriptionCategories,
        savedCategories,
        medications.map((medication) => medication.category),
        category !== CUSTOM_CATEGORY ? [category] : [],
        editCategory !== CUSTOM_CATEGORY ? [editCategory] : []
      ),
    [category, editCategory, medications, savedCategories]
  );
  const medicationCountByCategory = useMemo(() => {
    const counts = new Map<string, number>();
    for (const medication of medications) {
      counts.set(medication.category, (counts.get(medication.category) ?? 0) + 1);
    }
    return counts;
  }, [medications]);
  const activeCategoryName = resolveCategoryName(category, customCategory);
  const activeCategoryLabel = activeCategoryName || CUSTOM_CATEGORY;

  async function refreshPage() {
    setIsLoading(true);
    setPageError("");
    try {
      const [nextPatient, nextMedications, nextCategories] = await Promise.all([
        getPatientById(patientId),
        listPatientMedications(patientId),
        listPrescriptionCategories()
      ]);
      setPatient(nextPatient);
      setMedications(nextMedications);
      setSavedCategories(nextCategories);
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

  async function handleOcrFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }

    if (!file.type.startsWith("image/")) {
      setOcrError("JPG, PNG, WEBP 이미지 파일을 업로드해주세요.");
      setOcrCandidates([]);
      setOcrWarnings([]);
      return;
    }

    setIsOcrProcessing(true);
    setOcrFileName(file.name);
    setOcrError("");
    setOcrWarnings([]);
    setOcrCandidates([]);
    setNotice("");

    try {
      const result = await extractMedicationCandidatesFromImage(file);
      const enrichedCandidates = await Promise.all(
        result.candidates.map(async (candidate) => {
          try {
            const matches = await searchDrugs(candidate.enteredDrugName, 5);
            return { ...candidate, matches };
          } catch (caught) {
            return {
              ...candidate,
              matches: [],
              matchError: toUserErrorMessage(caught, "식약처 DB 검색에 실패했습니다.")
            };
          }
        })
      );
      setOcrCandidates(enrichedCandidates);
      setOcrWarnings(result.warnings);
      if (enrichedCandidates.length === 0) {
        setOcrError("약명 후보를 찾지 못했습니다. 더 선명한 사진으로 다시 시도하거나 약명을 직접 입력해주세요.");
      }
    } catch (caught) {
      setOcrCandidates([]);
      setOcrWarnings([]);
      setOcrError(toUserErrorMessage(caught, "사진에서 약 정보를 읽지 못했습니다."));
    } finally {
      setIsOcrProcessing(false);
    }
  }

  function applyOcrCandidate(candidate: OcrCandidateView, drug: DrugSearchItem) {
    const nextCategoryName = candidate.categoryName?.trim();
    if (nextCategoryName) {
      if (categoryOptions.includes(nextCategoryName)) {
        setCategory(nextCategoryName);
        setCustomCategory("");
      } else {
        setCategory(CUSTOM_CATEGORY);
        setCustomCategory(nextCategoryName);
      }
    }
    setDrugName(drug.productName);
    setSelectedDrug(drug);
    setSearchResults([]);
    setSearchError("");
    setDurationDays(String(candidate.durationDays ?? 30));
    setDosesPerDay(String(candidate.dosesPerDay ?? 1));
    setDoseAmount(String(candidate.doseAmount ?? 1));
    setDoseUnit(candidate.doseUnit?.trim() || "정");
    setError("");
    setNotice("OCR 후보를 입력폼에 불러왔습니다. 내용을 확인한 뒤 저장해주세요.");
  }

  function searchOcrCandidateManually(candidate: OcrCandidateView) {
    setDrugName(candidate.enteredDrugName);
    setSelectedDrug(null);
    setSearchResults([]);
    setDurationDays(String(candidate.durationDays ?? 30));
    setDosesPerDay(String(candidate.dosesPerDay ?? 1));
    setDoseAmount(String(candidate.doseAmount ?? 1));
    setDoseUnit(candidate.doseUnit?.trim() || "정");
    setError("");
    setNotice("OCR 약명 후보를 검색창에 넣었습니다. 식약처 DB 결과를 선택해주세요.");
  }

  function handleDrugNameChange(value: string) {
    setDrugName(value);
    setSelectedDrug(null);
    setError("");
    setNotice("");
  }

  function selectCategory(nextCategory: PrescriptionCategory) {
    setCategory(nextCategory);
    if (nextCategory !== CUSTOM_CATEGORY) {
      setCustomCategory("");
    }
    setError("");
    setNotice("");
  }

  function selectEditCategory(nextCategory: PrescriptionCategory) {
    setEditCategory(nextCategory);
    if (nextCategory !== CUSTOM_CATEGORY) {
      setEditCustomCategory("");
    }
    setEditError("");
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

    const nextCategoryName = resolveCategoryName(category, customCategory);
    if (!nextCategoryName) {
      setError("기타 항목명을 입력해주세요.");
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
        categoryName: nextCategoryName,
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
      setCategory(nextCategoryName);
      setCustomCategory("");
      setSavedCategories((current) => mergePrescriptionCategories(current, [nextCategoryName]));
      setNotice(`${nextCategoryName} 항목에 약 정보를 저장했습니다.`);
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
    setEditCustomCategory("");
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

    const nextCategoryName = resolveCategoryName(editCategory, editCustomCategory);
    if (!nextCategoryName) {
      setEditError("기타 항목명을 입력해주세요.");
      return;
    }

    setIsEditing(true);
    setEditError("");

    try {
      await updateMedicationOnServer(editTarget.id, {
        categoryName: nextCategoryName,
        durationDays: parsedDuration,
        dosesPerDay: parsedDoses,
        doseAmount: parsedAmount,
        doseUnit: editDoseUnit.trim() || "정"
      });
      setEditTarget(null);
      setSavedCategories((current) => mergePrescriptionCategories(current, [nextCategoryName]));
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

            <section className="yk-ocr-assist">
              <div className="yk-ocr-assist-header">
                <div>
                  <strong>사진으로 입력 보조</strong>
                  <p>약봉지나 처방전 사진에서 약명 후보를 읽고 식약처 DB 검색 결과로 연결합니다.</p>
                </div>
                <label className={`yk-button yk-button-secondary yk-button-compact ${isOcrProcessing ? "disabled" : ""}`}>
                  <Upload size={15} />
                  {isOcrProcessing ? "읽는 중" : "사진 업로드"}
                  <input
                    className="yk-file-input"
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    disabled={isOcrProcessing}
                    onChange={handleOcrFileChange}
                  />
                </label>
              </div>

              {ocrFileName && <p className="subtext">최근 파일 {ocrFileName}</p>}
              {ocrError && (
                <YkInlineAlert title="OCR 확인 필요" tone="caution">
                  {ocrError}
                </YkInlineAlert>
              )}
              {ocrWarnings.map((warning) => (
                <YkInlineAlert title="OCR 안내" tone="caution" key={warning}>
                  {warning}
                </YkInlineAlert>
              ))}
              {ocrCandidates.length > 0 && (
                <div className="yk-ocr-candidate-list">
                  {ocrCandidates.map((candidate) => (
                    <OcrCandidateCard
                      candidate={candidate}
                      key={candidate.candidateId}
                      onApply={applyOcrCandidate}
                      onManualSearch={searchOcrCandidateManually}
                    />
                  ))}
                </div>
              )}
            </section>

            <form className="stack yk-product-form" onSubmit={submitMedication}>
              <CategorySelector
                categories={categoryOptions}
                selectedCategory={category}
                counts={medicationCountByCategory}
                onSelect={selectCategory}
              />

              {category === CUSTOM_CATEGORY && (
                <label className="fieldLabel">
                  기타 항목명
                  <input
                    className="input"
                    value={customCategory}
                    onChange={(event) => {
                      setCustomCategory(event.target.value);
                      setError("");
                    }}
                    placeholder="예: A병원, 피부과, 한의원"
                    maxLength={30}
                  />
                </label>
              )}

              <div className="activeCategoryBar">
                <span>입력 항목</span>
                <strong>{activeCategoryLabel}</strong>
                <span>{medicationCountByCategory.get(activeCategoryName) ?? 0}개</span>
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

              <YkButton
                icon={Plus}
                type="submit"
                disabled={isAdding || !selectedDrug || (category === CUSTOM_CATEGORY && !customCategory.trim())}
              >
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
                      <div className="rowActions">
                        <YkButton
                          className="yk-button-compact"
                          variant="secondary"
                          type="button"
                          onClick={() => selectCategory(group.category)}
                        >
                          입력
                        </YkButton>
                      </div>
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
              <CategorySelector
                categories={categoryOptions}
                selectedCategory={editCategory}
                counts={medicationCountByCategory}
                onSelect={selectEditCategory}
              />

              {editCategory === CUSTOM_CATEGORY && (
                <label className="fieldLabel">
                  기타 항목명
                  <input
                    className="input"
                    value={editCustomCategory}
                    onChange={(event) => {
                      setEditCustomCategory(event.target.value);
                      setEditError("");
                    }}
                    placeholder="예: A병원, 피부과, 한의원"
                    maxLength={30}
                  />
                </label>
              )}

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

function OcrCandidateCard({
  candidate,
  onApply,
  onManualSearch
}: {
  candidate: OcrCandidateView;
  onApply: (candidate: OcrCandidateView, drug: DrugSearchItem) => void;
  onManualSearch: (candidate: OcrCandidateView) => void;
}) {
  return (
    <article className="yk-ocr-candidate">
      <header>
        <div>
          <strong>{candidate.enteredDrugName}</strong>
          <p>{candidate.sourceLine}</p>
        </div>
        <YkStatusPill tone={candidate.needsReview ? "caution" : "safe"}>
          {Math.round(candidate.confidence * 100)}%
        </YkStatusPill>
      </header>
      <div className="yk-ocr-dose-row">
        <span>{candidate.durationDays ? `${candidate.durationDays}일` : "일수 확인"}</span>
        <span>{candidate.dosesPerDay ? `하루 ${candidate.dosesPerDay}회` : "횟수 확인"}</span>
        <span>
          {candidate.doseAmount ? `1회 ${candidate.doseAmount}${candidate.doseUnit ?? ""}` : "용량 확인"}
        </span>
      </div>

      {candidate.matchError && (
        <p className="yk-ocr-match-error">{candidate.matchError}</p>
      )}

      {candidate.matches.length > 0 ? (
        <div className="yk-ocr-match-list">
          {candidate.matches.slice(0, 3).map((drug) => (
            <button
              className="yk-ocr-match-button"
              type="button"
              key={`${candidate.candidateId}-${drug.productCode}-${drug.itemSeq}`}
              onClick={() => onApply(candidate, drug)}
            >
              <strong>{drug.productName}</strong>
              <span>
                {drug.companyName || "업체명 없음"} · 제품코드 {drug.productCode || "-"}
              </span>
            </button>
          ))}
        </div>
      ) : (
        <button className="yk-button yk-button-secondary yk-button-compact" type="button" onClick={() => onManualSearch(candidate)}>
          약명으로 검색
        </button>
      )}
    </article>
  );
}

function CategorySelector({
  categories,
  selectedCategory,
  counts,
  onSelect
}: {
  categories: PrescriptionCategory[];
  selectedCategory: PrescriptionCategory;
  counts: Map<string, number>;
  onSelect: (category: PrescriptionCategory) => void;
}) {
  return (
    <div className="fieldLabel">
      입력 항목
      <div className="categoryPicker" role="tablist" aria-label="약 입력 항목">
        {categories.map((item) => (
          <button
            className={`categoryTab ${selectedCategory === item ? "selected" : ""}`}
            key={item}
            type="button"
            role="tab"
            aria-selected={selectedCategory === item}
            onClick={() => onSelect(item)}
          >
            <span>{item}</span>
            <small>{item === CUSTOM_CATEGORY ? "직접 입력" : `${counts.get(item) ?? 0}개`}</small>
          </button>
        ))}
      </div>
    </div>
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
