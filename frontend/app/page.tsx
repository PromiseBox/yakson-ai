"use client";

import { AlertCircle, AlertTriangle, BookOpen, ChevronRight, Database, Pill, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";

import { AppShell } from "@/components/AppShell";
import { YkBadge, YkCard, YkDataSourceBadge, YkNoticeBox, YkSectionHeader } from "@/components/ui/design-system";

export default function HomePage() {
  return (
    <AppShell>
      <div className="yk-product-stack">
        <section className="yk-app-hero">
          <div>
            <YkBadge tone="brand">
              <Sparkles size={13} />
              대한민국 노인 안전 복약 전문 분석 시스템
            </YkBadge>
            <h1>어르신의 여러 처방전과 약봉투, 함께 드실 때 안전할까요?</h1>
            <p>
              보호자가 어르신의 복용 약을 등록하면 병용금기, 효능군 중복, 고령자 주의 위험을 한눈에 확인할 수
              있습니다. 식약처 DB에서 선택된 약물만 저장하고, 분석 결과는 상담 참고자료로 제공합니다.
            </p>
            <div className="yk-app-hero-actions">
              <Link className="yk-button yk-button-secondary" href="/patients">
                <span>복약 안전 점검 시작하기</span>
                <ChevronRight size={16} />
              </Link>
              <Link className="yk-button yk-button-ghost yk-app-hero-link" href="/reports">
                저장된 리포트 보기
              </Link>
            </div>
          </div>
          <YkDataSourceBadge />
        </section>

        <YkNoticeBox title="[보호자 필수 확인] 의료 전문가 대면 의견 대체 불가 고지" tone="caution" icon={AlertCircle}>
          본 서비스는 공인 가이드라인과 식약처 기반 데이터를 참조한 정보 전달 목적의 참고용 도구입니다. 처방
          변경, 복약 중단, 용량 조절은 반드시 주치의 또는 대면 조제 약사와 먼저 상담해야 합니다.
        </YkNoticeBox>

        <section className="yk-styleguide-grid">
          <YkCard>
            <YkSectionHeader title="핵심 점검 영역" subtitle="현재 구현된 룰 기반 분석 범위" icon={ShieldCheck} />
            <div className="yk-product-feature-list">
              <div>
                <span className="yk-product-feature-icon yk-feature-danger">
                  <AlertTriangle size={18} />
                </span>
                <strong>상호작용 및 병용금기</strong>
                <p>여러 진료과에서 처방받은 약물을 통합 대조하여 병용 주의군을 확인합니다.</p>
              </div>
              <div>
                <span className="yk-product-feature-icon yk-feature-caution">
                  <ShieldCheck size={18} />
                </span>
                <strong>고령자 주의 약물</strong>
                <p>낙상, 졸림, 인지 저하 등 고령자에게 민감한 위험 신호를 분류합니다.</p>
              </div>
              <div>
                <span className="yk-product-feature-icon yk-feature-safe">
                  <Pill size={18} />
                </span>
                <strong>효능군 중복 처방</strong>
                <p>동일 성분 또는 유사 효능군 중복 가능성을 리포트에 표시합니다.</p>
              </div>
            </div>
          </YkCard>

          <YkCard>
            <YkSectionHeader title="안전 점검 3단계" subtitle="보호자가 따라가는 실제 사용 흐름" icon={BookOpen} />
            <div className="yk-product-steps">
              <div>
                <span>01.</span>
                <strong>복용자 정보 입력</strong>
                <p>성명, 나이, 성별을 등록합니다.</p>
              </div>
              <div>
                <span>02.</span>
                <strong>식약처 DB 약물 선택</strong>
                <p>자동완성 후보에서 공식 약물을 선택합니다.</p>
              </div>
              <div>
                <span>03.</span>
                <strong>리포트 지참 후 상담</strong>
                <p>결과를 확인하고 주치의 또는 약사와 상담합니다.</p>
              </div>
            </div>
          </YkCard>
        </section>

        <section className="yk-styleguide-grid">
          <Link className="yk-card yk-product-link-card" href="/patients">
            <Database size={20} />
            <div>
              <strong>복용자 및 약 입력</strong>
              <p>복용자를 추가하고 식약처 DB 자동완성으로 약물 목록을 저장합니다.</p>
            </div>
            <ChevronRight size={18} />
          </Link>
          <Link className="yk-card yk-product-link-card" href="/reports">
            <BookOpen size={20} />
            <div>
              <strong>약 조회 및 리포트</strong>
              <p>등록된 복용자별 약 대시보드와 최신 분석 이력을 확인합니다.</p>
            </div>
            <ChevronRight size={18} />
          </Link>
        </section>
      </div>
    </AppShell>
  );
}
