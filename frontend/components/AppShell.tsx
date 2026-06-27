"use client";

import { Activity, BookOpen, FileText, Pill, Plus } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

import { YkEmptyState, YkLoadingState } from "@/components/ui/design-system";

const navItems = [
  { href: "/", label: "서비스 안내", icon: BookOpen },
  { href: "/patients", label: "약 입력", icon: Plus },
  { href: "/reports", label: "리포트", icon: FileText }
];

function isActive(pathname: string, href: string) {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({
  children,
  title,
  subtitle,
  action
}: {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="yk-app-frame yk-product-shell">
      <header className="yk-topbar">
        <Link className="yk-brand" href="/">
          <span className="yk-brand-mark">
            <Pill size={20} />
          </span>
          <span>
            <strong>약손 AI</strong>
            <small>건강보험심사평가원·식약처 공공 데이터 기반</small>
          </span>
        </Link>

        <nav className="yk-tabs" aria-label="주요 메뉴">
          {navItems.map((item) => (
            <Link
              className={`yk-product-nav-link ${isActive(pathname, item.href) ? "is-active" : ""}`}
              href={item.href}
              key={item.href}
            >
              <item.icon size={15} />
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
      </header>

      <main className="yk-main">
        {(title || subtitle || action) && (
          <div className="yk-product-page-header">
            <div>
              {subtitle && <p>{subtitle}</p>}
              {title && <h1>{title}</h1>}
            </div>
            {action}
          </div>
        )}

        <div className="yk-product-content">{children}</div>
      </main>

      <footer className="yk-footer">
        본 결과는 공식 DUR 데이터를 바탕으로 한 복약 보조 참고 정보이며, 의사·약사의 최종 판단을 대체할 수 없습니다.
      </footer>
    </div>
  );
}

export function LoadingState() {
  return <YkLoadingState />;
}

export function EmptyState({
  title,
  description,
  action
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return <YkEmptyState title={title} description={description} action={action} />;
}
