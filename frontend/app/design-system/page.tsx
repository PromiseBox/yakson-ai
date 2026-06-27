"use client";

import { AlertCircle, CheckCircle2, Database, Pill, ShieldAlert, Sparkles } from "lucide-react";

import {
  YkAlertCard,
  YkAnalysisActionCard,
  YkAppFrame,
  YkBadge,
  YkButton,
  YkCard,
  YkDataSourceBadge,
  YkDrugSearchResultItem,
  YkEmptyState,
  YkErrorState,
  YkEvidenceTable,
  YkFormField,
  YkHistoryCard,
  YkInlineAlert,
  YkLoadingState,
  YkMedicationEntryCard,
  YkNoResultState,
  YkNoticeBox,
  YkPatientCard,
  YkReportHeaderBanner,
  YkReportSummaryBox,
  YkSectionHeader,
  YkSegmentedControl,
  YkSelectedMedicationList,
  YkStatusPill,
  YkTextarea,
  YkTextInput
} from "@/components/ui/design-system";

const selectedMedications = [
  { name: "아스피린정 100mg", detail: "혈전예방 및 해열소염제 · 30일 · 하루 1회" },
  { name: "이부프로펜정 400mg", detail: "소염진통제 · 5일 · 하루 3회" },
  { name: "디아제팜정 2mg", detail: "고령자 주의 약물 · 14일 · 취침 전" }
];

