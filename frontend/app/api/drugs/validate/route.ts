import { NextResponse } from "next/server";

const backendBaseUrl = (process.env.BACKEND_API_BASE_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  ""
);

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const productCode = searchParams.get("productCode") ?? "";
  const itemSeq = searchParams.get("itemSeq") ?? "";

  if (!productCode && !itemSeq) {
    return NextResponse.json({ detail: "약물 검증에는 제품코드 또는 품목코드가 필요합니다." }, { status: 400 });
  }

  const params = new URLSearchParams();
  if (productCode) {
    params.set("productCode", productCode);
  }
  if (itemSeq) {
    params.set("itemSeq", itemSeq);
  }

  try {
    const response = await fetch(`${backendBaseUrl}/api/drugs/validate?${params.toString()}`, {
      headers: { Accept: "application/json" },
      cache: "no-store"
    });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json(
      {
        detail:
          "약물 검증 백엔드에 연결할 수 없습니다. FastAPI를 8000번 포트로 실행하거나 BACKEND_API_BASE_URL을 설정해주세요."
      },
      { status: 503 }
    );
  }
}
