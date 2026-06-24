import { NextResponse } from "next/server";

import { backendBaseUrl, backendHeaders, backendUnavailableDetail } from "../../_backend";

export async function POST(request: Request) {
  const payload = await request.json();

  try {
    const response = await fetch(`${backendBaseUrl}/api/analysis/preview`, {
      method: "POST",
      headers: backendHeaders({
        Accept: "application/json",
        "Content-Type": "application/json"
      }),
      body: JSON.stringify(payload),
      cache: "no-store"
    });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json(
      {
        detail: backendUnavailableDetail("분석 서버")
      },
      { status: 503 }
    );
  }
}
