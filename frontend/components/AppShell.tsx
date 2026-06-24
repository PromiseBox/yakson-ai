"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

const navItems = [
  { href: "/", label: "홈", icon: "홈" },
  { href: "/patients", label: "입력", icon: "+" },
  { href: "/reports", label: "조회", icon: "표" }
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
    <div className="siteShell">
      <aside className="sidebar" aria-label="주요 메뉴">
        <Link className="brand" href="/">
          <span className="brandMark">약</span>
          <span>
            <strong>약손 AI</strong>
            <small>복약 안전 리포트</small>
          </span>
        </Link>
        <nav className="sideNav">
          {navItems.map((item) => (
            <Link
              className={`sideNavItem ${isActive(pathname, item.href) ? "active" : ""}`}
              href={item.href}
              key={item.href}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="sideNote">
          <strong>안전 원칙</strong>
          <span>식약처 기반 DB에서 선택된 약물만 분석하고, AI는 설명 보조로만 사용합니다.</span>
        </div>
      </aside>

      <div className="mainArea">
        <header className="mobileHeader">
          <Link className="mobileBrand" href="/">
            <span className="brandMark">약</span>
            <strong>약손 AI</strong>
          </Link>
          {action}
        </header>

        {(title || subtitle || action) && (
          <div className="pageHeader">
            <div>
              {subtitle && <p className="eyebrow">{subtitle}</p>}
              {title && <h1>{title}</h1>}
            </div>
            <div className="desktopOnly">{action}</div>
          </div>
        )}

        <main className="webContent">{children}</main>
      </div>

      <nav className="mobileNav" aria-label="하단 메뉴">
        {navItems.map((item) => (
          <Link
            className={`mobileNavItem ${isActive(pathname, item.href) ? "active" : ""}`}
            href={item.href}
            key={item.href}
          >
            <span>{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}

export function LoadingState() {
  return (
    <div className="emptyState">
      <strong>불러오는 중</strong>
      <p>화면 데이터를 확인하고 있습니다.</p>
    </div>
  );
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
  return (
    <div className="emptyState">
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}
