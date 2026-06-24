import { NextResponse } from "next/server";

import { backendBaseUrl, backendHeaders, backendUnavailableDetail } from "../../_backend";

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
      headers: backendHeaders({ Accept: "application/json" }),
      cache: "no-store"
    });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json(
      {
        detail: backendUnavailableDetail("약물 검증 서버")
      },
      { status: 503 }
    );
  }
}
