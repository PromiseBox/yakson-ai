import { NextResponse } from "next/server";

import { buildMockReport } from "@/lib/mock";
import type { AnalyzeRequest } from "@/lib/types";

export async function POST(request: Request) {
  const payload = (await request.json()) as AnalyzeRequest;

  if (!payload.patient?.displayName || !payload.medications?.length) {
    return NextResponse.json({ detail: "Patient and medications are required." }, { status: 400 });
  }

  return NextResponse.json(buildMockReport(payload));
}
