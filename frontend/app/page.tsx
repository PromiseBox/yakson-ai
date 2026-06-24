import Link from "next/link";

import { AppShell } from "@/components/AppShell";

export default function HomePage() {
  return (
    <AppShell>
      <section className="heroGrid">
        <div className="heroPanel">
          <p className="eyebrow">노인 복약 안전을 위한 출처 있는 AI 리포트</p>
          <h1>복용자와 약 정보를 입력하고 위험 리포트를 확인하세요</h1>
          <p className="subtext">
            보호자가 어르신의 복용 약을 등록하면 병용금기, 효능군 중복, 노인 부적절약물 위험을
            한눈에 확인할 수 있습니다. 프론트는 mock 데이터로 먼저 동작하며 이후 API만 연결하면 됩니다.
          </p>

          <div className="heroActions">
            <Link className="button primary" href="/patients">
              복용자 및 약 입력
            </Link>
            <Link className="button secondary" href="/reports">
              약 조회 및 리포트
            </Link>
          </div>
        </div>

        <div className="statStack">
          <div className="statCard">
            <div>
              <strong>3단계</strong>
              <span>복용자 관리 → 약 입력 → 리포트 조회</span>
            </div>
          </div>
          <div className="statCard">
            <div>
              <strong>7종</strong>
              <span>병용금기·PIM·효능군 중복 등 위험 유형 UI</span>
            </div>
          </div>
          <div className="guidance">
            <strong>진단 금지 라우팅</strong>
            <br />
            화면의 모든 문구는 진단이나 처방이 아닌 상담 참고자료로 표현됩니다.
          </div>
        </div>
      </section>

      <section className="section" style={{ marginTop: 22 }}>
        <div className="cardGrid">
          <Link className="quickLink" href="/patients">
            <strong>입력 흐름</strong>
            <p className="subtext">복용자 추가, 정보 수정, 약 정보 등록과 삭제를 진행합니다.</p>
          </Link>
          <Link className="quickLink" href="/reports">
            <strong>조회 흐름</strong>
            <p className="subtext">등록된 복용자별 약 대시보드와 AI 리포트를 확인합니다.</p>
          </Link>
        </div>
      </section>
    </AppShell>
  );
}
