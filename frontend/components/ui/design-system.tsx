"use client";

import {
  AlertCircle,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  CircleSlash,
  Clipboard,
  Database,
  FileText,
  LucideIcon,
  Pill,
  Plus,
  ShieldAlert,
  Sparkles,
  Trash2,
  User
} from "lucide-react";
import { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

type Tone = "brand" | "safe" | "danger" | "caution" | "neutral";
type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type StatusTone = "danger" | "caution" | "safe" | "neutral" | "brand";

const statusIcons: Record<StatusTone, LucideIcon> = {
  danger: ShieldAlert,
  caution: AlertTriangle,
  safe: CheckCircle2,
  neutral: AlertCircle,
  brand: Sparkles
};

export function YkAppFrame({
  children,
  active = "guide",
  savedCount = 0
}: {
  children: ReactNode;
  active?: "guide" | "input" | "reports";
  savedCount?: number;
}) {
  const items = [
    { id: "guide", label: "서비스 안내", icon: BookOpen },
    { id: "input", label: "약 입력", icon: Pill },
    { id: "reports", label: "리포트", icon: FileText }
  ] as const;

  return (
    <div className="yk-app-frame">
      <header className="yk-topbar">
        <div className="yk-brand">
          <span className="yk-brand-mark">
            <Pill size={20} />
          </span>
          <span>
            <strong>약손 AI</strong>
            <small>건강보험심사평가원·식약처 공공 데이터 기반</small>
          </span>
        </div>

        <nav className="yk-tabs" aria-label="디자인 시스템 확인 메뉴">
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <button className={`yk-tab ${active === item.id ? "is-active" : ""}`} key={item.id} type="button">
                <Icon size={15} />
                <span>{item.label}</span>
                {item.id === "reports" && savedCount > 0 && <em>{savedCount}</em>}
              </button>
            );
          })}
        </nav>
      </header>
      <main className="yk-main">{children}</main>
      <footer className="yk-footer">
        본 결과는 공식 DUR 데이터를 바탕으로 한 복약 보조 참고 정보이며, 의사·약사의 최종 판단을 대체할 수 없습니다.
      </footer>
    </div>
  );
}

export function YkButton({
  variant = "primary",
  icon: Icon,
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  icon?: LucideIcon;
}) {
  return (
    <button className={`yk-button yk-button-${variant} ${className}`} type="button" {...props}>
      {Icon && <Icon size={16} />}
      <span>{children}</span>
    </button>
  );
}

export function YkIconButton({
  label,
  icon: Icon,
  tone = "neutral",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  icon: LucideIcon;
  tone?: Tone;
}) {
  return (
    <button className={`yk-icon-button yk-tone-${tone}`} type="button" aria-label={label} title={label} {...props}>
      <Icon size={16} />
    </button>
  );
}