export default function DesignSystemPage() {
  return (
    <YkAppFrame savedCount={2}>
      <div className="yk-styleguide">
        <section className="yk-styleguide-hero">
          <div>
            <YkBadge tone="brand">Yakson Design System</YkBadge>
            <h1>보호자용 복약 안전 UI 컴포넌트</h1>
            <p>
              ui_prototype의 시각 언어를 Next.js 프론트엔드에 이식하기 위한 토큰과 컴포넌트 패턴입니다.
              실제 제품 화면은 변경하지 않고, 이 페이지에서 재사용 단위를 먼저 확인합니다.
            </p>
          </div>
          <YkDataSourceBadge />
        </section>

        <section className="yk-styleguide-grid">
          <YkCard>
            <YkSectionHeader title="Tokens" subtitle="브랜드, 상태, 표면 색상과 radius/shadow 기준" icon={Database} />
            <div className="yk-component-stack">
              <div className="yk-component-row">
                <YkBadge tone="brand">brand indigo</YkBadge>
                <YkBadge tone="safe">safe emerald</YkBadge>
                <YkBadge tone="danger">danger rose</YkBadge>
                <YkBadge tone="caution">caution amber</YkBadge>
                <YkBadge tone="neutral">neutral slate</YkBadge>
              </div>
              <YkNoticeBox title="토큰 적용 원칙" icon={AlertCircle}>
                slate는 정보 구조, indigo는 주요 행동, emerald는 안전/완료, rose와 amber는 위험 등급 표현에 사용합니다.
              </YkNoticeBox>
            </div>
          </YkCard>

          <YkCard>
            <YkSectionHeader title="Buttons" subtitle="명령 버튼과 상태 배지" icon={Sparkles} />
            <div className="yk-component-stack">
              <div className="yk-component-row">
                <YkButton icon={Sparkles}>분석하기</YkButton>
                <YkButton variant="secondary" icon={Pill}>
                  약 정보 수정
                </YkButton>
                <YkButton variant="danger" icon={ShieldAlert}>
                  삭제
                </YkButton>
                <YkButton variant="ghost">취소</YkButton>
              </div>
              <div className="yk-component-row">
                <YkStatusPill tone="danger" count={1}>
                  위험
                </YkStatusPill>
                <YkStatusPill tone="caution" count={2}>
                  주의
                </YkStatusPill>
                <YkStatusPill tone="safe" count={5}>
                  정상
                </YkStatusPill>
                <YkStatusPill tone="brand" count={3}>
                  등록 약물
                </YkStatusPill>
              </div>
            </div>
          </YkCard>

          <YkCard>
            <YkSectionHeader title="Forms" subtitle="입력, 선택, 보조 설명" icon={Pill} />
            <div className="yk-component-stack">
              <div className="yk-form-grid">
                <YkFormField label="어르신 성함 / 별칭" hint="보호자가 알아보기 쉬운 이름을 사용합니다.">
                  <YkTextInput defaultValue="햇살 어르신" />
                </YkFormField>
                <YkFormField label="성별">
                  <YkSegmentedControl
                    value="female"
                    options={[
                      { value: "male", label: "남성" },
                      { value: "female", label: "여성" },
                      { value: "unknown", label: "미입력" }
                    ]}
                  />
                </YkFormField>
              </div>
              <YkFormField label="특이사항 또는 앓고 계신 질환">
                <YkTextarea defaultValue="간 기능은 다소 약하시고, 밤에 잠을 잘 이루지 못하십니다." />
              </YkFormField>
            </div>
          </YkCard>

          <YkCard>
            <YkSectionHeader title="Feedback" subtitle="고지, 비어 있음, 로딩 상태" icon={AlertCircle} />
            <div className="yk-component-stack">
              <YkNoticeBox title="의료 전문가 대면 의견 대체 불가 고지" tone="caution">
                어떠한 처방 추가 혹은 복약 변경 결정도 반드시 주치의 또는 대면 조제 약사와 상담해야 합니다.
              </YkNoticeBox>
              <YkEmptyState
                title="등록된 복용자가 없습니다"
                description="복용자를 추가한 뒤 약 정보 입력 화면에서 식약처 DB 검색 결과를 선택해주세요."
                action={<YkButton>복용자 추가</YkButton>}
              />
              <YkErrorState
                title="서버 연결에 실패했습니다"
                description="백엔드 서버가 응답하지 않습니다. 잠시 뒤 다시 시도하거나 Cloud SQL 프록시와 API 서버 상태를 확인해주세요."
                action={<YkButton variant="secondary">다시 시도</YkButton>}
              />
              <YkNoResultState
                title="리포트 결과 주의사항 없음"
                description="현재 분석 기준에서는 위험 또는 주의 알림이 확인되지 않았습니다. 복용 약이 변경되면 다시 분석해주세요."
              />
              <YkInlineAlert title="최소 입력이 필요합니다" tone="caution">
                분석을 시작하려면 복용자 정보와 식약처 DB에서 선택한 약물 1개 이상이 필요합니다.
              </YkInlineAlert>
              <YkLoadingState />
            </div>
          </YkCard>

          <YkCard className="yk-full">
            <YkSectionHeader title="Medication Input Patterns" subtitle="약물 검색, 선택 목록, 분석 CTA" icon={Pill} />
            <div className="yk-styleguide-grid">
              <div className="yk-component-stack">
                <YkMedicationEntryCard />
                <YkDrugSearchResultItem productName="타이레놀정 500mg" companyName="한국얀센" code="ITEM-001" />
                <YkDrugSearchResultItem productName="아스피린정 100mg" companyName="바이엘코리아" code="ITEM-002" />
                <YkSelectedMedicationList items={selectedMedications} />
              </div>
              <YkAnalysisActionCard />
            </div>
          </YkCard>

          <YkCard className="yk-full">
            <YkSectionHeader title="Report Patterns" subtitle="리포트 헤더, 요약, 등급별 알림, 근거 테이블" icon={CheckCircle2} />
            <div className="yk-component-stack">
              <YkReportHeaderBanner />
              <YkReportSummaryBox />
              <YkAlertCard
                tone="danger"
                title="아스피린정 100mg + 이부프로펜정 400mg"
                category="병용금기"
                reason="두 약물은 출혈 위험과 위장관 부작용 가능성을 높일 수 있어 병용 시 전문가 확인이 필요합니다."
                guidance="임의로 중단하지 말고 처방 의료진 또는 약사에게 현재 복용 목록을 보여주며 상담하세요."
              />
              <YkAlertCard
                tone="caution"
                title="디아제팜정 2mg"
                category="노인부적절약물"
                reason="고령자에게 졸림, 낙상, 인지 저하 가능성이 있어 복용 후 상태 관찰이 필요합니다."
                guidance="어지러움, 비틀거림, 심한 졸림이 있으면 보호자가 기록하고 진료 시 전달하세요."
              />
              <YkEvidenceTable />
            </div>
          </YkCard>

          <YkCard>
            <YkSectionHeader title="Patient Card" subtitle="목록과 대시보드에서 쓰는 복용자 카드" icon={Pill} />
            <YkPatientCard name="햇살 어르신" meta="78세 · 여성" medicationCount={3} latestReportAt="최신 리포트 2026.06.26" />
          </YkCard>

          <YkCard>
            <YkSectionHeader title="History Card" subtitle="저장된 리포트 이력 패턴" icon={Pill} />
            <YkHistoryCard />
          </YkCard>
        </section>
      </div>
    </YkAppFrame>
  );
}
