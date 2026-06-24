import { NextResponse } from "next/server";

const backendBaseUrl = (process.env.BACKEND_API_BASE_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  ""
);

export async function POST(request: Request) {
  const payload = await request.json();

  try {
    const response = await fetch(`${backendBaseUrl}/api/analysis/preview`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload),
      cache: "no-store"
    });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json(
      {
        detail:
          "분석 미리보기 백엔드에 연결할 수 없습니다. FastAPI를 8000번 포트로 실행하거나 BACKEND_API_BASE_URL을 설정해주세요."
      },
      { status: 503 }
    );
  }
}