export function YkCard({
  children,
  tone = "neutral",
  className = ""
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return <section className={`yk-card yk-card-${tone} ${className}`}>{children}</section>;
}

export function YkSectionHeader({
  title,
  subtitle,
  icon: Icon,
  action
}: {
  title: string;
  subtitle?: string;
  icon?: LucideIcon;
  action?: ReactNode;
}) {
  return (
    <div className="yk-section-header">
      <div>
        <h2>
          {Icon && <Icon size={19} />}
          <span>{title}</span>
        </h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function YkBadge({
  children,
  tone = "brand"
}: {
  children: ReactNode;
  tone?: StatusTone;
}) {
  return <span className={`yk-badge yk-status-${tone}`}>{children}</span>;
}

export function YkStatusPill({
  children,
  tone = "neutral",
  count
}: {
  children: ReactNode;
  tone?: StatusTone;
  count?: number;
}) {
  const Icon = statusIcons[tone];
  return (
    <span className={`yk-status-pill yk-status-${tone}`}>
      <Icon size={14} />
      <span>{children}</span>
      {typeof count === "number" && <strong>{count}</strong>}
    </span>
  );
}

export function YkNoticeBox({
  title,
  children,
  tone = "brand",
  icon: Icon = AlertCircle
}: {
  title: string;
  children: ReactNode;
  tone?: Tone;
  icon?: LucideIcon;
}) {
  return (
    <aside className={`yk-notice yk-notice-${tone}`}>
      <Icon size={19} />
      <div>
        <strong>{title}</strong>
        <p>{children}</p>
      </div>
    </aside>
  );
}

export function YkFormField({
  label,
  hint,
  children
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="yk-field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export function YkTextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className="yk-input" {...props} />;
}

export function YkTextarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className="yk-textarea" {...props} />;
}

export function YkSegmentedControl({
  value,
  options,
  onChange
}: {
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange?: (value: string) => void;
}) {
  return (
    <div className="yk-segmented">
      {options.map((option) => (
        <button
          className={`yk-segment ${value === option.value ? "is-selected" : ""}`}
          key={option.value}
          type="button"
          onClick={() => onChange?.(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function YkEmptyState({
  title,
  description,
  action
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="yk-empty">
      <BookOpen size={38} />
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function YkLoadingState({ label = "화면 데이터를 확인하고 있습니다." }: { label?: string }) {
  return (
    <div className="yk-loading">
      <span />
      <strong>불러오는 중</strong>
      <p>{label}</p>
    </div>
  );
}

export function YkErrorState({
  title = "서버 응답을 불러오지 못했습니다",
  description = "잠시 뒤 다시 시도해주세요. 문제가 계속되면 네트워크 상태와 백엔드 서버를 확인합니다.",
  action
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="yk-feedback-state yk-feedback-error">
      <div className="yk-feedback-icon">
        <AlertCircle size={24} />
      </div>
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function YkNoResultState({
  title = "확인된 주의사항이 없습니다",
  description = "현재 입력된 조건에서는 표시할 리포트 결과가 없습니다. 약물 목록이 바뀌면 다시 분석해주세요.",
  action
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="yk-feedback-state yk-feedback-empty-result">
      <div className="yk-feedback-icon">
        <CircleSlash size={24} />
      </div>
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function YkInlineAlert({
  title,
  children,
  tone = "caution",
  icon: Icon
}: {
  title: string;
  children: ReactNode;
  tone?: StatusTone;
  icon?: LucideIcon;
}) {
  const FallbackIcon = statusIcons[tone];
  const AlertIcon = Icon ?? FallbackIcon;
  return (
    <div className={`yk-inline-alert yk-status-${tone}`} role="alert">
      <AlertIcon size={16} />
      <div>
        <strong>{title}</strong>
        <p>{children}</p>
      </div>
    </div>
  );
}

export function YkPatientCard({
  name,
  meta,
  medicationCount,
  latestReportAt
}: {
  name: string;
  meta: string;
  medicationCount: number;
  latestReportAt?: string;
}) {
  return (
    <YkCard className="yk-patient-card">
      <div className="yk-avatar-row">
        <span className="yk-avatar">
          <User size={18} />
        </span>
        <div>
          <strong>{name}</strong>
          <p>{meta}</p>
        </div>
      </div>
      <div className="yk-card-meta">
        <YkStatusPill tone="brand" count={medicationCount}>
          등록 약물
        </YkStatusPill>
        <span>{latestReportAt ?? "리포트 없음"}</span>
      </div>
    </YkCard>
  );
}

export function YkMedicationEntryCard() {
  return (
    <YkCard>
      <YkSectionHeader
        title="복용 중인 약 입력"
        subtitle="식약처 DB 자동완성에서 선택된 약만 저장합니다."
        icon={Pill}
        action={<YkButton icon={Plus}>추가</YkButton>}
      />
      <div className="yk-form-grid">
        <YkFormField label="약 제품명">
          <YkTextInput placeholder="예: 타이레놀정 500mg" />
        </YkFormField>
        <YkFormField label="복용 구분">
          <YkSegmentedControl
            value="internal"
            options={[
              { value: "internal", label: "내과" },
              { value: "ortho", label: "정형외과" },
              { value: "other", label: "기타" }
            ]}
          />
        </YkFormField>
      </div>
    </YkCard>
  );
}

export function YkDrugSearchResultItem({
  productName,
  companyName,
  code
}: {
  productName: string;
  companyName: string;
  code: string;
}) {
  return (
    <button className="yk-drug-result" type="button">
      <span>
        <strong>{productName}</strong>
        <small>{companyName}</small>
      </span>
      <YkBadge tone="brand">{code}</YkBadge>
    </button>
  );
}

export function YkSelectedMedicationList({
  items
}: {
  items: Array<{ name: string; detail: string }>;
}) {
  return (
    <div className="yk-selected-list">
      {items.map((item) => (
        <div className="yk-selected-row" key={item.name}>
          <span>
            <strong>{item.name}</strong>
            <small>{item.detail}</small>
          </span>
          <YkIconButton icon={Trash2} label={`${item.name} 삭제`} tone="danger" />
        </div>
      ))}
    </div>
  );
}

export function YkAnalysisActionCard({
  disabled
}: {
  disabled?: boolean;
}) {
  return (
    <section className="yk-action-card">
      <YkBadge tone="brand">약손 AI 고령 투약 자가안전계획</YkBadge>
      <h3>식약처 DUR 데이터 정밀조사</h3>
      <p>입력된 약 목록을 안전 데이터베이스와 대조하여 병용금기, 고령자 주의, 효능군 중복을 확인합니다.</p>
      <YkButton disabled={disabled} icon={Sparkles} variant="secondary">
        사랑하는 어르신 약 점검하기
      </YkButton>
    </section>
  );
}

export function YkReportHeaderBanner() {
  return (
    <YkCard className="yk-report-banner">
      <div>
        <YkBadge tone="safe">DUR 안전 점검성평가 완료</YkBadge>
        <h2>
          <Pill size={24} />
          햇살 어르신의 안심 복약 리포트
        </h2>
        <p>만 78세 · 여성 · 처방: 백세가정의원 · 복용 시작일: 2026-06-26</p>
      </div>
      <YkButton icon={Clipboard} variant="secondary">
        리포트 복사
      </YkButton>
    </YkCard>
  );
}

export function YkReportSummaryBox() {
  return (
    <div className="yk-summary-box">
      <div>
        <span>DUR 검진 한줄요약</span>
        <strong>병용 주의 1건과 고령자 주의 1건이 확인되었습니다.</strong>
      </div>
      <div className="yk-summary-pills">
        <YkStatusPill tone="danger" count={1}>
          위험
        </YkStatusPill>
        <YkStatusPill tone="caution" count={1}>
          주의
        </YkStatusPill>
        <YkStatusPill tone="safe" count={3}>
          정상
        </YkStatusPill>
      </div>
    </div>
  );
}

export function YkAlertCard({
  tone,
  title,
  category,
  reason,
  guidance
}: {
  tone: "danger" | "caution" | "safe";
  title: string;
  category: string;
  reason: string;
  guidance: string;
}) {
  const label = tone === "danger" ? "위험" : tone === "caution" ? "주의" : "정상";
  return (
    <article className={`yk-alert-card yk-alert-${tone}`}>
      <header>
        <div>
          <YkBadge tone={tone}>{label}</YkBadge>
          <h3>{title}</h3>
        </div>
        <YkBadge tone={tone}>{category}</YkBadge>
      </header>
      <div className="yk-alert-body">
        <section>
          <span>DUR 주의 감지 원인</span>
          <p>{reason}</p>
        </section>
        <section>
          <span>보호자 안심 케어 행동 요령</span>
          <p>{guidance}</p>
        </section>
      </div>
    </article>
  );
}

export function YkEvidenceTable() {
  const rows = [
    ["아스피린정 100mg", "이부프로펜정 400mg", "NSAIDs 병용 주의"],
    ["디아제팜정 2mg", "고령자 기준", "낙상 및 인지 저하 주의"]
  ];

  return (
    <div className="yk-table-wrap">
      <table className="yk-table">
        <thead>
          <tr>
            <th>대상 약물</th>
            <th>비교 기준</th>
            <th>근거</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.join("-")}>
              {row.map((cell) => (
                <td key={cell}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function YkHistoryCard() {
  return (
    <YkCard className="yk-history-card">
      <div>
        <YkBadge tone="brand">햇살 어르신 · 78세</YkBadge>
        <h3>검토 약품 3종</h3>
        <p>아스피린정, 이부프로펜정, 디아제팜정</p>
      </div>
      <div className="yk-card-meta">
        <span>2026.06.26 20:54</span>
        <span>
          자세히 보기 <ChevronRight size={13} />
        </span>
      </div>
    </YkCard>
  );
}

export function YkDataSourceBadge() {
  return (
    <div className="yk-data-badge">
      <Database size={20} />
      <div>
        <strong>국가 표준 준수</strong>
        <span>식약처 및 건강보험심사평가원 DUR 공식 가이드라인 기반</span>
      </div>
    </div>
  );
}
