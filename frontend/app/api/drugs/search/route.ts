import { NextResponse } from "next/server";

import { backendBaseUrl, backendHeaders, backendUnavailableDetail } from "../../_backend";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get("q") ?? "";
  const limit = searchParams.get("limit") ?? "15";

  if (q.trim().length < 2) {
    return NextResponse.json({ items: [] });
  }

  try {
    const response = await fetch(
      `${backendBaseUrl}/api/drugs/search?q=${encodeURIComponent(q)}&limit=${encodeURIComponent(limit)}`,
      {
        headers: backendHeaders({
          Accept: "application/json"
        }),
        cache: "no-store"
      }
    );

    if (!response.ok) {
      const contentType = response.headers.get("content-type") ?? "";
      let detail = "약명 검색 요청에 실패했습니다. 잠시 후 다시 시도해주세요.";
      if (contentType.includes("application/json")) {
        const body = (await response.json()) as { detail?: unknown };
        if (typeof body.detail === "string") {
          detail = body.detail;
        }
      } else {
        detail = (await response.text()) || detail;
      }
      return NextResponse.json(
        { detail },
        { status: response.status }
      );
    }

    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json(
      {
        detail: backendUnavailableDetail("약명 검색 서버")
      },
      { status: 503 }
    );
  }
}
