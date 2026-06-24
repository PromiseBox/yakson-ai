import { NextResponse } from "next/server";

import { buildDemoReport } from "@/lib/mock";

export async function GET(
  _: Request,
  context: { params: Promise<{ id: string }> }
) {
  const params = await context.params;

  if (params.id === "demo-latest") {
    return NextResponse.json(buildDemoReport());
  }

  return NextResponse.json({ detail: "Report not found." }, { status: 404 });
}
